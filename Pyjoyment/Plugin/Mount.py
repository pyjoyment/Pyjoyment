"""
Pyjoyment.Plugin.Mount - Application mount plugin
=================================================
::

    # Pyjoyment
    route = app.plugin('Mount', {'/prefix': '/home/sri/foo/script/foo'})

    # Pyjoyment.Lite
    route = plugin('Mount', {'/prefix': '/home/sri/myapp.py'})

    # Adjust the generated route and mounted application
    example = plugin('Mount', {'/example': '/home/sri/example.py'})
    example.to(message='It works great!')
    embedded = example.pattern.defaults['app']
    embedded.config(foo='bar')
    embedded.log = app.log

    # Mount application with host
    plugin('Mount', {'example.com': '/home/sri/myapp.py'})

    # Host and path
    plugin('Mount', {'example.com/myapp': '/home/sri/myapp.py'})

    # Or even hosts with wildcard subdomains
    plugin('Mount', {'*.example.com/myapp': '/home/sri/myapp.py'})

    # Application object
    plugin('Mount', {'/prefix': MyApp.new()})

    # WSGI application, as an object or as the name of its module and its
    # attribute
    plugin('Mount', {'/flask': flask_app})
    plugin('Mount', {'/flask': 'myflask:app'})

    # ASGI application, as an object or as the name of its module and its
    # attribute
    plugin('Mount', {'/starlette': starlette_app})
    plugin('Mount', {'/starlette': 'mystarlette:app'})

    # FastCGI application, as PHP on php-fpm, by its location, with the
    # directory of its scripts and the one entry of every other path
    plugin('Mount', {'/php': 'fcgi://127.0.0.1:9000'})
    plugin('Mount', {'/php': 'fcgi+unix://%2Frun%2Fphp%2Ffpm.sock'})
    plugin('Mount', {'/blog': 'fcgi://127.0.0.1:9000?document_root=%2Fvar%2Fwww&script=index.php'})

    # CGI application, as an object, as a string is the path of a script
    plugin('Mount', {'/cgi-bin': Pyjo.App.CGI.new(document_root='/usr/lib/cgi-bin')})

    # Event function of AWS Lambda, as an object, in a process of its own
    plugin('Mount', {'/function': Pyjo.App.Lambda.new(function='myfunction.handler')})

    # A regular expression of the whole path, whose group path is the rest of
    # the path for the application, and whose other named groups are captures
    plugin('Mount', {re.compile(r'/php(?P<path>/.*)?'): flask_app})
    plugin('Mount', {re.compile(r'/(?P<user>\\w+)/blog(?P<path>/.*)?'): flask_app})

:mod:`Pyjoyment.Plugin.Mount` is a plugin that allows you to mount whole
:mod:`Pyjoyment` applications, other applications of :mod:`Pyjo`, ``WSGI``
applications, which :mod:`Pyjo.App.WSGI` runs, and ``ASGI`` applications,
whose ``__call__`` is a coroutine function, which :mod:`Pyjo.App.ASGI` runs,
as an application of :mod:`Pyjo` from a script, an object, or the name of a
module and its attribute, and ``FastCGI`` applications, which
:mod:`Pyjo.App.FastCGI` connects to, by their location ``fcgi://`` or
``fcgi+unix://``, ``CGI`` programs, which :mod:`Pyjo.App.CGI` runs, and
event functions of AWS Lambda, which :mod:`Pyjo.App.Lambda` runs, as an
object of them. An application that is not one of :mod:`Pyjoyment` gets the
server that runs it with :meth:`~Pyjo.App.Pyjo_App.server` before the server
starts, as the application that mounts it does.

The path is a pattern of a route that matches the beginning of the path of a
request, as in Mojolicious, so that ``/php`` matches ``/php.css`` too, which
an application of another framework does not get, as its ``SCRIPT_NAME`` or
``root_path`` ends at a slash. A regular expression matches the whole path, as
the ones of PromQL do, with the rest of it for the application in its group
``path``.

The static files of :mod:`Pyjoyment.Static` are served before the routes, also
the bundled ``favicon.ico`` of :attr:`~Pyjoyment.Static.Pyjoyment_Static.extra`,
so an application mounted on ``/`` has its own ``favicon.ico`` in a directory
of :attr:`~Pyjoyment.Static.Pyjoyment_Static.paths`, which comes first, or
the bundled one is removed with ``del app.static.extra['favicon.ico']``.

The code of this plugin is a good example for learning to build new plugins,
you're welcome to fork it.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Plugin::Mount
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Plugin/Mount.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.App
import Pyjo.App.ASGI
import Pyjo.App.FastCGI
import Pyjo.App.WSGI
import Pyjo.Exception
import Pyjo.Server
import Pyjoyment.Plugin
import Pyjoyment.Routes.Pattern

import importlib
import inspect
import os
import re

from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    import Pyjoyment
    import Pyjoyment.Routes.Route


class Pyjoyment_Plugin_Mount(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.Mount` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[Any, Any]) -> 'Pyjoyment.Routes.Route.object':
        """::

            route = plugin.register(Pyjoyment.new(), {'/foo': '/some/app.py'})
            route = plugin.register(Pyjoyment.new(), {'/foo': 'some_app:app'})

        Mount application and return the generated route, which is usually a
        :mod:`Pyjoyment.Routes.Route` object.
        """
        import Pyjoyment

        key: str | re.Pattern[str] = next(iter(conf))
        embed: Any = _load(conf[key])
        if isinstance(embed, Pyjoyment.object):
            embed.secrets = app.secrets

        # Not in Mojolicious: another application of Pyjo, as one of Pyjo.App.WSGI, gets the server that runs it before it
        # starts and after it stops, as the application that mounts it gets it
        else:

            def before_server_start(server: Pyjo.Server.object, app: Any) -> None:
                embed.server(server)

            def after_server_stop(server: Pyjo.Server.object, app: Any) -> Any:
                return embed.server_stopped(server)

            app.hook('before_server_start', before_server_start)
            app.hook('after_server_stop', after_server_stop)
        embed.log = app.log

        # Not in Mojolicious: a regular expression that matches the whole path, as the ones of PromQL do, whose group
        # path is the rest of the path for the application, as partial routes have it, and whose other named groups are
        # captures
        if isinstance(key, re.Pattern):
            route = app.routes.any()
            route.pattern = _Whole(key)
            route.partial = True
            return route.to(app=embed)

        # Extract host
        path: str | None = key
        host = None
        if m := re.match(r'^(\*\.)?([^/]+)(/.*)?$', path):
            host = re.compile(rf'^(?:.*\.)?{re.escape(m[2])}$' if m[1] else rf'^{re.escape(m[2])}$', re.I)
            path = m[3]

        route = app.routes.any(path)
        route.partial = True
        route.to(app=embed)
        return route.requires(host=host) if host else route


# Not in Mojolicious: an application as an object, or as the name of a module and its attribute, as ASGI servers take
# it, an ASGI or a WSGI application, which Pyjo.App.ASGI or Pyjo.App.WSGI runs, and the location of a FastCGI
# application, which Pyjo.App.FastCGI connects to, where Mojolicious loads a script
def _load(value: Any) -> Pyjo.Server.Application:
    if isinstance(value, str) and re.match(r'fcgi(\+unix)?://', value):
        return Pyjo.App.FastCGI.new(url=value)
    if isinstance(value, str) and re.fullmatch(r'[\w.]+:[\w.]+', value) and not os.path.exists(value):
        module, _, name = value.partition(':')
        try:
            value = importlib.import_module(module)
            for attr in name.split('.'):
                value = getattr(value, attr)
        except Exception as e:
            raise Pyjo.Exception.new(f'Can\'t load application "{module}:{name}": {e}') from e
    elif isinstance(value, str | os.PathLike):
        return Pyjo.Server.new().load_app(cast(str, value))

    if isinstance(value, Pyjo.App.object):
        return value
    if inspect.iscoroutinefunction(value) or inspect.iscoroutinefunction(type(value).__call__):
        return Pyjo.App.ASGI.new(app=value)
    if not callable(value):
        raise Pyjo.Exception.new(f'"{value!r}" is not an application')
    return Pyjo.App.WSGI.new(app=value)


# Not in Mojolicious: the pattern of a regular expression that matches the whole path, whose named groups are captures,
# and whose group path, from its start to the end of the path, is the rest of the path
class _Whole(Pyjoyment.Routes.Pattern.object):
    def __init__(self, whole: re.Pattern[str]) -> None:
        super().__init__()
        self.whole = whole
        # The regular expression and its source, as the pages of exceptions and of not found and the command routes show
        # them
        self.regex = whole
        self.unparsed = whole.pattern

    def match_partial(self, path: str, detect: bool = False) -> tuple[dict[str, Any], str] | None:
        if (m := self.whole.fullmatch(path)) is None:
            return None
        captures = {**self.defaults, **{name: value for name, value in m.groupdict().items() if value is not None}}
        rest = path[m.start('path') :] if captures.pop('path', None) is not None else ''
        return captures, rest


new = Pyjoyment_Plugin_Mount.new
object = Pyjoyment_Plugin_Mount
Mount = Pyjoyment_Plugin_Mount
