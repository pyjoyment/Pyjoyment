import Pyjo.Collection
import Pyjo.EventEmitter
import Pyjo.IOLoop
import Pyjo.IOLoop.Datagram
import Pyjo.IOLoop.Messages
import Pyjo.IOLoop.Stream
import Pyjo.Iterator
import Pyjo.Promise

from Pyjo.Collection import c
from Pyjo.Test import *

import gc
import re
import socket
import time
import warnings


# A coroutine of the test, run by the reactor until it is done
def run(coro):
    values = []
    Pyjo.Promise.new(coro).then(lambda *v: values.append(v)).wait()
    return values[0][0] if len(values[0]) else None


async def numbers(n):
    for i in range(1, n + 1):
        await Pyjo.Promise.timer(0.001)
        yield i


class Word:
    def __init__(self, word):
        self.word = word

    def upper(self):
        return self.word.upper()

    def __str__(self):
        return self.word


with subtest('Constructors'):
    isa_ok(Pyjo.Iterator.new([1, 2, 3]), Pyjo.Iterator.object, 'right class')
    is_deeply_ok(list(Pyjo.Iterator.new([1, 2, 3])), [1, 2, 3], 'right elements')
    is_deeply_ok(list(Pyjo.Iterator.Iterator([1, 2, 3])), [1, 2, 3], 'class of the module')
    is_deeply_ok(list(Pyjo.Iterator.new()), [], 'no elements')
    is_deeply_ok(list(c(1, 2, 3).iterate()), [1, 2, 3], 'from a collection')
    isa_ok(c(1, 2, 3).iterate(), Pyjo.Iterator.object, 'iterate of a collection')

with subtest('Each iteration takes the source anew'):
    iterator = Pyjo.Iterator.new([1, 2, 3]).map(lambda e: e * 2)
    is_deeply_ok(list(iterator), [2, 4, 6], 'first iteration')
    is_deeply_ok(list(iterator), [2, 4, 6], 'second iteration')
    iterator = Pyjo.Iterator.new(e for e in (1, 2, 3))
    is_deeply_ok(list(iterator), [1, 2, 3], 'generator')
    is_deeply_ok(list(iterator), [], 'generator once')

with subtest('Lazy'):
    taken = []

    def source():
        for i in range(1, 6):
            taken.append(i)
            yield i

    iterator = Pyjo.Iterator.new(source()).map(lambda e: e * 10)
    is_deeply_ok(taken, [], 'nothing taken before the iteration')
    elements = iter(iterator)
    is_ok(next(elements), 10, 'first element')
    is_deeply_ok(taken, [1], 'one taken for the first element')
    taken.clear()
    is_ok(Pyjo.Iterator.new(source()).first(lambda e: e > 1), 2, 'first')
    is_deeply_ok(taken, [1, 2], 'no more taken after the first one')
    taken.clear()
    is_deeply_ok(list(Pyjo.Iterator.new(source()).head(2)), [1, 2], 'head')
    is_deeply_ok(taken, [1, 2], 'no more taken after the head')

with subtest('compact'):
    is_deeply_ok(list(Pyjo.Iterator.new([0, 1, None, 2, '', 3]).compact()), [0, 1, 2, 3], 'compacted')
    is_deeply_ok(run(Pyjo.Iterator.new([0, None, '', b'', 1]).compact().to_list_p()), [0, 1], 'async')

with subtest('each'):
    got = []
    iterator = Pyjo.Iterator.new([3, 2, 1])
    is_ok(iterator.each(lambda e, num: got.append((e, num))), iterator, 'right return value')
    is_deeply_ok(got, [(3, 1), (2, 2), (1, 3)], 'right elements')
    got = []
    Pyjo.Iterator.new([1, 2]).each(lambda e, num: Pyjo.Promise.timer(0.001).then(lambda: got.append(e)))
    is_deeply_ok(got, [1, 2], 'promises of the callback waited for')
    got = []
    is_ok(run(iterator.each_p(lambda e, num: got.append(e))), iterator, 'each_p')
    is_deeply_ok(got, [3, 2, 1], 'right elements')

