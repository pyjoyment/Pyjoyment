"""
Pyjoyment.Plugin.INIConfig - INI configuration plugin
=====================================================
::

    # myapp.ini (it's just INI with embedded Python)
    %# Just a value
    foo = bar

    %# You have full access to the application
    music_dir = <%= app.home.child('music') %>

    [db]
    host = localhost

    # Pyjoyment
    config = app.plugin('INIConfig')
    print(config['foo'])

    # Pyjoyment.Lite
    config = plugin('INIConfig')
    print(config['foo'])

    # foo.html.ep
    %= config()['foo']

    # The configuration is available application-wide
    config = app.config()
    print(config['foo'])

    # Everything can be customized with options
    config = plugin('INIConfig', file='/etc/myapp.conf')

:mod:`Pyjoyment.Plugin.INIConfig` is an INI configuration plugin that
preprocesses its input with :mod:`Pyjo.Template` and parses it with
:mod:`Pyjo.INI`, whose values are strings.

The application object can be accessed via ``app``. A default configuration
filename in the application home directory will be generated from the value
of :attr:`Pyjoyment.Pyjoyment_App.moniker` (``$moniker.ini``). You can extend
the normal configuration file ``$moniker.ini`` with ``mode`` specific ones
like ``$moniker.$mode.ini``, which will be detected automatically.

These configuration values are currently reserved:

``config_override``
    If this configuration value has been set in
    :meth:`Pyjoyment.Pyjoyment_App.config` when this plugin is loaded, it will
    not do anything besides loading deployment specific plugins.

``plugins`` ::

    [plugin SetUserGroup]
    user = sri
    group = staff

    One or more deployment specific plugins that should be loaded right after
    this plugin has been loaded, a section ``[plugin Name]`` for each, as the
    profiles of ``~/.aws/config`` are sections ``[profile name]``, with the
    options of the plugin, in the order of the file. A plugin comes once, as
    a section that comes again adds its keys.

The code of this plugin is a good example for learning to build new plugins,
you're welcome to fork it.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Options
-------

:mod:`Pyjoyment.Plugin.INIConfig` inherits all options from
:mod:`Pyjoyment.Plugin.JSONConfig` and supports the following new ones.

unquote ::

    # Pyjoyment.Lite
    plugin('INIConfig', unquote=True)

Take the quotes around the values off, as PHP does, which :mod:`Pyjo.INI`
keeps by default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Inspired by `Mojolicious::Plugin::NotYAMLConfig
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Plugin/NotYAMLConfig.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.INI
import Pyjoyment.Plugin.JSONConfig

import re

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import Pyjoyment


# The section of a deployment specific plugin, as [plugin SetUserGroup]
_RE_PLUGIN = re.compile(r'plugin\s+(\S.*)')


class Pyjoyment_Plugin_INIConfig(Pyjoyment.Plugin.JSONConfig.object):
    """
    :mod:`Pyjoyment.Plugin.INIConfig` inherits all methods from
    :mod:`Pyjoyment.Plugin.JSONConfig` and implements the following new ones.
    """

    def parse(self, content: str, file: str, conf: dict[str, Any], app: 'Pyjoyment.object') -> dict[str, Any]:
        """::

            plugin.parse(content, file, conf, app)

        Process content with
        :meth:`~Pyjoyment.Plugin.JSONConfig.Pyjoyment_Plugin_JSONConfig.render`
        and parse it with :mod:`Pyjo.INI`, with the sections ``[plugin Name]``
        as the value ``plugins``. ::

            def parse(self, content, file, conf, app):
                ...
                content = self.render(content, file, conf, app)
                ...
                return config
        """
        try:
            config = Pyjo.INI.load(self.render(content, file, conf, app), unquote=bool(conf.get('unquote')))
        except Exception as e:
            raise Pyjo.Exception.new(f'Can\'t load configuration from file "{file}": {e}') from e

        plugins = [
            {m[1]: config.pop(name)}
            for name in list(config)
            if (m := _RE_PLUGIN.fullmatch(name)) and isinstance(config[name], dict)
        ]
        if plugins:
            if 'plugins' in config:
                raise Pyjo.Exception.new(f'Configuration file "{file}" has "plugins" and sections "[plugin Name]"')
            config['plugins'] = plugins
        return config

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> dict[str, Any]:
        """::

            config = plugin.register(Pyjoyment.new())
            config = plugin.register(Pyjoyment.new(), {'file': '/etc/foo.conf'})

        Register plugin in :mod:`Pyjoyment` application and merge
        configuration.
        """
        return super().register(app, {'ext': 'ini', **(conf or {})})


new = Pyjoyment_Plugin_INIConfig.new
object = Pyjoyment_Plugin_INIConfig
INIConfig = Pyjoyment_Plugin_INIConfig
