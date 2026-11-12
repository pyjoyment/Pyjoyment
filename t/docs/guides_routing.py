from Pyjo.File import curfile

import contextlib
import io
import random
import re
import sys

from unittest.mock import patch


# The examples of docs/guides/routing.rst, which includes them: a directory for each application, whose plugins in the
# namespace Pyjoyment.Plugin are found only by a directory that is on sys.path before Pyjoyment.Plugin is imported, as
# extend_path extends the namespace then
EXAMPLES = curfile().dirname().dirname().sibling('docs', 'guides', 'routing')
PLUGINS = [EXAMPLES.child(name).to_str() for name in ('werewolf', 'app_plugin')]
sys.path[0:0] = PLUGINS

import Pyjo.IOLoop  # noqa: E402
import Pyjo.Test.Pyjo  # noqa: E402
import Pyjoyment  # noqa: E402
import Pyjoyment.Controller  # noqa: E402
import Pyjoyment.Plugin  # noqa: E402
import Pyjoyment.Routes.Match  # noqa: E402
import Pyjoyment.Routes.Pattern  # noqa: E402

from Pyjo.Test import *  # noqa: E402


# The package MyApp of these directories would hide the one of another example, which has no __init__.py
for path in PLUGINS:
    sys.path.remove(path)


def match(r, path, method='GET', websocket=False):
    # The stack of the destinations of a request, the stash of each dispatch cycle
    m = Pyjoyment.Routes.Match.new(root=r)
    m.find(Pyjoyment.Controller.new(), method=method, path=path, websocket=websocket)
    return m.stack


def endpoint(r, path, method='GET'):
    stack = match(r, path, method)
    return stack[-1] if stack else None


def pattern(route, path):
    return Pyjoyment.Routes.Pattern.new(route).match(path)


@contextlib.contextmanager
def application(name):
    # The package MyApp of an example, which another example has too
    path = EXAMPLES.child(name).to_str()
    sys.path.insert(0, path)
    for module in [module for module in sys.modules if module == 'MyApp' or module.startswith('MyApp.')]:
        del sys.modules[module]
    try:
        yield path
    finally:
        sys.path.remove(path)


with subtest('Routes'):
    is_deeply_ok(pattern('/user/:role/:id', '/user/admin/23'), {'role': 'admin', 'id': '23'}, 'two placeholders')
    p = Pyjoyment.Routes.Pattern.new('/user/admin/:id')
    p.match('/user/admin/23')
    is_ok(p.regex.pattern, '^/user/admin/([^/.]+)', 'regular expression')
    is_deeply_ok(pattern('/user/:role/:id', '/user/admin/23/'), {'role': 'admin', 'id': '23'}, 'trailing slash')

with subtest('Reversibility'):
    is_deeply_ok(pattern('/:name', '/sebastian'), {'name': 'sebastian'}, 'match')
    is_ok(Pyjoyment.Routes.Pattern.new('/:name').render({'name': 'sebastian'}), '/sebastian', 'render')

with subtest('Standard placeholders'):
    is_ok(pattern('/:name/hello', '/hello'), None, 'no name')
    is_ok(pattern('/:name/hello', '/sebastian/23/hello'), None, 'slash')
    is_ok(pattern('/:name/hello', '/sebastian.23/hello'), None, 'dot')
    is_deeply_ok(pattern('/:name/hello', '/sebastian/hello'), {'name': 'sebastian'}, 'name')
    is_deeply_ok(pattern('/:name/hello', '/sebastian23/hello'), {'name': 'sebastian23'}, 'name with number')
    is_deeply_ok(pattern('/:name/hello', '/sebastian 23/hello'), {'name': 'sebastian 23'}, 'name with space')
    is_ok(pattern('/<:name>hello', '/hello'), None, 'no name')
    is_ok(pattern('/<:name>hello', '/sebastian/23hello'), None, 'slash')
    is_ok(pattern('/<:name>hello', '/sebastian.23hello'), None, 'dot')
    is_deeply_ok(pattern('/<:name>hello', '/sebastianhello'), {'name': 'sebastian'}, 'name')
    is_deeply_ok(pattern('/<:name>hello', '/sebastian23hello'), {'name': 'sebastian23'}, 'name with number')
    is_deeply_ok(pattern('/<:name>hello', '/sebastian 23hello'), {'name': 'sebastian 23'}, 'name with space')
    is_deeply_ok(pattern('/<one>♥<two>', '/i♥mojolicious'), {'one': 'i', 'two': 'mojolicious'}, 'without colon')

