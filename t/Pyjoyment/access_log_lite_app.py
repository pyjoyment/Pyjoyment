import os


os.environ['PYJO_MODE'] = 'development'

import Pyjo.IOLoop
import Pyjo.Log
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.File import tempdir
from Pyjo.Test import *
from Pyjo.Util import steady_time
from Pyjoyment.Lite import app, get, plugin, websocket

import contextlib
import io
import json
import re


# Not in Mojolicious: Pyjoyment.Plugin.AccessLog, the access log of a server of production

app.log.level = 'fatal'

tmp = tempdir()
path = tmp.child('access.log').spew('')

plugin('AccessLog', log=path.to_str())
plugin('Health')

get('/', {'text': 'Hello!'})


@get('/chunked')
def chunked(c):
    c.write_chunk(b'abc', lambda c: c.write_chunk(b'defgh', lambda c: c.write_chunk(b'')))


@get('/never')
def never(c):
    c.render_later()


@websocket('/echo')
def echo(c):
    c.on('message', lambda c, msg: c.send(f'echo: {msg}'))


embedded = Pyjoyment.new()
embedded.log.level = 'fatal'
embedded.routes.get('/hello', lambda c: c.render(text='Embedded!'))
plugin('Mount', {'/embedded': embedded})


def lines(count=1):
    # The lines written since the last call, once there are as many, as the server writes one after its response
    deadline = steady_time() + 5
    while len(path.slurp().splitlines()) < count and steady_time() < deadline:
        Pyjo.IOLoop.timer(0.01, lambda loop: None)
        Pyjo.IOLoop.one_tick()
    content = path.slurp().decode()
    path.spew('')
    return content.splitlines()


def application(**conf):
    # An application of its own, with the options of the plugin
    other = Pyjoyment.new()
    other.log.level = 'fatal'
    other.plugin('AccessLog', conf)
    other.plugin('Health')
    other.routes.get('/', lambda c: c.render(text='Hello!'))
    other.routes.get('/missing', lambda c: c.helpers.reply.not_found())
    return other


COMBINED = r'^127\.0\.0\.1 - - \[\d\d/[A-Z][a-z]{2}/\d{4}:\d\d:\d\d:\d\d \+0000\] '

t = Pyjo.Test.Pyjo.new()

with subtest('Combined'):
    lines(0)
    t.get_ok('/?q=1', {'Referer': 'https://example.com/', 'User-Agent': 'Test/1.0'}).status_is(200)
    (line,) = lines()
    like_ok(line, COMBINED + r'"GET /\?q=1 HTTP/1\.1" 200 6 "https://example\.com/" "Test/1\.0"$', 'line of a route')

    t.get_ok('/chunked').status_is(200).content_is('abcdefgh')
    like_ok(lines()[0], r'"GET /chunked HTTP/1\.1" 200 23 "-" "Pyjoyment \(Python\)"$', 'chunked, with its framing')

    t.get_ok('/pyjo/bootstrap/bootstrap.css').status_is(200)
    size = len(t.tx.res.body)
    like_ok(lines()[0], rf'"GET /pyjo/bootstrap/bootstrap\.css HTTP/1\.1" 200 {size} ', 'static file')

    t.get_ok('/pyjo/bootstrap/bootstrap.css', {'Range': 'bytes=0-9'}).status_is(206)
    like_ok(lines()[0], r'" 206 10 ', 'range of a static file')

    t.get_ok('/missing').status_is(404)
    like_ok(lines()[0], r'"GET /missing HTTP/1\.1" 404 \d+ ', 'not found')

    t.get_ok('/embedded/hello').status_is(200).content_is('Embedded!')
    like_ok(lines()[0], r'"GET /embedded/hello HTTP/1\.1" 200 9 ', 'mounted application')

    t.head_ok('/').status_is(200)
    like_ok(lines()[0], r'"HEAD / HTTP/1\.1" 200 - ', 'no body')

    # A header of the bytes of UTF-8, as the characters of Latin-1
    t.post_ok('/', {'User-Agent': 'Evil "agent" \\ ' + 'ż'.encode().decode('latin-1')}).status_is(404)
    like_ok(lines()[0], r'"Evil \\x22agent\\x22 \\x5C \\xC5\\xBC"$', 'escaped')

