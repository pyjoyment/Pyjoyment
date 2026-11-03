"""
Pyjo.Reactor.Asyncio - Low-level event reactor on asyncio
=========================================================
::

    from Pyjo.Reactor.Asyncio import Asyncio

    # Watch if handle becomes readable or writable
    reactor = Asyncio()
    reactor.io(first, lambda reactor, writable: print(
        'First handle is writable' if writable else 'First handle is readable'
    ))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Reactor.Asyncio

    # Watch if handle becomes readable or writable
    reactor = Pyjo.Reactor.Asyncio.new()
    reactor.io(first, lambda reactor, writable: print(
        'First handle is writable' if writable else 'First handle is readable'
    ))

    # Change to watching only if handle becomes writable
    reactor.watch(first, False, True)

    # Watch a file descriptor if it becomes readable
    reactor.io(fd, lambda reactor, writable: print(
        'Second handle is writable' if writable else 'Second handle is readable'
    )).watch(fd, True, False)

    # Add a timer
    def timeout(reactor):
        reactor.remove(first)
        reactor.remove(fd)
        print('Timeout!')

    reactor.timer(15, timeout)

    # Start reactor if necessary
    if not reactor.is_running:
        reactor.start()

:mod:`Pyjo.Reactor.Asyncio` is a low-level event reactor based on
:mod:`asyncio`. It watches handles and runs timers in an asyncio event loop,
so coroutines, tasks and other users of the loop run along with it.

A reactor uses the event loop it is given, or else the loop that is running,
as inside :func:`asyncio.run`, or a new event loop of its own, and moves its
handles and timers to the loop that is running. In a loop that runs
already, :meth:`start` and :meth:`one_tick` return right away, as asyncio
does not nest event loops, and the handles and timers are watched by that
loop.

The loop watches handles with ``add_reader`` and ``add_writer``, which the
default event loop of asyncio on Windows, :class:`asyncio.ProactorEventLoop`,
does not have. There, a loop of its own is an
:class:`asyncio.SelectorEventLoop`, and a loop that the reactor is given or
that is running has to be one too, as of
``asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)``. The
:class:`asyncio.SelectorEventLoop` of Windows watches sockets only, not pipes
or files, up to 512 of them, with :func:`select.select`.

In the debug mode of asyncio, as of ``PYTHONDEVMODE``, a loop logs a callback
that takes longer than its ``slow_callback_duration``, 0.1 seconds. The
``PYJO_ASYNCIO_SLOW_CALLBACK`` environment variable sets it in seconds for a
loop that the reactor makes, as on a machine that is busy, where TLS and an
application of a server take longer. ::

    PYTHONDEVMODE=1 PYJO_ASYNCIO_SLOW_CALLBACK=5 python myapp.py daemon

The end of a ``with`` block closes the event loop that the reactor made.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Reactor::Poll <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Reactor/Poll.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.Exception
import Pyjo.Reactor

from Pyjo.Reactor import Handle, IOCallback, TimerCallback
from Pyjo.Util import _call_hint, md5_sum  # pyright: ignore[reportPrivateUsage]

import asyncio
import atexit
import collections
import os
import random
import sys
import time
import weakref

from collections.abc import Awaitable, Callable, Coroutine, Generator
from types import TracebackType
from typing import Any, Self, TypedDict


class _IO(TypedDict):
    cb: IOCallback
    read: bool
    write: bool


class _Timer(TypedDict):
    cb: TimerCallback | None
    after: float
    recurring: bool
    handle: asyncio.Handle
    deadline: float


class Pyjo_Reactor_Asyncio(Pyjo.Reactor.object):
    """
    :mod:`Pyjo.Reactor.Asyncio` inherits all methods from
    :mod:`Pyjo.Reactor` and implements the following new ones.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """::

            reactor = Pyjo.Reactor.Asyncio.new()
            reactor = Pyjo.Reactor.Asyncio.new(loop=asyncio.new_event_loop())

        Construct a new :mod:`Pyjo.Reactor.Asyncio` object.
        """
        super().__init__()

        # Not in Mojolicious: the asyncio event loop
        self._fixed = loop is not None
        self._loop = loop
        self._own: asyncio.AbstractEventLoop | None = None
        self._finalizer: weakref.finalize[..., Any] | None = None

        self._error: BaseException | None = None
        self._io: dict[int, _IO] = {}
        # A deque, whose popleft takes the first callback as shift of Perl does, where pop(0) of a list moves all the others
        self._next_tick: collections.deque[TimerCallback] = collections.deque()
        self._next_timer: str | None = None
        self._one = 0
        self._run = 0
        self._running = 0
        self._tasks: set[asyncio.Task[Any]] = set()
        self._timers: dict[str, _Timer] = {}
        _REACTORS.add(self)

    # Not in Mojolicious: a context manager, which closes the event loop that the reactor made where the block ends, as
    # PyPy frees the object only when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    # The cleanups that finalizers deferred at the next tick, with call_soon_threadsafe of the event loop, which only
    # appends to a queue, where the timers of the reactor would change its structures, and works from any thread, as the
    # garbage collector runs finalizers in any of them; the reactor stops after them when it watches nothing anymore, as
    # after an event
    def _wake(self) -> None:
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(Pyjo_Reactor_Asyncio._weak_drain, weakref.ref(self))

    @staticmethod
    def _weak_drain(ref: 'weakref.ref[Any]') -> None:
        Pyjo.Reactor._drain()  # pyright: ignore[reportPrivateUsage]
        if (self := ref()) is not None and self._run and (not self._running or not self._watching()):
            self._stop()

    def _close_loop(self) -> None:
        if (loop := self._own) is not None:
            _cancel(loop)
            _close(loop)

    # Not in Mojolicious: a loop of its own, which is closed with the reactor by weakref.finalize, which the garbage
    # collector calls before the finalizers of the objects that it frees, as the loop warns when it is freed before the
    # reactor closes it, as among the objects that a free-threaded Python frees only when the garbage collector runs
    def _own_loop(self) -> asyncio.AbstractEventLoop:
        loop = self._own = _new_event_loop()
        _OWN.add(loop)
        self._finalizer = weakref.finalize(self, _close, loop)
        _register()
        return loop

    # Not in Mojolicious: the asyncio event loop
    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """::

            loop = reactor.loop

        The :mod:`asyncio` event loop of the reactor: the one it is given, or
        else the loop that is running, as inside :func:`asyncio.run`, or a
        loop of its own. A reactor that is not given a loop follows the loop
        that is running, and moves its handles and timers to it, unless it
        has tasks in another loop, which cannot move. In the child of a fork,
        it moves to a new loop of its own, as the selector of the loop of the
        parent is not the child's.
        """
        return self._follow()

    # The loop that is running, which a reactor that is not given a loop follows, or the one of the reactor
    def _follow(self) -> asyncio.AbstractEventLoop:
        loop = self._loop
        if self._fixed and loop is not None:
            return loop

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is not None:
            if running is not loop and not len(self._tasks):
                self._move(running)
        elif loop is None or loop.is_closed() or (loop is not self._own and not loop.is_running()):
            if self._own is None or self._own.is_closed():
                self._own_loop()
            assert self._own is not None
            self._move(self._own)

        assert self._loop is not None
        return self._loop

    # The child of a fork moves to a new loop, as the selector of the old one, epoll or kqueue, is the one of the parent;
    # the old loop, and the loop of its own when it follows another one, are kept, not closed, neither at the exit nor by
    # the garbage collector, which would close the files of the parent
    def _fork(self) -> None:
        if self._fixed or self._loop is None:
            return
        for loop in (self._loop, self._own):
            if loop is not None:
                _FORKED.append(loop)
                _OWN.discard(loop)
        if self._finalizer is not None:
            self._finalizer.detach()
        self._loop = self._own = None
        self._move(self._own_loop())

    # Move the handles and timers to another loop
    def _move(self, new: asyncio.AbstractEventLoop) -> None:
        old, self._loop = self._loop, new
        alive = old is not None and not old.is_closed()
        for id, timer in self._timers.items():
            after = timer['after']
            if old is not None and alive and after > 0:
                after = max(0.0, timer['deadline'] - old.time())
            timer['handle'].cancel()
            timer['handle'], timer['deadline'] = self._schedule(new, after, id)
        for fd, io in self._io.items():
            if old is not None and alive:
                if io['read']:
                    old.remove_reader(fd)
                if io['write']:
                    old.remove_writer(fd)
            if io['read']:
                self._add(new, fd, False)
            if io['write']:
                self._add(new, fd, True)

    def again(self, id: str, after: float | None = None) -> None:
        """::

            reactor.again(id)
            reactor.again(id, 0.5)

        Restart timer and optionally change the invocation time. Note that this
        method requires an active timer.
        """
        if (timer := self._timers.get(id)) is None:
            Pyjo.Exception.object.throw('Timer not active')
        if after is not None:
            timer['after'] = after

        # Not in Mojolicious: a later time only moves the deadline, which the timer checks when it is due, as a stream
        # restarts its timer on every read and write, and a handle of asyncio cancelled and scheduled again each time
        # is what costs, where Mojo sets the time of the timer
        loop = self.loop
        after, handle = timer['after'], timer['handle']
        deadline = loop.time() + after
        if (
            after > 0
            and isinstance(handle, asyncio.TimerHandle)
            and not handle.cancelled()
            and handle.when() <= deadline
        ):
            timer['deadline'] = deadline
            return
        handle.cancel()
        timer['handle'], timer['deadline'] = self._schedule(loop, after, id)

    # Not in Mojolicious: a future of the loop
    def awaitable(self, promise: Any) -> Awaitable[None]:
        """::

            future = reactor.awaitable(promise)

        Return a future of :attr:`loop` that is done when the promise is
        fulfilled or rejected, so that ``await promise`` works in any task of
        the loop.
        """
        future: asyncio.Future[None] = self.loop.create_future()

        def settle(*values: Any) -> None:
            if not future.done():
                future.set_result(None)

        promise.then(settle, settle)
        return future

    # Not in Mojolicious: the release of the event loop of its own, which Perl does in DESTROY, also at the end of a with
    # block
    def close(self) -> None:
        """::

            reactor.close()

        Close the event loop that the reactor made for itself, as the end of a
        ``with`` block does, after the tasks that are left in it are cancelled
        and have ended, as :func:`asyncio.run` does, and as the end of the
        program does; an event loop that it was given, or that was running, is
        left to its owner.
        """
        self._close_loop()

    # Not in Mojolicious: a task of the loop
    def run_coroutine(
        self, coro: Coroutine[Any, Any, Any], resolve: Callable[[Any], Any], reject: Callable[[Any], Any]
    ) -> None:
        """::

            reactor.run_coroutine(coro, resolve, reject)

        Run a coroutine as a task of :attr:`loop`, where it can await anything
        of the loop, and call ``resolve`` with what it returns or ``reject``
        with the exception it raises. A task that is not done is something to
        watch, so that :meth:`start` does not stop before it, and each step of
        the coroutine is an event, which ends :meth:`one_tick`.
        """
        task = self.loop.create_task(_steps(coro, weakref.WeakMethod(self._step)))
        self._tasks.add(task)

        def done(task: asyncio.Task[Any]) -> None:
            self._tasks.discard(task)
            if task.cancelled():
                # A task cancelled before its first step never starts the coroutine, which would warn that it was never
                # awaited
                coro.close()
                reject(asyncio.CancelledError())
            elif (e := task.exception()) is not None:
                reject(e)
            else:
                resolve(task.result())

        task.add_done_callback(done)

    # Not in Mojolicious: a future of the loop
    def future(self) -> asyncio.Future[Any]:
        """::

            future = reactor.future()

        Return a new :class:`asyncio.Future` of :attr:`loop`, which
        :meth:`Pyjo.Promise.Pyjo_Promise.to_future` turns a promise into.
        """
        return self.loop.create_future()

    def io(self, handle: Handle, cb: IOCallback) -> Self:
        """::

            reactor = reactor.io(handle, cb)

        Watch handle for I/O events, invoking the callback whenever handle
        becomes readable or writable. ::

            # Callback will be executed twice if handle becomes readable and writable
            reactor.io(handle, lambda reactor, writable: print('Handle is writable' if writable else 'Handle is readable'))
        """
        self._io[_fileno(handle)] = {'cb': cb, 'read': False, 'write': False}
        return self.watch(handle, True, True)

    @property
    def is_running(self) -> bool:
        """::

            boolean = reactor.is_running

        Check if reactor is running.
        """
        return bool(self._running)

    def next_tick(self, cb: TimerCallback) -> None:
        """::

            none = reactor.next_tick(cb)

        Execute callback as soon as possible, but not before returning or other
        callbacks that have been registered with this method, always returns
        ``None``.
        """
        self._next_tick.append(cb)
        if self._next_timer is None:
            self._next_timer = self.timer(0, Pyjo_Reactor_Asyncio._next)

        # Not in Mojolicious: a reactor that follows the loop that is running moves there with the timer of the next tick,
        # which a loop that stopped in the middle of a tick, as in Pyjo.Promise.wait, leaves where nothing runs it; its
        # own loop that runs, as most of the time, needs no move
        elif not self._fixed and (loop := self._loop) is not None and not loop.is_running():
            self._follow()
        return None

    def one_tick(self) -> None:
        """::

            reactor.one_tick()

        Run reactor until an event occurs or no events are being watched
        anymore. ::

            # Don't block longer than 0.5 seconds
            id = reactor.timer(0.5, lambda reactor: None)
            reactor.one_tick()
            reactor.remove(id)
        """
        # Just one tick
        running = self._running
        if not running:
            self._running = 1

        try:
            # Stop automatically if there is nothing to watch
            if not self._watching():
                return self.stop()

            # Unlike Mojolicious: asyncio does not nest event loops, the one that runs already watches the events
            loop = self.loop
            if loop.is_running():
                return

            # Wait for one event
            self._one += 1
            try:
                loop.run_forever()
            finally:
                self._one -= 1

            # An exception of an unhandled error event
            if (error := self._error) is not None:
                self._error = None
                raise error
        finally:
            if not running:
                self._running = running

    def recurring(self, after: float, cb: TimerCallback) -> str:
        """::

            id = reactor.recurring(0.25, cb)

        Create a new recurring timer, invoking the callback repeatedly after a
        given amount of time in seconds.
        """
        return self._timer(True, after, cb)

    def remove(self, remove: Handle | str) -> bool:
        """::

            boolean = reactor.remove(handle)
            boolean = reactor.remove(id)

        Remove handle or timer.
        """
        if isinstance(remove, str):
            if (timer := self._timers.pop(remove, None)) is None:
                return False
            timer['handle'].cancel()
            return True
        fd = _fileno(remove)
        if (io := self._io.pop(fd, None)) is None:
            return False
        self._unwatch(fd, io)
        return True

    def reset(self) -> None:
        """::

            reactor.reset()

        Remove all handles and timers.
        """
        for fd, io in self._io.items():
            self._unwatch(fd, io)
        for timer in self._timers.values():
            timer['handle'].cancel()
        self._events = {}
        self._io = {}
        self._next_tick.clear()
        self._next_timer = None
        self._running = 0
        self._tasks = set()
        self._timers = {}
        self._stop()

    def start(self) -> None:
        """::

            reactor.start()

        Start watching for I/O and timer events, this will block until
        :meth:`stop` is called or no events are being watched anymore. ::

            # Start reactor only if it is not running already
            if not reactor.is_running:
                reactor.start()
        """
        running = self._running
        self._running = running + 1
        try:
            # Unlike Mojolicious: asyncio does not nest event loops, the one that runs already watches the events
            while self._running and not (loop := self.loop).is_running():
                # Stop automatically if there is nothing to watch
                if not self._watching():
                    return self.stop()

                # Not in Mojolicious: the loop runs until the reactor stops, where Mojo runs one tick after another, as
                # an asyncio loop that stops and runs again for every event is what costs
                self._run += 1
                try:
                    loop.run_forever()
                finally:
                    self._run -= 1

                # An exception of an unhandled error event
                if (error := self._error) is not None:
                    self._error = None
                    raise error
        finally:
            self._running = running

    def stop(self) -> None:
        """::

            reactor.stop()

        Stop watching for I/O and timer events.
        """
        self._running = 0
        self._stop()

    def timer(self, after: float, cb: TimerCallback) -> str:
        """::

            id = reactor.timer(0.5, cb)

        Create a new timer, invoking the callback after a given amount of time
        in seconds.
        """
        return self._timer(False, after, cb)

    def watch(self, handle: Handle, read: bool, write: bool) -> Self:
        """::

            reactor = reactor.watch(handle, readable, writable)

        Change I/O events to watch handle for with true and false values. Note
        that this method requires an active I/O watcher. ::

            # Watch only for readable events
            reactor.watch(handle, True, False)

            # Watch only for writable events
            reactor.watch(handle, False, True)

            # Watch for readable and writable events
            reactor.watch(handle, True, True)

            # Pause watching for events
            reactor.watch(handle, False, False)
        """
        fd = _fileno(handle)
        if (io := self._io.get(fd)) is None:
            Pyjo.Exception.object.throw('I/O watcher not active')

        # Not in Mojolicious: only the events that change are added or removed, as each is a call of the selector of
        # asyncio, where Mojo sets the mask of the handle
        loop = self.loop
        read, write = bool(read), bool(write)
        if read != io['read']:
            if read:
                self._add(loop, fd, False)
            else:
                loop.remove_reader(fd)
        if write != io['write']:
            if write:
                self._add(loop, fd, True)
            else:
                loop.remove_writer(fd)
        io['read'], io['write'] = read, write

        return self

    # Not in Mojolicious: a loop without add_reader and add_writer, as the ProactorEventLoop of Windows, which
    # asyncio.run makes there, cannot watch handles, and says so
    def _add(self, loop: asyncio.AbstractEventLoop, fd: int, writable: bool) -> None:
        add = loop.add_writer if writable else loop.add_reader
        try:
            add(fd, Pyjo_Reactor_Asyncio._weak_ready, weakref.ref(self), fd, writable)
        except NotImplementedError:
            name = f'{type(loop).__module__}.{type(loop).__qualname__}'
            Pyjo.Exception.object.throw(f'Event loop {name} cannot watch handles, an asyncio.SelectorEventLoop can')

    # A timer of no time runs before the I/O of the next iteration of the loop, as the timers of Mojo's reactor run in
    # the same tick, after its I/O; call_later would run it after the I/O of the next iteration
    def _schedule(self, loop: asyncio.AbstractEventLoop, after: float, id: str) -> tuple[asyncio.Handle, float]:
        if after <= 0:
            return loop.call_soon(Pyjo_Reactor_Asyncio._weak_alarm, weakref.ref(self), id), loop.time()
        handle = loop.call_later(after, Pyjo_Reactor_Asyncio._weak_alarm, weakref.ref(self), id)
        return handle, handle.when()

    # The loop refers to the reactor weakly, so that the reactor and its loop do not make a cycle
    @staticmethod
    def _weak_alarm(ref: 'weakref.ref[Any]', id: str) -> None:
        if (reactor := ref()) is not None:
            reactor._alarm(id)

    @staticmethod
    def _weak_ready(ref: 'weakref.ref[Any]', fd: int, writable: bool) -> None:
        if (reactor := ref()) is not None:
            reactor._ready(fd, writable)

    # A timer is due
    def _alarm(self, id: str) -> None:
        if (timer := self._timers.get(id)) is None:
            return

        # Not in Mojolicious: a timer that again moved to a later time waits for it
        loop = self.loop
        if (left := timer['deadline'] - loop.time()) > 0:
            timer['handle'] = loop.call_later(left, Pyjo_Reactor_Asyncio._weak_alarm, weakref.ref(self), id)
            return

        # Recurring timer
        if timer['recurring']:
            timer['handle'], timer['deadline'] = self._schedule(loop, timer['after'], id)

        # Normal timer
        else:
            self.remove(id)

        if (cb := timer['cb']) is not None:
            self._event('Timer', cb)

    # An event of a watcher or a timer, which ends one_tick, and start once the reactor stops or watches nothing
    def _event(self, what: str, cb: Any, *args: Any) -> None:
        try:
            self._try(what, cb, *args)
        except Exception as e:
            # Not in Mojolicious: asyncio logs an exception of a callback, Perl dies out of one_tick, so it is kept and
            # raised by one_tick or start, unless the loop runs without them
            if not self._one and not self._run:
                raise
            self._error = e
            return self._stop()
        if self._one or (self._run and (not self._running or not self._watching())):
            self._stop()

    def _id(self) -> str:
        while True:
            id = md5_sum(f't{time.monotonic()}{random.random()}'.encode())
            if id not in self._timers:
                return id

    def _next(self) -> None:
        self._next_timer = None
        while len(self._next_tick):
            self._next_tick.popleft()(self)

    # A handle is ready
    def _ready(self, fd: int, writable: bool) -> None:
        if (io := self._io.get(fd)) is not None:
            self._event('I/O watcher', io['cb'], writable)

    # A step of a coroutine, which ends one_tick
    def _step(self) -> None:
        if self._one and self.loop.is_running():
            self.loop.stop()

    def _stop(self) -> None:
        if (self._one or self._run) and self.loop.is_running():
            self.loop.stop()

    def _timer(self, recurring: bool, after: float, cb: TimerCallback) -> str:
        id = self._id()
        handle, deadline = self._schedule(self.loop, after, id)
        self._timers[id] = {'cb': cb, 'after': after, 'recurring': recurring, 'handle': handle, 'deadline': deadline}
        return id

    def _try(self, what: str, cb: Any, *args: Any) -> None:
        try:
            cb(self, *args)
        except Exception as e:
            # Not in Mojolicious: the arguments of a callback, which Perl does not check
            if isinstance(e, TypeError):
                _call_hint(e, 'the callbacks of a reactor get the reactor first')
            # Unlike Mojolicious: the message of Python has no file and line, the exception keeps the frames
            err = Pyjo.Exception.new(e)
            err.message = f'{what} failed: {err.message}'
            err.__cause__ = e
            self.emit('error', err)

    def _watching(self) -> bool:
        return bool(len(self._timers) or len(self._io) or len(self._tasks))

    # The handle is removed from the loop that watches it, without the move to a loop that runs, which leaves out the
    # handles that are not watched anymore, so the loop of before would keep it, and select of Windows fails once the
    # handle is closed
    def _unwatch(self, fd: int, io: _IO) -> None:
        if (loop := self._loop) is not None and not loop.is_closed():
            if io['read']:
                loop.remove_reader(fd)
            if io['write']:
                loop.remove_writer(fd)
        io['read'] = io['write'] = False


