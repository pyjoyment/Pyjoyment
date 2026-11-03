# pyright: reportUnnecessaryTypeIgnoreComment=true

import Pyjo.Collection
import Pyjo.Iterator
import Pyjo.Promise

from Pyjo.Iterator import Iterator
from Pyjo.Test import *

from typing import Any, assert_type


# The types of the values of the callbacks of map, which pyright checks in this file in strict mode


async def ten(n: int) -> int:
    await Pyjo.Promise.timer(0.001)
    return n * 10


def promised(n: int) -> Pyjo.Promise.object:
    return Pyjo.Promise.timer(0.001, n)


def times(e: int, n: int) -> int:
    return e * n


class Word:
    def __init__(self, word: str) -> None:
        self.word = word

    def upper(self) -> str:
        return self.word.upper()


with subtest('map with a callback of a value'):
    iterator = Iterator([1, 2]).map(lambda e: str(e))
    assert_type(iterator, Iterator[str])
    is_deeply_ok(list(iterator), ['1', '2'], 'right result')

with subtest('map with a coroutine function'):
    iterator = Iterator([1, 2]).map(ten)
    assert_type(iterator, Iterator[int])
    is_deeply_ok(list(iterator), [10, 20], 'right result')
    assert_type(Iterator([1, 2]).map(ten, concurrency=2), Iterator[int])
    is_deeply_ok(list(Iterator([1, 2]).map(ten, concurrency=2)), [10, 20], 'concurrency')
    assert_type(Pyjo.Iterator.new([1, 2]).map(ten, concurrency=2), Iterator[int])

    # The values chain on
    assert_type(Iterator([1, 2]).map(ten).map(lambda e: e + 1), Iterator[int])
    assert_type(Iterator([1, 2]).map(ten).to_list(), Pyjo.Collection.object[int])
    is_deeply_ok(Iterator([1, 2]).map(ten).map(lambda e: e + 1).to_list(), [11, 21], 'chain')

with subtest('map with a callback of a promise'):
    iterator = Iterator([1, 2]).map(promised, concurrency=2)
    assert_type(iterator, Iterator[Any])
    is_deeply_ok(list(iterator), [1, 2], 'right result')
    assert_type(Iterator([1, 2]).map(lambda e: Pyjo.Promise.resolve(e)), Iterator[Any])

with subtest('map with a method or arguments'):
    assert_type(Iterator([Word('a')]).map('upper'), Iterator[Any])
    is_deeply_ok(list(Iterator([Word('a')]).map('upper')), ['A'], 'method')
    assert_type(Iterator([1, 2]).map(times, 10), Iterator[Any])
    is_deeply_ok(list(Iterator([1, 2]).map(times, 10)), [10, 20], 'arguments')

done_testing()
