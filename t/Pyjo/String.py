import Pyjo.String.Bytes
import Pyjo.String.Unicode

from Pyjo.String.Bytes import b
from Pyjo.String.Unicode import u
from Pyjo.Test import *

import contextlib
import hashlib
import io
import re


# Mojo::ByteStream holds characters or bytes, Pyjo.String.Unicode and
# Pyjo.String.Bytes one of them each: u() is for characters and b() for bytes

with subtest('Tap into method chain'):
    # Unlike Mojolicious: str is immutable, so the callback cannot append to it
    is_ok(u('test').tap(lambda s: s + '1').camelize(), 'Test', 'right result')

with subtest('camelize'):
    is_ok(u('foo_bar_baz').camelize(), 'FooBarBaz', 'right camelized result')

with subtest('decamelize'):
    is_ok(u('FooBarBaz').decamelize(), 'foo_bar_baz', 'right decamelized result')

with subtest('unindent'):
    is_ok(u(' test\n  123\n 456\n').unindent(), 'test\n 123\n456\n', 'right unindented result')

with subtest('b64_encode'):
    is_ok(b(b'foobar$%^&3217').b64_encode(), 'Zm9vYmFyJCVeJjMyMTc=\n', 'right Base64 encoded result')

with subtest('b64_decode'):
    is_ok(b(b'Zm9vYmFyJCVeJjMyMTc=\n').b64_decode(), b'foobar$%^&3217', 'right Base64 decoded result')

# Not in Mojolicious: Base64 for URLs, of bytes and of strings, which chain
with subtest('b64url_encode and b64url_decode'):
    isa_ok(b(b'\xfb\xff\xfe').b64url_encode(), Pyjo.String.Unicode.object, 'string of bytes')
    is_ok(b(b'\xfb\xff\xfe').b64url_encode(), '-__-', 'right Base64 for URLs of bytes')
    is_ok(u('foo bar baz').b64url_encode(), 'Zm9vIGJhciBiYXo', 'right Base64 for URLs of a string')
    isa_ok(u('-__-').b64url_decode(), Pyjo.String.Bytes.object, 'bytes of a string')
    is_ok(u('-__-').b64url_decode(), b'\xfb\xff\xfe', 'right bytes of a string')
    is_ok(b(b'Zm9vIGJhciBiYXo').b64url_decode(), b'foo bar baz', 'right bytes of bytes')
    is_ok(u('foo').b64url_encode().b64url_decode().decode(), 'foo', 'chain')

with subtest('url_escape'):
    is_ok(b(b'business;23').url_escape(), b'business%3B23', 'right URL escaped result')

with subtest('url_unescape'):
    is_ok(
        b(b'foo%C3%9F%C4%80bar%E2%98%BA').url_unescape().decode(),
        'foo\xdfĀbar☺',
        'right URL unescaped result',
    )
    is_ok(
        b(b'foo%C3%9F%C4%80bar%E2%98%BA').url_unescape().decode('UTF-8'),
        'foo\xdfĀbar☺',
        'right URL unescaped result',
    )

with subtest('html_unescape'):
    is_ok(
        u('&#x3c;foo&#x3E;bar&lt;baz&gt;&#x26;&#34;').html_unescape(), '<foo>bar<baz>&"', 'right HTML unescaped result'
    )

with subtest('xml_escape'):
    is_ok(
        u('la<f>\nbar"baz"\'yada\n\'&lt;la').xml_escape(),
        'la&lt;f&gt;\nbar&quot;baz&quot;&#39;yada\n&#39;&amp;lt;la',
        'right XML escaped result',
    )

with subtest('punycode_encode'):
    is_ok(u('bücher').punycode_encode(), 'bcher-kva', 'right punycode encoded result')

with subtest('punycode_decode'):
    is_ok(u('bcher-kva').punycode_decode(), 'bücher', 'right punycode decoded result')

with subtest('quote'):
    is_ok(u('foo; 23 "bar').quote(), '"foo; 23 \\"bar"', 'right quoted result')

