"""
Pyjo.Util test
==============
::

    extract_usage test!
"""

from Pyjo.File import tempdir
from Pyjo.String.Bytes import b
from Pyjo.String.HTML import html
from Pyjo.String.Unicode import u
from Pyjo.Test import *
from Pyjo.Util import (
    b64_decode,
    b64_encode,
    b64url_decode,
    b64url_encode,
    camelize,
    class_to_file,
    class_to_path,
    decamelize,
    decode,
    die,
    dumper,
    encode,
    extract_usage,
    generate_secret,
    getenv,
    getopt,
    gunzip,
    gzip,
    header_params,
    hmac_sha1_bytes,
    hmac_sha1_sum,
    hmac_sha256_bytes,
    hmac_sha256_sum,
    hmac_sha512_bytes,
    hmac_sha512_sum,
    html_attr_unescape,
    html_unescape,
    humanize_bytes,
    isalive,
    md5_bytes,
    md5_sum,
    monkey_patch,
    network_contains,
    notnone,
    punycode_decode,
    punycode_encode,
    quote,
    random_bytes,
    scope_guard,
    secure_compare,
    setenv,
    sha1_bytes,
    sha1_sum,
    sha256_bytes,
    sha256_sum,
    sha512_bytes,
    sha512_sum,
    slugify,
    slurp,
    split_cookie_header,
    split_header,
    spurt,
    steady_time,
    tablify,
    term_escape,
    trim,
    unindent,
    unquote,
    url_escape,
    url_unescape,
    warn,
    xml_escape,
    xor_encode,
)

import contextlib
import gc
import importlib
import io
import os
import pathlib
import re
import sys
import tempfile
import textwrap
import traceback
import types
import warnings
import weakref


# The module of t/mojo/lib/Mojo/DeprecationTest.pm
lib = tempfile.TemporaryDirectory()
with open(os.path.join(lib.name, 'DeprecationTest.py'), 'w') as f:
    f.write(
        textwrap.dedent("""
            from Pyjo.Util import deprecated


            def foo():
                deprecated('foo is DEPRECATED')
                return 'bar'
        """)
    )
sys.path.insert(0, lib.name)
DeprecationTest = importlib.import_module('DeprecationTest')

# Pyjo.Util is brought to Mojolicious 9.49 one function at a time, so only the
# subtests of t/mojo/util.t for those functions are here

with subtest('camelize'):
    is_ok(camelize('foo_bar_baz'), 'FooBarBaz', 'right camelized result')
    is_ok(camelize('FooBarBaz'), 'FooBarBaz', 'right camelized result')
    is_ok(camelize('foo_b_b'), 'FooBB', 'right camelized result')
    is_ok(camelize('foo-b_b'), 'Foo::BB', 'right camelized result')
    is_ok(camelize('FooBar'), 'FooBar', 'already camelized')
    is_ok(camelize('Foo::Bar'), 'Foo::Bar', 'already camelized')

with subtest('decamelize'):
    is_ok(decamelize('FooBarBaz'), 'foo_bar_baz', 'right decamelized result')
    is_ok(decamelize('foo_bar_baz'), 'foo_bar_baz', 'right decamelized result')
    is_ok(decamelize('FooBB'), 'foo_b_b', 'right decamelized result')
    is_ok(decamelize('Foo::BB'), 'foo-b_b', 'right decamelized result')

with subtest('class_to_file'):
    is_ok(class_to_file('Foo.Bar'), 'foo_bar', 'right file')
    is_ok(class_to_file('FooBar'), 'foo_bar', 'right file')
    is_ok(class_to_file('FOOBar'), 'foobar', 'right file')
    is_ok(class_to_file('FOOBAR'), 'foobar', 'right file')
    is_ok(class_to_file('FOO.Bar'), 'foobar', 'right file')
    is_ok(class_to_file('FooBAR'), 'foo_bar', 'right file')
    is_ok(class_to_file('Foo.BAR'), 'foo_bar', 'right file')
    # Left out from Mojolicious: the deprecated package separator "'", which Python has never had

with subtest('class_to_path'):
    is_ok(class_to_path('Foo.Bar'), 'Foo/Bar.py', 'right path')
    # Left out from Mojolicious: the deprecated package separator "'", which Python has never had
    is_ok(class_to_path('Foo.Bar.Baz'), 'Foo/Bar/Baz.py', 'right path')
    # Left out from Mojolicious: the deprecated package separator "'", which Python has never had

with subtest('split_header'):
    is_deeply_ok(split_header(''), [], 'right result')
    is_deeply_ok(split_header('foo=b=a=r'), [[('foo', 'b=a=r')]], 'right result')
    is_deeply_ok(
        split_header('a=b ,, , c=d ;; ; e=f g h=i'),
        [[('a', 'b')], [('c', 'd'), ('e', 'f'), ('g', None), ('h', 'i')]],
        'right result',
    )
    is_deeply_ok(split_header(',,foo,, ,bar'), [[('foo', None)], [('bar', None)]], 'right result')
    is_deeply_ok(split_header(';;foo; ; ;bar'), [[('foo', None), ('bar', None)]], 'right result')
    is_deeply_ok(split_header('foo=;bar=""'), [[('foo', ''), ('bar', '')]], 'right result')
    is_deeply_ok(split_header('foo=bar baz=yada'), [[('foo', 'bar'), ('baz', 'yada')]], 'right result')
    is_deeply_ok(split_header('foo,bar,baz'), [[('foo', None)], [('bar', None)], [('baz', None)]], 'right result')
    is_deeply_ok(
        split_header('f "o" o , ba  r'),
        [[('f', None), ('"o"', None), ('o', None)], [('ba', None), ('r', None)]],
        'right result',
    )
    is_deeply_ok(split_header(r'foo="b,; a\" r\"\\"'), [[('foo', 'b,; a" r"\\')]], 'right result')
    is_deeply_ok(
        split_header(r'foo = "b a\" r\"\\"; bar="ba z"'), [[('foo', 'b a" r"\\'), ('bar', 'ba z')]], 'right result'
    )
    header = '</foo/bar>; rel="x"; t*=UTF-8\'de\'a%20b'
    tree = [[('</foo/bar>', None), ('rel', 'x'), ('t*', "UTF-8'de'a%20b")]]
    is_deeply_ok(split_header(header), tree, 'right result')
    header = 'a=b c; A=b.c; D=/E; a-b=3; expires=Thu, 07 Aug 2008 07:07:59 GMT; Ab;'
    tree = [
        [('a', 'b'), ('c', None), ('A', 'b.c'), ('D', '/E'), ('a-b', '3'), ('expires', 'Thu')],
        [('07', None), ('Aug', None), ('2008', None), ('07:07:59', None), ('GMT', None), ('Ab', None)],
    ]
    is_deeply_ok(split_header(header), tree, 'right result')

