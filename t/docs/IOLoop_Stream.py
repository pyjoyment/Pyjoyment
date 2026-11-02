import Pyjo.IOLoop.Stream

from Pyjo.Test import *

import os
import socket


# The documentation describes the default reactor, before Pyjo.IOLoop is loaded
os.environ.pop('PYJO_REACTOR', None)

handle, peer = socket.socketpair()

with subtest('Synopsis'):
    from Pyjo.IOLoop.Stream import Stream

    got = []

    # Create stream
    stream = Stream(handle)
    stream.on('read', lambda stream, chunk: ...)
    stream.on('close', lambda stream: ...)
    stream.on('error', lambda stream, err: ...)
    stream.on('read', lambda stream, chunk: got.append(chunk) or stream.reactor.stop())

    stream.start()
    peer.sendall(b'data')
    if not stream.reactor.is_running:
        stream.reactor.start()
    is_deeply_ok(got, [b'data'], 'read')
    stream.steal_handle()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.IOLoop.Stream

    got = []

    # Create stream
    stream = Pyjo.IOLoop.Stream.new(handle)
    stream.on('read', lambda stream, chunk: ...)
    stream.on('close', lambda stream: ...)
    stream.on('error', lambda stream, err: ...)
    stream.on('read', lambda stream, chunk: got.append(chunk) or stream.reactor.stop())

    # Start and stop watching for new data
    stream.start()
    stream.stop()
    stream.start()
    peer.sendall(b'data')

    # Start reactor if necessary
    if not stream.reactor.is_running:
        stream.reactor.start()
    is_deeply_ok(got, [b'data'], 'read')

with subtest('Events'):
    events = []
    stream.on('drain', lambda stream: events.append('drain'))
    stream.on('write', lambda stream, chunk: events.append(chunk))
    stream.on('timeout', lambda stream: ...)
    stream.write(b'out', lambda stream: stream.reactor.stop())
    stream.reactor.start()
    is_deeply_ok(events, [b'out', 'drain'], 'write and drain')
    is_ok(peer.recv(3), b'out', 'written')
    stream.unsubscribe('drain')

with subtest('high_water_mark'):
    size = stream.high_water_mark
    is_ok(size, 1048576, 'default')
    stream.high_water_mark = 1024
    is_ok(stream.high_water_mark, 1024, 'set')

with subtest('reactor'):
    import Pyjo.Reactor.Poll

    reactor = stream.reactor
    is_ok(reactor, Pyjo.IOLoop.singleton.reactor, 'default')
    poll = Pyjo.Reactor.Poll.new()
    other = Pyjo.IOLoop.Stream.new()
    other.reactor = poll
    is_ok(other.reactor, poll, 'set')

with subtest('bytes_read, bytes_waiting and bytes_written'):
    num = stream.bytes_read
    is_ok(num, 4, 'read')
    num = stream.bytes_waiting
    is_ok(num, 0, 'waiting')
    num = stream.bytes_written
    is_ok(num, 3, 'written')

with subtest('can_write, is_readable and is_writing'):
    boolean = stream.can_write
    ok(boolean, 'can write')
    boolean = stream.is_readable
    ok(not boolean, 'not readable')
    boolean = stream.is_writing
    ok(not boolean, 'not writing')

with subtest('handle, steal_handle and timeout'):
    handle = stream.handle
    isa_ok(handle, socket.socket, 'handle')
    timeout = stream.timeout
    is_ok(timeout, 15, 'default')
    stream.timeout = 45
    is_ok(stream.timeout, 45, 'set')
    handle = stream.steal_handle()
    is_ok(stream.handle, None, 'stolen')
    stream = Pyjo.IOLoop.Stream.new(handle)

with subtest('write'):
    stream.start()
    stream = stream.write(b'chunk')
    stream = stream.write(b'chunk', lambda stream: stream.reactor.stop())
    stream.reactor.start()
    is_ok(stream.bytes_written, 10, 'written')

with subtest('close and close_gracefully'):
    closed = []
    stream.on('close', lambda stream: closed.append(True))
    stream.close_gracefully()
    is_deeply_ok(closed, [True], 'closed')
    stream.close()
    is_deeply_ok(closed, [True], 'closed once')

