import os
import re


# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor of Pyjo.Reactor.detect()
os.environ['PYJO_MODE'] = 'development'
os.environ['PYJO_PROXY'] = '0'

# Not in Mojolicious: the level of the log, which ojo sets when it is loaded, and Pyjo when it runs as python -m Pyjo
os.environ.setdefault('PYJO_LOG_LEVEL', 'fatal')

from Pyjo import *
from Pyjo.Test import *

import contextlib
import io
import subprocess
import sys
import tempfile


ROOT = os.path.join(os.path.dirname(__file__), '..', '..')

with subtest('Application'):
    a('/', lambda c: c.render(data=c.req.method.encode() + c.req.body)).secrets = ['foobarbaz']
    is_ok(a().secrets[0], 'foobarbaz', 'right secret')

with subtest('Requests'):
    is_ok(g('/').body, b'GET', 'right content')
    is_ok(h('/').body, b'', 'no content')
    is_ok(o('/').body, b'OPTIONS', 'right content')
    is_ok(t('/').body, b'PATCH', 'right content')
    is_ok(p('/').body, b'POST', 'right content')
    # Renamed from Mojolicious: u, which is w
    is_ok(w('/').body, b'PUT', 'right content')
    is_ok(d('/').body, b'DELETE', 'right content')
    is_ok(p('/', form={'foo': 'bar'}).body, b'POSTfoo=bar', 'right content')
    is_ok(p('/', json={'foo': 'bar'}).body, b'POST{"foo":"bar"}', 'right content')

with subtest('Mojolicious::Lite'):
    # Unlike Mojolicious: from Pyjo import * does not import the functions of Pyjoyment.Lite, which give the application
    # of a
    from Pyjoyment.Lite import app, get

    get('/test', {'text': 'pass'})
    is_ok(app.ua.get('/test').res.body, b'pass', 'right content')

with subtest('Parse XML'):
    is_ok(x('<title>works</title>').at('title').text, 'works', 'right text')

with subtest('JSON'):
    is_ok(j([1, 2]), b'[1,2]', 'right result')
    is_deeply_ok(j(b'[1,2]'), [1, 2], 'right structure')
    is_ok(j({'foo': 'bar'}), b'{"foo":"bar"}', 'right result')
    is_deeply_ok(j(b'{"foo":"bar"}'), {'foo': 'bar'}, 'right structure')

# Not in Mojolicious: y, as j is for JSON
with subtest('YAML'):
    is_ok(y([1, 2]), '- 1\n- 2\n', 'right result')
    is_deeply_ok(y('- 1\n- 2\n'), [[1, 2]], 'right structure')
    is_ok(y({'foo': 'bar'}, {'baz': 1}), 'foo: bar\n---\nbaz: 1\n', 'right result')
    is_deeply_ok(y(b'foo: bar\n---\nbaz: 1\n'), [{'foo': 'bar'}, {'baz': 1}], 'right structure')

with subtest('ByteStream'):
    is_ok(u('<foo>').url_escape(), '%3Cfoo%3E', 'right result')

with subtest('Collection'):
    is_ok(c(1, 2, 3).join('-'), '1-2-3', 'right result')

# Not in Mojolicious: a lazy iterator, as c makes a collection
with subtest('Iterator'):
    is_ok(i(e for e in (1, 2, 3)).map(lambda e: e * 2).join('-'), '2-4-6', 'right result')

with subtest('File'):
    is_ok(f(__file__).basename(), os.path.basename(__file__), 'right result')

with subtest('Dumper'):
    is_ok(r([1, 2]), '[1, 2]\n', 'right result')

with subtest('Benchmark'):
    calls = []
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        n(lambda: calls.append(1))
    is_ok(len(calls), 1, 'block has been executed once')
    like_ok(buffer.getvalue(), r'wallclock', 'right output')
    with contextlib.redirect_stderr(buffer):
        n(lambda: calls.append(1), 10)
    is_ok(len(calls), 11, 'block has been executed ten times')
    like_ok(buffer.getvalue(), r'(?s)wallclock.*wallclock', 'right output')

with subtest('Link'):
    is_ok(l('http://mojolicious.org/').path.to_str(), '/', 'right result')


# Not in Mojolicious: q for a regular expression, as qr// of Perl
with subtest('Regular expression'):
    ok(q(r'/php(?P<path>/.*)?').fullmatch('/php/foo'), 'match')
    is_ok(q(r'/php(?P<path>/.*)?').fullmatch('/php/foo')['path'], '/foo', 'right group')
    ok(not q(r'/php').fullmatch('/phpx'), 'no match')
    ok(q(r'hello', re.I).fullmatch('HeLLo'), 'flags')


# Not in Mojolicious: z for the builder of Pyjo.JSON.Schema, as z of zod
with subtest('JSON Schema'):
    import Pyjo.JSON.Schema

    is_ok(z.object, Pyjo.JSON.Schema.z.object, 'builder')
    is_ok(repr(z), 'Pyjo.JSON.Schema.z', 'repr')
    ok(z.object(a=z.int()).validate({'a': 1}), 'valid')
    is_ok(str(z.object(a=z.int()).validate({'a': 'b'})), '/a: Expected integer - got string.', 'errors')


# Not in Mojolicious: b for bytes, next to u for characters
with subtest('Bytes'):
    is_ok(b(b'<foo>').url_escape(), b'%3Cfoo%3E', 'right result')


