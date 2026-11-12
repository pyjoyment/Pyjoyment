import Pyjo.Message.Request

from Pyjo.Test import *

import os


with subtest('Parse Lighttpd CGI environment variables and body'):
    req = Pyjo.Message.Request.new()
    body = None

    @req.content.on('body')
    def body_cb(content):
        global body
        body = (body or 0) + 1

    req.parse(
        {
            'HTTP_CONTENT_LENGTH': 11,
            'HTTP_DNT': 1,
            'PATH_INFO': '/te+st/index.cgi/foo/bar',
            'QUERY_STRING': 'lalala=23&bar=baz',
            'REQUEST_METHOD': 'POST',
            'SCRIPT_NAME': '/te+st/index.cgi',
            'HTTP_HOST': 'localhost:8080',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    is_ok(body, 1, 'body event has been emitted once')
    req.parse(b'Hello ')
    is_ok(body, 1, 'body event has been emitted once')
    req.parse(b'World')
    is_ok(body, 1, 'body event has been emitted once')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.path, 'foo/bar', 'right path')
    is_ok(req.url.base.path, '/te+st/index.cgi/', 'right base path')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.base.port, 8080, 'right base port')
    is_ok(req.url.query, 'lalala=23&bar=baz', 'right query')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.headers.dnt, '1', 'right "DNT" value')
    is_ok(req.body, b'Hello World', 'right content')
    is_ok(
        req.url.to_abs().to_str(),
        'http://localhost:8080/te+st/index.cgi/foo/bar?lalala=23&bar=baz',
        'right absolute URL',
    )

with subtest('Parse Lighttpd CGI environment variables and body (behind reverse proxy)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'HTTP_CONTENT_LENGTH': 11,
            'HTTP_DNT': 1,
            'HTTP_X_FORWARDED_FOR': '127.0.0.1',
            'PATH_INFO': '/test/index.cgi/foo/bar',
            'QUERY_STRING': 'lalala=23&bar=baz',
            'REQUEST_METHOD': 'POST',
            'SCRIPT_NAME': '/test/index.cgi',
            'HTTP_HOST': 'mojolicious.org',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'Hello World')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.path, 'foo/bar', 'right path')
    is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
    is_ok(req.url.base.host, 'mojolicious.org', 'right base host')
    is_ok(req.url.base.port, None, 'no base port')
    is_ok(req.url.query, 'lalala=23&bar=baz', 'right query')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.headers.dnt, '1', 'right "DNT" value')
    is_ok(req.body, b'Hello World', 'right content')
    is_ok(
        req.url.to_abs().to_str(),
        'http://mojolicious.org/test/index.cgi/foo/bar?lalala=23&bar=baz',
        'right absolute URL',
    )

with subtest('Parse Apache CGI environment variables and body'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 11,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'HTTP_DNT': 1,
            'PATH_INFO': '/test/index.cgi/foo/bar',
            'QUERY_STRING': 'lalala=23&bar=baz',
            'REQUEST_METHOD': 'POST',
            'SCRIPT_NAME': '/test/index.cgi',
            'HTTP_HOST': 'localhost:8080',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'hello=world')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.path, 'foo/bar', 'right path')
    is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.base.port, 8080, 'right base port')
    is_ok(req.url.query, 'lalala=23&bar=baz', 'right query')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.headers.dnt, '1', 'right "DNT" value')
    is_ok(req.body, b'hello=world', 'right content')
    is_deeply_ok(req.param('hello'), 'world', 'right value')
    is_ok(
        req.url.to_abs().to_str(),
        'http://localhost:8080/test/index.cgi/foo/bar?lalala=23&bar=baz',
        'right absolute URL',
    )

