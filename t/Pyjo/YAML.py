from Pyjo.Test import *
from Pyjo.YAML import dump, dump_all, load, load_all, y

import datetime
import re


# Not in Mojolicious: Pyjo.YAML, the YAML that Mojolicious::Plugin::NotYAMLConfig reads with CPAN::Meta::YAML; the
# results are those of YAML 1.2, as of PyYAML for its YAML 1.1 where the two agree, where CPAN::Meta::YAML keeps the
# plain scalars as strings, reads the aliases and the flow collections as strings, and drops the empty lines and the
# comments of the block scalars

with subtest('Mappings'):
    is_deeply_ok(load('foo: bar\n'), {'foo': 'bar'}, 'one key')
    is_deeply_ok(load('foo: bar\nbaz: yada\n'), {'foo': 'bar', 'baz': 'yada'}, 'two keys')
    is_deeply_ok(load('a:\n  b:\n    c: d\n  e: f\ng: h\n'), {'a': {'b': {'c': 'd'}, 'e': 'f'}, 'g': 'h'}, 'nested')
    is_deeply_ok(load('\'quoted key\': v\n"dq key": w\n'), {'quoted key': 'v', 'dq key': 'w'}, 'quoted keys')
    is_deeply_ok(load('key with spaces: value\n'), {'key with spaces': 'value'}, 'key with spaces')
    is_deeply_ok(load('url: http://example.com:80/path\n'), {'url': 'http://example.com:80/path'}, 'colon in value')
    is_deeply_ok(load('time: 12:30\n'), {'time': '12:30'}, 'colon without space')
    is_deeply_ok(load('foo:\n  bar:\n  baz: x\n'), {'foo': {'bar': None, 'baz': 'x'}}, 'null in nested')

with subtest('Sequences'):
    is_deeply_ok(load('- one\n- two\n'), ['one', 'two'], 'root sequence')
    is_deeply_ok(load('foo:\n  - one\n  - two\nbar: x\n'), {'foo': ['one', 'two'], 'bar': 'x'}, 'indented')
    is_deeply_ok(load('foo:\n- one\n- two\nbar: x\n'), {'foo': ['one', 'two'], 'bar': 'x'}, 'not indented')
    is_deeply_ok(load('- a: 1\n  b: 2\n- c: 3\n'), [{'a': 1, 'b': 2}, {'c': 3}], 'mappings in items')
    is_deeply_ok(load('-\n  - x\n  - y\n- z\n'), [['x', 'y'], 'z'], 'nested sequence')
    is_deeply_ok(load('- - x\n  - y\n- z\n'), [['x', 'y'], 'z'], 'nested sequence on the line of the item')
    is_deeply_ok(load('- - - x\n- - a: 1\n    b: 2\n'), [[['x']], [{'a': 1, 'b': 2}]], 'deeper on the line of the item')
    is_deeply_ok(load('list:\n  -\n    a: 1\n  -\n    b: 2\n'), {'list': [{'a': 1}, {'b': 2}]}, 'items below')
    is_deeply_ok(load('- \n'), [None], 'null item')

with subtest('Scalars'):
    is_deeply_ok(load('foo: ~\nbar:\n'), {'foo': None, 'bar': None}, 'null')
    is_deeply_ok(load("foo: 'it''s'\n"), {'foo': "it's"}, 'single quoted')
    is_deeply_ok(load('foo: "a\\nb\\tc\\x41\\\\d\\"e"\n'), {'foo': 'a\nb\tcA\\d"e'}, 'double quoted')
    is_deeply_ok(load('foo: "\\N\\e\\0"\n'), {'foo': '\x85\x1b\x00'}, 'escapes')
    is_deeply_ok(
        load('foo: "\\u263a\\U0001F600\\L\\P\\_\\/\\ \\\t"\n'),
        {'foo': '\u263a\U0001f600\u2028\u2029\xa0/ \t'},
        'escapes of YAML',
    )
    is_deeply_ok(load("foo: '\\n'\n"), {'foo': '\\n'}, 'no escapes in single quotes')
    is_deeply_ok(load('foo: {}\nbar: []\n'), {'foo': {}, 'bar': []}, 'empty collections')
    is_deeply_ok(load("empty: ''\n"), {'empty': ''}, 'empty string')
    is_deeply_ok(load('foo:   spaced   \n'), {'foo': 'spaced'}, 'trimmed')
    is_deeply_ok(load('utf: утф\n'), {'utf': 'утф'}, 'Unicode')

