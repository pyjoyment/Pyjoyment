import Pyjo.App.FastCGI
import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjo.URL
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.Server.FastCGI import END_REQUEST, HEADER, PARAMS, STDIN, STDOUT, _pairs, _record  # pyright: ignore[reportPrivateUsage]
from Pyjo.Test import *
from Pyjo.Util import url_escape

import concurrent.futures
import http.client
import os
import re
import socket
import struct
import sys
import time


# An application of Pyjoyment on the FastCGI server of Pyjo, in the event loop of the test, which gives the parameters
# that it gets, and responses and chunks that come from timers
inner = Pyjoyment.new()
inner.log.level = 'fatal'


def env(c):
    c.render(json={'env': dict(c.req.env), 'body': c.req.body.decode('latin-1')})


inner.routes.any('/env/*rest', {'rest': ''}).to(cb=env)


@inner.routes.get('/later')
def later(c):
    c.render_later()
    Pyjo.IOLoop.timer(0.01, lambda loop: c.render(text=f'Hello later at {c.url_for("/")}!'))


@inner.routes.get('/chunks')
def chunks(c):
    def write(n):
        if n < 3:
            Pyjo.IOLoop.timer(0.01, lambda loop: c.write_chunk(f'{n}'.encode(), lambda c: write(n + 1)))
        else:
            c.finish()

    write(0)


@inner.routes.get('/length')
def length(c):
    c.res.headers.content_length = 6
    c.write(b'one', lambda c: Pyjo.IOLoop.timer(0.01, lambda loop: c.write(b'two', lambda c: c.finish())))


@inner.routes.get('/redirect')
def redirect(c):
    c.redirect_to('/later')


daemon = Pyjo.Server.Daemon.new(app=inner, listen=['fcgi://127.0.0.1'], silent=True).start()
URL = f'fcgi://127.0.0.1:{daemon.ports()[0]}'


# The value of a promise, which the event loop fulfills
def result(promise):
    values = []
    promise.then(lambda *args: values.extend(args)).wait()
    return values[0] if len(values) == 1 else values


# The response as it is on the wire, as the user agent removes the chunked transfer encoding
def raw(t, method, path='/'):
    url = t if isinstance(t, Pyjo.URL.object) else t.ua.server.url()

    def request():
        connection = http.client.HTTPConnection(url.host, url.port, timeout=5)
        try:
            connection.request(method, path)
            res = connection.getresponse()
            try:
                body = res.read()
            except http.client.IncompleteRead as e:
                body = ('incomplete', e.partial)
            return res.status, res.getheader('Content-Length'), res.getheader('Transfer-Encoding'), body
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(1) as executor:
        return result(Pyjo.Promise.new(executor.submit(request)))


