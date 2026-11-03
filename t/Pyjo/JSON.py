import os


os.environ['PYJO_NO_JSON_STDLIB'] = '1'

# E402 "Module level import not at top of file": the environment variable has to
# be set before Pyjo.JSON is imported
import Pyjo.Base  # noqa: E402
import Pyjo.JSON  # noqa: E402

from Pyjo.JSON import decode_json, encode_json, false, from_json, j, to_json, true  # noqa: E402
from Pyjo.String.Bytes import b  # noqa: E402
from Pyjo.Test import *  # noqa: E402
from Pyjo.Util import encode  # noqa: E402

import re  # noqa: E402


class JSONTest(Pyjo.Base.object):
    def __init__(self, **kwargs):
        self.something = {}
        self.set(**kwargs)

    def __json__(self):
        return self.something


class JSONTest2(Pyjo.Base.object):
    def __and__(self, other):
        raise RuntimeError

    def __str__(self):
        return 'works!'


class JSONTest3(Pyjo.Base.object):
    pass


with subtest('Decode array'):
    array = decode_json('[]')
    is_deeply_ok(array, [], 'decode []')
    array = decode_json('[ [ ]]')
    is_deeply_ok(array, [[]], 'decode [ [ ]]')

with subtest('Decode number'):
    array = decode_json('[0]')
    is_deeply_ok(array, [0], 'decode [0]')
    array = decode_json('[1]')
    is_deeply_ok(array, [1], 'decode [1]')
    array = decode_json('[ "-122.026020" ]')
    is_deeply_ok(array, ['-122.026020'], 'decode [ -122.026020 ]')
    array = decode_json('[ -122.026020 ]')
    is_deeply_ok(array, [-122.02602], 'decode [ -122.026020 ]')
    array = decode_json('[0.0]')
    cmp_ok(array[0], '==', 0, 'value is 0')
    array = decode_json('[0e0]')
    cmp_ok(array[0], '==', 0, 'value is 0')
    array = decode_json('[1,-2]')
    is_deeply_ok(array, [1, -2], 'decode [1,-2]')
    array = decode_json('["10e12" , [2 ]]')
    is_deeply_ok(array, ['10e12', [2]], 'decode ["10e12" , [2 ]]')
    array = decode_json('[10e12 , [2 ]]')
    is_deeply_ok(array, [10000000000000, [2]], 'decode [10e12 , [2 ]]')
    array = decode_json('[37.7668 , [ 20 ]] ')
    is_deeply_ok(array, [37.7668, [20]], 'decode [37.7668 , [ 20 ]] ')
    array = decode_json('[1e3]')
    cmp_ok(array[0], '==', 1e3, 'value is 1e3')
    value = decode_json('0')
    cmp_ok(value, '==', 0, 'decode 0')
    value = decode_json('23.3')
    cmp_ok(value, '==', 23.3, 'decode 23.3')

with subtest('Decode name'):
    array = decode_json('[true]')
    is_deeply_ok(array, [Pyjo.JSON.true], 'decode [true]')
    array = decode_json('[null]')
    is_deeply_ok(array, [None], 'decode [null]')
    array = decode_json('[true, false]')
    is_deeply_ok(array, [true, false], 'decode [true, false]')
    value = decode_json('true')
    is_ok(value, Pyjo.JSON.true, 'decode true')
    value = decode_json('false')
    is_ok(value, Pyjo.JSON.false, 'decode false')
    value = decode_json('null')
    is_ok(value, None, 'decode null')