def _fileno(handle: Handle) -> int:
    fd = handle if isinstance(handle, int) else handle.fileno()
    if fd < 0:
        Pyjo.Exception.object.throw('Handle is closed')
    return fd


# Not in Mojolicious: a step of a coroutine is an event of the reactor, as a step of an async sub of Mojo is a callback of
# next_tick, so that one_tick returns after it: the step of a task of asyncio is a callback of the loop that ends nothing,
# so code that waits with one_tick for what the coroutine does, as a server that waits for the response of an action,
# would wait for the next event of a watcher or a timer
async def _steps(coro: Coroutine[Any, Any, Any], step: 'weakref.WeakMethod[Callable[[], None]]') -> Any:
    return await _Steps(coro, step)


class _Steps:
    def __init__(self, coro: Coroutine[Any, Any, Any], step: 'weakref.WeakMethod[Callable[[], None]]') -> None:
        self._coro = coro
        self._step = step

    def __await__(self) -> Generator[Any, Any, Any]:
        coro = self._coro
        method: Callable[[Any], Any] = coro.send
        arg: Any = None
        while True:
            try:
                result = method(arg)
            except StopIteration as e:
                self._stepped()
                return e.value
            except BaseException:
                self._stepped()
                raise
            self._stepped()
            try:
                arg = yield result
                method = coro.send
            except GeneratorExit:
                coro.close()
                raise
            except BaseException as e:
                arg = e
                method = coro.throw

    def _stepped(self) -> None:
        if (step := self._step()) is not None:
            step()