with subtest('split_cookie_header'):
    is_deeply_ok(split_cookie_header(''), [], 'right result')
    is_deeply_ok(
        split_cookie_header('a=b; expires=Thu, 07 Aug 2008 07:07:59 GMT,c=d'),
        [[('a', 'b'), ('expires', 'Thu, 07 Aug 2008 07:07:59 GMT')], [('c', 'd')]],
        'right result',
    )
    is_deeply_ok(
        split_cookie_header('a=b; expires=Tuesday, 09-Nov-1999 23:12:40 GMT, c=d'),
        [[('a', 'b'), ('expires', 'Tuesday, 09-Nov-1999 23:12:40 GMT')], [('c', 'd')]],
        'right result',
    )
    is_deeply_ok(
        split_cookie_header('a=b; expires=Tuesday, 09-Nov-1999 23:12:40 GMT;, c=d;'),
        [[('a', 'b'), ('expires', 'Tuesday, 09-Nov-1999 23:12:40 GMT')], [('c', 'd')]],
        'right result',
    )
    is_deeply_ok(
        split_cookie_header('a=b; expires=Sun,06  Nov  1994  08:49:37  UTC; path=/'),
        [[('a', 'b'), ('expires', 'Sun,06  Nov  1994  08:49:37  UTC'), ('path', '/')]],
        'right result',
    )
    is_deeply_ok(
        split_cookie_header('a=b ; expires = Sunday 06 Nov 94 08:49:37UTC ; path=/'),
        [[('a', 'b'), ('expires', 'Sunday 06 Nov 94 08:49:37UTC'), ('path', '/')]],
        'right result',
    )
    header = 'expires=Thu, 07 Aug 2008 07:07:59 GMT, a=b'
    tree = [
        [('expires', 'Thu')],
        [('07', None), ('Aug', None), ('2008', None), ('07:07:59', None), ('GMT', None)],
        [('a', 'b')],
    ]
    is_deeply_ok(split_cookie_header(header), tree, 'right result')

with subtest('header_params'):
    is_deeply_ok(header_params(''), ({}, ''), 'right result')
    is_deeply_ok(header_params('foo=b=a=r'), ({'foo': 'b=a=r'}, ''), 'right result')
    is_deeply_ok(header_params('a=b; c, d=e'), ({'a': 'b'}, ', d=e'), 'right result')
    is_deeply_ok(header_params('a=b; a=c'), ({'a': 'b'}, ''), 'right result')
    is_deeply_ok(header_params('a=b; a="c"'), ({'a': 'b'}, ''), 'right result')
    is_deeply_ok(header_params('a=b; b="c=d"'), ({'a': 'b', 'b': 'c=d'}, ''), 'right result')
    is_deeply_ok(header_params('a=b, c=d'), ({'a': 'b'}, ', c=d'), 'right result')
    is_deeply_ok(
        header_params('rel="x"; t*=UTF-8\'de\'a%20b'), ({'rel': 'x', 't*': "UTF-8'de'a%20b"}, ''), 'right result'
    )

with subtest('extract_usage'):
    is_ok(extract_usage(), 'extract_usage test!\n', 'right result')
    # The script of t/mojo/lib, in a temporary directory, as a test writes nothing into t
    myapp = (
        tempdir()
        .child('myapp.py')
        .spew(b'''\
"""
myapp.py
========
::

    USAGE: myapp.py daemon

     test
    123
"""
''')
    )
    is_ok(extract_usage(myapp.to_str()), 'USAGE: myapp.py daemon\n\n test\n123\n', 'right result')

    # Not in Mojolicious: the usage of a section, as the one of a script in the docstring of its module
    module = (
        tempdir()
        .child('myserver.py')
        .spew(b'''\
"""
myserver
========
::

    server = myserver.new()

myserver-script
---------------
::

    Usage: myserver-script [OPTIONS]

      -h   Help

Text.

Other
-----
::

    Not this
"""
''')
    )
    is_ok(extract_usage(module.to_str()), 'server = myserver.new()\n', 'synopsis')
    is_ok(
        extract_usage(module.to_str(), section='myserver-script'),
        'Usage: myserver-script [OPTIONS]\n\n  -h   Help\n',
        'usage of the section',
    )
    is_ok(extract_usage(module.to_str(), section='Other'), 'Not this\n', 'last section')
    is_ok(extract_usage(module.to_str(), section='Missing'), '', 'no section')

with subtest('getopt'):
    opts = getopt(['--charset', 'UTF-8'], {'c|charset=s': None})
    is_ok(opts.charset, 'UTF-8', 'right string')
    array = ['-t', 'test', '-h', '--whatever', 'Whatever!', 'stuff']
    opts = getopt(array, {'t|test=s': None}, pass_through=True)
    is_ok(opts.test, 'test', 'right string')
    is_deeply_ok(array, ['-h', '--whatever', 'Whatever!', 'stuff'], 'right structure')
    opts = getopt(array, {'h': None, 'w|whatever=s': None})
    ok(opts.h, 'flag has been set')
    is_ok(opts.whatever, 'Whatever!', 'right string')
    is_deeply_ok(array, ['stuff'], 'right structure')
    argv = sys.argv
    try:
        sys.argv = [argv[0], '--charset', 'UTF-16', 'test']
        charset = []
        getopt({'c|charset=s': charset})
        is_deeply_ok(charset, ['UTF-16'], 'right structure')
        is_deeply_ok(sys.argv[1:], ['test'], 'right structure')
    finally:
        sys.argv = argv

with subtest('getopt (return value)'):
    with contextlib.redirect_stderr(io.StringIO()):
        ret = getopt(['--lang', 'de'], {'l|lang=s': None})
        is_ok(ret.lang, 'de', 'right result')
        ok(ret, 'right return value')

        ret = getopt(['--lnag', 'de'], {'l|lang=s': None})
        is_ok(ret.lang, None, 'right result')
        ok(not ret, 'right return value')

        ret = getopt(['--lnag', 'de', '--lang', 'de'], {'l|lang=s': None})
        is_ok(ret.lang, 'de', 'right result')
        ok(not ret, 'right return value')

with subtest('unindent'):
    is_ok(unindent(' test\n  123\n 456\n'), 'test\n 123\n456\n', 'right unindented result')
    is_ok(unindent('\ttest\n\t\t123\n\t456\n'), 'test\n\t123\n456\n', 'right unindented result')
    is_ok(unindent('\t \ttest\n\t \t\t123\n\t \t456\n'), 'test\n\t123\n456\n', 'right unindented result')
    is_ok(unindent('\n\n\n test\n  123\n 456\n'), '\n\n\ntest\n 123\n456\n', 'right unindented result')
    is_ok(unindent('   test\n    123\n   456\n'), 'test\n 123\n456\n', 'right unindented result')
    is_ok(unindent('    test\n  123\n   456\n'), '  test\n123\n 456\n', 'right unindented result')
    is_ok(unindent('test\n123\n'), 'test\n123\n', 'right unindented result')
    is_ok(unindent(' test\n\n 123\n'), 'test\n\n123\n', 'right unindented result')
    is_ok(unindent('  test'), 'test', 'right unindented result')
    is_ok(unindent(' te st\r\n\r\n  1 2 3\r\n 456\r\n'), 'te st\r\n\r\n 1 2 3\r\n456\r\n', 'right unindented result')

