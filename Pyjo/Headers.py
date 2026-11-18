r"""
Pyjo.Headers - HTTP headers
===========================
::

    from Pyjo.Headers import Headers

    # Parse
    headers = Headers()
    headers.parse('Content-Length: 42\x0d\x0a')
    headers.parse('Content-Type: text/html\x0d\x0a\x0d\x0a')
    print(headers.content_length)
    print(headers.content_type)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Headers

    # Parse
    headers = Pyjo.Headers.new()
    headers.parse('Content-Length: 42\x0d\x0a')
    headers.parse('Content-Type: text/html\x0d\x0a\x0d\x0a')
    print(headers.content_length)
    print(headers.content_type)

    # Build
    headers = Pyjo.Headers.new()
    headers.content_length = 42
    headers.content_type = 'text/plain'
    print(headers.to_str())

:mod:`Pyjo.Headers` is a container for HTTP headers, based on :rfc:`7230` and
:rfc:`7231`.

The values are strings; bytes from the wire are decoded as ISO-8859-1, as
:mod:`http.client` does.

The headers also work with the Python standard library: they take an
:class:`email.message.Message`, such as :class:`http.client.HTTPMessage`, a
``dict`` or a list of pairs, they are a mapping of the names to the values
without regard to case, and they turn into an :class:`email.message.Message`
with :meth:`to_message` or into a list of pairs with :meth:`to_list`. ::

    # "text/html"
    Pyjo.Headers.new({'Content-Type': 'text/html'})['content-type']

    # [('Vary', 'Accept'), ('Vary', 'Accept-Encoding')]
    Pyjo.Headers.new([('Vary', 'Accept'), ('Vary', 'Accept-Encoding')]).to_list()

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Headers <https://github.com/mojolicious/mojo/blob/v9.52/lib/Mojo/Headers.pm>`_
of Mojolicious 9.52.

Classes
-------
"""

import Pyjo.Base
import Pyjo.String.Mixin

from Pyjo.Util import header_params

import builtins
import os
import re

from collections.abc import Iterator
from email.message import Message
from typing import Self, cast, overload


# The module ends with `object = Pyjo_Headers`, which an annotation of
# `object` would mean, as annotations are evaluated lazily
type Anything = builtins.object

# Common headers
NAMES = {
    name.lower(): name
    for name in (
        'Accept Accept-Charset Accept-Encoding Accept-Language Accept-Ranges Access-Control-Allow-Origin Allow '
        'Authorization Cache-Control Connection Content-Disposition Content-Encoding Content-Language Content-Length '
        'Content-Location Content-Range Content-Security-Policy Content-Type Cookie DNT Date ETag Expect Expires Host '
        'If-Modified-Since If-None-Match Last-Modified Link Location Origin Proxy-Authenticate Proxy-Authorization '
        'Range Sec-WebSocket-Accept Sec-WebSocket-Extensions Sec-WebSocket-Key Sec-WebSocket-Protocol '
        'Sec-WebSocket-Version Server Server-Timing Set-Cookie Status Strict-Transport-Security TE Trailer '
        'Transfer-Encoding Upgrade User-Agent Vary WWW-Authenticate '
        # Not in Mojolicious: the headers of security and of CORS
        'Access-Control-Allow-Credentials Access-Control-Allow-Headers Access-Control-Allow-Methods '
        'Access-Control-Expose-Headers Access-Control-Max-Age Access-Control-Request-Headers '
        'Access-Control-Request-Method Content-Security-Policy-Report-Only Cross-Origin-Embedder-Policy '
        'Cross-Origin-Opener-Policy Cross-Origin-Resource-Policy Permissions-Policy Referrer-Policy '
        'Reporting-Endpoints X-Content-Type-Options'
    ).split()
}

# Hop-by-hop headers
HOP_BY_HOP = [
    name.lower()
    for name in (
        'Connection',
        'Keep-Alive',
        'Proxy-Authenticate',
        'Proxy-Authorization',
        'TE',
        'Trailer',
        'Transfer-Encoding',
        'Upgrade',
    )
]


