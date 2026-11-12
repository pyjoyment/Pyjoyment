import os


os.environ['PYJO_NO_TLS'] = '1'
# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor that Pyjo.Reactor.detect gives

import Pyjo.App
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Server
import Pyjo.Server.Daemon
import Pyjo.Transaction.HTTP
import Pyjo.URL
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.File import tempdir
from Pyjo.Test import *

import contextlib
import gc
import io
import re
import socket

from unittest.mock import patch


class TestApp(Pyjoyment.object):
    def handler(self, tx):
        tx.res.code = 200
        tx.res.body = b'Hello TestApp!'
        tx.resume()


with subtest('Minimal application'):
    ua = Pyjo.UserAgent.new()
    ua.server.app = TestApp()
    tx = ua.get('/')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Hello TestApp!', 'right content')

with subtest('Timeouts'):
    with patch.dict(os.environ):
        os.environ.pop('PYJO_INACTIVITY_TIMEOUT', None)
        os.environ.pop('PYJO_KEEP_ALIVE_TIMEOUT', None)
        is_ok(Pyjo.Server.Daemon.new().inactivity_timeout, 30, 'right value')
        os.environ['PYJO_INACTIVITY_TIMEOUT'] = '25'
        is_ok(Pyjo.Server.Daemon.new().inactivity_timeout, 25, 'right value')
        os.environ['PYJO_INACTIVITY_TIMEOUT'] = '0'
        is_ok(Pyjo.Server.Daemon.new().inactivity_timeout, 0, 'right value')
        is_ok(Pyjo.Server.Daemon.new().keep_alive_timeout, 5, 'right value')
        os.environ['PYJO_KEEP_ALIVE_TIMEOUT'] = '25'
        is_ok(Pyjo.Server.Daemon.new().keep_alive_timeout, 25, 'right value')
        os.environ['PYJO_KEEP_ALIVE_TIMEOUT'] = '0'
        is_ok(Pyjo.Server.Daemon.new().keep_alive_timeout, 0, 'right value')

with subtest('Listen'):
    with patch.dict(os.environ):
        os.environ.pop('PYJO_LISTEN', None)
        # Not in Mojolicious: PORT, which is not set for the test
        os.environ.pop('PORT', None)
        is_deeply_ok(Pyjo.Server.Daemon.new().listen, ['http://*:3000'], 'right value')
        os.environ['PYJO_LISTEN'] = 'http://127.0.0.1:8080'
        is_deeply_ok(Pyjo.Server.Daemon.new().listen, ['http://127.0.0.1:8080'], 'right value')
        os.environ['PYJO_LISTEN'] = 'http://*:80,https://*:443'
        is_deeply_ok(Pyjo.Server.Daemon.new().listen, ['http://*:80', 'https://*:443'], 'right value')

        # Not in Mojolicious: PORT, of the platforms that tell the port to listen on, as Knative, Cloud Run and Heroku,
        # after PYJO_LISTEN
        os.environ['PORT'] = '8080'
        is_deeply_ok(Pyjo.Server.Daemon.new().listen, ['http://*:80', 'https://*:443'], 'PYJO_LISTEN first')
        os.environ.pop('PYJO_LISTEN')
        is_deeply_ok(Pyjo.Server.Daemon.new().listen, ['http://*:8080'], 'port of PORT')
        os.environ['PORT'] = ''
        is_deeply_ok(Pyjo.Server.Daemon.new().listen, ['http://*:3000'], 'empty PORT')
        os.environ['PORT'] = 'http'
        is_deeply_ok(Pyjo.Server.Daemon.new().listen, ['http://*:3000'], 'PORT that is not a port')

with subtest('Reverse proxy'):
    ok(not Pyjo.Server.Daemon.new().reverse_proxy, 'no reverse proxy')
    with patch.dict(os.environ, {'PYJO_REVERSE_PROXY': '1'}):
        ok(Pyjo.Server.Daemon.new().reverse_proxy, 'reverse proxy')

