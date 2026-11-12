import Pyjo.Asset.File
import Pyjo.File
import Pyjo.IOLoop
import Pyjo.IOLoop.Server
import Pyjo.JSON
import Pyjo.Promise
import Pyjo.Reactor.Asyncio
import Pyjo.Server
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjo.URL
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.Test import *
from Pyjo.Util import md5_sum, steady_time, url_escape, warn

import atexit
import contextlib
import importlib
import io
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import wsgiref.util
import wsgiref.validate


ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
ServerStart = importlib.import_module('ServerStart')

# The examples of docs/guides/cookbook.rst, which includes them
EXAMPLES = Pyjo.File.curfile().dirname().dirname().sibling('docs', 'guides', 'cookbook')

# The remote services of the examples, which a mock answers in their place, as the tests do not use the network
TITLES = {
    'github.com': 'GitHub',
    'mojolicious.org': 'Mojolicious - Perl real-time web framework',
    'pyjoyment.readthedocs.io': 'Pyjoyment documentation',
    'www.google.com': 'Google',
}

backend = Pyjoyment.new()
r = backend.routes


@r.get('/search/repositories')
def search(c):
    c.render(json={'items': [{'full_name': f'pyjoyment/{c.param("q")}', 'owner': {'login': 'pyjoyment'}}]})


@r.get('/hideout')
def hideout(c):
    if c.req.url.to_abs().userinfo != 'sri:secret':
        return c.render(text='Authentication required!', status=401)
    c.render(text='Welcome to the hideout!')


@r.websocket('/raw')
def raw(c):
    c.on('message', lambda c, msg: c.send(msg))


# A slow service, which never answers
@r.post('/v1/slow')
def slow(c):
    c.render_later()


@r.any('/*rest', {'rest': ''})
def page(c):
    host = c.req.headers.host
    if host == 'google.com':
        return c.redirect_to('http://www.google.com/')
    if title := TITLES.get(host):
        return c.render(
            inline="""<html><head><title><%= title %></title></head><body>
<h1>Hello</h1><p>Pyjoyment <img alt="unicat"> rocks</p><h2><%= rest %></h2>
<div><%= c.req.headers.header('X-Bender') or '' %></div><div><%= c.req.headers.user_agent %></div>
</body></html>""",
            title=title,
        )
    c.render(
        json={
            'host': host,
            'method': c.req.method,
            'path': c.req.url.path.to_str(),
            'query': c.req.url.query.to_str(),
            'type': c.req.headers.content_type,
            'body': (c.req.build_body() if c.req.content.is_multipart else c.req.body).decode('latin-1'),
        }
    )


# The mock runs in a process of its own, as a blocking request of a user agent runs an event loop of its own
if sys.argv[1:2] == ['backend']:
    Pyjo.Server.Daemon.new(app=backend, listen=[f'http://127.0.0.1:{sys.argv[2]}'], silent=True).run()
    sys.exit()


def start_backend():
    port = ServerStart.port()
    process = subprocess.Popen([sys.executable, __file__, 'backend', str(port)], env={**os.environ, 'PYTHONPATH': ROOT})
    atexit.register(lambda: process.poll() is None and process.kill())
    return (port, process) if ServerStart.listening(port, process) else None


BACKEND, BACKEND_PROCESS = ServerStart.retry(start_backend)


@contextlib.contextmanager
def remote(ua):
    # The requests of the user agent go to the mock, with the host of the remote service as the Host header
    @ua.on('start')
    def start(ua, tx):
        url = tx.req.url
        if url.host and url.host != '127.0.0.1':
            tx.req.headers.host = url.host
            url.scheme = 'ws' if url.scheme in ('ws', 'wss') else 'http'
            url.host, url.port = '127.0.0.1', BACKEND

    try:
        yield
    finally:
        ua.unsubscribe('start', start)


def cookbook(name):
    return Pyjo.Test.Pyjo.new(EXAMPLES.child(f'{name}.py'))


def sandbox(name):
    # The module of an example that Pyjo.Test.Pyjo has loaded
    return sys.modules[f'Pyjo.Server.Sandbox.{md5_sum(EXAMPLES.child(f"{name}.py").to_abs().to_str().encode())}']


def concurrently(*requests):
    # Requests of several applications at the same time, as each of them waits for seconds
    results = []
    Pyjo.Promise.all(*(t.ua.get_p(path) for t, path in requests)).then(lambda *txs: results.extend(txs)).wait()
    return [tx for tx, *_ in results]


def command(*args, cwd=None, path=(), input=None):
    # A command in a process of its own, with the directories of its modules in front of sys.path
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([*path, os.getcwd()])}
    for name in ('PYJO_EXE', 'PYJO_HOME', 'PYJO_LOG_LEVEL', 'PYJO_MODE'):
        env.pop(name, None)
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, env=env, cwd=cwd, timeout=60, input=input
    )


def wsgi(application, path):
    # A request of a WSGI server, which the validator of wsgiref checks
    environ = {'PATH_INFO': path, 'QUERY_STRING': '', 'SCRIPT_NAME': ''}
    wsgiref.util.setup_testing_defaults(environ)
    status, headers = None, None

    def start_response(s, h, exc_info=None):
        nonlocal status, headers
        status, headers = s, dict(h)
        return lambda data: None

    result = wsgiref.validate.validator(application)(environ, start_response)
    try:
        body = b''.join(result)
    finally:
        result.close()
    return status, headers, body


with subtest('Hosts and origins'):
    with cookbook('hosts') as t:
        t.get_ok('/', {'Host': 'example.com'}).status_is(200).content_is('Hello World!')
        t.get_ok('/', {'Host': 'www.example.com', 'Origin': 'https://example.com'}).status_is(200)
        t.get_ok('/', {'Host': 'localhost:3000'}).status_is(200)
        t.get_ok('/', {'Host': 'evil.com'}).status_is(421).content_is('Host not allowed')
        t.get_ok('/', {'Origin': 'https://evil.com'}).status_is(403).content_is('Origin not allowed')
        t.get_ok('/', {'Origin': 'http://localhost:5173'}).status_is(403)
    with cookbook('hosts_under') as t:
        t.get_ok('/', {'Host': 'evil.com'}).status_is(200).content_is('Hello World!')
        t.post_ok('/mcp').status_is(200).json_is({'jsonrpc': '2.0', 'id': 1, 'result': {}})
        t.post_ok('/mcp', {'Host': 'evil.com', 'Origin': 'http://evil.com'}).status_is(421)
        t.post_ok('/mcp', {'Origin': 'http://evil.com'}).status_is(403)

