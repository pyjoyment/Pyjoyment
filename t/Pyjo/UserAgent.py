import os


os.environ['PYJO_NO_NNR'] = os.environ['PYJO_NO_SOCKS'] = os.environ['PYJO_NO_TLS'] = '1'
# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor that Pyjo.Reactor.detect gives

import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.IOLoop.Client
import Pyjo.IOLoop.TLS
import Pyjo.Message.Request
import Pyjo.Promise
import Pyjo.Server.Daemon
import Pyjo.UserAgent
import Pyjo.UserAgent.Server
import Pyjoyment.Lite

from Pyjo.Test import *
from Pyjo.Util import gzip
from Pyjoyment.Lite import any, app, get, post

import gc
import re
import threading
import time

from unittest.mock import patch


# Silence
app.log.level = 'trace'
app.log.unsubscribe('message')

get('/', {'text': 'works!'})

get('/huge', {'text': 'x' * 262144})

timeout = None


@get('/timeout')
def timeout_action(c):
    c.inactivity_timeout(float(c.param('timeout')))

    def finish(c):
        global timeout
        timeout = 1

    c.on('finish', finish)


@get('/no_length')
def no_length(c):
    c.finish(b'works too!')
    c.rendered(200)


get('/no_content', {'text': 'fail!', 'status': 204})


@get('/echo')
def echo_get(c):
    compressed = gzip(c.req.body)
    c.res.headers.content_encoding = c.req.headers.accept_encoding
    c.render(data=compressed)


@post('/echo')
def echo_post(c):
    c.render(data=c.req.body)


any('/method', {'inline': '<%= c.req.method =%>'})


@get('/one')
def one(c):
    c.res.version = '1.0'
    if connection := c.param('connection'):
        c.res.headers.connection = connection

    c.render(text='One!')


@get('/redirect_close')
def redirect_close(c):
    c.res.headers.connection = 'close'
    c.res.headers.location = str(c.url_for('/').to_abs())
    c.rendered(302)
    c.res.fix_headers().headers.remove('Content-Length')


# Max redirects
with patch.dict(os.environ, {'PYJO_MAX_REDIRECTS': '25'}):
    is_ok(Pyjo.UserAgent.new().max_redirects, 25, 'right value')
    os.environ['PYJO_MAX_REDIRECTS'] = '0'
    is_ok(Pyjo.UserAgent.new().max_redirects, 0, 'right value')

# Timeouts
with patch.dict(os.environ):
    for name in ('PYJO_CONNECT_TIMEOUT', 'PYJO_INACTIVITY_TIMEOUT', 'PYJO_REQUEST_TIMEOUT'):
        os.environ.pop(name, None)
    is_ok(Pyjo.UserAgent.new().connect_timeout, 10, 'right value')
    os.environ['PYJO_CONNECT_TIMEOUT'] = '25'
    is_ok(Pyjo.UserAgent.new().connect_timeout, 25, 'right value')
    is_ok(Pyjo.UserAgent.new().inactivity_timeout, 40, 'right value')
    os.environ['PYJO_INACTIVITY_TIMEOUT'] = '25'
    is_ok(Pyjo.UserAgent.new().inactivity_timeout, 25, 'right value')
    os.environ['PYJO_INACTIVITY_TIMEOUT'] = '0'
    is_ok(Pyjo.UserAgent.new().inactivity_timeout, 0, 'right value')
    is_ok(Pyjo.UserAgent.new().request_timeout, 0, 'right value')
    os.environ['PYJO_REQUEST_TIMEOUT'] = '25'
    is_ok(Pyjo.UserAgent.new().request_timeout, 25, 'right value')
    os.environ['PYJO_REQUEST_TIMEOUT'] = '0'
    is_ok(Pyjo.UserAgent.new().request_timeout, 0, 'right value')

