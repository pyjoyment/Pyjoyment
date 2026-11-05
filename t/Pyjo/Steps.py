import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Steps
import Pyjo.UserAgent

from Pyjo.Steps import Command, Request, Sleep, Steps
from Pyjo.Test import *
from Pyjoyment.Lite import app, get

import gc
import os
import re
import sys
import time


# The steps of a coroutine or a generator, blocking and non-blocking, against an application of the test

app.log.level = 'fatal'


@get('/token')
def token(c):
    if c.req.headers.header('X-Token') != 'secret':
        return c.render(json={'error': 'Forbidden'}, status=403)
    c.render(json={'token': 'abc'})


ua = Pyjo.UserAgent.new()
ua.server.app = app


# The value or the error of a promise, of its own event loop
def wait(promise):
    result = {}
    promise.then(
        lambda *values: result.update(value=values[0] if len(values) == 1 else values),
        lambda reason: result.update(error=reason),
    ).wait()
    return result


async def request(url, secret='secret'):
    tx = await Request(ua.build_tx('GET', url, {'X-Token': secret}))
    if tx.res.code != 200:
        raise Pyjo.Exception.new(f'Cannot get a token: {tx.res.code}')
    return tx.res.json('/token')


with subtest('Requests'):
    is_ok(Steps(request('/token')).run(ua), 'abc', 'request, blocking')
    result = wait(Steps(request('/token')).run_p(ua))
    is_ok(result['value'], 'abc', 'request, non-blocking')

    throws_ok(lambda: Steps(request('/token', 'wrong')).run(ua), re.compile(r'^Cannot get a token: 403'), 'status')
    result = wait(Steps(request('/token', 'wrong')).run_p(ua))
    like_ok(str(result['error']), re.compile(r'^Cannot get a token: 403'), 'status, non-blocking')

    async def refused():
        closed = Pyjo.UserAgent.new(connect_timeout=2)
        try:
            await Request(closed.build_tx('GET', 'http://127.0.0.1:1/token'), closed)
        except Pyjo.Exception.object as e:
            return str(e)

    like_ok(
        Steps(refused()).run(ua),
        re.compile(r'^GET http://127\.0\.0\.1:1/token: '),
        'connection error thrown in, blocking',
    )
    result = wait(Steps(refused()).run_p(ua))
    like_ok(
        result['value'], re.compile(r'^GET http://127\.0\.0\.1:1/token: '), 'connection error thrown in, non-blocking'
    )

    # Only the promise of the request refers to the steps, whose user agent the event loop refers to weakly
    promise = Steps(refused()).run_p(ua)
    Pyjo.IOLoop.next_tick(lambda loop: gc.collect())
    result = wait(promise)
    like_ok(
        result.get('value'),
        re.compile(r'^GET http://127\.0\.0\.1:1/token: '),
        'steps kept while they wait, non-blocking',
    )

    # The user agent of the request, whose event start changes it, not the one of run
    other = Pyjo.UserAgent.new()
    other.server.app = app
    other.on('start', lambda ua, tx: tx.req.headers.header('X-Token', 'secret'))

    async def signed():
        tx = await Request(other.build_tx('GET', '/token'), other)
        return tx.res.json('/token')

    is_ok(Steps(signed()).run(ua), 'abc', 'user agent of the request, blocking')
    is_ok(wait(Steps(signed()).run_p(ua))['value'], 'abc', 'user agent of the request, non-blocking')
    other.close()

with subtest('Commands'):

    async def command(*args):
        return await Command([sys.executable, '-c', *args], b'input')

    code, out, err = Steps(command('import sys; print(sys.stdin.read()); sys.exit(3)')).run(ua)
    is_ok((code, out.strip(), err), (3, b'input', b''), 'program, blocking')

    throws_ok(
        lambda: Steps(Command.new(['/nonexistent/program']).__await__()).run(ua),
        re.compile(r'^Cannot run /nonexistent/program: '),
        'program that cannot be run',
    )

    if sys.platform == 'win32':
        skip('the reactor watches no pipes on Windows', 2)
    else:
        result = wait(Steps(command('print("out")')).run_p(ua))
        is_ok((result['value'][0], result['value'][1].strip()), (0, b'out'), 'program, non-blocking')
        result = wait(Steps(Command.new(['/nonexistent/program']).__await__()).run_p(ua))
        like_ok(str(result['error']), re.compile(r'^Cannot run /nonexistent/program: '), 'cannot run, non-blocking')

