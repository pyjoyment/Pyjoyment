"""
Pyjo.Reactor - Low-level event reactor base class
=================================================
::

    from Pyjo.Reactor import Reactor

    class MyEventLoop(Reactor):
        def again(self, id, after=None): ...
        def io(self, handle, cb): ...
        @property
        def is_running(self): ...
        def next_tick(self, cb): ...
        def one_tick(self): ...
        def recurring(self, after, cb): ...
        def remove(self, remove): ...
        def reset(self): ...
        def start(self): ...
        def stop(self): ...
        def timer(self, after, cb): ...
        def watch(self, handle, read, write): ...

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Reactor

    class MyEventLoop(Pyjo.Reactor.object):
        def again(self, id, after=None): ...
        def io(self, handle, cb): ...
        @property
        def is_running(self): ...
        def next_tick(self, cb): ...
        def one_tick(self): ...
        def recurring(self, after, cb): ...
        def remove(self, remove): ...
        def reset(self): ...
        def start(self): ...
        def stop(self): ...
        def timer(self, after, cb): ...
        def watch(self, handle, read, write): ...

:mod:`Pyjo.Reactor` is an abstract base class for low-level event reactors,
like :mod:`Pyjo.Reactor.Asyncio`.

Events
------

:mod:`Pyjo.Reactor` inherits all events from :mod:`Pyjo.EventEmitter` and can
emit the following new ones.

error
~~~~~
::

    reactor.on('error', lambda reactor, err: ...)

Emitted for exceptions caught in callbacks, fatal if unhandled. Note that if
this event is unhandled or fails it might kill your program, so you need to be
careful. ::

    reactor.on('error', lambda reactor, err: print(f'Something very bad happened: {err}'))

Alternative reactors
--------------------

:mod:`Pyjo.Reactor` is a namespace that other distributions can add reactors
to, and the ``PYJO_REACTOR`` environment variable selects one for
:mod:`Pyjo.IOLoop`. A reactor on another implementation of the asyncio event
loop, like uvloop, is a subclass of :mod:`Pyjo.Reactor.Asyncio`, and one on
an event loop that is not asyncio's, like the ones of Trio or gevent,
implements the methods of :mod:`Pyjo.Reactor`.

A reactor is a module named ``Pyjo.Reactor.<Name>``, with a function ``new``
that constructs it and the class as ``object``, as the modules of Pyjoyment
have them. ::

    # Pyjo/Reactor/MyLoop.py of another distribution
    import Pyjo.Reactor.Asyncio

    import asyncio
    import selectors

    class Pyjo_Reactor_MyLoop(Pyjo.Reactor.Asyncio.object):
        def __init__(self, loop=None):
            super().__init__(loop=loop or asyncio.SelectorEventLoop(selectors.SelectSelector()))

    new = Pyjo_Reactor_MyLoop.new
    object = Pyjo_Reactor_MyLoop

The distribution contains the module and no ``__init__.py`` of ``Pyjo`` or
``Pyjo.Reactor``: those of Pyjoyment have the base class and keep the
namespace open with :func:`pkgutil.extend_path`, and another one would
replace them when both are installed in the same directory. Its package
depends on Pyjoyment and holds only the files of its own reactor::

    Pyjo/
        Reactor/
            MyLoop.py

The reactor is found when the distribution is installed next to Pyjoyment or
in another directory of :data:`sys.path`, and the environment variable
selects it::

    PYJO_REACTOR=Pyjo.Reactor.MyLoop

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Reactor <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Reactor.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.EventEmitter

from Pyjo.Loader import load_class

import builtins
import collections
import concurrent.futures
import os
import sys
import threading
import types
import weakref

from collections.abc import Awaitable, Callable, Coroutine, Generator
from pkgutil import extend_path
from typing import Any, Protocol, Self


type Anything = builtins.object


class HasFileno(Protocol):
    def fileno(self) -> int: ...


# A handle to watch: an object with a fileno() method, or a file descriptor
type Handle = HasFileno | int

# A callback of an I/O watcher gets the reactor and whether the handle is writable
type IOCallback = Callable[[Any, bool], Anything]

# A callback of a timer gets the reactor
type TimerCallback = Callable[[Any], Anything]


# Not in Mojolicious: what the futures of concurrent.futures and asyncio have in common
class Future[T](Protocol):
    def add_done_callback(self, fn: Callable[[Any], Anything], /) -> None: ...

    def cancel(self) -> bool: ...

    def cancelled(self) -> bool: ...

    def done(self) -> bool: ...

    def exception(self) -> BaseException | None: ...

    def result(self) -> T: ...

    def set_exception(self, exception: BaseException, /) -> None: ...

    def set_result(self, result: T, /) -> None: ...


_DETECTED: dict[str, str] = {}

# Not in Mojolicious: a namespace that other distributions can add reactors to
__path__ = extend_path(__path__, __name__)


class Pyjo_Reactor(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.Reactor` inherits all methods from :mod:`Pyjo.EventEmitter` and
    implements the following new ones.
    """

    # Not in Mojolicious: the frames of an event loop, below which a finalizer defers its cleanup
    event_loop_modules: tuple[str, ...] = ()
    """::

        modules = reactor.event_loop_modules

    The names of the modules of the event loop that the reactor runs on, as
    ``('trio',)``, whose code a finalizer of the garbage collector may
    interrupt. The cleanup of a stream, a server or a user agent that is freed
    in a frame of such a module, or of a module of a class of the reactor,
    waits for the next tick of the reactor, so that it does not change the
    structures that the event loop is changing. Defaults to ``()``. ::

        class Pyjo_Reactor_MyLoop(Pyjo.Reactor.Poll.object):
            event_loop_modules = ('myloop',)
    """

    def __init__(self) -> None:
        super().__init__()
        # Not in Mojolicious: the thread that made the reactor, where it runs
        self._thread = threading.get_ident()

        # Not in Mojolicious: the coroutines that run_coroutine runs, which wait for promises, and which only these
        # promises refer to otherwise, through the objects that they wait for, which the reactor refers to weakly, in a
        # cycle that the garbage collector would free, as the reactor of asyncio keeps its tasks
        self._coroutines: set[Coroutine[Any, Any, Any]] = set()
        _ALL.add(self)

    def again(self, id: str, after: float | None = None) -> None:
        """::

            reactor.again(id)
            reactor.again(id, 0.5)

        Restart timer and optionally change the invocation time. Meant to be
        overloaded in a subclass. Note that this method requires an active
        timer.
        """
        raise NotImplementedError('Method "again" not implemented by subclass')

    # Not in Mojolicious: what awaiting a promise of Pyjoyment waits on
    def awaitable(self, promise: Any) -> Awaitable[None]:
        """::

            awaitable = reactor.awaitable(promise)

        Return what ``await promise`` waits on, which completes when the
        promise is fulfilled or rejected. The base class gives one that
        :meth:`run_coroutine` drives, without asyncio, and a reactor of an event
        loop gives one of its loop, so that a promise can be awaited in the
        tasks of that loop.
        """
        return _Awaitable(promise)

    # Not in Mojolicious: how a coroutine runs as a promise, as Mojo's async sub
    def run_coroutine(
        self, coro: Coroutine[Any, Any, Any], resolve: Callable[[Any], Anything], reject: Callable[[Any], Anything]
    ) -> None:
        """::

            reactor.run_coroutine(coro, resolve, reject)

        Run a coroutine and call ``resolve`` with what it returns or
        ``reject`` with the exception it raises. The base class runs it at
        once, until it waits for a promise, as Mojo runs an ``async sub``,
        and continues it when the promise is fulfilled or rejected, so that it
        can await the promises of Pyjoyment without asyncio, and keeps it
        until it ends, as the reactor of asyncio keeps its tasks. A reactor of an
        event loop runs it as a task of its loop, where it can await anything
        of that loop.
        """

        coroutines = self._coroutines
        coroutines.add(coro)

        def step() -> None:
            try:
                waiting = coro.send(None)
            except StopIteration as e:
                coroutines.discard(coro)
                resolve(e.value)
                return
            except Exception as e:
                coroutines.discard(coro)
                reject(e)
                return
            then = getattr(waiting, 'then', None)
            if not callable(then):
                coroutines.discard(coro)
                coro.close()
                reject(TypeError(f'{_name(type(self))} cannot wait for {waiting!r}'))
                return
            then(resume, resume)

        def resume(*values: Any) -> None:
            step()

        step()

    @classmethod
    def detect(cls) -> str:
        """::

            name = Pyjo.Reactor.detect()

        Detect and load the best reactor implementation available, will try
        the value of the ``PYJO_REACTOR`` environment variable or
        :mod:`Pyjo.Reactor.Asyncio`, and return the name of its module. ::

            # Instantiate best reactor implementation available
            reactor = sys.modules[Pyjo.Reactor.detect()].new()
        """
        # Left out from Mojolicious: Mojo::Reactor::EV, as asyncio is the event loop
        default = 'Pyjo.Reactor.Asyncio'
        tried = os.environ.get('PYJO_REACTOR') or default
        # Not in Mojolicious: the error of the default reactor, which may not load, as asyncio without SYSTEMROOT on
        # Windows, where Mojo::Reactor::Poll always does; the first one, as a module that failed is not imported again
        if tried not in _DETECTED:
            _DETECTED[tried] = default if (e := load_class(tried)) else tried
            if tried == default and isinstance(e, Exception):
                raise e
        if isinstance(e := load_class(_DETECTED[tried]), Exception):
            raise e
        return _DETECTED[tried]

    # Not in Mojolicious: a future that a promise turns into
    def future(self) -> Future[Any]:
        """::

            future = reactor.future()

        Return a new future, which :meth:`Pyjo.Promise.Pyjo_Promise.to_future`
        turns a promise into. The base class gives a
        :class:`concurrent.futures.Future`, which needs no event loop and
        can be waited for in another thread, and a reactor of an event loop
        gives one of its loop, so that it can be awaited in the tasks of that
        loop.
        """
        return concurrent.futures.Future()

    def io(self, handle: Handle, cb: IOCallback) -> Self:
        """::

            reactor = reactor.io(handle, cb)

        Watch handle for I/O events, invoking the callback whenever handle
        becomes readable or writable. Meant to be overloaded in a subclass. ::

            # Callback will be executed twice if handle becomes readable and writable
            reactor.io(handle, lambda reactor, writable: print('Handle is writable' if writable else 'Handle is readable'))
        """
        raise NotImplementedError('Method "io" not implemented by subclass')

    @property
    def is_running(self) -> bool:
        """::

            boolean = reactor.is_running

        Check if reactor is running. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "is_running" not implemented by subclass')

    def next_tick(self, cb: TimerCallback) -> None:
        """::

            none = reactor.next_tick(cb)

        Execute callback as soon as possible, but not before returning or other
        callbacks that have been registered with this method, always returns
        ``None``. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "next_tick" not implemented by subclass')

    def one_tick(self) -> None:
        """::

            reactor.one_tick()

        Run reactor until an event occurs. Note that this method can recurse
        back into the reactor, so you need to be careful. Meant to be
        overloaded in a subclass. ::

            # Don't block longer than 0.5 seconds
            id = reactor.timer(0.5, lambda reactor: None)
            reactor.one_tick()
            reactor.remove(id)
        """
        raise NotImplementedError('Method "one_tick" not implemented by subclass')

    def recurring(self, after: float, cb: TimerCallback) -> str:
        """::

            id = reactor.recurring(0.25, cb)

        Create a new recurring timer, invoking the callback repeatedly after a
        given amount of time in seconds. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "recurring" not implemented by subclass')

    def remove(self, remove: Handle | str) -> bool:
        """::

            boolean = reactor.remove(handle)
            boolean = reactor.remove(id)

        Remove handle or timer. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "remove" not implemented by subclass')

    def reset(self) -> None:
        """::

            reactor.reset()

        Remove all handles and timers. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "reset" not implemented by subclass')

    def start(self) -> None:
        """::

            reactor.start()

        Start watching for I/O and timer events, this will block until
        :meth:`stop` is called. Note that some reactors stop automatically if
        there are no events being watched anymore. Meant to be overloaded in a
        subclass. ::

            # Start reactor only if it is not running already
            if not reactor.is_running:
                reactor.start()
        """
        raise NotImplementedError('Method "start" not implemented by subclass')

    def stop(self) -> None:
        """::

            reactor.stop()

        Stop watching for I/O and timer events. Meant to be overloaded in a
        subclass.
        """
        raise NotImplementedError('Method "stop" not implemented by subclass')

    def timer(self, after: float, cb: TimerCallback) -> str:
        """::

            id = reactor.timer(0.5, cb)

        Create a new timer, invoking the callback after a given amount of time
        in seconds. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "timer" not implemented by subclass')

    def watch(self, handle: Handle, read: bool, write: bool) -> Self:
        """::

            reactor = reactor.watch(handle, readable, writable)

        Change I/O events to watch handle for with true and false values.
        Meant to be overloaded in a subclass. Note that this method requires an
        active I/O watcher. ::

            # Watch only for readable events
            reactor.watch(handle, True, False)

            # Watch only for writable events
            reactor.watch(handle, False, True)

            # Watch for readable and writable events
            reactor.watch(handle, True, True)

            # Pause watching for events
            reactor.watch(handle, False, False)
        """
        raise NotImplementedError('Method "watch" not implemented by subclass')

    # Not in Mojolicious: run the cleanups that finalizers deferred at the next tick, in a way that is safe in the middle
    # of what the reactor does, as the garbage collector runs a finalizer there
    def _wake(self) -> None:
        pass