with subtest('unquote'):
    is_ok(u('"foo 23 \\"bar"').unquote(), 'foo 23 "bar', 'right unquoted result')

with subtest('trim'):
    is_ok(u(' la la la ').trim(), 'la la la', 'right trimmed result')

with subtest('md5_bytes'):
    is_ok(
        u('foo bar baz ♥').encode().md5_bytes().hex(), 'a740aeb6e066f158cbf19fd92e890d2d', 'right binary md5 checksum'
    )
    is_ok(
        u('foo bar baz ♥').encode('UTF-8').md5_bytes().hex(),
        'a740aeb6e066f158cbf19fd92e890d2d',
        'right binary md5 checksum',
    )

with subtest('md5_sum'):
    is_ok(b(b'foo bar baz').md5_sum(), 'ab07acbb1e496801937adfa772424bf7', 'right md5 checksum')

with subtest('sha1_bytes'):
    is_ok(
        b(b'foo bar baz').sha1_bytes().hex(), 'c7567e8b39e2428e38bf9c9226ac68de4c67dc39', 'right binary sha1 checksum'
    )

with subtest('sha1_sum'):
    is_ok(b(b'foo bar baz').sha1_sum(), 'c7567e8b39e2428e38bf9c9226ac68de4c67dc39', 'right sha1 checksum')

with subtest('hmac_sha1_sum'):
    is_ok(
        b(b'Hi there').hmac_sha1_sum(b'abc1234567890'),
        '5344f37e1948dd3ffb07243a4d9201a227abd6e1',
        'right hmac sha1 checksum',
    )

# Not in Mojolicious: SHA-256 and SHA-512, and their HMAC, of bytes and of strings, which chain
with subtest('sha256 and sha512'):
    sha256 = 'dbd318c1c462aee872f41109a4dfd3048871a03dedd0fe0e757ced57dad6f2d7'
    sha512 = (
        'bce50343a56f01dc7cf2d4c82127be4fff3a83ddb8b783b1a28fb6574637ceb7'
        '1ef594b1f03a8e9b7d754341831292bcad1a3cb8a12fd2ded7a57b1b173b3bf7'
    )
    for string in (b(b'foo bar baz'), u('foo bar baz')):
        name = type(string).__name__
        isa_ok(string.sha256_bytes(), Pyjo.String.Bytes.object, f'binary sha256 of {name}')
        is_ok(string.sha256_bytes().hex(), sha256, f'right binary sha256 checksum of {name}')
        isa_ok(string.sha256_sum(), Pyjo.String.Unicode.object, f'sha256 of {name}')
        is_ok(string.sha256_sum(), sha256, f'right sha256 checksum of {name}')
        is_ok(string.sha512_bytes().hex(), sha512, f'right binary sha512 checksum of {name}')
        is_ok(string.sha512_sum(), sha512, f'right sha512 checksum of {name}')
        is_ok(
            string.hmac_sha256_sum(b'secr3t'),
            'cfd435b7e14cb5ed539ee154ce73ef0edea9ad480d54d2ca8894075b79386471',
            f'right hmac sha256 checksum of {name}',
        )
        is_ok(
            string.hmac_sha512_sum('secr3t'),
            'd36109e634778df63a9aea191ab5cbe260c1eed5c0ad946b02380dab74d42df3'
            '35154654619b608e2eac85f0f7a227d93e0be66f512c8b768a80fd71b87e015e',
            f'right hmac sha512 checksum of {name}',
        )
    is_ok(b(b'foo').sha256_bytes().sha256_sum(), hashlib.sha256(hashlib.sha256(b'foo').digest()).hexdigest(), 'chain')

with subtest('secure_compare'):
    ok(u('hello').secure_compare('hello'), 'values are equal')
    ok(not u('hell').secure_compare('hello'), 'values are not equal')