with subtest('Pre-forking'):
    with cookbook('worker') as t, t.app.log.capture('info') as logs:
        t.get_ok('/').status_is(200).content_is('Hello World!')
    like_ok(str(logs), re.compile(rf'Worker {os.getpid()} started'), 'started')

with subtest('Health checks'):
    uploads = tempfile.mkdtemp()
    os.environ['MYAPP_UPLOADS'] = uploads
    try:
        with cookbook('health') as t:
            t.get_ok('/').status_is(200).content_is('Hello World!')
            t.get_ok('/livez').status_is(200).content_is('ok')
            t.get_ok('/healthz').status_is(200).content_is('ok')
            t.get_ok('/readyz').status_is(200).content_is('ok')
            t.get_ok('/readyz?verbose').status_is(200).content_is(
                '[+]shutdown ok\n[+]uploads ok\nreadyz check passed\n'
            )

            async def search(c):
                tx = await c.ua().get_p('http://search.internal:9200/_cluster/health')
                return tx.res.is_success

            t.app.health.check('search', search, timeout=2)
            with remote(t.app.ua):
                t.get_ok('/readyz/search').status_is(200).content_is('ok')
            os.rmdir(uploads)
            t.get_ok('/readyz?exclude=search').status_is(503).content_is(
                '[+]shutdown ok\n[-]uploads failed: reason withheld\n[+]search excluded: ok\nreadyz check failed\n'
            )
            t.get_ok('/livez').status_is(200).content_is('ok')
    finally:
        del os.environ['MYAPP_UPLOADS']
        if os.path.isdir(uploads):
            os.rmdir(uploads)

with subtest('Access log'):

    def logged(t, *args):
        # The output of a request, once the transaction of the server has finished, after the plugin, which subscribes
        # to the event finish first, so that a request that writes nothing does not wait
        finished = []
        t.app.hook('after_build_tx', lambda tx, app: tx.on('finish', lambda tx: finished.append(tx)))
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            t.get_ok(*args)
            deadline = steady_time() + 5
            while not finished and steady_time() < deadline:
                Pyjo.IOLoop.timer(0.01, lambda loop: None)
                Pyjo.IOLoop.one_tick()
        return stdout.getvalue()

    with cookbook('health') as t:
        t.app.plugin('AccessLog')
        output = logged(t, '/', {'User-Agent': 'curl/8.7.1'})
        like_ok(output, r'127\.0\.0\.1 - - \[.+ [+-]\d{4}\] "GET / HTTP/1\.1" 200 12 "-" "curl/8\.7\.1"\n', 'line')
        output = logged(t, '/livez')
        unlike_ok(output, r'"GET /livez', 'no probes')

    with cookbook('health') as t:
        t.app.plugin('AccessLog', client='X-Envoy-External-Address', format='json')
        output = logged(t, '/', {'X-Envoy-External-Address': '203.0.113.7'})
        record = Pyjo.JSON.decode_json(output.splitlines()[0])
        is_ok(record['client'], '203.0.113.7', 'client of the gateway')
        is_ok(record['httpRequest']['remoteIp'], '203.0.113.7', 'request of Cloud Logging')

with subtest('Hot deployment'):
    with cookbook('hot') as t:
        is_deeply_ok(t.app.config('hot'), {'listen': ['http://*:80']}, 'settings')
        t.get_ok('/').status_is(200).content_is('Hello World!')
    if not hasattr(os, 'fork'):
        skip('Pyjo.Server.Hot needs os.fork', 1)
    else:
        result = command('-m', 'Pyjo.Server.Hot', '-t', EXAMPLES.child('hot.py').to_str())
        is_ok(result.stdout, 'Everything looks good!\n', 'tested')

    with tempfile.TemporaryDirectory() as tmp:
        conf = Pyjo.File.path(tmp, 'myapp.conf')
        conf.spew(
            "{\n    'hot': {\n        'listen': ['https://*:443?cert=/etc/server.crt&key=/etc/server.key'],\n"
            "        'workers': 10,\n    }\n}\n"
        )
        config = Pyjoyment.new().plugin('Config', {'file': conf.to_str()})
        is_deeply_ok(
            config['hot'],
            {'listen': ['https://*:443?cert=/etc/server.crt&key=/etc/server.key'], 'workers': 10},
            'configuration file',
        )
        conf.spew("{'hot': {'proxy': True}}\n")
        is_ok(Pyjoyment.new().plugin('Config', {'file': conf.to_str()})['hot']['proxy'], True, 'proxy')

with subtest('WSGI middleware'):
    cwd = os.getcwd()
    os.chdir(EXAMPLES.child('wsgi').to_str())
    try:
        application = runpy.run_path('myapp_wsgi.py', run_name='myapp_wsgi')['application']
        status, headers, body = wsgi(application, '/')
        is_ok(status, '200 OK', 'status')
        is_ok(headers['X-Powered-By'], 'Pyjoyment', 'middleware')
        is_ok(body, b'Hello bar!', 'configured')

        application = runpy.run_path('welcome.py', run_name='welcome')['application']
        status, headers, body = wsgi(application, '/welcome')
        is_ok(status, '200 OK', 'status')
        is_ok(headers['X-Powered-By'], 'Pyjoyment', 'middleware')
        is_ok(body, b'Hello Pyjo!', 'application')
    finally:
        os.chdir(cwd)


with subtest('AWS Lambda'):
    if os.name == 'nt':
        skip('Lambda functions need pipes that the event loop watches', 3)
    else:
        lam = EXAMPLES.child('lambda')

        # The application as the handler of the runtime of Lambda, which AWS_LAMBDA_RUNTIME_API tells
        os.environ['AWS_LAMBDA_RUNTIME_API'] = '127.0.0.1:9001'
        try:
            handler = runpy.run_path(lam.child('myapp.py').to_str(), run_name='myapp')['handler']
        finally:
            del os.environ['AWS_LAMBDA_RUNTIME_API']
        event = {'version': '2.0', 'rawPath': '/', 'requestContext': {'http': {'method': 'GET'}, 'stage': '$default'}}
        is_ok(handler(event, None)['body'], 'Hello Lambda at /!', 'handler')

        # The function mounted, live and in the tests
        t = Pyjo.Test.Pyjo.new(lam.child('gateway.py'))
        t.get_ok('/myapp').status_is(200).content_is('Hello Lambda at /myapp!')

