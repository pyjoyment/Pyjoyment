import os


os.environ['PYJO_MODE'] = 'development'

import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.File import tempdir
from Pyjo.Test import *
from Pyjoyment.Lite import app, get, hook, plugin

import http.client
import signal
import socket


# Not in Mojolicious: Pyjoyment.Plugin.Health, the liveness and the readiness of containers and orchestrators

app.log.level = 'fatal'

dispatched = []
hook('before_dispatch', lambda c: dispatched.append(c.req.url.path.to_route()))

plugin('Health')

get('/', {'text': 'Hello!'})


def application(conf=None, **checks):
    # An application of its own, with the options of the plugin
    other = Pyjoyment.new()
    other.log.level = 'fatal'
    other.plugin('Health', conf or {'checks': checks})
    other.routes.get('/', lambda c: c.render(text='Hello!'))
    return other


t = Pyjo.Test.Pyjo.new()

with subtest('Liveness'):
    t.get_ok('/livez').status_is(200).content_type_like(r'^text/plain').content_is('ok')
    t.get_ok('/healthz').status_is(200).content_is('ok')
    t.get_ok('/livez/ping').status_is(200).content_is('ok')
    t.get_ok('/healthz/ping').status_is(200).content_is('ok')
    t.get_ok('/livez?verbose').status_is(200).content_is('[+]ping ok\nlivez check passed\n')
    t.get_ok('/healthz?verbose').status_is(200).content_is('[+]ping ok\nhealthz check passed\n')
    t.head_ok('/livez').status_is(200).content_is('')
    t.post_ok('/livez').status_is(404)
    t.get_ok('/livez/other').status_is(404)
    t.get_ok('/').status_is(200).content_is('Hello!')

with subtest('Readiness'):
    t.get_ok('/readyz').status_is(200).content_type_like(r'^text/plain').content_is('ok')
    t.get_ok('/readyz?verbose').status_is(200).content_is('[+]shutdown ok\nreadyz check passed\n')
    t.get_ok('/readyz?verbose=1').status_is(200).content_is('[+]shutdown ok\nreadyz check passed\n')
    t.get_ok('/readyz/shutdown').status_is(200).content_is('ok')
    t.get_ok('/readyz/other').status_is(404)
    t.head_ok('/readyz').status_is(200).content_is('')

with subtest('Probes before the hooks of the application'):
    del dispatched[:]
    t.get_ok('/livez').status_is(200)
    t.get_ok('/readyz').status_is(200)
    is_deeply_ok(dispatched, [], 'no hooks of before_dispatch')
    t.get_ok('/').status_is(200)
    t.get_ok('/readyz/other').status_is(404)
    is_deeply_ok(dispatched, ['/', '/readyz/other'], 'hooks of before_dispatch')

    # The address of a pod, which AllowedHosts rejects
    other = application()
    other.plugin('AllowedHosts')
    t2 = Pyjo.Test.Pyjo.new(other)
    t2.get_ok('/livez', {'Host': '10.1.2.3:3000'}).status_is(200).content_is('ok')
    t2.get_ok('/readyz', {'Host': '10.1.2.3:3000'}).status_is(200).content_is('ok')
    t2.get_ok('/', {'Host': '10.1.2.3:3000'}).status_is(421)

