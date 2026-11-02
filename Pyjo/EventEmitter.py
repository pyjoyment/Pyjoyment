"""
Pyjo.EventEmitter - Event emitter base class
============================================
::

    from Pyjo.EventEmitter import EventEmitter

    class Cat(EventEmitter):
        # Emit events
        def poke(self):
            self.emit('roar', 3)

    # Subscribe to events
    tiger = Cat()

    @tiger.on('roar')
    def roar(tiger, times):
        for _ in range(times):
            print('RAWR!')

    tiger.poke()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.EventEmitter

    class Cat(Pyjo.EventEmitter.object):
        # Emit events
        def poke(self):
            self.emit('roar', 3)

    # Subscribe to events
    tiger = Cat.new()

    @tiger.on('roar')
    def roar(tiger, times):
        for _ in range(times):
            print('RAWR!')

    tiger.poke()

:mod:`Pyjo.EventEmitter` is a simple base class for event emitting objects.

Events
------

:mod:`Pyjo.EventEmitter` can emit the following events.

error
~~~~~
::

    e.on('error', lambda e, err: ...)

This is a special event for errors, it will not be emitted directly by this
class, but is fatal if unhandled. Subclasses may choose to emit it, but are
not required to do so. ::

    e.on('error', lambda e, err: print(f'This looks bad: {err}'))

An unhandled error raises a :mod:`Pyjo.Exception` with the name of the class
and the error in its message, and an error that is an exception is its cause.

Debugging
---------

You can set the ``PYJO_EVENTEMITTER_DEBUG`` environment variable to get some
advanced diagnostics information printed to ``sys.stderr``. ::

    PYJO_EVENTEMITTER_DEBUG=1

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::EventEmitter <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/EventEmitter.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.Base
import Pyjo.Exception

from Pyjo.Util import _call_hint, warn  # pyright: ignore[reportPrivateUsage]

import collections
import os
import weakref

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self, cast, overload


if TYPE_CHECKING:
    import Pyjo.Iterator
    import Pyjo.Promise


# A subscriber gets the emitter and the arguments of the event
type Callback = Callable[..., Any]

DEBUG = bool(os.environ.get('PYJO_EVENTEMITTER_DEBUG'))

# Not in Mojolicious: the emitters whose promises wait, with how many of them, by the id of the emitter. The promise of an
# emitter, as a socket that a coroutine waits for, may be the only way to it, as the reactor refers to the socket weakly,
# in a cycle that the garbage collector would free with the promise, as Perl keeps such a cycle
_holding: dict[int, list[Any]] = {}


class Pyjo_EventEmitter(Pyjo.Base.object):
    """
    :mod:`Pyjo.EventEmitter` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[Callback]] = {}

    def catch(self, cb: Callback) -> Self:
        """::

            e = e.catch(lambda e, err: ...)

        Subscribe to the ``error`` event. ::

            # Longer version
            e.on('error', lambda e, err: ...)
        """
        self.on('error', cb)
        return self

    def emit(self, name: str, *args: Any) -> Self:
        """::

            e = e.emit('foo')
            e = e.emit('foo', 123)

        Emit event.
        """
        # Unlike Mojolicious: an empty list of subscribers, as subscribers() leaves it, is no subscriber, and Mojo
        # swallows an unhandled error then
        if s := self._events.get(name):
            if DEBUG:
                warn(f'-- Emit {name} in {_name(type(self))} ({len(s)})')
            for cb in s:
                try:
                    cb(self, *args)
                except TypeError as e:
                    # Not in Mojolicious: the arguments of a callback, which Perl does not check
                    _call_hint(e, f'the callbacks of the event "{name}" get the emitter first')
                    raise
        else:
            if DEBUG:
                warn(f'-- Emit {name} in {_name(type(self))} (0)')
            if name == 'error':
                err = args[0] if args else ''
                e = Pyjo.Exception.new(f'{_name(type(self))}: {err}')
                # Not in Mojolicious: an error that is an exception is the cause
                if isinstance(err, BaseException):
                    raise e from err
                raise e

        return self

    # Not in Mojolicious: the events as an asynchronous iterator, as events.on of Node.js
    def events(self, name: str) -> 'Pyjo.Iterator.object[tuple[Any, ...]]':
        """::

            async for args in e.events('foo'):
                ...

        The arguments of the events as a :mod:`Pyjo.Iterator`, as a tuple for
        each event, which are queued until they are taken, and which ends at
        the event ``close`` or ``end``, and raises the error of the event
        ``error``. ::

            async for message, in ws.events('message'):
                print(f'Message: {message}')

            # The messages in capitals, in a chain
            async for message in ws.events('message').map(lambda args: args[0].upper()):
                print(f'Message: {message}')
        """
        import Pyjo.Iterator

        return Pyjo.Iterator.object(_Pull(self, name, False).iterate())

    def has_subscribers(self, name: str) -> bool:
        """::

            boolean = e.has_subscribers('foo')

        Check if event has subscribers.
        """
        # Unlike Mojolicious: an empty list of subscribers is no subscriber
        return bool(self._events.get(name))

    @overload
    def on[F: Callback](self, name: F, cb: None = None) -> F: ...

    @overload
    def on[F: Callback](self, name: str, cb: None = None) -> Callable[[F], F]: ...

    @overload
    def on[F: Callback](self, name: str, cb: F) -> F: ...

    def on(self, name: str | Callback, cb: Callback | None = None) -> Any:
        """::

            cb = e.on('foo', lambda e, *args: ...)

        Subscribe to event. ::

            e.on('foo', lambda e, *args: ...)

        Without a callback, it is a decorator, with the name of the event or
        of the function. ::

            @e.on('foo')
            def cb(e, *args):
                ...

            @e.on
            def foo(e, *args):
                ...
        """
        # Not in Mojolicious: a decorator
        if not isinstance(name, str):
            return self.on(name.__name__, name)
        if cb is None:
            event = name

            def decorator(cb: Callback) -> Callback:
                return self.on(event, cb)

            return decorator

        self._events.setdefault(name, []).append(cb)
        return cb

    # Not in Mojolicious: a promise of the event, as events.once of Node.js
    def once_p(self, name: str) -> 'Pyjo.Promise.object':
        """::

            promise = e.once_p('foo')

        Same as :meth:`once`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled with the arguments of the event, and rejected with the
        error of the event ``error``, which comes first. ::

            code, signal = await child.once_p('close')
        """
        # Imported here, as Pyjo.Promise uses Pyjo.IOLoop, whose classes are event emitters
        import Pyjo.Promise

        promise = Pyjo.Promise.new()
        failed: Callback | None = None

        def done(e: Any, *args: Any) -> None:
            if failed is not None:
                self.unsubscribe('error', failed)
            promise.resolve(*args)

        wrapper = self.once(name, done)
        if name != 'error':

            def error(e: Any, err: Any) -> None:
                self.unsubscribe(name, wrapper)
                promise.reject(err)

            failed = self.once('error', error)
        return self._hold(promise)

    @overload
    def once(self, name: Callback, cb: None = None) -> Callback: ...

    @overload
    def once(self, name: str, cb: None = None) -> Callable[[Callback], Callback]: ...

    @overload
    def once(self, name: str, cb: Callback) -> Callback: ...

    def once(self, name: str | Callback, cb: Callback | None = None) -> Any:
        """::

            cb = e.once('foo', lambda e, *args: ...)

        Subscribe to event and unsubscribe again after it has been emitted
        once. ::

            e.once('foo', lambda e, *args: ...)

        Without a callback, it is a decorator, as :meth:`on` is.
        """
        # Not in Mojolicious: a decorator
        if not isinstance(name, str):
            return self.once(name.__name__, name)
        event = name
        if cb is None:

            def once_decorator(cb: Callback) -> Callback:
                return self.once(event, cb)

            return once_decorator

        wrapper = _Once(weakref.proxy(self), event, cb)
        self.on(event, wrapper)

        return wrapper

    def subscribers(self, name: str) -> list[Callback]:
        """::

            subscribers = e.subscribers('foo')

        All subscribers for event. ::

            # Unsubscribe last subscriber
            e.unsubscribe('foo', e.subscribers('foo')[-1])

            # Change order of subscribers
            e.subscribers('foo').reverse()
        """
        return self._events.setdefault(name, [])

    # Not in Mojolicious: the emitter kept while the promise waits, as nothing else may refer to it, which leaves the promise
    # as handled as it was, so that a rejection that nothing handles is still reported
    def _hold(self, promise: 'Pyjo.Promise.object') -> 'Pyjo.Promise.object':
        key = id(self)
        entry = _holding.setdefault(key, [self, 0])
        entry[1] += 1

        def release(*args: Any) -> None:
            entry[1] -= 1
            if entry[1] <= 0 and _holding.get(key) is entry:
                del _holding[key]

        handled = promise._handled  # pyright: ignore[reportPrivateUsage]
        promise.then(release, release)
        promise._handled = handled  # pyright: ignore[reportPrivateUsage]
        return promise

    # Not in Mojolicious: the values of an event of a subclass that are pulled with promises, one pull for each event, so
    # that the promises and the iterators of a stream take its chunks in order, and with flow, the start and the stop of
    # the reading of a stream, which reads only while a promise waits, and the TimeoutError of its event timeout
    # A value is the first argument of the event, or all of them as a tuple, and an error of the event error, which ends
    # the pull, or only rejects the promises that wait, where the emitter goes on after it, as a datagram socket
    def _pull(self, name: str, flow: bool = False, *, value: bool = True, fatal: bool = True) -> '_Pull':
        pulls: dict[str, _Pull] = self.__dict__.setdefault('_pulls', {})
        if (pull := pulls.get(name)) is None:
            # The methods of a stream, which the subclass has
            stream = cast(Any, self)
            start, stop = (stream.start, stream.stop) if flow else (None, None)
            pull = pulls[name] = _Pull(self, name, value, start, stop, fatal)
            if flow:
                pull.subscribed.append(('timeout', self.on('timeout', pull.timeout)))
        return pull

    def unsubscribe(self, name: str, cb: Callback | None = None) -> Self:
        """::

            e = e.unsubscribe('foo')
            e = e.unsubscribe('foo', cb)

        Unsubscribe from event.
        """
        # One
        if cb is not None:
            self._events[name] = [c for c in self._events.get(name, []) if c != cb]
            if not self._events[name]:
                del self._events[name]

        # All
        else:
            self._events.pop(name, None)

        return self