with subtest('Standard input and output'):
    if os.name == 'nt':
        skip('the standard input and output need pipes that the event loop watches', 7)
    else:
        stdio = EXAMPLES.child('stdio').to_str()

        # printf 'hello\nworld\n' | ./lines.py stdio
        result = command('lines.py', 'stdio', cwd=stdio, input='hello\nworld\n')
        is_ok(result.stdout, 'HELLO\nWORLD\n', 'lines')
        like_ok(result.stderr, r'^Got hello\nGot world\n', 'print on stderr')

        # echo '{"jsonrpc":"2.0","method":"divide","params":[7,2],"id":1}' | ./rpc.py stdio
        request = '{"jsonrpc":"2.0","method":"divide","params":[7,2],"id":1}\n'
        result = command('rpc.py', 'stdio', cwd=stdio, input=request)
        is_ok(result.stdout, '{"jsonrpc":"2.0","result":3.5,"id":1}\n', 'JSON-RPC')

        # python client.py
        result = command('client.py', cwd=stdio)
        is_ok(result.stdout, '3.5\n', 'client')
        is_ok(result.returncode, 0, 'server ended')

        # The same server over HTTP
        t = Pyjo.Test.Pyjo.new(EXAMPLES.child('stdio', 'rpc.py'))
        t.post_ok('/rpc', json={'jsonrpc': '2.0', 'method': 'divide', 'params': [7, 2], 'id': 1}).json_is(
            '/result', 3.5
        )

with subtest('Rewriting'):
    app = Pyjoyment.new()
    app.mode = 'production'

    # Change scheme if "X-Forwarded-HTTPS" header is set
    @app.hook('before_dispatch')
    def https(c):
        if c.req.headers.header('X-Forwarded-HTTPS'):
            c.req.url.base.scheme = 'https'

    # Move first part and slash from path to base path in production mode
    if app.mode == 'production':

        @app.hook('before_dispatch')
        def prefix(c):
            base, path = c.req.url.base.path, c.req.url.path
            base.trailing_slash, path.leading_slash = True, False
            base.parts.append(path.parts.pop(0))

    app.routes.get('/bar').to(cb=lambda c: c.render(text=c.url_for('/baz').to_abs().to_str()))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/myapp/bar').status_is(200).content_like(re.compile(r'^http://127\.0\.0\.1:\d+/myapp/baz$'))
        t.get_ok('/myapp/bar', {'X-Forwarded-HTTPS': 1})
        t.status_is(200).content_like(re.compile(r'^https://127\.0\.0\.1:\d+/myapp/baz$'))

with subtest('Deployment specific plugins'):
    with tempfile.TemporaryDirectory() as tmp:
        conf = Pyjo.File.path(tmp, 'myapp.conf')
        conf.spew("{\n    'plugins': [\n        {'HeaderCondition': {}},\n    ]\n}\n")
        app = Pyjoyment.new()
        app.plugin('Config', {'file': conf.to_str()})
        ok('headers' in app.routes.conditions, 'plugin loaded')

with subtest('Application embedding'):
    with tempfile.TemporaryDirectory() as tmp:
        Pyjo.File.path(tmp, 'myapp.py').spew('''"""
__DATA__
@@ foo.html.ep
Hello <%= config('secret_identity') %>!
"""

from Pyjoyment.Lite import *

app.config(secret_identity='Pyjo')
app.start()
''')
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            # Load application with mock server
            server = Pyjo.Server.new()
            app = server.load_app('./myapp.py')
        finally:
            os.chdir(cwd)

        # Access fully initialized application
        # Both real, as a temporary directory of Windows may have the short names of 8.3, as C:\Users\RUNNER~1
        is_ok(os.path.realpath(app.static.paths[0]), os.path.join(os.path.realpath(tmp), 'public'), 'static paths')
        is_ok(app.config('secret_identity'), 'Pyjo', 'config')
        is_ok(app.dumper({'just': 'a helper test'}), "{'just': 'a helper test'}\n", 'helper')
        is_ok(app.build_controller().render_to_string(template='foo'), 'Hello Pyjo!\n', 'template')

        for name, text in (('myapp1', 'One'), ('myapp2', 'Two')):
            Pyjo.File.path(tmp, f'{name}.py').spew(
                f"from Pyjoyment.Lite import *\n\nget('/', {{'text': '{text}'}})\n\napp.start()\n"
            )
        app = Pyjoyment.new()
        app.config(hot={'listen': ['http://*:80']})
        app.plugin('Mount', {'test1.example.com': Pyjo.File.path(tmp, 'myapp1.py').to_str()})
        app.plugin('Mount', {'test2.example.com': Pyjo.File.path(tmp, 'myapp2.py').to_str()})
        with Pyjo.Test.Pyjo.new(app) as t:
            t.get_ok('/', {'Host': 'test1.example.com'}).status_is(200).content_is('One')
            t.get_ok('/', {'Host': 'test2.example.com'}).status_is(200).content_is('Two')

with subtest('Web server embedding'):
    app = Pyjoyment.new()

    # Normal action
    app.routes.get('/').to(text='Hello World!')

    # Connect application with web server and start accepting connections
    with Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], silent=True) as daemon:
        daemon.start()
        port = Pyjo.IOLoop.acceptor(daemon.acceptors[0]).port

        # Call "one_tick" repeatedly from the alien environment
        with Pyjo.UserAgent.new() as ua:
            txs = []
            ua.get(f'http://127.0.0.1:{port}/', lambda ua, tx: txs.append(tx))
            while not txs:
                Pyjo.IOLoop.one_tick()
            is_ok(txs[0].res.text, 'Hello World!', 'embedded')

with subtest('Backend web services'):
    with cookbook('backend') as t, remote(t.app.ua):
        t.get_ok('/').status_is(200).text_is('title', 'GitHub results for "pyjoyment"')
        t.text_is('p', 'pyjoyment/pyjoyment')