# Not in Mojolicious: a loop of its own is a SelectorEventLoop on Windows, where the default of asyncio is the
# ProactorEventLoop, which has no add_reader and add_writer, with the threshold of a slow callback of
# PYJO_ASYNCIO_SLOW_CALLBACK, as asyncio has no variable of its own for it
def _new_event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.SelectorEventLoop() if sys.platform == 'win32' else asyncio.new_event_loop()
    if duration := os.environ.get('PYJO_ASYNCIO_SLOW_CALLBACK'):
        loop.slow_callback_duration = float(duration)
    return loop


# Not in Mojolicious: the event loops that the reactors make for themselves, which are closed at the exit of the
# interpreter, before it finalizes the objects and the loops of the reactors that still exist would warn that they are
# not closed
_OWN: 'weakref.WeakSet[asyncio.AbstractEventLoop]' = weakref.WeakSet()


# Not in Mojolicious: the reactors that exist, which move to new loops in the child of a fork, and the loops of the parent,
# which the child keeps
_REACTORS: 'weakref.WeakSet[Pyjo_Reactor_Asyncio]' = weakref.WeakSet()
_FORKED: list[asyncio.AbstractEventLoop] = []


def _after_fork_in_child() -> None:
    for reactor in list(_REACTORS):
        try:
            reactor._fork()  # pyright: ignore[reportPrivateUsage]
        except Exception:
            pass


