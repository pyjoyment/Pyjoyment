from Pyjo.Test import *

import contextlib
import importlib
import io
import os
import socket
import subprocess
import sys


# The documentation describes the default reactor
os.environ.pop('PYJO_REACTOR', None)


# A port below the ephemeral ones, which no other socket takes before the server binds it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
ServerStart = importlib.import_module('ServerStart')


with subtest('Synopsis'):
    port = ServerStart.port()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        import Pyjo.IOLoop

        # Listen on port 3000
        @Pyjo.IOLoop.server(port=port)
        def server(loop, stream, id):
            @stream.on
            def read(stream, chunk):
                # Process input chunk
                print(chunk)

                # Write response
                stream.write(b'HTTP/1.1 200 OK')

        # Connect to port 3000
        @Pyjo.IOLoop.client(port=port)
        def id(loop, err, stream):
            @stream.on
            def read(stream, chunk):
                # Process input
                print(f'Input: {chunk}')
                loop.stop()

            # Write request
            stream.write(b'GET / HTTP/1.1\x0d\x0a\x0d\x0a')

        # Add a timer
        Pyjo.IOLoop.timer(5, lambda loop: loop.remove(id))

        # Start event loop if necessary
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(output.getvalue(), "b'GET / HTTP/1.1\\r\\n\\r\\n'\nInput: b'HTTP/1.1 200 OK'\n", 'request and response')
    Pyjo.IOLoop.reset()

with subtest('Decorators'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):

        @Pyjo.IOLoop.timer(0.01)
        def id(loop):
            print('Timeout!')

        Pyjo.IOLoop.start()
    is_ok(output.getvalue(), 'Timeout!\n', 'timer')
    isa_ok(id, str, 'decorated name is the id')

with subtest('Events'):
    loop = Pyjo.IOLoop.new()
    loop.on('finish', lambda loop: ...)
    loop.on('reset', lambda loop: ...)
    ok(loop.has_subscribers('finish'), 'finish')
    ok(loop.has_subscribers('reset'), 'reset')

with subtest('Debugging'):
    env = dict(os.environ, PYJO_IOLOOP_DEBUG='1')
    env.pop('PYJO_REACTOR', None)
    result = subprocess.run([sys.executable, '-c', 'import Pyjo.IOLoop'], env=env, capture_output=True, text=True)
    is_ok(result.stderr, '-- Reactor initialized (Pyjo.Reactor.Asyncio)\n', 'diagnostics')

with subtest('max_accepts and max_connections'):
    loop = Pyjo.IOLoop.new()
    max = loop.max_accepts
    is_ok(max, 0, 'default')
    loop.max_accepts = 1000
    is_ok(loop.max_accepts, 1000, 'set')
    max = loop.max_connections
    is_ok(max, 1000, 'default')
    loop.max_connections = 100
    is_ok(loop.max_connections, 100, 'set')

with subtest('reactor'):
    import Pyjo.Reactor.Asyncio

    loop = Pyjo.IOLoop.new()
    reactor = loop.reactor
    isa_ok(reactor, Pyjo.Reactor.Asyncio.object, 'default')
    loop.reactor = Pyjo.Reactor.Asyncio.new()
    isnt_ok(loop.reactor, reactor, 'set')

    handle, peer = socket.socketpair()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Watch if handle becomes readable or writable
        Pyjo.IOLoop.singleton.reactor.io(
            handle, lambda reactor, writable: print('Handle is writable' if writable else 'Handle is readable')
        )

        # Change to watching only if handle becomes writable
        Pyjo.IOLoop.singleton.reactor.watch(handle, False, True)
        Pyjo.IOLoop.one_tick()

        # Remove handle again
        Pyjo.IOLoop.singleton.reactor.remove(handle)
    is_ok(output.getvalue(), 'Handle is writable\n', 'watched')
    handle.close()
    peer.close()

