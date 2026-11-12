import Pyjo.File
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.Test import *
from Pyjoyment.Lite import any, app, get, post, websocket

import os
import re
import subprocess
import sys
import textwrap
import time
import types


# The checkout, of the processes of the examples
ROOT = Pyjo.File.curfile().dirname().dirname().dirname().to_str()

# The application of the examples
app.log.level = 'fatal'
app.defaults(foo='bar')


@get('/welcome')
def welcome(c):
    c.render(text='<div id="message">Hello!</div>', format='html')


@post('/search.json')
def search(c):
    c.res.headers.server = 'Pyjoyment (Python)'
    results = [{'title': f'Result {i}'} for i in range(8)]
    results[4]['title'] = 'Python rocks!'
    results[7]['title'] = 'Python is fun'
    c.render(json={'results': results})


@websocket('/echo', 'echo')
def echo(c):
    c.on('message', lambda c, msg: c.send(f'echo: {msg}'))


@get('/events')
def events(c):
    c.write_sse({'text': 'hello pyjo'})
    c.finish()


@get('/page')
def page(c):
    html = (
        '<html><head><title>Hello sri</title></head><body>'
        '<img class="cat" alt="Grumpy cat"><div class="foo" x="y">Hello!</div>'
        '<label for="email"></label><input name="email" type="text" value="sri@example.com">'
        '<label for="pass"></label><input name="pass" type="password"><input type="submit" value="Go">'
        '<input value="whatever"></body></html>'
    )
    c.res.headers.etag = '"abc321"'
    c.render(text=html, format='html')


any('/foo', {'text': 'Foo!'})

get('/', lambda c: c.redirect_to('https://mojolicious.org'))

get('/hello', {'text': 'Howdy!'})


@websocket('/time')
def time_(c):
    c.send(str(int(time.time())))


@websocket('/echo.json')
def echo_json(c):
    c.on('json', lambda c, hash: c.send({'json': hash}))


@get('/bad')
def bad(c):
    c.render(text='<html><head><title>Glen was here</title></head></html>', format='html', status=500)


# The MyApp of the examples, a module with a new function
myapp = types.ModuleType('MyApp')
myapp.new = lambda **kwargs: Pyjoyment.new(**kwargs)
sys.modules['MyApp'] = myapp

# The calls of the handler, which the examples of the methods make
calls = []


def record(name, *args):
    calls.append([name, *args])
    return True


# A tester, which the examples use in a with block that closes its user agent and servers where it ends, as the garbage
# collector would free them in the middle of what the event loop does, as they are in cycles
def tester(path=None):
    t = Pyjo.Test.Pyjo.new(app)
    if path is not None:
        t.get_ok(path)
    calls.clear()
    t.handler = record
    return t


with subtest('Synopsis'):
    with Pyjo.Test.Pyjo.new(app) as t:
        # HTML/XML
        t.get_ok('/welcome').status_is(200).text_is('div#message', 'Hello!')
        ok(t.success, 'HTML/XML')

        # JSON
        (
            t.post_ok('/search.json', form={'q': 'Python'})
            .status_is(200)
            .header_is('Server', 'Pyjoyment (Python)')
            .header_isnt('X-Bender', 'Bite my shiny metal ass!')
            .json_is('/results/4/title', 'Python rocks!')
            .json_like('/results/7/title', re.compile(r'Python'))
        )
        ok(t.success, 'JSON')

        # WebSocket
        t.websocket_ok('/echo').send_ok('hello').message_ok().message_is('echo: hello').finish_ok()
        ok(t.success, 'WebSocket')

        # Server-Sent Events (SSE)
        (
            t.get_sse_ok('/events')
            .status_is(200)
            .sse_ok()
            .sse_type_is('message')
            .sse_text_is('hello pyjo')
            .sse_finish_ok()
        )
        ok(t.success, 'SSE')

