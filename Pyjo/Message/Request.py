r"""
Pyjo.Message.Request - HTTP request
===================================
::

    from Pyjo.Message.Request import Request

    # Parse
    req = Request()
    req.parse(b'GET /foo HTTP/1.0\x0d\x0a')
    req.parse(b'Content-Length: 12\x0d\x0a')
    req.parse(b'Content-Type: text/plain\x0d\x0a\x0d\x0a')
    req.parse(b'Hello World!')
    print(req.method)
    print(req.headers.content_type)
    print(req.body)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Message.Request

    # Parse
    req = Pyjo.Message.Request.new()
    req.parse(b'GET /foo HTTP/1.0\x0d\x0a')
    req.parse(b'Content-Length: 12\x0d\x0a')
    req.parse(b'Content-Type: text/plain\x0d\x0a\x0d\x0a')
    req.parse(b'Hello World!')
    print(req.method)
    print(req.headers.content_type)
    print(req.body)

    # Build
    req = Pyjo.Message.Request.new()
    req.url.parse('http://127.0.0.1/foo/bar')
    req.method = 'GET'
    print(req.to_bytes())

:mod:`Pyjo.Message.Request` is a container for HTTP requests, based on
`RFC 7230 <https://tools.ietf.org/html/rfc7230>`_,
`RFC 7231 <https://tools.ietf.org/html/rfc7231>`_,
`RFC 7235 <https://tools.ietf.org/html/rfc7235>`_ and
`RFC 2817 <https://tools.ietf.org/html/rfc2817>`_.

Events
------

:mod:`Pyjo.Message.Request` inherits all events from :mod:`Pyjo.Message`.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Message::Request <https://github.com/mojolicious/mojo/blob/v9.51/lib/Mojo/Message/Request.pm>`_
of Mojolicious 9.51.
"""

import Pyjo.Cookie.Request
import Pyjo.Message
import Pyjo.Parameters
import Pyjo.URL

from Pyjo.Util import b64_decode, b64_encode, b64url_encode, decode, sha1_bytes, url_unescape

import builtins
import os
import random
import re
import time
import urllib.request

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, Self, cast, overload


if TYPE_CHECKING:
    import http.server


type Anything = builtins.object