with subtest('first'):
    iterator = Pyjo.Iterator.new([5, 4, [3, 2], 1])
    is_deeply_ok(iterator.first(), 5, 'right result')
    is_deeply_ok(iterator.first(lambda e: isinstance(e, list)), [3, 2], 'right result')
    is_ok(iterator.first(lambda e: not isinstance(e, list) and e < 5), 4, 'right result')
    is_ok(iterator.first(re.compile(r'^\d+$')), 5, 'right result')
    is_ok(iterator.first(re.compile(r'^\d+$')), 5, 'right result')
    is_ok(Pyjo.Iterator.new([]).first(), None, 'no result')
    is_ok(Pyjo.Iterator.new([Word('a'), Word('b')]).first('upper').word, 'a', 'right result')
    is_ok(iterator.first(lambda e: Pyjo.Promise.resolve(e == 1)), 1, 'promise of the callback')
    is_ok(run(iterator.first_p(lambda e: e == 1)), 1, 'first_p')
    is_ok(run(iterator.first_p()), 5, 'first_p without a callback')
    is_ok(run(Pyjo.Iterator.new([]).first_p()), None, 'first_p without a result')

with subtest('flatten'):
    iterator = Pyjo.Iterator.new([1, 2, [3, 4], 5, [6, c(7, 8)], 9, 10])
    is_deeply_ok(list(iterator.flatten()), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 'flattened')
    is_deeply_ok(run(iterator.flatten().to_list_p()), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 'async')

with subtest('grep'):
    iterator = Pyjo.Iterator.new([1, 2, 3, 4, 5, 6, 7, 8, 9])
    is_deeply_ok(list(iterator.grep(re.compile(r'[6-9]'))), [6, 7, 8, 9], 'regular expression')
    is_deeply_ok(list(iterator.grep(lambda e: e > 5)), [6, 7, 8, 9], 'callback')
    is_deeply_ok(list(iterator.grep(lambda e: e < 5).grep(lambda e: e > 2)), [3, 4], 'chained')
    is_deeply_ok(list(iterator.grep(lambda e: Pyjo.Promise.resolve(e > 7))), [8, 9], 'promise of the callback')
    is_deeply_ok(list(Pyjo.Iterator.new(['a', '', 'b']).grep('__len__')), ['a', 'b'], 'method')
    is_deeply_ok(run(iterator.grep(re.compile(r'[1-2]')).to_list_p()), [1, 2], 'async regular expression')
    is_deeply_ok(run(iterator.grep(lambda e: e > 8).to_list_p()), [9], 'async callback')

with subtest('head'):
    iterator = Pyjo.Iterator.new([1, 2, 3, 4, 5])
    is_deeply_ok(list(iterator.head(3)), [1, 2, 3], 'right result')
    is_deeply_ok(list(iterator.head(0)), [], 'no result')
    is_deeply_ok(list(iterator.head(10)), [1, 2, 3, 4, 5], 'all elements')
    is_deeply_ok(run(iterator.head(2).to_list_p()), [1, 2], 'async')
    is_deeply_ok(run(iterator.head(0).to_list_p()), [], 'async no result')
    throws_ok(lambda: iterator.head(-1), 'The size of head of an iterator cannot be negative', 'negative size')

with subtest('join'):
    iterator = Pyjo.Iterator.new([1, 2, 3])
    is_ok(iterator.join(), '123', 'right result')
    is_ok(iterator.join(''), '123', 'right result')
    is_ok(iterator.join('---'), '1---2---3', 'right result')
    isa_ok(iterator.join(), Pyjo.String.Unicode.object, 'right class')
    is_ok(run(iterator.join_p(', ')), '1, 2, 3', 'join_p')
    isa_ok(run(iterator.join_p()), Pyjo.String.Unicode.object, 'right class')

with subtest('map'):
    iterator = Pyjo.Iterator.new([1, 2, 3])
    is_deeply_ok(list(iterator.map(lambda e: e + 1)), [2, 3, 4], 'right result')
    is_deeply_ok(list(iterator.map(lambda e: e + 2)), [3, 4, 5], 'right result')
    is_deeply_ok(list(Pyjo.Iterator.new([Word('a')]).map('upper')), ['A'], 'method')
    is_deeply_ok(list(iterator.map(lambda e, n: e * n, 10)), [10, 20, 30], 'arguments')
    is_deeply_ok(list(iterator.map(lambda e: Pyjo.Promise.timer(0.001, e * 3))), [3, 6, 9], 'promises')

    async def double(e):
        await Pyjo.Promise.timer(0.001)
        return e * 2

    is_deeply_ok(list(iterator.map(double)), [2, 4, 6], 'coroutine function')
    is_deeply_ok(run(iterator.map(double).to_list_p()), [2, 4, 6], 'async coroutine function')
    is_deeply_ok(run(iterator.map(lambda e: Pyjo.Promise.resolve(e)).to_list_p()), [1, 2, 3], 'async promises')
    throws_ok(lambda: iterator.map(double, concurrency=0), 'The concurrency of map of an iterator must be at least 1')

