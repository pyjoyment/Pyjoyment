"""
Pyjoyment.Plugins - Plugin manager
==================================
::

    from Pyjoyment.Plugins import Plugins

    plugins = Plugins()
    plugins.namespaces.append('MyApp.Plugin')

    # Or import the module, as in Google Python Style Guide

    import Pyjoyment.Plugins

    plugins = Pyjoyment.Plugins.new()
    plugins.namespaces.append('MyApp.Plugin')

:mod:`Pyjoyment.Plugins` is the plugin manager of :mod:`Pyjoyment`.

Plugins
-------

The following plugins are included in the :mod:`Pyjoyment` distribution as
examples.

:mod:`Pyjoyment.Plugin.AccessLog`
    Access log of the requests, in the combined format or in JSON.

:mod:`Pyjoyment.Plugin.AllowedHosts`
    Validation of ``Host`` and ``Origin`` against DNS rebinding.

:mod:`Pyjoyment.Plugin.Config`
    Python-ish configuration files.

:mod:`Pyjoyment.Plugin.DefaultHelpers`
    General purpose helper collection, loaded automatically.

:mod:`Pyjoyment.Plugin.EPLRenderer`
    Renderer for plain embedded Python templates, loaded automatically.

:mod:`Pyjoyment.Plugin.EPRenderer`
    Renderer for more sophisticated embedded Python templates, loaded
    automatically.

:mod:`Pyjoyment.Plugin.Health`
    Liveness and readiness of containers and orchestrators.

:mod:`Pyjoyment.Plugin.HeaderCondition`
    Route condition for all kinds of headers, loaded automatically.

:mod:`Pyjoyment.Plugin.INIConfig`
    INI configuration files.

:mod:`Pyjoyment.Plugin.JSONConfig`
    JSON configuration files.

:mod:`Pyjoyment.Plugin.Mount`
    Mount whole :mod:`Pyjoyment` applications.

:mod:`Pyjoyment.Plugin.PyRenderer`
    Renderer for template strings, loaded automatically.

:mod:`Pyjoyment.Plugin.TagHelpers`
    Template specific helper collection, loaded automatically.

:mod:`Pyjoyment.Plugin.TOMLConfig`
    TOML configuration files.

:mod:`Pyjoyment.Plugin.YAMLConfig`
    YAML configuration files.

Events
------

:mod:`Pyjoyment.Plugins` inherits all events from :mod:`Pyjo.EventEmitter`.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Plugins <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Plugins.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.EventEmitter
import Pyjo.Exception
import Pyjo.Loader
import Pyjoyment.Plugin

from Pyjo.Util import camelize

import re

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self


if TYPE_CHECKING:
    import Pyjoyment


class Pyjoyment_Plugins(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjoyment.Plugins` inherits all methods from
    :mod:`Pyjo.EventEmitter` and implements the following new ones.
    """

    def __init__(self) -> None:
        """::

            plugins = Pyjoyment.Plugins.new()

        Construct a new :mod:`Pyjoyment.Plugins` object.
        """
        super().__init__()

        self.namespaces = ['Pyjoyment.Plugin']
        """::

            namespaces = plugins.namespaces
            plugins.namespaces = ['Pyjoyment.Plugin']

        Namespaces to load plugins from, defaults to :mod:`Pyjoyment.Plugin`. ::

            # Add another namespace to load plugins from
            plugins.namespaces.append('MyApp.Plugin')
        """

    def emit_chain(self, name: str, *args: Any) -> Any:
        """::

            plugins.emit_chain('foo')
            plugins.emit_chain('foo', 123)

        Emit events as chained hooks.
        """
        wrapper: Callable[[], Any] | None = None
        for cb in reversed(self.subscribers(name)):
            wrapper = _wrap(cb, wrapper, args)

        return wrapper() if wrapper is not None else None

    def emit_hook(self, name: str, *args: Any) -> Self:
        """::

            plugins = plugins.emit_hook('foo')
            plugins = plugins.emit_hook('foo', 123)

        Emit events as hooks.
        """
        for cb in self.subscribers(name):
            cb(*args)
        return self

    def emit_hook_reverse(self, name: str, *args: Any) -> Self:
        """::

            plugins = plugins.emit_hook_reverse('foo')
            plugins = plugins.emit_hook_reverse('foo', 123)

        Emit events as hooks in reverse order.
        """
        for cb in reversed(self.subscribers(name)):
            cb(*args)
        return self

    def load_plugin(self, name: str) -> Pyjoyment.Plugin.object:
        """::

            plugin = plugins.load_plugin('some_thing')
            plugin = plugins.load_plugin('SomeThing')
            plugin = plugins.load_plugin('MyApp.Plugin.SomeThing')

        Load a plugin from the configured namespaces or by full module name.
        """
        # Try all namespaces and full module name
        suffix = camelize(name).replace('::', '.') if re.match(r'^[a-z]', name) else name
        classes = [f'{namespace}.{suffix}' for namespace in self.namespaces]
        for cls in [*classes, name]:
            if (plugin := _load(cls)) is not None:
                return plugin.new()

        # Not found
        raise Pyjo.Exception.new(f'Plugin "{name}" missing, maybe you need to install it?\n')

    def register_plugin(
        self, name: str, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None, /, **values: Any
    ) -> Any:
        """::

            plugins.register_plugin('some_thing', Pyjoyment.new())
            plugins.register_plugin('some_thing', Pyjoyment.new(), foo=23)
            plugins.register_plugin('some_thing', Pyjoyment.new(), {'foo': 23})
            plugins.register_plugin('SomeThing', Pyjoyment.new())
            plugins.register_plugin('SomeThing', Pyjoyment.new(), foo=23)
            plugins.register_plugin('SomeThing', Pyjoyment.new(), {'foo': 23})
            plugins.register_plugin('MyApp.Plugin.SomeThing', Pyjoyment.new())
            plugins.register_plugin('MyApp.Plugin.SomeThing', Pyjoyment.new(), foo=23)
            plugins.register_plugin('MyApp.Plugin.SomeThing', Pyjoyment.new(), {'foo': 23})

        Load a plugin from the configured namespaces or by full module name and
        run ``register``, optional arguments are passed through.
        """
        return self.load_plugin(name).register(app, {**(conf or {}), **values})


def _load(name: str) -> type[Pyjoyment.Plugin.object] | None:
    if isinstance(e := Pyjo.Loader.load_class(name), Exception):
        raise e
    cls = Pyjo.Loader._class(name)  # pyright: ignore[reportPrivateUsage]
    return cls if cls is not None and issubclass(cls, Pyjoyment.Plugin.object) else None


def _wrap(cb: Callable[..., Any], next: Callable[[], Any] | None, args: tuple[Any, ...]) -> Callable[[], Any]:
    return lambda: cb(next, *args)


new = Pyjoyment_Plugins.new
object = Pyjoyment_Plugins
Plugins = Pyjoyment_Plugins
