r"""
Pyjo.Server.ASGI - ASGI server
==============================
::

    from Pyjo.Server.ASGI import ASGI

    asgi = ASGI()
    asgi.unsubscribe('request')

    @asgi.on('request')
    def request(asgi, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()

    app = asgi.to_asgi_app()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Server.ASGI

    asgi = Pyjo.Server.ASGI.new()
    asgi.unsubscribe('request')

    @asgi.on('request')
    def request(asgi, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()

    app = asgi.to_asgi_app()

    # uvicorn myapp:app
    # hypercorn myapp:app

:mod:`Pyjo.Server.ASGI` allows :mod:`Pyjoyment` applications to run on all
`ASGI <https://asgi.readthedocs.io>`_ compatible servers, with HTTP,
WebSocket and lifespan connections.

The application runs in the event loop of the ASGI server: the reactor of
:mod:`Pyjo.IOLoop` follows the loop that is running, so timers, promises and
the I/O of :mod:`Pyjoyment` share it, and the response can be given later
than the ``request`` event, once the transaction is resumed.

An HTTP request is read from the connection scope as the ``CGI`` environment
that :meth:`Pyjo.Message.Request.Pyjo_Message_Request.parse` takes, as
:mod:`Pyjo.Server.WSGI` does. The ASGI server frames the response itself, so
chunked content is sent without its framing and without the
``Transfer-Encoding`` header, and the ``Date`` header is the one of the ASGI
server, unless the application sets one. A WebSocket handshake is a
:mod:`Pyjo.Transaction.WebSocket`, as with :mod:`Pyjo.Server.Daemon`; a
response other than ``101`` rejects it, the ASGI server negotiates
``permessage-deflate`` on its own, and a ``Ping`` frame, which ASGI cannot
send, is answered with a ``Pong`` frame, as the ASGI server pings the client
itself.

The lifespan of the ASGI server is the one of the server of the application:
its startup calls :meth:`Pyjo.App.Pyjo_App.server`, which emits the hook
``before_server_start`` of :mod:`Pyjoyment`, and its shutdown calls
:meth:`Pyjo.App.Pyjo_App.server_stopped`, which emits the hook
``after_server_stop``, and waits for the promise that it returns, as of the
lifespan of a mounted ASGI application. An exception of either fails the
lifespan of the ASGI server with its message.

This needs a reactor that runs in the event loop of the ASGI server and
gives awaitables for it. :mod:`Pyjo.Reactor.Asyncio`, the default, does so in
an ASGI server on :mod:`asyncio`, whose loop may be another implementation of
the event loop of :mod:`asyncio`, as uvloop is, as the reactor takes the loop
that the server runs. :mod:`Pyjo.Reactor.Poll` runs a loop of its own, which
nothing runs in an ASGI server, so a response given later than the
``request`` event fails, with ``Task got bad yield`` in a server on
:mod:`asyncio`. A server on another framework, as Hypercorn on Trio, needs a
reactor for it, which may come from another distribution, as
:mod:`Pyjo.Reactor` describes.

ASGI servers
------------

* uvicorn, on :mod:`asyncio` or uvloop: HTTP, WebSocket and lifespan.
* Hypercorn, on :mod:`asyncio` or uvloop: HTTP, WebSocket and lifespan; on
  Trio only with a reactor for Trio, which Pyjoyment does not have.
* Daphne: HTTP and WebSocket. It adds no ``Date`` header, so a response has
  one only when the application sets it, and it sends no reason with a
  WebSocket close code. It has no lifespan, so the start and the end of the
  server are not emitted, and the lifespan of a mounted ASGI application does
  not shut down.
* Granian: HTTP, WebSocket and lifespan. A ``websocket.close`` that the
  application sends is not delivered while a ``receive`` is waiting, and an
  application of WebSocket always waits for the next message, so a WebSocket
  that the application closes stays open until the client closes it.

Events
------

:mod:`Pyjo.Server.ASGI` inherits all events from :mod:`Pyjo.Server`.

See also
--------

:mod:`Pyjoyment`, :mod:`Pyjo.Server.WSGI`, https://asgi.readthedocs.io.

It has no counterpart in Mojolicious; :mod:`Pyjo.Server.WSGI` is the
counterpart of
`Mojo::Server::PSGI <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Server/PSGI.pm>`_.
"""

