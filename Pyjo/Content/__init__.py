r"""
Pyjo.Content - HTTP content base class
======================================
::

    from Pyjo.Content import Content

    class MyContent(Content):
        def body_contains(self, chunk): ...
        @property
        def body_size(self): ...
        def get_body_chunk(self, offset): ...

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Content

    class MyContent(Pyjo.Content.object):
        def body_contains(self, chunk): ...
        @property
        def body_size(self): ...
        def get_body_chunk(self, offset): ...

:mod:`Pyjo.Content` is an abstract base class for HTTP content containers,
based on `RFC 7230 <https://tools.ietf.org/html/rfc7230>`_ and
`RFC 7231 <https://tools.ietf.org/html/rfc7231>`_, like
:mod:`Pyjo.Content.MultiPart` and :mod:`Pyjo.Content.Single`.

Events
------

:mod:`Pyjo.Content` inherits all events from :mod:`Pyjo.EventEmitter` and can
emit the following new ones.

body
~~~~
::

    content.on('body', lambda content: ...)

Emitted once all headers have been parsed and the body starts. ::

    @content.on('body')
    def body(content):
        if content.headers.header('X-No-MultiPart'):
            content.auto_upgrade = False

drain
~~~~~
::

    content.on('drain', lambda content, offset: ...)

Emitted once all data has been written. ::

    content.on('drain', lambda content, offset: content.write_chunk(str(time.time()).encode()))

read
~~~~
::

    content.on('read', lambda content, chunk: ...)

Emitted when a new chunk of content arrives. ::

    content.on('read', lambda content, chunk: print(f'Streaming: {chunk}'))

sse
~~~
::

    content.on('sse', lambda content, event: ...)

Emitted when a new Server-Sent Event (SSE) connection has been established,
with ``None`` for the event, and for each new event that arrives. Note that
this event is **EXPERIMENTAL** and may change without warning! ::

    @content.on('sse')
    def sse(content, event):
        if event:
            print(f'Type: {event["type"]}, Data: {event["text"]}')
        else:
            print('SSE connection established')

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Content <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Content.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.EventEmitter
import Pyjo.Headers

from Pyjo.SSE import build_event, parse_event

import builtins
import codecs
import os
import re
import zlib

from collections.abc import Callable, Mapping
from typing import Any, Self


type Anything = builtins.object

# A callback of a write gets the content once all data has been written
type DrainCallback = Callable[..., Anything]

BOUNDARY_RE = re.compile(r'multipart.*boundary\s*=\s*(?:"([^"]+)"|([\w\'(),.:?\-+/]+))', re.I)


class Pyjo_Content(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.Content` inherits all methods from :mod:`Pyjo.EventEmitter` and
    implements the following new ones.
    """

    def __init__(
        self,
        *,
        auto_decompress: bool | None = None,
        auto_relax: bool | None = None,
        headers: Pyjo.Headers.object | None = None,
        max_buffer_size: int | None = None,
        max_leftover_size: int | None = None,
        relaxed: bool | None = None,
        skip_body: bool | None = None,
    ) -> None:
        """::

            content = Pyjo.Content.Single.new()
            content = Pyjo.Content.Single.new(headers=Pyjo.Headers.new())

        Construct a new content object.
        """
        super().__init__()

        self.auto_decompress = auto_decompress
        """::

            boolean = content.auto_decompress
            content.auto_decompress = boolean

        Decompress content automatically if :attr:`is_compressed` is true.
        """

        self.auto_relax = auto_relax
        """::

            boolean = content.auto_relax
            content.auto_relax = boolean

        Try to detect when relaxed parsing is necessary.
        """

        self._max_buffer_size: int | None = max_buffer_size
        self._max_leftover_size: int | None = max_leftover_size

        self.relaxed = relaxed
        """::

            boolean = content.relaxed
            content.relaxed = boolean

        Activate relaxed parsing for responses that are terminated with a
        connection close.
        """

        self.skip_body = skip_body
        """::

            boolean = content.skip_body
            content.skip_body = boolean

        Skip body parsing and finish after headers.
        """

        self._headers = headers

        # The state of the parser and of the generator, as the keys of Mojo's hash
        self._body = False
        self._body_buffer: bytes | None = None
        self._buffer = bytearray()
        self._chunk_len = 0
        self._chunk_state: str | None = None
        self._chunked = False
        self._chunks = 0
        self._dynamic = False
        self._eof = False
        self._gz: Any = None
        self._gz_total = 0
        self._header_buffer: bytes | None = None
        self._header_size: int | None = None
        self._limit = False
        self._post_buffer = b''
        self._pre_buffer = bytearray()
        self._raw_size = 0
        self._real_size: int | None = None
        self._size = 0
        self._sse = False
        self._sse_buffer = bytearray()
        self._sse_start = True
        self._state: str | None = None

    @property
    def max_buffer_size(self) -> int:
        """::

            size = content.max_buffer_size
            content.max_buffer_size = 1024

        Maximum size in bytes of buffer for content parser, defaults to the
        value of the ``PYJO_MAX_BUFFER_SIZE`` environment variable or
        ``262144`` (256KiB).
        """
        if self._max_buffer_size is None:
            self._max_buffer_size = int(os.environ.get('PYJO_MAX_BUFFER_SIZE') or 262144)
        return self._max_buffer_size

    @max_buffer_size.setter
    def max_buffer_size(self, value: int) -> None:
        self._max_buffer_size = value

    @property
    def max_leftover_size(self) -> int:
        """::

            size = content.max_leftover_size
            content.max_leftover_size = 1024

        Maximum size in bytes of buffer for pipelined HTTP requests, defaults
        to the value of the ``PYJO_MAX_LEFTOVER_SIZE`` environment variable or
        ``262144`` (256KiB).
        """
        if self._max_leftover_size is None:
            self._max_leftover_size = int(os.environ.get('PYJO_MAX_LEFTOVER_SIZE') or 262144)
        return self._max_leftover_size

    @max_leftover_size.setter
    def max_leftover_size(self, value: int) -> None:
        self._max_leftover_size = value

    @property
    def headers(self) -> Pyjo.Headers.object:
        """::

            headers = content.headers
            content.headers = Pyjo.Headers.new()

        Content headers, defaults to a :mod:`Pyjo.Headers` object.
        """
        if self._headers is None:
            self._headers = Pyjo.Headers.new()
        return self._headers

    @headers.setter
    def headers(self, value: Pyjo.Headers.object) -> None:
        self._headers = value

    def body_contains(self, chunk: bytes) -> bool:
        """::

            boolean = content.body_contains(b'foo bar baz')

        Check if content contains a specific string. Meant to be overloaded in
        a subclass.
        """
        raise NotImplementedError('Method "body_contains" not implemented by subclass')

    @property
    def body_size(self) -> int:
        """::

            size = content.body_size

        Content size in bytes. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "body_size" not implemented by subclass')

    @property
    def boundary(self) -> str | None:
        """::

            boundary = content.boundary

        Extract multipart boundary from ``Content-Type`` header.
        """
        if m := BOUNDARY_RE.search(self.headers.content_type or ''):
            return m[1] if m[1] is not None else m[2]
        return None

    @property
    def charset(self) -> str | None:
        """::

            charset = content.charset

        Extract charset from ``Content-Type`` header.
        """
        if m := re.search(r'charset\s*=\s*"?([^"\s;]+)"?', self.headers.content_type or '', re.I):
            return m[1]
        return None

    def clone(self) -> Self | None:
        """::

            clone = content.clone()

        Return a new content object cloned from this content if possible,
        otherwise return ``None``.
        """
        if self.is_dynamic:
            return None
        return type(self).new(headers=self.headers.clone())

    def generate_body_chunk(self, offset: int) -> bytes | None:
        """::

            chunk = content.generate_body_chunk(0)

        Generate dynamic content.
        """
        if self._body_buffer is None:
            self._body_buffer = b''
        if not len(self._body_buffer):
            self.emit('drain', offset)
        if len(self._body_buffer):
            chunk, self._body_buffer = self._body_buffer, None
            return chunk
        if self._eof:
            return b''

        length = self._number(self.headers.content_length)
        return b'' if length is not None and length == offset else None

    def get_body_chunk(self, offset: int) -> bytes | None:
        """::

            chunk = content.get_body_chunk(0)

        Get a chunk of content starting from a specific position. Meant to be
        overloaded in a subclass.
        """
        raise NotImplementedError('Method "get_body_chunk" not implemented by subclass')

    def get_header_chunk(self, offset: int) -> bytes:
        """::

            chunk = content.get_header_chunk(13)

        Get a chunk of the headers starting from a specific position. Note that
        this method finalizes the content.
        """
        return self._headers_buffer()[offset : offset + 131072]

    @property
    def header_size(self) -> int:
        """::

            size = content.header_size

        Size of headers in bytes. Note that this method finalizes the content.
        """
        return len(self._headers_buffer())

    def headers_contain(self, chunk: bytes) -> bool:
        """::

            boolean = content.headers_contain(b'foo bar baz')

        Check if headers contain a specific string. Note that this method
        finalizes the content.
        """
        return self._headers_buffer().find(chunk) >= 0

    @property
    def is_chunked(self) -> bool:
        """::

            boolean = content.is_chunked

        Check if ``Transfer-Encoding`` header indicates chunked transfer
        encoding.
        """
        return bool(self.headers.transfer_encoding)

    @property
    def is_compressed(self) -> bool:
        """::

            boolean = content.is_compressed

        Check ``Content-Encoding`` header for ``gzip`` value.
        """
        return (self.headers.content_encoding or '').lower() == 'gzip'

    @property
    def is_dynamic(self) -> bool:
        """::

            boolean = content.is_dynamic

        Check if content will be dynamically generated, which prevents
        :meth:`clone` from working.
        """
        return self._dynamic

    @property
    def is_finished(self) -> bool:
        """::

            boolean = content.is_finished

        Check if parser is finished.
        """
        return self._state == 'finished'

    @property
    def is_limit_exceeded(self) -> bool:
        """::

            boolean = content.is_limit_exceeded

        Check if buffer has exceeded :attr:`max_buffer_size`.
        """
        return self._limit

    @property
    def is_multipart(self) -> bool:
        """::

            boolean = content.is_multipart

        False, this is not a :mod:`Pyjo.Content.MultiPart` object.
        """
        return False

    @property
    def is_parsing_body(self) -> bool:
        """::

            boolean = content.is_parsing_body

        Check if body parsing started yet.
        """
        return self._state == 'body'

    @property
    def is_sse(self) -> bool:
        """::

            boolean = content.is_sse

        Check if ``Content-Type`` header indicates Server-Sent Events (SSE).
        Note that this method is **EXPERIMENTAL** and may change without
        warning!
        """
        return (self.headers.content_type or '') == 'text/event-stream'

    def leftovers(self) -> bytes:
        """::

            data = content.leftovers()

        Get leftover data from content parser.
        """
        return bytes(self._buffer)

    def parse(self, chunk: bytes | None = None) -> 'Pyjo_Content':
        r"""::

            content = content.parse(b'Content-Length: 12\x0d\x0a\x0d\x0aHello World!')

        Parse content chunk.
        """
        # Headers
        self._parse_until_body(chunk)
        if self._state == 'headers':
            return self

        # Chunked content
        if self._real_size is None:
            self._real_size = 0
        if self.is_chunked:
            self._parse_chunked()
            if self._chunk_state == 'finished':
                self._state = 'finished'

        # SSE
        elif self.is_sse:
            self._parse_sse()

        # Not chunked, pass through to second buffer
        else:
            self._real_size += len(self._pre_buffer)
            limit = self.is_finished and len(self._buffer) > self.max_leftover_size
            if not limit:
                self._buffer += self._pre_buffer
            self._pre_buffer = bytearray()

        # No content
        if self.skip_body:
            self._state = 'finished'
            return self

        # Relaxed parsing
        headers = self.headers
        length = headers.content_length if headers.content_length is not None else ''
        if self.auto_relax and not len(length):
            connection = (headers.connection or '').lower()
            if connection == 'close' or not connection:
                self.relaxed = True

        # Chunked or relaxed content
        if self.is_chunked or self.relaxed:
            self._decompress(bytes(self._buffer))
            self._size += len(self._buffer)
            self._buffer = bytearray()
            return self

        # Normal content
        size = self._number(length) or 0
        if (need := size - self._size) > 0:
            have = len(self._buffer)
            take = int(need) if need < have else have
            chunk = bytes(self._buffer[:take])
            del self._buffer[:take]
            self._decompress(chunk)
            self._size += len(chunk)
        if size <= self.progress:
            self._state = 'finished'

        return self

    def parse_body(self, chunk: bytes | None = None) -> 'Pyjo_Content':
        """::

            content = content.parse_body(b'Hi!')

        Parse body chunk and skip headers.
        """
        self._state = 'body'
        return self.parse(chunk)

    @property
    def progress(self) -> int:
        """::

            size = content.progress

        Size of content already received from message in bytes.
        """
        if self._state not in ('body', 'finished'):
            return 0
        return self._raw_size - (self._header_size or 0)

    def write(self, chunk: bytes | None = None, cb: DrainCallback | None = None) -> Self:
        """::

            content = content.write()
            content = content.write(b'')
            content = content.write(chunk)
            content = content.write(chunk, lambda content, offset: ...)

        Write dynamic content non-blocking, the optional drain callback will
        be executed once all data has been written. Calling this method
        without a chunk of data will finalize the :attr:`headers` and allow
        for dynamic content to be written later. You can write an empty chunk
        of data at any time to end the stream. ::

            # Make sure previous chunk of data has been written before continuing
            content.write(
                b'He',
                lambda content, offset: content.write(b'llo!', lambda content, offset: content.write(b'')),
            )
        """
        self._dynamic = True
        if chunk is not None:
            self._body_buffer = (self._body_buffer or b'') + chunk
        if cb is not None:
            self.once('drain', cb)
        if chunk is not None and not len(chunk):
            self._eof = True

        return self

    def write_chunk(self, chunk: bytes | None = None, cb: DrainCallback | None = None) -> Self:
        """::

            content = content.write_chunk()
            content = content.write_chunk(b'')
            content = content.write_chunk(chunk)
            content = content.write_chunk(chunk, lambda content, offset: ...)

        Write dynamic content non-blocking with chunked transfer encoding, the
        optional drain callback will be executed once all data has been
        written. Calling this method without a chunk of data will finalize the
        :attr:`headers` and allow for dynamic content to be written later. You
        can write an empty chunk of data at any time to end the stream. ::

            # Make sure previous chunk of data has been written before continuing
            content.write_chunk(
                b'He',
                lambda content, offset: content.write_chunk(b'llo!', lambda content, offset: content.write_chunk(b'')),
            )
        """
        if not self._chunked:
            self.headers.transfer_encoding = 'chunked'
        self._chunked = self._dynamic = True

        if chunk is not None:
            self._body_buffer = (self._body_buffer or b'') + self._build_chunk(chunk)
        if cb is not None:
            self.once('drain', cb)
        if chunk is not None and not len(chunk):
            self._eof = True

        return self

    def write_sse(self, event: Mapping[str, Any] | None = None, cb: DrainCallback | None = None) -> Self:
        """::

            content = content.write_sse()
            content = content.write_sse(event)
            content = content.write_sse(event, lambda content, offset: ...)

        Write Server-Sent Event (SSE) non-blocking, the optional drain callback
        will be executed once all data has been written. Calling this method
        without an event will finalize the response headers and allow for
        events to be written later. Note that this method is **EXPERIMENTAL**
        and may change without warning!
        """
        if not self._sse:
            self.headers.content_type = 'text/event-stream'
        self._sse = True

        if event is None:
            return self.write()
        return self.write(build_event(event), cb)

    def _build_chunk(self, chunk: bytes) -> bytes:
        # End
        if not len(chunk):
            return b'\x0d\x0a0\x0d\x0a\x0d\x0a'

        # First chunk has no leading CRLF
        crlf = b'\x0d\x0a' if self._chunks else b''
        self._chunks += 1
        return crlf + f'{len(chunk):x}'.encode() + b'\x0d\x0a' + chunk

    def _decompress(self, chunk: bytes) -> None:
        # No compression
        if not (self.auto_decompress and self.is_compressed):
            self.emit('read', chunk)
            return

        # Decompress
        out = self._inflate(chunk)
        self.emit('read', out)

        # Replace Content-Encoding with Content-Length
        if self._gz.eof:
            self.headers.content_length = self._gz_total
            self.headers.remove('Content-Encoding')

        # Check buffer size
        if len(self._post_buffer) > self.max_buffer_size:
            self._state, self._limit = 'finished', True

    # Renamed from Mojolicious: _headers, the attribute _headers is the headers
    def _headers_buffer(self) -> bytes:
        if self._header_buffer is None:
            headers = self.headers.to_bytes()
            self._header_buffer = headers + b'\x0d\x0a\x0d\x0a' if headers else b'\x0d\x0a'
        return self._header_buffer

    def _parse_chunked(self) -> None:
        # Trailing headers
        if self._chunk_state == 'trailing_headers':
            return self._parse_chunked_trailing_headers()

        while length := len(self._pre_buffer):
            # Start new chunk (ignore the chunk extension)
            if not self._chunk_len:
                if not (m := re.match(rb'(?:\x0d?\x0a)?([0-9a-fA-F]+).*\x0a', self._pre_buffer)):
                    break
                end, self._chunk_len = m.end(), int(m[1], 16)
                del self._pre_buffer[:end]
                if self._chunk_len:
                    continue

                # Last chunk
                self._chunk_state = 'trailing_headers'
                break

            # Remove as much as possible from payload
            if self._chunk_len < length:
                length = self._chunk_len
            self._buffer += self._pre_buffer[:length]
            del self._pre_buffer[:length]
            self._real_size = (self._real_size or 0) + length
            self._chunk_len -= length

        # Trailing headers
        if self._chunk_state == 'trailing_headers':
            self._parse_chunked_trailing_headers()

        # Check buffer size
        if len(self._pre_buffer) > self.max_buffer_size:
            self._state, self._limit = 'finished', True

    def _parse_chunked_trailing_headers(self) -> None:
        headers = self.headers.parse(self._pre_buffer)
        self._pre_buffer = bytearray()
        if not headers.is_finished:
            return
        self._chunk_state = 'finished'

        # Take care of leftover and replace Transfer-Encoding with Content-Length
        self._buffer += headers.leftovers()
        headers.remove('Transfer-Encoding')
        if not headers.content_length:
            headers.content_length = self._real_size

    def _parse_headers(self) -> None:
        headers = self.headers.parse(self._pre_buffer)
        self._pre_buffer = bytearray()
        if not headers.is_finished:
            return
        self._state = 'body'

        # Take care of leftovers
        leftovers = headers.leftovers()
        self._pre_buffer = bytearray(leftovers)
        self._header_size = self._raw_size - len(leftovers)

    def _inflate(self, chunk: bytes) -> bytes:
        # Decompress, as Compress::Raw::Zlib does with WANT_GZIP
        self._post_buffer += chunk
        if self._gz is None:
            self._gz = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
        gz = self._gz
        try:
            out = gz.decompress(self._post_buffer)
            self._post_buffer = gz.unused_data
        except zlib.error:
            out = b''
        self._gz_total += len(out)
        return out

    def _parse_sse(self) -> None:
        # Connection established, with None for the event that Mojo leaves out
        if not self._sse:
            self.emit('sse', None)
        self._sse = True

        # Unlike Mojolicious: the events of a compressed stream are parsed from the decompressed bytes, where Mojo parses
        # the compressed ones and finds no event
        buffer = self._pre_buffer
        if self.auto_decompress and self.is_compressed:
            self._sse_buffer += self._inflate(bytes(self._pre_buffer))
            self._pre_buffer = bytearray()
            buffer = self._sse_buffer

        # Unlike Mojolicious: one byte order mark at the start of the stream, which HTML ignores, decided once with the
        # first bytes of the stream, which is UTF-8, where Mojo makes it a part of the name of the first field
        if self._sse_start:
            if len(buffer) < len(codecs.BOM_UTF8) and codecs.BOM_UTF8.startswith(buffer):
                return
            if buffer.startswith(codecs.BOM_UTF8):
                del buffer[: len(codecs.BOM_UTF8)]
            self._sse_start = False

        # Parse SSE
        while event := parse_event(buffer):
            self.emit('sse', event)

        # Check buffer size
        if len(buffer) > self.max_buffer_size or len(self._post_buffer) > self.max_buffer_size:
            self._state, self._limit = 'finished', True

    # Perl's looks_like_number and the number of a string
    @staticmethod
    def _number(value: str | int | float | None) -> int | float | None:
        if value is None:
            return None
        if isinstance(value, int | float):
            return value
        try:
            return int(value.strip())
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return None

    def _parse_until_body(self, chunk: bytes | None) -> None:
        chunk = chunk if chunk is not None else b''
        self._raw_size += len(chunk)
        self._pre_buffer += chunk
        if not self._state:
            self._state = 'headers'
        if self._state == 'headers':
            self._parse_headers()
        if self._state != 'headers' and not self._body:
            self._body = True
            self.emit('body')


new = Pyjo_Content.new
object = Pyjo_Content
Content = Pyjo_Content
