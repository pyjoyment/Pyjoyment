from Pyjo.Test import *

import contextlib
import io
import os
import subprocess
import sys


with subtest('Synopsis'):
    from Pyjo.EventEmitter import EventEmitter

    class Cat(EventEmitter):
        # Emit events
        def poke(self):
            self.emit('roar', 3)

    # Subscribe to events
    tiger = Cat()

    @tiger.on('roar')
    def roar(tiger, times):
        for _ in range(times):
            print('RAWR!')

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        tiger.poke()
    is_ok(output.getvalue(), 'RAWR!\nRAWR!\nRAWR!\n', 'roars three times')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.EventEmitter

    class Cat(Pyjo.EventEmitter.object):
        # Emit events
        def poke(self):
            self.emit('roar', 3)

    # Subscribe to events
    tiger = Cat.new()

    # F811 "Redefinition of unused `roar`": the synopsis defines it in both forms
    @tiger.on('roar')
    def roar(tiger, times):  # noqa: F811
        for _ in range(times):
            print('RAWR!')

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        tiger.poke()
    is_ok(output.getvalue(), 'RAWR!\nRAWR!\nRAWR!\n', 'roars three times')

with subtest('error'):
    e = Pyjo.EventEmitter.new()
    e.on('error', lambda e, err: ...)
    ok(e.has_subscribers('error'), 'subscribed')

    e = Pyjo.EventEmitter.new()
    e.on('error', lambda e, err: print(f'This looks bad: {err}'))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        e.emit('error', 'Oops')
    is_ok(output.getvalue(), 'This looks bad: Oops\n', 'handled')

    e = Pyjo.EventEmitter.new()
    try:
        e.emit('error', ValueError('Oops'))
    except Pyjo.Exception.object as err:
        is_ok(err.message, 'Pyjo.EventEmitter.Pyjo_EventEmitter: Oops', 'unhandled')
        isa_ok(err.__cause__, ValueError, 'cause')

with subtest('Debugging'):
    env = dict(os.environ, PYJO_EVENTEMITTER_DEBUG='1')
    code = 'import Pyjo.EventEmitter; Pyjo.EventEmitter.new().emit("foo")'
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    is_ok(result.stderr, '-- Emit foo in Pyjo.EventEmitter.Pyjo_EventEmitter (0)\n', 'diagnostics')

with subtest('catch'):
    e = Pyjo.EventEmitter.new()
    is_ok(e.catch(lambda e, err: ...), e, 'returns the emitter')
    ok(e.has_subscribers('error'), 'subscribed')

    # Longer version
    e = Pyjo.EventEmitter.new()
    e.on('error', lambda e, err: ...)
    ok(e.has_subscribers('error'), 'subscribed')

with subtest('emit'):
    e = Pyjo.EventEmitter.new()
    got = []
    e.on('foo', lambda e, *args: got.append(args))
    is_ok(e.emit('foo'), e, 'returns the emitter')
    e = e.emit('foo', 123)
    is_deeply_ok(got, [(), (123,)], 'arguments')

with subtest('events'):
    import Pyjo.Promise

    e = Pyjo.EventEmitter.new()
    got = []

    @Pyjo.Promise.coroutine
    async def foo(events):
        async for args in events:
            got.append(args)

    promise = foo(e.events('foo'))
    e.emit('foo', 1).emit('close')
    promise.wait()
    is_deeply_ok(got, [(1,)], 'arguments of the events')

    ws = Pyjo.EventEmitter.new()

    @Pyjo.Promise.coroutine
    async def messages(events):
        async for (message,) in events:
            print(f'Message: {message}')

    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        promise = messages(ws.events('message'))
        ws.emit('message', 'hi').emit('close')
        promise.wait()
    is_ok(stdout.getvalue(), 'Message: hi\n', 'printed')

    @Pyjo.Promise.coroutine
    async def capitals(events):
        # The messages in capitals, in a chain
        async for message in events:
            print(f'Message: {message}')

    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        promise = capitals(ws.events('message').map(lambda args: args[0].upper()))
        ws.emit('message', 'hi').emit('close')
        promise.wait()
    is_ok(stdout.getvalue(), 'Message: HI\n', 'printed in capitals')

with subtest('has_subscribers'):
    e = Pyjo.EventEmitter.new()
    boolean = e.has_subscribers('foo')
    is_ok(boolean, False, 'no subscribers')

with subtest('on'):
    e = Pyjo.EventEmitter.new()
    cb = e.on('foo', lambda e, *args: ...)
    is_ok(e.subscribers('foo'), [cb], 'returns the callback')

    e.on('foo', lambda e, *args: ...)
    is_ok(len(e.subscribers('foo')), 2, 'subscribed')

    @e.on('foo')
    def cb(e, *args): ...

    @e.on
    def foo(e, *args): ...

    is_ok(e.subscribers('foo')[2:], [cb, foo], 'decorators')

with subtest('once'):
    e = Pyjo.EventEmitter.new()
    cb = e.once('foo', lambda e, *args: ...)
    is_ok(e.subscribers('foo'), [cb], 'returns the wrapper')

    e.once('foo', lambda e, *args: ...)
    e.emit('foo')
    ok(not e.has_subscribers('foo'), 'unsubscribed')

with subtest('once_p'):
    e = Pyjo.EventEmitter.new()
    promise = e.once_p('foo')
    e.emit('foo', 'bar')
    got = []
    promise.then(got.append).wait()
    is_deeply_ok(got, ['bar'], 'promise')

    child = Pyjo.EventEmitter.new()
    closed = child.once_p('close')

    @Pyjo.Promise.coroutine
    async def wait():
        code, signal = await closed
        got.append((code, signal))

    child.emit('close', 0, None)
    wait().wait()
    is_deeply_ok(got[-1], (0, None), 'code and signal')

with subtest('subscribers'):
    e = Pyjo.EventEmitter.new()
    one = e.on('foo', lambda e: ...)
    two = e.on('foo', lambda e: ...)
    three = e.on('foo', lambda e: ...)
    subscribers = e.subscribers('foo')
    is_ok(subscribers, [one, two, three], 'all subscribers')

    # Unsubscribe last subscriber
    e.unsubscribe('foo', e.subscribers('foo')[-1])
    is_ok(e.subscribers('foo'), [one, two], 'last unsubscribed')

    # Change order of subscribers
    e.subscribers('foo').reverse()
    is_ok(e.subscribers('foo'), [two, one], 'reversed')

with subtest('unsubscribe'):
    e = Pyjo.EventEmitter.new()
    cb = e.on('foo', lambda e: ...)
    e.on('foo', lambda e: ...)
    e = e.unsubscribe('foo', cb)
    is_ok(len(e.subscribers('foo')), 1, 'one unsubscribed')
    e = e.unsubscribe('foo')
    ok(not e.has_subscribers('foo'), 'all unsubscribed')

done_testing()
