"""
Pyjo.Server.Daemon - Non-blocking I/O HTTP and WebSocket server
===============================================================
::

    from Pyjo.Server.Daemon import Daemon

    daemon = Daemon(listen=['http://*:8080'])


    @daemon.unsubscribe('request').on('request')
    def request(daemon, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()


    daemon.run()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Server.Daemon

    daemon = Pyjo.Server.Daemon.new(listen=['http://*:8080'])


    @daemon.unsubscribe('request').on('request')
    def request(daemon, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()


    daemon.run()

:mod:`Pyjo.Server.Daemon` is a full featured, highly portable non-blocking
I/O HTTP and WebSocket server, with IPv6, TLS, SNI, Comet (long polling),
keep-alive and multiple event loop support. It also speaks FastCGI to a web
server in front of it, on the listen locations ``fcgi://`` and
``fcgi+unix://``, with :mod:`Pyjo.Server.FastCGI`.

TLS support comes from :mod:`ssl` of the standard library, and can be
disabled with the ``PYJO_NO_TLS`` environment variable, as name resolution
and SOCKS5 support of :mod:`Pyjo.IOLoop` with ``PYJO_NO_NNR`` and
``PYJO_NO_SOCKS``.

A daemon is also a context manager, which stops listening and closes its
connections at its end.

The end of a ``with`` block stops the daemon and closes its sockets.

Signals
-------

The :mod:`Pyjo.Server.Daemon` process can be controlled at runtime with the
following signals.

INT, TERM
~~~~~~~~~

Shut down server gracefully: close the listen sockets, so that a new
connection is refused, and wait for the accepted ones to be closed, after
:attr:`~Pyjo_Server_Daemon.shutdown_delay`, while it serves as before. A
second ``INT``, as of Ctrl-C pressed twice, shuts it down immediately, also
during the delay, a second ``TERM`` does nothing.

QUIT
~~~~

Shut down server immediately. On Windows, which has no ``QUIT``, ``BREAK``
does it, as of Ctrl-Break.

HUP
~~~

Ignored, as there is nothing to reload. Windows has no ``HUP``.

Events
------

:mod:`Pyjo.Server.Daemon` inherits all events from :mod:`Pyjo.Server`.

Debugging
---------

You can set the ``PYJO_SERVER_DEBUG`` environment variable to get some
advanced diagnostics information printed to :data:`sys.stderr`. ::

    PYJO_SERVER_DEBUG=1

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Server::Daemon <https://github.com/mojolicious/mojo/blob/v9.54/lib/Mojo/Server/Daemon.pm>`_
of Mojolicious 9.54.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.IOLoop.Stream
import Pyjo.IOLoop.TLS
import Pyjo.Reactor
import Pyjo.Server
import Pyjo.Server.FastCGI
import Pyjo.Transaction
import Pyjo.Transaction.HTTP
import Pyjo.Transaction.WebSocket
import Pyjo.URL

from Pyjo.String.Unicode import split
from Pyjo.Util import term_escape, warn
from Pyjo.WebSocket import server_handshake

import atexit
import contextlib
import os
import re
import signal
import socket
import ssl
import sys
import threading
import weakref

from collections.abc import Callable, Sequence
from types import TracebackType
from typing import Any, Self


# A location to listen on, which Pyjo.URL parses
type Location = str | Pyjo.URL.object


DEBUG = bool(os.environ.get('PYJO_SERVER_DEBUG'))

# The protocol versions of IO::Socket::SSL's SSL_version
VERSIONS = {
    'TLSv1': ssl.TLSVersion.TLSv1,
    'TLSv1_1': ssl.TLSVersion.TLSv1_1,
    'TLSv1_2': ssl.TLSVersion.TLSv1_2,
    'TLSv1_3': ssl.TLSVersion.TLSv1_3,
}


class Pyjo_Server_Daemon(Pyjo.Server.object):
    """
    :mod:`Pyjo.Server.Daemon` inherits all methods from :mod:`Pyjo.Server`
    and implements the following new ones.
    """

    def __init__(
        self,
        *,
        acceptors: list[str] | None = None,
        backlog: int | None = None,
        inactivity_timeout: float | None = None,
        ioloop: Pyjo.IOLoop.object | None = None,
        keep_alive_timeout: float | None = None,
        lingering_timeout: float = 5,
        listen: Sequence[Location] | None = None,
        max_clients: int | None = None,
        max_requests: int = 100,
        shutdown_delay: float = 0,
        silent: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            daemon = Pyjo.Server.Daemon.new()
            daemon = Pyjo.Server.Daemon.new(listen=['http://*:8080'], silent=True)

        Construct a new :mod:`Pyjo.Server.Daemon` object.
        """
        super().__init__(**kwargs)

        self.acceptors: list[str] = acceptors if acceptors is not None else []
        """::

            acceptors = daemon.acceptors
            daemon.acceptors = ['6be0c140ef00a389c5d039536b56d139']

        Active acceptor ids. ::

            # Check port
            port = daemon.ioloop.acceptor(daemon.acceptors[0]).port
        """

        self.backlog = backlog
        """::

            backlog = daemon.backlog
            daemon.backlog = 128

        Listen backlog size, defaults to :data:`socket.SOMAXCONN`.
        """

        self._inactivity_timeout: float | None = inactivity_timeout

        self.ioloop: Pyjo.IOLoop.object = ioloop if ioloop is not None else Pyjo.IOLoop.object.singleton()
        """::

            loop = daemon.ioloop
            daemon.ioloop = Pyjo.IOLoop.new()

        Event loop object to use for I/O operations, defaults to the global
        :mod:`Pyjo.IOLoop` singleton.
        """

        self._keep_alive_timeout: float | None = keep_alive_timeout
        self._locations: list[Location] | None = list(listen) if listen is not None else None

        # Not in Mojolicious: the rest of a request that has its response already, as one over a limit, is read before the
        # connection is closed, as a close with unread data resets it, which loses the response on Windows
        self.lingering_timeout = lingering_timeout
        """::

            timeout = daemon.lingering_timeout
            daemon.lingering_timeout = 10

        Maximum amount of time in seconds a connection whose request has not
        been read to its end, as one that exceeds a limit, is kept open after its
        response, to read and discard the rest of the request, so that the
        client receives the response before the connection is closed, defaults
        to ``5``.
        """

        self.max_clients = max_clients
        """::

            max = daemon.max_clients
            daemon.max_clients = 100

        Maximum number of accepted connections this server is allowed to
        handle concurrently, before stopping to accept new incoming
        connections, passed along to :attr:`Pyjo.IOLoop.Pyjo_IOLoop.max_connections`.
        """

        self.max_requests = max_requests
        """::

            max = daemon.max_requests
            daemon.max_requests = 250

        Maximum number of keep-alive requests per connection, defaults to
        ``100``.
        """

        # Not in Mojolicious: the time that a load balancer, which checks the readiness of the server, needs to send no
        # more connections to it
        self.shutdown_delay = shutdown_delay
        """::

            delay = daemon.shutdown_delay
            daemon.shutdown_delay = 5

        Amount of time in seconds the server keeps accepting and serving
        connections after ``INT`` or ``TERM``, before it closes the listen
        sockets and shuts down gracefully, while
        :attr:`Pyjo.IOLoop.Pyjo_IOLoop.is_stopping` is true already, so that
        the readiness of :mod:`Pyjoyment.Plugin.Health` fails and a load
        balancer sends the connections to another instance, defaults to
        ``0``.
        """

        self.silent = silent
        """::

            boolean = daemon.silent
            daemon.silent = boolean

        Disable console messages.
        """

        self._connections: dict[str, dict[str, Any]] = {}
        self._servers: dict[str, Any] = {}
        _DAEMONS.add(self)

    @property
    def inactivity_timeout(self) -> float:
        """::

            timeout = daemon.inactivity_timeout
            daemon.inactivity_timeout = 5

        Maximum amount of time in seconds a connection with an active request
        can be inactive before getting closed, defaults to the value of the
        ``PYJO_INACTIVITY_TIMEOUT`` environment variable or ``30``. Setting
        the value to ``0`` will allow connections to be inactive
        indefinitely.
        """
        if self._inactivity_timeout is None:
            self._inactivity_timeout = _number(os.environ.get('PYJO_INACTIVITY_TIMEOUT'), 30)
        return self._inactivity_timeout

    @inactivity_timeout.setter
    def inactivity_timeout(self, value: float) -> None:
        self._inactivity_timeout = value

    @property
    def keep_alive_timeout(self) -> float:
        """::

            timeout = daemon.keep_alive_timeout
            daemon.keep_alive_timeout = 10

        Maximum amount of time in seconds a connection without an active
        request can be inactive before getting closed, defaults to the value
        of the ``PYJO_KEEP_ALIVE_TIMEOUT`` environment variable or ``5``.
        Setting the value to ``0`` will allow connections to be inactive
        indefinitely.
        """
        if self._keep_alive_timeout is None:
            self._keep_alive_timeout = _number(os.environ.get('PYJO_KEEP_ALIVE_TIMEOUT'), 5)
        return self._keep_alive_timeout

    @keep_alive_timeout.setter
    def keep_alive_timeout(self, value: float) -> None:
        self._keep_alive_timeout = value

    @property
    def listen(self) -> list[Location]:
        """::

            listen = daemon.listen
            daemon.listen = ['https://127.0.0.1:8080']

        List of one or more locations to listen on, as strings or
        :mod:`Pyjo.URL` objects, defaults to the value of the ``PYJO_LISTEN``
        environment variable, to ``http://*:`` with the port of the ``PORT``
        environment variable, which platforms as Knative, Cloud Run and Heroku
        set, or to ``http://*:3000`` (shortcut for ``http://0.0.0.0:3000``). ::

            # Listen on all IPv4 interfaces
            daemon.listen = ['http://*:3000']

            # Listen on all IPv4 and IPv6 interfaces
            daemon.listen = ['http://[::]:3000']

            # Listen on IPv6 interface
            daemon.listen = ['http://[::1]:4000']

            # Listen on IPv4 and IPv6 interfaces
            daemon.listen = ['http://127.0.0.1:3000', 'http://[::1]:3000']

            # Listen on UNIX domain socket "/tmp/myapp.sock" (percent encoded slash)
            daemon.listen = ['http+unix://%2Ftmp%2Fmyapp.sock']

            # FastCGI for a web server in front of the application
            daemon.listen = ['fcgi://127.0.0.1:9000']

            # FastCGI on UNIX domain socket "/tmp/myapp.sock"
            daemon.listen = ['fcgi+unix://%2Ftmp%2Fmyapp.sock']

            # File descriptor, as used by systemd
            daemon.listen = ['http://127.0.0.1?fd=3']

            # Allow multiple servers to use the same port (SO_REUSEPORT)
            daemon.listen = ['http://*:8080?reuse=1']

            # Listen on two ports with HTTP and HTTPS at the same time
            daemon.listen = ['http://*:3000', 'https://*:4000']

            # Location of a URL object
            daemon.listen = [Pyjo.URL.new().set(scheme='http', host='127.0.0.1', port=3000)]

            # Use a custom certificate and key
            daemon.listen = ['https://*:3000?cert=/x/server.crt&key=/y/server.key']

            # Domain specific certificates and keys (SNI)
            daemon.listen = ['https://*:3000?example.com_cert=/x/my.crt&example.com_key=/y/my.key']

            # Or even a custom certificate authority
            daemon.listen = ['https://*:3000?cert=/x/server.crt&key=/y/server.key&ca=/z/ca.crt']

        These parameters are currently available:

        ca
            ::

                ca=/etc/tls/ca.crt

            Path to TLS certificate authority file used to verify the peer
            certificate.

        cert
            ::

                cert=/etc/tls/server.crt
                mojolicious.org_cert=/etc/tls/mojo.crt

            Path to the TLS cert file, defaults to a built-in test
            certificate.

        ciphers
            ::

                ciphers=AES128-GCM-SHA256:RC4:HIGH:!MD5:!aNULL:!EDH

            TLS cipher specification string. For more information about the
            format see
            https://www.openssl.org/docs/manmaster/man1/ciphers.html#CIPHER-STRINGS.

        fd
            ::

                fd=3

            File descriptor with an already prepared listen socket.

        key
            ::

                key=/etc/tls/server.key
                mojolicious.org_key=/etc/tls/mojo.key

            Path to the TLS key file, defaults to a built-in test key.

        reuse
            ::

                reuse=1

            Allow multiple servers to use the same port with the
            ``SO_REUSEPORT`` socket option.

        single_accept
            ::

                single_accept=1

            Only accept one connection at a time.

        verify
            ::

                verify=0x00

            TLS verification mode: ``0x00`` verifies no peer, ``0x01``
            verifies a peer certificate if there is one, and ``0x03`` requires
            it.

        version
            ::

                version=TLSv1_2

            TLS protocol version.
        """
        if self._locations is None:
            # Not in Mojolicious: the port of PORT, which the platform that runs the server tells it to listen on
            port = os.environ.get('PORT') or ''
            default = f'http://*:{port}' if re.fullmatch(r'\d+', port) else 'http://*:3000'
            self._locations = [location or '' for location in split(',', os.environ.get('PYJO_LISTEN') or default)]
        return self._locations

    @listen.setter
    def listen(self, value: Sequence[Location]) -> None:
        self._locations = list(value)

    def __del__(self) -> None:
        try:
            if sys.is_finalizing():
                return
            # Not in Mojolicious: the reactor that the daemon has, without making one
            reactor = getattr(getattr(self, 'ioloop', None), '_reactor', None)
            Pyjo.Reactor._finalize(self._cleanup, reactor)  # pyright: ignore[reportPrivateUsage]
        except Exception:
            pass

    # Not in Mojolicious: a context manager, which does what DESTROY does, as PyPy frees the daemon only when its
    # garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    # Not in Mojolicious: the release of the listen sockets and the connections, which Perl does in DESTROY, also at the
    # end of a with block
    def close(self) -> None:
        """::

            daemon.close()

        Close the listen sockets and the connections of the server, as the end
        of a ``with`` block does.
        """
        self._cleanup()

    def ports(self) -> list[int]:
        """::

            ports = daemon.ports()

        Get all ports this server is currently listening on. ::

            # All ports
            for port in daemon.ports():
                print(port)
        """
        return [self.ioloop.acceptor(id).port for id in self.acceptors]

    def run(self) -> None:
        """::

            daemon.run()

        Run server and wait for the signals ``INT``, ``TERM`` and ``QUIT``.
        """
        # Make sure the event loop can be stopped in regular intervals
        loop = self.ioloop
        interval = loop.recurring(1, lambda loop: None)
        graceful = immediate = False

        # Unlike Mojolicious: INT and TERM stop the event loop gracefully, as Docker and Kubernetes stop the server with
        # TERM, and QUIT immediately, where Mojo stops it immediately on INT and TERM; a second INT, as of Ctrl-C pressed
        # twice, stops it immediately, and the graceful stop is left to the next tick, as a handler of Python runs in the
        # middle of what the event loop does
        def stop(signum: int, frame: Any) -> None:
            nonlocal graceful, immediate
            if signum == _QUIT or (signum == signal.SIGINT and graceful):
                immediate = True
                loop.stop()
            elif not graceful:
                graceful = True
                loop.next_tick(lambda loop: loop.stop_gracefully(self.shutdown_delay))

        # Not in Mojolicious: the graceful stop, after its delay, closes the listen sockets, and a connection that is
        # kept alive after its next response, as a worker of Mojo::Server::Prefork does, so that a client that keeps
        # requesting does not keep the server from stopping; local $self->{max_requests}, the value is set back at the end
        max_requests = self.max_requests

        def finish(loop: Any) -> None:
            self._close_listen()
            self.max_requests = 1

        finished = loop.once('finish', finish)

        # Not in Mojolicious: a thread other than the main one cannot handle signals, and HUP is ignored, as there is
        # nothing to reload
        handlers: dict[signal.Signals, Any] = {}
        waker = wakee = None
        wakeup = -1
        if threading.current_thread() is threading.main_thread():
            for name in (signal.SIGINT, signal.SIGTERM, _QUIT):
                handlers[name] = signal.signal(name, stop)
            if sys.platform != 'win32':
                handlers[signal.SIGHUP] = signal.signal(signal.SIGHUP, signal.SIG_IGN)

            # Not in Mojolicious: a socket pair that Python writes to on a signal wakes the event loop up, as Python
            # repeats a system call that a signal interrupts until its timeout, so that a stop does not wait for the
            # interval, as the workers of Pyjo.Server.Prefork are woken up
            waker, wakee = socket.socketpair()
            waker.setblocking(False)
            wakee.setblocking(False)
            wakeup = signal.set_wakeup_fd(waker.fileno())

            def wake(reactor: Any, writable: bool) -> None:
                try:
                    wakee.recv(4096)
                except OSError:
                    pass

            loop.reactor.io(wakee, wake).watch(wakee, True, False)
        try:
            self.start().ioloop.start()

            # Not in Mojolicious: the end of the server, unless it has stopped immediately, whose cleanup a signal that
            # stops it immediately interrupts
            if not immediate:
                self._server_stopped()
        finally:
            if waker is not None and wakee is not None:
                signal.set_wakeup_fd(wakeup)
                loop.reactor.remove(wakee)
                waker.close()
                wakee.close()
            for name, handler in handlers.items():
                signal.signal(name, handler)
            loop.remove(interval)
            loop.unsubscribe('finish', finished)
            self.max_requests = max_requests

    # Not in Mojolicious: the cleanup of the application runs the event loop of its promise, which a signal that stops
    # the server immediately stops, as it is the one of the server
    def _server_stopped(self) -> None:
        import Pyjo.Promise

        if not isinstance(promise := self.app.server_stopped(self), Pyjo.Promise.object):
            return
        loop = promise.ioloop
        done: list[bool] = []

        def finish(*args: Any) -> None:
            done.append(True)
            loop.stop()

        promise.then(finish, finish)
        if not done:
            loop.start()

    def start(self) -> Self:
        """::

            daemon = daemon.start()

        Start or resume accepting connections through :attr:`ioloop`. ::

            # Listen on random port
            daemon.listen = ['http://127.0.0.1']
            port = daemon.start().ports()[0]

            # Run multiple web servers concurrently
            daemon1 = Pyjo.Server.Daemon.new(listen=['http://*:3000']).start()
            daemon2 = Pyjo.Server.Daemon.new(listen=['http://*:4000']).start()
            if not Pyjo.IOLoop.is_running():
                Pyjo.IOLoop.start()
        """
        loop = self.ioloop
        if max := self.max_clients:
            loop.max_connections = max

        # Resume accepting connections
        if servers := self._servers:
            for id in list(servers):
                self.acceptors.append(loop.acceptor(servers.pop(id)))

        # Start listening
        elif not len(self.acceptors):
            self.app.server(self)
            for listen in self.listen:
                self._listen(listen)

        return self

    def stop(self) -> Self:
        """::

            daemon = daemon.stop()

        Stop accepting connections through :attr:`ioloop`.
        """
        # Suspend accepting connections but keep listen sockets open
        loop = self.ioloop
        while len(self.acceptors):
            id = self.acceptors.pop(0)
            self._servers[id] = loop.acceptor(id)
            loop.remove(id, close=False)

        return self

    def _build_tx(self, id: str, c: dict[str, Any]) -> Pyjo.Transaction.HTTP.object:
        tx = self.build_tx()
        tx.connection = id
        # Unlike Mojolicious: Pyjoyment names itself
        tx.res.headers.server = 'Pyjoyment (Python)'
        stream = self.ioloop.stream(id)
        stream.timeout = self.inactivity_timeout
        handle = stream.handle
        if handle.family != getattr(socket, 'AF_UNIX', None):
            if (addr := c.get('addr')) is None:
                addr = c['addr'] = (*_address(handle.getsockname), *_address(handle.getpeername))
            tx.local_address, tx.local_port, tx.remote_address, tx.remote_port = addr
        if c.get('tls'):
            tx.req.url.base.scheme = 'https'

        ref = weakref.ref(self)

        @tx.on('request')
        def request(tx: Pyjo.Transaction.HTTP.object) -> None:
            if (this := ref()) is None:
                return
            req = tx.req
            if error := req.error:
                this._trace(id, error['message'])

            # WebSocket
            if req.is_handshake:
                ws = this._connections[id]['next'] = Pyjo.Transaction.WebSocket.new(handshake=tx)
                this.emit('request', server_handshake(ws))

            # HTTP
            else:
                this.emit('request', tx)

            # Last keep-alive request or corrupted connection
            c = this._connections.get(id, {})
            if (c.get('requests') or 1) >= this.max_requests or req.error:
                tx.res.headers.connection = 'close'

            def resume(tx: Pyjo.Transaction.HTTP.object) -> None:
                _call(ref, '_write', id)

            tx.on('resume', resume)
            this._write(id)

        # Kept alive if we have more than one request on the connection
        c['requests'] = c.get('requests', 0) + 1
        if c['requests'] > 1:
            tx.kept_alive = True
        return tx

    def _cleanup(self) -> None:
        for id in list(self._connections):
            self._remove(id)
        loop = self.ioloop
        for id in self.acceptors:
            loop.remove(id)
        self.acceptors = []
        # Not in Mojolicious: the listen sockets of a stopped daemon, which Perl closes as it frees them
        for server in self._servers.values():
            server.close()
        self._servers = {}

    # Unlike Mojolicious: the listen sockets are closed when the server starts to stop gracefully, after its delay, so
    # that a new connection is refused at once, where Mojo only stops accepting connections and keeps the sockets until it
    # ends, so that a new connection waits in the backlog of the socket, without a response, until the server ends and
    # resets it
    def _close_listen(self) -> None:
        loop = self.ioloop
        for id in self.acceptors:
            if (acceptor := loop.acceptor(id)) is not None:
                acceptor.close()
        for server in self._servers.values():
            server.close()

    def _close(self, id: str) -> None:
        if (fcgi := self._connections.get(id, {}).get('fcgi')) is not None:
            fcgi.closed()
        if (tx := self._connections.get(id, {}).get('tx')) is not None:
            tx.closed()
        # Not in Mojolicious: the WebSocket of a handshake whose response has not been written, which Mojo drops without
        # its event finish, so that what the response waits for, as the websocket.accept of an ASGI application, ends
        if (ws := self._connections.get(id, {}).get('next')) is not None:
            ws.closed()
        self._connections.pop(id, None)

    def _finish(self, id: str) -> None:
        # Always remove connection for WebSockets
        c = self._connections.get(id)
        if c is None or (tx := c.get('tx')) is None:
            return
        if tx.is_websocket:
            return self._remove(id)

        # Finish transaction
        c.pop('tx').closed()

        # Upgrade connection to WebSocket
        if (ws := c.pop('next', None)) is not None:
            # Successful upgrade
            if ws.handshake.res.code == 101:
                ws.established = True
                c['tx'] = ws
                ref = weakref.ref(self)

                def resume(ws: Pyjo.Transaction.WebSocket.object) -> None:
                    _call(ref, '_write', id)

                ws.on('resume', resume)
                self._write(id)
                return ws.server_read(tx.req.content.leftovers())

            # Failed upgrade
            else:
                ws.closed()

        # Close connection if necessary
        if tx.error or not tx.keep_alive:
            if (req := tx.req).error or not req.is_finished:
                return self._linger(id)
            return self._remove(id)

        # Build new transaction for leftovers
        if len(leftovers := tx.req.content.leftovers()):
            tx = c['tx'] = self._build_tx(id, c)
            tx.server_read(leftovers)

        # Keep-alive connection
        if c.get('tx') is None:
            self.ioloop.stream(id).timeout = self.keep_alive_timeout

    # Not in Mojolicious: the end of the response, with the rest of the request read and discarded until the client closes
    # the connection or the lingering timeout, as a close with unread data resets the connection, which loses the response
    # on Windows, as it does on other systems where the reset comes before the client has read it
    def _linger(self, id: str) -> None:
        stream = self.ioloop.stream(id)
        self._close(id)
        if stream is None:
            return
        stream.unsubscribe('read')

        # The end of the response, which a TLS connection cannot send without its own close
        if not isinstance(handle := stream.handle, ssl.SSLSocket):
            with contextlib.suppress(OSError):
                handle.shutdown(socket.SHUT_WR)
        self.ioloop.timer(self.lingering_timeout, lambda loop: loop.remove(id))

    def _listen(self, listen: Location) -> None:
        # A Pyjo.URL stringifies, as a Mojo::URL does for Mojo::URL->new
        url = Pyjo.URL.new(str(listen))
        proto = url.protocol
        # Not in Mojolicious: FastCGI, with Pyjo.Server.FastCGI
        if proto not in ('http', 'https', 'http+unix', 'fcgi', 'fcgi+unix'):
            raise Pyjo.Exception.new(f'Invalid listen location "{listen}"')
        fcgi = proto.startswith('fcgi')

        query = url.query
        options: dict[str, Any] = {'backlog': self.backlog}
        if (fd := query.param('fd')) is not None:
            options['fd'] = int(fd)
        for name in ('single_accept', 'reuse'):
            options[name] = (value := query.param(name)) is not None and value not in ('', '0')
        if proto in ('http+unix', 'fcgi+unix'):
            options['path'] = url.host
        else:
            if (host := url.host) != '*':
                options['address'] = host
            if port := url.port:
                options['port'] = port

        options['tls_ca'] = query.param('ca')
        for name in query.names():
            if m := re.fullmatch(r'(.*)_(cert|key)', name):
                options.setdefault(f'tls_{m[2]}', {})[m[1]] = query.param(name)
        if cert := query.param('cert'):
            options.setdefault('tls_cert', {})[''] = cert
        if key := query.param('key'):
            options.setdefault('tls_key', {})[''] = key
        tls = options['tls'] = proto == 'https'

        # Unlike Mojolicious: the options of IO::Socket::SSL change the context that the other options make
        ciphers, verify, version = query.param('ciphers'), query.param('verify'), query.param('version')
        if tls and (ciphers is not None or verify is not None or version is not None):
            context = Pyjo.IOLoop.TLS.context(server=True, **options)
            if ciphers is not None:
                context.set_ciphers(ciphers)
            if verify is not None:
                mode = int(verify, 16)
                context.verify_mode = (
                    ssl.CERT_NONE if not mode & 1 else ssl.CERT_REQUIRED if mode & 2 else ssl.CERT_OPTIONAL
                )
            if version is not None and (tls_version := VERSIONS.get(version)) is not None:
                context.minimum_version = context.maximum_version = tls_version
            options['tls_context'] = context

        ref = weakref.ref(self)

        def server(loop: Pyjo.IOLoop.object, stream: Pyjo.IOLoop.Stream.object, id: str) -> None:
            if (this := ref()) is None:
                return
            this._connections[id] = {'tls': tls}
            # Not in Mojolicious: FastCGI, whose records Pyjo.Server.FastCGI reads and writes
            if fcgi:
                this._connections[id]['fcgi'] = Pyjo.Server.FastCGI.new(this, id)
            if DEBUG:
                warn(f'-- Accept {id} ({_peer(stream.handle)})\n')
            stream.timeout = this.inactivity_timeout

            def close(stream: Pyjo.IOLoop.Stream.object) -> None:
                _call(ref, '_close', id)

            def error(stream: Pyjo.IOLoop.Stream.object, err: Any) -> None:
                _call(ref, '_error', id, err)

            def read(stream: Pyjo.IOLoop.Stream.object, chunk: bytes) -> None:
                _call(ref, '_read', id, chunk)

            def timeout(stream: Pyjo.IOLoop.Stream.object) -> None:
                _call(ref, '_trace', id, 'Inactivity timeout (see FAQ for more)')

            stream.on('close', close)
            stream.on('error', error)
            stream.on('read', read)
            stream.on('timeout', timeout)

        self.acceptors.append(self.ioloop.server(server, **options))

        if self.silent:
            return
        self.app.log.info(f'Listening at "{url}"')
        query.pairs = []
        if url.host == '*':
            url.host = '127.0.0.1'
        if not options.get('path') and not url.port:
            url.port = self.ports()[-1]
        # Not in Mojolicious: the message is flushed, as a pipe, as of a log or of a container, would keep it until the
        # server ends, and lose it when the server is killed
        print(f'Web application available at {options.get("path") or url}', flush=True)

    def _error(self, id: str, err: Any) -> None:
        self.app.log.error(str(err))
        self._close(id)

    def _read(self, id: str, chunk: bytes) -> None:
        # Unlike Mojolicious: the data of a connection that the daemon has removed, whose stream reads on while it closes
        # gracefully, is discarded, where Mojo makes the connection again and builds a transaction of it
        if (c := self._connections.get(id)) is None:
            return

        # Make sure we have a transaction
        if (fcgi := c.get('fcgi')) is not None:
            return fcgi.read(chunk)
        if (tx := c.get('tx')) is None:
            tx = c['tx'] = self._build_tx(id, c)
        if DEBUG:
            warn(term_escape(f'-- Server <<< Client ({_url(tx)})\n{chunk.decode("latin-1")}\n'))
        tx.server_read(chunk)

    def _remove(self, id: str) -> None:
        self.ioloop.remove(id)
        self._close(id)

    def _trace(self, id: str, message: str) -> None:
        if self._connections.get(id, {}).get('tx') is not None:
            self.app.log.trace(message)

    def _write(self, id: str) -> None:
        # Protect from resume event recursion
        c = self._connections.get(id)
        if c is None or (tx := c.get('tx')) is None or c.get('writing'):
            return
        writing = c.get('writing')
        c['writing'] = True
        try:
            chunk = tx.server_write()
        finally:
            c['writing'] = writing
        if DEBUG:
            warn(term_escape(f'-- Server >>> Client ({_url(tx)})\n{chunk.decode("latin-1")}\n'))
        next = '_finish' if tx.is_finished else '_write' if len(chunk) else None
        # Unlike Mojolicious: the stream that a callback of the event drain of the content, which server_write emits,
        # has closed, as an application does once the last chunk of its response has been written, ends the write,
        # where Mojo calls write on undef
        if (stream := self.ioloop.stream(id)) is None:
            return
        if next is None:
            stream.write(chunk)
            return
        ref = weakref.ref(self)

        def written(stream: Pyjo.IOLoop.Stream.object) -> None:
            _call(ref, next, id)

        stream.write(chunk, written)


