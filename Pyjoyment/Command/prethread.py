"""
Pyjoyment.Command.prethread - Pre-thread command
================================================
::

    Usage: APPLICATION prethread [OPTIONS]

      ./myapp.py prethread
      ./myapp.py prethread -m production -p -l http://*:8080
      ./myapp.py prethread -l http://127.0.0.1:8080 -l https://[::]:8081
      ./myapp.py prethread -l 'https://*:443?cert=./server.crt&key=./server.key'
      ./myapp.py prethread -l http+unix://%2Ftmp%2Fmyapp.sock -w 12
      ./myapp.py prethread -l fcgi://127.0.0.1:9000
      ./myapp.py prethread -l http://127.0.0.1:8080 -p 127.0.0.0/8 -p fc00::/7

    Options:
      -a, --accepts <number>               Number of connections for workers to
                                           accept, defaults to 10000
      -b, --backlog <size>                 Listen backlog size, defaults to
                                           SOMAXCONN
      -c, --clients <number>               Maximum number of concurrent
                                           connections, defaults to 1000
      -G, --graceful-timeout <seconds>     Graceful timeout, defaults to 25.
      -I, --heartbeat-interval <seconds>   Heartbeat interval, defaults to 5
      -H, --heartbeat-timeout <seconds>    Heartbeat timeout, defaults to 50
      -h, --help                           Show this summary of available options
          --home <path>                    Path to home directory of your
                                           application, defaults to the value of
                                           PYJO_HOME or auto-detection
      -i, --inactivity-timeout <seconds>   Inactivity timeout, defaults to the
                                           value of PYJO_INACTIVITY_TIMEOUT or 30
      -k, --keep-alive-timeout <seconds>   Keep-alive timeout, defaults to the
                                           value of PYJO_KEEP_ALIVE_TIMEOUT or 5
      -l, --listen <location>              One or more locations you want to
                                           listen on, defaults to the value of
                                           PYJO_LISTEN, the port of PORT or
                                           "http://*:3000"
          --log-format <name>              Format of log messages, "text",
                                           "plain" without time and process, or
                                           "json", defaults to the value of
                                           PYJO_LOG_FORMAT or "text"
      -m, --mode <name>                    Operating mode for your application,
                                           defaults to the value of PYJO_MODE or
                                           "development"
      -P, --pid-file <path>                Path to process id file, defaults to
                                           "prethread.pid" in a temporary
                                           directory
      -p, --proxy [<network>]              Activate reverse proxy support,
                                           defaults to the value of
                                           PYJO_REVERSE_PROXY, optionally takes
                                           one or more trusted proxy addresses or
                                           networks
      -r, --requests <number>              Maximum number of requests per
                                           keep-alive connection, defaults to 100
      -S, --shutdown-delay <seconds>       Time to keep serving after INT or TERM
                                           before shutting down gracefully,
                                           defaults to 0
      -s, --spare <number>                 Temporarily spawn up to this number of
                                           additional workers, defaults to 2
      -w, --workers <number>               Number of workers, defaults to 4

:mod:`Pyjoyment.Command.prethread` starts applications with the
:mod:`Pyjo.Server.Prethread` backend, with the options of
:mod:`Pyjoyment.Command.prefork`.

An option that is not given has the value of the environment variable of
``PYJO_`` and its name, as ``PYJO_WORKERS`` for ``--workers``, with the
values of ``--listen`` and ``--proxy`` separated by commas, see
:mod:`Pyjo.GetOpt`, so that the environment of a container or a platform
can tune the server. ::

    PYJO_GRACEFUL_TIMEOUT=8 PYJO_WORKERS=2 ./myapp.py prethread

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjo.Server.Prethread`, :mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious; it is inspired by
:mod:`Pyjoyment.Command.prefork`, the counterpart of `Mojolicious::Command::prefork
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/prefork.pm>`_.

Classes
-------
"""

import Pyjo.Server.Prethread
import Pyjoyment.Command.prefork

from Pyjo.Util import extract_usage


class Pyjoyment_Command_prethread(Pyjoyment.Command.prefork.object):
    """
    :mod:`Pyjoyment.Command.prethread` inherits all attributes and methods from
    :mod:`Pyjoyment.Command.prefork` and implements the following new ones.
    """

    description = 'Start application with pre-threading HTTP and WebSocket server'
    """::

        description = prethread.description
        prethread.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = prethread.usage
        prethread.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    _server = Pyjo.Server.Prethread.object


new = Pyjoyment_Command_prethread.new
object = Pyjoyment_Command_prethread