import Pyjo.Content.Single
import Pyjo.Promise
import Pyjo.Server
import Pyjo.Transaction
import Pyjo.Transaction.HTTP
import Pyjo.Transaction.WebSocket

from Pyjo.Util import url_escape
from Pyjo.WebSocket import (
    WS_BINARY,
    WS_CLOSE,
    WS_CONTINUATION,
    WS_PING,
    WS_PONG,
    WS_TEXT,
    Frame,
    parse_frame,
    server_handshake,
)

import struct
import sys

from collections.abc import Awaitable, Callable, Mapping
from typing import Any


# The connection scope, a message, and the functions that receive and send messages
type Scope = Mapping[str, Any]
type Message = Mapping[str, Any]
type Receive = Callable[[], Awaitable[Message]]
type Send = Callable[[Message], Awaitable[None]]
type Application = Callable[[Scope, Receive, Send], Awaitable[None]]


class Pyjo_Server_ASGI(Pyjo.Server.object):
    """
    :mod:`Pyjo.Server.ASGI` inherits all attributes and methods from
    :mod:`Pyjo.Server` and implements the following new ones.
    """

    # The run of Pyjo.Server takes no arguments, as the one of Mojo::Server; the run of an ASGI server is a coroutine for
    # one connection, as the one of Mojo::Server::PSGI takes the environment
    async def run(self, scope: Scope, receive: Receive, send: Send) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """::

            await asgi.run(scope, receive, send)

        Run ``ASGI`` for one connection.
        """
        type = scope['type']
        if type == 'http':
            await self._http(scope, receive, send)
        elif type == 'websocket':
            await self._websocket(scope, receive, send)
        elif type == 'lifespan':
            await self._lifespan(receive, send)
        else:
            raise ValueError(f'Unsupported ASGI connection type "{type}"')

    def to_asgi_app(self) -> Application:
        """::

            app = asgi.to_asgi_app()

        Turn the application into an ``ASGI`` application.
        """
        # Preload application and wrap it
        self.app

        async def application(scope: Scope, receive: Receive, send: Send) -> None:
            await self.run(scope, receive, send)

        return application

    def _build(self, scope: Scope) -> Pyjo.Transaction.HTTP.object:
        tx = self.build_tx()
        if (client := scope.get('client')) is not None:
            tx.remote_address, tx.remote_port = client[0], client[1]
        if (server := scope.get('server')) is not None and server[1] is not None:
            tx.local_address, tx.local_port = server[0], server[1]
        return tx

    async def _http(self, scope: Scope, receive: Receive, send: Send) -> None:
        env = _environ(scope)

        # Request body of unknown length, as the ASGI server removes the chunked framing
        body: bytes | None = None
        if 'CONTENT_LENGTH' not in env:
            whole = bytearray()
            async for chunk in _body(receive):
                whole += chunk
            body = bytes(whole)
            if len(body):
                env['CONTENT_LENGTH'] = str(len(body))

        tx = self._build(scope)
        req = tx.req.parse(env)
        if body is not None:
            req.parse(body)
        else:
            async for chunk in _body(receive):
                req.parse(chunk)
                if req.is_finished:
                    break

        resumed = _Resumed(tx)
        self.emit('request', tx)
        await resumed.wait()

        # Response headers, without the framing of chunked content, and without the Date header that fix_headers adds,
        # as the ASGI server adds its own
        res = tx.res
        dated = res.headers.date is not None
        res.fix_headers()
        if not dated:
            res.headers.remove('Date')
        content = res.content
        chunked = content.is_chunked
        headers = [
            (name.lower().encode('latin-1'), value.encode('latin-1'))
            for name, value in res.headers.to_list()
            if not chunked or name.lower() != 'transfer-encoding'
        ]
        await send({'type': 'http.response.start', 'status': res.code or 404, 'headers': headers})

        # Response body
        if not tx.is_empty:
            unchunk = _Unchunk() if chunked else None
            offset = 0
            while True:
                # No content yet, try again later
                if (chunk := res.get_body_chunk(offset)) is None:
                    await resumed.wait()
                    continue

                # End of content
                if not len(chunk):
                    break

                offset += len(chunk)
                if unchunk is not None:
                    chunk = unchunk.parse(chunk)
                if len(chunk):
                    await send({'type': 'http.response.body', 'body': chunk, 'more_body': True})

        await send({'type': 'http.response.body', 'body': b'', 'more_body': False})
        tx.closed()

    # The start and the end of the server, which the application learns, and whose cleanup the ASGI server waits for
    async def _lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                try:
                    self.app.server(self)
                except Exception as e:
                    await send({'type': 'lifespan.startup.failed', 'message': str(e)})
                    return
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                try:
                    if isinstance(promise := self.app.server_stopped(self), Pyjo.Promise.object):
                        await promise
                except Exception as e:
                    await send({'type': 'lifespan.shutdown.failed', 'message': str(e)})
                    return
                await send({'type': 'lifespan.shutdown.complete'})
                return

    async def _websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
        message = await receive()
        if message['type'] != 'websocket.connect':
            return

        # Handshake
        tx = self._build(scope)
        tx.req.parse(_environ(scope))
        if not tx.req.is_handshake:
            tx.req.headers.upgrade = 'websocket'
        ws = Pyjo.Transaction.WebSocket.new(handshake=tx)
        handshake = _Resumed(tx)
        self.emit('request', server_handshake(ws))
        await handshake.wait()

        # Rejected
        if ws.res.code != 101:
            await send({'type': 'websocket.close', 'code': 1008})
            tx.closed()
            ws.closed()
            return

        # Established, the ASGI server compresses messages itself
        await send({'type': 'websocket.accept', 'subprotocol': ws.protocol})
        tx.closed()
        ws.set(established=True, compressed=False)

        # Write messages as they are sent, and read them as they arrive
        writer = _Writer(ws, send)
        while not writer.closed:
            message = await receive()
            if message['type'] == 'websocket.receive':
                if (text := message.get('text')) is not None:
                    ws.parse_message((1, 0, 0, 0, WS_TEXT, text.encode()))
                else:
                    ws.parse_message((1, 0, 0, 0, WS_BINARY, message.get('bytes') or b''))
            elif message['type'] == 'websocket.disconnect':
                writer.stop()
                code = message.get('code', 1005)
                if code == 1005:
                    ws.parse_message((1, 0, 0, 0, WS_CLOSE, b''))
                elif code != 1006:
                    reason = (message.get('reason') or '').encode()
                    ws.parse_message((1, 0, 0, 0, WS_CLOSE, struct.pack('>H', code) + reason))
                break
        await writer.done
        ws.closed()


