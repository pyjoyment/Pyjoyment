import Pyjo.IOLoop
import Pyjo.Server.Daemon

from Pyjo.Test import *

# The examples request real hosts, so a daemon with an application of Pyjoyment.Lite answers them instead
from Pyjoyment.Lite import app

import contextlib
import io
import os
import sys
import time


if os.name == 'nt':
    plan(skip_all='child processes need pipes that the reactor watches, which Windows does not have')

app.log.level = 'fatal'

app.routes.any('/', {'text': '<html><head><title>Mojolicious</title></head></html>'})

daemon = Pyjo.Server.Daemon.new(app=app, ioloop=Pyjo.IOLoop.singleton, listen=['http://127.0.0.1'], silent=True)
port = daemon.start().ports()[0]

# The programs of the examples, as Python, which every system of the tests has
HOSTNAME = [sys.executable, '-c', 'print("myhost")']
TOKEN = [sys.executable, '-c', 'import os; print(os.environ["AUDIENCE"])']


def local(ua):
    # Blocking requests run on the singleton too, where the daemon is
    ua.ioloop = Pyjo.IOLoop.singleton

    @ua.on('start')
    def start(ua, tx):
        url = tx.req.url
        url.scheme, url.host, url.port = 'http', '127.0.0.1', port
        tx.req.proxy = None

    return ua


@contextlib.contextmanager
def output():
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        yield stdout


with subtest('Synopsis'):
    from Pyjo.Steps import Command, Request, Sleep, Steps
    from Pyjo.UserAgent import UserAgent

    ua = local(UserAgent())

    async def hello():
        tx = await Request(ua.build_tx('GET', 'https://mojolicious.org'))
        await Sleep(0.5)
        code, out, err = await Command(HOSTNAME)
        return f'{out.decode().strip()}: {tx.result.dom().at("title").text}'

    with output() as stdout:
        print(Steps(hello()).run(ua))
        Steps(hello()).run_p(ua).then(lambda text: print(text)).wait()
    is_ok(stdout.getvalue(), 'myhost: Mojolicious\nmyhost: Mojolicious\n', 'blocking and non-blocking')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Steps

    # The steps of another coroutine, awaited
    async def twice():
        return [await Pyjo.Steps.Steps(hello()), await Pyjo.Steps.Steps(hello())]

    is_ok(Steps(twice()).run(ua), ['myhost: Mojolicious', 'myhost: Mojolicious'], 'awaited steps')

with subtest('Command'):

    async def commands(audience):
        code, out, err = await Command.new(HOSTNAME)
        hostname = out.decode().strip()
        code, out, err = await Command.new(TOKEN, env={**os.environ, 'AUDIENCE': audience}, timeout=30)
        return hostname, out.decode().strip()

    is_ok(Steps(commands('aud')).run(ua), ('myhost', 'aud'), 'program and its environment')

    async def awaited(command):
        code, out, err = await command
        return code, out.strip(), err

    is_ok(Steps(awaited(Command.new(HOSTNAME))).run(ua), (0, b'myhost', b''), 'await command')

with subtest('Request'):

    async def requests():
        tx = await Request.new(ua.build_tx('GET', 'https://mojolicious.org'))
        tx = await Request.new(tx, ua)
        return tx.res.code

    is_ok(Steps(requests()).run(ua), 200, 'transaction and its user agent')

    async def awaited_request(request):
        tx = await request
        return tx.res.code

    is_ok(Steps(awaited_request(Request.new(ua.build_tx('GET', '/')))).run(ua), 200, 'await request')

with subtest('Sleep'):

    async def sleeps():
        start = time.monotonic()
        await Sleep.new(0.5)
        sleep = Sleep.new(0.1)
        await sleep
        return time.monotonic() - start

    ok(Steps(sleeps()).run(ua) >= 0.6, 'sleeps, blocking')
    result = []
    Pyjo.Steps.new(sleeps()).run_p(ua).then(result.append).wait()
    # A timer of an event loop on libuv, as the ones of uvloop and gevent, counts whole milliseconds of a clock that
    # libuv rounds down, so each one may be due up to a millisecond early by time.monotonic
    ok(result[0] >= 0.59, 'sleeps, non-blocking')

with subtest('Steps'):

    class Provider:
        async def fetch(self):
            tx = await Request(ua.build_tx('GET', '/'))
            return tx.res.code

    provider = Provider()
    steps = Pyjo.Steps.new(provider.fetch())
    is_ok(steps.run(ua), 200, 'new and run')

    async def outer():
        steps = Pyjo.Steps.new(provider.fetch())
        value = await steps
        return value

    def generated():
        steps = Pyjo.Steps.new(provider.fetch())
        value = yield from steps
        return value

    is_ok(Steps(outer()).run(ua), 200, 'await steps')
    is_ok(Steps(generated()).run(ua), 200, 'yield from steps')

    steps = Pyjo.Steps.new(provider.fetch())
    value = steps.run(ua)
    is_ok(value, 200, 'run')
    steps = Pyjo.Steps.new(provider.fetch())
    promise = steps.run_p(ua)
    result = []
    promise.then(result.append).wait()
    is_ok(result, [200], 'run_p')

ua.close()
daemon.stop()

done_testing()