with subtest('Config'):
    app = Pyjoyment.new()
    is_ok(app.config('foo'), None, 'no value')
    is_deeply_ok(app.config(foo='bar').config(), {'foo': 'bar'}, 'right value')
    is_ok(app.config('foo'), 'bar', 'right value')
    del app.config()['foo']
    is_ok(app.config('foo'), None, 'no value')
    app.config(foo='bar', baz='yada')
    is_ok(app.config({'test': 23}).config()['test'], 23, 'right value')
    is_deeply_ok(app.config(), {'foo': 'bar', 'baz': 'yada', 'test': 23}, 'right value')

# Not in Mojolicious: the scripts and modules that Mojo has in t/mojo/lib, written into a temporary directory
tmp = tempdir()
tmp.child('myapp.py').spew(
    'import sys\n\nfrom Pyjoyment.Lite import app\n\napp.config(script=sys.argv[0])\n\napp.start()\n'
)
tmp.child('A.py').spew('class A:\n    pass\n')
tmp.child('LoaderException.py').spew('class LoaderException:\n    def new(self):\n        pass\n\n\nfoo = {\n')

with subtest('Loading'):
    daemon = Pyjo.Server.Daemon.new()
    path = tmp.child('myapp.py')
    app = daemon.load_app(path)
    is_ok(f'{type(app).__module__}.{type(app).__qualname__}', 'Pyjoyment.Lite.Pyjoyment_Lite', 'right reference')
    is_ok(daemon.app.config('script'), path.to_abs().to_str(), 'right script name')
    is_ok(type(daemon.build_app(f'{__name__}.TestApp')).__qualname__, 'TestApp', 'right reference')
    is_ok(type(daemon.app).__qualname__, 'TestApp', 'right reference')

with subtest('Load broken app'):
    throws_ok(
        lambda: Pyjo.Server.Daemon.new().load_app(tmp.child('A.py')),
        re.compile(r'did not return an application object'),
        'right error',
    )
    try:
        Pyjo.Server.Daemon.new().load_app(tmp.child('LoaderException.py'))
        err = ''
    except Exception as e:
        err = str(e)
    # Unlike Mojolicious: the message of Python for the syntax error
    like_ok(err, r"'\{' was never closed", 'right error')
    like_ok(err, r"^Can't load application", 'right error')

# Left out from Mojolicious: the subtest "Load app using module_true", a feature of Perl 5.38

with subtest('Load missing application class'):
    throws_ok(
        lambda: Pyjo.Server.Daemon.new().build_app('Pyjo.DoesNotExist'),
        re.compile(r'^Can\'t find application class "Pyjo\.DoesNotExist" in sys\.path'),
        'right error',
    )

with subtest('Invalid listen location'):
    throws_ok(
        lambda: Pyjo.Server.Daemon.new(listen=['fail']).start(),
        re.compile(r'Invalid listen location'),
        'right error',
    )

# Not in Mojolicious: a location of a Pyjo.URL object, which Mojo::URL->new takes as it stringifies a Mojo::URL
# Not in Mojolicious: a transaction as a context manager, which ends a handler with the default error after an
# exception, and keeps the connection
with subtest('Transaction as a context manager'):

    class App(Pyjo.App.object):
        def handler(self, tx):
            with tx:
                tx.res.code = 200
                tx.res.body = b'works!'
                if tx.req.url.path == '/die':
                    raise Exception('Something went wrong!')

    with Pyjo.Server.Daemon.new(app=App.new(), listen=['http://127.0.0.1'], silent=True) as daemon:
        port = daemon.start().ports()[0]
        ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
        tx = ua.get(f'http://127.0.0.1:{port}/')
        is_ok(tx.res.code, 200, 'right status')
        is_ok(tx.res.body, b'works!', 'right content')
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            tx = ua.get(f'http://127.0.0.1:{port}/die')
        is_ok(tx.res.code, 500, 'right status')
        is_ok(tx.res.body, b'Internal Server Error', 'right content')
        like_ok(err.getvalue(), r'^Something went wrong! at ', 'warning')
        tx = ua.get(f'http://127.0.0.1:{port}/')
        ok(tx.kept_alive, 'kept alive')
        is_ok(tx.res.body, b'works!', 'right content')

with subtest('Message of the listen location is flushed'):
    # The values of stdout when it is flushed
    class Stdout(io.StringIO):
        def __init__(self):
            super().__init__()
            self.flushed = []

        def flush(self):
            self.flushed.append(self.getvalue())

    with contextlib.redirect_stdout(Stdout()) as stdout, Pyjo.Server.Daemon.new(listen=['http://127.0.0.1']) as daemon:
        port = daemon.start().ports()[0]
    is_deeply_ok(stdout.flushed, [f'Web application available at http://127.0.0.1:{port}\n'], 'flushed')