with subtest('Description'):
    verbose = os.environ.get('PYJO_HARNESS_IS_VERBOSE', os.environ.get('HARNESS_IS_VERBOSE'))
    is_ok(os.environ.get('PYJO_LOG_LEVEL'), 'trace' if verbose else 'fatal', 'log level')
    ok(Pyjo.Test.Pyjo.new().ua.insecure, 'insecure')

    # The test of unittest, with a MyApp of its own, in a process of its own, as unittest runs it
    with Pyjo.File.tempdir() as tmp:
        tmp.child('MyApp.py').spurt(
            textwrap.dedent("""\
                import Pyjoyment


                def new(**kwargs):
                    app = Pyjoyment.new(**kwargs)
                    app.log.level = 'fatal'
                    app.routes.get('/welcome', {'text': '<div id="message">Hello!</div>', 'format': 'html'})
                    return app
            """)
        )
        tmp.child('test_myapp.py').spurt(
            textwrap.dedent("""\
                import unittest

                import Pyjo.Test
                import Pyjo.Test.Pyjo


                def setUpModule():
                    unittest.enterModuleContext(Pyjo.Test.raise_failures())


                class TestMyApp(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls):
                        cls.t = cls.enterClassContext(Pyjo.Test.Pyjo.new('MyApp'))

                    def test_welcome(self):
                        self.t.get_ok('/welcome').status_is(200).text_is('div#message', 'Hello!')
            """)
        )
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([ROOT, tmp.to_str()]))
        p = subprocess.run(
            [sys.executable, '-m', 'unittest', '-v', 'test_myapp'],
            cwd=tmp.to_str(),
            capture_output=True,
            text=True,
            env=env,
        )
        like_ok(p.stderr, r'(?m)^test_welcome \(test_myapp\.TestMyApp\.test_welcome\) \.\.\. ok$', 'test of unittest')
        unlike_ok(p.stderr, r'ResourceWarning', 'closed at the end of the class')
        is_ok(p.returncode, 0, 'right exit status')

with subtest('new'):
    t = Pyjo.Test.Pyjo.new()
    is_ok(t.app, Pyjo.UserAgent.Server.app(), 'default application')
    t = Pyjo.Test.Pyjo.new('MyApp')
    isa_ok(t.app, Pyjoyment.object, 'class name')
    t = Pyjo.Test.Pyjo.new('MyApp', {'foo': 'bar'})
    is_deeply_ok(t.app.config(), {'config_override': 1, 'foo': 'bar'}, 'configuration')
    script = Pyjo.File.tempdir().child('myapp.py')
    script.spew(b'from Pyjoyment.Lite import app\n\napp.start()\n')
    t = Pyjo.Test.Pyjo.new(Pyjo.File.new(script))
    is_ok(t.app.moniker, 'myapp', 'script')
    t = Pyjo.Test.Pyjo.new(Pyjo.File.new(script), {'foo': 'bar'})
    is_ok(t.app.config('foo'), 'bar', 'script with configuration')
    t = Pyjo.Test.Pyjo.new(myapp.new())
    isa_ok(t.app, Pyjoyment.object, 'object')
    t = Pyjo.Test.Pyjo.new(myapp.new(), {'foo': 'bar'})
    is_ok(t.app.config('config_override'), 1, 'object with configuration')

    # Load application script relative to the "t" directory
    from Pyjo.File import curfile

    path = curfile().dirname().sibling('myapp.py')
    is_ok(path.basename(), 'myapp.py', 'relative to the "t" directory')

with subtest('handler'):
    with tester() as t:
        cb = t.handler
        is_ok(cb, record, 'callback')

        def handler(name, *args):
            return {'is': is_ok, 'like': like_ok, 'ok': ok}[name](*args)

        t.handler = handler
        t.test('is', 1, 1, 'through Pyjo.Test')

with subtest('message'):
    with tester() as t:
        msg = t.message
        is_ok(msg, None, 'no message')
        t.message = ['text', b'{"foo": "bar"}']

        # More specific tests
        from Pyjo.JSON import decode_json

        hash = decode_json(t.message[1])
        is_ok(type(hash), dict, 'right reference')
        is_ok(hash['foo'], 'bar', 'right value')

        # Test custom message
        t.message = ['binary', b'{"foo": {"bar": 1, "baz": {"yada": [1, 2, 3]}}}']
        t.json_message_has('/foo/bar').json_message_hasnt('/bar').json_message_is('/foo/baz', {'yada': [1, 2, 3]})
        is_deeply_ok([c[1] for c in calls], [True, True, {'yada': [1, 2, 3]}], 'custom message')

with subtest('sse'):
    with tester() as t:
        event = t.sse
        t.sse = {'type': 'message', 'text': 'working!'}
        t.sse_text_is('working!')
        is_deeply_ok([event, calls[-1][1]], [None, 'working!'], 'event')

with subtest('success'):
    with Pyjo.Test.Pyjo.new(app) as t:
        boolean = t.success
        t.success = boolean

        # Build custom tests
        def location_is(t, value, desc=''):
            desc = desc or f'Location: {value}'
            t.success = calls.append(['is', t.tx.res.headers.location, value, desc]) or True
            return t

        calls.clear()
        diags = []
        t.get_ok('/').status_is(302)
        t.handler = record
        location_is(t, 'https://mojolicious.org').otherwise(lambda t: diags.append('Must have been Joel!'))
        is_deeply_ok(
            calls[-1],
            ['is', 'https://mojolicious.org', 'https://mojolicious.org', 'Location: https://mojolicious.org'],
            'custom test',
        )

