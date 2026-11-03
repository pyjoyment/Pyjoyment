import os


os.environ['PYJO_PROXY'] = '0'
# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor that Pyjo.Reactor.detect gives

import Pyjo.IOLoop
import Pyjo.IOLoop.Server
import Pyjo.IOLoop.TLS
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent

from Pyjo.Test import *

import gc
import socket
import sys


if not (os.environ.get('TEST_ONLINE') or os.environ.get('TEST_ALL')):
    plan(skip_all='set TEST_ONLINE to enable this test (developer only!)')
if not Pyjo.IOLoop.TLS.object.can_tls():
    plan(skip_all='TLS support required for this test!')
# Left out from Mojolicious: Mozilla::CA, as ssl takes the certificate authorities of the system

from Pyjo import g, h, p
from Pyjoyment.Lite import app, get


# Not in Mojolicious: the application logs nothing, where Mojo logs the requests of its server to STDERR, as the test
# does not load Test::Mojo, which sets MOJO_LOG_LEVEL
app.log.level = 'fatal'

# Unlike Mojolicious: the remote hosts are those of GitHub, where Mojo requests mojolicious.org, metacpan.org and
# wikipedia.org, as the runners of GitHub Actions reach them the most reliably; github.com answers a form POST without
# a CSRF token with 422, where metacpan.org answers it with 200, and redirects from HTTP to HTTPS in one step, where
# wikipedia.org takes two; a form is posted to the page of a repository, as the search of GitHub limits the requests
# of a client, which the jobs of CI, all of them online, would reach


@get('/remote_address')
def remote_address(c):
    c.render(text=c.tx.remote_address)


loop = Pyjo.IOLoop.singleton

# Unlike Mojolicious: a subtest that requests a remote host runs again after a failure of the network, with a user agent
# of its own, so that a rerun does not take the connections that the run before it kept alive, where Mojo runs it once,
# with a user agent that the subtests after it share
RERUNS = {'reruns': 2, 'reruns_delay': 10}