with subtest('Listen location of a URL object'):
    url = Pyjo.URL.new().set(scheme='http', host='127.0.0.1')
    with Pyjo.Server.Daemon.new(listen=[url], silent=True) as daemon:
        port = daemon.start().ports()[0]
        is_ok(Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton).get(f'http://127.0.0.1:{port}/').res.code, 200, 'served')
    throws_ok(
        lambda: Pyjo.Server.Daemon.new(listen=[Pyjo.URL.new('fail')]).start(),
        re.compile(r'Invalid listen location "fail"'),
        'right error',
    )

with subtest('Transaction'):
    app = Pyjoyment.new()
    isa_ok(app.build_tx(), Pyjo.Transaction.HTTP.object, 'right transaction')

app = Pyjoyment.new()

ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)

with subtest('Moniker'):
    ua.server.app = app
    # Unlike Mojolicious: the moniker of Pyjoyment
    is_ok(ua.server.app.moniker, 'pyjoyment', 'right moniker')

# Silence
app.log.level = 'fatal'


@app.routes.post('/chunked')
def chunked(c):
    params = c.req.params.to_dict()
    chunks = []
    for key in sorted(params):
        chunks.append(params[key].encode())

    def cb(c):
        chunk = chunks.pop(0) if chunks else b''
        c.write_chunk(chunk, cb if chunk else None)

    cb(c)


local_address = local_port = remote_address = remote_port = None


@app.routes.post('/upload')
def upload(c):
    global local_address, local_port, remote_address, remote_port
    local_address = c.tx.local_address
    local_port = c.tx.local_port
    remote_address = c.tx.remote_address
    remote_port = c.tx.remote_port
    c.render(data=c.req.upload('file').slurp())


@app.routes.any('/port')
def port_action(c):
    c.render(text=c.req.url.to_abs().port)


@app.routes.any('/timeout')
def timeout_action(c):
    id = c.tx.connection
    c.res.headers.header('X-Connection-ID', id)
    c.render(text=f'{Pyjo.IOLoop.stream(id).timeout:g}')


app.routes.any('/*whatever', {'text': 'Whatever!'})

with subtest('Normal request'):
    tx = ua.get('/normal/')
    ok(tx.keep_alive, 'will be kept alive')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')

with subtest('Keep-alive request'):
    tx = ua.get('/normal/')
    ok(tx.keep_alive, 'will be kept alive')
    ok(tx.kept_alive, 'was kept alive')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')

with subtest('Non-keep-alive request'):
    tx = ua.get('/close/', {'Connection': 'close'})
    ok(not tx.keep_alive, 'will not be kept alive')
    ok(tx.kept_alive, 'was kept alive')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')

with subtest('Second non-keep-alive request'):
    tx = ua.get('/close/', {'Connection': 'close'})
    ok(not tx.keep_alive, 'will not be kept alive')
    ok(not tx.kept_alive, 'was not kept alive')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')

with subtest('HTTP/1.0 request'):
    tx = ua.build_tx('GET', '/normal/')
    tx.req.version = '1.0'
    tx = ua.start(tx)
    ok(not tx.keep_alive, 'will not be kept alive')
    is_ok(tx.res.version, '1.1', 'right version')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')

with subtest('POST request'):
    tx = ua.post('/fun/', {'Expect': 'fun'}, 'foo bar baz' * 128)
    ok(tx.connection is not None, 'has connection id')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')

with subtest('Concurrent requests'):
    tx = ua.post('/fun/', {'Expect': 'fun'}, 'foo bar baz' * 128)
    txs = []
    Pyjo.Promise.all(
        ua.get_p('/concurrent1/'),
        ua.post_p('/concurrent2/', {'Expect': 'fun'}, 'bar baz foo' * 128),
        ua.get_p('/concurrent3/'),
    ).then(lambda *results: txs.extend(result[0] for result in results)).wait()
    tx, tx2, tx3 = txs
    ok(tx.is_finished, 'transaction is finished')
    is_ok(tx.res.body, b'Whatever!', 'right content')
    ok(not tx.error, 'no error')
    ok(tx2.is_finished, 'transaction is finished')
    is_ok(tx2.res.body, b'Whatever!', 'right content')
    ok(not tx2.error, 'no error')
    ok(tx3.is_finished, 'transaction is finished')
    is_ok(tx3.res.body, b'Whatever!', 'right content')
    ok(not tx3.error, 'no error')

