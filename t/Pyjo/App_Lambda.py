import Pyjo.App.Lambda
import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.Test import *

import base64
import os
import re
import sys
import time


if os.name == 'nt':
    plan(skip_all='Lambda functions run in processes whose pipes the reactor watches, which Windows does not have')

# The functions of the tests, in their directory, and an application of Pyjoyment on Pyjo.Server.Lambda as one of them
TMP = Pyjo.File.tempdir()
TMP.child('handlers.py').spew(
    b"""import base64
import json
import os
import time

import Pyjo.IOLoop
import Pyjo.Server.Lambda
import Pyjoyment


def echo(event, context):
    names = ('AWS_LAMBDA_FUNCTION_NAME', 'AWS_LAMBDA_FUNCTION_MEMORY_SIZE', '_HANDLER', 'LAMBDA_TASK_ROOT', 'FOO')
    body = {
        'event': event,
        'request_id': context.aws_request_id,
        'arn': context.invoked_function_arn,
        'env': {name: os.environ.get(name) for name in names},
    }
    return {'statusCode': 200, 'headers': {'content-type': 'application/json'}, 'body': json.dumps(body)}


def value(event, context):
    return {'hello': 'world'}


def text(event, context):
    return 'Hello Lambda!'


def binary(event, context):
    body = base64.b64encode(b'\\x89PNG\\x00').decode()
    return {'statusCode': 201, 'headers': {'content-type': 'image/png'}, 'body': body, 'isBase64Encoded': True}


def multi(event, context):
    return {
        'statusCode': 200,
        'headers': {'X-One': 'single', 'X-Two': 'single'},
        'multiValueHeaders': {'X-Two': ['a', 'b']},
        'cookies': ['a=1', 'b=2'],
        'body': 'multi',
    }


def printing(event, context):
    print('Hello from the function')
    return {'statusCode': 200, 'body': 'printed'}


def fail(event, context):
    raise ValueError('Something went wrong')


def invalid(event, context):
    return {'statusCode': 'many'}


def slow(event, context):
    time.sleep(10)
    return {'statusCode': 200, 'body': 'slow'}


def nap(event, context):
    time.sleep(1)
    return {'statusCode': 200, 'body': str(os.getpid())}


def crash(event, context):
    os._exit(3)


def pid(event, context):
    return {'statusCode': 200, 'body': str(os.getpid())}


def generator(event, context):
    yield b'first'
    yield b'second'


def broken_stream(event, context):
    yield b'first'
    raise ValueError('Stream broke')


def stalled(event, context):
    yield b'first'
    time.sleep(10)


# An iterator of the chunks of the response of an HTTP integration, as Pyjo.Server.Lambda streams it
class Integration:
    content_type = 'application/vnd.awslambda.http-integration-response'

    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.chunks)


def split_prelude(event, context):
    return Integration([b'{"statusCode":201,"head', b'ers":{"x-foo":"bar"}}\\x00\\x00\\x00\\x00', b'\\x00\\x00\\x00\\x00body'])


def no_prelude(event, context):
    return Integration([b'no delimiter'])


def bad_prelude(event, context):
    return Integration([b'not json' + b'\\x00' * 8 + b'body'])


app = Pyjoyment.new()
app.log.level = 'fatal'


def index(c):
    c.render(json={'url': c.url_for('/').to_str(), 'path': c.req.url.path.to_abs_str(), 'query': c.param('q'),
                   'body': c.req.body.decode('latin-1'), 'cookie': c.cookie('foo')})


def parts(c):
    c.res.headers.content_type = 'text/plain'
    c.write_chunk(b'one, ')
    Pyjo.IOLoop.timer(0.5, lambda loop: c.write_chunk(b'two', lambda c: c.finish()))


app.routes.get('/parts').to(cb=parts)
app.routes.any('/*rest', {'rest': ''}).to(cb=index)
pyjoyment = Pyjo.Server.Lambda.new(app=app).to_lambda_app()
streaming = Pyjo.Server.Lambda.new(app=app, invoke_mode='RESPONSE_STREAM').to_lambda_app()
"""
)
TMP.child('broken.py').spew(b"raise ImportError('No module named oops')\n")

