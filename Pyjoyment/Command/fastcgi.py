"""
Pyjoyment.Command.fastcgi - FastCGI command
===========================================
::

    Usage: APPLICATION fastcgi [OPTIONS]

      ./myapp.py fastcgi

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

:mod:`Pyjoyment.Command.fastcgi` starts applications that a web server starts
as FastCGI applications, as Apache with ``mod_fcgid`` and lighttpd do: it
serves the listen socket that the web server gives the application as the
file descriptor ``0``, with :mod:`Pyjo.Server.Daemon` and
:mod:`Pyjo.Server.FastCGI`, and is detected by :mod:`Pyjoyment.Commands`
when the file descriptor ``0`` is such a socket. A FastCGI application that
listens on a socket of its own, which the web server connects to, is started
with the commands ``daemon`` and ``prefork`` and a listen location
``fcgi://`` or ``fcgi+unix://``.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious; :mod:`Pyjoyment.Command.cgi` is the
counterpart of `Mojolicious::Command::cgi
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/cgi.pm>`_.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.Server.Daemon
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

from typing import Any


class Pyjoyment_Command_fastcgi(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.fastcgi` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application with FastCGI of the web server'
    """::

        description = fastcgi.description
        fastcgi.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = fastcgi.usage
        fastcgi.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> Any:
        """::

            fastcgi.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not getopt(arguments, {}) or len(arguments):
            raise Pyjo.Exception.new(self.usage)

        # The listen socket of the web server, silent, as the web server does not read the output of the application
        Pyjo.Server.Daemon.new(app=self.app, listen=['fcgi://*?fd=0'], silent=True).run()


new = Pyjoyment_Command_fastcgi.new
object = Pyjoyment_Command_fastcgi