with subtest('Form with chunked response'):
    params = {}
    for i in range(1, 11):
        params[f'test{i}'] = i
    result = ''
    for key in sorted(params):
        result += str(params[key])
    tx = ua.post('/chunked', form=params)
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, result.encode(), 'right content')

with subtest('Upload'):
    result = ''
    tx = ua.post('/upload', form={'file': {'content': result}})
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, result.encode(), 'right content')
    ok(tx.local_address, 'has local address')
    ok(tx.local_port > 0, 'has local port')
    ok(tx.original_remote_address, 'has original remote address')
    ok(tx.remote_address, 'has remote address')
    ok(tx.remote_port > 0, 'has remote port')
    ok(local_address, 'has local address')
    ok(local_port > 0, 'has local port')
    ok(remote_address, 'has remote address')
    ok(remote_port > 0, 'has remote port')

with subtest('Timeout'):
    tx = ua.get('/timeout')
    ok(tx.keep_alive, 'will be kept alive')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'30', 'inactivity timeout was used for the request')
    is_ok(
        Pyjo.IOLoop.stream(tx.res.headers.header('X-Connection-ID')).timeout,
        5,
        'keep-alive timeout was assigned after the request',
    )

with subtest('Pipelined'):
    daemon = Pyjo.Server.Daemon.new(listen=['http://127.0.0.1'], silent=True)
    port = daemon.start().ports()[0]
    # Unlike Mojolicious: the moniker of Pyjo.HelloWorld
    is_ok(daemon.app.moniker, 'pyjo-hello_world', 'right moniker')
    buffer = b''

    @Pyjo.IOLoop.client(port=port)
    def id(loop, err, stream):
        @stream.on('read')
        def read(stream, chunk):
            global buffer
            buffer += chunk
            buffer, count = re.subn(rb' is working!.*is working!$', b'', buffer, flags=re.S)
            if count:
                Pyjo.IOLoop.remove(id)
                Pyjo.IOLoop.stop()

        stream.write(
            b'GET /pipeline1/ HTTP/1.1\x0d\x0a'
            b'Content-Length: 0\x0d\x0a\x0d\x0a'
            b'GET /pipeline2/ HTTP/1.1\x0d\x0a'
            b'Content-Length: 0\x0d\x0a\x0d\x0a'
        )

    Pyjo.IOLoop.start()
    # Unlike Mojolicious: Pyjo.HelloWorld answers "Your Pyjo is working!"
    like_ok(buffer, rb'Pyjo$', 'transactions were pipelined')

with subtest('Throttling'):
    daemon = Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], max_clients=23, silent=True)
    is_ok(len(daemon.acceptors), 0, 'no active acceptors')
    is_ok(len(daemon.start().start().acceptors), 1, 'one active acceptor')
    is_ok(daemon.ioloop.max_connections, 23, 'right value')
    id = daemon.acceptors[0]
    ok(Pyjo.IOLoop.acceptor(id), 'acceptor has been added')
    is_ok(len(daemon.stop().acceptors), 0, 'no active acceptors')
    ok(not Pyjo.IOLoop.acceptor(id), 'acceptor has been removed')
    is_ok(len(daemon.start().acceptors), 1, 'one active acceptor')
    id = daemon.acceptors[0]
    ok(Pyjo.IOLoop.acceptor(id), 'acceptor has been added')
    del daemon
    # Not in Mojolicious: PyPy frees the daemon when its garbage collector runs
    gc.collect()
    ok(not Pyjo.IOLoop.acceptor(id), 'acceptor has been removed')

