"""
Pyjo.Server.Reload - Auto-restarting development server
========================================================
::

    from Pyjo.Server.Reload import Reload

    reload = Reload()
    reload.run('/home/sri/myapp.py')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Server.Reload

    reload = Pyjo.Server.Reload.new()
    reload.run('/home/sri/myapp.py')
    reload.run('/home/sri/myapp.py', 'prefork', '-w', '1')

    Pyjo.Server.Reload.new(exec=['npx webpack --watch']).run('/home/sri/myapp.py')

:mod:`Pyjo.Server.Reload` is a self-restart capable development server. It
starts your application with a server command, like
:mod:`Pyjoyment.Command.daemon` or :mod:`Pyjoyment.Command.prefork`, and
restarts it whenever a file changes. Listen sockets are only created once and
then passed on to the server, so they should be configured with
:mod:`Pyjo.Server.Reload` and not the server command. Note that the server
uses signals for process management, so you should avoid modifying signal
handlers in your applications.

Additional commands, like asset bundlers in watch mode, can be started
alongside the server with :attr:`~Pyjo_Server_Reload.exec`. They only get
started once, are not restarted together with the server, and get stopped when
:mod:`Pyjo.Server.Reload` shuts down.

To start applications with it you can use the ``pyjo-reload`` script,
``python -m Pyjo.Server.Reload``, or the command
:mod:`Pyjoyment.Command.reload` of the application. ::

    $ pyjo-reload ./myapp.py
    Web application available at http://127.0.0.1:3000

    $ ./myapp.py reload
    Web application available at http://127.0.0.1:3000

The server and the commands run in process groups of their own, which the
signals of POSIX stop, so it does not run on Windows. Name resolution in a
thread, SOCKS5 and TLS support can be disabled with the ``PYJO_NO_NNR``,
``PYJO_NO_SOCKS`` and ``PYJO_NO_TLS`` environment variables.

Signals
-------

The :mod:`Pyjo.Server.Reload` process can be controlled at runtime with the
following signals.

INT, TERM
~~~~~~~~~

Shut down server immediately. The server, all
:attr:`~Pyjo_Server_Reload.exec` commands and their subprocesses get a
``TERM`` signal, and the server also ``QUIT``, and will be killed if they have
not stopped after 5 seconds, just like for restarts.

HUP
~~~

Restart the server, as a change of a file does, while the
:attr:`~Pyjo_Server_Reload.exec` commands go on.

pyjo-reload
-----------
::

    Usage: pyjo-reload [OPTIONS] APPLICATION [COMMAND] [ARGS]

      pyjo-reload ./myapp.py
      pyjo-reload ./myapp.py prefork -w 1
      pyjo-reload -l http://127.0.0.1:8080 -w assets/css ./myapp.py prefork -w 3
      pyjo-reload -m production -l https://*:443 -l http://[::]:3000 ./myapp.py
      pyjo-reload -l 'https://*:443?cert=./server.crt&key=./server.key' ./myapp.py
      pyjo-reload -w /usr/local/lib -w public -w myapp.conf ./myapp.py
      pyjo-reload -x 'npx webpack --watch' ./myapp.py

    Options:
      -b, --backend <name>           Reload backend to use for reloading,
                                     defaults to "Poll"
      -h, --help                     Show this message
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
                                     script as well as the "lib" and "templates"
                                     directories in the current working directory
      -x, --exec <command>           One or more shell commands to start
                                     alongside the server, like asset bundlers in
                                     watch mode

Start :mod:`Pyjoyment` applications with the :mod:`Pyjo.Server.Reload`
restarter. The server command defaults to ``daemon``, and all options of
``pyjo-reload`` need to come before the application. Shell commands started
with ``--exec`` run for as long as :mod:`Pyjo.Server.Reload` does, they are
not restarted together with the server.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Server::Morbo <https://github.com/mojolicious/mojo/blob/v9.53/lib/Mojo/Server/Morbo.pm>`_
and `script/morbo <https://github.com/mojolicious/mojo/blob/v9.53/script/morbo>`_ of Mojolicious 9.53.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.GetOpt
import Pyjo.Server.Daemon

from Pyjo.Loader import load_class
from Pyjo.Util import die, extract_usage, getopt, warn

import contextlib
import os
import re
import signal
import sys
import time

from collections.abc import Sequence
from pkgutil import extend_path
from typing import TYPE_CHECKING, Any, NoReturn


if TYPE_CHECKING:
    import Pyjo.Server.Reload.Backend


# Not in Mojolicious: a namespace that other distributions can add to, as Pyjo.Server.Reload.Backend is one
__path__ = extend_path(__path__, __name__)

# The signals that stop the manager, and HUP, which restarts the server, blocked across a fork, so that the child does
# not run the handlers of the manager before its exec
_SIGNALS = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP} if hasattr(signal, 'SIGHUP') else set[signal.Signals]()


# Renamed from Mojolicious: Mojo::Server::Morbo, as the names of Futurama are not ours
class Pyjo_Server_Reload(Pyjo.Base.object):
    """
    :mod:`Pyjo.Server.Reload` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(
        self,
        *,
        backend: 'Pyjo.Server.Reload.Backend.object | None' = None,
        daemon: Pyjo.Server.Daemon.object | None = None,
        exec: list[str] | None = None,
        silent: bool = True,
    ) -> None:
        """::

            reload = Pyjo.Server.Reload.new()
            reload = Pyjo.Server.Reload.new(silent=False)

        Construct a new :mod:`Pyjo.Server.Reload` object.
        """
        super().__init__()

        self.exec: list[str] = exec if exec is not None else []
        """::

            commands = reload.exec
            reload.exec = ['npx webpack --watch', 'npx tailwindcss -i app.css -o public/assets/app.css --watch']

        Shell commands to start alongside the server, like asset bundlers in
        watch mode. The ``PYJO_MODE`` environment variable will be set to the
        operating mode of your application, so commands can use it too. The
        standard input of all commands is a pipe that gets closed when
        :mod:`Pyjo.Server.Reload` exits, even if it gets killed unexpectedly,
        which some tools use to shut down. When a command exits on its own, a
        message with its exit status is written to ``sys.stderr``.
        """

        self.silent = silent
        """::

            boolean = reload.silent
            reload.silent = False

        Disable console messages, defaults to a true value.
        """

        self._backend = backend
        self._command: list[str] = []
        self._commands: dict[int, str] = {}
        self._daemon = daemon
        self._finished = False
        self._kill: dict[int, float] = {}
        self._modified = False
        self._stdin: int | None = None
        self._worker: int | None = None

    @property
    def backend(self) -> 'Pyjo.Server.Reload.Backend.object':
        """::

            backend = reload.backend
            reload.backend = Pyjo.Server.Reload.Backend.Poll.new()

        Backend, usually a :mod:`Pyjo.Server.Reload.Backend.Poll` object, or
        ``Pyjo.Server.Reload.Backend.<Name>`` of the ``PYJO_RELOAD_BACKEND``
        environment variable.
        """
        if self._backend is None:
            name = f'Pyjo.Server.Reload.Backend.{os.environ.get("PYJO_RELOAD_BACKEND") or "Poll"}'
            if e := load_class(name):
                if isinstance(e, BaseException):
                    raise e
                raise Pyjo.Exception.new(f'Can\'t find Reload backend class "{name}" in sys.path. ({sys.path})\n')
            self._backend = sys.modules[name].new()
        return self._backend

    @backend.setter
    def backend(self, value: 'Pyjo.Server.Reload.Backend.object') -> None:
        self._backend = value

    @property
    def daemon(self) -> Pyjo.Server.Daemon.object:
        """::

            daemon = reload.daemon
            reload.daemon = Pyjo.Server.Daemon.new()

        :mod:`Pyjo.Server.Daemon` object used to create listen sockets. Other
        settings will be ignored, since the server runs in a separate process,
        use options of the server command instead.
        """
        if self._daemon is None:
            self._daemon = Pyjo.Server.Daemon.new(silent=True)
        return self._daemon

    @daemon.setter
    def daemon(self, value: Pyjo.Server.Daemon.object) -> None:
        self._daemon = value

    def run(self, app: str, *args: str) -> NoReturn:
        """::

            reload.run('myapp.py')
            reload.run('myapp.py', 'prefork', '-w', '1')

        Run server command for application and wait for the signals. The
        command defaults to ``daemon``.
        """

        # Unlike Mojolicious: no Windows, where Mojo has no fork emulation
        if not hasattr(os, 'fork'):
            die('Pyjo.Server.Reload does not support Windows.\n')

        # Clean manager environment
        def stop(signum: int, frame: Any) -> None:
            self._finished = True
            for pid in [self._worker, *self._commands]:
                self._stop(pid)

        # Unlike Mojolicious: HUP restarts the server, as it reloads the other servers of Pyjoyment, where Mojo stops on
        # it
        def restart(signum: int, frame: Any) -> None:
            if not self._finished:
                self._stop(self._worker)
                self._modified = True

        # Not in Mojolicious: local %SIG, the handlers of the signals are set back at the end
        handlers = {name: signal.signal(name, restart if name == signal.SIGHUP else stop) for name in _SIGNALS}
        try:
            self.backend.watch.insert(0, app)
            sys.argv[0] = app
            self._command = [sys.executable, app, *(args or ['daemon'])]
            self._modified = True

            # Prepare and cache listen sockets for smooth restarting (inherited by the server)
            self.daemon.start().stop()
            os.environ['PYJO_LISTEN'] = ','.join(str(location) for location in self.daemon.listen)
            # Renamed from Mojolicious: PERL5LIB, the path of the modules of the manager, with its current directory
            os.environ['PYTHONPATH'] = os.pathsep.join(os.path.abspath(path) for path in sys.path)

            # Commands (like asset bundlers in watch mode) need to know the mode too, and only get started once
            if not os.environ.get('PYJO_MODE'):
                os.environ['PYJO_MODE'] = 'development'

            # Commands get a pipe as STDIN that stays open until the manager exits, so they can read from it without
            # getting stopped (process group is not in the foreground) and know when to exit if it dies unexpectedly
            # (like esbuild does)
            stdin, self._stdin = os.pipe()
            self._commands = {self._spawn(stdin, *_shell(command)): command for command in self.exec}
            os.close(stdin)

            while not (self._finished and not self._worker and not self._commands):
                self._manage()
        finally:
            for name, handler in handlers.items():
                signal.signal(name, handler)
        sys.exit(0)

    def _manage(self) -> None:
        if files := self.backend.modified_files():
            if not self.silent:
                print(
                    f'File "{files[0]}" changed, restarting.'
                    if len(files) == 1
                    else f'{len(files)} files changed, restarting.'
                )
            self._stop(self._worker)
            self._modified = True

        for pid in [pid for pid in (self._worker, *self._commands) if pid is not None]:
            try:
                done, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done, status = pid, 0
            if done == pid:
                self._kill.pop(pid, None)
                if self._worker == pid:
                    self._worker = None
                elif not self._finished:
                    command = self._commands.get(pid)
                    warn(
                        f'Command "{command}" was killed by signal {os.WTERMSIG(status)}.\n'
                        if os.WIFSIGNALED(status)
                        else f'Command "{command}" exited with status {os.WEXITSTATUS(status)}.\n'
                    )
                self._commands.pop(pid, None)

            # Process did not stop in time
            elif pid in self._kill:
                if self._kill[pid] <= time.monotonic():
                    _kill(signal.SIGKILL, -pid)

            # Process was started after the signal handler ran
            elif self._finished:
                self._stop(pid)

        if not self._worker and not self._finished and self._modified:
            self._modified = False
            self._worker = self._spawn(None, *self._command)

    def _spawn(self, stdin: int | None, *command: str) -> int:
        # Not in Mojolicious: the buffers of the standard streams are written before, so that the child does not write
        # them again, and the signals of the manager are blocked, so that the child does not run its handlers
        _flush()
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, _SIGNALS)
        try:
            pid = os.fork()
        except OSError as e:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            raise OSError(e.errno, f"Can't fork: {e.strerror}") from e

        # Manager (process group gets set in both processes to avoid a race)
        if pid:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            with contextlib.suppress(OSError):
                os.setpgid(pid, pid)
            return pid

        # Worker (process group includes subprocesses)
        try:
            os.setpgid(0, 0)
            for name in _SIGNALS:
                signal.signal(name, signal.SIG_DFL)
            # Not in Mojolicious: the server ignores QUIT until it has a handler of its own, as QUIT, which stops it
            # immediately, would dump its core before
            if stdin is None:
                signal.signal(signal.SIGQUIT, signal.SIG_IGN)
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            if stdin is not None:
                try:
                    os.dup2(stdin, 0)
                except OSError as e:
                    warn(f"Can't redirect STDIN: {e.strerror}\n")
            os.execvp(command[0], command)
        except OSError as e:
            warn(f'Can\'t exec "{command[0]}": {e.strerror}\n')
        except BaseException:
            pass

        # Skip cleanup code inherited from the manager if exec fails
        _flush()
        os._exit(1)

    def _stop(self, pid: int | None) -> None:
        if not pid:
            return
        # Unlike Mojolicious: the server gets QUIT too, which stops it immediately, as TERM stops the servers of
        # Pyjoyment gracefully
        if pid == self._worker:
            _kill(signal.SIGQUIT, pid)
        _kill(signal.SIGTERM, -pid)
        self._kill.setdefault(pid, time.monotonic() + 5)