# Not in Mojolicious: the specification of the shortcuts of the headers of CORS
_CORS = ' from the `CORS protocol <https://fetch.spec.whatwg.org/#http-cors-protocol>`_ of Fetch'


class _Shortcut:
    # A property for a common header, as Mojo makes them with monkey_patch
    def __init__(self, name: str, example: str, about: str = '') -> None:
        attr = name.lower().replace('-', '_')
        self.name = name
        self.__doc__ = f"""::

        {attr} = headers.{attr}
        headers.{attr} = {example}

    Get or replace current header value, shortcut for the ``{name}`` header{about}.
    """

    @overload
    def __get__(self, headers: None, owner: type | None = None) -> Self: ...

    @overload
    def __get__(self, headers: 'Pyjo_Headers', owner: type | None = None) -> str | None: ...

    def __get__(self, headers: 'Pyjo_Headers | None', owner: type | None = None) -> Self | str | None:
        return self if headers is None else headers.header(self.name)

    def __set__(self, headers: 'Pyjo_Headers', value: Anything) -> None:
        # Unlike Mojolicious: the value is checked for invalid characters, as add
        # does; Mojo sets it directly
        headers.header(self.name, value)


class Pyjo_Headers(Pyjo.Base.object, Pyjo.String.Mixin.object):
    """
    :mod:`Pyjo.Headers` inherits all methods from :mod:`Pyjo.Base` and
    :mod:`Pyjo.String.Mixin` and implements the following new ones.
    """

    def __init__(
        self,
        headers: 'Message | dict[str, Anything] | list[tuple[str, Anything]] | Pyjo_Headers | None' = None,
        *,
        max_line_size: int | None = None,
        max_lines: int | None = None,
    ) -> None:
        """::

            headers = Pyjo.Headers.new()
            headers = Pyjo.Headers.new({'Content-Type': 'text/html'})
            headers = Pyjo.Headers.new([('Vary', 'Accept'), ('Vary', 'Accept-Encoding')])
            headers = Pyjo.Headers.new(http_response.headers)

        Construct a new :mod:`Pyjo.Headers` object, from headers of the standard
        library if they are given: an :class:`email.message.Message`, such as
        :class:`http.client.HTTPMessage`, a ``dict``, as :meth:`from_dict` takes,
        or a list of pairs.
        """
        self._max_line_size: int | None = max_line_size or None
        self._max_lines: int | None = max_lines or None

        self._headers: dict[str, list[str]] = {}
        self._names: dict[str, str] = {}
        self._buffer = bytearray()
        self._cache: list[list[str]] = []
        self._state: str | None = None
        self._limit = False

        # Not in Mojolicious: headers of the standard library
        if isinstance(headers, Message | Pyjo_Headers | list):
            pairs = (
                headers.items()
                if isinstance(headers, Message)
                else headers.to_list()
                if isinstance(headers, Pyjo_Headers)
                else headers
            )
            for name, value in pairs:
                self.add(name, value)
        elif isinstance(headers, dict):
            self.from_dict(headers)

    @property
    def max_line_size(self) -> int:
        """::

            size = headers.max_line_size
            headers.max_line_size = 1024

        Maximum header line size in bytes, defaults to the value of the
        ``PYJO_MAX_LINE_SIZE`` environment variable or ``65536`` (64KiB).
        """
        if self._max_line_size is None:
            # Unlike Mojolicious: 64KiB, as _MAXLINE of http.client, where Mojo has 8KiB, as a header of a response, as
            # Content-Security-Policy, can be longer
            self._max_line_size = int(os.environ.get('PYJO_MAX_LINE_SIZE') or 65536)
        return self._max_line_size

    @max_line_size.setter
    def max_line_size(self, value: int) -> None:
        self._max_line_size = value

    @property
    def max_lines(self) -> int:
        """::

            num = headers.max_lines
            headers.max_lines = 200

        Maximum number of header lines, defaults to the value of the
        ``PYJO_MAX_LINES`` environment variable or ``100``.
        """
        if self._max_lines is None:
            self._max_lines = int(os.environ.get('PYJO_MAX_LINES') or 100)
        return self._max_lines

    @max_lines.setter
    def max_lines(self, value: int) -> None:
        self._max_lines = value

    def __bool__(self) -> bool:
        """::

            boolean = bool(headers)

        Always true, also without headers.
        """
        return True

    # Not in Mojolicious: the mapping protocol of the standard library
    def __contains__(self, name: Anything) -> bool:
        """::

            boolean = 'Content-Type' in headers

        Check if a header exists, without regard to case.
        """
        return isinstance(name, str) and name.lower() in self._headers

    # Not in Mojolicious: the mapping protocol of the standard library
    def __getitem__(self, name: str) -> str:
        """::

            value = headers['Content-Type']

        Same as :meth:`header`, but raises :class:`KeyError` for a header that does
        not exist.
        """
        if (value := self.header(name)) is None:
            raise KeyError(name)
        return value

    # Not in Mojolicious: the mapping protocol of the standard library
    def __iter__(self) -> Iterator[str]:
        """::

            names = list(headers)

        Iterate over :meth:`names`.
        """
        return iter(self.names())

    # Not in Mojolicious: the mapping protocol of the standard library
    def __len__(self) -> int:
        """::

            size = len(headers)

        Number of headers, with the values of a header counting once.
        """
        return len(self._headers)

    def __str__(self) -> str:
        """::

            string = str(headers)

        Alias for :meth:`to_str`.
        """
        return self.to_str()

    accept = _Shortcut('Accept', "'*/*'")
    accept_charset = _Shortcut('Accept-Charset', "'UTF-8'")
    accept_encoding = _Shortcut('Accept-Encoding', "'gzip'")
    accept_language = _Shortcut('Accept-Language', "'de, en'")
    accept_ranges = _Shortcut('Accept-Ranges', "'bytes'")
    # Not in Mojolicious: the headers of CORS other than Access-Control-Allow-Origin
    access_control_allow_credentials = _Shortcut('Access-Control-Allow-Credentials', "'true'", _CORS)
    access_control_allow_headers = _Shortcut('Access-Control-Allow-Headers', "'Content-Type, Authorization'", _CORS)
    access_control_allow_methods = _Shortcut('Access-Control-Allow-Methods', "'GET, POST'", _CORS)
    access_control_allow_origin = _Shortcut(
        'Access-Control-Allow-Origin',
        "'*'",
        ' from `Cross-Origin Resource Sharing <https://www.w3.org/TR/cors/>`_',
    )
    # Not in Mojolicious: the headers of CORS other than Access-Control-Allow-Origin
    access_control_expose_headers = _Shortcut('Access-Control-Expose-Headers', "'Server-Timing'", _CORS)
    access_control_max_age = _Shortcut('Access-Control-Max-Age', '86400', _CORS)
    access_control_request_headers = _Shortcut('Access-Control-Request-Headers', "'content-type'", _CORS)
    access_control_request_method = _Shortcut('Access-Control-Request-Method', "'PUT'", _CORS)

    def add(self, name: str, *values: Anything) -> Self:
        """::

            headers = headers.add('Foo', 'one value')
            headers = headers.add('Foo', 'first value', 'second value')

        Add header with one or more lines. ::

            # "Vary: Accept
            #  Vary: Accept-Encoding"
            headers.add('Vary', 'Accept').add('Vary', 'Accept-Encoding').to_str()
        """
        # Not in Mojolicious: a list adds its values
        strings = [
            str(v)
            for value in values
            for v in (cast(list[Anything], value) if isinstance(value, (list, tuple)) else [value])
        ]
        for value in strings:
            if '\x0d' in value or '\x0a' in value:
                raise ValueError(f'Invalid characters in {name} header')

        # Make sure we have a normal case entry for name
        key = name.lower()
        if key not in NAMES:
            self._names.setdefault(key, name)
        self._headers.setdefault(key, []).extend(strings)

        return self

    allow = _Shortcut('Allow', "'GET, POST'")

    def append(self, name: str, value: Anything) -> Self:
        """::

            headers = headers.append('Vary', 'Accept-Encoding')

        Append value to header and flatten it if necessary. ::

            # "Vary: Accept"
            headers.append('Vary', 'Accept').to_str()

            # "Vary: Accept, Accept-Encoding"
            headers.set(vary='Accept').append('Vary', 'Accept-Encoding').to_str()
        """
        old = self.header(name)
        return self.header(name, f'{old}, {value}' if old is not None else value)

    authorization = _Shortcut('Authorization', "'Basic Zm9vOmJhcg=='")
    cache_control = _Shortcut('Cache-Control', "'max-age=1, no-cache'")

    def clone(self) -> Self:
        """::

            clone = headers.clone()

        Return a new :mod:`Pyjo.Headers` object cloned from these headers.
        """
        clone = self.new()
        clone._names = dict(self._names)
        clone._headers = {key: list(values) for key, values in self._headers.items()}
        return clone

    connection = _Shortcut('Connection', "'close'")
    content_disposition = _Shortcut('Content-Disposition', "'foo'")
    content_encoding = _Shortcut('Content-Encoding', "'gzip'")
    content_language = _Shortcut('Content-Language', "'en'")
    content_length = _Shortcut('Content-Length', '4000')
    content_location = _Shortcut('Content-Location', "'http://127.0.0.1/foo'")
    content_range = _Shortcut('Content-Range', "'bytes 2-8/100'")
    content_security_policy = _Shortcut(
        'Content-Security-Policy',
        "'default-src https:'",
        ' from `Content Security Policy 1.0 <https://www.w3.org/TR/CSP/>`_',
    )
    # Not in Mojolicious: the policy that the browser reports without enforcing it
    content_security_policy_report_only = _Shortcut(
        'Content-Security-Policy-Report-Only',
        '"default-src \'self\'; report-to csp"',
        ' from `Content Security Policy Level 3 <https://www.w3.org/TR/CSP3/>`_',
    )
    content_type = _Shortcut('Content-Type', "'text/plain'")
    cookie = _Shortcut('Cookie', "'f=b'", ' from :rfc:`6265`')
    # Not in Mojolicious: the policies of the isolation of a document from the ones of other origins
    cross_origin_embedder_policy = _Shortcut(
        'Cross-Origin-Embedder-Policy',
        "'require-corp'",
        ' from the `HTML Standard <https://html.spec.whatwg.org/multipage/browsers.html#coep>`_',
    )
    cross_origin_opener_policy = _Shortcut(
        'Cross-Origin-Opener-Policy',
        "'same-origin'",
        ' from the `HTML Standard'
        ' <https://html.spec.whatwg.org/multipage/browsers.html#cross-origin-opener-policies>`_',
    )
    cross_origin_resource_policy = _Shortcut(
        'Cross-Origin-Resource-Policy',
        "'same-origin'",
        ' from `Fetch <https://fetch.spec.whatwg.org/#cross-origin-resource-policy-header>`_',
    )
    date = _Shortcut('Date', "'Sun, 17 Aug 2008 16:27:35 GMT'")

    def dehop(self) -> Self:
        """::

            headers = headers.dehop()

        Remove hop-by-hop headers that should not be retransmitted.
        """
        for key in HOP_BY_HOP:
            self._headers.pop(key, None)
        return self

    dnt = _Shortcut(
        'DNT',
        '1',
        ' (Do Not Track), which has no specification yet, but is very commonly used',
    )
    etag = _Shortcut('ETag', '\'"abc321"\'')

    def every_header(self, name: str) -> list[str]:
        """::

            all = headers.every_header('Location')

        Similar to :meth:`header`, but returns all headers sharing the same name as a
        list. ::

            # Get first header value
            print(headers.every_header('Location')[0])
        """
        return self._headers.get(name.lower(), [])

    expect = _Shortcut('Expect', "'100-continue'")
    expires = _Shortcut('Expires', "'Thu, 01 Dec 1994 16:00:00 GMT'")

    def from_dict(self, d: dict[str, Anything]) -> Self:
        """::

            headers = headers.from_dict({'Cookie': 'a=b'})
            headers = headers.from_dict({'Cookie': ['a=b', 'c=d']})
            headers = headers.from_dict({})

        Parse headers from a ``dict``, an empty one removes all headers.
        """
        # Empty dict deletes all headers
        if not d:
            self._headers = {}

        # Merge
        for header, value in d.items():
            self.add(header, value)

        return self

    # Not in Mojolicious: the mapping protocol of the standard library
    def get(self, name: str, default: str | None = None) -> str | None:
        """::

            value = headers.get('Content-Type')
            value = headers.get('Content-Type', 'text/plain')

        Same as :meth:`header`, but returns the default for a header that does not
        exist.
        """
        value = self.header(name)
        return value if value is not None else default

    @overload
    def header(self, name: str, /) -> str | None: ...

    @overload
    def header(self, name: str, value: Anything, /, *values: Anything) -> Self: ...

    def header(self, name: str, /, *values: Anything) -> Self | str | None:
        """::

            value = headers.header('Foo')
            headers = headers.header('Foo', 'one value')
            headers = headers.header('Foo', 'first value', 'second value')

        Get or replace the current header values.
        """
        # Replace
        if values:
            return self.remove(name).add(name, *values)

        if (headers := self._headers.get(name.lower())) is None:
            return None
        return ', '.join(headers)

    host = _Shortcut('Host', "'127.0.0.1'")
    if_modified_since = _Shortcut('If-Modified-Since', "'Sun, 17 Aug 2008 16:27:35 GMT'")
    if_none_match = _Shortcut('If-None-Match', '\'"abc321"\'')

    @property
    def is_finished(self) -> bool:
        """::

            boolean = headers.is_finished

        Check if header parser is finished.
        """
        return self._state == 'finished'

    @property
    def is_limit_exceeded(self) -> bool:
        """::

            boolean = headers.is_limit_exceeded

        Check if headers have exceeded :attr:`max_line_size` or :attr:`max_lines`.
        """
        return self._limit

    # Not in Mojolicious: the mapping protocol of the standard library
    def items(self) -> list[tuple[str, str]]:
        """::

            items = headers.items()

        Return a list of :meth:`names` with the values that :meth:`header` gives.
        """
        return [(name, ', '.join(self._headers[name.lower()])) for name in self.names()]

    # Not in Mojolicious: the mapping protocol of the standard library
    def keys(self) -> list[str]:
        """::

            names = headers.keys()

        Alias for :meth:`names`.
        """
        return self.names()

    last_modified = _Shortcut('Last-Modified', "'Sun, 17 Aug 2008 16:27:35 GMT'")

    def leftovers(self) -> bytes:
        """::

            data = headers.leftovers()

        Get and remove leftover data from header parser.
        """
        buffer, self._buffer = bytes(self._buffer), bytearray()
        return buffer

    link = _Shortcut('Link', '\'<http://127.0.0.1/foo/3>; rel="next"\'', ' from :rfc:`5988`')

    @property
    def links(self) -> dict[str, dict[str, str]]:
        """::

            links = headers.links
            headers.links = {'next': 'http://example.com/foo', 'prev': 'http://example.com/bar'}

        Get or set web links from or to ``Link`` header according to :rfc:`5988`. ::

            # Extract information about next page
            print(headers.links['next']['link'])
            print(headers.links['next']['title'])
        """
        header = self.link or ''
        data: dict[str, dict[str, str]] = {}
        while m := re.match(r'[,\s]*<(.+?)>', header):
            target = m[1]
            params, header = header_params(header[m.end() :])
            if (rel := params.get('rel')) is not None:
                data.setdefault(rel, {**params, 'link': target})

        return data

    @links.setter
    def links(self, links: dict[str, str]) -> None:
        self.link = ', '.join(f'<{links[rel]}>; rel="{rel}"' for rel in sorted(links))

    location = _Shortcut('Location', "'http://127.0.0.1/foo'")

    def names(self) -> list[str]:
        """::

            names = headers.names()

        Return a list with all currently defined headers. ::

            # Names of all headers
            for name in headers.names():
                print(name)
        """
        return [NAMES.get(key) or self._names[key] for key in sorted(self._headers)]

    origin = _Shortcut('Origin', "'http://example.com'", ' from :rfc:`6454`')

    def parse(self, chunk: str | bytes | bytearray) -> Self:
        r"""::

            headers = headers.parse('Content-Type: text/plain\x0d\x0a\x0d\x0a')

        Parse formatted headers, given as characters or as bytes.
        """
        self._state = 'headers'
        # Not in Mojolicious: characters, as ISO-8859-1
        self._buffer += chunk if isinstance(chunk, (bytes, bytearray)) else chunk.encode('latin-1')
        headers = self._cache
        size = self.max_line_size
        lines = self.max_lines
        while (length := self._buffer.find(b'\x0a') + 1) > 0:
            raw = self._buffer[: length - 1]
            del self._buffer[:length]
            line = (raw[:-1] if raw.endswith(b'\x0d') else raw).decode('latin-1')

            # Check line size limit
            if length > size or len(headers) >= lines:
                self._state, self._limit = 'finished', True
                return self

            # New header
            if header := re.match(r'^(\S[^:]*):\s*(.*)$', line):
                headers.append([header[1], header[2]])

            # Multi-line
            elif (space := re.match(r'\s+', line)) and headers:
                headers[-1][1] += ' ' + line[space.end() :]

            # Empty line
            else:
                for name, value in headers:
                    self.add(name, value)
                self._state, self._cache = 'finished', []
                return self

        # Check line size limit
        if len(self._buffer) > size:
            self._state, self._limit = 'finished', True

        return self

    # Not in Mojolicious: the features of the browser that a document may use
    permissions_policy = _Shortcut(
        'Permissions-Policy',
        "'camera=(), geolocation=(), microphone=()'",
        ' from `Permissions Policy <https://www.w3.org/TR/permissions-policy/>`_',
    )
    proxy_authenticate = _Shortcut('Proxy-Authenticate', '\'Basic "realm"\'')
    proxy_authorization = _Shortcut('Proxy-Authorization', "'Basic Zm9vOmJhcg=='")
    range = _Shortcut('Range', "'bytes=2-8'")

    @property
    def referer(self) -> str | None:
        """::

            referrer = headers.referer
            headers.referer = 'http://example.com'

        Alias for :attr:`referrer`.
        """
        return self.referrer

    @referer.setter
    def referer(self, value: Anything) -> None:
        self.referrer = value

    @property
    def referrer(self) -> str | None:
        """::

            referrer = headers.referrer
            headers.referrer = 'http://example.com'

        Get or replace current header value, shortcut for the ``Referer`` header,
        there was a typo in :rfc:`2068` which resulted in ``Referer`` becoming an
        official header.
        """
        return self.header('Referer')

    @referrer.setter
    def referrer(self, value: Anything) -> None:
        self.header('Referer', value)

    # Not in Mojolicious: the referrer that the browser sends with the requests of a document
    referrer_policy = _Shortcut(
        'Referrer-Policy',
        "'strict-origin-when-cross-origin'",
        ' from `Referrer Policy <https://www.w3.org/TR/referrer-policy/>`_',
    )

    def remove(self, name: str) -> Self:
        """::

            headers = headers.remove('Foo')

        Remove a header.
        """
        self._headers.pop(name.lower(), None)
        return self

    # Not in Mojolicious: the endpoints of the reports of the browser, as the ones of CSP
    reporting_endpoints = _Shortcut(
        'Reporting-Endpoints',
        '\'csp="/csp-reports"\'',
        ' from `Reporting API <https://www.w3.org/TR/reporting-1/>`_',
    )
    sec_websocket_accept = _Shortcut(
        'Sec-WebSocket-Accept',
        "'s3pPLMBiTxaQ9kYGzzhZRbK+xOo='",
        ' from :rfc:`6455`',
    )
    sec_websocket_extensions = _Shortcut('Sec-WebSocket-Extensions', "'foo'", ' from :rfc:`6455`')
    sec_websocket_key = _Shortcut('Sec-WebSocket-Key', "'dGhlIHNhbXBsZSBub25jZQ=='", ' from :rfc:`6455`')
    sec_websocket_protocol = _Shortcut('Sec-WebSocket-Protocol', "'sample'", ' from :rfc:`6455`')
    sec_websocket_version = _Shortcut('Sec-WebSocket-Version', '13', ' from :rfc:`6455`')
    server = _Shortcut('Server', "'Pyjoyment'")
    server_timing = _Shortcut(
        'Server-Timing',
        "'app;desc=Pyjoyment;dur=0.0001'",
        ' from `Server Timing <https://www.w3.org/TR/server-timing/>`_',
    )
    set_cookie = _Shortcut('Set-Cookie', "'f=b; path=/'", ' from :rfc:`6265`')
    status = _Shortcut('Status', "'200 OK'", ' from :rfc:`3875`')
    strict_transport_security = _Shortcut('Strict-Transport-Security', "'max-age=31536000'", ' from :rfc:`6797`')
    te = _Shortcut('TE', "'chunked'")

    # Not in Mojolicious: bytes for the standard library and the network
    def to_bytes(self) -> bytes:
        """::

            data = headers.to_bytes()

        Turn headers into bytes, suitable for HTTP messages, with the characters
        encoded as ISO-8859-1.
        """
        return self.to_str().encode('latin-1')

    def to_dict(self, multi: bool = False) -> dict[str, str] | dict[str, list[str]]:
        """::

            single = headers.to_dict()
            multi = headers.to_dict(True)

        Turn headers into ``dict``, lists to represent multiple headers with the same
        name are disabled by default. ::

            print(headers.to_dict()['DNT'])
        """
        if multi:
            return {name: list(self._headers[name.lower()]) for name in self.names()}
        return dict(self.items())

    # Not in Mojolicious: a list of pairs for the standard library
    def to_list(self) -> list[tuple[str, str]]:
        """::

            pairs = headers.to_list()

        Turn headers into a list of pairs, one for each value, as WSGI and
        :meth:`http.client.HTTPResponse.getheaders` have them.
        """
        return [(name, value) for name in self.names() for value in self._headers[name.lower()]]

    # Not in Mojolicious: email.message of the standard library
    def to_message(self) -> Message:
        """::

            message = headers.to_message()

        Turn headers into an :class:`email.message.Message`, with each value as a
        header of its own, as :mod:`http.client` has them.
        """
        message = Message()
        for name, value in self.to_list():
            message[name] = value
        return message

    def to_str(self) -> str:
        """::

            string = headers.to_str()

        Turn headers into a string, suitable for HTTP messages.
        """
        # Make sure multi-line values are formatted correctly
        return '\x0d\x0a'.join(f'{name}: {value}' for name, value in self.to_list())

    trailer = _Shortcut('Trailer', "'X-Foo'")
    transfer_encoding = _Shortcut('Transfer-Encoding', "'chunked'")
    upgrade = _Shortcut('Upgrade', "'websocket'")
    user_agent = _Shortcut('User-Agent', "'Pyjoyment/1.0'")

    # Not in Mojolicious: the mapping protocol of the standard library
    def values(self) -> list[str]:
        """::

            values = headers.values()

        Return a list of the values that :meth:`header` gives, in the order of
        :meth:`names`.
        """
        return [value for _, value in self.items()]

    vary = _Shortcut('Vary', "'*'")
    www_authenticate = _Shortcut('WWW-Authenticate', '\'Basic realm="realm"\'')
    # Not in Mojolicious: the type of the content that the browser does not sniff
    x_content_type_options = _Shortcut(
        'X-Content-Type-Options',
        "'nosniff'",
        ' from `Fetch <https://fetch.spec.whatwg.org/#x-content-type-options-header>`_',
    )


new = Pyjo_Headers.new
object = Pyjo_Headers
Headers = Pyjo_Headers
