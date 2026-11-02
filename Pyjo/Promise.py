"""
Pyjo.Promise - Promises/A+
==========================
::

    import Pyjo.UserAgent

    from Pyjo.Promise import Promise

    # Wrap continuation-passing style APIs with promises
    ua = Pyjo.UserAgent.new()

    def get_p(url):
        promise = Promise()

        def cb(ua, tx):
            err = tx.error
            if not err or err.get('code'):
                promise.resolve(tx)
            else:
                promise.reject(err['message'])

        ua.get(url, cb)
        return promise

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Promise
    import Pyjo.UserAgent

    # Wrap continuation-passing style APIs with promises
    ua = Pyjo.UserAgent.new()

    def get_p(url):
        promise = Pyjo.Promise.new()

        def cb(ua, tx):
            err = tx.error
            if not err or err.get('code'):
                promise.resolve(tx)
            else:
                promise.reject(err['message'])

        ua.get(url, cb)
        return promise

    # Perform non-blocking operations sequentially
    def mojo_cb(mojo):
        print(mojo.res.code)
        return get_p('https://metacpan.org')

    get_p('https://mojolicious.org').then(mojo_cb).then(
        lambda cpan: print(cpan.res.code)
    ).catch(lambda err: warn(f'Something went wrong: {err}')).wait()

    # Synchronize non-blocking operations (all)
    mojo = get_p('https://mojolicious.org')
    cpan = get_p('https://metacpan.org')
    Pyjo.Promise.all(mojo, cpan).then(
        lambda mojo, cpan: print(mojo[0].res.code, cpan[0].res.code)
    ).catch(lambda err: warn(f'Something went wrong: {err}')).wait()

    # Synchronize non-blocking operations (race)
    mojo = get_p('https://mojolicious.org')
    cpan = get_p('https://metacpan.org')
    Pyjo.Promise.race(mojo, cpan).then(
        lambda tx: print(tx.req.url, 'won!')
    ).catch(lambda err: warn(f'Something went wrong: {err}')).wait()

    # Await a promise in a coroutine
    @Pyjo.Promise.coroutine
    async def code(url):
        tx = await get_p(url)
        return tx.res.code

    code('https://mojolicious.org').then(print).wait()

:mod:`Pyjo.Promise` is a Python implementation of
`Promises/A+ <https://promisesaplus.com>`_ and a superset of
`ES6 Promises <https://duckduckgo.com/?q=\\\\mdn%20Promise>`_.

States
------

A promise is an object representing the eventual completion or failure of a
non-blocking operation. It allows non-blocking functions to return values,
like blocking functions. But instead of immediately returning the final value,
the non-blocking function returns a promise to supply the value at some point
in the future.

A promise can be in one of three states:

pending
    Initial state, neither fulfilled nor rejected.

fulfilled
    Meaning that the operation completed successfully.

rejected
    Meaning that the operation failed.

A pending promise can either be fulfilled with a value or rejected with a
reason. When either happens, the associated handlers queued up by a promise's
:meth:`~Pyjo_Promise.then` method are called.

Values
------

A promise is fulfilled or rejected with any number of values, and the
handlers get them as arguments. What a handler returns is the value of the new
promise, ``None`` is no value, and a promise is adopted, so a handler that
passes several values on returns a promise of them. ::

    promise.then(lambda *values: Pyjo.Promise.resolve(*values))

Coroutines
----------

``await promise`` waits for the promise in a coroutine, and gives its value,
a tuple of several values, or ``None`` for none. A rejection raises the
exception the promise was rejected with, or a :mod:`Pyjo.Exception` of the
first reason. A coroutine is a promise with :meth:`~Pyjo_Promise.new` or
:func:`coroutine`. The reactor of the event loop runs it: a coroutine awaits the
promises of Pyjoyment with any reactor, and with :mod:`Pyjo.Reactor.Asyncio`
anything of asyncio too, and a promise can be awaited in any asyncio task.
Another awaitable, as a future of asyncio, is a promise with
:meth:`~Pyjo_Promise.new` too, and :meth:`~Pyjo_Promise.to_future` turns a
promise into a future of the reactor. ::

    async def main():
        title = (await get_p('https://mojolicious.org')).res.dom().at('title').text

Debugging
---------

You can set the ``PYJO_PROMISE_DEBUG`` environment variable to get some
advanced diagnostics information printed to ``sys.stderr``. ::

    PYJO_PROMISE_DEBUG=1

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Promise <https://github.com/mojolicious/mojo/blob/v9.52/lib/Mojo/Promise.pm>`_
of Mojolicious 9.52.

Functions
---------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Reactor

from Pyjo.Util import warn

import atexit
import builtins
import collections
import concurrent.futures
import functools
import os
import socket
import warnings
import weakref

from collections.abc import Awaitable, Callable, Coroutine, Generator
from typing import TYPE_CHECKING, Any, Concatenate, cast


type Anything = builtins.object

# A handler gets the values of the promise
type Handler = Callable[..., Any]

DEBUG = bool(os.environ.get('PYJO_PROMISE_DEBUG'))


class _hybridmethod[**P, R]:
    """A method that is called on the class or on an object, as Perl's can be."""

    def __init__(self, func: Callable[Concatenate[Any, P], R]) -> None:
        self.func = func
        self.__doc__ = func.__doc__

    def __get__(self, obj: Anything, objtype: type | None = None) -> Callable[P, R]:
        def bound(*args: P.args, **kwargs: P.kwargs) -> R:
            return self.func(obj if obj is not None else objtype, *args, **kwargs)

        bound.__doc__ = self.__doc__
        return bound