# Not in Mojolicious: the cleanups of the finalizers that the garbage collector ran in the middle of what an event loop
# does, as a socket that an object closes there, or an acceptor that it removes, changes the structures that the event
# loop or asyncio are changing; Perl runs a finalizer where the last reference goes, at the end of a statement. Each
# thread has its own, which the reactors of the thread run
_DEFERRED: dict[int | None, collections.deque[Callable[[], Anything]]] = {}

# The reactors that run the deferred cleanups
_ALL: 'weakref.WeakSet[Pyjo_Reactor]' = weakref.WeakSet()


# The reactor is the one of the object, none for an object without one
def _finalize(  # pyright: ignore[reportUnusedFunction]
    cb: Callable[[], Anything], reactor: Pyjo_Reactor | None = None
) -> None:
    # The cleanup runs at once, as Mojo's DESTROY runs, unless the garbage collector interrupted the code of an event
    # loop, in a frame of Pyjo.IOLoop, of a reactor or of its event loop, below the finalizer that calls it, or
    # ran in another thread than the one of the reactor of the object, the main one for an object without a reactor, as
    # a thread of name resolution, while that thread may be in the middle of what its event loop does, which the frames
    # of this thread do not show
    thread = threading.main_thread().ident if reactor is None else reactor._thread  # pyright: ignore[reportPrivateUsage]
    if threading.get_ident() == thread:
        prefixes = _prefixes()
        # The frame below the finalizer, none when the interpreter frees the object outside of any code
        frame = sys._getframe(1).f_back  # pyright: ignore[reportPrivateUsage]
        while frame is not None and not frame.f_code.co_filename.startswith(prefixes):
            frame = frame.f_back
        if frame is None:
            cb()
            return
    _DEFERRED.setdefault(thread, collections.deque()).append(cb)
    for reactor in list(_ALL):
        if reactor._thread == thread:  # pyright: ignore[reportPrivateUsage]
            reactor._wake()  # pyright: ignore[reportPrivateUsage]