def application(fcgi, prefix='/prefix'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    route = app.routes.any(prefix)
    route.partial = True
    route.to(app=fcgi)
    return app


# A responder of FastCGI that answers a request, once its body has ended, with the bytes of a reply, and closes the
# connection after them, unless it is told to keep it, and the requests that it got, and the connections in a list
def responder(reply, close=True, delay=0, connections=None):
    requests = []

    def accept(loop, stream, id):
        if connections is not None:
            connections.append(id)
        buffer = bytearray()

        def answer(*args):
            stream.write(reply, (lambda stream: stream.close()) if close else None)

        def read(stream, chunk):
            buffer.extend(chunk)
            if _record(STDIN, 1) in buffer:
                requests.append(bytes(buffer))
                buffer.clear()
                if reply is not None:
                    Pyjo.IOLoop.timer(delay, answer) if delay else answer()

        stream.on('read', read)

    id = Pyjo.IOLoop.server(accept, address='127.0.0.1')
    return f'fcgi://127.0.0.1:{Pyjo.IOLoop.acceptor(id).port}', requests, id


def stdout(*chunks):
    return b''.join(_record(STDOUT, 1, chunk) for chunk in chunks) + _record(STDOUT, 1)


def end():
    return _record(END_REQUEST, 1, struct.pack('>IB3x', 0, 0))


# The parameters of a request that a responder got
def params(request):
    data, offset = b'', 0
    while offset + HEADER.size <= len(request):
        version, type, id, length, padding = HEADER.unpack_from(request, offset)
        if type == PARAMS:
            data += request[offset + HEADER.size : offset + HEADER.size + length]
        offset += HEADER.size + length + padding
    return _pairs(data)


with subtest('Parameters'):
    with Pyjo.App.FastCGI.new(url=URL) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/env?a=1&b=%20', {'X-Foo': 'bar', 'Proxy': 'http://evil.example:8080'}).status_is(200)
        env = t.tx.res.json('/env')
        is_ok(env['REQUEST_METHOD'], 'GET', 'right method')
        is_ok(env['SCRIPT_NAME'], '', 'no script name')
        is_ok(env['PATH_INFO'], '/env', 'right path')
        is_ok(env['QUERY_STRING'], 'a=1&b=%20', 'right query')
        is_ok(env['REQUEST_URI'], '/env?a=1&b=%20', 'right request URI')
        is_ok(env['SERVER_NAME'], '127.0.0.1', 'right server name')
        is_ok(env['SERVER_PORT'], str(t.ua.server.url().port), 'right server port')
        is_ok(env['SERVER_PROTOCOL'], 'HTTP/1.1', 'right protocol')
        is_ok(env['GATEWAY_INTERFACE'], 'CGI/1.1', 'right gateway interface')
        is_ok(env['SERVER_SOFTWARE'], 'Pyjoyment (Python)', 'right server software')
        is_ok(env['REMOTE_ADDR'], '127.0.0.1', 'right remote address')
        ok(env['REMOTE_PORT'].isdigit(), 'remote port')
        is_ok(env['HTTP_X_FOO'], 'bar', 'right header')
        ok('HTTP_PROXY' not in env, 'no header Proxy, as with httpoxy')
        ok('HTTPS' not in env, 'not secure')
        ok('CONTENT_LENGTH' not in env, 'no content length')

    # The parameters of the application, which replace the ones of the request
    with Pyjo.App.FastCGI.new(
        url=URL, env={'SCRIPT_FILENAME': '/var/www/index.php', 'SERVER_NAME': 'example.com'}
    ) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/env').status_is(200)
        is_ok(t.tx.res.json('/env/SCRIPT_FILENAME'), '/var/www/index.php', 'added parameter')
        is_ok(t.tx.res.json('/env/SERVER_NAME'), 'example.com', 'replaced parameter')

with subtest('Body'):
    with Pyjo.App.FastCGI.new(url=URL) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.post_ok('/env', {'Content-Type': 'text/plain'}, b'Hello!').status_is(200)
        is_ok(t.tx.res.json('/env/CONTENT_TYPE'), 'text/plain', 'right content type')
        is_ok(t.tx.res.json('/env/CONTENT_LENGTH'), '6', 'right content length')
        is_ok(t.tx.res.json('/body'), 'Hello!', 'right body')

        # Chunked
        tx = t.ua.build_tx('POST', '/env')
        tx.req.content.write_chunk(b'Hello').write_chunk(b' World!').write_chunk(b'')
        t.request_ok(tx).status_is(200)
        is_ok(t.tx.res.json('/env/CONTENT_LENGTH'), '12', 'right content length')
        is_ok(t.tx.res.json('/body'), 'Hello World!', 'right body')

        # In more than one record
        body = b'0123456789' * 20000
        t.post_ok('/env', body).status_is(200)
        is_ok(t.tx.res.json('/env/CONTENT_LENGTH'), '200000', 'right content length')
        ok(t.tx.res.json('/body') == body.decode(), 'right body')

with subtest('Path of a route'):
    with Pyjo.App.FastCGI.new(url=URL) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi))
        t.get_ok('/prefix/env/foo/bar?x=1').status_is(200)
        is_ok(t.tx.res.json('/env/SCRIPT_NAME'), '/prefix', 'right script name')
        is_ok(t.tx.res.json('/env/PATH_INFO'), '/env/foo/bar', 'right path')
        is_ok(t.tx.res.json('/env/REQUEST_URI'), '/prefix/env/foo/bar?x=1', 'right request URI')

        # Not after a part of the path that does not end with a slash, which cannot be SCRIPT_NAME
        t.get_ok('/prefixx').status_is(404)

        # The path of the mount itself
        t.get_ok('/prefix/later').status_is(200).content_is('Hello later at /prefix!')

        # Escaped, as the bytes of the path
        t.get_ok('/prefix/env/a%20b/%E2%99%A5').status_is(200)
        # The bytes of the path in the parameter, which the server of Pyjo escapes beyond ASCII
        is_ok(t.tx.res.json('/env/PATH_INFO'), '/env/a b/%E2%99%A5', 'right path')