# A runtime whose streaming response comes in one write, with the error of its trailers after its first chunk
TMP.child('onewrite.py').spew(
    b"""import base64
import http.client
import json
import os
import socket

api = os.environ['AWS_LAMBDA_RUNTIME_API']
host, port = api.split(':')
error = base64.b64encode(json.dumps({'errorMessage': 'Stream broke', 'errorType': 'ValueError'}).encode())
while True:
    connection = http.client.HTTPConnection(api)
    connection.request('GET', '/2018-06-01/runtime/invocation/next')
    res = connection.getresponse()
    res.read()
    id = res.headers['Lambda-Runtime-Aws-Request-Id']
    connection.close()
    request = (
        f'POST /2018-06-01/runtime/invocation/{id}/response HTTP/1.1\\r\\nHost: {api}\\r\\n'
        'Content-Type: application/octet-stream\\r\\nLambda-Runtime-Function-Response-Mode: streaming\\r\\n'
        'Transfer-Encoding: chunked\\r\\n'
        'Trailer: Lambda-Runtime-Function-Error-Type, Lambda-Runtime-Function-Error-Body\\r\\n\\r\\n'
        '5\\r\\nfirst\\r\\n0\\r\\nLambda-Runtime-Function-Error-Type: Unhandled\\r\\n'
        f'Lambda-Runtime-Function-Error-Body: {error.decode()}\\r\\n\\r\\n'
    )
    with socket.create_connection((host, int(port))) as sock:
        sock.sendall(request.encode())
        sock.recv(65536)
"""
)
ROOT = TMP.to_str()


def function(name, **attrs):
    app = Pyjo.App.Lambda.new(function=f'handlers.{name}', task_root=ROOT, **attrs)
    app.log.level = 'fatal'
    return app


def mounted(fcn, path='/fn'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.plugin('Mount', {path: fcn})
    return Pyjo.Test.Pyjo.new(app)


with subtest('Payload format 2.0'):
    with function('echo', env={'FOO': 'bar'}, function_name='myfunction', memory_size=256) as fcn:
        t = mounted(fcn)
        t.get_ok('/fn/hello?a=1&a=2&b=%C3%A9', {'Cookie': 'x=1; y=2', 'X-Foo': 'one'}).status_is(200)
        event = t.tx.res.json('/event')
        is_ok(event['version'], '2.0', 'version')
        is_ok(event['rawPath'], '/fn/hello', 'path with the mount')
        is_ok(event['rawQueryString'], 'a=1&a=2&b=%C3%A9', 'query')
        is_deeply_ok(event['queryStringParameters'], {'a': '1,2', 'b': 'é'}, 'parameters')
        is_deeply_ok(event['cookies'], ['x=1', 'y=2'], 'cookies')
        is_ok(event['headers']['x-foo'], 'one', 'header')
        ok('cookie' not in event['headers'], 'no Cookie header')
        is_ok(event['requestContext']['stage'], 'fn', 'stage of the mount')
        is_ok(event['requestContext']['http']['method'], 'GET', 'method')
        is_ok(event['requestContext']['http']['sourceIp'], '127.0.0.1', 'source address')
        is_ok(event['requestContext']['requestId'], t.tx.res.json('/request_id'), 'id of the request')
        is_ok(event['isBase64Encoded'], False, 'no body')
        is_ok(t.tx.res.json('/arn'), 'arn:aws:lambda:us-east-1:123456789012:function:myfunction', 'ARN')
        env = t.tx.res.json('/env')
        is_ok(env['AWS_LAMBDA_FUNCTION_NAME'], 'myfunction', 'AWS_LAMBDA_FUNCTION_NAME')
        is_ok(env['AWS_LAMBDA_FUNCTION_MEMORY_SIZE'], '256', 'AWS_LAMBDA_FUNCTION_MEMORY_SIZE')
        is_ok(env['_HANDLER'], 'handlers.echo', '_HANDLER')
        is_ok(os.path.realpath(env['LAMBDA_TASK_ROOT']), os.path.realpath(ROOT), 'LAMBDA_TASK_ROOT')
        is_ok(env['FOO'], 'bar', 'variable of the attribute')

        # A body of text, and one in Base64
        t.post_ok('/fn', {'Content-Type': 'application/json'}, b'{"a":1}').status_is(200)
        is_ok(t.tx.res.json('/event/body'), '{"a":1}', 'text')
        is_ok(t.tx.res.json('/event/isBase64Encoded'), False, 'not in Base64')
        is_ok(t.tx.res.json('/event/rawPath'), '/fn', 'path of the mount')
        t.post_ok('/fn', {'Content-Type': 'application/octet-stream'}, b'\x00\xff').status_is(200)
        is_ok(t.tx.res.json('/event/body'), base64.b64encode(b'\x00\xff').decode(), 'binary')
        is_ok(t.tx.res.json('/event/isBase64Encoded'), True, 'in Base64')

    # Not mounted, as the default stage
    with function('echo') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/foo').status_is(200).json_is('/event/rawPath', '/foo').json_is(
            '/event/requestContext/stage', '$default'
        )