# Default application
is_ok(Pyjo.UserAgent.Server.app(), app, 'applications are equal')
is_ok(Pyjo.UserAgent.new().server.app, app, 'applications are equal')
Pyjo.UserAgent.Server.app(app)
is_ok(Pyjo.UserAgent.Server.app(), app, 'applications are equal')
dummy = Pyjoyment.Lite.new()
ua = Pyjo.UserAgent.new()
ua.server.app = dummy
isnt_ok(ua.server.app, app, 'applications are not equal')
is_ok(Pyjo.UserAgent.Server.app(), app, 'applications are still equal')
Pyjo.UserAgent.Server.app(dummy)
isnt_ok(Pyjo.UserAgent.Server.app(), app, 'applications are not equal')
is_ok(Pyjo.UserAgent.Server.app(), dummy, 'application are equal')
Pyjo.UserAgent.Server.app(app)
is_ok(Pyjo.UserAgent.Server.app(), app, 'applications are equal again')

# Clean up non-blocking requests
ua = Pyjo.UserAgent.new()
results = {}
ua.get('/', lambda ua, tx: results.update(get=tx.error))
ua.post('/', lambda ua, tx: results.update(post=tx.error))
del ua
# Not in Mojolicious: PyPy frees the user agent when its garbage collector runs
gc.collect()
is_ok(results['get']['message'], 'Premature connection close', 'right error')
is_ok(results['post']['message'], 'Premature connection close', 'right error')

# The poll reactor stops when there are no events being watched anymore
start = time.time()
Pyjo.IOLoop.start()
ok(time.time() < (start + 10), 'stopped automatically')

# Blocking and non-blocking
ua = Pyjo.UserAgent.new()
result = {}


def cb(ua, tx):
    result.update(success=not tx.error, code=tx.res.code, body=tx.res.body)
    Pyjo.IOLoop.stop()


ua.get('/', cb)
is_ok(ua.get('/').res.code, 200, 'right status')
Pyjo.IOLoop.start()
ok(result['success'], 'successful')
is_ok(result['code'], 200, 'right status')
is_ok(result['body'], b'works!', 'right content')

# Promises
results = []
p1 = ua.get_p('/')
p2 = ua.get_p('/')
Pyjo.Promise.all(p1, p2).then(lambda first, second: results.extend([first, second])).wait()
ok(not results[0][0].error, 'no error')
is_ok(results[0][0].res.code, 200, 'right status')
is_ok(results[0][0].res.body, b'works!', 'right content')
ok(not results[1][0].error, 'no error')
is_ok(results[1][0].res.code, 200, 'right status')
is_ok(results[1][0].res.body, b'works!', 'right content')

# Promises (shortcut methods)
result = None


def body(tx):
    global result
    result = tx.res.body


ua.delete_p('/method').then(body).wait()
is_ok(result, b'DELETE', 'right result')
ua.get_p('/method').then(body).wait()
is_ok(result, b'GET', 'right result')
ua.head_p('/method').then(body).wait()
is_ok(result, b'', 'no result')
ua.options_p('/method').then(body).wait()
is_ok(result, b'OPTIONS', 'right result')
ua.patch_p('/method').then(body).wait()
is_ok(result, b'PATCH', 'right result')
ua.post_p('/method').then(body).wait()
is_ok(result, b'POST', 'right result')
ua.put_p('/method').then(body).wait()
is_ok(result, b'PUT', 'right result')
ua.query_p('/method').then(body).wait()
is_ok(result, b'QUERY', 'right result')
ua.start_p(ua.build_tx('TEST', '/method')).then(body).wait()
is_ok(result, b'TEST', 'right result')

# No timeout
ua = Pyjo.UserAgent.new(inactivity_timeout=0)
tx = ua.get('/')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')
tx = ua.get('/')
ok(tx.kept_alive, 'kept connection alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')

# SOCKS proxy request without SOCKS support
ua = Pyjo.UserAgent.new()
tx = ua.build_tx('GET', '/')
proxy = ua.server.url()
proxy.scheme = 'socks'
tx.req.proxy = proxy
tx = ua.start(tx)
# Unlike Mojolicious: the message of Pyjo.IOLoop.Client, where Mojo names IO::Socket::Socks
like_ok(tx.error['message'], r'SOCKS support is disabled', 'right error')
ok(not Pyjo.IOLoop.Client.object.can_socks(), 'no SOCKS5 support')

# HTTPS request without TLS support
ua = Pyjo.UserAgent.new()
url = ua.server.url()
url.scheme = 'https'
tx = ua.get(url)
# Unlike Mojolicious: the message of Pyjo.IOLoop.TLS, where Mojo names IO::Socket::SSL
like_ok(tx.error['message'], r'TLS support is disabled', 'right error')
ok(not Pyjo.IOLoop.TLS.object.can_tls(), 'no TLS support')