def _drain(every: bool = False) -> None:  # pyright: ignore[reportUnusedFunction]
    # The cleanups of the thread, or of every thread, as at the end of the interpreter; they fail as a finalizer fails,
    # without an exception
    queues = list(_DEFERRED.values()) if every else [_DEFERRED.get(threading.get_ident())]
    for queue in queues:
        while queue:
            try:
                cb = queue.popleft()
            except IndexError:
                break
            try:
                cb()
            except Exception:
                pass


def _prefixes() -> tuple[str, ...]:
    # The directories of Pyjo.IOLoop and of the reactors of Pyjoyment, the modules of the classes of the reactors, also
    # of other distributions, which are not there when one of them is installed editable, and the modules of their
    # event loops that are loaded, a package as its directory
    pyjo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prefixes = {os.path.join(pyjo, 'IOLoop') + os.sep, os.path.join(pyjo, 'Reactor') + os.sep}
    for cls in {type(reactor) for reactor in list(_ALL)}:
        for base in cls.__mro__:
            if issubclass(base, Pyjo_Reactor) and (file := _file(sys.modules.get(base.__module__))):
                prefixes.add(file)
        for name in cls.event_loop_modules:
            if (module := sys.modules.get(name)) is not None and (file := _file(module)):
                prefixes.add(os.path.dirname(file) + os.sep if hasattr(module, '__path__') else file)
    return tuple(prefixes)


def _file(module: types.ModuleType | None) -> str | None:
    # As it is, as the frames of its code have it
    file = getattr(module, '__file__', None)
    return file if isinstance(file, str) else None


# What the base class gives to await: it waits for the promise itself
class _Awaitable:
    def __init__(self, promise: Any) -> None:
        self.promise = promise

    def __await__(self) -> Generator[Any, Any, None]:
        yield self.promise


def _name(cls: type) -> str:
    return f'{cls.__module__}.{cls.__qualname__}'


detect = Pyjo_Reactor.detect
new = Pyjo_Reactor.new
object = Pyjo_Reactor
Reactor = Pyjo_Reactor