with subtest('Relaxed placeholders'):
    is_ok(pattern('/#name/hello', '/hello'), None, 'no name')
    is_ok(pattern('/#name/hello', '/sebastian/23/hello'), None, 'slash')
    is_deeply_ok(pattern('/#name/hello', '/sebastian.23/hello'), {'name': 'sebastian.23'}, 'dot')
    is_deeply_ok(pattern('/#name/hello', '/sebastian/hello'), {'name': 'sebastian'}, 'name')
    is_deeply_ok(pattern('/#name/hello', '/sebastian23/hello'), {'name': 'sebastian23'}, 'name with number')
    is_deeply_ok(pattern('/#name/hello', '/sebastian 23/hello'), {'name': 'sebastian 23'}, 'name with space')
    is_deeply_ok(pattern('/music/#filename', '/music/song.mp3'), {'filename': 'song.mp3'}, 'file name')

with subtest('Wildcard placeholders'):
    is_ok(pattern('/*name/hello', '/hello'), None, 'no name')
    is_deeply_ok(pattern('/*name/hello', '/sebastian/23/hello'), {'name': 'sebastian/23'}, 'slash')
    is_deeply_ok(pattern('/*name/hello', '/sebastian.23/hello'), {'name': 'sebastian.23'}, 'dot')
    is_deeply_ok(pattern('/*name/hello', '/sebastian/hello'), {'name': 'sebastian'}, 'name')
    is_deeply_ok(pattern('/*name/hello', '/sebastian23/hello'), {'name': 'sebastian23'}, 'name with number')
    is_deeply_ok(pattern('/*name/hello', '/sebastian 23/hello'), {'name': 'sebastian 23'}, 'name with space')
    is_deeply_ok(pattern('/music/*filepath', '/music/rock/song.mp3'), {'filepath': 'rock/song.mp3'}, 'file path')

with subtest('Minimal route'):
    with application('minimal'):
        with Pyjo.Test.Pyjo.new('MyApp') as t:
            t.get_ok('/welcome').status_is(200).content_is('Hello there.')

with subtest('Route shortcuts'):
    app = Pyjoyment.new()
    app.get('/welcome').to(controller='foo', action='welcome')
    is_deeply_ok(endpoint(app.routes, '/welcome'), {'controller': 'foo', 'action': 'welcome'}, 'same as routes')

with subtest('Routing destination'):
    r = Pyjoyment.new().routes
    r.get('/welcome').to(controller='foo', action='welcome')
    is_deeply_ok(endpoint(r, '/welcome'), {'controller': 'foo', 'action': 'welcome'}, 'destination')

with subtest('HTTP methods'):
    r = Pyjoyment.new().routes
    r.get('/hello').to(controller='foo', action='hello')
    is_ok(endpoint(r, '/hello', 'PUT'), None, 'PUT')
    is_deeply_ok(endpoint(r, '/hello'), {'controller': 'foo', 'action': 'hello'}, 'GET')
    r = Pyjoyment.new().routes
    r.put('/hello').to(controller='foo', action='hello')
    is_deeply_ok(endpoint(r, '/hello', 'PUT'), {'controller': 'foo', 'action': 'hello'}, 'PUT')
    r.post('/hello').to(controller='foo', action='hello')
    is_deeply_ok(endpoint(r, '/hello', 'POST'), {'controller': 'foo', 'action': 'hello'}, 'POST')
    r.any(['GET', 'POST'], '/bye').to(controller='foo', action='bye')
    is_deeply_ok(endpoint(r, '/bye'), {'controller': 'foo', 'action': 'bye'}, 'GET')
    is_deeply_ok(endpoint(r, '/bye', 'POST'), {'controller': 'foo', 'action': 'bye'}, 'POST')
    is_ok(endpoint(r, '/bye', 'PUT'), None, 'PUT')
    r.any('/whatever').to(controller='foo', action='whatever')
    is_deeply_ok(endpoint(r, '/whatever', 'DELETE'), {'controller': 'foo', 'action': 'whatever'}, 'any')

    # HEAD and _method, which the router reads from the request
    app = Pyjoyment.new()
    app.routes.get('/test').to(cb=lambda c: c.render(text='test'))
    app.routes.put('/stuff').to(cb=lambda c: c.render(text='stuff'))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/test').status_is(200).content_is('test')
        t.head_ok('/test').status_is(200).header_is('Content-Length', '4').content_is('')
        t.put_ok('/stuff').status_is(200).content_is('stuff')
        t.post_ok('/stuff?_method=PUT').status_is(200).content_is('stuff')
        t.post_ok('/stuff').status_is(404)

with subtest('IRIs'):
    r = Pyjoyment.new().routes
    r.get('/☃').to(controller='foo', action='snowman')
    is_deeply_ok(endpoint(r, '/☃'), {'controller': 'foo', 'action': 'snowman'}, 'snowman')
    app = Pyjoyment.new()
    app.routes.get('/☃').to(cb=lambda c: c.render(text='snowman'))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/%E2%98%83').status_is(200).content_is('snowman')

