"""
Pyjo.App.ASGI - ASGI application
================================
::

    from Pyjo.App.ASGI import ASGI


    async def hello(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'Hello World!'})


    app = ASGI(app=hello)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.App.ASGI

    app = Pyjo.App.ASGI.new(app=hello)

    # Mount it in an application of Pyjoyment
    import Pyjoyment

    pyjoyment = Pyjoyment.new()
    pyjoyment.plugin('Mount', {'/hello': app})

:mod:`Pyjo.App.ASGI` is an application of :mod:`Pyjo` that runs an ``ASGI``
application, as https://asgi.readthedocs.io describes it, so that a server of
:mod:`Pyjo` serves it, a route of :mod:`Pyjoyment` embeds it, as
:mod:`Pyjoyment.Plugin.Mount` does, and :mod:`Pyjo.Test.Pyjo` tests it.

The part of the path that a route embeds the application under is
``root_path``, after the base path of the request, and ``path`` is the whole
path, with ``root_path`` in front of it. A route that embeds the application
at a part of the path that does not end with a slash, as ``/php`` of
``/phpx``, which ``root_path`` cannot be, does not find it. The body of the request is the
message ``http.request`` of ``receive``, in chunks with ``more_body``, and
the next ``receive`` waits for the end of the connection, the message
``http.disconnect``.

The application runs as a coroutine of the reactor, as
:meth:`Pyjo.Reactor.Pyjo_Reactor.run_coroutine` runs it: with
:mod:`Pyjo.Reactor.Asyncio`, a task of the event loop of :mod:`asyncio`,
where it can await anything of the loop, and with another reactor, as
:mod:`Pyjo.Reactor.Poll`, a coroutine that awaits only ``receive`` and
``send``, so that an application that awaits anything else fails there. A
response that the application gives in one message ``http.response.body`` is
written with its ``Content-Length``. Another one is written as the application
sends it, with the chunked transfer encoding when the application does not
give its ``Content-Length``, and ``send`` returns once the chunk has been
written, so that a stream of server-sent events goes at the pace of the
client. Once the connection is gone, ``send`` does nothing.

An exception of the application before its response starts is a response
``500``, the exception page of :mod:`Pyjoyment` in a route that embeds it, an
exception after that is logged and closes the connection, as does an
application that returns before the end of its response, and an exception
after the end of the response is logged.

A WebSocket handshake is the connection ``websocket``, whose
``subprotocols`` are the ones that the client offers. The response of the
handshake waits for the message ``websocket.accept``, whose ``subprotocol``
and ``headers`` are those of the response ``101``, and a ``websocket.close``
before it rejects the handshake with the response ``403``, as does a response
of the application with the extension ``websocket.http.response``. The
messages of the WebSocket are ``websocket.receive``, and ``send`` of
``websocket.send`` returns once the message has been written. The end of the
WebSocket, also of a connection that is gone before the response of its
handshake, is the message ``websocket.disconnect`` with the status of the
close, after which ``send`` does nothing. An exception of the application, or
its return, before the response of the handshake is a response ``500``, and
after it is logged and closes the WebSocket with the status ``1011``, unless
the application has closed it.

The WebSockets are pinged, as by an ``ASGI`` server, with
:meth:`Pyjo.Transaction.WebSocket.Pyjo_Transaction_WebSocket.heartbeat` and
the intervals of :attr:`ping_interval` and :attr:`ping_timeout`, so that the
inactivity timeout of the server does not close a WebSocket without messages,
and a client that is gone is found.

The lifespan of the application, the connection ``lifespan``, starts with
the first request in each event loop, as of each process of
:mod:`Pyjo.Server.Prefork` and each thread of :mod:`Pyjo.Server.Prethread`,
or with :meth:`startup`, and the requests wait for its
``lifespan.startup.complete``, after which each gets a copy of its ``state``.
A ``lifespan.startup.failed`` is logged, and the requests get the response
``500``. An application that fails or returns before its startup has no
lifespan, as uvicorn takes it, and one that neither answers nor fails keeps
the requests waiting. The lifespan shuts down once the server has stopped
gracefully, with :meth:`server_stopped`, which
:mod:`Pyjoyment.Plugin.Mount` calls with the hook ``after_server_stop``,
with :meth:`close`, as at the end of a ``with`` block, and at the end of the
interpreter, where nothing has shut it down.

Attributes
----------

:mod:`Pyjo.App.ASGI` inherits all attributes from :mod:`Pyjo.App` and
implements the following new ones.

See also
--------

:mod:`Pyjoyment`, :mod:`Pyjoyment.Plugin.Mount`, :mod:`Pyjo.App.WSGI`,
:mod:`Pyjo.Server.ASGI`, https://mojolicious.org.

It has no counterpart in Mojolicious; it is the reverse of
:mod:`Pyjo.Server.ASGI`.

Classes
-------
"""

