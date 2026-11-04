import Pyjo.App.FastCGI
import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Reactor.Asyncio
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.INI import dump as dump_ini
from Pyjo.Test import *
from Pyjo.Util import url_escape

import contextlib
import glob
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


# The applications of other frameworks, which Pyjoyment.Plugin.Mount mounts, of the dependency group "servers": uv run
# --only-group servers python -m Pyjo.Prove t/servers
if missing := [
    m for m in ('flask', 'mangum', 'mcp', 'starlette', 'waitress', 'websockets') if not importlib.util.find_spec(m)
]:
    plan(skip_all=f'needs the dependency group "servers", without {", ".join(missing)}')

import flask  # noqa: E402
import starlette.applications  # noqa: E402
import starlette.responses  # noqa: E402
import starlette.routing  # noqa: E402

from websockets.exceptions import ConnectionClosed, InvalidStatus  # noqa: E402


# The servers in processes of their own
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Server = importlib.import_module('ServerProcess').Server

# The examples of an application of Pyjoyment on WSGI and on ASGI, mounted in an application of Pyjoyment.Lite, on the
# WSGI and the ASGI servers
EXAMPLE = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'mount', 'mount_wsgi_inception.py')
EXAMPLE_ASGI = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'mount', 'mount_asgi_inception.py')

# The script of PHP of the example of php-fpm, which a FastCGI application runs, and php-fpm, as it is on PATH, as
# Debian names it with its version, or as Homebrew installs it
PHP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'mount', 'php', 'index.php'))
PHP_FPM = shutil.which('php-fpm') or next(
    (
        path
        for path in (*sorted(glob.glob('/usr/sbin/php-fpm*'), reverse=True), '/opt/homebrew/opt/php/sbin/php-fpm')
        if os.access(path, os.X_OK)
    ),
    None,
)

# The example of php-cgi, which runs php-cgi of PATH
EXAMPLE_PHP_CGI = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'mount', 'mount_cgi_php.py')
PHP_CGI = shutil.which('php-cgi')

# The example of a server of the MCP SDK
EXAMPLE_MCP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'mount', 'mount_mcp.py'))

# The example of Starlette on Mangum, an event function of AWS Lambda
EXAMPLE_MANGUM = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'mount', 'mount_lambda_mangum.py')
PYTHON = sys.executable
UWSGI = shutil.which('uwsgi', path=os.path.dirname(sys.executable))
GUNICORN = [PYTHON, '-m', 'gunicorn', 'served:application', '--bind', '127.0.0.1:{port}']
# The servers, and wsgi.multithread, wsgi.multiprocess and wsgi.run_once that they set
SERVERS = [
    ('Gunicorn', importlib.util.find_spec('gunicorn'), GUNICORN, [False, False, False]),
    (
        'Gunicorn with threads',
        importlib.util.find_spec('gunicorn'),
        [*GUNICORN, '--threads', '4'],
        [True, False, False],
    ),
    (
        'Gunicorn with workers',
        importlib.util.find_spec('gunicorn'),
        [*GUNICORN, '--workers', '2'],
        [False, True, False],
    ),
    (
        'uWSGI',
        UWSGI,
        [UWSGI, '--http-socket', '127.0.0.1:{port}', '--module', 'served:application'],
        [False, False, False],
    ),
    (
        'Waitress',
        True,
        [PYTHON, '-m', 'waitress', '--listen=127.0.0.1:{port}', 'served:application'],
        [True, False, False],
    ),
    (
        'Werkzeug',
        importlib.util.find_spec('werkzeug'),
        [
            PYTHON,
            '-c',
            'from werkzeug.serving import run_simple; from served import application; '
            "run_simple('127.0.0.1', {port}, application, threaded=True)",
        ],
        [True, False, False],
    ),
]
LOCAL = ['--host', '127.0.0.1', '--port', '{port}']
ASGI_SERVERS = [
    ('uvicorn', 'uvicorn', [PYTHON, '-m', 'uvicorn', 'served_asgi:application', '--log-level', 'warning', *LOCAL]),
    (
        'uvicorn on uvloop',
        'uvloop',
        [PYTHON, '-m', 'uvicorn', 'served_asgi:application', '--loop', 'uvloop', '--log-level', 'warning', *LOCAL],
    ),
    ('Hypercorn', 'hypercorn', [PYTHON, '-m', 'hypercorn', 'served_asgi:application', '--bind', '127.0.0.1:{port}']),
    ('Daphne', 'daphne', [PYTHON, '-m', 'daphne', '-b', '127.0.0.1', '-p', '{port}', 'served_asgi:application']),
    ('Granian', 'granian', [PYTHON, '-m', 'granian', '--interface', 'asgi', 'served_asgi:application', *LOCAL]),
]