# The wrapper of once, which unsubscribes itself as the argument of its call, as Mojo does with __SUB__: a closure that
# refers to itself is a cycle, which keeps the callback, and the objects of its closure, until the garbage collector runs
class _Once:
    __slots__ = ('cb', 'emitter', 'event')

    def __init__(self, emitter: Pyjo_EventEmitter, event: str, cb: Callback) -> None:
        self.cb, self.emitter, self.event = cb, emitter, event

    def __call__(self, *args: Any) -> Any:
        self.emitter.unsubscribe(self.event, self)
        return self.cb(*args)


# Not in Mojolicious: the events of an emitter, which are pulled with promises, as the streams of Node.js in their paused
# mode, and queued until they are, until the event close or end, or the error of the event error. With start and stop, the
# emitter is a stream, which reads only while a promise waits, so that it reads no more than it is asked for
class _Pull:
    def __init__(
        self,
        emitter: Pyjo_EventEmitter,
        name: str,
        value: bool,
        start: Callable[[], Any] | None = None,
        stop: Callable[[], Any] | None = None,
        fatal: bool = True,
    ) -> None:
        self.emitter, self.value, self.start, self.stop, self.fatal = emitter, value, start, stop, fatal
        self.queue: collections.deque[Any] = collections.deque()
        self.waiting: collections.deque[Pyjo.Promise.object] = collections.deque()
        self.done = False
        self.error: Any = None

        # An error that is not fatal, which came while no promise waited, for the next one
        self.missed: Any = None
        self.subscribed: list[tuple[str, Callback]] = [
            (name, emitter.on(name, self._push)),
            ('error', emitter.on('error', self._fail)),
            ('close', emitter.on('close', self._end)),
            ('end', emitter.on('end', self._end)),
        ]

    def iterate(self, size: int | None = None) -> '_Iterator':
        return _Iterator(self, size)

    # A promise that waits no more, as one whose time is up, which is rejected
    def cancel(self, promise: Any, err: Any) -> None:
        if promise in self.waiting:
            self.waiting.remove(promise)
            promise.reject(err)
            if not self.waiting and self.stop is not None:
                self.stop()

    # The end of an emitter that has ended before, as a stream that is closed
    def end(self) -> None:
        if not self.done and self.error is None:
            self._end(self.emitter)

    def timeout(self, emitter: Any) -> None:
        self._fail(emitter, TimeoutError('Inactivity timeout'))

    def close(self) -> None:
        for name, cb in self.subscribed:
            self.emitter.unsubscribe(name, cb)
        self.subscribed = []

    def next_p(self, size: int | None = None) -> 'Pyjo.Promise.object':
        import Pyjo.Promise

        if self.queue:
            item = self.queue.popleft()
            return Pyjo.Promise.resolve(self._split(item, size) if size is not None else item)
        if self.error is not None:
            return Pyjo.Promise.reject(self.error)
        if (missed := self.missed) is not None:
            self.missed = None
            return Pyjo.Promise.reject(missed)
        if self.done:
            return Pyjo.Promise.resolve(None)
        promise = Pyjo.Promise.new()
        self.waiting.append(promise)
        self.emitter._hold(promise)  # pyright: ignore[reportPrivateUsage]
        if size is not None:

            def split(item: Any = None) -> Any:
                return self._split(item, size)

            promise = promise.then(split)
        if self.start is not None:
            self.start()
        return promise

    def _end(self, emitter: Any, *args: Any) -> None:
        self.done = True
        self.close()
        while self.waiting:
            self.waiting.popleft().resolve(None)

    def _fail(self, emitter: Any, err: Any) -> None:
        if self.fatal:
            self.error = err
            self.close()
        elif not self.waiting:
            self.missed = err
        while self.waiting:
            self.waiting.popleft().reject(err)
        if not self.fatal and self.stop is not None:
            self.stop()

    def _push(self, emitter: Any, *args: Any) -> None:
        item = args[0] if self.value else args
        if self.waiting:
            self.waiting.popleft().resolve(item)
        else:
            self.queue.append(item)
        if not self.waiting and self.stop is not None:
            self.stop()

    # A chunk that is longer than what is asked for, whose rest is the next one
    def _split(self, item: Any, size: int) -> Any:
        if isinstance(item, bytes | bytearray) and len(item) > size:
            self.queue.appendleft(item[size:])
            return bytes(item[:size])
        return item


# Not in Mojolicious: an asynchronous iterator of the items of a pull, until None
class _Iterator:
    def __init__(self, pull: _Pull, size: int | None = None) -> None:
        self.pull, self.size = pull, size

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Any:
        if (item := await self.pull.next_p(self.size)) is None:
            raise StopAsyncIteration
        return item

    async def aclose(self) -> None:
        self.pull.close()


# The name of a class, as Perl's blessed gives the name of a package
def _name(cls: type) -> str:
    return f'{cls.__module__}.{cls.__qualname__}'


new = Pyjo_EventEmitter.new
object = Pyjo_EventEmitter
EventEmitter = Pyjo_EventEmitter
