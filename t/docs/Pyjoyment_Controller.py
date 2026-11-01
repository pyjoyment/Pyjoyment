import Pyjo.IOLoop
import Pyjo.String.HTML
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent
import Pyjoyment
import Pyjoyment.Routes.Match

from Pyjo.File import tempdir
from Pyjo.JSON import decode_json, encode_json
from Pyjo.Test import *

import re
import sys
import time
import types


def request(app, path, method='GET', **kwargs):
    # The application and the user agent share the event loop, as Test::Mojo makes them
    ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
    ua.server.app = app
    return ua.start(ua.build_tx(method, path, **kwargs))


def controller():
    app = Pyjoyment.new(secrets=['works'])
    app.log.level = 'fatal'
    return app, app.build_controller()


with subtest('Synopsis'):
    # Controller
    from Pyjoyment.Controller import Controller

    class MyApp_Controller_Foo(Controller):
        # Action
        def bar(self):
            name = self.param('name')
            self.res.headers.cache_control = 'max-age=1, no-cache'
            self.render(json={'hello': name})

    # The module of the controller, where the routes find it
    sys.modules['MyApp_Controller_Foo'] = types.ModuleType('MyApp_Controller_Foo')
    sys.modules['MyApp_Controller_Foo'].object = MyApp_Controller_Foo
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/bar').to('MyApp_Controller_Foo#bar', namespace='')
    tx = request(app, '/bar?name=sri')
    is_deeply_ok(decode_json(tx.res.body), {'hello': 'sri'}, 'action')
    is_ok(tx.res.headers.cache_control, 'max-age=1, no-cache', 'header')

    # Or import the module, as in Google Python Style Guide

    # Controller
    import Pyjoyment.Controller

    class MyApp_Controller_Foo(Pyjoyment.Controller.object):
        # Action
        def bar(self):
            name = self.param('name')
            self.res.headers.cache_control = 'max-age=1, no-cache'
            self.render(json={'hello': name})

    # The module of the controller, where the routes find it
    sys.modules['MyApp_Controller_Foo'] = types.ModuleType('MyApp_Controller_Foo')
    sys.modules['MyApp_Controller_Foo'].object = MyApp_Controller_Foo
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/bar').to('MyApp_Controller_Foo#bar', namespace='')
    tx = request(app, '/bar?name=sri')
    is_deeply_ok(decode_json(tx.res.body), {'hello': 'sri'}, 'action')
    is_ok(tx.res.headers.cache_control, 'max-age=1, no-cache', 'header')

with subtest('Context manager'):

    class MyApp_Controller_Later(Pyjoyment.Controller.object):
        # Exception in a callback of a delayed response
        def later(self):
            @Pyjo.IOLoop.next_tick
            def tick(loop):
                with self:
                    self.render(text=self.param('name').upper())

    sys.modules['MyApp_Controller_Later'] = types.ModuleType('MyApp_Controller_Later')
    sys.modules['MyApp_Controller_Later'].object = MyApp_Controller_Later
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.exception_format = 'txt'
    app.routes.get('/later').to('MyApp_Controller_Later#later', namespace='')
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/later?name=sri').status_is(200).content_is('SRI')
    t.get_ok('/later').status_is(500).content_like(r"'NoneType' object has no attribute 'upper'")

with subtest('Helpers'):
    app, c = controller()

    # Call helpers
    c.layout('green')
    c.title('Welcome!')

    # Longer version
    c.helpers.layout('green')

    is_ok(c.stash('layout'), 'green', 'layout')
    is_ok(c.stash('title'), 'Welcome!', 'title')

with subtest('app'):
    app, c = controller()
    is_ok(c.app, app, 'application')
    # The application is weakened, so it is kept in a variable
    other = Pyjoyment.new()
    c.app = other

    # Use application logger
    c.app.log.level = 'fatal'
    c.app.log.debug('Hello Pyjo')

    # Generate path
    path = c.app.home.child('templates', 'foo', 'bar.html.ep')
    like_ok(path.to_str(), r'bar\.html\.ep$', 'path')