import Pyjo.App
import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Transaction

from Pyjo.Server.ASGI import Application, Message, Scope
from Pyjo.Util import url_unescape

import atexit
import collections
import traceback
import weakref
import wsgiref.util

from typing import Any


class Pyjo_App_ASGI(Pyjo.App.object):
    """
    :mod:`Pyjo.App.ASGI` inherits all methods from :mod:`Pyjo.App` and
    implements the following new ones.
    """

    def __init__(self, attrs: dict[str, Any] | None = None, /, **kwargs: Any) -> None:
        """::

            app = Pyjo.App.ASGI.new(app=application)

        Construct a new :mod:`Pyjo.App.ASGI` object.
        """
        self.app: Application | None = None
        """::

            application = app.app
            app.app = application

        The ``ASGI`` application to run.
        """

        self.ping_interval: float | None = 20
        """::

            interval = app.ping_interval
            app.ping_interval = 60

        Interval in seconds of the pings of the WebSockets, defaults to
        ``20``, as of uvicorn. ``None`` or ``0`` sends no pings.
        """

        self.ping_timeout: float | None = 20
        """::

            timeout = app.ping_timeout
            app.ping_timeout = 60

        Timeout in seconds of the answer of a client to a ping of a WebSocket,
        after which its connection is closed, defaults to ``20``, as of
        uvicorn. ``None`` or ``0`` waits for no answer.
        """

        # The lifespan of the application in each event loop, as each thread has one
        self._lifespans: weakref.WeakKeyDictionary[Any, _Lifespan] = weakref.WeakKeyDictionary()

        super().__init__(attrs, **kwargs)

    def close(self) -> None:
        """::

            app.close()

        Shut the lifespan of the application down, and wait for it, unless
        the event loop runs, as the end of a ``with`` block does, and close
        the connections and the servers of :attr:`ua`.
        """
        if (promise := self.shutdown()) is not None and not Pyjo.IOLoop.is_running():
            promise.wait()
        super().close()

    def handler(self, tx: Any) -> None:
        """::

            app.handler(Pyjo.Transaction.HTTP.new())
            app.handler(Pyjoyment.Controller.new())

        Run the application for the request of the transaction, or of the
        controller of a route that embeds the application, and write its
        response.
        """
        if (application := self.app) is None:
            raise Pyjo.Exception.new('No ASGI application')
        c = None
        if not isinstance(tx, Pyjo.Transaction.object):
            c = tx
            tx = c.tx
            if not Pyjo.App._within(c):  # pyright: ignore[reportPrivateUsage]
                return Pyjo.App._not_found(c)  # pyright: ignore[reportPrivateUsage]
            c.render_later()
        call = _WebSocket(self, application, tx, c) if tx.is_websocket else _Call(self, application, tx, c)

        # The lifespan of the application starts with its first request, which waits for its startup
        if (lifespan := self._lifespan()).ready:
            return call.start(lifespan)
        lifespan.started.then(lambda *args: call.start(lifespan))

    def server_stopped(self, server: Any) -> Pyjo.Promise.object | None:
        """::

            promise = app.server_stopped(Pyjo.Server.Daemon.new())

        Shut the lifespan of the application down, as :meth:`shutdown` does,
        once the server has stopped.
        """
        return self.shutdown()

    def shutdown(self) -> Pyjo.Promise.object | None:
        """::

            promise = app.shutdown()

        Shut the lifespan of the application in the event loop of the thread
        down, with the message ``lifespan.shutdown``, and return a promise
        that is fulfilled once the application has answered it, or ``None``
        when the lifespan has not started.
        """
        if (lifespan := self._lifespans.pop(Pyjo.IOLoop.object.singleton(), None)) is None:
            return None
        return lifespan.shutdown()

    def startup(self) -> Pyjo.Promise.object:
        """::

            promise = app.startup()

        Start the lifespan of the application in the event loop of the
        thread, with the message ``lifespan.startup``, unless it has started,
        and return a promise that is fulfilled once the application has
        answered it, as the first request does.
        """
        return self._lifespan().started

    def _lifespan(self) -> '_Lifespan':
        loop = Pyjo.IOLoop.object.singleton()
        if (lifespan := self._lifespans.get(loop)) is None:
            if (application := self.app) is None:
                raise Pyjo.Exception.new('No ASGI application')
            lifespan = self._lifespans[loop] = _Lifespan(self, application)
            lifespan.start()
        return lifespan