with subtest('Stash'):
    r = Pyjoyment.new().routes
    r.get('/bye').to(controller='foo', action='bye', mymessage='Bye')
    is_deeply_ok(endpoint(r, '/bye'), {'controller': 'foo', 'action': 'bye', 'mymessage': 'Bye'}, 'stash')

    app = Pyjoyment.new()

    def bye(self):

        # Get message from stash
        msg = self.stash('mymessage')

        # Change message in stash
        self.stash(mymessage='Welcome')

        self.render(text=f'{msg} {self.stash("mymessage")}')

    app.routes.get('/bye').to(cb=bye, mymessage='Bye')
    app.routes.get('/howdy').to(cb=lambda c: c.render(text=c.stash('mymessage')))
    app.defaults(mymessage='Howdy')
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/bye').status_is(200).content_is('Bye Welcome')
        t.get_ok('/howdy').status_is(200).content_is('Howdy')

with subtest('Nested routes'):
    r = Pyjoyment.new().routes
    foo = r.any('/foo').to(controller='foo')
    foo.get('/bar').to(action='bar')
    is_ok(endpoint(r, '/foo'), None, 'no endpoint')
    is_deeply_ok(endpoint(r, '/foo/bar'), {'controller': 'foo', 'action': 'bar'}, 'endpoint')

    cats = r.any('/cats').to(controller='cats', action='default')
    cats.get('/').to(action='index')
    cats.get('/nyan').to(action='nyan')
    cats.get('/lol')
    is_deeply_ok(endpoint(r, '/cats'), {'controller': 'cats', 'action': 'index'}, 'index')
    is_deeply_ok(endpoint(r, '/cats/nyan'), {'controller': 'cats', 'action': 'nyan'}, 'nyan')
    is_deeply_ok(endpoint(r, '/cats/lol'), {'controller': 'cats', 'action': 'default'}, 'default')

with subtest('Special stash values'):
    with application('special'):
        with Pyjo.Test.Pyjo.new('MyApp') as t:
            t.get_ok('/bye').status_is(200).content_is('Good bye.')

            r = t.app.routes
            r.get('/bye2').to('foo#bye', mymessage='Bye')
            is_deeply_ok(endpoint(r, '/bye2'), {'controller': 'foo', 'action': 'bye', 'mymessage': 'Bye'}, 'shortcut')
            t.get_ok('/bye2').status_is(200).content_is('Good bye.')

            # foo-bar and Foo.Bar are the class Bar of MyApp.Controller.Foo or MyApp.Foo, which do not exist, as in Mojo
            r.get('/hi').to('foo-bar#hi')
            r.get('/hi2').to('Foo.Bar#hi')
            t.get_ok('/hi').status_is(500).text_is('#error', 'Controller "MyApp.Foo.Bar" does not exist')
            t.get_ok('/hi2').status_is(500).text_is('#error', 'Controller "MyApp.Foo.Bar" does not exist')
            r.get('/bye3').to('Foo#bye')
            t.get_ok('/bye3').status_is(200).content_is('Good bye.')

            # The class has to be a controller
            r.get('/routes').to('Routes#bye', namespace='Pyjoyment')
            t.get_ok('/routes').status_is(500)

with subtest('Timeouts of routes'):
    r = Pyjoyment.Routes.new()

    # Ten minutes of silence, and two minutes to the end of the response at most
    r.post('/chat', {'inactivity_timeout': 600, 'request_timeout': 120}).to('chat#reply')

    # A stream of events with a comment every 15 seconds
    r.get('/events', {'heartbeat': 15}).to('chat#events')
    is_deeply_ok(endpoint(r, '/events'), {'heartbeat': 15, 'controller': 'chat', 'action': 'events'}, 'heartbeat')

    # The same for every route of a group
    llm = r.under('/llm', {'inactivity_timeout': 600, 'request_timeout': 120})
    llm.post('/complete').to('llm#complete')

    timeouts = {'inactivity_timeout': 600, 'request_timeout': 120}
    is_deeply_ok(endpoint(r, '/chat', 'POST'), {**timeouts, 'controller': 'chat', 'action': 'reply'}, 'route')
    is_deeply_ok(match(r, '/llm/complete', 'POST')[0], timeouts, 'group')
    is_deeply_ok(
        endpoint(r, '/llm/complete', 'POST'), {**timeouts, 'controller': 'llm', 'action': 'complete'}, 'nested'
    )