with subtest('Directory of the scripts'):
    url, requests, id = responder(stdout(b'Status: 200\r\n\r\nOK') + end())
    with Pyjo.App.FastCGI.new(url=url, document_root='/var/www/') as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/php'))
        for path, script, name, info in (
            ('/php', '/var/www/index.php', '/php/index.php', ''),
            ('/php/', '/var/www/index.php', '/php/index.php', ''),
            ('/php/phpinfo.php', '/var/www/phpinfo.php', '/php/phpinfo.php', ''),
            ('/php/index.php/foo/bar?x=1', '/var/www/index.php', '/php/index.php', '/foo/bar'),
            ('/php/index.php/', '/var/www/index.php', '/php/index.php', '/'),
            ('/php/dir/', '/var/www/dir/index.php', '/php/dir/index.php', ''),
            ('/php/foo', '/var/www/foo', '/php/foo', ''),
        ):
            t.get_ok(path).status_is(200).content_is('OK')
            env = params(requests[-1])
            is_ok(env['SCRIPT_FILENAME'], script, f'right script file of {path}')
            is_ok(env['SCRIPT_NAME'], name, f'right script name of {path}')
            is_ok(env['PATH_INFO'], info, f'right path of {path}')
            is_ok(env['DOCUMENT_ROOT'], '/var/www/', f'right document root of {path}')
        is_ok(params(requests[-4])['REQUEST_URI'], '/php/index.php/foo/bar?x=1', 'right request URI')

        # Not above the directory
        count = len(requests)
        t.get_ok('/php/%2E%2E/etc/passwd').status_is(404)
        is_ok(len(requests), count, 'no request to the application')

    # The one script for a path that names no script of the directory, as the one entry of an application
    with Pyjo.App.FastCGI.new(url=url, document_root='/var/www', script='index.php') as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/php'))
        for path, script, name, info in (
            ('/php/', '/var/www/index.php', '/php/index.php', ''),
            ('/php/2026/10/hello-world/', '/var/www/index.php', '/php/index.php', ''),
            ('/php/wp-admin/edit.php', '/var/www/wp-admin/edit.php', '/php/wp-admin/edit.php', ''),
            ('/php/xmlrpc.php/x', '/var/www/xmlrpc.php', '/php/xmlrpc.php', '/x'),
        ):
            t.get_ok(path).status_is(200)
            env = params(requests[-1])
            is_ok(env['SCRIPT_FILENAME'], script, f'right script file of {path}')
            is_ok(env['SCRIPT_NAME'], name, f'right script name of {path}')
            is_ok(env['PATH_INFO'], info, f'right path of {path}')
        is_ok(params(requests[-3])['REQUEST_URI'], '/php/2026/10/hello-world/', 'right request URI')

    # The one script for every path, without a directory
    with Pyjo.App.FastCGI.new(url=url, script='/srv/app.php') as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/php'))
        t.get_ok('/php/foo/bar').status_is(200)
        env = params(requests[-1])
        is_ok(env['SCRIPT_FILENAME'], '/srv/app.php', 'right script file')
        is_ok(env['SCRIPT_NAME'], '/php', 'right script name')
        is_ok(env['PATH_INFO'], '/foo/bar', 'right path')

    # The directory and the script of the query of the location, which the attributes take the place of
    with Pyjo.App.FastCGI.new(url=f'{url}?document_root=%2Fsrv%2Fwww&script=front.php') as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/php'))
        t.get_ok('/php/foo').status_is(200)
        is_ok(params(requests[-1])['SCRIPT_FILENAME'], '/srv/www/front.php', 'script of the query')
        fcgi.script = 'index.php'
        t.get_ok('/php/foo').status_is(200)
        is_ok(params(requests[-1])['SCRIPT_FILENAME'], '/srv/www/index.php', 'script of the attribute')

    # Other extensions of the scripts, the first one of the index of a directory
    with Pyjo.App.FastCGI.new(url=url, document_root='/var/www', script_extensions=['.phtml', '.php']) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/php'))
        for path, script, info in (
            ('/php/', '/var/www/index.phtml', ''),
            ('/php/page.phtml/x', '/var/www/page.phtml', '/x'),
            ('/php/info.php', '/var/www/info.php', ''),
        ):
            t.get_ok(path).status_is(200)
            env = params(requests[-1])
            is_ok(env['SCRIPT_FILENAME'], script, f'right script file of {path}')
            is_ok(env['PATH_INFO'], info, f'right path of {path}')
    with Pyjo.App.FastCGI.new(
        url=f'{url}?document_root=%2Fvar%2Fwww&script_extensions=.cgi&script_extensions=.fcgi'
    ) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/php'))
        t.get_ok('/php/app.fcgi/x').status_is(200)
        is_ok(params(requests[-1])['SCRIPT_FILENAME'], '/var/www/app.fcgi', 'extensions of the query')
        t.get_ok('/php/').status_is(200)
        is_ok(params(requests[-1])['SCRIPT_FILENAME'], '/var/www/index.cgi', 'index of the query')
        fcgi.script_extensions = ['.php']
        t.get_ok('/php/').status_is(200)
        is_ok(params(requests[-1])['SCRIPT_FILENAME'], '/var/www/index.php', 'extensions of the attribute')

    # The script of the parameters of the application takes its place
    with Pyjo.App.FastCGI.new(url=url, document_root='/var/www', env={'SCRIPT_FILENAME': '/srv/app.php'}) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/php'))
        t.get_ok('/php/foo/bar').status_is(200)
        env = params(requests[-1])
        is_ok(env['SCRIPT_FILENAME'], '/srv/app.php', 'script of the parameters')
        is_ok(env['SCRIPT_NAME'], '/php', 'script name of the mount')
        is_ok(env['PATH_INFO'], '/foo/bar', 'path after the mount')
    Pyjo.IOLoop.remove(id)

