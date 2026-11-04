import Pyjo.IOLoop
import Pyjo.IOLoop.ChildProcess
import Pyjo.IOLoop.Client
import Pyjo.IOLoop.Server
import Pyjo.IOLoop.Stream
import Pyjo.Promise
import Pyjo.String.Bytes

from Pyjo.Test import *

import contextlib
import io
import os
import re
import socket
import sys
import time


# Left out from Mojolicious: BEGIN { $ENV{MOJO_REACTOR} = 'Mojo::Reactor::Poll' }, the tests run on the reactor that
# Pyjo.Reactor.detect() gives, Pyjo.Reactor.Asyncio unless PYJO_REACTOR names another one


def eval_(cb):
    try:
        cb()
    except Exception as e:
        return e


with subtest('Defaults'):
    loop = Pyjo.IOLoop.new()
    is_ok(loop.max_connections, 1000, 'right default')
    loop = Pyjo.IOLoop.new(max_connections=10)
    is_ok(loop.max_connections, 10, 'right value')

with subtest('Double start'):
    err = None

    def double_start(loop):
        global err
        err = eval_(lambda: loop.start())
        loop.stop()

    Pyjo.IOLoop.next_tick(double_start)
    Pyjo.IOLoop.start()
    like_ok(str(err), r'^Pyjo.IOLoop already running', 'right error')

with subtest('Double one_tick'):
    err = None

    def double_one_tick(loop):
        global err
        err = eval_(lambda: loop.one_tick())

    Pyjo.IOLoop.next_tick(double_one_tick)
    Pyjo.IOLoop.one_tick()
    like_ok(str(err), r'^Pyjo.IOLoop already running', 'right error')

with subtest('Basic functionality'):
    ticks = timer = hirestimer = 0

    def ticks_cb(loop):
        global ticks
        ticks += 1

    def timer_cb(loop):
        global timer
        loop.timer(0, lambda loop: loop.stop())
        timer += 1

    def hirestimer_cb(loop):
        global hirestimer
        hirestimer += 1

    loop = Pyjo.IOLoop.new()
    id = loop.recurring(0, ticks_cb)
    loop.timer(1, timer_cb)
    loop.timer(0.25, hirestimer_cb)
    loop.start()
    ok(timer, 'recursive timer works')
    ok(hirestimer, 'hires timer works')
    loop.one_tick()
    ok(ticks > 2, 'more than two ticks')

    # Run again without first tick event handler
    before = ticks
    after = 0

    def after_cb(loop):
        global after
        after += 1

    id2 = loop.recurring(0, after_cb)
    loop.remove(id)
    loop.timer(0.5, lambda loop: loop.stop())
    loop.start()
    loop.one_tick()
    loop.remove(id2)
    ok(after > 1, 'more than one tick')
    is_ok(ticks, before, 'no additional ticks')

with subtest('Recurring timer'):
    count = 0

    def count_cb(loop):
        global count
        count += 1

    loop = Pyjo.IOLoop.new()
    id = loop.recurring(0.1, count_cb)
    loop.timer(0.5, lambda loop: loop.stop())
    loop.start()
    loop.one_tick()
    loop.remove(id)
    ok(count > 1, 'more than one recurring event')
    ok(count < 10, 'less than ten recurring events')


def handle_and_reset(freeze):
    global handle, handle2, reset, close, count, running, riding, timer
    handle = handle2 = None
    reset = close = 0

    def reset_cb(loop):
        global reset
        reset += 1

    def close_cb(stream):
        global close
        close += 1

    def server_cb(loop, stream, id):
        global handle
        stream.on('close', close_cb)
        handle = stream.handle
        Pyjo.IOLoop.stop()

    def accept_cb(server, accepted):
        global handle2
        handle2 = accepted

    Pyjo.IOLoop.singleton.on('reset', reset_cb)
    id = Pyjo.IOLoop.server(server_cb, address='127.0.0.1')
    port = Pyjo.IOLoop.acceptor(id).port
    Pyjo.IOLoop.acceptor(id).on('accept', accept_cb)
    id2 = Pyjo.IOLoop.client(lambda loop, err, stream: None, address='127.0.0.1', port=port)
    Pyjo.IOLoop.start()
    count = running = timer = 0

    def timer_cb(loop):
        global timer
        timer += 1

    def reset_tick(loop):
        global running, riding
        Pyjo.IOLoop.reset(freeze=freeze)
        running = Pyjo.IOLoop.is_running()

        # Not in Mojolicious: whether a new reactor of the same class runs in the loop that runs, as one on an event loop
        # that does not nest
        riding = type(Pyjo.IOLoop.singleton.reactor).new().is_running

    Pyjo.IOLoop.recurring(10, timer_cb)
    Pyjo.IOLoop.next_tick(reset_tick)
    Pyjo.IOLoop.start()
    return id, id2


