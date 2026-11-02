from Pyjo.Test import *

import importlib
import io
import os
import socket
import sys
import tempfile

from contextlib import redirect_stdout


# The documentation describes the default reactor, before Pyjo.IOLoop is loaded
os.environ.pop('PYJO_REACTOR', None)


# A port below the ephemeral ones, which no other socket takes before the datagram socket binds it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
ServerStart = importlib.import_module('ServerStart')
free_port = ServerStart.port


port = free_port()

with subtest('Synopsis'):
    from Pyjo.IOLoop.Datagram import Datagram

    # Echo server
    server = Datagram()
    server.on('message', lambda server, data, peer: server.send(b'Echo: ' + data, peer))
    server.bind(address='127.0.0.1', port=port)

    got = []
    client = Datagram()
    client.on('message', lambda client, data, peer: got.append(data) or client.reactor.stop())
    client.send(b'Hello!', ('127.0.0.1', port))
    if not client.reactor.is_running:
        client.reactor.start()
    is_deeply_ok(got, [b'Echo: Hello!'], 'echo')
    client.close()
    server.close()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.IOLoop.Datagram

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        # Echo server
        server = Pyjo.IOLoop.Datagram.new()
        server.on('message', lambda server, data, peer: server.send(b'Echo: ' + data, peer))
        server.bind(address='127.0.0.1', port=port)

        # Client
        client = Pyjo.IOLoop.Datagram.new()
        client.on('message', lambda client, data, peer: print(data))
        client.on('error', lambda client, err: print(err))
        client.on('message', lambda client, data, peer: client.reactor.stop())
        client.send(b'Hello!', ('127.0.0.1', port))

        # Start reactor if necessary
        if not client.reactor.is_running:
            client.reactor.start()
    is_ok(stdout.getvalue(), "b'Echo: Hello!'\n", 'print(data)')

with subtest('Events'):
    events = []
    client.on('close', lambda datagram: events.append('close'))
    other = Pyjo.IOLoop.Datagram.new()
    other.on('connect', lambda datagram: events.append('connect') or datagram.reactor.stop())
    other.on('error', lambda datagram, err: ...)
    other.on('message', lambda datagram, data, peer: ...)
    other.connect(address='127.0.0.1', port=port)
    other.reactor.start()
    client.close()
    is_deeply_ok(events, ['connect', 'close'], 'connect and close')
    other.close()

with subtest('new'):
    datagram = Pyjo.IOLoop.Datagram.new()
    is_ok(datagram.handle, None, 'not bound')
    handle = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    handle.bind(('127.0.0.1', 0))
    datagram = Pyjo.IOLoop.Datagram.new(handle)
    is_ok(datagram.handle, handle, 'handle')
    datagram.close()

with subtest('reactor'):
    import Pyjo.Reactor.Poll

    datagram = Pyjo.IOLoop.Datagram.new()
    reactor = datagram.reactor
    is_ok(reactor, Pyjo.IOLoop.singleton.reactor, 'default')
    poll = Pyjo.Reactor.Poll.new()
    datagram.reactor = Pyjo.Reactor.Poll.new()
    datagram.reactor = poll
    is_ok(datagram.reactor, poll, 'set')

with subtest('add_membership and drop_membership'):
    datagram = Pyjo.IOLoop.Datagram.new().bind(port=free_port())
    try:
        datagram = datagram.add_membership('224.0.0.114')
    except OSError as e:
        skip(f'No multicast: {e}', 1)
    else:
        datagram = datagram.drop_membership('224.0.0.114')
        pass_ok('joined and left')
    datagram.close()

with subtest('bind'):
    datagram = Pyjo.IOLoop.Datagram.new()
    datagram = datagram.bind(port=free_port())
    ok(datagram.port, 'bound')
    datagram.close()
    datagram = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1', ipv6_only=True, reuse=True)
    ok(datagram.port, 'options')
    datagram.close()
    if not hasattr(socket, 'AF_UNIX'):
        skip('no UNIX domain sockets', 1)
    else:
        with tempfile.TemporaryDirectory() as dir:
            datagram = Pyjo.IOLoop.Datagram.new().bind(path=os.path.join(dir, 'myapp.sock'))
            is_ok(datagram.port, None, 'path')
            datagram.close()

with subtest('broadcast'):
    datagram = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1')
    boolean = datagram.broadcast
    ok(not boolean, 'default')
    datagram.broadcast = True
    ok(datagram.broadcast, 'set')

with subtest('bytes_waiting'):
    num = datagram.bytes_waiting
    is_ok(num, 0, 'nothing')

with subtest('close and close_gracefully'):
    datagram.close()
    is_ok(datagram.handle, None, 'closed')
    datagram = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1')
    datagram.close_gracefully()
    is_ok(datagram.handle, None, 'closed gracefully')

with subtest('connect'):
    server = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1', port=free_port())
    datagram = Pyjo.IOLoop.Datagram.new()
    datagram.on('connect', lambda datagram: datagram.reactor.stop())
    datagram = datagram.connect(address='127.0.0.1', port=server.port)
    datagram.reactor.start()
    is_ok(datagram.handle.getpeername(), ('127.0.0.1', server.port), 'connected')
    datagram.close()

with subtest('handle'):
    handle = server.handle
    isa_ok(handle, socket.socket, 'socket')