with subtest('WebSocket'):
    lines(0)
    t.websocket_ok('/echo').send_ok('hello').message_ok().message_is('echo: hello').finish_ok()
    like_ok(lines()[0], COMBINED + r'"GET /echo HTTP/1\.1" 101 - ', 'handshake')

with subtest('Closed before the response'):
    lines(0)
    t.ua.inactivity_timeout = 0.2
    tx = t.ua.get('/never')
    is_ok(tx.error['message'], 'Inactivity timeout', 'right error')
    t.ua.inactivity_timeout = 20
    like_ok(lines()[0], r'"GET /never HTTP/1\.1" 499 - ', 'client closed')

with subtest('Probes of Health'):
    lines(0)
    t.get_ok('/livez').status_is(200)
    t.get_ok('/readyz').status_is(200)
    t.get_ok('/healthz/ping').status_is(200)
    t.get_ok('/').status_is(200)
    logged = lines()
    is_ok(len(logged), 1, 'left out')
    like_ok(logged[0], r'"GET / HTTP', 'only the other request')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), exclude=[]))
    t2.get_ok('/livez').status_is(200)
    like_ok(lines()[0], r'"GET /livez HTTP/1\.1" 200 2 ', 'logged with an empty exclude')

with subtest('Exclude'):
    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), exclude=['/missing', re.compile(r'^/static/')]))
    lines(0)
    t2.get_ok('/missing').status_is(404)
    t2.get_ok('/missing/more').status_is(404)
    t2.get_ok('/static/app.css').status_is(404)
    t2.get_ok('/').status_is(200)
    t2.get_ok('/missingx').status_is(404)
    t2.get_ok('/livez').status_is(200)
    logged = lines(3)
    is_ok(len(logged), 3, 'paths left out')
    like_ok(logged[1], r'"GET /missingx ', 'not a path under a path')
    like_ok(logged[2], r'"GET /livez ', 'probes of Health')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), exclude=lambda tx: tx.req.method == 'HEAD'))
    t2.head_ok('/').status_is(200)
    t2.get_ok('/').status_is(200)
    logged = lines()
    is_ok(len(logged), 1, 'function')
    like_ok(logged[0], r'"GET / ', 'not left out')

with subtest('Status'):
    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), status=400))
    lines(0)
    t2.get_ok('/').status_is(200)
    t2.get_ok('/missing').status_is(404)
    logged = lines()
    is_ok(len(logged), 1, 'errors only')
    like_ok(logged[0], r'" 404 ', 'error')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), status=[200]))
    t2.get_ok('/').status_is(200)
    t2.get_ok('/missing').status_is(404)
    logged = lines()
    is_ok(len(logged), 1, 'statuses')
    like_ok(logged[0], r'" 200 ', 'status')

with subtest('Client'):
    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), client='X-Envoy-External-Address'))
    lines(0)
    t2.get_ok('/', {'X-Envoy-External-Address': '203.0.113.7', 'X-Forwarded-For': '198.51.100.1'}).status_is(200)
    like_ok(lines()[0], r'^203\.0\.113\.7 - - ', 'header')
    t2.get_ok('/').status_is(200)
    like_ok(lines()[0], r'^127\.0\.0\.1 - - ', 'remote address without the header')

    other = application(log=path.to_str())
    other.hook('after_build_tx', lambda tx, app: setattr(tx.req, 'reverse_proxy', True))
    t2 = Pyjo.Test.Pyjo.new(other)
    t2.get_ok('/', {'X-Forwarded-For': '198.51.100.1, 203.0.113.7'}).status_is(200)
    like_ok(lines()[0], r'^203\.0\.113\.7 - - ', 'reverse proxy')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), client=lambda tx: 'client'))
    t2.get_ok('/').status_is(200)
    like_ok(lines()[0], r'^client - - ', 'function')

