"""
Pyjoyment.Commands - Command line interface
===========================================
::

    Usage: APPLICATION COMMAND [OPTIONS]

      pyjo version
      pyjo generate lite-app
      ./myapp.py daemon -m production -l http://*:8080
      ./myapp.py get /foo
      ./myapp.py routes -v

    Tip: CGI, FastCGI and AWS Lambda environments, and WSGI and ASGI ones with
         PYJO_WSGI and PYJO_ASGI, can be automatically detected very often and
         work without commands.

    Options (for all commands):
      -h, --help                Get more information on a specific command
          --home <path>         Path to home directory of your application,
                                defaults to the value of PYJO_HOME or
                                auto-detection
          --log-format <name>   Format of log messages, "text", "plain" without
                                time and process, or "json", defaults to the
                                value of PYJO_LOG_FORMAT or "text"
      -m, --mode <name>         Operating mode for your application, defaults to
                                the value of PYJO_MODE or "development"

:mod:`Pyjoyment.Commands` is the interactive command line interface for the
:mod:`Pyjoyment` framework. It will automatically detect available commands in
the ``Pyjoyment.Command`` and ``Pyjoyment.Command.Author`` namespaces.

The command line interface of :mod:`Pyjoyment.HelloWorld` is the ``pyjo``
script, or ``python -m Pyjoyment``.

Commands
--------

These commands are available by default.

asgi
~~~~
::

    application = app.start('asgi')

Use :mod:`Pyjoyment.Command.asgi` to start application with ASGI backend,
auto detected with the ``PYJO_ASGI`` environment variable.

cgi
~~~
::

    $ ./myapp.py cgi

Use :mod:`Pyjoyment.Command.cgi` to start application with CGI backend,
usually auto detected.

daemon
~~~~~~
::

    $ ./myapp.py daemon

Use :mod:`Pyjoyment.Command.daemon` to start application with standalone
HTTP and WebSocket server.

eval
~~~~
::

    $ ./myapp.py eval 'print(app.home)'

Use :mod:`Pyjoyment.Command.eval` to run code against application.

fastcgi
~~~~~~~
::

    $ ./myapp.py fastcgi

Use :mod:`Pyjoyment.Command.fastcgi` to start application with the FastCGI
of a web server that starts it, usually auto detected.

generate
~~~~~~~~
::

    $ pyjo generate
    $ pyjo generate help
    $ ./myapp.py generate help

List available generator commands with short descriptions. ::

    $ pyjo generate help <generator>
    $ ./myapp.py generate help <generator>

List available options for generator command with short descriptions.

generate app
~~~~~~~~~~~~
::

    $ pyjo generate app <AppName>

Use :mod:`Pyjoyment.Command.Author.generate.app` to generate application
directory structure for a fully functional :mod:`Pyjoyment` application.

generate dockerfile
~~~~~~~~~~~~~~~~~~~
::

    $ ./myapp.py generate dockerfile
    $ python -m MyApp generate dockerfile

Use :mod:`Pyjoyment.Command.Author.generate.dockerfile` to generate
``Dockerfile`` for application.

generate kubernetes
~~~~~~~~~~~~~~~~~~~
::

    $ ./myapp.py generate kubernetes
    $ python -m MyApp generate kubernetes

Use :mod:`Pyjoyment.Command.Author.generate.kubernetes` to generate the
manifests of Kubernetes for application, with the overlays of Kustomize for
development and production.

generate lambda-zip
~~~~~~~~~~~~~~~~~~~
::

    $ ./myapp.py generate lambda-zip
    $ python -m MyApp generate lambda-zip

Use :mod:`Pyjoyment.Command.Author.generate.lambda_zip` to generate the ZIP
files of an event function of AWS Lambda on a custom runtime, with a layer of
Python.

generate lite-app
~~~~~~~~~~~~~~~~~
::

    $ pyjo generate lite-app

Use :mod:`Pyjoyment.Command.Author.generate.lite_app` to generate a fully
functional :mod:`Pyjoyment.Lite` application.

generate plugin
~~~~~~~~~~~~~~~
::

    $ pyjo generate plugin <PluginName>

Use :mod:`Pyjoyment.Command.Author.generate.plugin` to generate directory
structure for a fully functional :mod:`Pyjoyment` plugin.

generate pyproject
~~~~~~~~~~~~~~~~~~
::

    $ pyjo generate pyproject
    $ ./myapp.py generate pyproject

Use :mod:`Pyjoyment.Command.Author.generate.pyproject` to generate
``pyproject.toml`` file for application.

get
~~~
::

    $ pyjo get https://mojolicious.org
    $ ./myapp.py get /foo

Use :mod:`Pyjoyment.Command.get` to perform requests to remote host or local
application.

help
~~~~
::

    $ pyjo
    $ pyjo help
    $ ./myapp.py help

List available commands with short descriptions. ::

    $ pyjo help <command>
    $ ./myapp.py help <command>

List available options for the command with short descriptions.

inflate
~~~~~~~
::

    $ ./myapp.py inflate

Use :mod:`Pyjoyment.Command.Author.inflate` to turn templates and static files
embedded in the ``DATA`` sections of your application into real files.

lambda
~~~~~~
::

    handler = app.start('lambda')

Use :mod:`Pyjoyment.Command.lambda` to start application as an event function
of AWS Lambda, auto detected with the ``AWS_LAMBDA_RUNTIME_API`` environment
variable.

prefork
~~~~~~~
::

    $ ./myapp.py prefork

Use :mod:`Pyjoyment.Command.prefork` to start application with standalone
pre-forking HTTP and WebSocket server.

prethread
~~~~~~~~~
::

    $ ./myapp.py prethread

Use :mod:`Pyjoyment.Command.prethread` to start application with standalone
pre-threading HTTP and WebSocket server.

routes
~~~~~~
::

    $ ./myapp.py routes

Use :mod:`Pyjoyment.Command.routes` to list application routes.

stdio
~~~~~
::

    $ ./myapp.py stdio

Use :mod:`Pyjoyment.Command.stdio` to start application on the standard input
and output, with the protocol that the application or a plugin gives.

version
~~~~~~~
::

    $ pyjo version
    $ ./myapp.py version

Use :mod:`Pyjoyment.Command.version` to show version information for
available core and optional modules, very useful for debugging.

wsgi
~~~~
::

    application = app.start('wsgi')

Use :mod:`Pyjoyment.Command.wsgi` to start application with WSGI backend,
auto detected with the ``PYJO_WSGI`` environment variable.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Commands <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Commands.pm>`_
of Mojolicious 9.49.

Classes
-------
"""

