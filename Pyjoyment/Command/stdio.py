"""
Pyjoyment.Command.stdio - Standard input and output command
===========================================================
::

    Usage: APPLICATION stdio [OPTIONS]

      ./myapp.py stdio
      ./myapp.py stdio -m production

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

:mod:`Pyjoyment.Command.stdio` starts applications with the
:mod:`Pyjo.Server.Stdio` backend, which serves the protocol that the
application or a plugin gives with a subscriber of its event ``stream`` on
the standard input and output. It is not detected, as a pipe on the standard
input is too common to mean it.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.Server.Stdio
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

from typing import Any


class Pyjoyment_Command_stdio(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.stdio` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application on standard input and output'
    """::

        description = stdio.description
        stdio.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = stdio.usage
        stdio.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> Any:
        """::

            stdio.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not getopt(arguments, {}) or len(arguments):
            raise Pyjo.Exception.new(self.usage)
        return Pyjo.Server.Stdio.new(app=self.app).run()


new = Pyjoyment_Command_stdio.new
object = Pyjoyment_Command_stdio