with subtest('Payload format 1.0'):
    with function('echo', payload='1.0') as fcn:
        t = mounted(fcn)
        t.get_ok('/fn/hello?a=1&a=2&b=%C3%A9', {'X-Foo': 'one'}).status_is(200)
        event = t.tx.res.json('/event')
        is_ok(event['version'], '1.0', 'version')
        is_ok(event['path'], '/hello', 'path without the stage')
        is_ok(event['httpMethod'], 'GET', 'method')
        is_ok(event['requestContext']['path'], '/fn/hello', 'path with the stage')
        is_ok(event['requestContext']['stage'], 'fn', 'stage')
        is_deeply_ok(event['queryStringParameters'], {'a': '2', 'b': 'é'}, 'parameters')
        is_deeply_ok(event['multiValueQueryStringParameters'], {'a': ['1', '2'], 'b': ['é']}, 'parameters')
        is_ok(event['headers']['X-Foo'], 'one', 'header')
        is_deeply_ok(event['multiValueHeaders']['X-Foo'], ['one'], 'header of multiple values')
        is_ok(event['pathParameters']['proxy'], 'hello', 'proxy')

with subtest('Application Load Balancer'):
    with function('echo', payload='alb') as fcn:
        t = mounted(fcn)
        t.get_ok('/fn/hello?a=1&a=2&b=%C3%A9', {'X-Foo': 'one'}).status_is(200)
        event = t.tx.res.json('/event')
        ok('elb' in event['requestContext'], 'target group')
        is_ok(event['path'], '/fn/hello', 'whole path')
        is_deeply_ok(event['queryStringParameters'], {'a': '2', 'b': '%C3%A9'}, 'parameters as they were sent')
        is_ok(event['headers']['x-foo'], 'one', 'header in lower case')
        ok('multiValueHeaders' not in event, 'no headers of multiple values')
    with function('echo', payload='alb', multi_value_headers=True) as fcn:
        t = mounted(fcn)
        t.get_ok('/fn/hello?a=1&a=2', {'X-Foo': 'one'}).status_is(200)
        event = t.tx.res.json('/event')
        is_deeply_ok(event['multiValueQueryStringParameters'], {'a': ['1', '2']}, 'parameters of multiple values')
        is_deeply_ok(event['multiValueHeaders']['x-foo'], ['one'], 'headers of multiple values')
        ok('headers' not in event, 'no headers of one value')

with subtest('Application of Pyjoyment on Pyjo.Server.Lambda'):
    for payload, url in (('2.0', '/fn'), ('1.0', '/fn'), ('alb', '/')):
        with function('pyjoyment', payload=payload) as fcn:
            t = mounted(fcn)
            t.get_ok('/fn/foo/bar?q=1', {'Cookie': 'foo=baz'}).status_is(200)
            t.json_is('/path', '/fn/foo/bar' if payload == 'alb' else '/foo/bar', f'path of {payload}')
            t.json_is('/url', url, f'base path of {payload}')
            t.json_is('/query', '1', f'query of {payload}')
            t.json_is('/cookie', 'baz', f'cookie of {payload}')
            t.post_ok('/fn', {'Content-Type': 'text/plain'}, b'Hello!').status_is(200)
            t.json_is('/body', 'Hello!', f'body of {payload}')

with subtest('Responses'):
    with function('value') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/').status_is(200).content_type_is('application/json').json_is({'hello': 'world'})
    with function('text') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/').status_is(200).content_is('Hello Lambda!')
    with function('binary') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/').status_is(201).content_type_is('image/png')
        is_ok(t.tx.res.body, b'\x89PNG\x00', 'body in Base64')
    with function('multi') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/').status_is(200).header_is('X-One', 'single').content_is('multi')
        is_deeply_ok(t.tx.res.headers.every_header('X-Two'), ['a', 'b'], 'headers of multiple values')
        is_deeply_ok(t.tx.res.headers.every_header('Set-Cookie'), ['a=1', 'b=2'], 'cookies')

    # A value without statusCode is not a response of the format 1.0
    with function('value', payload='1.0') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502).content_is('Bad Gateway')
        like_ok(str(messages), r'Lambda function returned no statusCode', 'right error')