with subtest('tx'):
    with tester('/search.json') as t:
        tx = t.tx
        t.tx = Pyjo.Transaction.HTTP.new()
        t.tx = tx

        # More specific tests
        t.get_ok('/foo')
        t.tx.res.body = b'{"foo": "bar"}'
        is_ok(t.tx.res.json()['foo'], 'bar', 'right value')
        ok(not t.tx.res.content.is_multipart, 'multipart content')
        is_ok(t.tx.previous, None, 'no redirect')

with subtest('ua'):
    with tester() as t:
        ua = t.ua
        t.ua = Pyjo.UserAgent.new()
        t.ua = ua

        # Allow redirects
        t.ua.max_redirects = 10
        t.get_ok('/redirect').status_is(200).content_like(re.compile(r'redirected'))
        is_ok(calls[0][1:], [True, 'GET /redirect'], 'redirects')

        # Switch protocol from HTTP to HTTPS
        calls.clear()
        t.ua.server.url('https')
        t.get_ok('/secure').status_is(200).content_like(re.compile(r'secure'))
        is_ok(calls[0][2], 'GET /secure', 'HTTPS')

        # Use absolute URL for request with Basic authentication
        calls.clear()
        url = t.ua.server.url().set(userinfo='sri:secr3t').set(path='/secrets.json')
        t.post_ok(url, json={'limit': 10}).status_is(200).json_is('/1/content', 'Pyjo rocks!')
        # The URL of the description leaves out the userinfo, as it stringifies without it
        like_ok(calls[0][2], r'^POST https://127\.0\.0\.1:\d+/secrets\.json$', 'absolute URL')
        is_ok(t.tx.req.url.to_abs().userinfo, 'sri:secr3t', 'userinfo')

        # Customize all transactions (including followed redirects)
        t.ua.on('start', lambda ua, tx: tx.req.headers.set(accept_language='en-US'))
        t.get_ok('/hello').status_is(200).content_like(re.compile(r'Howdy'))
        is_ok(t.tx.req.headers.accept_language, 'en-US', 'customized')

with subtest('app'):
    with Pyjo.Test.Pyjo.new(app) as t:
        app_ = t.app
        t.app = Pyjoyment.new()
        t.app = app_

        # Change log level
        t.app.log.level = 'fatal'

        # Test application directly
        is_ok(t.app.defaults('foo'), 'bar', 'right value')
        ok(t.app.routes.find('echo').is_websocket, 'WebSocket route')
        tmp = Pyjo.File.tempdir()
        # A template that ends with a backslash, which leaves out the newline at the end
        tmp.child('foo.html.ep').spew(b'Foo!\\')
        t.app.renderer.paths.append(str(tmp))
        c = t.app.build_controller()
        ok(c.render(template='foo'), 'rendering was successful')
        is_ok(c.res.code, 200, 'right status')
        is_ok(c.res.body, b'Foo!', 'right content')

        # Change application behavior
        @t.app.hook('before_dispatch')
        def before_dispatch(c):
            if c.req.url.path.contains('/user'):
                c.render(text='This request did not reach the router.')

        t.get_ok('/user').status_is(200).content_like(re.compile(r'not reach the router'))

        # Extract additional information
        stash = {}
        t.app.hook('after_dispatch', lambda c: stash.update(c.stash()))
        t.get_ok('/hello').status_is(200)
        is_ok(stash['foo'], 'bar', 'right value')

with subtest('attr_is'):
    with tester('/page') as t:
        t = t.attr_is('img.cat', 'alt', 'Grumpy cat')
        t = t.attr_is('img.cat', 'alt', 'Grumpy cat', 'right alt text')
        is_deeply_ok(calls, [
            ['is', 'Grumpy cat', 'Grumpy cat', 'exact match for attribute "alt" at selector "img.cat"'],
            ['is', 'Grumpy cat', 'Grumpy cat', 'right alt text'],
        ], 'calls')  # fmt: skip

with subtest('attr_isnt'):
    with tester('/page') as t:
        t = t.attr_isnt('img.cat', 'alt', 'Calm cat')
        t = t.attr_isnt('img.cat', 'alt', 'Calm cat', 'different alt text')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('attr_like'):
    with tester('/page') as t:
        t = t.attr_like('img.cat', 'alt', re.compile(r'Grumpy'))
        t = t.attr_like('img.cat', 'alt', re.compile(r'Grumpy'), 'right alt text')
        is_deeply_ok([c[0] for c in calls], ['like', 'like'], 'calls')

with subtest('attr_unlike'):
    with tester('/page') as t:
        t = t.attr_unlike('img.cat', 'alt', re.compile(r'Calm'))
        t = t.attr_unlike('img.cat', 'alt', re.compile(r'Calm'), 'different alt text')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')

with subtest('close'):
    t = Pyjo.Test.Pyjo.new(Pyjoyment.new())
    before = t.ua.server.url().port
    t.close()
    isnt_ok(t.ua.server.url().port, before, 'a new server when it is used again')
    t.close()