with subtest('Namespaces'):
    with application('special'):
        with Pyjo.Test.Pyjo.new('MyApp') as t:
            r = t.app.routes
            r.get('/bye1').to(namespace='MyApp.Controller', controller='Foo', action='bye')
            r.get('/bye2').to('foo#bye', namespace='MyApp.Controller')
            r.get('/bye3').to('Foo#bye', namespace='MyApp.Controller')
            t.get_ok('/bye1').status_is(200).content_is('Good bye.')
            t.get_ok('/bye2').status_is(200).content_is('Good bye.')
            t.get_ok('/bye3').status_is(200).content_is('Good bye.')
            r.get('/bye4').to(namespace='MyApp.MyController', controller='Foo.Bar', action='bye')
            r.get('/bye5').to('foo-bar#bye', namespace='MyApp.MyController')
            r.get('/hey').to('Foo.Bar#hey', namespace='MyApp.MyController')
            for path in ('/bye4', '/bye5', '/hey'):
                t.get_ok(path).status_is(500).text_is(
                    '#error', 'Controller "MyApp.MyController.Foo.Bar" does not exist'
                )

            is_deeply_ok(r.namespaces, ['MyApp.Controller', 'MyApp'], 'default namespaces')
            r.namespaces = ['MyApp.MyController']
            t.get_ok('/bye').status_is(500).text_is('#error', 'Controller "MyApp.MyController.Foo" does not exist')

with subtest('Route to callback'):
    app = Pyjoyment.new()
    r = app.routes
    r.get('/bye').to(cb=lambda c: c.render(text='Good bye.'))

    @r.get('/bye2')
    def bye2(c):
        c.render(text='Good bye.')

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/bye').status_is(200).content_is('Good bye.')
        t.get_ok('/bye2').status_is(200).content_is('Good bye.')

with subtest('Named routes'):
    app = Pyjoyment.new()
    r = app.routes
    r.get('/foo/:user').to('foo#bar').set(name='baz')
    is_deeply_ok(endpoint(r, '/foo/marcus'), {'controller': 'foo', 'action': 'bar', 'user': 'marcus'}, 'match')
    r.get('/foo/bar').to('test#stuff')
    urls = {}

    @r.get('/urls/:user')
    def urls_(c):
        urls['baz'] = c.url_for('baz').to_str()
        urls['jan'] = c.url_for('baz', user='jan').to_str()
        urls['abs'] = c.url_for('baz', user='jan').to_abs().to_str()
        urls['foobar'] = c.url_for('foobar').to_str()
        urls['current'] = c.url_for('current').to_str()
        urls['none'] = c.url_for().to_str()
        urls['name'] = c.current_route()
        if c.current_route('urlsuser'):
            c.stash(button='green')
        c.render(text=c.stash('button') or '')

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/urls/marcus').status_is(200).content_is('green')
        is_ok(urls['baz'], '/foo/marcus', 'in previous request context')
        is_ok(urls['jan'], '/foo/jan', 'with placeholder')
        like_ok(urls['abs'], re.compile(r'^http://127\.0\.0\.1:\d+/foo/jan$'), 'absolute')
        is_ok(urls['foobar'], '/foo/bar', 'automatic name')
        is_ok(urls['current'], '/urls/marcus', 'current')
        is_ok(urls['none'], '/urls/marcus', 'no name')
        is_ok(urls['name'], 'urlsuser', 'current route')

with subtest('Optional placeholders'):
    r = Pyjoyment.new().routes
    r.get('/:mymessage').to('foo#bar', mymessage='hi')
    is_deeply_ok(endpoint(r, '/bye'), {'controller': 'foo', 'action': 'bar', 'mymessage': 'bye'}, 'bye')
    is_deeply_ok(endpoint(r, '/hey'), {'controller': 'foo', 'action': 'bar', 'mymessage': 'hey'}, 'hey')
    is_deeply_ok(endpoint(r, '/'), {'controller': 'foo', 'action': 'bar', 'mymessage': 'hi'}, 'optional')
    r = Pyjoyment.new().routes
    r.get('/test/:mymessage/123').to('foo#bar', mymessage='hi')
    is_deeply_ok(endpoint(r, '/test/123'), {'controller': 'foo', 'action': 'bar', 'mymessage': 'hi'}, 'optional')
    is_deeply_ok(endpoint(r, '/test/bye/123'), {'controller': 'foo', 'action': 'bar', 'mymessage': 'bye'}, 'bye')

with subtest('Restrictive placeholders'):
    r = Pyjoyment.new().routes
    r.get('/:name', name=['bender', 'leela']).to('foo#bar')
    is_ok(endpoint(r, '/fry'), None, 'fry')
    is_deeply_ok(endpoint(r, '/bender'), {'controller': 'foo', 'action': 'bar', 'name': 'bender'}, 'bender')
    is_deeply_ok(endpoint(r, '/leela'), {'controller': 'foo', 'action': 'bar', 'name': 'leela'}, 'leela')
    r = Pyjoyment.new().routes
    r.get('/:number', number=re.compile(r'\d+')).to('foo#bar')
    is_deeply_ok(endpoint(r, '/23'), {'controller': 'foo', 'action': 'bar', 'number': '23'}, 'number')
    is_ok(endpoint(r, '/test'), None, 'not a number')
    r = Pyjoyment.new().routes
    r.get('/:name', name=re.compile(r'[a-zA-Z]+')).to('foo#bar')
    is_ok(endpoint(r, '/23'), None, 'not a name')
    is_deeply_ok(endpoint(r, '/test'), {'controller': 'foo', 'action': 'bar', 'name': 'test'}, 'name')