with subtest('Environment and timeout of commands'):
    env = {**os.environ, 'PYJO_STEPS_TEST': 'environment'}
    printenv = Command.new([sys.executable, '-c', 'import os; print(os.environ["PYJO_STEPS_TEST"])'], env=env)
    code, out, _ = Steps(printenv.__await__()).run(ua)
    is_ok((code, out.strip()), (0, b'environment'), 'environment, blocking')

    sleep = [sys.executable, '-c', 'import time; time.sleep(10)']
    start = time.monotonic()
    throws_ok(
        lambda: Steps(Command.new(sleep, timeout=0.5).__await__()).run(ua),
        re.compile(r'^Cannot run \S+: no exit in 0\.5 seconds'),
        'timeout, blocking',
    )
    ok(time.monotonic() - start < 5, 'killed at the timeout')

    if sys.platform == 'win32':
        skip('the reactor watches no pipes on Windows', 4)
    else:
        result = wait(Steps(printenv.__await__()).run_p(ua))
        is_ok((result['value'][0], result['value'][1].strip()), (0, b'environment'), 'environment, non-blocking')

        start = time.monotonic()
        result = wait(Steps(Command.new(sleep, timeout=0.5).__await__()).run_p(ua))
        like_ok(str(result['error']), re.compile(r'^Cannot run \S+: no exit in 0\.5 seconds'), 'timeout, non-blocking')
        ok(time.monotonic() - start < 5, 'killed at the timeout, non-blocking')

        start = time.monotonic()
        result = wait(Steps(Command.new([sys.executable, '-c', 'pass'], timeout=10).__await__()).run_p(ua))
        ok(result['value'][0] == 0 and time.monotonic() - start < 5, 'exit before the timeout, without its timer')

with subtest('Sleeps'):

    async def nap(seconds):
        start = time.monotonic()
        value = await Sleep(seconds)
        return value, time.monotonic() - start

    # time.monotonic of Windows before Python 3.13 counts the ticks of GetTickCount64, of 15.6 milliseconds, so a time
    # that it measures may be a tick short
    tick = time.get_clock_info('monotonic').resolution

    value, slept = Steps(nap(0.2)).run(ua)
    is_ok(value, None, 'nothing, blocking')
    ok(slept >= 0.2 - tick, 'slept, blocking')

    # The event loop runs the other events while the steps sleep
    ticks = []
    timer = Pyjo.IOLoop.recurring(0.02, lambda loop: ticks.append(time.monotonic()))
    result = wait(Steps(nap(0.2)).run_p(ua))
    Pyjo.IOLoop.remove(timer)
    value, slept = result['value']
    is_ok(value, None, 'nothing, non-blocking')
    # A timer of an event loop on libuv, as the ones of uvloop and gevent, counts whole milliseconds of a clock that
    # libuv rounds down, so it may be due up to a millisecond early by time.monotonic
    ok(slept >= 0.19 - tick, 'slept, non-blocking')
    ok(len(ticks) >= 3, 'other events meanwhile')

    async def retried():
        for attempt in range(3):
            tx = await Request(ua.build_tx('GET', '/token', {'X-Token': 'secret' if attempt == 2 else 'wrong'}))
            if tx.res.code == 200:
                return attempt, tx.res.json('/token')
            await Sleep(0.01)

    is_ok(Steps(retried()).run(ua), (2, 'abc'), 'request tried again, blocking')
    is_ok(wait(Steps(retried()).run_p(ua))['value'], (2, 'abc'), 'request tried again, non-blocking')

with subtest('Generators and coroutines'):

    def generated():
        tx = yield Request(ua.build_tx('GET', '/token', {'X-Token': 'secret'}))
        yield Sleep(0.01)
        code, out, _ = yield Command([sys.executable, '-c', 'print("process")'])
        return f'{tx.res.json("/token")} {out.decode().strip()} {code}'

    async def awaited(steps):
        return 'awaited ' + await steps

    def yielded(steps):
        return 'yielded ' + (yield from steps)

    is_ok(Steps(generated()).run(ua), 'abc process 0', 'generator')
    is_ok(
        Steps(yielded(Steps(awaited(Steps(generated()))))).run(ua),
        'yielded awaited abc process 0',
        'generator over coroutine over generator',
    )

    if sys.platform == 'win32':
        skip('the reactor watches no pipes on Windows', 1)
    else:
        result = wait(Steps(awaited(Steps(yielded(Steps(generated()))))).run_p(ua))
        is_ok(result['value'], 'awaited yielded abc process 0', 'coroutine over generator, non-blocking')

    async def promised():
        try:
            await Pyjo.Promise.new()
        except Exception:
            return None

    throws_ok(
        lambda: Steps(promised()).run(ua),
        re.compile(r'^Steps await \w+: only a Request, a Command, a Sleep and Steps'),
        'promise awaited, not thrown in',
    )
    result = wait(Steps(promised()).run_p(ua))
    ok(isinstance(result['error'], TypeError), 'promise awaited, non-blocking')
    like_ok(str(result['error']), re.compile(r'^Steps await'), 'error of the promise')

    is_ok(Pyjo.Steps.Steps, Pyjo.Steps.object, 'class of the module')
    isa_ok(Pyjo.Steps.new(generated()), Pyjo.Steps.object, 'new of the module')

ua.close()

done_testing()
