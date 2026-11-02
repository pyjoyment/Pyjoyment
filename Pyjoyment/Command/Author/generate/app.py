"""
Pyjoyment.Command.Author.generate.app - App generator command
=============================================================
::

    Usage: APPLICATION generate app [OPTIONS] [NAME]

      pyjo generate app
      pyjo generate app TestApp
      pyjo generate app My.TestApp

    Options:
      -h, --help   Show this summary of available options

:mod:`Pyjoyment.Command.Author.generate.app` generates application directory
structures for fully functional :mod:`Pyjoyment` applications: the package of
the application in the directory of the project, which is its home, with
``pyproject.toml`` for its dependencies, so that
``uv run python -m MyApp daemon`` starts it and
``uv run python -m Pyjo.Prove -l -r t`` tests it, as does ``uv run pytest``,
with pytest of the dependency group ``dev``, and ``AGENTS.md``, which
``CLAUDE.md`` imports, tells a coding agent how the application is made, run
and tested, and where the skills of Pyjoyment are.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::Author::generate::app
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/Author/generate/app.pm>`_ of
Mojolicious 9.49.

Classes
-------
"""

import Pyjoyment.Command
import Pyjoyment.Command.Author.generate.pyproject

from Pyjo.Util import class_to_file, class_to_path, decamelize, extract_usage
from Pyjoyment.Command.Author.generate.pyproject import _requirement  # pyright: ignore[reportPrivateUsage]