with subtest('Synchronizing non-blocking operations'):
    with cookbook('synchronizing') as t, remote(t.app.ua):
        t.get_ok('/').status_is(200).json_is({'pyjo': 'pyjoyment/pyjoyment', 'mojo': 'pyjoyment/mojolicious'})

    # Wrap a user agent method with a promise
    with Pyjo.UserAgent.new() as ua, remote(ua):

        def get_p(*args):
            promise = Pyjo.Promise.new()

            def done(ua, tx):
                err = tx.error
                if not err or err.get('code'):
                    promise.resolve(tx)
                promise.reject(err['message'] if err else None)

            ua.get(*args, done)
            return promise

        # Use our new promise generating function
        titles = []
        get_p('https://pyjoyment.readthedocs.io').then(
            lambda tx: titles.append(tx.result.dom().at('title').text)
        ).wait()
        is_deeply_ok(titles, ['Pyjoyment documentation'], 'wrapped')

with subtest('async/await'):

    @Pyjo.Promise.coroutine
    async def hello_p():
        return 'Hello Pyjo!'

    results = []
    hello_p().then(results.append).wait()
    is_deeply_ok(results, ['Hello Pyjo!'], 'coroutine')

    with Pyjo.UserAgent.new() as ua, remote(ua):
        # Search GitHub non-blocking for multiple terms sequentially
        @Pyjo.Promise.coroutine
        async def search_github_p(terms):
            github = Pyjo.URL.new('https://api.github.com/search/repositories')
            urls = [github.clone().set(query={'q': term}) for term in terms]

            for url in urls:
                tx = await ua.get_p(url)
                print(tx.result.json('/items/0/full_name'))

        with contextlib.redirect_stdout(io.StringIO()) as out:
            search_github_p(['pyjoyment', 'mojolicious']).wait()
        is_ok(out.getvalue(), 'pyjoyment/pyjoyment\npyjoyment/mojolicious\n', 'sequentially')

        # Search GitHub non-blocking for multiple terms concurrently
        @Pyjo.Promise.coroutine
        async def search_github_p(terms):
            github = Pyjo.URL.new('https://api.github.com/search/repositories')
            urls = [github.clone().set(query={'q': term}) for term in terms]

            promises = [ua.get_p(url) for url in urls]
            results = await Pyjo.Promise.all(*promises)
            for result in results:
                print(result[0].result.json('/items/0/full_name'))

        with contextlib.redirect_stdout(io.StringIO()) as out:
            search_github_p(['pyjoyment', 'mojolicious']).wait()
        is_ok(out.getvalue(), 'pyjoyment/pyjoyment\npyjoyment/mojolicious\n', 'concurrently')

    # Catch a non-blocking exception
    @Pyjo.Promise.coroutine
    async def hello_p():
        try:
            await Pyjo.Promise.reject('This is an exception')
        except Exception as err:
            warn(f'Error: {err}')

    with contextlib.redirect_stderr(io.StringIO()) as err:
        hello_p().wait()
    like_ok(err.getvalue(), re.compile(r'^Error: This is an exception'), 'caught')

    with cookbook('titles') as t, remote(t.app.ua):
        t.get_ok('/').status_is(200)
        t.json_is({'pyjo': 'Pyjoyment documentation', 'mojo': 'Mojolicious - Perl real-time web framework'})

with subtest('Timers and subprocesses'):
    with (
        cookbook('delayed') as delayed,
        cookbook('counter') as counter,
        cookbook('blocking') as blocking,
        cookbook('sleepy') as sleepy,
    ):
        txs = concurrently((delayed, '/'), (counter, '/'), (blocking, '/'), (sleepy, '/'))
        is_ok(txs[0].res.text, 'Delayed by 3 seconds!', 'timer')
        is_ok(txs[1].res.text, '12345', 'recurring timer')
        if not hasattr(os, 'fork'):
            skip('Pyjo.IOLoop.Subprocess needs os.fork', 1)
        else:
            is_ok(txs[2].res.text, 'I ♥ Pyjoyment!', 'subprocess')
        if isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
            is_ok(txs[3].res.text, 'Delayed by 3 seconds!', 'asyncio')
        else:
            skip('needs Pyjo.Reactor.Asyncio, as the coroutine awaits asyncio.sleep', 1)

    # A program in a child process, whose output streams as it comes
    if os.name == 'nt':
        skip('child processes need pipes that the reactor watches', 6)
    else:
        with cookbook('sort') as t:
            t.post_ok('/sort', b'b\na\n').status_is(200).content_is('a\nb\n')

        # The snippet of run_p, copied
        import Pyjo.IOLoop.ChildProcess

        import platform

        app = Pyjoyment.new()
        app.log.level = 'fatal'

        async def system(c):
            code, out, err = await Pyjo.IOLoop.ChildProcess.new().run_p(['uname', '-s'])
            c.render(text=out.strip().decode())

        app.routes.get('/system').to(cb=system)
        with Pyjo.Test.Pyjo.new(app) as t:
            t.get_ok('/system').status_is(200).content_is(platform.system())

    with cookbook('background') as t:
        t.get_ok('/').status_is(200).json_is('/title', 'Got no title yet.')

        # The recurring timer of the example would request the remote service later
        Pyjo.IOLoop.remove(sandbox('background').check)

with subtest('Exceptions in non-blocking operations'):
    # The default subscriber of the event loop warns, which the example keeps, as the test does not
    reactor = Pyjo.IOLoop.singleton.reactor
    subscribers = reactor.subscribers('error')
    reactor.unsubscribe('error')
    try:
        with cookbook('errors') as t:
            t.ua.inactivity_timeout = 3
            with t.app.log.capture('error') as logs:
                t.get_ok('/catch_exception').status_is(500).content_like(re.compile(r'will be getting a response'))
                like_ok(t.ua.get('/connection_times_out').error['message'], re.compile(r'Inactivity timeout'))
            like_ok(str(logs), re.compile(r'Timer failed: This request will not be getting a response'), 'logged')
    finally:
        reactor.unsubscribe('error')
        for cb in subscribers:
            reactor.on('error', cb)