with subtest('acceptor'):
    import Pyjo.IOLoop.Server

    loop = Pyjo.IOLoop.new()
    listening = Pyjo.IOLoop.Server.new()
    listening.listen(address='127.0.0.1')
    id = loop.acceptor(listening)
    server = loop.acceptor(id)
    isa_ok(server, Pyjo.IOLoop.Server.object, 'acceptor')
    is_ok(Pyjo.IOLoop.acceptor(id), None, 'not of the singleton')
    loop.reset()

with subtest('blocking'):
    import Pyjo.Test.Pyjo
    import Pyjoyment

    import asyncio

    # A model of Django, whose query refuses a running loop of asyncio, as the ORM of Django does
    class Note:
        class objects:
            @staticmethod
            def exists():
                with contextlib.suppress(RuntimeError):
                    asyncio.get_running_loop()
                    raise AssertionError('You cannot call this from an async context')
                return True

    app = Pyjoyment.new()
    app.log.level = 'fatal'
    plugin = app.plugin
    plugin('Health', checks={'db': lambda c: Pyjo.IOLoop.blocking(Note.objects.exists)})
    Pyjo.Test.Pyjo.new(app).get_ok('/readyz').status_is(200).content_is('ok')
    is_ok(Pyjo.IOLoop.blocking(lambda a, b: a + b, 1, b=2), 3, 'result')

with subtest('client and server'):
    loop = Pyjo.IOLoop.new()
    got = []

    id = loop.server(cb=lambda loop, stream, id: None, address='127.0.0.1')
    ok(loop.acceptor(id).port, 'listening with cb')
    loop.remove(id)

    # Listen on random port
    id = loop.server(lambda loop, stream, id: got.append('accepted'), address='127.0.0.1')
    port = loop.acceptor(id).port

    def cb(loop, err, stream):
        got.append('connected')
        loop.stop()

    id = loop.client(cb, address='127.0.0.1', port=port)
    loop.start()
    ok('connected' in got, 'connected')
    isa_ok(id, str, 'id')

    got.clear()
    id = loop.client(cb=cb, address='127.0.0.1', port=port)
    loop.start()
    ok('connected' in got, 'connected with cb')

    @loop.client(address='127.0.0.1', port=port)
    def id2(loop, err, stream):
        loop.stop()

    loop.start()
    isa_ok(id2, str, 'decorator')

with subtest('client_p'):
    import Pyjo.Promise

    # An echo server on the singleton, as the module function uses it
    id = Pyjo.IOLoop.server(
        lambda loop, stream, id: stream.on('read', lambda stream, chunk: stream.write(chunk)), address='127.0.0.1'
    )
    port = Pyjo.IOLoop.acceptor(id).port
    promise = Pyjo.IOLoop.client_p(address='127.0.0.1', port=port)
    got = []
    promise.then(lambda stream: (got.append(stream), stream.close())).wait()
    isa_ok(got[0], Pyjo.IOLoop.Stream.object, 'stream')

    loop = Pyjo.IOLoop.new()
    loop_id = loop.server(lambda loop, stream, id: None, address='127.0.0.1')
    promise = loop.client_p(address='127.0.0.1', port=loop.acceptor(loop_id).port)
    promise.then(lambda stream: (got.append('loop'), stream.close(), loop.stop()))
    loop.start()
    is_ok(got[-1], 'loop', 'promise of the loop')

    @Pyjo.Promise.coroutine
    async def hello():
        stream = await Pyjo.IOLoop.client_p(address='127.0.0.1', port=port)
        await stream.write_p(b'Hello!')
        reply = await stream.read_p()
        stream.close()
        return reply

    hello().then(got.append).wait()
    is_ok(got[-1], b'Hello!', 'reply')
    Pyjo.IOLoop.remove(id)

with subtest('datagram'):
    loop = Pyjo.IOLoop.new()
    got = []

    def cb(loop, datagram, id):
        got.append(id)

    id = loop.datagram(cb, address='127.0.0.1')
    id = loop.datagram(cb=cb)
    is_ok(len(got), 2, 'callback')
    isa_ok(id, str, 'id')

    # Echo server
    @loop.datagram(address='127.0.0.1')
    def id(loop, datagram, id):
        datagram.on('message', lambda datagram, data, peer: datagram.send(data, peer))

    isa_ok(id, str, 'decorator')
    port = loop.stream(id).port
    client = loop.stream(loop.datagram(cb=cb))
    client.on('message', lambda client, data, peer: [got.append(data), loop.stop()])
    client.send(b'echo', ('127.0.0.1', port))
    loop.start()
    is_ok(got[-1], b'echo', 'echo')
    loop.reset()