class Pyjoyment_Command_Author_generate_app(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.Author.generate.app` inherits all attributes and
    methods from :mod:`Pyjoyment.Command` and implements the following new
    ones.
    """

    description = 'Generate Pyjoyment application directory structure'
    """::

        description = app.description
        app.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = app.usage
        app.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, class_: str | None = None, *args: str) -> None:
        """::

            app.run(*sys.argv[1:])

        Run this command.
        """
        class_ = class_ or 'MyApp'

        # Script
        # Renamed from Mojolicious: the __main__ module of the package, for python -m, where Mojo has script/my_app
        name = class_to_file(class_)
        package = class_.replace('.', '/')
        self.render_to_rel_file('main', f'{name}/{package}/__main__.py', {'class_': class_})

        # Application class
        # Unlike Mojolicious: a package in the directory of the project, as the current directory is on sys.path, where
        # Mojo has the lib directory
        self.render_to_rel_file(
            'appclass', f'{name}/{package}/__init__.py', {'class_': _identifier(class_), 'alias': _alias(class_)}
        )

        # Config file (using the default moniker)
        self.render_to_rel_file('config', f'{name}/{decamelize(class_.replace(".", "::"))}.yml')

        # Controller
        controller = f'{class_}.Controller.Example'
        path = class_to_path(controller)
        self.render_to_rel_file(
            'controller', f'{name}/{path}', {'class_': _identifier(controller), 'alias': _alias(controller)}
        )

        # Test
        # Renamed from Mojolicious: t/basic.py, where Mojo has t/basic.t
        self.render_to_rel_file('test', f'{name}/t/basic.py', {'class_': class_})

        # Not in Mojolicious: pyproject.toml, with the dependencies, as Mojo leaves Makefile.PL to generate makefile
        pyproject = Pyjoyment.Command.Author.generate.pyproject.new(app=self.app, quiet=self.quiet)
        pyproject.render_to_rel_file(
            'pyproject', f'{name}/pyproject.toml', {'name': name, 'requirement': _requirement(), 'tests': True}
        )

        # Static file
        self.render_to_rel_file('static', f'{name}/public/index.html')
        self.create_rel_dir(f'{name}/public/assets')

        # Templates
        self.render_to_rel_file('layout', f'{name}/templates/layouts/default.html.ep')
        self.render_to_rel_file('welcome', f'{name}/templates/example/welcome.html.ep')

        # Not in Mojolicious: the guide of the coding agents, AGENTS.md, which CLAUDE.md imports for Claude Code
        config = f'{decamelize(class_.replace(".", "::"))}.yml'
        self.render_to_rel_file('agents', f'{name}/AGENTS.md', {'class_': class_, 'config': config, 'package': package})
        self.render_to_rel_file('claude', f'{name}/CLAUDE.md')


# Not in Mojolicious: the name of the class in its module, with underscores, as Pyjo_URL is of Pyjo.URL
def _identifier(class_: str) -> str:
    return class_.replace('.', '_')


# Not in Mojolicious: the name of the class for the constructor of Python, the last part of its module, as Path is of
# Pyjo.Path
def _alias(class_: str) -> str:
    return class_.rsplit('.', 1)[-1]


new = Pyjoyment_Command_Author_generate_app.new
object = Pyjoyment_Command_Author_generate_app

__DATA__ = r"""
@@ main
import Pyjoyment.Commands


# Start command line interface for application
Pyjoyment.Commands.start_app('<%= class_ %>')

@@ appclass
import Pyjoyment


class <%= class_ %>(Pyjoyment.object):
    # This method will run once at server start
    def startup(self):
        # Load configuration from config file
        config = self.plugin('YAMLConfig')

        # Configure the application
        self.secrets = config.get('secrets')

%# Not in Mojolicious: the plugin Health, whose endpoints the probes of containers and orchestrators request
        # Liveness and readiness for containers and orchestrators
        self.plugin('Health')

        # Router
        r = self.routes

        # Normal route to controller
        r.get('/').to('Example#welcome')


new = <%= class_ %>.new
object = <%= class_ %>
% if alias != class_:
<%= alias %> = <%= class_ %>
% end

@@ controller
import Pyjoyment.Controller


class <%= class_ %>(Pyjoyment.Controller.object):
    # This action will render a template
    def welcome(self):
        # Render template "example/welcome.html.ep" with message
        self.render(msg='Welcome to the Pyjoyment real-time web framework!')


object = <%= class_ %>
<%= alias %> = <%= class_ %>

@@ static
<!DOCTYPE html>
<html>
  <head>
    <title>Welcome to the Pyjoyment real-time web framework!</title>
  </head>
  <body>
    <h2>Welcome to the Pyjoyment real-time web framework!</h2>
    This is the static document "public/index.html",
    <a href="/">click here</a> to get back to the start.
  </body>
</html>

@@ test
from Pyjo.Test import *

import Pyjo.Test.Pyjo


t = Pyjo.Test.Pyjo.new('<%= class_ %>')
t.get_ok('/').status_is(200).content_like(r'(?i)Pyjoyment')

done_testing()

@@ layout
<!DOCTYPE html>
<html>
  <head><title><%%= c.title() %></title></head>
  <body><%%= content() %></body>
</html>

@@ welcome
%% c.layout('default')
%% c.title('Welcome')
<h2><%%= msg %></h2>
<p>
  This page was generated from the template "templates/example/welcome.html.ep"
  and the layout "templates/layouts/default.html.ep",
  <%%= link_to('click here', url_for()) %> to reload the page or
  <%%= link_to('here', '/index.html') %> to move forward to a static page.
</p>

@@ config
% from Pyjo.Util import generate_secret
---
secrets:
  - <%= generate_secret() %>

@@ agents
# <%= class_ %>

An application of [Pyjoyment](https://pyjoyment.readthedocs.io/), the port of
Mojolicious to Python, made with `pyjo generate app`. This file says how it is
made and run, for whoever changes it, a coding agent too.

## Layout

- `<%= package %>/__init__.py`: the application, whose `startup` loads the
  configuration and sets up the routes, as `r.get('/').to('Example#welcome')`.
- `<%= package %>/Controller/`: the controllers, a class for each, whose
  methods are the actions.
- `templates/`: the `ep` templates of the actions, as
  `templates/example/welcome.html.ep`, and the layouts.
- `public/`: the static files.
- `<%= config %>`: the configuration, with the secrets of the sessions.
- `t/`: the test scripts of `Pyjo.Test` and `Pyjo.Test.Pyjo`.

## Commands

```sh
% for command, comment in ((f'python -m {class_} daemon', 'http://127.0.0.1:3000'), (f'python -m {class_} routes', 'the routes and their names'), (f'python -m {class_} get /', 'a request without a server'), ('python -m Pyjo.Prove -l -r t', 'the tests'), ('pytest', 'the tests with pytest')):
<%= f'uv run {command}'.ljust(max(41, len(class_) + 36)) %># <%= comment %>
% end
```

## Conventions

- An action renders its response with `self.render(...)`, as
  `self.render(json={...})`; what it returns is not the response.
- One event loop serves every connection: an action that waits is an
  `async def` that awaits promises, as `await self.ua().get_p(url)`, and
  nothing blocks it, as `time.sleep` or `requests`.
- A helper is called, `self.ua()`, not `self.ua`.
- A change comes with a test in `t/`, where `Pyjo.Test.Pyjo` requests the
  application without a server.

## Skills

The plugin of Claude Code for Pyjoyment has skills of its idioms, of the
migration from Flask, FastAPI and Django, of the tests, the templates, the
APIs and the deployment:

```sh
claude plugin install pyjoyment --marketplace pyjoyment/Pyjoyment
```

Other agents read their files, the `SKILL.md` of each skill, in
https://github.com/pyjoyment/Pyjoyment/tree/main/plugins/pyjoyment/skills.

@@ claude
@AGENTS.md
"""
