"""
Pyjo.IOLoop.Messages - Messages on a stream
===========================================
::

    from Pyjo.IOLoop.Messages import Messages
    from Pyjo.IOLoop.Stdio import Stdio

    # Echo the lines of the standard input in capitals
    messages = Messages(Stdio())
    messages.on('message', lambda messages, message: messages.send(message.upper()))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.IOLoop.Messages
    import Pyjo.IOLoop.Stdio

    # Echo the lines of the standard input in capitals
    messages = Pyjo.IOLoop.Messages.new(Pyjo.IOLoop.Stdio.new())
    messages.on('message', lambda messages, message: messages.send(message.upper()))
    messages.on('close', lambda messages: messages.stream.reactor.stop())
    messages.start()

    # The messages of the Language Server Protocol, framed by Content-Length headers
    messages = Pyjo.IOLoop.Messages.new(stream, framing=Pyjo.IOLoop.Messages.ContentLength())

    # The standard output and input of a server in a child process
    child = Pyjo.IOLoop.ChildProcess.new().spawn(['./server.py'])
    messages = Pyjo.IOLoop.Messages.new(child.stdout, output=child.stdin)
    messages.send('{"jsonrpc": "2.0", "method": "update", "params": [1]}')

    # Start reactor if necessary
    if not messages.stream.reactor.is_running:
        messages.stream.reactor.start()

:mod:`Pyjo.IOLoop.Messages` is a stream of messages on a
:mod:`Pyjo.IOLoop.Stream`, a stream of bytes, as a connection of TCP or of a
Unix domain socket, the standard input and output of :mod:`Pyjo.IOLoop.Stdio`,
or the standard output and input of a :mod:`Pyjo.IOLoop.ChildProcess`. The
framing of the messages tells where one ends and the next begins, as the line
of :class:`Lines`, the default, the headers of :class:`ContentLength` or the
length of :class:`LengthPrefix`. A message is :class:`bytes`, and the frame of
a message is written as a whole, so that the frames of two messages never
interleave.

A message that would be larger than :attr:`~Pyjo_IOLoop_Messages.max_message_size`
closes the stream gracefully with an error, as the stream can not tell where
the next message begins: nothing more is read, and the messages that have been
sent are written.

A framing is an object with the method ``decode``, which takes the next
message that is whole from the front of a :class:`bytearray` of what has been
read and returns it, or ``None`` until it is whole, raising a
:mod:`Pyjo.Exception` for a message that is larger than the maximum size, and
the method ``encode``, which returns the frame of a message. A framing keeps what it knows of the stream that it decodes, as the
length of the message whose headers it has read, so each stream of messages
has one of its own. ::

    # Messages of netstrings, as 3:abc,
    class Netstrings:
        def decode(self, buffer, max_size):
            if (colon := buffer.find(b':')) < 0:
                return None
            length = int(buffer[:colon])
            if max_size and length > max_size:
                raise Pyjo.Exception.new('Maximum message size exceeded')
            if len(buffer) < colon + length + 2:
                return None
            message = bytes(buffer[colon + 1 : colon + 1 + length])
            del buffer[: colon + length + 2]
            return message

        def encode(self, message):
            return b'%d:%s,' % (len(message), message)

    messages = Pyjo.IOLoop.Messages.new(stream, framing=Netstrings())

Events
------

:mod:`Pyjo.IOLoop.Messages` inherits all events from :mod:`Pyjo.EventEmitter`
and can emit the following new ones.

close
~~~~~
::

    messages.on('close', lambda messages: ...)

Emitted once the stream has been closed, or the input, when the input and the
output are two, as the peer ends its output when it has no more to send.

end
~~~
::

    messages.on('end', lambda messages: ...)

Emitted once the input has ended, as the event ``end`` of
:mod:`Pyjo.IOLoop.Stdio`, while messages can still be sent, as the responses of
the requests that are in progress. Without a subscriber of this event, the
stream closes gracefully, once all messages have been written; with one, the
subscriber closes it. ::

    messages.on('end', lambda messages: messages.close_gracefully())

error
~~~~~
::

    messages.on('error', lambda messages, err: ...)

Emitted if an error occurs on the stream, as a message that is larger than the
maximum size, fatal if unhandled. ::

    messages.on('error', lambda messages, err: print(f'This looks bad: {err}'))

message
~~~~~~~
::

    messages.on('message', lambda messages, message: ...)

Emitted for each message that has arrived, without its framing. ::

    messages.on('message', lambda messages, message: print(f'Message: {message!r}'))

timeout
~~~~~~~
::

    messages.on('timeout', lambda messages: ...)

Emitted if the stream has been inactive for too long and will get closed
automatically, as the event ``timeout`` of :mod:`Pyjo.IOLoop.Stream`.

See also
--------

:mod:`Pyjo.IOLoop.Stream`, :mod:`Pyjo.IOLoop.Stdio`, :mod:`Pyjoyment`,
https://mojolicious.org.

It has no counterpart in Mojolicious, and the framings follow the transport
stdio of the Model Context Protocol, the base protocol of the Language Server
Protocol, and Native Messaging of the extensions of the browsers.

Classes
-------
"""