# A call of the application, whose messages are the request and the response of the transaction
class _Call:
    def __init__(self, app: Pyjo_App_ASGI, application: Application, tx: Any, c: Any) -> None:
        self.app = app
        self.application = application
        self.c = c
        self.tx = tx
        self.chunked = False
        self.closed = False
        self.ended = False
        self.finished = Pyjo.Promise.new()
        self.headers: list[tuple[str, str]] = []
        self.offset = 0
        self.read = False
        self.started = False
        self.status: int | None = None
        self.written: Pyjo.Promise.object | None = None

    def start(self, lifespan: '_Lifespan') -> None:
        self.tx.on('finish', self._finish)
        if lifespan.failed is not None:
            return self._error(Pyjo.Exception.new(f'ASGI application failed to start: {lifespan.failed}'))
        try:
            coro = self.application(lifespan.scope(_scope(self.tx, self.c)), self._receive, self._send)
        except Exception as e:
            return self._error(e)
        Pyjo.Promise.new(coro).then(self._returned, self._error)

    # End of the response
    def _end(self) -> None:
        self.ended = True
        content = self.tx.res.content
        (content.write_chunk if self.chunked else content.write)(b'')
        self._rendered()

    def _error(self, e: Any) -> None:
        message = _message(e)

        # The response has started, so the connection is closed, as the response cannot change, unless it has ended, as
        # Starlette raises the exception after its response 500
        if self.started:
            if self.ended or not self.closed:
                self.app.log.error(f'ASGI application failed: {message}')
                if not self.ended:
                    self._close()
            return

        # The exception page of Pyjoyment
        self.started = self.ended = True
        if (c := self.c) is not None:
            c.helpers.reply.exception(e)
            return

        self.app.log.error(f'ASGI application failed: {message}')
        res = self.tx.res
        res.code = 500
        res.headers.content_type = 'text/plain'
        res.body = b'Internal Server Error'
        self.tx.resume()

    def _close(self) -> None:
        if (connection := self.tx.connection) is not None and (stream := Pyjo.IOLoop.stream(connection)) is not None:
            stream.close()

    # The end of the transaction, also when the connection is gone before the end of the response, after which receive
    # gives http.disconnect and send does nothing
    def _finish(self, *args: Any) -> None:
        self.closed = True
        self.finished.resolve()
        if (written := self.written) is not None:
            self.written = None
            written.resolve()

    # The status and the headers of http.response.start, and the chunked transfer encoding for a body that comes in more
    # than one message without its length
    def _headers(self, whole: bool) -> None:
        self.started = True
        res = self.tx.res
        res.code = self.status
        headers = res.headers
        for name, value in self.headers:
            if not wsgiref.util.is_hop_by_hop(name):
                headers.add(name, value)
        self.chunked = not whole and headers.content_length is None and self.tx.req.version == '1.1'

    async def _receive(self) -> Message:
        # The body of the request, which has been read whole, in chunks
        if not self.read:
            content = self.tx.req.content
            chunk = content.get_body_chunk(self.offset) or b''
            self.offset += len(chunk)
            more = len(chunk) > 0 and self.offset < content.body_size
            self.read = not more
            return {'type': 'http.request', 'body': bytes(chunk), 'more_body': more}

        # The end of the connection
        if not self.closed:
            await self.finished
        return {'type': 'http.disconnect'}

    def _rendered(self) -> None:
        if (c := self.c) is not None:
            c.rendered()
        else:
            self.tx.resume()

    def _returned(self, *args: Any) -> None:
        if not self.started:
            return self._error(Pyjo.Exception.new('ASGI application returned without a response'))
        if not self.ended and not self.closed:
            self.app.log.error('ASGI application returned without the end of its response')
            self._close()

    async def _send(self, message: Message) -> None:
        if self.closed:
            return
        type = message['type']

        # Status and headers
        if type == 'http.response.start':
            if self.status is not None:
                raise Pyjo.Exception.new('ASGI message "http.response.start" has already been sent')
            self.status = int(message['status'])
            self.headers = [
                (bytes(name).decode('latin-1'), bytes(value).decode('latin-1')) for name, value in message['headers']
            ]
            return

        if type != 'http.response.body':
            raise Pyjo.Exception.new(f'Unknown ASGI message "{type}"')
        if self.status is None:
            raise Pyjo.Exception.new('ASGI message "http.response.start" has not been sent')
        if self.ended:
            # A HEAD request, whose response ends with its headers
            if self.tx.is_empty:
                return
            raise Pyjo.Exception.new('ASGI response has already ended')
        body = bytes(message.get('body', b''))
        more = bool(message.get('more_body', False))

        # Whole response
        if not self.started:
            self._headers(not more)
            if not more:
                self.ended = True
                self.tx.res.body = body
                return self._rendered()

        # Response as the application sends it, with the headers only for a HEAD request
        if self.tx.is_empty:
            return self._end()
        if len(body):
            written = self.written = Pyjo.Promise.new()
            content = self.tx.res.content

            def drained(*args: Any) -> None:
                written.resolve()

            (content.write_chunk if self.chunked else content.write)(body, drained)
            self._rendered()
            await written
        if not more and not self.closed:
            self._end()


