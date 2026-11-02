"""
Pyjo.IOLoop.Datagram - Non-blocking datagram socket
===================================================
::

    from Pyjo.IOLoop.Datagram import Datagram

    # Echo server
    server = Datagram()
    server.on('message', lambda server, data, peer: server.send(b'Echo: ' + data, peer))
    server.bind(address='127.0.0.1', port=9999)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.IOLoop.Datagram

    # Echo server
    server = Pyjo.IOLoop.Datagram.new()
    server.on('message', lambda server, data, peer: server.send(b'Echo: ' + data, peer))
    server.bind(address='127.0.0.1', port=9999)

    # Client
    client = Pyjo.IOLoop.Datagram.new()
    client.on('message', lambda client, data, peer: print(data))
    client.on('error', lambda client, err: print(err))
    client.send(b'Hello!', ('127.0.0.1', 9999))

    # Start reactor if necessary
    if not client.reactor.is_running:
        client.reactor.start()

:mod:`Pyjo.IOLoop.Datagram` is a container for datagram sockets used by
:mod:`Pyjo.IOLoop`: UDP over IPv4 and IPv6, and UNIX domain datagram sockets.
Every :meth:`send` is one datagram, and every ``message`` event is one
datagram that has arrived.

A socket that is neither bound with :meth:`bind` nor connected with
:meth:`connect` is bound to a random port by the first :meth:`send`, as the
family of the address of the peer needs it.

The end of a ``with`` block closes the socket.

Events
------

:mod:`Pyjo.IOLoop.Datagram` inherits all events from :mod:`Pyjo.EventEmitter`
and can emit the following new ones.

close
~~~~~
::

    datagram.on('close', lambda datagram: ...)

Emitted if the socket gets closed.

connect
~~~~~~~
::

    datagram.on('connect', lambda datagram: ...)

Emitted once the socket has been connected with :meth:`connect`.

error
~~~~~
::

    datagram.on('error', lambda datagram, err: ...)

Emitted if an error occurs on the socket, fatal if unhandled. The error is the
:class:`OSError` of the handle, as a datagram that cannot be sent or the
refusal of a peer that a connected socket gets, or a message for a name that
cannot be resolved. The socket stays open.

message
~~~~~~~
::

    datagram.on('message', lambda datagram, data, peer: ...)

Emitted for every datagram that arrives, with the address of its sender, as
:meth:`socket.socket.recvfrom` gives it, which :meth:`send` takes as the
address of a reply.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Inspired by `dgram <https://nodejs.org/api/dgram.html>`_ of Node.js, as
Mojolicious has no datagram sockets.
"""

import Pyjo.EventEmitter
import Pyjo.IOLoop
import Pyjo.IOLoop.Client
import Pyjo.Reactor

import atexit
import builtins
import collections
import errno
import os
import socket
import stat
import struct
import sys
import weakref

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self


if TYPE_CHECKING:
    import Pyjo.Iterator
    import Pyjo.Promise


# The address of a peer: a tuple as recvfrom gives it, or the path of a UNIX domain socket
type Peer = tuple[Any, ...] | str

type Anything = builtins.object

# A callback of a send gets the datagram socket once the datagram has been sent
type SendCallback = Callable[[Any], Anything]

# The largest datagram that UDP carries
_SIZE = 65535

# Python has no UNIX domain sockets on Windows
_NO_UNIX = 'UNIX domain sockets are not supported'


@dataclass
class _Datagram:
    """A datagram waiting to be sent, and the name of its peer while it is being resolved."""

    data: bytes
    cb: SendCallback | None
    failed: Callable[[Any], Anything] | None = None
    family: int = 0
    sockaddr: Any = None
    resolver: Any = None
    error: str | None = None