with subtest('Streaming responses'):
    with function('streaming') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)

        # The chunks of the response as they come
        times = []

        @t.ua.once('start')
        def start(ua, tx):
            tx.res.content.on('read', lambda content, chunk: times.append((time.time(), bytes(chunk))))

        t.get_ok('/parts').status_is(200).content_type_is('text/plain').content_is('one, two')
        received, at = b'', {}
        for when, chunk in times:
            received += chunk
            for part in (b'one, ', b'two'):
                if part in received:
                    at.setdefault(part, when)
        ok(at[b'two'] - at[b'one, '] >= 0.4, 'chunks as they come')

        # The headers and the cookies of the prelude, and the next invocation
        t.get_ok('/foo?q=1', {'Cookie': 'foo=baz'}).status_is(200).json_is('/path', '/foo').json_is('/cookie', 'baz')
        t.head_ok('/parts').status_is(200).content_is('')

    with function('streaming') as fcn:
        t = mounted(fcn)
        t.get_ok('/fn/parts').status_is(200).content_is('one, two')

    # Any stream, of its content type
    with function('generator') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/').status_is(200).content_type_is('application/octet-stream').content_is('firstsecond')

    # A prelude in several chunks
    with function('split_prelude') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/').status_is(201).header_is('X-Foo', 'bar').content_is('body')

    # A response without its prelude, or with one that is not valid
    with function('no_prelude') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502).content_is('Bad Gateway')
        like_ok(str(messages), r'Lambda function returned no prelude in its streaming response', 'no prelude')
    with function('bad_prelude') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'Lambda function returned an invalid prelude', 'invalid prelude')

    # An error in the middle of the stream closes the connection, and the next invocation goes on
    with function('broken_stream') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            tx = t.ua.get('/')
        # The user agent takes a response that is cut for one without an error, as Mojolicious does
        is_ok(tx.res.code, 200, 'status of the stream')
        is_ok(tx.res.body, b'first', 'body before the error')
        ok(not tx.res.content.is_finished, 'cut before its last chunk')
        like_ok(str(messages), r'Lambda function error: ValueError: Stream broke', 'error of the trailers')
        with fcn.log.capture('error'):
            tx = t.ua.get('/')
        is_ok(tx.res.code, 200, 'next invocation')

    # An error that comes in the same read as the first chunk, which the client gets before the connection closes
    with Pyjo.App.Lambda.new(command=[sys.executable, 'onewrite.py'], task_root=ROOT) as fcn:
        fcn.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            tx = t.ua.get('/')
        is_ok(tx.res.code, 200, 'status of the stream')
        is_ok(tx.res.body, b'first', 'body before the error')
        ok(not tx.res.content.is_finished, 'cut before its last chunk')
        like_ok(str(messages), r'Lambda function error: ValueError: Stream broke', 'error of the trailers')
        with fcn.log.capture('error'):
            tx = t.ua.get('/')
        is_ok(tx.res.body, b'first', 'next invocation')

    # The timeout of the function goes on while it streams
    with function('stalled', timeout=1) as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            tx = t.ua.get('/')
        is_ok(tx.res.body, b'first', 'body before the timeout')
        ok(not tx.res.content.is_finished, 'cut before its last chunk')
        like_ok(str(messages), r'Lambda function timed out after 1 seconds', 'timeout')

with subtest('Output'):
    with function('printing') as fcn:
        with fcn.log.capture('info') as messages:
            Pyjo.Test.Pyjo.new(fcn).get_ok('/').status_is(200).content_is('printed')
            Pyjo.IOLoop.timer(0.2, lambda loop: loop.stop())
            Pyjo.IOLoop.start()
        like_ok(str(messages), r'Lambda function: Hello from the function', 'output logged')

with subtest('Errors'):
    with function('fail') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502).content_is('Bad Gateway')
        like_ok(str(messages), r'Lambda function error: ValueError: Something went wrong', 'error of the function')
        t.get_ok('/').status_is(502)

    with function('invalid') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'Lambda function returned an invalid response', 'invalid response')

    with Pyjo.App.Lambda.new(function='broken.handler', task_root=ROOT) as fcn:
        fcn.log.level = 'fatal'
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'initialization error: Runtime.ImportModuleError: No module named oops', 'init error')
        like_ok(str(messages), r'Lambda function ended with status 1', 'process ended')
        t.get_ok('/').status_is(502)

    # A process that ends during an invocation, and a new one for the next
    with function('crash') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'Lambda function ended with status 3', 'process ended')

    # An invocation that takes longer than the timeout, whose process is killed, and a new one for the next
    with function('slow', timeout=0.5) as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        with fcn.log.capture('error') as messages:
            t.get_ok('/').status_is(502)
        like_ok(str(messages), r'Lambda function timed out after 0\.5 seconds', 'timed out')

    throws_ok(
        lambda: Pyjo.App.Lambda.new().handler(Pyjo.Transaction.HTTP.new()),
        re.compile(r'^No Lambda function'),
        'no function',
    )
    throws_ok(
        lambda: Pyjo.App.Lambda.new(function='a.b', payload='3.0').handler(Pyjo.Transaction.HTTP.new()),
        re.compile(r'^Invalid Lambda payload format "3\.0"'),
        'invalid payload format',
    )