# Left out from Mojolicious: the command cpanify, as uv publish uploads distributions to PyPI

import Pyjo.Exception
import Pyjo.GetOpt
import Pyjo.Loader
import Pyjo.Server
import Pyjoyment.Command

from Pyjo.Util import getopt, setenv, tablify

import errno
import os
import re
import socket
import sys

from collections.abc import Sequence
from typing import Any


class Pyjoyment_Commands(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Commands` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    hint: str = "\nSee 'APPLICATION help COMMAND' for more information on a specific command.\n"
    """::

        hint = commands.hint
        commands.hint = 'Foo'

    Short hint shown after listing available commands.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._message: str | None = None
        self.namespaces: list[str] = ['Pyjoyment.Command.Author', 'Pyjoyment.Command']
        """::

            namespaces = commands.namespaces
            commands.namespaces = ['MyApp.Command']

        Namespaces to load commands from, defaults to
        ``Pyjoyment.Command.Author`` and ``Pyjoyment.Command``. ::

            # Add another namespace to load commands from
            commands.namespaces.append('MyApp.Command')
        """
        super().__init__(**kwargs)

    @property
    def message(self) -> str:
        """::

            msg = commands.message
            commands.message = 'Hello World!'

        Short usage message shown before listing available commands.
        """
        if self._message is None:
            self._message = self.extract_usage() + '\nCommands:\n'
        return self._message

    @message.setter
    def message(self, value: str) -> None:
        self._message = value

    @staticmethod
    def detect() -> str | None:
        """::

            env = commands.detect()

        Try to detect environment, or return ``None`` if none could be
        detected.
        """
        # WSGI
        # Renamed from Mojolicious: PYJO_WSGI, as WSGI has no environment variable of its own, where Mojo detects PSGI
        # with PLACK_ENV
        if os.environ.get('PYJO_WSGI') is not None:
            return 'wsgi'

        # Not in Mojolicious: ASGI, with PYJO_ASGI
        if os.environ.get('PYJO_ASGI') is not None:
            return 'asgi'

        # Not in Mojolicious: an event function of AWS Lambda, whose runtime has the endpoint of its API
        if os.environ.get('AWS_LAMBDA_RUNTIME_API') is not None:
            return 'lambda'

        # Not in Mojolicious: FastCGI, whose web server gives the application its listen socket as the file descriptor 0
        if _fastcgi():
            return 'fastcgi'

        # CGI
        if os.environ.get('PATH_INFO') is not None or os.environ.get('GATEWAY_INTERFACE') is not None:
            return 'cgi'

        # Nothing
        return None

    def run(self, name: str | None = None, *args: str) -> Any:
        """::

            commands.run()
            commands.run(*sys.argv[1:])

        Load and run commands. Automatic deployment environment detection can
        be disabled with the ``PYJO_NO_DETECT`` environment variable. A
        detected environment, CGI, FastCGI, AWS Lambda, or WSGI and ASGI with
        the ``PYJO_WSGI`` and ``PYJO_ASGI`` environment variables, runs its
        command, whatever the arguments are, as a WSGI or an ASGI server and
        AWS Lambda import the script of the application with their own
        arguments. ::

            # The WSGI application of a script, for PYJO_WSGI=1 gunicorn myapp:application
            application = app.start()
        """
        # Application loader
        # Not in Mojolicious: the application for Pyjo.Server.load_app, which Mojo returns from the script
        if os.environ.get('PYJO_APP_LOADER') is not None:
            Pyjo.Server.loaded_app = self.app
            return self.app

        # Try to detect environment
        if not os.environ.get('PYJO_NO_DETECT') and (env := self.detect()):
            name = env

        # Run command
        arguments = list(args)
        if name and re.fullmatch(r'\w[\w-]+', name) and (name != 'help' or arguments):
            # Help
            help = name == 'help'
            if help:
                name = arguments.pop(0)
            saved = os.environ.get('PYJO_HELP')
            help = bool(saved) or help
            setenv('PYJO_HELP', '1' if help else None)
            try:
                name = name.replace('-', '_')

                # Remove options shared by all commands before loading the command
                _args(arguments)
                module = None
                for namespace in self.namespaces:
                    if module := _command(f'{namespace}.{name}', True):
                        break

                # Unknown command
                if not module:
                    raise Pyjo.Exception.new(f'Unknown command "{name}", maybe you need to install it?\n')

                # Run command
                app = self.app
                command = module.new(app=app)
                if help:
                    return command.help(*arguments)
                app.plugins.emit_hook('before_command', command, arguments)
                return command.run(*arguments)
            finally:
                setenv('PYJO_HELP', saved)

        elif name and name not in ('help', '--help', '-h'):
            raise Pyjo.Exception.new(f'Invalid command "{name}".\n')

        # Hide list for tests
        # Renamed from Mojolicious: PYJO_HARNESS_ACTIVE, which Pyjo.Prove sets, as prove sets HARNESS_ACTIVE
        if os.environ.get('PYJO_HARNESS_ACTIVE', '0') not in ('', '0'):
            return True

        # Find all available commands
        all: dict[str, str] = {}
        for namespace in self.namespaces:
            for module in [*Pyjo.Loader.find_modules(namespace), *Pyjo.Loader.find_packages(namespace)]:
                if (cls := _command(module)) is not None:
                    all.setdefault(module[len(namespace) + 1 :], cls.new().description)

        rows = [[' ' + re.sub(r'(?<!^)_', '-', name), all[name]] for name in sorted(all)]
        print(self.message, tablify(rows), self.hint, sep='', end='')
        return True

    @staticmethod
    def start_app(app: str | type, *args: str) -> Any:
        """::

            Pyjoyment.Commands.start_app('MyApp')
            Pyjoyment.Commands.start_app('MyApp', *sys.argv[1:])

        Load application from class and start the command line interface for
        it. Note that the options ``-h``/``--help``, ``--home`` and
        ``-m``/``--mode``, which are shared by all commands, will be parsed
        from ``sys.argv`` when the module is imported. ::

            # Always start daemon for application
            Pyjoyment.Commands.start_app('MyApp', 'daemon', '-l', 'http://*:8080')
        """
        application: Any = Pyjo.Server.new().build_app(app)
        return application.start(*args)


# Command line options for PYJO_HELP, PYJO_HOME, PYJO_LOG_FORMAT and PYJO_MODE
def _args(args: list[str]) -> None:
    if not Pyjoyment_Commands.detect():
        getopt(
            args,
            {
                'h|help': Pyjo.GetOpt.env('PYJO_HELP'),
                'home=s': Pyjo.GetOpt.env('PYJO_HOME'),
                # Not in Mojolicious: the format of the log messages of Pyjo.Log, text or JSON
                'log-format=s': Pyjo.GetOpt.env('PYJO_LOG_FORMAT'),
                'm|mode=s': Pyjo.GetOpt.env('PYJO_MODE'),
            },
            pass_through=True,
        )


def _command(module: str, fatal: bool = False) -> type[Pyjoyment.Command.object] | None:
    if not (e := Pyjo.Loader.load_class(module)):
        cls = Pyjo.Loader._class(module)  # pyright: ignore[reportPrivateUsage]
        return cls if cls is not None and issubclass(cls, Pyjoyment.Command.object) else None
    if fatal and isinstance(e, Exception):
        raise e
    return None


# Not in Mojolicious: the file descriptor 0 is a listen socket, which has no peer, as the specification of FastCGI tells
# an application to check
def _fastcgi() -> bool:
    try:
        fd = os.dup(0)
    except OSError:
        return False
    try:
        handle = socket.socket(fileno=fd)
    except OSError:
        os.close(fd)
        return False
    with handle:
        try:
            handle.getpeername()
        except OSError as e:
            return e.errno == errno.ENOTCONN
    return False


# Do not remove options from sys.argv
_args(sys.argv[1:])


# Not in Mojolicious: script/mojo, the command line interface of Pyjoyment.HelloWorld
def main(argv: Sequence[str] | None = None) -> None:
    """::

        main(['version'])

    The command line interface of the ``pyjo`` script: start the command line
    interface of :mod:`Pyjoyment.HelloWorld`.
    """
    start_app('Pyjoyment.HelloWorld', *(argv or ()))


start_app = Pyjoyment_Commands.start_app


new = Pyjoyment_Commands.new
object = Pyjoyment_Commands
Commands = Pyjoyment_Commands