with subtest('WebSocket web service'):
    with cookbook('echo') as t:
        t.get_ok('/').status_is(200).content_like(re.compile(r"new WebSocket\('ws://127\.0\.0\.1:\d+/echo'\)"))
        with t.app.log.capture('debug') as logs:
            t.websocket_ok('/echo').send_ok('Hello Pyjo!').message_ok().message_is('echo: Hello Pyjo!')
            t.finish_ok().finished_ok(1005)
        like_ok(str(logs), re.compile(r'WebSocket opened'), 'opened')
        like_ok(str(logs), re.compile(r'WebSocket closed with status 1005'), 'closed')

    app = Pyjoyment.new()

    @app.routes.websocket('/')
    def compressed(c):
        c.tx.with_compression()
        proto = c.tx.with_protocols('v2.proto', 'v1.proto')
        c.on('message', lambda c, msg: c.send(f'{proto}: {msg}'))

    with Pyjo.Test.Pyjo.new(app) as t:
        t.websocket_ok('/', {'Sec-WebSocket-Extensions': 'permessage-deflate', 'Sec-WebSocket-Protocol': 'v1.proto'})
        t.header_is('Sec-WebSocket-Extensions', 'permessage-deflate').header_is('Sec-WebSocket-Protocol', 'v1.proto')
        t.send_ok('Hi!').message_ok().message_is('v1.proto: Hi!').finish_ok()

with subtest('Server-Sent Events web service'):
    with cookbook('livelog') as t:
        t.get_ok('/').status_is(200).content_like(re.compile(r"new EventSource\('/events'\)"))

        # A log message once the response headers have been written
        Pyjo.IOLoop.timer(0.5, lambda loop: t.app.log.info('Hello SSE!'))
        with t.app.log.capture('info'):
            t.get_sse_ok('/events').status_is(200).sse_ok().sse_type_is('log').sse_text_is('[info] Hello SSE!')
            t.sse_finish_ok()

with subtest('Streaming multipart uploads'):
    with cookbook('upload') as t:
        t.get_ok('/').status_is(200).element_exists('form[enctype="multipart/form-data"] input[name="example"]')
        with t.app.log.capture('debug') as logs:
            form = {'example': {'content': 'x' * 300000, 'filename': 'example.txt'}}
            t.post_ok('/upload', form=form).status_is(200).content_is('Upload was successful.')
        sizes = [int(size) for size in re.findall(r'(\d+) bytes uploaded', str(logs))]
        ok(len(sizes) > 1, 'chunks')
        is_ok(sum(sizes), 300000, 'all bytes')

with subtest('REST web services'):
    # Request a resource and make sure there were no connection errors
    with Pyjo.UserAgent.new() as ua, remote(ua):
        tx = ua.get('https://pyjoyment.readthedocs.io/en/latest/api/Pyjo.html', {'Accept': 'text/plain'})
        res = tx.result

        # Decide what to do with its representation
        ok(res.is_success, 'success')
        like_ok(res.text, re.compile(r'<h2>en/latest/api/Pyjo\.html</h2>'), 'body')

        res = ua.get('google.com').result
        is_ok(res.code, 302, 'redirect')
        is_ok(res.headers.location, 'http://www.google.com/', 'location')

with subtest('Web scraping'):
    # Fetch website
    with Pyjo.UserAgent.new() as ua, remote(ua):
        res = ua.get('https://pyjoyment.readthedocs.io').result

        # Extract title
        is_ok(res.dom().at('head > title').text, 'Pyjoyment documentation', 'title')

        # Extract headings
        headings = []
        res.dom('h1, h2, h3').each(lambda dom, i: headings.append(dom.all_text))
        is_deeply_ok(headings, ['Hello', ''], 'headings')

        # Visit all nodes recursively to extract more than just text
        with contextlib.redirect_stdout(io.StringIO()) as out:
            for n in res.dom().descendant_nodes:
                # Text or CDATA node
                if n.type == 'text' or n.type == 'cdata':
                    print(n.content, end='')

                # Also include alternate text for images
                if n.type == 'tag' and n.tag == 'img':
                    print(n['alt'] or '', end='')
        like_ok(out.getvalue(), re.compile(r'Pyjoyment documentation.*Pyjoyment unicat rocks', re.S), 'nodes')

with subtest('JSON web services'):
    # Fresh user agent
    with Pyjo.UserAgent.new() as ua, remote(ua):
        # Search GitHub for "pyjoyment" and list recently updated repositories
        url = Pyjo.URL.new('https://api.github.com/search/repositories')
        url.query = {'q': 'pyjoyment', 'sort': 'updated'}
        items = [f'{item["full_name"]} ({item["owner"]["login"]})' for item in ua.get(url).result.json('/items')]
        is_deeply_ok(items, ['pyjoyment/pyjoyment (pyjoyment)'], 'repositories')

with subtest('Basic authentication'):
    with Pyjo.UserAgent.new() as ua, remote(ua):
        is_ok(ua.get('https://sri:secret@example.com/hideout').result.text, 'Welcome to the hideout!', 'userinfo')

        url = Pyjo.URL.new('https://example.com/hideout').set(userinfo='sri:secret')
        is_ok(url.to_str(), 'https://example.com/hideout', 'not included')
        is_ok(url.to_unsafe_str(), 'https://sri:secret@example.com/hideout', 'unsafe')
        is_ok(ua.get(url).result.text, 'Welcome to the hideout!', 'object')

with subtest('Decorating follow-up requests'):
    # User agent following up to 10 redirects
    with Pyjo.UserAgent.new(max_redirects=10) as ua:
        requests = []

        # Add a witty header to every request
        @ua.on('start')
        def start(ua, tx):
            tx.req.headers.header('X-Bender', 'Bite my shiny metal ass!')
            requests.append(tx.req.url.clone().to_abs().to_str())

        with remote(ua):
            # Request that will most likely get redirected
            dom = ua.get('google.com').result.dom()
            is_ok(dom.at('head > title').text, 'Google', 'title')
            is_ok(dom.at('div').text, 'Bite my shiny metal ass!', 'header')
        is_deeply_ok(requests, ['http://google.com', 'http://www.google.com/'], 'requests')

