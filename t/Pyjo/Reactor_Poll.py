import Pyjo.Reactor
import Pyjo.Reactor.Poll

from Pyjo.Loader import load_class
from Pyjo.Test import *

import os
import signal
import socket
import time


# Unlike Mojolicious: skipped when PYJO_REACTOR names the reactor of another distribution, which runs the tests of
# Pyjoyment on it and has a test of its own reactor
if os.environ.get('PYJO_REACTOR', '') not in ('', 'Pyjo.Reactor.Asyncio', 'Pyjo.Reactor.Poll'):
    plan(skip_all=f'PYJO_REACTOR is {os.environ["PYJO_REACTOR"]}, not a reactor of Pyjoyment')

# BEGIN { $ENV{MOJO_REACTOR} = 'Mojo::Reactor::Poll' }, before Pyjo.IOLoop is loaded
os.environ['PYJO_REACTOR'] = 'Pyjo.Reactor.Poll'


def eval_(cb):
    try:
        cb()
    except Exception as e:
        return e


# Shared between subtests, since I/O watchers and timers keep firing across them
readable = writable = 0


def rw_cb(reactor, is_writable):
    global readable, writable
    if is_writable:
        writable += 1
    else:
        readable += 1


with subtest('Instantiation'):
    reactor = Pyjo.Reactor.Poll.new()
    is_ok(type(reactor), Pyjo.Reactor.Poll.object, 'right object')
    is_ok(type(Pyjo.Reactor.Poll.new()), Pyjo.Reactor.Poll.object, 'right object')
    del reactor
    is_ok(type(Pyjo.Reactor.Poll.new()), Pyjo.Reactor.Poll.object, 'right object')
    ok(not load_class('Pyjo.IOLoop'), 'use Pyjo.IOLoop')
    reactor = Pyjo.IOLoop.singleton.reactor
    is_ok(type(reactor), Pyjo.Reactor.Poll.object, 'right object')

with subtest('Make sure it stops automatically when not watching for events'):
    triggered = 0

    def triggered_cb(loop):
        global triggered
        triggered += 1

    Pyjo.IOLoop.next_tick(triggered_cb)
    Pyjo.IOLoop.start()
    ok(triggered, 'reactor waited for one event')
    started = time.time()
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.one_tick()
    ok(time.time() < (started + 10), 'stopped automatically')

with subtest('Listen'):
    listen = socket.create_server(('127.0.0.1', 0), backlog=5)
    port = listen.getsockname()[1]
    reactor.io(listen, rw_cb).watch(listen, False, False).watch(listen, True, True)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(not readable, 'handle is not readable')
    ok(not writable, 'handle is not writable')

