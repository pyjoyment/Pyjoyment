r"""
Pyjo.Transaction - Transaction base class
=========================================
::

    from Pyjo.Transaction import Transaction

    class MyTransaction(Transaction):
        def client_read(self, chunk): ...
        def client_write(self): ...
        def server_read(self, chunk): ...
        def server_write(self): ...

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Transaction

    class MyTransaction(Pyjo.Transaction.object):
        def client_read(self, chunk): ...
        def client_write(self): ...
        def server_read(self, chunk): ...
        def server_write(self): ...

:mod:`Pyjo.Transaction` is an abstract base class for transactions, like
:mod:`Pyjo.Transaction.HTTP` and :mod:`Pyjo.Transaction.WebSocket`.

Events
------

:mod:`Pyjo.Transaction` inherits all events from :mod:`Pyjo.EventEmitter` and
can emit the following new ones.

connection
~~~~~~~~~~
::

    tx.on('connection', lambda tx, connection: ...)

Emitted when a connection has been assigned to transaction.

finish
~~~~~~
::

    tx.on('finish', lambda tx: ...)

Emitted when transaction is finished.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Transaction <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Transaction.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.EventEmitter
import Pyjo.Exception
import Pyjo.Message
import Pyjo.Message.Request
import Pyjo.Message.Response

from Pyjo.String.Unicode import split
from Pyjo.Util import network_contains

import builtins

from typing import TYPE_CHECKING, Any, Self


type Anything = builtins.object


class Pyjo_Transaction(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.Transaction` inherits all methods from :mod:`Pyjo.EventEmitter`
    and implements the following new ones.
    """

    def __init__(
        self,
        *,
        kept_alive: bool | None = None,
        local_address: str | None = None,
        local_port: int | None = None,
        original_remote_address: str | None = None,
        remote_port: int | None = None,
        req: Pyjo.Message.Request.object | None = None,
        res: Pyjo.Message.Response.object | None = None,
    ) -> None:
        """::

            tx = Pyjo.Transaction.HTTP.new()
            tx = Pyjo.Transaction.HTTP.new(req=Pyjo.Message.Request.new())

        Construct a new transaction object.
        """
        super().__init__()

        self.original_remote_address = original_remote_address
        """::

            address = tx.original_remote_address
            tx.original_remote_address = '127.0.0.1'

        Remote interface address.
        """

        self._kept_alive = kept_alive
        self._local_address = local_address
        self._local_port = local_port
        self._remote_port = remote_port
        self._req = req
        self._res = res

        # The state of the transaction, as the keys of Mojo's hash
        self._completed = False
        self._connection: str | None = None

    if not TYPE_CHECKING:
        # Not in Mojolicious: the transaction of a blocking request used as a decorator, as @ua.get(url) over a
        # callback; out of the sight of type checkers, which would take a transaction for a callable
        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            raise TypeError(
                f"'{type(self).__name__}' object is not callable: a request without a callback is blocking and returns"
                ' its transaction, a non-blocking one takes its callback as the last argument or cb=..., or is a promise'
                ' of get_p(...)'
            )

    @property
    def kept_alive(self) -> bool | None:
        """::

            boolean = tx.kept_alive
            tx.kept_alive = boolean

        Connection has been kept alive.
        """
        return self._kept_alive

    @kept_alive.setter
    def kept_alive(self, value: bool | None) -> None:
        self._kept_alive = value

    @property
    def local_address(self) -> str | None:
        """::

            address = tx.local_address
            tx.local_address = '127.0.0.1'

        Local interface address.
        """
        return self._local_address

    @local_address.setter
    def local_address(self, value: str | None) -> None:
        self._local_address = value

    @property
    def local_port(self) -> int | None:
        """::

            port = tx.local_port
            tx.local_port = 8080

        Local interface port.
        """
        return self._local_port

    @local_port.setter
    def local_port(self, value: int | None) -> None:
        self._local_port = value

    @property
    def remote_port(self) -> int | None:
        """::

            port = tx.remote_port
            tx.remote_port = 8081

        Remote interface port.
        """
        return self._remote_port

    @remote_port.setter
    def remote_port(self, value: int | None) -> None:
        self._remote_port = value

    @property
    def req(self) -> Pyjo.Message.Request.object:
        """::

            req = tx.req
            tx.req = Pyjo.Message.Request.new()

        HTTP request, defaults to a :mod:`Pyjo.Message.Request` object. ::

            # Access request information
            method = tx.req.method
            url = tx.req.url.to_abs()
            info = tx.req.url.to_abs().userinfo
            host = tx.req.url.to_abs().host
            agent = tx.req.headers.user_agent
            custom = tx.req.headers.header('Custom-Header')
            data = tx.req.body
            string = tx.req.text
            params = tx.req.params.to_dict()
            all = tx.req.uploads()
            value = tx.req.json()
            foo = tx.req.json('/23/foo')
            dom = tx.req.dom()
            bar = tx.req.dom('div.bar').first().text
        """
        if self._req is None:
            self._req = Pyjo.Message.Request.new()
        return self._req

    @req.setter
    def req(self, value: Pyjo.Message.Request.object) -> None:
        self._req = value

    @property
    def res(self) -> Pyjo.Message.Response.object:
        """::

            res = tx.res
            tx.res = Pyjo.Message.Response.new()

        HTTP response, defaults to a :mod:`Pyjo.Message.Response` object. ::

            # Access response information
            code = tx.res.code
            message = tx.res.message
            server = tx.res.headers.server
            custom = tx.res.headers.header('Custom-Header')
            data = tx.res.body
            string = tx.res.text
            value = tx.res.json()
            foo = tx.res.json('/23/foo')
            dom = tx.res.dom()
            bar = tx.res.dom('div.bar').first().text
        """
        if self._res is None:
            self._res = Pyjo.Message.Response.new()
        return self._res

    @res.setter
    def res(self, value: Pyjo.Message.Response.object) -> None:
        self._res = value

    def client_read(self, chunk: bytes) -> Anything:
        """::

            tx.client_read(data)

        Read data client-side, used to implement user agents such as
        :mod:`Pyjo.UserAgent`. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "client_read" not implemented by subclass')

    def client_write(self) -> bytes:
        """::

            data = tx.client_write()

        Write data client-side, used to implement user agents such as
        :mod:`Pyjo.UserAgent`. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "client_write" not implemented by subclass')

    def closed(self) -> Self:
        """::

            tx = tx.closed()

        Same as :meth:`completed`, but also indicates that all transaction data
        has been sent.
        """
        return self.completed().emit('finish')

    def completed(self) -> Self:
        """::

            tx = tx.completed()

        Low-level method to finalize transaction.
        """
        self._completed = True
        return self

    @property
    def connection(self) -> str | None:
        """::

            id = tx.connection
            tx.connection = id

        Connection identifier, setting it emits the ``connection`` event.
        """
        return self._connection

    @connection.setter
    def connection(self, value: str | None) -> None:
        self._connection = value
        self.emit('connection', value)

    @property
    def error(self) -> Pyjo.Message.Error | None:
        """::

            err = tx.error

        Get request or response error and return ``None`` if there is no
        error. ::

            # Longer version
            err = tx.req.error or tx.res.error

            # Check for 4xx/5xx response and connection errors
            if err := tx.error:
                if 'code' in err:
                    raise Exception(f'{err["code"]} response: {err["message"]}')
                raise Exception(f'Connection error: {err["message"]}')
        """
        return self.req.error or self.res.error

    @property
    def is_finished(self) -> bool:
        """::

            boolean = tx.is_finished

        Check if transaction is finished.
        """
        return self._completed

    @property
    def is_websocket(self) -> bool:
        """::

            boolean = tx.is_websocket

        False, this is not a :mod:`Pyjo.Transaction.WebSocket` object.
        """
        return False

    @property
    def remote_address(self) -> str | None:
        """::

            address = tx.remote_address
            tx.remote_address = '127.0.0.1'

        Same as :attr:`original_remote_address` unless :attr:`req` has been
        performed via a
        :attr:`Pyjo.Message.Request.Pyjo_Message_Request.reverse_proxy`. If so
        then the last value of ``X-Forwarded-For`` header is returned.
        Additionally if
        :attr:`Pyjo.Message.Request.Pyjo_Message_Request.trusted_proxies` are
        also provided then the original address must be trusted and any
        ``X-Forwarded-For`` entries that are trusted are ignored, returning
        the last untrusted address or the first address if all are trusted.
        """
        if not self.req.reverse_proxy:
            return self.original_remote_address

        # Reverse proxy
        forwarded = split(r'\s*,\s*', self.req.headers.header('X-Forwarded-For') or '')
        addrs: list[str | None] = [a for a in forwarded if a is not None]
        trusted = self.req.trusted_proxies
        if not len(trusted):
            return addrs[-1] if addrs else self.original_remote_address

        addrs.append(self.original_remote_address)
        for addr in reversed(addrs):
            if not any(network_contains(t, addr or '') for t in trusted):
                return addr
        return addrs[0]

    @remote_address.setter
    def remote_address(self, value: str | None) -> None:
        self.original_remote_address = value

    @property
    def result(self) -> Pyjo.Message.Response.object:
        """::

            res = tx.result

        Returns the :mod:`Pyjo.Message.Response` object from :attr:`res` or
        raises an exception if a connection error has occurred. ::

            # Fine grained response handling (raises on connection errors)
            res = tx.result
            if res.is_success:
                print(res.body)
            elif res.is_error:
                print(res.message)
            elif res.code == 301:
                print(res.headers.location)
            else:
                print('Whatever...')
        """
        err = self.error
        if not err or err.get('code'):
            return self.res
        raise Pyjo.Exception.new(err['message'])

    def server_read(self, chunk: bytes) -> Anything:
        """::

            tx.server_read(data)

        Read data server-side, used to implement web servers such as
        :mod:`Pyjo.Server.Daemon`. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "server_read" not implemented by subclass')

    def server_write(self) -> bytes:
        """::

            data = tx.server_write()

        Write data server-side, used to implement web servers such as
        :mod:`Pyjo.Server.Daemon`. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "server_write" not implemented by subclass')


new = Pyjo_Transaction.new
object = Pyjo_Transaction
Transaction = Pyjo_Transaction