@subtest('Make sure user agents dont taint the ioloop', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    result = {}

    def cb(ua, tx):
        result.update(id=tx.connection, code=tx.res.code)
        loop.stop()

    ua.get('http://github.com', cb)
    loop.start()
    ua = None
    # Not in Mojolicious: the garbage collector runs, as PyPy frees the user agent only then, where Perl frees it at once
    gc.collect()
    loop.timer(0.25, lambda loop: loop.stop())
    loop.start()
    ok(not loop.stream(result['id']), 'loop not tainted')
    is_ok(result['code'], 301, 'right status')


@subtest('Local address', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    ua.server.app = app
    with socket.create_connection(('github.com', 80)) as sock:
        address = sock.getsockname()[0]
    isnt_ok(address, '127.0.0.1', 'different address')
    ua.max_connections = 0
    # Unlike Mojolicious: source_address, where Mojo sets LocalAddr of socket_options
    ua.source_address = ('127.0.0.1', 0)
    tx = ua.get('/remote_address')
    ok(not ua.ioloop.stream(tx.connection), 'connection is not active')
    is_ok(tx.res.body, b'127.0.0.1', 'right address')
    ua.source_address = (address, 0)
    # Unlike Mojolicious: Windows connects to the loopback from a loopback address only (WSAEADDRNOTAVAIL)
    if sys.platform == 'win32':
        skip('no loopback from another address on Windows', 1)
    else:
        is_ok(ua.get('/remote_address').res.body, address.encode(), 'right address')


ua = Pyjo.UserAgent.new()
port = Pyjo.IOLoop.Server.object.generate_port()

with subtest('Connection refused'):
    tx = ua.build_tx('GET', f'http://127.0.0.1:{port}')
    ua.start(tx)
    ok(tx.is_finished, 'transaction is finished')
    ok(tx.error, 'has error')

with subtest('Connection refused (IPv4)'):
    tx = ua.build_tx('GET', f'http://127.0.0.1:{port}')
    ua.start(tx)
    ok(tx.is_finished, 'transaction is finished')
    ok(tx.error, 'has error')

with subtest('Connection refused (IPv6)'):
    tx = ua.build_tx('GET', f'http://[::1]:{port}')
    ua.start(tx)
    ok(tx.is_finished, 'transaction is finished')
    ok(tx.error, 'has error')

with subtest('Host does not exist'):
    tx = ua.build_tx('GET', 'http://cdeabcdeffoobarnonexisting.com')
    ua.start(tx)
    ok(tx.is_finished, 'transaction is finished')
    ok(tx.error, 'has error')


@subtest('Keep-alive', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    ua.get('http://github.com', lambda ua, tx: Pyjo.IOLoop.singleton.stop())
    Pyjo.IOLoop.singleton.start()
    kept_alive = []

    def keep_alive(ua, tx):
        Pyjo.IOLoop.singleton.stop()
        kept_alive.append(tx.kept_alive)

    ua.get('http://github.com', keep_alive)
    Pyjo.IOLoop.singleton.start()
    ok(kept_alive[0], 'connection was kept alive')


@subtest('Nested keep-alive', **RERUNS)
def _():
    # Not in Mojolicious: a request opens the connection, which Mojo keeps alive from the subtest before
    ua = Pyjo.UserAgent.new()
    ua.get('http://github.com', lambda ua, tx: Pyjo.IOLoop.singleton.stop())
    Pyjo.IOLoop.singleton.start()
    kept_alive = []

    def first(ua, tx):
        kept_alive.append(tx.kept_alive)

        def second(ua, tx):
            kept_alive.append(tx.kept_alive)

            def third(ua, tx):
                kept_alive.append(tx.kept_alive)
                Pyjo.IOLoop.singleton.stop()

            ua.get('http://github.com', third)

        ua.get('http://github.com', second)

    ua.get('http://github.com', first)
    Pyjo.IOLoop.singleton.start()
    is_deeply_ok(kept_alive, [True, True, True], 'connections kept alive')


@subtest('Custom non-keep-alive request', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    tx = Pyjo.Transaction.HTTP.new()
    tx.req.method = 'GET'
    tx.req.url.parse('http://github.com')
    tx.req.headers.connection = 'close'
    ua.start(tx)
    ok(tx.is_finished, 'transaction is finished')
    is_ok(tx.res.code, 301, 'right status')
    like_ok(tx.res.headers.connection, r'(?i)close', 'right "Connection" header')


@subtest('One-liner', **RERUNS)
def _():
    is_ok(g('github.com').code, 200, 'right status')
    is_ok(h('github.com').code, 200, 'right status')
    is_ok(h('github.com').body, b'', 'no content')
    is_ok(p('github.com/pyjoyment/lalalala').code, 404, 'right status')
    is_ok(g('http://github.com').code, 200, 'right status')
    res = p('https://github.com/pyjoyment/Pyjoyment', form={'q': 'mojolicious'})
    like_ok(res.body, rb'GitHub', 'right content')
    is_ok(res.code, 422, 'right status')


@subtest('Simple request', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    tx = ua.get('github.com')
    is_ok(tx.req.method, 'GET', 'right method')
    is_ok(str(tx.req.url), 'http://github.com', 'right url')
    is_ok(tx.res.code, 301, 'right status')


@subtest('Simple keep-alive requests', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    tx = ua.get('https://github.com')
    is_ok(tx.req.method, 'GET', 'right method')
    is_ok(str(tx.req.url), 'https://github.com', 'right url')
    is_ok(tx.req.body, b'', 'no content')
    is_ok(tx.res.code, 200, 'right status')
    ok(tx.keep_alive, 'connection will be kept alive')
    ok(not tx.kept_alive, 'connection was not kept alive')
    tx = ua.get('https://github.com')
    is_ok(tx.req.method, 'GET', 'right method')
    is_ok(str(tx.req.url), 'https://github.com', 'right url')
    is_ok(tx.res.code, 200, 'right status')
    ok(tx.keep_alive, 'connection will be kept alive')
    ok(tx.kept_alive, 'connection was kept alive')
    tx = ua.get('https://github.com')
    is_ok(tx.req.method, 'GET', 'right method')
    is_ok(str(tx.req.url), 'https://github.com', 'right url')
    is_ok(tx.res.code, 200, 'right status')
    ok(tx.keep_alive, 'connection will be kept alive')
    ok(tx.kept_alive, 'connection was kept alive')


@subtest('Simple HTTPS request', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    tx = ua.get('https://github.com')
    is_ok(tx.req.method, 'GET', 'right method')
    is_ok(str(tx.req.url), 'https://github.com', 'right url')
    is_ok(tx.res.code, 200, 'right status')


@subtest('Simple keep-alive form POST', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    tx = ua.post('https://github.com/pyjoyment/Pyjoyment', form={'q': 'mojolicious'})
    is_ok(tx.req.method, 'POST', 'right method')
    is_ok(str(tx.req.url), 'https://github.com/pyjoyment/Pyjoyment', 'right url')
    is_ok(tx.req.headers.content_length, '13', 'right content length')
    is_ok(tx.req.body, b'q=mojolicious', 'right content')
    like_ok(tx.res.body, rb'GitHub', 'right content')
    is_ok(tx.res.code, 422, 'right status')
    ok(tx.keep_alive, 'connection will be kept alive')
    tx = ua.post('https://github.com/pyjoyment/Pyjoyment', form={'q': 'mojolicious'})
    is_ok(tx.req.method, 'POST', 'right method')
    is_ok(str(tx.req.url), 'https://github.com/pyjoyment/Pyjoyment', 'right url')
    is_ok(tx.req.headers.content_length, '13', 'right content length')
    is_ok(tx.req.body, b'q=mojolicious', 'right content')
    like_ok(tx.res.body, rb'GitHub', 'right content')
    is_ok(tx.res.code, 422, 'right status')
    ok(tx.kept_alive, 'connection was kept alive')
    ok(tx.local_address, 'has local address')
    ok(tx.local_port > 0, 'has local port')
    ok(tx.original_remote_address, 'has original remote address')
    ok(tx.remote_address, 'has remote address')
    ok(tx.remote_port > 0, 'has remote port')


@subtest('Simple request with redirect', **RERUNS)
def _():
    ua = Pyjo.UserAgent.new()
    ua.max_redirects = 3
    tx = ua.get('http://github.com/pyjoyment')
    ua.max_redirects = 0
    is_ok(tx.req.method, 'GET', 'right method')
    is_ok(str(tx.req.url), 'https://github.com/pyjoyment', 'right url')
    is_ok(tx.res.code, 200, 'right status')
    is_ok(tx.previous.req.method, 'GET', 'right method')
    is_ok(str(tx.previous.req.url), 'http://github.com/pyjoyment', 'right url')
    is_ok(tx.previous.res.code, 301, 'right status')
    is_ok(tx.redirects()[-1].req.method, 'GET', 'right method')
    is_ok(str(tx.redirects()[-1].req.url), 'http://github.com/pyjoyment', 'right url')
    is_ok(tx.redirects()[-1].res.code, 301, 'right status')


ua = Pyjo.UserAgent.new()

with subtest('Connect timeout (non-routable address)'):
    ua.connect_timeout = 0.5
    tx = ua.get('192.0.2.1')
    ok(tx.is_finished, 'transaction is finished')
    is_ok(tx.error['message'], 'Connect timeout', 'right error')
    ua.connect_timeout = 3

done_testing()
