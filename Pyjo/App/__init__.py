"""
Pyjo.App - Duct tape for the HTML5 web
======================================
::

    from Pyjo.App import App

    class MyApp(App):

        # All the complexities of CGI, WSGI, ASGI, HTTP and WebSockets get
        # reduced to a single method call!
        def handler(self, tx):

            # Resume transaction at the end of the block
            with tx:

                # Request
                method = tx.req.method
                path = tx.req.url.path

                # Response
                tx.res.code = 200
                tx.res.headers.content_type = 'text/plain'
                tx.res.body = f'{method} request for {path}!'.encode()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.App

    class MyApp(Pyjo.App.object):

        # All the complexities of CGI, WSGI, ASGI, HTTP and WebSockets get
        # reduced to a single method call!
        def handler(self, tx):

            # Resume transaction at the end of the block
            with tx:

                # Request
                method = tx.req.method
                path = tx.req.url.path

                # Response
                tx.res.code = 200
                tx.res.headers.content_type = 'text/plain'
                tx.res.body = f'{method} request for {path}!'.encode()

:mod:`Pyjo.App` is the base class of applications of :mod:`Pyjo`, a flexible
runtime environment for real-time web frameworks, with all the basic tools and
helpers needed to write simple web applications and higher level web
frameworks, such as :mod:`Pyjoyment`.

The end of a ``with`` block closes the connections and the servers of its
:attr:`~Pyjo_App.ua`.

See also
--------

:mod:`Pyjo.App.WSGI`, :mod:`Pyjo.HelloWorld`, :mod:`Pyjoyment`, https://mojolicious.org.

Inspired by `Mojo <https://github.com/mojolicious/mojo/blob/v6.0/lib/Mojo.pm>`_ of Mojolicious 6.0, the base class of
Mojolicious until Mojolicious 7.
"""

import Pyjo.Base
import Pyjo.Home
import Pyjo.Log
import Pyjo.Promise
import Pyjo.Server
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent
import Pyjo.Util

import os
import sys

from types import TracebackType
from typing import Any, Self, overload