class Pyjo_Promise(Pyjo.Base.object):
    """
    :mod:`Pyjo.Promise` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(
        self, cb: Callable[[Handler, Handler], Anything] | Awaitable[Any] | concurrent.futures.Future[Any] | None = None
    ) -> None:
        """::

            promise = Pyjo.Promise.new()
            promise = Pyjo.Promise.new(lambda resolve, reject: ...)
            promise = Pyjo.Promise.new(coroutine)
            promise = Pyjo.Promise.new(future)

        Construct a new :mod:`Pyjo.Promise` object. ::

            # Wrap a continuation-passing style API
            def cb(resolve, reject):
                Pyjo.IOLoop.timer(5, lambda loop: resolve('Lucky!') if random.randint(0, 1) else reject('Unlucky!'))

            promise = Pyjo.Promise.new(cb)

        A coroutine is run by the reactor of :attr:`ioloop`, and the promise
        is fulfilled with what it returns, or rejected with the exception it
        raises. ::

            # Wrap a coroutine
            async def lucky():
                await Pyjo.Promise.timer(5)
                return 'Lucky!'

            promise = Pyjo.Promise.new(lucky())

        Another awaitable, like an :class:`asyncio.Future` or an
        :class:`asyncio.Task`, is awaited in a coroutine, so with a reactor
        that can await it, as :mod:`Pyjo.Reactor.Asyncio`. ::

            # Wrap a future of asyncio
            future = asyncio.get_running_loop().run_in_executor(None, time.sleep, 1)
            promise = Pyjo.Promise.new(future)

        A :class:`concurrent.futures.Future`, which is done in another thread
        or process, is waited for with any reactor, which the thread that
        completes the future wakes up. ::

            # Wrap a future of a pool of threads
            with concurrent.futures.ThreadPoolExecutor() as executor:
                promise = Pyjo.Promise.new(executor.submit(time.sleep, 1))
                promise.wait()
        """
        self._debug: Pyjo.Exception.object | None = None
        self._handled = False
        self._ioloop: weakref.ref[Pyjo.IOLoop.object] | None = None
        self._reject: list[Handler] = []
        self._resolve: list[Handler] = []
        self._results: tuple[Any, ...] | None = None
        self._status = ''

        if DEBUG:
            self._debug = Pyjo.Exception.new().trace()

        # Not in Mojolicious: a future of concurrent.futures, done in another thread
        if isinstance(cb, concurrent.futures.Future):
            _wait_future(self, cast(concurrent.futures.Future[Any], cb))

        # Not in Mojolicious: a coroutine, or another awaitable in one, as a future of asyncio
        elif isinstance(cb, Awaitable):
            coro = cast(Coroutine[Any, Any, Any], cb) if isinstance(cb, Coroutine) else _await(cast(Awaitable[Any], cb))

            def resolve(value: Any) -> None:
                self.resolve() if value is None else self.resolve(value)

            self.ioloop.reactor.run_coroutine(coro, resolve, lambda e: self.reject(e))

        elif cb is not None:
            cb(lambda *values: self.resolve(*values), lambda *values: self.reject(*values))

    @property
    def ioloop(self) -> Pyjo.IOLoop.object:
        """::

            loop = promise.ioloop
            promise.ioloop = Pyjo.IOLoop.new()

        Event loop object to control, defaults to the global
        :mod:`Pyjo.IOLoop` singleton. Note that this attribute is weakened.
        """
        if self._ioloop is None:
            self._ioloop = weakref.ref(Pyjo.IOLoop.singleton)
        if (loop := self._ioloop()) is None:
            raise ReferenceError('weakly-referenced object no longer exists')
        return loop

    @ioloop.setter
    def ioloop(self, value: Pyjo.IOLoop.object) -> None:
        self._ioloop = weakref.ref(value)

    def __await__(self) -> Generator[Any, Any, Any]:
        """::

            value = await promise

        Wait for the promise in a coroutine and return its value, a tuple of
        several values, or ``None`` for none, or raise the exception it was
        rejected with, or a :mod:`Pyjo.Exception` of the first reason.
        """
        # Mojo's AWAIT_* methods
        self._handled = True
        yield from self.ioloop.reactor.awaitable(self).__await__()

        results: tuple[Any, ...] = self._results or ()
        if self._status == 'resolve':
            return _result(results)
        raise _exception(results)

    if not TYPE_CHECKING:
        # Not in Mojolicious: an attribute of the value taken from the promise itself, as of the result of a request of
        # get_p without await; out of the sight of type checkers, which would take any attribute of a promise for one
        def __getattr__(self, name: str) -> Any:
            message = f"'{type(self).__name__}' object has no attribute '{name}'"
            if not name.startswith('_'):
                message += ', a promise gives its value to await or to a callback of then'
            raise AttributeError(message, name=name, obj=self)

    def __del__(self) -> None:
        if getattr(self, '_handled', True) or getattr(self, '_status', '') != 'reject' or self._results is None:
            return
        try:
            warnings.warn(f'Unhandled rejected promise: {" ".join(str(r) for r in self._results)}', stacklevel=2)
            if DEBUG and (debug := self._debug) is not None:
                debug.message = '-- Destroyed promise\n'
                debug.verbose = True
                warn(debug.to_str())
        except Exception:
            pass

    @classmethod
    def all(cls, *promises: 'Pyjo_Promise') -> 'Pyjo_Promise':
        """::

            new = Pyjo.Promise.all(*promises)

        Returns a new :mod:`Pyjo.Promise` object that either fulfills when all
        of the passed :mod:`Pyjo.Promise` objects have fulfilled or rejects as
        soon as one of them rejects. If the returned promise fulfills, it is
        fulfilled with the values from the fulfilled promises in the same order
        as the passed promises, a list of the values of each.
        """
        return _all(2, promises)

    @classmethod
    def all_settled(cls, *promises: 'Pyjo_Promise') -> 'Pyjo_Promise':
        """::

            new = Pyjo.Promise.all_settled(*promises)

        Returns a new :mod:`Pyjo.Promise` object that fulfills when all of the
        passed :mod:`Pyjo.Promise` objects have fulfilled or rejected, with
        dicts that describe the outcome of each promise.
        """
        return _all(0, promises)

    @classmethod
    def any(cls, *promises: 'Pyjo_Promise') -> 'Pyjo_Promise':
        """::

            new = Pyjo.Promise.any(*promises)

        Returns a new :mod:`Pyjo.Promise` object that fulfills as soon as one
        of the passed :mod:`Pyjo.Promise` objects fulfills, with the value from
        that promise.
        """
        return _all(3, promises)

    def catch(self, cb: Handler) -> 'Pyjo_Promise':
        """::

            new = promise.catch(lambda *reason: ...)

        Appends a rejection handler callback to the promise, and returns a new
        :mod:`Pyjo.Promise` object resolving to the return value of the
        callback if it is called, or to its original fulfillment value if the
        promise is instead fulfilled. ::

            # Longer version
            new = promise.then(None, lambda *reason: ...)

            # Pass along the rejection reason
            def cb(*reason):
                warn(f'Something went wrong: {reason[0]}')
                return Pyjo.Promise.reject(*reason)

            promise.catch(cb)

            # Change the rejection reason
            promise.catch(lambda *reason: f'This is bad: {reason[0]}')
        """
        return self.then(None, cb)

    def clone(self) -> 'Pyjo_Promise':
        """::

            new = promise.clone()

        Return a new :mod:`Pyjo.Promise` object cloned from this promise that
        is still pending.
        """
        new = type(self)()
        new.ioloop = self.ioloop
        return new

    def lastly(self, cb: Callable[[], Any]) -> 'Pyjo_Promise':
        """::

            new = promise.lastly(lambda: ...)

        Appends a fulfillment and rejection handler to the promise, and returns
        a new :mod:`Pyjo.Promise` object resolving to the original fulfillment
        value or rejection reason. ``finally_`` is an alias, the name of
        Mojolicious with an underscore. ::

            # Do something on fulfillment and rejection
            promise.lastly(lambda: print('We are done!'))
        """
        # Renamed from Mojolicious: finally, a keyword of Python, as Bluebird names it
        return self._finally(True, cb)

    # The name of Mojolicious, with an underscore as finally is a keyword of Python
    finally_ = lastly

    @classmethod
    def map(cls, cb: Callable[[Any], 'Pyjo_Promise'], *items: Any, concurrency: int = 0) -> 'Pyjo_Promise':
        """::

            new = Pyjo.Promise.map(lambda item: ..., *items)
            new = Pyjo.Promise.map(lambda item: ..., *items, concurrency=3)

        Apply a function that returns a :mod:`Pyjo.Promise` to each item in a
        list of items while optionally limiting concurrency. Returns a
        :mod:`Pyjo.Promise` that collects the results in the same manner as
        :meth:`all`. If any item's promise is rejected, any remaining items
        which have not yet been mapped will not be. ::

            # Perform 3 requests at a time concurrently
            Pyjo.Promise.map(lambda url: ua.get_p(url), *urls, concurrency=3).then(
                lambda *results: [print(r[0].res.dom().at('title').text) for r in results]
            )

        These options are currently available:

        concurrency
            ::

                concurrency=3

            The maximum number of items that are in progress at the same time.
        """
        if not concurrency or len(items) <= concurrency:
            return cls.all(*(cb(item) for item in items))

        # Deques, whose popleft takes the first item as shift of Perl does, where pop(0) of a list moves all the others
        rest = collections.deque(items[concurrency:])
        start = [cb(item) for item in items[:concurrency]]
        wait = [start[0].clone() for _ in rest]
        waiting = collections.deque(wait)

        def start_next(*values: Any) -> None:
            if not len(rest):
                return
            item = rest.popleft()
            chain = waiting.popleft()

            def resolve(*values: Any) -> None:
                chain.resolve(*values)
                start_next()

            def reject(*values: Any) -> None:
                chain.reject(*values)
                rest.clear()

            cb(item).then(resolve, reject)

        for promise in start:
            promise.then(start_next, lambda *values: None)

        return cls.all(*start, *wait)

    @classmethod
    def race(cls, *promises: 'Pyjo_Promise') -> 'Pyjo_Promise':
        """::

            new = Pyjo.Promise.race(*promises)

        Returns a new :mod:`Pyjo.Promise` object that fulfills or rejects as
        soon as one of the passed :mod:`Pyjo.Promise` objects fulfills or
        rejects, with the value or reason from that promise.
        """
        return _all(1, promises)

    @_hybridmethod
    def reject(self_or_cls: 'Pyjo_Promise | type[Pyjo_Promise]', *reason: Any) -> 'Pyjo_Promise':  # noqa: N805
        """::

            new = Pyjo.Promise.reject(*reason)
            promise = promise.reject(*reason)

        Build rejected :mod:`Pyjo.Promise` object or reject the promise with one
        or more rejection reasons. ::

            # Longer version
            promise = Pyjo.Promise.new().reject(*reason)
        """
        return Pyjo_Promise._settle(self_or_cls, 'reject', reason)

    @_hybridmethod
    def resolve(self_or_cls: 'Pyjo_Promise | type[Pyjo_Promise]', *value: Any) -> 'Pyjo_Promise':  # noqa: N805
        """::

            new = Pyjo.Promise.resolve(*value)
            promise = promise.resolve(*value)

        Build resolved :mod:`Pyjo.Promise` object or resolve the promise with
        one or more fulfillment values. ::

            # Longer version
            promise = Pyjo.Promise.new().resolve(*value)
        """
        return Pyjo_Promise._settle(self_or_cls, 'resolve', value)

    def then(self, resolve: Handler | None = None, reject: Handler | None = None) -> 'Pyjo_Promise':
        """::

            new = promise.then(lambda *value: ...)
            new = promise.then(lambda *value: ..., lambda *reason: ...)
            new = promise.then(None, lambda *reason: ...)

        Appends fulfillment and rejection handlers to the promise, and returns
        a new :mod:`Pyjo.Promise` object resolving to the return value of the
        called handler. ::

            # Pass along the fulfillment value or rejection reason
            def value_cb(*value):
                print(f'The result is {value[0]}')
                return Pyjo.Promise.resolve(*value)

            def reason_cb(*reason):
                warn(f'Something went wrong: {reason[0]}')
                return Pyjo.Promise.reject(*reason)

            promise.then(value_cb, reason_cb)

            # Change the fulfillment value or rejection reason
            promise.then(lambda *value: f'This is good: {value[0]}', lambda *reason: f'This is bad: {reason[0]}')
        """
        new = self.clone()
        self._handled = True
        self._resolve.append(lambda *results: _then_cb(new, resolve, 'resolve', results))
        self._reject.append(lambda *results: _then_cb(new, reject, 'reject', results))

        if self._results is not None:
            self._defer()

        return new

    @_hybridmethod
    def timer(self_or_cls: 'Pyjo_Promise | type[Pyjo_Promise]', after: float, *value: Any) -> 'Pyjo_Promise':  # noqa: N805
        """::

            new = Pyjo.Promise.timer(5, 'Success!')
            promise = promise.timer(5, 'Success!')
            promise = promise.timer(5)

        Create a new :mod:`Pyjo.Promise` object with a timer or attach a timer
        to an existing promise. The promise will be resolved after the given
        amount of time in seconds with or without a value, unless it has already
        been settled. Note that this does not delay the resolution of an existing
        promise, to add a delay to a promise chain you have to return a new timer
        promise instead. ::

            # Wait 5 seconds between two steps
            promise.then(lambda *_: Pyjo.Promise.timer(5)).then(lambda *_: print('Five seconds later'))
        """
        return _timer(self_or_cls, 'resolve', after, value)

    @_hybridmethod
    def timeout(self_or_cls: 'Pyjo_Promise | type[Pyjo_Promise]', after: float, *reason: Any) -> 'Pyjo_Promise':  # noqa: N805
        """::

            new = Pyjo.Promise.timeout(5, 'Timeout!')
            promise = promise.timeout(5, 'Timeout!')
            promise = promise.timeout(5)

        Create a new :mod:`Pyjo.Promise` object with a timeout or attach a
        timeout to an existing promise. The promise will be rejected after the
        given amount of time in seconds with a reason, which defaults to
        ``Promise timeout``, unless it has already been settled.
        """
        return _timer(self_or_cls, 'reject', after, reason)

    # Not in Mojolicious: a future of the reactor
    def to_future(self) -> Pyjo.Reactor.Future[Any]:
        """::

            future = promise.to_future()

        Turn promise into a future of the reactor of :attr:`ioloop`, an
        :class:`asyncio.Future` of its loop with :mod:`Pyjo.Reactor.Asyncio`,
        or a :class:`concurrent.futures.Future` with a reactor without asyncio,
        as :mod:`Pyjo.Reactor.Poll`. The future is done when the promise is
        fulfilled or rejected, with what ``await promise`` gives: its value, a
        tuple of several values, or ``None`` for none, or the exception it was
        rejected with, or a :mod:`Pyjo.Exception` of the first reason. ::

            # Print the value when the future is done
            future = Pyjo.Promise.timer(1, 'Done!').to_future()
            future.add_done_callback(lambda future: print(future.result()))
        """
        future = self.ioloop.reactor.future()

        def resolve(*values: Any) -> None:
            if not future.done():
                future.set_result(_result(values))

        def reject(*reason: Any) -> None:
            if not future.done():
                future.set_exception(_exception(reason))

        self.then(resolve, reject)
        return future

    def wait(self) -> None:
        """::

            promise.wait()

        Start :attr:`ioloop` and stop it again once the promise has been
        fulfilled or rejected, does nothing when :attr:`ioloop` is already
        running.
        """
        if (loop := self.ioloop).is_running:
            return
        done = False

        def finish() -> None:
            nonlocal done
            done = True
            loop.stop()

        self._finally(False, finish).catch(lambda *reason: None)
        while not done:
            loop.start()

    # Not in Mojolicious: the value of the promise for a caller that cannot await it, as the for of Pyjo.Iterator, which
    # waits for it with the event loop, or fails in an event loop that runs already, where wait() returns at once
    def _wait_value(self) -> Any:
        if not self._status:
            if self.ioloop.is_running:
                raise RuntimeError('A promise cannot be waited for in a running event loop, await it instead')
            self.wait()
        self._handled = True
        results: tuple[Any, ...] = self._results or ()
        if self._status == 'resolve':
            return _result(results)
        raise _exception(results)

    @staticmethod
    def _settle(
        self_or_cls: 'Pyjo_Promise | type[Pyjo_Promise]', status: str, results: tuple[Any, ...]
    ) -> 'Pyjo_Promise':
        first = results[0] if len(results) else None
        thenable = first is not None and not isinstance(first, type) and callable(getattr(first, 'then', None))
        if isinstance(self_or_cls, type):
            if thenable and status == 'resolve' and isinstance(first, Pyjo_Promise):
                return first
            promise = self_or_cls.new()
        else:
            promise = self_or_cls

        if thenable and status == 'resolve':

            def resolve(*values: Any) -> None:
                promise.resolve(*values)

            def reject(*values: Any) -> None:
                promise.reject(*values)

            cast(Any, first).then(resolve, reject)

        elif promise._results is None:
            promise._results, promise._status = results, status
            promise._defer()

        return promise

    def _defer(self) -> None:
        if (results := self._results) is None:
            return
        cbs = self._resolve if self._status == 'resolve' else self._reject
        self._resolve, self._reject = [], []

        def run(loop: Any) -> None:
            for cb in cbs:
                cb(*results)

        self.ioloop.next_tick(run)

    def _finally(self, handled: bool, cb: Callable[[], Any]) -> 'Pyjo_Promise':
        new = self.clone()

        def finally_cb(*results: Any) -> 'Pyjo_Promise':
            value = cb()
            return (new.resolve() if value is None else new.resolve(value)).then(lambda *values: _values(results))

        before = self._handled
        self.catch(finally_cb)
        then = self.then(finally_cb)
        if not before and not handled:
            self._handled = False

        return then


# Not in Mojolicious: a decorator of a coroutine function, as Mojo's async sub
def coroutine[**P](func: Callable[P, Coroutine[Any, Any, Any]]) -> Callable[P, Pyjo_Promise]:
    """::

        @Pyjo.Promise.coroutine
        async def title(url):
            tx = await ua.get_p(url)
            return tx.res.dom().at('title').text

        title('https://mojolicious.org').then(print).wait()

    Turn a coroutine function into a function that returns a
    :mod:`Pyjo.Promise` of the coroutine, as ``async sub`` does in Mojo.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Pyjo_Promise:
        return Pyjo_Promise.new(func(*args, **kwargs))

    return wrapper