with subtest('Static files'):
    tmp = Pyjo.File.tempdir()
    root = tmp.child('www').make_path()
    root.child('style.css').spew(b'body { color: red }')
    root.child('sub').make_path().child('app.js').spew(b'alert(1)')
    root.child('index.php').spew(b'<?php')
    tmp.child('secret.txt').spew(b'secret')
    links = hasattr(os, 'symlink') and sys.platform != 'win32'
    if links:
        os.symlink(tmp.child('secret.txt').to_str(), root.child('link.txt').to_str())

    url, requests, id = responder(stdout(b'Status: 200\r\n\r\nfrom the application') + end())
    with Pyjo.App.FastCGI.new(url=url, document_root=root.to_str(), script='index.php', static=True) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/blog'))
        count = len(requests)
        t.get_ok('/blog/style.css').status_is(200).content_type_is('text/css').content_is('body { color: red }')
        t.get_ok('/blog/sub/app.js').status_is(200).content_is('alert(1)')
        t.get_ok('/blog/style.css', {'Range': 'bytes=0-3'}).status_is(206).content_is('body')
        is_ok(len(requests), count, 'no request to the application')

        # The application for the paths of no file, of a script, or of a link out of the directory
        t.get_ok('/blog/missing.css').status_is(200).content_is('from the application')
        is_ok(params(requests[-1])['SCRIPT_FILENAME'], f'{root.to_str()}/index.php', 'the one script')
        t.get_ok('/blog/index.php').status_is(200).content_is('from the application')
        t.get_ok('/blog/sub/').status_is(200).content_is('from the application')
        if links:
            t.get_ok('/blog/link.txt').status_is(200).content_is('from the application')
        else:
            skip('no symbolic links', 3)

    # The flag of the query of the location, and no static files without it
    with Pyjo.App.FastCGI.new(url=f'{url}?static=1', document_root=root.to_str()) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/blog'))
        t.get_ok('/blog/style.css').status_is(200).content_is('body { color: red }')
    with Pyjo.App.FastCGI.new(url=url, document_root=root.to_str()) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/blog'))
        t.get_ok('/blog/style.css').status_is(200).content_is('from the application')
    Pyjo.IOLoop.remove(id)

with subtest('Scripts in the static files'):
    # The static files of the application that mounts it are served before the route of the mount, with the source of
    # the scripts, when they are on the same file system
    project = Pyjo.File.tempdir()
    public = project.child('public').make_path()

    def start(fcgi):
        app = Pyjoyment.new()
        app.log.level = 'fatal'
        app.static.paths = [public.to_str()]
        app.plugin('Mount', {'/': fcgi})
        return Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], silent=True).start()

    error = re.compile(r'^Scripts of Pyjo\.App\.FastCGI in \S+ are in the static files of \S+public, which would serve')
    location = 'fcgi://127.0.0.1:9000'
    throws_ok(lambda: start(f'{location}?document_root={url_escape(public.to_str())}'), error, 'document root')
    script = url_escape(public.child('index.php').to_str())
    throws_ok(lambda: start(f'{location}?script={script}'), error, 'one script')
    throws_ok(lambda: start(Pyjo.App.FastCGI.new(url=location, document_root=public.to_str())), error, 'attribute')

    # Another directory, one of the file system of the application, and the static files on purpose
    www = url_escape(project.child('www').make_path().to_str())
    for fcgi in (
        f'{location}?document_root={www}',
        f'{location}?document_root=%2Fvar%2Fwww&script=index.php',
        f'{location}?document_root={url_escape(public.to_str())}&public_source=1',
        Pyjo.App.FastCGI.new(url=location, document_root=public.to_str(), public_source=True),
    ):
        with start(fcgi) as server:
            ok(server.ports(), 'started')

