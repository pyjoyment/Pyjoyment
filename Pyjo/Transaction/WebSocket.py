r"""
Pyjo.Transaction.WebSocket - WebSocket transaction
==================================================
::

    from Pyjo.Transaction.WebSocket import WebSocket

    # Send and receive WebSocket messages
    ws = WebSocket()
    ws.send('Hello World!')
    ws.on('message', lambda ws, msg: print(f'Message: {msg}'))
    ws.on('finish', lambda ws, code, reason: print(f'WebSocket closed with status {code}.'))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Transaction.WebSocket

    # Send and receive WebSocket messages
    ws = Pyjo.Transaction.WebSocket.new()
    ws.send('Hello World!')
    ws.on('message', lambda ws, msg: print(f'Message: {msg}'))
    ws.on('finish', lambda ws, code, reason: print(f'WebSocket closed with status {code}.'))

:mod:`Pyjo.Transaction.WebSocket` is a container for WebSocket transactions,
based on `RFC 6455 <https://tools.ietf.org/html/rfc6455>`_ and
`RFC 7692 <https://tools.ietf.org/html/rfc7692>`_.

Events
------

:mod:`Pyjo.Transaction.WebSocket` inherits all events from
:mod:`Pyjo.Transaction` and can emit the following new ones.

binary
~~~~~~
::

    ws.on('binary', lambda ws, data: ...)

Emitted when a complete WebSocket binary message has been received. ::

    ws.on('binary', lambda ws, data: print(f'Binary: {data}'))

drain
~~~~~
::

    ws.on('drain', lambda ws: ...)

Emitted once all data has been sent. ::

    ws.on('drain', lambda ws: ws.send(str(time.time())))

finish
~~~~~~
::

    ws.on('finish', lambda ws, code, reason: ...)

Emitted when the WebSocket connection has been closed.

frame
~~~~~
::

    ws.on('frame', lambda ws, frame: ...)

Emitted when a WebSocket frame has been received. ::

    @ws.on('frame')
    def frame(ws, frame):
        print(f'FIN: {frame[0]}')
        print(f'RSV1: {frame[1]}')
        print(f'RSV2: {frame[2]}')
        print(f'RSV3: {frame[3]}')
        print(f'Opcode: {frame[4]}')
        print(f'Payload: {frame[5]}')

json
~~~~
::

    ws.on('json', lambda ws, json: ...)

Emitted when a complete WebSocket message has been received, all text and
binary messages will be automatically JSON decoded. Note that this event only
gets emitted when it has at least one subscriber. ::

    ws.on('json', lambda ws, data: print(f'Message: {data["msg"]}'))

message
~~~~~~~
::

    ws.on('message', lambda ws, msg: ...)

Emitted when a complete WebSocket message has been received, text messages
will be automatically decoded. Note that this event only gets emitted when it
has at least one subscriber. ::

    ws.on('message', lambda ws, msg: print(f'Message: {msg}'))

resume
~~~~~~
::

    tx.on('resume', lambda tx: ...)

Emitted when transaction is resumed.

text
~~~~
::

    ws.on('text', lambda ws, data: ...)

Emitted when a complete WebSocket text message has been received. ::

    ws.on('text', lambda ws, data: print(f'Text: {data}'))

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Transaction::WebSocket <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Transaction/WebSocket.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.IOLoop
import Pyjo.Message.Request
import Pyjo.Message.Response
import Pyjo.Transaction
import Pyjo.Transaction.HTTP
import Pyjo.WebSocket

from Pyjo.JSON import encode_json, j
from Pyjo.Util import decode, encode, trim
from Pyjo.WebSocket import WS_BINARY, WS_CLOSE, WS_PING, WS_PONG, WS_TEXT, Frame

import builtins
import os
import struct
import weakref
import zlib

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Self


type Anything = builtins.object


class Pyjo_Transaction_WebSocket(Pyjo.Transaction.object):
    """
    :mod:`Pyjo.Transaction.WebSocket` inherits all methods from
    :mod:`Pyjo.Transaction` and implements the following new ones.
    """

    def __init__(
        self,
        *,
        compressed: bool | None = None,
        established: bool | None = None,
        handshake: Pyjo.Transaction.HTTP.object | None = None,
        masked: bool | None = None,
        max_websocket_size: int | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            ws = Pyjo.Transaction.WebSocket.new()
            ws = Pyjo.Transaction.WebSocket.new(compressed=True)

        Construct a new :mod:`Pyjo.Transaction.WebSocket` object.
        """
        super().__init__(**kwargs)

        self.compressed = compressed
        """::

            boolean = ws.compressed
            ws.compressed = boolean

        Compress messages with ``permessage-deflate`` extension.
        """

        self.established = established
        """::

            boolean = ws.established
            ws.established = boolean

        WebSocket connection established.
        """

        self.handshake = handshake if handshake is not None else Pyjo.Transaction.HTTP.new()
        """::

            handshake = ws.handshake
            ws.handshake = Pyjo.Transaction.HTTP.new()

        The original handshake transaction, usually a
        :mod:`Pyjo.Transaction.HTTP` object.
        """

        self.masked = masked
        """::

            boolean = ws.masked
            ws.masked = boolean

        Mask outgoing frames with XOR cipher and a random 32-bit key.
        """

        self._max_websocket_size: int | None = max_websocket_size

        # The state of the transaction, as the keys of Mojo's hash
        self._close: list[Any] | None = None
        self._closing = False
        self._heartbeat: _Heartbeat | None = None
        self._inflate: Any = None
        self._message: bytes | None = None
        self._op: int | None = None
        self._pmc = False
        self._read = bytearray()
        self._write: bytes | None = None

    @property
    def max_websocket_size(self) -> int:
        """::

            size = ws.max_websocket_size
            ws.max_websocket_size = 1024

        Maximum WebSocket message size in bytes, defaults to the value of the
        ``PYJO_MAX_WEBSOCKET_SIZE`` environment variable or ``262144``
        (256KiB).
        """
        if self._max_websocket_size is None:
            self._max_websocket_size = int(os.environ.get('PYJO_MAX_WEBSOCKET_SIZE') or 262144)
        return self._max_websocket_size

    @max_websocket_size.setter
    def max_websocket_size(self, value: int) -> None:
        self._max_websocket_size = value

    def build_message(self, frame: str | Mapping[str, Any]) -> Frame:
        """::

            frame = ws.build_message({'binary': data})
            frame = ws.build_message({'text': data})
            frame = ws.build_message({'json': {'test': [1, 2, 3]}})
            frame = ws.build_message(chars)

        Build WebSocket message.
        """
        # Text
        message = {'text': encode('UTF-8', frame)} if isinstance(frame, str) else dict(frame)

        # JSON
        if 'json' in message:
            message['text'] = encode_json(message['json'])

        # Raw text or binary
        op, payload = (WS_TEXT, message['text']) if 'text' in message else (WS_BINARY, message['binary'])

        # "permessage-deflate" extension
        if not self.compressed:
            return (1, 0, 0, 0, op, payload)
        # A new context for each message, as deflateReset gives
        deflate = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15, 8)
        out = deflate.compress(payload) + deflate.flush(zlib.Z_SYNC_FLUSH)

        return (1, 1, 0, 0, op, out[:-4])

    def client_read(self, chunk: bytes) -> None:
        """::

            ws.client_read(data)

        Read data client-side, used to implement user agents such as
        :mod:`Pyjo.UserAgent`.
        """
        self.server_read(chunk)

    def client_write(self) -> bytes:
        """::

            data = ws.client_write()

        Write data client-side, used to implement user agents such as
        :mod:`Pyjo.UserAgent`.
        """
        return self.server_write()

    def closed(self) -> Self:
        """::

            ws = ws.closed()

        Same as :meth:`Pyjo.Transaction.Pyjo_Transaction.completed`, but also
        indicates that all transaction data has been sent.
        """
        self.completed()
        args = list(self._close) if self._close else [1006]
        return self.emit('finish', *(args if len(args) > 1 else [*args, None]))

    @property
    def connection(self) -> str | None:
        """::

            id = ws.connection

        Connection identifier.
        """
        return self.handshake.connection

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @connection.setter
    def connection(self, value: str | None) -> None:
        self.handshake.connection = value

    def finish(self, code: int | None = None, reason: str | None = None) -> Self:
        """::

            ws = ws.finish()
            ws = ws.finish(1000)
            ws = ws.finish(1003, 'Cannot accept data!')

        Close WebSocket connection gracefully.
        """
        close = self._close = [code, reason] if reason is not None else [code] if code is not None else []
        payload = struct.pack('>H', close[0]) if close and close[0] else b''
        if reason is not None:
            payload += encode('UTF-8', reason)
        if not close:
            close.append(1005)
        elif close[0] is None:
            close[0] = 1005
        self.send((1, 0, 0, 0, WS_CLOSE, payload))._closing = True

        return self

    # Not in Mojolicious: the pings that ASGI servers and other WebSocket servers send, so that an application does not
    # repeat a recurring timer and its end for every WebSocket
    def heartbeat(self, interval: float | None = 20, timeout: float | None = 20) -> Self:
        """::

            ws = ws.heartbeat()
            ws = ws.heartbeat(60, 10)
            ws = ws.heartbeat(None)

        Send a ``Ping`` frame every ``interval`` seconds while the WebSocket
        connection is established, so that the inactivity timeout of the
        connection does not close a WebSocket without messages, and close the
        connection, with the status ``1006`` of the event ``finish``, when the
        peer sends no frame, as the ``Pong`` that answers it, within
        ``timeout`` seconds. The timers are of :data:`Pyjo.IOLoop.singleton`,
        whose connection :attr:`connection` is. An ``interval`` of ``None``
        or ``0`` stops the pings, and a ``timeout`` of ``None`` or ``0`` waits
        for no frame. ::

            # Keep the WebSocket of a route alive
            @websocket('/echo')
            def echo(c):
                c.tx.heartbeat()
                c.on('message', lambda c, msg: c.send(f'echo: {msg}'))
        """
        if (heartbeat := self._heartbeat) is not None:
            self._heartbeat = None
            heartbeat.stop()
        if interval:
            self._heartbeat = _Heartbeat(self, interval, timeout)
        return self

    @property
    def is_websocket(self) -> bool:
        """::

            boolean = ws.is_websocket

        True, this is a :mod:`Pyjo.Transaction.WebSocket` object.
        """
        return True

    @property
    def kept_alive(self) -> bool | None:
        """::

            boolean = ws.kept_alive

        Connection has been kept alive.
        """
        return self.handshake.kept_alive

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @kept_alive.setter
    def kept_alive(self, value: bool | None) -> None:
        self.handshake.kept_alive = value

    @property
    def local_address(self) -> str | None:
        """::

            address = ws.local_address

        Local interface address.
        """
        return self.handshake.local_address

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @local_address.setter
    def local_address(self, value: str | None) -> None:
        self.handshake.local_address = value

    @property
    def local_port(self) -> int | None:
        """::

            port = ws.local_port

        Local interface port.
        """
        return self.handshake.local_port

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @local_port.setter
    def local_port(self, value: int | None) -> None:
        self.handshake.local_port = value

    def parse_message(self, frame: Sequence[Any]) -> Anything:
        """::

            ws.parse_message((fin, rsv1, rsv2, rsv3, op, payload))

        Parse WebSocket message.
        """
        self.emit('frame', frame)

        # Ping/Pong
        op, payload = frame[4], bytes(frame[5])
        if op == WS_PING:
            return self.send((1, 0, 0, 0, WS_PONG, payload))
        if op == WS_PONG:
            return None

        # Close
        if op == WS_CLOSE:
            if not len(payload) >= 2:
                return self.finish()
            return self.finish(struct.unpack('>H', payload[:2])[0], decode('UTF-8', payload[2:]))

        # Append chunk and check message size
        if self._op is None:
            self._op, self._pmc = op, bool(self.compressed and frame[1])
        self._message = (self._message or b'') + payload
        max = self.max_websocket_size
        if len(self._message) > max:
            return self.finish(1009)

        # No FIN bit (Continuation)
        if not frame[0]:
            return None

        # "permessage-deflate" extension (handshake and RSV1)
        msg, self._message = self._message, None
        if self.compressed and self._pmc:
            if self._inflate is None:
                self._inflate = zlib.decompressobj(-15)
            out = self._inflate.decompress(msg + b'\x00\x00\xff\xff', max)
            if len(self._inflate.unconsumed_tail):
                return self.finish(1009)
            msg = out

        if self.has_subscribers('json'):
            self.emit('json', j(msg))
        op, self._op = self._op, None
        self.emit('text' if op == WS_TEXT else 'binary', msg)
        if self.has_subscribers('message'):
            self.emit('message', decode('UTF-8', msg) if op == WS_TEXT else msg)
        return None

    @property
    def protocol(self) -> str | None:
        """::

            proto = ws.protocol

        Return negotiated subprotocol or ``None``.
        """
        return self.res.headers.sec_websocket_protocol

    @property
    def remote_address(self) -> str | None:
        """::

            address = ws.remote_address

        Remote interface address.
        """
        return self.handshake.remote_address

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @remote_address.setter
    def remote_address(self, value: str | None) -> None:
        self.handshake.remote_address = value

    @property
    def remote_port(self) -> int | None:
        """::

            port = ws.remote_port

        Remote interface port.
        """
        return self.handshake.remote_port

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @remote_port.setter
    def remote_port(self, value: int | None) -> None:
        self.handshake.remote_port = value

    @property
    def req(self) -> Pyjo.Message.Request.object:
        """::

            req = ws.req

        Handshake request, usually a :mod:`Pyjo.Message.Request` object.
        """
        return self.handshake.req

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @req.setter
    def req(self, value: Pyjo.Message.Request.object) -> None:
        self.handshake.req = value

    @property
    def res(self) -> Pyjo.Message.Response.object:
        """::

            res = ws.res

        Handshake response, usually a :mod:`Pyjo.Message.Response` object.
        """
        return self.handshake.res

    # Not in Mojolicious: setting it sets the handshake's, which Mojo's getter ignores
    @res.setter
    def res(self, value: Pyjo.Message.Response.object) -> None:
        self.handshake.res = value

    def resume(self) -> Self:
        """::

            ws = ws.resume()

        Resume :attr:`handshake` transaction.
        """
        self.handshake.resume()
        return self

    def send(self, msg: str | Mapping[str, Any] | Sequence[Any], cb: Callable[..., Anything] | None = None) -> Self:
        """::

            ws = ws.send({'binary': data})
            ws = ws.send({'text': data})
            ws = ws.send({'json': {'test': [1, 2, 3]}})
            ws = ws.send((fin, rsv1, rsv2, rsv3, op, payload))
            ws = ws.send(chars)
            ws = ws.send(chars, lambda ws: ...)

        Send message or frame non-blocking via WebSocket, the optional drain
        callback will be executed once all data has been written. ::

            # Send "Ping" frame
            from Pyjo.WebSocket import WS_PING
            ws.send((1, 0, 0, 0, WS_PING, b'Hello World!'))
        """
        if cb is not None:
            self.once('drain', cb)
        frame = self.build_message(msg) if isinstance(msg, str | Mapping) else msg
        fin, rsv1, rsv2, rsv3, op, payload = frame
        self._write = (self._write or b'') + Pyjo.WebSocket.build_frame(self.masked, fin, rsv1, rsv2, rsv3, op, payload)
        return self.emit('resume')

    def server_read(self, chunk: bytes) -> None:
        """::

            ws.server_read(data)

        Read data server-side, used to implement web servers such as
        :mod:`Pyjo.Server.Daemon`.
        """
        self._read += chunk
        max = self.max_websocket_size
        while frame := Pyjo.WebSocket.parse_frame(self._read, max):
            if not isinstance(frame, tuple):
                self.finish(1009)
                break
            self.parse_message(frame)

        self.emit('resume')

    def server_write(self) -> bytes:
        """::

            data = ws.server_write()

        Write data server-side, used to implement web servers such as
        :mod:`Pyjo.Server.Daemon`.
        """
        if self._write is None:
            self._write = b''
        if not len(self._write):
            self.emit('drain')
        if not len(self._write or b'') and self._closing:
            self.completed()
        write, self._write = self._write or b'', None
        return write

    def with_compression(self) -> None:
        """::

            ws.with_compression()

        Negotiate ``permessage-deflate`` extension for this WebSocket
        connection.
        """
        # "permessage-deflate" extension
        if 'permessage-deflate' in (self.req.headers.sec_websocket_extensions or ''):
            self.compressed = True
            self.res.headers.sec_websocket_extensions = 'permessage-deflate'

    def with_protocols(self, *protos: str) -> str | None:
        """::

            proto = ws.with_protocols('v2.proto', 'v1.proto')

        Negotiate subprotocol for this WebSocket connection.
        """
        offered = {trim(p) for p in (self.req.headers.sec_websocket_protocol or '').split(',')}
        if (proto := next((p for p in protos if p in offered), None)) is None:
            return None

        self.res.headers.sec_websocket_protocol = proto
        return proto