# Promises (rejected)
error = None


def catch(err):
    global error
    error = err


url = ua.server.url()
url.scheme = 'https'
ua.get_p(url).catch(catch).wait()
like_ok(str(error), r'TLS support is disabled', 'right error')

# No non-blocking name resolution
ok(not Pyjo.IOLoop.Client.object.can_nnr(), 'no non-blocking name resolution support')

# Blocking
tx = ua.get('/')
ok(not tx.error, 'no error')
ok(not tx.kept_alive, 'kept connection not alive')
is_ok(tx.res.version, '1.1', 'right version')
is_ok(tx.res.code, 200, 'right status')
ok(not tx.res.headers.connection, 'no "Connection" value')
is_ok(tx.res.max_message_size, 2147483648, 'right value')
is_ok(tx.res.body, b'works!', 'right content')

# Again
tx = ua.get('/')
ok(not tx.error, 'no error')
ok(tx.kept_alive, 'kept connection alive')
is_ok(tx.res.version, '1.1', 'right version')
is_ok(tx.res.code, 200, 'right status')
ok(not tx.res.headers.connection, 'no "Connection" value')
is_ok(tx.res.body, b'works!', 'right content')
ua.max_response_size = 0
tx = ua.get('/')
ok(not tx.error, 'no error')
is_ok(tx.res.version, '1.1', 'right version')
is_ok(tx.res.code, 200, 'right status')
ok(not tx.res.headers.connection, 'no "Connection" value')
is_ok(tx.res.max_message_size, 0, 'right value')
is_ok(tx.res.body, b'works!', 'right content')

# Unsupported protocol
ua.request_timeout = 3600
tx = ua.get('htttp://example.com')
is_ok(tx.error['message'], 'Unsupported protocol: htttp', 'right error')
throws_ok(lambda: tx.result, re.compile(r'Unsupported protocol: htttp'), 'right error')

# Shortcuts for common request methods
is_ok(ua.delete('/method').res.body, b'DELETE', 'right content')
is_ok(ua.get('/method').res.body, b'GET', 'right content')
is_ok(ua.head('/method').res.body, b'', 'no content')
is_ok(ua.options('/method').res.body, b'OPTIONS', 'right method')
is_ok(ua.patch('/method').res.body, b'PATCH', 'right method')
is_ok(ua.post('/method').res.body, b'POST', 'right method')
is_ok(ua.put('/method').res.body, b'PUT', 'right method')
is_ok(ua.query('/method').res.body, b'QUERY', 'right method')

# No keep-alive
tx = ua.get('/one?connection=test')
ok(not tx.error, 'no error')
ok(not tx.keep_alive, 'connection will not be kept alive')
is_ok(tx.res.version, '1.0', 'right version')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.headers.connection, 'test', 'right "Connection" value')
is_ok(tx.res.body, b'One!', 'right content')
tx = ua.get('/one?connection=test')
ok(not tx.error, 'no error')
ok(not tx.kept_alive, 'kept connection not alive')
ok(not tx.keep_alive, 'connection will not be kept alive')
is_ok(tx.res.version, '1.0', 'right version')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.headers.connection, 'test', 'right "Connection" value')
is_ok(tx.res.body, b'One!', 'right content')
tx = ua.get('/one')
ok(not tx.error, 'no error')
ok(not tx.kept_alive, 'kept connection not alive')
ok(not tx.keep_alive, 'connection will not be kept alive')
is_ok(tx.res.version, '1.0', 'right version')
is_ok(tx.res.code, 200, 'right status')
ok(not tx.res.headers.connection, 'no "Connection" value')
is_ok(tx.res.body, b'One!', 'right content')

# Error in callback
Pyjo.IOLoop.singleton.reactor.unsubscribe('error')
err = ''


@Pyjo.IOLoop.singleton.reactor.once('error')
def reactor_error(reactor, e):
    global err
    err += str(e)
    Pyjo.IOLoop.stop()


def die(ua, tx):
    raise Pyjo.Exception.new('error event works')


app.ua.get('/', die)
Pyjo.IOLoop.start()
like_ok(err, r'error event works', 'right error')

# Events
finished = {'req': 0, 'tx': 0, 'res': 0}