with subtest('Types'):
    is_deeply_ok(load('foo: 1\nbar: true\nbaz: 1.5\n'), {'foo': 1, 'bar': True, 'baz': 1.5}, 'types')
    is_ok(load('- null')[0], None, 'null')
    is_ok(load('- Null')[0], None, 'Null')
    is_ok(load('- NULL')[0], None, 'NULL')
    is_ok(load('- ~')[0], None, 'tilde')
    is_ok(load('- true')[0], True, 'true')
    is_ok(load('- True')[0], True, 'True')
    is_ok(load('- TRUE')[0], True, 'TRUE')
    is_ok(load('- false')[0], False, 'false')
    is_ok(load('- False')[0], False, 'False')
    is_ok(load('- FALSE')[0], False, 'FALSE')
    is_ok(load('- 0')[0], 0, 'zero')
    is_ok(load('- -12')[0], -12, 'negative')
    is_ok(load('- +12')[0], 12, 'positive')
    is_ok(load('- 0o17')[0], 15, 'octal')
    is_ok(load('- 0x1F')[0], 31, 'hexadecimal')
    is_ok(load('- 1.5')[0], 1.5, 'float')
    is_ok(load('- .5')[0], 0.5, 'float without integer part')
    is_ok(load('- 1.')[0], 1.0, 'float without fraction')
    is_ok(load('- 1e3')[0], 1000.0, 'exponent')
    is_ok(load('- -1.5E-2')[0], -0.015, 'negative exponent')
    is_ok(load('- .inf')[0], float('inf'), 'infinity')
    is_ok(load('- -.Inf')[0], float('-inf'), 'negative infinity')
    ok(load('- .NaN')[0] != load('- .NaN')[0], 'not a number')
    is_ok(type(load('- 1')[0]), int, 'int')
    is_ok(type(load('- 1.0')[0]), float, 'float type')
    is_ok(type(load('- true')[0]), bool, 'bool')

    # The words of YAML 1.1 are strings
    is_deeply_ok(load('- yes\n- no\n- on\n- off\n- y\n- n\n'), ['yes', 'no', 'on', 'off', 'y', 'n'], 'YAML 1.1')

    # Strings
    is_deeply_ok(load('- \'1\'\n- "true"\n'), ['1', 'true'], 'quoted')
    is_deeply_ok(load('- 1.2.3\n- 0x\n- 12abc\n- tRuE\n'), ['1.2.3', '0x', '12abc', 'tRuE'], 'not numbers')
    is_deeply_ok(load('foo: |\n  1\n'), {'foo': '1\n'}, 'block scalar')
    is_deeply_ok(load('404: one\ntrue: yes\n"2": two\n'), {404: 'one', True: 'yes', '2': 'two'}, 'keys')
    is_ok(load('--- 42\n'), 42, 'document')

with subtest('Tags'):
    is_ok(load('- !!str 8080')[0], '8080', 'str')
    is_ok(load('- !!str true')[0], 'true', 'str of a bool')
    is_ok(load('- !!str ~')[0], '~', 'str of a tilde')
    is_ok(load('foo: !!str')['foo'], '', 'empty str')
    is_ok(load('foo: !!str |\n  text\n')['foo'], 'text\n', 'str of a block')
    is_ok(load('- !!int "42"')[0], 42, 'int of a quoted scalar')
    is_ok(load('- !!int 0x1F')[0], 31, 'int of hexadecimal')
    is_ok(load('- !!float 1')[0], 1.0, 'float of an integer')
    is_ok(type(load('- !!float 1')[0]), float, 'float type')
    is_ok(load("- !!bool 'true'")[0], True, 'bool')
    is_ok(load('- !!bool FALSE')[0], False, 'bool false')
    is_ok(load('foo: !!null')['foo'], None, 'null')
    is_ok(load('- !!null null')[0], None, 'null of null')
    is_ok(load('- !!binary aGVsbG8=')[0], b'hello', 'binary')
    is_ok(load('foo: !!binary |\n  aGVs\n  bG8=\n')['foo'], b'hello', 'binary of a block')
    is_ok(load('- !!timestamp 2001-12-14')[0], datetime.date(2001, 12, 14), 'date')
    is_ok(
        load('- !!timestamp 2001-12-14t21:59:43.10-05:00')[0],
        datetime.datetime(2001, 12, 14, 21, 59, 43, 100000, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))),
        'datetime',
    )
    is_ok(load('- !!timestamp 2001-12-14 21:59:43')[0], datetime.datetime(2001, 12, 14, 21, 59, 43), 'space')
    throws_ok(lambda: load('- !!int abc'), re.compile(r"^YAML found an invalid value of the tag !!int: 'abc'"), 'int')
    throws_ok(lambda: load('- !!bool yes'), re.compile(r'^YAML found an invalid value of the tag !!bool'), 'bool')
    throws_ok(lambda: load('- !!null 0'), re.compile(r'^YAML found an invalid value of the tag !!null'), 'null')
    throws_ok(lambda: load('- !!binary abc'), re.compile(r'^YAML found an invalid value of the tag !!binary'), 'binary')
    throws_ok(
        lambda: load('- !!timestamp x'), re.compile(r'^YAML found an invalid value of the tag !!timestamp'), 'time'
    )
    throws_ok(lambda: load('- !!map'), re.compile(r'^YAML does not support a feature'), 'collection tag')
    throws_ok(lambda: load('- !local x'), re.compile(r'^YAML does not support a feature'), 'local tag')

