import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Reactor.Asyncio

from Pyjo.Test import *

import asyncio
import concurrent.futures
import gc
import os
import subprocess
import sys
import time
import warnings


# The tests of asyncio need the reactor of asyncio, whatever PYJO_REACTOR says
Pyjo.IOLoop.singleton.reactor = Pyjo.Reactor.Asyncio.new()

with subtest('await in an asyncio task'):

    async def main():
        got = [
            await Pyjo.Promise.resolve('one'),
            await Pyjo.Promise.resolve('a', 'b'),
            await Pyjo.Promise.resolve(),
            await Pyjo.Promise.timer(0.01, 'timer'),
        ]
        try:
            await Pyjo.Promise.reject(KeyError('key'))
        except KeyError as e:
            got.append(type(e).__name__)
        try:
            await Pyjo.Promise.reject('reason', 'more')
        except Pyjo.Exception.object as e:
            got.append(e.message)
        return got

    # A SelectorEventLoop, as the ProactorEventLoop that asyncio.run makes on Windows cannot watch handles
    is_deeply_ok(
        asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop),
        ['one', ('a', 'b'), None, 'timer', 'KeyError', 'reason'],
        'values, tuple, None, and exceptions',
    )

with subtest('asyncio.gather'):

    async def gather():
        return await asyncio.gather(Pyjo.Promise.timer(0.01, 'promise'), asyncio.sleep(0, 'coroutine'))

    is_deeply_ok(
        asyncio.run(gather(), loop_factory=asyncio.SelectorEventLoop),
        ['promise', 'coroutine'],
        'promises and coroutines together',
    )

with subtest('A coroutine with asyncio in a promise'):

    @Pyjo.Promise.coroutine
    async def slow(value):
        await asyncio.sleep(0.01)
        return await Pyjo.Promise.timer(0.01, value)

    got = []
    slow('done').then(got.append).wait()
    is_deeply_ok(got, ['done'], 'wait runs the loop until the task is done')

    @Pyjo.Promise.coroutine
    async def nothing():
        await asyncio.sleep(0)

    got = []
    nothing().then(lambda *values: got.append(values)).wait()
    is_deeply_ok(got, [()], 'None is no value')

    @Pyjo.Promise.coroutine
    async def fails():
        await asyncio.sleep(0)
        raise ValueError('Oops')

    got = []
    fails().catch(got.append).wait()
    isa_ok(got[0], ValueError, 'rejected with the exception')

with subtest('A coroutine without asyncio'):
    code = """
import asyncio, Pyjo.Promise

@Pyjo.Promise.coroutine
async def twice(value):
    first = await Pyjo.Promise.timer(0.01, value)
    return first * 2

@Pyjo.Promise.coroutine
async def foreign():
    await asyncio.sleep(0)

got = []
twice(21).then(got.append).wait()
foreign().catch(lambda e: got.append(type(e).__name__)).wait()
print(got)
"""
    env = dict(os.environ, PYJO_REACTOR='Pyjo.Reactor.Poll')
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    is_ok(result.stdout, "[42, 'TypeError']\n", 'promises of Pyjoyment only')

with subtest('wait and for of Pyjo.Iterator inside asyncio.run'):
    code = """
import asyncio, Pyjo.IOLoop, Pyjo.Iterator, Pyjo.Promise

async def main():
    got = [Pyjo.IOLoop.is_running()]
    promise = Pyjo.Promise.timer(0.01, 'timer')
    promise.wait()
    got.append('wait returned')
    got.append(await promise)
    try:
        list(Pyjo.Iterator.new([1]).map(lambda e: Pyjo.Promise.timer(0.01, e)))
    except RuntimeError as e:
        got.append(str(e))
    return got

print(asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop))
"""
    # A process of its own with a timeout, as a wait that starts the loop again and again would never return
    env = dict(os.environ, PYJO_REACTOR='Pyjo.Reactor.Asyncio')
    try:
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        output = 'timeout'
    is_ok(
        output,
        "[True, 'wait returned', 'timer', 'A promise cannot be waited for in a running event loop, await it instead']\n",
        'the event loop of asyncio runs, wait returns at once and for fails',
    )

with subtest('Promise of a future or a task of asyncio'):

    async def futures():
        loop = asyncio.get_running_loop()
        got = [await Pyjo.Promise.new(loop.run_in_executor(None, lambda: 'executor'))]
        got.append(await Pyjo.Promise.new(asyncio.ensure_future(asyncio.sleep(0.01, 'task'))))
        future = loop.create_future()
        loop.call_later(0.01, future.set_result, ('a', 'b'))
        got.append(await Pyjo.Promise.new(future))
        failed = loop.create_future()
        failed.set_exception(KeyError('key'))
        try:
            await Pyjo.Promise.new(failed)
        except KeyError as e:
            got.append(type(e).__name__)
        cancelled = loop.create_future()
        cancelled.cancel()
        try:
            await Pyjo.Promise.new(cancelled)
        except asyncio.CancelledError as e:
            got.append(type(e).__name__)
        return got

    is_deeply_ok(
        asyncio.run(futures(), loop_factory=asyncio.SelectorEventLoop),
        ['executor', 'task', ('a', 'b'), 'KeyError', 'CancelledError'],
        'value, tuple as one value, exception and cancellation',
    )

    got = []
    Pyjo.Promise.new(Pyjo.Promise.timer(0.01, 'promise')).then(got.append).wait()
    is_deeply_ok(got, ['promise'], 'promise of a promise')