with subtest('Parse CGI environment with maximum message size'):
    req = Pyjo.Message.Request.new()
    req.max_message_size = 10
    req.parse(
        {
            'CONTENT_LENGTH': 26,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'HTTP_DNT': 1,
            'PATH_INFO': '/test/index.cgi/foo/bar',
            'QUERY_STRING': 'lalala=23&bar=baz',
            'REQUEST_METHOD': 'POST',
            'SCRIPT_NAME': '/test/index.cgi',
            'HTTP_HOST': 'localhost:8080',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'abcdefghijklm')
    req.parse(b'nopqrstuvwxyz')
    ok(req.is_finished, 'request is finished')
    ok(req.is_limit_exceeded, 'limit exceeded')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.path, 'foo/bar', 'right path')
    is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.base.port, 8080, 'right base port')
    is_ok(req.url.query, 'lalala=23&bar=baz', 'right query')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.headers.dnt, '1', 'right "DNT" value')
    is_ok(req.body, b'abcdefghijklm', 'right content')
    is_ok(
        req.url.to_abs().to_str(),
        'http://localhost:8080/test/index.cgi/foo/bar?lalala=23&bar=baz',
        'right absolute URL',
    )

with subtest('Parse Apache CGI environment variables and body (file storage)'):
    os.environ['PYJO_MAX_MEMORY_SIZE'] = '10'
    try:
        req = Pyjo.Message.Request.new()
        is_ok(req.content.asset.max_memory_size, 10, 'right size')
        ok(not req.content.is_parsing_body, b'is not parsing body')
        req.parse(
            {
                'CONTENT_LENGTH': 12,
                'CONTENT_TYPE': 'text/plain',
                'HTTP_DNT': 1,
                'PATH_INFO': '/test/index.cgi/foo/bar',
                'QUERY_STRING': 'lalala=23&bar=baz',
                'REQUEST_METHOD': 'POST',
                'SCRIPT_NAME': '/test/index.cgi',
                'HTTP_HOST': 'localhost:8080',
                'SERVER_PROTOCOL': 'HTTP/1.1',
            }
        )
        ok(req.content.is_parsing_body, b'is parsing body')
        is_ok(req.content.progress, 0, 'right progress')
        req.parse(b'Hello ')
        ok(req.content.is_parsing_body, b'is parsing body')
        ok(not req.content.asset.is_file, 'stored in memory')
        is_ok(req.content.progress, 6, 'right progress')
        req.parse(b'World!')
        ok(not req.content.is_parsing_body, b'is not parsing body')
        ok(req.content.asset.is_file, 'stored in file')
        is_ok(req.content.progress, 12, 'right progress')
        ok(req.is_finished, 'request is finished')
        ok(not req.content.is_multipart, 'no multipart content')
        is_ok(req.method, 'POST', 'right method')
        is_ok(req.url.path, 'foo/bar', 'right path')
        is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
        is_ok(req.url.base.host, 'localhost', 'right base host')
        is_ok(req.url.base.port, 8080, 'right base port')
        is_ok(req.url.query, 'lalala=23&bar=baz', 'right query')
        is_ok(req.version, '1.1', 'right version')
        is_ok(req.headers.dnt, '1', 'right "DNT" value')
        is_ok(req.headers.content_type, 'text/plain', 'right "Content-Type" value')
        is_ok(req.headers.content_length, '12', 'right "Content-Length" value')
        is_ok(req.body, b'Hello World!', 'right content')
        is_ok(
            req.url.to_abs().to_str(),
            'http://localhost:8080/test/index.cgi/foo/bar?lalala=23&bar=baz',
            'right absolute URL',
        )
    finally:
        del os.environ['PYJO_MAX_MEMORY_SIZE']

with subtest('Parse Apache CGI environment variables with basic authentication'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 11,
            'HTTP_Authorization': 'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==',
            'HTTP_Proxy_Authorization': 'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'HTTP_DNT': 1,
            'PATH_INFO': '/test/index.cgi/foo/bar',
            'QUERY_STRING': 'lalala=23&bar=baz',
            'REQUEST_METHOD': 'POST',
            'SCRIPT_NAME': '/test/index.cgi',
            'HTTP_HOST': 'localhost:8080',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'hello=world')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.path, 'foo/bar', 'right path')
    is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.base.port, 8080, 'right base port')
    is_ok(req.url.query, 'lalala=23&bar=baz', 'right query')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.headers.dnt, '1', 'right "DNT" value')
    is_ok(req.body, b'hello=world', 'right content')
    is_deeply_ok(req.param('hello'), 'world', 'right value')
    is_ok(
        req.url.to_abs().to_str(),
        'http://localhost:8080/test/index.cgi/foo/bar?lalala=23&bar=baz',
        'right absolute URL',
    )
    is_ok(req.url.base, 'http://localhost:8080/test/index.cgi/', 'right base URL')
    is_ok(req.url.base.userinfo, 'Aladdin:open sesame', 'right userinfo')
    is_ok(req.url, 'foo/bar?lalala=23&bar=baz', 'right URL')
    is_ok(req.proxy.userinfo, 'Aladdin:open sesame', 'right proxy userinfo')

