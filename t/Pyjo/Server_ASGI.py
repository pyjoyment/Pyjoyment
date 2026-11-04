import Pyjo.IOLoop
import Pyjo.Reactor.Asyncio
import Pyjo.Server.ASGI

from Pyjo.Test import *
from Pyjo.WebSocket import WS_PING, WS_PONG

import importlib
import os
import re
import sys


# Pyjo.Server.ASGI needs a reactor that runs in the loop of the ASGI server, which Pyjo.Reactor.Poll, with a loop of its
# own, does not
if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
    plan(skip_all='needs Pyjo.Reactor.Asyncio, which runs in the loop of the ASGI server')

# The ASGI server of the tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
ASGIClient = importlib.import_module('ASGIClient')


def server(handler):
    asgi = Pyjo.Server.ASGI.new()
    asgi.unsubscribe('request')
    asgi.on('request', lambda asgi, tx: handler(tx))
    return asgi.to_asgi_app()


def hello(tx):
    tx.res.code = 200
    tx.res.headers.content_type = 'text/plain'
    tx.res.body = f'{tx.req.method} {tx.req.url.path}'.encode()
    tx.resume()


with subtest('Simple GET request'):
    app = server(hello)
    status, headers, body = ASGIClient.response(ASGIClient.run(app, *ASGIClient.http('GET', '/foo')))
    is_ok(status, 200, 'right status')
    is_ok(headers['content-type'], 'text/plain', 'right "Content-Type" value')
    is_ok(headers['content-length'], '8', 'right "Content-Length" value')
    ok('date' not in headers, 'no "Date" header, as the ASGI server adds one')
    is_ok(body, b'GET /foo', 'right content')

with subtest('Messages of a response'):
    app = server(hello)
    sent = ASGIClient.run(app, *ASGIClient.http('GET', '/foo'))
    is_deeply_ok(
        [m['type'] for m in sent],
        ['http.response.start', 'http.response.body', 'http.response.body'],
        'start, body and the end',
    )
    is_ok(sent[-1]['more_body'], False, 'last message')
    ok(all(isinstance(name, bytes) and name == name.lower() for name, value in sent[0]['headers']), 'lowercase names')

with subtest('Unknown status'):
    app = server(lambda tx: tx.resume())
    status, headers, body = ASGIClient.response(ASGIClient.run(app, *ASGIClient.http('GET', '/')))
    is_ok(status, 404, 'right status')
    is_ok(body, b'', 'no content')

with subtest('Query and form parameters'):
    got = {}

    def params(tx):
        got['params'] = tx.req.params.to_dict()
        got['body'] = tx.req.body
        hello(tx)

    app = server(params)
    scope, messages = ASGIClient.http(
        'POST',
        '/form',
        b'a=1',
        b'x=1&y=%C5%BC',
        [(b'content-type', b'application/x-www-form-urlencoded'), (b'content-length', b'12')],
        chunks=3,
    )
    status, headers, body = ASGIClient.response(ASGIClient.run(app, scope, messages))
    is_ok(status, 200, 'right status')
    is_deeply_ok(got['params'], {'a': '1', 'x': '1', 'y': 'ż'}, 'right parameters')
    is_ok(got['body'], b'x=1&y=%C5%BC', 'right content')

with subtest('Request body without Content-Length'):
    got = {}

    def length(tx):
        got['length'] = tx.req.headers.content_length
        got['encoding'] = tx.req.headers.transfer_encoding
        got['body'] = tx.req.body
        hello(tx)

    app = server(length)
    scope, messages = ASGIClient.http(
        'POST', '/', body=b'Hello World!', headers=[(b'transfer-encoding', b'chunked')], chunks=2
    )
    ASGIClient.run(app, scope, messages)
    is_ok(got['length'], '12', 'length of the whole body')
    is_ok(got['encoding'], None, 'no "Transfer-Encoding" value')
    is_ok(got['body'], b'Hello World!', 'right content')

with subtest('Empty request body without Content-Length'):
    got = {}

    def empty(tx):
        got['length'] = tx.req.headers.content_length
        got['finished'] = tx.req.is_finished
        hello(tx)

    app = server(empty)
    ASGIClient.run(app, *ASGIClient.http('GET', '/'))
    is_ok(got['length'], None, 'no "Content-Length" value')
    ok(got['finished'], 'request is finished')

with subtest('Addresses'):
    got = {}

    def addresses(tx):
        got.update(
            remote_address=tx.remote_address,
            remote_port=tx.remote_port,
            local_address=tx.local_address,
            local_port=tx.local_port,
        )
        hello(tx)

    app = server(addresses)
    ASGIClient.run(app, *ASGIClient.http('GET', '/', client=('192.0.2.1', 4242), server=('192.0.2.2', 8080)))
    is_deeply_ok(
        got,
        {'remote_address': '192.0.2.1', 'remote_port': 4242, 'local_address': '192.0.2.2', 'local_port': 8080},
        'right addresses',
    )