import Pyjo.Base
import Pyjo.EventEmitter
import Pyjo.Exception
import Pyjo.IOLoop.Stream
import Pyjo.Iterator
import Pyjo.Promise

import os
import re
import sys

from collections.abc import AsyncIterator, Callable
from typing import Any, Literal, Protocol, Self


class Framing(Protocol):
    """
    The framing of the messages of a stream, as :class:`Lines`.
    """

    def decode(self, buffer: bytearray, max_size: int) -> bytes | None:
        """::

            message = framing.decode(buffer, 16777216)

        Take the next message that is whole from the front of ``buffer`` and
        return it, without its framing, or ``None`` until it is whole, or raise
        a :mod:`Pyjo.Exception` for a message that is larger than ``max_size``,
        unless it is ``0``.
        """
        ...

    def encode(self, message: bytes) -> bytes:
        """::

            frame = framing.encode(b'Hello')

        Return the frame of a message.
        """
        ...


class Lines(Pyjo.Base.object):
    """
    Messages of one line each, as the transport stdio of the Model Context
    Protocol and many protocols of text have them, which end with a line feed,
    or a carriage return and a line feed, which :attr:`terminator` writes. A
    message has no line feed. ::

        framing = Pyjo.IOLoop.Messages.Lines.new()
        framing = Pyjo.IOLoop.Messages.Lines.new(terminator=b'\\r\\n')
    """

    def __init__(self, terminator: bytes = b'\n') -> None:
        self.terminator = terminator
        """::

            terminator = framing.terminator
            framing.terminator = b'\\r\\n'

        Terminator of the lines that are written, defaults to ``b'\\n'``. Both
        are read.
        """

        # The part of the buffer that has no line feed, which the next decode does not search again
        self._searched = 0

    def decode(self, buffer: bytearray, max_size: int) -> bytes | None:
        if (end := buffer.find(b'\n', self._searched)) < 0:
            self._searched = len(buffer)

            # A line that is longer already, without a carriage return that may end it
            if max_size and len(buffer) - buffer.endswith(b'\r') > max_size:
                raise Pyjo.Exception.new('Maximum message size exceeded')
            return None
        message = bytes(buffer[: end - 1 if end and buffer[end - 1] == 13 else end])
        if max_size and len(message) > max_size:
            raise Pyjo.Exception.new('Maximum message size exceeded')
        del buffer[: end + 1]
        self._searched = 0
        return message

    def encode(self, message: bytes) -> bytes:
        if b'\n' in message:
            raise Pyjo.Exception.new('Message with a line feed')
        return message + self.terminator