def application(prefix, wsgi):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/').to(cb=lambda c: c.render(text='Hello from Pyjoyment!'))
    app.plugin('Mount', {prefix: wsgi})
    return app


with subtest('Flask'):
    hello = flask.Flask('hello')
    hello.logger.disabled = True

    @hello.get('/')
    def index():
        return f'Hello from Flask at {flask.url_for("index")}!'

    @hello.get('/hello/<name>')
    def name(name):
        return {'name': name, 'url': flask.url_for('name', name=name, _external=True)}

    @hello.post('/form')
    def form():
        return f'{flask.request.form["foo"]} and {flask.request.files["file"].read().decode()}'

    @hello.get('/redirect')
    def redirect():
        return flask.redirect(flask.url_for('index'))

    @hello.get('/stream')
    def stream():
        def body():
            yield 'one'
            yield 'two'

        return flask.Response(flask.stream_with_context(body()), mimetype='text/plain')

    @hello.get('/fail')
    def fail():
        raise RuntimeError('Something went wrong')

    t = Pyjo.Test.Pyjo.new(application('/flask', hello))
    t.get_ok('/').status_is(200).content_is('Hello from Pyjoyment!')
    t.get_ok('/flask/').status_is(200).content_is('Hello from Flask at /flask/!')
    t.get_ok('/flask/hello/%E2%99%A5').status_is(200).json_is('/name', '♥')
    t.json_like('/url', r'^http://127\.0\.0\.1:\d+/flask/hello/%E2%99%A5$')
    t.post_ok('/flask/form', form={'foo': 'bar', 'file': {'content': 'Hello!', 'filename': 'hello.txt'}})
    t.status_is(200).content_is('bar and Hello!')
    t.get_ok('/flask/redirect').status_is(302).header_is('Location', '/flask/')
    t.get_ok('/flask/stream').status_is(200).content_type_like(r'^text/plain').content_is('onetwo')
    t.get_ok('/flask/missing').status_is(404).content_like(r'Not Found')
    t.get_ok('/flask/fail').status_is(500).content_like(r'Internal Server Error')

