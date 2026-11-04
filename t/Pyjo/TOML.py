from Pyjo.Test import *
from Pyjo.TOML import dump, load

import datetime
import math
import re
import tomllib


# Not in Mojolicious: Pyjo.TOML, which dumps TOML 1.0, as the standard library only reads it with tomllib

with subtest('Load'):
    is_deeply_ok(
        load('name = "Pyjoyment"\n[server]\nworkers = 4\n'), {'name': 'Pyjoyment', 'server': {'workers': 4}}, 'table'
    )
    throws_ok(lambda: load('name = '), re.compile(r'^TOML '), 'invalid')
    is_deeply_ok(load('\ufeffa = 1\n'), {'a': 1}, 'byte order mark')
    is_deeply_ok(load(b'a = "\xe2\x99\xa5"\n'), {'a': '\u2665'}, 'bytes of UTF-8')
    is_deeply_ok(load(bytearray(b'a = 1\n')), {'a': 1}, 'bytearray')
    for encoding in ('UTF-8-SIG', 'UTF-16', 'UTF-32'):
        is_deeply_ok(load('a = "\u2665"\r\n'.encode(encoding)), {'a': '\u2665'}, encoding)
    throws_ok(lambda: load(b'a = "\xc3"\n'), re.compile(r'^TOML found input that is not UTF-8'), 'invalid UTF-8')
    throws_ok(lambda: load(b'\xff\xfea'), re.compile(r'^TOML found input that is not UTF-16'), 'odd UTF-16')

with subtest('Dump keys and values'):
    is_ok(dump({'name': 'Pyjoyment', 'workers': 4}), 'name = "Pyjoyment"\nworkers = 4\n', 'keys')
    is_ok(dump({}), '', 'empty table')
    is_ok(
        dump({'a': True, 'b': False, 'c': 0, 'd': -12, 'e': 1.5, 'f': 1e20, 'g': 2.0}),
        'a = true\nb = false\nc = 0\nd = -12\ne = 1.5\nf = 1e+20\ng = 2.0\n',
        'types',
    )
    is_ok(dump({'a': float('inf'), 'b': float('-inf'), 'c': float('nan')}), 'a = inf\nb = -inf\nc = nan\n', 'floats')
    is_ok(
        dump({'key with spaces': 1, 'dotted.key': 2, 'ü': 3, '': 4, 'bare-key_1': 5}),
        '"key with spaces" = 1\n"dotted.key" = 2\n"ü" = 3\n"" = 4\nbare-key_1 = 5\n',
        'quoted keys',
    )

with subtest('Dump strings'):
    is_ok(dump({'s': 'it\'s "quoted"\\'}), 's = "it\'s \\"quoted\\"\\\\"\n', 'quotes and backslash')
    is_ok(dump({'s': '\x00\x08\t\x0c\r\x1b\x7f'}), 's = "\\u0000\\b\\t\\f\\r\\u001B\\u007F"\n', 'escapes')
    is_ok(dump({'s': 'utf ♥ \U0001f600'}), 's = "utf ♥ \U0001f600"\n', 'Unicode')
    is_ok(dump({'s': 'one\ntwo\n'}), 's = """\none\ntwo\n"""\n', 'multi-line')
    is_ok(dump({'s': '\none "two"\r\n'}), 's = """\n\none \\"two\\"\\r\n"""\n', 'multi-line with escapes')
    throws_ok(lambda: dump({'s': '\ud800'}), re.compile(r'^TOML does not support the surrogate'), 'surrogate')

with subtest('Dump dates and times'):
    is_ok(
        dump(
            {
                'a': datetime.datetime(1979, 5, 27, 7, 32, tzinfo=datetime.timezone(datetime.timedelta(hours=-8))),
                'b': datetime.datetime(1979, 5, 27, 7, 32, 0, 999999),
                'c': datetime.date(1979, 5, 27),
                'd': datetime.time(7, 32),
            }
        ),
        'a = 1979-05-27T07:32:00-08:00\nb = 1979-05-27T07:32:00.999999\nc = 1979-05-27\nd = 07:32:00\n',
        'offset, local date-time, date and time',
    )
    throws_ok(
        lambda: dump({'t': datetime.time(7, 32, tzinfo=datetime.UTC)}),
        re.compile(r'^TOML does not support a time with an offset'),
        'time with an offset',
    )

with subtest('Dump arrays and inline tables'):
    is_ok(dump({'a': [1, 2, 3], 'b': [], 'c': ('x', 'y')}), 'a = [1, 2, 3]\nb = []\nc = ["x", "y"]\n', 'arrays')
    is_ok(dump({'a': [[1, 2], ['x']]}), 'a = [[1, 2], ["x"]]\n', 'nested arrays')
    is_ok(dump({'a': [{'b': 1}, 2]}), 'a = [{ b = 1 }, 2]\n', 'inline table in a mixed array')
    is_ok(dump({'a': [[{'b': {}}]]}), 'a = [[{ b = {} }]]\n', 'empty inline table')
    is_ok(dump({'a': ['one\ntwo']}), 'a = ["one\\ntwo"]\n', 'line break in an inline string')