with subtest('Block scalars'):
    is_deeply_ok(
        load('foo: |\n  line one\n  line two\nbar: x\n'), {'foo': 'line one\nline two\n', 'bar': 'x'}, 'literal'
    )
    is_deeply_ok(load('foo: |-\n  line one\n  line two\n'), {'foo': 'line one\nline two'}, 'literal chomped')
    is_deeply_ok(load('foo: >\n  folded\n  text\n'), {'foo': 'folded text\n'}, 'folded')
    is_deeply_ok(load('foo: >-\n  folded\n  text\n'), {'foo': 'folded text'}, 'folded chomped')

with subtest('Block scalars with empty lines and comments'):
    is_ok(load('k: |\n  a\n\n  b\n')['k'], 'a\n\nb\n', 'empty line')
    is_ok(load('k: |\n  a\n  # not a comment\n  b\n')['k'], 'a\n# not a comment\nb\n', 'comment')
    is_ok(load('k: |\n\n  a\n')['k'], '\na\n', 'leading empty line')
    is_ok(load('k: |\n  a\n\n')['k'], 'a\n', 'clip')
    is_ok(load('k: |-\n  a\n\n')['k'], 'a', 'strip')
    is_ok(load('k: |+\n  a\n\n\nnext: 1\n')['k'], 'a\n\n\n', 'keep')
    is_ok(load('k: >+\n  a\n\n')['k'], 'a\n\n', 'keep at the end')
    is_ok(load('k: >\n  a\n  b\n\n  c\n   d\n  e\n')['k'], 'a b\nc\n d\ne\n', 'folding')
    is_deeply_ok(load('foo: |\nbar: x\n'), {'foo': '', 'bar': 'x'}, 'empty block')
    is_deeply_ok(load('a:\n  run: |-\n    one\n\n    two\n  b: 1\n'), {'a': {'run': 'one\n\ntwo', 'b': 1}}, 'nested')

with subtest('Multi-line scalars'):
    is_deeply_ok(load('k: some\n  text\nnext: 1\n'), {'k': 'some text', 'next': 1}, 'plain')
    is_deeply_ok(load('k:\n  value below\n  more\n'), {'k': 'value below more'}, 'plain below its key')
    is_deeply_ok(load('- a\n  b\n- c\n'), ['a b', 'c'], 'plain item')
    is_deeply_ok(load('- a\n  - b\n'), ['a - b'], 'plain item with a dash')
    is_ok(load('k: first\n\n  second\n')['k'], 'first\nsecond', 'plain with an empty line')
    is_ok(load('r: ${{ x\n  && y }}\n')['r'], '${{ x && y }}', 'expression of a workflow')
    is_ok(load('k: "multi\n  line"\n')['k'], 'multi line', 'double quoted')
    is_ok(load("k: 'multi\n\n  line'\n")['k'], 'multi\nline', 'single quoted with an empty line')
    is_ok(load('k: "a\\\n  b"\n')['k'], 'ab', 'escaped line break')
    is_ok(load('k: 1\n  2\n')['k'], '1 2', 'not a number')

with subtest('Flow collections'):
    is_deeply_ok(load('labels: [bug]\n'), {'labels': ['bug']}, 'sequence')
    is_deeply_ok(load('x: ["{|}"]\n'), {'x': ['{|}']}, 'quoted item')
    is_deeply_ok(
        load('x: [a, [b, c], {d: e, f: [1, 2.5, true, null]}]\n'),
        {'x': ['a', ['b', 'c'], {'d': 'e', 'f': [1, 2.5, True, None]}]},
        'nested',
    )
    is_deeply_ok(load("x: ['it''s', \"q\\\"\", 'a,b']\n"), {'x': ["it's", 'q"', 'a,b']}, 'quotes')
    is_deeply_ok(load('x: [\n  a,\n  b,\n]\n'), {'x': ['a', 'b']}, 'lines')
    is_deeply_ok(load('x: {a: 1,\n  b: 2}\n'), {'x': {'a': 1, 'b': 2}}, 'mapping in lines')
    is_deeply_ok(load('x: []\ny: {}\n'), {'x': [], 'y': {}}, 'empty')
    is_deeply_ok(load('[1, 2]\n'), [1, 2], 'document')
    is_deeply_ok(load('{a: b}\n'), {'a': 'b'}, 'mapping document')
    is_deeply_ok(load('x: [a: 1, b]\n'), {'x': [{'a': 1}, 'b']}, 'pair')
    is_deeply_ok(load('x: {a, b: 2}\n'), {'x': {'a': None, 'b': 2}}, 'key without a value')
    is_deeply_ok(load('x: [http://a.b:80/c, d]\n'), {'x': ['http://a.b:80/c', 'd']}, 'colons')
    is_deeply_ok(load('x: [a b, c] # comment\n'), {'x': ['a b', 'c']}, 'spaces and a comment')
    is_deeply_ok(load('x: {200: ok}\n'), {'x': {200: 'ok'}}, 'key with a type')
    is_deeply_ok(load('- {a: 1}\n- [b]\n'), [{'a': 1}, ['b']], 'items')