with subtest('Parse Apache 2.2 (win32) CGI environment variables and body'):
    req = Pyjo.Message.Request.new()
    finished = progress = None

    @req.on('finish')
    def finish(req):
        global finished
        finished = req.is_finished

    @req.on('progress')
    def progress_cb(req, *args):
        global progress
        progress = (progress or 0) + 1

    ok(not finished, 'not finished')
    ok(not progress, 'no progress')
    is_ok(req.content.progress, 0, 'right progress')
    req.parse(
        {
            'CONTENT_LENGTH': 87,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded; charset=UTF-8',
            'PATH_INFO': '',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'POST',
            'SCRIPT_NAME': '/index.pl',
            'HTTP_HOST': 'test1',
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
    )
    ok(not finished, 'not finished')
    ok(progress, 'made progress')
    progress = 0
    is_ok(req.content.progress, 0, 'right progress')
    req.parse(b'request=&ajax=true&login=test&password=111&')
    ok(not finished, 'not finished')
    ok(progress, 'made progress')
    progress = 0
    is_ok(req.content.progress, 43, 'right progress')
    req.parse(b'edition=db6d8b30-16df-4ecd-be2f-c8194f94e1f4')
    ok(finished, 'finished')
    ok(progress, 'made progress')
    is_ok(req.content.progress, 87, 'right progress')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.path, '', 'no path')
    is_ok(req.url.base.path, '/index.pl/', 'right base path')
    is_ok(req.url.base.host, 'test1', 'right base host')
    is_ok(req.url.base.port, None, 'no base port')
    ok(not req.url.query.to_str(), 'no query')
    is_ok(req.version, '1.1', 'right version')
    is_ok(
        req.body,
        b'request=&ajax=true&login=test&password=111&' + b'edition=db6d8b30-16df-4ecd-be2f-c8194f94e1f4',
        'right content',
    )
    is_ok(req.param('ajax'), 'true', 'right value')
    is_ok(req.param('login'), 'test', 'right value')
    is_ok(req.param('password'), '111', 'right value')
    is_ok(req.param('edition'), 'db6d8b30-16df-4ecd-be2f-c8194f94e1f4', 'right value')
    is_ok(req.url.to_abs().to_str(), 'http://test1/index.pl/', 'right absolute URL')

with subtest('Parse Apache 2.2 (win32) CGI environment variables and body'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 87,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded; charset=UTF-8',
            'PATH_INFO': '',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'POST',
            'SCRIPT_NAME': '/index.pl',
            'HTTP_HOST': 'test1',
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
    )
    req.parse(b'request=&ajax=true&login=test&password=111&')
    req.parse(b'edition=db6d8b30-16df-4ecd-be2f-c8194f94e1f4')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.path, '', 'no path')
    is_ok(req.url.base.path, '/index.pl/', 'right base path')
    is_ok(req.url.base.host, 'test1', 'right base host')
    is_ok(req.url.base.port, None, 'no base port')
    ok(not req.url.query.to_str(), 'no query')
    is_ok(req.version, '1.1', 'right version')
    is_ok(
        req.body,
        b'request=&ajax=true&login=test&password=111&' + b'edition=db6d8b30-16df-4ecd-be2f-c8194f94e1f4',
        'right content',
    )
    is_ok(req.param('ajax'), 'true', 'right value')
    is_ok(req.param('login'), 'test', 'right value')
    is_ok(req.param('password'), '111', 'right value')
    is_ok(req.param('edition'), 'db6d8b30-16df-4ecd-be2f-c8194f94e1f4', 'right value')
    is_ok(req.url.to_abs().to_str(), 'http://test1/index.pl/', 'right absolute URL')