with subtest('match'):
    app, c = controller()
    app.routes.get('/foo', {'foo': 'bar', 'action': 'baz'}).set(name='foo')
    c.req.method = 'GET'
    c.req.url.parse('/foo')
    app.routes.match(c)
    m = c.match
    isa_ok(m, Pyjoyment.Routes.Match.object, 'match')

    # Introspect
    name = c.match.endpoint.name
    foo = c.match.endpoint.pattern.defaults['foo']
    action = c.match.stack[-1]['action']
    is_deeply_ok([name, foo, action], ['foo', 'bar', 'baz'], 'introspected')
    c.match = Pyjoyment.Routes.Match.new()

with subtest('tx'):
    app, c = controller()
    tx = c.tx
    isa_ok(tx, Pyjo.Transaction.HTTP.object, 'transaction')
    c.tx = tx = Pyjo.Transaction.HTTP.new()

    # Check peer information
    address = c.tx.remote_address
    port = c.tx.remote_port

    # Increase size limit for WebSocket messages to 16MiB
    if c.tx.is_websocket:
        c.tx.max_websocket_size = 16777216

    # Perform non-blocking operation without knowing the connection status
    tx = c.tx
    Pyjo.IOLoop.timer(0, lambda loop: c.app.log.debug('Finished' if tx.is_finished else 'In progress'))
    Pyjo.IOLoop.one_tick()
    is_ok(address, None, 'no peer')

with subtest('proceed'):
    app, c = controller()
    c.req.method = 'GET'
    c.req.url.parse('/')
    calls = []
    app.routes.under('/', lambda c: calls.append('under')).get('/', lambda c: calls.append('get'))
    # The handler of a request puts the action dispatcher last in the hook around_action
    app.handler(Pyjo.Transaction.HTTP.new())
    calls.clear()
    app.routes.match(c)
    c.proceed()
    is_deeply_ok(calls, ['under'], 'intermediate destination')
    c.proceed()
    is_deeply_ok(calls, ['under', 'get'], 'continued')

with subtest('cookie'):
    app, c = controller()
    c.req.cookies({'name': 'foo', 'value': 'bar'})
    value = c.cookie('foo')
    is_ok(value, 'bar', 'request cookie')
    c = c.cookie('foo', 'bar')
    c = c.cookie('foo', 'bar', {'path': '/'})

    # Create response cookie with domain and expiration date
    c.cookie('user', 'sri', {'domain': 'example.com', 'expires': time.time() + 60})

    # Create secure response cookie
    c.cookie('secret', 'I <3 Pyjoyment', {'secure': True, 'httponly': True})

    is_deeply_ok([cookie.name for cookie in c.res.cookies()], ['foo', 'foo', 'user', 'secret'], 'response cookies')

with subtest('every_cookie'):
    app, c = controller()
    c.req.cookies({'name': 'foo', 'value': 'a'}, {'name': 'foo', 'value': 'b'})
    values = c.every_cookie('foo')
    is_deeply_ok(values, ['a', 'b'], 'values')

    # Get first cookie value
    first = c.every_cookie('foo')[0]
    is_ok(first, 'a', 'first')

with subtest('every_param'):
    app, c = controller()
    c.req.url.parse('/?foo=a&foo=b')
    values = c.every_param('foo')
    is_deeply_ok(values, ['a', 'b'], 'values')

    # Get first value
    first = c.every_param('foo')[0]
    is_ok(first, 'a', 'first')

with subtest('every_signed_cookie'):
    app, c = controller()
    c.signed_cookie('foo', 'a')
    signed = c.res.cookies()[0].value
    c.req.cookies({'name': 'foo', 'value': signed}, {'name': 'foo', 'value': 'b'})
    values = c.every_signed_cookie('foo')
    is_deeply_ok(values, ['a'], 'only the signed value')

    # Get first signed cookie value
    first = c.every_signed_cookie('foo')[0]
    is_ok(first, 'a', 'first')