class Pyjo_IOLoop_Datagram(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.IOLoop.Datagram` inherits all methods from
    :mod:`Pyjo.EventEmitter` and implements the following new ones.
    """

    def __init__(self, handle: socket.socket | None = None) -> None:
        """::

            datagram = Pyjo.IOLoop.Datagram.new()
            datagram = Pyjo.IOLoop.Datagram.new(handle)

        Construct a new :mod:`Pyjo.IOLoop.Datagram` object, with a datagram
        socket that is already bound or connected, if given.
        """
        super().__init__()

        self._connecting: Any = None
        self._graceful = False
        self._handle = handle
        self._ended = False
        self._paused = False
        self._queue: collections.deque[_Datagram] = collections.deque()
        self._reactor: weakref.ref[Pyjo.Reactor.object] | None = None

        if handle is not None:
            handle.setblocking(False)
        _DATAGRAMS.add(self)

    def __del__(self) -> None:
        # Module globals may be gone at the end of the interpreter
        try:
            if not sys.is_finalizing() and getattr(self, '_handle', None) is not None:
                reactor = self._reactor() if self._reactor is not None else None
                Pyjo.Reactor._finalize(self.close, reactor)  # pyright: ignore[reportPrivateUsage]
        except Exception:
            pass

    # Not in Mojolicious: a context manager, which closes the socket where the block ends, as PyPy frees the object only
    # when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    def __aiter__(self) -> AsyncIterator[tuple[bytes, Any]]:
        """::

            async for data, peer in datagram:
                ...

        Same as :meth:`iterate`.
        """
        return aiter(self.iterate())

    @property
    def reactor(self) -> Pyjo.Reactor.object:
        """::

            reactor = datagram.reactor
            datagram.reactor = Pyjo.Reactor.Poll.new()

        Low-level event reactor, defaults to the ``reactor`` attribute value of
        the global :mod:`Pyjo.IOLoop` singleton. Note that this attribute is
        weakened.
        """
        if self._reactor is None:
            self._reactor = weakref.ref(Pyjo.IOLoop.singleton.reactor)
        if (reactor := self._reactor()) is None:
            raise ReferenceError('weakly-referenced object no longer exists')
        return reactor

    @reactor.setter
    def reactor(self, value: Pyjo.Reactor.object) -> None:
        self._reactor = weakref.ref(value)

    def add_membership(self, group: str, interface: str | int | None = None) -> Self:
        """::

            datagram = datagram.add_membership('224.0.0.114')
            datagram = datagram.add_membership('224.0.0.114', '192.168.1.1')
            datagram = datagram.add_membership('ff02::114', 'eth0')

        Join a multicast group, on the interface with the address for IPv4,
        or the name or the index for IPv6, or on the one that the system
        chooses.
        """
        self._membership(group, interface, True)
        return self

    def bind(self, **options: Any) -> Self:
        """::

            datagram = datagram.bind(port=9999)

        Bind the socket to a local address, and start receiving datagrams.

        These options are currently available:

        address
            ::

                address='127.0.0.1'

            Local address to bind to, defaults to ``0.0.0.0``.

        ipv6_only
            ::

                ipv6_only=True

            Receive only IPv6 datagrams on an IPv6 address, with the
            ``IPV6_V6ONLY`` socket option.

        path
            ::

                path='/tmp/myapp.sock'

            Path for UNIX domain datagram socket to bind to.

        port
            ::

                port=9999

            Port to bind to, defaults to a random port.

        reuse
            ::

                reuse=True

            Allow multiple sockets to use the same port with the
            ``SO_REUSEPORT`` socket option, or ``SO_REUSEADDR`` on Windows,
            which has no ``SO_REUSEPORT``.
        """
        path = options.get('path')
        created: socket.socket | None = None
        try:
            # UNIX domain socket
            if path:
                if os.path.exists(path) and stat.S_ISSOCK(os.stat(path).st_mode):
                    os.remove(path)
                if sys.platform == 'win32':
                    raise OSError(errno.EAFNOSUPPORT, _NO_UNIX)
                handle = created = self._handle or socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                handle.bind(path)

            # IP socket
            else:
                host = str(options.get('address') or '0.0.0.0').replace('[', '').replace(']', '')
                family, _, _, _, sockaddr = socket.getaddrinfo(
                    host, options.get('port') or 0, type=socket.SOCK_DGRAM, flags=socket.AI_PASSIVE
                )[0]
                handle = created = self._handle or socket.socket(family, socket.SOCK_DGRAM)
                # SO_REUSEADDR on Windows, which has no SO_REUSEPORT, and lets several sockets of datagrams have the
                # same port there, as reuseAddr of dgram of Node.js does
                if options.get('reuse'):
                    if sys.platform == 'win32':
                        handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    else:
                        handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                if options.get('ipv6_only') and family == socket.AF_INET6:
                    handle.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                handle.bind(sockaddr)
        except OSError as e:
            # The socket that cannot be bound is closed, as Pyjo.IOLoop.Server does with one that cannot listen
            if created is not None and created is not self._handle:
                created.close()
            raise _error(e, "Can't bind datagram socket") from e

        handle.setblocking(False)
        self._handle = handle
        self.start()
        return self

    @property
    def broadcast(self) -> bool:
        """::

            boolean = datagram.broadcast
            datagram.broadcast = True

        Allow datagrams to a broadcast address, with the ``SO_BROADCAST``
        socket option.
        """
        return bool(self._socket().getsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST))

    @broadcast.setter
    def broadcast(self, value: bool) -> None:
        self._socket().setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, int(value))

    @property
    def bytes_waiting(self) -> int:
        """::

            num = datagram.bytes_waiting

        Number of bytes of the datagrams that have been enqueued with
        :meth:`send` and are waiting to be sent.
        """
        return sum(len(d.data) for d in self._queue)

    def close(self) -> None:
        """::

            datagram.close()

        Close socket immediately, the datagrams that wait to be sent are
        dropped.
        """
        reactor = self._reactor() if self._reactor is not None else Pyjo.IOLoop.singleton.reactor
        for d in self._queue:
            self._cancel(d.resolver)
        self._queue.clear()
        if self._connecting is not None and not isinstance(self._connecting, bool):
            self._cancel(self._connecting)
        self._connecting = None
        if (handle := self._handle) is None:
            return
        self._handle = None
        # Not in Mojolicious: the handle of a socket whose reactor is gone is closed, as Perl frees it with the socket
        if reactor is None:
            handle.close()
            return
        reactor.remove(handle)
        handle.close()
        self._ended = True
        self.emit('close')

    def close_gracefully(self) -> None:
        """::

            datagram.close_gracefully()

        Close socket once the datagrams that wait have been sent.
        """
        if self._queue:
            self._graceful = True
        else:
            self.close()

    def close_gracefully_p(self) -> 'Pyjo.Promise.object':
        """::

            promise = datagram.close_gracefully_p()

        Same as :meth:`close_gracefully`, but returns a :mod:`Pyjo.Promise`
        object, which is fulfilled once the socket has been closed, also when it
        is closed already, or has never been opened. ::

            await datagram.send_p(b'Bye!')
            await datagram.close_gracefully_p()
        """
        import Pyjo.Promise

        if self._handle is None:
            return Pyjo.Promise.resolve()
        promise = self.once_p('close')
        self.close_gracefully()
        return promise

    def connect(self, **options: Any) -> Self:
        """::

            datagram = datagram.connect(address='127.0.0.1', port=9999)

        Connect the socket to a peer, so that :meth:`send` needs no address and
        only the datagrams of the peer arrive, emitting ``connect`` once it is
        connected, or ``error`` if it cannot be. A name is resolved without
        blocking.

        These options are currently available:

        address
            ::

                address='mojolicious.org'

            Address or host name of the peer to connect to, defaults to
            ``127.0.0.1``.

        path
            ::

                path='/tmp/myapp.sock'

            Path of UNIX domain datagram socket to connect to.

        port
            ::

                port=9999

            Port to connect to.
        """
        ref = weakref.ref(self)

        def connected(family: int, sockaddr: Any, err: str | None) -> None:
            if (datagram := ref()) is not None:
                datagram._connected(family, sockaddr, err)

        self._connecting = True
        if path := options.get('path'):
            self._connecting = self._resolve(path, 0, connected, defer=True, unix=True)
        else:
            host = str(options.get('address') or '127.0.0.1').replace('[', '').replace(']', '')
            self._connecting = self._resolve(host, int(options.get('port') or 0), connected, defer=True)
        return self

    def drop_membership(self, group: str, interface: str | int | None = None) -> Self:
        """::

            datagram = datagram.drop_membership('224.0.0.114')

        Leave a multicast group, with the same arguments as
        :meth:`add_membership`.
        """
        self._membership(group, interface, False)
        return self

    @property
    def handle(self) -> socket.socket | None:
        """::

            handle = datagram.handle

        Get handle for socket, a :class:`socket.socket` object, or ``None``
        before it is bound.
        """
        return self._handle

    @property
    def multicast_loopback(self) -> bool:
        """::

            boolean = datagram.multicast_loopback
            datagram.multicast_loopback = False

        Receive the multicast datagrams that the socket sends, with the
        ``IP_MULTICAST_LOOP`` or ``IPV6_MULTICAST_LOOP`` socket option.
        """
        level, name = self._option(socket.IP_MULTICAST_LOOP, socket.IPV6_MULTICAST_LOOP)
        return bool(self._socket().getsockopt(level, name))

    @multicast_loopback.setter
    def multicast_loopback(self, value: bool) -> None:
        level, name = self._option(socket.IP_MULTICAST_LOOP, socket.IPV6_MULTICAST_LOOP)
        self._socket().setsockopt(level, name, int(value))

    @property
    def multicast_ttl(self) -> int:
        """::

            ttl = datagram.multicast_ttl
            datagram.multicast_ttl = 64

        Number of hops of multicast datagrams, with the ``IP_MULTICAST_TTL`` or
        ``IPV6_MULTICAST_HOPS`` socket option.
        """
        level, name = self._option(socket.IP_MULTICAST_TTL, socket.IPV6_MULTICAST_HOPS)
        return self._socket().getsockopt(level, name)

    @multicast_ttl.setter
    def multicast_ttl(self, value: int) -> None:
        level, name = self._option(socket.IP_MULTICAST_TTL, socket.IPV6_MULTICAST_HOPS)
        self._socket().setsockopt(level, name, value)

    @property
    def port(self) -> int | None:
        """::

            port = datagram.port

        Get port the socket is bound to, ``None`` for a UNIX domain socket or
        before it is bound.
        """
        if (handle := self._handle) is None or handle.family not in (socket.AF_INET, socket.AF_INET6):
            return None
        return handle.getsockname()[1]

    def connect_p(self, **options: Any) -> 'Pyjo.Promise.object':
        """::

            promise = datagram.connect_p(address='127.0.0.1', port=9999)

        Same as :meth:`connect`, but returns a :mod:`Pyjo.Promise` object,
        which is fulfilled with the socket once it is connected, and rejected
        with the error of the event ``error`` if it cannot be. The socket keeps
        what arrives for :meth:`recv_p` from then on, also the refusal of the
        peer, as a coroutine that awaits the promise goes on later. ::

            datagram = await Pyjo.IOLoop.Datagram.new().connect_p(address='127.0.0.1', port=9999)
            await datagram.send_p(b'Hello!')
        """

        def connected(*args: Any) -> Self:
            self._messages()
            return self

        promise = self.once_p('connect').then(connected)
        self.connect(**options)
        return promise

    def iterate(self) -> 'Pyjo.Iterator.object[tuple[bytes, Any]]':
        """::

            async for data, peer in datagram.iterate():
                ...

        The datagrams that arrive as a :mod:`Pyjo.Iterator`, with the address
        of their sender, until the socket is closed, which :meth:`recv_p`
        takes. ::

            # Echo server, one datagram after another
            async for data, peer in datagram:
                await datagram.send_p(b'Echo: ' + data, peer)

            # The datagrams of one peer, in a chain
            async for data, peer in datagram.iterate().grep(lambda message: message[1] == trusted):
                ...
        """
        import Pyjo.Iterator

        return Pyjo.Iterator.object(self._messages().iterate())

    def once_p(self, name: str) -> 'Pyjo.Promise.object':
        """::

            promise = datagram.once_p('close')

        Same as :meth:`~Pyjo.EventEmitter.Pyjo_EventEmitter.once_p` of
        :mod:`Pyjo.EventEmitter`, but fulfilled at once for the event
        ``close`` of a socket that is closed already, as it comes no more.
        """
        import Pyjo.Promise

        if name == 'close' and self._ended:
            return Pyjo.Promise.resolve()
        return super().once_p(name)

    def recv_p(self, timeout: float | None = None) -> 'Pyjo.Promise.object':
        """::

            promise = datagram.recv_p()
            promise = datagram.recv_p(timeout=5)

        Return a :mod:`Pyjo.Promise` object, which is fulfilled with the next
        datagram and the address of its sender, as the event ``message`` gives
        them, or ``None`` once the socket is closed, also when it is closed
        already, and rejected with the error of the event ``error``, after
        which the socket stays open and the next promise waits again, or a
        :class:`TimeoutError` when no datagram has arrived for ``timeout``
        seconds. The socket reads only while a promise waits, and the datagrams
        that arrive before wait in the socket, as the streams do. ::

            if (received := await datagram.recv_p()) is not None:
                data, peer = received
                print(f'{data!r} from {peer}')
        """
        pull = self._messages()
        promise = pull.next_p()
        if timeout is not None and promise in pull.waiting:
            reactor = self.reactor

            def expired(reactor: Any) -> None:
                pull.cancel(promise, TimeoutError('Receive timeout'))

            timer = reactor.timer(timeout, expired)

            def settled(*args: Any) -> None:
                reactor.remove(timer)

            promise.then(settled, settled)
        return promise

    def send(self, data: bytes, peer: Peer | None = None, cb: SendCallback | None = None) -> Self:
        """::

            datagram = datagram.send(b'Hello!')
            datagram = datagram.send(b'Hello!', ('127.0.0.1', 9999))
            datagram = datagram.send(b'Hello!', ('localhost', 9999), lambda datagram: ...)
            datagram = datagram.send(b'Hello!', '/tmp/myapp.sock')

        Enqueue a datagram to be sent as soon as possible, to the peer of
        :meth:`connect`, or to the address given to a socket that is not
        connected, whose name is resolved without blocking. The optional callback will be executed once the
        datagram has been sent.
        """
        return self._send(data, peer, cb)

    def send_p(self, data: bytes, peer: Peer | None = None) -> 'Pyjo.Promise.object':
        """::

            promise = datagram.send_p(b'Hello!')
            promise = datagram.send_p(b'Hello!', ('127.0.0.1', 9999))

        Same as :meth:`send`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled once the datagram has been sent, and rejected with the
        error of the datagram, in the place of the event ``error``, or if the
        socket is closed before, or is closed already. ::

            await datagram.send_p(b'Hello!', ('127.0.0.1', 9999))
        """
        import Pyjo.Exception
        import Pyjo.Promise

        if self._ended:
            return Pyjo.Promise.reject(Pyjo.Exception.new('Socket closed before the datagram has been sent'))
        promise = Pyjo.Promise.new()

        def closed(datagram: Any) -> None:
            promise.reject(Pyjo.Exception.new('Socket closed before the datagram has been sent'))

        wrapper = self.once('close', closed)

        def sent(datagram: Any) -> None:
            self.unsubscribe('close', wrapper)
            promise.resolve()

        def failed(err: Any) -> None:
            self.unsubscribe('close', wrapper)
            promise.reject(err)

        self._send(data, peer, sent, failed)
        return self._hold(promise)

    def start(self) -> None:
        """::

            datagram.start()

        Start or resume watching for new datagrams on the socket.
        """
        if (handle := self._handle) is None:
            return
        self._paused = False
        ref = weakref.ref(self)

        def cb(reactor: Any, writable: bool) -> None:
            if (datagram := ref()) is not None:
                datagram._flush() if writable else datagram._read_handle()

        reactor = self.reactor
        reactor.io(handle, cb)
        reactor.watch(handle, True, bool(self._queue))

    def stop(self) -> None:
        """::

            datagram.stop()

        Stop watching for new datagrams on the socket.
        """
        if self._handle is not None and not self._paused:
            self._paused = True
            self.reactor.watch(self._handle, False, bool(self._queue))

    @property
    def ttl(self) -> int:
        """::

            ttl = datagram.ttl
            datagram.ttl = 64

        Number of hops of unicast datagrams, with the ``IP_TTL`` or
        ``IPV6_UNICAST_HOPS`` socket option.
        """
        level, name = self._option(socket.IP_TTL, socket.IPV6_UNICAST_HOPS)
        return self._socket().getsockopt(level, name)

    @ttl.setter
    def ttl(self, value: int) -> None:
        level, name = self._option(socket.IP_TTL, socket.IPV6_UNICAST_HOPS)
        self._socket().setsockopt(level, name, value)

    def _cancel(self, resolver: Any) -> None:
        if resolver is None or isinstance(resolver, bool):
            return
        reactor = self._reactor() if self._reactor is not None else None
        if reactor is not None:
            reactor.remove(resolver.handle)
        resolver.close()

    # Closed by a callback or a subscriber, which the type checker does not see
    def _closed(self) -> bool:
        return self._handle is None

    def _connected(self, family: int, sockaddr: Any, err: str | None) -> None:
        # Closed in the meantime
        if self._connecting is None:
            return
        self._connecting = None
        if err is not None:
            self.emit('error', err)
            return
        try:
            if self._handle is None:
                self._handle = socket.socket(family, socket.SOCK_DGRAM)
                self._handle.setblocking(False)
            self._handle.connect(sockaddr)
        except OSError as e:
            self.emit('error', e)
            return
        self.start()
        self.emit('connect')._flush()

    # The error of a datagram, which its promise gets, or the event error
    def _failed(self, d: '_Datagram', err: Any) -> None:
        if d.failed is not None:
            d.failed(err)
        else:
            self.emit('error', err)

    def _flush(self) -> None:
        queue = self._queue
        while queue:
            d = queue[0]

            # The name of the peer is being resolved, or the socket is being connected
            if d.resolver is not None or self._connecting is not None:
                return

            if d.error is not None:
                queue.popleft()
                self._failed(d, d.error)
                continue

            # A socket that is not bound yet is bound to a random port
            if (handle := self._handle) is None:
                handle = self._handle = socket.socket(d.family or socket.AF_INET, socket.SOCK_DGRAM)
                handle.setblocking(False)
                self.start()

            # An address of another family than the socket, which the socket cannot send to
            if d.family and d.family != handle.family:
                queue.popleft()
                self._failed(d, OSError(errno.EAFNOSUPPORT, f'Address {d.sockaddr} is not of the family of the socket'))
                continue

            try:
                if d.sockaddr is None:
                    handle.send(d.data)
                else:
                    handle.sendto(d.data, d.sockaddr)
            except (BlockingIOError, InterruptedError):
                self._watch()
                return
            except OSError as e:
                queue.popleft()
                self._failed(d, _refused(e))
                if self._closed():
                    return
                continue

            queue.popleft()
            if d.cb is not None:
                d.cb(self)
            if self._closed():
                return

        self._watch()
        if self._graceful:
            self.close()

    # The pull of the datagrams, whose errors leave the socket open, and which a socket that is closed already has ended
    def _messages(self) -> Any:
        pull = self._pull('message', True, value=False, fatal=False)
        if self._ended:
            pull.end()
        return pull

    def _membership(self, group: str, interface: str | int | None, add: bool) -> None:
        handle = self._socket()
        if ':' in group:
            index = socket.if_nametoindex(interface) if isinstance(interface, str) else interface or 0
            mreq = socket.inet_pton(socket.AF_INET6, group) + struct.pack('@I', index)
            name = socket.IPV6_JOIN_GROUP if add else socket.IPV6_LEAVE_GROUP
            handle.setsockopt(socket.IPPROTO_IPV6, name, mreq)
        else:
            mreq = socket.inet_aton(group) + socket.inet_aton(str(interface or '0.0.0.0'))
            name = socket.IP_ADD_MEMBERSHIP if add else socket.IP_DROP_MEMBERSHIP
            handle.setsockopt(socket.IPPROTO_IP, name, mreq)

    def _option(self, ipv4: int, ipv6: int) -> tuple[int, int]:
        if self._socket().family == socket.AF_INET6:
            return socket.IPPROTO_IPV6, ipv6
        return socket.IPPROTO_IP, ipv4

    def _read_handle(self) -> None:
        if (handle := self._handle) is None:
            return
        try:
            data, peer = handle.recvfrom(_SIZE)
        except (BlockingIOError, InterruptedError):
            return
        except OSError as e:
            self.emit('error', _refused(e))
            return
        self.emit('message', data, peer)

    # The address of a peer, at once for a path or a numeric address, else resolved without blocking unless that is
    # turned off; done gets the family, the address and an error, and the result is what is still being resolved
    def _resolve(
        self,
        host: str,
        port: int,
        done: Callable[[int, Any, str | None], None],
        *,
        defer: bool = False,
        sockaddr: Any = None,
        unix: bool = False,
    ) -> Any:
        reactor = self.reactor
        family = self._handle.family if self._handle is not None else 0

        def finish(family: int, address: Any, err: str | None) -> Any:
            if not defer:
                done(family, address, err)
                return None
            reactor.next_tick(lambda reactor: done(family, address, err))
            return True

        # UNIX domain socket, which Python has not on Windows
        if unix:
            if sys.platform == 'win32':
                return finish(family, host, _NO_UNIX)
            return finish(socket.AF_UNIX, host, None)

        # Numeric address, kept as it is with the flow information and the scope of IPv6
        try:
            info = socket.getaddrinfo(host, port, family, socket.SOCK_DGRAM, 0, socket.AI_NUMERICHOST)[0]
            address = tuple(sockaddr) if sockaddr is not None and len(sockaddr) == 4 else info[4]
            return finish(info[0], address, None)
        except OSError:
            pass

        # Blocking name resolution
        if not Pyjo.IOLoop.Client.NNR:
            try:
                infos = socket.getaddrinfo(host, port, family, socket.SOCK_DGRAM)
            except OSError as e:
                return finish(0, None, f"Can't resolve: {e.strerror or e}")
            return finish(*self._pick(infos))

        # Non-blocking name resolution
        dns = Pyjo.IOLoop.Client._Resolver(host, port, socket.SOCK_DGRAM, family)  # pyright: ignore[reportPrivateUsage]

        ref = weakref.ref(self)

        def resolved(reactor: Any, writable: bool) -> None:
            reactor.remove(dns.handle)
            try:
                infos = dns.future.result()
            except OSError as e:
                return done(0, None, f"Can't resolve: {e.strerror or e}")
            finally:
                dns.close()
            if (datagram := ref()) is not None:
                done(*datagram._pick(infos))

        reactor.io(dns.handle, resolved).watch(dns.handle, True, False)
        return dns

    # The first address of a name, or the first of the family of the socket, which may have been made in the meantime
    def _pick(self, infos: list[Any]) -> tuple[int, Any, str | None]:
        if self._handle is None:
            return infos[0][0], infos[0][4], None
        for info in infos:
            if info[0] == self._handle.family:
                return info[0], info[4], None
        return 0, None, "Can't resolve: no address of the family of the socket"

    def _send(
        self, data: bytes, peer: Peer | None, cb: SendCallback | None, failed: Callable[[Any], Anything] | None = None
    ) -> Self:
        d = _Datagram(data, cb, failed)
        self._queue.append(d)

        if peer is not None:
            ref = weakref.ref(self)

            def resolved(family: int, sockaddr: Any, err: str | None) -> None:
                d.resolver, d.family, d.sockaddr, d.error = None, family, sockaddr, err
                if (datagram := ref()) is not None:
                    datagram._flush()

            if isinstance(peer, str):
                d.resolver = self._resolve(peer, 0, resolved, unix=True)
            else:
                d.resolver = self._resolve(str(peer[0]), int(peer[1]), resolved, sockaddr=peer)

        self._flush()
        return self

    def _socket(self) -> socket.socket:
        if (handle := self._handle) is None:
            raise OSError(errno.EBADF, 'Datagram socket is not bound')
        return handle

    def _watch(self) -> None:
        if self._handle is not None:
            self.reactor.watch(self._handle, not self._paused, bool(self._queue))


# The datagram sockets that exist, closed at the end of the interpreter, as Perl closes the handles that are left in its
# global destruction and Python warns that they were not closed
_DATAGRAMS: 'weakref.WeakSet[Pyjo_IOLoop_Datagram]' = weakref.WeakSet()


@atexit.register
def _cleanup() -> None:
    for datagram in list(_DATAGRAMS):
        try:
            datagram.close()
        except Exception:
            pass


def _error(e: OSError, message: str) -> OSError:
    error = type(e)(f'{message}: {e.strerror}' if e.strerror else message)
    error.errno = e.errno
    return error


# Windows reports a datagram that a port refused as a reset of the connection (WSAECONNRESET), where other systems
# report it as refused
def _refused(e: OSError) -> OSError:
    if sys.platform == 'win32' and e.winerror == 10054:
        return ConnectionRefusedError(errno.ECONNREFUSED, 'Connection refused')
    return e


new = Pyjo_IOLoop_Datagram.new
object = Pyjo_IOLoop_Datagram
Datagram = Pyjo_IOLoop_Datagram