with subtest('Placeholder types'):
    r = Pyjoyment.new().routes
    r.add_type('futurama_name', ['bender', 'leela'])
    r.get('/<name:futurama_name>').to('foo#bar')
    is_ok(endpoint(r, '/fry'), None, 'fry')
    is_deeply_ok(endpoint(r, '/bender'), {'controller': 'foo', 'action': 'bar', 'name': 'bender'}, 'bender')
    is_deeply_ok(endpoint(r, '/leela'), {'controller': 'foo', 'action': 'bar', 'name': 'leela'}, 'leela')
    r.add_type('upper', re.compile(r'[A-Z]+'))
    r.get('/user/<name:upper>').to('users#show')
    is_deeply_ok(endpoint(r, '/user/ROOT'), {'controller': 'users', 'action': 'show', 'name': 'ROOT'}, 'upper')
    is_ok(endpoint(r, '/user/root'), None, 'lower')
    is_ok(endpoint(r, '/user/23'), None, 'number')
    r.get('/article/<id:num>').to('articles#show')
    is_deeply_ok(endpoint(r, '/article/12'), {'controller': 'articles', 'action': 'show', 'id': '12'}, 'num')
    is_ok(endpoint(r, '/article/test'), None, 'not num')

with subtest('Introspection'):
    app = Pyjoyment.new()
    r = app.routes
    r.post('/foo/:name').to('foo#name')
    r.under('/bar').to('bar#auth').websocket('/baz').to('bar#baz')
    r.any('/yada').to('yada#yada')
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        app.start('routes', '-v')
    is_ok(
        stdout.getvalue(),
        '/foo/:name  ....  POST  fooname  ^/foo/([^/.]+)\n'
        '/bar        ..U.  *     bar      ^/bar\n'
        '  +/baz     ...W  GET   baz      ^/baz\n'
        '/yada       ....  *     yada     ^/yada\n',
        'routes -v',
    )

with subtest('Under'):
    r = Pyjoyment.new().routes
    foo = r.under('/foo').to('foo#baz')
    foo.get('/bar').to('#bar')
    is_deeply_ok(match(r, '/foo'), [], 'no endpoint')
    is_deeply_ok(
        match(r, '/foo/bar'),
        [{'controller': 'foo', 'action': 'baz'}, {'controller': 'foo', 'action': 'bar'}],
        'two dispatch cycles',
    )

    app = Pyjoyment.new()
    r = app.routes

    @r.under('/')
    def auth(c):

        # Authenticated
        if c.req.headers.header('X-Bender'):
            return True

        # Not authenticated
        c.render(text="You're not Bender.", status=401)
        return None

    auth.get('/blackjack').to(cb=lambda c: c.render(text='Blackjack!'))
    stack = match(r, '/blackjack')
    ok(callable(stack[0]['cb']), 'callback')
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/blackjack').status_is(401).content_is("You're not Bender.")
        t.get_ok('/blackjack', {'X-Bender': '1'}).status_is(200).content_is('Blackjack!')

        app = Pyjoyment.new()
        r = app.routes

        @r.under('/maybe')
        def maybe(c):

            # Wait 3 seconds and then give visitors a 50% chance to continue
            @Pyjo.IOLoop.timer(0.03)
            def timer(loop):

                # Loser
                if not random.randrange(2):
                    return c.render(text='No luck.')

                # Winner
                c.proceed()

            return None

        maybe.get('/').to(cb=lambda c: c.render(text='Winner!'))
        with Pyjo.Test.Pyjo.new(app) as t:
            with patch('random.randrange', return_value=0):
                t.get_ok('/maybe').status_is(200).content_is('No luck.')
            with patch('random.randrange', return_value=1):
                t.get_ok('/maybe').status_is(200).content_is('Winner!')

            app = Pyjoyment.new()
            r = app.routes
            one = r.under('/one').to(cb=lambda c: True, action='first')
            two = one.under('/two').to(cb=lambda c: True, action='second')
            three = two.under('/three').to(cb=lambda c: True, action='third')

            @three.get('/four', {'action': 'fourth'})
            def four(c):
                # Action of the fourth dispatch cycle
                action = c.match.stack[3]['action']
                c.render(text=action)

            with Pyjo.Test.Pyjo.new(app) as t:
                t.get_ok('/one/two/three/four').status_is(200).content_is('fourth')

