from Pyjo.Test import *

import contextlib
import io
import os
import sys


# The documentation describes the default reactor
os.environ.pop('PYJO_REACTOR', None)


with subtest('Synopsis'):
    from Pyjo.Reactor import Reactor

    class MyEventLoop(Reactor):
        def again(self, id, after=None): ...
        def io(self, handle, cb): ...
        @property
        def is_running(self): ...
        def next_tick(self, cb): ...
        def one_tick(self): ...
        def recurring(self, after, cb): ...
        def remove(self, remove): ...
        def reset(self): ...
        def start(self): ...
        def stop(self): ...
        def timer(self, after, cb): ...
        def watch(self, handle, read, write): ...

    isa_ok(MyEventLoop(), Reactor, 'subclass')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Reactor

    class MyEventLoop(Pyjo.Reactor.object):
        def again(self, id, after=None): ...
        def io(self, handle, cb): ...
        @property
        def is_running(self): ...
        def next_tick(self, cb): ...
        def one_tick(self): ...
        def recurring(self, after, cb): ...
        def remove(self, remove): ...
        def reset(self): ...
        def start(self): ...
        def stop(self): ...
        def timer(self, after, cb): ...
        def watch(self, handle, read, write): ...

    isa_ok(MyEventLoop.new(), Pyjo.Reactor.object, 'subclass')

with subtest('error'):
    reactor = Pyjo.Reactor.new()
    reactor.on('error', lambda reactor, err: ...)
    ok(reactor.has_subscribers('error'), 'subscribed')

    reactor = Pyjo.Reactor.new()
    reactor.on('error', lambda reactor, err: print(f'Something very bad happened: {err}'))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        reactor.emit('error', 'Oops')
    is_ok(output.getvalue(), 'Something very bad happened: Oops\n', 'handled')

with subtest('detect'):
    name = Pyjo.Reactor.detect()
    is_ok(name, 'Pyjo.Reactor.Asyncio', 'default')

    # Instantiate best reactor implementation available
    reactor = sys.modules[Pyjo.Reactor.detect()].new()
    isa_ok(reactor, Pyjo.Reactor.object, 'reactor')

with subtest('Alternative reactors'):
    from Pyjo.File import tempdir

    import os
    import subprocess

    dist = tempdir()
    dist.child('Pyjo', 'Reactor').make_path()
    dist.child('Pyjo', 'Reactor', 'MyLoop.py').spew(
        """# Pyjo/Reactor/MyLoop.py of another distribution
import Pyjo.Reactor.Asyncio

import asyncio
import selectors

class Pyjo_Reactor_MyLoop(Pyjo.Reactor.Asyncio.object):
    def __init__(self, loop=None):
        super().__init__(loop=loop or asyncio.SelectorEventLoop(selectors.SelectSelector()))

new = Pyjo_Reactor_MyLoop.new
object = Pyjo_Reactor_MyLoop
"""
    )
    code = """
import Pyjo.IOLoop
reactor = Pyjo.IOLoop.singleton.reactor
reactor.timer(0, lambda reactor: print('timer'))
reactor.start()
print(type(reactor).__name__, type(reactor.loop._selector).__name__)
"""
    env = dict(os.environ, PYJO_REACTOR='Pyjo.Reactor.MyLoop')
    env['PYTHONPATH'] = os.pathsep.join([os.getcwd(), dist.to_str()])
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    is_ok(result.stdout, 'timer\nPyjo_Reactor_MyLoop SelectSelector\n', 'reactor of another distribution')

with subtest('awaitable and coroutine'):
    import Pyjo.Promise

    reactor = Pyjo.Reactor.new()
    promise = Pyjo.Promise.resolve('done')
    awaitable = reactor.awaitable(promise)
    ok(hasattr(awaitable, '__await__'), 'awaitable')

    async def coro():
        await reactor.awaitable(promise)
        return 'done'

    got = []
    reactor.run_coroutine(coro(), got.append, got.append)
    Pyjo.IOLoop.one_tick()
    is_deeply_ok(got, ['done'], 'driven without asyncio')

    # Cancel the coroutine, whose finally blocks run
    events = []

    async def main():
        try:
            await reactor.awaitable(Pyjo.Promise.new(cancel=lambda: events.append('promise cancelled')))
        finally:
            events.append('finally')

    got = []
    cancel = reactor.run_coroutine(main(), got.append, got.append)
    cancel()
    is_deeply_ok(events, ['finally', 'promise cancelled'], 'cancelled where it waits, with its promise')
    isa_ok(got[0], Pyjo.Reactor.CancelledError, 'rejected')
    cancel()
    is_ok(len(got), 1, 'once')

with subtest('future'):
    import concurrent.futures

    future = Pyjo.Reactor.new().future()
    isa_ok(future, concurrent.futures.Future, 'future without an event loop')

with subtest('Abstract methods'):
    reactor = Pyjo.Reactor.new()
    for call in (
        lambda: reactor.again('id'),
        lambda: reactor.again('id', 0.5),
        lambda: reactor.io(
            0, lambda reactor, writable: print('Handle is writable' if writable else 'Handle is readable')
        ),
        lambda: reactor.is_running,
        lambda: reactor.next_tick(lambda reactor: None),
        lambda: reactor.one_tick(),
        lambda: reactor.recurring(0.25, lambda reactor: None),
        lambda: reactor.remove(0),
        lambda: reactor.remove('id'),
        lambda: reactor.reset(),
        lambda: reactor.start(),
        lambda: reactor.stop(),
        lambda: reactor.timer(0.5, lambda reactor: None),
        lambda: reactor.watch(0, True, False),
    ):
        throws_ok(call, NotImplementedError, 'meant to be overloaded')

done_testing()