with subtest('Handle and reset'):
    id, id2 = handle_and_reset(False)
    ok(not running, 'not running')
    is_ok(count, 0, 'no recurring events')
    ok(not Pyjo.IOLoop.acceptor(id), 'acceptor has been removed')
    ok(not Pyjo.IOLoop.stream(id2), 'stream has been removed')
    is_ok(handle, handle2, 'handles are equal')
    isa_ok(handle, socket.socket, 'right reference')
    is_ok(reset, 1, 'reset event has been emitted once')
    is_ok(close, 1, 'close event has been emitted once')

with subtest('Handle and reset with freeze'):
    id, id2 = handle_and_reset(True)
    # Unlike Mojolicious: a reactor on an event loop that does not nest, as of asyncio or Trio, runs after the freeze in
    # the loop that the frozen one runs, as any new reactor there, where Mojo starts the new reactor inside the old one
    if riding:
        ok(running, 'running in the loop of the frozen reactor')
    else:
        ok(not running, 'not running')
    is_ok(count, 0, 'no recurring events')
    ok(not Pyjo.IOLoop.acceptor(id), 'acceptor has been removed')
    ok(not Pyjo.IOLoop.stream(id2), 'stream has been removed')
    is_ok(handle, handle2, 'handles are equal')
    isa_ok(handle, socket.socket, 'right reference')
    is_ok(reset, 1, 'reset event has been emitted once')
    ok(not close, 'close event has not been emitted')

with subtest('The poll reactor stops when there are no events being watched anymore'):
    started = time.time()
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.one_tick()
    Pyjo.IOLoop.reset()
    ok(time.time() < (started + 10), 'stopped automatically')

with subtest('Reset events'):
    Pyjo.IOLoop.singleton.on('finish', lambda loop: None)
    ok(Pyjo.IOLoop.singleton.has_subscribers('finish'), 'has subscribers')
    Pyjo.IOLoop.reset()
    ok(not Pyjo.IOLoop.singleton.has_subscribers('finish'), 'no subscribers')

