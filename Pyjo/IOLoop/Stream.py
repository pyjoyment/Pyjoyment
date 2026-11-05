"""
Pyjo.IOLoop.Stream - Non-blocking I/O stream
============================================
::

    from Pyjo.IOLoop.Stream import Stream

    # Create stream
    stream = Stream(handle)
    stream.on('read', lambda stream, chunk: ...)
    stream.on('close', lambda stream: ...)
    stream.on('error', lambda stream, err: ...)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.IOLoop.Stream

    # Create stream
    stream = Pyjo.IOLoop.Stream.new(handle)
    stream.on('read', lambda stream, chunk: ...)
    stream.on('close', lambda stream: ...)
    stream.on('error', lambda stream, err: ...)

    # Start and stop watching for new data
    stream.start()
    stream.stop()

    # Start reactor if necessary
    if not stream.reactor.is_running:
        stream.reactor.start()

:mod:`Pyjo.IOLoop.Stream` is a container for I/O streams used by
:mod:`Pyjo.IOLoop`. A handle is a socket, an :class:`ssl.SSLSocket` too, or
anything else with a file descriptor, like a pipe.

The end of a ``with`` block closes the stream.

Events
------

:mod:`Pyjo.IOLoop.Stream` inherits all events from :mod:`Pyjo.EventEmitter`
and can emit the following new ones.

close
~~~~~
::

    stream.on('close', lambda stream: ...)

Emitted if the stream gets closed.

drain
~~~~~
::

    stream.on('drain', lambda stream: ...)

Emitted once all data has been written.

error
~~~~~
::

    stream.on('error', lambda stream, err: ...)

Emitted if an error occurs on the stream, fatal if unhandled. The error is
the :class:`OSError` of the handle.

read
~~~~
::

    stream.on('read', lambda stream, chunk: ...)

Emitted if new data arrives on the stream.

timeout
~~~~~~~
::

    stream.on('timeout', lambda stream: ...)

Emitted if the stream has been inactive for too long and will get closed
automatically.

write
~~~~~
::

    stream.on('write', lambda stream, chunk: ...)

Emitted if new data has been written to the stream.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::IOLoop::Stream <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/IOLoop/Stream.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.EventEmitter
import Pyjo.IOLoop
import Pyjo.Reactor

import builtins
import os
import select
import ssl
import sys
import weakref

from collections.abc import AsyncIterator, Callable
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self


if TYPE_CHECKING:
    import Pyjo.Iterator
    import Pyjo.Promise


type Anything = builtins.object

# A callback of a write gets the stream once all data has been written
type DrainCallback = Callable[[Any], Anything]


class Pyjo_IOLoop_Stream(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.IOLoop.Stream` inherits all methods from
    :mod:`Pyjo.EventEmitter` and implements the following new ones.
    """

    def __init__(self, handle: Any = None) -> None:
        """::

            stream = Pyjo.IOLoop.Stream.new(handle)

        Construct a new :mod:`Pyjo.IOLoop.Stream` object.
        """
        super().__init__()

        self.high_water_mark = 1048576
        """::

            size = stream.high_water_mark
            stream.high_water_mark = 1024

        Maximum size of :meth:`write` buffer in bytes before :attr:`can_write`
        is false, defaults to ``1048576`` (1MiB).
        """

        # A bytearray, whose front is cut without copying the rest, as substr of Perl does
        self._buffer = bytearray()
        self._graceful = False
        self._handle: Any = handle
        self._paused = False
        self._read = 0
        self._reactor: weakref.ref[Pyjo.Reactor.object] | None = None
        self._timeout: float = 15
        self._timer: str | None = None
        self._written = 0

    def __del__(self) -> None:
        # Module globals may be gone at the end of the interpreter
        try:
            if not sys.is_finalizing() and getattr(self, '_handle', None) is not None:
                reactor = self._reactor() if self._reactor is not None else None
                Pyjo.Reactor._finalize(self.close, reactor)  # pyright: ignore[reportPrivateUsage]
        except Exception:
            pass

    # Not in Mojolicious: a context manager, which closes the stream where the block ends, as PyPy frees the object only
    # when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    # Not in Mojolicious: an asynchronous iterator of the chunks, as the one of the streams of Node.js
    def __aiter__(self) -> AsyncIterator[bytes]:
        """::

            async for chunk in stream:
                ...

        Same as :meth:`iterate`.
        """
        return aiter(self.iterate())

    @property
    def reactor(self) -> Pyjo.Reactor.object:
        """::

            reactor = stream.reactor
            stream.reactor = Pyjo.Reactor.Poll.new()

        Low-level event reactor, defaults to the ``reactor`` attribute value of
        the global :mod:`Pyjo.IOLoop` singleton. Note that this attribute is
        weakened.
        """
        if self._reactor is None:
            self._reactor = weakref.ref(Pyjo.IOLoop.singleton.reactor)
        if (reactor := self._reactor()) is None:
            raise ReferenceError('weakly-referenced object no longer exists')
        return reactor

    @reactor.setter
    def reactor(self, value: Pyjo.Reactor.object) -> None:
        self._reactor = weakref.ref(value)

    @property
    def bytes_read(self) -> int:
        """::

            num = stream.bytes_read

        Number of bytes received.
        """
        return self._read

    @property
    def bytes_waiting(self) -> int:
        """::

            num = stream.bytes_waiting

        Number of bytes that have been enqueued with :meth:`write` and are
        waiting to be written.
        """
        return len(self._buffer)

    @property
    def bytes_written(self) -> int:
        """::

            num = stream.bytes_written

        Number of bytes written.
        """
        return self._written

    @property
    def can_write(self) -> bool:
        """::

            boolean = stream.can_write

        True if calling :meth:`write` is safe.
        """
        return self._handle is not None and self.bytes_waiting < self.high_water_mark

    def close(self) -> None:
        """::

            stream.close()

        Close stream immediately.
        """
        reactor = self._reactor() if self._reactor is not None else Pyjo.IOLoop.singleton.reactor
        if reactor is None:
            # Not in Mojolicious: the handle of a stream whose reactor is gone is closed, as Perl frees it with the
            # stream
            if (handle := self._handle) is not None:
                self._handle = None
                handle.close()
            return
        self.timeout = 0
        if (handle := self._handle) is None:
            return
        self._handle = None
        reactor.remove(handle)
        # Perl closes the handle it frees at once, Python later, as PyPy does when its garbage collector runs
        handle.close()
        self.emit('close')

    def close_gracefully(self) -> None:
        """::

            stream.close_gracefully()

        Close stream gracefully.
        """
        if self.is_writing:
            self._graceful = True
        else:
            self.close()

    # Not in Mojolicious: the end of a graceful close, as end of promise-writable, which subscribes the event close before
    # the close, which comes at once when nothing is waiting to be written
    def close_gracefully_p(self) -> 'Pyjo.Promise.object':
        """::

            promise = stream.close_gracefully_p()

        Same as :meth:`close_gracefully`, but returns a :mod:`Pyjo.Promise`
        object, which is fulfilled once the stream has been closed, also when it
        is closed already. ::

            await stream.write_p(b'Bye!')
            await stream.close_gracefully_p()
        """
        import Pyjo.Promise

        if self._handle is None:
            return Pyjo.Promise.resolve()
        promise = self.once_p('close')
        self.close_gracefully()
        return promise

    @property
    def handle(self) -> Any:
        """::

            handle = stream.handle

        Get handle for stream, usually a :class:`socket.socket` or
        :class:`ssl.SSLSocket` object.
        """
        return self._handle

    @property
    def is_readable(self) -> bool:
        """::

            boolean = stream.is_readable

        Quick non-blocking check if stream is readable, useful for identifying
        tainted sockets.
        """
        self._again()
        if (handle := self._handle) is None:
            return False
        return bool(select.select([handle], [], [], 0)[0])

    @property
    def is_writing(self) -> bool:
        """::

            boolean = stream.is_writing

        Check if stream is writing.
        """
        if self._handle is None:
            return False
        return bool(len(self._buffer)) or self.has_subscribers('drain')

    # Not in Mojolicious: the chunks as an asynchronous iterator, as iterate of promise-readable
    def iterate(self, size: int | None = None) -> 'Pyjo.Iterator.object[bytes]':
        """::

            async for chunk in stream.iterate():
                ...
            async for chunk in stream.iterate(1024):
                ...

        The chunks as a :mod:`Pyjo.Iterator`, at most ``size`` bytes each,
        until the end of the stream, which :meth:`read_p` takes. ::

            # Echo in capitals
            async for chunk in stream:
                await stream.write_p(chunk.upper())

            # The same in a chain
            async for chunk in stream.iterate().map(bytes.upper):
                await stream.write_p(chunk)
        """
        import Pyjo.Iterator

        return Pyjo.Iterator.object(self._chunks().iterate(size))

    # Not in Mojolicious: the event close of a stream that is closed already, as once of promise-writable
    def once_p(self, name: str) -> 'Pyjo.Promise.object':
        """::

            promise = stream.once_p('close')

        Same as :meth:`~Pyjo.EventEmitter.Pyjo_EventEmitter.once_p` of
        :mod:`Pyjo.EventEmitter`, but fulfilled at once for the event
        ``close`` of a stream that is closed already, as it comes no more.
        """
        import Pyjo.Promise

        if name == 'close' and self._handle is None:
            return Pyjo.Promise.resolve()
        return super().once_p(name)

    # Not in Mojolicious: everything until the end, as readAll of promise-readable
    def read_all_p(self) -> 'Pyjo.Promise.object':
        """::

            promise = stream.read_all_p()

        Return a :mod:`Pyjo.Promise` object, which is fulfilled with all the
        data of the stream until its end as a :mod:`Pyjo.String.Bytes`
        object, as :meth:`read_p` takes it. ::

            data = await stream.read_all_p()
        """
        # Imported here, as Pyjo.Promise uses Pyjo.IOLoop
        import Pyjo.Promise
        import Pyjo.String.Bytes

        # The first chunk is asked for at once, as the reactor of asyncio runs a coroutine later, when the stream may have
        # read it already
        first = self.read_p()

        async def read() -> Pyjo.String.Bytes.object:
            chunks: list[bytes] = []
            chunk = await first
            while chunk is not None:
                chunks.append(chunk)
                chunk = await self.read_p()
            return Pyjo.String.Bytes.new(b''.join(chunks))

        return Pyjo.Promise.new(read())

    # Not in Mojolicious: the next chunk, as read of promise-readable, which the stream reads only while a promise waits
    def read_p(self, size: int | None = None) -> 'Pyjo.Promise.object':
        """::

            promise = stream.read_p()
            promise = stream.read_p(1024)

        Return a :mod:`Pyjo.Promise` object, which is fulfilled with the next
        chunk of the stream, at most ``size`` bytes, or ``None`` at its end,
        the event ``close``, or ``end`` of :mod:`Pyjo.IOLoop.Stdio`, or when it
        is closed already, and rejected with the error of the event ``error``,
        or a :class:`TimeoutError` when the stream has been inactive for too
        long. The stream reads only
        while a promise waits, and stops in between, so that a chunk that
        comes before is kept for the next promise, and a stream that is read
        no more stops reading, as the streams of Node.js in their paused mode.
        The subscribers of the event ``read`` get the chunks that the stream
        reads then. ::

            # Read until the end
            while (chunk := await stream.read_p()) is not None:
                print(chunk)
        """
        return self._chunks().next_p(size)

    def start(self) -> None:
        """::

            stream.start()

        Start or resume watching for new data on the stream.
        """
        # Resume
        if (handle := self._handle) is None:
            return
        reactor = self.reactor
        if self._paused:
            self._paused = False
            reactor.watch(handle, True, self.is_writing)
            return

        ref = weakref.ref(self)

        def cb(reactor: Any, writable: bool) -> None:
            if (stream := ref()) is not None:
                stream._write() if writable else stream._read_handle()

        self.timeout = self._timeout
        reactor.io(handle, cb)

    def steal_handle(self) -> Any:
        """::

            handle = stream.steal_handle()

        Steal :attr:`handle` and prevent it from getting closed automatically.
        """
        handle, self._handle = self._handle, None
        if handle is not None:
            self.reactor.remove(handle)
        return handle

    def stop(self) -> None:
        """::

            stream.stop()

        Stop watching for new data on the stream.
        """
        if self._handle is not None and not self._paused:
            self._paused = True
            self.reactor.watch(self._handle, False, self.is_writing)

    @property
    def timeout(self) -> float:
        """::

            timeout = stream.timeout
            stream.timeout = 45

        Maximum amount of time in seconds stream can be inactive before getting
        closed automatically, defaults to ``15``. Setting the value to ``0``
        will allow this stream to be inactive indefinitely.
        """
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = value

        reactor = self.reactor
        if self._timer is not None:
            if not self._timeout:
                timer, self._timer = self._timer, None
                reactor.remove(timer)
            else:
                reactor.again(self._timer, self._timeout)

        elif self._timeout:
            ref = weakref.ref(self)

            def timeout(reactor: Any) -> None:
                if (stream := ref()) is not None and stream._timer is not None:
                    stream._timer = None
                    stream.emit('timeout').close()

            self._timer = reactor.timer(value, timeout)

    def write(self, chunk: bytes, cb: DrainCallback | None = None) -> Self:
        """::

            stream = stream.write(chunk)
            stream = stream.write(chunk, lambda stream: ...)

        Enqueue data to be written to the stream as soon as possible, the
        optional drain callback will be executed once all data has been
        written.
        """
        # Left out from Mojolicious: utf8::downgrade, as the chunk is bytes already
        self._buffer += chunk
        if cb is not None:
            self.once('drain', cb)
        elif not len(self._buffer):
            return self
        if self._handle is not None:
            self.reactor.watch(self._handle, not self._paused, True)

        return self

    # Not in Mojolicious: the end of a write, as write of promise-writable
    def write_p(self, chunk: bytes) -> 'Pyjo.Promise.object':
        """::

            promise = stream.write_p(chunk)

        Same as :meth:`write`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled once all data has been written, and rejected if the stream
        closes before, or is closed already, or with a :class:`TimeoutError`
        when it has been inactive for too long. ::

            await stream.write_p(b'Hello World!')
        """
        import Pyjo.Exception
        import Pyjo.Promise

        if self._handle is None:
            return Pyjo.Promise.reject(Pyjo.Exception.new('Stream closed before all data has been written'))
        promise = Pyjo.Promise.new()

        def closed(stream: Any) -> None:
            self.unsubscribe('timeout', inactive)
            promise.reject(Pyjo.Exception.new('Stream closed before all data has been written'))

        def timeout(stream: Any) -> None:
            self.unsubscribe('close', wrapper)
            promise.reject(TimeoutError('Inactivity timeout'))

        wrapper = self.once('close', closed)
        inactive = self.once('timeout', timeout)

        def drained(stream: Any) -> None:
            self.unsubscribe('close', wrapper).unsubscribe('timeout', inactive)
            promise.resolve()

        self.write(chunk, drained)
        return self._hold(promise)

    # Not in Mojolicious: the pull of the chunks, which a stream that is closed already has ended
    def _chunks(self) -> Any:
        pull = self._pull('read', True)
        if self._handle is None:
            pull.end()
        return pull

    def _again(self) -> None:
        if self._timer is not None:
            self.reactor.again(self._timer)

    # Renamed from Mojolicious: _read, the attribute _read is the number of bytes read
    def _read_handle(self) -> None:
        handle = self._handle
        try:
            chunk = handle.recv(131072) if hasattr(handle, 'recv') else os.read(handle.fileno(), 131072)
        except OSError as e:
            # Retry
            if isinstance(e, (BlockingIOError, InterruptedError, ssl.SSLWantReadError, ssl.SSLWantWriteError)):
                return

            # Closed (maybe real error)
            # Unlike Mojolicious: EPIPE is a close too, as ECONNRESET is, as a read of TLS writes the session tickets
            # of TLS 1.3 with OpenSSL 3.5, which fails when the peer is gone, and ECONNABORTED, which a read of Windows
            # fails with after a write to a peer that has closed the socket
            if isinstance(e, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
                return self.close()
            return self.emit('error', e).close()

        self._read += len(chunk)
        if not len(chunk):
            return self.close()
        self.emit('read', chunk)._again()

    def _write(self) -> None:
        # Handle errors only when reading (to avoid timing problems)
        handle = self._handle
        if len(self._buffer):
            # A copy of the front of the buffer, as the socket of TLS of PyPy keeps the data that it sends exported, so
            # that the buffer cannot change its size, and at most as much as a read, so that a write copies no more
            data = bytes(self._buffer[:131072])
            try:
                written = handle.send(data) if hasattr(handle, 'send') else os.write(handle.fileno(), data)
            except OSError:
                return
            self._written += written
            chunk = data[:written]
            del self._buffer[:written]
            self.emit('write', chunk)._again()

        if not len(self._buffer):
            self.emit('drain')
        if self.is_writing:
            return
        if self._graceful:
            return self.close()
        if self._handle is not None:
            self.reactor.watch(self._handle, not self._paused, False)


new = Pyjo_IOLoop_Stream.new
object = Pyjo_IOLoop_Stream
Stream = Pyjo_IOLoop_Stream