# The address of a socket, or none, as sockhost and peerhost of IO::Socket give undef, not an error, of a connection that
# the peer has closed already
def _address(name: Callable[[], Any]) -> tuple[str | None, int | None]:
    try:
        address = name()
    except OSError:
        return None, None
    return address[0], address[1]


# A method of the daemon, as long as it exists, as Mojo weakens the daemon in its callbacks
def _call(ref: 'weakref.ref[Any]', method: str, *args: Any) -> None:
    if (daemon := ref()) is not None:
        getattr(daemon, method)(*args)


def _number(value: str | None, default: float) -> float:
    if value is None:
        return default
    number = float(value)
    return int(number) if number.is_integer() else number


def _peer(handle: Any) -> str:
    if handle.family == getattr(socket, 'AF_UNIX', None):
        try:
            return str(handle.getpeername())
        except OSError:
            return ''
    return _address(handle.getpeername)[0] or ''


def _url(tx: Pyjo.Transaction.object) -> str:
    return str(tx.req.url.to_abs())


# Not in Mojolicious: the daemons that exist, whose listen sockets are closed at the end of the interpreter, as Perl
# closes them then, before Pyjo.IOLoop closes the connections of its event loops
_DAEMONS: 'weakref.WeakSet[Pyjo_Server_Daemon]' = weakref.WeakSet()

# Not in Mojolicious: Windows has no QUIT, of Ctrl-\ in a terminal, and BREAK of Ctrl-Break takes its place in a console
_QUIT = signal.SIGBREAK if sys.platform == 'win32' else signal.SIGQUIT


@atexit.register
def _cleanup() -> None:
    for daemon in list(_DAEMONS):
        try:
            daemon._cleanup()  # pyright: ignore[reportPrivateUsage]
        except Exception:
            pass


new = Pyjo_Server_Daemon.new
object = Pyjo_Server_Daemon
Daemon = Pyjo_Server_Daemon
