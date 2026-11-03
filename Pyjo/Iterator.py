"""
Pyjo.Iterator - Lazy iterator
=============================
::

    from Pyjo.Iterator import Iterator

    # Elements of an iterable, one by one, through a chain
    for word in Iterator(['just', 'works']).map(lambda e: e.upper()):
        print(word)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Iterator

    # Three requests at a time, and their titles in the order of the URLs
    titles = Pyjo.Iterator.new(urls).map(ua.get_p, concurrency=3).map(lambda tx: tx.result.dom().at('title').text)
    for title in titles:
        print(title)

    # The same in a coroutine
    async for title in titles:
        print(title)

    # A collection, lazily
    from Pyjo.Collection import c
    c(1, 2, 3).iterate().map(lambda e: e * 2).join(', ').say()

:mod:`Pyjo.Iterator` is a lazy iterator of the elements of an iterable or of an
asynchronous iterable, with the methods of :mod:`Pyjo.Collection`. Each step
of a chain passes an element on to the next one as soon as it has it, so that
the first element is processed before the last one is taken from the source.
It is iterated with ``for`` and with ``async for`` alike, and each iteration
takes the elements of the source anew, which a source that is iterated once,
as a generator or a stream, gives once.

A callback may return a :mod:`Pyjo.Promise` or another awaitable, or be a
coroutine function, and the iterator passes on the value that it waits for.
``async for`` awaits it, and ``for`` waits for it with
:meth:`~Pyjo.Promise.Pyjo_Promise.wait`, which runs the event loop, so that
``for`` cannot wait in an event loop that runs already, as in an action of a
server, where it raises a :class:`RuntimeError`, and where ``async for`` or a
method whose name ends with ``_p`` waits instead. ``for`` takes the elements of an
asynchronous iterable, as a stream, the same way. ::

    # The messages of a stream as JSON, in a coroutine
    async for request in messages.iterate().map(Pyjo.JSON.decode_json):
        ...

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious; it is inspired by the iterator helpers of
JavaScript, with the methods of :mod:`Pyjo.Collection`.
"""

import Pyjo.Base
import Pyjo.Collection
import Pyjo.Promise
import Pyjo.String.Unicode

from Pyjo.Collection import _call, _flatten, _str  # pyright: ignore[reportPrivateUsage]

import builtins
import collections
import collections.abc
import inspect
import itertools
import re

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterable
from typing import Any, Self, overload


# The sync and the async form of a step of a chain, which take the elements of the step before
type SyncStep = Callable[[collections.abc.Iterator[Any]], collections.abc.Iterator[Any]]
type AsyncStep = Callable[[AsyncIterator[Any]], AsyncIterator[Any]]