def count(name):
    def cb(*args):
        finished[name] += 1

    return cb


tx = ua.build_tx('GET', '/does_not_exist')
ok(not tx.is_finished, 'transaction is not finished')


@ua.once('prepare')
def prepare(ua, tx):
    tx.req.url.path = '/'


@ua.once('start')
def start_events(ua, tx):
    tx.req.on('finish', count('req'))
    tx.on('finish', count('tx'))
    tx.res.on('finish', count('res'))


tx = ua.start(tx)
ok(not tx.error, 'no error')
is_ok(finished['req'], 1, 'finish event has been emitted once')
is_ok(finished['tx'], 1, 'finish event has been emitted once')
is_ok(finished['res'], 1, 'finish event has been emitted once')
ok(tx.req.is_finished, 'request is finished')
ok(tx.is_finished, 'transaction is finished')
ok(tx.res.is_finished, 'response is finished')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')

# Missing Content-Length header
finished = {'req': 0, 'tx': 0, 'res': 0}
tx = ua.build_tx('GET', '/no_length')
ok(not tx.is_finished, 'transaction is not finished')
ua.once('start', start_events)
tx = ua.start(tx)
ok(not tx.error, 'no error')
is_ok(finished['req'], 1, 'finish event has been emitted once')
is_ok(finished['tx'], 1, 'finish event has been emitted once')
is_ok(finished['res'], 1, 'finish event has been emitted once')
ok(tx.req.is_finished, 'request is finished')
ok(tx.is_finished, 'transaction is finished')
ok(tx.res.is_finished, 'response is finished')
ok(not tx.error, 'no error')
ok(tx.kept_alive, 'kept connection alive')
ok(not tx.keep_alive, 'keep connection not alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works too!', 'right content')