with subtest('Checks'):

    async def coroutine(c):
        await Pyjo.Promise.timer(0.01)

    async def failing(c):
        await Pyjo.Promise.timer(0.01)
        raise RuntimeError('Connection refused')

    t2 = Pyjo.Test.Pyjo.new(
        application(
            true=lambda c: True,
            none=lambda c: None,
            promise=lambda c: Pyjo.Promise.timer(0.01, 'pong'),
            coroutine=coroutine,
        )
    )
    t2.get_ok('/readyz').status_is(200).content_is('ok')
    t2.get_ok('/readyz?verbose').status_is(200).content_is(
        '[+]shutdown ok\n[+]true ok\n[+]none ok\n[+]promise ok\n[+]coroutine ok\nreadyz check passed\n'
    )
    t2.get_ok('/readyz/coroutine').status_is(200).content_is('ok')
    t2.get_ok('/livez?verbose').status_is(200).content_is('[+]ping ok\nlivez check passed\n')

    def raising(c):
        raise RuntimeError('Database is down')

    other = application(
        true=lambda c: True,
        false=lambda c: False,
        raising=raising,
        rejected=lambda c: Pyjo.Promise.timer(0.01).then(lambda: Pyjo.Promise.reject('Queue is full')),
        fulfilled=lambda c: Pyjo.Promise.timer(0.01, False),
        failing=failing,
    )
    t2 = Pyjo.Test.Pyjo.new(other)
    with other.log.capture('warn') as logs:
        t2.get_ok('/readyz').status_is(503).content_is(
            '[+]shutdown ok\n[+]true ok\n[-]false failed: reason withheld\n[-]raising failed: reason withheld\n'
            + '[-]rejected failed: reason withheld\n[-]fulfilled failed: reason withheld\n'
            + '[-]failing failed: reason withheld\nreadyz check failed\n'
        )
    like_ok(str(logs), r'\[warn\] .*Health check "false" failed: returned False', 'right message')
    like_ok(str(logs), r'\[warn\] .*Health check "raising" failed: Database is down', 'right message')
    like_ok(str(logs), r'\[warn\] .*Health check "rejected" failed: Queue is full', 'right message')
    like_ok(str(logs), r'\[warn\] .*Health check "fulfilled" failed: returned False', 'right message')
    like_ok(str(logs), r'\[warn\] .*Health check "failing" failed: Connection refused', 'right message')
    t2.get_ok('/readyz?verbose').status_is(503).content_like(r'readyz check failed\n$')
    t2.get_ok('/readyz/true').status_is(200).content_is('ok')
    t2.get_ok('/readyz/false').status_is(503).content_is('[-]false failed: reason withheld\nreadyz check failed\n')
    t2.get_ok('/readyz/failing').status_is(503).content_is('[-]failing failed: reason withheld\nreadyz check failed\n')
    t2.get_ok('/livez').status_is(200).content_is('ok')

with subtest('Excluded checks'):
    t2 = Pyjo.Test.Pyjo.new(application(true=lambda c: True, false=lambda c: False, other=lambda c: False))
    t2.get_ok('/readyz?exclude=false').status_is(503)
    t2.get_ok('/readyz?exclude=false&exclude=other').status_is(200).content_is('ok')
    t2.get_ok('/readyz?exclude=false&exclude=other&exclude=unknown&verbose').status_is(200).content_is(
        '[+]shutdown ok\n[+]true ok\n[+]false excluded: ok\n[+]other excluded: ok\nreadyz check passed\n'
    )
    t2.get_ok('/readyz/false?exclude=false').status_is(503)

with subtest('Timeout'):
    # A promise of the application, as the one of its warm-up, which the timeout of the check does not reject
    warmup = Pyjo.Promise.new()
    other = application({'checks': {'warmup': lambda c: warmup}, 'timeout': 0.1})
    t2 = Pyjo.Test.Pyjo.new(other)
    with other.log.capture('warn') as logs:
        t2.get_ok('/readyz').status_is(503).content_is(
            '[+]shutdown ok\n[-]warmup failed: reason withheld\nreadyz check failed\n'
        )
    like_ok(str(logs), r'Health check "warmup" failed: timeout of 0\.1 seconds', 'right message')
    warmup.resolve()
    t2.get_ok('/readyz').status_is(200).content_is('ok')

with subtest('Helpers'):
    other = application()
    is_ok(other.health.path('livez'), '/livez', 'right path')
    is_ok(other.health.path('readyz'), '/readyz', 'right path')
    is_ok(other.health.path('healthz'), '/healthz', 'right path')
    is_ok(other.health.path('other'), None, 'no path')
    t2 = Pyjo.Test.Pyjo.new(other)
    t2.get_ok('/readyz/db').status_is(404)
    other.health.check('db', lambda c: False)
    t2.get_ok('/readyz').status_is(503).content_like(r'\[-\]db failed')
    t2.get_ok('/readyz/db').status_is(503)
    other.health.check('db', lambda c: True)
    t2.get_ok('/readyz').status_is(200).content_is('ok')
    other.health.check('none', lambda c: Pyjo.Promise.reject())
    with other.log.capture('warn') as logs:
        t2.get_ok('/readyz/none').status_is(503)
    like_ok(str(logs), r'Health check "none" failed: rejected', 'right message')
    other.health.check('none', lambda c: Pyjo.Promise.reject(None))
    t2.get_ok('/readyz/none').status_is(503)
    other.health.check('slow', lambda c: Pyjo.Promise.timer(0.2), timeout=0.05)
    t2.get_ok('/readyz/slow').status_is(503)
    other.health.check('slow', lambda c: Pyjo.Promise.timer(0.05), timeout=1)
    t2.get_ok('/readyz/slow').status_is(200)

