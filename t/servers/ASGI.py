import Pyjo.IOLoop
import Pyjo.Reactor.Asyncio

from Pyjo.Test import *

import importlib.util
import os
import sys
import tempfile
import textwrap


# The servers of the dependency group "servers": uv run --only-group servers python -m Pyjo.Prove t/servers
if missing := [
    m for m in ('daphne', 'granian', 'hypercorn', 'uvicorn', 'websockets') if not importlib.util.find_spec(m)
]:
    plan(skip_all=f'needs the dependency group "servers", without {", ".join(missing)}')

# Pyjo.Server.ASGI needs a reactor that runs in the loop of the ASGI server, which Pyjo.Reactor.Poll, with a loop of its
# own, does not
if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
    plan(skip_all='needs Pyjo.Reactor.Asyncio, which runs in the loop of the ASGI server')

from websockets.exceptions import ConnectionClosed, InvalidStatus  # noqa: E402


# The servers in processes of their own
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Server = importlib.import_module('ServerProcess').Server

APP = """
import Pyjo.IOLoop
import Pyjo.Server.ASGI

asgi = Pyjo.Server.ASGI.new()
asgi.unsubscribe('request')


@asgi.on('request')
def request(asgi, tx):
    path = str(tx.req.url.path)

    # WebSocket
    if tx.is_websocket:
        if path == '/reject':
            tx.res.code = 403
            return tx.resume()
        tx.on('message', lambda ws, msg: ws.finish(4000, 'Bye!') if msg == 'quit' else ws.send(f'echo: {msg}'))
        tx.res.code = 101
        return tx.resume()

    # Response given later
    if path == '/later':

        def later(loop):
            tx.res.code = 200
            tx.res.body = b'later'
            tx.resume()

        return Pyjo.IOLoop.timer(0.1, later)

    # Streaming
    if path == '/stream':
        tx.res.code = 200
        tx.res.content.write_chunk(b'Hello ')

        def more(loop):
            tx.res.content.write_chunk(b'World!').write_chunk(b'')
            tx.resume()

        Pyjo.IOLoop.timer(0.1, more)
        return tx.resume()

    tx.res.code = 200
    tx.res.headers.content_type = 'text/plain'
    tx.res.body = f'{tx.req.method} {path} {tx.req.params.to_dict()} {tx.req.body!r}'.encode()
    tx.resume()


app = asgi.to_asgi_app()
"""

LITE = """
from Pyjoyment.Lite import app, get

get('/hello', {'text': 'Hello ASGI!'})

application = app.start()
"""

PYTHON = sys.executable
LOCAL = ['--host', '127.0.0.1', '--port', '{port}']
SERVERS = [
    ('uvicorn', [PYTHON, '-m', 'uvicorn', 'app:app', '--loop', 'asyncio', '--log-level', 'warning', *LOCAL]),
    ('uvicorn on uvloop', [PYTHON, '-m', 'uvicorn', 'app:app', '--loop', 'uvloop', '--log-level', 'warning', *LOCAL]),
    ('Hypercorn', [PYTHON, '-m', 'hypercorn', 'app:app', '--bind', '127.0.0.1:{port}']),
    (
        'Hypercorn on uvloop',
        [PYTHON, '-m', 'hypercorn', 'app:app', '--worker-class', 'uvloop', '--bind', '127.0.0.1:{port}'],
    ),
    ('Daphne', [PYTHON, '-m', 'daphne', '-b', '127.0.0.1', '-p', '{port}', 'app:app']),
    ('Granian', [PYTHON, '-m', 'granian', '--interface', 'asgi', 'app:app', *LOCAL]),
]


with tempfile.TemporaryDirectory() as dir:
    with open(os.path.join(dir, 'app.py'), 'w') as file:
        file.write(textwrap.dedent(APP))

    for name, command in SERVERS:
        if 'uvloop' in name and not importlib.util.find_spec('uvloop'):
            continue

        with subtest(name):
            server = Server(dir, command)
            try:
                status, headers, body = server.request('GET', '/foo?a=1')
                is_ok(status, 200, 'right status')
                is_ok(body, b"GET /foo {'a': '1'} b''", 'right content')
                # Daphne adds no Date header, and Pyjo.Server.ASGI leaves out its own for the servers that do
                is_ok(len(headers.get_all('Date') or []), 0 if name == 'Daphne' else 1, 'one Date header at most')

                type = {'Content-Type': 'application/x-www-form-urlencoded'}
                status, headers, body = server.request('POST', '/form', b'x=1&y=2', type)
                is_ok(body, b"POST /form {'x': '1', 'y': '2'} b'x=1&y=2'", 'form')

                status, headers, body = server.request('POST', '/chunked', iter([b'x=1', b'&y=2']), type, True)
                is_ok(body, b"POST /chunked {'x': '1', 'y': '2'} b'x=1&y=2'", 'chunked request')

                status, headers, body = server.request('GET', '/later')
                is_ok(body, b'later', 'response given later')

                status, headers, body = server.request('GET', '/stream')
                is_ok(body, b'Hello World!', 'streaming')

                status, headers, body = server.request('HEAD', '/foo')
                is_ok(status, 200, 'HEAD request')
                is_ok(body, b'', 'no content')

                with server.websocket('/ws') as ws:
                    ws.send('hi')
                    is_ok(ws.recv(10), 'echo: hi', 'WebSocket message')
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
                            # Daphne sends no reason with a close code
                            is_ok(e.rcvd.reason if e.rcvd else None, '' if name == 'Daphne' else 'Bye!', 'reason')

                def reject(server=server):
                    with server.websocket('/reject'):
                        pass

                throws_ok(reject, InvalidStatus, 'rejected handshake')
            except Exception:
                diag(server.output())
                raise
            finally:
                server.close()

    # The script of an application of Pyjoyment.Lite, whose command PYJO_ASGI tells, whatever the arguments of the
    # server are
    with open(os.path.join(dir, 'lite.py'), 'w') as file:
        file.write(textwrap.dedent(LITE))

    with subtest('Pyjoyment.Lite on uvicorn, detected with PYJO_ASGI'):
        os.environ['PYJO_ASGI'] = '1'
        try:
            server = Server(
                dir,
                [PYTHON, '-m', 'uvicorn', 'lite:application', '--loop', 'asyncio', '--log-level', 'warning', *LOCAL],
            )
        finally:
            del os.environ['PYJO_ASGI']
        try:
            status, headers, body = server.request('GET', '/hello')
            is_ok(status, 200, 'right status')
            is_ok(body, b'Hello ASGI!', 'right content')
        except Exception:
            diag(server.output())
            raise
        finally:
            server.close()

done_testing()