with subtest('Mappings in items'):
    is_deeply_ok(
        load('- generic [ref=e1]:\n  - text: hi\n'), [{'generic [ref=e1]': [{'text': 'hi'}]}], 'key with spaces'
    )
    is_deeply_ok(load('- "q: x"\n- \'{"a": 1}\'\n'), ['q: x', '{"a": 1}'], 'quoted items')
    is_deeply_ok(load("- 'k': v\n"), [{'k': 'v'}], 'quoted key')

with subtest('Comments and lines'):
    is_deeply_ok(load('foo: bar # comment\n'), {'foo': 'bar'}, 'trailing comment')
    is_deeply_ok(load('# comment\nfoo: bar\n\n# another\n'), {'foo': 'bar'}, 'comment lines')
    is_deeply_ok(load('\ufefffoo: bar\n'), {'foo': 'bar'}, 'byte order mark')
    is_deeply_ok(load('foo: bar\r\nbaz: yada\r\n'), {'foo': 'bar', 'baz': 'yada'}, 'CRLF')

with subtest('Documents'):
    is_deeply_ok(load('---\nfoo: bar\n'), {'foo': 'bar'}, 'start')
    is_deeply_ok(load('---\nfoo: bar\n...\n'), {'foo': 'bar'}, 'end')
    is_deeply_ok(load('%YAML 1.1\n---\nfoo: bar\n'), {'foo': 'bar'}, 'directive')
    is_ok(load('--- scalar\n'), 'scalar', 'scalar document')
    is_deeply_ok(load_all('--- one\n--- two\n'), ['one', 'two'], 'all documents')
    is_ok(load('--- one\n--- two\n'), 'two', 'last document')
    is_deeply_ok(load_all('---\n- a\n---\n- b\n'), [['a'], ['b']], 'sequences')
    is_deeply_ok(load_all(''), [], 'no document')
    is_ok(load(''), None, 'empty')
    is_ok(load('   \n'), None, 'blank')

with subtest('Anchors and aliases'):
    is_deeply_ok(load('a: &x 1\nb: *x\n'), {'a': 1, 'b': 1}, 'scalar')
    is_deeply_ok(load('a: &x\n  b: 1\nc: *x\n'), {'a': {'b': 1}, 'c': {'b': 1}}, 'mapping')
    is_deeply_ok(load('a: &x\n  - 1\n  - 2\nb: *x\n'), {'a': [1, 2], 'b': [1, 2]}, 'sequence')
    is_deeply_ok(load('a: &x\n- 1\nb: *x\n'), {'a': [1], 'b': [1]}, 'sequence at the indentation of the key')
    is_deeply_ok(load('- &x one\n- *x\n'), ['one', 'one'], 'items')
    is_deeply_ok(load('- &x\n  a: 1\n- *x\n'), [{'a': 1}, {'a': 1}], 'mapping in an item')
    is_deeply_ok(load('a: &x |\n  text\nb: *x\n'), {'a': 'text\n', 'b': 'text\n'}, 'block scalar')
    is_deeply_ok(load('a: &x "quoted"\nb: *x # comment\n'), {'a': 'quoted', 'b': 'quoted'}, 'quoted')
    is_deeply_ok(load('a: &x !!str 1\nb: !!str &y 2\nc: [*x, *y]\n'), {'a': '1', 'b': '2', 'c': ['1', '2']}, 'tags')
    is_deeply_ok(load('a: &x [1, &y 2]\nb: {c: *x, d: *y}\n'), {'a': [1, 2], 'b': {'c': [1, 2], 'd': 2}}, 'flow')
    is_deeply_ok(load('a: &x\nb: *x\n'), {'a': None, 'b': None}, 'empty')
    is_deeply_ok(load('a: &x 1\nb: &x 2\nc: *x\n'), {'a': 1, 'b': 2, 'c': 2}, 'anchor again')
    data = load('a: &x\n  b: 1\nc: *x\n')
    ok(data['a'] is data['c'], 'same object')
    is_deeply_ok(load_all('a: &x 1\nb: *x\n---\nc: &x 2\nd: *x\n'), [{'a': 1, 'b': 1}, {'c': 2, 'd': 2}], 'documents')
    is_deeply_ok(load('&a foo: bar\nb: *a\n'), {'foo': 'bar', 'b': 'foo'}, 'key')
    is_deeply_ok(load('x:\n  &a k: v\n  b: *a\n'), {'x': {'k': 'v', 'b': 'k'}}, 'nested key')
    is_deeply_ok(load('- &a k: v\n- *a\n'), [{'k': 'v'}, 'k'], 'key in an item')
    is_deeply_ok(load('a: &k key\n*k : v\n'), {'a': 'key', 'key': 'v'}, 'alias as a key')
    throws_ok(
        lambda: load('a: &x [1]\n*x : v\n'), re.compile(r'^YAML found a key that is not hashable'), 'list as a key'
    )
    throws_ok(
        lambda: load_all('a: &x 1\n---\nb: *x\n'), re.compile(r"^YAML found an unknown alias '\*x'"), 'per document'
    )