with subtest('HTTPS and root path'):
    got = {}

    def url(tx):
        got['abs'] = tx.req.url.to_abs()
        got['path'] = tx.req.url.path
        got['base'] = tx.req.url.base.path
        got['secure'] = tx.req.is_secure
        hello(tx)

    app = server(url)
    ASGIClient.run(app, *ASGIClient.http('GET', '/app/foo', b'a=b', scheme='https', root_path='/app'))
    is_ok(got['abs'], 'https://localhost:8000/app/foo?a=b', 'right absolute URL')
    is_ok(got['path'], 'foo', 'right path')
    is_ok(got['base'], '/app/', 'right base path')
    ok(got['secure'], 'secure')

with subtest('Path with escaped and non-ASCII characters'):
    got = {}

    def path(tx):
        got['path'] = tx.req.url.path
        got['parts'] = list(tx.req.url.path.parts)
        hello(tx)

    app = server(path)
    ASGIClient.run(app, *ASGIClient.http('GET', '/café/a/b', raw_path=b'/caf%C3%A9/a%2Fb'))
    is_ok(got['path'], '/caf%C3%A9/a/b', 'right path')
    is_deeply_ok(got['parts'], ['café', 'a', 'b'], 'right parts')

with subtest('Repeated headers'):
    got = {}

    def repeated(tx):
        got['cookie'] = tx.req.headers.cookie
        got['foo'] = tx.req.headers.header('X-Foo')
        got['cookies'] = [c.name for c in tx.req.cookies()]
        hello(tx)

    app = server(repeated)
    headers = [(b'cookie', b'a=1'), (b'cookie', b'b=2'), (b'x-foo', b'one'), (b'x-foo', b'two')]
    ASGIClient.run(app, *ASGIClient.http('GET', '/', headers=headers))
    is_ok(got['cookie'], 'a=1; b=2', 'cookies joined')
    is_ok(got['foo'], 'one, two', 'values joined')
    is_deeply_ok(got['cookies'], ['a', 'b'], 'right cookies')

with subtest('Response later'):

    def later(tx):
        def respond(loop):
            tx.res.code = 200
            tx.res.body = b'later'
            tx.resume()

        Pyjo.IOLoop.timer(0.05, respond)

    app = server(later)
    status, headers, body = ASGIClient.response(ASGIClient.run(app, *ASGIClient.http('GET', '/')))
    is_ok(status, 200, 'right status')
    is_ok(body, b'later', 'right content')

with subtest('Chunked response'):

    def chunked(tx):
        tx.res.code = 200
        tx.res.content.write_chunk(b'Hello ')

        def more(loop):
            tx.res.content.write_chunk(b'World!').write_chunk(b'')
            tx.resume()

        Pyjo.IOLoop.timer(0.05, more)
        tx.resume()

    app = server(chunked)
    sent = ASGIClient.run(app, *ASGIClient.http('GET', '/'))
    status, headers, body = ASGIClient.response(sent)
    is_ok(status, 200, 'right status')
    ok('transfer-encoding' not in headers, 'no "Transfer-Encoding" header')
    is_ok(body, b'Hello World!', 'content without framing')
    is_deeply_ok(
        [m['body'] for m in sent if m['type'] == 'http.response.body'],
        [b'Hello ', b'World!', b''],
        'content as it comes',
    )

with subtest('Dynamic response with Content-Length'):

    def dynamic(tx):
        tx.res.code = 200
        tx.res.headers.content_length = 12
        tx.res.content.write(b'Hello ', lambda content, offset: content.write(b'World!'))
        tx.resume()

    app = server(dynamic)
    status, headers, body = ASGIClient.response(ASGIClient.run(app, *ASGIClient.http('GET', '/')))
    is_ok(headers['content-length'], '12', 'right "Content-Length" value')
    is_ok(body, b'Hello World!', 'right content')

with subtest('HEAD request'):
    app = server(hello)
    sent = ASGIClient.run(app, *ASGIClient.http('HEAD', '/foo'))
    status, headers, body = ASGIClient.response(sent)
    is_ok(status, 200, 'right status')
    is_ok(headers['content-length'], '9', 'right "Content-Length" value')
    is_ok(body, b'', 'no content')

with subtest('Date of the application'):

    def dated(tx):
        tx.res.headers.date = 'Sun, 17 Aug 2008 16:27:35 GMT'
        hello(tx)

    app = server(dated)
    status, headers, body = ASGIClient.response(ASGIClient.run(app, *ASGIClient.http('GET', '/')))
    is_ok(headers['date'], 'Sun, 17 Aug 2008 16:27:35 GMT', 'right "Date" value')