# A call of the application for a WebSocket, whose handshake waits for websocket.accept, and whose response of HTTP that
# rejects the handshake is the one of a call for a request
class _WebSocket(_Call):
    def __init__(self, app: Pyjo_App_ASGI, application: Application, ws: Any, c: Any) -> None:
        super().__init__(app, application, ws.handshake, c)
        self.accepted = False
        self.closing = False
        self.connected = False
        # A deque, whose popleft takes the first message, where pop(0) of a list moves all the others
        self.messages: collections.deque[Message] = collections.deque()
        self.responding = False
        self.waiting: Pyjo.Promise.object | None = None
        self.ws = ws

    def start(self, lifespan: '_Lifespan') -> None:
        ws = self.ws
        ws.on('message', self._message)
        ws.on('finish', self._disconnect)
        if lifespan.failed is not None:
            return self._error(Pyjo.Exception.new(f'ASGI application failed to start: {lifespan.failed}'))
        ws.heartbeat(self.app.ping_interval, self.app.ping_timeout)
        try:
            coro = self.application(lifespan.scope(_scope(self.tx, self.c, ws)), self._receive, self._send)
        except Exception as e:
            return self._error(e)
        Pyjo.Promise.new(coro).then(self._returned, self._error)

    # The end of the WebSocket, also when the connection is gone before its handshake, after which receive gives
    # websocket.disconnect and send does nothing
    def _disconnect(self, ws: Any, code: int | None, reason: str | None) -> None:
        self.messages.append({'type': 'websocket.disconnect', 'code': code or 1005, 'reason': reason or ''})
        self._finish()
        self._wake()

    def _error(self, e: Any) -> None:
        if not self.accepted:
            return super()._error(e)

        # The error of an application that has closed the WebSocket itself is logged also once the close has ended, which
        # the order of the events of the reactor decides, and not after the peer has gone, as for a request
        if self.closing or not self.closed:
            self.app.log.error(f'ASGI application failed: {_message(e)}')

        # The WebSocket is closed with the status of an error of the server, unless the application has closed it
        if not self.closed:
            self._close_ws(1011)

    def _message(self, ws: Any, message: str | bytes) -> None:
        self.messages.append(
            {'type': 'websocket.receive', 'text': message}
            if isinstance(message, str)
            else {'type': 'websocket.receive', 'bytes': message}
        )
        self._wake()

    async def _receive(self) -> Message:
        if not self.connected:
            self.connected = True
            return {'type': 'websocket.connect'}
        while not self.messages:
            self.waiting = Pyjo.Promise.new()
            await self.waiting
        return self.messages.popleft()

    def _returned(self, *args: Any) -> None:
        if self.closed and not self.accepted:
            return
        if not self.accepted:
            return super()._returned(*args)
        if not self.closed and not self.closing:
            self.app.log.error('ASGI application returned without closing its WebSocket')
            self._close_ws(1011)

    async def _send(self, message: Message) -> None:
        if self.closed or self.closing:
            return
        type = message['type']

        # The response of HTTP that rejects the handshake
        if self.responding or type == 'websocket.http.response.start':
            if not type.startswith('websocket.http.response.'):
                raise Pyjo.Exception.new(f'ASGI message "{type}" after "websocket.http.response.start"')
            self.responding = True
            return await super()._send({**message, 'type': type.removeprefix('websocket.')})

        # Handshake
        if not self.accepted:
            if type == 'websocket.accept':
                self.accepted = True
                ws = self.ws
                headers = ws.res.headers
                for name, value in message.get('headers', []):
                    headers.add(bytes(name).decode('latin-1'), bytes(value).decode('latin-1'))
                if (protocol := message.get('subprotocol')) is not None:
                    headers.sec_websocket_protocol = protocol
                ws.with_compression()
                return self._accepted()

            # Rejected
            if type == 'websocket.close':
                self.started = self.ended = True
                res = self.tx.res
                res.code = 403
                res.body = b''
                return self._rendered()

            raise Pyjo.Exception.new(f'ASGI message "{type}" before "websocket.accept"')

        # Message
        if type == 'websocket.send':
            written = self.written = Pyjo.Promise.new()

            def drained(*args: Any) -> None:
                written.resolve()

            if (data := message.get('bytes')) is not None:
                self.ws.send({'binary': bytes(data)}, drained)
            else:
                self.ws.send(message.get('text') or '', drained)
            await written
            return

        # Close
        if type == 'websocket.close':
            return self._close_ws(int(message.get('code') or 1000), message.get('reason') or None)

        raise Pyjo.Exception.new(f'Unknown ASGI message "{type}"')

    # The response 101 of the handshake
    def _accepted(self) -> None:
        if (c := self.c) is not None:
            c.rendered(101)
        else:
            self.tx.res.code = 101
            self.ws.resume()

    def _close_ws(self, code: int, reason: str | None = None) -> None:
        if not self.closing:
            self.closing = True
            self.ws.finish(code, reason)

    def _wake(self) -> None:
        if (waiting := self.waiting) is not None:
            self.waiting = None
            waiting.resolve()


