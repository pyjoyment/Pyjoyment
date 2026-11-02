"""
Pyjoyment.Command.Author.generate.plugin - Plugin generator command
===================================================================
::

    Usage: APPLICATION generate plugin [OPTIONS] [NAME]

      pyjo generate plugin
      pyjo generate plugin AliceSearch
      pyjo generate plugin -f MyApp.Ext.Test

    Options:
      -f, --full   Do not prepend "Pyjoyment.Plugin."
      -h, --help   Show this summary of available options

:mod:`Pyjoyment.Command.Author.generate.plugin` generates directory structures
for fully functional :mod:`Pyjoyment` plugins: a distribution with
``pyproject.toml``, which builds with hatchling, and a test, which
``uv run python -m Pyjo.Prove -l -r t`` runs, as does ``uv run pytest``,
with pytest of the dependency group ``dev``. The module of a plugin is in the
namespace ``Pyjoyment.Plugin``, which the distribution adds to without the
``__init__.py`` files of the namespace. ``AGENTS.md``, which ``CLAUDE.md``
imports, tells a coding agent how the plugin is made, tested and built, and
where the skills of Pyjoyment are.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::Author::generate::plugin
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/Author/generate/plugin.pm>`_ of
Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjoyment.Command

from Pyjo.Util import class_to_path, extract_usage, getopt
from Pyjoyment.Command.Author.generate.pyproject import _requirement  # pyright: ignore[reportPrivateUsage]


class Pyjoyment_Command_Author_generate_plugin(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.Author.generate.plugin` inherits all attributes and
    methods from :mod:`Pyjoyment.Command` and implements the following new
    ones.
    """

    description = 'Generate Pyjoyment plugin directory structure'
    """::

        description = plugin.description
        plugin.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = plugin.usage
        plugin.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> None:
        """::

            plugin.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not (opts := getopt(arguments, {'f|full': None})):
            raise Pyjo.Exception.new(self.usage)

        # Class
        name = arguments[0] if arguments else 'MyPlugin'
        class_ = name if opts.full else f'Pyjoyment.Plugin.{name}'
        dir = '-'.join(class_.split('.'))
        app = class_to_path(class_)
        title = f'{class_} - Pyjoyment Plugin'
        self.render_to_rel_file(
            'class',
            f'{dir}/{app}',
            {
                'alias': class_.rsplit('.', 1)[-1],
                'class_': class_,
                'identifier': class_.replace('.', '_'),
                'name': name,
                'title': title,
            },
        )

        # Test
        # Renamed from Mojolicious: t/basic.py, where Mojo has t/basic.t
        self.render_to_rel_file('test', f'{dir}/t/basic.py', {'name': name})

        # Makefile
        # Renamed from Mojolicious: pyproject.toml, where Mojo has Makefile.PL
        self.render_to_rel_file(
            'pyproject', f'{dir}/pyproject.toml', {'dir': dir, 'path': app, 'requirement': _requirement()}
        )

        # Not in Mojolicious: the guide of the coding agents, AGENTS.md, which CLAUDE.md imports for Claude Code
        self.render_to_rel_file('agents', f'{dir}/AGENTS.md', {'class_': class_, 'dir': dir, 'name': name, 'path': app})
        self.render_to_rel_file('claude', f'{dir}/CLAUDE.md')


new = Pyjoyment_Command_Author_generate_plugin.new
object = Pyjoyment_Command_Author_generate_plugin

__DATA__ = r'''
@@ class
"""
<%= title %>
<%= '=' * len(title) %>
::

    # Pyjoyment
    app.plugin('<%= name %>')

    # Pyjoyment.Lite
    plugin('<%= name %>')

:mod:`<%= class_ %>` is a :mod:`Pyjoyment` plugin.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Classes
-------
"""

import Pyjoyment.Plugin


__version__ = '0.1.0'


class <%= identifier %>(Pyjoyment.Plugin.object):
    """
    :mod:`<%= class_ %>` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app, conf):
        """::

            plugin.register(Pyjoyment.new(), {})

        Register plugin in :mod:`Pyjoyment` application.
        """


object = <%= identifier %>
% if alias != identifier:
<%= alias %> = <%= identifier %>
% end

@@ test
from Pyjo.Test import *
from Pyjoyment.Lite import *

import Pyjo.Test.Pyjo


plugin('<%= name %>')


@get('/')
def index(c):
    c.render(text='Hello Pyjo!')


t = Pyjo.Test.Pyjo.new()
t.get_ok('/').status_is(200).content_is('Hello Pyjo!')

done_testing()

@@ pyproject
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "<%= dir %>"
dynamic = ["version"]
authors = [{ name = "A Good Programmer", email = "nospam@example.com" }]
requires-python = ">=3.12"
dependencies = ["<%= requirement %>"]

[tool.hatch.version]
path = "<%= path %>"

[tool.hatch.build.targets.wheel]
only-include = ["<%= path %>"]

[dependency-groups]
dev = ["pytest>=9", "pytest-xdist>=3"]

[tool.pytest.ini_options]
testpaths = ["t"]
pythonpath = ["."]

@@ agents
# <%= dir %>

A plugin of [Pyjoyment](https://pyjoyment.readthedocs.io/), the port of
Mojolicious to Python, made with `pyjo generate plugin`, a distribution of its
own. This file says how it is made, tested and built, for whoever changes it,
a coding agent too.

## Layout

- `<%= path %>`: the plugin `<%= class_ %>`, whose `register` adds its
  helpers, hooks and routes to an application, as `plugin('<%= name %>')`.
- `t/basic.py`: its test, with an application of `Pyjoyment.Lite`.
- `pyproject.toml`: the distribution, whose wheel has only the module, as the
  packages of the namespace are the ones of Pyjoyment.

## Commands

```sh
uv run python -m Pyjo.Prove -l -r t      # the tests
uv run pytest                            # the tests with pytest
uv build                                 # the wheel and the sdist in dist/
```

## Conventions

- The directories of the namespace have no `__init__.py`, which would
  replace the packages of Pyjoyment.
- `register` runs once, at the start of the application, and what the
  requests share is made there; nothing in a helper or a hook blocks the
  event loop, as `time.sleep` or `requests`.
- A change comes with a test in `t/`, where `Pyjo.Test.Pyjo` requests an
  application without a server.

## Skills

The plugin of Claude Code for Pyjoyment has skills of its idioms, of plugins
and distributions, of the tests and of the templates:

```sh
claude plugin install pyjoyment --marketplace pyjoyment/Pyjoyment
```

Other agents read their files, the `SKILL.md` of each skill, in
https://github.com/pyjoyment/Pyjoyment/tree/main/plugins/pyjoyment/skills.

@@ claude
@AGENTS.md
'''