with subtest('Parse Apache 2.2.14 CGI environment variables and body (root)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'SCRIPT_NAME': '/upload',
            'SERVER_NAME': '127.0.0.1',
            'SERVER_ADMIN': '[no address given]',
            'PATH_INFO': '/upload',
            'HTTP_CONNECTION': 'Keep-Alive',
            'REQUEST_METHOD': 'POST',
            'CONTENT_LENGTH': '11',
            'SCRIPT_FILENAME': '/tmp/SnLu1cQ3t2/test.fcgi',
            'SERVER_SOFTWARE': 'Apache/2.2.14 (Unix) mod_fastcgi/2.4.2',
            'QUERY_STRING': '',
            'REMOTE_PORT': '58232',
            'HTTP_USER_AGENT': 'Mojolicious (Perl)',
            'SERVER_PORT': '13028',
            'SERVER_SIGNATURE': '',
            'REMOTE_ADDR': '127.0.0.1',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded; charset=UTF-8',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'REQUEST_URI': '/upload',
            'GATEWAY_INTERFACE': 'CGI/1.1',
            'SERVER_ADDR': '127.0.0.1',
            'DOCUMENT_ROOT': '/tmp/SnLu1cQ3t2',
            'PATH_TRANSLATED': '/tmp/test.fcgi/upload',
            'HTTP_HOST': '127.0.0.1:13028',
        }
    )
    req.parse(b'hello=world')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.base.host, '127.0.0.1', 'right base host')
    is_ok(req.url.base.port, 13028, 'right base port')
    is_ok(req.url.path, '', 'no path')
    is_ok(req.url.base.path, '/upload/', 'right base path')
    is_ok(req.version, '1.1', 'right version')
    ok(not req.is_secure, 'not secure')
    is_ok(req.body, b'hello=world', 'right content')
    is_deeply_ok(req.param('hello'), 'world', 'right parameters')
    is_ok(req.url.to_abs().to_str(), 'http://127.0.0.1:13028/upload/', 'right absolute URL')

with subtest('Parse Apache 2.2.11 CGI environment variables and body (HTTPS=ON)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 11,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'PATH_INFO': '/foo/bar',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '/test/index.cgi',
            'HTTP_HOST': 'localhost',
            'HTTPS': 'ON',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'hello=world')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'GET', 'right method')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.path, 'foo/bar', 'right path')
    is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
    is_ok(req.version, '1.0', 'right version')
    ok(req.is_secure, 'is secure')
    is_ok(req.body, b'hello=world', 'right content')
    is_deeply_ok(req.param('hello'), 'world', 'right parameters')
    is_ok(req.url.to_abs().to_str(), 'https://localhost/test/index.cgi/foo/bar', 'right absolute URL')

with subtest('Parse Apache 2.2.11 CGI environment variables and body (trailing slash)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 11,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'PATH_INFO': '/foo/bar/',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '/test/index.cgi',
            'HTTP_HOST': 'localhost',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'hello=world')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'GET', 'right method')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.path, 'foo/bar/', 'right path')
    is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.body, b'hello=world', 'right content')
    is_deeply_ok(req.param('hello'), 'world', 'right parameters')
    is_ok(req.url.to_abs().to_str(), 'http://localhost/test/index.cgi/foo/bar/', 'right absolute URL')

with subtest('Parse Apache 2.2.11 CGI environment variables and body (no SCRIPT_NAME)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 11,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'PATH_INFO': '/foo/bar',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'HTTP_HOST': 'localhost',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'hello=world')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'GET', 'right method')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.path, '/foo/bar', 'right path')
    is_ok(req.url.base.path, '', 'no base path')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.body, b'hello=world', 'right content')
    is_deeply_ok(req.param('hello'), 'world', 'right parameters')
    is_ok(req.url.to_abs().to_str(), 'http://localhost/foo/bar', 'right absolute URL')

