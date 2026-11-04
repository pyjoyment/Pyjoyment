import Pyjo.App.ASGI
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Reactor
import Pyjo.Server.ASGI
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjoyment

from Pyjo.JSON import encode_json
from Pyjo.Test import *
from Pyjo.WebSocket import WS_PING, WS_PONG

import asyncio
import concurrent.futures
import http.client
import json
import os
import re


# The connection scope of the request, and the messages of the body that the application receives
async def echo(scope, receive, send):
    messages = []
    while True:
        message = await receive()
        messages.append({**message, 'body': message['body'].decode('latin-1')})
        if not message['more_body']:
            break
    values = {
        **scope,
        'headers': [[name.decode('latin-1'), value.decode('latin-1')] for name, value in scope['headers']],
        'raw_path': scope['raw_path'].decode('latin-1'),
        'query_string': scope['query_string'].decode('latin-1'),
    }
    body = encode_json({**values, 'messages': messages})
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'application/json')]})
    await send({'type': 'http.response.body', 'body': body})


# The value of a promise, which the event loop fulfills
def result(promise):
    values = []
    promise.then(lambda *args: values.extend(args)).wait()
    return values[0] if len(values) == 1 else values


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


def application(asgi, prefix='/prefix'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    route = app.routes.any(prefix)
    route.partial = True
    route.to(app=asgi)
    return app


def header(scope, name):
    return [value for key, value in scope['headers'] if key == name]


with subtest('Scope'):
    with Pyjo.App.ASGI.new(app=echo) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/foo/bar?a=1&b=%20', {'X-Foo': 'bar'}).status_is(200)
        scope = t.tx.res.json()
        is_ok(scope['type'], 'http', 'right type')
        is_deeply_ok(scope['asgi'], {'version': '3.0', 'spec_version': '2.4'}, 'right version')
        is_ok(scope['http_version'], '1.1', 'right HTTP version')
        is_ok(scope['method'], 'GET', 'right method')
        is_ok(scope['scheme'], 'http', 'right scheme')
        is_ok(scope['root_path'], '', 'no root path')
        is_ok(scope['path'], '/foo/bar', 'right path')
        is_ok(scope['raw_path'], '/foo/bar', 'right raw path')
        is_ok(scope['query_string'], 'a=1&b=%20', 'right query')
        is_deeply_ok(scope['server'], ['127.0.0.1', t.ua.server.url().port], 'right server')
        is_ok(scope['client'][0], '127.0.0.1', 'right client address')
        ok(isinstance(scope['client'][1], int), 'client port')
        is_deeply_ok(header(scope, 'x-foo'), ['bar'], 'right header')
        is_deeply_ok(header(scope, 'content-length'), [], 'no content length')
        is_deeply_ok(scope['messages'], [{'type': 'http.request', 'body': '', 'more_body': False}], 'no body')

with subtest('Headers'):
    with Pyjo.App.ASGI.new(app=echo) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/', {'X-Foo': ['a', 'b']}).status_is(200)
        is_deeply_ok(header(t.tx.res.json(), 'x-foo'), ['a', 'b'], 'every value')

with subtest('Body'):
    with Pyjo.App.ASGI.new(app=echo) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.post_ok('/', {'Content-Type': 'text/plain'}, b'Hello!').status_is(200)
        scope = t.tx.res.json()
        is_deeply_ok(header(scope, 'content-type'), ['text/plain'], 'right content type')
        is_deeply_ok(header(scope, 'content-length'), ['6'], 'right content length')
        is_deeply_ok(scope['messages'], [{'type': 'http.request', 'body': 'Hello!', 'more_body': False}], 'right body')

        # Chunked
        tx = t.ua.build_tx('POST', '/')
        tx.req.content.write_chunk(b'Hello').write_chunk(b' World!').write_chunk(b'')
        t.request_ok(tx).status_is(200)
        scope = t.tx.res.json()
        is_deeply_ok(header(scope, 'content-length'), ['12'], 'right content length')
        is_deeply_ok(header(scope, 'transfer-encoding'), [], 'no transfer encoding')
        is_ok(''.join(message['body'] for message in scope['messages']), 'Hello World!', 'right body')

        # Multipart
        t.post_ok('/', form={'foo': 'bar', 'file': {'content': 'Hello!', 'filename': 'hello.txt'}}).status_is(200)
        scope = t.tx.res.json()
        like_ok(header(scope, 'content-type')[0], r'^multipart/form-data; boundary=', 'right content type')
        body = ''.join(message['body'] for message in scope['messages'])
        is_deeply_ok(header(scope, 'content-length'), [str(len(body))], 'right content length')
        like_ok(body, r'(?s)name=\"file\"; filename=\"hello\.txt\".*Hello!', 'right file')

with subtest('Body in a file'):
    max_memory_size = os.environ.get('PYJO_MAX_MEMORY_SIZE')
    os.environ['PYJO_MAX_MEMORY_SIZE'] = '10'
    try:
        with Pyjo.App.ASGI.new(app=echo) as app:
            t = Pyjo.Test.Pyjo.new(app)
            body = b'0123456789' * 100000
            t.post_ok('/', body).status_is(200)
            messages = t.tx.res.json('/messages')
            ok(len(messages) > 1, 'body in more than one message')
            ok(all(message['more_body'] for message in messages[:-1]), 'more body')
            is_ok(messages[-1]['more_body'], False, 'end of the body')
            ok(''.join(message['body'] for message in messages) == body.decode(), 'right body')
    finally:
        if max_memory_size is None:
            del os.environ['PYJO_MAX_MEMORY_SIZE']
        else:
            os.environ['PYJO_MAX_MEMORY_SIZE'] = max_memory_size

with subtest('Path of a route'):
    with Pyjo.App.ASGI.new(app=echo) as asgi:
        t = Pyjo.Test.Pyjo.new(application(asgi))
        t.get_ok('/prefix').status_is(200)
        is_ok(t.tx.res.json('/root_path'), '/prefix', 'right root path')
        is_ok(t.tx.res.json('/path'), '/prefix', 'right path')
        t.get_ok('/prefix/foo/bar/?x=1').status_is(200)
        is_ok(t.tx.res.json('/root_path'), '/prefix', 'right root path')
        is_ok(t.tx.res.json('/path'), '/prefix/foo/bar/', 'right path')
        is_ok(t.tx.res.json('/query_string'), 'x=1', 'right query')

        # Not after a part of the path that does not end with a slash, which cannot be root_path
        t.get_ok('/prefixx').status_is(404)
        t.get_ok('/prefix.json').status_is(404)

        # Escaped, as UTF-8, and as they are on the wire in the raw path
        t.get_ok('/prefix/a%20b/%E2%99%A5/%2F').status_is(200)
        is_ok(t.tx.res.json('/path'), '/prefix/a b/♥//', 'right path')
        is_ok(t.tx.res.json('/raw_path'), '/prefix/a%20b/%E2%99%A5/%2F', 'right raw path')

    # Placeholders
    with Pyjo.App.ASGI.new(app=echo) as asgi:
        t = Pyjo.Test.Pyjo.new(application(asgi, '/users/:id'))
        t.get_ok('/users/%E2%99%A5/foo').status_is(200)
        is_ok(t.tx.res.json('/root_path'), '/users/♥', 'right root path')
        is_ok(t.tx.res.json('/path'), '/users/♥/foo', 'right path')

with subtest('Base path'):
    # A reverse proxy with a path prefix, which the application moves from the path to the base path
    with Pyjo.App.ASGI.new(app=echo) as asgi:
        app = application(asgi)

        @app.hook('before_dispatch')
        def before_dispatch(c):
            url = c.req.url
            url.base.path.parse('/outer/')
            url.path.leading_slash = False
            url.path.parts.pop(0)

        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/outer/prefix/foo?x=1').status_is(200)
        is_ok(t.tx.res.json('/root_path'), '/outer/prefix', 'right root path')
        is_ok(t.tx.res.json('/path'), '/outer/prefix/foo', 'right path')


async def whole(scope, receive, send):
    headers = [(b'content-type', b'text/plain'), (b'x-foo', b'a'), (b'x-foo', b'b')]
    await send({'type': 'http.response.start', 'status': 201, 'headers': headers})
    await send({'type': 'http.response.body', 'body': b'Hello World!'})


async def stream(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
    for chunk in (b'one', b'', b'two', b'three'):
        await send({'type': 'http.response.body', 'body': chunk, 'more_body': True})
    await send({'type': 'http.response.body', 'body': b''})


async def length(scope, receive, send):
    headers = [(b'content-type', b'text/plain'), (b'content-length', b'6')]
    await send({'type': 'http.response.start', 'status': 200, 'headers': headers})
    await send({'type': 'http.response.body', 'body': b'one', 'more_body': True})
    await send({'type': 'http.response.body', 'body': b'two'})


with subtest('Response'):
    with Pyjo.App.ASGI.new(app=whole) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(201).content_is('Hello World!')
        is_deeply_ok(t.tx.res.headers.every_header('X-Foo'), ['a', 'b'], 'right headers')
        is_deeply_ok(raw(t, 'GET'), (201, '12', None, b'Hello World!'), 'whole response')
        is_deeply_ok(raw(t, 'HEAD'), (201, '12', None, b''), 'whole response without content')

    with Pyjo.App.ASGI.new(app=stream) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('onetwothree')
        is_deeply_ok(raw(t, 'GET'), (200, None, 'chunked', b'onetwothree'), 'chunked response')
        is_deeply_ok(raw(t, 'HEAD'), (200, None, 'chunked', b''), 'chunked response without content')

        # Without the chunked transfer encoding in HTTP/1.0
        tx = t.ua.build_tx('GET', '/')
        tx.req.version = '1.0'
        t.request_ok(tx).status_is(200).content_is('onetwothree')
        is_ok(t.tx.keep_alive, False, 'no keep-alive')

    with Pyjo.App.ASGI.new(app=length) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('onetwo')
        is_ok(t.tx.keep_alive, True, 'keep-alive')
        is_deeply_ok(raw(t, 'GET'), (200, '6', None, b'onetwo'), 'response with its length')


async def fail(scope, receive, send):
    raise RuntimeError('Something went wrong')


async def silent(scope, receive, send):
    pass


async def started(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': []})


async def twice(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': []})
    await send({'type': 'http.response.start', 'status': 200, 'headers': []})


async def unknown(scope, receive, send):
    await send({'type': 'http.response.unknown'})


async def broken(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
    await send({'type': 'http.response.body', 'body': b'one', 'more_body': True})
    raise RuntimeError('Broken body')


async def after(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 500, 'headers': [(b'content-type', b'text/plain')]})
    await send({'type': 'http.response.body', 'body': b'Failed'})
    raise RuntimeError('After the response')


async def unfinished(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
    await send({'type': 'http.response.body', 'body': b'one', 'more_body': True})


with subtest('Errors'):
    for application_, error in (
        (fail, r'Something went wrong'),
        (silent, r'returned without a response'),
        (started, r'returned without a response'),
        (twice, r'"http\.response\.start" has already been sent'),
        (unknown, r'Unknown ASGI message "http\.response\.unknown"'),
    ):
        with Pyjo.App.ASGI.new(app=application_) as app:
            app.log.level = 'fatal'
            t = Pyjo.Test.Pyjo.new(app)
            with app.log.capture('error') as messages:
                t.get_ok('/').status_is(500).content_is('Internal Server Error')
            like_ok(str(messages), error, f'right error of {application_.__name__}')

    # The connection is closed, as the response has started
    for application_, error in ((broken, r'Broken body'), (unfinished, r'without the end of its response')):
        with Pyjo.App.ASGI.new(app=application_) as app:
            app.log.level = 'fatal'
            t = Pyjo.Test.Pyjo.new(app)
            with app.log.capture('error') as messages:
                is_deeply_ok(
                    raw(t, 'GET'), (200, None, 'chunked', None), f'incomplete response of {application_.__name__}'
                )
            like_ok(str(messages), error, f'right error of {application_.__name__}')

    # The response that has ended is written
    with Pyjo.App.ASGI.new(app=after) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(500).content_is('Failed')
        like_ok(str(messages), r'After the response', 'right error of after')

    # The exception page of Pyjoyment, in a route
    with Pyjo.App.ASGI.new(app=fail) as asgi:
        t = Pyjo.Test.Pyjo.new(application(asgi))
        t.get_ok('/prefix').status_is(500).content_like(r'Something went wrong')

    throws_ok(
        lambda: Pyjo.App.ASGI.new().handler(Pyjo.Transaction.HTTP.new()),
        re.compile(r'^No ASGI application'),
        'no application',
    )

with subtest('Connection closed'):
    sent = []
    events = []

    async def endless(scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        for _ in range(100):
            await send({'type': 'http.response.body', 'body': b'x' * 1024, 'more_body': True})
            sent.append(1)
        events.append((await receive())['type'])

    with Pyjo.App.ASGI.new(app=endless) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.ua.max_response_size = 10000
        tx = t.ua.get('/')
        is_ok(tx.error['message'], 'Maximum message size exceeded', 'right error')
        while not events:
            Pyjo.IOLoop.one_tick()
        is_ok(len(sent), 100, 'send does nothing once the connection is gone')
        is_deeply_ok(events, ['http.disconnect'], 'disconnect')

with subtest('Disconnect after the response'):
    events = []

    async def disconnect(scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'Hello!'})
        events.append((await receive())['type'])

    with Pyjo.App.ASGI.new(app=disconnect) as app:
        t = Pyjo.Test.Pyjo.new(app)
        t.get_ok('/').status_is(200).content_is('Hello!')
        while not events:
            Pyjo.IOLoop.one_tick()
        is_deeply_ok(events, ['http.disconnect'], 'disconnect')


# A WebSocket that echoes its messages, closes as the client asks and keeps the messages that it receives
async def chat(scope, receive, send):
    events = scope.get('events', [])
    events.append(await receive())
    path = scope['path'][len(scope['root_path']) :]
    protocols = scope['subprotocols']
    await send({'type': 'websocket.accept', 'subprotocol': protocols[0] if protocols else None})
    if path == '/scope':
        values = {
            **scope,
            'headers': [[name.decode('latin-1'), value.decode('latin-1')] for name, value in scope['headers']],
            'raw_path': scope['raw_path'].decode('latin-1'),
            'query_string': scope['query_string'].decode('latin-1'),
        }
        await send({'type': 'websocket.send', 'text': encode_json(values).decode()})
    while True:
        message = await receive()
        received.append(message)
        if message['type'] == 'websocket.disconnect':
            return
        if (text := message.get('text')) is not None:
            if text.startswith('close'):
                _, code, reason = text.split(' ', 2)
                await send({'type': 'websocket.close', 'code': int(code), 'reason': reason})
                await send({'type': 'websocket.send', 'text': 'ignored'})
            else:
                await send({'type': 'websocket.send', 'text': f'echo: {text}'})
        else:
            await send({'type': 'websocket.send', 'bytes': message['bytes'][::-1]})


received = []


# The response of a WebSocket handshake that is not established
def handshake(t, path):
    t.tx = t.ua.start(t.ua.build_websocket_tx(path))
    ok(not t.tx.is_websocket, 'not a WebSocket')
    return t


with subtest('WebSocket scope'):
    with Pyjo.App.ASGI.new(app=chat) as app:
        t = Pyjo.Test.Pyjo.new(app)
        del received[:]
        t.websocket_ok('/scope?a=1', {'X-Foo': 'bar', 'Sec-WebSocket-Protocol': 'foo, bar'}).message_ok()
        scope = json.loads(t.message[1])
        is_ok(scope['type'], 'websocket', 'right type')
        is_deeply_ok(scope['asgi'], {'version': '3.0', 'spec_version': '2.4'}, 'right version')
        is_ok(scope['http_version'], '1.1', 'right HTTP version')
        ok('method' not in scope, 'no method')
        is_ok(scope['scheme'], 'ws', 'right scheme')
        is_ok(scope['root_path'], '', 'no root path')
        is_ok(scope['path'], '/scope', 'right path')
        is_ok(scope['raw_path'], '/scope', 'right raw path')
        is_ok(scope['query_string'], 'a=1', 'right query')
        is_deeply_ok(scope['server'], ['127.0.0.1', t.ua.server.url().port], 'right server')
        is_ok(scope['client'][0], '127.0.0.1', 'right client address')
        is_deeply_ok(header(scope, 'x-foo'), ['bar'], 'right header')
        is_deeply_ok(header(scope, 'upgrade'), ['websocket'], 'right upgrade header')
        is_deeply_ok(scope['subprotocols'], ['foo', 'bar'], 'right subprotocols')
        is_deeply_ok(scope['extensions'], {'websocket.http.response': {}}, 'response of HTTP')
        t.header_is('Sec-WebSocket-Protocol', 'foo').finish_ok()
        while not received:
            Pyjo.IOLoop.one_tick()
        is_deeply_ok(received, [{'type': 'websocket.disconnect', 'code': 1005, 'reason': ''}], 'disconnect')

with subtest('WebSocket'):
    with Pyjo.App.ASGI.new(app=chat) as app:
        t = Pyjo.Test.Pyjo.new(app)
        del received[:]
        t.websocket_ok('/').header_is('Sec-WebSocket-Protocol', None)
        t.send_ok('hi').message_ok().message_is('echo: hi')
        t.send_ok('I ♥ Pyjoyment!').message_ok().message_is('echo: I ♥ Pyjoyment!')
        t.send_ok({'binary': b'abc'}).message_ok().message_is(b'cba')
        t.finish_ok(4001, 'bye').finished_ok(4001)
        while len(received) < 4:
            Pyjo.IOLoop.one_tick()
        is_deeply_ok(
            received,
            [
                {'type': 'websocket.receive', 'text': 'hi'},
                {'type': 'websocket.receive', 'text': 'I ♥ Pyjoyment!'},
                {'type': 'websocket.receive', 'bytes': b'abc'},
                {'type': 'websocket.disconnect', 'code': 4001, 'reason': 'bye'},
            ],
            'right messages',
        )

        # Closed by the application, which sends nothing more
        del received[:]
        t.websocket_ok('/').send_ok('close 4000 Done!').finished_ok(4000)
        while len(received) < 2:
            Pyjo.IOLoop.one_tick()
        is_deeply_ok(
            received,
            [
                {'type': 'websocket.receive', 'text': 'close 4000 Done!'},
                {'type': 'websocket.disconnect', 'code': 4000, 'reason': 'Done!'},
            ],
            'right messages',
        )

    # In a route
    with Pyjo.App.ASGI.new(app=chat) as asgi:
        t = Pyjo.Test.Pyjo.new(application(asgi))
        t.websocket_ok('/prefix/scope').message_ok().json_message_is('/root_path', '/prefix')
        t.json_message_is('/path', '/prefix/scope').send_ok('hi').message_ok().message_is('echo: hi').finish_ok()

with subtest('WebSocket rejected'):

    async def reject(scope, receive, send):
        await receive()
        await send({'type': 'websocket.close'})

    async def deny(scope, receive, send):
        await receive()
        await send({'type': 'websocket.http.response.start', 'status': 401, 'headers': [(b'x-test', b'yes')]})
        await send({'type': 'websocket.http.response.body', 'body': b'Denied', 'more_body': True})
        await send({'type': 'websocket.http.response.body', 'body': b'!'})

    with Pyjo.App.ASGI.new(app=reject) as app:
        handshake(Pyjo.Test.Pyjo.new(app), '/').status_is(403).content_is('')

    with Pyjo.App.ASGI.new(app=deny) as app:
        handshake(Pyjo.Test.Pyjo.new(app), '/').status_is(401).header_is('X-Test', 'yes').content_is('Denied!')

    with Pyjo.App.ASGI.new(app=deny) as asgi:
        handshake(Pyjo.Test.Pyjo.new(application(asgi)), '/prefix').status_is(401).content_is('Denied!')

with subtest('WebSocket errors'):

    async def silent_ws(scope, receive, send):
        await receive()

    async def fail_ws(scope, receive, send):
        await receive()
        raise Exception('Something went wrong')

    async def early(scope, receive, send):
        await receive()
        await send({'type': 'websocket.send', 'text': 'Too early'})

    for application_, error in (
        (fail_ws, r'Something went wrong'),
        (silent_ws, r'returned without a response'),
        (early, r'"websocket\.send" before "websocket\.accept"'),
    ):
        with Pyjo.App.ASGI.new(app=application_) as app:
            app.log.level = 'fatal'
            t = Pyjo.Test.Pyjo.new(app)
            with app.log.capture('error') as messages:
                handshake(t, '/').status_is(500).content_is('Internal Server Error')
            like_ok(str(messages), error, f'right error of {application_.__name__}')

    # The WebSocket is closed with the status of an error of the server
    async def broken_ws(scope, receive, send):
        await receive()
        await send({'type': 'websocket.accept'})
        await receive()
        raise Exception('Broken WebSocket')

    async def returned(scope, receive, send):
        await receive()
        await send({'type': 'websocket.accept'})
        await receive()

    for application_, error in (
        (broken_ws, r'Broken WebSocket'),
        (returned, r'returned without closing its WebSocket'),
    ):
        with Pyjo.App.ASGI.new(app=application_) as app:
            app.log.level = 'fatal'
            t = Pyjo.Test.Pyjo.new(app)
            with app.log.capture('error') as messages:
                t.websocket_ok('/').send_ok('hi').finished_ok(1011)
            like_ok(str(messages), error, f'right error of {application_.__name__}')

    # The WebSocket that the application has closed
    async def closed(scope, receive, send):
        await receive()
        await send({'type': 'websocket.accept'})
        await send({'type': 'websocket.close', 'code': 4000})
        raise Exception('After the close')

    with Pyjo.App.ASGI.new(app=closed) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.websocket_ok('/').finished_ok(4000)
        like_ok(str(messages), r'After the close', 'right error of closed')

    # The error comes after the end of the close of the application, as the close of a reactor of uvloop ends before
    # the rejection of the coroutine, or after the peer has gone, which is not an error of the server
    ended = []

    async def closed_and_ended(scope, receive, send):
        await receive()
        await send({'type': 'websocket.accept'})
        await send({'type': 'websocket.close', 'code': 4000})
        try:
            while (await receive())['type'] != 'websocket.disconnect':
                pass
            raise Exception('After the end of the close')
        finally:
            ended.append(True)

    async def gone(scope, receive, send):
        await receive()
        await send({'type': 'websocket.accept'})
        try:
            while (await receive())['type'] != 'websocket.disconnect':
                pass
            raise Exception('After the peer has gone')
        finally:
            ended.append(True)

    for application_, test in (
        (closed_and_ended, lambda t: t.websocket_ok('/').finished_ok(4000)),
        (gone, lambda t: t.websocket_ok('/').finish_ok()),
    ):
        ended.clear()
        with Pyjo.App.ASGI.new(app=application_) as app:
            app.log.level = 'fatal'
            t = Pyjo.Test.Pyjo.new(app)
            with app.log.capture('error') as messages:
                test(t)
                while not ended:
                    Pyjo.IOLoop.one_tick()

                # The rejection of the coroutine, a few ticks after its end
                Pyjo.IOLoop.timer(0.1, lambda loop: Pyjo.IOLoop.stop())
                Pyjo.IOLoop.start()
            if application_ is gone:
                unlike_ok(str(messages), r'After the peer has gone', 'no error after the peer has gone')
            else:
                like_ok(str(messages), r'After the end of the close', 'right error after the end of the close')

    # The exception page of Pyjoyment, in a route
    with Pyjo.App.ASGI.new(app=fail_ws) as asgi:
        handshake(Pyjo.Test.Pyjo.new(application(asgi)), '/prefix').status_is(500).content_like(r'Something went')

with subtest('WebSocket closed before its handshake'):
    events = []

    async def waiting(scope, receive, send):
        if scope['type'] != 'websocket':
            return
        events.append((await receive())['type'])
        events.append(await receive())
        await send({'type': 'websocket.accept'})
        events.append('accepted')

    with Pyjo.App.ASGI.new(app=waiting) as app:
        t = Pyjo.Test.Pyjo.new(app)
        port = t.ua.server.nb_url().port

        @Pyjo.IOLoop.client(address='127.0.0.1', port=port)
        def client(loop, err, stream):
            stream.write(
                b'GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n'
                b'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n',
                lambda stream: Pyjo.IOLoop.timer(0.05, lambda loop: stream.close()),
            )

        while len(events) < 3:
            Pyjo.IOLoop.one_tick()
        is_deeply_ok(
            events,
            ['websocket.connect', {'type': 'websocket.disconnect', 'code': 1006, 'reason': ''}, 'accepted'],
            'disconnect, and send does nothing',
        )

with subtest('WebSocket pings'):

    async def quiet(scope, receive, send):
        await receive()
        await send({'type': 'websocket.accept'})
        while (await receive())['type'] != 'websocket.disconnect':
            pass

    # A WebSocket of a server whose inactivity timeout is shorter than the time without messages
    def quiet_for(app, seconds):
        os.environ['PYJO_INACTIVITY_TIMEOUT'] = '0.3'
        try:
            t = Pyjo.Test.Pyjo.new(app)
            frames = []
            t.websocket_ok('/').tx.on('frame', lambda ws, frame: frames.append(frame[4]))
            timer = Pyjo.IOLoop.timer(seconds, lambda loop: loop.stop())
            t.tx.on('finish', lambda *args: Pyjo.IOLoop.stop())
            Pyjo.IOLoop.start()
            Pyjo.IOLoop.remove(timer)
        finally:
            del os.environ['PYJO_INACTIVITY_TIMEOUT']
        return t, frames

    with Pyjo.App.ASGI.new(app=quiet, ping_interval=0.05, ping_timeout=0.2) as app:
        t, frames = quiet_for(app, 0.6)
        ok(len(frames) > 5, 'pings')
        is_deeply_ok(set(frames), {WS_PING}, 'only pings')
        ok(not t.tx.is_finished, 'kept alive')
        t.finish_ok().finished_ok(1005)

    with Pyjo.App.ASGI.new(app=quiet, ping_interval=None) as app:
        app.log.level = 'fatal'
        t, frames = quiet_for(app, 2)
        is_deeply_ok(frames, [], 'no pings')
        ok(t.tx.is_finished, 'closed by the inactivity timeout')


# The lifespan of an application, whose startup and shutdown come later, with the state of the requests
def lifespan(events, failed=None):
    async def application(scope, receive, send):
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                events.append(message['type'])
                await Pyjo.Promise.timer(0.05)
                if message['type'] == 'lifespan.startup':
                    if failed is not None:
                        return await send({'type': 'lifespan.startup.failed', 'message': failed})
                    scope['state']['pool'] = 'connected'
                    await send({'type': 'lifespan.startup.complete'})
                else:
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
        await receive()
        state = scope['state']
        body = f'{state.get("pool")} {state.get("changed")}'.encode()
        state['changed'] = True
        events.append('request')
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': body})

    return application


with subtest('Lifespan'):
    events = []
    app = Pyjo.App.ASGI.new(app=lifespan(events))
    t = Pyjo.Test.Pyjo.new(app)
    is_deeply_ok(events, [], 'not started')
    t.get_ok('/').status_is(200).content_is('connected None')
    t.get_ok('/').status_is(200).content_is('connected None')
    is_deeply_ok(events, ['lifespan.startup', 'request', 'request'], 'started by the first request, once')

    # Shut down
    app.close()
    is_deeply_ok(events, ['lifespan.startup', 'request', 'request', 'lifespan.shutdown'], 'shut down')
    ok(app.shutdown() is None, 'not started again')

    # Started again, as of the next request, and by the end of the server
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/').status_is(200).content_is('connected None')
    promise = app.server_stopped(Pyjo.Server.Daemon.new())
    promise.wait()
    is_deeply_ok(events[-3:], ['lifespan.startup', 'request', 'lifespan.shutdown'], 'shut down by the server')
    is_ok(app.server_stopped(Pyjo.Server.Daemon.new()), None, 'nothing to shut down')
    app.close()

with subtest('Lifespan started before the requests'):
    events = []
    with Pyjo.App.ASGI.new(app=lifespan(events)) as app:
        t = Pyjo.Test.Pyjo.new(app)
        app.startup().wait()
        is_deeply_ok(events, ['lifespan.startup'], 'started')
        t.get_ok('/').status_is(200).content_is('connected None')
        is_deeply_ok(events, ['lifespan.startup', 'request'], 'request after the startup')
    is_deeply_ok(events, ['lifespan.startup', 'request', 'lifespan.shutdown'], 'shut down by the end of the block')

    # Requests that wait for the startup together
    events = []
    with Pyjo.App.ASGI.new(app=lifespan(events)) as app:
        t = Pyjo.Test.Pyjo.new(app)
        codes = []
        for _ in range(3):
            t.ua.get('/', lambda ua, tx: codes.append(tx.res.code))
        while len(codes) < 3:
            Pyjo.IOLoop.one_tick()
        is_deeply_ok(codes, [200, 200, 200], 'all served')
        is_deeply_ok(events, ['lifespan.startup', 'request', 'request', 'request'], 'one startup')

with subtest('Lifespan failed'):
    events = []
    with Pyjo.App.ASGI.new(app=lifespan(events, failed='No database')) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)
        with app.log.capture('error') as messages:
            t.get_ok('/').status_is(500).content_is('Internal Server Error')
            t.get_ok('/').status_is(500)
        like_ok(str(messages), r'failed to start: No database', 'right error')
        is_deeply_ok(events, ['lifespan.startup'], 'no request')

    # In a route
    with Pyjo.App.ASGI.new(app=lifespan([], failed='No database')) as asgi:
        t = Pyjo.Test.Pyjo.new(application(asgi))
        t.get_ok('/prefix').status_is(500).content_like(r'No database')

with subtest('Application without lifespan'):

    async def unsupported(scope, receive, send):
        assert scope['type'] == 'http'
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': str('state' in scope).encode()})

    async def returned(scope, receive, send):
        if scope['type'] != 'http':
            return
        await unsupported(scope, receive, send)

    for application_ in (unsupported, returned):
        with Pyjo.App.ASGI.new(app=application_) as app:
            app.log.level = 'fatal'
            t = Pyjo.Test.Pyjo.new(app)
            t.get_ok('/').status_is(200).content_is('False')
            ok(app.shutdown() is not None, f'lifespan of {application_.__name__}')

with subtest('Pyjoyment on ASGI'):
    # An application of Pyjoyment as the ASGI application, whose response and content come in later ticks of the event
    # loop
    inner = Pyjoyment.new()
    inner.log.level = 'fatal'

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

    @inner.routes.websocket('/echo')
    def echo_ws(c):
        c.on('message', lambda c, msg: c.send(f'echo: {msg} at {c.url_for("/")}'))

    pongs = []

    @inner.routes.websocket('/pinged')
    def pinged(c):
        c.tx.heartbeat(0.05, 0.1).on('frame', lambda ws, frame: pongs.append(frame[4]))
        c.on('message', lambda c, msg: c.send(f'still here: {msg}'))

    @inner.routes.websocket('/forbidden')
    def forbidden(c):
        c.render(text='Forbidden!', status=403)

    with Pyjo.App.ASGI.new(app=Pyjo.Server.ASGI.new(app=inner).to_asgi_app()) as asgi:
        t = Pyjo.Test.Pyjo.new(application(asgi))
        t.get_ok('/prefix/later').status_is(200).content_is('Hello later at /prefix!')
        t.get_ok('/prefix/chunks').status_is(200).content_is('012')
        t.get_ok('/prefix/missing').status_is(404)
        t.websocket_ok('/prefix/echo').send_ok('hi').message_ok().message_is('echo: hi at /prefix').finish_ok()
        handshake(t, '/prefix/forbidden').status_is(403)

        # The pings of the inner WebSocket, which ASGI cannot send, are answered by its server
        t.websocket_ok('/prefix/pinged')
        Pyjo.IOLoop.timer(0.3, lambda loop: loop.stop())
        Pyjo.IOLoop.start()
        t.send_ok('hi').message_ok().message_is('still here: hi').finish_ok()
        ok(len(pongs) > 2, 'pongs')
        is_deeply_ok(set(pongs[:3]), {WS_PONG}, 'only pongs')

with subtest('Event loop of asyncio'):

    async def sleepy(scope, receive, send):
        await asyncio.sleep(0.01)
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'Hello after a sleep!'})

    with Pyjo.App.ASGI.new(app=sleepy) as app:
        app.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(app)

        # Not on another reactor, which drives a coroutine that awaits only the promises of Pyjoyment
        if Pyjo.Reactor.detect() != 'Pyjo.Reactor.Asyncio':
            with app.log.capture('error') as messages:
                t.get_ok('/').status_is(500)
            like_ok(str(messages), r'no running event loop|cannot wait for', 'right error')
        else:
            t.get_ok('/').status_is(200).content_is('Hello after a sleep!')

done_testing()