with subtest('Single-accept and connection limit'):
    loop = Pyjo.IOLoop.new()
    daemon = Pyjo.Server.Daemon.new(
        app=app, ioloop=loop, listen=['http://127.0.0.1?single_accept=1'], max_clients=2, silent=True
    ).start()
    acceptor = loop.acceptor(daemon.acceptors[0])
    accepting = []

    @acceptor.on('accept')
    def accept(acceptor, handle):
        def tick(loop):
            accepting.append(acceptor.is_accepting)
            if len(accepting) == 2:
                loop.stop()

        loop.next_tick(tick)

    for _ in range(2):
        loop.client(lambda loop, err, stream: None, port=acceptor.port)
    loop.start()
    ok(accepting[0], 'accepting connections')
    ok(not accepting[1], 'connection limit reached')

with subtest('Destroy daemon while writing'):
    loop = Pyjo.IOLoop.new()
    app_ = Pyjoyment.new()
    app_.log.level = 'fatal'
    got = {}
    finished = []
    app_.hook('after_build_tx', lambda tx, app: tx.on('finish', lambda tx: finished.append(True)))

    @app_.routes.get('/')
    def destroy(c):
        c.render(text='x' * 1_000_000)
        got.pop('daemon')

    got['daemon'] = Pyjo.Server.Daemon.new(app=app_, ioloop=loop, listen=['http://127.0.0.1'], silent=True).start()
    port = loop.acceptor(got['daemon'].acceptors[0]).port

    # Unlike Mojolicious: the errors of the reactor, which Mojo warns of
    errors = []
    loop.reactor.on('error', lambda reactor, err: errors.append(str(err)))
    closed, timeout = [], []

    @loop.client(port=port)
    def client(loop, err, stream):
        @stream.on('close')
        def close(stream):
            closed.append(True)
            loop.stop()

        stream.on('read', lambda stream, chunk: None)
        stream.write(b'GET / HTTP/1.1\x0d\x0aConnection: close\x0d\x0a\x0d\x0a')

    loop.timer(5, lambda loop: (timeout.append(True), loop.stop()))
    loop.start()
    ok(closed, 'connection has been closed')
    ok(not timeout, 'no timeout')
    ok(finished, 'transaction has been finished')
    is_deeply_ok([e for e in errors if 'I/O watcher failed' in e], [], 'no exceptions')

# Not in Mojolicious: the rest of a request that has its response already, which the server reads before it closes the
# connection, so that the client gets the response
with subtest('Response before the end of the request'):
    loop = Pyjo.IOLoop.new()
    app_ = Pyjoyment.new()
    app_.log.level = 'fatal'
    app_.max_request_size = 10
    app_.routes.post('/').to(cb=lambda c: c.render(text='Too big' if c.req.is_limit_exceeded else 'Fine'))
    daemon = Pyjo.Server.Daemon.new(
        app=app_, ioloop=loop, listen=['http://127.0.0.1'], lingering_timeout=0.5, silent=True
    ).start()
    port = loop.acceptor(daemon.acceptors[0]).port

    def run(seconds):
        loop.timer(seconds, lambda loop: loop.stop())
        loop.start()

    def send(client, data):
        try:
            client.sendall(data)
            run(0.1)
            client.sendall(data)
            return None
        except OSError as e:
            return e

    with socket.create_connection(('127.0.0.1', port)) as client:
        client.sendall(b'POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n\r\n' + b'a' * 50)
        run(0.2)
        client.settimeout(5)
        response = b''
        while chunk := client.recv(4096):
            response += chunk
        like_ok(response, rb'(?s)^HTTP/1\.1 200 OK\r\n.*\r\n\r\nToo big$', 'response and end of the response')
        is_ok(send(client, b'a' * 25), None, 'rest of the request has been read')
        run(0.5)
        isa_ok(send(client, b'a' * 25), OSError, 'connection closed after the lingering timeout')

with subtest('Request limit'):
    daemon = Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], silent=True).start()
    port = daemon.ports()[0]
    is_ok(daemon.max_requests, 100, 'right value')
    daemon.max_requests = 2
    is_ok(daemon.max_requests, 2, 'right value')
    tx = ua.get(f'http://127.0.0.1:{port}/keep_alive/1')
    ok(tx.keep_alive, 'will be kept alive')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')
    tx = ua.get(f'http://127.0.0.1:{port}/keep_alive/1')
    ok(not tx.keep_alive, 'will not be kept alive')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, b'Whatever!', 'right content')