with subtest('Formats'):
    r = Pyjoyment.new().routes
    r.get('/foo', format=['rss', 'xml']).to('foo#bar')
    is_ok(endpoint(r, '/foo.txt'), None, 'txt')
    is_deeply_ok(endpoint(r, '/foo.rss'), {'controller': 'foo', 'action': 'bar', 'format': 'rss'}, 'rss')
    is_deeply_ok(endpoint(r, '/foo.xml'), {'controller': 'foo', 'action': 'bar', 'format': 'xml'}, 'xml')

    r = Pyjoyment.new().routes
    r.get('/foo', format=['html', 'txt']).to('foo#bar', format=None)
    is_deeply_ok(endpoint(r, '/foo'), {'controller': 'foo', 'action': 'bar', 'format': None}, 'no format')
    is_deeply_ok(endpoint(r, '/foo.html'), {'controller': 'foo', 'action': 'bar', 'format': 'html'}, 'html')
    is_deeply_ok(endpoint(r, '/foo.txt'), {'controller': 'foo', 'action': 'bar', 'format': 'txt'}, 'txt')

    r = Pyjoyment.new().routes
    with_format = r.any('/', format=['html', 'json']).to(format=None)
    with_format.get('/foo').to('foo#one')
    with_format.get('/bar').to('bar#two')
    is_deeply_ok(endpoint(r, '/foo'), {'controller': 'foo', 'action': 'one', 'format': None}, 'foo')
    is_deeply_ok(endpoint(r, '/foo.html'), {'controller': 'foo', 'action': 'one', 'format': 'html'}, 'foo.html')
    is_deeply_ok(endpoint(r, '/foo.json'), {'controller': 'foo', 'action': 'one', 'format': 'json'}, 'foo.json')
    is_deeply_ok(endpoint(r, '/bar'), {'controller': 'bar', 'action': 'two', 'format': None}, 'bar')
    is_deeply_ok(endpoint(r, '/bar.html'), {'controller': 'bar', 'action': 'two', 'format': 'html'}, 'bar.html')
    is_deeply_ok(endpoint(r, '/bar.json'), {'controller': 'bar', 'action': 'two', 'format': 'json'}, 'bar.json')

    app = Pyjoyment.new()
    r = app.routes
    r.get('/foo/:id', format=['txt']).to('foo#bar').set(name='baz')
    is_deeply_ok(endpoint(r, '/foo/23.txt'), {'controller': 'foo', 'action': 'bar', 'id': '23', 'format': 'txt'}, 'txt')
    c = app.build_controller()
    is_ok(c.url_for('baz', id=24, format='txt').to_str(), '/foo/24.txt', 'url_for')

with subtest('WebSockets'):
    with application('websockets'):
        app = Pyjoyment.new()
        app.routes.namespaces = ['MyApp.Controller']
        app.routes.websocket('/echo').to('foo#echo')
        is_ok(endpoint(app.routes, '/echo'), None, 'no handshake')
        with Pyjo.Test.Pyjo.new(app) as t:
            t.websocket_ok('/echo').header_is('Upgrade', 'websocket').send_ok('hi').message_ok().message_is('echo: hi')
            t.finish_ok()

with subtest('Catch-all route'):
    app = Pyjoyment.new()
    r = app.routes
    r.get('/welcome').to(cb=lambda c: c.render(text='Welcome!'))

    @r.any('/*whatever', {'whatever': ''})
    def whatever(c):
        whatever = c.param('whatever')
        c.render(text=f'/{whatever} did not match.', status=404)

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/welcome').status_is(200).content_is('Welcome!')
        t.get_ok('/').status_is(404).content_is('/ did not match.')
        t.post_ok('/foo/bar.txt').status_is(404).content_is('/foo/bar.txt did not match.')

with subtest('Conditions'):
    app = Pyjoyment.new()
    r = app.routes
    r.get('/').requires(headers={'Origin': re.compile(r'python\.org')}).to(cb=lambda c: c.render(text='Python'))
    r.get('/').requires(agent=re.compile(r'Firefox')).to(cb=lambda c: c.render(text='Firefox'))
    r.get('/').requires(agent=re.compile(r'Internet Explorer')).to(cb=lambda c: c.render(text='IE'))
    r.get('/').requires(host='docs.mojolicious.org').to(cb=lambda c: c.render(text='Docs'))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/', {'Origin': 'http://python.org'}).status_is(200).content_is('Python')
        t.get_ok('/', {'User-Agent': 'Firefox'}).status_is(200).content_is('Firefox')
        t.get_ok('/', {'User-Agent': 'Internet Explorer'}).status_is(200).content_is('IE')
        t.get_ok('/', {'Host': 'docs.mojolicious.org'}).status_is(200).content_is('Docs')
        t.get_ok('/').status_is(404)

