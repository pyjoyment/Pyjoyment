import Pyjo.IOLoop
import Pyjo.Log
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.File import tempdir
from Pyjo.Test import *
from Pyjo.Util import steady_time
from Pyjoyment.Lite import app as lite
from Pyjoyment.Lite import get, plugin

import contextlib
import io
import json
import re


lite.log.level = 'fatal'

tmp = tempdir()


def application():
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/', lambda c: c.render(text='Hello!'))
    app.routes.get('/assets/app.css', lambda c: c.render(text='body {}', format='css'))
    return app


def logged(t, *args, **kwargs):
    # The lines that a request writes to the standard output, once the server has written its response
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        t.get_ok(*args, **kwargs)
        deadline = steady_time() + 5
        while '" ' not in stdout.getvalue() and steady_time() < deadline:
            Pyjo.IOLoop.timer(0.01, lambda loop: None)
            Pyjo.IOLoop.one_tick()
    return [line for line in stdout.getvalue().splitlines() if not re.match(r'\s*(?:not )?ok ', line)]


def written(path, count=1):
    # The lines of a file, once there are as many
    deadline = steady_time() + 5
    while len(path.slurp().splitlines()) < count and steady_time() < deadline:
        Pyjo.IOLoop.timer(0.01, lambda loop: None)
        Pyjo.IOLoop.one_tick()
    content = path.slurp().decode()
    path.spew('')
    return content.splitlines()


COMBINED = r'^127\.0\.0\.1 - - \[\d\d/[A-Z][a-z]{2}/\d{4}:\d\d:\d\d:\d\d \+0000\] '

with subtest('Synopsis'):
    # Pyjoyment
    app = application()
    app.plugin('AccessLog')
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/')[0], COMBINED + r'"GET / HTTP/1\.1" 200 6 "-" "Pyjoyment \(Python\)"$', 'combined')

    # Pyjoyment.Lite
    plugin('AccessLog')
    get('/', {'text': 'Hello!'})
    t = Pyjo.Test.Pyjo.new()
    like_ok(logged(t, '/')[0], COMBINED + r'"GET / HTTP/1\.1" 200 6 ', 'Lite')

    # Lines of JSON, with the client of a header of the gateway, and the errors only
    app = application()
    app.plugin('AccessLog', format='json', client='X-Envoy-External-Address', status=400)
    t = Pyjo.Test.Pyjo.new(app)
    with contextlib.redirect_stdout(io.StringIO()):
        t.get_ok('/', {'X-Envoy-External-Address': '203.0.113.7'})
    (line,) = logged(t, '/missing', {'X-Envoy-External-Address': '203.0.113.7'})
    record = json.loads(line)
    is_ok(record['client'], '203.0.113.7', 'client')
    is_ok(record['status'], 404, 'error')

    # A file, with the time of the response at the end of each line
    path = tmp.child('access.log').spew('')
    app = application()
    app.plugin('AccessLog', log=path.to_str(), duration=True)
    Pyjo.Test.Pyjo.new(app).get_ok('/')
    like_ok(written(path)[0], r'" 200 6 "-" "Pyjoyment \(Python\)" \d+\.\d{3}$', 'file with the duration')

with subtest('Description'):
    app = application()
    app.plugin('AccessLog')
    t = Pyjo.Test.Pyjo.new(app)
    line = logged(t, '/', {'User-Agent': 'Mozilla/5.0 ...'})[0]
    like_ok(line, COMBINED + r'"GET / HTTP/1\.1" 200 6 "-" "Mozilla/5\.0 \.\.\."$', 'line')