with subtest('Stream'):
    buffer = b''

    def server_cb(loop, stream, id):
        global buffer
        buffer += b'accepted'

        def read(stream, chunk):
            global buffer
            buffer += chunk
            if buffer != b'acceptedhello':
                return
            stream.write(b'wo').write(b'').write(b'rld', lambda stream: stream.close())

        stream.on('read', read)

    id = Pyjo.IOLoop.server(server_cb, address='127.0.0.1')
    port = Pyjo.IOLoop.acceptor(id).port
    promise = Pyjo.Promise.new()
    handle = None

    def client_cb(loop, err, stream):
        global handle

        def close(stream):
            global buffer
            buffer += b'should not happen'

        def error(stream, err):
            global buffer
            buffer += b'should not happen either'

        handle = stream.steal_handle()
        promise.resolve()
        stream.on('close', close)
        stream.on('error', error)

    Pyjo.IOLoop.client(client_cb, port=port)
    promise.wait()
    stream = Pyjo.IOLoop.Stream.new(handle)
    is_ok(stream.timeout, 15, 'right default')
    stream.timeout = 16
    is_ok(stream.timeout, 16, 'right timeout')
    id = Pyjo.IOLoop.stream(stream)

    def read(stream, chunk):
        global buffer
        buffer += chunk

    stream.on('close', lambda stream: Pyjo.IOLoop.stop())
    stream.on('read', read)
    stream.write(b'hello')
    ok(Pyjo.IOLoop.stream(id), 'stream exists')
    is_ok(stream.timeout, 16, 'right timeout')
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.timer(0.25, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()
    ok(not Pyjo.IOLoop.stream(id), 'stream does not exist anymore')
    is_ok(buffer, b'acceptedhelloworld', 'right result')
    # Not in Mojolicious: no id is no stream, as Mojo looks up undef, which is not a reference
    is_ok(Pyjo.IOLoop.stream(None), None, 'no stream without id')

with subtest('Removed listen socket'):
    loop = Pyjo.IOLoop.new()
    id = loop.server(lambda loop, stream, id: None, address='127.0.0.1')
    port = loop.acceptor(id).port
    connected = False

    def connected_cb(loop, err, stream):
        global connected
        loop.remove(id)
        loop.stop()
        connected = True

    loop.client(connected_cb, port=port)
    fd = loop.acceptor(id).handle.fileno()
    like_ok(os.environ['PYJO_REUSE'], rf'(?:^|\,)127\.0\.0\.1:{port}:{fd}', 'file descriptor can be reused')
    loop.start()
    unlike_ok(os.environ['PYJO_REUSE'], rf'(?:^|\,)127\.0\.0\.1:{port}:{fd}', 'environment is clean')
    ok(connected, 'connected')
    ok(not loop.acceptor(id), 'acceptor has been removed')

with subtest('Removed connection (with promise)'):
    removed = 0
    promise = Pyjo.Promise.new()

    def removed_cb(*values):
        global removed
        removed += 1

    def server_cb(loop, stream, id):
        stream.on('close', lambda stream: promise.resolve())

    promise.then(removed_cb)
    id = Pyjo.IOLoop.server(server_cb, address='127.0.0.1')
    port = Pyjo.IOLoop.acceptor(id).port
    promise2 = Pyjo.Promise.new()

    def client_cb(loop, err, stream):
        stream.on('close', lambda stream: promise2.resolve())
        loop.remove(id)

    id = Pyjo.IOLoop.client(client_cb, port=port)
    Pyjo.Promise.all(promise, promise2).wait()
    is_ok(removed, 1, 'connection has been removed')

with subtest('Stream throttling'):
    client = server = client_after = server_before = server_after = None
    waiting = []

    def server_cb(loop, stream, id):
        def read(stream, chunk):
            global server

            def first(loop):
                global server_before

                def second(loop):
                    global server_after, client_after
                    server_after = server
                    client_after = client
                    waiting.append(stream.bytes_waiting)
                    stream.start()
                    Pyjo.IOLoop.timer(0.5, lambda loop: Pyjo.IOLoop.stop())

                server_before = server
                stream.stop()
                stream.write(b'works!')
                waiting.append(stream.bytes_waiting)
                Pyjo.IOLoop.timer(0.5, second)

            if not server:
                Pyjo.IOLoop.timer(0.5, first)
            server = (server or b'') + chunk

        stream.timeout = 0
        stream.on('read', read)

    id = Pyjo.IOLoop.server(server_cb, address='127.0.0.1')
    port = Pyjo.IOLoop.acceptor(id).port

    def client_cb(loop, err, stream):
        def drain(stream):
            stream.write(b'1', drain)

        def read(stream, chunk):
            global client
            client = (client or b'') + chunk

        drain(stream)
        stream.on('read', read)

    Pyjo.IOLoop.client(client_cb, port=port)
    Pyjo.IOLoop.start()
    is_ok(server_before, server_after, 'stream has been paused')
    ok(len(server) > len(server_after), 'stream has been resumed')
    is_ok(client, client_after, 'stream was writable while paused')
    is_ok(client, b'works!', 'full message has been written')
    is_deeply_ok(waiting, [6, 0], 'right buffer sizes')

with subtest('Watermarks'):
    fake = socket.create_server(('127.0.0.1', 0), backlog=5)
    stream = Pyjo.IOLoop.Stream.new(fake)
    stream.start()
    stream.high_water_mark = 10
    stream.write(b'abcd')
    is_ok(stream.bytes_waiting, 4, 'four bytes waiting')
    ok(stream.can_write, 'stream is still writable')
    stream.write(b'efghijk')
    is_ok(stream.bytes_waiting, 11, 'eleven bytes waiting')
    ok(not stream.can_write, 'stream is not writable anymore')
    stream.high_water_mark = 12
    ok(stream.can_write, 'stream is writable again')
    stream.close()
    ok(not stream.can_write, 'closed stream is not writable anymore')
    del stream

with subtest('Graceful shutdown'):
    err = None
    finish = 0

    def finish_cb(loop):
        global finish
        finish += 1
        loop.stream(id).close()

    def failed_cb(loop):
        global err
        loop.stop()
        err = 'failed'

    loop = Pyjo.IOLoop.new()
    port = loop.acceptor(loop.server(lambda loop, stream, id: None, address='127.0.0.1')).port
    id = loop.client(lambda loop, err, stream: loop.stop_gracefully(), port=port)
    loop.on('finish', finish_cb)
    loop.timer(30, failed_cb)
    loop.start()
    ok(not loop.stream(id), 'stopped gracefully')
    ok(not err, 'no error')
    is_ok(finish, 1, 'finish event has been emitted once')

with subtest('Graceful shutdown (without connection)'):
    err = None
    finish = 0

    def finish_cb(loop):
        global finish
        finish += 1

    loop = Pyjo.IOLoop.new()
    loop.on('finish', finish_cb)
    loop.next_tick(lambda loop: loop.stop_gracefully())
    loop.timer(30, failed_cb)
    # Not in Mojolicious: is_stopping
    ok(not loop.is_stopping, 'not stopping')
    loop.start()
    ok(not err, 'no error')
    is_ok(finish, 1, 'finish event has been emitted once')
    # Not in Mojolicious: is_stopping until reset
    ok(loop.is_stopping, 'stopping')
    loop.reset()
    ok(not loop.is_stopping, 'not stopping after reset')

# Not in Mojolicious: the delay of a graceful shutdown, while the event loop accepts as before and is stopping already
with subtest('Graceful shutdown (delay)'):
    events = []
    loop = Pyjo.IOLoop.new()
    id = loop.server(lambda loop, stream, id: events.append('accepted'), address='127.0.0.1')
    port = loop.acceptor(id).port

    def delay_cb(loop):
        events.append(('stopping', loop.is_stopping, loop.acceptor(id).is_accepting))
        loop.client(lambda loop, err, stream: stream.close(), port=port)

    loop.on('finish', lambda loop: events.append(('finish', loop.acceptor(id).is_accepting)))
    loop.next_tick(lambda loop: loop.stop_gracefully(0.3))
    loop.next_tick(lambda loop: loop.stop_gracefully(10))
    loop.timer(0.1, delay_cb)
    loop.timer(30, failed_cb)
    loop.start()
    is_deeply_ok(
        events,
        [('stopping', True, True), 'accepted', ('finish', False)],
        'accepting and stopping during the delay, a second delay is ignored',
    )
    loop.reset()

    events = []
    loop = Pyjo.IOLoop.new()
    loop.on('finish', lambda loop: events.append('finish'))
    loop.next_tick(lambda loop: loop.stop_gracefully(10))
    loop.timer(0.1, lambda loop: loop.stop_gracefully())
    loop.timer(30, failed_cb)
    loop.start()
    is_deeply_ok(events, ['finish'], 'a stop without a delay ends the delay')
    ok(loop.is_stopping, 'stopping')
    loop.reset()
    ok(not loop.is_stopping, 'not stopping after reset')

with subtest('Graceful shutdown (max_accepts)'):
    err = None
    loop = Pyjo.IOLoop.new(max_accepts=1)
    id = loop.server(lambda loop, stream, id: None, address='127.0.0.1')
    port = loop.acceptor(id).port
    loop.client(lambda loop, err, stream: stream.close(), port=port)
    loop.timer(30, failed_cb)
    loop.start()
    ok(not err, 'no error')
    is_ok(loop.max_accepts, 1, 'right value')

with subtest('Connection limit'):
    err = id = None
    loop = Pyjo.IOLoop.new(max_connections=2)
    accepting = []

    def accepting_cb(loop, stream, cid):
        def tick(loop):
            accepting.append(loop.acceptor(id).is_accepting)
            if len(accepting) == 2:
                loop.stop()

        loop.next_tick(tick)

    id = loop.server(accepting_cb, address='127.0.0.1', single_accept=True)
    port = loop.acceptor(id).port
    for _ in range(2):
        loop.client(lambda loop, err, stream: None, port=port)
    loop.timer(30, failed_cb)
    loop.start()
    ok(not err, 'no error')
    ok(accepting[0], 'accepting connections')
    ok(not accepting[1], 'connection limit reached')

with subtest('Exception in timer'):
    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        loop = Pyjo.IOLoop.new()

        def bye(loop):
            raise Exception('Bye!')

        loop.timer(0, bye)
        loop.start()
    name = f'{type(loop.reactor).__module__}.{type(loop.reactor).__qualname__}'
    like_ok(stderr.getvalue(), rf'^{re.escape(name)}:.*Bye!', 'right error')

    # Not in Mojolicious: the arguments of a callback, which Perl does not check
    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        loop = Pyjo.IOLoop.new()
        loop.timer(0, lambda: None)
        loop.start()
    like_ok(
        stderr.getvalue(),
        r'takes 0 positional arguments but 1 was given: the callback of a timer gets the event loop',
        'hint',
    )

with subtest('Defaults'):
    is_ok(Pyjo.IOLoop.Client.new().reactor, Pyjo.IOLoop.singleton.reactor, 'right default')
    is_ok(Pyjo.IOLoop.Server.new().reactor, Pyjo.IOLoop.singleton.reactor, 'right default')
    is_ok(Pyjo.IOLoop.Stream.new(None).reactor, Pyjo.IOLoop.singleton.reactor, 'right default')


# Not in Mojolicious: the promises of the chunks of a stream, as promise-readable and promise-writable of Node.js
def stream_pair():
    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)
    streams = Pyjo.IOLoop.Stream.new(a), Pyjo.IOLoop.Stream.new(b)
    for stream in streams:
        stream.start()
    return streams