# 204 No Content
tx = ua.get('/no_content')
ok(not tx.error, 'no error')
ok(not tx.kept_alive, 'kept connection not alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 204, 'right status')
ok(tx.is_empty, 'transaction is empty')
is_ok(tx.res.body, b'', 'no content')

# Connection was kept alive
tx = ua.head('/huge')
ok(not tx.error, 'no error')
ok(tx.kept_alive, 'kept connection alive')
is_ok(tx.res.code, 200, 'right status')
ok(tx.res.headers.content_length, 'has "Content-Length" value')
ok(tx.is_empty, 'transaction is empty')
is_ok(tx.res.body, b'', 'no content')
tx = ua.get('/huge')
ok(not tx.error, 'no error')
ok(tx.kept_alive, 'kept connection alive')
is_ok(tx.res.code, 200, 'right status')
ok(tx.res.headers.content_length, 'has "Content-Length" value')
ok(not tx.is_empty, 'transaction is not empty')
is_ok(tx.res.body, b'x' * 262144, 'right content')

# Non-blocking form
result = {}
ua.post('/echo', cb, form={'hello': 'world'})
Pyjo.IOLoop.start()
ok(result['success'], 'successful')
is_ok(result['code'], 200, 'right status')
is_ok(result['body'], b'hello=world', 'right content')

# Non-blocking JSON
result = {}
ua.post('/echo', cb, json={'hello': 'world'})
Pyjo.IOLoop.start()
ok(result['success'], 'successful')
is_ok(result['code'], 200, 'right status')
is_ok(result['body'], b'{"hello":"world"}', 'right content')

# Built-in web server times out
ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
with app.log.capture('trace') as logs:
    tx = ua.get('/timeout?timeout=0.25')
is_ok(tx.error['message'], 'Premature connection close', 'right error')
is_ok(timeout, 1, 'finish event has been emitted')
like_ok(str(logs), r'Inactivity timeout', 'right log message')
throws_ok(lambda: tx.result, re.compile(r'Premature connection close'), 'right error')


# Client times out
@ua.once('start')
def client_timeout(ua, tx):
    @tx.on('connection')
    def connection(tx, connection):
        Pyjo.IOLoop.stream(connection).timeout = 0.25


tx = ua.get('/timeout?timeout=5')
is_ok(tx.error['message'], 'Inactivity timeout', 'right error')
throws_ok(lambda: tx.result, re.compile(r'Inactivity timeout'), 'right error')

# Keep alive connection times out
id = None


def keep_alive(ua, tx):
    global id
    Pyjo.IOLoop.timer(0.5, lambda loop: Pyjo.IOLoop.stop())
    id = tx.connection
    Pyjo.IOLoop.stream(id).timeout = 0.25


ua.get('/', keep_alive)
Pyjo.IOLoop.start()
ok(not Pyjo.IOLoop.stream(id), 'connection timed out')

# Request timeout with keep-alive
ua.request_timeout = 3600
ok(not ua.get('/').error, 'priming the keep-alive connection')
ua.request_timeout = 0.01
tx = ua.get('/timeout?timeout=5')
is_ok(tx.error['message'], 'Request timeout', 'right error message')
is_ok(tx.error.get('code'), None, 'no status')
ua.request_timeout = 0


# Response exceeding message size limit
@ua.once('start')
def message_size(ua, tx):
    tx.res.max_message_size = 12


tx = ua.get('/echo', 'Hello World!')
is_ok(tx.error['message'], 'Maximum message size exceeded', 'right error')
is_ok(tx.error.get('code'), None, 'no status')
ok(tx.res.is_limit_exceeded, 'limit is exceeded')

# 404 response
tx = ua.get('/does_not_exist')
ok(tx.result, 'has a result')
is_ok(tx.result.code, 404, 'right status')
ok(not tx.kept_alive, 'kept connection not alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.error['message'], 'Not Found', 'right error')
is_ok(tx.error['code'], 404, 'right status')
tx = ua.get('/does_not_exist')
ok(tx.kept_alive, 'kept connection alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.error['message'], 'Not Found', 'right error')
is_ok(tx.error['code'], 404, 'right status')

# Redirect with connection close
ua.max_redirects = 3
tx = ua.get('/redirect_close')
ok(not tx.error, 'no error')
ok(not tx.kept_alive, 'kept connection not alive')
is_ok(tx.res.version, '1.1', 'right version')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')
ua.max_redirects = 0

# Compressed response
tx = ua.build_tx('GET', '/echo', 'Hello GZip!')
tx = ua.start(ua.build_tx('GET', '/echo', 'Hello GZip!'))
ok(not tx.error, 'no error')
ok(tx.result, 'has a result')
is_ok(tx.result.code, 200, 'right status')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.headers.content_encoding, None, 'no "Content-Encoding" value')
is_ok(tx.res.body, b'Hello GZip!', 'right content')
tx = ua.build_tx('GET', '/echo', 'Hello GZip!')
tx.res.content.auto_decompress = False
tx = ua.start(tx)
ok(not tx.error, 'no error')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.headers.content_encoding, 'gzip', 'right "Content-Encoding" value')
isnt_ok(tx.res.body, b'Hello GZip!', 'different content')

# Keep-alive timeout in between requests
daemon = Pyjo.Server.Daemon.new(
    app=app, ioloop=ua.ioloop, keep_alive_timeout=0.5, listen=['http://127.0.0.1'], silent=True
)
port = daemon.start().ports()[0]
tx = ua.get(f'http://127.0.0.1:{port}')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')
promise = Pyjo.Promise.new()
promise.ioloop = ua.ioloop
promise.timer(1).wait()
tx = ua.get(f'http://127.0.0.1:{port}')
ok(not tx.kept_alive, 'kept connection not alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')

with subtest('Fork-safety'):
    tx = ua.get('/')
    ok(tx.keep_alive, 'keep connection alive')
    is_ok(tx.res.body, b'works!', 'right content')
    last = tx.connection
    port = ua.server.url().port
    tx = ua.get('/')
    is_ok(tx.res.body, b'works!', 'right content')
    is_ok(tx.connection, last, 'same connection')
    is_ok(ua.server.url().port, port, 'same port')
    with patch('os.getpid', return_value=-23):
        tx = ua.get('/')
        ok(not tx.kept_alive, 'kept connection not alive')
        ok(tx.keep_alive, 'keep connection alive')
        is_ok(tx.res.body, b'works!', 'right content')
        isnt_ok(tx.connection, last, 'new connection')
        isnt_ok(ua.server.url().port, port, 'new port')
        port2 = ua.server.url().port
        last2 = tx.connection
        with patch('os.getpid', return_value=-24):
            tx = ua.get('/')
            ok(not tx.kept_alive, 'kept connection not alive')
            ok(tx.keep_alive, 'keep connection alive')
            is_ok(tx.res.body, b'works!', 'right content')
            isnt_ok(tx.connection, last, 'new connection')
            isnt_ok(tx.connection, last2, 'new connection')
            isnt_ok(ua.server.url().port, port, 'new port')
            isnt_ok(ua.server.url().port, port2, 'new port')

# Introspect
req = res = b''
num = []


def introspect(ua, tx):
    @tx.on('connection')
    def connection(tx, connection):
        stream = Pyjo.IOLoop.stream(connection)
        num.extend([stream.bytes_read, stream.bytes_written])

        def on_read(stream, chunk):
            global res
            res += chunk

        def on_write(stream, chunk):
            global req
            req += chunk

        read = stream.on('read', on_read)
        write = stream.on('write', on_write)

        @tx.on('finish')
        def finish(tx):
            num.extend([stream.bytes_read, stream.bytes_written])
            stream.unsubscribe('read', read)
            stream.unsubscribe('write', write)


start_cb = ua.on('start', introspect)
tx = ua.get('/', 'whatever')
ok(not tx.error, 'no error')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')
is_ok(len(Pyjo.IOLoop.stream(tx.connection).subscribers('write')), 0, 'unsubscribed successfully')
is_ok(len(Pyjo.IOLoop.stream(tx.connection).subscribers('read')), 1, 'unsubscribed successfully')
like_ok(req, rb'(?s)^GET / .*whatever$', 'right request')
like_ok(res, rb'(?s)^HTTP/.*200 OK.*works!$', 'right response')
is_deeply_ok(num, [0, 0, len(res), len(req)], 'right structure')
ua.unsubscribe('start', start_cb)
ok(not ua.has_subscribers('start'), 'unsubscribed successfully')

# Stream with drain callback and compressed response
tx = ua.build_tx('GET', '/echo')
i = 0
stream = 0


def drain(content, *args):
    global i, stream
    if i >= 10:

        def last(loop):
            global stream
            content.write_chunk(b'')
            tx.resume()
            stream += len(Pyjo.IOLoop.stream(tx.connection).subscribers('drain'))

        return ua.ioloop.timer(0.25, last)
    content.write_chunk(str(i).encode(), drain)
    i += 1
    tx.resume()
    if not (id := tx.connection):
        return
    stream += len(Pyjo.IOLoop.stream(id).subscribers('drain'))


drain(tx.req.content)
ua.start(tx)
ok(not tx.error, 'no error')
ok(tx.kept_alive, 'kept connection alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'0123456789', 'right content')
is_ok(stream, 1, 'no leaking subscribers')

# Upload progress
ua = Pyjo.UserAgent.new()
progress = {}


@ua.on('start')
def upload_progress(ua, tx):
    tx.req.on('progress', lambda req, state, offset: progress.update({state: 1}))
    tx.req.on('finish', lambda req: progress.update(finish=1))


tx = ua.post('/echo', 'Hello Mojo!')
ok(not tx.error, 'no error')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'Hello Mojo!', 'right content')
is_deeply_ok(progress, {'start_line': 1, 'headers': 1, 'body': 1, 'finish': 1}, 'right structure')

# Mixed blocking and non-blocking requests, with custom URL
ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
tx = ua.get(ua.server.url())
ok(not tx.error, 'no error')
ok(not tx.kept_alive, 'kept connection not alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')
kept_alive = []


def first(ua, tx):
    kept_alive.append(tx.kept_alive)

    def second(ua, tx):
        kept_alive.append(tx.kept_alive)

        def third(ua, tx):
            kept_alive.append(tx.kept_alive)
            Pyjo.IOLoop.stop()

        ua.get(ua.server.nb_url(), third)

    ua.get('/', second)


ua.get(ua.server.nb_url(), first)
Pyjo.IOLoop.start()
is_deeply_ok(kept_alive, [None, True, True], 'connections kept alive')
tx = ua.get(ua.server.url())
ok(not tx.error, 'no error')
ok(tx.kept_alive, 'kept connection alive')
ok(tx.keep_alive, 'keep connection alive')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'works!', 'right content')

