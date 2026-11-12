import Pyjo.App.WSGI
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Server.CGI
import Pyjo.Server.Daemon
import Pyjo.Server.Prefork
import Pyjo.Server.Prethread
import Pyjo.Server.WSGI
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.JSON import decode_json, encode_json
from Pyjo.Test import *

import asyncio
import concurrent.futures
import contextvars
import http.client
import os
import re
import sys
import threading
import time
import wsgiref.util

from wsgiref.validate import validator


# The environment of the request without the objects of WSGI, and the body that the application reads
@validator
def echo(environ, start_response):
    body = environ['wsgi.input'].read(int(environ.get('CONTENT_LENGTH') or 0))
    values = {k: v for k, v in environ.items() if not k.startswith('wsgi.') or k == 'wsgi.url_scheme'}
    start_response('200 OK', [('Content-Type', 'application/json')])
    return [encode_json({**values, 'body': body.decode('latin-1')})]


# The value of a promise, which the event loop fulfills
def result(promise):
    values = []
    promise.then(lambda *args: values.extend(args)).wait()
    return values[0] if len(values) == 1 else values


# The event loop runs while a thread waits for the event
def wait(event):
    with concurrent.futures.ThreadPoolExecutor(1) as executor:
        return result(Pyjo.Promise.new(executor.submit(event.wait, 5)))


# The response as it is on the wire, as the user agent removes the chunked transfer encoding
def raw(t, method, path='/'):
    url = t.ua.server.url()

    def request():
        connection = http.client.HTTPConnection(url.host, url.port, timeout=5)
        try:
            connection.request(method, path)
            res = connection.getresponse()
            try:
                body = res.read()
            except http.client.IncompleteRead:
                body = None
            return res.status, res.getheader('Content-Length'), res.getheader('Transfer-Encoding'), body
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(1) as executor:
        return result(Pyjo.Promise.new(executor.submit(request)))


