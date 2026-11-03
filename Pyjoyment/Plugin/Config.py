"""
Pyjoyment.Plugin.Config - Python-ish configuration plugin
=========================================================
::

    # myapp.conf (it's just Python ending with a dict)
    {
        # Just a value
        'foo': 'bar',

        # Nested data structures are fine too
        'baz': ['♥'],

        # You have full access to the application
        'music_dir': app.home.child('music'),
    }

    # Pyjoyment
    config = app.plugin('Config')
    print(config['foo'])

    # Pyjoyment.Lite
    config = plugin('Config')
    print(config['foo'])

    # foo.html.ep
    %= config()['foo']

    # The configuration is available application-wide
    config = app.config()
    print(config['foo'])

    # Everything can be customized with options
    config = plugin('Config', file='/etc/myapp.stuff')

:mod:`Pyjoyment.Plugin.Config` is a Python-ish configuration plugin.

The configuration file is Python code, and the value of its last expression,
a dict, is the configuration; the statements before it can import modules and
prepare values. The application object can be accessed via ``app``. A
default configuration filename in the application home directory will be
generated from the value of :attr:`Pyjoyment.Pyjoyment_App.moniker`
(``$moniker.conf``). You can extend the normal configuration file
``$moniker.conf`` with ``mode`` specific ones like ``$moniker.$mode.conf``,
which will be detected automatically.

These configuration values are currently reserved:

``config_override``
    If this configuration value has been set in
    :meth:`Pyjoyment.Pyjoyment_App.config` when this plugin is loaded, it will
    not do anything besides loading deployment specific plugins.

``plugins`` ::

    'plugins': [{'SetUserGroup': {'user': 'sri', 'group': 'staff'}}]

    One or more deployment specific plugins that should be loaded right after
    this plugin has been loaded.

The code of this plugin is a good example for learning to build new plugins,
you're welcome to fork it.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Options
-------

:mod:`Pyjoyment.Plugin.Config` supports the following options.

default ::

    # Pyjoyment.Lite
    plugin('Config', default={'foo': 'bar'})

Default configuration, making configuration files optional.

ext ::

    # Pyjoyment.Lite
    plugin('Config', ext='stuff')

File extension for generated configuration filenames, defaults to ``conf``.

file ::

    # Pyjoyment.Lite
    plugin('Config', file='myapp.conf')
    plugin('Config', file='/etc/foo.stuff')

Path to configuration file, absolute or relative to the application home
directory, defaults to the value of the ``PYJO_CONFIG`` environment variable
or ``$moniker.conf`` in the application home directory.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Plugin::Config
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Plugin/Config.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.File
import Pyjoyment.Plugin

import ast
import os
import re

from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    import Pyjoyment


class Pyjoyment_Plugin_Config(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.Config` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def load(self, file: str, conf: dict[str, Any], app: 'Pyjoyment.object') -> dict[str, Any]:
        """::

            plugin.load(file, conf, app)

        Loads configuration file and passes the content to :meth:`parse`. ::

            def load(self, file, conf, app):
                ...
                return self.parse(content, file, conf, app)
        """
        if (content := Pyjo.File.path(file).slurp('UTF-8')) is None:
            raise Pyjo.Exception.new(f'Configuration file "{file}" has invalid encoding')
        return self.parse(content, file, conf, app)

    def parse(self, content: str, file: str, conf: dict[str, Any], app: 'Pyjoyment.object') -> dict[str, Any]:
        """::

            plugin.parse(content, file, conf, app)

        Parse configuration file. ::

            def parse(self, content, file, conf, app):
                ...
                return config
        """
        # Run Python code in sandbox
        try:
            config = _run(content, file, app)
        except Exception as e:
            raise Pyjo.Exception.new(f'Can\'t load configuration from file "{file}": {e}') from e
        if not isinstance(config, dict):
            raise Pyjo.Exception.new(f'Configuration file "{file}" did not return a dict')

        return cast(dict[str, Any], config)

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> dict[str, Any]:
        """::

            config = plugin.register(Pyjoyment.new())
            config = plugin.register(Pyjoyment.new(), {'file': '/etc/app.conf'})

        Register plugin in :mod:`Pyjoyment` application and merge
        configuration.
        """
        conf = conf or {}

        # Override
        if app.config().get('config_override'):
            return _plugins(app, app.config())

        # Config file
        file = conf.get('file') or os.environ.get('PYJO_CONFIG')
        file = str(file) if file else f'{app.moniker}.{conf.get("ext") or "conf"}'

        # Mode specific config file
        m = re.search(r'^(.*)\.([^.]+)$', file)
        mode: str | None = f'{m[1]}.{app.mode}.{m[2]}' if m else ''

        home = app.home
        if not Pyjo.File.path(file).is_abs:
            file = home.child(file).to_str()
        if mode and not Pyjo.File.path(mode).is_abs:
            mode = home.child(mode).to_str()
        if not (mode and os.path.exists(mode)):
            mode = None

        # Read config file
        config: dict[str, Any] = {}
        if os.path.exists(file):
            config = self.load(file, conf, app)

        # Check for default and mode specific config file
        elif not conf.get('default') and not mode:
            raise Pyjo.Exception.new(f'Configuration file "{file}" missing, maybe you need to create it?\n')

        # Merge everything
        if mode:
            config = {**config, **self.load(mode, conf, app)}
        if conf.get('default'):
            config = {**conf['default'], **config}
        return _plugins(app, app.config(config).config())


def _plugins(app: 'Pyjoyment.object', config: dict[str, Any]) -> dict[str, Any]:
    if plugins := config.get('plugins'):
        if not isinstance(plugins, list):
            raise Pyjo.Exception.new('Configuration value "plugins" is not a list')
        for plugin in cast(list[Any], plugins):
            if not isinstance(plugin, dict):
                raise Pyjo.Exception.new('Configuration value "plugins" contains an entry that is not a dict')
            name, values = next(iter(cast(dict[str, Any], plugin).items()))
            app.plugin(name, values)

    return app.config()


# The value of the last expression of the code, as Perl gives the value of the last statement, with the application
# as "app"
def _run(content: str, file: str, app: 'Pyjoyment.object') -> Any:
    tree = ast.parse(content, filename=file)
    last = tree.body[-1] if tree.body else None
    if not isinstance(last, ast.Expr):
        last = None
    else:
        tree.body.pop()
    namespace: dict[str, Any] = {'__name__': f'{__name__}.Sandbox', 'app': app}
    exec(compile(tree, file, 'exec'), namespace)
    if last is None:
        return None
    return eval(compile(ast.Expression(last.value), file, 'eval'), namespace)


new = Pyjoyment_Plugin_Config.new
object = Pyjoyment_Plugin_Config
Config = Pyjoyment_Plugin_Config