with subtest('Finish event'):
    finished = []

    def finish(tx):
        tx.on('finish', lambda tx: finished.append(tx.is_finished))
        hello(tx)

    app = server(finish)
    ASGIClient.run(app, *ASGIClient.http('GET', '/'))
    is_deeply_ok(finished, [True], 'transaction is finished')

with subtest('WebSocket'):
    events = []

    def echo(tx):
        if not tx.is_websocket:
            return hello(tx)
        tx.on('message', lambda ws, msg: ws.send(f'echo: {msg!r}'))
        tx.on('finish', lambda ws, code, reason: events.append(('finish', code, reason)))
        tx.res.code = 101
        tx.resume()

    app = server(echo)
    messages = [
        {'type': 'websocket.receive', 'text': 'hi'},
        {'type': 'websocket.receive', 'bytes': b'\x00'},
        {'type': 'websocket.disconnect', 'code': 1000},
    ]
    sent = ASGIClient.run(app, *ASGIClient.websocket('/ws', messages))
    is_deeply_ok(
        sent,
        [
            {'type': 'websocket.accept', 'subprotocol': None},
            {'type': 'websocket.send', 'text': "echo: 'hi'"},
            {'type': 'websocket.send', 'text': "echo: b'\\x00'"},
        ],
        'right messages',
    )
    is_deeply_ok(events, [('finish', 1000, '')], 'right close code')

with subtest('WebSocket closed by the application'):
    events = []

    def close(tx):
        tx.on('message', lambda ws, msg: ws.finish(4000, 'Bye!'))
        tx.on('finish', lambda ws, code, reason: events.append((code, reason)))
        tx.res.code = 101
        tx.resume()

    app = server(close)
    messages = [{'type': 'websocket.receive', 'text': 'quit'}, {'type': 'websocket.disconnect', 'code': 4000}]
    sent = ASGIClient.run(app, *ASGIClient.websocket('/ws', messages))
    is_deeply_ok(sent[-1], {'type': 'websocket.close', 'code': 4000, 'reason': 'Bye!'}, 'right close message')
    is_deeply_ok(events, [(4000, '')], 'right close code')

with subtest('WebSocket drain callbacks'):

    def drain(tx):
        @tx.on('message')
        def message(ws, msg):
            ws.send('one', lambda ws: ws.send('two', lambda ws: ws.finish(4000)))

        tx.res.code = 101
        tx.resume()

    app = server(drain)
    messages = [{'type': 'websocket.receive', 'text': 'go'}, {'type': 'websocket.disconnect', 'code': 4000}]
    sent = ASGIClient.run(app, *ASGIClient.websocket('/ws', messages))
    is_deeply_ok(
        sent,
        [
            {'type': 'websocket.accept', 'subprotocol': None},
            {'type': 'websocket.send', 'text': 'one'},
            {'type': 'websocket.send', 'text': 'two'},
            {'type': 'websocket.close', 'code': 4000, 'reason': ''},
        ],
        'messages sent as the ones before are written',
    )

with subtest('WebSocket ping'):
    events = []

    def ping(tx):
        @tx.on('message')
        def message(ws, msg):
            ws.on('frame', lambda ws, frame: events.append(frame[4]))
            ws.send((1, 0, 0, 0, WS_PING, b'test'))

        tx.res.code = 101
        tx.resume()

    app = server(ping)
    messages = [{'type': 'websocket.receive', 'text': 'go'}, {'type': 'websocket.disconnect', 'code': 1000}]
    sent = ASGIClient.run(app, *ASGIClient.websocket('/ws', messages))
    is_deeply_ok(sent, [{'type': 'websocket.accept', 'subprotocol': None}], 'no message for the ping')
    is_deeply_ok(events[:1], [WS_PONG], 'pong of the server')

with subtest('WebSocket closed abnormally'):
    events = []

    def abnormal(tx):
        tx.on('finish', lambda ws, code, reason: events.append((code, reason)))
        tx.res.code = 101
        tx.resume()

    app = server(abnormal)
    ASGIClient.run(app, *ASGIClient.websocket('/ws', [{'type': 'websocket.disconnect', 'code': 1006}]))
    is_deeply_ok(events, [(1006, None)], 'abnormal closure')