with subtest('content_is'):
    with tester('/foo') as t:
        t = t.content_is('working!')
        t = t.content_is('working!', 'right content')
        is_deeply_ok(calls[0], ['is', 'Foo!', 'working!', 'exact match for content'], 'calls')

with subtest('content_isnt'):
    with tester('/foo') as t:
        t = t.content_isnt('working!')
        t = t.content_isnt('working!', 'different content')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('content_like'):
    with tester('/foo') as t:
        t = t.content_like(re.compile(r'working!'))
        t = t.content_like(re.compile(r'working!'), 'right content')
        is_deeply_ok([c[0] for c in calls], ['like', 'like'], 'calls')

with subtest('content_type_is'):
    with tester('/foo') as t:
        t = t.content_type_is('text/html')
        t = t.content_type_is('text/html', 'right content type')
        is_deeply_ok(calls[0], ['is', 'text/html;charset=UTF-8', 'text/html', 'Content-Type: text/html'], 'calls')

with subtest('content_type_isnt'):
    with tester('/foo') as t:
        t = t.content_type_isnt('text/html')
        t = t.content_type_isnt('text/html', 'different content type')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('content_type_like'):
    with tester('/foo') as t:
        t = t.content_type_like(re.compile(r'text'))
        t = t.content_type_like(re.compile(r'text'), 'right content type')
        is_deeply_ok([c[0] for c in calls], ['like', 'like'], 'calls')

with subtest('content_type_unlike'):
    with tester('/foo') as t:
        t = t.content_type_unlike(re.compile(r'text'))
        t = t.content_type_unlike(re.compile(r'text'), 'different content type')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')

with subtest('content_unlike'):
    with tester('/foo') as t:
        t = t.content_unlike(re.compile(r'working!'))
        t = t.content_unlike(re.compile(r'working!'), 'different content')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')


def requests(method):
    # The forms of the arguments of a request method, which the examples share, with the URL of the application in
    # place of http://example.com
    with tester() as t:
        url = t.ua.server.url().set(path='/foo')
        getattr(t, method)(url)
        getattr(t, method)('/foo')
        getattr(t, method)('/foo', {'Accept': '*/*'}, 'Content!')
        getattr(t, method)('/foo', {'Accept': '*/*'}, form={'a': 'b'})
        getattr(t, method)('/foo', {'Accept': '*/*'}, json={'a': 'b'})
        return [c[2] for c in calls]


with subtest('delete_ok'):
    is_ok(requests('delete_ok')[1:], ['DELETE /foo'] * 4, 'forms of arguments')

with subtest('element_count_is'):
    with tester('/page') as t:
        t = t.element_count_is('div.foo[x=y]', 5)
        t = t.element_count_is('html body div', 30, 'thirty elements')
        is_deeply_ok(calls[0], ['is', 1, 5, 'element count for selector "div.foo[x=y]"'], 'calls')

with subtest('element_exists'):
    with tester('/page') as t:
        t = t.element_exists('div.foo[x=y]')
        t = t.element_exists('html head title', 'has a title')
        is_ok(calls[0][2], 'element for selector "div.foo[x=y]" exists', 'calls')

        # Check attribute values
    with Pyjo.Test.Pyjo.new(app) as t:
        (
            t.get_ok('/page')
            .element_exists('label[for=email]')
            .element_exists('input[name=email][type=text][value*="example.com"]')
            .element_exists('label[for=pass]')
            .element_exists('input[name=pass][type=password]')
            .element_exists('input[type=submit][value]')
        )
        ok(t.success, 'attribute values')

with subtest('element_exists_not'):
    with tester('/page') as t:
        t = t.element_exists_not('div.foo[x=y]')
        t = t.element_exists_not('html head title', 'has no title')
        is_deeply_ok([c[1] for c in calls], [False, False], 'calls')

with subtest('finish_ok'):
    with Pyjo.Test.Pyjo.new(app) as t:
        t = t.websocket_ok('/echo').finish_ok()
        t = t.websocket_ok('/echo').finish_ok(1000)
        t = t.websocket_ok('/echo').finish_ok(1003, 'Cannot accept data!')
        ok(t.success, 'closed')

with subtest('finished_ok'):
    with Pyjo.Test.Pyjo.new(app) as t:
        t.websocket_ok('/echo').finish_ok(1000)
        t = t.finished_ok(1000)
        ok(t.success, 'status')

with subtest('get_ok'):
    with tester() as t:
        is_ok(requests('get_ok')[1:], ['GET /foo'] * 4, 'forms of arguments')

        # Run tests against remote host
        if os.environ.get('TEST_ONLINE'):
            subtest(
                'Remote host',
                lambda: Pyjo.Test.Pyjo.new().get_ok('https://github.com').status_is(200),
                reruns=2,
                reruns_delay=10,
            )
        else:
            skip('set TEST_ONLINE to request a remote host', 1)

        # Use relative URL for request with Basic authentication
    with tester() as t:
        t.get_ok('//sri:secr3t@/secrets.json').status_is(200).json_is('/1/content', 'Pyjo rocks!')
        is_ok(calls[0][2], 'GET //sri:secr3t@/secrets.json', 'relative URL')

        # Run additional tests on the transaction
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/page').status_is(200)
        is_ok(t.tx.res.dom().at('input').val, 'sri@example.com', 'right value')