with subtest('Content generators'):
    with tempfile.TemporaryDirectory() as tmp:
        Pyjo.File.path(tmp, 'pyjo.png').spew(b'PNG data')

        # Add "stream" generator
        with Pyjo.UserAgent.new() as ua, remote(ua):

            def stream(transactor, tx, path):
                tx.req.content.asset = Pyjo.Asset.File.new(path=path)

            ua.transactor.add_generator('stream', stream)

            # Send multiple files streaming via PUT and POST
            tx = ua.put('http://example.com/upload', stream=Pyjo.File.path(tmp, 'pyjo.png').to_str())
            is_ok(tx.result.json('/method'), 'PUT', 'PUT')
            is_ok(tx.result.json('/body'), 'PNG data', 'streamed')
            tx = ua.post('http://example.com/upload', stream=Pyjo.File.path(tmp, 'pyjo.png').to_str())
            is_ok(tx.result.json('/method'), 'POST', 'POST')

            # The file is closed before its directory is removed, which Windows does not do with a file that is open
            tx.req.content.asset.close()

    with Pyjo.UserAgent.new() as ua, remote(ua):
        # Send "application/json" content via PATCH
        tx = ua.patch('http://api.example.com', json={'foo': 'bar'})
        is_deeply_ok(
            [tx.result.json(f'/{key}') for key in ('method', 'type', 'body')],
            ['PATCH', 'application/json', '{"foo":"bar"}'],
            'json',
        )

        # Send query parameters via GET
        tx2 = ua.get('search.example.com', form={'q': 'test'})
        is_deeply_ok([tx2.result.json(f'/{key}') for key in ('method', 'query')], ['GET', 'q=test'], 'query')

        # Send "application/x-www-form-urlencoded" content via POST
        tx3 = ua.post('http://search.example.com', form={'q': 'test'})
        is_deeply_ok(
            [tx3.result.json(f'/{key}') for key in ('method', 'type', 'body')],
            ['POST', 'application/x-www-form-urlencoded', 'q=test'],
            'form',
        )

        # Send "multipart/form-data" content via PUT
        tx4 = ua.put('upload.example.com', form={'test': {'content': 'Hello World!'}})
        like_ok(tx4.result.json('/type'), re.compile(r'^multipart/form-data'), 'multipart form')
        like_ok(tx4.result.json('/body'), re.compile(r'name="test".*Hello World!', re.S), 'multipart form content')

        # Send custom multipart content via PUT
        tx5 = ua.put('api.example.com', multipart=['Hello', 'World!'])
        like_ok(tx5.result.json('/body'), re.compile(r'Hello.*World!', re.S), 'multipart')

with subtest('Large file downloads and uploads'):
    with tempfile.TemporaryDirectory() as tmp:
        # Fetch the latest Pyjoyment tarball
        with Pyjo.UserAgent.new(max_redirects=5) as ua, remote(ua):
            tx = ua.get('https://github.com/pyjoyment/Pyjoyment/tarball/main')
            tx.result.save_to(Pyjo.File.path(tmp, 'pyjoyment.tar.gz').to_str())
        like_ok(Pyjo.File.path(tmp, 'pyjoyment.tar.gz').slurp(), re.compile(rb'pyjoyment/Pyjoyment/tarball/main'))

        # Download the latest Pyjoyment tarball directly into a file
        with Pyjo.UserAgent.new(max_redirects=10, max_response_size=0) as ua, remote(ua):
            target = Pyjo.File.path(tmp, 'download.tar.gz')
            ok(target.download('https://github.com/pyjoyment/Pyjoyment/tarball/main', ua=ua), 'downloaded')
        like_ok(target.slurp(), re.compile(rb'pyjoyment/Pyjoyment/tarball/main'), 'file')

        # Increase limit to 10GiB
        with Pyjo.UserAgent.new() as ua:
            ua.max_response_size = 10737418240
            is_ok(ua.max_response_size, 10737418240, 'limit')

        # Upload file via POST and "multipart/form-data"
        Pyjo.File.path(tmp, 'hello.png').spew(b'Hello PNG')
        with Pyjo.UserAgent.new() as ua, remote(ua):
            tx = ua.post('example.com/upload', form={'image': {'file': Pyjo.File.path(tmp, 'hello.png').to_str()}})
            like_ok(tx.result.json('/body'), re.compile(r'name="image"; filename="hello\.png".*Hello PNG', re.S))

            # The file is closed before its directory is removed, which Windows does not do with a file that is open
            for part in tx.req.content.parts:
                part.asset.close()

with subtest('Streaming response and request'):
    # Accept responses of indefinite size
    with Pyjo.UserAgent.new(max_response_size=0) as ua, remote(ua):
        # Build a normal transaction
        tx = ua.build_tx('GET', 'http://example.com')

        # Replace "read" events to disable default content parser
        chunks = []
        tx.res.content.unsubscribe('read').on('read', lambda content, data: chunks.append(data))

        # Process transaction
        tx = ua.start(tx)
        like_ok(b''.join(chunks), re.compile(rb'"host":"example\.com"'), 'streamed')
        is_ok(tx.res.body, b'', 'no body')

    # Build a normal transaction
    with Pyjo.UserAgent.new() as ua, remote(ua):
        tx = ua.build_tx('POST', 'http://example.com')

        # Prepare body
        body = b'Hello World!'
        tx.req.headers.content_length = len(body)

        # Start writing directly with a drain callback
        def drain(content, offset=None):
            global body
            chunk, body = body[:1], body[1:]
            content.write(chunk, drain if len(body) else None)

        drain(tx.req.content)

        # Process transaction
        tx = ua.start(tx)
        is_ok(tx.result.json('/body'), 'Hello World!', 'written')

with subtest('Long requests of the user agent'):
    import Pyjo.Promise
    import Pyjo.UserAgent

    # A user agent of its own for a slow service
    llm = Pyjo.UserAgent.new(inactivity_timeout=300, request_timeout=600)

    # One request with a time of its own
    async def complete(prompt):
        promise = llm.post_p('https://api.example.com/v1/complete', json={'prompt': prompt})
        try:
            tx = await Pyjo.Promise.race(promise, Pyjo.Promise.timeout(120, 'Too slow'))
        finally:
            promise.cancel()
        return tx.result.json()

    with llm, remote(llm):
        got = []
        Pyjo.Promise.new(complete('Hello')).then(got.append).wait()
        is_ok(got[0]['host'], 'api.example.com', 'host of the service')
        is_ok(got[0]['body'], '{"prompt":"Hello"}', 'request')

        # The same with a time that passes first, on a service that does not answer
        async def slow(prompt):
            promise = llm.post_p('https://api.example.com/v1/slow', json={'prompt': prompt})
            try:
                tx = await Pyjo.Promise.race(promise, Pyjo.Promise.timeout(0.1, 'Too slow'))
            finally:
                promise.cancel()
            return tx.result.json()

        reason = []
        Pyjo.Promise.new(slow('Hello')).catch(reason.append).wait()
        like_ok(str(reason[0]), r'^Too slow', 'the time passed first')
        is_deeply_ok(llm._connections, {}, 'connection of the request closed')

