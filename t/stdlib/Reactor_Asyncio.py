import Pyjo.Exception
import Pyjo.Reactor.Asyncio

from Pyjo.Test import *

import asyncio
import os
import re
import socket
import subprocess
import sys
import time


with subtest('Coroutines run in the loop of the reactor'):
    reactor = Pyjo.Reactor.Asyncio.new()
    got = []

    async def coroutine():
        got.append(asyncio.get_running_loop() is reactor.loop)
        await asyncio.sleep(0.01)
        got.append('slept')

    task = reactor.loop.create_task(coroutine())
    reactor.timer(0.05, lambda reactor: reactor.stop())
    reactor.start()
    is_deeply_ok(got, [True, 'slept'], 'task ran while the reactor did')
    ok(task.done(), 'task done')

with subtest('Callbacks see the running loop'):
    reactor = Pyjo.Reactor.Asyncio.new()
    loops = []
    reactor.next_tick(lambda reactor: loops.append(asyncio.get_running_loop()))
    reactor.start()
    is_deeply_ok(loops, [reactor.loop], 'loop of the reactor')

with subtest('Inside asyncio.run'):
    got = []

    async def main():
        reactor = Pyjo.Reactor.Asyncio.new()
        got.append(reactor.loop is asyncio.get_running_loop())
        reactor.timer(0, lambda reactor: got.append('timer'))
        reactor.next_tick(lambda reactor: got.append('next tick'))
        reactor.start()
        got.append('start returned')
        await asyncio.sleep(0.01)
        got.append(reactor.is_running)

    asyncio.run(main())
    is_deeply_ok(got, [True, 'start returned', 'timer', 'next tick', False], 'the running loop watches the events')

with subtest('Unhandled error in a loop that runs already'):
    contexts = []

    def die(reactor):
        raise Exception('Oops')

    async def main():
        asyncio.get_running_loop().set_exception_handler(lambda loop, context: contexts.append(context))
        reactor = Pyjo.Reactor.Asyncio.new()
        reactor.timer(0, die)
        await asyncio.sleep(0.01)

    asyncio.run(main())
    is_ok(len(contexts), 1, 'exception handler of asyncio')
    isa_ok(contexts[0]['exception'], Pyjo.Exception.object, 'error event')

with subtest('Unhandled error raised by start'):
    reactor = Pyjo.Reactor.Asyncio.new()

    def die(reactor):
        raise ValueError('Oops')

    reactor.timer(0, die)
    try:
        reactor.start()
    except Pyjo.Exception.object as e:
        like_ok(str(e), r'Timer failed: Oops', 'message')
        isa_ok(e.__cause__.__cause__, ValueError, 'cause of the error')
    ok(not reactor.is_running, 'not running')

with subtest('Handles and timers move to the loop that is running'):
    reactor = Pyjo.Reactor.Asyncio.new()
    got = []
    reactor.timer(0.01, lambda reactor: got.append(asyncio.get_running_loop()))
    own = reactor.loop

    async def outer():
        # the reactor moves when it is used in the running loop
        reactor.loop
        await asyncio.sleep(0.05)
        return asyncio.get_running_loop()

    running = asyncio.run(outer())
    is_deeply_ok(got, [running], 'the timer ran in the loop that was running')
    reactor.timer(0, lambda reactor: got.append('back'))
    reactor.start()
    is_ok(got[-1], 'back', 'and back in a loop of its own')
    ok(reactor.loop is own, 'the same loop of its own')

with subtest('The next tick moves to the loop that is running with its timer'):
    reactor = Pyjo.Reactor.Asyncio.new()
    got = []

    # The timer of the next tick in a loop of its own that does not run, as one that stopped in the middle of a tick, as
    # in Pyjo.Promise.wait, leaves it
    reactor.next_tick(lambda reactor: got.append('before'))

    async def outer():
        reactor.next_tick(lambda reactor: got.append(asyncio.get_running_loop()))
        await asyncio.sleep(0.05)
        return asyncio.get_running_loop()

    running = asyncio.run(outer())
    is_deeply_ok(got, ['before', running], 'the next ticks ran in the loop that was running')
    reactor.close()

