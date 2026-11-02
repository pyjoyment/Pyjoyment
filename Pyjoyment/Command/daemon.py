"""
Pyjoyment.Command.daemon - Daemon command
=========================================
::

    Usage: APPLICATION daemon [OPTIONS]

      ./myapp.py daemon
      ./myapp.py daemon -m production -p -l http://*:8080
      ./myapp.py daemon -l http://127.0.0.1:8080 -l https://[::]:8081
      ./myapp.py daemon -l 'https://*:443?cert=./server.crt&key=./server.key'
      ./myapp.py daemon -l http+unix://%2Ftmp%2Fmyapp.sock
      ./myapp.py daemon -l fcgi://127.0.0.1:9000
      ./myapp.py daemon -l http://127.0.0.1:8080 -p 127.0.0.0/8 -p fc00::/7

    Options:
      -b, --backlog <size>                 Listen backlog size, defaults to
                                           SOMAXCONN
      -c, --clients <number>               Maximum number of concurrent
                                           connections, defaults to 1000
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

:mod:`Pyjoyment.Command.daemon` starts applications with the
:mod:`Pyjo.Server.Daemon` backend.

An option that is not given has the value of the environment variable of
``PYJO_`` and its name, as ``PYJO_CLIENTS`` for ``--clients``, with the
values of ``--listen`` and ``--proxy`` separated by commas, see
:mod:`Pyjo.GetOpt`, so that the environment of a container or a platform
can tune the server. ::

    PYJO_CLIENTS=100 ./myapp.py daemon

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::daemon
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/daemon.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.Server.Daemon
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

from typing import Any


class Pyjoyment_Command_daemon(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.daemon` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application with HTTP and WebSocket server'
    """::

        description = daemon.description
        daemon.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = daemon.usage
        daemon.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def build_server(self, *args: str) -> Pyjo.Server.Daemon.object:
        """::

            server = daemon.build_server(*sys.argv[1:])

        Build :mod:`Pyjo.Server.Daemon` instance from command line arguments.
        """
        arguments = list(args)
        daemon = Pyjo.Server.Daemon.new(app=self.app)
        listen: list[str] = []
        proxy: list[str] = []
        # Not in Mojolicious: the options from the environment variables of their names
        if not getopt(
            arguments,
            {
                'b|backlog=i': lambda name, value: setattr(daemon, 'backlog', value),
                'c|clients=i': lambda name, value: setattr(daemon, 'max_clients', value),
                'i|inactivity-timeout=i': lambda name, value: setattr(daemon, 'inactivity_timeout', value),
                'k|keep-alive-timeout=i': lambda name, value: setattr(daemon, 'keep_alive_timeout', value),
                'l|listen=s': listen,
                'p|proxy:s': proxy,
                'r|requests=i': lambda name, value: setattr(daemon, 'max_requests', value),
                # Not in Mojolicious: the delay of the graceful shutdown, while the readiness fails
                'S|shutdown-delay=i': lambda name, value: setattr(daemon, 'shutdown_delay', value),
            },
            env_prefix='PYJO_',
        ):
            raise Pyjo.Exception.new(self.usage)

        if listen:
            daemon.listen = listen
        if proxy:
            daemon.reverse_proxy = True
        if trusted := [p for p in proxy if p]:
            daemon.trusted_proxies = trusted
        return daemon

    def run(self, *args: str) -> Any:
        """::

            daemon.run(*sys.argv[1:])

        Run this command.
        """
        return self.build_server(*args).run()


new = Pyjoyment_Command_daemon.new
object = Pyjoyment_Command_daemon