with subtest('Decode string'):
    array = decode_json('[" "]')
    is_deeply_ok(array, [' '], 'decode [" "]')
    array = decode_json('["hello world!"]')
    is_deeply_ok(array, ['hello world!'], 'decode ["hello world!"]')
    array = decode_json(r'["hello\nworld!"]')
    is_deeply_ok(array, ['hello\nworld!'], r'decode ["hello\nworld!"]')
    array = decode_json(r'["hello\t\"world!"]')
    is_deeply_ok(array, ['hello\t"world!'], r'decode ["hello\t\"world!"]')
    array = decode_json(r'["hello\u0152world\u0152!"]')
    is_deeply_ok(array, ['hello\u0152world\u0152!'], r'decode ["hello\u0152world\u0152!"]')
    array = decode_json('["0."]')
    is_deeply_ok(array, ['0.'], 'decode ["0."]')
    array = decode_json('[" 0"]')
    is_deeply_ok(array, [' 0'], 'decode [" 0"]')
    array = decode_json('["1"]')
    is_deeply_ok(array, ['1'], 'decode ["1"]')
    array = decode_json(r'["\u0007\b\/\f\r"]')
    is_deeply_ok(array, ['\a\b/\f\r'], r'decode ["\u0007\b\/\f\r"]')
    value = decode_json('""')
    is_ok(value, '', 'decode ""')
    value = decode_json(r'"hell\no"')
    is_ok(value, 'hell\no', r'decode "hell\no"')

with subtest('Decode object'):
    hash = decode_json('{}')
    is_deeply_ok(hash, {}, 'decode {}')
    hash = decode_json('{"foo": "bar"}')
    is_deeply_ok(hash, {'foo': 'bar'}, 'decode {"foo": "bar"}')
    hash = decode_json('{"foo": [23, "bar"]}')
    is_deeply_ok(hash, {'foo': [23, 'bar']}, 'decode {"foo": [23, "bar"]}')

with subtest('Decode full spec example'):
    hash = decode_json("""{
   "Image": {
       "Width":  800,
       "Height": 600,
       "Title":  "View from 15th Floor",
       "Thumbnail": {
           "Url":    "http://www.example.com/image/481989943",
           "Height": 125,
           "Width":  "100"
       },
       "IDs": [116, 943, 234, 38793]
    }
}
""")
    is_ok(hash['Image']['Width'], 800, 'right value')
    is_ok(hash['Image']['Height'], 600, 'right value')
    is_ok(hash['Image']['Title'], 'View from 15th Floor', 'right value')
    is_ok(hash['Image']['Thumbnail']['Url'], 'http://www.example.com/image/481989943', 'right value')
    is_ok(hash['Image']['Thumbnail']['Height'], 125, 'right value')
    is_ok(hash['Image']['Thumbnail']['Width'], '100', 'right value')
    is_ok(hash['Image']['IDs'][0], 116, 'right value')
    is_ok(hash['Image']['IDs'][1], 943, 'right value')
    is_ok(hash['Image']['IDs'][2], 234, 'right value')
    is_ok(hash['Image']['IDs'][3], 38793, 'right value')

with subtest('Encode array'):
    data = encode_json([])
    is_ok(data, b'[]', 'encode []')
    data = encode_json([[]])
    is_ok(data, b'[[]]', 'encode [[]]')
    data = encode_json([[], []])
    is_ok(data, b'[[],[]]', 'encode [[], []]')
    data = encode_json([[], [[]], []])
    is_ok(data, b'[[],[[]],[]]', 'encode [[], [[]], []]')

with subtest('Encode string'):
    data = encode_json(['foo'])
    is_ok(data, b'["foo"]', "encode ['foo']")
    data = encode_json(['hello\nworld!'])
    is_ok(data, rb'["hello\nworld!"]', r"encode ['hello\nworld!']")
    data = encode_json(['hello\t"world!'])
    is_ok(data, rb'["hello\t\"world!"]', r"""encode ['hello\t"world!']""")
    data = encode_json(['hello\x03\u0152world\u0152!'])
    is_ok(
        data.decode('UTF-8'),
        '["hello\\u0003\u0152world\u0152!"]',
        r"encode ['hello\x03\u0152world\u0152!']",
    )
    data = encode_json(['123abc'])
    is_ok(data, b'["123abc"]', "encode ['123abc']")
    data = encode_json(['\x00\x1f \a\b/\f\r'])
    is_ok(data, rb'["\u0000\u001F \u0007\b\/\f\r"]', r"encode ['\x00\x1f \a\b/\f\r']")
    data = encode_json('')
    is_ok(data, b'""', "encode ''")
    data = encode_json('hell\no')
    is_ok(data, rb'"hell\no"', r"encode 'hell\no'")