class Pyjo_Message_Request(Pyjo.Message.object):
    """
    :mod:`Pyjo.Message.Request` inherits all methods from :mod:`Pyjo.Message`
    and implements the following new ones.
    """

    def __init__(
        self,
        request: 'urllib.request.Request | http.server.BaseHTTPRequestHandler | None' = None,
        /,
        *,
        env: Mapping[str, Any] | None = None,
        method: str = 'GET',
        proxy: Pyjo.URL.object | None = None,
        request_id: str | None = None,
        reverse_proxy: bool | None = None,
        trusted_proxies: list[str] | None = None,
        url: Pyjo.URL.object | None = None,
        via_proxy: bool = True,
        **kwargs: Any,
    ) -> None:
        """::

            req = Pyjo.Message.Request.new()
            req = Pyjo.Message.Request.new(method='POST', url=Pyjo.URL.new('http://127.0.0.1/'))
            req = Pyjo.Message.Request.new(urllib.request.Request('http://127.0.0.1/', data=b'Hi!'))
            req = Pyjo.Message.Request.new(handler)

        Construct a new :mod:`Pyjo.Message.Request` object, from a request of
        the standard library if it is given: the method, URL, headers and data
        of a :class:`urllib.request.Request`, or the request that a
        :class:`http.server.BaseHTTPRequestHandler` has parsed, which is parsed
        again, as :meth:`parse` does, with the body that it reads from the
        ``rfile`` of the handler, of the ``Content-Length`` or chunked, and not
        further. ::

            # A request in a handler of http.server
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    req = Pyjo.Message.Request.new(self)
                    res = Pyjo.Message.Response.new(code=200).set(body=bytes(req.url.path))
                    self.wfile.write(res.to_bytes())
        """
        super().__init__(**kwargs)

        self.env: Mapping[str, Any] = env if env is not None else {}
        """::

            env = req.env
            req.env = {'PATH_INFO': '/'}

        Direct access to the ``CGI`` or ``WSGI`` environment dict if
        available. ::

            # Check CGI version
            version = req.env['GATEWAY_INTERFACE']

            # Check WSGI version
            version = req.env['wsgi.version']
        """

        self.method = method
        """::

            method = req.method
            req.method = 'POST'

        HTTP request method, defaults to ``GET``.
        """

        self.proxy = proxy
        """::

            url = req.proxy
            req.proxy = Pyjo.URL.new('http://127.0.0.1:3000')

        Proxy URL for request.
        """

        self.reverse_proxy = reverse_proxy
        """::

            boolean = req.reverse_proxy
            req.reverse_proxy = boolean

        Request has been performed through a reverse proxy.
        """

        self.trusted_proxies: list[str] = trusted_proxies if trusted_proxies is not None else []
        """::

            proxies = req.trusted_proxies
            req.trusted_proxies = ['10.0.0.0/8', '127.0.0.1', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7']

        Trusted reverse proxies, addresses or networks in CIDR form.
        """

        self.via_proxy = via_proxy
        """::

            boolean = req.via_proxy
            req.via_proxy = boolean

        Request can be performed through a proxy server.
        """

        self._params: Pyjo.Parameters.object | None = None
        self._request_id = request_id
        self._start_buffer: bytes | None = None
        self._url = url

        # Not in Mojolicious: a request of urllib or http.server
        if isinstance(request, urllib.request.Request):
            self._from_urllib(request)
        elif request is not None:
            self._from_http_server(request)

    @property
    def request_id(self) -> str:
        """::

            request_id = req.request_id
            req.request_id = 'aee7d5d8'

        Request ID, defaults to a reasonably unique value.
        """
        if self._request_id is None:
            self._request_id = _request_id()
        return self._request_id

    @request_id.setter
    def request_id(self, value: str) -> None:
        self._request_id = value

    @property
    def url(self) -> Pyjo.URL.object:
        """::

            url = req.url
            req.url = Pyjo.URL.new()

        HTTP request URL, defaults to a :mod:`Pyjo.URL` object. ::

            # Get request information
            info = req.url.to_abs().userinfo
            host = req.url.to_abs().host
            path = req.url.to_abs().path
        """
        if self._url is None:
            self._url = Pyjo.URL.new()
        return self._url

    @url.setter
    def url(self, value: Pyjo.URL.object) -> None:
        self._url = value

    def clone(self) -> Self | None:
        """::

            clone = req.clone()

        Return a new :mod:`Pyjo.Message.Request` object cloned from this
        request if possible, otherwise return ``None``.
        """
        # Dynamic requests cannot be cloned
        if (content := self.content.clone()) is None:
            return None
        clone = self.new(content=content, method=self.method, url=self.url.clone(), version=self.version)
        if self.proxy:
            clone.proxy = self.proxy.clone()

        return clone

    @overload
    def cookies(self) -> list[Pyjo.Cookie.Request.object]: ...

    @overload
    def cookies(self, cookie: Pyjo.Cookie.object | Mapping[str, Any], /, *cookies: Anything) -> Self: ...

    def cookies(self, *cookies: Anything) -> list[Pyjo.Cookie.Request.object] | Self:
        """::

            cookies = req.cookies()
            req = req.cookies(Pyjo.Cookie.Request.new())
            req = req.cookies({'name': 'foo', 'value': 'bar'})

        Access request cookies, usually :mod:`Pyjo.Cookie.Request` objects. ::

            # Names of all cookies
            for cookie in req.cookies():
                print(cookie.name)
        """
        # Parse cookies
        headers = self.headers
        if not cookies:
            return Pyjo.Cookie.Request.parse(headers.cookie)

        # Add cookies
        values = [headers.cookie] if headers.cookie else []
        for cookie in cookies:
            values.append(
                str(
                    Pyjo.Cookie.Request.new(**cast(Mapping[str, Any], cookie))
                    if isinstance(cookie, Mapping)
                    else cookie
                )
            )
        headers.cookie = '; '.join(values)

        return self

    def every_param(self, name: str) -> list[str]:
        """::

            values = req.every_param('foo')

        Similar to :meth:`param`, but returns all values sharing the same name
        as a list. ::

            # Get first value
            print(req.every_param('foo')[0])
        """
        return self.params.every_param(name)

    def extract_start_line(self, buffer: bytearray) -> bool | None:
        """::

            boolean = req.extract_start_line(buffer)

        Extract request-line from a :class:`bytearray`, which loses it.
        """
        # Ignore any leading empty lines
        if not (m := re.match(rb'\s*(.*?)\x0d?\x0a', bytes(buffer))):
            return None
        del buffer[: m.end()]

        # We have a (hopefully) full request-line
        if not (m := re.fullmatch(rb'(\S+)\s+(\S+)\s+HTTP/(\d\.\d)', m[1])):
            self.error = {'message': 'Bad request start-line'}
            return False
        self.method, self.version = m[1].decode('latin-1'), m[3].decode('latin-1')
        url = self.url
        target = m[2].decode('latin-1')
        if self.method == 'CONNECT':
            url.host_port = target
        elif re.match(r'[^:/?#]+:', target):
            url.parse(target).fragment = None
        else:
            url.path_query = target
        return True

    def fix_headers(self) -> Self:
        """::

            req = req.fix_headers()

        Make sure request has all required headers.
        """
        if self._fix:
            return self
        super().fix_headers()

        # Empty
        headers = self.headers
        if headers.content_length == '0' and self.method == 'GET':
            headers.remove('Content-Length')

        # Host
        url = self.url
        if headers.host is None:
            headers.host = url.host_port or ''

        # Basic authentication
        if (info := url.userinfo) and not headers.authorization:
            headers.authorization = 'Basic ' + _basic_encode(info)

        # Basic proxy authentication
        if not ((proxy := self.proxy) and self.via_proxy):
            return self
        if not (info := proxy.userinfo):
            return self
        if not headers.proxy_authorization:
            headers.proxy_authorization = 'Basic ' + _basic_encode(info)
        return self

    def get_start_line_chunk(self, offset: int) -> bytes:
        """::

            data = req.get_start_line_chunk(offset)

        Get a chunk of request-line data starting from a specific position.
        Note that this method finalizes the request.
        """
        buffer = self._start_line()
        self.emit('progress', 'start_line', offset)
        return buffer[offset : offset + 131072]

    @property
    def is_handshake(self) -> bool:
        """::

            boolean = req.is_handshake

        Check ``Upgrade`` header for ``websocket`` value.
        """
        return (self.headers.upgrade or '').lower() == 'websocket'

    @property
    def is_secure(self) -> bool:
        """::

            boolean = req.is_secure

        Check if connection is secure.
        """
        url = self.url
        return (url.protocol or url.base.protocol) == 'https'

    @property
    def is_xhr(self) -> bool:
        """::

            boolean = req.is_xhr

        Check ``X-Requested-With`` header for ``XMLHttpRequest`` value.
        """
        return bool(re.search(r'XMLHttpRequest', self.headers.header('X-Requested-With') or '', re.I))

    @overload
    def param(self, name: str, /) -> str | None: ...

    @overload
    def param(self, name: str, value: Anything, /, *values: Anything) -> Pyjo.Parameters.object: ...

    def param(self, name: str, /, *values: Anything) -> str | None | Pyjo.Parameters.object:
        """::

            value = req.param('foo')

        Access ``GET`` and ``POST`` parameters extracted from the query string
        and ``application/x-www-form-urlencoded`` or ``multipart/form-data``
        message body. If there are multiple values sharing the same name, and
        you want to access more than just the last one, you can use
        :meth:`every_param`. Note that this method caches all data, so it
        should not be called before the entire request body has been received.
        Parts of the request body need to be loaded into memory to parse
        ``POST`` parameters, so you have to make sure it is not excessively
        large. There's a 16MiB limit for requests by default.
        """
        return self.params.param(name, *values)

    @property
    def params(self) -> Pyjo.Parameters.object:
        """::

            params = req.params

        All ``GET`` and ``POST`` parameters extracted from the query string and
        ``application/x-www-form-urlencoded`` or ``multipart/form-data``
        message body, usually a :mod:`Pyjo.Parameters` object. Note that this
        method caches all data, so it should not be called before the entire
        request body has been received. Parts of the request body need to be
        loaded into memory to parse ``POST`` parameters, so you have to make
        sure it is not excessively large. There's a 16MiB limit for requests by
        default. ::

            # Get parameter names and values
            params = req.params.to_dict()
        """
        if self._params is None:
            self._params = self.body_params.clone().append(self.query_params)
        return self._params

    def parse(self, chunk: bytes | Mapping[str, Any]) -> Self:
        """::

            req = req.parse(b'GET /foo/bar HTTP/1.1')
            req = req.parse({'PATH_INFO': '/'})

        Parse HTTP request chunks or environment dict.
        """
        env, chunk = (chunk, b'') if isinstance(chunk, Mapping) else (None, chunk)

        # Parse CGI environment
        if env is not None:
            self.env = env
            self._parse_env(env)

        # Parse normal message
        if (self._state or '') != 'cgi':
            super().parse(chunk)

        # Parse CGI content
        else:
            if env is None:
                self._raw_size += len(chunk)
            self.content = self.content.parse_body(chunk)
            super().parse(b'')

        # Check if we can fix things that require all headers
        if not self.is_finished:
            return self

        # Base URL
        base = self.url.base
        if not base.scheme:
            base.scheme = 'http'
        headers = self.headers
        if not base.host and (host := headers.host):
            base.host_port = host

        # Basic authentication
        if basic := _basic(headers.authorization):
            base.userinfo = basic

        # Basic proxy authentication
        if basic := _basic(headers.proxy_authorization):
            self.proxy = Pyjo.URL.new().set(userinfo=basic)

        # "X-Forwarded-Proto"
        if self.reverse_proxy and headers.header('X-Forwarded-Proto') == 'https':
            base.scheme = 'https'

        return self

    @property
    def query_params(self) -> Pyjo.Parameters.object:
        """::

            params = req.query_params

        All ``GET`` parameters, usually a :mod:`Pyjo.Parameters` object. ::

            # Turn GET parameters to dict and extract value
            print(req.query_params.to_dict()['foo'])
        """
        return self.url.query

    @property
    def start_line_size(self) -> int:
        """::

            size = req.start_line_size

        Size of the request-line in bytes. Note that this method finalizes the
        request.
        """
        return len(self._start_line())

    # Not in Mojolicious: a request of urllib
    def to_urllib(self) -> urllib.request.Request:
        """::

            request = req.to_urllib()

        Turn request into a :class:`urllib.request.Request`, with the absolute
        :attr:`url`, the headers, the body and the :attr:`proxy`. urllib takes
        no userinfo in a URL, so the userinfo of :attr:`url` and :attr:`proxy`
        becomes the ``Authorization`` and ``Proxy-Authorization`` headers, as
        :meth:`fix_headers` does. ::

            # Send the request with urllib
            with urllib.request.urlopen(req.to_urllib()) as response:
                res = Pyjo.Message.Response.new(response)
        """
        url = self.url.to_abs()
        headers = self.headers
        body = self.build_body() if self.content.is_multipart else self.body
        request = urllib.request.Request(
            str(url),
            data=body or None,
            headers={name: value for name in headers.names() if (value := headers.header(name)) is not None},
            method=self.method,
        )

        # Basic authentication
        if (info := url.userinfo) and not headers.authorization:
            request.add_header('Authorization', 'Basic ' + _basic_encode(info))

        # Proxy with basic authentication
        if (proxy := self.proxy) and self.via_proxy:
            request.set_proxy(proxy.host_port or '', proxy.scheme or 'http')
            if (info := proxy.userinfo) and not headers.proxy_authorization:
                request.add_header('Proxy-Authorization', 'Basic ' + _basic_encode(info))

        return request

    # Not in Mojolicious: a request of http.server
    def _from_http_server(self, handler: 'http.server.BaseHTTPRequestHandler') -> None:
        start = f'{handler.command} {handler.path} {handler.request_version}\x0d\x0a'
        headers = ''.join(f'{name}: {value}\x0d\x0a' for name, value in handler.headers.items())
        self.parse(f'{start}{headers}\x0d\x0a'.encode('latin-1'))

        # The body of the Content-Length, or chunked line by line, so that nothing of the next request is read
        rfile = handler.rfile
        if not self.is_finished and (length := self.headers.content_length or '').isdigit():
            self.parse(rfile.read(int(length)))
        while not self.is_finished and (line := rfile.readline(131072)):
            self.parse(line)

    # Not in Mojolicious: a request of urllib
    def _from_urllib(self, request: urllib.request.Request) -> None:
        self.method = request.get_method()
        self.url = Pyjo.URL.new(request.full_url)
        headers = self.headers
        for name, value in request.header_items():
            headers.add(name, value)

        # Data as bytes, a file or an iterable of bytes
        data = request.data
        if data is None:
            return
        if isinstance(data, bytes | bytearray):
            self.body = bytes(data)
        elif isinstance(data, memoryview):
            self.body = data.tobytes()
        elif (read := getattr(data, 'read', None)) is not None:
            self.body = bytes(read())
        else:
            self.body = b''.join(bytes(chunk) for chunk in cast(Iterable[bytes], data))

    def _parse_env(self, env: Mapping[str, Any]) -> None:
        # Bypass normal message parser
        self._state = 'cgi'

        # Extract headers
        headers = self.headers
        url = self.url
        base = url.base
        for name, value in env.items():
            if not (m := re.match(r'HTTP_(.*)', name, re.I | re.S)):
                continue
            name, value = m[1].replace('_', '-'), str(value)
            headers.header(name, value)

            # Host/Port
            if name == 'HOST':
                if m := re.search(r':(\d+)$', value):
                    base.host, base.port = value[: m.start()], int(m[1])
                else:
                    base.host = value

        # Content-Type is a special case on some servers
        if env.get('CONTENT_TYPE'):
            headers.content_type = str(env['CONTENT_TYPE'])

        # Content-Length is a special case on some servers
        if env.get('CONTENT_LENGTH'):
            headers.content_length = str(env['CONTENT_LENGTH'])

        # Query
        if env.get('QUERY_STRING'):
            url.query.parse(str(env['QUERY_STRING']))

        # Method
        if env.get('REQUEST_METHOD'):
            self.method = str(env['REQUEST_METHOD'])

        # Scheme/Version
        if m := re.fullmatch(r'([^/]+)/([^/]+)', str(env.get('SERVER_PROTOCOL', ''))):
            base.scheme, self.version = m[1], m[2]

        # HTTPS
        if str(env.get('HTTPS', '')).upper() == 'ON':
            base.scheme = 'https'

        # Path
        path = url.path.parse(str(env['PATH_INFO']) if env.get('PATH_INFO') else '')

        # Base path
        if value := env.get('SCRIPT_NAME'):
            value = str(value)

            # Make sure there is a trailing slash (important for merging)
            base.path.parse(value if value.endswith('/') else f'{value}/')

            # Remove SCRIPT_NAME prefix if necessary (unless the server already did it)
            buffer = path.to_str()
            value = re.sub(r'^/|/$', '', value)
            uri = url_unescape(re.sub(r'\?.*$', '', str(env.get('REQUEST_URI') or ''), count=1))
            if not uri.startswith(f'/{value}' + str(env.get('PATH_INFO') or '')):
                buffer = re.sub(rf'^/?{re.escape(value)}(?:/|$)', '', buffer, count=1)
            buffer = re.sub(r'^/', '', buffer, count=1)
            path.parse(buffer)

    def _start_line(self) -> bytes:
        if self._start_buffer is not None:
            return self._start_buffer

        # Path
        url = self.url
        path = url.path_query
        if not path.startswith('/'):
            path = f'/{path}'

        # CONNECT
        method = self.method.upper()
        if method == 'CONNECT':
            port = url.port if url.port is not None else 443 if url.protocol == 'https' else 80
            path = f'{url.ihost}:{port}'

        # Proxy
        elif self.proxy and self.via_proxy and url.protocol != 'https':
            if not self.is_handshake:
                path = url.clone().set(userinfo=None).to_str()

        self._start_buffer = f'{method} {path} HTTP/{self.version}\x0d\x0a'.encode('latin-1')
        return self._start_buffer


def _basic(header: str | None) -> str | None:
    if not header or not (m := re.search(r'Basic (.+)$', header)):
        return None
    # Unlike Mojolicious: the userinfo is decoded from UTF-8 where it can be, as the URL decodes it; Mojo keeps the bytes
    info = b64_decode(m[1])
    return decoded if (decoded := decode('UTF-8', info)) is not None else info.decode('latin-1')


def _basic_encode(info: str) -> str:
    # Unlike Mojolicious: the userinfo is encoded as UTF-8, as the URL decodes it from UTF-8; Mojo encodes it as
    # Latin-1 and dies of "Wide character" on any other character
    return b64_encode(info.encode('UTF-8'), '')


# The seed and the counter of request IDs, made on first use, as Perl's state variables
_seed: str | None = None
_counter = 0


def _request_id() -> str:
    global _seed, _counter
    if _seed is None:
        _seed, _counter = f'{os.getpid()}{time.time()}{random.random()}', random.randrange(0xFFFFFF)
    _counter = (_counter + 1) % 0xFFFFFF
    return b64url_encode(sha1_bytes(f'{_seed}{_counter}'.encode()))[:12]


new = Pyjo_Message_Request.new
object = Pyjo_Message_Request
Request = Pyjo_Message_Request