with subtest('b64_encode'):
    is_ok(b64_encode(b'foobar$%^&3217'), 'Zm9vYmFyJCVeJjMyMTc=\n', 'right Base64 encoded result')

with subtest('b64_decode'):
    is_ok(b64_decode('Zm9vYmFyJCVeJjMyMTc=\n'), b'foobar$%^&3217', 'right Base64 decoded result')

# Not in Mojolicious: Base64 for URLs
with subtest('b64url_encode'):
    is_ok(b64url_encode(b'foobar$%^&3217'), 'Zm9vYmFyJCVeJjMyMTc', 'without the padding')
    is_ok(b64url_encode(b'\xfb\xff\xfe'), '-__-', 'without + and /')
    is_ok(b64url_encode(b''), '', 'empty')

with subtest('b64url_decode'):
    is_ok(b64url_decode('Zm9vYmFyJCVeJjMyMTc'), b'foobar$%^&3217', 'without the padding')
    is_ok(b64url_decode('Zm9vYmFyJCVeJjMyMTc='), b'foobar$%^&3217', 'with the padding')
    is_ok(b64url_decode(b'-__-'), b'\xfb\xff\xfe', 'with - and _')
    is_ok(b64url_decode('YQ'), b'a', 'one byte')
    data = bytes(range(256))
    is_ok(b64url_decode(b64url_encode(data)), data, 'every byte')

with subtest('b64_encode (UTF-8)'):
    is_ok(
        b64_encode(encode('UTF-8', 'foo\xdfĀbar%23☺')),
        'Zm9vw5/EgGJhciUyM+KYug==\n',
        'right Base64 encoded result',
    )

with subtest('b64_decode (UTF-8)'):
    is_ok(
        decode('UTF-8', b64_decode('Zm9vw5/EgGJhciUyM+KYug==\n')),
        'foo\xdfĀbar%23☺',
        'right Base64 decoded result',
    )

with subtest('b64_encode (custom line ending)'):
    is_ok(b64_encode(b'foobar$%^&3217', ''), 'Zm9vYmFyJCVeJjMyMTc=', 'right Base64 encoded result')

with subtest('decode (invalid UTF-8)'):
    is_ok(decode('UTF-8', 'က'), None, 'decoding invalid UTF-8 worked')

with subtest('decode (invalid encoding)'):
    is_ok(decode('does_not_exist', ''), None, 'decoding with invalid encoding worked')

with subtest('encode (invalid encoding)'):
    throws_ok(lambda: encode('does_not_exist', ''), re.compile(r"Unknown encoding 'does_not_exist'"), 'right error')

with subtest('url_escape'):
    is_ok(url_escape('business;23'), 'business%3B23', 'right URL escaped result')

with subtest('url_escape (custom pattern)'):
    is_ok(url_escape('&business;23', 's&'), '%26bu%73ine%73%73;23', 'right URL escaped result')

with subtest('url_escape (nothing to escape)'):
    is_ok(url_escape('foobar123-._~'), 'foobar123-._~', 'no changes')

with subtest('url_unescape'):
    is_ok(url_unescape('business%3B23'), 'business;23', 'right URL unescaped result')

with subtest('UTF-8 url_escape'):
    is_ok(
        url_escape(encode('UTF-8', 'foo\xdfĀbar☺')),
        b'foo%C3%9F%C4%80bar%E2%98%BA',
        'right URL escaped result',
    )

with subtest('UTF-8 url_unescape'):
    is_ok(
        decode('UTF-8', url_unescape('foo%C3%9F%C4%80bar%E2%98%BA')),
        'foo\xdfĀbar☺',
        'right URL unescaped result',
    )

with subtest('html_unescape'):
    is_ok(html_unescape('&#x3c;foo&#x3E;bar&lt;baz&gt;&#x0026;&#34;'), '<foo>bar<baz>&"', 'right HTML unescaped result')
    is_ok(html_unescape('foo&lt;baz&gt;&#x26;&#34;&OElig;&Foo;'), 'foo<baz>&"Œ&Foo;', 'right HTML unescaped result')

with subtest('html_unescape (special entities)'):
    is_ok(
        html_unescape('foo &#x2603; &CounterClockwiseContourIntegral; bar &sup1baz'),
        'foo ☃ ∳ bar ¹baz',
        'right HTML unescaped result',
    )

with subtest('html_unescape (multi-character entity)'):
    is_ok(html_unescape('&acE;'), '∾̳', 'right HTML unescaped result')

with subtest('html_unescape (invalid code points)'):
    is_ok(html_unescape('&#0;'), '�', 'null character reference')
    is_ok(html_unescape('&#x0;'), '�', 'null character reference')
    is_ok(html_unescape('&#xD800;'), '�', 'leading surrogate')
    is_ok(html_unescape('&#xDBFF;'), '�', 'leading surrogate')
    is_ok(html_unescape('&#xDC00;'), '�', 'trailing surrogate')
    is_ok(html_unescape('&#xDFFF;'), '�', 'trailing surrogate')
    is_ok(html_unescape('&#55296;'), '�', 'surrogate in decimal')
    is_ok(html_unescape('&#1114112;'), '�', 'outside unicode range')
    is_ok(html_unescape('&#9999999;'), '�', 'outside unicode range')
    is_ok(html_unescape('&#xD83D;&#xDE00;'), '��', 'surrogate pairs are not combined')
    is_ok(html_unescape('&#xD7FF;'), '퟿', 'below surrogate range')
    is_ok(html_unescape('&#xE000;'), '', 'above surrogate range')
    is_ok(html_unescape('&#x10FFFF;'), '\U0010ffff', 'noncharacters are preserved')
    is_ok(html_unescape('&#xFFFE;'), '￾', 'noncharacters are preserved')

with subtest('html_unescape (windows-1252 remap)'):
    is_ok(html_unescape('&#x80;'), '€', 'euro sign')
    is_ok(html_unescape('&#128;'), '€', 'euro sign in decimal')
    is_ok(html_unescape('&#0128;'), '€', 'euro sign with leading zero')
    is_ok(html_unescape('&#x93;'), '“', 'left double quotation mark')
    is_ok(html_unescape('&#x99;'), '™', 'trade mark sign')
    is_ok(html_unescape('&#x9F;'), 'Ÿ', 'latin capital letter y with diaeresis')
    is_ok(html_unescape('&#x81;'), '\x81', 'unmapped control is preserved')
    is_ok(html_unescape('&#x9D;'), '\x9d', 'unmapped control is preserved')
    is_ok(html_unescape('&#x7F;'), '\x7f', 'delete is not remapped')
    is_ok(html_unescape('&#xA0;'), '\xa0', 'no-break space is not remapped')

