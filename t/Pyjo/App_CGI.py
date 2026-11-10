import Pyjo.App.CGI
import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjoyment

from Pyjo.Test import *

import concurrent.futures
import http.client
import os
import re
import sys
import time


if os.name == 'nt':
    plan(skip_all='CGI applications need pipes that the event loop watches, which Windows does not have')

# The programs of the tests, with the Python of the test, in a temporary directory, as a test writes nothing into t
tmp = Pyjo.File.tempdir()
root = tmp.child('cgi-bin').make_path()
repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def program(directory, name, code, mode=0o755):
    file = directory.child(name)
    file.spew(f'#!{sys.executable}\n{code}'.encode())
    os.chmod(file.to_str(), mode)
    return file.to_str()


ENV = """\
import json, os, sys

length = int(os.environ.get('CONTENT_LENGTH') or 0)
body = sys.stdin.buffer.read(length) if length else b''
sys.stdout.buffer.write(b'Content-Type: application/json\\r\\n\\r\\n')
data = {'env': dict(os.environ), 'cwd': os.getcwd(), 'args': sys.argv, 'body': body.decode('latin-1')}
sys.stdout.buffer.write(json.dumps(data).encode())
"""
env_cgi = program(root, 'env.cgi', ENV)
program(root.child('sub').make_path(), 'env.cgi', ENV)
program(
    root, 'status.cgi', "import sys\nsys.stdout.buffer.write(b'Status: 201 Created\\r\\nX-Test: 1\\r\\n\\r\\nmade')\n"
)
program(root, 'location.cgi', "import sys\nsys.stdout.buffer.write(b'Location: /there\\r\\n\\r\\n')\n")
program(
    root,
    'stream.cgi',
    """\
import sys, time

out = sys.stdout.buffer
out.write(b'Content-Type: text/plain\\n\\n')
out.flush()
for n in range(3):
    time.sleep(0.02)
    out.write(str(n).encode())
    out.flush()
""",
)
program(
    root,
    'length.cgi',
    """\
import sys, time

out = sys.stdout.buffer
out.write(b'Content-Length: 6\\r\\n\\r\\none')
out.flush()
time.sleep(0.02)
out.write(b'two')
""",
)
program(
    root,
    'nph-hello.cgi',
    "import sys\nsys.stdout.buffer.write(b'HTTP/1.1 202 Accepted\\r\\nContent-Type: text/plain\\r\\n\\r\\nhello')\n",
)
program(
    root,
    'nph-chunked.cgi',
    """\
import sys, time

out = sys.stdout.buffer
out.write(b'HTTP/1.1 200 OK\\r\\nTransfer-Encoding: chunked\\r\\n\\r\\n3\\r\\none\\r\\n')
out.flush()
time.sleep(0.02)
out.write(b'3\\r\\ntwo\\r\\n0\\r\\n\\r\\n')
""",
)
program(
    root,
    'nph-length.cgi',
    """\
import sys, time

out = sys.stdout.buffer
out.write(b'HTTP/1.1 200 OK\\r\\nContent-Length: 6\\r\\n\\r\\none')
out.flush()
time.sleep(0.02)
out.write(b'two')
""",
)
program(root, 'nph-end.cgi', "import sys\nsys.stdout.buffer.write(b'HTTP/1.0 404 Gone Fishing\\n\\nuntil the end')\n")
program(root, 'nph-bad.cgi', "import sys\nsys.stdout.buffer.write(b'Content-Type: text/plain\\r\\n\\r\\nx')\n")
program(root, 'start.cgi', "import sys\nsys.stdout.buffer.write(b'HTTP/1.1 201 Created\\r\\n\\r\\nmade')\n")
program(root, 'fail.cgi', "import sys\nsys.stderr.write('oops\\n')\nsys.exit(1)\n")
program(root, 'half.cgi', "import sys\nsys.stdout.buffer.write(b'Content-Type: text/plain\\r\\n')\n")