with subtest('Paths'):
    other = application({'livez': '/-/live', 'readyz': '/-/ready', 'healthz': None})
    is_ok(other.health.path('livez'), '/-/live', 'right path')
    is_ok(other.health.path('healthz'), None, 'no path')
    t2 = Pyjo.Test.Pyjo.new(other)
    t2.get_ok('/-/live').status_is(200).content_is('ok')
    t2.get_ok('/-/live/ping').status_is(200).content_is('ok')
    t2.get_ok('/-/ready').status_is(200).content_is('ok')
    t2.get_ok('/-/ready/shutdown').status_is(200).content_is('ok')
    t2.get_ok('/healthz').status_is(404)
    t2.get_ok('/livez').status_is(404)
    t2.get_ok('/readyz').status_is(404)

    other = application({'livez': None, 'readyz': None})
    t2 = Pyjo.Test.Pyjo.new(other)
    t2.get_ok('/livez').status_is(404)
    t2.get_ok('/readyz').status_is(404)
    t2.get_ok('/healthz').status_is(200).content_is('ok')


# The readiness of a connection that is kept alive, from the moment that the server stops gracefully
def stopping(server):
    results = []
    conn = None

    @server.on('heartbeat')
    def heartbeat(server, id):
        nonlocal conn
        if not server.healthy or (results and results[-1][0] == 503):
            return
        if conn is None:
            conn = http.client.HTTPConnection('127.0.0.1', server.ports()[0], timeout=5)
        conn.request('GET', '/readyz')
        res = conn.getresponse()
        results.append((res.status, res.read()))
        if len(results) == 1:
            signal.raise_signal(signal.SIGTERM)
        if res.status == 503:
            conn.close()

    server.app = application()
    server.run()
    return results


if not hasattr(os, 'fork'):
    skip('no os.fork', 3)
else:
    with subtest('Readiness while the workers of prefork stop gracefully'):
        import Pyjo.Server.Prefork

        results = stopping(
            Pyjo.Server.Prefork.new(
                heartbeat_interval=0.1,
                listen=['http://127.0.0.1'],
                pid_file=tempdir().child('prefork.pid'),
                silent=True,
                workers=1,
            )
        )
        is_ok(results[0], (200, b'ok'), 'ready')
        is_ok(results[-1][0], 503, 'not ready')
        is_ok(results[-1][1], b'[-]shutdown failed: reason withheld\nreadyz check failed\n', 'shutdown')

with subtest('Readiness while the workers of prethread stop gracefully'):
    import Pyjo.Server.Prethread

    results = stopping(
        Pyjo.Server.Prethread.new(
            heartbeat_interval=0.1,
            listen=['http://127.0.0.1'],
            pid_file=tempdir().child('prethread.pid'),
            silent=True,
            workers=1,
        )
    )
    is_ok(results[0], (200, b'ok'), 'ready')
    is_ok(results[-1][0], 503, 'not ready')
    is_ok(results[-1][1], b'[-]shutdown failed: reason withheld\nreadyz check failed\n', 'shutdown')

with subtest('Readiness while the daemon stops gracefully'):
    results = []
    with (
        Pyjo.Server.Daemon.new(app=application(), listen=['http://127.0.0.1'], silent=True) as daemon,
        Pyjo.UserAgent.new() as ua,
    ):
        port = daemon.start().ports()[0]
        url = f'http://127.0.0.1:{port}/readyz'
        daemon.stop()

        # A connection of the server that keeps the event loop running until the client in the same loop has read the
        # last response, as the loop stops as soon as the server has closed the connection of the client
        held = socket.create_connection(('127.0.0.1', port))

        def second(ua, tx):
            results.append((tx.res.code, tx.res.body, tx.res.headers.connection))
            held.close()

        def first(ua, tx):
            results.append((tx.res.code, tx.res.body, tx.res.headers.connection))
            Pyjo.IOLoop.stop_gracefully()
            ua.get(url, second)

        Pyjo.IOLoop.next_tick(lambda loop: ua.get(url, first))
        timer = Pyjo.IOLoop.timer(5, lambda loop: loop.stop())
        daemon.run()
        Pyjo.IOLoop.remove(timer)
    is_ok(results[0], (200, b'ok', None), 'ready')
    is_ok(results[1], (503, b'[-]shutdown failed: reason withheld\nreadyz check failed\n', 'close'), 'not ready')
    ok(Pyjo.IOLoop.is_stopping(), 'stopping')
    Pyjo.IOLoop.reset()
    ok(not Pyjo.IOLoop.is_stopping(), 'not stopping')

done_testing()