# Simple nested non-blocking requests with timers
kept_alive = []


def nested(ua, tx):
    kept_alive.append(tx.kept_alive)

    def again(loop):
        def done(ua, tx):
            kept_alive.append(tx.kept_alive)
            Pyjo.IOLoop.next_tick(lambda loop: Pyjo.IOLoop.stop())

        ua.get('/', done)

    Pyjo.IOLoop.next_tick(again)


ua.get('/', nested)
Pyjo.IOLoop.start()
is_deeply_ok(kept_alive, [True, True], 'connections kept alive')

# Unexpected 1xx responses
req = Pyjo.Message.Request.new()


@Pyjo.IOLoop.server(address='127.0.0.1')
def id(loop, stream, id):
    @stream.on('read')
    def read(stream, chunk):
        if req.parse(chunk).is_finished:
            stream.write(
                b'HTTP/1.1 100 Continue\x0d\x0a'
                b'X-Foo: Bar\x0d\x0a\x0d\x0a'
                b'HTTP/1.1 101 Switching Protocols\x0d\x0a\x0d\x0a'
                b'HTTP/1.1 200 OK\x0d\x0a'
                b'Content-Length: 3\x0d\x0a\x0d\x0a' + b'Hi!'
            )


port = Pyjo.IOLoop.acceptor(id).port
tx = ua.build_tx('GET', f'http://127.0.0.1:{port}/')
unexpected = []
tx.on('unexpected', lambda tx, res: unexpected.append(res))
tx = ua.start(tx)
is_ok(unexpected[0].code, 100, 'right status')
is_ok(unexpected[0].headers.header('X-Foo'), 'Bar', 'right "X-Foo" value')
is_ok(unexpected[1].code, 101, 'right status')
ok(not tx.error, 'no error')
is_ok(tx.res.code, 200, 'right status')
is_ok(tx.res.body, b'Hi!', 'right content')