with subtest('Encode object'):
    data = encode_json({})
    is_ok(data, b'{}', 'encode {}')
    data = encode_json({'foo': {}})
    is_ok(data, b'{"foo":{}}', "encode {'foo': {}}")
    data = encode_json({'foo': 'bar'})
    is_ok(data, b'{"foo":"bar"}', "encode {'foo': 'bar'}")
    data = encode_json({'foo': []})
    is_ok(data, b'{"foo":[]}', "encode {'foo': []}")
    data = encode_json({'foo': ['bar']})
    is_ok(data, b'{"foo":["bar"]}', "encode {'foo': ['bar']}")
    # Unlike Mojolicious: the keys in the order of the dict, which Mojo sorts, as a hash of Perl has no order
    data = encode_json({'foo': 'bar', 'baz': 'yada'}, sort_keys=True)
    is_ok(data, b'{"baz":"yada","foo":"bar"}', "encode {'foo': 'bar', 'baz': 'yada'}")
    # Not in Mojolicious: the order of the dict
    data = encode_json({'foo': 'bar', 'baz': 'yada'})
    is_ok(data, b'{"foo":"bar","baz":"yada"}', "encode {'foo': 'bar', 'baz': 'yada'} in order")
    data = encode_json({'foo': {'b': 1, 'a': 2}, 'bar': [{'d': 3, 'c': 4}]}, sort_keys=True)
    is_ok(data, b'{"bar":[{"c":4,"d":3}],"foo":{"a":2,"b":1}}', 'encode nested objects with the keys sorted')
    data = encode_json({'foo': {'b': 1, 'a': 2}, 'bar': [{'d': 3, 'c': 4}]})
    is_ok(data, b'{"foo":{"b":1,"a":2},"bar":[{"d":3,"c":4}]}', 'encode nested objects in order')

with subtest('Encode name'):
    data = encode_json([Pyjo.JSON.true])
    is_ok(data, b'[true]', 'encode [Pyjo.JSON.true]')
    data = encode_json([None])
    is_ok(data, b'[null]', 'encode [None]')
    data = encode_json([Pyjo.JSON.true, Pyjo.JSON.false])
    is_ok(data, b'[true,false]', 'encode [Pyjo.JSON.true, Pyjo.JSON.false]')
    data = encode_json(Pyjo.JSON.true)
    is_ok(data, b'true', 'encode Pyjo.JSON.true')
    data = encode_json(Pyjo.JSON.false)
    is_ok(data, b'false', 'encode Pyjo.JSON.false')
    data = encode_json(None)
    is_ok(data, b'null', 'encode None')

with subtest('Encode number'):
    data = encode_json([1])
    is_ok(data, b'[1]', 'encode [1]')
    data = encode_json(['1'])
    is_ok(data, b'["1"]', "encode ['1']")
    data = encode_json(['-122.026020'])
    is_ok(data, b'["-122.026020"]', "encode ['-122.026020']")
    data = encode_json([-122.026020])
    is_ok(data, b'[-122.02602]', 'encode [-122.026020]')
    data = encode_json([1, -2])
    is_ok(data, b'[1,-2]', 'encode [1, -2]')
    data = encode_json(['10e12', [2]])
    is_ok(data, b'["10e12",[2]]', "encode ['10e12', [2]]")
    data = encode_json([10e12, [2]])
    is_ok(data, b'[10000000000000,[2]]', 'encode [10e12, [2]]')
    data = encode_json([37.7668, [20]])
    is_ok(data, b'[37.7668,[20]]', 'encode [37.7668, [20]]')
    data = encode_json(0)
    is_ok(data, b'0', 'encode 0')
    data = encode_json(23.3)
    is_ok(data, b'23.3', 'encode 23.3')