# A program that writes its process id at once, as a shell does, which Python does not before its timeout
sleep_cgi = root.child('sleep.cgi')
sleep_cgi.spew(b"""#!/bin/sh
sleep 10 &
echo $! > "$PID_FILE.child"
echo $$ > "$PID_FILE"
if [ "$QUERY_STRING" = started ]; then
  printf 'Content-Type: text/plain\\r\\n\\r\\nstarted'
fi
exec sleep 10
""")
os.chmod(sleep_cgi.to_str(), 0o755)
program(
    root,
    'big.cgi',
    """\
import os, sys

with open(os.environ['PID_FILE'], 'w') as file:
    file.write(str(os.getpid()))
out = sys.stdout.buffer
out.write(b'Content-Type: text/plain\\r\\n\\r\\n')
while True:
    out.write(b'x' * 10000)
    out.flush()
""",
)
program(
    root,
    'sendfile.cgi',
    """\
import os, sys

file = os.environ['QUERY_STRING']
sys.stdout.buffer.write(f'Status: 200\\r\\nX-Sendfile: {file}\\r\\nX-Test: 1\\r\\n\\r\\n'.encode())
""",
)
root.child('readme.txt').spew(b'not a program')
tmp.child('secret.cgi').spew(b'')
links = hasattr(os, 'symlink')
if links:
    os.symlink(tmp.child('secret.cgi').to_str(), root.child('link.cgi').to_str())


# The value of a promise, which the event loop fulfills
def result(promise):
    values = []
    promise.then(lambda *args: values.extend(args)).wait()
    return values[0] if len(values) == 1 else values


# The response as it is on the wire, as the user agent removes the chunked transfer encoding
def raw(t, method, path='/'):
    url = t.ua.server.url()

    def request():
        connection = http.client.HTTPConnection(url.host, url.port, timeout=5)
        try:
            connection.request(method, path)
            res = connection.getresponse()
            try:
                body = res.read()
            except http.client.IncompleteRead as e:
                body = ('incomplete', e.partial)
            return res.status, res.getheader('Content-Length'), res.getheader('Transfer-Encoding'), body
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(1) as executor:
        return result(Pyjo.Promise.new(executor.submit(request)))


def application(cgi, prefix='/prefix'):
    cgi.log.level = 'fatal'
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    route = app.routes.any(prefix)
    route.partial = True
    route.to(app=cgi)
    return app


# The inactivity timeout of a program that writes its PID file and sleeps, which counts from the start of the program,
# so that a shell that starts slowly on a busy machine writes the file before the program is killed
INACTIVE = 2


# The process of a program, once the event loop has reaped it
def gone(pid_file, timeout=5):
    deadline = time.monotonic() + timeout
    while not os.path.exists(pid_file) and time.monotonic() < deadline:
        Pyjo.IOLoop.timer(0.05, lambda loop: None)
        Pyjo.IOLoop.one_tick()
    with open(pid_file) as file:
        pid = int(file.read())
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        Pyjo.IOLoop.timer(0.05, lambda loop: None)
        Pyjo.IOLoop.one_tick()
    return False


with subtest('Parameters'):
    with Pyjo.App.CGI.new(script=env_cgi, env={'FOO': 'bar', 'SERVER_NAME': 'example.com'}) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        t.get_ok('/prefix/foo/bar?x=1', {'X-Test': 'a', 'Proxy': 'http://evil:8080'}).status_is(200)
        env = t.tx.res.json('/env')
        is_ok(env['REQUEST_METHOD'], 'GET', 'right method')
        is_ok(env['SCRIPT_NAME'], '/prefix', 'right script name')
        is_ok(env['PATH_INFO'], '/foo/bar', 'right path')
        is_ok(env['QUERY_STRING'], 'x=1', 'right query')
        is_ok(env['REQUEST_URI'], '/prefix/foo/bar?x=1', 'right request URI')
        is_ok(env['SCRIPT_FILENAME'], env_cgi, 'right script file')
        is_ok(env['GATEWAY_INTERFACE'], 'CGI/1.1', 'right gateway interface')
        is_ok(env['SERVER_SOFTWARE'], 'Pyjoyment (Python)', 'right server software')
        is_ok(env['HTTP_X_TEST'], 'a', 'right header')
        is_ok(env['FOO'], 'bar', 'added variable')
        is_ok(env['SERVER_NAME'], 'example.com', 'replaced variable')
        is_ok(env['PATH'], os.environ['PATH'], 'path of the process')
        ok('HTTP_PROXY' not in env, 'no proxy of the header Proxy')
        ok('REDIRECT_STATUS' not in env, 'no redirect status without a command')
        ok('PYTHONPATH' not in env, 'no other variables of the process')
        is_ok(os.path.realpath(t.tx.res.json('/cwd')), os.path.realpath(root.to_str()), 'directory of the program')
        is_deeply_ok(t.tx.res.json('/args'), [env_cgi], 'the program itself')

        # The path of the mount itself
        t.get_ok('/prefix').status_is(200).json_is('/env/SCRIPT_NAME', '/prefix').json_is('/env/PATH_INFO', '')

        # The bytes of the path in the variable, which the program decodes
        t.get_ok('/prefix/a%20b/%E2%99%A5').status_is(200).json_is('/env/PATH_INFO', '/a b/♥')

        # Not at a part of the path that does not end with a slash
        t.get_ok('/prefixx').status_is(404)