with subtest('Merge keys'):
    is_deeply_ok(load('a: &x\n  b: 1\n  c: 2\nd:\n  <<: *x\n  c: 3\n')['d'], {'b': 1, 'c': 3}, 'mapping')
    is_deeply_ok(load('a: &x {b: 1}\nd:\n  c: 3\n  <<: *x\n')['d'], {'b': 1, 'c': 3}, 'explicit keys first')
    is_deeply_ok(
        load('a: &x {b: 1, c: 1}\ne: &y {c: 2, d: 2}\nf:\n  <<: [*x, *y]\n')['f'],
        {'c': 1, 'd': 2, 'b': 1},
        'earlier mappings first',
    )
    is_deeply_ok(load('a: &x {b: 1}\nc: {<<: *x, d: 2}\n')['c'], {'b': 1, 'd': 2}, 'flow')
    is_deeply_ok(load('a: &x {b: 1}\nc:\n  - <<: *x\n    d: 2\n')['c'], [{'b': 1, 'd': 2}], 'item')
    is_deeply_ok(load('"<<": 1\n'), {'<<': 1}, 'quoted key')
    throws_ok(lambda: load('a: &x 1\nb:\n  <<: *x\n'), re.compile(r'^YAML found a merge key'), 'not a mapping')
    throws_ok(lambda: load('a: &x 1\nb:\n  <<: [*x]\n'), re.compile(r'^YAML found a merge key'), 'not mappings')

with subtest('Errors'):
    throws_ok(
        lambda: load('a: b\n  c: d\n'), re.compile(r"^YAML found illegal characters in plain scalar: 'c: d'"), 'indent'
    )
    throws_ok(lambda: load('? complex\n'), re.compile(r'^YAML does not support a feature'), 'complex key')
    throws_ok(lambda: load('!!str foo: bar\n'), re.compile(r'^YAML does not support a feature'), 'tag of a key')
    throws_ok(lambda: load('foo: !tag bar\n'), re.compile(r'^YAML does not support a feature'), 'local tag')
    throws_ok(lambda: load('foo: - bar\n'), re.compile(r'^YAML found illegal characters'), 'dash')
    throws_ok(lambda: load('foo: @bar\n'), re.compile(r'^YAML found illegal characters'), 'reserved')
    throws_ok(lambda: load('foo: a: b\n'), re.compile(r'^YAML found illegal characters'), 'colon')
    throws_ok(lambda: load('--- foo\nbar: baz\n'), re.compile(r'^YAML failed to classify the line'), 'second document')
    throws_ok(lambda: load('foo: [a, b\n'), re.compile(r'^YAML failed to find the end of the flow collection'), 'flow')
    throws_ok(lambda: load('foo: [a, b] c\n'), re.compile(r'^YAML found illegal characters after the flow'), 'after')
    throws_ok(lambda: load('foo: [a b c, ]x]\n'), re.compile(r'^YAML'), 'flow syntax')
    throws_ok(lambda: load('foo: "open\n'), re.compile(r'^YAML failed to find the end of the quoted scalar'), 'quote')
    throws_ok(lambda: load('foo: |2\n  x\n'), re.compile(r'^YAML does not support a feature'), 'indentation indicator')

    # Not in CPAN::Meta::YAML: an unknown alias is an error, not a string
    throws_ok(lambda: load('foo: *alias\n'), re.compile(r"^YAML found an unknown alias '\*alias'"), 'alias')
    throws_ok(lambda: load('foo: *alias bar\n'), re.compile(r'^YAML found illegal characters after the alias'), 'after')

with subtest('Dump mappings'):
    is_ok(dump({'foo': 'bar'}), 'foo: bar\n', 'one key')
    is_ok(dump({'a': {'b': {'c': 'd'}, 'e': 'f'}, 'g': 'h'}), 'a:\n  b:\n    c: d\n  e: f\ng: h\n', 'nested')
    is_ok(dump({404: 'one', True: 'two', None: 3, 1.5: 'four'}), '404: one\ntrue: two\nnull: 3\n1.5: four\n', 'keys')
    is_ok(
        dump({'404': 1, 'a: b': 2, 'a #b': 3, '<<': 4, '': 5}),
        "'404': 1\n'a: b': 2\n'a #b': 3\n'<<': 4\n'': 5\n",
        'quoted',
    )
    is_ok(
        dump({'-a': 1, 'a:b': 2, 'key with spaces': 3}), "'-a': 1\na:b: 2\nkey with spaces: 3\n", 'keys of characters'
    )
    is_ok(dump({'a\nb': 1, 'c\x00': 2}), '"a\\nb": 1\n"c\\0": 2\n', 'escaped keys')