# Renamed from Mojolicious: script/morbo, the command line interface, a function of the module, whose usage is the
# section pyjo-reload of its docstring
def main(argv: Sequence[str] | None = None) -> NoReturn:
    """::

        main(['-l', 'http://*:8080', 'myapp.py'])
        main(['-l', 'http://*:8080', 'myapp.py', 'prefork', '-w', '2'])

    The command line interface of ``pyjo-reload``: parse the options and run
    the server command for the application.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    exec: list[str] = []
    listen: list[str] = []
    watch: list[str] = []
    opts = getopt(
        args,
        {
            'b|backend=s': Pyjo.GetOpt.env('PYJO_RELOAD_BACKEND'),
            'h|help': None,
            'l|listen=s': listen,
            # Not in Mojolicious: the format of the log messages of Pyjo.Log, as the option of the commands
            'log-format=s': Pyjo.GetOpt.env('PYJO_LOG_FORMAT'),
            'm|mode=s': Pyjo.GetOpt.env('PYJO_MODE'),
            'v|verbose': None,
            'w|watch=s': watch,
            'x|exec=s': exec,
        },
        require_order=True,
    )

    if not opts or opts.help or not args:
        # The usage without its last newline, as SystemExit writes the message with one
        die(extract_usage(section='pyjo-reload').rstrip('\n'))
    app = args.pop(0)
    if args and args[0].startswith('-'):
        die(f'pyjo-reload options need to come before the application, e.g. "pyjo-reload {args[0]} ... {app}"')
    reload = Pyjo_Server_Reload.new(silent=not opts.verbose)
    if listen:
        reload.daemon.listen = listen
    if watch:
        reload.backend.watch = watch
    if exec:
        reload.exec = exec
    reload.run(app, *args)


def _flush() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass


# Perl's kill, true if the signal was sent
def _kill(sig: int, pid: int) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except OSError:
        return False


# Perl's exec of one string, through the shell only with its metacharacters, as a command of exec
def _shell(command: str) -> list[str]:
    if re.search(r"""[$&*(){}\[\]'";\\|?<>~`\n]""", command):
        return ['/bin/sh', '-c', command]
    return command.split()


new = Pyjo_Server_Reload.new
object = Pyjo_Server_Reload
Reload = Pyjo_Server_Reload