with subtest('Body'):
    with Pyjo.App.CGI.new(script=env_cgi) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        t.post_ok('/prefix', b'Hello CGI!').status_is(200).json_is('/body', 'Hello CGI!')
        t.json_is('/env/CONTENT_LENGTH', '10')

        # More than the pipe takes at once
        body = b'0123456789' * 50000
        t.post_ok('/prefix', body).status_is(200).json_is('/body', body.decode())

with subtest('Directory of the programs'):
    with Pyjo.App.CGI.new(document_root=root.to_str()) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))
        t.get_ok('/cgi-bin/env.cgi/foo/bar').status_is(200)
        t.json_is('/env/SCRIPT_NAME', '/cgi-bin/env.cgi').json_is('/env/PATH_INFO', '/foo/bar')
        t.json_is('/env/SCRIPT_FILENAME', f'{root.to_str()}/env.cgi').json_is('/env/DOCUMENT_ROOT', root.to_str())
        t.get_ok('/cgi-bin/sub/env.cgi').status_is(200)
        t.json_is('/env/SCRIPT_NAME', '/cgi-bin/sub/env.cgi').json_is('/env/PATH_INFO', '')
        is_ok(os.path.realpath(t.tx.res.json('/cwd')), os.path.realpath(root.child('sub').to_str()), 'its directory')

        # Not found
        t.get_ok('/cgi-bin/missing.cgi').status_is(404)
        t.get_ok('/cgi-bin/').status_is(404)
        t.get_ok('/cgi-bin/sub').status_is(404)
        t.get_ok('/cgi-bin/%2E%2E/secret.cgi').status_is(404)
        if links:
            t.get_ok('/cgi-bin/link.cgi').status_is(404)

        # Not executable
        with cgi.log.capture('error') as messages:
            t.get_ok('/cgi-bin/readme.txt').status_is(502)
        like_ok(str(messages), r"Can't run CGI application: Permission denied", 'right error')

    # The one program for a path that names no program of the directory
    with Pyjo.App.CGI.new(document_root=root.to_str(), script='env.cgi') as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))
        t.get_ok('/cgi-bin/2026/10/hello/').status_is(200)
        t.json_is('/env/SCRIPT_NAME', '/cgi-bin/env.cgi').json_is('/env/PATH_INFO', '')
        t.json_is('/env/REQUEST_URI', '/cgi-bin/2026/10/hello/')
        t.get_ok('/cgi-bin/sub/env.cgi/x').status_is(200).json_is('/env/SCRIPT_NAME', '/cgi-bin/sub/env.cgi')

    # The script of the variables takes its place
    with Pyjo.App.CGI.new(document_root=root.to_str(), env={'SCRIPT_FILENAME': env_cgi}) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))
        t.get_ok('/cgi-bin/foo').status_is(200).json_is('/env/SCRIPT_NAME', '/cgi-bin').json_is(
            '/env/PATH_INFO', '/foo'
        )