with subtest('Promises of the chunks of a stream'):
    reader, writer = stream_pair()
    got = []

    @Pyjo.Promise.coroutine
    async def read():
        first = reader.read_p(5)
        await writer.write_p(b'hello world')
        got.append(await first)
        got.append(await reader.read_p())

        # Nothing reads, so the stream stops, and what comes waits for the next promise
        read = reader.bytes_read
        await writer.write_p(b'more')
        await Pyjo.Promise.timer(0.1)
        got.append(reader.bytes_read - read)
        got.append(await reader.read_p())

        writer.write(b'last').close_gracefully()
        got.append(await reader.read_all_p())
        got.append(await reader.read_p())

    read().wait()
    is_deeply_ok(got, [b'hello', b' world', 0, b'more', b'last', None], 'chunks, then the end')
    isa_ok(got[4], Pyjo.String.Bytes.object, 'everything as bytes')

with subtest('Chunks of a stream as an asynchronous iterator'):
    reader, writer = stream_pair()
    got = []

    @Pyjo.Promise.coroutine
    async def iterate(chunks):
        async for chunk in chunks:
            got.append(chunk)

    promise = iterate(reader.iterate(3))
    writer.write(b'abcdefg').close_gracefully()
    promise.wait()
    is_deeply_ok(got, [b'abc', b'def', b'g'], 'at most 3 bytes each')

    reader, writer = stream_pair()
    got = []
    promise = iterate(reader)
    writer.write(b'abcdefg').close_gracefully()
    promise.wait()
    is_ok(b''.join(got), b'abcdefg', 'the stream itself')