if hasattr(os, 'register_at_fork'):
    os.register_at_fork(after_in_child=_after_fork_in_child)


def _close(loop: asyncio.AbstractEventLoop) -> None:
    if not loop.is_running() and not loop.is_closed():
        loop.close()


# Not in Mojolicious: the tasks that are left in a loop of its own, as a coroutine that waits for the next cycle of a loop
# that has stopped, are cancelled and run to their end before the loop closes, as asyncio.run does, so that none is
# destroyed while it is pending; not in another loop that runs, which cannot run this one, nor in the garbage collector
def _cancel(loop: asyncio.AbstractEventLoop) -> None:
    if loop.is_running() or loop.is_closed():
        return
    try:
        asyncio.get_running_loop()
        return
    except RuntimeError:
        pass
    if tasks := [task for task in asyncio.all_tasks(loop) if not task.done()]:
        for task in tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))


def _close_own() -> None:
    for loop in list(_OWN):
        _cancel(loop)
        _close(loop)


# Not in Mojolicious: the loops of their own are closed at the end of the program after their tasks, by a handler that is
# registered after the first finalizer, so that it runs before the exit function of weakref.finalize, as atexit runs
# the handlers in the reverse order, which would close the loops with their tasks pending
_registered = False


def _register() -> None:
    global _registered
    if not _registered:
        _registered = True
        atexit.register(_close_own)


new = Pyjo_Reactor_Asyncio.new
object = Pyjo_Reactor_Asyncio
Asyncio = Pyjo_Reactor_Asyncio