with subtest('Scripts of a command'):
    www = tmp.child('www').make_path()
    for name in ('index.py', 'page.py'):
        www.child(name).spew(ENV.encode())
    www.child('style.css').spew(b'body { color: red }')
    www.child('private.txt').spew(b'private')
    with Pyjo.App.CGI.new(
        command=[sys.executable], document_root=www.to_str(), script_extensions=['.py'], static=True
    ) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/www'))
        t.get_ok('/www/').status_is(200)
        t.json_is('/env/SCRIPT_NAME', '/www/index.py').json_is('/env/SCRIPT_FILENAME', f'{www.to_str()}/index.py')
        t.json_is('/env/REDIRECT_STATUS', '200').json_is('/args', [f'{www.to_str()}/index.py'])
        t.get_ok('/www/page.py/x').status_is(200)
        t.json_is('/env/SCRIPT_NAME', '/www/page.py').json_is('/env/PATH_INFO', '/x')
        t.get_ok('/www/style.css').status_is(200).content_is('body { color: red }')
        t.get_ok('/www/missing.py').status_is(404)
        t.get_ok('/www/private.txt/x').status_is(404)
        t.get_ok('/www/missing.css').status_is(404)

    # The one script for every path, with a command
    with Pyjo.App.CGI.new(command=[sys.executable], script=f'{www.to_str()}/page.py') as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/app'))
        t.get_ok('/app/foo').status_is(200).json_is('/env/PATH_INFO', '/foo').json_is('/env/REDIRECT_STATUS', '200')

with subtest('X-Sendfile'):
    with Pyjo.App.CGI.new(document_root=root.to_str(), sendfile=tmp.child('www').to_str()) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))
        t.get_ok(f'/cgi-bin/sendfile.cgi?{tmp.child("www", "private.txt").to_str()}').status_is(200)
        t.header_is('X-Test', '1').content_is('private')
        with cgi.log.capture('error') as messages:
            t.get_ok(f'/cgi-bin/sendfile.cgi?{env_cgi}').status_is(404)
        like_ok(
            str(messages), r'CGI application sent the file ".*env\.cgi", which sendfile does not allow', 'right error'
        )

    # A regular expression of the whole path of the file, once its symbolic links are resolved
    private = re.escape(os.path.realpath(tmp.child('www', 'private.txt').to_str()))
    with Pyjo.App.CGI.new(document_root=root.to_str(), sendfile=re.compile(private)) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))
        t.get_ok(f'/cgi-bin/sendfile.cgi?{tmp.child("www", "private.txt").to_str()}').status_is(200).content_is(
            'private'
        )
        t.get_ok(f'/cgi-bin/sendfile.cgi?{env_cgi}').status_is(404)

with subtest('Response'):
    with Pyjo.App.CGI.new(document_root=root.to_str()) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))
        t.get_ok('/cgi-bin/status.cgi').status_is(201).header_is('X-Test', '1').content_is('made')
        t.get_ok('/cgi-bin/location.cgi').status_is(302).header_is('Location', '/there')
        t.get_ok('/cgi-bin/stream.cgi').status_is(200).content_is('012')
        is_deeply_ok(raw(t, 'GET', '/cgi-bin/stream.cgi'), (200, None, 'chunked', b'012'), 'chunked')
        is_deeply_ok(raw(t, 'GET', '/cgi-bin/length.cgi'), (200, '6', None, b'onetwo'), 'with its length')
        is_deeply_ok(raw(t, 'HEAD', '/cgi-bin/stream.cgi'), (200, None, 'chunked', b''), 'headers only')

