r"""
Pyjo.Collection - Collection
============================
::

    from Pyjo.Collection import Collection

    # Manipulate collection
    collection = Collection(['just', 'works'])
    collection.insert(0, 'it')
    print(collection.join("\n"))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Collection

    # Manipulate collection
    collection = Pyjo.Collection.new('just', 'works')
    collection.insert(0, 'it')
    print(collection.join("\n"))

    # Chain methods
    collection.map(lambda e: e.capitalize()).shuffle().each(lambda word, num: print(f'{num}: {word}'))

    # Use the alternative constructor
    from Pyjo.Collection import c
    c('a', 'b', 'c').join('/').url_escape().say()

:mod:`Pyjo.Collection` is a :class:`list` for collections. The class itself
takes an iterable, as :class:`list` does. ::

    # Access list directly to manipulate collection
    collection = Pyjo.Collection.new(*range(1, 26))
    collection[23] += 100
    for e in collection:
        print(e)

    # Make a collection of an iterable
    collection = Pyjo.Collection.object(range(1, 26))

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Collection <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Collection.pm>`_
of Mojolicious 9.49.

Functions
---------
"""

import Pyjo.Base
import Pyjo.String.Unicode

import builtins
import functools
import random
import re

from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from typing import TYPE_CHECKING, Any, Self, cast, overload


if TYPE_CHECKING:
    import Pyjo.Iterator


type Anything = builtins.object