# The next resume event of a transaction, which may come before it is waited for
class _Resumed:
    def __init__(self, tx: Pyjo.Transaction.object) -> None:
        self._resumed = False
        self._promise: Pyjo.Promise.object | None = None
        tx.on('resume', self.resume)

    def resume(self, *args: Any) -> None:
        self._resumed = True
        if (promise := self._promise) is not None:
            self._promise = None
            promise.resolve()

    async def wait(self) -> None:
        if not self._resumed:
            self._promise = Pyjo.Promise.new()
            await self._promise
        self._resumed = False


# Chunked content without its framing
class _Unchunk:
    def __init__(self) -> None:
        self._chunks: list[bytes] = []
        self._parser = Pyjo.Content.Single.new()
        self._parser.unsubscribe('read').on('read', self._read)
        self._parser.parse(b'Transfer-Encoding: chunked\x0d\x0a\x0d\x0a')

    def _read(self, content: Pyjo.Content.Single.object, chunk: bytes) -> None:
        self._chunks.append(chunk)

    def parse(self, chunk: bytes) -> bytes:
        self._parser.parse(chunk)
        chunks, self._chunks = self._chunks, []
        return b''.join(chunks)


# The frames that a WebSocket transaction writes, as messages of ASGI
class _Writer:
    def __init__(self, ws: Pyjo.Transaction.WebSocket.object, send: Send) -> None:
        self.closed = False
        self._buffer = bytearray()
        self._message: list[Any] = []
        self._resumed = _Resumed(ws)
        self._send = send
        self._stopped = False
        self._ws = ws
        self.done = Pyjo.Promise.new(self._write())

    def stop(self) -> None:
        self._stopped = True
        self._resumed.resume()

    async def _write(self) -> None:
        while not self._stopped:
            chunk = self._ws.server_write()
            self._buffer += chunk
            while not self._stopped and isinstance(frame := parse_frame(self._buffer, sys.maxsize), tuple):
                await self._frame(frame)
            if self.closed or self._ws.is_finished:
                return

            # What has been written, after which the next write, of nothing, emits the event drain, as a server does
            # once the data has been written
            if not len(chunk):
                await self._resumed.wait()

    async def _frame(self, frame: Frame) -> None:
        fin, _, _, _, op, payload = frame

        # Close
        if op == WS_CLOSE:
            code = struct.unpack('>H', payload[:2])[0] if len(payload) >= 2 else 1000
            await self._send(
                {'type': 'websocket.close', 'code': code, 'reason': payload[2:].decode('utf-8', 'replace')}
            )
            self.closed = True
            return

        # A ping, which ASGI cannot send, is answered as by the client, as the ASGI server keeps the connection alive
        if op == WS_PING:
            self._ws.parse_message((1, 0, 0, 0, WS_PONG, payload))
            return

        # Text or binary message, which may come in fragments
        if op in (WS_TEXT, WS_BINARY):
            self._message = [op, payload]
        elif op == WS_CONTINUATION and self._message:
            self._message[1] += payload
        else:
            return
        if not fin:
            return
        op, payload = self._message
        self._message = []
        if op == WS_TEXT:
            await self._send({'type': 'websocket.send', 'text': payload.decode('utf-8', 'replace')})
        else:
            await self._send({'type': 'websocket.send', 'bytes': payload})