with subtest('Encode boolean'):
    data = encode_json([not not 1])
    is_ok(data, b'[true]', 'encode [not not 1]')
    data = encode_json([not not 0])
    is_ok(data, b'[false]', 'encode [not not 0]')

with subtest('Faihu roundtrip'):
    data = j(['\U00010346'])
    is_ok(data.decode('UTF-8'), '["\U00010346"]', r"encode ['\U00010346']")
    array = j(data)
    is_deeply_ok(array, ['\U00010346'], 'successful roundtrip')

with subtest('Decode faihu surrogate pair'):
    array = decode_json(r'["\ud800\udf46"]')
    is_deeply_ok(array, ['\U00010346'], r'decode ["\ud800\udf46"]')

with subtest('Complicated roundtrips'):
    data = b'{"":""}'
    hash = decode_json(data)
    is_deeply_ok(hash, {'': ''}, 'decode {"":""}')
    is_ok(encode_json(hash), data, 're-encode')
    data = b'[null,false,true,"",0,1]'
    array = decode_json(data)
    is_deeply_ok(array, [None, Pyjo.JSON.false, Pyjo.JSON.true, '', 0, 1], 'decode [null,false,true,"",0,1]')
    is_ok(encode_json(array), data, 're-encode')
    array = [None, 0, 1, '', Pyjo.JSON.true, Pyjo.JSON.false]
    data = encode_json(array)
    ok(data, 'defined value')
    is_deeply_ok(decode_json(data), array, 'successful roundtrip')

with subtest('Real world roundtrip'):
    data = encode_json({'foo': r'c:\progra~1\mozill~1\firefox.exe'})
    is_ok(
        data,
        rb'{"foo":"c:\\progra~1\\mozill~1\\firefox.exe"}',
        r"encode {'foo': 'c:\progra~1\mozill~1\firefox.exe'}",
    )
    hash = decode_json(data)
    is_deeply_ok(hash, {'foo': r'c:\progra~1\mozill~1\firefox.exe'}, 'successful roundtrip')

with subtest('Huge string'):
    data = encode_json(['a' * 32768])
    is_deeply_ok(decode_json(data), ['a' * 32768], 'successful roundtrip')

with subtest('Slash'):
    data = encode_json(['123</script>'])
    # Unlike Mojolicious: "<" is escaped too, where Mojo keeps it
    is_ok(data, rb'["123\u003C\/script>"]', 'escaped slash')
    is_deeply_ok(decode_json(data), ['123</script>'], 'successful roundtrip')
    # Not in Mojolicious: "<!--<script>", which would keep "</script>" from ending an element "script" of HTML
    data = encode_json(['<!--<script>'])
    is_ok(data, rb'["\u003C!--\u003Cscript>"]', 'escaped less-than sign')
    is_deeply_ok(decode_json(data), ['<!--<script>'], 'successful roundtrip')

with subtest('JSON without UTF-8 encoding'):
    is_deeply_ok(from_json('["♥"]'), ['♥'], 'characters decoded')
    is_ok(to_json(['♥']), '["♥"]', 'characters encoded')
    is_deeply_ok(from_json(to_json(['\xe9'])), ['\xe9'], 'successful roundtrip')

with subtest('Blessed reference'):
    data = encode_json([b('test')])
    is_deeply_ok(decode_json(data), ['test'], 'successful roundtrip')

with subtest('Blessed reference with __json__ method'):
    data = encode_json(JSONTest.new())
    is_deeply_ok(decode_json(data), {}, 'successful roundtrip')
    data = encode_json(JSONTest.new(something={'just': 'works'}, **{'else': {'not': 'working'}}))
    is_deeply_ok(decode_json(data), {'just': 'works'}, 'successful roundtrip')

