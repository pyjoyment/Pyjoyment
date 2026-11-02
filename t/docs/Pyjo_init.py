import Pyjo
import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Server.Daemon
import Pyjoyment

from Pyjo import *
from Pyjo.Test import *

import contextlib
import http.client
import io
import os
import subprocess
import sys
import threading


ROOT = os.path.join(os.path.dirname(__file__), '..', '..')

# The examples request a real host and listen on a fixed port, so a local daemon with an application answers instead
app = Pyjoyment.new()
app.log.level = 'fatal'
HTML = '<html><head><title>Mojolicious</title></head><body><h1>One</h1><h1>Two &amp; Three</h1></body></html>'
app.routes.any('/', {'text': HTML})
app.routes.get('/repos/pyjoyment/Pyjoyment', {'json': {'id': 1, 'name': 'Pyjoyment'}})
local = Pyjo.Server.Daemon.new(app=app, ioloop=Pyjo.IOLoop.singleton, listen=['http://127.0.0.1'], silent=True)
port = local.start().ports()[0]


def to_local(ua):
    ua.ioloop = Pyjo.IOLoop.singleton

    @ua.on('start')
    def start(ua, tx):
        url = tx.req.url
        url.scheme, url.host, url.port = 'http', '127.0.0.1', port
        tx.req.proxy = None

    return ua


@contextlib.contextmanager
def output():
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        yield stdout


with subtest('Synopsis'):
    with output() as stdout:
        # HTTP/WebSocket user agent
        import Pyjo.UserAgent

        ua = to_local(Pyjo.UserAgent.new())
        print(ua.get('www.mojolicious.org').result.headers.server)
    is_ok(stdout.getvalue(), 'Pyjoyment (Python)\n', 'user agent')

    with output() as stdout:
        # HTML/XML DOM parser with CSS selectors
        import Pyjo.DOM

        dom = Pyjo.DOM.new('<div><b>Hello Pyjo!</b></div>')
        print(dom.at('div > b').text)
    is_ok(stdout.getvalue(), 'Hello Pyjo!\n', 'DOM')

    with output() as stdout:
        # Python-ish templates
        import Pyjo.Template

        mt = Pyjo.Template.new(vars=True)
        print(mt.render('Hello <%= what %>!', {'what': 'Pyjo'}))
    is_ok(stdout.getvalue(), 'Hello Pyjo!\n\n', 'template, with the newline at its end')

    # HTTP/WebSocket server
    import Pyjo.Server.Daemon

    daemon = Pyjo.Server.Daemon.new(listen=['http://127.0.0.1'], silent=True)

    @daemon.unsubscribe('request').on('request')
    def request(daemon, tx):
        tx.res.code = 200
        tx.res.body = b'Hello Pyjo!'
        tx.resume()

    daemon_port = daemon.start().ports()[0]
    results = []

    def client():
        conn = http.client.HTTPConnection('127.0.0.1', daemon_port, timeout=10)
        conn.request('GET', '/')
        results.append(conn.getresponse().read())
        conn.close()

    # The client in a thread of its own, and the event loop stops when it is done
    worker = threading.Thread(target=client)
    worker.start()
    id = Pyjo.IOLoop.recurring(0.05, lambda loop: worker.is_alive() or loop.stop())
    daemon.run()
    worker.join()
    Pyjo.IOLoop.remove(id)
    is_deeply_ok(results, [b'Hello Pyjo!'], 'server')

    with output() as stdout:
        # Event loop, with a tenth of a second for each second
        import Pyjo.IOLoop

        for seconds in range(1, 6):
            Pyjo.IOLoop.timer(seconds / 10, lambda loop, seconds=seconds: print(seconds))
        Pyjo.IOLoop.timer(0.6, lambda loop: loop.stop())
        Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), '1\n2\n3\n4\n5\n', 'event loop')

# The user agent of the functions, on the local daemon, and python -m Pyjo for the examples that do not request a host
to_local(Pyjo._ua())