# The lifespan of the application in an event loop, whose state the requests get a copy of, or nothing for an
# application without lifespan, which fails or returns before its startup, as uvicorn takes it
class _Lifespan:
    def __init__(self, app: Pyjo_App_ASGI, application: Application) -> None:
        self.app = app
        self.application = application
        self.failed: str | None = None
        self.loop = Pyjo.IOLoop.object.singleton()
        self.ready = False
        self.received = False
        self.requested = Pyjo.Promise.new()
        self.started = Pyjo.Promise.new()
        self.state: dict[str, Any] = {}
        self.stopped = Pyjo.Promise.new()
        self.supported = True

    def scope(self, scope: Scope) -> Scope:
        return {**scope, 'state': dict(self.state)} if self.supported else scope

    def shutdown(self) -> Pyjo.Promise.object:
        _running.discard(self)
        if self.ready:
            self.requested.resolve()
        else:
            self.started.then(lambda *args: self.requested.resolve())
        return self.stopped

    def start(self) -> None:
        _exit()
        _running.add(self)
        scope = {'type': 'lifespan', 'asgi': {'version': '3.0', 'spec_version': '2.0'}, 'state': self.state}
        try:
            coro = self.application(scope, self._receive, self._send)
        except Exception as e:
            return self._error(e)
        Pyjo.Promise.new(coro).then(self._returned, self._error)

    def _end(self) -> None:
        self._ready()
        _running.discard(self)
        self.stopped.resolve()

    def _error(self, e: Any) -> None:
        if not self.ready and self.failed is None:
            self.supported = False
            self.app.log.debug(f'ASGI application without lifespan: {e!r}')
        elif self.ready:
            self.app.log.error(f'ASGI application failed: {_message(e)}')
        self._end()

    def _ready(self) -> None:
        if not self.ready:
            self.ready = True
            self.started.resolve()

    async def _receive(self) -> Message:
        if not self.received:
            self.received = True
            return {'type': 'lifespan.startup'}
        await self.requested
        return {'type': 'lifespan.shutdown'}

    def _returned(self, *args: Any) -> None:
        if not self.ready:
            self.supported = False
        self._end()

    async def _send(self, message: Message) -> None:
        type = message['type']
        if type == 'lifespan.startup.complete':
            self._ready()
        elif type == 'lifespan.startup.failed':
            self.failed = str(message.get('message') or '')
            self.app.log.error(f'ASGI application failed to start: {self.failed}')
            self._ready()
        elif type == 'lifespan.shutdown.complete':
            self._end()
        elif type == 'lifespan.shutdown.failed':
            self.app.log.error(f'ASGI application failed to stop: {message.get("message") or ""}')
            self._end()
        else:
            raise Pyjo.Exception.new(f'Unknown ASGI message "{type}"')