with subtest('html_unescape (apos)'):
    is_ok(html_unescape('foobar&apos;&lt;baz&gt;&#x26;&#34;'), 'foobar\'<baz>&"', 'right HTML unescaped result')

with subtest('html_unescape (nothing to unescape)'):
    is_ok(html_unescape('foobar'), 'foobar', 'no changes')

with subtest('html_unescape (relaxed)'):
    is_ok(html_unescape('&0&Ltf&amp&0oo&nbspba;&ltr'), '&0&Ltf&&0oo\xa0ba;<r', 'right HTML unescaped result')

with subtest('html_attr_unescape'):
    is_ok(html_attr_unescape('/?foo&lt=bar'), '/?foo&lt=bar', 'right HTML unescaped result')
    is_ok(html_attr_unescape('/?f&ltoo=bar'), '/?f&ltoo=bar', 'right HTML unescaped result')
    is_ok(html_attr_unescape('/?f&lt-oo=bar'), '/?f<-oo=bar', 'right HTML unescaped result')
    is_ok(html_attr_unescape('/?foo=&lt'), '/?foo=<', 'right HTML unescaped result')
    is_ok(html_attr_unescape('/?f&lt;oo=bar'), '/?f<oo=bar', 'right HTML unescaped result')

with subtest('url_unescape (bengal numbers with nothing to unescape)'):
    is_ok(html_unescape('&#০৩৯;&#x০৩৯;'), '&#০৩৯;&#x০৩৯;', 'no changes')

with subtest('xml_escape'):
    is_ok(
        xml_escape('la<f>\nbar"baz"\'yada\n\'&lt;la'),
        'la&lt;f&gt;\nbar&quot;baz&quot;&#39;yada\n&#39;&amp;lt;la',
        'right XML escaped result',
    )
    is_ok(xml_escape('привет<foo>'), 'привет&lt;foo&gt;', 'right XML escaped result')

with subtest('xml_escape (nothing to escape)'):
    is_ok(xml_escape('привет'), 'привет', 'no changes')

with subtest('xml_escape (XSS)'):
    is_ok(xml_escape('<p>'), '&lt;p&gt;', 'right XSS escaped result')
    # Unlike Mojolicious: markup is Pyjo.String.HTML, not every Pyjo.String.Unicode, as Mojo::ByteStream is
    is_ok(xml_escape(html('<p>')), '<p>', 'right XSS escaped result')
    is_ok(xml_escape(u('<p>')), '&lt;p&gt;', 'right XSS escaped result')

with subtest('punycode_encode'):
    is_ok(punycode_encode('bücher'), 'bcher-kva', 'right punycode encoded result')

with subtest('punycode_decode'):
    is_ok(punycode_decode('bcher-kva'), 'bücher', 'right punycode decoded result')

with subtest('punycode_decode/punycode_encode roundtrip'):
    is_ok(punycode_decode(punycode_encode('☃⭐️ ')), '☃⭐️ ', 'right punycode roundtrip result')
    is_ok(punycode_decode(punycode_encode('🐳')), '🐳', 'right punycode roundtrip result')

with subtest('RFC 3492'):
    tests = [
        '(A) Arabic (Egyptian):',
        'ليهمابتكلموشعربي؟',
        'egbpdaj6bu4bxfgehfvwxn',
        '(B) Chinese (simplified):',
        '他们为什么不说中文',
        'ihqwcrb4cv8a8dqg056pqjye',
        '(C) Chinese (traditional):',
        '他們爲什麽不說中文',
        'ihqwctvzc91f659drss3x8bo0yb',
        '(D) Czech: Pro<ccaron>prost<ecaron>nemluv<iacute><ccaron>esky',
        'Pročprostěnemluvíčesky',
        'Proprostnemluvesky-uyb24dma41a',
        '(E) Hebrew:',
        'למההםפשוטלאמדבריםעברית',
        '4dbcagdahymbxekheh6e0a7fei0b',
        '(F) Hindi (Devanagari):',
        'यहलोगहिन्दीक्योंनहींबोलसकतेहैं',
        'i1baa7eci9glrd9b2ae1bj0hfcgg6iyaf8o0a1dig0cd',
        '(G) Japanese (kanji and hiragana):',
        'なぜみんな日本語を話してくれないのか',
        'n8jok5ay5dzabd5bym9f0cm5685rrjetr6pdxa',
        '(H) Korean (Hangul syllables):',
        '세계의모든사람들이한국어를이해한다면얼마나좋을까',
        '989aomsvi5e83db1d2a355cv1e0vak1dwrv93d5xbh15a0dt30a5jpsd879ccm6fea98c',
        '(I) Russian (Cyrillic):',
        'почемужеонинеговорятпорусски',
        'b1abfaaepdrnnbgefbadotcwatmq2g4l',
        '(J) Spanish: Porqu<eacute>nopuedensimplementehablarenEspa<ntilde>ol',
        'PorquénopuedensimplementehablarenEspañol',
        'PorqunopuedensimplementehablarenEspaol-fmd56a',
        '(K) Vietnamese: T<adotbelow>isaoh<odotbelow>kh<ocirc>ngth'
        '<ecirchookabove>ch<ihookabove>n<oacute>iti<ecircacute>ngVi'
        '<ecircdotbelow>t',
        'TạisaohọkhôngthểchỉnóitiếngViệt',
        'TisaohkhngthchnitingVit-kjcr8268qyxafd2f1b9g',
        '(L) 3<nen>B<gumi><kinpachi><sensei>',
        '3年B組金八先生',
        '3B-ww4c5e180e575a65lsy2b',
        '(M) <amuro><namie>-with-SUPER-MONKEYS',
        '安室奈美恵-with-SUPER-MONKEYS',
        '-with-SUPER-MONKEYS-pc58ag80a8qai00g7n9n',
        '(N) Hello-Another-Way-<sorezore><no><basho>',
        'Hello-Another-Way-それぞれの場所',
        'Hello-Another-Way--fc4qua05auwb3674vfr0b',
        '(O) <hitotsu><yane><no><shita>2',
        'ひとつ屋根の下2',
        '2-u9tlzr9756bt3uc0v',
        '(P) Maji<de>Koi<suru>5<byou><mae>',
        'MajiでKoiする5秒前',
        'MajiKoi5-783gue6qz075azm5e',
        '(Q) <pafii>de<runba>',
        'パフィーdeルンバ',
        'de-jg4avhby1noc0d',
        '(R) <sono><supiido><de>',
        'そのスピードで',
        'd9juau41awczczp',
        '(S) -> $1.00 <-',
        '-> $1.00 <-',
        '-> $1.00 <--',
    ]

    for i in range(0, len(tests), 3):
        d, o, p = tests[i], tests[i + 1], tests[i + 2]
        is_ok(punycode_encode(o), p, f'punycode_encode {d}')
        is_ok(punycode_decode(p), o, f'punycode_decode {d}')