def one_liner(code, **kwargs):
    env = dict(os.environ, PYTHONPATH=os.path.abspath(ROOT))
    return subprocess.run([sys.executable, '-m', 'Pyjo', code], env=env, capture_output=True, text=True, **kwargs)


with subtest('One-liners'):
    is_ok(g('mojolicious.org').dom().at('title').text, 'Mojolicious', 'g')
    is_ok(g('example.com').code, 200, 'PYJO_MAX_REDIRECTS=0')
    like_ok(g('example.com').body, rb'<title>', 'PYJO_PROXY=0')
    like_ok(g('https://127.0.0.1:3000').body, rb'<title>', 'PYJO_INSECURE=1')
    result = one_liner('import os; print(os.environ["PYJO_LOG_LEVEL"])')
    is_ok(result.stdout, 'fatal\n', 'PYJO_LOG_LEVEL')

with subtest('b'):
    stream = b(b'lalala')
    isa_ok(stream, Pyjo.String.Bytes.object, 'stream')
    stdout = io.TextIOWrapper(io.BytesIO(), write_through=True)
    with contextlib.redirect_stdout(stdout):
        b(g('mojolicious.org').body).html_unescape().say()
    like_ok(stdout.buffer.getvalue(), rb'<h1>Two & Three</h1>', 'say')

with subtest('c'):
    collection = c(1, 2, 3)
    is_deeply_ok(list(collection), [1, 2, 3], 'collection')