with subtest('Non-parsed headers'):
    with Pyjo.App.CGI.new(document_root=root.to_str()) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))
        t.get_ok('/cgi-bin/nph-hello.cgi').status_is(202).header_is('Content-Type', 'text/plain').content_is('hello')
        is_ok(t.tx.res.message, 'Accepted', 'right message')

        # The body of its chunks, of its length, and up to the end of the output, with lines that end with LF
        t.get_ok('/cgi-bin/nph-chunked.cgi').status_is(200).content_is('onetwo')
        status, length, encoding, body = raw(t, 'GET', '/cgi-bin/nph-chunked.cgi')
        is_deeply_ok((status, body), (200, b'onetwo'), 'chunks without their sizes')
        ok((length, encoding) in (('6', None), (None, 'chunked')), 'length or chunks')
        is_deeply_ok(raw(t, 'GET', '/cgi-bin/nph-length.cgi'), (200, '6', None, b'onetwo'), 'with its length')
        is_deeply_ok(raw(t, 'HEAD', '/cgi-bin/nph-length.cgi'), (200, '6', None, b''), 'headers only')
        t.get_ok('/cgi-bin/nph-end.cgi').status_is(404).content_is('until the end')
        is_ok(t.tx.res.message, 'Gone Fishing', 'right message')

        # Not an HTTP response
        with cgi.log.capture('error') as messages:
            t.get_ok('/cgi-bin/nph-bad.cgi').status_is(502)
        like_ok(str(messages), r'CGI application sent an invalid response', 'right error')

    # The attribute, which takes the place of the name of the file
    with Pyjo.App.CGI.new(script=f'{root}/start.cgi', nph=True) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        t.get_ok('/prefix').status_is(201).content_is('made')
    with Pyjo.App.CGI.new(script=f'{root}/nph-bad.cgi', nph=False) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        t.get_ok('/prefix').status_is(200).content_is('x')

with subtest('Errors'):
    with Pyjo.App.CGI.new(document_root=root.to_str()) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/cgi-bin'))

        # Ended without a response, with its standard error logged
        with cgi.log.capture('warn') as messages:
            t.get_ok('/cgi-bin/fail.cgi').status_is(502).content_is('Bad Gateway')
        like_ok(str(messages), r'CGI application ended without a response', 'right error')
        like_ok(str(messages), r'CGI application: oops', 'standard error')
        with cgi.log.capture('error') as messages:
            t.get_ok('/cgi-bin/half.cgi').status_is(502)
        like_ok(str(messages), r'CGI application ended without a response', 'right error')

    # Not found
    with Pyjo.App.CGI.new(script=tmp.child('missing.cgi').to_str()) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        with cgi.log.capture('error') as messages:
            t.get_ok('/prefix').status_is(502)
        like_ok(str(messages), r"Can't run CGI application: No such file or directory", 'right error')

    # Inactive, which kills the process
    pid_file = tmp.child('inactive.pid').to_str()
    with Pyjo.App.CGI.new(script=f'{root}/sleep.cgi', env={'PID_FILE': pid_file}, inactivity_timeout=INACTIVE) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        with cgi.log.capture('error') as messages:
            t.get_ok('/prefix').status_is(502)
        like_ok(str(messages), r'CGI application inactive', 'right error')
        ok(gone(pid_file), 'process killed')
        ok(gone(f'{pid_file}.child'), 'process that it has started killed')

    # Inactive after the start of the response, which closes the connection of the client
    pid_file = tmp.child('started.pid').to_str()
    with Pyjo.App.CGI.new(script=f'{root}/sleep.cgi', env={'PID_FILE': pid_file}, inactivity_timeout=INACTIVE) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        is_deeply_ok(
            raw(t, 'GET', '/prefix?started'), (200, None, 'chunked', ('incomplete', b'started')), 'incomplete response'
        )
        ok(gone(pid_file), 'process killed')
        ok(gone(f'{pid_file}.child'), 'process that it has started killed')

    throws_ok(
        lambda: Pyjo.App.CGI.new().handler(Pyjo.Transaction.HTTP.new()),
        re.compile(r'^No CGI application'),
        'no application',
    )

