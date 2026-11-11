"""
Pyjoyment.Command.prefork - Pre-fork command
============================================
::

    Usage: APPLICATION prefork [OPTIONS]

      ./myapp.py prefork
      ./myapp.py prefork -m production -p -l http://*:8080
      ./myapp.py prefork -l http://127.0.0.1:8080 -l https://[::]:8081
      ./myapp.py prefork -l 'https://*:443?cert=./server.crt&key=./server.key'
      ./myapp.py prefork -l http+unix://%2Ftmp%2Fmyapp.sock -w 12
      ./myapp.py prefork -l fcgi://127.0.0.1:9000
      ./myapp.py prefork -l http://127.0.0.1:8080 -p 127.0.0.0/8 -p fc00::/7

    Options:
      -a, --accepts <number>               Number of connections for workers to
                                           accept, less up to half at random,
                                           defaults to 10000
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
                                           "prefork.pid" in a temporary directory
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

:mod:`Pyjoyment.Command.prefork` starts applications with the
:mod:`Pyjo.Server.Prefork` backend.

An option that is not given has the value of the environment variable of
``PYJO_`` and its name, as ``PYJO_WORKERS`` for ``--workers``, with the
values of ``--listen`` and ``--proxy`` separated by commas, see
:mod:`Pyjo.GetOpt`, so that the environment of a container or a platform
can tune the server. ::

    PYJO_GRACEFUL_TIMEOUT=8 PYJO_WORKERS=2 ./myapp.py prefork

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::prefork
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/prefork.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.Server.Prefork
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

from typing import Any


class Pyjoyment_Command_prefork(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.prefork` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Start application with pre-forking HTTP and WebSocket server'
    """::

        description = prefork.description
        prefork.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = prefork.usage
        prefork.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    # Not in Mojolicious: the class of the server, which Pyjoyment.Command.prethread replaces
    _server: type[Pyjo.Server.Prefork.object] = Pyjo.Server.Prefork.object

    def build_server(self, *args: str) -> Pyjo.Server.Prefork.object:
        """::

            server = prefork.build_server(*sys.argv[1:])

        Build :mod:`Pyjo.Server.Prefork` instance from command line arguments.
        """
        arguments = list(args)
        prefork = self._server.new(app=self.app)
        listen: list[str] = []
        proxy: list[str] = []
        # Not in Mojolicious: the options from the environment variables of their names
        if not getopt(
            arguments,
            {
                'a|accepts=i': lambda name, value: setattr(prefork, 'accepts', value),
                'b|backlog=i': lambda name, value: setattr(prefork, 'backlog', value),
                'c|clients=i': lambda name, value: setattr(prefork, 'max_clients', value),
                # Unlike Mojolicious: the graceful timeout defaults to 25 seconds, as Pyjo.Server.Prefork has it
                'G|graceful-timeout=i': lambda name, value: setattr(prefork, 'graceful_timeout', value),
                'I|heartbeat-interval=i': lambda name, value: setattr(prefork, 'heartbeat_interval', value),
                'H|heartbeat-timeout=i': lambda name, value: setattr(prefork, 'heartbeat_timeout', value),
                'i|inactivity-timeout=i': lambda name, value: setattr(prefork, 'inactivity_timeout', value),
                'k|keep-alive-timeout=i': lambda name, value: setattr(prefork, 'keep_alive_timeout', value),
                'l|listen=s': listen,
                'P|pid-file=s': lambda name, value: setattr(prefork, 'pid_file', value),
                'p|proxy:s': proxy,
                'r|requests=i': lambda name, value: setattr(prefork, 'max_requests', value),
                # Not in Mojolicious: the delay of the graceful shutdown, while the readiness fails
                'S|shutdown-delay=i': lambda name, value: setattr(prefork, 'shutdown_delay', value),
                's|spare=i': lambda name, value: setattr(prefork, 'spare', value),
                'w|workers=i': lambda name, value: setattr(prefork, 'workers', value),
            },
            env_prefix='PYJO_',
        ):
            raise Pyjo.Exception.new(self.usage)

        if listen:
            prefork.listen = listen
        if proxy:
            prefork.reverse_proxy = True
        if trusted := [p for p in proxy if p]:
            prefork.trusted_proxies = trusted
        return prefork

    def run(self, *args: str) -> Any:
        """::

            prefork.run(*sys.argv[1:])

        Run this command.
        """
        return self.build_server(*args).run()


new = Pyjoyment_Command_prefork.new
object = Pyjoyment_Command_prefork
