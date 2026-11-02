"""
Pyjoyment.Command.asgi - ASGI command
=====================================
::

    Usage: APPLICATION asgi [OPTIONS]

      application = app.start('asgi')
      PYJO_ASGI=1 uvicorn myapp:application

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

:mod:`Pyjoyment.Command.asgi` starts applications with the
:mod:`Pyjo.Server.ASGI` backend: it returns the ASGI application, which a
script keeps for the ASGI server that imports it. The script of an application
that ends with ``application = app.start()`` runs this command when the
``PYJO_ASGI`` environment variable is set, and the command of its arguments
otherwise.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Inspired by `Mojolicious::Command::psgi
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/psgi.pm>`_ of Mojolicious 9.49, for ASGI.

Classes
-------
"""

# Not in Mojolicious: the command of ASGI, as Pyjoyment.Command.wsgi of WSGI

import Pyjo.Server.ASGI
import Pyjoyment.Command

from Pyjo.Util import extract_usage

from typing import Any


class Pyjoyment_Command_asgi(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.asgi` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application with ASGI'
    """::

        description = asgi.description
        asgi.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = asgi.usage
        asgi.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> Any:
        """::

            application = asgi.run()

        Run this command.
        """
        return Pyjo.Server.ASGI.new(app=self.app).to_asgi_app()


new = Pyjoyment_Command_asgi.new
object = Pyjoyment_Command_asgi