with subtest('X-Sendfile'):
    tmp = Pyjo.File.tempdir()
    root = tmp.child('www').make_path()
    root.child('style.css').spew(b'body { color: red }')
    private = tmp.child('private').make_path()
    private.child('file.bin').spew(b'0123456789')

    def sendfile(path):
        headers = (
            b'Status: 200\r\nContent-Type: application/octet-stream\r\n'
            b'Content-Disposition: attachment; filename="file.bin"\r\nX-Sendfile: ' + path.encode() + b'\r\n\r\n'
        )
        return responder(stdout(headers) + end())

    # A private file of the directory of sendfile, with the status and the headers of the application
    url, requests, id = sendfile(private.child('file.bin').to_str())
    with Pyjo.App.FastCGI.new(url=url, sendfile=private.to_str()) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
        t.get_ok('/dl/file').status_is(200).content_is('0123456789')
        t.content_type_is('application/octet-stream').header_is(
            'Content-Disposition', 'attachment; filename="file.bin"'
        )
        ok(not t.tx.res.headers.header('X-Sendfile'), 'no header X-Sendfile')
        t.get_ok('/dl/file', {'Range': 'bytes=2-4'}).status_is(206).content_is('234')
    Pyjo.IOLoop.remove(id)

    # A path relative to the directory of sendfile
    url, requests, id = sendfile('file.bin')
    with Pyjo.App.FastCGI.new(url=f'{url}?sendfile={private.to_str()}') as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
        t.get_ok('/dl/file').status_is(200).content_is('0123456789')
    Pyjo.IOLoop.remove(id)

    # Several directories, of the attribute and of the query
    for path in (root.child('style.css').to_str(), private.child('file.bin').to_str()):
        url, requests, id = sendfile(path)
        with Pyjo.App.FastCGI.new(url=url, sendfile=[root.to_str(), private.to_str()]) as fcgi:
            t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
            t.get_ok('/dl/file').status_is(200).content_like(r'^(body|0123)')
        with Pyjo.App.FastCGI.new(url=f'{url}?sendfile={root.to_str()}&sendfile={private.to_str()}') as fcgi:
            t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
            t.get_ok('/dl/file').status_is(200).content_like(r'^(body|0123)')
        Pyjo.IOLoop.remove(id)

    # A regular expression of the whole path of the file, once its symbolic links are resolved
    real = re.escape(os.path.realpath(private.to_str()) + os.sep)
    url, requests, id = sendfile(private.child('file.bin').to_str())
    with Pyjo.App.FastCGI.new(url=url, sendfile=re.compile(real + r'[^/\\]+\.bin')) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
        t.get_ok('/dl/file').status_is(200).content_is('0123456789')
    with Pyjo.App.FastCGI.new(url=url, sendfile=[root.to_str(), re.compile(real + r'[^/\\]+\.txt')]) as fcgi:
        fcgi.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
        with fcgi.log.capture('error') as messages:
            t.get_ok('/dl/file').status_is(404)
        like_ok(
            str(messages),
            r'FastCGI application sent the file ".*file\.bin", which sendfile does not allow',
            'right error',
        )
    Pyjo.IOLoop.remove(id)
    url, requests, id = sendfile('file.bin')
    with Pyjo.App.FastCGI.new(url=url, sendfile=re.compile(r'.*')) as fcgi:
        fcgi.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
        t.get_ok('/dl/file').status_is(404)
    Pyjo.IOLoop.remove(id)

    # Not the files of the document root with static, as the directories of sendfile are the only ones
    url, requests, id = sendfile(root.child('style.css').to_str())
    with Pyjo.App.FastCGI.new(url=url, document_root=root.to_str(), static=True) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
        t.get_ok('/dl/file.php').status_is(200).content_is('').header_like('X-Sendfile', r'style\.css$')
    Pyjo.IOLoop.remove(id)
    url, requests, id = sendfile(private.child('file.bin').to_str())

    # The header as the application sends it without the directories
    with Pyjo.App.FastCGI.new(url=url) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi, '/dl'))
        t.get_ok('/dl/file').status_is(200).content_is('').header_like('X-Sendfile', r'file\.bin$')
    Pyjo.IOLoop.remove(id)

with subtest('Response'):
    with Pyjo.App.FastCGI.new(url=URL) as fcgi:
        t = Pyjo.Test.Pyjo.new(application(fcgi))
        t.get_ok('/prefix/later').status_is(200).content_is('Hello later at /prefix!')
        is_ok(t.tx.res.headers.content_length, '23', 'whole response with its length')
        is_deeply_ok(raw(t, 'GET', '/prefix/chunks'), (200, None, 'chunked', b'012'), 'chunked response')
        is_deeply_ok(raw(t, 'GET', '/prefix/length'), (200, '6', None, b'onetwo'), 'response with its length')
        is_deeply_ok(raw(t, 'HEAD', '/prefix/later'), (200, '23', None, b''), 'response without content')
        t.get_ok('/prefix/redirect').status_is(302).header_is('Location', '/prefix/later')
        t.get_ok('/prefix/missing').status_is(404)

        # Without the chunked transfer encoding in HTTP/1.0
        tx = t.ua.build_tx('GET', '/prefix/chunks')
        tx.req.version = '1.0'
        t.request_ok(tx).status_is(200).content_is('012')
        is_ok(t.tx.keep_alive, False, 'no keep-alive')