with subtest('get_sse_ok'):
    with tester() as t:
        t = t.get_sse_ok('/events')
        t.sse_finished_ok()
        is_ok(calls[0][2], 'SSE connection established: GET /events', 'calls')
        t = t.get_sse_ok('/events', {'Accept': 'text/event-stream'}, 'Content!')
        t.sse_finished_ok()
        t = t.get_sse_ok('/events', {'Accept': 'text/event-stream'}, form={'a': 'b'})
        t.sse_finished_ok()
        t = t.get_sse_ok('/events', {'Accept': 'text/event-stream'}, json={'a': 'b'})
        t.sse_finished_ok()
        is_ok(len(calls), 8, 'forms of arguments')

with subtest('head_ok'):
    is_ok(requests('head_ok')[1:], ['HEAD /foo'] * 4, 'forms of arguments')

with subtest('header_exists'):
    with tester('/page') as t:
        t = t.header_exists('ETag')
        t = t.header_exists('ETag', 'header exists')
        is_deeply_ok(calls[0], ['ok', True, 'header "ETag" exists'], 'calls')

with subtest('header_exists_not'):
    with tester('/page') as t:
        t = t.header_exists_not('ETag')
        t = t.header_exists_not('ETag', 'header is missing')
        is_deeply_ok(calls[0], ['ok', False, 'no "ETag" header'], 'calls')

with subtest('header_is'):
    with tester('/page') as t:
        t = t.header_is('ETag', '"abc321"')
        t = t.header_is('ETag', '"abc321"', 'right header')
        is_deeply_ok(calls[0], ['is', '"abc321"', '"abc321"', 'ETag: "abc321"'], 'calls')

with subtest('header_isnt'):
    with tester('/page') as t:
        t = t.header_isnt('Etag', '"abc321"')
        t = t.header_isnt('ETag', '"abc321"', 'different header')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('header_like'):
    with tester('/page') as t:
        t = t.header_like('ETag', re.compile(r'abc'))
        t = t.header_like('ETag', re.compile(r'abc'), 'right header')
        is_deeply_ok([c[0] for c in calls], ['like', 'like'], 'calls')

with subtest('header_unlike'):
    with tester('/page') as t:
        t = t.header_unlike('ETag', re.compile(r'abc'))
        t = t.header_unlike('ETag', re.compile(r'abc'), 'different header')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')


def json(t):
    # The JSON response of the examples
    t.tx.res.body = b'{"foo": [1, 2, 3], "minibar": 1}'
    return t


with subtest('json_has'):
    with tester('/foo') as t:
        json(t)
        t = t.json_has('/foo')
        t = t.json_has('/minibar', 'has a minibar')
        is_deeply_ok(calls, [['ok', True, 'has value for JSON Pointer "/foo"'], ['ok', True, 'has a minibar']], 'calls')

with subtest('json_hasnt'):
    with tester('/foo') as t:
        json(t)
        t = t.json_hasnt('/foo')
        t = t.json_hasnt('/minibar', 'no minibar')
        is_deeply_ok([c[1] for c in calls], [False, False], 'calls')

with subtest('json_is'):
    with tester('/foo') as t:
        json(t)
        t = t.json_is({'foo': [1, 2, 3]})
        t = t.json_is('/foo', [1, 2, 3])
        t = t.json_is('/foo/1', 2, 'right value')
        is_deeply_ok(calls[1:], [
            ['is_deeply', [1, 2, 3], [1, 2, 3], 'exact match for JSON Pointer "/foo"'],
            ['is_deeply', 2, 2, 'right value'],
        ], 'calls')  # fmt: skip

        # Use an empty JSON Pointer to test the whole JSON response with a test description
        t.json_is('', {'foo': [1, 2, 3]}, 'right object')
        is_ok(calls[-1][3], 'right object', 'description')

with subtest('json_like'):
    with tester('/foo') as t:
        json(t)
        t = t.json_like('/foo/1', re.compile(r'^\d+$'))
        t = t.json_like('/foo/1', re.compile(r'^\d+$'), 'right value')
        is_deeply_ok(calls[0][:2], ['like', 2], 'calls')

with subtest('json_message_has'):
    with tester() as t:
        t.message = ['text', b'{"foo": 1, "minibar": 2}']
        t = t.json_message_has('/foo')
        t = t.json_message_has('/minibar', 'has a minibar')
        is_deeply_ok([c[1] for c in calls], [True, True], 'calls')