with subtest('Parse Apache 2.2.11 CGI environment variables and body (no PATH_INFO)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 11,
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '/test/index.cgi',
            'HTTP_HOST': 'localhost',
            'SERVER_PROTOCOL': 'HTTP/1.0',
        }
    )
    req.parse(b'hello=world')
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'GET', 'right method')
    is_ok(req.url.base.host, 'localhost', 'right base host')
    is_ok(req.url.path, '', 'no path')
    is_ok(req.url.base.path, '/test/index.cgi/', 'right base path')
    is_ok(req.version, '1.0', 'right version')
    is_ok(req.body, b'hello=world', 'right content')
    is_deeply_ok(req.param('hello'), 'world', 'right parameters')
    is_ok(req.url.to_abs().to_str(), 'http://localhost/test/index.cgi/', 'right absolute URL')

with subtest('Parse Apache 2.2.9 CGI environment variables (root without PATH_INFO)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'SCRIPT_NAME': '/cgi-bin/myapp/myapp.pl',
            'HTTP_CONNECTION': 'keep-alive',
            'HTTP_HOST': 'getmyapp.org',
            'REQUEST_METHOD': 'GET',
            'QUERY_STRING': '',
            'REQUEST_URI': '/cgi-bin/myapp/myapp.pl',
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
    )
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'GET', 'right method')
    is_ok(req.url.base.host, 'getmyapp.org', 'right base host')
    is_ok(req.url.path, '', 'no path')
    is_ok(req.url.base.path, '/cgi-bin/myapp/myapp.pl/', 'right base path')
    is_ok(req.version, '1.1', 'right version')
    is_ok(req.url.to_abs().to_str(), 'http://getmyapp.org/cgi-bin/myapp/myapp.pl/', 'right absolute URL')

with subtest('Parse Apache mod_fastcgi CGI environment variables (multipart file upload)'):
    req = Pyjo.Message.Request.new()
    is_ok(req.content.progress, 0, 'right progress')
    req.parse(
        {
            'SCRIPT_NAME': '',
            'SERVER_NAME': '127.0.0.1',
            'SERVER_ADMIN': '[no address given]',
            'PATH_INFO': '/upload',
            'HTTP_CONNECTION': 'Keep-Alive',
            'REQUEST_METHOD': 'POST',
            'CONTENT_LENGTH': '139',
            'SCRIPT_FILENAME': '/tmp/SnLu1cQ3t2/test.fcgi',
            'SERVER_SOFTWARE': 'Apache/2.2.14 (Unix) mod_fastcgi/2.4.2',
            'QUERY_STRING': '',
            'REMOTE_PORT': '58232',
            'HTTP_USER_AGENT': 'Mojolicious (Perl)',
            'SERVER_PORT': '13028',
            'SERVER_SIGNATURE': '',
            'REMOTE_ADDR': '127.0.0.1',
            'CONTENT_TYPE': 'multipart/form-data; boundary=8jXGX',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'PATH': '/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin',
            'REQUEST_URI': '/upload',
            'GATEWAY_INTERFACE': 'CGI/1.1',
            'SERVER_ADDR': '127.0.0.1',
            'DOCUMENT_ROOT': '/tmp/SnLu1cQ3t2',
            'PATH_TRANSLATED': '/tmp/test.fcgi/upload',
            'HTTP_HOST': '127.0.0.1:13028',
        }
    )
    is_ok(req.content.progress, 0, 'right progress')
    req.parse(b'--8jXGX\x0d\x0a')
    is_ok(req.content.progress, 9, 'right progress')
    req.parse(
        b'Content-Disposition: form-data; name="file"; filename="file.txt"'
        + b'\x0d\x0aContent-Type: application/octet-stream\x0d\x0a\x0d\x0a'
    )
    is_ok(req.content.progress, 117, 'right progress')
    req.parse(b'11023456789')
    is_ok(req.content.progress, 128, 'right progress')
    req.parse(b'\x0d\x0a--8jXGX--')
    is_ok(req.content.progress, 139, 'right progress')
    ok(req.is_finished, 'request is finished')
    ok(req.content.is_multipart, 'multipart content')
    is_ok(req.method, 'POST', 'right method')
    is_ok(req.url.base.host, '127.0.0.1', 'right base host')
    is_ok(req.url.path, '/upload', 'right path')
    is_ok(req.url.base.path, '', 'no base path')
    is_ok(req.version, '1.1', 'right version')
    is_ok(req.url.to_abs().to_str(), 'http://127.0.0.1:13028/upload', 'right absolute URL')
    file = req.upload('file')
    is_ok(file.filename, 'file.txt', 'right filename')
    is_ok(file.slurp(), b'11023456789', 'right uploaded content')