def application(wsgi, prefix='/prefix'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    route = app.routes.any(prefix)
    route.partial = True
    route.to(app=wsgi)
    return app


with subtest('Environment'):
    with Pyjo.App.WSGI.new(app=echo) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/foo/bar?a=1&b=%20', {'X-Foo': 'bar'}).status_is(200)
        env = t.tx.res.json()
        is_ok(env['REQUEST_METHOD'], 'GET', 'right method')
        is_ok(env['SCRIPT_NAME'], '', 'no script name')
        is_ok(env['PATH_INFO'], '/foo/bar', 'right path')
        is_ok(env['QUERY_STRING'], 'a=1&b=%20', 'right query')
        is_ok(env['SERVER_NAME'], '127.0.0.1', 'right server name')
        is_ok(env['SERVER_PORT'], str(t.ua.server.url().port), 'right server port')
        is_ok(env['SERVER_PROTOCOL'], 'HTTP/1.1', 'right protocol')
        is_ok(env['REMOTE_ADDR'], '127.0.0.1', 'right remote address')
        ok(env['REMOTE_PORT'].isdigit(), 'remote port')
        is_ok(env['HTTP_X_FOO'], 'bar', 'right header')
        is_ok(env['wsgi.url_scheme'], 'http', 'right scheme')
        ok('CONTENT_LENGTH' not in env, 'no content length')
        is_ok(env['body'], '', 'no body')


# The flags of WSGI for the server that runs the application
def flags(environ, start_response):
    start_response('200 OK', [('Content-Type', 'application/json')])
    return [encode_json([environ['wsgi.multithread'], environ['wsgi.multiprocess'], environ['wsgi.run_once']])]


def model(app, path='/'):
    tx = Pyjo.Transaction.HTTP.new()
    tx.req.method = 'GET'
    tx.req.url.parse(path)
    app.handler(tx)
    return tx.res.json()


with subtest('Server'):
    with Pyjo.App.WSGI.new(app=flags) as app:
        is_deeply_ok(model(app), [False, False, False], 'no server')
        daemon = Pyjo.Server.Daemon.new()
        app.server(daemon)
        is_deeply_ok(model(app), [False, False, False], 'daemon')
        prefork = Pyjo.Server.Prefork.new(workers=2)
        app.server(prefork)
        is_deeply_ok(model(app), [False, True, False], 'prefork')
        prefork.workers = 1
        is_deeply_ok(model(app), [False, False, False], 'prefork with one worker')
        prethread = Pyjo.Server.Prethread.new(workers=2)
        app.server(prethread)
        is_deeply_ok(model(app), [True, False, False], 'prethread')
        cgi = Pyjo.Server.CGI.new()
        app.server(cgi)
        is_deeply_ok(model(app), [False, True, True], 'CGI')

    # The server of the application that mounts it
    with Pyjo.App.WSGI.new(app=flags) as wsgi:
        app = Pyjoyment.new()
        app.log.level = 'fatal'
        app.plugin('Mount', {'/flags': wsgi})
        prefork = Pyjo.Server.Prefork.new(workers=4)
        app.server(prefork)
        is_deeply_ok(model(app, '/flags'), [False, True, False], 'prefork of the application that mounts it')

    # The flags of the WSGI server, which Pyjo.Server.WSGI keeps in the environment of the request
    with Pyjo.App.WSGI.new(app=flags) as wsgi:
        env = {'PATH_INFO': '/prefix', 'wsgi.multithread': True, 'wsgi.multiprocess': True, 'wsgi.run_once': False}
        wsgiref.util.setup_testing_defaults(env)
        body = Pyjo.Server.WSGI.new(app=application(wsgi)).to_wsgi_app()(env, lambda *args: None)
        try:
            is_deeply_ok(decode_json(b''.join(body)), [True, True, False], 'flags of the WSGI server')
        finally:
            body.close()

with subtest('Headers joined'):
    with Pyjo.App.WSGI.new(app=echo) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/', {'X-Foo': ['a', 'b'], 'Cookie': ['c=1', 'd=2']}).status_is(200)
        is_ok(t.tx.res.json('/HTTP_X_FOO'), 'a, b', 'joined with commas')
        is_ok(t.tx.res.json('/HTTP_COOKIE'), 'c=1; d=2', 'joined with semicolons')

with subtest('Body'):
    with Pyjo.App.WSGI.new(app=echo) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.post_ok('/', {'Content-Type': 'text/plain'}, b'Hello!').status_is(200)
        is_ok(t.tx.res.json('/CONTENT_TYPE'), 'text/plain', 'right content type')
        is_ok(t.tx.res.json('/CONTENT_LENGTH'), '6', 'right content length')
        is_ok(t.tx.res.json('/body'), 'Hello!', 'right body')

        # Chunked
        tx = t.ua.build_tx('POST', '/')
        tx.req.content.write_chunk(b'Hello').write_chunk(b' World!').write_chunk(b'')
        t.request_ok(tx).status_is(200)
        is_ok(t.tx.res.json('/CONTENT_LENGTH'), '12', 'right content length')
        ok('HTTP_TRANSFER_ENCODING' not in t.tx.res.json(), 'no transfer encoding')
        is_ok(t.tx.res.json('/body'), 'Hello World!', 'right body')

        # Multipart
        t.post_ok('/', form={'foo': 'bar', 'file': {'content': 'Hello!', 'filename': 'hello.txt'}}).status_is(200)
        env = t.tx.res.json()
        like_ok(env['CONTENT_TYPE'], r'^multipart/form-data; boundary=', 'right content type')
        is_ok(env['CONTENT_LENGTH'], str(len(env['body'])), 'right content length')
        like_ok(env['body'], r'(?s)name=\"file\"; filename=\"hello\.txt\".*Hello!', 'right file')
        like_ok(env['body'], r'(?s)name=\"foo\".*bar', 'right field')

with subtest('Body in a file'):
    max_memory_size = os.environ.get('PYJO_MAX_MEMORY_SIZE')
    os.environ['PYJO_MAX_MEMORY_SIZE'] = '10'
    try:
        with Pyjo.App.WSGI.new(app=echo) as app:
            t = Pyjo.Test.Pyjo.new(app)
            body = b'0123456789' * 100000
            t.post_ok('/', body).status_is(200)
            is_ok(t.tx.res.json('/CONTENT_LENGTH'), '1000000', 'right content length')
            ok(t.tx.res.json('/body') == body.decode(), 'right body')
    finally:
        if max_memory_size is None:
            del os.environ['PYJO_MAX_MEMORY_SIZE']
        else:
            os.environ['PYJO_MAX_MEMORY_SIZE'] = max_memory_size

with subtest('Path of a route'):
    with Pyjo.App.WSGI.new(app=echo) as wsgi:
        t = Pyjo.Test.Pyjo.new(application(wsgi))
        t.get_ok('/prefix').status_is(200)
        is_ok(t.tx.res.json('/SCRIPT_NAME'), '/prefix', 'right script name')
        is_ok(t.tx.res.json('/PATH_INFO'), '', 'no path')
        t.get_ok('/prefix/').status_is(200)
        is_ok(t.tx.res.json('/SCRIPT_NAME'), '/prefix', 'right script name')
        is_ok(t.tx.res.json('/PATH_INFO'), '/', 'right path')
        t.get_ok('/prefix/foo/bar/?x=1').status_is(200)
        is_ok(t.tx.res.json('/SCRIPT_NAME'), '/prefix', 'right script name')
        is_ok(t.tx.res.json('/PATH_INFO'), '/foo/bar/', 'right path')
        is_ok(t.tx.res.json('/QUERY_STRING'), 'x=1', 'right query')

        # Not after a part of the path that does not end with a slash, which cannot be SCRIPT_NAME
        t.get_ok('/prefixx').status_is(404)
        t.get_ok('/prefix.json').status_is(404)

        # The page of 404 of the application, with the assets of the root, in both modes
        for mode in ('development', 'production'):
            t.app.mode = mode
            t.get_ok('/prefixx').status_is(404).element_exists('link[href="/favicon.ico"]')
            t.element_exists_not('[src^="/prefix"], [href^="/prefix"]', f'no asset under the path of the route, {mode}')
            t.element_exists('[src^="/pyjo/"]', f'assets of the root, {mode}')
        t.app.mode = 'development'

        # Escaped, as the bytes of the path
        t.get_ok('/prefix/a%20b/%E2%99%A5/%2F').status_is(200)
        is_ok(t.tx.res.json('/SCRIPT_NAME'), '/prefix', 'right script name')
        is_ok(t.tx.res.json('/PATH_INFO'), '/a b/\xe2\x99\xa5//', 'right path')

    # Placeholders
    with Pyjo.App.WSGI.new(app=echo) as wsgi:
        t = Pyjo.Test.Pyjo.new(application(wsgi, '/users/:id'))
        t.get_ok('/users/%E2%99%A5/foo').status_is(200)
        is_ok(t.tx.res.json('/SCRIPT_NAME'), '/users/\xe2\x99\xa5', 'right script name')
        is_ok(t.tx.res.json('/PATH_INFO'), '/foo', 'right path')

    # A route that is not partial gives the whole path
    with Pyjo.App.WSGI.new(app=echo) as wsgi:
        app = Pyjoyment.new()
        app.log.level = 'fatal'
        app.routes.get('/whole').to(app=wsgi)
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/whole').status_is(200)
        is_ok(t.tx.res.json('/SCRIPT_NAME'), '', 'no script name')
        is_ok(t.tx.res.json('/PATH_INFO'), '/whole', 'right path')

with subtest('Base path'):
    # A reverse proxy with a path prefix, which the application moves from the path to the base path
    with Pyjo.App.WSGI.new(app=echo) as wsgi:
        app = application(wsgi)

        @app.hook('before_dispatch')
        def before_dispatch(c):
            url = c.req.url
            url.base.path.parse('/outer/')
            url.path.leading_slash = False
            url.path.parts.pop(0)

        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/outer/prefix/foo?x=1').status_is(200)
        is_ok(t.tx.res.json('/SCRIPT_NAME'), '/outer/prefix', 'right script name')
        is_ok(t.tx.res.json('/PATH_INFO'), '/foo', 'right path')
        is_ok(t.tx.res.json('/QUERY_STRING'), 'x=1', 'right query')


with subtest('Under a WSGI server'):
    # An application of Pyjoyment on a WSGI server, whose script name is the base path, waits for the response
    with Pyjo.App.WSGI.new(app=echo) as wsgi:
        env = {'SCRIPT_NAME': '/outer', 'PATH_INFO': '/prefix/foo', 'QUERY_STRING': 'x=1'}
        wsgiref.util.setup_testing_defaults(env)
        res = []
        server = Pyjo.Server.WSGI.new(app=application(wsgi))
        body = server.to_wsgi_app()(env, lambda status, headers, exc_info=None: res.extend([status, headers]))
        try:
            env = decode_json(b''.join(body))
        finally:
            body.close()
        is_ok(res[0], '200 OK', 'right status')
        is_ok(env['SCRIPT_NAME'], '/outer/prefix', 'right script name')
        is_ok(env['PATH_INFO'], '/foo', 'right path')
        is_ok(env['QUERY_STRING'], 'x=1', 'right query')


with subtest('Pyjoyment on WSGI'):
    # An application of Pyjoyment as the WSGI application, whose response and content come in later ticks of the event
    # loop, which runs already
    inner = Pyjoyment.new()
    inner.log.level = 'fatal'

    @inner.routes.get('/later')
    def later(c):
        c.render_later()
        Pyjo.IOLoop.timer(0.01, lambda loop: c.render(text='Hello later!'))

    @inner.routes.get('/chunks')
    def chunks(c):
        def write(n):
            if n < 3:
                Pyjo.IOLoop.timer(0.01, lambda loop: c.write_chunk(f'{n}'.encode(), lambda c: write(n + 1)))
            else:
                c.finish()

        write(0)

    with Pyjo.App.WSGI.new(app=Pyjo.Server.WSGI.new(app=inner).to_wsgi_app()) as wsgi:
        t = Pyjo.Test.Pyjo.new(application(wsgi))
        t.get_ok('/prefix/later').status_is(200).content_is('Hello later!')
        is_ok(t.tx.res.headers.content_length, '12', 'right "Content-Length" value')
        t.get_ok('/prefix/chunks').status_is(200).content_is('012')
        t.get_ok('/prefix/missing').status_is(404)


# An iterator that sets a context variable at its start and resets it with its token at its end, as the one of
# stream_with_context of Flask, which needs one context for the call, the iteration and the close, as a WSGI server gives
variable = contextvars.ContextVar('variable')


@validator
def contextual(environ, start_response):
    def body():
        token = variable.set('set')
        try:
            yield b'one'
            yield b'two'
        finally:
            variable.reset(token)

    start_response('200 OK', [('Content-Type', 'text/plain')])
    return body()


with subtest('Context of the call'):
    with Pyjo.App.WSGI.new(app=contextual) as app:
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as logs:
            t.get_ok('/').status_is(200).content_is('onetwo')
        ok(not t.tx.error, 'whole response')
        is_deeply_ok(list(logs), [], 'no error of the application')


# A list, without the validator, whose iterator would hide it
def whole(environ, start_response):
    start_response('201 Created', [('Content-Type', 'text/plain'), ('X-Foo', 'a'), ('X-Foo', 'b')])
    return [b'Hello', b' ', b'World!']


@validator
def stream(environ, start_response):
    # start_response once the body is iterated, and an empty chunk before the first one
    def body():
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield b''
        yield b'one'
        yield b'two'
        yield b'three'

    return body()


@validator
def length(environ, start_response):
    def body():
        yield b'one'
        yield b'two'

    start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', '6')])
    return body()


def written(environ, start_response):
    write = start_response('200 OK', [('Content-Type', 'text/plain')])
    write(b'one')
    write(b'two')
    return iter([b'three'])


with subtest('Response'):
    with Pyjo.App.WSGI.new(app=whole) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(201).content_is('Hello World!')
        is_deeply_ok(t.tx.res.headers.every_header('X-Foo'), ['a', 'b'], 'right headers')
        is_deeply_ok(raw(t, 'GET'), (201, '12', None, b'Hello World!'), 'whole response')
        is_deeply_ok(raw(t, 'HEAD'), (201, '12', None, b''), 'whole response without content')

    with Pyjo.App.WSGI.new(app=stream) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('onetwothree')
        is_deeply_ok(raw(t, 'GET'), (200, None, 'chunked', b'onetwothree'), 'chunked response')
        is_deeply_ok(raw(t, 'HEAD'), (200, None, 'chunked', b''), 'chunked response without content')

        # Without the chunked transfer encoding in HTTP/1.0
        tx = t.ua.build_tx('GET', '/')
        tx.req.version = '1.0'
        t.request_ok(tx).status_is(200).content_is('onetwothree')
        is_ok(t.tx.keep_alive, False, 'no keep-alive')

    with Pyjo.App.WSGI.new(app=length) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('onetwo')
        is_ok(t.tx.keep_alive, True, 'keep-alive')
        is_deeply_ok(raw(t, 'GET'), (200, '6', None, b'onetwo'), 'response with its length')

    with Pyjo.App.WSGI.new(app=written) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('onetwothree')


def fail(environ, start_response):
    raise RuntimeError('Something went wrong')


def silent(environ, start_response):
    return [b'Hello!']


def twice(environ, start_response):
    start_response('200 OK', [])
    start_response('200 OK', [])
    return [b'Hello!']


def replaced(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    try:
        raise RuntimeError('Something went wrong')
    except RuntimeError:
        start_response('503 Service Unavailable', [('Content-Type', 'text/plain')], sys.exc_info())
    return [b'Try again later']


def broken(environ, start_response):
    def body():
        yield b'one'
        raise RuntimeError('Broken body')

    start_response('200 OK', [('Content-Type', 'text/plain')])
    return body()


with subtest('Errors'):
    with Pyjo.App.WSGI.new(app=fail) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(500).content_is('Internal Server Error')
        like_ok(str(messages), r'Something went wrong', 'right error')

    with Pyjo.App.WSGI.new(app=silent) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(500)
        like_ok(str(messages), r'did not call start_response', 'right error')

    with Pyjo.App.WSGI.new(app=twice) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(500)
        like_ok(str(messages), r'start_response has already been called', 'right error')

    with Pyjo.App.WSGI.new(app=replaced) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(503).content_is('Try again later')

    # The connection is closed, as the response has started
    with Pyjo.App.WSGI.new(app=broken) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            is_deeply_ok(raw(t, 'GET'), (200, None, 'chunked', None), 'incomplete response')
        like_ok(str(messages), r'Broken body', 'right error')

    # The exception page of Pyjoyment, in a route
    with Pyjo.App.WSGI.new(app=fail) as wsgi:
        t = Pyjo.Test.Pyjo.new(application(wsgi))
        t.get_ok('/prefix').status_is(500).content_like(r'Something went wrong')

    throws_ok(
        lambda: Pyjo.App.WSGI.new().handler(Pyjo.Transaction.HTTP.new()),
        re.compile(r'^No WSGI application'),
        'no application',
    )

with subtest('Connection closed'):
    closed = threading.Event()

    def endless(environ, start_response):
        def body():
            try:
                while True:
                    yield b'x' * 1024
                    time.sleep(0.01)
            finally:
                closed.set()

        start_response('200 OK', [('Content-Type', 'text/plain')])
        return body()

    with Pyjo.App.WSGI.new(app=endless) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.ua.max_response_size = 10000
        tx = t.ua.get('/')
        is_ok(tx.error['message'], 'Maximum message size exceeded', 'right error')
        ok(wait(closed), 'body closed')

with subtest('Closed body'):
    closed = threading.Event()

    class Body:
        def __iter__(self):
            yield b'Hello!'

        def close(self):
            closed.set()

    def closing(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return Body()

    with Pyjo.App.WSGI.new(app=closing) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('Hello!')
        ok(wait(closed), 'body closed')

# A synchronous application sees no running loop of asyncio, when it is called, when its body is iterated and closed,
# as on a WSGI server, so that a library that refuses to block in one, as Django or a blocking request of
# Pyjo.UserAgent, runs on the reactor of asyncio too
with subtest('No running loop'):
    seen = []

    def running(where):
        try:
            asyncio.get_running_loop()
            seen.append((where, True))
        except RuntimeError:
            seen.append((where, False))

    class Body:
        def __iter__(self):
            running('iteration')
            yield b'Hello'

        def close(self):
            running('close')

    def synchronous(environ, start_response):
        running('call')
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return Body()

    with Pyjo.App.WSGI.new(app=synchronous) as app:
        Pyjo.Test.Pyjo.new(app).get_ok('/').status_is(200).content_is('Hello')
    is_deeply_ok(seen, [('call', False), ('iteration', False), ('close', False)], 'no running loop')

    # A blocking request of a user agent with an event loop and a server of its own, which a reactor on an event loop that
    # does not nest, as Trio, refuses, as a new reactor of its class runs in the loop that runs
    inner = Pyjo.UserAgent.new()
    inner.server.app = Pyjo.App.WSGI.new(app=echo)
    riding = []

    def client(environ, start_response):
        riding.append(type(Pyjo.IOLoop.singleton.reactor).new().is_running)
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [inner.get('/inner').result.json('/PATH_INFO').encode()]

    with Pyjo.App.WSGI.new(app=client) as app:
        t = Pyjo.Test.Pyjo.new(app).get_ok('/')
        if riding[0]:
            t.status_is(500)
        else:
            t.status_is(200).content_is('/inner')
    inner.close()

done_testing()