with subtest('Dump sequences'):
    is_ok(dump(['one', 'two']), '- one\n- two\n', 'root sequence')
    is_ok(dump({'foo': ['one', 'two'], 'bar': 'x'}), 'foo:\n  - one\n  - two\nbar: x\n', 'indented')
    is_ok(
        dump({'foo': ['one', 'two'], 'bar': 'x'}, indent_sequences=False),
        'foo:\n- one\n- two\nbar: x\n',
        'not indented',
    )
    is_ok(dump([{'a': 1, 'b': 2}, {'c': 3}]), '- a: 1\n  b: 2\n- c: 3\n', 'mappings in items')
    is_ok(dump([['a', 'b'], 'c']), '- - a\n  - b\n- c\n', 'nested sequence')
    is_ok(dump([[['x']], [{'a': 1, 'b': 2}]]), '- - - x\n- - a: 1\n    b: 2\n', 'deeper')
    is_ok(dump(('a', 'b')), '- a\n- b\n', 'tuple')
    is_ok(dump({'a': {}, 'b': [], 'c': [[], {}]}), 'a: {}\nb: []\nc:\n  - []\n  - {}\n', 'empty collections')

with subtest('Dump indentation'):
    data = {'a': {'b': [{'c': 1, 'd': [2]}], 'e': 'x\n'}}
    is_ok(dump(data), 'a:\n  b:\n    - c: 1\n      d:\n        - 2\n  e: |\n    x\n', 'two spaces')
    is_ok(
        dump(data, indent=4),
        'a:\n    b:\n        - c: 1\n          d:\n              - 2\n    e: |\n        x\n',
        'four spaces',
    )
    is_ok(
        dump(data, indent=4, indent_sequences=False),
        'a:\n    b:\n    - c: 1\n      d:\n      - 2\n    e: |\n        x\n',
        'four spaces and sequences not indented',
    )
    is_ok(dump(['x\n']), '- |\n  x\n', 'block scalar in an item')
    throws_ok(lambda: dump([], indent=0), ValueError, 'no indentation')

with subtest('Dump scalars'):
    is_ok(
        dump([None, True, False, 0, -12, 1.5, 1e20]), '- null\n- true\n- false\n- 0\n- -12\n- 1.5\n- 1e+20\n', 'types'
    )
    is_ok(dump([float('inf'), float('-inf'), float('nan')]), '- .inf\n- -.inf\n- .nan\n', 'special floats')
    is_ok(
        dump(['', '1', 'true', 'null', '~', '1.5', '0x1F', '.inf']),
        "- ''\n- '1'\n- 'true'\n- 'null'\n- '~'\n- '1.5'\n- '0x1F'\n- '.inf'\n",
        'strings of other types',
    )

    # Strings that YAML 1.1 reads as other types
    is_ok(
        dump(['yes', 'Off', 'y', '1_000', '12:30', '2001-12-14']),
        "- 'yes'\n- 'Off'\n- 'y'\n- '1_000'\n- '12:30'\n- '2001-12-14'\n",
        'YAML 1.1',
    )
    is_ok(
        dump(['yes', 'Off', 'y', '1_000', '12:30', '2001-12-14'], version='1.2'),
        '- yes\n- Off\n- y\n- 1_000\n- 12:30\n- 2001-12-14\n',
        'YAML 1.2',
    )
    throws_ok(lambda: dump('a', version='1.0'), ValueError, 'unknown version')

    # Indicators
    is_ok(
        dump(['- a', '-', '---', '...', '?a', ':a', '#a', '&a', '*a', '!a']),
        "- '- a'\n- '-'\n- '---'\n- '...'\n- '?a'\n- ':a'\n- '#a'\n- '&a'\n- '*a'\n- '!a'\n",
        'indicators',
    )
    is_ok(
        dump(['|a', '>a', "'a", '"a', '%a', '@a', '`a', '[a', '{a', ',a']),
        "- '|a'\n- '>a'\n- '''a'\n- '\"a'\n- '%a'\n- '@a'\n- '`a'\n- '[a'\n- '{a'\n- ',a'\n",
        'more indicators',
    )
    is_ok(
        dump(['a: b', 'a:', 'a #b', ' a', 'a ', 'a\tb']),
        "- 'a: b'\n- 'a:'\n- 'a #b'\n- ' a'\n- 'a '\n- \"a\\tb\"\n",
        'inside',
    )
    is_ok(
        dump(['-a', '--port', 'a:b', 'a#b', "it's", 'a "b"', 'утф', '12abc', 'a\\b']),
        '- -a\n- --port\n- a:b\n- a#b\n- it\'s\n- a "b"\n- утф\n- 12abc\n- a\\b\n',
        'plain',
    )

    # Escapes
    is_ok(dump(['\x00\x07\x08\t\x0b\x0c\r\x1b'], multiline=False), '- "\\0\\a\\b\\t\\v\\f\\r\\e"\n', 'escapes of C')
    is_ok(
        dump(['\x01\x7f\x85\x9f\xa0\u2028\u2029\ufeff\ud800']),
        '- "\\x01\\x7f\\N\\x9f\xa0\\L\\P\\ufeff\\ud800"\n',
        'escapes of YAML',
    )
    is_ok(dump(['a\\"b\x00']), '- "a\\\\\\"b\\0"\n', 'backslash and quote')
    is_ok(dump(['\U0001f600']), '- \U0001f600\n', 'printable')

