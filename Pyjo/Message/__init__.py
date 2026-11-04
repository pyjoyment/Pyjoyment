r"""
Pyjo.Message - HTTP message base class
======================================
::

    from Pyjo.Message import Message

    class MyMessage(Message):
        def cookies(self, *cookies): ...
        def extract_start_line(self, buffer): ...
        def get_start_line_chunk(self, offset): ...
        @property
        def start_line_size(self): ...

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Message

    class MyMessage(Pyjo.Message.object):
        def cookies(self, *cookies): ...
        def extract_start_line(self, buffer): ...
        def get_start_line_chunk(self, offset): ...
        @property
        def start_line_size(self): ...

:mod:`Pyjo.Message` is an abstract base class for HTTP message containers,
based on `RFC 7230 <https://tools.ietf.org/html/rfc7230>`_,
`RFC 7231 <https://tools.ietf.org/html/rfc7231>`_ and
`RFC 2388 <https://tools.ietf.org/html/rfc2388>`_, like
:mod:`Pyjo.Message.Request` and :mod:`Pyjo.Message.Response`.

Events
------

:mod:`Pyjo.Message` inherits all events from :mod:`Pyjo.EventEmitter` and can
emit the following new ones.

finish
~~~~~~
::

    msg.on('finish', lambda msg: ...)

Emitted after message building or parsing is finished. ::

    before = time.time()
    msg.on('finish', lambda msg: msg.headers.header('X-Parser-Time', int(time.time() - before)))

progress
~~~~~~~~
::

    msg.on('progress', lambda msg, *args: ...)

Emitted when message building or parsing makes progress. ::

    # Building
    msg.on('progress', lambda msg, state, offset: print(f'Building "{state}" at offset {offset}'))

    # Parsing
    @msg.on('progress')
    def progress(msg):
        if not (length := int(msg.headers.content_length or 0)):
            return
        size = msg.content.progress
        print('Progress:', 100 if size == length else int(size / (length / 100)), '%')

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Message <https://github.com/mojolicious/mojo/blob/v9.52/lib/Mojo/Message.pm>`_
of Mojolicious 9.52.
"""

import Pyjo.Asset.Memory
import Pyjo.Collection
import Pyjo.Content
import Pyjo.Content.MultiPart
import Pyjo.Content.Single
import Pyjo.Cookie
import Pyjo.DOM
import Pyjo.EventEmitter
import Pyjo.Exception
import Pyjo.Headers
import Pyjo.JSON.Pointer
import Pyjo.Parameters
import Pyjo.Upload

from Pyjo.DOM.HTML import _decode  # pyright: ignore[reportPrivateUsage]
from Pyjo.JSON import j
from Pyjo.Util import decode

import builtins
import collections
import os
import re

from collections.abc import Callable, Mapping, Sequence
from typing import Any, NotRequired, Self, TypedDict, cast, overload


type Anything = builtins.object


class Error(TypedDict):
    """An error of a message, with the status code of a response for a 4xx or
    5xx response."""

    message: str
    code: NotRequired[int]


# The parameters and the uploads of multipart/form-data, parsed once, as the hash of Mojo
class _FormData(TypedDict):
    params: list[tuple[str, str]]
    uploads: list[Pyjo.Upload.object]