with subtest('d'):
    res = d('example.com')
    is_ok(res.code, 200, 'DELETE')
    res = d('http://example.com', {'Accept': '*/*'}, b'Hi!')
    is_ok(res.code, 200, 'body')
    res = d('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    is_ok(res.code, 200, 'form')
    res = d('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(res.code, 200, 'JSON')

with subtest('f'):
    path = f('/home/sri/foo.txt')
    is_ok(path.basename(), 'foo.txt', 'path')
    dir = Pyjo.File.tempdir()
    is_ok(one_liner('f("hello.json").spew(j({"hello": "world!"}))', cwd=dir.to_str()).returncode, 0, 'spew')
    is_ok(one_liner('r(j(f("hello.json").slurp()))', cwd=dir.to_str()).stdout, "{'hello': 'world!'}\n\n", 'r')

with subtest('g'):
    res = g('example.com')
    is_ok(res.code, 200, 'GET')
    res = g('http://example.com', {'Accept': '*/*'}, b'Hi!')
    is_ok(res.code, 200, 'body')
    res = g('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    is_ok(res.code, 200, 'form')
    res = g('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(res.code, 200, 'JSON')
    is_ok(g('mojolicious.org').dom('h1').map('text').join('\n'), 'One\nTwo & Three', 'dom')

with subtest('h'):
    res = h('example.com')
    is_ok(res.code, 200, 'HEAD')
    res = h('http://example.com', {'Accept': '*/*'}, b'Hi!')
    is_ok(res.code, 200, 'body')
    res = h('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    is_ok(res.code, 200, 'form')
    res = h('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(res.code, 200, 'JSON')

with subtest('i'):
    iterator = i(range(1, 4))
    is_deeply_ok(list(iterator), [1, 2, 3], 'iterator')

    # "2, 4, 6"
    is_ok(i(range(1, 4)).map(lambda n: n * 2).join(', '), '2, 4, 6', 'chain')

with subtest('j'):
    data = j([1, 2, 3])
    is_ok(data, b'[1,2,3]', 'list')
    data = j({'foo': 'bar'})
    is_ok(data, b'{"foo":"bar"}', 'dict')
    value = j(data)
    is_deeply_ok(value, {'foo': 'bar'}, 'decoded')

with subtest('l'):
    url = l('https://mojolicious.org')
    is_ok(url.host, 'mojolicious.org', 'url')
    is_ok(
        one_liner('l("/perldoc").to_abs(l("https://mojolicious.org"))').stdout,
        'https://mojolicious.org/perldoc\n',
        'to_abs',
    )

with subtest('n'):
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        n(lambda: ...)
        n(lambda: ..., 100)
        with output() as stdout:
            n(lambda: print(g('mojolicious.org').code))
    is_ok(stdout.getvalue(), '200\n', 'callback')
    like_ok(stderr.getvalue(), r'(?s)^.*wallclock secs .*wallclock secs .*wallclock secs ', 'results')

with subtest('o'):
    res = o('example.com')
    is_ok(res.code, 200, 'OPTIONS')
    res = o('http://example.com', {'Accept': '*/*'}, b'Hi!')
    is_ok(res.code, 200, 'body')
    res = o('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    is_ok(res.code, 200, 'form')
    res = o('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(res.code, 200, 'JSON')

with subtest('p'):
    res = p('example.com')
    is_ok(res.code, 200, 'POST')
    res = p('http://example.com', {'Accept': '*/*'}, b'Hi!')
    is_ok(res.code, 200, 'body')
    res = p('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    is_ok(res.code, 200, 'form')
    res = p('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(res.code, 200, 'JSON')

with subtest('q'):
    regex = q(r'/phpinfo\.php')
    ok(regex.fullmatch('/phpinfo.php'), 'regular expression')
    regex = q(r'/php(?P<path>/.*)?')
    is_ok(regex.fullmatch('/php/foo')['path'], '/foo', 'group path')
    is_ok(one_liner('bool(q(r"\\d+").fullmatch("42"))').stdout, 'True\n', 'one-liner')

with subtest('r'):
    python = r({'data': 'structure'})
    is_ok(python, "{'data': 'structure'}\n", 'dumped')
    like_ok(r(g('example.com').headers.to_dict()), r"'Server': 'Pyjoyment \(Python\)'", 'headers')

with subtest('t'):
    res = t('example.com')
    is_ok(res.code, 200, 'PATCH')
    res = t('http://example.com', {'Accept': '*/*'}, b'Hi!')
    is_ok(res.code, 200, 'body')
    res = t('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    is_ok(res.code, 200, 'form')
    res = t('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(res.code, 200, 'JSON')

with subtest('u'):
    stream = u('lalala')
    isa_ok(stream, Pyjo.String.Unicode.object, 'stream')
    with output() as stdout:
        u(g('mojolicious.org').text).html_unescape().say()
    like_ok(stdout.getvalue(), r'<h1>Two & Three</h1>', 'say')

with subtest('w'):
    res = w('example.com')
    is_ok(res.code, 200, 'PUT')
    res = w('http://example.com', {'Accept': '*/*'}, b'Hi!')
    is_ok(res.code, 200, 'body')
    res = w('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    is_ok(res.code, 200, 'form')
    res = w('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(res.code, 200, 'JSON')

with subtest('x'):
    dom = x('<div>Hello!</div>')
    is_ok(dom.at('div').text, 'Hello!', 'dom')
    dir = Pyjo.File.tempdir()
    dir.child('test.html').spew(HTML.encode())
    is_ok(one_liner('x(f("test.html").slurp()).at("title").text', cwd=dir.to_str()).stdout, 'Mojolicious\n', 'file')

with subtest('z'):
    schema = z.object(name=z.string(), stars=z.int().min(0))
    ok(schema.validate({'name': 'Pyjoyment', 'stars': 1}), 'schema')
    dir = Pyjo.File.tempdir()
    dir.child('config.json').spew(b'{"port": "3000"}')
    result = one_liner('z.object(port=z.int()).validate(j(f("config.json").slurp()))', cwd=dir.to_str())
    is_ok(result.stdout, '/port: Expected integer - got string.\n', 'file')
    is_ok(
        z.object(id=z.int()).validate(g('api.github.com/repos/pyjoyment/Pyjoyment').json()).is_valid, True, 'response'
    )

local.stop()

done_testing()