with subtest('xor_encode'):
    is_ok(b(b'hello').xor_encode(b'foo'), b'\x0e\x0a\x03\x0a\x00', 'right result')
    is_ok(b(b'\x0e\x0a\x03\x0a\x00').xor_encode(b'foo'), b'hello', 'right result')

with subtest('Nested bytestreams'):
    stream = u(u('test'))
    ok(type(stream.to_str()) is str, 'nested bytestream stringified')
    stream = Pyjo.String.Unicode.new(Pyjo.String.Unicode.new('test'))
    ok(type(stream.to_str()) is str, 'nested bytestream stringified')

with subtest('split'):
    stream = u('1,2,3,4,5')
    is_deeply_ok(stream.split(',').to_list(), ['1', '2', '3', '4', '5'], 'right elements')
    is_deeply_ok(stream.split(re.compile(r',')).to_list(), ['1', '2', '3', '4', '5'], 'right elements')
    is_deeply_ok(u('1,2,3,4,5,,,').split(',').to_list(), ['1', '2', '3', '4', '5'], 'right elements')
    is_deeply_ok(u('1,2,3,4,5,,,').split(',', -1).to_list(), ['1', '2', '3', '4', '5', '', '', ''], 'right elements')
    is_deeply_ok(u('54321').split('').to_list(), ['5', '4', '3', '2', '1'], 'right elements')
    is_deeply_ok(u('').split('').to_list(), [], 'no elements')
    is_deeply_ok(u('').split(',').to_list(), [], 'no elements')
    is_deeply_ok(u('').split(re.compile(r',')).to_list(), [], 'no elements')
    stream = u('1/2/3')
    is_ok(stream.split('/').map(lambda s: s.quote()).join(', '), '"1", "2", "3"', 'right result')
    is_ok(stream.split('/').map(lambda s: s.quote()).join(', '), '"1", "2", "3"', 'right result')

with subtest('length'):
    is_ok(u('foo bar baz').size, 11, 'size is 11')

with subtest('"0"'):
    stream = u('0')
    is_ok(stream.size, 1, 'size is 1')
    is_ok(stream.to_str(), '0', 'right content')

with subtest('clone'):
    stream = u('foo')
    clone = stream.clone()
    # Unlike Mojolicious: str is immutable, so the original does not change
    isnt_ok(stream.b64_encode().to_str(), 'foo', 'original changed')
    is_ok(clone.to_str(), 'foo', 'clone did not change')

with subtest('say and autojoin'):
    handle = io.StringIO()
    u('te', 'st').say(handle)
    with contextlib.redirect_stdout(handle):
        u(1, 2, 3).say().quote().say()
    is_ok(handle.getvalue(), 'test\n123\n"123"\n', 'right output')

with subtest('term_escape'):
    is_ok(u('\t\b\r\n\f').term_escape(), '\\x09\\x08\\x0d\n\\x0c', 'right result')

with subtest('slugify'):
    is_ok(
        u("Un \xe9l\xe9phant \xe0 l'or\xe9e du bois").slugify().to_str(), 'un-elephant-a-loree-du-bois', 'right result'
    )
    is_ok(
        u("Un \xe9l\xe9phant \xe0 l'or\xe9e du bois").slugify(True).to_str(),
        'un-\xe9l\xe9phant-\xe0-lor\xe9e-du-bois',
        'right result',
    )

with subtest('gzip/gunzip'):
    uncompressed = b(b'a' * 1000)
    compressed = uncompressed.clone().gzip()
    isnt_ok(compressed.to_str(), uncompressed.to_str(), 'bytestream changed')
    ok(compressed.size < uncompressed.size, 'bytestream is shorter')
    is_ok(compressed.gunzip().to_str(), uncompressed.to_str(), 'same bytestream')

with subtest('humanize_bytes'):
    is_ok(u(8007188480).humanize_bytes(), '7.5GiB', 'humanized')
    is_ok(u(-8007188480).humanize_bytes(), '-7.5GiB', 'humanized')

done_testing()