with subtest('quote'):
    is_ok(quote('foo; 23 "bar'), '"foo; 23 \\"bar"', 'right quoted result')
    is_ok(quote('"foo; 23 "bar"'), '"\\"foo; 23 \\"bar\\""', 'right quoted result')

with subtest('unquote'):
    is_ok(unquote('"foo 23 \\"bar"'), 'foo 23 "bar', 'right unquoted result')
    is_ok(unquote('"\\"foo 23 \\"bar\\""'), '"foo 23 "bar"', 'right unquoted result')

with subtest('trim'):
    is_ok(trim(' la la  la '), 'la la  la', 'right trimmed result')
    is_ok(trim(' \n la la la \n '), 'la la la', 'right trimmed result')
    is_ok(trim('\n la\nla la \n'), 'la\nla la', 'right trimmed result')
    is_ok(trim(' \nla \n  \t\nla\nla\n '), 'la \n  \t\nla\nla', 'right trimmed result')

with subtest('md5_bytes'):
    is_ok(
        md5_bytes(encode('UTF-8', 'foo bar baz ♥')).hex(),
        'a740aeb6e066f158cbf19fd92e890d2d',
        'right binary md5 checksum',
    )

with subtest('md5_sum'):
    is_ok(md5_sum(b'foo bar baz'), 'ab07acbb1e496801937adfa772424bf7', 'right md5 checksum')

with subtest('sha1_bytes'):
    is_ok(sha1_bytes(b'foo bar baz').hex(), 'c7567e8b39e2428e38bf9c9226ac68de4c67dc39', 'right binary sha1 checksum')

with subtest('sha1_sum'):
    is_ok(sha1_sum(b'foo bar baz'), 'c7567e8b39e2428e38bf9c9226ac68de4c67dc39', 'right sha1 checksum')

with subtest('hmac_sha1_sum'):
    is_ok(
        hmac_sha1_sum(b'Hi there', b'abc1234567890'),
        '5344f37e1948dd3ffb07243a4d9201a227abd6e1',
        'right hmac sha1 checksum',
    )

# Not in Mojolicious: SHA-256 and SHA-512, and their HMAC with the test case 2 of RFC 4231
RFC4231 = (b'what do ya want for nothing?', b'Jefe')
SHA512 = (
    'bce50343a56f01dc7cf2d4c82127be4fff3a83ddb8b783b1a28fb6574637ceb7'
    '1ef594b1f03a8e9b7d754341831292bcad1a3cb8a12fd2ded7a57b1b173b3bf7'
)

with subtest('sha256_bytes'):
    is_ok(
        sha256_bytes(b'foo bar baz').hex(),
        'dbd318c1c462aee872f41109a4dfd3048871a03dedd0fe0e757ced57dad6f2d7',
        'right binary sha256 checksum',
    )

with subtest('sha256_sum'):
    is_ok(
        sha256_sum(b'foo bar baz'),
        'dbd318c1c462aee872f41109a4dfd3048871a03dedd0fe0e757ced57dad6f2d7',
        'right sha256 checksum',
    )

with subtest('sha512_bytes'):
    is_ok(sha512_bytes(b'foo bar baz').hex(), SHA512, 'right binary sha512 checksum')

with subtest('sha512_sum'):
    is_ok(sha512_sum(b'foo bar baz'), SHA512, 'right sha512 checksum')

with subtest('hmac_sha256_sum'):
    is_ok(
        hmac_sha256_sum(*RFC4231),
        '5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843',
        'right hmac sha256 checksum',
    )

with subtest('hmac_sha512_sum'):
    is_ok(
        hmac_sha512_sum(*RFC4231),
        '164b7a7bfcf819e2e395fbe73b56e0a387bd64222e831fd610270cd7ea250554'
        '9758bf75c05a994a6d034f65f8f0e6fdcaeab1a34d4a6b4b636e070a38bce737',
        'right hmac sha512 checksum',
    )

# Not in Mojolicious: the binary HMAC, the bytes of the checksums, and a key derived in steps, as the signing key of the
# example of Signature Version 4 of AWS
with subtest('hmac_sha1_bytes, hmac_sha256_bytes and hmac_sha512_bytes'):
    for binary, checksum in (
        (hmac_sha1_bytes, hmac_sha1_sum),
        (hmac_sha256_bytes, hmac_sha256_sum),
        (hmac_sha512_bytes, hmac_sha512_sum),
    ):
        isa_ok(binary(*RFC4231), bytes, f'{binary.__name__} gives bytes')
        is_ok(binary(*RFC4231), bytes.fromhex(checksum(*RFC4231)), f'right {binary.__name__}')
    key = b'AWS4wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY'
    for step in (b'20150830', b'us-east-1', b'iam', b'aws4_request'):
        key = hmac_sha256_bytes(step, key)
    is_ok(key.hex(), 'c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9', 'key derived in steps')

with subtest('secure_compare'):
    ok(secure_compare('hello', 'hello'), 'values are equal')
    ok(not secure_compare('hell', 'hello'), 'values are not equal')
    ok(not secure_compare('hallo', 'hello'), 'values are not equal')
    ok(secure_compare('0', '0'), 'values are equal')
    ok(secure_compare('1', '1'), 'values are equal')
    ok(not secure_compare('1', '0'), 'values are not equal')
    ok(not secure_compare('0', '1'), 'values are not equal')
    ok(secure_compare('00', '00'), 'values are equal')
    ok(secure_compare('11', '11'), 'values are equal')
    ok(not secure_compare('11', '00'), 'values are not equal')
    ok(not secure_compare('00', '11'), 'values are not equal')
    ok(secure_compare('♥', '♥'), 'values are equal')
    ok(secure_compare('0♥', '0♥'), 'values are equal')
    ok(secure_compare('♥1', '♥1'), 'values are equal')
    ok(not secure_compare('♥', '♥0'), 'values are not equal')
    ok(not secure_compare('0♥', '♥'), 'values are not equal')
    ok(not secure_compare('0♥1', '1♥0'), 'values are not equal')
    ok(not secure_compare('', '♥'), 'values are not equal')
    ok(not secure_compare('♥', ''), 'values are not equal')