with subtest('Dump tables'):
    is_ok(
        dump({'name': 'app', 'server': {'workers': 4, 'listen': ['http://*:3000']}, 'debug': False}),
        'name = "app"\ndebug = false\n\n[server]\nworkers = 4\nlisten = ["http://*:3000"]\n',
        'keys before the tables',
    )
    is_ok(dump({'a': {'b': {'c': 1}}}), '[a.b]\nc = 1\n', 'only the tables that have keys')
    is_ok(dump({'a': {'b': {}}}), '[a.b]\n', 'empty table')
    is_ok(dump({'a b': {'c.d': {'e': 1}}}), '["a b"."c.d"]\ne = 1\n', 'quoted names')
    is_ok(
        dump({'a': {'x': 1, 'b': {'y': 2}, 'c': {'z': 3}}}),
        '[a]\nx = 1\n\n[a.b]\ny = 2\n\n[a.c]\nz = 3\n',
        'tables after the keys of their parent',
    )

with subtest('Dump arrays of tables'):
    is_ok(
        dump({'products': [{'name': 'Hammer', 'sku': 738594937}, {}, {'name': 'Nail', 'color': 'gray'}]}),
        '[[products]]\nname = "Hammer"\nsku = 738594937\n\n[[products]]\n\n[[products]]\nname = "Nail"\ncolor = "gray"\n',
        'products',
    )
    is_ok(
        dump({'fruits': [{'name': 'apple', 'physical': {'color': 'red'}, 'varieties': [{'name': 'red delicious'}]}]}),
        '[[fruits]]\nname = "apple"\n\n[fruits.physical]\ncolor = "red"\n\n[[fruits.varieties]]\nname = "red delicious"\n',
        'tables in an array of tables',
    )

with subtest('Dump objects and errors'):
    import Pyjo.URL

    class Data:
        def __json__(self):
            return {'a': [1]}

    is_ok(
        dump({'data': Data(), 'url': Pyjo.URL.new('http://example.com')}),
        'url = "http://example.com"\n\n[data]\na = [1]\n',
        'objects',
    )
    throws_ok(lambda: dump(['a']), re.compile(r'^TOML needs a table at the top, not a list'), 'not a table')
    throws_ok(lambda: dump({'a': None}), re.compile(r"^TOML does not support a value of the type 'NoneType'"), 'null')
    throws_ok(lambda: dump({'a': b'x'}), re.compile(r"^TOML does not support a value of the type 'bytes'"), 'bytes')
    throws_ok(lambda: dump({1: 'a'}), re.compile(r"^TOML does not support a key of the type 'int'"), 'key')
    recursive: dict[str, object] = {}
    recursive['self'] = recursive
    throws_ok(lambda: dump(recursive), re.compile(r'^TOML found a collection inside itself'), 'recursion')

with subtest('Dump the order of the keys'):
    value = {
        'b': 1,
        'a': {'d': 1, 'c': {'z': 1, 'y': 2}},
        'x': [{'q': 1, 'p': {'s': 1, 'r': 2}}],
        'm': [3, {'s': 1, 'r': 2}],
    }
    is_ok(
        dump(value),
        'b = 1\nm = [3, { s = 1, r = 2 }]\n\n[a]\nd = 1\n\n[a.c]\nz = 1\ny = 2\n\n[[x]]\nq = 1\n\n[x.p]\ns = 1\nr = 2\n',
        'order of the dict',
    )
    is_ok(
        dump(value, sort_keys=True),
        'b = 1\nm = [3, { r = 2, s = 1 }]\n\n[a]\nd = 1\n\n[a.c]\ny = 2\nz = 1\n\n[[x]]\nq = 1\n\n[x.p]\nr = 2\ns = 1\n',
        'keys sorted, with the keys of a table before its tables',
    )
    is_deeply_ok(load(dump(value, sort_keys=True)), load(dump(value)), 'same table')

with subtest('Dump round trip'):
    data = {
        'title': 'TOML "Example"',
        'owner': {'name': 'Tom', 'dob': datetime.datetime(1979, 5, 27, 7, 32, tzinfo=datetime.UTC)},
        'database': {'ports': [8000, 8001], 'data': [['delta', 'phi'], [3.14]], 'temp_targets': {'cpu': 79.5}},
        'servers': {'alpha': {'ip': '10.0.0.1'}, 'beta': {'ip': '10.0.0.2', 'role': 'backend'}},
        'products': [{'name': 'Hammer'}, {'name': 'Nail', 'tags': [{'a': 1}, {'b': [1, {'c': 'd\ne'}]}]}],
        'text': 'line one\nline "two" \\ \t\x01\n\n',
        'special keys': {'a.b': {'"': 1, "'": 2, '\n': 3}},
        'empty': {},
        'list': [],
    }
    is_deeply_ok(tomllib.loads(dump(data)), data, 'tomllib')
    is_deeply_ok(load(dump(data)), data, 'load')
    ok(math.isnan(load(dump({'n': float('nan')}))['n']), 'nan')

    # Every character of the ASCII, the Latin-1 and some more, alone and in strings and keys
    for code in [*range(0x100), 0x2028, 0xFEFF, 0x1F600]:
        string = chr(code)
        strings = [string, f'a{string}', f'{string}\n', f'a\n{string}', f'{string}"""']
        data = {s: s for s in strings}
        data['inline'] = strings
        if not is_deeply_ok(tomllib.loads(dump(data)), data, f'U+{code:04X}'):
            diag(dump(data))

done_testing()