with subtest('Hooks'):
    with application('hooks'), Pyjo.Test.Pyjo.new('MyApp') as t:
        t.get_ok('/test').status_is(200).content_is('This request did not reach the router.')
        t.post_ok('/test/bye').status_is(200).content_is('This request did not reach the router.')
        t.get_ok('/welcome').status_is(500).text_is('#error', 'Controller "MyApp.Foo" does not exist')

    app = Pyjoyment.new()
    app.routes.get('/').to(cb=lambda c: c.render(text=c.stash('variant') or 'default'))

    # Make sure static files are cached
    @app.hook('after_static')
    def after_static(c):
        c.res.headers.cache_control = 'max-age=3600, must-revalidate'

    # Remove a default header
    @app.hook('after_dispatch')
    def after_dispatch(c):
        c.res.headers.remove('Server')

    # Choose template variant based on request headers
    @app.hook('before_dispatch')
    def before_dispatch(c):
        if not (agent := c.req.headers.user_agent):
            return
        if re.search(r'Internet Explorer', agent):
            c.stash(variant='ie')

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/pyjo/pyjo.css').status_is(200).header_is('Cache-Control', 'max-age=3600, must-revalidate')
        t.get_ok('/').status_is(200).header_exists_not('Server').content_is('default')
        t.get_ok('/', {'User-Agent': 'Internet Explorer'}).status_is(200).content_is('ie')

        # Forward exceptions to a web service
        app = Pyjoyment.new()
        bugs = []
        promises = []
        app.routes.post('/bugs').to(cb=lambda c: bugs.append(c.param('exception')) or c.render(text='ok'))

        @app.routes.get('/dies')
        def dies(c):
            raise Exception('Intentional error')

        @app.hook('after_dispatch')
        def forward(c):
            if not (e := c.stash('exception')):
                return
            promises.append(c.ua().post_p('/bugs', form={'exception': str(e)}))

        # The server of the user agent of an application is the one of the first application in a process, as in Mojo
        app.ua.server.app = app
        # The user agent of the application has a server of its own, which is closed here
        with Pyjo.Test.Pyjo.new(app) as t, app.ua:
            t.get_ok('/dies').status_is(500)
            promises[0].wait()
        is_ok(len(bugs), 1, 'one exception')
        like_ok(bugs[0], re.compile(r'^Intentional error'), 'exception')

        # Pass route name as argument to actions
        app = Pyjoyment.new()

        @app.hook('around_action')
        def around_action(next, c, action, last):
            return action(c, c.current_route())

        app.routes.get('/name').to(cb=lambda c, name: c.render(text=name))
        with Pyjo.Test.Pyjo.new(app) as t:
            t.get_ok('/name').status_is(200).content_is('name')

with subtest('Shortcuts'):
    r = Pyjoyment.new().routes

    # Simple "resource" shortcut
    def resource(r, name):

        # Prefix for resource
        resource = r.any(f'/{name}').to(f'{name}#')

        # Render a list of resources
        resource.get('/').to('#index').set(name=name)

        # Render a form to create a new resource (submitted to "store")
        resource.get('/create').to('#create').set(name=f'create_{name}')

        # Store newly created resource (submitted by "create")
        resource.post().to('#store').set(name=f'store_{name}')

        # Render a specific resource
        resource.get('/:id').to('#show').set(name=f'show_{name}')

        # Render a form to edit a resource (submitted to "update")
        resource.get('/:id/edit').to('#edit').set(name=f'edit_{name}')

        # Store updated resource (submitted by "edit")
        resource.put('/:id').to('#update').set(name=f'update_{name}')

        # Remove a resource
        resource.delete('/:id').to('#remove').set(name=f'remove_{name}')

        return resource

    r.add_shortcut('resource', resource)
    r.resource('users')
    is_deeply_ok(endpoint(r, '/users'), {'controller': 'users', 'action': 'index'}, 'index')
    is_deeply_ok(endpoint(r, '/users/create'), {'controller': 'users', 'action': 'create'}, 'create')
    is_deeply_ok(endpoint(r, '/users', 'POST'), {'controller': 'users', 'action': 'store'}, 'store')
    is_deeply_ok(endpoint(r, '/users/23'), {'controller': 'users', 'action': 'show', 'id': '23'}, 'show')
    is_deeply_ok(endpoint(r, '/users/23/edit'), {'controller': 'users', 'action': 'edit', 'id': '23'}, 'edit')
    is_deeply_ok(endpoint(r, '/users/23', 'PUT'), {'controller': 'users', 'action': 'update', 'id': '23'}, 'update')
    is_deeply_ok(endpoint(r, '/users/23', 'DELETE'), {'controller': 'users', 'action': 'remove', 'id': '23'}, 'remove')
    is_ok(r.find('edit_users').pattern.unparsed, '/:id/edit', 'name')