with subtest('Errors of the promises of a stream'):
    reader, writer = stream_pair()
    errors = []
    promise = reader.read_p().catch(lambda err: errors.append(err))
    reader.emit('error', OSError('broken'))
    promise.wait()
    is_ok(str(errors[0]), 'broken', 'read rejected with the error')
    reader.read_p().catch(lambda err: errors.append(err)).wait()
    is_ok(len(errors), 2, 'the next read too')

    writer.high_water_mark = 1
    promise = writer.write_p(b'x' * 10000000).catch(lambda err: errors.append(str(err)))
    writer.close()
    promise.wait()
    like_ok(errors[-1], r'^Stream closed before all data has been written', 'write rejected')
    reader.close()

with subtest('Promises of streams that only a coroutine refers to'):
    import gc

    got = []

    # The reactor refers to the streams weakly, so only the coroutine and the promises that it waits for keep them
    @Pyjo.Promise.coroutine
    async def read():
        reader, writer = stream_pair()
        first = reader.read_p()
        Pyjo.IOLoop.timer(0.1, lambda loop: writer.write(b'late'))
        got.append(await first)
        reader.close()
        writer.close()

    promise = read()
    gc.collect()
    Pyjo.IOLoop.timer(0.05, lambda loop: gc.collect())
    promise.wait()
    is_deeply_ok(got, [b'late'], 'not freed while the coroutine waits')