with subtest('finish'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/1', lambda c: c.finish())
    app.routes.get('/2', lambda c: c.finish(b'Bye!'))
    app.routes.websocket('/3', lambda c: c.finish(1000))
    app.routes.websocket('/4', lambda c: c.finish(1003, 'Cannot accept data!'))
    is_ok(request(app, '/1').res.code, 200, 'finished')
    is_ok(request(app, '/2').res.body, b'Bye!', 'finished with data')
    t = Pyjo.Test.Pyjo.new(app)
    t.websocket_ok('/3').finished_ok(1000)
    t.websocket_ok('/4').finished_ok(1003)

with subtest('helpers'):
    app, c = controller()
    helpers = c.helpers

    # Make sure to use the "title" helper and not the controller method
    c.helpers.title('Welcome!')

    # Use a nested helper instead of the "reply" controller method
    c.exception_format('txt')
    c.helpers.reply.not_found()

    is_ok(c.stash('title'), 'Welcome!', 'title')
    is_ok(c.res.code, 404, 'not found')
    ok(helpers, 'proxy')

with subtest('on'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    events = []

    def action(c):
        cb = c.on('finish', lambda c: ...)
        ok(callable(cb), 'subscribed')

        @c.on('finish')
        def cb2(c): ...

        # Do something after the transaction has been finished
        @c.on('finish')
        def finish(c):
            c.app.log.debug('All data has been sent')
            events.append('finish')

        c.render(text='on')

    app.routes.get('/', action)
    request(app, '/')
    is_deeply_ok(events, ['finish'], 'event')

    # The examples of the events of a WebSocket, each in an action of its own
    def message_action(c):
        # Receive WebSocket message
        @c.on('message')
        def message(c, msg):
            c.app.log.debug(f'Message: {msg}')
            events.append(f'message {msg}')

    def json_action(c):
        # Receive JSON object via WebSocket message
        @c.on('json')
        def json(c, hash):
            c.app.log.debug(f'Test: {hash["test"]}')
            events.append(f'json {hash["test"]}')

    def binary_action(c):
        # Receive WebSocket "Binary" message
        @c.on('binary')
        def binary(c, data):
            c.app.log.debug(f'Received {len(data)} bytes')
            events.append(f'binary {len(data)}')

    app.routes.websocket('/message', message_action)
    app.routes.websocket('/json', json_action)
    app.routes.websocket('/binary', binary_action)
    t = Pyjo.Test.Pyjo.new(app)
    t.websocket_ok('/message').send_ok('hello').finish_ok()
    t.websocket_ok('/json').send_ok({'json': {'test': 23}}).finish_ok()
    t.websocket_ok('/binary').send_ok({'binary': b'\x00\x01\x02'}).finish_ok()
    is_deeply_ok(events, ['finish', 'message hello', 'json 23', 'binary 3'], 'WebSocket events')

with subtest('param'):
    app, c = controller()
    value = c.param('foo')
    is_ok(value, None, 'no value')
    c = c.param('foo', 'ba;r')
    c = c.param('foo', 'ba;r', 'baz')
    c = c.param('foo', ['ba;r', 'baz'])
    is_ok(c.param('foo'), 'baz', 'last value')

    # Get first value
    first = c.every_param('foo')[0]
    is_ok(first, 'ba;r', 'first value')

    c = app.build_controller()
    c.req.url.parse('/?foo=a')

    # Only GET parameters
    foo = c.req.query_params.param('foo')

    # Only POST parameters
    foo = c.req.body_params.param('foo')

    # Only GET and POST parameters
    foo = c.req.param('foo')

    # Only file uploads
    foo = c.req.upload('foo')

    is_ok(c.req.param('foo'), 'a', 'request parameter')

with subtest('render'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'

    def text(c):
        # Render characters
        c.render(text='I ♥ Pyjoyment!')

    app.routes.get('/text', text)

    def stash(c):
        # Render characters (alternative)
        c.stash(text='I ♥ Pyjoyment!').render()

    app.routes.get('/stash', stash)

    def data(c):
        # Render binary data
        from Pyjo.JSON import encode_json

        c.render(data=encode_json({'test': 'I ♥ Pyjoyment!'}))

    app.routes.get('/data', data)

    def json(c):
        # Render JSON
        c.render(json={'test': 'I ♥ Pyjoyment!'})

    app.routes.get('/json', json)

    def yaml(c):
        # Render YAML, in the style of index.yaml of a chart repository of Helm
        c.render(yaml={'entries': {'test': [{'version': '1.0.0'}]}})

    app.routes.get('/yaml', yaml)

    def toml(c):
        # Render TOML, of a table
        c.render(toml={'server': {'workers': 4}})

    app.routes.get('/toml', toml)

    def inline(c):
        # Render inline template
        c.render(inline='<%= 1 + 1 %>')

    app.routes.get('/inline', inline)

    def template(c):
        # Render template "foo/bar.html.ep"
        c.render(template='foo/bar', format='html', handler='ep')

    app.routes.get('/template', template)

    def values(c):
        # Render template "test.*.*" with arbitrary values "foo" and "bar"
        c.render(template='test', foo='test', bar=23)

    app.routes.get('/values', values)

    def xml(c):
        # Render template "test.xml.*"
        c.render(template='test', format='xml')

    app.routes.get('/xml', xml)

    def alternative(c):
        # Render template "test.xml.*" (alternative)
        c.render('test', format='xml')

    app.routes.get('/alternative', alternative)

    tmp = tempdir()
    tmp.child('foo').make_path()
    tmp.child('foo', 'bar.html.ep').spew(b'<p>Bar</p>\n')
    tmp.child('test.html.ep').spew(b'<%= foo %> <%= bar %>\n')
    tmp.child('test.xml.ep').spew(b'<test>works</test>\n')
    app.renderer.paths.append(str(tmp))

    is_ok(request(app, '/text').res.text, 'I ♥ Pyjoyment!', 'characters')
    is_ok(request(app, '/stash').res.text, 'I ♥ Pyjoyment!', 'characters from the stash')
    is_deeply_ok(request(app, '/data').res.json(), {'test': 'I ♥ Pyjoyment!'}, 'binary data')
    is_deeply_ok(request(app, '/json').res.json(), {'test': 'I ♥ Pyjoyment!'}, 'JSON')
    is_ok(request(app, '/yaml').res.text, 'entries:\n  test:\n  - version: 1.0.0\n', 'YAML')
    is_ok(request(app, '/toml').res.text, '[server]\nworkers = 4\n', 'TOML')
    is_ok(request(app, '/inline').res.text, '2\n', 'inline template')
    is_ok(request(app, '/template').res.text, '<p>Bar</p>\n', 'template')
    is_ok(request(app, '/values').res.text, 'test 23\n', 'template with values')
    res = request(app, '/xml').res
    is_deeply_ok([res.text, res.headers.content_type], ['<test>works</test>\n', 'application/xml'], 'XML')
    is_ok(request(app, '/alternative').res.text, '<test>works</test>\n', 'XML (alternative)')
    app, c = controller()
    throws_ok(lambda: c.render(), re.compile(r'Could not render a response'), 'nothing to render')

with subtest('render_later'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'

    def action(c):
        c = c.render_later()

        # Delayed rendering
        c.render_later()
        Pyjo.IOLoop.timer(0.1, lambda loop: c.render(text='Delayed by 2 seconds!'))

    app.routes.get('/', action)
    is_ok(request(app, '/').res.text, 'Delayed by 2 seconds!', 'delayed')

with subtest('render_maybe'):
    app, c = controller()
    boolean = c.render_maybe()
    is_ok(boolean, None, 'nothing rendered')
    boolean = c.render_maybe(foo='bar', baz=23)
    boolean = c.render_maybe('foo/index', format='html')
    is_ok(boolean, None, 'no template')
    is_ok(c.stash('foo'), None, 'arguments localized')

    app, c = controller()
    tmp = tempdir()
    tmp.child('index.html.ep').spew(b'Index\n')
    app.renderer.paths.append(str(tmp))

    # Render template "index_local" only if it exists
    c.render_maybe('index_local') or c.render('index')

    is_ok(c.res.text, 'Index\n', 'fallback')

with subtest('render_to_string'):
    app, c = controller()
    output = c.render_to_string('foo/index', format='pdf')
    is_ok(output, None, 'no template')
    is_ok(c.render_to_string(text='works'), b'works', 'text')

    # Render inline template
    two = c.render_to_string(inline='<%= 1 + 1 %>')

    is_ok(two, '2\n', 'inline template')
    isa_ok(two, Pyjo.String.HTML.object, 'markup')

with subtest('rendered'):
    app, c = controller()
    c = c.rendered()
    is_ok(c.res.code, 200, 'default status')
    app, c = controller()
    c = c.rendered(302)
    is_ok(c.res.code, 302, 'status')

    app, c = controller()

    # Custom response
    c.res.headers.content_type = 'text/plain'
    c.res.body = b'Hello World!'
    c.rendered(200)

    is_ok(c.res.body, b'Hello World!', 'custom response')

with subtest('req'):
    app, c = controller()
    c.req.url.parse('http://sri:secret@example.com/?foo=bar')
    c.req.headers.user_agent = 'Pyjo'
    c.req.headers.header('Custom-Header', 'custom')
    c.req.body = b'[{"foo": "baz"}]'
    req = c.req

    # Longer version
    req = c.tx.req

    # Extract request information
    id = c.req.request_id
    method = c.req.method
    url = c.req.url.to_abs()
    info = c.req.url.to_abs().userinfo
    host = c.req.url.to_abs().host
    agent = c.req.headers.user_agent
    custom = c.req.headers.header('Custom-Header')
    data = c.req.body
    string = c.req.text
    hash = c.req.params.to_dict()
    all = c.req.uploads
    value = c.req.json()
    foo = c.req.json('/0/foo')
    dom = c.req.dom()

    is_deeply_ok(
        [method, info, host, agent, custom, hash, foo],
        ['GET', 'sri:secret', 'example.com', 'Pyjo', 'custom', {'foo': 'bar'}, 'baz'],
        'request information',
    )

with subtest('res'):
    app, c = controller()
    res = c.res

    # Longer version
    res = c.tx.res

    # Force file download by setting a response header
    c.res.headers.content_disposition = 'attachment; filename=foo.png;'

    # Use a custom response header
    c.res.headers.header('Custom-Header', 'whatever')

    # Make sure response is cached correctly
    c.res.headers.cache_control = 'public, max-age=300'
    c.res.headers.append('Vary', 'Accept-Encoding')

    is_ok(res.headers.header('Custom-Header'), 'whatever', 'header')

with subtest('send'):
    app, c = controller()
    throws_ok(lambda: c.send('I ♥ Pyjoyment!'), re.compile(r'No WebSocket connection'), 'no WebSocket')

    app = Pyjoyment.new()
    app.log.level = 'fatal'

    @app.routes.websocket('/')
    def send(c):
        c.send({'binary': b'data'})
        c.send({'text': b'data'})
        c.send({'json': {'test': [1, 2, 3]}})

        # Send "Text" message
        c.send('I ♥ Pyjoyment!')

        # Send JSON object as "Text" message
        c.send({'json': {'test': 'I ♥ Pyjoyment!'}})

        # Send JSON object as "Binary" message
        c.send({'binary': encode_json({'test': 'I ♥ Pyjoyment!'})})

        # Send "Ping" frame
        from Pyjo.WebSocket import WS_PING

        c.send([1, 0, 0, 0, WS_PING, b'Hello World!'])

        # Make sure the first message has been written before continuing
        c.send('First message!', lambda c: c.send('Second message!'))

        # Increase inactivity timeout for connection to 300 seconds
        c.inactivity_timeout(300)

    (
        Pyjo.Test.Pyjo.new(app)
        .websocket_ok('/')
        .message_ok()
        .message_is({'binary': b'data'})
        .message_ok()
        .message_is({'text': b'data'})
        .message_ok()
        .json_message_is({'test': [1, 2, 3]})
        .message_ok()
        .message_is('I ♥ Pyjoyment!')
        .message_ok()
        .json_message_is({'test': 'I ♥ Pyjoyment!'})
        .message_ok()
        .json_message_is({'test': 'I ♥ Pyjoyment!'})
        .message_ok()
        .message_is('First message!')
        .message_ok()
        .message_is('Second message!')
        .finish_ok()
    )

with subtest('session'):
    app, c = controller()
    session = c.session()
    is_deeply_ok(session, {}, 'empty')
    c = c.session({'foo': 'bar'})
    c = c.session(foo='bar')
    foo = c.session('foo')
    is_ok(foo, 'bar', 'value')

    # Manipulate session
    c.session()['foo'] = 'bar'
    foo = c.session()['foo']
    del c.session()['foo']

    # Expiration date in seconds from now (persists between requests)
    c.session(expiration=604800)

    # Expiration date as absolute epoch time (only valid for one request)
    c.session(expires=time.time() + 604800)

    # Delete whole session by setting an expiration date in the past
    c.session(expires=1)

    is_deeply_ok(c.session(), {'expiration': 604800, 'expires': 1}, 'session')

with subtest('signed_cookie'):
    app, c = controller()
    c = c.signed_cookie('foo', 'bar')
    c = c.signed_cookie('foo', 'bar', {'path': '/'})
    signed = c.res.cookies()[0].value
    like_ok(signed, r'^bar--[0-9a-f]{64}$', 'signed')
    c.req.cookies({'name': 'foo', 'value': signed})
    value = c.signed_cookie('foo')
    is_ok(value, 'bar', 'verified')

with subtest('stash'):
    app, c = controller()
    hash = c.stash()
    c = c.stash({'foo': 'bar', 'baz': 23})
    c = c.stash(foo='bar', baz=23)
    foo = c.stash('foo')
    is_ok(foo, 'bar', 'value')

    # Remove value
    foo = c.stash().pop('foo')

    # Assign multiple values at once
    c.stash(foo='test', bar=23)

    is_ok(c.stash('bar'), 23, 'values')

with subtest('url_for'):
    app, c = controller()
    app.routes.get('/test/:name').set(name='test')
    app.routes.get('/:name').set(name='current')
    c.req.url.parse('/foo')
    app.routes.match(c)
    url = c.url_for()
    url = c.url_for(name='sebastian')
    url = c.url_for({'name': 'sebastian'})
    is_ok(url.to_str(), '/sebastian', 'current route')
    url = c.url_for('test', name='sebastian')
    url = c.url_for('test', {'name': 'sebastian'})
    is_ok(url.to_str(), '/test/sebastian', 'named route')
    url = c.url_for('/index.html')
    url = c.url_for('//example.com/index.html')
    url = c.url_for('http://example.com/index.html')
    url = c.url_for('mailto:sri@example.com')
    url = c.url_for('#whatever')
    is_ok(url.to_str(), '#whatever', 'fragment')

    # Rebuild URL for the current route
    c.url_for()

    # Rebuild URL for the current route, but replace the "name" placeholder value
    c.url_for(name='sebastian')

    # Absolute URL for the current route
    c.url_for().to_abs()

    # Build URL for route "test" with two placeholder values
    c.url_for('test', name='sebastian', foo='bar')

    # "http://127.0.0.1:3000/index.html" if application was started with Pyjo.Server.Reload
    c.url_for('/index.html').to_abs()

    # "https://127.0.0.1:443/index.html" if application was started with Pyjo.Server.Reload
    c.url_for('/index.html').to_abs().set(scheme='https', port=443)

    # "/index.html?foo=bar" if application is deployed under "/"
    c.url_for('/index.html').set(query={'foo': 'bar'})

    # "/myapp/index.html?foo=bar" if application is deployed under "/myapp"
    c.url_for('/index.html').set(query={'foo': 'bar'})

    is_ok(c.url_for('/index.html').set(query={'foo': 'bar'}).to_str(), '/index.html?foo=bar', 'query')

    c.req.url.parse('/list?q=mojo&page=1')

    # "/list?q=mojo&page=2" if current request was for "/list?q=mojo&page=1"
    url = c.url_with().set(query={'page': 2})
    is_ok(url.query.param('page'), '2', 'inherited query')

with subtest('url_for_asset'):
    app, c = controller()
    url = c.url_for_asset('/app.js')
    is_ok(url.to_str(), '/assets/app.js', 'asset')

with subtest('url_for_file'):
    app, c = controller()
    url = c.url_for_file('/index.html')
    is_ok(url.to_str(), '/index.html', 'file')

with subtest('write'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'

    def one(c):
        c = c.write()
        c = c.write(b'')

    app.routes.get('/1', one)

    def two(c):
        # Keep connection alive (with Content-Length header)
        c.res.headers.content_length = 6
        c.write(b'Hel', lambda c: c.write(b'lo!'))

    app.routes.get('/2', two)

    def three(c):
        # Close connection when finished (without Content-Length header)
        c.write(b'Hel', lambda c: c.write(b'lo!', lambda c: c.finish()))

    app.routes.get('/3', three)

    is_ok(request(app, '/2').res.body, b'Hello!', 'with Content-Length')
    is_ok(request(app, '/3').res.body, b'Hello!', 'without Content-Length')

with subtest('write_chunk'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'

    def action(c):
        # Make sure previous chunk has been written before continuing
        c.write_chunk(b'H', lambda c: c.write_chunk(b'ell', lambda c: c.finish(b'o!')))

    app.routes.get('/', action)

    is_ok(request(app, '/').res.body, b'Hello!', 'chunked')

with subtest('write_sse'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'

    def action(c):
        c.res.headers.content_type = 'text/event-stream'

        # Send event with default "message" type
        c.write_sse({'text': 'Hello World!'})

        # You can send comments in regular intervals to keep the connection alive
        c.write_sse({'comment': 'Keep connection alive!'})

        # Make sure previous event has been written before continuing (id and type are optional)
        c.write_sse(
            {'id': 23, 'type': 'greeting', 'text': 'Hello World!'},
            lambda c: c.write_sse({'id': 24, 'type': 'farewell', 'text': 'Goodbye World!'}, lambda c: c.finish()),
        )

    app.routes.get('/', action)

    ua = Pyjo.UserAgent.new()
    ua.server.app = app
    tx = ua.build_tx('GET', '/')
    events = []
    tx.res.content.on('sse', lambda content, event: events.append(event and event.get('type')))
    ua.start(tx)
    is_deeply_ok([type for type in events if type], ['message', 'greeting', 'farewell'], 'events')

with subtest('helper'):
    import Pyjoyment.Controller

    class MyApp_Model_Users:
        def list(self):
            return ['sri', 'tom']

    # The helper, which startup registers with app.helper('users', users)
    def users(c: Pyjoyment.Controller.object) -> MyApp_Model_Users:
        return c.app.users

    # The base class of the controllers of the application
    class Controller(Pyjoyment.Controller.object):
        users = Pyjoyment.Controller.Helper(users)

    class Users(Controller):
        def index(self) -> None:
            self.render(json=self.users().list())

    sys.modules['MyApp_Controller_Users'] = types.ModuleType('MyApp_Controller_Users')
    sys.modules['MyApp_Controller_Users'].object = Users
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.users = MyApp_Model_Users()
    app.helper('users', users)
    app.routes.get('/users').to('MyApp_Controller_Users#index', namespace='')
    tx = request(app, '/users')
    is_deeply_ok(decode_json(tx.res.body), ['sri', 'tom'], 'helper of the application')

    app.routes.get('/not_action').to('MyApp_Controller_Users#users', namespace='')
    is_ok(request(app, '/not_action').res.code, 500, 'not an action, a route without action')

    def _not_found(c):
        return c.render(text='Not here', status=404)

    class Reply:
        not_found = Pyjoyment.Controller.Helper(_not_found)

    class Helpers:
        reply: Reply

    ok(Helpers.__annotations__['reply'] is Reply, 'prefix of nested helpers')

done_testing()
