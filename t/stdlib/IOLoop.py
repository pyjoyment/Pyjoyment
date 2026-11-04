import Pyjo.IOLoop
import Pyjo.IOLoop.Stream

from Pyjo.Test import *

import asyncio
import os
import socket
import threading


with subtest('A server for a client of the standard library'):
    loop = Pyjo.IOLoop.new()

    @loop.server(address='127.0.0.1')
    def id(loop, stream, id):
        stream.on('read', lambda stream, chunk: stream.write(chunk.upper()))

    port = loop.acceptor(id).port
    got = []

    def client():
        with socket.create_connection(('127.0.0.1', port)) as s:
            s.sendall(b'hello')
            got.append(s.recv(5))

    thread = threading.Thread(target=client)
    thread.start()
    loop.recurring(0.01, lambda loop: loop.stop() if not thread.is_alive() else None)
    loop.start()
    thread.join()
    is_deeply_ok(got, [b'HELLO'], 'echoed')

with subtest('A stream of a socket of the standard library'):
    loop = Pyjo.IOLoop.new()
    a, b = socket.socketpair()
    stream = Pyjo.IOLoop.Stream.new(a)
    id = loop.stream(stream)
    chunks = []

    def read(stream, chunk):
        chunks.append(chunk)
        loop.stop()

    stream.on('read', read)
    b.sendall(b'from the other end')
    loop.start()
    is_deeply_ok(chunks, [b'from the other end'], 'read')
    loop.remove(id)
    b.close()

with subtest('Inside asyncio.run'):
    got = []

    async def main():
        loop = Pyjo.IOLoop.new()
        got.append(loop.reactor.loop is asyncio.get_running_loop())
        loop.timer(0, lambda loop: got.append('timer'))
        await asyncio.sleep(0.01)
        got.append(loop.is_running)

    os.environ.pop('PYJO_REACTOR', None)
    asyncio.run(main())
    is_deeply_ok(got, [True, 'timer', True], 'the reactor watches in the running loop')

with subtest('A callback as a keyword argument'):
    loop = Pyjo.IOLoop.new()
    got = []

    def accept(loop, stream, id):
        got.append('accepted')
        stream.on('close', lambda stream: loop.stop())

    def connect(loop, err, stream):
        got.append('connected')
        stream.close()

    id = loop.server(cb=accept, address='127.0.0.1')
    isa_ok(id, str, 'server')
    port = loop.acceptor(id).port
    isa_ok(loop.client(cb=connect, address='127.0.0.1', port=port), str, 'client')
    timer = loop.timer(cb=lambda loop: got.append('timer'), after=0)
    isa_ok(timer, str, 'timer')
    loop.start()
    is_deeply_ok(sorted(got), ['accepted', 'connected', 'timer'], 'all called')
    loop.reset()

with subtest('Decorators with and without parentheses'):
    loop = Pyjo.IOLoop.new()
    got = []

    @loop.server
    def server(loop, stream, id):
        got.append('accepted')
        stream.on('close', lambda stream: loop.stop())

    isa_ok(server, str, 'the name of the server is its id')
    port = loop.acceptor(server).port

    @loop.client(address='127.0.0.1', port=port)
    def client(loop, err, stream):
        got.append('connected')
        stream.close()

    isa_ok(client, str, 'the name of the client is its id')

    @loop.timer(0)
    def timer(loop):
        got.append('timer')

    isa_ok(timer, str, 'the name of the timer is its id')
    loop.start()
    is_deeply_ok(sorted(got), ['accepted', 'connected', 'timer'], 'all called')
    loop.reset()

with subtest('Context manager'):
    with Pyjo.IOLoop.new() as loop:
        id = loop.timer(10, lambda loop: None)
        ok(loop.reactor.remove(id) or True, 'timer')
        id = loop.timer(10, lambda loop: None)
    ok(not loop.reactor.remove(id), 'everything removed at the end of the block')

done_testing()