# The pings of a WebSocket, whose timers refer to it weakly, and which end with it
class _Heartbeat:
    def __init__(self, ws: Pyjo_Transaction_WebSocket, interval: float, timeout: float | None) -> None:
        self.loop = Pyjo.IOLoop.object.singleton()
        self.pong: str | None = None
        self.timeout = timeout
        self.ws = weakref.ref(ws)
        ref = weakref.ref(self)

        def ping(loop: Any) -> None:
            if (this := ref()) is not None:
                this.ping()

        def frame(ws: Any, frame: Any) -> None:
            if (this := ref()) is not None:
                this.frame()

        def finish(ws: Any, *args: Any) -> None:
            if (this := ref()) is not None:
                this.stop()

        self.events = [ws.on('frame', frame), ws.on('finish', finish)]
        self.timer = self.loop.recurring(interval, ping)

    # A frame of the peer, which is there
    def frame(self) -> None:
        if (pong := self.pong) is not None:
            self.pong = None
            self.loop.remove(pong)

    # The connection of a peer that has not answered
    def gone(self) -> None:
        self.pong = None
        if (ws := self.ws()) is not None and (connection := ws.connection) is not None:
            self.loop.remove(connection)

    def ping(self) -> None:
        if (ws := self.ws()) is None:
            return self.stop()
        if not ws.established or self.pong is not None:
            return
        ws.send((1, 0, 0, 0, WS_PING, b''))
        if self.timeout:
            ref = weakref.ref(self)

            def gone(loop: Any) -> None:
                if (this := ref()) is not None:
                    this.gone()

            self.pong = self.loop.timer(self.timeout, gone)

    def stop(self) -> None:
        self.loop.remove(self.timer)
        if (pong := self.pong) is not None:
            self.pong = None
            self.loop.remove(pong)
        if (ws := self.ws()) is not None:
            ws.unsubscribe('frame', self.events[0]).unsubscribe('finish', self.events[1])


new = Pyjo_Transaction_WebSocket.new
object = Pyjo_Transaction_WebSocket
WebSocket = Pyjo_Transaction_WebSocket