def _all(type: int, promises: tuple[Pyjo_Promise, ...]) -> Pyjo_Promise:
    all = promises[0].clone()
    results: list[Any] = [None] * len(promises)
    remaining = len(promises)

    def resolve_all(*values: Any) -> None:
        all.resolve(*values)

    def reject_all(*values: Any) -> None:
        all.reject(*values)

    for i, promise in enumerate(promises):
        # "race"
        if type == 1:
            promise.then(resolve_all, reject_all)

        # "all"
        elif type == 2:

            def fulfilled(*values: Any, i: int = i) -> None:
                nonlocal remaining
                results[i] = list(values)
                remaining -= 1
                if remaining <= 0:
                    all.resolve(*results)

            promise.then(fulfilled, reject_all)

        # "any"
        elif type == 3:

            def rejected(*values: Any, i: int = i) -> None:
                nonlocal remaining
                results[i] = list(values)
                remaining -= 1
                if remaining <= 0:
                    all.reject(*results)

            promise.then(resolve_all, rejected)

        # "all_settled"
        else:

            def settled_fulfilled(*values: Any, i: int = i) -> None:
                nonlocal remaining
                results[i] = {'status': 'fulfilled', 'value': list(values)}
                remaining -= 1
                if remaining <= 0:
                    all.resolve(*results)

            def settled_rejected(*values: Any, i: int = i) -> None:
                nonlocal remaining
                results[i] = {'status': 'rejected', 'reason': list(values)}
                remaining -= 1
                if remaining <= 0:
                    all.resolve(*results)

            promise.then(settled_fulfilled, settled_rejected)

    return all