class Pyjo_App(Pyjo.Base.object):
    """
    :mod:`Pyjo.App` inherits all methods from :mod:`Pyjo.Base` and implements
    the following new ones.
    """

    # The methods that keep a stash, whose values the arguments of the constructor are
    _stashes: tuple[str, ...] = ('config',)

    def __init__(self, attrs: dict[str, Any] | None = None, /, **kwargs: Any) -> None:
        """::

            app = MyApp.new()
            app = MyApp.new(moniker='foo_bar')
            app = MyApp.new({'moniker': 'foo_bar'})

        Construct a new application, with the attributes as keyword arguments
        or a dict, and the arguments of
        :meth:`Pyjo.Server.Pyjo_Server.load_app` for its script. The value of
        ``config`` is the dict of :meth:`config`.
        """
        self._home: Pyjo.Home.object | None = None
        self._log: Pyjo.Log.object | None = None
        self._moniker: str | None = None
        self._ua: Pyjo.UserAgent.object | None = None

        # Not in Mojolicious: the value of a method that keeps a stash, as config, is its dict, as Mojo keeps the stash in
        # the hash of the object, which the arguments of new fill
        for name, value in {**(attrs or {}), **kwargs, **Pyjo.Server.args_override}.items():
            setattr(self, f'_{name}' if name in self._stashes else name, value)

    # Not in Mojolicious: a context manager, which closes the connections and the servers of its user agent where the
    # block ends, as PyPy frees the object only when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    @property
    def home(self) -> Pyjo.Home.object:
        """::

            home = app.home
            app.home = Pyjo.Home.new()

        The home directory of your application, defaults to a :mod:`Pyjo.Home`
        object which stringifies to the actual path. ::

            # Portably generate path relative to home directory
            path = app.home.child('data', 'important.txt')
        """
        if self._home is None:
            self._home = Pyjo.Home.new().detect(type(self))
        return self._home

    @home.setter
    def home(self, value: Pyjo.Home.object) -> None:
        self._home = value

    @property
    def log(self) -> Pyjo.Log.object:
        """::

            log = app.log
            app.log = Pyjo.Log.new()

        The logging layer of your application, defaults to a :mod:`Pyjo.Log`
        object. The level will default to the ``PYJO_LOG_LEVEL`` environment
        variable, or ``trace``, and the messages will be written to
        ``sys.stderr``. ::

            # Log debug message
            app.log.debug('It works')
        """
        if self._log is None:
            log = Pyjo.Log.new()
            # The level of the environment, as an application of Pyjoyment has it, which the tests of Pyjo.Test.Pyjo
            # set, so that an application of Pyjo, as an adapter of another framework, logs as quietly
            if level := os.environ.get('PYJO_LOG_LEVEL'):
                log.level = level
            self._log = log
        return self._log

    @log.setter
    def log(self, value: Pyjo.Log.object) -> None:
        self._log = value

    @property
    def moniker(self) -> str:
        """::

            moniker = app.moniker
            app.moniker = 'foo_bar'

        Moniker of this application, often used as default filename for
        configuration files and the like, defaults to decamelizing the
        application class with :func:`Pyjo.Util.decamelize`: the module of a
        class that the module names ``object``, as ``pyjo-hello_world`` of
        :mod:`Pyjo.HelloWorld`, or the class in its module.
        """
        if self._moniker is None:
            self._moniker = Pyjo.Util.decamelize(_package(type(self)).replace('.', '::'))
        return self._moniker

    @moniker.setter
    def moniker(self, value: str) -> None:
        self._moniker = value

    @property
    def ua(self) -> Pyjo.UserAgent.object:
        """::

            ua = app.ua
            app.ua = Pyjo.UserAgent.new()

        A full featured HTTP user agent for use in your applications, defaults
        to a :mod:`Pyjo.UserAgent` object. ::

            # Perform blocking request
            print(app.ua.get('example.com').result.body)
        """
        if self._ua is None:
            self._ua = Pyjo.UserAgent.new()
        return self._ua

    @ua.setter
    def ua(self, value: Pyjo.UserAgent.object) -> None:
        self._ua = value

    def build_tx(self) -> Pyjo.Transaction.HTTP.object:
        """::

            tx = app.build_tx()

        Transaction builder, defaults to building a
        :mod:`Pyjo.Transaction.HTTP` object.
        """
        return Pyjo.Transaction.HTTP.new()

    # Not in Mojolicious: the release of the user agent, which Perl does in DESTROY, also at the end of a with block
    def close(self) -> None:
        """::

            app.close()

        Close the connections and the servers of :attr:`ua`, as the end of a
        ``with`` block does.
        """
        if self._ua is not None:
            self._ua.close()

    # config(**values) with no values is config(), which the first overload types
    @overload
    def config(self) -> dict[str, Any]: ...  # pyright: ignore[reportOverlappingOverload]

    @overload
    def config(self, name: str, /) -> Any: ...

    @overload
    def config(self, values: dict[str, Any], /) -> Self: ...

    @overload
    def config(self, **values: Any) -> Self: ...

    def config(self, *args: Any, **values: Any) -> Any:
        """::

            hash = app.config()
            foo = app.config('foo')
            app = app.config({'foo': 'bar', 'baz': 23})
            app = app.config(foo='bar', baz=23)

        Application configuration. ::

            # Remove value
            foo = app.config().pop('foo')

            # Assign multiple values at once
            app.config(foo='test', bar=23)
        """
        return Pyjo.Util._stash('config', self, args, values)  # pyright: ignore[reportPrivateUsage]

    def handler(self, tx: Any) -> None:
        """::

            app.handler(Pyjo.Transaction.HTTP.new())

        The handler is the main entry point to your application or framework
        and will be called for each new transaction, which will usually be a
        :mod:`Pyjo.Transaction.HTTP` or :mod:`Pyjo.Transaction.WebSocket`
        object. A route of :mod:`Pyjoyment` that embeds the application, as
        :mod:`Pyjoyment.Plugin.Mount` does, calls it with its controller
        instead, whose ``tx`` is the transaction and whose stash has the rest of
        the path in ``path``. Meant to be overloaded in a subclass. ::

            def handler(self, tx):
                ...
        """
        raise NotImplementedError('Method "handler" not implemented by subclass')

    def server(self, server: Pyjo.Server.object) -> None:
        """::

            app.server(Pyjo.Server.new())

        Called by the server before it starts. Meant to be overloaded in a
        subclass.
        """

    # Not in Mojolicious: the end of a server, as server is its start, after which the application cleans up what it has
    # started, as the lifespan of an ASGI application
    def server_stopped(self, server: Pyjo.Server.object) -> 'Pyjo.Promise.object | None':
        """::

            promise = app.server_stopped(Pyjo.Server.new())

        Called by the server once it has stopped gracefully, in each process
        and thread that has run the application, with the event loop no longer
        running. A promise that it returns is waited for, so that the
        application can clean up with the event loop. Meant to be overloaded
        in a subclass.
        """
        return None

    def start(self, *args: str) -> Self:
        """::

            app = app.start()

        Start the application. When the environment variable
        ``PYJO_APP_LOADER`` is set, as :meth:`Pyjo.Server.Pyjo_Server.load_app`
        does, it is kept in :data:`Pyjo.Server.loaded_app` for the server.
        """
        # Application loader
        if os.environ.get('PYJO_APP_LOADER') is not None:
            Pyjo.Server.loaded_app = self
        return self