with subtest('Dump quotes'):
    is_ok(
        dump({'a': 'b', 'c': 1, 'd': "it's", 'e': 'x\x00'}, quote="'"),
        "a: 'b'\nc: 1\nd: 'it''s'\ne: \"x\\0\"\n",
        'single',
    )
    is_ok(dump({'a': 'b', 'c': None, 'd': "it's"}, quote='"'), 'a: "b"\nc: null\nd: "it\'s"\n', 'double')
    is_ok(dump({'a': 'b', '1': 'c'}, quote_keys="'"), "'a': b\n'1': c\n", 'single keys')
    is_ok(dump({'a': 'b', 1: 'c'}, quote_keys='"'), '"a": b\n1: c\n', 'double keys')
    is_ok(dump({'1': 'x\x00'}), '\'1\': "x\\0"\n', 'quotes when needed')
    throws_ok(lambda: dump('a', quote='`'), ValueError, 'unknown quote')
    throws_ok(lambda: dump('a', quote_keys='`'), ValueError, 'unknown quote of keys')

with subtest('Dump multi-line strings'):
    is_ok(dump({'a': 'one\ntwo\n', 'b': 1}), 'a: |\n  one\n  two\nb: 1\n', 'literal')
    is_ok(dump({'a': 'one\ntwo', 'b': 1}), 'a: |-\n  one\n  two\nb: 1\n', 'strip')
    is_ok(dump({'a': 'one\n\n', 'b': 1}), 'a: |+\n  one\n\nb: 1\n', 'keep')
    is_ok(dump({'a': '\none\n\n  two\n'}), 'a: |\n\n  one\n\n    two\n', 'empty and indented lines')
    is_ok(dump('a\nb\n'), '--- |\n  a\n  b\n', 'document')
    is_ok(dump({'a': 'x\n'}, quote="'"), 'a: |\n  x\n', 'with quotes')
    is_ok(dump({'a': 'one\ntwo\n'}, multiline=False), 'a: "one\\ntwo\\n"\n', 'off')
    is_ok(
        dump(['  a\nb', 'a\n  \nb', 'a\r\nb', '\n', 'a\n\x00']),
        '- "  a\\nb"\n- "a\\n  \\nb"\n- "a\\r\\nb"\n- "\\n"\n- "a\\n\\0"\n',
        'quoted',
    )

with subtest('Dump documents'):
    is_ok(dump({'a': 1}, explicit_start=True), '---\na: 1\n', 'start')
    is_ok(dump('scalar'), '--- scalar\n', 'scalar')
    is_ok(dump(None), '--- null\n', 'null')
    is_ok(dump({}), '--- {}\n', 'empty mapping')
    is_ok(dump_all([{'a': 1}, ['b'], 'c']), 'a: 1\n---\n- b\n--- c\n', 'documents')
    is_ok(dump_all([{'a': 1}, ['b']], explicit_start=True), '---\na: 1\n---\n- b\n', 'documents with the start')
    is_ok(dump_all([]), '', 'no document')

with subtest('Dump tags'):
    is_ok(dump({'key': b'hello', 'raw': bytearray(b'\x00')}), 'key: !!binary aGVsbG8=\nraw: !!binary AA==\n', 'binary')
    is_ok(
        dump([datetime.date(2001, 12, 14), datetime.datetime(2001, 12, 14, 21, 59, 43, 100000)]),
        '- !!timestamp 2001-12-14\n- !!timestamp 2001-12-14T21:59:43.100000\n',
        'timestamp',
    )

with subtest('Dump objects'):
    import Pyjo.Collection
    import Pyjo.String.Unicode
    import Pyjo.URL

    class Data:
        def __json__(self):
            return {'a': [1]}

    is_ok(dump({'data': Data()}), 'data:\n  a:\n    - 1\n', '__json__')
    is_ok(dump([Pyjo.URL.new('http://example.com')]), '- http://example.com\n', 'string')
    is_ok(dump(Pyjo.Collection.new(Pyjo.String.Unicode.new('a'))), '- a\n', 'collection')
    throws_ok(lambda: dump({'a': {1}}), re.compile(r"^YAML does not support a value of the type 'set'"), 'set')
    throws_ok(lambda: dump({(1, 2): 3}), re.compile(r"^YAML does not support a key of the type 'tuple'"), 'key')
    recursive: list[object] = []
    recursive.append(recursive)
    throws_ok(lambda: dump(recursive), re.compile(r'^YAML found a collection inside itself'), 'recursion')
    inner: list[object] = []
    inner.append({'a': inner})
    throws_ok(lambda: dump({'b': inner}), re.compile(r'^YAML found a collection inside itself'), 'deeper recursion')

