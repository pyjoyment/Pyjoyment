import Pyjo.DOM
import Pyjo.Promise

from Pyjo.Test import *

import contextlib
import io
import re
import types


# A user agent that answers without the network, the later URLs sooner
class FakeUA:
    def get_p(self, url):
        tx = types.SimpleNamespace(result=types.SimpleNamespace(dom=lambda: Pyjo.DOM.new(f'<title>{url}</title>')))
        return Pyjo.Promise.timer(0.01 * (4 - len(url)), tx)


# The messages of a stream, as an asynchronous iterable
async def stream(*messages):
    for message in messages:
        await Pyjo.Promise.timer(0.001)
        yield message


# A coroutine of the test, run by the reactor until it is done
def run(coro):
    Pyjo.Promise.new(coro).wait()


ua = FakeUA()
urls = ['a', 'bb', 'ccc']

with subtest('Synopsis'):
    from Pyjo.Iterator import Iterator

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Elements of an iterable, one by one, through a chain
        for word in Iterator(['just', 'works']).map(lambda e: e.upper()):
            print(word)
    is_ok(output.getvalue(), 'JUST\nWORKS\n', 'map')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Iterator

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Three requests at a time, and their titles in the order of the URLs
        titles = Pyjo.Iterator.new(urls).map(ua.get_p, concurrency=3).map(lambda tx: tx.result.dom().at('title').text)
        for title in titles:
            print(title)
    is_ok(output.getvalue(), 'a\nbb\nccc\n', 'for')

    output = io.StringIO()

    async def titles_async():
        # The same in a coroutine
        async for title in titles:
            print(title)

    with contextlib.redirect_stdout(output):
        run(titles_async())
    is_ok(output.getvalue(), 'a\nbb\nccc\n', 'async for')

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # A collection, lazily
        from Pyjo.Collection import c

        c(1, 2, 3).iterate().map(lambda e: e * 2).join(', ').say()
    is_ok(output.getvalue(), '2, 4, 6\n', 'collection')

with subtest('Description'):
    import Pyjo.JSON

    messages = stream(b'{"id": 1}', b'{"id": 2}')
    requests = []

    async def decode():
        # The messages of a stream as JSON, in a coroutine
        async for request in Pyjo.Iterator.new(messages).map(Pyjo.JSON.decode_json):
            requests.append(request)

    run(decode())
    is_deeply_ok(requests, [{'id': 1}, {'id': 2}], 'messages')

with subtest('compact'):
    # "0, 1, 2, 3"
    is_ok(Pyjo.Iterator.new([0, 1, None, 2, '', 3]).compact().join(', '), '0, 1, 2, 3', 'compact')

with subtest('each'):
    iterator = Pyjo.Iterator.new(['a', 'b'])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Make a numbered list
        iterator.each(lambda e, num: print(f'{num}: {e}'))
    is_ok(output.getvalue(), '1: a\n2: b\n', 'numbered list')

with subtest('each_p'):
    messages = stream(b'first', b'second')
    handled = []

    def handle(message, num):
        handled.append(message)

    async def each():
        # Process the messages one after another
        await Pyjo.Iterator.new(messages).each_p(handle)

    run(each())
    is_deeply_ok(handled, [b'first', b'second'], 'messages')

with subtest('first'):
    iterator = Pyjo.Iterator.new([3, 6, 9])

    # Find first value that is greater than 5
    greater = iterator.first(lambda e: e > 5)
    is_ok(greater, 6, 'greater')

with subtest('flatten'):
    # "1, 2, 3, 4, 5, 6, 7"
    is_ok(Pyjo.Iterator.new([1, [2, [3, 4], 5, [6]], 7]).flatten().join(', '), '1, 2, 3, 4, 5, 6, 7', 'flatten')

with subtest('grep'):
    iterator = Pyjo.Iterator.new([3, 6, 9])

    # Find all values that are greater than 5
    greater = iterator.grep(lambda e: e > 5)
    is_deeply_ok(list(greater), [6, 9], 'greater')
    is_deeply_ok(list(iterator.grep(re.compile(r'6'))), [6], 'regular expression')

with subtest('head'):
    # "A B C"
    is_ok(Pyjo.Iterator.new(['A', 'B', 'C', 'D', 'E']).head(3).join(' '), 'A B C', 'head(3)')

with subtest('join'):
    iterator = Pyjo.Iterator.new(['a', 'b'])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Join all values with commas
        iterator.join(', ').say()
    is_ok(output.getvalue(), 'a, b\n', 'join')

with subtest('map'):
    iterator = Pyjo.Iterator.new(['a', 'b'])

    # Append the word "pyjo" to all values
    pyjoified = iterator.map(lambda e: e + 'pyjo')
    is_deeply_ok(list(pyjoified), ['apyjo', 'bpyjo'], 'pyjoified')

    iterator = Pyjo.Iterator.new(urls)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Perform 3 requests at a time concurrently
        iterator.map(ua.get_p, concurrency=3).each(lambda tx, num: print(tx.result.dom().at('title').text))
    is_ok(output.getvalue(), 'a\nbb\nccc\n', 'titles')

with subtest('new'):
    is_deeply_ok(list(Pyjo.Iterator.new([1, 2, 3])), [1, 2, 3], 'iterable')
    is_deeply_ok(list(Pyjo.Iterator.new(n for n in range(3))), [0, 1, 2], 'generator')
    is_deeply_ok(list(Pyjo.Iterator.new(stream(b'a'))), [b'a'], 'asynchronous iterable')

with subtest('reduce'):
    iterator = Pyjo.Iterator.new([2, 5, 4, 1])

    # Calculate the sum of all values
    total = iterator.reduce(lambda a, b: a + b)
    is_ok(total, 12, 'total')

with subtest('to_list_p'):

    def title(tx):
        return tx.result.dom().at('title').text

    got = []

    async def to_list():
        # The titles of all pages, 3 at a time
        titles = await Pyjo.Iterator.new(urls).map(ua.get_p, concurrency=3).map(title).to_list_p()
        got.append(titles)

    run(to_list())
    is_deeply_ok(got, [['a', 'bb', 'ccc']], 'titles')

with subtest('uniq'):
    # "foo bar baz"
    is_ok(Pyjo.Iterator.new(['foo', 'bar', 'bar', 'baz']).uniq().join(' '), 'foo bar baz', 'uniq')

done_testing()