with subtest('Formats'):
    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format='common'))
    lines(0)
    t2.get_ok('/', {'Referer': 'https://example.com/'}).status_is(200)
    like_ok(lines()[0], COMBINED + r'"GET / HTTP/1\.1" 200 6$', 'common')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format='%h %l %u %t "%r" %>s %b'))
    t2.get_ok('/', {'Referer': 'https://example.com/'}).status_is(200)
    like_ok(lines()[0], COMBINED + r'"GET / HTTP/1\.1" 200 6$', 'common of LogFormat')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format='%%|%a|%b|%B|%m|%U|%q|%H|%s|%<s|%P|%l|%u'))
    t2.get_ok('/?a=b').status_is(200)
    is_deeply_ok(lines(), [f'%|127.0.0.1|6|6|GET|/|?a=b|HTTP/1.1|200|200|{os.getpid()}|-|-'], 'directives')
    t2.head_ok('/').status_is(200)
    is_deeply_ok(lines(), [f'%|127.0.0.1|-|0|HEAD|/||HTTP/1.1|200|200|{os.getpid()}|-|-'], 'directives without a body')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format='%u %v %V %p'))
    t2.get_ok(f'http://sri:secr3t@localhost:{t2.ua.server.url().port}/').status_is(200)
    is_deeply_ok(lines(), [f'sri localhost localhost {t2.ua.server.url().port}'], 'user, host and port')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format='"%{X-Request-ID}i" "%{Content-Type}o" "%{foo}C"'))
    t2.get_ok('/', {'X-Request-ID': 'abc"1', 'Cookie': 'foo=bar'}).status_is(200)
    is_deeply_ok(lines(), ['"abc\\x221" "text/html;charset=UTF-8" "bar"'], 'headers and cookie')
    t2.get_ok('/').status_is(200)
    is_deeply_ok(lines(), ['"-" "text/html;charset=UTF-8" "-"'], 'missing')

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format='%D %T %{s}T %{ms}T %{us}T'))
    t2.get_ok('/').status_is(200)
    like_ok(lines()[0], r'^\d+ \d+ \d+ \d+ \d+$', 'time of the response')

    format = '%{%Y-%m-%dT%H:%M:%SZ}t %{sec}t %{msec}t %{usec}t %{msec_frac}t %{usec_frac}t %{end:sec}t %{begin:%Y}t'
    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format=format))
    t2.get_ok('/').status_is(200)
    line = lines()[0]
    like_ok(line, r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ \d{10} \d{13} \d{16} \d{3} \d{6} \d{10} \d{4}$', 'time')

    def own(tx, entry):
        return f'{entry["method"]} {entry["path"]} {entry["status"]} {entry["bytes"]} {entry["time"].epoch > 0}'

    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format=own))
    t2.get_ok('/?a=b').status_is(200)
    is_deeply_ok(lines(), ['GET /?a=b 200 6 True'], 'function')

    throws_ok(
        lambda: application(format='apache'),
        re.compile(r'^Unknown format "apache" of the access log, not one of combined, common, json nor of LogFormat'),
        'unknown format',
    )
    throws_ok(
        lambda: application(format='%h %Z'), re.compile(r'^Unknown directive "%Z" of the access log'), 'directive'
    )
    throws_ok(
        lambda: application(format='%{x}h'), re.compile(r'^Unknown directive "%\{x\}h" of the access log'), 'name'
    )
    throws_ok(lambda: application(format='%{fs}T'), re.compile(r'^Unknown directive "%\{fs\}T"'), 'unit')
    throws_ok(
        lambda: application(format='%h %400{User-Agent}i'),
        re.compile(r'^Unknown directive of the access log in "%h %400\{User-Agent\}i"'),
        'statuses of Apache',
    )

with subtest('JSON'):
    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format='json'))
    lines(0)
    t2.get_ok('/?q=1', {'Referer': 'https://example.com/', 'User-Agent': 'Test/1.0'}).status_is(200)
    (line,) = lines()
    record = json.loads(line)
    like_ok(record['time'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$', 'time')
    is_ok(record['level'], 'info', 'level')
    is_ok(record['severity'], 'INFO', 'severity')
    is_ok(record['message'], 'GET /?q=1 200', 'message')
    is_ok(record['pid'], os.getpid(), 'pid')
    is_ok(record['client'], '127.0.0.1', 'client')
    is_ok(record['method'], 'GET', 'method')
    is_ok(record['path'], '/?q=1', 'path')
    is_ok(record['protocol'], 'HTTP/1.1', 'protocol')
    is_ok(record['status'], 200, 'status')
    is_ok(record['bytes'], 6, 'bytes')
    is_ok(record['referrer'], 'https://example.com/', 'referrer')
    is_ok(record['user_agent'], 'Test/1.0', 'user agent')
    ok(isinstance(record['duration'], float), 'duration')
    request = record['httpRequest']
    is_ok(request['requestMethod'], 'GET', 'request method')
    like_ok(request['requestUrl'], r'^http://127\.0\.0\.1:\d+/\?q=1$', 'request URL')
    is_ok(request['status'], 200, 'status of the request')
    is_ok(request['responseSize'], '6', 'response size')
    is_ok(request['userAgent'], 'Test/1.0', 'user agent of the request')
    is_ok(request['remoteIp'], '127.0.0.1', 'remote IP')
    is_ok(request['referer'], 'https://example.com/', 'referer')
    like_ok(request['latency'], r'^\d+\.\d{6}s$', 'latency')
    is_ok(request['protocol'], 'HTTP/1.1', 'protocol of the request')

    t2.head_ok('/').status_is(200)
    record = json.loads(lines()[0])
    is_ok(record['referrer'], None, 'no referrer')
    ok('referer' not in record['httpRequest'], 'no referer of the request')

    os.environ['PYJO_LOG_FORMAT'] = 'json'
    try:
        t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str()))
    finally:
        del os.environ['PYJO_LOG_FORMAT']
    t2.get_ok('/').status_is(200)
    is_ok(json.loads(lines()[0])['message'], 'GET / 200', 'default with PYJO_LOG_FORMAT')