class ContentLength(Pyjo.Base.object):
    """
    Messages with headers, of which ``Content-Length`` has their size, as the
    base protocol of the Language Server Protocol and of the Debug Adapter
    Protocol have them. The other headers, as ``Content-Type``, are read and
    not written. ::

        framing = Pyjo.IOLoop.Messages.ContentLength.new()
    """

    max_header_size = 8192
    """::

        size = framing.max_header_size
        framing.max_header_size = 1024

    Maximum size of the headers of a message in bytes, defaults to ``8192``.
    """

    def __init__(self) -> None:
        # The size of the message whose headers have been read
        self._length: int | None = None

    def decode(self, buffer: bytearray, max_size: int) -> bytes | None:
        if (length := self._length) is None:
            if (end := buffer.find(b'\r\n\r\n')) < 0:
                if len(buffer) > self.max_header_size:
                    raise Pyjo.Exception.new('Maximum header size exceeded')
                return None
            headers = bytes(buffer[:end]).decode('latin-1')
            if not (match := re.search(r'(?im)^content-length:[ \t]*(\d+)[ \t]*$', headers)):
                raise Pyjo.Exception.new('Message without Content-Length')
            length = int(match[1])
            if max_size and length > max_size:
                raise Pyjo.Exception.new('Maximum message size exceeded')
            del buffer[: end + 4]
            self._length = length
        if len(buffer) < length:
            return None
        message = bytes(buffer[:length])
        del buffer[:length]
        self._length = None
        return message

    def encode(self, message: bytes) -> bytes:
        return b'Content-Length: %d\r\n\r\n%s' % (len(message), message)


class LengthPrefix(Pyjo.Base.object):
    """
    Messages that follow their size, as an unsigned integer of :attr:`size`
    bytes, as Native Messaging of the extensions of the browsers has them, with
    4 bytes in the native byte order. ::

        framing = Pyjo.IOLoop.Messages.LengthPrefix.new()
        framing = Pyjo.IOLoop.Messages.LengthPrefix.new(size=2, byteorder='big')
    """

    def __init__(self, size: int = 4, byteorder: Literal['little', 'big'] = sys.byteorder) -> None:
        self.size = size
        """::

            size = framing.size
            framing.size = 2

        Size of the length of a message in bytes, defaults to ``4``.
        """

        self.byteorder: Literal['little', 'big'] = byteorder
        """::

            byteorder = framing.byteorder
            framing.byteorder = 'big'

        Byte order of the length of a message, ``'little'`` or ``'big'``,
        defaults to the native one, :data:`sys.byteorder`.
        """

    def decode(self, buffer: bytearray, max_size: int) -> bytes | None:
        size = self.size
        if len(buffer) < size:
            return None
        length = int.from_bytes(buffer[:size], self.byteorder)
        if max_size and length > max_size:
            raise Pyjo.Exception.new('Maximum message size exceeded')
        if len(buffer) < size + length:
            return None
        message = bytes(buffer[size : size + length])
        del buffer[: size + length]
        return message

    def encode(self, message: bytes) -> bytes:
        try:
            return len(message).to_bytes(self.size, self.byteorder) + message
        except OverflowError:
            raise Pyjo.Exception.new('Message too large for its length') from None