with subtest('File descriptor'):
    listen = socket.socket()
    listen.bind(('127.0.0.1', 0))
    listen.listen(5)
    fd = listen.fileno()
    daemon = Pyjo.Server.Daemon.new(app=app, listen=[f'http://127.0.0.1?fd={fd}'], silent=True).start()
    port = listen.getsockname()[1]
    is_ok(daemon.ports()[0], port, 'same port')
    tx = ua.get(f'http://127.0.0.1:{port}/port')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.res.body, str(port).encode(), 'right content')
    # The daemon owns the file descriptor
    listen.detach()

with subtest('No TLS support'):
    # Unlike Mojolicious: the message of Pyjo.IOLoop.Server, where Mojo names IO::Socket::SSL
    throws_ok(
        lambda: Pyjo.Server.Daemon.new(listen=['https://127.0.0.1'], silent=True).start(),
        re.compile(r'TLS support is disabled'),
        'right error',
    )

with subtest('Abstract methods'):
    throws_ok(
        lambda: Pyjo.Server.new().run(),
        re.compile(r'Method "run" not implemented by subclass'),
        'right error',
    )


# Not in Mojolicious: INT and TERM stop the server gracefully, a second INT immediately, a second TERM does not, QUIT
# immediately, and HUP is ignored
with subtest('Signals'):
    import signal
    import sys
    import time

    restored, refused = [], []

    def run(*signals, connect=False, poll=False, refuse=False):
        # An event loop of its own, which the connections of the other subtests do not keep from stopping gracefully
        finished, connections = [], []
        with (
            Pyjo.IOLoop.new() as loop,
            Pyjo.Server.Daemon.new(ioloop=loop, listen=['http://127.0.0.1'], silent=True) as daemon,
            Pyjo.UserAgent.new(ioloop=loop) as ua,
        ):
            daemon.start()
            loop.once('finish', lambda loop: finished.append(True))
            if connect:
                connections.append(socket.create_connection(('127.0.0.1', daemon.ports()[0])))
            # A client that requests every 0.1 seconds, on a connection that it keeps alive
            if poll:
                url = f'http://127.0.0.1:{daemon.ports()[0]}/'
                loop.recurring(0.1, lambda loop: ua.get(url, lambda ua, tx: None))
            for i, signum in enumerate(signals):
                loop.timer(0.2 * (i + 1), lambda loop, signum=signum: os.kill(os.getpid(), signum))
            # A new connection while the server stops gracefully, which the closed listen socket refuses
            if refuse:
                port = daemon.ports()[0]

                def new(loop):
                    try:
                        socket.create_connection(('127.0.0.1', port), timeout=1).close()
                        refused.append(False)
                    # A connection that comes while the socket closes is reset, as a refused one is
                    except (ConnectionRefusedError, ConnectionResetError):
                        refused.append(True)

                loop.timer(0.6, new)
            loop.timer(5, lambda loop: loop.stop())
            daemon.stop()
            daemon.run()
            for connection in connections:
                connection.close()
            restored.append(daemon.max_requests)
        return bool(finished)

    if sys.platform == 'win32':
        skip('no signals of POSIX', 12)
    else:
        ok(run(signal.SIGTERM), 'TERM stops gracefully')
        ok(run(signal.SIGINT), 'INT stops gracefully')
        ok(not run(signal.SIGQUIT), 'QUIT stops immediately')
        ok(run(signal.SIGHUP, signal.SIGTERM), 'HUP is ignored')
        started = time.monotonic()
        ok(run(signal.SIGINT, signal.SIGINT, connect=True), 'graceful stop before the second INT')
        ok(
            time.monotonic() - started < 2,
            'second INT stops immediately, with a connection that keeps it from stopping',
        )
        started = time.monotonic()
        ok(run(signal.SIGTERM, signal.SIGTERM, connect=True, refuse=True), 'graceful stop before the second TERM')
        ok(time.monotonic() - started > 4, 'second TERM does nothing')
        is_deeply_ok(refused, [True], 'a new connection is refused while it stops gracefully')
        started = time.monotonic()
        ok(run(signal.SIGTERM, poll=True), 'TERM stops gracefully, with a client that keeps requesting')
        ok(time.monotonic() - started < 2, 'a connection kept alive closes after its next response')
        is_ok(restored[-1], 100, 'max_requests is set back')