class Pyjo_Collection[T](list[T]):
    """
    :mod:`Pyjo.Collection` inherits all methods from :class:`list` and
    implements the following new ones.
    """

    def __repr__(self) -> str:
        return f'{self.__module__}.new({", ".join(map(repr, self))})'

    # Not in Mojolicious: the elements in a coroutine, as Pyjo.Iterator takes them
    def __aiter__(self) -> AsyncIterator[T]:
        """::

            async for e in collection:
                ...

        Same as :meth:`iterate`.
        """
        return aiter(self.iterate())

    def __json__(self) -> list[T]:
        """::

            array = collection.__json__()

        Alias for :meth:`to_list`.
        """
        return self.to_list()

    def compact(self) -> Self:
        """::

            new = collection.compact()

        Create a new collection with all elements that are not ``None`` and not
        an empty string. ::

            # "0, 1, 2, 3"
            c(0, 1, None, 2, '', 3).compact().join(', ')
        """
        return type(self)(e for e in self if e is not None and (not isinstance(e, (str, bytes)) or len(e)))

    @overload
    def each(self) -> list[T]: ...

    @overload
    def each(self, cb: Callable[[T, int], Any]) -> Self: ...

    def each(self, cb: Callable[[T, int], Any] | None = None) -> list[T] | Self:
        """::

            elements = collection.each()
            collection = collection.each(lambda e, num: ...)

        Evaluate callback for each element in collection, or return all
        elements as a list if none has been provided. The element will be the
        first argument passed to the callback, and its number the second. ::

            # Make a numbered list
            collection.each(lambda e, num: print(f'{num}: {e}'))
        """
        if cb is None:
            return self.to_list()
        for i, e in enumerate(self, 1):
            cb(e, i)
        return self

    @overload
    def first(self, cb: Callable[[T], object] | None = None, /) -> T | None: ...

    @overload
    def first(self, cb: Callable[..., Any] | str | re.Pattern[str], /, *args: Any, **kwargs: Any) -> T | None: ...

    def first(
        self, cb: Callable[..., Any] | str | re.Pattern[str] | None = None, /, *args: Any, **kwargs: Any
    ) -> T | None:
        """::

            first = collection.first()
            first = collection.first(re.compile(r'foo'))
            first = collection.first(lambda e: ...)
            first = collection.first('some_method')
            first = collection.first('some_method', *args)

        Evaluate regular expression/callback for, or call method on, each
        element in collection and return the first one that matched the
        regular expression, or for which the callback/method returned true.
        The element will be the first argument passed to the callback. ::

            # Longer version
            first = collection.first(lambda e: e.some_method(*args))

            # Find first value that contains the word "pyjo"
            interesting = collection.first(re.compile(r'pyjo', re.I))

            # Find first value that is greater than 5
            greater = collection.first(lambda e: e > 5)
        """
        if cb is None:
            return self[0] if len(self) else None
        if isinstance(cb, re.Pattern):
            return next((e for e in self if cb.search(_str(e))), None)
        return next((e for e in self if _call(e, cb, args, kwargs)), None)

    def flatten(self) -> 'Pyjo_Collection[Any]':
        """::

            new = collection.flatten()

        Flatten nested collections/lists/tuples recursively and create a new
        collection with all elements. ::

            # "1, 2, 3, 4, 5, 6, 7"
            c(1, [2, [3, 4], 5, [6]], 7).flatten().join(', ')
        """
        return cast(Pyjo_Collection[Any], type(self)(_flatten(self)))

    # Not in Mojolicious: the expression form of an index with a default, as
    # dict.get() is
    @overload
    def get(self, index: int) -> T | None: ...

    @overload
    def get[D](self, index: int, default: D) -> T | D: ...

    def get(self, index: int, default: Any = None) -> Any:
        """::

            element = collection.get(index)
            element = collection.get(index, default)

        Return the element at the index, or the default, which is ``None``
        unless given, if there is no such element. A negative index counts
        from the end. ::

            import sys
            from Pyjo.Util import die
            address = c(*sys.argv).get(1) or die('address missing')
            port = int(c(*sys.argv).get(2, '80'))
        """
        return self[index] if -len(self) <= index < len(self) else default

    @overload
    def grep(self, cb: Callable[[T], object], /) -> Self: ...

    @overload
    def grep(self, cb: Callable[..., Any] | str | re.Pattern[str], /, *args: Any, **kwargs: Any) -> Self: ...

    def grep(self, cb: Callable[..., Any] | str | re.Pattern[str], /, *args: Any, **kwargs: Any) -> Self:
        """::

            new = collection.grep(re.compile(r'foo'))
            new = collection.grep(lambda e: ...)
            new = collection.grep('some_method')
            new = collection.grep('some_method', *args)

        Evaluate regular expression/callback for, or call method on, each
        element in collection and create a new collection with all elements
        that matched the regular expression, or for which the callback/method
        returned true. The element will be the first argument passed to the
        callback. ::

            # Longer version
            new = collection.grep(lambda e: e.some_method(*args))

            # Find all values that contain the word "pyjo"
            interesting = collection.grep(re.compile(r'pyjo', re.I))

            # Find all values that are greater than 5
            greater = collection.grep(lambda e: e > 5)
        """
        if isinstance(cb, re.Pattern):
            return type(self)(e for e in self if cb.search(_str(e)))
        return type(self)(e for e in self if _call(e, cb, args, kwargs))

    def head(self, size: int) -> Self:
        """::

            new = collection.head(4)
            new = collection.head(-2)

        Create a new collection with up to the specified number of elements
        from the beginning of the collection. A negative number will count
        from the end. ::

            # "A B C"
            c('A', 'B', 'C', 'D', 'E').head(3).join(' ')

            # "A B"
            c('A', 'B', 'C', 'D', 'E').head(-3).join(' ')
        """
        return type(self)(self[:size])

    # Not in Mojolicious: a lazy chain, for and async for alike
    def iterate(self) -> 'Pyjo.Iterator.object[T]':
        """::

            iterator = collection.iterate()

        Turn collection into a lazy :mod:`Pyjo.Iterator`, whose chain passes
        each element on as soon as it has it, and waits for the promises of
        its callbacks. ::

            # "2, 4, 6"
            c(1, 2, 3).iterate().map(lambda e: e * 2).join(', ')

            # Perform 3 requests at a time concurrently, in a coroutine
            async for tx in c(*urls).iterate().map(ua.get_p, concurrency=3):
                print(tx.result.dom().at('title').text)
        """
        import Pyjo.Iterator

        return Pyjo.Iterator.object(self)

    def join(self, string: str | None = None) -> 'Pyjo.String.Unicode.object':
        r"""::

            string = collection.join()
            string = collection.join("\n")

        Turn collection into :mod:`Pyjo.String.Unicode`. ::

            # Join all values with commas
            collection.join(', ').say()
        """
        return Pyjo.String.Unicode.new((string or '').join(map(_str, self)))

    def last(self) -> T | None:
        """::

            last = collection.last()

        Return the last element in collection.
        """
        return self[-1] if len(self) else None

    @overload
    def map[U](self, cb: Callable[[T], U], /) -> 'Pyjo_Collection[U]': ...

    @overload
    def map(self, cb: Callable[..., Any] | str, /, *args: Any, **kwargs: Any) -> 'Pyjo_Collection[Any]': ...

    def map(self, cb: Callable[..., Any] | str, /, *args: Any, **kwargs: Any) -> 'Pyjo_Collection[Any]':
        """::

            new = collection.map(lambda e: ...)
            new = collection.map('some_method')
            new = collection.map('some_method', *args)

        Evaluate callback for, or call method on, each element in collection
        and create a new collection from the results. The element will be the
        first argument passed to the callback. ::

            # Longer version
            new = collection.map(lambda e: e.some_method(*args))

            # Append the word "pyjo" to all values
            pyjoified = collection.map(lambda e: e + 'pyjo')
        """
        return cast(Pyjo_Collection[Any], type(self)(_call(e, cb, args, kwargs) for e in self))

    @classmethod
    def new(cls, *elements: T) -> Self:
        """::

            collection = Pyjo.Collection.new(1, 2, 3)

        Construct a new :mod:`Pyjo.Collection` object. The constructor of the
        class takes an iterable, as the one of :class:`list`, so that a single
        element that is iterable stays one element of :meth:`new`. ::

            collection = Collection([1, 2, 3])
            collection = Collection(n for n in range(3))
        """
        return cls(elements)

    def reduce(self, cb: Callable[[Any, T], Any], *initial: Any) -> Any:
        """::

            result = collection.reduce(lambda a, b: ...)
            result = collection.reduce(lambda a, b: ..., initial)

        Reduce elements in collection with a callback and return its final
        result, passing ``a`` and ``b`` each time the callback is executed. The
        first time ``a`` will be an optional initial value or the first element
        in the collection. And from then on ``a`` will be the return value of
        the callback, while ``b`` will always be the next element in the
        collection. ::

            # Calculate the sum of all values
            total = collection.reduce(lambda a, b: a + b)

            # Count how often each value occurs in collection
            counts = collection.reduce(lambda a, b: a | {b: a.get(b, 0) + 1}, {})
        """
        elements = [*initial, *self]
        return functools.reduce(cb, elements) if len(elements) else None

    # Mojo's reverse creates a new collection, list.reverse() reverses in place
    def reverse(self) -> Self:  # pyright: ignore[reportIncompatibleMethodOverride]
        """::

            new = collection.reverse()

        Create a new collection with all elements in reverse order.
        """
        return type(self)(reversed(self))

    def shuffle(self) -> Self:
        """::

            new = collection.shuffle()

        Create a new collection with all elements in random order.
        """
        return type(self)(random.sample(self, len(self)))

    @property
    def size(self) -> int:
        """::

            size = collection.size

        Number of elements in collection.
        """
        return len(self)

    # Mojo's sort creates a new collection, list.sort() sorts in place
    def sort(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, *, key: Callable[[T], Any] | None = None, reverse: bool = False
    ) -> Self:
        """::

            new = collection.sort()
            new = collection.sort(key=lambda e: ...)
            new = collection.sort(reverse=True)

        Sort elements based on return value of a key function and create a new
        collection from the results, as :func:`sorted` does. ::

            # Sort values case-insensitive
            case_insensitive = collection.sort(key=str.upper)
        """
        # Unlike Mojolicious: Mojo takes a function that compares $a and $b, which
        # Python 3 has no use for; the key and reverse arguments are sorted()'s
        return type(self)(sorted(cast(list[Any], self), key=key, reverse=reverse))

    def tail(self, size: int) -> Self:
        """::

            new = collection.tail(4)
            new = collection.tail(-2)

        Create a new collection with up to the specified number of elements
        from the end of the collection. A negative number will count from the
        beginning. ::

            # "C D E"
            c('A', 'B', 'C', 'D', 'E').tail(3).join(' ')

            # "D E"
            c('A', 'B', 'C', 'D', 'E').tail(-3).join(' ')
        """
        return type(self)(self[max(len(self) - size, 0) :] if size >= 0 else self[-size:])

    def tap(self, cb: Callable[..., Any] | str, *args: Any, **kwargs: Any) -> Self:
        """::

            collection = collection.tap(lambda c: ...)

        Alias for :meth:`Pyjo.Base.tap`.
        """
        Pyjo.Base.tap(self, cb, *args, **kwargs)
        return self

    # Not in Mojolicious: a conversion to a type of the standard library
    def to_dict[K, V](self: 'Pyjo_Collection[tuple[K, V]]') -> dict[K, V]:
        """::

            d = collection.to_dict()

        Turn collection of pairs of key and value into :class:`dict`. ::

            # {'a': 1, 'b': 2, 'c': 3}
            c(('a', 1), ('b', 2), ('c', 3)).to_dict()
        """
        return dict(self)

    # Not in Mojolicious: a conversion to a type of the standard library
    def to_iter(self) -> Iterator[T]:
        """::

            i = collection.to_iter()

        Turn collection into an iterator. ::

            for e in c(1, 2, 3).to_iter():
                print(e)
        """
        return iter(self)

    def to_list(self) -> list[T]:
        """::

            array = collection.to_list()

        Turn collection into :class:`list`.
        """
        return list(self)

    # Not in Mojolicious: a conversion to a type of the standard library
    def to_set(self) -> set[T]:
        """::

            s = collection.to_set()

        Turn collection into :class:`set`. ::

            # {1, 2, 3}
            c(1, 2, 3, 2).to_set()
        """
        return set(self)

    # Not in Mojolicious: a conversion to a type of the standard library
    def to_tuple(self) -> tuple[T, ...]:
        """::

            t = collection.to_tuple()

        Turn collection into :class:`tuple`. ::

            # (1, 2, 3)
            c(1, 2, 3).to_tuple()
        """
        return tuple(self)

    def uniq(self, cb: Callable[..., Any] | str | None = None, *args: Any, **kwargs: Any) -> Self:
        """::

            new = collection.uniq()
            new = collection.uniq(lambda e: ...)
            new = collection.uniq('some_method')
            new = collection.uniq('some_method', *args)

        Create a new collection without duplicate elements, using the string
        representation of either the elements or the return value of the
        callback/method to decide uniqueness. Note that ``None`` and empty
        string are treated the same. ::

            # Longer version
            new = collection.uniq(lambda e: e.some_method(*args))

            # "foo bar baz"
            c('foo', 'bar', 'bar', 'baz').uniq().join(' ')

            # [[1, 2], [2, 1]]
            c([1, 2], [2, 1], [3, 2]).uniq(lambda e: e[1]).to_list()
        """
        seen: set[str] = set()
        new = type(self)()
        for e in self:
            value = e if cb is None else _call(e, cb, args, kwargs)
            if (key := '' if value is None else _str(value)) not in seen:
                seen.add(key)
                new.append(e)
        return new

    # Left out from Mojolicious: with_roles, as Pyjoyment has no roles

    # Not in Mojolicious: the method form of zip(), for a chain
    @overload
    def zip[U](self, iterable: Iterable[U], /, *, strict: bool = False) -> 'Pyjo_Collection[tuple[T, U]]': ...

    @overload
    def zip(self, *iterables: Iterable[Any], strict: bool = False) -> 'Pyjo_Collection[tuple[Any, ...]]': ...

    def zip(self, *iterables: Iterable[Any], strict: bool = False) -> 'Pyjo_Collection[tuple[Any, ...]]':
        """::

            new = collection.zip(iterable)
            new = collection.zip(iterable, strict=True)

        Create a new collection of tuples of the elements of the collection and
        of the iterables, as :func:`zip` does. ::

            # [('a', 1), ('b', 2), ('c', 3)]
            c('a', 'b', 'c').zip([1, 2, 3]).to_list()

            # {'a': 1, 'b': 2, 'c': 3}
            c('a', 'b', 'c').zip([1, 2, 3]).to_dict()
        """
        return cast(
            Pyjo_Collection[tuple[Any, ...]], type(self)(cast(Iterable[Any], zip(self, *iterables, strict=strict)))
        )


def c[T](*elements: T) -> Pyjo_Collection[T]:
    """::

        collection = c(1, 2, 3)

    Construct a new :mod:`Pyjo.Collection` object.
    """
    return Pyjo_Collection(elements)


# A method of the element, or Mojo's attribute, which is a property
def _call(element: Any, cb: Callable[..., Any] | str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    if callable(cb):
        return cb(element, *args, **kwargs)
    value = getattr(element, cb)
    if callable(value):
        return value(*args, **kwargs)
    if len(args):
        setattr(element, cb, args[0])
        return element
    return value


def _flatten(elements: Iterable[Any]) -> Iterable[Any]:
    for e in elements:
        if isinstance(e, (list, tuple)):
            yield from _flatten(cast(Iterable[Any], e))
        else:
            yield e


def _str(element: Anything) -> str:
    return Pyjo.String.Unicode.new(element).to_str()


# Any: the type of the elements is not known before they are given
new = Pyjo_Collection[Any].new
object = Pyjo_Collection
Collection = Pyjo_Collection