with subtest('Starlette'):

    async def index(request):
        return starlette.responses.PlainTextResponse(f'Hello from Starlette at {request.url_for("index").path}!')

    async def name(request):
        name = request.path_params['name']
        return starlette.responses.JSONResponse({'name': name, 'url': str(request.url_for('name', name=name))})

    async def echo(request):
        return starlette.responses.PlainTextResponse(
            f'{(await request.body()).decode()} and {request.query_params["x"]}'
        )

    async def redirect(request):
        return starlette.responses.RedirectResponse(request.url_for('index').path)

    async def stream(request):
        async def body():
            yield 'one'
            yield 'two'

        return starlette.responses.StreamingResponse(body(), media_type='text/plain')

    async def fail(request):
        raise RuntimeError('Something went wrong')

    async def chat(websocket):
        await websocket.accept(subprotocol='chat')
        async for text in websocket.iter_text():
            if text == 'quit':
                return await websocket.close(4000, 'Bye!')
            await websocket.send_text(f'echo: {text} at {websocket.url.path}')

    async def denied(websocket):
        await websocket.send_denial_response(starlette.responses.PlainTextResponse('Denied!', status_code=401))

    async def closed(websocket):
        await websocket.close()

    async def pool(request):
        return starlette.responses.PlainTextResponse(f'Pool {request.state.pool}')

    lifespan_events = []

    @contextlib.asynccontextmanager
    async def lifespan(app):
        lifespan_events.append('startup')
        yield {'pool': 'connected'}
        lifespan_events.append('shutdown')

    hello = starlette.applications.Starlette(
        lifespan=lifespan,
        routes=[
            starlette.routing.Route('/', index, name='index'),
            starlette.routing.Route('/hello/{name}', name, name='name'),
            starlette.routing.Route('/echo', echo, methods=['POST']),
            starlette.routing.Route('/redirect', redirect),
            starlette.routing.Route('/stream', stream),
            starlette.routing.Route('/fail', fail),
            starlette.routing.WebSocketRoute('/ws', chat),
            starlette.routing.WebSocketRoute('/ws/denied', denied),
            starlette.routing.WebSocketRoute('/ws/closed', closed),
            starlette.routing.Route('/pool', pool),
        ],
    )

    t = Pyjo.Test.Pyjo.new(application('/starlette', hello))
    t.app.log.level = 'fatal'
    t.get_ok('/').status_is(200).content_is('Hello from Pyjoyment!')
    t.get_ok('/starlette/').status_is(200).content_is('Hello from Starlette at /starlette/!')
    t.get_ok('/starlette/hello/%E2%99%A5').status_is(200).json_is('/name', '♥')
    # Starlette does not escape a parameter of the path in url_for
    t.json_like('/url', r'^http://127\.0\.0\.1:\d+/starlette/hello/♥$')
    t.post_ok('/starlette/echo?x=1', b'Hello!').status_is(200).content_is('Hello! and 1')
    t.get_ok('/starlette/redirect').status_is(307).header_is('Location', '/starlette/')
    t.get_ok('/starlette/stream').status_is(200).content_type_like(r'^text/plain').content_is('onetwo')
    t.get_ok('/starlette/missing').status_is(404).content_like(r'Not Found')
    t.get_ok('/starlette/fail').status_is(500).content_like(r'Internal Server Error')
    t.websocket_ok('/starlette/ws', {'Sec-WebSocket-Protocol': 'chat'}).header_is('Sec-WebSocket-Protocol', 'chat')
    t.send_ok('hi').message_ok().message_is('echo: hi at /starlette/ws').send_ok('quit').finished_ok(4000)
    t.tx = t.ua.start(t.ua.build_websocket_tx('/starlette/ws/denied'))
    t.status_is(401).content_is('Denied!')
    t.tx = t.ua.start(t.ua.build_websocket_tx('/starlette/ws/closed'))
    t.status_is(403)

    # The lifespan, which the first request has started, and the end of the server shuts down
    t.get_ok('/starlette/pool').status_is(200).content_is('Pool connected')
    is_deeply_ok(lifespan_events, ['startup'], 'started')
    t.app.server_stopped(Pyjo.Server.Daemon.new()).wait()
    is_deeply_ok(lifespan_events, ['startup', 'shutdown'], 'shut down')