with subtest('is_running'):
    boolean = Pyjo.IOLoop.is_running()
    ok(not boolean, 'module')
    boolean = Pyjo.IOLoop.new().is_running
    ok(not boolean, 'loop')

with subtest('is_stopping'):
    boolean = Pyjo.IOLoop.is_stopping()
    ok(not boolean, 'module')
    boolean = Pyjo.IOLoop.new().is_stopping
    ok(not boolean, 'loop')

with subtest('next_tick'):
    got = []
    none = Pyjo.IOLoop.next_tick(lambda loop: got.append('module'))
    is_ok(none, None, 'always None')
    loop = Pyjo.IOLoop.new()
    none = loop.next_tick(lambda loop: got.append('loop'))
    loop.start()

    # Perform operation on next reactor tick
    Pyjo.IOLoop.next_tick(lambda loop: ...)
    Pyjo.IOLoop.start()
    is_deeply_ok(got, ['loop', 'module'], 'ticks')

with subtest('one_tick'):
    # Don't block longer than 0.5 seconds
    id = Pyjo.IOLoop.timer(0.5, lambda loop: None)
    Pyjo.IOLoop.one_tick()
    Pyjo.IOLoop.remove(id)
    pass_ok('one tick')

with subtest('recurring and timer'):
    loop = Pyjo.IOLoop.new()
    ids = [
        Pyjo.IOLoop.recurring(3, lambda loop: ...),
        loop.recurring(0, lambda loop: ...),
        loop.recurring(0.25, lambda loop: ...),
        Pyjo.IOLoop.timer(3, lambda loop: ...),
        loop.timer(0, lambda loop: ...),
        loop.timer(0.25, lambda loop: ...),
    ]

    # Perform operation every 5 seconds
    ids.append(Pyjo.IOLoop.recurring(5, lambda loop: ...))

    # Perform operation in 5 seconds
    ids.append(Pyjo.IOLoop.timer(5, lambda loop: ...))
    ok(all(isinstance(id, str) for id in ids), 'ids')
    Pyjo.IOLoop.reset()
    loop.reset()

with subtest('remove and reset'):
    loop = Pyjo.IOLoop.new()
    id = Pyjo.IOLoop.timer(10, lambda loop: None)
    Pyjo.IOLoop.remove(id)
    id = loop.timer(10, lambda loop: None)
    loop.remove(id)
    Pyjo.IOLoop.reset()
    loop.reset()
    loop.reset(freeze=True)
    pass_ok('removed and reset')

