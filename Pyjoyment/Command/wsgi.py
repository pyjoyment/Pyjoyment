"""
Pyjoyment.Command.wsgi - WSGI command
=====================================
::

    Usage: APPLICATION wsgi [OPTIONS]

      application = app.start('wsgi')
      PYJO_WSGI=1 gunicorn myapp:application

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

:mod:`Pyjoyment.Command.wsgi` starts applications with the
:mod:`Pyjo.Server.WSGI` backend: it returns the WSGI application, which a
script keeps for the WSGI server that imports it. The script of an application
that ends with ``application = app.start()`` runs this command when the
``PYJO_WSGI`` environment variable is set, and the command of its arguments
otherwise.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::psgi
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/psgi.pm>`_ of Mojolicious 9.49, for WSGI
instead of PSGI.

Classes
-------
"""

# Renamed from Mojolicious: wsgi, where Mojo has psgi, as WSGI is the PSGI of Python

import Pyjo.Server.WSGI
import Pyjoyment.Command

from Pyjo.Util import extract_usage

from typing import Any


class Pyjoyment_Command_wsgi(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.wsgi` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application with WSGI'
    """::

        description = wsgi.description
        wsgi.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = wsgi.usage
        wsgi.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> Any:
        """::

            application = wsgi.run()

        Run this command.
        """
        return Pyjo.Server.WSGI.new(app=self.app).to_wsgi_app()


new = Pyjoyment_Command_wsgi.new
object = Pyjoyment_Command_wsgi
