"""
Pyjoyment.Command.reload - Reload command
=========================================
::

    Usage: APPLICATION reload [OPTIONS] [COMMAND] [ARGS]

      ./myapp.py reload
      ./myapp.py reload prefork -w 1
      ./myapp.py reload -l http://127.0.0.1:8080 -w assets/css prefork -w 3
      ./myapp.py reload -m production -l https://*:443 -l http://[::]:3000
      ./myapp.py reload -w /usr/local/lib -w public -w myapp.conf
      ./myapp.py reload -x 'npx webpack --watch'
      python -m MyApp reload

    Options:
      -b, --backend <name>           Reload backend to use for reloading,
                                     defaults to "Poll"
      -h, --help                     Show this summary of available options
          --home <path>              Path to home directory of your application,
                                     defaults to the value of PYJO_HOME or
                                     auto-detection
      -l, --listen <location>        One or more locations you want to listen on,
                                     defaults to the value of PYJO_LISTEN, the
                                     port of PORT or "http://*:3000"
          --log-format <name>        Format of log messages, "text", "plain"
                                     without time and process, or "json",
                                     defaults to the value of PYJO_LOG_FORMAT or
                                     "text"
      -m, --mode <name>              Operating mode for your application,
                                     defaults to the value of PYJO_MODE or
                                     "development"
      -v, --verbose                  Print details about what files changed to
                                     sys.stdout
      -w, --watch <directory/file>   One or more directories and files to watch
                                     for changes, defaults to the application
                                     script, the package of the application in
                                     its home, as well as the "lib" and
                                     "templates" directories in the current
                                     working directory
      -x, --exec <command>           One or more shell commands to start
                                     alongside the server, like asset bundlers in
                                     watch mode

:mod:`Pyjoyment.Command.reload` starts applications with the
:mod:`Pyjo.Server.Reload` restarter, as ``pyjo-reload`` does, with the
script of the application that runs the command: the script of
:mod:`Pyjoyment.Lite`, or the ``__main__`` module of the package of an
application, which ``python -m`` runs, whose package is watched too. The
server command defaults to ``daemon``, and all options of the command need to
come before it.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.GetOpt
import Pyjo.Server.Reload
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

import os
import sys

from typing import NoReturn


# Not in Mojolicious: Mojo starts Mojo::Server::Morbo only with script/morbo
class Pyjoyment_Command_reload(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.reload` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application with auto-restarting development server'
    """::

        description = reload.description
        reload.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = reload.usage
        reload.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    @property
    def script(self) -> str:
        """::

            path = reload.script

        The script of the application, which :mod:`Pyjo.Server.Reload` runs
        with the server command: the one of ``PYJO_EXE``, as
        :mod:`Pyjoyment.Lite` sets it, or the one that Python runs, as the
        ``__main__`` module of a package for ``python -m``.
        """
        return os.environ.get('PYJO_EXE') or sys.argv[0]

    def build_server(self, *args: str) -> Pyjo.Server.Reload.object:
        """::

            reload = reload.build_server(*sys.argv[1:])

        Build :mod:`Pyjo.Server.Reload` instance from command line arguments,
        the options before the server command.
        """
        return self._build(list(args))

    def run(self, *args: str) -> NoReturn:
        """::

            reload.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        server = self._build(arguments)
        script = self.script
        if not os.path.isfile(script):
            raise Pyjo.Exception.new(f"Can't find the script of the application: {script}\n")
        server.run(script, *arguments)

    # The options of pyjo-reload, but the ones that all commands share, which Pyjoyment.Commands parses; the arguments
    # after them are the server command
    def _build(self, arguments: list[str]) -> Pyjo.Server.Reload.object:
        server = Pyjo.Server.Reload.new()
        exec: list[str] = []
        listen: list[str] = []
        watch: list[str] = []
        if not getopt(
            arguments,
            {
                'b|backend=s': Pyjo.GetOpt.env('PYJO_RELOAD_BACKEND'),
                'l|listen=s': listen,
                'v|verbose': lambda name, value: setattr(server, 'silent', False),
                'w|watch=s': watch,
                'x|exec=s': exec,
            },
            require_order=True,
        ):
            raise Pyjo.Exception.new(self.usage)

        if listen:
            server.daemon.listen = listen
        server.backend.watch = watch or [*server.backend.watch, *self._package()]
        if exec:
            server.exec = exec
        return server

    # The directory of the package of the application, when it is in the home of the application, and not one of
    # Pyjoyment itself, as the classes of Pyjoyment.Lite and of the default application of the command pyjo are, whose
    # home can be a checkout of Pyjoyment
    def _package(self) -> list[str]:
        name = type(self.app).__module__
        module = sys.modules.get(name)
        file = getattr(module, '__file__', None)
        if not file or name == '__main__' or name.split('.')[0] == 'Pyjoyment':
            return []
        package, home = os.path.dirname(os.path.abspath(file)), os.path.abspath(self.app.home)
        return [package] if os.path.commonpath([package, home]) == home else []


new = Pyjoyment_Command_reload.new
object = Pyjoyment_Command_reload
