r"""
Pyjo.IOLoop - Minimalistic event loop
=====================================
::

    import Pyjo.IOLoop

    # Listen on port 3000
    @Pyjo.IOLoop.server(port=3000)
    def server(loop, stream, id):
        @stream.on
        def read(stream, chunk):
            # Process input chunk
            print(chunk)

            # Write response
            stream.write(b'HTTP/1.1 200 OK')

    # Connect to port 3000
    @Pyjo.IOLoop.client(port=3000)
    def id(loop, err, stream):
        @stream.on
        def read(stream, chunk):
            # Process input
            print(f'Input: {chunk}')

        # Write request
        stream.write(b'GET / HTTP/1.1\x0d\x0a\x0d\x0a')

    # Add a timer
    Pyjo.IOLoop.timer(5, lambda loop: loop.remove(id))

    # Start event loop if necessary
    if not Pyjo.IOLoop.is_running():
        Pyjo.IOLoop.start()

:mod:`Pyjo.IOLoop` is a very minimalistic event loop based on
:mod:`Pyjo.Reactor`, it has been reduced to the absolute minimal feature set
required to build solid and scalable non-blocking clients and servers.

Depending on operating system, the default per-process and system-wide file
descriptor limits are often very low and need to be tuned for better
scalability.

The event loop is resilient to time jumps, as it uses a monotonic clock. A
TLS certificate and key are also built right in, to make writing test servers
as easy as possible.

What Mojo calls on the class, as ``Mojo::IOLoop->timer``, is a function of
the module that works with the :data:`singleton`, as ``Pyjo.IOLoop.timer``.
Each thread has a :data:`singleton` of its own, as each thread of Perl has a
copy of the interpreter, so that the threads run event loops of their own at
the same time, and the functions of the module work with the one of the
thread that calls them.
A method that takes a callback takes it also as the keyword argument ``cb``,
and is a decorator without it, and the decorated name is what the method
returns. ::

    @Pyjo.IOLoop.timer(3)
    def id(loop):
        print('Timeout!')

The end of a ``with`` block removes everything, as :meth:`~Pyjo_IOLoop.reset`
does.

Events
------

:mod:`Pyjo.IOLoop` inherits all events from :mod:`Pyjo.EventEmitter` and can
emit the following new ones.

finish
~~~~~~
::

    loop.on('finish', lambda loop: ...)

Emitted when the event loop wants to shut down gracefully and is just waiting
for all existing connections to be closed.

reset
~~~~~
::

    loop.on('reset', lambda loop: ...)

Emitted when the event loop is reset, this usually happens after the process
is forked to clean up resources that cannot be shared.

Debugging
---------

You can set the ``PYJO_IOLOOP_DEBUG`` environment variable to get some
advanced diagnostics information printed to ``sys.stderr``. ::

    PYJO_IOLOOP_DEBUG=1

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::IOLoop <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/IOLoop.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.EventEmitter
import Pyjo.Exception
import Pyjo.IOLoop.Client
import Pyjo.IOLoop.Datagram
import Pyjo.IOLoop.Server
import Pyjo.IOLoop.Stream
import Pyjo.Reactor

from Pyjo.Util import _call_hint, md5_sum, warn  # pyright: ignore[reportPrivateUsage]

import atexit
import builtins
import gc
import os
import random
import sys
import threading
import time
import weakref

from collections.abc import Callable, Iterator
from types import TracebackType
from typing import TYPE_CHECKING, Any, Concatenate, Self, overload


if TYPE_CHECKING:
    import Pyjo.IOLoop.ChildProcess
    import Pyjo.IOLoop.Subprocess
    import Pyjo.Promise

    from Pyjo.IOLoop.Subprocess import Child, Parent


type Anything = builtins.object

# A callback of a timer gets the loop
type TimerCallback = Callable[[Any], Anything]

# A callback of a server gets the loop, the stream and the id of the connection
type ServerCallback = Callable[[Any, Any, str], Anything]

# A callback of a client gets the loop, an error and the stream
type ClientCallback = Callable[[Any, Any, Any], Anything]

# A callback of a datagram socket gets the loop, the socket and its id
type DatagramCallback = Callable[[Any, Any, str], Anything]

DEBUG = bool(os.environ.get('PYJO_IOLOOP_DEBUG'))

# The states that reset(freeze=True) keeps
_FROZEN: list[dict[str, Any]] = []

# Not in Mojolicious: the singleton of each thread, as each thread of Perl has a copy of the interpreter with its own
_local = threading.local()

# Not in Mojolicious: the event loops that exist, which are reset at the end of the interpreter
_LOOPS: 'weakref.WeakSet[Pyjo_IOLoop]' = weakref.WeakSet()


class Pyjo_IOLoop(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.IOLoop` inherits all methods from :mod:`Pyjo.EventEmitter` and
    implements the following new ones.
    """

    def __init__(
        self, *, max_accepts: int = 0, max_connections: int = 1000, reactor: Pyjo.Reactor.object | None = None
    ) -> None:
        """::

            loop = Pyjo.IOLoop.new()
            loop = Pyjo.IOLoop.new(max_connections=100)

        Construct a new :mod:`Pyjo.IOLoop` object.
        """
        super().__init__()

        self.max_accepts = max_accepts
        """::

            max = loop.max_accepts
            loop.max_accepts = 1000

        The maximum number of connections this event loop is allowed to
        accept, before shutting down gracefully without interrupting existing
        connections, defaults to ``0``. Setting the value to ``0`` will allow
        this event loop to accept new connections indefinitely. Note that up to
        half of this value can be subtracted randomly to improve load balancing
        between multiple server processes, and to make sure that not all of
        them restart at the same time.
        """

        self.max_connections = max_connections
        """::

            max = loop.max_connections
            loop.max_connections = 100

        The maximum number of accepted connections this event loop is allowed
        to handle concurrently, before stopping to accept new incoming
        connections, defaults to ``1000``.
        """

        _LOOPS.add(self)
        self._accepting = False
        self._accepts: int | None = None
        self._acceptors: dict[str, Any] = {}
        self._in: dict[str, dict[str, Any]] = {}
        self._out: dict[str, dict[str, Any]] = {}
        self._reactor = reactor
        self._stop = 0
        self._delay: str | None = None

    # Not in Mojolicious: a context manager, which removes everything, as reset does, where the block ends, as PyPy
    # frees the object only when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.reset()

    @property
    def reactor(self) -> Pyjo.Reactor.object:
        """::

            reactor = loop.reactor
            loop.reactor = Pyjo.Reactor.Asyncio.new()

        Low-level event reactor, usually a :mod:`Pyjo.Reactor.Asyncio` object
        with a default subscriber to the event ``error`` of
        :mod:`Pyjo.Reactor`. ::

            # Watch if handle becomes readable or writable
            Pyjo.IOLoop.singleton.reactor.io(handle, lambda reactor, writable: print(
                'Handle is writable' if writable else 'Handle is readable'
            ))

            # Change to watching only if handle becomes writable
            Pyjo.IOLoop.singleton.reactor.watch(handle, False, True)

            # Remove handle again
            Pyjo.IOLoop.singleton.reactor.remove(handle)
        """
        if self._reactor is None:
            name = Pyjo.Reactor.detect()
            if DEBUG:
                warn(f'-- Reactor initialized ({name})')
            reactor: Pyjo.Reactor.object = sys.modules[name].new()

            def catch(reactor: Pyjo.Reactor.object, err: Any) -> None:
                warn(f'{_name(type(reactor))}: {err}')

            self._reactor = reactor.catch(catch)
        return self._reactor

    @reactor.setter
    def reactor(self, value: Pyjo.Reactor.object) -> None:
        self._reactor = value

    def acceptor(self, acceptor: Any) -> Any:
        """::

            server = Pyjo.IOLoop.acceptor(id)
            server = loop.acceptor(id)
            id = loop.acceptor(Pyjo.IOLoop.Server.new())

        Get :mod:`Pyjo.IOLoop.Server` object for id or turn object into an
        acceptor.
        """
        # Find acceptor for id
        if isinstance(acceptor, str):
            return self._acceptors.get(acceptor)

        # Connect acceptor with reactor
        id = self._id()
        acceptor.reactor = self.reactor
        self._acceptors[id] = acceptor

        # Allow new acceptor to get picked up
        self._not_accepting()._maybe_accepting()

        return id

    # Not in Mojolicious: Perl has no event loop that its libraries could find running
    def blocking[**P, R](self, cb: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        """::

            result = Pyjo.IOLoop.blocking(cb, *args, **kwargs)
            result = loop.blocking(cb, *args, **kwargs)

        Call blocking code and return what it returns, with
        :meth:`Pyjo.Reactor.Pyjo_Reactor.blocking` of the reactor, so that a
        library that refuses to block in a running event loop of
        :mod:`asyncio`, as Django, runs. :mod:`Pyjo.App.WSGI` calls its
        application with it. ::

            # A query of Django in a check of the plugin Health
            plugin('Health', checks={'db': lambda c: Pyjo.IOLoop.blocking(Note.objects.exists)})
        """
        return self.reactor.blocking(cb, *args, **kwargs)

    # Unlike Mojolicious: the callback comes before the options, which are keyword arguments, or is the keyword
    # argument cb
    @overload
    def client(self, cb: ClientCallback, **options: Any) -> str: ...

    @overload
    def client(self, **options: Any) -> Callable[[ClientCallback], str]: ...

    def client(self, cb: ClientCallback | None = None, **options: Any) -> Any:
        """::

            id = Pyjo.IOLoop.client(cb, address='127.0.0.1', port=3000)
            id = loop.client(cb, address='127.0.0.1', port=3000)
            id = loop.client(cb=cb, address='127.0.0.1', port=3000)

            @loop.client(address='127.0.0.1', port=3000)
            def id(loop, err, stream):
                ...

        Open a TCP/IP or UNIX domain socket connection with
        :mod:`Pyjo.IOLoop.Client` and create a stream object (usually
        :mod:`Pyjo.IOLoop.Stream`), takes the same arguments as
        :meth:`Pyjo.IOLoop.Client.connect`.
        """
        # Not in Mojolicious: a decorator
        if cb is None:

            def decorator(cb: ClientCallback) -> str:
                return self.client(cb, **options)

            return decorator

        id = self._id()
        client: Any = Pyjo.IOLoop.Client.new(reactor=self.reactor)
        self._out[id] = {'client': client}

        ref = weakref.ref(self)

        def connect(client: Any, handle: Any) -> None:
            if (loop := ref()) is None:
                return
            del loop._out[id]['client']
            stream = Pyjo.IOLoop.Stream.new(handle)
            loop._stream(stream, id)
            cb(loop, None, stream)

        def error(client: Any, err: Any) -> None:
            if (loop := ref()) is None:
                return
            loop._remove(id)
            cb(loop, err, None)

        client.on('connect', connect)
        client.on('error', error)
        client.connect(**options)

        return id

    # Not in Mojolicious: the stream of a connection as a promise, as connect of promise-socket
    def client_p(self, **options: Any) -> 'Pyjo.Promise.object':
        """::

            promise = Pyjo.IOLoop.client_p(address='127.0.0.1', port=3000)
            promise = loop.client_p(address='127.0.0.1', port=3000)

        Same as :meth:`client`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled with the stream object of the connection, and rejected
        with its error. The stream keeps what arrives for its promises, as
        :meth:`~Pyjo.IOLoop.Stream.Pyjo_IOLoop_Stream.read_p`, from the
        connection on, as a coroutine that awaits the promise goes on later,
        when a peer may have sent something already. ::

            stream = await Pyjo.IOLoop.client_p(address='127.0.0.1', port=3000)
            await stream.write_p(b'Hello!')
            reply = await stream.read_p()
        """
        # Imported here, as Pyjo.Promise uses Pyjo.IOLoop
        import Pyjo.Promise

        promise = Pyjo.Promise.new()
        promise.ioloop = self

        def connected(loop: Any, err: Any, stream: Any) -> None:
            if err is not None:
                promise.reject(err)
                return
            stream._chunks()  # pyright: ignore[reportPrivateUsage]
            promise.resolve(stream)

        self.client(connected, **options)
        return promise

    # Not in Mojolicious: datagram sockets
    @overload
    def datagram(self, cb: DatagramCallback, **options: Any) -> str: ...

    @overload
    def datagram(self, **options: Any) -> Callable[[DatagramCallback], str]: ...

    def datagram(self, cb: DatagramCallback | None = None, **options: Any) -> Any:
        """::

            id = Pyjo.IOLoop.datagram(cb, port=9999)
            id = loop.datagram(cb, address='127.0.0.1', port=9999)
            id = loop.datagram(cb=cb)

            @loop.datagram(port=9999)
            def id(loop, datagram, id):
                ...

        Open a datagram socket with :mod:`Pyjo.IOLoop.Datagram`, bound with the
        options of :meth:`Pyjo.IOLoop.Datagram.Pyjo_IOLoop_Datagram.bind` if
        any are given, which the event loop watches until it is closed. The
        callback gets the loop, the datagram socket and its id, which
        :meth:`remove` takes. ::

            # Echo server
            @Pyjo.IOLoop.datagram(address='127.0.0.1', port=9999)
            def id(loop, datagram, id):
                datagram.on('message', lambda datagram, data, peer: datagram.send(data, peer))
        """
        # Not in Mojolicious: a decorator
        if cb is None:

            def decorator(cb: DatagramCallback) -> str:
                return self.datagram(cb, **options)

            return decorator

        datagram = Pyjo.IOLoop.Datagram.new()
        datagram.reactor = self.reactor
        if options:
            datagram.bind(**options)
        id = self._stream(datagram, self._id())
        cb(self, datagram, id)

        return id

    @property
    def is_running(self) -> bool:
        """::

            boolean = Pyjo.IOLoop.is_running()
            boolean = loop.is_running

        Check if event loop is running.
        """
        return self.reactor.is_running

    # Not in Mojolicious: what readiness answers while the connections are closing, as Mojo keeps the count private
    @property
    def is_stopping(self) -> bool:
        """::

            boolean = Pyjo.IOLoop.is_stopping()
            boolean = loop.is_stopping

        Check if event loop is stopping gracefully, from :meth:`stop_gracefully`,
        its delay too, until :meth:`reset`.
        """
        return bool(self._stop) or self._delay is not None

    @overload
    def next_tick(self, cb: TimerCallback) -> None: ...

    @overload
    def next_tick(self) -> Callable[[TimerCallback], None]: ...

    def next_tick(self, cb: TimerCallback | None = None) -> Any:
        """::

            none = Pyjo.IOLoop.next_tick(lambda loop: ...)
            none = loop.next_tick(lambda loop: ...)

        Execute callback as soon as possible, but not before returning or other
        callbacks that have been registered with this method, always returns
        ``None``. ::

            # Perform operation on next reactor tick
            Pyjo.IOLoop.next_tick(lambda loop: ...)
        """
        # Not in Mojolicious: a decorator
        if cb is None:

            def decorator(cb: TimerCallback) -> None:
                return self.next_tick(cb)

            return decorator

        ref = weakref.ref(self)
        callback = cb

        def next_tick(reactor: Pyjo.Reactor.object) -> None:
            callback(ref())

        return self.reactor.next_tick(next_tick)

    def one_tick(self) -> None:
        """::

            Pyjo.IOLoop.one_tick()
            loop.one_tick()

        Run event loop until an event occurs. ::

            # Don't block longer than 0.5 seconds
            id = Pyjo.IOLoop.timer(0.5, lambda loop: None)
            Pyjo.IOLoop.one_tick()
            Pyjo.IOLoop.remove(id)
        """
        if self.is_running:
            Pyjo.Exception.object.throw('Pyjo.IOLoop already running')
        self.reactor.one_tick()

    @overload
    def recurring(self, after: float, cb: TimerCallback) -> str: ...

    @overload
    def recurring(self, after: float) -> Callable[[TimerCallback], str]: ...

    def recurring(self, after: float, cb: TimerCallback | None = None) -> Any:
        """::

            id = Pyjo.IOLoop.recurring(3, lambda loop: ...)
            id = loop.recurring(0, lambda loop: ...)
            id = loop.recurring(0.25, lambda loop: ...)

        Create a new recurring timer, invoking the callback repeatedly after a
        given amount of time in seconds. ::

            # Perform operation every 5 seconds
            Pyjo.IOLoop.recurring(5, lambda loop: ...)
        """
        return self._timer('recurring', after, cb)

    def remove(self, id: str, *, close: bool = True) -> None:
        """::

            Pyjo.IOLoop.remove(id)
            loop.remove(id)
            loop.remove(id, close=False)

        Remove anything with an id, connections will be dropped gracefully by
        allowing them to finish writing all data in their write buffers. An
        acceptor keeps its listen socket open with ``close=False``, so that it
        can be turned into an acceptor again.
        """
        c = self._in.get(id) or self._out.get(id)
        if c and (stream := c.get('stream')):
            return stream.close_gracefully()
        self._remove(id, close)

    def reset(self, *, freeze: bool = False) -> None:
        """::

            Pyjo.IOLoop.reset()
            loop.reset()
            loop.reset(freeze=True)

        Remove everything and stop the event loop.

        These options are currently available:

        freeze
            ::

                freeze=True

            Freeze the current state of the event loop in time before
            resetting it. This will prevent active connections from getting
            closed immediately, which can help with many unintended side
            effects when processes are forked.
        """
        self.emit('reset').stop()
        if freeze:
            _FROZEN.append(dict(self.__dict__))
            self._reactor = None
        else:
            self.reactor.reset()

        acceptors, connections = [*self._acceptors.values()], [*self._in.values(), *self._out.values()]
        self._accepting = False
        self._acceptors = {}
        self._events = {}
        self._in = {}
        self._out = {}
        self._stop = 0
        self._delay = None

        # Perl closes what it frees at once, Python later, as PyPy does when its garbage collector runs
        if not freeze:
            for acceptor in acceptors:
                acceptor.close()
            for connection in connections:
                for value in connection.values():
                    value.close()

    # Unlike Mojolicious: the callback comes before the options, which are keyword arguments, or is the keyword
    # argument cb
    @overload
    def server(self, cb: ServerCallback, **options: Any) -> str: ...

    @overload
    def server(self, **options: Any) -> Callable[[ServerCallback], str]: ...

    def server(self, cb: ServerCallback | None = None, **options: Any) -> Any:
        """::

            id = Pyjo.IOLoop.server(cb, port=3000)
            id = loop.server(cb, port=3000)
            id = loop.server(cb=cb, port=3000)

            @loop.server(port=3000)
            def id(loop, stream, id):
                ...

        Accept TCP/IP and UNIX domain socket connections with
        :mod:`Pyjo.IOLoop.Server` and create stream objects (usually
        :mod:`Pyjo.IOLoop.Stream`), takes the same arguments as
        :meth:`Pyjo.IOLoop.Server.listen`. ::

            # Listen on random port
            id = Pyjo.IOLoop.server(lambda loop, stream, id: ..., address='127.0.0.1')
            port = Pyjo.IOLoop.acceptor(id).port
        """
        # Not in Mojolicious: a decorator
        if cb is None:

            def decorator(cb: ServerCallback) -> str:
                return self.server(cb, **options)

            return decorator

        server: Any = Pyjo.IOLoop.Server.new()
        ref = weakref.ref(self)

        def accept(server: Any, handle: Any) -> None:
            if (loop := ref()) is None:
                return
            stream = Pyjo.IOLoop.Stream.new(handle)
            id = loop._stream(stream, loop._id(), True)
            cb(loop, stream, id)

            # Enforce connection limit (randomize to improve load balancing)
            if max := loop.max_accepts:
                if loop._accepts is None:
                    loop._accepts = max - int(random.random() * max / 2)
                loop._accepts -= 1
                if loop._accepts <= 0:
                    loop.stop_gracefully()

            # Stop accepting if connection limit has been reached
            if loop._limit():
                loop._not_accepting()

        server.on('accept', accept)
        server.listen(**options)

        return self.acceptor(server)

    @classmethod
    def singleton(cls) -> 'Pyjo_IOLoop':
        """::

            loop = Pyjo.IOLoop.object.singleton()
            loop = Pyjo.IOLoop.singleton

        The global :mod:`Pyjo.IOLoop` singleton, used to access a single shared
        event loop object from everywhere inside the thread, which is also the
        :data:`singleton` of the module. Each thread has one of its own. ::

            # Many methods also allow you to take shortcuts
            Pyjo.IOLoop.timer(2, lambda loop: Pyjo.IOLoop.stop())
            Pyjo.IOLoop.start()

            # Restart active timer
            id = Pyjo.IOLoop.timer(3, lambda loop: print('Timeout!'))
            Pyjo.IOLoop.singleton.reactor.again(id)

            # Watch a file descriptor if it becomes readable
            Pyjo.IOLoop.singleton.reactor.io(fd, lambda reactor, writable: print(
                'Handle is writable' if writable else 'Handle is readable'
            )).watch(fd, True, False)
        """
        try:
            return _local.singleton
        except AttributeError:
            _local.singleton = loop = Pyjo_IOLoop()
            return loop

    def spawn(self, args: Any, **options: Any) -> 'Pyjo.IOLoop.ChildProcess.object':
        """::

            child = Pyjo.IOLoop.spawn(['ls', '-l'])
            child = loop.spawn(['php-cgi', 'index.php'], cwd='/var/www')

        Run a program with :mod:`Pyjo.IOLoop.ChildProcess` on the reactor of
        the event loop, with the options of
        :meth:`Pyjo.IOLoop.ChildProcess.Pyjo_IOLoop_ChildProcess.spawn`. ::

            # The output of a program, and its exit code
            child = Pyjo.IOLoop.spawn(['ls', '-l'])
            child.stdout.on('read', lambda stream, chunk: print(chunk))
            child.on('close', lambda child, code, signal: print(f'Exited with {code}'))
        """
        # Not in Mojolicious: child processes, inspired by child_process of Node.js, imported here, as
        # Pyjo.IOLoop.ChildProcess uses Pyjo.IOLoop
        import Pyjo.IOLoop.ChildProcess

        return Pyjo.IOLoop.ChildProcess.new(reactor=self.reactor).spawn(args, **options)

    def start(self) -> None:
        """::

            Pyjo.IOLoop.start()
            loop.start()

        Start the event loop, this will block until :meth:`stop` is called.
        Note that some reactors stop automatically if there are no events being
        watched anymore. ::

            # Start event loop only if it is not running already
            if not Pyjo.IOLoop.is_running():
                Pyjo.IOLoop.start()
        """
        if self.is_running:
            Pyjo.Exception.object.throw('Pyjo.IOLoop already running')
        self.reactor.start()

    def stop(self) -> None:
        """::

            Pyjo.IOLoop.stop()
            loop.stop()

        Stop the event loop, this will not interrupt any existing connections
        and the event loop can be restarted by running :meth:`start` again.
        """
        self.reactor.stop()

    # Not in Mojolicious: the delay, while which the event loop serves as before and is_stopping is true already, so that
    # the readiness of a server fails before it stops accepting
    def stop_gracefully(self, delay: float = 0) -> None:
        """::

            Pyjo.IOLoop.stop_gracefully()
            loop.stop_gracefully()
            loop.stop_gracefully(delay=5)

        Stop accepting new connections and wait for already accepted
        connections to be closed, before stopping the event loop. With a
        ``delay`` in seconds, the event loop keeps accepting them for that
        long, while :attr:`is_stopping` is true already, so that a load
        balancer that checks the readiness of the server sends no more of
        them. A call without a delay ends the delay of an earlier one.
        """
        if delay > 0:
            if self._delay is None and not self._stop:
                self._delay = self.timer(delay, lambda loop: loop.stop_gracefully())
            return
        if (timer := self._delay) is not None:
            self._delay = None
            self.remove(timer)
        self._not_accepting()
        self._stop += 1
        if not len(self.emit('finish')._in):
            self.stop()

    def stream(self, stream: Any) -> Any:
        """::

            stream = Pyjo.IOLoop.stream(id)
            stream = loop.stream(id)
            id = loop.stream(Pyjo.IOLoop.Stream.new(handle))

        Get :mod:`Pyjo.IOLoop.Stream` object for id or turn object into a
        connection. ::

            # Increase inactivity timeout for connection to 300 seconds
            Pyjo.IOLoop.stream(id).timeout = 300
        """
        if stream is None:
            return None
        if not isinstance(stream, str):
            return self._stream(stream, self._id())
        c = self._in.get(stream) or self._out.get(stream) or {}
        return c.get('stream')

    def subprocess(
        self, child: 'Child | None' = None, parent: 'Parent | None' = None
    ) -> 'Pyjo.IOLoop.Subprocess.object':
        """::

            subprocess = Pyjo.IOLoop.subprocess()
            subprocess = loop.subprocess()
            subprocess = loop.subprocess(lambda subprocess: ..., lambda subprocess, err, *results: ...)

        Build :mod:`Pyjo.IOLoop.Subprocess` object to perform computationally
        expensive operations in subprocesses, without blocking the event loop.
        Callbacks will be passed along to
        :meth:`Pyjo.IOLoop.Subprocess.Pyjo_IOLoop_Subprocess.run`. ::

            # Operation that would block the event loop for 5 seconds
            Pyjo.IOLoop.subprocess().run_p(blocking).then(lambda *results: print(f'I {results[0]} {results[1]}!')).catch(
                lambda err: print(f'Subprocess error: {err}')
            )
        """
        # Not in Mojolicious: imported here, as Pyjo.IOLoop.Subprocess uses Pyjo.Promise, which uses Pyjo.IOLoop
        import Pyjo.IOLoop.Subprocess

        subprocess = Pyjo.IOLoop.Subprocess.new(ioloop=self)
        if child is not None and parent is not None:
            return subprocess.run(child, parent)
        return subprocess

    @overload
    def timer(self, after: float, cb: TimerCallback) -> str: ...

    @overload
    def timer(self, after: float) -> Callable[[TimerCallback], str]: ...

    def timer(self, after: float, cb: TimerCallback | None = None) -> Any:
        """::

            id = Pyjo.IOLoop.timer(3, lambda loop: ...)
            id = loop.timer(0, lambda loop: ...)
            id = loop.timer(0.25, lambda loop: ...)

        Create a new timer, invoking the callback after a given amount of time
        in seconds. ::

            # Perform operation in 5 seconds
            Pyjo.IOLoop.timer(5, lambda loop: ...)
        """
        return self._timer('timer', after, cb)

    def _id(self) -> str:
        while True:
            id = md5_sum(f'c{time.monotonic()}{random.random()}'.encode())
            if id not in self._in and id not in self._out and id not in self._acceptors:
                return id

    def _limit(self) -> bool:
        return True if self._stop else len(self._in) >= self.max_connections

    # Not in Mojolicious: the acceptors of a copy that are still there, as the garbage collector may free another server
    # meanwhile, whose finalizer removes its acceptor and closes its socket, which a new one may then reuse
    def _each_acceptor(self) -> Iterator[Any]:
        for id, acceptor in list(self._acceptors.items()):
            if self._acceptors.get(id) is acceptor:
                yield acceptor

    def _maybe_accepting(self) -> None:
        if self._accepting or self._limit():
            return
        for acceptor in self._each_acceptor():
            acceptor.start()
        self._accepting = True

    def _not_accepting(self) -> Self:
        if not self._accepting:
            return self
        self._accepting = False
        for acceptor in self._each_acceptor():
            acceptor.stop()
        return self

    def _remove(self, id: str, close: bool = True) -> None:
        # Timer
        if self.reactor.remove(id):
            return

        # Acceptor
        if (acceptor := self._acceptors.pop(id, None)) is not None:
            # Perl closes the acceptor it frees at once, Python later; Not in Mojolicious: one that a server keeps to
            # resume it later, as Perl does not free it
            if close:
                acceptor.close()
            else:
                acceptor.stop()
            return self._not_accepting()._maybe_accepting()

        # Connection
        if (connection := self._in.pop(id, None) or self._out.pop(id, None)) is None:
            return
        # Perl closes the client it frees at once, Python later
        if (client := connection.get('client')) is not None:
            client.close()
        if self._stop and not len(self._in):
            return self.stop()
        self._maybe_accepting()
        if DEBUG:
            warn(f'-- {id} <<< {os.getpid()} ({len(self._in)}:{len(self._out)})')

    def _stream(self, stream: Any, id: str, server: bool = False) -> str:
        # Connect stream with reactor
        stream.reactor = self.reactor
        (self._in if server else self._out).setdefault(id, {})['stream'] = stream
        if DEBUG:
            warn(f'-- {id} >>> {os.getpid()} ({len(self._in)}:{len(self._out)})')

        ref = weakref.ref(self)

        def close(stream: Any) -> None:
            if (loop := ref()) is not None:
                loop._remove(id)

        stream.on('close', close)
        stream.start()

        return id

    def _timer(self, method: str, after: float, cb: TimerCallback | None) -> Any:
        # Not in Mojolicious: a decorator
        if cb is None:

            def decorator(cb: TimerCallback) -> Any:
                return self._timer(method, after, cb)

            return decorator

        ref = weakref.ref(self)
        callback = cb

        def timer(reactor: Pyjo.Reactor.object) -> None:
            try:
                callback(ref())
            except TypeError as e:
                # Not in Mojolicious: the arguments of a callback, which Perl does not check
                _call_hint(e, 'the callback of a timer gets the event loop')
                raise

        return getattr(self.reactor, method)(after, timer)


def _name(cls: type) -> str:
    return f'{cls.__module__}.{cls.__qualname__}'


new = Pyjo_IOLoop.new
object = Pyjo_IOLoop
IOLoop = Pyjo_IOLoop

# Left out from Mojolicious: $SIG{PIPE} = 'IGNORE', which Python does already

singleton: Pyjo_IOLoop
"""::

    loop = Pyjo.IOLoop.singleton

The global :mod:`Pyjo.IOLoop` singleton, as :meth:`Pyjo_IOLoop.singleton`
gives it, the one of the thread.
"""

# Initialize singleton reactor early
Pyjo_IOLoop.singleton().reactor


# Not in Mojolicious: Perl closes the handles that are left at the end of the interpreter, Python warns that they were
# not closed, as __del__ does nothing while it finalizes, so the connections of the event loops are closed and the
# objects that close theirs are freed before; registered after the reactor, so that it runs before the event loops of
# asyncio are closed
@atexit.register
def _cleanup() -> None:
    def close(*objects: Any) -> None:
        for obj in objects:
            try:
                obj.close()
            except Exception:
                pass

    # The cleanups that finalizers deferred, before and after the event loops and the garbage collector, whose
    # finalizers run in this frame of Pyjo.IOLoop, and so are deferred too
    Pyjo.Reactor._drain(every=True)  # pyright: ignore[reportPrivateUsage]

    for loop in list(_LOOPS):
        try:
            loop.reset()
        except Exception:
            pass

    # The frozen state too, which Perl frees then
    for state in _FROZEN:
        close(*state.get('_acceptors', {}).values())
        for connection in [*state.get('_in', {}).values(), *state.get('_out', {}).values()]:
            close(*connection.values())
    _FROZEN.clear()
    gc.collect()
    Pyjo.Reactor._drain(every=True)  # pyright: ignore[reportPrivateUsage]


# Not in Mojolicious: the singleton is found in the thread that asks for it, as a module has the same attributes in all
# threads
def __getattr__(name: str) -> Any:
    if name == 'singleton':
        return Pyjo_IOLoop.singleton()
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


# What Mojo calls on the class works with the singleton, the one of the thread that calls it
def _shortcut[**P, R](method: Callable[Concatenate[Pyjo_IOLoop, P], R]) -> Callable[P, R]:
    def shortcut(*args: P.args, **kwargs: P.kwargs) -> R:
        return method(Pyjo_IOLoop.singleton(), *args, **kwargs)

    return shortcut


acceptor = _shortcut(Pyjo_IOLoop.acceptor)
blocking = _shortcut(Pyjo_IOLoop.blocking)
client = _shortcut(Pyjo_IOLoop.client)
client_p = _shortcut(Pyjo_IOLoop.client_p)
datagram = _shortcut(Pyjo_IOLoop.datagram)
next_tick = _shortcut(Pyjo_IOLoop.next_tick)
one_tick = _shortcut(Pyjo_IOLoop.one_tick)
recurring = _shortcut(Pyjo_IOLoop.recurring)
remove = _shortcut(Pyjo_IOLoop.remove)
reset = _shortcut(Pyjo_IOLoop.reset)
server = _shortcut(Pyjo_IOLoop.server)
spawn = _shortcut(Pyjo_IOLoop.spawn)
start = _shortcut(Pyjo_IOLoop.start)
stop = _shortcut(Pyjo_IOLoop.stop)
stop_gracefully = _shortcut(Pyjo_IOLoop.stop_gracefully)
stream = _shortcut(Pyjo_IOLoop.stream)
subprocess = _shortcut(Pyjo_IOLoop.subprocess)
timer = _shortcut(Pyjo_IOLoop.timer)


def is_running() -> bool:
    """::

        boolean = Pyjo.IOLoop.is_running()

    Check if the :data:`singleton` is running.
    """
    return Pyjo_IOLoop.singleton().is_running


# Not in Mojolicious: the counterpart of is_running
def is_stopping() -> bool:
    """::

        boolean = Pyjo.IOLoop.is_stopping()

    Check if the :data:`singleton` is stopping gracefully.
    """
    return Pyjo_IOLoop.singleton().is_stopping