# The name of a class as Mojo has the package: the module that names the class its object, or the class in the module,
# and the class only in a script
def _package(cls: type) -> str:
    module = cls.__module__
    if getattr(sys.modules.get(module), 'object', None) is cls:
        return module
    return cls.__qualname__ if module == '__main__' else f'{module}.{cls.__qualname__}'


# The path of the request for an application of another framework, as escaped strings: the path that a route embeds the
# application under, after the base path, as SCRIPT_NAME of WSGI and root_path of ASGI, and the rest of it, which the
# route left in the stash
def _mount(tx: Any, c: Any) -> tuple[str, str]:  # pyright: ignore[reportUnusedFunction]
    url = tx.req.url
    path = url.path.to_abs_str()
    script = url.base.path.to_str().rstrip('/')

    if c is not None and (rest := c.stash().get('path')) is not None:
        route = url.path.to_route()
        if not route.endswith(rest):
            path = rest
        else:
            # The rest begins at the slash after the ones of the path above it
            end = len(path)
            if len(rest):
                end = -1
                for _ in range(route[: len(route) - len(rest)].count('/') + 1):
                    if (end := path.find('/', end + 1)) < 0:
                        end = len(path)
                        break
            script += path[:end]
            path = path[end:]

    return script, path


# Not in Mojolicious: a route embeds an application of another framework at a part of the path that ends with a slash,
# or at the whole path, as SCRIPT_NAME of CGI and WSGI and root_path of ASGI can only be, where /php of /phpx is not
def _within(c: Any) -> bool:  # pyright: ignore[reportUnusedFunction]
    return c is None or not (rest := c.stash().get('path')) or rest.startswith('/')


# Not in Mojolicious: the page of 404 of a path that the application does not take, as /phpx of /php, of the application
# that embeds it, without the rest of the path that the route has matched, with which url_for of the page would put its
# links, as the ones of its assets, under the path of the route
def _not_found(c: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
    c.stash().pop('path', None)
    return c.helpers.reply.not_found()


# The environment of CGI for the request, as an application of another framework gets it: the path that a route embeds
# the application under is SCRIPT_NAME, and the rest of it is PATH_INFO, as unescaped bytes in the characters 0-255
def _cgi(tx: Any, c: Any) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
    req = tx.req
    url = req.url
    base = url.base
    script, path = _mount(tx, c)

    https = req.is_secure
    env = {
        'REQUEST_METHOD': req.method,
        'SCRIPT_NAME': _bytes(script),
        'PATH_INFO': _bytes(path),
        'QUERY_STRING': url.query.to_str(),
        'SERVER_NAME': base.host or tx.local_address or 'localhost',
        'SERVER_PORT': str(base.port or tx.local_port or (443 if https else 80)),
        'SERVER_PROTOCOL': f'HTTP/{req.version}',
    }
    if (address := tx.remote_address) is not None:
        env['REMOTE_ADDR'] = address
    if (port := tx.remote_port) is not None:
        env['REMOTE_PORT'] = str(port)

    # Headers, joined as CGI has them, and the length of the body, which is whole, as it has been read
    headers = req.headers
    for name in headers.names():
        key = name.upper().replace('-', '_')
        if key == 'CONTENT_TYPE':
            env[key] = headers.header(name)
        elif key not in ('CONTENT_LENGTH', 'TRANSFER_ENCODING'):
            env[f'HTTP_{key}'] = ('; ' if key == 'COOKIE' else ', ').join(headers.every_header(name))
    if size := req.content.body_size:
        env['CONTENT_LENGTH'] = str(size)

    return env


# A path of CGI: the unescaped bytes as the characters 0-255
def _bytes(path: str) -> str:
    return Pyjo.Util.url_unescape(path.encode()).decode('latin-1')


new = Pyjo_App.new
object = Pyjo_App
App = Pyjo_App