with subtest('xor_encode'):
    is_ok(xor_encode(b'hello', b'foo'), b'\x0e\x0a\x03\x0a\x00', 'right result')
    is_ok(xor_encode(b'\x0e\x0a\x03\x0a\x00', b'foo'), b'hello', 'right result')
    is_ok(xor_encode(b'hello world', b'x'), b'\x10\x1d\x14\x14\x17\x58\x0f\x17\x0a\x14\x1c', 'right result')
    is_ok(xor_encode(b'\x10\x1d\x14\x14\x17\x58\x0f\x17\x0a\x14\x1c', b'x'), b'hello world', 'right result')
    is_ok(xor_encode(b'hello', b'123456789'), b'\x59\x57\x5f\x58\x5a', 'right result')
    is_ok(xor_encode(b'\x59\x57\x5f\x58\x5a', b'123456789'), b'hello', 'right result')
    is_ok(xor_encode(b'', b'foo'), b'', 'right result')

with subtest('steady_time'):
    like_ok(str(steady_time()), r'^[\d.]+$', 'high resolution time')

with subtest('monkey_patch'):

    class MojoMonkeyTest:
        @staticmethod
        def foo():
            return 'foo'

    ok(hasattr(MojoMonkeyTest, 'foo'), 'function "foo" exists')
    is_ok(MojoMonkeyTest.foo(), 'foo', 'right result')
    ok(not hasattr(MojoMonkeyTest, 'bar'), 'function "bar" does not exist')
    monkey_patch(MojoMonkeyTest, bar=lambda: 'bar')
    ok(hasattr(MojoMonkeyTest, 'bar'), 'function "bar" exists')
    is_ok(MojoMonkeyTest.bar(), 'bar', 'right result')
    monkey_patch(MojoMonkeyTest, foo=lambda: 'baz')
    ok(hasattr(MojoMonkeyTest, 'foo'), 'function "foo" exists')
    is_ok(MojoMonkeyTest.foo(), 'baz', 'right result')
    ok(not hasattr(MojoMonkeyTest, 'yin'), 'function "yin" does not exist')
    ok(not hasattr(MojoMonkeyTest, 'yang'), 'function "yang" does not exist')
    monkey_patch(MojoMonkeyTest, yin=lambda: 'yin', yang=lambda: 'yang')
    ok(hasattr(MojoMonkeyTest, 'yin'), 'function "yin" exists')
    is_ok(MojoMonkeyTest.yin(), 'yin', 'right result')
    ok(hasattr(MojoMonkeyTest, 'yang'), 'function "yang" exists')
    is_ok(MojoMonkeyTest.yang(), 'yang', 'right result')

with subtest('monkey_patch (with name)'):
    is_ok(MojoMonkeyTest.foo.__qualname__, 'MojoMonkeyTest.foo', 'right name')
    is_ok(MojoMonkeyTest.bar.__qualname__, 'MojoMonkeyTest.bar', 'right name')

# Not in Mojolicious: a module, the other target of monkey_patch
with subtest('monkey_patch (module)'):
    module = types.ModuleType('MojoMonkeyModule')
    monkey_patch(module, foo=lambda: 'foo')
    is_ok(module.foo(), 'foo', 'right result')
    is_ok(f'{module.foo.__module__}.{module.foo.__qualname__}', 'MojoMonkeyModule.foo', 'right name')