with subtest('Response of CGI'):
    # The status in its header, the headers in records of their own, and lines that end with LF
    url, requests, id = responder(stdout(b'Status: 201 Made\nX-Foo: a\n', b'X-Foo: b\n\nHel', b'lo!') + end())
    with Pyjo.App.FastCGI.new(url=url) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(201).content_is('Hello!')
        is_ok(t.tx.res.message, 'Made', 'right message')
        is_deeply_ok(t.tx.res.headers.every_header('X-Foo'), ['a', 'b'], 'right headers')
    Pyjo.IOLoop.remove(id)

    # A redirect for Location without a status
    url, requests, id = responder(stdout(b'Location: http://example.com/\r\n\r\n') + end())
    with Pyjo.App.FastCGI.new(url=url) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(302).header_is('Location', 'http://example.com/')
    Pyjo.IOLoop.remove(id)

    # The standard error of the application is logged
    url, requests, id = responder(_record(7, 1, b'Something to say\n') + stdout(b'Status: 200\r\n\r\nOK') + end())
    with Pyjo.App.FastCGI.new(url=url) as app:
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('warn') as messages:
            t.get_ok('/').status_is(200).content_is('OK')
        like_ok(str(messages), r'FastCGI application: Something to say', 'standard error logged')
    Pyjo.IOLoop.remove(id)

    # The records of a request
    record = requests[0]
    is_ok(record[:16], _record(1, 1, struct.pack('>HB5x', 1, 0)), 'request of a responder, closed after it')

with subtest('Errors'):
    # Refused, by a privileged port, which no test that runs at the same time takes, as it could take the port of a
    # socket that is closed before the connection, and a socket bound without listening refuses nothing on macOS, where
    # the connection times out
    with Pyjo.App.FastCGI.new(url='fcgi://127.0.0.1:1') as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(502).content_is('Bad Gateway')
        like_ok(str(messages), r'FastCGI connection failed', 'right error')

    # Closed before the response
    url, requests, id = responder(b'')
    with Pyjo.App.FastCGI.new(url=url) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'FastCGI connection closed before the end of the response', 'right error')
    Pyjo.IOLoop.remove(id)

    # Ended without a response
    url, requests, id = responder(end())
    with Pyjo.App.FastCGI.new(url=url) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'FastCGI application ended without a response', 'right error')
    Pyjo.IOLoop.remove(id)

    # Closed after the start of the response, which closes the connection of the client
    url, requests, id = responder(_record(STDOUT, 1, b'Status: 200\r\n\r\none'))
    with Pyjo.App.FastCGI.new(url=url) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            is_deeply_ok(raw(t, 'GET'), (200, None, 'chunked', ('incomplete', b'one')), 'incomplete response')
        like_ok(str(messages), r'FastCGI connection closed before the end of the response', 'right error')
    Pyjo.IOLoop.remove(id)

    # Inactive
    url, requests, id = responder(None)
    with Pyjo.App.FastCGI.new(url=url, inactivity_timeout=0.2) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'FastCGI connection inactive', 'right error')
    Pyjo.IOLoop.remove(id)

    throws_ok(
        lambda: Pyjo.App.FastCGI.new().handler(Pyjo.Transaction.HTTP.new()),
        re.compile(r'^No FastCGI application'),
        'no application',
    )
    throws_ok(
        lambda: Pyjo.App.FastCGI.new(url='http://127.0.0.1:9000').handler(Pyjo.Transaction.HTTP.new()),
        re.compile(r'^Invalid FastCGI location "http://127\.0\.0\.1:9000"'),
        'invalid location',
    )

