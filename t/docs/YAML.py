from Pyjo.Test import *

import re


with subtest('Synopsis'):
    from Pyjo.YAML import load, load_all

    config = load("""\
foo: bar
list:
  - one
  - two
""")
    is_deeply_ok(config, {'foo': 'bar', 'list': ['one', 'two']}, 'mapping')

    documents = load_all('--- first\n--- second\n')
    is_deeply_ok(documents, ['first', 'second'], 'documents')

    from Pyjo.YAML import dump, dump_all

    string = dump({'foo': 'bar', 'list': ['one', 'two']})
    is_ok(string, 'foo: bar\nlist:\n  - one\n  - two\n', 'dump')

    from Pyjo.YAML import y

    string = y({'foo': 'bar'}, {'baz': 1})
    is_ok(string, 'foo: bar\n---\nbaz: 1\n', 'y dumps')
    documents = y(string)
    is_deeply_ok(documents, [{'foo': 'bar'}, {'baz': 1}], 'y loads')

with subtest('Description'):
    # {'foo': [1, True, 'yes', '2']}
    is_deeply_ok(load("foo:\n  - 1\n  - true\n  - yes\n  - '2'\n"), {'foo': [1, True, 'yes', '2']}, 'types')
    throws_ok(lambda: load('foo: !tag bar'), re.compile(r'^YAML does not support a feature'), 'other tag')

with subtest('Tags'):
    import datetime

    # {'port': '8080', 'key': b'hello', 'day': datetime.date(2001, 12, 14)}
    is_deeply_ok(
        load('port: !!str 8080\nkey: !!binary aGVsbG8=\nday: !!timestamp 2001-12-14\n'),
        {'port': '8080', 'key': b'hello', 'day': datetime.date(2001, 12, 14)},
        'standard tags',
    )

with subtest('Anchors'):
    # {'base': {'a': 1, 'b': 1}, 'copy': {'a': 1, 'b': 2}}
    is_deeply_ok(
        load('base: &base\n  a: 1\n  b: 1\ncopy:\n  <<: *base\n  b: 2\n'),
        {'base': {'a': 1, 'b': 1}, 'copy': {'a': 1, 'b': 2}},
        'anchor, alias and merge key',
    )

with subtest('Dump'):
    # 'name: Pyjoyment\nlist:\n  - one\n  - 2\nrun: |\n  make\n'
    is_ok(
        dump({'name': 'Pyjoyment', 'list': ['one', 2], 'run': 'make\n'}),
        'name: Pyjoyment\nlist:\n  - one\n  - 2\nrun: |\n  make\n',
        'block style',
    )

with subtest('dump'):
    value = {'foo': ['bar']}
    string = dump(value)
    is_ok(string, 'foo:\n  - bar\n', 'string')
    string = dump({'foo': ['bar'], 'baz': 1}, sort_keys=True)
    is_ok(string, 'baz: 1\nfoo:\n  - bar\n', 'sorted')
    string = dump(value, indent=4, indent_sequences=False, quote='"')
    is_ok(string, 'foo:\n- "bar"\n', 'options')

    # 'foo:\n- "bar"\n'
    is_ok(dump({'foo': ['bar']}, indent_sequences=False, quote='"'), 'foo:\n- "bar"\n', 'example')

with subtest('dump_all'):
    values = ['first', 'second']
    string = dump_all(values)

    # '--- first\n--- second\n'
    is_ok(dump_all(['first', 'second']), '--- first\n--- second\n', 'documents')

with subtest('load'):
    value = load('foo: bar')

    # {'foo': 'bar'}
    is_deeply_ok(value, {'foo': 'bar'}, 'value')

with subtest('load_all'):
    values = load_all('--- first\n--- second\n')

    # ['first', 'second']
    is_deeply_ok(values, ['first', 'second'], 'values')

with subtest('y'):
    documents = y('foo: bar\n')
    is_deeply_ok(documents, [{'foo': 'bar'}], 'documents')
    string = y({'foo': 'bar'})
    is_ok(string, 'foo: bar\n', 'dict')
    string = y({'foo': 'bar'}, {'baz': 1})
    is_ok(string, 'foo: bar\n---\nbaz: 1\n', 'dicts')
    string = y({'foo': 'bar', 'baz': 1}, sort_keys=True)
    is_ok(string, 'baz: 1\nfoo: bar\n', 'sorted')

    # 'foo: bar\n'
    is_ok(y({'foo': 'bar'}), 'foo: bar\n', 'dump')

    # '--- 1\n--- 2\n'
    is_ok(y(1, 2), '--- 1\n--- 2\n', 'dump documents')

    # [{'foo': 'bar'}]
    is_deeply_ok(y(b'foo: bar\n'), [{'foo': 'bar'}], 'load')

    # 'bar'
    is_ok(y('foo: bar\n').first()['foo'], 'bar', 'first')

done_testing()