# The body of a request, from http.request messages
async def _body(receive: Receive):
    while True:
        message = await receive()
        if message['type'] == 'http.disconnect':
            return
        if len(chunk := message.get('body', b'')):
            yield chunk
        if not message.get('more_body'):
            return


# The CGI environment of a connection scope
def _environ(scope: Scope) -> dict[str, str]:
    # The raw path is bytes, which a path of Pyjoyment takes as characters, so the bytes beyond ASCII are percent-encoded,
    # as the path is escaped
    raw = scope.get('raw_path')
    path = url_escape(raw.split(b'?', 1)[0], rb'\x80-\xff').decode('ascii') if raw else scope.get('path', '')
    env = {
        'PATH_INFO': path,
        'QUERY_STRING': scope.get('query_string', b'').decode('latin-1'),
        'REQUEST_METHOD': scope.get('method', 'GET'),
        'SCRIPT_NAME': scope.get('root_path', ''),
        'SERVER_PROTOCOL': f'HTTP/{scope.get("http_version", "1.1")}',
    }
    if scope.get('scheme') in ('https', 'wss'):
        env['HTTPS'] = 'ON'

    # Headers, joined as CGI has them
    for name, value in scope.get('headers', []):
        key, value = name.decode('latin-1').upper().replace('-', '_'), value.decode('latin-1')
        if key in ('CONTENT_LENGTH', 'CONTENT_TYPE'):
            env[key] = value
        elif key != 'TRANSFER_ENCODING':
            key = f'HTTP_{key}'
            env[key] = f'{env[key]}{"; " if key == "HTTP_COOKIE" else ", "}{value}' if key in env else value

    return env


new = Pyjo_Server_ASGI.new
object = Pyjo_Server_ASGI
ASGI = Pyjo_Server_ASGI
