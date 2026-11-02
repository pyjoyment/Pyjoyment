"""
Pyjoyment.Command.routes - Routes command
=========================================
::

    Usage: APPLICATION routes [OPTIONS]

      ./myapp.py routes
      ./myapp.py routes -v

    Options:
      -h, --help                Show this summary of available options
          --home <path>         Path to home directory of your application,
                                defaults to the value of PYJO_HOME or
                                auto-detection
          --log-format <name>   Format of log messages, "text", "plain" without
                                time and process, or "json", defaults to the
                                value of PYJO_LOG_FORMAT or "text"
      -m, --mode <name>         Operating mode for your application, defaults to
                                the value of PYJO_MODE or "development"
      -v, --verbose             Print additional details about routes, flags
                                indicate C=Conditions, P=Partial, U=Under and
                                W=WebSocket

:mod:`Pyjoyment.Command.routes` lists all your application routes.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::routes
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/routes.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjoyment.Command
import Pyjoyment.Routes.Route

from Pyjo.Util import extract_usage, getopt, tablify

from typing import Any


class Pyjoyment_Command_routes(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.routes` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Show available routes'
    """::

        description = routes.description
        routes.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = routes.usage
        routes.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> None:
        """::

            routes.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not (opts := getopt(arguments, {'v|verbose': None})):
            raise Pyjo.Exception.new(self.usage)

        rows: list[list[str]] = []
        for route in self.app.routes.children:
            _walk(route, 0, rows, bool(opts.verbose))
        print(tablify(rows), end='')


def _walk(route: Pyjoyment.Routes.Route.object, depth: int, rows: list[list[str]], verbose: bool) -> None:
    # Pattern
    prefix = ''
    if i := depth * 2:
        prefix += ' ' * i + '+'
    row = [prefix + (route.pattern.unparsed or '/')]
    rows.append(row)

    # Flags
    flags: list[str] = []
    flags.append('C' if route.requires() else '.')
    flags.append('P' if (partial := route.partial) else '.')
    flags.append('U' if route.inline else '.')
    flags.append('W' if route.is_websocket else '.')
    if verbose:
        row.append(''.join(flags))

    # Methods
    methods: Any = route.methods()
    row.append(','.join(methods).upper() if methods else '*')

    # Name
    name = route.name or ''
    row.append(f'"{name}"' if route.has_custom_name else name)

    # Regex (verbose)
    pattern = route.pattern
    pattern.match('/', route.is_endpoint and not partial)
    if verbose:
        row.append(pattern.regex.pattern if pattern.regex is not None else '')

    depth += 1
    for child in route.children:
        _walk(child, depth, rows, verbose)
    depth -= 1


new = Pyjoyment_Command_routes.new
object = Pyjoyment_Command_routes