class Pyjo_Message(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.Message` inherits all methods from :mod:`Pyjo.EventEmitter` and
    implements the following new ones.
    """

    # The default of max_message_size, which a response raises
    _MAX_MESSAGE_SIZE = 16777216

    def __init__(
        self,
        *,
        content: Pyjo.Content.object | None = None,
        default_charset: str | None = 'UTF-8',
        max_line_size: int | None = None,
        max_message_size: int | None = None,
        version: str = '1.1',
    ) -> None:
        """::

            msg = Pyjo.Message.Request.new()
            msg = Pyjo.Message.Response.new(content=Pyjo.Content.MultiPart.new())

        Construct a new message object.
        """
        super().__init__()

        self.default_charset = default_charset
        """::

            charset = msg.default_charset
            msg.default_charset = 'UTF-8'

        Default charset used by :attr:`text` and to extract data from
        ``application/x-www-form-urlencoded`` or ``multipart/form-data``
        message body, defaults to ``UTF-8``.
        """

        self._max_line_size: int | None = max_line_size
        self._max_message_size: int | None = max_message_size

        self.version = version
        """::

            version = msg.version
            msg.version = '1.1'

        HTTP version of message, defaults to ``1.1``.
        """

        self._content = content

        # The state of the parser and of the generator, as the keys of Mojo's hash
        self._body_params: Pyjo.Parameters.object | None = None
        self._buffer = bytearray()
        self._cached: dict[str, dict[str | None, list[Any]]] = {}
        self._dom: Pyjo.DOM.object | None = None
        self._error: Error | None = None
        self._finished = False
        self._fix = False
        self._formdata: _FormData | None = None
        self._json: Any = None
        self._limit = False
        self._raw_size = 0
        self._state: str | None = None

    @property
    def max_line_size(self) -> int:
        """::

            size = msg.max_line_size
            msg.max_line_size = 1024

        Maximum start-line size in bytes, defaults to the value of the
        ``PYJO_MAX_LINE_SIZE`` environment variable or ``65536`` (64KiB).
        """
        if self._max_line_size is None:
            # Unlike Mojolicious: 64KiB, as _MAXLINE of http.client and the lines of Pyjo.Headers, where Mojo has 8KiB
            self._max_line_size = int(os.environ.get('PYJO_MAX_LINE_SIZE') or 65536)
        return self._max_line_size

    @max_line_size.setter
    def max_line_size(self, value: int) -> None:
        self._max_line_size = value

    @property
    def max_message_size(self) -> int:
        """::

            size = msg.max_message_size
            msg.max_message_size = 1024

        Maximum message size in bytes, defaults to the value of the
        ``PYJO_MAX_MESSAGE_SIZE`` environment variable or ``16777216``
        (16MiB). Setting the value to ``0`` will allow messages of indefinite
        size.
        """
        if self._max_message_size is None:
            self._max_message_size = (
                int(size) if (size := os.environ.get('PYJO_MAX_MESSAGE_SIZE')) is not None else self._MAX_MESSAGE_SIZE
            )
        return self._max_message_size

    @max_message_size.setter
    def max_message_size(self, value: int) -> None:
        self._max_message_size = value

    @property
    def content(self) -> Pyjo.Content.object:
        """::

            content = msg.content
            msg.content = Pyjo.Content.Single.new()

        Message content, defaults to a :mod:`Pyjo.Content.Single` object.
        """
        if self._content is None:
            self._content = Pyjo.Content.Single.new()
        return self._content

    @content.setter
    def content(self, value: Pyjo.Content.object) -> None:
        self._content = value

    @property
    def body(self) -> bytes:
        """::

            data = msg.body
            msg.body = b'Hello!'

        Slurp or replace :attr:`content`.
        """
        content = self.content
        return b'' if content.is_multipart else _single(content).asset.slurp()

    @body.setter
    def body(self, value: bytes) -> None:
        # Multipart content needs to be downgraded
        content = self.content
        if content.is_multipart:
            content = self.content = Pyjo.Content.Single.new()
        _single(content).asset = Pyjo.Asset.Memory.new().add_chunk(value)

    @property
    def body_params(self) -> Pyjo.Parameters.object:
        """::

            params = msg.body_params

        ``POST`` parameters extracted from ``application/x-www-form-urlencoded``
        or ``multipart/form-data`` message body, usually a
        :mod:`Pyjo.Parameters` object. Note that this method caches all data, so
        it should not be called before the entire message body has been
        received. Parts of the message body need to be loaded into memory to
        parse ``POST`` parameters, so you have to make sure it is not
        excessively large. There's a 16MiB limit for requests and a 2GiB limit
        for responses by default. ::

            # Get POST parameter names and values
            params = msg.body_params.to_dict()
        """
        if self._body_params is not None:
            return self._body_params
        params = self._body_params = Pyjo.Parameters.new()
        params.charset = self.content.charset or self.default_charset

        # "application/x-www-form-urlencoded"
        type = self.headers.content_type or ''
        if re.search(r'application/x-www-form-urlencoded', type, re.I):
            params.parse(_single(self.content).asset.slurp())

        # "multipart/form-data"
        elif re.search(r'multipart/form-data', type, re.I):
            for name, value in self._parse_formdata()['params']:
                params.append(name, value)

        return params

    @property
    def body_size(self) -> int:
        """::

            size = msg.body_size

        Content size in bytes.
        """
        return self.content.body_size

    def build_body(self) -> bytes:
        """::

            data = msg.build_body()

        Render whole body with :meth:`get_body_chunk`.
        """
        return self._build(self.get_body_chunk)

    def build_headers(self) -> bytes:
        """::

            data = msg.build_headers()

        Render all headers with :meth:`get_header_chunk`.
        """
        return self._build(self.get_header_chunk)

    def build_start_line(self) -> bytes:
        """::

            data = msg.build_start_line()

        Render start-line with :meth:`get_start_line_chunk`.
        """
        return self._build(self.get_start_line_chunk)

    def cookie(self, name: str) -> Pyjo.Cookie.object | None:
        """::

            cookie = msg.cookie('foo')

        Access message cookies, usually :mod:`Pyjo.Cookie.Request` or
        :mod:`Pyjo.Cookie.Response` objects. If there are multiple cookies
        sharing the same name, and you want to access more than just the last
        one, you can use :meth:`every_cookie`. Note that this method caches all
        data, so it should not be called before all headers have been
        received. ::

            # Get cookie value
            print(msg.cookie('foo').value)
        """
        cookies = self._cache('cookies', self.cookies, name)
        return cookies[-1] if cookies else None

    @overload
    def cookies(self) -> Sequence[Pyjo.Cookie.object]: ...

    @overload
    def cookies(self, cookie: Pyjo.Cookie.object | Mapping[str, Any], /, *cookies: Anything) -> Self: ...

    def cookies(self, *cookies: Anything) -> Sequence[Pyjo.Cookie.object] | Self:
        """::

            cookies = msg.cookies()

        Access message cookies. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "cookies" not implemented by subclass')

    @overload
    def dom(self) -> Pyjo.DOM.object | None: ...

    @overload
    def dom(self, css: Anything, /) -> 'Pyjo.Collection.object[Pyjo.DOM.object] | None': ...

    def dom(self, *args: Anything) -> 'Pyjo.DOM.object | Pyjo.Collection.object[Pyjo.DOM.object] | None':
        r"""::

            dom = msg.dom()
            collection = msg.dom('a[href]')

        Retrieve message body and turn it into a :mod:`Pyjo.DOM` object, with
        its encoding found as the HTML Living Standard sniffs it, a byte order
        mark, the :attr:`Pyjo.Content.Pyjo_Content.charset`, the encoding of an
        XML declaration or of a ``<meta charset>``, and
        :attr:`default_charset`, an optional selector can be used to call the
        method :meth:`Pyjo.DOM.Pyjo_DOM.find` on it right away, which then
        returns a :mod:`Pyjo.Collection` object. Note that this method caches
        all data, so it should not be called before the entire message body has
        been received. The whole message body needs to be loaded into memory to
        parse it, so you have to make sure it is not excessively large. There's
        a 16MiB limit for requests and a 2GiB limit for responses by default. ::

            # Perform "find" right away
            print(msg.dom('h1, h2, h3').map('text').join("\n"))

            # Use everything else Pyjo.DOM has to offer
            print(msg.dom().at('title').text)
            print(msg.dom().at('body').children().map('tag').uniq().join("\n"))
        """
        if self.content.is_multipart:
            return None
        if self._dom is None:
            # Unlike Mojolicious: the encoding of the page, where Mojo decodes the text with the charset of Content-Type
            # or the default, as a page in another encoding often says it in a meta element only
            text = _decode(self.body, self.content.charset, self.default_charset)
            self._dom = Pyjo.DOM.new(text)
        return self._dom.find(args[0]) if args else self._dom

    @property
    def error(self) -> Error | None:
        """::

            err = msg.error
            msg.error = {'message': 'Parser error'}

        Get or set message error, a ``None`` return value indicates that there
        is no error. Setting it finishes the message. ::

            # Connection or parser error
            msg.error = {'message': 'Connection refused'}

            # 4xx/5xx response
            msg.error = {'message': 'Internal Server Error', 'code': 500}
        """
        return self._error

    @error.setter
    def error(self, value: Error | None) -> None:
        self._error = value
        self.finish()

    def every_cookie(self, name: str) -> list[Pyjo.Cookie.object]:
        """::

            cookies = msg.every_cookie('foo')

        Similar to :meth:`cookie`, but returns all message cookies sharing the
        same name as a list. ::

            # Get first cookie value
            print(msg.every_cookie('foo')[0].value)
        """
        return self._cache('cookies', self.cookies, name)

    def every_upload(self, name: str) -> list[Pyjo.Upload.object]:
        """::

            uploads = msg.every_upload('foo')

        Similar to :meth:`upload`, but returns all file uploads sharing the
        same name as a list. ::

            # Get content of first uploaded file
            print(msg.every_upload('foo')[0].asset.slurp())
        """
        return self._cache('uploads', self.uploads, name)

    def extract_start_line(self, buffer: bytearray) -> bool | None:
        """::

            boolean = msg.extract_start_line(buffer)

        Extract start-line from a :class:`bytearray`, which loses it. Meant to
        be overloaded in a subclass.
        """
        raise NotImplementedError('Method "extract_start_line" not implemented by subclass')

    def finish(self) -> Self:
        """::

            msg = msg.finish()

        Finish message parser/generator.
        """
        self._state = 'finished'
        if self._finished:
            return self
        self._finished = True
        return self.emit('finish')

    def fix_headers(self) -> Self:
        """::

            msg = msg.fix_headers()

        Make sure message has all required headers.
        """
        if self._fix:
            return self
        self._fix = True

        # Content-Length or Connection (unless chunked transfer encoding is used), "0" is false as in Perl
        content = self.content
        headers = content.headers
        if content.is_multipart:
            headers.remove('Content-Length')
        elif content.is_chunked or headers.content_length not in (None, '', '0'):
            return self
        if content.is_dynamic:
            headers.connection = 'close'
        else:
            headers.content_length = self.body_size

        return self

    def get_body_chunk(self, offset: int) -> bytes | None:
        """::

            data = msg.get_body_chunk(offset)

        Get a chunk of body data starting from a specific position. Note that
        it might not be possible to get the same chunk twice if content was
        generated dynamically.
        """
        self.emit('progress', 'body', offset)
        chunk = self.content.get_body_chunk(offset)
        if chunk is None or len(chunk):
            return chunk
        self.finish()

        return chunk

    def get_header_chunk(self, offset: int) -> bytes:
        """::

            data = msg.get_header_chunk(offset)

        Get a chunk of header data, starting from a specific position. Note
        that this method finalizes the message.
        """
        self.emit('progress', 'headers', offset)
        return self.fix_headers().content.get_header_chunk(offset)

    def get_start_line_chunk(self, offset: int) -> bytes:
        """::

            data = msg.get_start_line_chunk(offset)

        Get a chunk of start-line data starting from a specific position. Meant
        to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "get_start_line_chunk" not implemented by subclass')

    @property
    def header_size(self) -> int:
        """::

            size = msg.header_size

        Size of headers in bytes. Note that this method finalizes the message.
        """
        return self.fix_headers().content.header_size

    @property
    def headers(self) -> Pyjo.Headers.object:
        """::

            headers = msg.headers

        Message headers, usually a :mod:`Pyjo.Headers` object. ::

            # Longer version
            headers = msg.content.headers
        """
        return self.content.headers

    @property
    def is_finished(self) -> bool:
        """::

            boolean = msg.is_finished

        Check if message parser/generator is finished.
        """
        return self._state == 'finished'

    @property
    def is_limit_exceeded(self) -> bool:
        """::

            boolean = msg.is_limit_exceeded

        Check if message has exceeded :attr:`max_line_size`,
        :attr:`max_message_size`,
        :attr:`Pyjo.Content.Pyjo_Content.max_buffer_size` or
        :attr:`Pyjo.Headers.Pyjo_Headers.max_line_size`.
        """
        return self._limit

    def json(self, pointer: str | None = None) -> Any:
        """::

            value = msg.json()
            value = msg.json('/foo/bar')

        Decode JSON message body directly using :mod:`Pyjo.JSON` if possible,
        a ``None`` return value indicates a bare ``null`` or that decoding
        failed. An optional JSON Pointer can be used to extract a specific value
        with :mod:`Pyjo.JSON.Pointer`. Note that this method caches all data,
        so it should not be called before the entire message body has been
        received. The whole message body needs to be loaded into memory to
        parse it, so you have to make sure it is not excessively large. There's
        a 16MiB limit for requests and a 2GiB limit for responses by default. ::

            # Extract JSON values
            print(msg.json()['foo']['bar'][23])
            print(msg.json('/foo/bar/23'))
        """
        if self.content.is_multipart:
            return None
        if self._json is None:
            self._json = j(self.body)
        data = self._json
        return Pyjo.JSON.Pointer.new(data).get(pointer) if pointer else data

    def parse(self, chunk: bytes) -> Self:
        """::

            msg = msg.parse(b'HTTP/1.1 200 OK...')

        Parse message chunk.
        """
        if self._error is not None:
            return self
        self._raw_size += len(chunk)
        self._buffer += chunk

        # Start-line
        if not self._state:
            # Check start-line size
            length = self._buffer.find(b'\x0a')
            if length < 0:
                length = len(self._buffer)
            if length > self.max_line_size:
                return self._limit_exceeded('Maximum start-line size exceeded')

            if self.extract_start_line(self._buffer):
                self._state = 'content'

        # Content
        state = self._state or ''
        if state == 'content' or state == 'finished':
            buffer, self._buffer = bytes(self._buffer), bytearray()
            self.content = self.content.parse(buffer)

        # Check message size
        max = self.max_message_size
        if max and max < self._raw_size:
            return self._limit_exceeded('Maximum message size exceeded')

        # Check header size
        if self.headers.is_limit_exceeded:
            return self._limit_exceeded('Maximum header size exceeded')

        # Check buffer size
        if self.content.is_limit_exceeded:
            return self._limit_exceeded('Maximum buffer size exceeded')

        return self.finish() if self.emit('progress').content.is_finished else self

    def save_to(self, path: Anything) -> Self:
        """::

            msg = msg.save_to('/some/path/index.html')

        Save message body to a file.
        """
        content = self.content
        if content.is_multipart:
            raise Pyjo.Exception.new('Multipart content cannot be saved to files')
        _single(content).asset.move_to(path)
        return self

    @property
    def start_line_size(self) -> int:
        """::

            size = msg.start_line_size

        Size of the start-line in bytes. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "start_line_size" not implemented by subclass')

    @property
    def text(self) -> str:
        """::

            string = msg.text

        Retrieve :attr:`body` and try to decode it with
        :attr:`Pyjo.Content.Pyjo_Content.charset` or :attr:`default_charset`.
        A body that does not decode is a string of the characters 0-255, one
        for each byte.
        """
        body = self.body
        charset = self.content.charset or self.default_charset
        if charset and (text := decode(charset, body)) is not None:
            return text
        return body.decode('latin-1')

    def to_bytes(self) -> bytes:
        """::

            data = msg.to_bytes()

        Render whole message. Note that this method finalizes the message, and
        that it might not be possible to render the same message twice if
        content was generated dynamically.
        """
        # Renamed from Mojolicious: to_string, as the message is rendered as bytes
        return self.build_start_line() + self.build_headers() + self.build_body()

    def upload(self, name: str) -> Pyjo.Upload.object | None:
        """::

            upload = msg.upload('foo')

        Access ``multipart/form-data`` file uploads, usually :mod:`Pyjo.Upload`
        objects. If there are multiple uploads sharing the same name, and you
        want to access more than just the last one, you can use
        :meth:`every_upload`. Note that this method caches all data, so it
        should not be called before the entire message body has been
        received. ::

            # Get content of uploaded file
            print(msg.upload('foo').asset.slurp())
        """
        uploads = self._cache('uploads', self.uploads, name)
        return uploads[-1] if uploads else None

    def uploads(self) -> list[Pyjo.Upload.object]:
        """::

            uploads = msg.uploads()

        All ``multipart/form-data`` file uploads, usually :mod:`Pyjo.Upload`
        objects. ::

            # Names of all uploads
            for upload in msg.uploads():
                print(upload.name)
        """
        return list(self._parse_formdata()['uploads'])

    def _build(self, method: Callable[[int], bytes | None]) -> bytes:
        buffer, offset = bytearray(), 0
        while True:
            # No chunk yet, try again
            if (chunk := method(offset)) is None:
                continue

            # End of part
            if not (length := len(chunk)):
                break

            offset += length
            buffer += chunk

        return bytes(buffer)

    def _cache[T: Pyjo.Cookie.object | Pyjo.Upload.object](
        self, method: str, objects: Callable[[], Sequence[T]], name: str
    ) -> list[T]:
        # Cache objects by name
        if method not in self._cached:
            cached = self._cached[method] = {}
            for obj in objects():
                cached.setdefault(obj.name, []).append(obj)

        return self._cached[method].get(name, [])

    def _limit_exceeded(self, message: str) -> Self:
        # Renamed from Mojolicious: _limit, the attribute _limit is the flag
        self._limit = True
        self.error = {'message': message}
        return self

    # Renamed from Mojolicious: _formdata, the attribute _formdata is the cache
    def _parse_formdata(self) -> _FormData:
        if self._formdata is not None:
            return self._formdata
        formdata = self._formdata = _FormData(params=[], uploads=[])
        content = self.content
        if not content.is_multipart:
            return formdata
        charset = content.charset or self.default_charset

        # Check all parts recursively
        # A deque, whose popleft and extendleft take and put back the parts as shift and unshift of Perl do, where pop(0) of
        # a list moves all the others, which the many parts of a form of a client would make slow
        parts: collections.deque[Pyjo.Content.object] = collections.deque([content])
        while parts:
            part = parts.popleft()
            if part.is_multipart:
                parts.extendleft(reversed(cast(Pyjo.Content.MultiPart.object, part).parts))
                continue

            if not (disposition := part.headers.content_disposition):
                continue
            filename = m[1] if (m := re.search(r'[; ]filename="((?:\\"|[^"])*)"', disposition)) else None
            if (name := m[1] if (m := re.search(r'[; ]name="((?:\\"|[^;"])*)"', disposition)) else None) is None:
                continue
            if charset:
                if name:
                    name = decoded if (decoded := decode(charset, name)) is not None else name
                if filename:
                    filename = decoded if (decoded := decode(charset, filename)) is not None else filename

            # Upload
            if filename is not None:
                formdata['uploads'].append(
                    Pyjo.Upload.new(name=name, filename=filename, asset=_single(part).asset, headers=part.headers)
                )

            # Parameter
            else:
                value: bytes | str = _single(part).asset.slurp()
                if charset:
                    value = decoded if (decoded := decode(charset, value)) is not None else value

                # A value that does not decode is a string of the characters 0-255, as a Perl byte string
                if isinstance(value, bytes):
                    value = value.decode('latin-1')
                formdata['params'].append((name, value))

        return formdata


# The asset of content that is not multipart
def _single(content: Pyjo.Content.object) -> Pyjo.Content.Single.object:
    return cast(Pyjo.Content.Single.object, content)


new = Pyjo_Message.new
object = Pyjo_Message
Message = Pyjo_Message