with subtest('Scripts in the static files'):
    # The static files of the application that mounts it are served before the route of the mount, with the source of
    # the scripts
    project = Pyjo.File.tempdir()
    public = project.child('public').make_path()

    def start(cgi):
        app = Pyjoyment.new()
        app.log.level = 'fatal'
        app.static.paths = [public.to_str()]
        app.plugin('Mount', {'/': cgi})
        return Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], silent=True).start()

    error = re.compile(
        r'^Scripts of Pyjo\.App\.CGI in \S+ are in the static files of \S+public, which would serve their'
    )
    throws_ok(lambda: start(Pyjo.App.CGI.new(document_root=public.to_str())), error, 'document root')
    cgi = Pyjo.App.CGI.new(document_root=public.child('cgi-bin').make_path().to_str())
    throws_ok(lambda: start(cgi), error, 'directory in the static files')
    throws_ok(lambda: start(Pyjo.App.CGI.new(script=public.child('hello.cgi').to_str())), error, 'one script')
    www = project.child('www').make_path().to_str()
    throws_ok(
        lambda: start(Pyjo.App.CGI.new(document_root=www, script='../public/hello.cgi')), error, 'relative script'
    )

    # Another directory, and the static files on purpose
    for cgi in (
        Pyjo.App.CGI.new(document_root=www),
        Pyjo.App.CGI.new(document_root=public.to_str(), public_source=True),
    ):
        with start(cgi) as server:
            ok(server.ports(), 'started')

with subtest('Connection of the client closed'):
    pid_file = tmp.child('big.pid').to_str()
    with Pyjo.App.CGI.new(script=f'{root}/big.cgi', env={'PID_FILE': pid_file}) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi))
        t.ua.max_response_size = 100000
        tx = t.ua.get('/prefix')
        is_ok(tx.error['message'], 'Maximum message size exceeded', 'right error')
        ok(gone(pid_file), 'process killed')

with subtest('Pyjoyment on CGI'):
    lite = tmp.child('lite').make_path()
    code = f"""\
import sys

sys.path.insert(0, {repo!r})

import Pyjo.IOLoop

from Pyjoyment.Lite import app, get, post

app.log.level = 'fatal'
get('/', lambda c: c.render(text=f'Hello CGI at {{c.url_for("/")}} for {{c.req.url.path.to_abs_str()}}!'))
post('/echo', lambda c: c.render(data=c.req.body))
get('/chunks', lambda c: c.write_chunk(b'one', lambda c: c.write_chunk(b'two', lambda c: c.finish())))
get('/gone', lambda c: c.render(text='gone', status=410))


@get('/later')
def later(c):
    c.render_later()
    Pyjo.IOLoop.timer(0.01, lambda loop: c.render(text='later'))


app.start(*sys.argv[1:])
"""
    program(lite, 'hello.cgi', code)
    program(lite, 'nph-hello.cgi', code.replace('app.start(*sys.argv[1:])', "app.start('cgi', '--nph')"))
    with Pyjo.App.CGI.new(document_root=lite.to_str()) as cgi:
        t = Pyjo.Test.Pyjo.new(application(cgi, '/lite'))
        t.get_ok('/lite/hello.cgi').status_is(200).content_is('Hello CGI at /lite/hello.cgi for /!')
        t.get_ok('/lite/hello.cgi/').status_is(200).content_is('Hello CGI at /lite/hello.cgi for /!')
        t.post_ok('/lite/hello.cgi/echo', b'echo').status_is(200).content_is('echo')
        t.get_ok('/lite/hello.cgi/missing').status_is(404)
        t.get_ok('/lite/hello.cgi/chunks').status_is(200).content_is('onetwo')
        t.get_ok('/lite/hello.cgi/later').status_is(200).content_is('later')
        t.get_ok('/lite/nph-hello.cgi').status_is(200).content_is('Hello CGI at /lite/nph-hello.cgi for /!')
        t.post_ok('/lite/nph-hello.cgi/echo', b'echo').status_is(200).content_is('echo')
        t.get_ok('/lite/nph-hello.cgi/chunks').status_is(200).content_is('onetwo')

        # The chunks without their sizes, with the length of the whole response when it comes at once
        status, length, encoding, body = raw(t, 'GET', '/lite/nph-hello.cgi/chunks')
        is_deeply_ok((status, body), (200, b'onetwo'), 'chunks without their sizes')
        ok((length, encoding) in (('6', None), (None, 'chunked')), 'length or chunks')
        t.get_ok('/lite/nph-hello.cgi/gone').status_is(410).content_is('gone')
        t.get_ok('/lite/nph-hello.cgi/missing').status_is(404)

done_testing()