peer.close()


# The promises of streams of their own, as the one above is closed
def pair():
    a, b = socket.socketpair()
    streams = Pyjo.IOLoop.Stream.new(a), Pyjo.IOLoop.Stream.new(b)
    for stream in streams:
        stream.start()
    return streams


with subtest('__aiter__ and iterate'):
    import Pyjo.Promise

    stream, peer = pair()
    got = []

    @Pyjo.Promise.coroutine
    async def collect(chunks):
        async for chunk in chunks:
            got.append(chunk)

    promise = collect(aiter(stream))
    peer.write(b'abc').close_gracefully()
    promise.wait()
    is_deeply_ok(got, [b'abc'], 'async for chunk in stream')

    stream, peer = pair()
    got = []
    promise = collect(stream.iterate(1024))
    peer.write(b'abc').close_gracefully()
    promise.wait()
    is_deeply_ok(got, [b'abc'], 'async for chunk in stream.iterate(1024)')

    # Echo in capitals
    stream, peer = pair()
    echoed = []

    @Pyjo.Promise.coroutine
    async def echo(chunks):
        async for chunk in chunks:
            await stream.write_p(chunk.upper())

    peer.on('read', lambda peer, chunk: (echoed.append(chunk), peer.close()))
    promise = echo(aiter(stream))
    peer.write(b'abc')
    promise.wait()
    is_deeply_ok(echoed, [b'ABC'], 'echo')

    # The same in a chain
    stream, peer = pair()
    echoed = []

    @Pyjo.Promise.coroutine
    async def chain():
        async for chunk in stream.iterate().map(bytes.upper):
            await stream.write_p(chunk)

    peer.on('read', lambda peer, chunk: (echoed.append(chunk), peer.close()))
    promise = chain()
    peer.write(b'abc')
    promise.wait()
    is_deeply_ok(echoed, [b'ABC'], 'echo in a chain')

with subtest('close_gracefully_p and once_p'):
    stream, peer = pair()
    data = peer.read_all_p()
    promise = stream.close_gracefully_p()
    promise.wait()
    is_ok(stream.handle, None, 'closed')
    stream.once_p('close').wait()

    stream, peer = pair()
    data = peer.read_all_p()

    @Pyjo.Promise.coroutine
    async def bye():
        await stream.write_p(b'Bye!')
        await stream.close_gracefully_p()

    bye().wait()
    got = []
    data.then(got.append).wait()
    is_deeply_ok(got, [b'Bye!'], 'written, then closed')

with subtest('read_all_p'):
    stream, peer = pair()
    promise = stream.read_all_p()
    peer.write(b'abc').close_gracefully()

    @Pyjo.Promise.coroutine
    async def read_all():
        data = await promise
        return data

    data = []
    read_all().then(data.append).wait()
    is_deeply_ok(data, [b'abc'], 'data')

with subtest('read_p'):
    stream, peer = pair()
    promise = stream.read_p()
    peer.write(b'abcdef')
    got = []
    promise.then(got.append).wait()
    promise = stream.read_p(3)
    peer.write(b'ghijkl').close_gracefully()
    promise.then(got.append).wait()
    is_deeply_ok(got, [b'abcdef', b'ghi'], 'chunks')

    # Read until the end
    chunks = []

    @Pyjo.Promise.coroutine
    async def read():
        while (chunk := await stream.read_p()) is not None:
            chunks.append(chunk)

    read().wait()
    is_ok(b''.join(chunks), b'jkl', 'until the end')

with subtest('write_p'):
    stream, peer = pair()
    promise = stream.write_p(b'chunk')
    got = []
    promise.then(lambda *args: got.append(stream.bytes_written)).wait()
    is_deeply_ok(got, [5], 'written')

    @Pyjo.Promise.coroutine
    async def write():
        await stream.write_p(b'Hello World!')

    write().wait()
    is_ok(stream.bytes_written, 17, 'await')
    stream.close()
    peer.close()

done_testing()