with subtest('PHP on php-fpm'):
    if PHP_FPM is None or sys.platform == 'win32':
        skip('needs php-fpm', 1)
    else:
        with tempfile.TemporaryDirectory() as dir:
            # A pool on a UNIX domain socket of the temporary directory, which takes no port
            sock = os.path.join(dir, 'fpm.sock')
            conf = os.path.join(dir, 'php-fpm.conf')
            with open(conf, 'w') as file:
                file.write(
                    dump_ini(
                        {
                            'global': {'error_log': '/dev/stderr', 'daemonize': False},
                            'www': {'listen': sock, 'pm': 'static', 'pm.max_children': 2},
                        }
                    )
                )
            with open(os.path.join(dir, 'php-fpm.log'), 'w+') as log:
                fpm = subprocess.Popen([PHP_FPM, '-n', '-y', conf, '-F'], stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 10
                    while not os.path.exists(sock) and fpm.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.05)

                    location = f'fcgi+unix://{url_escape(sock, rb"^A-Za-z0-9\-._~")}'
                    php = Pyjo.App.FastCGI.new(
                        url=location, env={'SCRIPT_FILENAME': PHP, 'DOCUMENT_ROOT': os.path.dirname(PHP)}
                    )
                    t = Pyjo.Test.Pyjo.new(application('/php', php))
                    t.get_ok('/php/foo/bar?x=1').status_is(200).content_type_like(r'^text/plain')
                    t.content_is('Hello PHP at /php for /foo/bar (GET /php/foo/bar?x=1)!\n')
                    t.header_like('X-Powered-By', r'^PHP/')
                    t.get_ok('/php').status_is(200).content_is('Hello PHP at /php for / (GET /php)!\n')
                    t.post_ok('/php/form', form={'a': '1'}).status_is(200)
                    t.content_is('Hello PHP at /php for /form (POST /php/form)!\n')
                    t.get_ok('/php/events').status_is(200).content_type_like(r'^text/event-stream')
                    t.content_is('data: 0\n\ndata: 1\n\ndata: 2\n\n')

                    # The scripts of the directory of the example
                    php = Pyjo.App.FastCGI.new(url=location, document_root=os.path.dirname(PHP))
                    t = Pyjo.Test.Pyjo.new(application('/php', php))
                    t.get_ok('/php/').status_is(200).content_is('Hello PHP at /php/index.php for  (GET /php/)!\n')
                    t.get_ok('/php/index.php/events').status_is(200).content_type_like(r'^text/event-stream')
                    t.content_is('data: 0\n\ndata: 1\n\ndata: 2\n\n')
                    t.get_ok('/php/phpinfo.php').status_is(200).content_like(r'<title>PHP [\d.]+ - phpinfo\(\)</title>')
                    t.get_ok('/php/missing.php').status_is(404)

                    # The scripts of the directory, and its index.php for every other path, as the one entry
                    php = Pyjo.App.FastCGI.new(url=location, document_root=os.path.dirname(PHP), script='index.php')
                    t = Pyjo.Test.Pyjo.new(application('/php', php))
                    t.get_ok('/php/2026/10/hello-world/').status_is(200)
                    t.content_is('Hello PHP at /php/index.php for  (GET /php/2026/10/hello-world/)!\n')
                    t.get_ok('/php/phpinfo.php').status_is(200).content_like(r'<title>PHP [\d.]+ - phpinfo\(\)</title>')

                    # A connection kept, which takes one of the workers of the pool, for the requests one after another
                    with Pyjo.App.FastCGI.new(
                        url=f'{location}?max_connections=1', document_root=os.path.dirname(PHP)
                    ) as php:
                        t = Pyjo.Test.Pyjo.new(application('/php', php))
                        t.get_ok('/php/').status_is(200).content_is('Hello PHP at /php/index.php for  (GET /php/)!\n')
                        t.post_ok('/php/index.php/form', form={'a': '1'}).status_is(200)
                        t.content_is('Hello PHP at /php/index.php for /form (POST /php/index.php/form)!\n')
                        t.get_ok('/php/index.php/events').status_is(200).content_is('data: 0\n\ndata: 1\n\ndata: 2\n\n')
                        t.get_ok('/php/missing.php').status_is(404)
                        t.get_ok('/php/').status_is(200).content_is('Hello PHP at /php/index.php for  (GET /php/)!\n')
                        is_ok(len(php._queues[Pyjo.IOLoop.singleton]), 1, 'one connection kept')
                except Exception:
                    log.seek(0)
                    diag(log.read())
                    raise
                finally:
                    fpm.terminate()
                    fpm.wait(10)