with subtest('Rearranging routes'):
    r = Pyjoyment.new().routes
    show = r.get('/show').to('example#show')
    r.any('/example').add_child(show)
    is_deeply_ok(endpoint(r, '/example/show'), {'controller': 'example', 'action': 'show'}, 'moved')
    is_ok(endpoint(r, '/show'), None, 'not at the old place')

    r.get('/secrets/show').to('secrets#show').set(name='show_secrets')
    r.find('show_secrets').remove()
    is_ok(endpoint(r, '/secrets/show'), None, 'removed')

    r.get('/something/else').to('something#else').set(name='test')
    test = r.find('test')
    test.pattern.parse('/example/test')
    test.pattern.defaults = {'controller': 'example', 'action': 'test'}
    is_deeply_ok(endpoint(r, '/example/test'), {'controller': 'example', 'action': 'test'}, 'changed')
    is_ok(endpoint(r, '/something/else'), None, 'not at the old pattern')

with subtest('Adding conditions'):
    r = Pyjoyment.new().routes

    # A condition that randomly allows a route to match
    def random_condition(route, c, captures, num):

        # Loser
        if random.randrange(num):
            return None

        # Winner
        return True

    r.add_condition('random', random_condition)
    r.get('/maybe').requires(random=4).to('foo#bar')
    with patch('random.randrange', return_value=0):
        is_deeply_ok(endpoint(r, '/maybe'), {'controller': 'foo', 'action': 'bar'}, 'winner')
    with patch('random.randrange', return_value=3):
        is_ok(endpoint(r, '/maybe'), None, 'loser')

    app = Pyjoyment.new()
    r = app.routes

    # A condition to check query parameters (useful for mock web services)
    def query(route, c, captures, values):

        for key in values:
            param = c.req.url.query.param(key)
            if param is None or param != values[key]:
                return None

        return True

    r.add_condition('query', query)
    r.get('/hello').requires(query={'test': '1', 'to': 'world'}).to(cb=lambda c: c.render(text='Hello World!'))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/hello?to=world&test=1').status_is(200).content_is('Hello World!')
        t.get_ok('/hello?to=world').status_is(404)
        t.get_ok('/hello?to=mars&test=1').status_is(404)

with subtest('Condition plugins'):
    with application('werewolf'):
        r = Pyjo.Test.Pyjo.new('MyApp').app.routes

        # A full moon on 2000-01-21, which is the 14th day after the new moon of 2000-01-06
        full = 947182440 + 14 * 86400
        with patch('time.time', return_value=full):
            is_deeply_ok(endpoint(r, '/hideout'), {'controller': 'foo', 'action': 'bar'}, 'full moon')
        with patch('time.time', return_value=full + 3 * 86400):
            is_ok(endpoint(r, '/hideout'), None, 'three days after full moon')

with subtest('Mount applications'):
    from Pyjoyment.Lite import app, get, plugin

    # Whole application mounted under "/prefix"
    plugin('Mount', {'/prefix': EXAMPLES.sibling('growing', 'foundation', 'myapp.py').to_str()})

    # Mount application with subdomain
    plugin('Mount', {'test.example.com': EXAMPLES.sibling('tutorial', 'hello_world.py').to_str()})

    # Normal route
    @get('/')
    def index(c):
        c.render(text='Hello World!')

    # The application of the module of this test lives until the end, its server is closed here
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/').status_is(200).content_is('Hello World!')
        t.get_ok('/prefix').status_is(200).content_is('Hello World!')
        t.get_ok('/', {'Host': 'test.example.com'}).status_is(200).content_is('Hello World!')

with subtest('Embed applications'):
    with application('embed_lite'):
        app = Pyjoyment.new()
        app.routes.namespaces = ['MyApp.Controller']
        app.routes.any('/foo').set(partial=True).to('bar#', name='Pyjo')
        with Pyjo.Test.Pyjo.new(app) as t:
            t.get_ok('/foo/hello').status_is(200).content_is('Hello Pyjo.')
            t.get_ok('/foo/bye').status_is(404)

    with application('embed'):
        app = Pyjoyment.new()
        app.routes.namespaces = ['MyApp.Controller']
        app.routes.any('/foo').set(partial=True).to('bar#', name='Pyjo')
        with Pyjo.Test.Pyjo.new(app) as t:
            t.get_ok('/foo').status_is(200).content_is('Hello Pyjo.')
            t.get_ok('/foo/whatever').status_is(200).content_is('Hello Pyjo.')

with subtest('Application plugins'):
    with application('app_plugin'):
        with Pyjo.Test.Pyjo.new('MyApp') as t:
            t.get_ok('/foo/bar').status_is(200).content_is('Hello World!\n')
            t.get_ok('/bar').status_is(404)

done_testing()