with subtest('Unknown reference'):
    is_deeply_ok(encode_json(lambda: None), b'null', 'unknown reference')

# Left out from Mojolicious: the "Boolean shortcut" subtest, as Python has no
# scalar references, which Mojo encodes as booleans

with subtest('Booleans in different contexts'):
    ok(true, 'true')
    is_ok(true, 1, 'right string value')
    is_ok(true + 0, 1, 'right numeric value')
    ok(not false, 'false')
    is_ok(false, 0, 'right string value')
    is_ok(false + 0, 0, 'right numeric value')

with subtest('Upgraded numbers'):
    num = 3
    string = str(num)
    is_ok(encode_json({'test': [num, string]}), b'{"test":[3,"3"]}', 'upgraded number detected')
    num = 3.21
    string = str(num)
    is_ok(encode_json({'test': [num, string]}), b'{"test":[3.21,"3.21"]}', 'upgraded number detected')
    # Left out from Mojolicious: "0 but true", a Perl string that is a number
    # without a warning, as a Python string is never a number

# Left out from Mojolicious: the "Upgraded string" and "dualvar" subtests, as a
# Python value is either a number or a string, never both

with subtest('Other reference types'):
    is_ok(encode_json([JSONTest2.new()]), b'["works!"]', 'object stringified')
    is_ok(encode_json([JSONTest3.new()]), b'[null]', 'object with no stringification overload')

with subtest('Ensure numbers and strings are not upgraded'):
    mixed = [3, 'three', '3', 0, '0']
    is_ok(encode_json(mixed), b'[3,"three","3",0,"0"]', 'all have been detected correctly')
    is_ok(encode_json(mixed), b'[3,"three","3",0,"0"]', 'all have been detected correctly again')

with subtest('"inf" and "nan"'):
    like_ok(encode_json({'test': float('inf')}), re.compile(rb'^{"test":".*"}$'), 'encode "inf" as string')
    like_ok(encode_json({'test': float('nan')}), re.compile(rb'^{"test":".*"}$'), 'encode "nan" as string')

with subtest('"null"'):
    is_ok(j('null'), None, 'decode null')