with subtest('A blocking request to an application after a wait for a promise'):
    import Pyjo.IOLoop
    import Pyjo.Promise
    import Pyjo.UserAgent
    import Pyjoyment

    # The promise of the action settles on the event loop of the singleton, whose reactor follows the one of the
    # blocking request, also after Pyjo.Promise.wait has stopped it in the middle of a tick
    if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
        skip('needs Pyjo.Reactor.Asyncio as the reactor of the singleton, as another one does not follow a loop', 1)
    else:
        app = Pyjoyment.new()
        app.log.level = 'fatal'
        app.routes.get('/promise', lambda c: Pyjo.Promise.resolve('promise').then(lambda text: c.render(text=text)))
        texts = []
        for _ in range(3):
            with Pyjo.UserAgent.new(request_timeout=5) as ua:
                ua.server.app = app
                tx = ua.get('/promise')
                texts.append(tx.res.text if tx.error is None else tx.error['message'])
            Pyjo.Promise.resolve(1).wait()
        is_deeply_ok(texts, ['promise', 'promise', 'promise'], 'each request gets its response')

with subtest('A timer that again restarts waits for its new time'):
    reactor = Pyjo.Reactor.Asyncio.new()
    fired = []
    start = time.monotonic()
    id = reactor.timer(0.2, lambda reactor: fired.append(time.monotonic() - start))
    reactor.timer(0.1, lambda reactor: reactor.again(id))
    reactor.timer(0.5, lambda reactor: reactor.stop())
    reactor.start()
    is_ok(len(fired), 1, 'fired once')
    ok(fired[0] >= 0.29, 'not before the time from the restart')

with subtest('A shorter time of again comes first'):
    reactor = Pyjo.Reactor.Asyncio.new()
    fired = []
    id = reactor.timer(1, lambda reactor: fired.append('timer'))
    reactor.again(id, 0.05)
    reactor.timer(0.5, lambda reactor: reactor.stop())
    reactor.start()
    is_deeply_ok(fired, ['timer'], 'fired before the old time')

with subtest('A recurring timer that again restarts'):
    reactor = Pyjo.Reactor.Asyncio.new()
    fired = []
    start = time.monotonic()
    id = reactor.recurring(0.1, lambda reactor: fired.append(time.monotonic() - start))
    reactor.timer(0.05, lambda reactor: reactor.again(id))
    reactor.timer(0.4, lambda reactor: reactor.stop())
    reactor.start()
    ok(len(fired) >= 1, 'fired')
    ok(fired[0] >= 0.14, 'not before the time from the restart')

with subtest('Start runs the loop once for many events'):
    reactor = Pyjo.Reactor.Asyncio.new()
    loop = reactor.loop
    runs = []
    run_forever = loop.run_forever

    def counted():
        runs.append(1)
        return run_forever()

    loop.run_forever = counted
    ticks = []

    def tick(reactor):
        ticks.append(1)
        if len(ticks) == 5:
            reactor.stop()

    reactor.recurring(0, tick)
    reactor.start()
    del loop.run_forever
    is_ok(len(ticks), 5, 'five events')
    is_ok(len(runs), 1, 'one run of the loop')
    ok(not reactor.is_running, 'not running')

with subtest('Start stops once nothing is left to watch'):
    reactor = Pyjo.Reactor.Asyncio.new()
    fired = []
    reactor.timer(0.01, lambda reactor: fired.append('first'))
    reactor.timer(0.02, lambda reactor: fired.append('second'))
    reactor.start()
    is_deeply_ok(fired, ['first', 'second'], 'both timers')
    ok(not reactor.is_running, 'not running')

with subtest('Start stops from a callback of asyncio'):
    reactor = Pyjo.Reactor.Asyncio.new()
    reactor.recurring(0.01, lambda reactor: None)
    reactor.loop.call_later(0.05, reactor.stop)
    reactor.start()
    ok(not reactor.is_running, 'stopped')
    reactor.reset()