with subtest('Non-blocking'):
    # Concurrent non-blocking requests
    with Pyjo.UserAgent.new() as ua, remote(ua):
        titles = []
        ua.get(
            'https://github.com/pyjoyment/Pyjoyment', lambda ua, pyjo: titles.append(pyjo.result.dom().at('title').text)
        )
        ua.get(
            'https://github.com/mojolicious/mojo', lambda ua, mojo: titles.append(mojo.result.dom().at('title').text)
        )

        # Start event loop if necessary, which the connections that the user agent keeps alive would keep running
        done = Pyjo.IOLoop.recurring(0.05, lambda loop: len(titles) == 2 and loop.stop())
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
        Pyjo.IOLoop.remove(done)
        is_deeply_ok(titles, ['GitHub', 'GitHub'], 'titles')

    urls = [
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_DOM.html',
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo.html',
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_File.html',
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_URL.html',
    ]

    # User agent with a custom name, following up to 5 redirects
    with Pyjo.UserAgent.new(max_redirects=5) as ua, remote(ua):
        ua.transactor.name = 'MyParallelCrawler 1.0'

        # Use a promise to keep the event loop running until we are done
        promise = Pyjo.Promise.new()
        count = 0
        fetched = []

        def fetch():
            global count

            # Stop if there are no more URLs
            if not urls:
                return
            url = urls.pop(0)

            # Fetch the next title
            def title(ua, tx):
                global count
                fetched.append(f'{url}: {tx.result.dom().at("div:last-child").text}')

                # Next request
                fetch()
                count -= 1
                if count == 0:
                    promise.resolve()

            ua.get(url, title)
            count += 1

        # Process two requests at a time
        for _ in range(2):
            fetch()
        promise.wait()
        is_ok(len(fetched), 4, 'all fetched')
        like_ok(fetched[0], re.compile(r'^https://pyjoyment\.readthedocs\.io/.*: MyParallelCrawler 1\.0$'), 'name')

with subtest('Concurrent blocking requests'):
    # Synchronize non-blocking requests with promises
    with Pyjo.UserAgent.new() as ua, remote(ua):
        pyjo_promise = ua.get_p('https://github.com/pyjoyment/Pyjoyment')
        mojo_promise = ua.get_p('https://github.com/mojolicious/mojo')

        with contextlib.redirect_stdout(io.StringIO()) as out:

            @Pyjo.Promise.all(pyjo_promise, mojo_promise).then
            def titles(pyjo, mojo):
                print(pyjo[0].result.dom().at('title').text)
                print(mojo[0].result.dom().at('title').text)

            titles.wait()
        is_ok(out.getvalue(), 'GitHub\nGitHub\n', 'titles')

with subtest('WebSockets'):
    # Open WebSocket to echo service
    with Pyjo.UserAgent.new() as ua, remote(ua), contextlib.redirect_stdout(io.StringIO()) as out:

        @ua.websocket_p('wss://ws.postman-echo.com/raw').then
        def echo(tx):
            # Prepare a followup promise so we can wait for messages
            promise = Pyjo.Promise.new()

            # Wait for WebSocket to be closed
            @tx.on('finish')
            def finish(tx, code, reason):
                print(f'WebSocket closed with status {code}.')
                promise.resolve()

            # Close WebSocket after receiving one message
            @tx.on('message')
            def message(tx, msg):
                print(f'WebSocket message: {msg}')
                tx.finish()

            # Send a message to the server
            tx.send('Hi!')

            # Insert a new promise into the promise chain
            return promise

        # Handle failed WebSocket handshakes and other exceptions
        echo.catch(lambda err: warn(f'WebSocket error: {err}')).wait()
    is_ok(out.getvalue(), 'WebSocket message: Hi!\nWebSocket closed with status 1005.\n', 'echo')

with subtest('UNIX domain sockets'):
    if sys.platform == 'win32':
        plan(skip_all='no UNIX domain sockets on Windows')
    app = Pyjoyment.new()
    app.routes.get('/index.html').to(text='Index')
    app.routes.get('/').to(cb=lambda c: c.render(text=f'Host {c.req.headers.host}'))

    @app.routes.websocket('/echo')
    def unix_echo(c):
        c.on('message', lambda c, msg: c.send(msg))

    with tempfile.TemporaryDirectory(dir='/tmp') as tmp, Pyjo.UserAgent.new() as ua:
        # Blocking requests run the event loop of the user agent, the WebSocket the one of the singleton
        socks = {name: url_escape(os.path.join(tmp, f'{name}.sock')) for name in ('foo', 'bar', 'baz')}
        daemons = [
            Pyjo.Server.Daemon.new(app=app, ioloop=ua.ioloop, listen=[f'http+unix://{socks["foo"]}'], silent=True),
            Pyjo.Server.Daemon.new(app=app, ioloop=ua.ioloop, listen=[f'http+unix://{socks["bar"]}'], silent=True),
            Pyjo.Server.Daemon.new(app=app, listen=[f'http+unix://{socks["baz"]}'], silent=True),
        ]
        try:
            for daemon in daemons:
                daemon.start()

            # GET request via UNIX domain socket
            is_ok(ua.get(f'http+unix://{socks["foo"]}/index.html').result.text, 'Index', 'GET')

            # GET request with HOST header via UNIX domain socket
            tx = ua.get(f'http+unix://{socks["bar"]}', {'Host': 'example.com'})
            is_ok(tx.result.text, 'Host example.com', 'Host header')

            # WebSocket connection via UNIX domain socket
            with contextlib.redirect_stdout(io.StringIO()) as out:

                @ua.websocket_p(f'ws+unix://{socks["baz"]}/echo').then
                def echo(tx):
                    promise = Pyjo.Promise.new()
                    tx.on('finish', lambda tx, *args: promise.resolve())

                    @tx.on('message')
                    def message(tx, msg):
                        print(f'WebSocket message: {msg}')
                        tx.finish()

                    tx.send('Hi!')

                    return promise

                echo.catch(lambda err: warn(f'WebSocket error: {err}')).wait()
            is_ok(out.getvalue(), 'WebSocket message: Hi!\n', 'WebSocket')
        finally:
            for daemon in daemons:
                daemon.stop()

with subtest('Basic authentication application'):
    with cookbook('basic_auth') as t:
        t.get_ok('/').status_is(401).header_is('WWW-Authenticate', 'Basic').content_is('Authentication required!')
        t.get_ok('//Bender:wrong@/').status_is(401)
        t.get_ok('//Bender:rocks@/').status_is(200).content_is('Hello Bender!')