with subtest('singleton'):
    loop = Pyjo.IOLoop.object.singleton()
    is_ok(loop, Pyjo.IOLoop.singleton, 'singleton')

    # Many methods also allow you to take shortcuts
    Pyjo.IOLoop.timer(0.01, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()

    # Restart active timer
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        id = Pyjo.IOLoop.timer(0.01, lambda loop: print('Timeout!'))
        Pyjo.IOLoop.singleton.reactor.again(id)
        Pyjo.IOLoop.start()
    is_ok(output.getvalue(), 'Timeout!\n', 'restarted')

    handle, peer = socket.socketpair()
    fd = handle.fileno()
    peer.sendall(b'x')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Watch a file descriptor if it becomes readable
        Pyjo.IOLoop.singleton.reactor.io(
            fd, lambda reactor, writable: print('Handle is writable' if writable else 'Handle is readable')
        ).watch(fd, True, False)
        Pyjo.IOLoop.one_tick()
    Pyjo.IOLoop.singleton.reactor.remove(fd)
    is_ok(output.getvalue(), 'Handle is readable\n', 'watched')
    handle.close()
    peer.close()

with subtest('spawn'):
    import Pyjo.IOLoop.ChildProcess

    if os.name == 'nt':
        skip('child processes need pipes that the reactor watches', 3)
    else:
        loop = Pyjo.IOLoop.new()
        child = loop.spawn([sys.executable, '-c', 'pass'], cwd='/')
        isa_ok(child, Pyjo.IOLoop.ChildProcess.object, 'child process')
        is_ok(child.reactor, loop.reactor, 'reactor of the loop')

        # The output of a program, and its exit code
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            # One write of the whole line, as print writes the end of the line apart when the output is not buffered
            child = Pyjo.IOLoop.spawn([sys.executable, '-c', 'import sys; sys.stdout.write("total 0\\n")'])
            child.stdout.on('read', lambda stream, chunk: print(chunk))
            child.on('close', lambda child, code, signal: print(f'Exited with {code}'))
            child.on('close', lambda child, code, signal: Pyjo.IOLoop.stop())
            Pyjo.IOLoop.start()
        is_ok(stdout.getvalue(), "b'total 0\\n'\nExited with 0\n", 'output and exit code')

with subtest('start and stop'):
    Pyjo.IOLoop.timer(0.01, lambda loop: Pyjo.IOLoop.stop())

    # Start event loop only if it is not running already
    if not Pyjo.IOLoop.is_running():
        Pyjo.IOLoop.start()
    loop = Pyjo.IOLoop.new()
    loop.timer(0.01, lambda loop: loop.stop())
    loop.start()
    pass_ok('stopped')

with subtest('stop_gracefully'):
    loop = Pyjo.IOLoop.new()
    loop.next_tick(lambda loop: loop.stop_gracefully())
    loop.start()
    Pyjo.IOLoop.next_tick(lambda loop: Pyjo.IOLoop.stop_gracefully())
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.reset()
    pass_ok('stopped gracefully')

with subtest('stream'):
    import Pyjo.IOLoop.Stream

    handle, peer = socket.socketpair()
    loop = Pyjo.IOLoop.new()
    id = loop.stream(Pyjo.IOLoop.Stream.new(handle))
    stream = loop.stream(id)
    isa_ok(stream, Pyjo.IOLoop.Stream.object, 'stream')

    # Increase inactivity timeout for connection to 300 seconds
    loop.stream(id).timeout = 300
    is_ok(loop.stream(id).timeout, 300, 'timeout')
    loop.reset()
    peer.close()

with subtest('subprocess'):
    import Pyjo.IOLoop.Subprocess

    import time

    # PyPy with its JIT on macOS: the child of a fork crashes now and then with a bus error, under load
    if sys.platform == 'darwin' and getattr(sys, 'pypy_translation_info', {}).get('translation.jit'):
        skip('PyPy with its JIT on macOS: the child of a fork crashes now and then with SIGBUS', 4)
    elif not hasattr(os, 'fork'):
        skip('Pyjo.IOLoop.Subprocess needs os.fork', 4)
    else:
        subprocess = Pyjo.IOLoop.subprocess()
        isa_ok(subprocess, Pyjo.IOLoop.Subprocess.object, 'subprocess')
        subprocess = Pyjo.IOLoop.new().subprocess()
        isa_ok(subprocess, Pyjo.IOLoop.Subprocess.object, 'subprocess of a loop')
        got = []
        loop = Pyjo.IOLoop.new()
        subprocess = loop.subprocess(lambda subprocess: 1, lambda subprocess, err, *results: got.extend(results))
        loop.start()
        is_deeply_ok(got, [1], 'run')

        def blocking(subprocess):
            time.sleep(0.05)
            return '♥', 'Pyjoyment'

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            # Operation that would block the event loop for 5 seconds
            Pyjo.IOLoop.subprocess().run_p(blocking).then(
                lambda *results: print(f'I {results[0]} {results[1]}!')
            ).catch(lambda err: print(f'Subprocess error: {err}'))
            Pyjo.IOLoop.start()
        is_ok(output.getvalue(), 'I ♥ Pyjoyment!\n', 'promise')

done_testing()
