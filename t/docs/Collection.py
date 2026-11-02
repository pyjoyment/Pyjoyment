from Pyjo.Test import *

import contextlib
import io
import re


with subtest('Synopsis'):
    from Pyjo.Collection import Collection

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Manipulate collection
        collection = Collection(['just', 'works'])
        collection.insert(0, 'it')
        print(collection.join('\n'))
    is_ok(output.getvalue(), 'it\njust\nworks\n', 'join')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Collection

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Manipulate collection
        collection = Pyjo.Collection.new('just', 'works')
        collection.insert(0, 'it')
        print(collection.join('\n'))
    is_ok(output.getvalue(), 'it\njust\nworks\n', 'join')

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Chain methods
        collection.map(lambda e: e.capitalize()).shuffle().each(lambda word, num: print(f'{num}: {word}'))
    is_ok(sorted(line[3:] for line in output.getvalue().splitlines()), ['It', 'Just', 'Works'], 'shuffled')

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Use the alternative constructor
        from Pyjo.Collection import c

        c('a', 'b', 'c').join('/').url_escape().say()
    is_ok(output.getvalue(), 'a%2Fb%2Fc\n', 'url_escape')

with subtest('Description'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Access list directly to manipulate collection
        collection = Pyjo.Collection.new(*range(1, 26))
        collection[23] += 100
        for e in collection:
            print(e)
    is_ok(output.getvalue().split('\n')[23], '124', 'element 23')

    # Make a collection of an iterable
    collection = Pyjo.Collection.object(range(1, 26))
    is_ok(collection.size, 25, 'size')

with subtest('c'):
    collection = c(1, 2, 3)
    is_deeply_ok(collection, [1, 2, 3], 'collection')

with subtest('compact'):
    # "0, 1, 2, 3"
    is_ok(c(0, 1, None, 2, '', 3).compact().join(', '), '0, 1, 2, 3', 'compact')

with subtest('each'):
    collection = c('a', 'b')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Make a numbered list
        collection.each(lambda e, num: print(f'{num}: {e}'))
    is_ok(output.getvalue(), '1: a\n2: b\n', 'numbered list')

with subtest('first'):
    collection = c(2, 'Pyjoyment', 7)

    # Find first value that contains the word "pyjo"
    interesting = collection.first(re.compile(r'pyjo', re.I))
    is_ok(interesting, 'Pyjoyment', 'interesting')

    collection = c(2, 7, 9)

    # Find first value that is greater than 5
    greater = collection.first(lambda e: e > 5)
    is_ok(greater, 7, 'greater')

with subtest('flatten'):
    # "1, 2, 3, 4, 5, 6, 7"
    is_ok(c(1, [2, [3, 4], 5, [6]], 7).flatten().join(', '), '1, 2, 3, 4, 5, 6, 7', 'flatten')

with subtest('get'):
    from Pyjo.Util import die

    import sys

    argv = sys.argv
    sys.argv = ['script', 'example.com']
    address = c(*sys.argv).get(1) or die('address missing')
    port = int(c(*sys.argv).get(2, '80'))
    sys.argv = argv
    is_ok(address, 'example.com', 'address')
    is_ok(port, 80, 'port')

with subtest('grep'):
    collection = c(2, 'Pyjoyment', 'pyjo', 7)

    # Find all values that contain the word "pyjo"
    interesting = collection.grep(re.compile(r'pyjo', re.I))
    is_deeply_ok(interesting, ['Pyjoyment', 'pyjo'], 'interesting')

    collection = c(2, 7, 9)

    # Find all values that are greater than 5
    greater = collection.grep(lambda e: e > 5)
    is_deeply_ok(greater, [7, 9], 'greater')

with subtest('head'):
    # "A B C"
    is_ok(c('A', 'B', 'C', 'D', 'E').head(3).join(' '), 'A B C', 'head(3)')

    # "A B"
    is_ok(c('A', 'B', 'C', 'D', 'E').head(-3).join(' '), 'A B', 'head(-3)')

with subtest('iterate'):
    import Pyjo.DOM
    import Pyjo.Promise

    import types

    # A user agent that answers without the network
    class FakeUA:
        def get_p(self, url):
            return Pyjo.Promise.timer(
                0.001,
                types.SimpleNamespace(result=types.SimpleNamespace(dom=lambda: Pyjo.DOM.new(f'<title>{url}</title>'))),
            )

    ua = FakeUA()
    urls = ['a', 'b', 'c', 'd']

    # "2, 4, 6"
    is_ok(c(1, 2, 3).iterate().map(lambda e: e * 2).join(', '), '2, 4, 6', 'map')

    output = io.StringIO()

    async def titles():
        # Perform 3 requests at a time concurrently, in a coroutine
        async for tx in c(*urls).iterate().map(ua.get_p, concurrency=3):
            print(tx.result.dom().at('title').text)

    with contextlib.redirect_stdout(output):
        Pyjo.Promise.new(titles()).wait()
    is_ok(output.getvalue(), 'a\nb\nc\nd\n', 'titles')

    got = []

    async def elements():
        async for e in c(1, 2, 3):
            got.append(e)

    Pyjo.Promise.new(elements()).wait()
    is_deeply_ok(got, [1, 2, 3], '__aiter__')

with subtest('join'):
    collection = c('a', 'b')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Join all values with commas
        collection.join(', ').say()
    is_ok(output.getvalue(), 'a, b\n', 'join')

with subtest('map'):
    collection = c('a', 'b')

    # Append the word "pyjo" to all values
    pyjoified = collection.map(lambda e: e + 'pyjo')
    is_deeply_ok(pyjoified, ['apyjo', 'bpyjo'], 'pyjoified')

with subtest('new'):
    collection = Pyjo.Collection.new(1, 2, 3)
    is_deeply_ok(collection, [1, 2, 3], 'collection')
    collection = Collection([1, 2, 3])
    is_deeply_ok(collection, [1, 2, 3], 'constructor')
    collection = Collection(n for n in range(3))
    is_deeply_ok(collection, [0, 1, 2], 'constructor of a generator')

with subtest('reduce'):
    collection = c(1, 2, 2, 3)

    # Calculate the sum of all values
    total = collection.reduce(lambda a, b: a + b)
    is_ok(total, 8, 'total')

    # Count how often each value occurs in collection
    counts = collection.reduce(lambda a, b: a | {b: a.get(b, 0) + 1}, {})
    is_deeply_ok(counts, {1: 1, 2: 2, 3: 1}, 'counts')

with subtest('sort'):
    collection = c('b', 'C', 'a')

    # Sort values case-insensitive
    case_insensitive = collection.sort(key=str.upper)
    is_deeply_ok(case_insensitive, ['a', 'b', 'C'], 'case_insensitive')

with subtest('tail'):
    # "C D E"
    is_ok(c('A', 'B', 'C', 'D', 'E').tail(3).join(' '), 'C D E', 'tail(3)')

    # "D E"
    is_ok(c('A', 'B', 'C', 'D', 'E').tail(-3).join(' '), 'D E', 'tail(-3)')

with subtest('to_dict'):
    # {'a': 1, 'b': 2, 'c': 3}
    is_deeply_ok(c(('a', 1), ('b', 2), ('c', 3)).to_dict(), {'a': 1, 'b': 2, 'c': 3}, 'to_dict')

with subtest('to_iter'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        for e in c(1, 2, 3).to_iter():
            print(e)
    is_ok(output.getvalue(), '1\n2\n3\n', 'to_iter')

with subtest('to_set'):
    # {1, 2, 3}
    is_deeply_ok(c(1, 2, 3, 2).to_set(), {1, 2, 3}, 'to_set')

with subtest('to_tuple'):
    # (1, 2, 3)
    is_deeply_ok(c(1, 2, 3).to_tuple(), (1, 2, 3), 'to_tuple')

with subtest('uniq'):
    # "foo bar baz"
    is_ok(c('foo', 'bar', 'bar', 'baz').uniq().join(' '), 'foo bar baz', 'uniq')

    # [[1, 2], [2, 1]]
    is_deeply_ok(c([1, 2], [2, 1], [3, 2]).uniq(lambda e: e[1]).to_list(), [[1, 2], [2, 1]], 'uniq with callback')

with subtest('zip'):
    # [('a', 1), ('b', 2), ('c', 3)]
    is_deeply_ok(c('a', 'b', 'c').zip([1, 2, 3]).to_list(), [('a', 1), ('b', 2), ('c', 3)], 'to_list')

    # {'a': 1, 'b': 2, 'c': 3}
    is_deeply_ok(c('a', 'b', 'c').zip([1, 2, 3]).to_dict(), {'a': 1, 'b': 2, 'c': 3}, 'to_dict')

done_testing()