with subtest('PHP on php-cgi'):
    if PHP_CGI is None or sys.platform == 'win32':
        skip('needs php-cgi', 1)
    else:
        # The scripts of the directory of the example, a process of php-cgi for each request
        t = Pyjo.Test.Pyjo.new(Pyjo.File.path(EXAMPLE_PHP_CGI).to_abs())
        t.get_ok('/').status_is(200).content_is('I ♥ Pyjoyment!')
        # Not X-Powered-By, which the php.ini of setup-php leaves out, as php-cgi reads it
        t.get_ok('/php/').status_is(200).content_type_like(r'^text/plain')
        t.content_is('Hello PHP at /php/index.php for  (GET /php/)!\n')
        t.get_ok('/php/index.php/foo/bar?x=1').status_is(200)
        t.content_is('Hello PHP at /php/index.php for /foo/bar (GET /php/index.php/foo/bar?x=1)!\n')
        t.post_ok('/php/index.php/form', form={'a': '1'}).status_is(200)
        t.content_is('Hello PHP at /php/index.php for /form (POST /php/index.php/form)!\n')
        t.get_ok('/php/index.php/events').status_is(200).content_type_like(r'^text/event-stream')
        t.content_is('data: 0\n\ndata: 1\n\ndata: 2\n\n')
        t.get_ok('/php/phpinfo.php').status_is(200).content_like(r'<title>PHP [\d.]+ - phpinfo\(\)</title>')
        t.get_ok('/php/missing.php').status_is(404)
        t.get_ok('/php/php-fpm.conf').status_is(404)

with subtest('Starlette on Mangum on Lambda'):
    if sys.platform == 'win32':
        skip('Lambda functions need pipes that the event loop watches', 1)
    else:
        # The event function of the example, which runs an event loop of its own in its process, which does not get
        # PYTHONWARNINGS or PYTHONDEVMODE, as the servers do not, as the warnings of Mangum are not ours
        saved = {name: os.environ.pop(name) for name in ('PYTHONDEVMODE', 'PYTHONWARNINGS') if name in os.environ}
        try:
            t = Pyjo.Test.Pyjo.new(Pyjo.File.path(EXAMPLE_MANGUM).to_abs())
            t.get_ok('/').status_is(200).content_is('I ♥ Pyjoyment!')
            t.get_ok('/mangum/').status_is(200).content_type_like(r'^text/plain')
            t.content_is('Hello Starlette for / on Mangum!')
            t.get_ok('/mangum/foo/bar').status_is(200).content_is('Hello Starlette for /foo/bar on Mangum!')
        finally:
            os.environ.update(saved)

with subtest('MCP SDK'):
    import asyncio

    from mcp import Client

    # The tools of the server for clients at the same time, each with its calls
    async def tools(url, clients=1, calls=1):
        async def client():
            async with Client(url) as mcp:
                names = [tool.name for tool in (await mcp.list_tools()).tools]
                results = [(await mcp.call_tool('add', {'a': n, 'b': 2})).structured_content for n in range(calls)]
                return names, results

        return await asyncio.gather(*(client() for _ in range(clients)))

    # The MCP SDK needs the event loop of asyncio, which Pyjo.Reactor.Poll does not run
    if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
        skip('needs Pyjo.Reactor.Asyncio, as the MCP SDK runs on asyncio', 1)
    else:
        with tempfile.TemporaryDirectory() as dir:
            # The example on the daemon, whose end shuts the lifespan of the server down, the manager of its sessions
            server = Server(dir, [PYTHON, EXAMPLE_MCP, 'daemon', '-l', 'http://127.0.0.1:{port}'])
            try:
                status, headers, body = server.request('GET', '/')
                is_ok(body, 'I ♥ Pyjoyment!'.encode(), 'right content')
                is_deeply_ok(
                    asyncio.run(tools(f'http://127.0.0.1:{server.port}/mcp/')),
                    [(['add'], [{'result': 2}])],
                    'tool of the MCP server',
                )
            except Exception:
                diag(server.output())
                raise
            finally:
                server.close()
            with open(os.path.join(dir, 'server.log')) as file:
                log = file.read()
            # Windows stops a server immediately with Ctrl-Break
            if sys.platform == 'win32':
                skip('no graceful stop on Windows', 1)
            else:
                like_ok(log, r'session manager shutting down', 'lifespan shut down')

            # Without sessions, as the guide Mounting has it, on the workers of the pre-forking server
            if not hasattr(os, 'fork'):
                skip('no os.fork', 1)
            else:
                with open(EXAMPLE_MCP) as file:
                    script = file.read().replace(
                        "mcp.streamable_http_app(streamable_http_path='/')",
                        "mcp.streamable_http_app(streamable_http_path='/', stateless_http=True)",
                    )
                with open(os.path.join(dir, 'stateless.py'), 'w') as file:
                    file.write(script)
                server = Server(dir, [PYTHON, 'stateless.py', 'prefork', '-w', '4', '-l', 'http://127.0.0.1:{port}'])
                try:
                    is_deeply_ok(
                        asyncio.run(tools(f'http://127.0.0.1:{server.port}/mcp/', clients=8, calls=5)),
                        [(['add'], [{'result': n + 2} for n in range(5)])] * 8,
                        'tools for eight clients on four workers',
                    )
                except Exception:
                    diag(server.output())
                    raise
                finally:
                    server.close()

