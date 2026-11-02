"""
Pyjoyment.Command.cgi - CGI command
===================================
::

    Usage: APPLICATION cgi [OPTIONS]

      ./myapp.py cgi

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
          --nph                 Enable non-parsed-header mode

:mod:`Pyjoyment.Command.cgi` starts applications with the
:mod:`Pyjo.Server.CGI` backend.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::cgi
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/cgi.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.Server.CGI
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

from typing import Any


class Pyjoyment_Command_cgi(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.cgi` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application with CGI'
    """::

        description = cgi.description
        cgi.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = cgi.usage
        cgi.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> Any:
        """::

            cgi.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not (opts := getopt(arguments, {'nph': None})):
            raise Pyjo.Exception.new(self.usage)
        return Pyjo.Server.CGI.new(app=self.app, nph=bool(opts.nph)).run()


new = Pyjoyment_Command_cgi.new
object = Pyjoyment_Command_cgi