class Pyjo_IOLoop_Messages(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.IOLoop.Messages` inherits all methods from
    :mod:`Pyjo.EventEmitter` and implements the following new ones.
    """

    def __init__(
        self,
        stream: Pyjo.IOLoop.Stream.object,
        *,
        framing: Framing | None = None,
        output: Pyjo.IOLoop.Stream.object | None = None,
    ) -> None:
        """::

            messages = Pyjo.IOLoop.Messages.new(stream)
            messages = Pyjo.IOLoop.Messages.new(stream, framing=Pyjo.IOLoop.Messages.ContentLength())
            messages = Pyjo.IOLoop.Messages.new(child.stdout, output=child.stdin)

        Construct a new :mod:`Pyjo.IOLoop.Messages` object, which reads and
        writes ``stream``, or reads it and writes ``output``.
        """
        super().__init__()

        self.framing: Framing = framing if framing is not None else Lines()
        """::

            framing = messages.framing
            messages.framing = Pyjo.IOLoop.Messages.ContentLength()

        Framing of the messages, defaults to a :class:`Lines` object.
        """

        self.stream = stream
        """::

            stream = messages.stream

        :mod:`Pyjo.IOLoop.Stream` object that the messages are read from, and
        written to, unless :attr:`output` is another one.
        """

        self.output = output if output is not None else stream
        """::

            stream = messages.output

        :mod:`Pyjo.IOLoop.Stream` object that the messages are written to,
        defaults to :attr:`stream`.
        """

        self._buffer = bytearray()
        self._closed = False
        self._failed = False
        self._max_message_size: int | None = None

        # The stream refers to this object until it closes, which the subscribers that it keeps drop
        self._subscribed: list[tuple[Pyjo.IOLoop.Stream.object, str, Callable[..., Any]]] = []

        def read(stream: Any, chunk: bytes) -> None:
            self._read(chunk)

        def end(stream: Any) -> None:
            self._end()

        def close(stream: Pyjo.IOLoop.Stream.object) -> None:
            self._close(stream)

        def error(stream: Any, e: Exception) -> None:
            self.emit('error', e)

        def timeout(stream: Any) -> None:
            self.emit('timeout')

        self._subscribe(stream, 'read', read)
        self._subscribe(stream, 'end', end)
        for handle in (stream, self.output) if self.output is not stream else (stream,):
            self._subscribe(handle, 'close', close)
            self._subscribe(handle, 'error', error)
            self._subscribe(handle, 'timeout', timeout)

    def __aiter__(self) -> AsyncIterator[bytes]:
        """::

            async for message in messages:
                ...

        Same as :meth:`iterate`.
        """
        return aiter(self.iterate())

    def close(self) -> None:
        """::

            messages.close()

        Close the stream immediately.
        """
        self.stream.close()
        self.output.close()

    def close_gracefully(self) -> None:
        """::

            messages.close_gracefully()

        Close the stream gracefully, once all messages have been written, or,
        when the input and the output are two, as the standard input and output
        of a child process, the output, and the input is read until the peer
        ends it, so that the responses of the peer still come in. ::

            # The last request of a server of the standard input and output, and its response
            messages.send(request).close_gracefully()
        """
        self.output.close_gracefully()

    def close_gracefully_p(self) -> Pyjo.Promise.object:
        """::

            promise = messages.close_gracefully_p()

        Same as :meth:`close_gracefully`, but returns a :mod:`Pyjo.Promise`
        object, which is fulfilled once the stream has been closed, also when it
        is closed already. ::

            await messages.send_p('Bye!')
            await messages.close_gracefully_p()
        """
        if self._closed:
            return Pyjo.Promise.resolve()
        promise = self.once_p('close')
        self.close_gracefully()
        return promise

    def iterate(self) -> Pyjo.Iterator.object[bytes]:
        """::

            async for message in messages.iterate():
                ...

        The messages as a :mod:`Pyjo.Iterator`, until the end of the stream,
        which :meth:`message_p` takes. ::

            # Echo in capitals, one message after another
            async for message in messages:
                await messages.send_p(message.upper())

            # The messages as JSON, in a chain
            async for request in messages.iterate().map(Pyjo.JSON.decode_json):
                ...
        """
        return Pyjo.Iterator.object(self._messages().iterate())

    @property
    def max_message_size(self) -> int:
        """::

            size = messages.max_message_size
            messages.max_message_size = 1024

        Maximum size of a message in bytes, defaults to the value of the
        ``PYJO_MAX_MESSAGE_SIZE`` environment variable or ``16777216``
        (16MiB). Setting the value to ``0`` will allow messages of indefinite
        size.
        """
        if self._max_message_size is None:
            size = os.environ.get('PYJO_MAX_MESSAGE_SIZE')
            self._max_message_size = int(size) if size is not None else 16777216
        return self._max_message_size

    @max_message_size.setter
    def max_message_size(self, value: int) -> None:
        self._max_message_size = value

    def message_p(self) -> Pyjo.Promise.object:
        """::

            promise = messages.message_p()

        Return a :mod:`Pyjo.Promise` object, which is fulfilled with the next
        message, or ``None`` at the end of the stream, the event ``close`` or
        ``end``, or when it is closed already, and rejected with the error of
        the event ``error``, or a :class:`TimeoutError` when the stream has been
        inactive for too long. The stream
        reads only while a promise waits, as :meth:`~Pyjo.IOLoop.Stream.Pyjo_IOLoop_Stream.read_p`
        of :mod:`Pyjo.IOLoop.Stream` does, and the subscribers of the event
        ``message`` get the messages that it reads then. A loop of them handles
        the messages one after another, where the events handle them at the
        same time, as :meth:`~Pyjo.JSON.RPC.Pyjo_JSON_RPC.serve` of
        :mod:`Pyjo.JSON.RPC` does. ::

            while (message := await messages.message_p()) is not None:
                print(message)
        """
        return self._messages().next_p()

    def once_p(self, name: str) -> Pyjo.Promise.object:
        """::

            promise = messages.once_p('close')

        Same as :meth:`~Pyjo.EventEmitter.Pyjo_EventEmitter.once_p` of
        :mod:`Pyjo.EventEmitter`, but fulfilled at once for the event
        ``close`` of a stream that is closed already, as it comes no more.
        """
        if name == 'close' and self._closed:
            return Pyjo.Promise.resolve()
        return super().once_p(name)

    def send(self, message: bytes | str, cb: Callable[[Self], Any] | None = None) -> Self:
        """::

            messages = messages.send(b'Hello')
            messages = messages.send('Hello')
            messages = messages.send('Hello', lambda messages: ...)

        Send a message, :class:`bytes`, or :class:`str` that is encoded in
        UTF-8, the optional drain callback will be executed once all data has
        been written.
        """
        if isinstance(message, str):
            message = message.encode()
        frame = self.framing.encode(message)
        self.output.write(frame, (lambda stream: cb(self)) if cb is not None else None)
        return self

    def send_p(self, message: bytes | str) -> Pyjo.Promise.object:
        """::

            promise = messages.send_p(b'Hello')

        Same as :meth:`send`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled once all data has been written, and rejected if the stream
        closes before, or is closed already, or with a :class:`TimeoutError`
        when it has been inactive for too long. ::

            await messages.send_p('Hello')
        """
        if self._closed:
            return Pyjo.Promise.reject(Pyjo.Exception.new('Stream closed before all data has been written'))
        promise = Pyjo.Promise.new()

        def closed(messages: Any) -> None:
            self.unsubscribe('timeout', inactive)
            promise.reject(Pyjo.Exception.new('Stream closed before all data has been written'))

        def timeout(messages: Any) -> None:
            self.unsubscribe('close', wrapper)
            promise.reject(TimeoutError('Inactivity timeout'))

        wrapper = self.once('close', closed)
        inactive = self.once('timeout', timeout)

        def drained(messages: Any) -> None:
            self.unsubscribe('close', wrapper).unsubscribe('timeout', inactive)
            promise.resolve()

        self.send(message, drained)
        return self._hold(promise)

    def start(self) -> None:
        """::

            messages.start()

        Start or resume reading messages from the stream.
        """
        self.stream.start()

    def stop(self) -> None:
        """::

            messages.stop()

        Stop reading messages from the stream.
        """
        self.stream.stop()

    # The pull of the messages, which a stream that is closed already has ended
    def _messages(self) -> Any:
        pull = self._pull('message', True)
        if self._closed:
            pull.end()
        return pull

    def _close(self, stream: Pyjo.IOLoop.Stream.object) -> None:
        # An output of its own that is closed, while the input is still read until the peer ends it
        if self._closed or stream is not self.stream:
            return
        self._closed = True
        for emitter, name, cb in self._subscribed:
            emitter.unsubscribe(name, cb)
        self._subscribed = []
        if self.output is not self.stream:
            self.output.close_gracefully()
        self.emit('close')

    def _end(self) -> None:
        if self._failed or not self.has_subscribers('end'):
            return self.close_gracefully()
        self.emit('end')

    def _read(self, chunk: bytes) -> None:
        if self._failed:
            return
        buffer = self._buffer
        buffer += chunk
        while not self._closed:
            try:
                message = self.framing.decode(buffer, self.max_message_size)

            # Nothing more is read, as where the next message begins is unknown, and what has been sent is written
            except Pyjo.Exception.object as e:
                self._failed = True
                buffer.clear()
                self.stream.stop()
                try:
                    self.emit('error', e)
                finally:
                    self.close_gracefully()
                return
            if message is None:
                return
            self.emit('message', message)

    def _subscribe(self, emitter: Pyjo.IOLoop.Stream.object, name: str, cb: Callable[..., Any]) -> None:
        emitter.on(name, cb)
        self._subscribed.append((emitter, name, cb))


new = Pyjo_IOLoop_Messages.new
object = Pyjo_IOLoop_Messages
Messages = Pyjo_IOLoop_Messages