def _then_cb(new: Pyjo_Promise, cb: Handler | None, method: str, results: tuple[Any, ...]) -> Pyjo_Promise:
    if cb is None:
        return new.resolve(*results) if method == 'resolve' else new.reject(*results)

    try:
        res = cb(*results)
    except Exception as e:
        return new.reject(e)
    # Not in Mojolicious: a callback of Python returns one value, None is no value
    return new.resolve() if res is None else new.resolve(res)


def _timer(
    self_or_cls: Pyjo_Promise | type[Pyjo_Promise], method: str, after: float, results: tuple[Any, ...]
) -> Pyjo_Promise:
    promise = self_or_cls.new() if isinstance(self_or_cls, type) else self_or_cls
    if method == 'reject' and not len(results):
        results = ('Promise timeout',)

    def timer(loop: Any) -> None:
        promise.resolve(*results) if method == 'resolve' else promise.reject(*results)

    promise.ioloop.timer(after, timer)
    return promise


# A future of concurrent.futures settles the promise in the thread of the reactor, which a socket pair wakes up from the
# thread that completes the future, as the resolver of Pyjo.IOLoop.Client does, so that it works with any reactor
def _wait_future(promise: Pyjo_Promise, future: concurrent.futures.Future[Any]) -> None:
    reactor = promise.ioloop.reactor
    reader, writer = socket.socketpair()
    reader.setblocking(False)
    _pairs.update((reader, writer))

    def ready(reactor: Any, writable: bool) -> None:
        reactor.remove(reader)
        _pairs.difference_update((reader, writer))
        reader.close()
        writer.close()
        if future.cancelled():
            promise.reject(concurrent.futures.CancelledError())
        elif (e := future.exception()) is not None:
            promise.reject(e)
        elif (value := future.result()) is None:
            promise.resolve()
        else:
            promise.resolve(value)

    reactor.io(reader, ready).watch(reader, True, False)
    future.add_done_callback(lambda future: writer.send(b'\x00'))