class Pyjo_Iterator[T](Pyjo.Base.object):
    """
    :mod:`Pyjo.Iterator` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(self, iterable: Iterable[T] | AsyncIterable[T] = ()) -> None:
        self._source: Iterable[Any] | AsyncIterable[Any] = iterable
        self._step: tuple[Pyjo_Iterator[Any], SyncStep, AsyncStep] | None = None

    def __aiter__(self) -> AsyncIterator[T]:
        """::

            async for e in iterator:
                ...

        Take the elements in a coroutine, and await the values of the
        callbacks.
        """
        if self._step is not None:
            previous, _, asynchronous = self._step
            return asynchronous(aiter(previous))
        if isinstance(self._source, Iterable):
            return _to_async(iter(self._source))
        return aiter(self._source)

    def __iter__(self) -> collections.abc.Iterator[T]:
        """::

            for e in iterator:
                ...

        Take the elements, and wait for the values of the callbacks with the
        event loop.
        """
        if self._step is not None:
            previous, sync, _ = self._step
            return sync(iter(previous))
        if isinstance(self._source, Iterable):
            return iter(self._source)
        return _to_sync(aiter(self._source))

    def compact(self) -> Self:
        """::

            new = iterator.compact()

        Pass on all elements that are not ``None`` and not an empty string. ::

            # "0, 1, 2, 3"
            Pyjo.Iterator.new([0, 1, None, 2, '', 3]).compact().join(', ')
        """

        def keep(e: Any) -> bool:
            return e is not None and (not isinstance(e, (str, bytes)) or len(e) > 0)

        def sync(source: collections.abc.Iterator[Any]) -> collections.abc.Iterator[Any]:
            return (e for e in source if keep(e))

        async def asynchronous(source: AsyncIterator[Any]) -> AsyncIterator[Any]:
            async for e in source:
                if keep(e):
                    yield e

        return self._chain(sync, asynchronous)

    def each(self, cb: Callable[[T, int], Any]) -> Self:
        """::

            iterator = iterator.each(lambda e, num: ...)

        Evaluate callback for each element, one after another, and wait for
        its value. The element will be the first argument passed to the
        callback, and its number the second. ::

            # Make a numbered list
            iterator.each(lambda e, num: print(f'{num}: {e}'))
        """
        for num, e in enumerate(self, 1):
            _sync_value(cb(e, num))
        return self

    def each_p(self, cb: Callable[[T, int], Any]) -> Pyjo.Promise.object:
        """::

            promise = iterator.each_p(lambda e, num: ...)

        Same as :meth:`each`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled with the iterator once the callback has been evaluated for
        each element. ::

            # Process the messages one after another
            await messages.iterate().each_p(handle)
        """

        async def each() -> Self:
            num = 0
            async for e in self:
                num += 1
                await _async_value(cb(e, num))
            return self

        return Pyjo.Promise.new(each())

    @overload
    def first(self, cb: Callable[[T], object] | None = None, /) -> T | None: ...

    @overload
    def first(self, cb: Callable[..., Any] | str | re.Pattern[str], /, *args: Any, **kwargs: Any) -> T | None: ...

    def first(
        self, cb: Callable[..., Any] | str | re.Pattern[str] | None = None, /, *args: Any, **kwargs: Any
    ) -> T | None:
        """::

            first = iterator.first()
            first = iterator.first(re.compile(r'foo'))
            first = iterator.first(lambda e: ...)
            first = iterator.first('some_method')
            first = iterator.first('some_method', *args)

        Evaluate regular expression/callback for, or call method on, each
        element and return the first one that matched the regular expression,
        or for which the callback/method returned true, without taking the
        elements after it. ::

            # Find first value that is greater than 5
            greater = iterator.first(lambda e: e > 5)
        """
        for e in self:
            if cb is None or _matches(e, cb, args, kwargs, _sync_value):
                return e
        return None

    def first_p(
        self, cb: Callable[..., Any] | str | re.Pattern[str] | None = None, /, *args: Any, **kwargs: Any
    ) -> Pyjo.Promise.object:
        """::

            promise = iterator.first_p(lambda e: ...)

        Same as :meth:`first`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled with the element, or ``None``.
        """

        async def first() -> Any:
            async for e in self:
                if cb is None or await _async_matches(e, cb, args, kwargs):
                    return e
            return None

        return Pyjo.Promise.new(first())

    def flatten(self) -> 'Pyjo_Iterator[Any]':
        """::

            new = iterator.flatten()

        Flatten nested collections/lists/tuples recursively and pass on all
        elements. ::

            # "1, 2, 3, 4, 5, 6, 7"
            Pyjo.Iterator.new([1, [2, [3, 4], 5, [6]], 7]).flatten().join(', ')
        """

        def sync(source: collections.abc.Iterator[Any]) -> collections.abc.Iterator[Any]:
            return (f for e in source for f in _flatten([e]))

        async def asynchronous(source: AsyncIterator[Any]) -> AsyncIterator[Any]:
            async for e in source:
                for f in _flatten([e]):
                    yield f

        return self._chain(sync, asynchronous)

    @overload
    def grep(self, cb: Callable[[T], object], /) -> Self: ...

    @overload
    def grep(self, cb: Callable[..., Any] | str | re.Pattern[str], /, *args: Any, **kwargs: Any) -> Self: ...

    def grep(self, cb: Callable[..., Any] | str | re.Pattern[str], /, *args: Any, **kwargs: Any) -> Self:
        """::

            new = iterator.grep(re.compile(r'foo'))
            new = iterator.grep(lambda e: ...)
            new = iterator.grep('some_method')
            new = iterator.grep('some_method', *args)

        Evaluate regular expression/callback for, or call method on, each
        element and pass on all elements that matched the regular expression,
        or for which the callback/method returned true. ::

            # Find all values that are greater than 5
            greater = iterator.grep(lambda e: e > 5)
        """

        def sync(source: collections.abc.Iterator[Any]) -> collections.abc.Iterator[Any]:
            return (e for e in source if _matches(e, cb, args, kwargs, _sync_value))

        async def asynchronous(source: AsyncIterator[Any]) -> AsyncIterator[Any]:
            async for e in source:
                if await _async_matches(e, cb, args, kwargs):
                    yield e

        return self._chain(sync, asynchronous)

    def head(self, size: int) -> Self:
        """::

            new = iterator.head(4)

        Pass on up to the specified number of elements from the beginning, and
        take no more of them. ::

            # "A B C"
            Pyjo.Iterator.new(['A', 'B', 'C', 'D', 'E']).head(3).join(' ')
        """
        # Unlike Mojolicious: a negative number counts from the end in Mojo's head, which an iterator does not know
        if size < 0:
            raise ValueError('The size of head of an iterator cannot be negative')

        def sync(source: collections.abc.Iterator[Any]) -> collections.abc.Iterator[Any]:
            return itertools.islice(source, size)

        async def asynchronous(source: AsyncIterator[Any]) -> AsyncIterator[Any]:
            if size == 0:
                return
            num = 0
            async for e in source:
                yield e
                num += 1
                if num >= size:
                    return

        return self._chain(sync, asynchronous)

    def join(self, string: str | None = None) -> 'Pyjo.String.Unicode.object':
        r"""::

            string = iterator.join()
            string = iterator.join("\n")

        Turn elements into :mod:`Pyjo.String.Unicode`. ::

            # Join all values with commas
            iterator.join(', ').say()
        """
        return Pyjo.String.Unicode.new((string or '').join(map(_str, self)))

    def join_p(self, string: str | None = None) -> Pyjo.Promise.object:
        """::

            promise = iterator.join_p(', ')

        Same as :meth:`join`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled with the :mod:`Pyjo.String.Unicode`.
        """

        async def join() -> Pyjo.String.Unicode.object:
            return Pyjo.String.Unicode.new((string or '').join([_str(e) async for e in self]))

        return Pyjo.Promise.new(join())

    # The value that an awaitable gives, which map waits for, before any other value of a callback; Any of a Pyjo.Promise
    @overload
    def map[U](self, cb: Callable[[T], Awaitable[U]], /, *, concurrency: int = 1) -> 'Pyjo_Iterator[U]': ...

    @overload
    def map[U](self, cb: Callable[[T], U], /, *, concurrency: int = 1) -> 'Pyjo_Iterator[U]': ...

    @overload
    def map(
        self, cb: Callable[..., Any] | str, /, *args: Any, concurrency: int = 1, **kwargs: Any
    ) -> 'Pyjo_Iterator[Any]': ...

    def map(
        self, cb: Callable[..., Any] | str, /, *args: Any, concurrency: int = 1, **kwargs: Any
    ) -> 'Pyjo_Iterator[Any]':
        """::

            new = iterator.map(lambda e: ...)
            new = iterator.map(lambda e: ..., concurrency=3)
            new = iterator.map('some_method')
            new = iterator.map('some_method', *args)

        Evaluate callback for, or call method on, each element and pass on its
        value. The element will be the first argument passed to the callback.
        ::

            # Append the word "pyjo" to all values
            pyjoified = iterator.map(lambda e: e + 'pyjo')

        A callback that returns a :mod:`Pyjo.Promise` or another awaitable, or
        a coroutine function, is evaluated ahead for up to ``concurrency``
        elements, so that as many promises are in progress at the same time,
        while the values are passed on in the order of the elements. ::

            # Perform 3 requests at a time concurrently
            iterator.map(ua.get_p, concurrency=3).each(lambda tx, num: print(tx.result.dom().at('title').text))

        These options are currently available:

        concurrency
            ::

                concurrency=3

            The maximum number of elements whose callbacks are in progress at
            the same time, ``1`` by default, as a source may have no end.
        """
        if concurrency < 1:
            raise ValueError('The concurrency of map of an iterator must be at least 1')

        def sync(source: collections.abc.Iterator[Any]) -> collections.abc.Iterator[Any]:
            if concurrency == 1:
                for e in source:
                    yield _sync_value(_call(e, cb, args, kwargs))
                return
            pending: collections.deque[Pyjo.Promise.object] = collections.deque()
            try:
                for e in source:
                    pending.append(_promise(_call(e, cb, args, kwargs)))
                    if len(pending) >= concurrency:
                        yield _wait(pending.popleft())
                while pending:
                    yield _wait(pending.popleft())
            finally:
                _abandon(pending)

        async def asynchronous(source: AsyncIterator[Any]) -> AsyncIterator[Any]:
            if concurrency == 1:
                async for e in source:
                    yield await _async_value(_call(e, cb, args, kwargs))
                return
            pending: collections.deque[Pyjo.Promise.object] = collections.deque()
            try:
                async for e in source:
                    pending.append(_promise(_call(e, cb, args, kwargs)))
                    if len(pending) >= concurrency:
                        yield await pending.popleft()
                while pending:
                    yield await pending.popleft()
            finally:
                _abandon(pending)

        return self._chain(sync, asynchronous)

    @classmethod
    def new(cls, iterable: Iterable[T] | AsyncIterable[T] = ()) -> Self:
        """::

            iterator = Pyjo.Iterator.new([1, 2, 3])
            iterator = Pyjo.Iterator.new(n for n in range(3))
            iterator = Pyjo.Iterator.new(stream)

        Construct a new :mod:`Pyjo.Iterator` object of an iterable or of an
        asynchronous iterable.
        """
        return cls(iterable)

    def reduce(self, cb: Callable[[Any, T], Any], *initial: Any) -> Any:
        """::

            result = iterator.reduce(lambda a, b: ...)
            result = iterator.reduce(lambda a, b: ..., initial)

        Reduce elements with a callback and return its final result, passing
        ``a`` and ``b`` each time the callback is executed. The first time ``a``
        will be an optional initial value or the first element. And from then
        on ``a`` will be the value of the callback, while ``b`` will always be
        the next element. ::

            # Calculate the sum of all values
            total = iterator.reduce(lambda a, b: a + b)
        """
        elements = iter(self)
        if len(initial):
            a = initial[0]
        elif (a := next(elements, _NONE)) is _NONE:
            return None
        for b in elements:
            a = _sync_value(cb(a, b))
        return a

    def reduce_p(self, cb: Callable[[Any, T], Any], *initial: Any) -> Pyjo.Promise.object:
        """::

            promise = iterator.reduce_p(lambda a, b: ...)
            promise = iterator.reduce_p(lambda a, b: ..., initial)

        Same as :meth:`reduce`, but returns a :mod:`Pyjo.Promise` object, which
        is fulfilled with the final result.
        """

        async def reduce() -> Any:
            elements = aiter(self)
            if len(initial):
                a = initial[0]
            elif (a := await anext(elements, _NONE)) is _NONE:
                return None
            async for b in elements:
                a = await _async_value(cb(a, b))
            return a

        return Pyjo.Promise.new(reduce())

    def to_list(self) -> 'Pyjo.Collection.object[T]':
        """::

            collection = iterator.to_list()

        Take all elements and turn them into a :mod:`Pyjo.Collection`, which
        is a :class:`list`.
        """
        return Pyjo.Collection.object(self)

    def to_list_p(self) -> Pyjo.Promise.object:
        """::

            promise = iterator.to_list_p()

        Same as :meth:`to_list`, but returns a :mod:`Pyjo.Promise` object,
        which is fulfilled with the :mod:`Pyjo.Collection`. ::

            # The titles of all pages, 3 at a time
            titles = await Pyjo.Iterator.new(urls).map(ua.get_p, concurrency=3).map(title).to_list_p()
        """

        async def to_list() -> Pyjo.Collection.object[T]:
            return Pyjo.Collection.object([e async for e in self])

        return Pyjo.Promise.new(to_list())

    def uniq(self, cb: Callable[..., Any] | str | None = None, *args: Any, **kwargs: Any) -> Self:
        """::

            new = iterator.uniq()
            new = iterator.uniq(lambda e: ...)
            new = iterator.uniq('some_method')
            new = iterator.uniq('some_method', *args)

        Pass on the elements without duplicates, using the string
        representation of either the elements or the value of the
        callback/method to decide uniqueness. Note that ``None`` and empty
        string are treated the same. ::

            # "foo bar baz"
            Pyjo.Iterator.new(['foo', 'bar', 'bar', 'baz']).uniq().join(' ')
        """

        def sync(source: collections.abc.Iterator[Any]) -> collections.abc.Iterator[Any]:
            seen: set[str] = set()
            for e in source:
                if _unseen(seen, e if cb is None else _sync_value(_call(e, cb, args, kwargs))):
                    yield e

        async def asynchronous(source: AsyncIterator[Any]) -> AsyncIterator[Any]:
            seen: set[str] = set()
            async for e in source:
                if _unseen(seen, e if cb is None else await _async_value(_call(e, cb, args, kwargs))):
                    yield e

        return self._chain(sync, asynchronous)

    # A new iterator of a step after this one
    def _chain(self, sync: SyncStep, asynchronous: AsyncStep) -> Any:
        new = type(self)()
        new._step = (self, sync, asynchronous)
        return new


# The default of next() and anext() that tells no element from an element None
_NONE = builtins.object()


def _abandon(pending: Iterable[Pyjo.Promise.object]) -> None:
    for promise in pending:
        promise.catch(lambda *reason: None)


async def _async_matches(
    e: Any, cb: Callable[..., Any] | str | re.Pattern[str], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> bool:
    if isinstance(cb, re.Pattern):
        return bool(cb.search(_str(e)))
    return bool(await _async_value(_call(e, cb, args, kwargs)))


async def _async_value(value: Any) -> Any:
    return await value if _awaitable(value) else value


def _awaitable(value: Any) -> bool:
    return isinstance(value, Pyjo.Promise.object) or inspect.isawaitable(value)


def _matches(
    e: Any,
    cb: Callable[..., Any] | str | re.Pattern[str],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    value: Callable[[Any], Any],
) -> bool:
    if isinstance(cb, re.Pattern):
        return bool(cb.search(_str(e)))
    return bool(value(_call(e, cb, args, kwargs)))


# A value of a callback as a promise, which settles while the event loop runs for another one
def _promise(value: Any) -> Pyjo.Promise.object:
    if isinstance(value, Pyjo.Promise.object):
        return value
    if inspect.isawaitable(value):
        return Pyjo.Promise.new(value)
    return Pyjo.Promise.resolve(value)


def _sync_value(value: Any) -> Any:
    return _wait(_promise(value)) if _awaitable(value) else value


async def _to_async[T](source: collections.abc.Iterator[T]) -> AsyncIterator[T]:
    for e in source:
        yield e


def _to_sync[T](source: AsyncIterator[T]) -> collections.abc.Iterator[T]:
    while True:
        try:
            yield _wait(Pyjo.Promise.new(anext(source)))
        except StopAsyncIteration:
            return


# The value of a promise, which for waits for with the event loop
def _wait(promise: Pyjo.Promise.object) -> Any:
    return promise._wait_value()  # pyright: ignore[reportPrivateUsage]


def _unseen(seen: set[str], value: Any) -> bool:
    if (key := '' if value is None else _str(value)) in seen:
        return False
    seen.add(key)
    return True


# Any: the type of the elements is not known before they are given
new = Pyjo_Iterator[Any].new
object = Pyjo_Iterator
Iterator = Pyjo_Iterator