with subtest('json_message_hasnt'):
    with tester() as t:
        t.message = ['text', b'{}']
        t = t.json_message_hasnt('/foo')
        t = t.json_message_hasnt('/minibar', 'no minibar')
        is_deeply_ok([c[1] for c in calls], [True, True], 'calls')

with subtest('json_message_is'):
    with tester() as t:
        t.message = ['text', b'{"foo": [1, 2, 3]}']
        t = t.json_message_is({'foo': [1, 2, 3]})
        t = t.json_message_is('/foo', [1, 2, 3])
        t = t.json_message_is('/foo/1', 2, 'right value')
        is_deeply_ok([c[1] for c in calls], [{'foo': [1, 2, 3]}, [1, 2, 3], 2], 'calls')

with subtest('json_message_like'):
    with tester() as t:
        t.message = ['text', b'{"foo": [1, 2, 3]}']
        t = t.json_message_like('/foo/1', re.compile(r'^\d+$'))
        t = t.json_message_like('/foo/1', re.compile(r'^\d+$'), 'right value')
        is_deeply_ok([c[0] for c in calls], ['like', 'like'], 'calls')

with subtest('json_message_unlike'):
    with tester() as t:
        t.message = ['text', b'{"foo": [1, 2, 3]}']
        t = t.json_message_unlike('/foo/1', re.compile(r'^\d+$'))
        t = t.json_message_unlike('/foo/1', re.compile(r'^\d+$'), 'different value')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')

with subtest('json_unlike'):
    with tester('/foo') as t:
        json(t)
        t = t.json_unlike('/foo/1', re.compile(r'^\d+$'))
        t = t.json_unlike('/foo/1', re.compile(r'^\d+$'), 'different value')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')

with subtest('message_is'):
    with tester() as t:
        t.message = ['binary', b'bytes']
        t = t.message_is({'binary': b'bytes'})
        t = t.message_is({'text': b'bytes'})
        t.message = ['text', b'working!']
        t = t.message_is('working!')
        t = t.message_is('working!', 'right message')
        is_deeply_ok([c[1] for c in calls], [b'bytes', '', 'working!', 'working!'], 'calls')

with subtest('message_isnt'):
    with tester() as t:
        t.message = ['text', b'working!']
        t = t.message_isnt({'binary': b'bytes'})
        t = t.message_isnt({'text': b'bytes'})
        t = t.message_isnt('working!')
        t = t.message_isnt('working!', 'different message')
        is_deeply_ok([c[0] for c in calls], ['isnt'] * 4, 'calls')

with subtest('message_like'):
    with tester() as t:
        t.message = ['text', b'working!']
        t = t.message_like({'binary': re.compile(rb'bytes')})
        t = t.message_like({'text': re.compile(rb'bytes')})
        t = t.message_like(re.compile(r'working!'))
        t = t.message_like(re.compile(r'working!'), 'right message')
        is_deeply_ok([c[0] for c in calls], ['like'] * 4, 'calls')

with subtest('message_ok'):
    with tester() as t:
        t.websocket_ok('/echo').send_ok('ping')
        t = t.message_ok()
        t.send_ok('pong')
        t = t.message_ok('got a message')
        is_deeply_ok(calls[-1], ['ok', True, 'got a message'], 'calls')
        t.finish_ok()

        # Wait for message and perform multiple tests on it
    with tester() as t:
        (
            t.websocket_ok('/time')
            .message_ok()
            .message_like(re.compile(r'\d+'))
            .message_unlike(re.compile(r'\w+'))
            .finish_ok()
        )
        is_deeply_ok([c[0] for c in calls], ['ok', 'ok', 'like', 'unlike', 'ok'], 'multiple tests')

with subtest('message_unlike'):
    with tester() as t:
        t.message = ['text', b'working!']
        t = t.message_unlike({'binary': re.compile(rb'bytes')})
        t = t.message_unlike({'text': re.compile(rb'bytes')})
        t = t.message_unlike(re.compile(r'working!'))
        t = t.message_unlike(re.compile(r'working!'), 'different message')
        is_deeply_ok([c[0] for c in calls], ['unlike'] * 4, 'calls')

with subtest('options_ok'):
    is_ok(requests('options_ok')[1:], ['OPTIONS /foo'] * 4, 'forms of arguments')

with subtest('otherwise'):
    with tester() as t:
        t.success = False
        t = t.otherwise(lambda t: calls.append('callback'))
        is_deeply_ok(calls, ['callback'], 'callback')

        # Diagnostics
        diags = []
        diag = diags.append
    with tester() as t:
        t.handler = lambda name, *args: name != 'is' or args[0] == args[1]
        (
            t.get_ok('/bad')
            .otherwise(lambda t: diag('Must have been Glen!'))
            .status_is(200)
            .otherwise(lambda t: diag(t.tx.res.dom().at('title').text))
        )
        is_deeply_ok(diags, ['Glen was here'], 'diagnostics')