with subtest('multicast_loopback'):
    boolean = server.multicast_loopback
    ok(boolean, 'default')
    server.multicast_loopback = False
    ok(not server.multicast_loopback, 'set')

with subtest('multicast_ttl'):
    ttl = server.multicast_ttl
    is_ok(ttl, 1, 'default')
    server.multicast_ttl = 64
    is_ok(server.multicast_ttl, 64, 'set')

with subtest('port'):
    port = server.port
    ok(port, 'port')

with subtest('send'):
    got = []

    @server.on
    def message(server, data, peer):
        got.append(data)
        if len(got) == 3:
            server.reactor.stop()

    connected = Pyjo.IOLoop.Datagram.new()
    connected.connect(address='127.0.0.1', port=port)
    datagram = connected.send(b'Hello!')

    # Bound to IPv4 first, so that localhost is resolved to an IPv4 address
    datagram = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1')
    datagram = datagram.send(b'Hello!', ('127.0.0.1', port))
    datagram = datagram.send(b'Hello!', ('localhost', port), lambda datagram: ...)
    datagram.reactor.start()
    is_deeply_ok(got, [b'Hello!', b'Hello!', b'Hello!'], 'sent')
    connected.close()
    datagram.close()
    if not hasattr(socket, 'AF_UNIX'):
        skip('no UNIX domain sockets', 1)
    else:
        with tempfile.TemporaryDirectory() as dir:
            path = os.path.join(dir, 'myapp.sock')
            unix = Pyjo.IOLoop.Datagram.new().bind(path=path)
            unix.on('message', lambda unix, data, peer: [got.append(data), unix.reactor.stop()])
            datagram = Pyjo.IOLoop.Datagram.new()
            datagram = datagram.send(b'Hello!', path)
            datagram.reactor.start()
            is_ok(len(got), 4, 'UNIX domain socket')
            datagram.close()
            unix.close()

with subtest('start and stop'):
    server.start()
    server.stop()
    server.start()
    pass_ok('started and stopped')

with subtest('ttl'):
    ttl = server.ttl
    ok(ttl, 'default')
    server.ttl = 64
    is_ok(server.ttl, 64, 'set')
    server.close()

with subtest('__aiter__, iterate, recv_p and send_p'):
    import Pyjo.IOLoop.Datagram
    import Pyjo.Promise

    server = Pyjo.IOLoop.Datagram.new()
    server.bind(address='127.0.0.1', port=free_port())

    # Echo server, one datagram after another
    @Pyjo.Promise.coroutine
    async def echo(datagrams):
        async for data, peer in datagrams:
            await server.send_p(b'Echo: ' + data, peer)

    echoed = echo(aiter(server))
    printed = []

    @Pyjo.Promise.coroutine
    async def client():
        datagram = await Pyjo.IOLoop.Datagram.new().connect_p(address='127.0.0.1', port=server.port)
        promise = datagram.send_p(b'Hello!')
        await promise
        if (received := await datagram.recv_p()) is not None:
            data, peer = received
            printed.append(f'{data!r} from {peer[0]}')
        promise = datagram.recv_p(timeout=0.1)
        try:
            await promise
        except TimeoutError:
            printed.append('timeout')
        other = Pyjo.IOLoop.Datagram.new()
        received = other.recv_p()
        await other.send_p(b'Hello!', ('127.0.0.1', server.port))
        printed.append((await received)[0])
        await datagram.send_p(b'Bye!')
        # The echo before the close, as Windows reports a datagram that comes to a closed port as an error of the
        # server, which would end its iteration
        await datagram.recv_p()
        await datagram.close_gracefully_p()
        promise = datagram.close_gracefully_p()
        await promise
        promise = datagram.once_p('close')
        await promise
        other.close()

    client().wait()
    is_deeply_ok(printed, ["b'Echo: Hello!' from 127.0.0.1", 'timeout', b'Echo: Hello!'], 'datagrams')
    server.close()
    echoed.wait()

    got = []
    server = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1')

    @Pyjo.Promise.coroutine
    async def collect(datagrams):
        async for data, _peer in datagrams:
            got.append(data)

    promise = collect(server.iterate())
    sender = Pyjo.IOLoop.Datagram.new()
    sender.send_p(b'one', ('127.0.0.1', server.port)).wait()
    Pyjo.Promise.timer(0.1).wait()
    server.close()
    sender.close()
    promise.wait()
    is_deeply_ok(got, [b'one'], 'until the close')

    got = []
    server = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1')
    trusted = None

    @Pyjo.Promise.coroutine
    async def one_peer():
        # The datagrams of one peer, in a chain
        async for data, peer in server.iterate().grep(lambda message: message[1] == trusted):
            got.append((data, peer))

    promise = one_peer()
    sender, other = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1'), Pyjo.IOLoop.Datagram.new()
    trusted = ('127.0.0.1', sender.port)
    other.send_p(b'other', ('127.0.0.1', server.port)).wait()
    sender.send_p(b'trusted', ('127.0.0.1', server.port)).wait()
    Pyjo.Promise.timer(0.1).wait()
    server.close()
    sender.close()
    other.close()
    promise.wait()
    is_deeply_ok(got, [(b'trusted', trusted)], 'one peer')

done_testing()