with subtest('network_contains'):
    ok(not network_contains('10.0.0.0/8', ''), 'empty address')
    ok(not network_contains('', '10.10.10.10'), 'empty network')
    ok(not network_contains('foo', '10.10.10.10'), 'invalid v4 network')
    ok(not network_contains('10.10.10.10', 'foo'), 'invalid v4 address')
    ok(not network_contains('foo:', '::'), 'invalid v6 network')
    ok(not network_contains('::', 'foo:'), 'invalid v6 address')
    ok(not network_contains('::/96', '192.168.0.1'), 'v6 network, v4 address')
    ok(not network_contains('10.10.10.10/32', '::'), 'v4 network, v6 address')

    ok(network_contains('192.168.0.1/33', '192.168.0.1'), 'oversize v4 mask')
    ok(network_contains('::/130', '::'), 'oversize v6 mask')

    ok(network_contains('0.0.0.0/0', '0.0.0.0'), 'v4 network contains addresss')
    ok(network_contains('0.0.0.0/0', '255.255.255.255'), 'v4 network contains addresss')
    ok(network_contains('192.168.0.0/24', '192.168.0.1'), 'v4 network contains addresss')
    ok(network_contains('10.10.10.8/30', '10.10.10.11'), 'v4 network contains addresss')
    ok(network_contains('10.10.10.8/30', '10.10.10.8'), 'v4 network contains addresss')
    ok(network_contains('10.10.10.8/31', '10.10.10.9'), 'v4 network contains addresss')
    ok(network_contains('10.0.0.0/8', '10.255.255.255'), 'v4 network contains addresss')
    ok(network_contains('255.255.255.255/32', '255.255.255.255'), 'v4 network contains addresss')
    ok(network_contains('10.10.10.8/29', '10.10.10.10'), 'v4 network contains addresss')
    ok(network_contains('127.0.0.1', '127.0.0.1'), 'v4 network contains addresss')

    ok(not network_contains('0.0.0.0/32', '0.0.0.1'), 'v4 network does not contain address')
    ok(not network_contains('192.168.1.0/24', '192.168.0.1'), 'v4 network does not contain address')
    ok(not network_contains('10.10.0.8/29', '10.10.10.8'), 'v4 network does not contain address')
    ok(not network_contains('10.10.10.8/29', '10.10.10.7'), 'v4 network does not contain address')
    ok(not network_contains('10.10.10.8/29', '10.10.10.16'), 'v4 network does not contain address')
    ok(not network_contains('10.0.0.0/9', '10.255.255.255'), 'v4 network does not contain address')
    ok(not network_contains('10.10.10.8/29', '10.10.10.19'), 'v4 network does not contain address')
    ok(not network_contains('127.0.0.1', '127.0.0.2'), 'v4 network does not contain address')
    ok(not network_contains('10.0.0.1/8', '10.0.0.2'), 'v4 network does not contain address')

    ok(network_contains('::/128', '::'), 'v6 network contains addresss')
    ok(network_contains('::/0', '::'), 'v6 network contains addresss')
    ok(network_contains('::1', '::1'), 'v6 network contains addresss')
    ok(network_contains('::/0', 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'), 'v6 network contains addresss')
    ok(network_contains('1:2:3:4:5:6:0::/96', '1:2:3:4:5:6:8000:8'), 'v6 network contains addresss')
    ok(network_contains('1:2:3:4:5:6:8000::/112', '1:2:3:4:5:6:8000:F1'), 'v6 network contains addresss')
    ok(network_contains('1:2:3:4:5:6:8000:20/123', '1:2:3:4:5:6:8000:3F'), 'v6 network contains addresss')
    ok(network_contains('ff:ff:ff:ff:ff:ff:8000::/127', 'ff:ff:ff:ff:ff:ff:8000:0'), 'v6 network contains addresss')
    ok(network_contains('ff:ff:ff:ff:ff:ff:8000::/127', 'ff:ff:ff:ff:ff:ff:8000:1'), 'v6 network contains addresss')
    ok(network_contains('::1', '::1'), 'v6 network contains addresss')
    ok(network_contains('::1/128', '::1'), 'v6 network contains addresss')
    ok(network_contains('a0:a0:a0:a0::/64', 'a0:a0:a0:a0:1::1'), 'v6 network contains addresss')
    ok(network_contains('a0::/16', 'a0:b0:a0:a0:1::1'), 'v6 network contains addresss')
    ok(network_contains('a000::/8', 'a0ff:dd0:1234:a0:1::1'), 'v6 network contains addresss')
    ok(network_contains('::ffff:0:0/96', '::ffff:10.10.10.10'), 'v6 network contains addresss')
    ok(network_contains('::ffff:127.0.0.0/120', '::ffff:127.0.0.255'), 'v6 network contains addresss')
    ok(network_contains('::ffff:10.10.10.8/127', '::ffff:10.10.10.9'), 'v6 network contains addresss')

    ok(not network_contains('::1/0', '::'), 'v6 network does not contain address')
    ok(not network_contains('::1', '::2'), 'v6 network does not contain address')
    ok(not network_contains('1::/0', 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'), 'v6 network does not contain address')
    ok(not network_contains('1:2:3:4:5:6:0::/96', '1:2:3:4:5:7:8000:8'), 'v6 network does not contain address')
    ok(not network_contains('1:2:3:4:5:6:8000::/112', '1:2:3:4:5:6:8001:F1'), 'v6 network does not contain address')
    ok(not network_contains('1:2:3:4:5:6:8000:20/123', '1:2:3:4:5:6:8000:40'), 'v6 network does not contain address')
    ok(
        not network_contains('ff:ff:ff:ff:ff:ff:8000::/127', 'ff:ff:ff:ff:ff:ff:8000:4'),
        'v6 network does not contain address',
    )
    ok(
        not network_contains('ff:ff:ff:ff:ff:ff:8000::/127', 'ff:ff:ff:ff:ff:ff:7FFF:0'),
        'v6 network does not contain address',
    )
    ok(not network_contains('::1', '1::1'), 'v6 network does not contain address')
    ok(not network_contains('::1/128', '::11'), 'v6 network does not contain address')
    ok(not network_contains('a0:a0:a0:a0::/64', 'a0:a0:a0:a1:1::1'), 'v6 network does not contain address')
    ok(not network_contains('a0::/16', 'a1:b0:a0:a0:1::1'), 'v6 network does not contain address')
    ok(not network_contains('a000::/8', 'b0ff:dd0:1234:a0:1::1'), 'v6 network does not contain address')
    ok(not network_contains('::ffff:0:0/96', '::fffe:0a0a:0a0a'), 'v6 network does not contain address')
    ok(not network_contains('::ffff:127.0.0.0/120', '::ffff:127.0.1.255'), 'v6 network does not contain address')
    ok(not network_contains('::ffff:10.10.10.8/127', '::ffff:10.10.10.12'), 'v6 network does not contain address')

with subtest('tablify'):
    is_ok(tablify([['f\r\no o\r\n', 'bar']]), 'fo o  bar\n', 'right result')
    is_ok(tablify([['  foo', '  b a r']]), '  foo    b a r\n', 'right result')
    is_ok(tablify([['foo']]), 'foo\n', 'right result')
    is_ok(tablify([['foo', 'yada'], ['yada', 'yada']]), 'foo   yada\nyada  yada\n', 'right result')
    is_ok(tablify([[None, 'yada'], ['yada', None]]), '      yada\nyada  \n', 'right result')
    is_ok(
        tablify([['foo', 'bar', 'baz'], ['yada', 'yada', 'yada']]),
        'foo   bar   baz\nyada  yada  yada\n',
        'right result',
    )
    is_ok(tablify([['a', '', 0], [0, '', 'b']]), 'a    0\n0    b\n', 'right result')
    is_ok(tablify([[1, 2], [3]]), '1  2\n3\n', 'right result')
    is_ok(tablify([[1], [2, 3]]), '1\n2  3\n', 'right result')
    is_ok(tablify([[1], [], [2, 3]]), '1\n\n2  3\n', 'right result')

with subtest('deprecated'):
    warn_, die_ = None, None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            is_ok(DeprecationTest.foo(), 'bar', 'right result')
        except Exception as e:
            die_ = e
    warn_ = f'{caught[0].message} at {caught[0].filename} line {caught[0].lineno}' if caught else None
    like_ok(warn_, r'foo is DEPRECATED at .*Util\.py line \d+', 'right warning')
    ok(not die_, 'no exception')
    warn_, die_ = None, None
    setenv('PYJO_FATAL_DEPRECATIONS', '1')
    result = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            result = DeprecationTest.foo()
        except DeprecationWarning as e:
            frame = traceback.extract_tb(e.__traceback__)[0]
            die_ = f'{e} at {frame.filename} line {frame.lineno}'
    setenv('PYJO_FATAL_DEPRECATIONS', None)
    ok(not result, 'no result')
    ok(not caught, 'no warning')
    like_ok(die_, r'foo is DEPRECATED at .*Util\.py line \d+', 'right exception')

with subtest('dumper'):
    is_ok(dumper([1, 2]), '[1, 2]\n', 'right result')

with subtest('term_escape'):
    is_ok(term_escape('Accept: */*\x0d\x0a'), 'Accept: */*\\x0d\x0a', 'right result')
    is_ok(term_escape('\t\b\r\n\f'), '\\x09\\x08\\x0d\n\\x0c', 'right result')
    is_ok(term_escape('\x00\x09\x0b\x1f\x7f\x80\x9f'), r'\x00\x09\x0b\x1f\x7f\x80\x9f', 'right result')

with subtest('slugify'):
    is_ok(slugify('a & b'), 'a-b', 'right result')
    is_ok(slugify('a &amp; b'), 'a-amp-b', 'right result')
    is_ok(slugify(123), '123', 'right result')
    is_ok(
        slugify(' Jack & Jill like numbers 1,2,3 and 4 and silly characters ?%.$!/'),
        'jack-jill-like-numbers-123-and-4-and-silly-characters',
        'right result',
    )
    is_ok(slugify("Un \xe9l\xe9phant \xe0 l'or\xe9e du bois"), 'un-elephant-a-loree-du-bois', 'right result')
    is_ok(
        slugify("Un \xe9l\xe9phant \xe0 l'or\xe9e du bois", True),
        'un-\xe9l\xe9phant-\xe0-lor\xe9e-du-bois',
        'right result',
    )
    is_ok(slugify('Hello, World!'), 'hello-world', 'right result')
    is_ok(slugify('spam & eggs'), 'spam-eggs', 'right result')
    is_ok(slugify('spam & ıçüş', True), 'spam-ıçüş', 'right result')
    is_ok(slugify('foo ıç bar', True), 'foo-ıç-bar', 'right result')
    is_ok(slugify('    foo ıç bar', True), 'foo-ıç-bar', 'right result')
    is_ok(slugify('你好', True), '你好', 'right result')

with subtest('gzip/gunzip'):
    uncompressed = b'a' * 1000
    compressed = gzip(uncompressed)
    isnt_ok(compressed, uncompressed, 'string changed')
    ok(len(compressed) < len(uncompressed), 'string is shorter')
    result = gunzip(compressed)
    is_ok(result, uncompressed, 'same string')
    is_ok(gunzip(gzip(b(uncompressed))), uncompressed, 'same string')

with subtest('scope_guard'):
    test = ['a']
    with scope_guard(lambda: test.append('c')):
        test.append('b')
    test.append('d')
    is_ok(''.join(test), 'abcd', 'right order')

with subtest('humanize_bytes'):
    is_ok(humanize_bytes(0), '0B', 'zero Bytes')
    is_ok(humanize_bytes(1), '1B', 'one Byte')
    is_ok(humanize_bytes(-1023), '-1023B', 'negative Bytes')
    is_ok(humanize_bytes(1024), '1KiB', 'one KiB')
    is_ok(humanize_bytes(1025), '1KiB', 'one KiB')
    is_ok(humanize_bytes(1024 * 1024), '1MiB', 'one MiB')
    is_ok(humanize_bytes(1024 * 1024 * 1024), '1GiB', 'one GiB')
    is_ok(humanize_bytes(1024 * 1024 * 1024 * 1024), '1TiB', 'one TiB')
    is_ok(humanize_bytes(3000), '2.9KiB', 'almost 3KiB')
    is_ok(humanize_bytes(-3000), '-2.9KiB', 'almost -3KiB')
    is_ok(humanize_bytes(13443399680), '13GiB', 'two digits GiB')
    is_ok(humanize_bytes(8007188480), '7.5GiB', 'smaller GiB')
    is_ok(humanize_bytes(-8007188480), '-7.5GiB', 'negative smaller GiB')
    is_ok(humanize_bytes(-1099511627776), '-1TiB', 'negative smaller TiB')
    is_ok(humanize_bytes(717946880), '685MiB', 'large MiB')
    is_ok(humanize_bytes(-717946880), '-685MiB', 'large negative MiB')
    is_ok(humanize_bytes(245760), '240KiB', 'less than a MiB')

# Left out from Mojolicious: the subtest "encrypt_cookie/decrypt_cookie", as the functions are left out

with subtest('random_bytes'):
    isnt_ok(random_bytes(16), random_bytes(16), 'two random_bytes invocations are not the same')
    is_ok(len(random_bytes(16)), 16, 'random_bytes(16) returns 16 bytes')

with subtest('generate_secret'):
    like_ok(generate_secret(), r'^[A-Za-z0-9_-]{32,}$', 'right format')

# Left out from Mojolicious: the subtest "Hide DATA usage from error messages", as Python has no DATA handle

# Not in Mojolicious: the errors of random_bytes
with subtest('random_bytes (invalid count)'):
    throws_ok(
        lambda: random_bytes(-1), re.compile(r'^Byte count must be a defined, non-negative integer'), 'right error'
    )
    throws_ok(
        lambda: random_bytes(None), re.compile(r'^Byte count must be a defined, non-negative integer'), 'right error'
    )
    is_ok(random_bytes(0), b'', 'no bytes')

# Not in Mojolicious: the helpers that turn statements into expressions
with subtest('die'):
    throws_ok(lambda: die(ValueError('Something went wrong')), ValueError, 'exception raised')
    throws_ok(lambda: die(ValueError('Something went wrong')), 'Something went wrong', 'right message')
    throws_ok(lambda: die('Exit immediately'), SystemExit, 'exit')
    try:
        die('Exit immediately')
    except SystemExit as e:
        is_ok(e.code, 'Exit immediately', 'right message')

with subtest('warn'):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        warn('foo')
        warn('bar\n')
        warn('baz', 23)
    is_ok(stderr.getvalue(), 'foo\nbar\nbaz23\n', 'right output')

with subtest('getenv/setenv'):
    setenv('PYJO_UTIL_TEST', 'foo')
    is_ok(getenv('PYJO_UTIL_TEST'), 'foo', 'right value')
    is_ok(getenv('PYJO_UTIL_TEST', 'bar'), 'foo', 'right value')
    setenv('PYJO_UTIL_TEST', None)
    ok('PYJO_UTIL_TEST' not in os.environ, 'removed')
    is_ok(getenv('PYJO_UTIL_TEST'), None, 'no value')
    is_ok(getenv('PYJO_UTIL_TEST', 'bar'), 'bar', 'default value')
    setenv('PYJO_UTIL_TEST', None)
    ok('PYJO_UTIL_TEST' not in os.environ, 'nothing to remove')

with subtest('slurp/spurt'):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'test.txt')
        is_ok(spurt('zażółć\r\n', path), 12, 'bytes written')
        is_ok(slurp(path), 'zażółć\r\n', 'characters read, line ending kept')
        is_ok(spurt('zażółć', pathlib.Path(path), 'iso-8859-2'), 6, 'bytes written in another charset')
        is_ok(slurp(pathlib.Path(path), 'iso-8859-2'), 'zażółć', 'characters read in another charset')
        throws_ok(lambda: slurp(path), UnicodeDecodeError, 'invalid UTF-8')
        pathlib.Path(path).write_bytes(b'\xff\xfe' + 'zażółć'.encode('utf-16-le'))
        is_ok(slurp(path), 'zażółć', 'characters of UTF-16LE with a byte order mark')
        pathlib.Path(path).write_bytes(b'\xef\xbb\xbfzaz')
        is_ok(slurp(path), 'zaz', 'characters of UTF-8 with a byte order mark')
        is_ok(slurp(path, 'latin-1'), '\xef\xbb\xbfzaz', 'byte order mark of another charset')

with subtest('notnone'):
    is_ok(notnone(None, 0, 1), 0, 'first value that is not None')
    is_ok(notnone(None, lambda: 'default'), 'default', 'callable called')
    is_ok(notnone(None, None), None, 'nothing')
    calls = []
    is_ok(notnone('value', lambda: calls.append(1)), 'value', 'value')
    is_deeply_ok(calls, [], 'callable not called')

with subtest('isalive'):

    class Obj:
        pass

    obj = Obj()
    proxy = weakref.proxy(obj)
    ok(isalive(proxy), 'alive')
    del obj
    gc.collect()
    ok(not isalive(proxy), 'dead')

lib.cleanup()

done_testing()
