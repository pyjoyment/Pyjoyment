"""
Pyjo.Steps - Steps of a coroutine, blocking or non-blocking
===========================================================
::

    from Pyjo.Steps import Command, Request, Sleep, Steps
    from Pyjo.UserAgent import UserAgent

    ua = UserAgent()

    async def hello():
        tx = await Request(ua.build_tx('GET', 'https://mojolicious.org'))
        await Sleep(0.5)
        code, out, err = await Command(['hostname'])
        return f"{out.decode().strip()}: {tx.result.dom().at('title').text}"

    print(Steps(hello()).run(ua))
    Steps(hello()).run_p(ua).then(lambda text: print(text)).wait()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Steps

    # The steps of another coroutine, awaited
    async def twice():
        return [await Pyjo.Steps.Steps(hello()), await Pyjo.Steps.Steps(hello())]

:mod:`Pyjo.Steps` runs a coroutine that awaits transactions of HTTP,
programs and sleeps, blocking and non-blocking, so that the code that makes
requests and runs programs is written once, for both, as a library that a
script and an action of a server share:

* a :class:`Request` gives the transaction back with its response, or raises
  the :mod:`Pyjo.Exception` of an error of the connection;
* a :class:`Command` gives the exit code, the output and the error of the
  program, or raises the :mod:`Pyjo.Exception` of a program that cannot be
  run;
* a :class:`Sleep` waits for a number of seconds;
* :class:`Steps` of another coroutine give what it returns.

A blocking request of :mod:`Pyjo.UserAgent` cannot run the event loop that
is running already, as in an action of a server, and a non-blocking one
cannot be waited for there either. The same steps run with
:meth:`~Pyjo_Steps.run` in a script and with :meth:`~Pyjo_Steps.run_p` in
the event loop.

No event loop runs the coroutine, so it awaits nothing else, not a
:mod:`Pyjo.Promise` and not a future of asyncio, which is a
:exc:`TypeError`. A generator that yields the requests, the programs and the
sleeps, and takes :class:`Steps` with ``yield from``, runs as a coroutine
does.

See also
--------

:mod:`Pyjo.UserAgent`, :mod:`Pyjo.IOLoop.ChildProcess`, :mod:`Pyjo.Promise`.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.IOLoop.ChildProcess
import Pyjo.Promise
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent

import builtins
import subprocess
import time

from collections.abc import Coroutine, Generator, Mapping, Sequence
from typing import Any, Self, cast


type Anything = builtins.object


class Command(Pyjo.Base.object):
    """
    A program to run, with its arguments, what it gets on its standard input,
    its environment, the one of the process by default, and the number of
    seconds that it may run, without a limit by default. ::

        code, out, err = await Command.new(['hostname'])
        code, out, err = await Command.new(['/opt/bin/token'], env={**os.environ, 'AUDIENCE': audience}, timeout=30)
    """

    def __init__(
        self,
        args: Sequence[str],
        input: bytes = b'',
        *,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> None:
        self.args = list(args)
        self.input = input
        self.env = dict(env) if env is not None else None
        self.timeout = timeout

    def __await__(self) -> Generator[Self, Any, tuple[int | None, bytes, bytes]]:
        """::

            code, out, err = await command

        Run the program and give its exit code, its standard output and its
        standard error, or an exception of a program that runs longer than
        its timeout, which is killed.
        """
        return (yield self)


class Request(Pyjo.Base.object):
    """
    A transaction to start, with the user agent that starts it, or the one of
    :meth:`~Pyjo_Steps.run` by default, as one whose event ``start`` adds the
    credentials of a client to it. ::

        tx = await Request.new(ua.build_tx('GET', 'https://mojolicious.org'))
        tx = await Request.new(tx, ua)
    """

    def __init__(self, tx: Pyjo.Transaction.HTTP.object, ua: Pyjo.UserAgent.object | None = None) -> None:
        self.tx = tx
        self.ua = ua

    def __await__(self) -> Generator[Self, Any, Pyjo.Transaction.HTTP.object]:
        """::

            tx = await request

        Start the transaction and give it back with its response.
        """
        return (yield self)


class Sleep(Pyjo.Base.object):
    """
    A number of seconds to wait, as for a file that another program writes,
    or before a request is tried again. ::

        await Sleep.new(0.5)
    """

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def __await__(self) -> Generator[Self, Any, None]:
        """::

            await sleep

        Wait for the seconds, with :func:`time.sleep` of
        :meth:`~Pyjo_Steps.run` and with a timer of the reactor of
        :meth:`~Pyjo_Steps.run_p`, which runs the other events meanwhile.
        """
        yield self


type Operation = Request | Command | Sleep


class Pyjo_Steps[T](Pyjo.Base.object):
    """
    :mod:`Pyjo.Steps` inherits all attributes and methods from
    :mod:`Pyjo.Base` and implements the following new ones. The steps are
    of one coroutine, which they run once.
    """

    def __init__(self, steps: Coroutine[Any, Any, T] | Generator[Operation, Any, T]) -> None:
        """::

            steps = Pyjo.Steps.new(provider.fetch())

        Construct a new :mod:`Pyjo.Steps` object of a coroutine or a
        generator.
        """
        self._steps = steps

    def __await__(self) -> Generator[Operation, Any, T]:
        """::

            value = await steps

        Wait for the steps in another coroutine and give what they return.
        """
        steps = self._steps
        if isinstance(steps, Coroutine):
            return cast(Generator[Operation, Any, T], steps.__await__())
        return steps

    def __iter__(self) -> Generator[Operation, Any, T]:
        """::

            value = yield from steps

        Same as :meth:`__await__`, in a generator.
        """
        return self.__await__()

    def run(self, ua: Pyjo.UserAgent.object) -> T:
        """::

            value = steps.run(ua)

        Run the steps blocking, the requests with a user agent, of
        :meth:`Pyjo.UserAgent.Pyjo_UserAgent.start`, the programs of
        :func:`subprocess.run` and the sleeps of :func:`time.sleep`, and give
        what they return.
        """
        gen = self.__await__()
        value: Any = None
        error: Exception | None = None
        while True:
            try:
                op = gen.send(value) if error is None else gen.throw(error)
            except StopIteration as e:
                return cast(T, e.value)
            if unexpected := _unexpected(gen, op):
                raise unexpected
            value, error = None, None
            try:
                value = _blocking(op, ua)
            except Exception as e:
                error = e

    def run_p(self, ua: Pyjo.UserAgent.object) -> Pyjo.Promise.object:
        """::

            promise = steps.run_p(ua)

        Same as :meth:`run`, but non-blocking, with
        :meth:`Pyjo.UserAgent.Pyjo_UserAgent.start_p`,
        :meth:`Pyjo.IOLoop.ChildProcess.Pyjo_IOLoop_ChildProcess.run_p` and
        :meth:`Pyjo.Promise.Pyjo_Promise.timer`, and returns a
        :mod:`Pyjo.Promise` object.
        """
        gen = self.__await__()
        promise = Pyjo.Promise.new()

        # The reactor keeps the steps until they end, as run_coroutine keeps a coroutine: only the promise of their
        # operation refers to them otherwise, in a cycle that the garbage collector would free while they wait
        running = promise.ioloop.reactor._coroutines  # pyright: ignore[reportPrivateUsage]
        running.add(gen)

        def step(value: Any = None, error: Exception | None = None) -> None:
            try:
                op = gen.send(value) if error is None else gen.throw(error)
                if unexpected := _unexpected(gen, op):
                    raise unexpected
                started = _nonblocking_p(op, ua)
            except StopIteration as e:
                running.discard(gen)
                promise.resolve(e.value)
                return
            except Exception as e:
                running.discard(gen)
                promise.reject(e)
                return

            def failed(reason: Anything) -> None:
                step(error=_error(op, reason))

            started.then(step, failed)

        step()
        return promise


# The error of an operation, as a Pyjo.Exception with what failed, of the reason of a rejected promise too, which is a
# string of an error of a connection, or the OSError of a program that cannot be run
def _error(op: Operation, reason: Anything) -> Exception:
    if isinstance(op, Command):
        if isinstance(reason, OSError):
            reason = reason.strerror or reason
        elif isinstance(reason, Exception):
            return reason
        return Pyjo.Exception.new(f'Cannot run {op.args[0]}: {reason}')
    if isinstance(reason, Exception):
        return reason
    # The timer of a sleep is never rejected, so the reason that is not an exception is of a request
    request = cast(Request, op)
    return Pyjo.Exception.new(f'{request.tx.req.method} {request.tx.req.url.to_str()}: {reason}')


def _timeout(op: Command) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'Cannot run {op.args[0]}: no exit in {op.timeout:g} seconds')


# What a coroutine awaits that is not an operation, as a Pyjo.Promise or a future of asyncio, which only an event loop
# knows: the coroutine is closed and the error raised, not thrown into it, where catching the errors of a connection
# would hide it
def _unexpected(steps: Generator[Operation, Any, Any], op: Anything) -> TypeError | None:
    if isinstance(op, (Request, Command, Sleep)):
        return None
    steps.close()
    return TypeError(f'Steps await {type(op).__name__}: only a Request, a Command, a Sleep and Steps')


def _blocking(op: Operation, ua: Pyjo.UserAgent.object) -> Any:
    if isinstance(op, Sleep):
        time.sleep(op.seconds)
        return None
    if isinstance(op, Command):
        try:
            done = subprocess.run(
                op.args, input=op.input, capture_output=True, check=False, env=op.env, timeout=op.timeout
            )
        except subprocess.TimeoutExpired as e:
            raise _timeout(op) from e
        except OSError as e:
            raise _error(op, e) from e
        return done.returncode, done.stdout, done.stderr
    tx: Pyjo.Transaction.HTTP.object = (op.ua or ua).start(op.tx)
    if (err := tx.error) and not err.get('code'):
        raise _error(op, err['message'])
    return tx


def _nonblocking_p(op: Operation, ua: Pyjo.UserAgent.object) -> Pyjo.Promise.object:
    if isinstance(op, Sleep):
        return Pyjo.Promise.timer(op.seconds)
    if isinstance(op, Command):
        child = Pyjo.IOLoop.ChildProcess.new()
        options: dict[str, Any] = {'env': op.env} if op.env is not None else {}
        promise: Pyjo.Promise.object = child.run_p(op.args, input=op.input, **options)
        timer: list[str] = []
        if op.timeout is not None:

            def kill(reactor: Any) -> None:
                timer.clear()
                child.kill()

            timer.append(child.reactor.timer(op.timeout, kill))

        def result(code: int | None, out: bytes, err: bytes) -> tuple[int | None, bytes, bytes]:
            if op.timeout is not None and not timer:
                raise _timeout(op)
            for id in timer:
                child.reactor.remove(id)
            return code, bytes(out), bytes(err)

        return promise.then(result)
    return (op.ua or ua).start_p(op.tx)


# Any: the type of what the steps return is not known before they are given
new = Pyjo_Steps[Any].new
object = Pyjo_Steps
Steps = Pyjo_Steps