with subtest('Connect'):
    client = socket.create_connection(('127.0.0.1', port))
    reactor.timer(1, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(not writable, 'handle is not writable')

with subtest('Accept'):
    server = listen.accept()[0]
    ok(reactor.remove(listen), 'removed')
    ok(not reactor.remove(listen), 'not removed again')
    readable = writable = 0
    reactor.io(client, rw_cb)
    reactor.again(reactor.timer(0.025, lambda reactor: reactor.stop()))
    reactor.start()
    ok(not readable, 'handle is not readable')
    ok(writable, 'handle is writable')
    client.sendall(b'hello!\n')
    time.sleep(1)
    ok(reactor.remove(client), 'removed')
    readable = writable = 0
    reactor.io(server, rw_cb)
    reactor.watch(server, True, False)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(not writable, 'handle is not writable')
    readable = writable = 0
    reactor.watch(server, True, True)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(writable, 'handle is writable')
    readable = writable = 0
    reactor.watch(server, False, False)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(not readable, 'handle is not readable')
    ok(not writable, 'handle is not writable')
    readable = writable = 0
    reactor.watch(server, True, False)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(not writable, 'handle is not writable')
    readable = writable = 0
    reactor.io(server, rw_cb)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(writable, 'handle is writable')

with subtest('Timers'):
    timer = recurring = 0

    def timer_cb(reactor):
        global timer
        timer += 1

    def recurring_cb(reactor):
        global recurring
        recurring += 1

    reactor.timer(0, timer_cb)
    ok(reactor.remove(reactor.timer(0, timer_cb)), 'removed')
    id = reactor.recurring(0, recurring_cb)
    readable = writable = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(timer, 'timer was triggered')
    ok(recurring, 'recurring was triggered')
    done = False
    readable = writable = timer = recurring = 0

    def done_cb(reactor):
        global done
        done = reactor.is_running

    reactor.timer(0.025, done_cb)
    while not done:
        reactor.one_tick()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(recurring, 'recurring was triggered again')
    readable = writable = timer = recurring = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(recurring, 'recurring was triggered again')
    ok(reactor.remove(id), 'removed')
    ok(not reactor.remove(id), 'not removed again')
    readable = writable = timer = recurring = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(not recurring, 'recurring was not triggered again')
    readable = writable = timer = recurring = 0
    next_tick = 0

    def next_tick_cb(reactor):
        global next_tick
        next_tick += 1

    is_ok(reactor.next_tick(next_tick_cb), None, 'returned None')
    id = reactor.recurring(0, recurring_cb)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(recurring, 'recurring was triggered again')
    ok(next_tick, 'next tick was triggered')


with subtest('Reset'):

    def reset_failed_cb(reactor):
        raise Exception('Reset failed')

    reactor.next_tick(reset_failed_cb)
    reactor.reset()
    readable = writable = recurring = 0
    reactor.next_tick(lambda reactor: reactor.stop())
    reactor.start()
    ok(not readable, 'io event was not triggered again')
    ok(not writable, 'io event was not triggered again')
    ok(not recurring, 'recurring was not triggered again')
    reactor2 = Pyjo.Reactor.Poll.new()
    is_ok(type(reactor2), Pyjo.Reactor.Poll.object, 'right object')

with subtest('Ordered next_tick'):
    result = []
    for i in range(1, 11):
        reactor.next_tick(lambda reactor, i=i: result.append(i))
    reactor.start()
    is_deeply_ok(result, list(range(1, 11)), 'right result')

with subtest('Reset while watchers are active'):
    writable = 0

    def reset_cb(reactor, is_writable):
        global writable
        writable += 1
        reactor.reset()

    for handle in (client, server):
        reactor.io(handle, reset_cb).watch(handle, False, True)
    reactor.start()
    is_ok(writable, 1, 'only one handle was writable')
    client.close()
    server.close()

with subtest('Concurrent reactors'):
    timer = 0
    reactor.recurring(0, timer_cb)
    timer2 = 0

    def timer2_cb(reactor):
        global timer2
        timer2 += 1

    reactor2.recurring(0, timer2_cb)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(timer, 'timer was triggered')
    ok(not timer2, 'timer was not triggered')
    timer = timer2 = 0
    reactor2.timer(0.025, lambda reactor: reactor.stop())
    reactor2.start()
    ok(not timer, 'timer was not triggered')
    ok(timer2, 'timer was triggered')
    timer = timer2 = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(timer, 'timer was triggered')
    ok(not timer2, 'timer was not triggered')
    timer = timer2 = 0
    reactor2.timer(0.025, lambda reactor: reactor.stop())
    reactor2.start()
    ok(not timer, 'timer was not triggered')
    ok(timer2, 'timer was triggered')
    reactor.reset()

with subtest('Restart timer'):
    single = pair = last = 0

    def single_cb(reactor):
        global single
        single += 1

    def one_cb(reactor):
        global pair, last
        if single and pair:
            last += 1
        pair += 1
        reactor.stop() if pair > 1 else reactor.again(two)

    def two_cb(reactor):
        global pair, last
        if single and pair:
            last += 1
        pair += 1
        reactor.stop() if pair > 1 else reactor.again(one)

    reactor.timer(0.025, single_cb)
    one = reactor.timer(0.025, one_cb)
    two = reactor.timer(0.025, two_cb)
    reactor.start()
    is_ok(pair, 2, 'timer pair was triggered')
    ok(single, 'single timer was triggered')
    ok(last, 'timers were triggered in the right order')

with subtest('Reset timer'):
    before = time.monotonic()
    after = None
    again = 0

    def after_cb(reactor):
        global after
        after = time.monotonic()

    def again_cb(reactor):
        global again
        again += 1
        if again > 3:
            reactor.remove(two)

    def restart_cb(reactor):
        reactor.again(one, 0.025)
        reactor.again(two, 0.025)

    one = reactor.timer(300, after_cb)
    two = reactor.recurring(300, again_cb)
    reactor.timer(0.025, restart_cb)
    reactor.start()
    ok(after, 'timer was triggered')
    ok((after - before) < 200, 'less than 200 seconds')
    is_ok(again, 4, 'recurring timer triggered four times')

with subtest('Restart inactive timer'):
    id = reactor.timer(0, lambda reactor: None)
    ok(reactor.remove(id), 'removed')
    err = eval_(lambda: reactor.again(id))
    like_ok(str(err), r'Timer not active', 'right error')

with subtest('Change inactive I/O watcher'):
    ok(not reactor.remove(listen), 'not removed again')
    err = eval_(lambda: reactor.watch(listen, True, True))
    like_ok(str(err), r'I/O watcher not active', 'right error')
    listen.close()

with subtest('Error'):
    err = None

    def error_cb(reactor, e):
        global err
        reactor.stop()
        err = e

    def die_cb(reactor):
        raise Exception('works!\n')

    reactor.unsubscribe('error').on('error', error_cb)
    reactor.timer(0, die_cb)
    reactor.start()
    like_ok(str(err), r'works!', 'right error')

    # Not in Mojolicious: the arguments of a callback, which Perl does not check
    reactor.timer(0, lambda: None)
    reactor.start()
    like_ok(
        str(err),
        r'takes 0 positional arguments but 1 was given: the callbacks of a reactor get the reactor first',
        'hint',
    )

with subtest('Reset events'):
    reactor.on('error', lambda reactor, err: None)
    ok(reactor.has_subscribers('error'), 'has subscribers')
    reactor.reset()
    ok(not reactor.has_subscribers('error'), 'no subscribers')

with subtest('Recursion'):
    timer = 0

    def recursion_cb(reactor):
        global timer
        timer += 1
        reactor.one_tick()

    reactor = Pyjo.Reactor.Poll.new()
    reactor.timer(0, recursion_cb)
    reactor.one_tick()
    is_ok(timer, 1, 'timer was triggered once')

with subtest('Detection'):
    is_ok(Pyjo.Reactor.Poll.object.detect(), 'Pyjo.Reactor.Poll', 'right class')

with subtest('Reactor in control'):
    is_ok(type(Pyjo.IOLoop.singleton.reactor), Pyjo.Reactor.Poll.object, 'right object')
    ok(not Pyjo.IOLoop.is_running(), 'loop is not running')
    buffer = b''
    server_err = server_running = client_err = client_running = None

    def server_cb(loop, stream, cid):
        global server_err, server_running
        stream.write(b'test', lambda stream: stream.write(b'321'))
        server_running = Pyjo.IOLoop.is_running()
        server_err = eval_(lambda: Pyjo.IOLoop.start())

    id = Pyjo.IOLoop.server(server_cb, address='127.0.0.1')
    port = Pyjo.IOLoop.acceptor(id).port

    def client_cb(loop, err, stream):
        global client_err, client_running

        def read_cb(stream, chunk):
            global buffer
            buffer += chunk
            if buffer != b'test321':
                return
            Pyjo.IOLoop.singleton.reactor.stop()

        stream.on('read', read_cb)
        client_running = Pyjo.IOLoop.is_running()
        client_err = eval_(lambda: Pyjo.IOLoop.start())

    Pyjo.IOLoop.client(client_cb, port=port)
    Pyjo.IOLoop.singleton.reactor.start()
    ok(not Pyjo.IOLoop.is_running(), 'loop is not running')
    like_ok(str(server_err), r'^Pyjo.IOLoop already running', 'right error')
    like_ok(str(client_err), r'^Pyjo.IOLoop already running', 'right error')
    ok(server_running, 'loop is running')
    ok(client_running, 'loop is running')

with subtest('Abstract methods'):
    base = Pyjo.Reactor.new()
    err = eval_(lambda: base.again(''))
    like_ok(str(err), r'Method "again" not implemented by subclass', 'right error')
    err = eval_(lambda: base.io(0, lambda reactor, writable: None))
    like_ok(str(err), r'Method "io" not implemented by subclass', 'right error')
    err = eval_(lambda: base.is_running)
    like_ok(str(err), r'Method "is_running" not implemented by subclass', 'right error')
    err = eval_(lambda: base.next_tick(lambda reactor: None))
    like_ok(str(err), r'Method "next_tick" not implemented by subclass', 'right error')
    err = eval_(lambda: base.one_tick())
    like_ok(str(err), r'Method "one_tick" not implemented by subclass', 'right error')
    err = eval_(lambda: base.recurring(0, lambda reactor: None))
    like_ok(str(err), r'Method "recurring" not implemented by subclass', 'right error')
    err = eval_(lambda: base.remove(''))
    like_ok(str(err), r'Method "remove" not implemented by subclass', 'right error')
    err = eval_(lambda: base.reset())
    like_ok(str(err), r'Method "reset" not implemented by subclass', 'right error')
    err = eval_(lambda: base.start())
    like_ok(str(err), r'Method "start" not implemented by subclass', 'right error')
    err = eval_(lambda: base.stop())
    like_ok(str(err), r'Method "stop" not implemented by subclass', 'right error')
    err = eval_(lambda: base.timer(0, lambda reactor: None))
    like_ok(str(err), r'Method "timer" not implemented by subclass', 'right error')
    err = eval_(lambda: base.watch(0, True, True))
    like_ok(str(err), r'Method "watch" not implemented by subclass', 'right error')

# Not in Mojolicious: a callback of next_tick from a signal handler, which Python runs in the middle of what the reactor
# does, as the servers stop gracefully, with enough timers that the handler interrupts the reactor that looks for the
# first of them
with subtest('next_tick from a signal handler'):
    if not hasattr(signal, 'setitimer'):
        plan(skip_all='signal.setitimer is required')
    reactor = Pyjo.Reactor.Poll.new()
    for _ in range(100000):
        reactor.timer(10, lambda reactor: None)
    ticks = []
    handler = signal.signal(signal.SIGALRM, lambda signum, frame: reactor.next_tick(lambda reactor: ticks.append(1)))
    signal.setitimer(signal.ITIMER_REAL, 0.001, 0.001)
    reactor.timer(0.3, lambda reactor: reactor.stop())
    try:
        err = eval_(lambda: reactor.start())
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
    is_ok(err, None, 'no error')
    ok(ticks, 'callbacks of the signal handler')
    reactor.reset()

# Not in Mojolicious: blocking code, which the reactor without asyncio calls as it is
with subtest('Blocking code'):
    reactor = Pyjo.Reactor.Poll.new()
    is_deeply_ok(reactor.blocking(lambda a, b=None: (a, b), 1, b=2), (1, 2), 'arguments and result')
    isa_ok(eval_(lambda: reactor.blocking(lambda: 1 / 0)), ZeroDivisionError, 'exception')
    is_deeply_ok(Pyjo.Reactor.new().blocking(lambda: 'base'), 'base', 'base class')

done_testing()