with tempfile.TemporaryDirectory() as dir:
    shutil.copy(EXAMPLE, os.path.join(dir, 'inception.py'))

    # The example, with a WSGI application that gives the flags of the WSGI server, which the servers run
    with open(os.path.join(dir, 'served.py'), 'w') as file:
        file.write("""\
import json

from inception import app, application


def flags(environ, start_response):
    start_response('200 OK', [('Content-Type', 'application/json')])
    keys = ('wsgi.multithread', 'wsgi.multiprocess', 'wsgi.run_once')
    return [json.dumps([bool(environ[key]) for key in keys]).encode()]


app.plugin('Mount', {'/flags': flags})
""")

    for name, available, command, model in SERVERS:
        if not available:
            continue

        with subtest(f'Pyjoyment on WSGI mounted in Pyjoyment.Lite on {name}'):
            os.environ['PYJO_WSGI'] = '1'
            try:
                server = Server(dir, command)
            finally:
                del os.environ['PYJO_WSGI']
            try:
                status, headers, body = server.request('GET', '/')
                is_ok(status, 200, 'right status')
                is_ok(body, 'I ♥ Pyjoyment!'.encode(), 'right content')

                status, headers, body = server.request('GET', '/wsgi')
                is_ok(status, 200, 'right status')
                is_ok(body, b'Hello Pyjoyment at /wsgi on WSGI!', 'right content')

                status, headers, body = server.request('GET', '/wsgi/pyjo/pyjo.css')
                is_ok(status, 200, 'right status')
                is_ok(headers['Content-Type'], 'text/css', 'static file')

                status, headers, body = server.request('GET', '/wsgi/foo')
                is_ok(status, 404, 'not found')

                # The flags of the WSGI server for the WSGI application mounted in the application of Pyjoyment
                status, headers, body = server.request('GET', '/flags')
                is_ok(status, 200, 'right status')
                is_deeply_ok(json.loads(body), model, 'flags of the WSGI server')
            except Exception:
                diag(server.output())
                raise
            finally:
                server.close()

    shutil.copy(EXAMPLE_ASGI, os.path.join(dir, 'inception_asgi.py'))

    # The example, with routes of the inner application whose response and chunks come from timers of the event loop of
    # the ASGI server
    with open(os.path.join(dir, 'served_asgi.py'), 'w') as file:
        file.write("""\
import Pyjo.IOLoop

import inception_asgi

from inception_asgi import application, hello


@hello.routes.get('/later')
def later(c):
    c.render_later()
    Pyjo.IOLoop.timer(0.01, lambda loop: c.render(text='Hello later!'))


@hello.routes.get('/chunks')
def chunks(c):
    def write(n):
        if n < 3:
            Pyjo.IOLoop.timer(0.01, lambda loop: c.write_chunk(f'{n}'.encode(), lambda c: write(n + 1)))
        else:
            c.finish()

    write(0)


# An ASGI application with a lifespan, which writes its startup and its shutdown to a file of the directory of the server
async def lifespan(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            with open('lifespan.log', 'a') as file:
                file.write(f'{message["type"]}\\n')
            if message['type'] == 'lifespan.startup':
                scope['state']['greeting'] = 'Hello'
                await send({'type': 'lifespan.startup.complete'})
            else:
                return await send({'type': 'lifespan.shutdown.complete'})
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
    await send({'type': 'http.response.body', 'body': f'{scope["state"]["greeting"]} with a lifespan!'.encode()})


inception_asgi.app.plugin('Mount', {'/lifespan': lifespan})


@hello.routes.websocket('/echo')
def echo(c):
    @c.on('message')
    def message(c, msg):
        if msg == 'quit':
            return c.finish(4000, 'Bye!')
        c.send(f'echo: {msg} at {c.url_for("/")}')
""")

    for name, module, command in ASGI_SERVERS:
        if not importlib.util.find_spec(module):
            continue

        with subtest(f'Pyjoyment on ASGI mounted in Pyjoyment.Lite on {name}'):
            # Pyjo.Server.ASGI needs a reactor that runs in the loop of the ASGI server, which Pyjo.Reactor.Poll, with a
            # loop of its own, does not
            if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
                skip('needs Pyjo.Reactor.Asyncio, which runs in the loop of the ASGI server', 1)
                continue
            log = os.path.join(dir, 'lifespan.log')
            if os.path.exists(log):
                os.remove(log)
            os.environ['PYJO_ASGI'] = '1'
            try:
                server = Server(dir, command)
            finally:
                del os.environ['PYJO_ASGI']
            try:
                status, headers, body = server.request('GET', '/')
                is_ok(status, 200, 'right status')
                is_ok(body, 'I ♥ Pyjoyment!'.encode(), 'right content')

                status, headers, body = server.request('GET', '/lifespan')
                is_ok(body, b'Hello with a lifespan!', 'state of the lifespan')

                status, headers, body = server.request('GET', '/asgi')
                is_ok(status, 200, 'right status')
                is_ok(body, b'Hello Pyjoyment at /asgi on ASGI!', 'right content')

                status, headers, body = server.request('GET', '/asgi/pyjo/pyjo.css')
                is_ok(status, 200, 'right status')
                is_ok(headers['Content-Type'], 'text/css', 'static file')

                status, headers, body = server.request('GET', '/asgi/foo')
                is_ok(status, 404, 'not found')

                status, headers, body = server.request('GET', '/asgi/later')
                is_ok(body, b'Hello later!', 'response given later')

                status, headers, body = server.request('GET', '/asgi/chunks')
                is_ok(body, b'012', 'chunks given later')

                with server.websocket('/asgi/echo') as ws:
                    ws.send('hi')
                    is_ok(ws.recv(10), 'echo: hi at /asgi', 'WebSocket message')
                    ws.send('quit')

                    # Granian does not deliver the websocket.close of the application while a receive is waiting
                    if name == 'Granian':
                        throws_ok(lambda: ws.recv(2), TimeoutError, 'close not delivered')
                    else:
                        try:
                            ws.recv(10)
                            fail_ok('closed by the application')
                        except ConnectionClosed as e:
                            is_ok(e.rcvd.code if e.rcvd else None, 4000, 'closed by the application')

                def missing(server=server):
                    with server.websocket('/asgi/missing'):
                        pass

                throws_ok(missing, InvalidStatus, 'rejected handshake')
            except Exception:
                diag(server.output())
                raise
            finally:
                server.close()

            # The lifespan of the mounted application shuts down with the one of the ASGI server, which Daphne does not
            # have
            with open(log) as file:
                is_deeply_ok(
                    file.read().split(),
                    ['lifespan.startup'] if name == 'Daphne' else ['lifespan.startup', 'lifespan.shutdown'],
                    'startup and shutdown',
                )

done_testing()