# Connection limit
ua = Pyjo.UserAgent.new(max_connections=2)
result = None
txs = [ua.get_p('/') for _ in range(1, 6)]


def limit(*results):
    global result
    # Unlike Mojolicious: the connections that are active, not the transactions whose connection is, as each start of
    # a request runs a tick of the event loop, where a fast one, as of uvloop, finishes the first request before the
    # last one starts, which takes its connection, so the transactions count it twice
    result = {r[0].connection for r in results if Pyjo.IOLoop.stream(r[0].connection) is not None}


Pyjo.Promise.all(*txs).then(limit).wait()
is_ok(len(result), 2, 'two active connections')

# Not in Mojolicious: a blocking request used as a decorator, whose transaction is not a callback
ua = Pyjo.UserAgent.new()
try:

    @ua.get('/')
    def decorated(ua, tx):
        pass

except TypeError as e:
    err = e
like_ok(str(err), r"^'Pyjo_Transaction_HTTP' object is not callable: a request without a callback is blocking", 'hint')

with subtest('Singleton'):
    # Not in Mojolicious: the user agent that the thread shares, with which the functions of the module request
    ua = Pyjo.UserAgent.singleton
    ok(ua is Pyjo.UserAgent.object.singleton(), 'same user agent')
    ok(ua is not Pyjo.UserAgent.new(), 'not a new user agent')
    is_ok(ua.max_redirects, 10, 'ten redirects')
    others = []
    thread = threading.Thread(target=lambda: others.append(Pyjo.UserAgent.singleton))
    thread.start()
    thread.join()
    ok(others[0] is not ua, 'another user agent in another thread')

    ua.server.app = app
    is_ok(Pyjo.UserAgent.get('/').result.body, b'works!', 'right content')
    for method in ('delete', 'get', 'head', 'options', 'patch', 'post', 'put', 'query'):
        tx = getattr(Pyjo.UserAgent, method)('/method')
        is_ok(tx.req.method, method.upper(), f'right method of {method}')
        is_ok(tx.res.text, '' if method == 'head' else method.upper(), f'right content of {method}')
    is_ok(Pyjo.UserAgent.post('/echo', json={'a': 'b'}).result.json(), {'a': 'b'}, 'right content')

    results = []
    Pyjo.UserAgent.get('/', lambda ua, tx: [results.append(tx.result.body), Pyjo.IOLoop.stop()])
    Pyjo.IOLoop.start()
    is_ok(results, [b'works!'], 'non-blocking request')
    ua.close()

done_testing()