with subtest('A handle removed while another loop runs'):
    with Pyjo.Reactor.Asyncio.new() as reactor:
        a, b = socket.socketpair()
        reactor.io(a, lambda reactor, writable: None).watch(a, True, False)
        loop = reactor.loop

        async def remove():
            reactor.remove(a)

        asyncio.run(remove(), loop_factory=asyncio.SelectorEventLoop)
        ok(not loop.remove_reader(a.fileno()), 'not left in the loop that watched it')
        a.close()
        b.close()

with subtest('Handles'):
    reactor = Pyjo.Reactor.Asyncio.new()
    a, b = socket.socketpair()
    reactor.io(a.fileno(), lambda reactor, writable: reactor.stop())
    reactor.start()
    ok(reactor.remove(a), 'file descriptor and socket are the same handle')
    a.close()
    throws_ok(lambda: reactor.remove(a), re.compile(r'^Handle is closed'), 'closed handle')
    b.close()

with subtest('An event loop that cannot watch handles'):
    with Pyjo.Reactor.Asyncio.new() as reactor:
        isa_ok(reactor.loop, asyncio.SelectorEventLoop, 'loop of its own, also on Windows')

    # The ProactorEventLoop of Windows, as asyncio.run makes it there
    class NoReader(asyncio.SelectorEventLoop):
        def add_reader(self, *args, **kwargs):
            raise NotImplementedError

    loop = NoReader()
    reactor = Pyjo.Reactor.Asyncio.new(loop=loop)
    a, b = socket.socketpair()
    throws_ok(
        lambda: reactor.io(a, lambda reactor, writable: None),
        re.compile(r'^Event loop __main__\.NoReader cannot watch handles, an asyncio\.SelectorEventLoop can'),
        'says what it needs',
    )
    reactor.remove(a)
    a.close()
    b.close()
    loop.close()

with subtest('The event loop of a reactor that exists at the exit is closed'):
    script = (
        'import Pyjo.Reactor.Asyncio\n'
        'reactor = Pyjo.Reactor.Asyncio.new()\n'
        'reactor.timer(0, lambda reactor: reactor.stop())\n'
        'reactor.start()\n'
    )
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    env = {**os.environ, 'PYTHONPATH': root, 'PYTHONWARNINGS': 'always::ResourceWarning'}
    process = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    is_ok(process.returncode, 0, 'exit status')
    unlike_ok(process.stderr, r'unclosed event loop', 'no ResourceWarning')

with subtest('The tasks that are left at the exit are cancelled before the event loop closes'):
    script = (
        'import Pyjo.Reactor.Asyncio\n'
        'reactor = Pyjo.Reactor.Asyncio.new()\n'
        'future = reactor.future()\n'
        'async def wait():\n'
        '    try:\n'
        '        await future\n'
        '    finally:\n'
        '        print("cancelled")\n'
        'reactor.run_coroutine(wait(), lambda value: None, lambda e: print(type(e).__name__))\n'
        'reactor.timer(0, lambda reactor: reactor.stop())\n'
        'reactor.start()\n'
    )
    root = os.path.join(os.path.dirname(__file__), '..', '..')
    env = {**os.environ, 'PYTHONPATH': root, 'PYTHONWARNINGS': 'always::ResourceWarning'}
    process = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    is_ok(process.returncode, 0, 'exit status')
    is_ok(process.stdout, 'cancelled\nCancelledError\n', 'task cancelled')
    is_ok(process.stderr, '', 'no task destroyed while it is pending')