with subtest('Formats'):
    app = application()
    app.plugin('AccessLog')
    t = Pyjo.Test.Pyjo.new(app)
    line = logged(t, '/?q=1', {'Referer': 'https://example.com/', 'User-Agent': 'curl/8.7.1'})[0]
    like_ok(line, COMBINED + r'"GET /\?q=1 HTTP/1\.1" 200 6 "https://example\.com/" "curl/8\.7\.1"$', 'combined')

    app = application()
    app.plugin('AccessLog', format='common')
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/?q=1')[0], COMBINED + r'"GET /\?q=1 HTTP/1\.1" 200 6$', 'common')

    app = application()
    app.plugin('AccessLog', format='json')
    t = Pyjo.Test.Pyjo.new(app)
    record = json.loads(logged(t, '/?q=1')[0])
    is_deeply_ok(
        list(record)[:5], ['time', 'level', 'severity', 'message', 'pid'], 'fields of a message of JSON of Pyjo.Log'
    )
    is_ok(record['message'], 'GET /?q=1 200', 'message')

with subtest('client'):
    app = application()
    app.plugin('AccessLog', client='X-Real-IP')
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/', {'X-Real-IP': '203.0.113.7'})[0], r'^203\.0\.113\.7 ', 'header')

    app = application()
    app.plugin('AccessLog', client=lambda tx: tx.req.headers.header('Fly-Client-IP'))
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/', {'Fly-Client-IP': '203.0.113.8'})[0], r'^203\.0\.113\.8 ', 'function')

with subtest('duration'):
    app = application()
    app.plugin('AccessLog', duration=True)
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/')[0], r' \d+\.\d{3}$', 'duration')

with subtest('exclude'):
    app = application()
    app.plugin('AccessLog', exclude=['/livez', '/readyz', re.compile(r'^/assets/')])
    t = Pyjo.Test.Pyjo.new(app)
    is_deeply_ok(logged(t, '/assets/app.css'), [], 'regular expression')

    app = application()
    app.plugin('AccessLog', exclude=lambda tx: tx.req.headers.user_agent == 'kube-probe')
    t = Pyjo.Test.Pyjo.new(app)
    is_deeply_ok(logged(t, '/', {'User-Agent': 'kube-probe'}), [], 'function')

with subtest('format'):
    app = application()
    app.plugin('AccessLog', format='json')
    t = Pyjo.Test.Pyjo.new(app)
    is_ok(json.loads(logged(t, '/')[0])['status'], 200, 'json')

    app = application()
    app.plugin('AccessLog', format=lambda tx, entry: f'{entry["method"]} {entry["path"]} {entry["status"]}')
    t = Pyjo.Test.Pyjo.new(app)
    is_deeply_ok(logged(t, '/'), ['GET / 200'], 'function')

with subtest('level'):
    app = application()
    app.plugin('AccessLog', log=app.log, level='debug')
    t = Pyjo.Test.Pyjo.new(app)
    with app.log.capture('debug') as messages:
        t.get_ok('/')
    like_ok(messages[0], r'\[debug\] 127\.0\.0\.1 - - ', 'level')

with subtest('log'):
    path = tmp.child('myapp', 'access.log')
    path.dirname().make_path()
    path.spew('')
    app = application()
    app.plugin('AccessLog', log=path.to_str())
    Pyjo.Test.Pyjo.new(app).get_ok('/')
    like_ok(written(path)[0], COMBINED, 'file')

    app = application()
    app.plugin('AccessLog', log=app.log)
    t = Pyjo.Test.Pyjo.new(app)
    with app.log.capture('info') as messages:
        t.get_ok('/')
    like_ok(messages[0], r'\[info\] 127\.0\.0\.1 - - ', 'log of the application')

with subtest('status'):
    app = application()
    app.plugin('AccessLog', status=400)
    t = Pyjo.Test.Pyjo.new(app)
    is_deeply_ok(logged(t, '/'), [], 'lowest status')

    app = application()
    app.plugin('AccessLog', status=[404, 499])
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/missing')[0], r'" 404 ', 'statuses')

with subtest('register'):
    app = application()
    plugin = app.plugins.load_plugin('AccessLog')
    plugin.register(app)
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/')[0], COMBINED, 'combined')
    app = application()
    plugin.register(app, {'format': 'json'})
    t = Pyjo.Test.Pyjo.new(app)
    is_ok(json.loads(logged(t, '/')[0])['status'], 200, 'json')

done_testing()