# The socket pairs of the futures that are not done when the program ends, after the threads of concurrent.futures, whose
# event loop does not run again to see them done
_pairs: set[socket.socket] = set()


@atexit.register
def _close_pairs() -> None:
    for handle in list(_pairs):
        handle.close()
    _pairs.clear()


# An awaitable in a coroutine, which the reactor runs
async def _await(awaitable: Awaitable[Any]) -> Any:
    return await awaitable


# The exception of a rejection: the reason, or an exception of it
def _exception(reason: tuple[Any, ...]) -> BaseException:
    if len(reason) and isinstance(reason[0], BaseException):
        return reason[0]
    return Pyjo.Exception.new(reason[0] if len(reason) else None)


# The value of a fulfillment: none, one, or a tuple of several
def _result(values: tuple[Any, ...]) -> Any:
    return None if not len(values) else values[0] if len(values) == 1 else values


# The value of a handler that passes values on: none, one, or a promise of several
def _values(values: tuple[Any, ...]) -> Any:
    if not len(values):
        return None
    if len(values) == 1:
        return values[0]
    return Pyjo_Promise.resolve(*values)


new = Pyjo_Promise.new
object = Pyjo_Promise
Promise = Pyjo_Promise

all = Pyjo_Promise.all
all_settled = Pyjo_Promise.all_settled
any = Pyjo_Promise.any
map = Pyjo_Promise.map
race = Pyjo_Promise.race
reject = Pyjo_Promise.reject
resolve = Pyjo_Promise.resolve
timer = Pyjo_Promise.timer
timeout = Pyjo_Promise.timeout