with subtest('A reactor moves to a new loop in the child of a fork'):
    if not hasattr(os, 'fork'):
        skip('no os.fork', 3)
    else:
        script = """
import Pyjo.Reactor.Asyncio, os, socket

reactor = Pyjo.Reactor.Asyncio.new()
parent = reactor.loop
a, b = socket.socketpair()
got = []
reactor.io(a, lambda reactor, writable: (got.append(a.recv(10)), reactor.stop())).watch(a, True, False)
reactor.timer(0, lambda reactor: b.send(b'io'))
r, w = os.pipe()
pid = os.fork()
if not pid:
    reactor.start()
    os.write(w, f'{reactor.loop is not parent} {got}'.encode())
    os._exit(0)
os.close(w)
os.waitpid(pid, 0)
child = os.read(r, 100).decode()
reactor.start()
print(child, reactor.loop is parent, got)
a.close()
b.close()
"""
        root = os.path.join(os.path.dirname(__file__), '..', '..')
        env = {**os.environ, 'PYTHONPATH': root, 'PYTHONWARNINGS': 'always::ResourceWarning,error::DeprecationWarning'}
        process = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
        is_ok(process.returncode, 0, 'exit status')
        is_ok(process.stdout, "True [b'io'] True [b'io']\n", 'a new loop in the child, the loop of the parent in it')
        is_ok(process.stderr, '', 'no warning')

with subtest('The child of a fork does not close the loops of the parent at its exit'):
    if not hasattr(os, 'fork'):
        skip('no os.fork', 3)
    else:
        script = """
import Pyjo.Reactor.Asyncio, asyncio, gc, os, sys

reactor = Pyjo.Reactor.Asyncio.new()
reactor.timer(0, lambda reactor: reactor.stop())
reactor.start()
pid = os.fork()
if not pid:
    reactor.timer(0, lambda reactor: reactor.stop())
    reactor.start()
    sys.exit(0)
os.waitpid(pid, 0)


async def follow():
    reactor.loop
    pid = os.fork()
    if not pid:
        gc.collect()
        os._exit(0)
    os.waitpid(pid, 0)


asyncio.run(follow())
print('done')
"""
        root = os.path.join(os.path.dirname(__file__), '..', '..')
        env = {**os.environ, 'PYTHONPATH': root, 'PYTHONWARNINGS': 'always::ResourceWarning,error::DeprecationWarning'}
        process = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
        is_ok(process.returncode, 0, 'exit status')
        is_ok(process.stdout, 'done\n', 'the parent goes on')
        is_ok(process.stderr, '', 'neither the exit of the child nor its garbage collector closes them')

with subtest('The threshold of a slow callback of a loop of its own'):
    duration = os.environ.pop('PYJO_ASYNCIO_SLOW_CALLBACK', None)
    try:
        with Pyjo.Reactor.Asyncio.new() as reactor:
            is_ok(reactor.loop.slow_callback_duration, 0.1, 'default of asyncio')
        os.environ['PYJO_ASYNCIO_SLOW_CALLBACK'] = '5'
        with Pyjo.Reactor.Asyncio.new() as reactor:
            is_ok(reactor.loop.slow_callback_duration, 5.0, 'PYJO_ASYNCIO_SLOW_CALLBACK')
        loop = asyncio.new_event_loop()
        with Pyjo.Reactor.Asyncio.new(loop=loop) as reactor:
            is_ok(reactor.loop.slow_callback_duration, 0.1, 'a loop that it is given stays as it is')
        loop.close()
    finally:
        if duration is None:
            os.environ.pop('PYJO_ASYNCIO_SLOW_CALLBACK', None)
        else:
            os.environ['PYJO_ASYNCIO_SLOW_CALLBACK'] = duration

with subtest('Context manager'):
    with Pyjo.Reactor.Asyncio.new() as reactor:
        loop = reactor.loop
        ok(not loop.is_closed(), 'event loop')
    ok(loop.is_closed(), 'event loop closed at the end of the block')

with subtest('close'):
    reactor = Pyjo.Reactor.Asyncio.new()
    loop = reactor.loop
    ok(not loop.is_closed(), 'event loop')
    reactor.close()
    ok(loop.is_closed(), 'event loop closed')

    # The tasks that are left are cancelled and end before the event loop closes
    reactor = Pyjo.Reactor.Asyncio.new()
    loop = reactor.loop
    rejected = []
    reactor.run_coroutine(asyncio.sleep(10), lambda value: None, rejected.append)
    reactor.close()
    ok(loop.is_closed(), 'event loop closed')
    ok(len(rejected) and isinstance(rejected[0], asyncio.CancelledError), 'task cancelled')

done_testing()