with subtest('Stream of a connection as a promise'):
    # A server that greets at once, before the coroutine that connects goes on
    id = Pyjo.IOLoop.server(lambda loop, stream, id: stream.write(b'220 hello'), address='127.0.0.1')
    port = Pyjo.IOLoop.acceptor(id).port
    got = []

    @Pyjo.Promise.coroutine
    async def greeted():
        stream = await Pyjo.IOLoop.client_p(address='127.0.0.1', port=port)
        await Pyjo.Promise.timer(0.1)
        got.append(await stream.read_p())
        stream.close()

    greeted().wait()
    is_deeply_ok(got, [b'220 hello'], 'the greeting kept for the promise')
    Pyjo.IOLoop.remove(id)

    # The port of the server, which listens no more
    errors = []
    Pyjo.IOLoop.client_p(address='127.0.0.1', port=port).catch(lambda err: errors.append(err)).wait()
    ok(errors, 'connection refused')

with subtest('Promises of a stream that is closed already'):
    reader, writer = stream_pair()
    reader.close()
    writer.close()
    got = []
    reader.read_p().then(got.append).wait()
    reader.once_p('close').then(lambda *args: got.append('close')).wait()
    reader.close_gracefully_p().then(lambda *args: got.append('closed')).wait()
    writer.write_p(b'x').catch(lambda err: got.append(str(err))).wait()
    is_deeply_ok(got[:3], [None, 'close', 'closed'], 'the end at once')
    like_ok(got[3], r'^Stream closed before all data has been written', 'write rejected at once')
    chunks = []

    @Pyjo.Promise.coroutine
    async def iterate():
        async for chunk in reader:
            chunks.append(chunk)

    iterate().wait()
    is_deeply_ok(chunks, [], 'no chunks')

with subtest('Graceful close of the promises of a stream'):
    reader, writer = stream_pair()
    got = []
    data = reader.read_all_p()
    writer.write(b'x' * 1000000)
    writer.close_gracefully_p().then(lambda *args: got.append('closed')).wait()
    data.then(lambda chunk: got.append(len(chunk))).wait()
    is_deeply_ok(got, ['closed', 1000000], 'closed once written')
    reader, writer = stream_pair()
    writer.close_gracefully_p().then(lambda *args: got.append('at once')).wait()
    is_ok(got[-1], 'at once', 'closed with nothing to write')
    reader.close()

with subtest('Timeout of the promises of a stream'):
    reader, writer = stream_pair()
    reader.timeout = 0.2
    errors = []
    reader.read_p().catch(lambda err: errors.append(err)).wait()
    reader.read_p().catch(lambda err: errors.append(err)).wait()
    ok(all(isinstance(err, TimeoutError) for err in errors), 'read rejected by the timeout')
    is_deeply_ok([str(err) for err in errors], ['Inactivity timeout', 'Inactivity timeout'], 'the next one too')
    writer.close()

    # The event of the timeout, as the buffers of the loopback of Windows take as much as a test writes
    reader, writer = stream_pair()
    reader.stop()
    failed = []
    promise = writer.write_p(b'x' * 10000000).catch(lambda err: failed.append(err))
    writer.emit('timeout')
    promise.wait()
    isa_ok(failed[0], TimeoutError, 'write rejected by the timeout')
    writer.close()
    reader.close()

if os.name != 'nt':
    with subtest('Promises of the pipes of a child process'):
        child = Pyjo.IOLoop.ChildProcess.new().spawn(
            [sys.executable, '-c', 'import sys; sys.stdout.write(sys.stdin.read().upper())']
        )
        # The promises before the events, as the reactor of asyncio runs a coroutine later
        output = child.stdout.read_all_p()
        closed = child.once_p('close')
        got = []

        @Pyjo.Promise.coroutine
        async def run():
            await child.stdin.write_p(b'hello')
            child.stdin.close_gracefully()
            got.append(await output)
            got.append(await closed)

        run().wait()
        is_deeply_ok(got, [b'HELLO', (0, None)], 'output and the end of the process')

done_testing()
