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
import datetime
import io
import json
import re
import time
import zoneinfo


lite.log.level = 'fatal'

tmp = tempdir()


def application():
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/', lambda c: c.render(text='Hello!'))
    app.routes.get('/assets/app.css', lambda c: c.render(text='body {}', format='css'))
    return app


def logged(t, *args, **kwargs):
    # The lines that a request writes to the standard output, once the transaction of the server has finished, after
    # the plugin, which subscribes to the event finish first, so that a request that writes nothing does not wait
    finished = []
    t.app.hook('after_build_tx', lambda tx, app: tx.on('finish', lambda tx: finished.append(tx)))
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        t.get_ok(*args, **kwargs)
        deadline = steady_time() + 5
        while not finished and steady_time() < deadline:
            Pyjo.IOLoop.timer(0.01, lambda loop: None)
            Pyjo.IOLoop.one_tick()
    return [line for line in stdout.getvalue().splitlines() if not re.match(r'\s*(?:not )?ok ', line)]


def written(path, count=1):
    # The lines of a file, once there are as many
    deadline = steady_time() + 5
    while (not path.is_file or len(path.slurp().splitlines()) < count) and steady_time() < deadline:
        Pyjo.IOLoop.timer(0.01, lambda loop: None)
        Pyjo.IOLoop.one_tick()
    content = path.slurp().decode()
    path.spew('')
    return content.splitlines()


COMBINED = r'^127\.0\.0\.1 - - \[\d\d/[A-Z][a-z]{2}/\d{4}:\d\d:\d\d:\d\d [+-]\d{4}\] '

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

    # A file, in a format of LogFormat of Apache, with the time of the response in milliseconds
    path = tmp.child('access.log').spew('')
    app = application()
    app.plugin('AccessLog', log=path.to_str(), format='%h %t "%r" %>s %b %{ms}T')
    Pyjo.Test.Pyjo.new(app).get_ok('/')
    like_ok(written(path)[0], COMBINED.replace(' - - ', ' ') + r'"GET / HTTP/1\.1" 200 6 \d+$', 'file of LogFormat')

    # A file of each day in UTC
    app = application()
    app.plugin('AccessLog', log=tmp.child('access-%Y-%m-%d.log').to_str(), tz='UTC')
    Pyjo.Test.Pyjo.new(app).get_ok('/')
    path = tmp.child(datetime.datetime.now(datetime.UTC).strftime('access-%Y-%m-%d.log'))
    like_ok(written(path)[0], r' \+0000\] "GET / HTTP/1\.1" 200 6 ', 'file of the day in UTC')

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

    app = application()
    app.plugin('AccessLog', format='%h %t "%r" %>s %b %D "%{X-Request-ID}i"')
    t = Pyjo.Test.Pyjo.new(app)
    line = logged(t, '/', {'X-Request-ID': 'f00d'})[0]
    like_ok(line, COMBINED.replace(' - - ', ' ') + r'"GET / HTTP/1\.1" 200 6 \d+ "f00d"$', 'LogFormat')

    app = application()
    throws_ok(
        lambda: app.plugin('AccessLog', format='%h %400,501{User-Agent}i'),
        re.compile(r'^Unknown directive of the access log'),
        'statuses of Apache',
    )

    app = application()
    app.plugin(
        'AccessLog',
        format={
            'client': '%h',
            'request': '%m %U%q',
            'status': '%>s',
            'bytes': '%B',
            'ms': '%{ms}T',
            'request_id': '%{X-Request-ID}i',
            'http': {'user_agent': '%{User-Agent}i', 'referrer': '%{Referer}i'},
            'service': 'myapp',
        },
    )
    t = Pyjo.Test.Pyjo.new(app)
    record = json.loads(logged(t, '/?q=1', {'User-Agent': 'curl/8.7.1'})[0])
    is_deeply_ok(list(record)[:5], ['time', 'level', 'severity', 'message', 'pid'], 'fields of Pyjo.Log')
    is_ok(record['message'], 'GET /?q=1 200', 'message of a dict')
    ok(isinstance(record.pop('ms'), int), 'time of the response')
    is_deeply_ok(
        {name: record[name] for name in list(record)[5:]},
        {
            'client': '127.0.0.1',
            'request': 'GET /?q=1',
            'status': 200,
            'bytes': 6,
            'request_id': None,
            'http': {'user_agent': 'curl/8.7.1', 'referrer': None},
            'service': 'myapp',
        },
        'fields of a dict',
    )

with subtest('client'):
    app = application()
    app.plugin('AccessLog', client='X-Real-IP')
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/', {'X-Real-IP': '203.0.113.7'})[0], r'^203\.0\.113\.7 ', 'header')

    app = application()
    app.plugin('AccessLog', client=lambda tx: tx.req.headers.header('Fly-Client-IP'))
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/', {'Fly-Client-IP': '203.0.113.8'})[0], r'^203\.0\.113\.8 ', 'function')

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
    app.plugin('AccessLog', format='%h %t "%r" %>s %b %{ms}T')
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/')[0], r'" 200 6 \d+$', 'LogFormat')

    app = application()
    app.plugin('AccessLog', format={'client': '%h', 'status': '%>s', 'request_id': '%{X-Request-ID}i'})
    t = Pyjo.Test.Pyjo.new(app)
    record = json.loads(logged(t, '/', {'X-Request-ID': 'f00d'})[0])
    is_deeply_ok([record['client'], record['status'], record['request_id']], ['127.0.0.1', 200, 'f00d'], 'dict')

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
    app.plugin('AccessLog', log=tmp.child('myapp', 'access-%Y-%m-%d.log').to_str())
    Pyjo.Test.Pyjo.new(app).get_ok('/')
    like_ok(written(tmp.child('myapp', time.strftime('access-%Y-%m-%d.log')))[0], COMBINED, 'file of the day')

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

with subtest('tz'):
    app = application()
    app.plugin('AccessLog', tz='UTC', format='%t')
    t = Pyjo.Test.Pyjo.new(app)
    like_ok(logged(t, '/')[0], r' \+0000\]$', 'UTC')

    try:
        zoneinfo.ZoneInfo('Europe/Warsaw')
    except zoneinfo.ZoneInfoNotFoundError:
        skip('no time zone database, as on Windows without tzdata', 1)
    else:
        app = application()
        app.plugin('AccessLog', tz='Europe/Warsaw', format='%t')
        t = Pyjo.Test.Pyjo.new(app)
        like_ok(logged(t, '/')[0], r' \+0[12]00\]$', 'name')

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