# The lifespans that have started, which the end of the interpreter shuts down, where no server has stopped, as at the
# end of a test, before the reactor of asyncio cancels the tasks that are left, as its handler of the end of the
# interpreter is registered before
_running: weakref.WeakSet[_Lifespan] = weakref.WeakSet()
_registered: list[bool] = []


def _exit() -> None:
    if not _registered:
        _registered.append(True)
        atexit.register(_shutdown)


def _shutdown() -> None:
    try:
        loop = Pyjo.IOLoop.object.singleton()
        for lifespan in list(_running):
            if lifespan.loop is loop and not loop.is_running:
                lifespan.shutdown().wait()
    except Exception:
        pass


# The connection scope of the request of the transaction, or of the handshake of a WebSocket: the path that a route
# embeds the application under is root_path, which path begins with
def _scope(tx: Any, c: Any, ws: Any = None) -> Scope:
    req = tx.req
    url = req.url
    base = url.base
    script, path = Pyjo.App._mount(tx, c)  # pyright: ignore[reportPrivateUsage]

    # Headers, with the length of the body, which is whole, as it has been read
    headers = [
        (name.lower().encode('latin-1'), value.encode('latin-1'))
        for name, value in req.headers.to_list()
        if name.lower() not in ('content-length', 'transfer-encoding')
    ]
    if size := req.content.body_size:
        headers.append((b'content-length', str(size).encode()))

    https = req.is_secure
    scope: dict[str, Any] = {
        'type': 'http' if ws is None else 'websocket',
        'asgi': {'version': '3.0', 'spec_version': '2.4'},
        'http_version': req.version,
        'scheme': ('https' if https else 'http') if ws is None else ('wss' if https else 'ws'),
        'path': _str(script + path),
        'raw_path': (script + path).encode(),
        'query_string': url.query.to_str().encode(),
        'root_path': _str(script),
        'headers': headers,
        'server': (base.host or tx.local_address or 'localhost', base.port or tx.local_port or (443 if https else 80)),
    }
    if ws is None:
        scope['method'] = req.method
    else:
        # The subprotocols that the client offers, and the response of HTTP that rejects the handshake
        offered = req.headers.sec_websocket_protocol or ''
        scope['subprotocols'] = [protocol.strip() for protocol in offered.split(',') if protocol.strip()]
        scope['extensions'] = {'websocket.http.response': {}}
    if (address := tx.remote_address) is not None:
        scope['client'] = (address, tx.remote_port or 0)
    return scope


# An exception with its traceback, for the log
def _message(e: Any) -> str:
    return ''.join(traceback.format_exception(e)).rstrip() if isinstance(e, BaseException) else str(e)


# A path of ASGI: the unescaped bytes as UTF-8
def _str(path: str) -> str:
    return url_unescape(path.encode()).decode('utf-8', 'replace')


new = Pyjo_App_ASGI.new
object = Pyjo_App_ASGI
ASGI = Pyjo_App_ASGI