with subtest('patch_ok'):
    is_ok(requests('patch_ok')[1:], ['PATCH /foo'] * 4, 'forms of arguments')

with subtest('post_ok'):
    is_ok(requests('post_ok')[1:], ['POST /foo'] * 4, 'forms of arguments')

    # Test file upload
    with tester() as t:
        upload = {'foo': {'content': 'bar', 'filename': 'baz.txt'}}
        t.post_ok('/upload', form=upload).status_is(200)
        is_ok(t.tx.req.upload('foo').filename, 'baz.txt', 'upload')

        # Test JSON API
    with tester() as t:
        t.post_ok('/hello.json', json={'hello': 'world'}).status_is(200).json_is({'bye': 'world'})
        is_ok(t.tx.req.json(), {'hello': 'world'}, 'JSON request')

with subtest('post_sse_ok'):
    with tester() as t:
        for args, kwargs in ([['/events'], {}], [['/events', {'Accept': 'text/event-stream'}, 'Content!'], {}]):
            t = t.post_sse_ok(*args, **kwargs)
            t.sse_finished_ok()
        t = t.post_sse_ok('/events', {'Accept': 'text/event-stream'}, form={'a': 'b'})
        t.sse_finished_ok()
        t = t.post_sse_ok('/events', {'Accept': 'text/event-stream'}, json={'a': 'b'})
        t.sse_finished_ok()
        is_ok(calls[0][2], 'SSE connection established: POST /events', 'calls')

with subtest('put_ok'):
    is_ok(requests('put_ok')[1:], ['PUT /foo'] * 4, 'forms of arguments')

with subtest('query_ok'):
    is_ok(requests('query_ok')[1:], ['QUERY /foo'] * 4, 'forms of arguments')

with subtest('request_ok'):
    with tester() as t:
        t = t.request_ok(Pyjo.Transaction.HTTP.new().set(req=t.ua.build_tx('GET', '/foo').req))

        # Request with custom method
        tx = t.ua.build_tx('FOO', '/test.json', json={'foo': 1})
        t.request_ok(tx).status_is(200).json_is({'success': 1})
        is_ok(t.tx.req.method, 'FOO', 'custom method')

        # Request with custom cookie
        tx = t.ua.build_tx('GET', '/account')
        tx.req.cookies({'name': 'user', 'value': 'sri'})
        t.request_ok(tx).status_is(200).text_is('head > title', 'Hello sri')
        is_ok(t.tx.req.cookie('user').value, 'sri', 'custom cookie')

        # Custom WebSocket handshake
        tx = t.ua.build_websocket_tx('/foo')
        tx.req.headers.remove('User-Agent')
        t.request_ok(tx).message_ok().message_is('bar').finish_ok()
        is_ok(t.tx.req.headers.user_agent, None, 'custom handshake')

with subtest('reset_session'):
    with tester('/foo') as t:
        t = t.reset_session()
        is_ok(t.tx, None, 'no transaction')

with subtest('send_ok'):
    with tester() as t:
        t.websocket_ok('/echo')
        t = t.send_ok({'binary': b'bytes'})
        t = t.send_ok({'text': b'bytes'})
        t = t.send_ok({'json': {'test': [1, 2, 3]}})
        t = t.send_ok([1, 0, 0, 0, 1, b'payload'])
        t = t.send_ok('chars')
        t = t.send_ok('chars', 'sent successfully')
        is_deeply_ok([c[1:] for c in calls[1:]], [[1, 'send message']] * 5 + [[1, 'sent successfully']], 'calls')
        t.finish_ok()

        # Send JSON object as "Text" message
    with Pyjo.Test.Pyjo.new(app) as t:
        (
            t.websocket_ok('/echo.json')
            .send_ok({'json': {'test': 'I ♥ Pyjoyment!'}})
            .message_ok()
            .json_message_is('/test', 'I ♥ Pyjoyment!')
            .finish_ok()
        )
        ok(t.success, 'JSON message')

with subtest('sse_finish_ok'):
    with tester() as t:
        t.get_sse_ok('/events')
        t = t.sse_finish_ok()
        is_deeply_ok(calls[-1], ['ok', 1, 'closed SSE connection'], 'calls')

with subtest('sse_finished_ok'):
    with tester() as t:
        t.get_sse_ok('/events')
        t = t.sse_finished_ok()
        is_deeply_ok(calls[-1], ['ok', 1, 'SSE connection has been closed'], 'calls')

with subtest('sse_ok'):
    with tester() as t:
        t.get_sse_ok('/events')
        t = t.sse_ok()
        t = t.sse_ok('got an event')
        is_deeply_ok([c[1:] for c in calls[1:]], [[True, 'event received'], [False, 'got an event']], 'calls')