with subtest('Connections kept'):
    # Used again, by the requests that ask the application to keep them
    connections = []
    url, requests, id = responder(stdout(b'Status: 200\r\n\r\nkept') + end(), close=False, connections=connections)
    with Pyjo.App.FastCGI.new(url=url, max_connections=1) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('kept')
        t.get_ok('/').status_is(200).content_is('kept')
        t.get_ok('/').status_is(200).content_is('kept')
        is_ok(len(requests), 3, 'three requests')
        is_ok(len(connections), 1, 'one connection')
        is_ok(requests[0][:16], _record(1, 1, struct.pack('>HB5x', 1, 1)), 'request that keeps the connection')

        # A connection of its own for the child of a fork, which leaves the ones of its parent
        if not hasattr(os, 'fork'):
            skip('no fork', 3)
        else:
            pid = os.fork()
            if pid == 0:
                code = 1
                try:
                    Pyjo.IOLoop.remove(id)
                    tx = t.ua.get('/')
                    code = 0 if tx.res.code == 200 and tx.res.body == b'kept' else 1
                finally:
                    sys.stdout.flush()
                    os._exit(code)
            status = []

            def reap(loop):
                if (waited := os.waitpid(pid, os.WNOHANG))[0]:
                    status.append(os.waitstatus_to_exitcode(waited[1]))
                    loop.stop()

            reaper = Pyjo.IOLoop.recurring(0.01, reap)
            deadline = Pyjo.IOLoop.timer(10, lambda loop: loop.stop())
            Pyjo.IOLoop.start()
            Pyjo.IOLoop.remove(reaper)
            Pyjo.IOLoop.remove(deadline)
            is_deeply_ok(status, [0], 'response in the child')
            is_ok(len(connections), 2, 'a connection of the child')
            t.get_ok('/').status_is(200).content_is('kept')
            is_ok(len(connections), 2, 'the connection of the parent used again')
    Pyjo.IOLoop.remove(id)

    # Kept after the end of the request that comes after the whole response, of its length, has been written, unless
    # more of the response comes
    head = stdout(b'Status: 200\r\nContent-Length: 4\r\n\r\nlate')[: -len(_record(STDOUT, 1))]

    def late(tail, connections):
        def accept(loop, stream, id):
            connections.append(id)
            buffer = bytearray()

            def read(stream, chunk):
                buffer.extend(chunk)
                if _record(STDIN, 1) in buffer:
                    buffer.clear()
                    stream.write(head)
                    Pyjo.IOLoop.timer(0.1, lambda loop: stream.write(tail))

            stream.on('read', read)

        return Pyjo.IOLoop.server(accept, address='127.0.0.1')

    for tail, kept, name in (
        (_record(STDOUT, 1) + end(), 1, 'kept after the end of the request'),
        (_record(STDOUT, 1, b'more') + _record(STDOUT, 1) + end(), 0, 'closed after more of the response'),
    ):
        connections = []
        id = late(tail, connections)
        with Pyjo.App.FastCGI.new(url=f'fcgi://127.0.0.1:{Pyjo.IOLoop.acceptor(id).port}', max_connections=1) as app:
            t = Pyjo.Test.Pyjo.new(app)
            t.get_ok('/').status_is(200).content_is('late')
            Pyjo.IOLoop.timer(0.3, lambda loop: loop.stop())
            Pyjo.IOLoop.start()
            is_ok(len(app._queues[Pyjo.IOLoop.singleton]), kept, name)
            t.get_ok('/').status_is(200).content_is('late')
            is_ok(len(connections), 2 - kept, 'connections')
        Pyjo.IOLoop.remove(id)

    # Not kept, by default
    connections = []
    url, requests, id = responder(stdout(b'Status: 200\r\n\r\nkept') + end(), close=False, connections=connections)
    with Pyjo.App.FastCGI.new(url=url) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('kept')
        t.get_ok('/').status_is(200).content_is('kept')
        is_ok(len(connections), 2, 'a connection for each request')
        is_ok(requests[0][:16], _record(1, 1, struct.pack('>HB5x', 1, 0)), 'request that closes the connection')
    Pyjo.IOLoop.remove(id)

    # Closed by the application, which does not keep it, with the query of the location
    connections = []
    url, requests, id = responder(stdout(b'Status: 200\r\n\r\nclosed') + end(), connections=connections)
    with Pyjo.App.FastCGI.new(url=f'{url}?max_connections=4') as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('closed')
        t.get_ok('/').status_is(200).content_is('closed')
        is_ok(len(connections), 2, 'a new connection')
    Pyjo.IOLoop.remove(id)

    # Closed by its inactivity timeout
    connections = []
    url, requests, id = responder(stdout(b'Status: 200\r\n\r\nkept') + end(), close=False, connections=connections)
    with Pyjo.App.FastCGI.new(url=url, max_connections=1, inactivity_timeout=0.1) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('kept')
        Pyjo.IOLoop.timer(0.3, lambda loop: loop.stop())
        Pyjo.IOLoop.start()
        t.get_ok('/').status_is(200).content_is('kept')
        is_ok(len(connections), 2, 'a new connection')
    Pyjo.IOLoop.remove(id)

    # Closed by the application when it gets the request again, which goes to a new one
    connections = []
    reply = stdout(b'Status: 200\r\n\r\nagain') + end()

    def accept(loop, stream, id):
        connections.append(id)
        buffer = bytearray()
        count = []

        def read(stream, chunk):
            buffer.extend(chunk)
            if _record(STDIN, 1) in buffer:
                buffer.clear()
                count.append(1)
                stream.write(reply) if len(count) == 1 else stream.close()

        stream.on('read', read)

    id = Pyjo.IOLoop.server(accept, address='127.0.0.1')
    with Pyjo.App.FastCGI.new(url=f'fcgi://127.0.0.1:{Pyjo.IOLoop.acceptor(id).port}', max_connections=1) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('again')
        t.get_ok('/').status_is(200).content_is('again')
        is_ok(len(connections), 2, 'the request again on a new connection')
    Pyjo.IOLoop.remove(id)