# Not in Mojolicious: python -m Pyjo, in the place of perl -Mojo -E
def one_liner(*args, **kwargs):
    env = {k: v for k, v in os.environ.items() if k != 'PYJO_LOG_LEVEL'} | {'PYTHONPATH': ROOT} | kwargs
    return subprocess.run([sys.executable, '-m', 'Pyjo', *args], env=env, capture_output=True, text=True)


with subtest('python -m Pyjo'):
    result = one_liner('x("<title>works</title>").at("title").text')
    is_ok(result.stdout, 'works\n', 'value of an expression printed')
    is_ok(result.returncode, 0, 'right exit status')
    is_ok(one_liner('None').stdout, '', 'nothing printed for None')
    is_ok(one_liner('j({"a": 1})').stdout, '{"a":1}\n', 'bytes printed as they are')
    is_ok(one_liner('bytearray(b"\\xff")').stdout, '\xff\n', 'bytes that are not UTF-8')
    is_ok(one_liner('print(c(1, 2, 3).join("-"))').stdout, '1-2-3\n', 'statement')
    is_ok(one_liner('z.object(a=z.int()).validate({"a": 1}).is_valid').stdout, 'True\n', 'builder of JSON Schema')
    is_ok(one_liner('import sys; print(sys.argv)', 'a', 'b').stdout, "['-c', 'a', 'b']\n", 'arguments')
    is_ok(one_liner('sys.argv[1:]', 'a', 'b').stdout, "['a', 'b']\n", 'arguments of an expression')
    is_ok(one_liner('import os; print(os.environ["PYJO_LOG_LEVEL"])').stdout, 'fatal\n', 'silent')
    is_ok(
        one_liner('import os; print(os.environ["PYJO_LOG_LEVEL"])', PYJO_LOG_LEVEL='debug').stdout,
        'debug\n',
        'log level',
    )
    result = one_liner()
    like_ok(result.stderr, r'^usage: python -m Pyjo CODE', 'usage')
    is_ok(result.returncode, 1, 'right exit status')
    result = one_liner('die("Exit")')
    like_ok(result.stderr, r"NameError: name 'die' is not defined", 'only the functions of ojo')

# Not in Mojolicious: the modules that a function uses are imported when it is called
with subtest('Lazy imports'):
    result = subprocess.run(
        [sys.executable, '-c', 'import sys, Pyjo.URL; print("Pyjo.UserAgent" in sys.modules)'],
        env=dict(os.environ, PYTHONPATH=ROOT),
        capture_output=True,
        text=True,
    )
    is_ok(result.stdout, 'False\n', 'no user agent for a module of Pyjo')
    result = subprocess.run(
        [sys.executable, '-c', 'import sys; from Pyjo import *; print("Pyjo.JSON.Schema" in sys.modules)'],
        env=dict(os.environ, PYTHONPATH=ROOT),
        capture_output=True,
        text=True,
    )
    is_ok(result.stdout, 'False\n', 'no JSON Schema for the functions of ojo')


# Not in Mojolicious: s for the standard input and output, as bytes, and the line break of print, which is CRLF on
# Windows, where s writes its bytes as they are
def stdio(code, input=b'', **kwargs):
    env = {k: v for k, v in os.environ.items() if k != 'PYJO_LOG_LEVEL'} | {'PYTHONPATH': ROOT}
    return subprocess.run([sys.executable, '-m', 'Pyjo', code], env=env, input=input, capture_output=True, **kwargs)


with subtest('Standard input and output'):
    newline = os.linesep.encode()
    is_ok(stdio('y(s()).first()["a"]', 'a: 1\n'.encode('UTF-16')).stdout, b'1' + newline, 'input of UTF-16')
    is_ok(stdio('j(s())["a"]', b'\xef\xbb\xbf{"a": 1}').stdout, b'1' + newline, 'input with a byte order mark')
    is_ok(stdio('s() is s()', b'x').stdout, b'True' + newline, 'input read once')
    is_ok(stdio('s().size').stdout, b'0' + newline, 'no input')
    is_ok(stdio('s(b"\\x89PNG\\r\\n\\x1a\\n")').stdout, b'\x89PNG\r\n\x1a\n', 'bytes written as they are')
    is_ok(stdio('s("\\u2665", b"\\xff", 1)').stdout, b'\xe2\x99\xa5\xff1', 'characters as UTF-8')
    result = stdio('s(s(s(), fd=2))', b'hello\n')
    is_ok(result.stdout, b'hello\n', 'written to the standard output once')
    is_ok(result.stderr, b'hello\n', 'and to the standard error')
    result = stdio('s("x", fd=2)')
    is_ok(result.stderr, b'x', 'written to the standard error')
    is_ok(result.stdout, b'x' + newline, 'and printed')
    is_ok(stdio('s("abc").size').stdout, b'abc3' + newline, 'chained')
    is_ok(stdio('print("first"); s("second")').stdout, b'first' + newline + b'second', 'after print')

    if sys.platform == 'win32':
        skip('other file descriptors are not passed on Windows', 2)
    else:
        with tempfile.TemporaryDirectory() as dir:
            path = os.path.join(dir, 'fd.txt')
            with open(path, 'wb') as handle:
                stdio(f's("to the descriptor", fd={handle.fileno()})', pass_fds=(handle.fileno(),))
            with open(path, 'rb') as handle:
                is_ok(handle.read(), b'to the descriptor', 'written to a file descriptor')
            with open(path, 'rb') as handle:
                result = stdio(f's(fd={handle.fileno()}).decode()', pass_fds=(handle.fileno(),))
            is_ok(result.stdout, b'to the descriptor\n', 'read from a file descriptor')

done_testing()