# Not in Mojolicious: the delay of a graceful stop, while the server serves as before and readiness fails, and a new
# connection is refused after it
with subtest('Shutdown delay'):
    import signal
    import sys
    import time

    # The singleton, as the one of every server, whose is_stopping readiness tells, and which the application uses
    def delayed(*signals):
        results = {}
        with (
            Pyjo.IOLoop.singleton as loop,
            Pyjo.Server.Daemon.new(listen=['http://127.0.0.1'], shutdown_delay=1, silent=True) as daemon,
            Pyjo.UserAgent.new(ioloop=loop) as ua,
        ):
            app = daemon.app = Pyjoyment.new()
            app.log.level = 'fatal'
            app.plugin('Health')
            port = daemon.start().ports()[0]
            started = time.monotonic()
            loop.once('finish', lambda loop: results.update(finish=time.monotonic() - started))
            # A connection that keeps the server from stopping, until the end
            connection = socket.create_connection(('127.0.0.1', port))
            for i, signum in enumerate(signals):
                loop.timer(0.2 * (i + 1), lambda loop, signum=signum: os.kill(os.getpid(), signum))

            def during(loop):
                results['stopping'] = loop.is_stopping
                for path in ('livez', 'readyz'):
                    ua.get(
                        f'http://127.0.0.1:{port}/{path}',
                        {'Connection': 'close'},
                        lambda ua, tx, path=path: results.update({path: tx.res.code}),
                    )

            def after(loop):
                try:
                    socket.create_connection(('127.0.0.1', port), timeout=1).close()
                    results['refused'] = False
                # A connection that comes while the socket closes is reset, as a refused one is
                except (ConnectionRefusedError, ConnectionResetError):
                    results['refused'] = True

            loop.timer(0.6, during)
            loop.timer(1.6, after)
            loop.timer(2, lambda loop: loop.stop())
            daemon.run()
            connection.close()
        results['elapsed'] = time.monotonic() - started
        return results

    if sys.platform == 'win32':
        skip('no signals of POSIX', 8)
    else:
        results = delayed(signal.SIGTERM)
        ok(results.get('stopping'), 'stopping during the delay')
        is_ok(results.get('livez'), 200, 'served during the delay')
        is_ok(results.get('readyz'), 503, 'not ready during the delay')
        ok(1 <= results.get('finish', 0) < 1.6, 'graceful stop after the delay')
        ok(results.get('refused'), 'a new connection is refused after the delay')
        results = delayed(signal.SIGINT, signal.SIGINT)
        ok('finish' not in results, 'second INT during the delay stops immediately')
        ok(results['elapsed'] < 1, 'without waiting for the delay')
        is_ok(Pyjo.Server.Daemon.new().shutdown_delay, 0, 'no delay by default')

# Not in Mojolicious: the end of the server, which the application learns once the event loop has stopped, and whose
# cleanup the server waits for, unless it stops immediately
with subtest('End of the server'):

    def end(stop):
        events = []
        with (
            Pyjo.IOLoop.new() as loop,
            Pyjo.Server.Daemon.new(ioloop=loop, listen=['http://127.0.0.1'], silent=True) as daemon,
        ):
            app = daemon.app = Pyjoyment.new()
            app.log.level = 'fatal'
            app.hook('before_server_start', lambda server, app: events.append('started'))

            def after_server_stop(server, app):
                events.append('running' if loop.is_running else 'stopped')
                promise = Pyjo.Promise.new()
                promise.ioloop = loop
                loop.timer(0.05, lambda loop: (events.append('cleaned up'), promise.resolve()))
                return promise

            app.hook('after_server_stop', after_server_stop)
            loop.timer(0.1, stop)
            daemon.run()
        return events

    is_deeply_ok(end(lambda loop: loop.stop_gracefully()), ['started', 'stopped', 'cleaned up'], 'graceful stop')
    is_deeply_ok(end(lambda loop: loop.stop()), ['started', 'stopped', 'cleaned up'], 'stop')
    if sys.platform == 'win32':
        skip('no signals of POSIX', 1)
    else:
        is_deeply_ok(end(lambda loop: os.kill(os.getpid(), signal.SIGQUIT)), ['started'], 'immediate stop')

done_testing()