with subtest('Future of asyncio'):

    async def futures():
        future = Pyjo.Promise.timer(0.01, 'one').to_future()
        got = [isinstance(future, asyncio.Future), future.get_loop() is asyncio.get_running_loop()]
        got.append(await future)
        got.append(await asyncio.wait_for(Pyjo.Promise.timer(0.01, 'a', 'b').to_future(), 5))
        got.append(await Pyjo.Promise.resolve().to_future())
        got.append(await asyncio.gather(Pyjo.Promise.timer(0.01, 'g').to_future(), asyncio.sleep(0, 's')))
        try:
            await Pyjo.Promise.reject(KeyError('key')).to_future()
        except KeyError as e:
            got.append(type(e).__name__)
        try:
            await Pyjo.Promise.reject('reason').to_future()
        except Pyjo.Exception.object as e:
            got.append(e.message)
        done = []
        future = Pyjo.Promise.timer(0.01, 'callback').to_future()
        future.add_done_callback(lambda future: done.append(future.result()))
        await asyncio.sleep(0.05)
        got.append(done)
        return got

    is_deeply_ok(
        asyncio.run(futures(), loop_factory=asyncio.SelectorEventLoop),
        [True, True, 'one', ('a', 'b'), None, ['g', 's'], 'KeyError', 'reason', ['callback']],
        'future of the loop, values and exceptions',
    )

    with warnings.catch_warnings(record=True) as warn:
        warnings.simplefilter('always')
        promise = Pyjo.Promise.new()
        future = promise.to_future()
        future.cancel()
        promise.reject('Too late')
        Pyjo.Promise.timer(0.01).wait()
        del promise
        gc.collect()
        ok(future.cancelled(), 'cancelled future')
        is_ok(len(warn), 0, 'rejection handled by the future')

with subtest('Future of concurrent.futures without asyncio'):
    code = """
import asyncio, concurrent.futures, threading, Pyjo.Promise

future = Pyjo.Promise.timer(0.05, 'thread').to_future()
got = [type(future).__module__ + '.' + type(future).__name__]
thread = threading.Thread(target=lambda: got.append(future.result(timeout=60)))
thread.start()
Pyjo.Promise.timer(0.1).wait()
thread.join()

futures = [Pyjo.Promise.timer(0.01, 'a').to_future(), Pyjo.Promise.reject('b').to_future()]
Pyjo.Promise.timer(0.05).wait()
done, pending = concurrent.futures.wait(futures, timeout=0)
got.append((len(done), len(pending), futures[0].result(), str(futures[1].exception()).strip()))

loop = asyncio.new_event_loop()
Pyjo.Promise.new(loop.create_future()).catch(lambda e: got.append(type(e).__name__)).wait()
loop.close()

with concurrent.futures.ThreadPoolExecutor() as executor:
    Pyjo.Promise.new(executor.submit(lambda: 'pool')).then(got.append).wait()
print(got)
"""
    env = dict(os.environ, PYJO_REACTOR='Pyjo.Reactor.Poll')
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    is_ok(
        result.stdout,
        "['concurrent.futures._base.Future', 'thread', (2, 0, 'a', 'b'), 'TypeError', 'pool']\n",
        'waited for in another thread and with concurrent.futures, no future of asyncio, a promise of a pool',
    )

with subtest('Promise of a future of concurrent.futures'):
    got = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        Pyjo.Promise.new(executor.submit(lambda: (time.sleep(0.05), 'thread')[1])).then(got.append).wait()
        Pyjo.Promise.new(executor.submit(lambda: ('a', 'b'))).then(got.append).wait()
        Pyjo.Promise.new(executor.submit(lambda: None)).then(lambda *values: got.append(values)).wait()
        Pyjo.Promise.new(executor.submit(lambda: 1 / 0)).catch(lambda e: got.append(type(e).__name__)).wait()
        busy = executor.submit(time.sleep, 0.05)
        later = executor.submit(lambda: 'never')
        later.cancel()
        Pyjo.Promise.new(later).catch(lambda e: got.append(type(e).__name__)).wait()
    done = concurrent.futures.Future()
    done.set_result('done')
    Pyjo.Promise.new(done).then(got.append).wait()
    is_deeply_ok(
        got,
        ['thread', ('a', 'b'), (), 'ZeroDivisionError', 'CancelledError', 'done'],
        'value, tuple as one value, none, exception, cancellation and a future that is done',
    )

    async def futures():
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return await Pyjo.Promise.new(executor.submit(lambda: 'awaited'))

    is_ok(asyncio.run(futures(), loop_factory=asyncio.SelectorEventLoop), 'awaited', 'awaited in a task of asyncio')

with subtest('warnings'):
    with warnings.catch_warnings(record=True) as warn:
        warnings.simplefilter('always')
        Pyjo.Promise.reject('Oops')
        gc.collect()
        is_ok(len(warn), 1, 'one warning')
        is_ok(warn[0].category, UserWarning, 'UserWarning')
        is_ok(str(warn[0].message), 'Unhandled rejected promise: Oops', 'message')

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        Pyjo.Promise.reject('Ignored')
        gc.collect()
        pass_ok('warnings can be ignored')

done_testing()