with subtest('map with concurrency'):
    started = []

    def slow(e):
        started.append(e)
        return Pyjo.Promise.timer(0.1 * (5 - e), e)

    start = time.monotonic()
    is_deeply_ok(list(Pyjo.Iterator.new([1, 2, 3, 4]).map(slow, concurrency=4)), [1, 2, 3, 4], 'order of the source')
    ok(time.monotonic() - start < 0.6, 'at the same time')
    started.clear()
    elements = iter(Pyjo.Iterator.new([1, 2, 3, 4]).map(slow, concurrency=2))
    is_ok(next(elements), 1, 'first element')
    is_deeply_ok(started, [1, 2], 'two in progress')
    is_deeply_ok(list(elements), [2, 3, 4], 'the rest')
    started.clear()
    start = time.monotonic()
    got = run(Pyjo.Iterator.new([1, 2, 3, 4]).map(slow, concurrency=4).to_list_p())
    is_deeply_ok(got, [1, 2, 3, 4], 'async order of the source')
    ok(time.monotonic() - start < 0.6, 'async at the same time')
    is_deeply_ok(
        list(Pyjo.Iterator.new([1, 2, 3]).map(lambda e: e * 2, concurrency=2)), [2, 4, 6], 'values that are no promises'
    )

with subtest('reduce'):
    iterator = Pyjo.Iterator.new([2, 5, 4, 1])
    is_ok(iterator.reduce(lambda a, b: a + b), 12, 'right result')
    is_ok(iterator.reduce(lambda a, b: a + b, 5), 17, 'right result')
    is_ok(Pyjo.Iterator.new([]).reduce(lambda a, b: a + b), None, 'no result')
    is_ok(Pyjo.Iterator.new([None]).reduce(lambda a, b: a + b), None, 'one element None')
    is_ok(iterator.reduce(lambda a, b: Pyjo.Promise.resolve(a + b)), 12, 'promises of the callback')
    is_ok(run(iterator.reduce_p(lambda a, b: a + b)), 12, 'reduce_p')
    is_ok(run(iterator.reduce_p(lambda a, b: a + b, 5)), 17, 'reduce_p with an initial value')
    is_ok(run(Pyjo.Iterator.new([]).reduce_p(lambda a, b: a + b)), None, 'reduce_p without a result')

with subtest('to_list'):
    collection = Pyjo.Iterator.new(e for e in (1, 2, 3)).to_list()
    isa_ok(collection, Pyjo.Collection.object, 'right class')
    is_deeply_ok(collection, [1, 2, 3], 'right elements')
    isa_ok(run(Pyjo.Iterator.new([1]).to_list_p()), Pyjo.Collection.object, 'to_list_p')

with subtest('uniq'):
    iterator = Pyjo.Iterator.new([1, 2, 3, 2, 3, 4, 5, 4])
    is_deeply_ok(list(iterator.uniq()), [1, 2, 3, 4, 5], 'right result')
    is_deeply_ok(list(Pyjo.Iterator.new([[1, 2], [2, 1], [3, 2]]).uniq(lambda e: e[1])), [[1, 2], [2, 1]], 'callback')
    is_deeply_ok(list(Pyjo.Iterator.new([Word('a'), Word('A')]).uniq('upper').map(str)), ['a'], 'method')
    is_deeply_ok(list(Pyjo.Iterator.new([None, '', 1]).uniq()), [None, 1], 'None and an empty string')
    is_deeply_ok(run(iterator.uniq().to_list_p()), [1, 2, 3, 4, 5], 'async')
    is_deeply_ok(run(iterator.uniq(lambda e: e % 2).to_list_p()), [1, 2], 'async callback')

with subtest('async for'):

    async def collect():
        got = []
        async for e in Pyjo.Iterator.new([1, 2, 3]).map(lambda e: e * 2):
            got.append(e)
        async for e in c(4, 5):
            got.append(e)
        return got

    is_deeply_ok(run(collect()), [2, 4, 6, 4, 5], 'iterator and collection')