with subtest('Timeouts'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    server = Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], silent=True, inactivity_timeout=0.2).start()
    base = f'http://127.0.0.1:{server.ports()[0]}'
    ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)

    # The connection of the client waits for a response that takes longer than the inactivity timeout of the server
    url, requests, id = responder(stdout(b'Status: 200\r\n\r\nslow') + end(), delay=0.5)
    app.plugin('Mount', {'/slow': Pyjo.App.FastCGI.new(url=url, inactivity_timeout=3)})
    tx = result(ua.get_p(f'{base}/slow'))
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'slow', 'right content')
    Pyjo.IOLoop.remove(id)

    # The inactivity timeout of the query of the location gives 502
    url, requests, id = responder(None)
    app.plugin('Mount', {'/quiet': f'{url}?inactivity_timeout=0.2'})
    tx = result(ua.get_p(f'{base}/quiet'))
    is_ok(tx.res.code, 502, 'inactive application')
    Pyjo.IOLoop.remove(id)

    # The inactivity timeout of the server again, once the response has started
    url, requests, id = responder(_record(STDOUT, 1, b'Status: 200\r\n\r\none'), close=False)
    app.plugin('Mount', {'/stalled': Pyjo.App.FastCGI.new(url=url, inactivity_timeout=3)})
    start = time.monotonic()
    is_deeply_ok(
        raw(Pyjo.URL.new(base), 'GET', '/stalled'),
        (200, None, 'chunked', ('incomplete', b'one')),
        'incomplete response',
    )
    ok(time.monotonic() - start < 2, 'closed by the inactivity timeout of the server')
    Pyjo.IOLoop.remove(id)

    ua.close()
    server.close()

    # The attributes, the query of the location, and the defaults
    options, query = Pyjo.App.FastCGI._location('fcgi://127.0.0.1:9000?connect_timeout=5&inactivity_timeout=300')
    is_deeply_ok(options, {'address': '127.0.0.1', 'port': 9000}, 'right options')
    is_deeply_ok(query, {'connect_timeout': '5', 'inactivity_timeout': '300'}, 'right query')
    is_ok(Pyjo.App.FastCGI._seconds(None, '5', 10), 5.0, 'timeout of the query')
    is_ok(Pyjo.App.FastCGI._seconds(2, '5', 10), 2, 'timeout of the attribute')
    is_ok(Pyjo.App.FastCGI._seconds(None, None, 10), 10, 'default timeout')
    options, query = Pyjo.App.FastCGI._location('fcgi://127.0.0.1:9000?max_connections=4')
    is_deeply_ok(query, {'max_connections': '4'}, 'number of the query')
    is_ok(Pyjo.App.FastCGI._number(None, '4'), 4, 'number of the query')
    is_ok(Pyjo.App.FastCGI._number(2, '4'), 2, 'number of the attribute')
    is_ok(Pyjo.App.FastCGI._number(None, None), 0, 'no connections kept')
    throws_ok(
        lambda: Pyjo.App.FastCGI.new(url='fcgi://127.0.0.1:9000?max_connections=many').handler(
            Pyjo.Transaction.HTTP.new()
        ),
        re.compile(r'^Invalid FastCGI number "many"'),
        'invalid number',
    )
    throws_ok(
        lambda: Pyjo.App.FastCGI.new(url='fcgi://127.0.0.1:9000?connect_timeout=soon').handler(
            Pyjo.Transaction.HTTP.new()
        ),
        re.compile(r'^Invalid FastCGI timeout "soon"'),
        'invalid timeout',
    )

with subtest('Connection of the client closed'):
    # The connection to the application is closed with the one of the client
    url, requests, id = responder(_record(STDOUT, 1, b'Status: 200\r\n\r\n' + b'x' * 20000), close=False)
    with Pyjo.App.FastCGI.new(url=url) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.ua.max_response_size = 10000
        tx = t.ua.get('/')
        is_ok(tx.error['message'], 'Maximum message size exceeded', 'right error')
    Pyjo.IOLoop.remove(id)

with subtest('UNIX domain socket'):
    if not hasattr(socket, 'AF_UNIX') or sys.platform == 'win32':
        skip('UNIX domain sockets not supported', 2)
    else:
        tmp = Pyjo.File.tempdir()
        path = tmp.child('fcgi.sock').to_str()
        unix = Pyjo.Server.Daemon.new(
            app=inner, listen=[f'fcgi+unix://{url_escape(path, rb"^A-Za-z0-9\-._~")}'], silent=True
        ).start()
        with Pyjo.App.FastCGI.new(url=f'fcgi+unix://{url_escape(path, rb"^A-Za-z0-9\-._~")}') as fcgi:
            t = Pyjo.Test.Pyjo.new(application(fcgi))
            t.get_ok('/prefix/later').status_is(200).content_is('Hello later at /prefix!')
            t.get_ok('/prefix/chunks').status_is(200).content_is('012')
        unix.close()

daemon.close()

done_testing()