def event():
    # The event of the examples
    t = tester()
    t.sse = {'id': '123', 'text': 'working!', 'type': 'message'}
    return t


with subtest('sse_id_is'):
    with event() as t:
        t = t.sse_id_is(123)
        t = t.sse_id_is(123, 'right id')
        is_deeply_ok(calls[0], ['is', '123', 123, 'exact match for SSE event id'], 'calls')

with subtest('sse_id_isnt'):
    with event() as t:
        t = t.sse_id_isnt(123)
        t = t.sse_id_isnt(123, 'different id')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('sse_text_is'):
    with event() as t:
        t = t.sse_text_is('working!')
        t = t.sse_text_is('working!', 'right text')
        is_deeply_ok(calls[0], ['is', 'working!', 'working!', 'exact match for SSE event text'], 'calls')

with subtest('sse_text_isnt'):
    with event() as t:
        t = t.sse_text_isnt('working!')
        t = t.sse_text_isnt('working!', 'different text')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('sse_text_like'):
    with event() as t:
        t = t.sse_text_like(re.compile(r'working'))
        t = t.sse_text_like(re.compile(r'working'), 'right text')
        is_deeply_ok([c[0] for c in calls], ['like', 'like'], 'calls')

with subtest('sse_text_unlike'):
    with event() as t:
        t = t.sse_text_unlike(re.compile(r'working'))
        t = t.sse_text_unlike(re.compile(r'working'), 'different text')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')

with subtest('sse_type_is'):
    with event() as t:
        t = t.sse_type_is('message')
        t = t.sse_type_is('message', 'right type')
        is_deeply_ok(calls[0], ['is', 'message', 'message', 'exact match for SSE event type'], 'calls')

with subtest('sse_type_isnt'):
    with event() as t:
        t = t.sse_type_isnt('message')
        t = t.sse_type_isnt('message', 'different type')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('status_is'):
    with tester('/foo') as t:
        t = t.status_is(200)
        t = t.status_is(200, 'right status')
        is_deeply_ok(calls, [['is', 200, 200, '200 OK'], ['is', 200, 200, 'right status']], 'calls')

with subtest('status_isnt'):
    with tester('/foo') as t:
        t = t.status_isnt(200)
        t = t.status_isnt(200, 'different status')
        is_deeply_ok(calls[0], ['isnt', 200, 200, 'not 200 OK'], 'calls')

with subtest('test'):
    with tester() as t:
        t = t.test('is', 'first value', 'second value', 'right value')
        is_deeply_ok(calls, [['is', 'first value', 'second value', 'right value']], 'calls')
        ok(t.success, 'stored')

with subtest('text_is'):
    with tester('/page') as t:
        t = t.text_is('div.foo[x=y]', 'Hello!')
        t = t.text_is('html head title', 'Hello!', 'right title')
        is_deeply_ok(calls, [
            ['is', 'Hello!', 'Hello!', 'exact match for selector "div.foo[x=y]"'],
            ['is', 'Hello sri', 'Hello!', 'right title'],
        ], 'calls')  # fmt: skip

with subtest('text_isnt'):
    with tester('/page') as t:
        t = t.text_isnt('div.foo[x=y]', 'Hello!')
        t = t.text_isnt('html head title', 'Hello!', 'different title')
        is_deeply_ok([c[0] for c in calls], ['isnt', 'isnt'], 'calls')

with subtest('text_like'):
    with tester('/page') as t:
        t = t.text_like('div.foo[x=y]', re.compile(r'Hello'))
        t = t.text_like('html head title', re.compile(r'Hello'), 'right title')
        is_deeply_ok([c[0] for c in calls], ['like', 'like'], 'calls')

with subtest('text_unlike'):
    with tester('/page') as t:
        t = t.text_unlike('div.foo[x=y]', re.compile(r'Hello'))
        t = t.text_unlike('html head title', re.compile(r'Hello'), 'different title')
        is_deeply_ok([c[0] for c in calls], ['unlike', 'unlike'], 'calls')

with subtest('websocket_ok'):
    with tester() as t:
        url = t.ua.server.url().set(path='/echo')
        t = t.websocket_ok(url)
        t.finish_ok()
        t = t.websocket_ok('/echo')
        t.finish_ok()
        t = t.websocket_ok('/echo', {'DNT': 1}, ['v1.proto'])
        t.finish_ok()
        is_ok(calls[2][2], 'WebSocket handshake with /echo', 'calls')

        # WebSocket with permessage-deflate compression
    with Pyjo.Test.Pyjo.new(app) as t:
        (
            t.websocket_ok('/echo', {'Sec-WebSocket-Extensions': 'permessage-deflate'})
            .send_ok('y' * 50000)
            .message_ok()
            .message_is('echo: ' + 'y' * 50000)
            .finish_ok()
        )
        ok(t.success, 'compression')

done_testing()