with subtest('Fields of JSON'):
    lines(0)
    format = {
        'status': '%>s',
        'size': '%b',
        'zero': '%B',
        'header': '%{X-Request-ID}i',
        'text': '%m %{X-Request-ID}i "%{X-Other}i"',
        'percent': '%%',
        'nested': {'deeper': {'method': '%m'}},
        'function': lambda tx, entry: entry['path'].upper(),
        'constant': 42,
        'none': None,
        'pid': '%s',
    }
    t2 = Pyjo.Test.Pyjo.new(application(log=path.to_str(), format=format))
    t2.head_ok('/', {'X-Request-ID': 'a"b'}).status_is(200)
    record = json.loads(lines()[0])
    is_ok(record['message'], 'HEAD / 200', 'message')
    is_ok(record['pid'], os.getpid(), 'fields of Pyjo.Log are not replaced')
    record = {name: record[name] for name in list(record)[5:]}
    is_deeply_ok(
        record,
        {
            'status': 200,
            'size': None,
            'zero': 0,
            'header': 'a"b',
            'text': 'HEAD a"b "-"',
            'percent': '%',
            'nested': {'deeper': {'method': 'HEAD'}},
            'function': '/',
            'constant': 42,
            'none': None,
        },
        'fields',
    )

    log = Pyjo.Log.new()
    t2 = Pyjo.Test.Pyjo.new(application(log=log, format={'status': '%>s', 'agent': '%{User-Agent}i'}))
    with log.capture() as messages:
        t2.get_ok('/').status_is(200)
    like_ok(messages[0], r'\[info\] GET / 200 status=200 agent="Pyjoyment \(Python\)"$', 'fields in a log of text')

    throws_ok(
        lambda: application(format={'nested': {'bad': '%Z'}}),
        re.compile(r'^Unknown directive "%Z" of the access log'),
        'unknown directive of a field',
    )

with subtest('Log'):
    log = Pyjo.Log.new()
    t2 = Pyjo.Test.Pyjo.new(application(log=log))
    with log.capture() as messages:
        t2.get_ok('/').status_is(200)
    like_ok(messages[0], r'\[info\] 127\.0\.0\.1 - - \[.*\] "GET / HTTP/1\.1" 200 6 ', 'line of the log')

    t2 = Pyjo.Test.Pyjo.new(application(log=log, level='debug'))
    with log.capture('info') as messages:
        t2.get_ok('/').status_is(200)
    is_ok(len(messages), 0, 'below the level of the log')
    with log.capture('debug') as messages:
        t2.get_ok('/').status_is(200)
    like_ok(messages[0], r'\[debug\] 127\.0\.0\.1 ', 'level')

    log = Pyjo.Log.new(json=True)
    t2 = Pyjo.Test.Pyjo.new(application(log=log))
    with log.capture() as messages:
        t2.get_ok('/').status_is(200)
    record = json.loads(messages[0])
    is_ok(record['message'], 'GET / 200', 'message of a log of JSON')
    is_ok(record['status'], 200, 'field of a log of JSON')

    t2 = Pyjo.Test.Pyjo.new(application())
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        t2.get_ok('/').status_is(200)
    # The output of the test follows the line
    like_ok(stdout.getvalue(), COMBINED + r'"GET / HTTP/1\.1" 200 6 "-" "Pyjoyment \(Python\)"\n', 'standard output')

done_testing()