with subtest('Adding a configuration file'):
    with cookbook('config/myapp') as t:
        t.get_ok('/').status_is(200).text_is('title', 'my Pyjoyment application')
        t.text_is('body', 'Welcome to my Pyjoyment application')

with subtest('Adding a plugin to your application'):
    sys.path.insert(0, EXAMPLES.child('plugin').to_str())
    try:
        with cookbook('plugin/myapp') as t:
            t.get_ok('/').status_is(200).header_is('X-Pyjo', 'I <3 Pyjoyment!').content_is('I ♥ Pyjoyment!')
    finally:
        sys.path.remove(EXAMPLES.child('plugin').to_str())
        for name in [name for name in sys.modules if name == 'MyApp' or name.startswith('MyApp.')]:
            del sys.modules[name]

with subtest('Adding commands to Pyjoyment'):
    commands = EXAMPLES.child('commands').to_str()
    result = command('-m', 'Pyjoyment', 'spy', 'secrets', path=[commands])
    is_ok(result.stdout, 'pyjoyment-hello_world\n', 'secrets')
    result = command('-m', 'MyApp', 'spy', 'secrets', cwd=commands)
    is_ok(result.stdout, 'my_app\n', 'application secrets')
    result = command('-m', 'MyApp', 'spy', '-m', 'production', 'mode', cwd=commands)
    is_ok(result.stdout, 'production\n', 'shared option')

with subtest('Making your application installable'):
    with tempfile.TemporaryDirectory() as tmp:
        result = command('-m', 'Pyjoyment', 'generate', 'app', 'MyApp', cwd=tmp)
        is_ok(result.returncode, 0, 'generated')
        project = os.path.join(tmp, 'my_app')
        for name in ('public', 'templates', 'my_app.yml'):
            shutil.move(os.path.join(project, name), os.path.join(project, 'MyApp'))
        shutil.copy(EXAMPLES.child('installable', 'MyApp', '__init__.py').to_str(), os.path.join(project, 'MyApp'))
        shutil.copy(EXAMPLES.child('installable', 'pyproject.toml').to_str(), project)
        result = command('-m', 'Pyjo.Prove', '-l', '-r', 't', cwd=project)
        like_ok(result.stdout, re.compile(r'Result: PASS'), 'tests pass')
        result = command('-m', 'MyApp', 'eval', '-v', 'app.home', cwd=project)
        is_ok(result.stdout, os.path.join(os.path.realpath(project), 'MyApp') + '\n', 'home in the package')
        result = command('-m', 'MyApp', 'generate', 'app', cwd=project)
        like_ok(result.stderr, re.compile(r'Unknown command "generate"'), 'no author commands')

with subtest('Proxy'):
    with cookbook('proxy') as t, remote(t.app.ua):
        t.get_ok('/').status_is(200).text_is('title', 'Pyjoyment documentation')
        t.get_ok('/en/latest/index.html').status_is(200).header_is('Server', 'PyjoProxy/1.0')
        t.text_is('h2', 'en/latest/index.html').text_is('div:last-child', 'PyjoProxy/1.0')

    app = Pyjoyment.new()

    @app.routes.put('/')
    def put(c):
        # Clone and modify request headers
        headers = c.req.headers.clone().dehop()
        headers.accept = 'application/json'
        tx = c.ua().build_tx('PUT', 'https://mojolicious.org', headers.to_dict())
        c.render(json=tx.req.headers.to_dict())

    with Pyjo.Test.Pyjo.new(app) as t:
        t.put_ok('/', {'Connection': 'close', 'X-Foo': 'bar'}).status_is(200)
        t.json_is('/Accept', 'application/json').json_is('/X-Foo', 'bar').json_hasnt('/Connection')

with subtest('JSONP'):
    app = Pyjoyment.new()
    HEADLINES = {'headlines': ['Pyjoyment released', 'Hello World!']}

    @app.routes.get('/headlines')
    def headlines(c):
        c.res.headers.access_control_allow_origin = 'https://example.com'
        c.render(json=HEADLINES)

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/headlines').status_is(200).header_is('Access-Control-Allow-Origin', 'https://example.com')
        t.json_is('/headlines/0', 'Pyjoyment released')

    with cookbook('jsonp') as t:
        t.get_ok('/headlines?callback=show').status_is(200)
        t.content_type_is('application/javascript').header_is('X-Content-Type-Options', 'nosniff')
        t.content_is('/**/show({"headlines":["Pyjoyment released","Hello World!"]});')
        t.get_ok('/headlines?callback=App.show').status_is(200).content_like(re.compile(r'^/\*\*/App\.show\('))
        for callback in ('alert(1)//', 'a b', '', '1a', 'a..b'):
            t.get_ok('/headlines', form={'callback': callback}).status_is(400).content_is('Invalid callback')
        t.get_ok('/headlines').status_is(400)

    result = command(EXAMPLES.child('jsonp.py').to_str(), 'get', '/headlines?callback=show')
    is_ok(result.stdout, '/**/show({"headlines":["Pyjoyment released","Hello World!"]});', 'command')

with subtest('JSON inline'):
    with cookbook('json_inline') as t:
        t.get_ok('/').status_is(200).text_is('title', 'Greeting')
        is_ok(Pyjo.JSON.from_json(t.tx.res.dom().at('script#state').text), {'greeting': 'Hello World!'}, 'state')

        greeting = '</script><!--<script>alert(1)</script>-->'
        t.get_ok('/', form={'greeting': greeting}).status_is(200).content_unlike(re.compile('<!--'))
        t.element_exists('script#state + script').element_exists('h1#greeting')
        is_ok(len(t.tx.res.dom().find('script')), 2, 'two elements')
        is_ok(Pyjo.JSON.from_json(t.tx.res.dom().at('script#state').text), {'greeting': greeting}, 'state kept whole')

with subtest('Hello World'):
    with cookbook('hello') as t:
        t.get_ok('/').status_is(200).content_is('Hello World!')

    result = command('-m', 'Pyjo', 'a({"text": "Hello World!"}).start()', 'get', '/')
    is_ok(result.stdout, 'Hello World!', 'one-liner')

BACKEND_PROCESS.terminate()
BACKEND_PROCESS.wait(30)

done_testing()