with subtest('Asynchronous iterable'):
    is_deeply_ok(list(Pyjo.Iterator.new(numbers(3))), [1, 2, 3], 'for')
    is_deeply_ok(run(Pyjo.Iterator.new(numbers(3)).map(lambda e: e * 2).to_list_p()), [2, 4, 6], 'async for')
    is_deeply_ok(Pyjo.Iterator.new(numbers(4)).grep(lambda e: e % 2).to_list(), [1, 3], 'chain for')

with subtest('Streams'):

    def stream_pair():
        a, b = socket.socketpair()
        a.setblocking(False)
        b.setblocking(False)
        streams = Pyjo.IOLoop.Stream.new(a), Pyjo.IOLoop.Stream.new(b)
        for stream in streams:
            stream.start()
        return streams

    reader, writer = stream_pair()
    isa_ok(reader.iterate(), Pyjo.Iterator.object, 'iterate of a stream')
    writer.write(b'abcdefg').close_gracefully()
    is_deeply_ok(list(reader.iterate(3)), [b'abc', b'def', b'g'], 'for over the chunks of a stream')

    reader, writer = stream_pair()
    messages = Pyjo.IOLoop.Messages.new(reader)
    isa_ok(messages.iterate(), Pyjo.Iterator.object, 'iterate of messages')
    writer.write(b'one\ntwo\n').close_gracefully()
    is_deeply_ok(list(messages.iterate().map(bytes.upper)), [b'ONE', b'TWO'], 'for over a chain of messages')

    server = Pyjo.IOLoop.Datagram.new().bind(address='127.0.0.1')
    isa_ok(server.iterate(), Pyjo.Iterator.object, 'iterate of a datagram socket')
    server.close()

    e = Pyjo.EventEmitter.new()
    events = e.events('foo')
    isa_ok(events, Pyjo.Iterator.object, 'events of an emitter')
    e.emit('foo', 1).emit('foo', 2).emit('close')
    is_deeply_ok(list(events.map(lambda args: args[0])), [1, 2], 'for over the events')

with subtest('Errors'):

    def fail(e):
        if e == 2:
            raise ValueError('Two')
        return e

    throws_ok(lambda: list(Pyjo.Iterator.new([1, 2, 3]).map(fail)), 'Two', 'callback')
    throws_ok(
        lambda: list(Pyjo.Iterator.new([1, 2]).map(lambda e: Pyjo.Promise.reject(ValueError('No')))), 'No', 'promise'
    )
    throws_ok(
        lambda: list(Pyjo.Iterator.new([1, 2, 3]).map(lambda e: Pyjo.Promise.reject(f'No {e}'), concurrency=2)),
        re.compile(r'^No 1$'),
        'promise with concurrency',
    )
    errors = []
    Pyjo.Iterator.new([1, 2, 3]).map(fail).to_list_p().catch(lambda e: errors.append(str(e))).wait()
    is_deeply_ok(errors, ['Two'], 'async callback')

with subtest('No unhandled rejections of the promises left in progress'):
    with warnings.catch_warnings(record=True) as warn:
        warnings.simplefilter('always')
        elements = iter(Pyjo.Iterator.new([1, 2, 3]).map(lambda e: Pyjo.Promise.reject(f'No {e}'), concurrency=3))
        throws_ok(lambda: next(elements), re.compile(r'^No 1$'), 'first rejection')
        gc.collect()
        Pyjo.IOLoop.one_tick()
        is_deeply_ok([str(w.message) for w in warn], [], 'no warnings')

with subtest('for in a running event loop'):
    errors = []

    def timer(loop):
        try:
            list(Pyjo.Iterator.new([1]).map(lambda e: Pyjo.Promise.timer(0.001, e)))
        except RuntimeError as e:
            errors.append(str(e))
        is_deeply_ok(list(Pyjo.Iterator.new([1]).map(lambda e: e + 1)), [2], 'no promise to wait for')
        is_deeply_ok(list(Pyjo.Iterator.new([1]).map(Pyjo.Promise.resolve)), [1], 'settled promise')

    Pyjo.IOLoop.timer(0, timer)
    Pyjo.IOLoop.one_tick()
    is_deeply_ok(errors, ['A promise cannot be waited for in a running event loop, await it instead'], 'right error')

done_testing()