with subtest('Parse PSGI like environment (SCRIPT_NAME prefix already removed)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'PATH_INFO': '/app/admin',
            'REQUEST_METHOD': 'GET',
            'REQUEST_URI': '/app/app/admin?foo=bar',
            'QUERY_STRING': 'foo=bar',
            'SCRIPT_NAME': '/app',
            'HTTP_HOST': 'localhost:8080',
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
    )
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'GET', 'right method')
    is_ok(req.url.path, 'app/admin', 'right path')
    is_ok(req.url.base.path, '/app/', 'right base path')
    is_ok(req.url.to_abs().to_str(), 'http://localhost:8080/app/app/admin?foo=bar', 'right absolute URL')

    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'PATH_INFO': '/appadmin',
            'REQUEST_METHOD': 'GET',
            'REQUEST_URI': '/app/appadmin',
            'SCRIPT_NAME': '/app',
            'HTTP_HOST': 'localhost:8080',
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
    )
    ok(req.is_finished, 'request is finished')
    is_ok(req.url.path, 'appadmin', 'right path')
    is_ok(req.url.to_abs().to_str(), 'http://localhost:8080/app/appadmin', 'right absolute URL')

with subtest('Parse CGI environment (SCRIPT_NAME prefix without segment boundary)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'PATH_INFO': '/appadmin',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '/app',
            'HTTP_HOST': 'localhost:8080',
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
    )
    ok(req.is_finished, 'request is finished')
    is_ok(req.url.path, 'appadmin', 'right path')
    is_ok(req.url.to_abs().to_str(), 'http://localhost:8080/app/appadmin', 'right absolute URL')

with subtest('Parse IIS 7.5 like CGI environment (HTTPS=off)'):
    req = Pyjo.Message.Request.new()
    req.parse(
        {
            'CONTENT_LENGTH': 0,
            'PATH_INFO': '/index.pl/',
            'SERVER_SOFTWARE': 'Microsoft-IIS/7.5',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '/index.pl',
            'HTTP_HOST': 'test',
            'HTTPS': 'off',
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
    )
    ok(req.is_finished, 'request is finished')
    is_ok(req.method, 'GET', 'right method')
    is_ok(req.url.path, '', 'right URL')
    is_ok(req.url.base.protocol, 'http', 'right base protocol')
    is_ok(req.url.base.path, '/index.pl/', 'right base path')
    is_ok(req.url.base.host, 'test', 'right base host')
    ok(not req.url.query.to_str(), 'no query')
    is_ok(req.version, '1.1', 'right version')
    ok(not req.is_secure, 'not secure')

# Not in Mojolicious: the method and the query of "0", which Mojolicious 9.54 takes from the environment without a test,
# and an empty method, which is defined
with subtest('Parse CGI environment variables with a method and a query of 0'):
    req = Pyjo.Message.Request.new()
    req.parse({'PATH_INFO': '/', 'QUERY_STRING': '0', 'REQUEST_METHOD': '0', 'HTTP_HOST': 'localhost'})
    is_ok(req.method, '0', 'right method')
    is_ok(req.url.query.to_str(), '0', 'right query')

    req = Pyjo.Message.Request.new()
    req.parse({'PATH_INFO': '/', 'REQUEST_METHOD': '', 'HTTP_HOST': 'localhost'})
    is_ok(req.method, '', 'empty method')

done_testing()