with subtest('Errors'):
    throws_ok(lambda: decode_json('test'), re.compile(r'Malformed JSON: Expected string, array, object'), 'right error')
    throws_ok(
        lambda: decode_json('test'), re.compile(r'object, number, boolean or null at line 0, offset 0'), 'right error'
    )
    throws_ok(
        lambda: decode_json(rb'["\ud800"]'),
        re.compile(r'Malformed JSON: Missing low-surrogate at line 1, offset 8'),
        'right error',
    )
    throws_ok(
        lambda: decode_json(rb'["\udf46"]'),
        re.compile(r'Malformed JSON: Missing high-surrogate at line 1, offset 8'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('[[]'), re.compile(r'Malformed JSON: Expected comma or right square bracket'), 'right error'
    )
    throws_ok(lambda: decode_json('[[]'), re.compile(r'bracket while parsing array at line 1, offset 3'), 'right error')
    throws_ok(
        lambda: decode_json('{{}'),
        re.compile(r'Malformed JSON: Expected string while parsing object at line 1, offset 1'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('["foo\x00]'),
        re.compile(r'Malformed JSON: Unexpected character or invalid escape'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('["foo\x00]'), re.compile(r'escape while parsing string at line 1, offset 5'), 'right error'
    )
    throws_ok(
        lambda: decode_json('{"foo":"bar"{'),
        re.compile(r'Malformed JSON: Expected comma or right curly bracket'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('{"foo":"bar"{'),
        re.compile(r'bracket while parsing object at line 1, offset 12'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('{"foo""bar"}'),
        re.compile(r'Malformed JSON: Expected colon while parsing object at line 1, offset 6'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('[[]...'),
        re.compile(r'Malformed JSON: Expected comma or right square bracket'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('[[]...'), re.compile(r'bracket while parsing array at line 1, offset 3'), 'right error'
    )
    throws_ok(
        lambda: decode_json('{{}...'),
        re.compile(r'Malformed JSON: Expected string while parsing object at line 1, offset 1'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('[nan]'),
        re.compile(r'Malformed JSON: Expected string, array, object, number'),
        'right error',
    )
    throws_ok(lambda: decode_json('[nan]'), re.compile(r'number, boolean or null at line 1, offset 1'), 'right error')
    throws_ok(
        lambda: decode_json('["foo]'),
        re.compile(r'Malformed JSON: Unterminated string at line 1, offset 6'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('{"foo":"bar"}lala'),
        re.compile(r'Malformed JSON: Unexpected data at line 1, offset 13'),
        'right error',
    )
    throws_ok(lambda: decode_json(''), re.compile(r'Missing or empty input at offset 0'), 'right error')
    throws_ok(
        lambda: decode_json('["foo",\n"bar"]lala'),
        re.compile(r'Malformed JSON: Unexpected data at line 2, offset 6'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('["foo",\n"bar",\n"bazra"]lalala'),
        re.compile(r'Malformed JSON: Unexpected data at line 3, offset 8'),
        'right error',
    )
    throws_ok(lambda: decode_json('["♥"]'), re.compile(r'Input is not UTF-8 encoded'), 'right error')
    throws_ok(
        lambda: decode_json(encode('Shift_JIS', 'やった')), re.compile(r'Input is not UTF-8 encoded'), 'right error'
    )
    is_ok(j('{'), None, 'syntax error')
    # Left out from Mojolicious: the two errors that name the file of the
    # caller, as croak adds it to the message and Python keeps it in the
    # traceback

with subtest('Maximum nesting level'):
    ok(decode_json('[' * 512 + ']' * 512), 'decode deeply nested array')
    throws_ok(
        lambda: decode_json('[' * 513 + ']' * 513),
        re.compile(r'Malformed JSON: Nesting too deep at line 1, offset 513'),
        'right error',
    )
    ok(decode_json('{"a":' * 512 + '1' + '}' * 512), 'decode deeply nested object')
    throws_ok(
        lambda: decode_json('{"a":' * 513 + '1' + '}' * 513),
        re.compile(r'Malformed JSON: Nesting too deep at line 1, offset 2561'),
        'right error',
    )
    throws_ok(
        lambda: decode_json('[{"a":' * 257 + '1' + '}]' * 257),
        re.compile(r'Malformed JSON: Nesting too deep'),
        'right error',
    )
    ok(decode_json('[' * 512 + ']' * 512), 'decode deeply nested array again')

# Unlike Mojolicious: the bytes of a whole document are UTF-8, UTF-16 or UTF-32, with a byte order mark that is not a
# part of the JSON, as json.loads detects them, where Mojo decodes UTF-8 only
with subtest('Encodings of bytes'):
    for encoding in ('UTF-8-SIG', 'UTF-16', 'UTF-16LE', 'UTF-16BE', 'UTF-32', 'UTF-32LE', 'UTF-32BE'):
        is_deeply_ok(decode_json('{"♥": [1]}'.encode(encoding)), {'♥': [1]}, encoding)
        is_deeply_ok(decode_json(bytearray('"♥"'.encode(encoding))), '♥', f'{encoding} of a bytearray')
    is_deeply_ok(j('{"a":1}'.encode('UTF-16')), {'a': 1}, 'j')
    throws_ok(lambda: decode_json(b'\xff\xfe[\x00]'), re.compile(r'^Input is not UTF-16 encoded'), 'odd UTF-16')
    throws_ok(lambda: decode_json('\ufeff[1]'), re.compile(r'^Input is not UTF-8 encoded'), 'characters of a string')

done_testing()