with subtest('Process kept'):
    with function('pid') as fcn:
        t = Pyjo.Test.Pyjo.new(fcn)
        first = t.get_ok('/').status_is(200).tx.res.text
        t.get_ok('/').status_is(200).content_is(first)
        isnt_ok(first, str(os.getpid()), 'a process of its own')

        # The child of a fork starts its own, and leaves the one of its parent
        if not hasattr(os, 'fork'):
            skip('no fork', 3)
        else:
            pid = os.fork()
            if pid == 0:
                code = 1
                try:
                    tx = t.ua.get('/')
                    code = 0 if tx.res.code == 200 and tx.res.text not in ('', first) else 1
                    fcn.close()
                finally:
                    sys.stdout.flush()
                    os._exit(code)
            status = []

            def reap(loop):
                if (waited := os.waitpid(pid, os.WNOHANG))[0]:
                    status.append(os.waitstatus_to_exitcode(waited[1]))
                    loop.stop()

            waiting = [Pyjo.IOLoop.recurring(0.01, reap), Pyjo.IOLoop.timer(30, lambda loop: loop.stop())]
            Pyjo.IOLoop.start()
            for id in waiting:
                Pyjo.IOLoop.remove(id)
            is_deeply_ok(status, [0], 'a process of the child')
            t.get_ok('/').status_is(200).content_is(first)
            is_ok(t.tx.res.text, first, 'the process of the parent')

with subtest('Process kept while the child of a fork runs its event loop'):
    # The runtime client of the parent asks for its next invocation, which the child does not read first
    if not hasattr(os, 'fork'):
        skip('no fork', 3)
    else:
        with function('pid', timeout=5) as fcn:
            t = Pyjo.Test.Pyjo.new(fcn)
            first = t.get_ok('/').status_is(200).tx.res.text
            pid = os.fork()
            if pid == 0:
                try:
                    Pyjo.IOLoop.timer(1, lambda loop: loop.stop())
                    Pyjo.IOLoop.start()
                finally:
                    sys.stdout.flush()
                    os._exit(0)
            time.sleep(1.5)
            os.waitpid(pid, 0)
            start = time.monotonic()
            t.get_ok('/').status_is(200).content_is(first)
            ok(time.monotonic() - start < 4, 'without the timeout of the function')

with subtest('Command'):
    command = [sys.executable, '-m', 'Pyjo.Server.Lambda', 'handlers.text']
    checkout = Pyjo.File.curfile().dirname().dirname().dirname().to_abs().to_str()
    with Pyjo.App.Lambda.new(command=command, task_root=ROOT, env={'PYTHONPATH': checkout}) as fcn:
        fcn.log.level = 'fatal'
        Pyjo.Test.Pyjo.new(fcn).get_ok('/').status_is(200).content_is('Hello Lambda!')

with subtest('Graceful stop'):
    # The runtime client waits for its next invocation in a request to the Runtime API, which the graceful stop of the
    # event loop ends, with the process, once the invocation of the request in progress has been answered
    with function('nap') as fcn:
        app = Pyjoyment.new()
        app.log.level = 'fatal'
        app.plugin('Mount', {'/fn': fcn})
        with Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], silent=True).start() as daemon:
            url = f'http://127.0.0.1:{daemon.ports()[0]}/fn'
            with Pyjo.UserAgent.new() as ua:
                results = []

                def first(tx):
                    results.append(tx.res.text)
                    # The graceful stop while the function answers the second request
                    ua.get_p(url, {'Connection': 'close'}).then(lambda tx: results.append(tx.res.text))
                    Pyjo.IOLoop.timer(0.3, lambda loop: loop.stop_gracefully())

                ua.get_p(url, {'Connection': 'close'}).then(first)
                timeout = Pyjo.IOLoop.timer(15, lambda loop: (results.append('timeout'), loop.stop()))
                start = time.monotonic()
                Pyjo.IOLoop.start()
                Pyjo.IOLoop.remove(timeout)
                is_ok(len(results), 2, 'request in progress answered')
                ok('timeout' not in results, 'stopped')
                ok(time.monotonic() - start < 10, 'without the timeout of the test')
                is_ok(len(set(results)), 1, 'by the same process')
        Pyjo.IOLoop.reset()

        # The next request starts a new process
        t = Pyjo.Test.Pyjo.new(fcn)
        t.get_ok('/').status_is(200)
        isnt_ok(t.tx.res.text, results[0], 'a new process after the stop')

done_testing()