with subtest('Dump anchors'):
    shared = ['x']
    is_ok(dump([shared, shared]), '- &id\n  - x\n- *id\n', 'sequence')
    is_ok(dump([shared, shared], anchors=False), '- - x\n- - x\n', 'without anchors')
    mapping = {'a': 1}
    is_ok(dump({'b': mapping, 'c': [mapping]}), 'b: &b\n  a: 1\nc:\n  - *b\n', 'mapping')
    is_ok(dump({'steps': [mapping, mapping]}), 'steps:\n  - &steps\n    a: 1\n  - *steps\n', 'items')
    is_ok(dump({'a': shared, 'b': shared}, indent_sequences=False), 'a: &a\n- x\nb: *a\n', 'not indented')
    empty: list[object] = []
    is_ok(dump({'a': empty, 'b': empty}), 'a: &a []\nb: *a\n', 'empty')
    is_ok(dump([mapping, shared, mapping, shared]), '- &id\n  a: 1\n- &id2\n  - x\n- *id\n- *id2\n', 'two')
    other = {'b': 2}
    is_ok(
        dump({'a': mapping, 'x': {'a': other}, 'c': mapping, 'd': other}),
        'a: &a\n  a: 1\nx:\n  a: &a2\n    b: 2\nc: *a\nd: *a2\n',
        'name of a key again',
    )
    is_ok(
        dump({'key with spaces': mapping, 'ü': other, 404: shared, 'k': [mapping, other, shared]}),
        'key with spaces: &key_with_spaces\n  a: 1\nü: &id\n  b: 2\n404: &404\n  - x\n'
        + 'k:\n  - *key_with_spaces\n  - *id\n  - *404\n',
        'characters of the names',
    )
    is_ok(dump_all([[shared, shared], [shared]]), '- &id\n  - x\n- *id\n---\n- - x\n', 'documents')
    pair = ('x',)
    is_ok(dump([pair, pair]), '- - x\n- - x\n', 'tuple')
    data = load(dump({'b': mapping, 'c': [mapping]}))
    ok(data['b'] is data['c'][0], 'same object')

with subtest('Dump the order of the keys'):
    value = {'b': 1, 'a': {'d': [{'z': 1, 'y': 2}], 'c': 3}}
    is_ok(dump(value), "b: 1\na:\n  d:\n    - z: 1\n      'y': 2\n  c: 3\n", 'order of the dict')
    is_ok(dump(value, sort_keys=True), "a:\n  c: 3\n  d:\n    - 'y': 2\n      z: 1\nb: 1\n", 'keys sorted')
    is_ok(dump_all([{'b': 1, 'a': 2}, {'d': 3, 'c': 4}], sort_keys=True), 'a: 2\nb: 1\n---\nc: 4\nd: 3\n', 'documents')
    is_ok(dump({2: 'two', 1: 'one'}, sort_keys=True), '1: one\n2: two\n', 'keys that are not strings')

with subtest('y'):
    is_ok(y((1, 2)), '- 1\n- 2\n', 'tuple')
    is_ok(y({}), '--- {}\n', 'empty dict')
    is_deeply_ok(y(bytearray(b'- \xe2\x99\xa5\n')), ['\u2665'], 'bytearray of UTF-8')
    is_ok(y(''), None, 'empty string')
    is_deeply_ok(y('--- first\n--- second\n'), 'second', 'last document')
    throws_ok(lambda: y('foo: !tag bar'), re.compile(r'^YAML does not support a feature'), 'error')
    is_deeply_ok(y(y({'b': [1, {'a': None}]})), {'b': [1, {'a': None}]}, 'round trip')

with subtest('Dump round trip'):
    data = {
        'name': 'Pyjoyment',
        'numbers': [0, -1, 1.5, float('inf'), True, None],
        'nested': {'list': [{'a': 'one\ntwo\n'}, ['x', ['y']], {}], 'empty': []},
        404: {'quoted': ['1', 'yes', '', ' a ', 'a: b', '\x00', '\u2028']},
    }
    for options in (
        {},
        {'indent': 4},
        {'indent': 3, 'indent_sequences': False},
        {'quote': "'", 'quote_keys': '"'},
        {'quote': '"', 'quote_keys': "'", 'multiline': False},
        {'explicit_start': True},
        {'version': '1.2'},
    ):
        is_deeply_ok(load(dump(data, **options)), data, f'round trip {options}')
    is_deeply_ok(load_all(dump_all([data, 'two', []])), [data, 'two', []], 'documents')

    # Every character of the ASCII, the Latin-1 and some more, alone and in strings
    for code in [*range(0x100), 0x2028, 0x2029, 0xFEFF, 0xD800, 0x1F600]:
        string = chr(code)
        strings = [string, f'a{string}', f'{string}a', f'a{string}b', f'a {string} b', f'{string}\n', f'a\n{string}\n']
        if not is_deeply_ok(load(dump({s: s for s in strings})), {s: s for s in strings}, f'U+{code:04X}'):
            diag(dump({s: s for s in strings}))

done_testing()