with subtest('WebSocket with binary, JSON and fragmented messages'):

    def messages(tx):
        tx.on('json', lambda ws, data: ws.send({'json': {'got': data}}) if isinstance(data, dict) else None)
        tx.on('binary', lambda ws, data: ws.send({'binary': data[::-1]}))

        def fragments(ws):
            ws.send((0, 0, 0, 0, 1, b'Hello '))
            ws.send((1, 0, 0, 0, 0, b'World!'))

        tx.on('text', lambda ws, data: fragments(ws) if data == b'fragments' else None)
        tx.res.code = 101
        tx.resume()

    app = server(messages)
    sent = ASGIClient.run(
        app,
        *ASGIClient.websocket(
            '/ws',
            [
                {'type': 'websocket.receive', 'text': '{"a":1}'},
                {'type': 'websocket.receive', 'bytes': b'abc'},
                {'type': 'websocket.receive', 'text': 'fragments'},
                {'type': 'websocket.disconnect', 'code': 1000},
            ],
        ),
    )
    is_deeply_ok(
        sent[1:],
        [
            {'type': 'websocket.send', 'text': '{"got":{"a":1}}'},
            {'type': 'websocket.send', 'bytes': b'cba'},
            {'type': 'websocket.send', 'text': 'Hello World!'},
        ],
        'right messages',
    )

with subtest('WebSocket subprotocol'):
    got = {}

    def protocol(tx):
        got['proto'] = tx.with_protocols('v2', 'v1')
        tx.res.code = 101
        tx.resume()

    app = server(protocol)
    scope, messages = ASGIClient.websocket(
        '/ws', [{'type': 'websocket.disconnect', 'code': 1000}], [(b'sec-websocket-protocol', b'v1, v3')]
    )
    sent = ASGIClient.run(app, scope, messages)
    is_ok(got['proto'], 'v1', 'negotiated')
    is_deeply_ok(sent[0], {'type': 'websocket.accept', 'subprotocol': 'v1'}, 'accepted with subprotocol')

with subtest('WebSocket rejected'):
    events = []

    def reject(tx):
        tx.on('finish', lambda ws, code, reason: events.append(code))
        tx.res.code = 403
        tx.resume()

    app = server(reject)
    sent = ASGIClient.run(app, *ASGIClient.websocket('/ws'))
    is_deeply_ok(sent, [{'type': 'websocket.close', 'code': 1008}], 'closed before accept')
    is_deeply_ok(events, [1006], 'finished')

with subtest('Lifespan'):
    app = server(hello)
    sent = ASGIClient.run(app, {'type': 'lifespan'}, [{'type': 'lifespan.startup'}, {'type': 'lifespan.shutdown'}])
    is_deeply_ok(
        sent, [{'type': 'lifespan.startup.complete'}, {'type': 'lifespan.shutdown.complete'}], 'startup and shutdown'
    )

with subtest('Lifespan of the server of the application'):
    import Pyjo.Promise
    import Pyjoyment

    events = []
    application = Pyjoyment.new()
    application.log.level = 'fatal'
    application.hook('before_server_start', lambda server, app: events.append(type(server).__module__))

    @application.hook('after_server_stop')
    def after_server_stop(server, app):
        events.append('stopping')
        return Pyjo.Promise.timer(0.05).then(lambda *args: events.append('stopped'))

    app = Pyjo.Server.ASGI.new(app=application).to_asgi_app()
    sent = ASGIClient.run(app, {'type': 'lifespan'}, [{'type': 'lifespan.startup'}, {'type': 'lifespan.shutdown'}])
    is_deeply_ok(
        sent, [{'type': 'lifespan.startup.complete'}, {'type': 'lifespan.shutdown.complete'}], 'startup and shutdown'
    )
    is_deeply_ok(events, ['Pyjo.Server.ASGI', 'stopping', 'stopped'], 'hooks, and the cleanup waited for')

    # Failed
    application = Pyjoyment.new()
    application.log.level = 'fatal'

    @application.hook('before_server_start')
    def fail_start(server, app):
        raise Exception('No database')

    app = Pyjo.Server.ASGI.new(app=application).to_asgi_app()
    sent = ASGIClient.run(app, {'type': 'lifespan'}, [{'type': 'lifespan.startup'}])
    is_deeply_ok(sent, [{'type': 'lifespan.startup.failed', 'message': 'No database'}], 'startup failed')

    application = Pyjoyment.new()
    application.log.level = 'fatal'

    @application.hook('after_server_stop')
    def fail_stop(server, app):
        raise Exception('Still busy')

    app = Pyjo.Server.ASGI.new(app=application).to_asgi_app()
    sent = ASGIClient.run(app, {'type': 'lifespan'}, [{'type': 'lifespan.startup'}, {'type': 'lifespan.shutdown'}])
    is_deeply_ok(
        sent,
        [{'type': 'lifespan.startup.complete'}, {'type': 'lifespan.shutdown.failed', 'message': 'Still busy'}],
        'shutdown failed',
    )

with subtest('Unsupported connection type'):
    app = server(hello)
    throws_ok(
        lambda: ASGIClient.run(app, {'type': 'foo'}, []),
        re.compile(r'Unsupported ASGI connection type "foo"'),
        'right error',
    )

done_testing()
