import Pyjo.IOLoop
import Pyjo.Server.Daemon

from Pyjo.File import tempdir
from Pyjo.Test import *

# The examples request real hosts, so a daemon with an application of Pyjoyment.Lite answers them instead
from Pyjoyment.Lite import app

import contextlib
import io


app.log.level = 'fatal'

HTML = '<html><head><title>Mojolicious</title></head><body><h2><a>One</a></h2><h2><a>Two</a></h2></body></html>'


@app.routes.any('/')
def root(c):
    if c.param('format') == 'json':
        return c.render(json={'Abstract': 'Mojolicious'})
    c.render(text=HTML)


app.routes.any('/test', {'text': 'test'})
app.routes.any('/test.json', lambda c: c.render(json={'user': c.req.url.to_abs().userinfo}))
app.routes.any('/search', {'text': 'Mojolicious'})
app.routes.any('/mock-mojolicious', {'text': 'mock'})
app.routes.any('/mojolicious/mojo/tarball/main', {'data': b'tarball'})
app.routes.any('/headers', lambda c: c.render(text=f'{c.req.headers.header("X-Bender")} {c.req.cookie("user")}'))


@app.routes.websocket('/echo')
def echo(c):
    c.tx.with_compression()
    c.on('message', lambda c, msg: c.send(f'echo: {msg}'))


@app.routes.websocket('/echo.json')
def echo_json(c):
    c.on('json', lambda c, data: c.send({'json': data}))


daemon = Pyjo.Server.Daemon.new(app=app, ioloop=Pyjo.IOLoop.singleton, listen=['http://127.0.0.1'], silent=True)
port = daemon.start().ports()[0]


def local(ua):
    # Blocking requests run on the singleton too, where the daemon is
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
    from Pyjo.UserAgent import UserAgent

    with output() as stdout:
        # Fine grained response handling (raises on connection errors)
        ua = local(UserAgent())
        res = ua.get('docs.mojolicious.org').result
        if res.is_success:
            print(res.body)
        elif res.is_error:
            print(res.message)
        elif res.code == 301:
            print(res.headers.location)
        else:
            print('Whatever...')
    like_ok(stdout.getvalue(), r'<title>Mojolicious</title>', 'print(res.body)')
    ua.close()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.IOLoop
    import Pyjo.Promise
    import Pyjo.URL
    import Pyjo.UserAgent

    with output() as stdout:
        # Fine grained response handling (raises on connection errors)
        ua = local(Pyjo.UserAgent.new())
        res = ua.get('docs.mojolicious.org').result
        if res.is_success:
            print(res.body)
        elif res.is_error:
            print(res.message)
        elif res.code == 301:
            print(res.headers.location)
        else:
            print('Whatever...')
    like_ok(stdout.getvalue(), r'<title>Mojolicious</title>', 'print(res.body)')

    # Quick request with the user agent of the module, which follows redirects
    local(Pyjo.UserAgent.singleton)
    with output() as stdout:
        print(Pyjo.UserAgent.get('mojolicious.org').result.dom().at('title').text)
    is_ok(stdout.getvalue(), 'Mojolicious\n', 'print(...)')

    # Say hello to the Unicode snowman and include an Accept header
    with output() as stdout:
        print(ua.get('www.☃.net?hello=there', {'Accept': '*/*'}).result.body)
    like_ok(stdout.getvalue(), r'Mojolicious', 'print(...)')

    # Extract data from HTML and XML resources with CSS selectors
    with output() as stdout:
        print(ua.get('www.perl.org').result.dom().at('title').text)
    is_ok(stdout.getvalue(), 'Mojolicious\n', 'print(...)')

    # Scrape the latest headlines from a news site
    with output() as stdout:
        print(ua.get('blogs.perl.org').result.dom().find('h2 > a').map('text').join('\n'))
    is_ok(stdout.getvalue(), 'One\nTwo\n', 'print(...)')

    # IPv6 PUT request with Content-Type header and content
    tx = ua.put('[::1]:3000', {'Content-Type': 'text/plain'}, b'Hi!')
    is_ok(tx.req.headers.content_type, 'text/plain', 'tx')

    # Quick JSON API request with Basic authentication
    url = Pyjo.URL.new('https://example.com/test.json')
    url.userinfo = 'sri:☃'
    value = ua.get(url).result.json()
    is_deeply_ok(value, {'user': 'sri:☃'}, 'value')

    # JSON POST (application/json) with TLS certificate authentication
    ua.cert, ua.key = 'tls.crt', 'tls.key'
    tx = ua.post('https://example.com', json={'top': 'secret'})
    is_ok(tx.req.body, b'{"top":"secret"}', 'tx')
    ua.cert = ua.key = None

    # Form POST (application/x-www-form-urlencoded)
    tx = ua.post('https://metacpan.org/search', form={'q': 'mojo'})
    is_ok(tx.req.body, b'q=mojo', 'tx')

    # Search DuckDuckGo anonymously through Tor
    ua.proxy.http = 'socks://127.0.0.1:9050'
    with output() as stdout:
        print(ua.get('api.3g2upl4pq6kufc4m.onion/?q=mojolicious&format=json').result.json('/Abstract'))
    is_ok(stdout.getvalue(), 'Mojolicious\n', 'print(...)')
    ua.proxy.http = None

    # GET request via UNIX domain socket "/tmp/myapp.sock" (percent encoded slash)
    with output() as stdout:
        print(ua.get('http+unix://%2Ftmp%2Fmyapp.sock/test').result.body)
    is_ok(stdout.getvalue(), "b'test'\n", 'print(...)')

    # Follow redirects to download Mojolicious from GitHub
    tmp = tempdir()
    ua.max_redirects = 5
    ua.get('https://www.github.com/mojolicious/mojo/tarball/main').result.save_to(tmp.child('mojo.tar.gz'))
    is_ok(tmp.child('mojo.tar.gz').slurp(), b'tarball', 'save_to')

    # Non-blocking request
    with output() as stdout:
        ua.get('mojolicious.org', lambda ua, tx: [print(tx.result.dom().at('title').text), Pyjo.IOLoop.stop()])
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), 'Mojolicious\n', 'print(...)')

    # Concurrent non-blocking requests (synchronized with promises)
    with output() as stdout:
        mojo_promise = ua.get_p('mojolicious.org')
        cpan_promise = ua.get_p('cpan.org')

        @Pyjo.Promise.all(mojo_promise, cpan_promise).then
        def titles(mojo, cpan):
            print(mojo[0].result.dom().at('title').text)
            print(cpan[0].result.dom().at('title').text)

        titles.wait()
    is_ok(stdout.getvalue(), 'Mojolicious\nMojolicious\n', 'print(...)')

    # WebSocket connection sending and receiving JSON via UNIX domain socket
    with output() as stdout:

        @ua.websocket('ws+unix://%2Ftmp%2Fmyapp.sock/echo.json')
        def echo_ws(ua, tx):
            if not tx.is_websocket:
                return print('WebSocket handshake failed!')

            @tx.on('json')
            def json(tx, hash):
                print(f'WebSocket message via JSON: {hash["msg"]}')
                tx.finish()

            tx.on('finish', lambda tx, *args: Pyjo.IOLoop.stop())
            tx.send({'json': {'msg': 'Hello World!'}})

        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), 'WebSocket message via JSON: Hello World!\n', 'print(...)')

with subtest('prepare'):
    ua = local(Pyjo.UserAgent.new())
    ua.on('prepare', lambda ua, tx: ...)
    ua.unsubscribe('prepare')

    @ua.on('prepare')
    def prepare(ua, tx):
        if tx.req.url.host == 'mojolicious.org':
            tx.req.url = Pyjo.URL.new('/mock-mojolicious')

    is_ok(ua.get('mojolicious.org').res.body, b'mock', 'mocked')

with subtest('close'):
    import Pyjo.UserAgent

    ua = Pyjo.UserAgent.new()
    before = ua.server.url().port
    ua.close()
    isnt_ok(ua.server.url().port, before, 'a new server when it is used again')
    ua.close()


with subtest('start'):
    ua = local(Pyjo.UserAgent.new())
    ua.on('start', lambda ua, tx: ...)

    @ua.on('start')
    def start(ua, tx):
        tx.req.headers.header('X-Bender', 'Bite my shiny metal ass!')

    is_ok(ua.get('example.com/headers').res.body, b'Bite my shiny metal ass! None', 'header')

with subtest('new'):
    ua = Pyjo.UserAgent.new()
    is_ok(ua.max_redirects, 0, 'ua')
    ua = Pyjo.UserAgent.new(max_redirects=3, request_timeout=5)
    is_ok(ua.request_timeout, 5, 'ua.request_timeout')

with subtest('ca'):
    ca = ua.ca
    is_ok(ca, None, 'ca')
    ua.ca = '/etc/tls/ca.crt'
    is_ok(ua.ca, '/etc/tls/ca.crt', 'ua.ca')

with subtest('cert'):
    cert = ua.cert
    is_ok(cert, None, 'cert')
    ua.cert = '/etc/tls/client.crt'
    is_ok(ua.cert, '/etc/tls/client.crt', 'ua.cert')

with subtest('connect_timeout'):
    timeout = ua.connect_timeout
    is_ok(timeout, 10, 'timeout')
    ua.connect_timeout = 5
    is_ok(ua.connect_timeout, 5, 'ua.connect_timeout')

with subtest('cookie_jar'):
    import Pyjo.Cookie.Response
    import Pyjo.UserAgent.CookieJar

    cookie_jar = ua.cookie_jar
    ok(isinstance(cookie_jar, Pyjo.UserAgent.CookieJar.object), 'cookie_jar')
    ua.cookie_jar = Pyjo.UserAgent.CookieJar.new()

    # Ignore all cookies
    ua.cookie_jar.ignore = lambda cookie: True

    # Add custom cookie to the jar
    ua.cookie_jar.add(
        Pyjo.Cookie.Response.new(name='foo', value='bar', domain='docs.mojolicious.org', path='/Mojolicious')
    )
    is_ok(ua.cookie_jar.all()[0].name, 'foo', 'added')

with subtest('inactivity_timeout'):
    timeout = ua.inactivity_timeout
    is_ok(timeout, 40, 'timeout')
    ua.inactivity_timeout = 15
    is_ok(ua.inactivity_timeout, 15, 'ua.inactivity_timeout')

with subtest('insecure'):
    ua = local(Pyjo.UserAgent.new())
    boolean = ua.insecure
    is_ok(boolean, False, 'boolean')
    ua.insecure = boolean

    # Disable TLS certificate verification for testing
    with output() as stdout:
        ua.insecure = True
        print(ua.get('https://127.0.0.1:3000').result.code)
    is_ok(stdout.getvalue(), '200\n', 'print(...)')

with subtest('ioloop'):
    ua = Pyjo.UserAgent.new()
    loop = ua.ioloop
    ok(isinstance(loop, Pyjo.IOLoop.object), 'loop')
    ua.ioloop = Pyjo.IOLoop.new()
    ok(ua.ioloop is not loop, 'ua.ioloop')

with subtest('key'):
    key = ua.key
    is_ok(key, None, 'key')
    ua.key = '/etc/tls/client.crt'
    is_ok(ua.key, '/etc/tls/client.crt', 'ua.key')

with subtest('max_connections'):
    max = ua.max_connections
    is_ok(max, 5, 'max')
    ua.max_connections = 5
    is_ok(ua.max_connections, 5, 'ua.max_connections')

with subtest('max_redirects'):
    max = ua.max_redirects
    is_ok(max, 0, 'max')
    ua.max_redirects = 3
    is_ok(ua.max_redirects, 3, 'ua.max_redirects')

with subtest('max_response_size'):
    max = ua.max_response_size
    is_ok(max, None, 'max')
    ua.max_response_size = 16777216
    is_ok(ua.max_response_size, 16777216, 'ua.max_response_size')

with subtest('proxy'):
    import Pyjo.UserAgent.Proxy

    proxy = ua.proxy
    ok(isinstance(proxy, Pyjo.UserAgent.Proxy.object), 'proxy')
    ua.proxy = Pyjo.UserAgent.Proxy.new()

    # Detect proxy servers from environment
    ua.proxy.detect()

    # Manually configure HTTP proxy (using CONNECT for HTTPS/WebSockets)
    ua.proxy.http = ua.proxy.https = 'http://127.0.0.1:8080'

    # Manually configure Tor (SOCKS5)
    ua.proxy.http = ua.proxy.https = 'socks://127.0.0.1:9050'

    # Manually configure UNIX domain socket (using CONNECT for HTTPS/WebSockets)
    ua.proxy.http = ua.proxy.https = 'http+unix://%2Ftmp%2Fproxy.sock'
    is_ok(ua.proxy.https, 'http+unix://%2Ftmp%2Fproxy.sock', 'configured')

with subtest('request_timeout'):
    timeout = ua.request_timeout
    is_ok(timeout, 0, 'timeout')
    ua.request_timeout = 5
    is_ok(ua.request_timeout, 5, 'ua.request_timeout')

    # Total limit of 5 seconds, of which 3 seconds may be spent connecting
    ua.max_redirects, ua.connect_timeout, ua.request_timeout = 0, 3, 5
    is_ok(ua.connect_timeout, 3, 'limits')

with subtest('server'):
    import Pyjo.UserAgent.Server

    server = ua.server
    ok(isinstance(server, Pyjo.UserAgent.Server.object), 'server')
    ua.server = Pyjo.UserAgent.Server.new()

    import Pyjoyment

    import time

    # Mock web service
    ua = Pyjo.UserAgent.new()
    ua.server.app = app = Pyjoyment.new()
    app.log.level = 'fatal'
    ua.server.app.get('/time', lambda c: c.render(json={'now': time.time()}))
    now = ua.get('/time').result.json()['now']
    ok(now > 0, 'mock web service')

    # Change log level
    ua.server.app.log.level = 'fatal'

    # Port currently used for processing relative URLs blocking
    with output() as stdout:
        print(ua.server.url().port)
    like_ok(stdout.getvalue(), r'^\d+\n$', 'print(...)')

    # Port currently used for processing relative URLs non-blocking
    with output() as stdout:
        print(ua.server.nb_url().port)
    like_ok(stdout.getvalue(), r'^\d+\n$', 'print(...)')

    import Pyjo.Promise

    # An application whose action settles a promise
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/later', lambda c: Pyjo.Promise.timer(0.1, 'Later!').then(lambda text: c.render(text=text)))
    ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
    ua.server.app = app
    text = ua.get('/later').result.text
    is_ok(text, 'Later!', 'blocking request on the event loop of the singleton')

    # The event loop of the singleton, which a blocking request on an event loop of its own does not run, as a reactor of
    # poll shows, where the one of asyncio follows the loop that runs
    if type(Pyjo.IOLoop.singleton.reactor).__module__ == 'Pyjo.Reactor.Poll':
        # The timer of the action comes when the singleton runs again, after the timeout has destroyed the transaction,
        # so the action renders only while it has one, as it would reject a promise that nothing handles
        app.routes.get(
            '/too-late', lambda c: Pyjo.Promise.timer(0.1, 'Later!').then(lambda text: c.tx and c.render(text=text))
        )
        other = Pyjo.UserAgent.new(request_timeout=0.5)
        other.server.app = app
        is_ok(other.get('/too-late').error, {'message': 'Request timeout'}, 'no response on an event loop of its own')
        other.close()

with subtest('source_address'):
    address = ua.source_address
    is_ok(address, None, 'address')
    ua.source_address = ('127.0.0.1', 0)
    is_ok(ua.source_address, ('127.0.0.1', 0), 'ua.source_address')

with subtest('tls_context'):
    import ssl

    context = ua.tls_context
    is_ok(context, None, 'context')
    ua.tls_context = ssl.create_default_context()
    ok(isinstance(ua.tls_context, ssl.SSLContext), 'ua.tls_context')

with subtest('transactor'):
    import Pyjo.UserAgent.Transactor

    t = ua.transactor
    ok(isinstance(t, Pyjo.UserAgent.Transactor.object), 't')
    ua.transactor = Pyjo.UserAgent.Transactor.new()

    # Change name of user agent
    ua.transactor.name = 'MyUA 1.0'

    # Disable compression
    ua.transactor.compressed = False
    is_ok(ua.build_tx('GET', '/').req.headers.user_agent, 'MyUA 1.0', 'name')

with subtest('build_tx'):
    ua = local(Pyjo.UserAgent.new())
    tx = ua.build_tx('GET', 'example.com')
    tx = ua.build_tx('PUT', 'http://example.com', {'Accept': '*/*'}, b'Content!')
    tx = ua.build_tx('PUT', 'http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    tx = ua.build_tx('PUT', 'http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(tx.req.body, b'{"a":"b"}', 'tx')

    # Request with custom cookie
    tx = ua.build_tx('GET', 'https://example.com/headers')
    tx.req.cookies({'name': 'user', 'value': 'sri'})
    tx = ua.start(tx)
    like_ok(tx.res.body, rb'user=sri$', 'cookie')

    # Deactivate gzip compression
    tx = ua.build_tx('GET', 'example.com')
    tx.req.headers.remove('Accept-Encoding')
    tx = ua.start(tx)
    is_ok(tx.req.headers.accept_encoding, None, 'no gzip')

    # Interrupt response by raising an error
    tx = ua.build_tx('GET', 'http://example.com')

    @tx.res.on('progress')
    def progress(res):
        if (server := res.headers.server) and 'IIS' in server:
            res.error = {'message': 'Oh noes, it is IIS!'}

    tx = ua.start(tx)
    ok(not tx.error, 'no IIS')

with subtest('build_websocket_tx'):
    tx = ua.build_websocket_tx('ws://example.com')
    tx = ua.build_websocket_tx('ws://example.com', {'DNT': 1}, ['v1.proto'])
    is_ok(tx.req.headers.sec_websocket_protocol, 'v1.proto', 'tx')

    # Custom WebSocket handshake with cookie
    tx = ua.build_websocket_tx('wss://example.com/echo')
    tx.req.cookies({'name': 'user', 'value': 'sri'})

    with output() as stdout:

        def echo_tx(ua, tx):
            if not tx.is_websocket:
                return print('WebSocket handshake failed!')

            @tx.on('message')
            def message(tx, msg):
                print(f'WebSocket message: {msg}')
                tx.finish()

            tx.on('finish', lambda tx, *args: Pyjo.IOLoop.stop())
            tx.send('Hi!')

        ua.start(tx, echo_tx)
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), 'WebSocket message: echo: Hi!\n', 'print(...)')

with subtest('delete, get, head, options, patch, post, put and query'):
    tx = ua.get('example.com')
    tx = ua.get('http://example.com', {'Accept': '*/*'}, b'Content!')
    tx = ua.get('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
    tx = ua.get('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
    is_ok(tx.res.code, 200, 'tx')

    with output() as stdout:
        ua.get('http://example.com', lambda ua, tx: [print(tx.result.code), Pyjo.IOLoop.stop()], json={'a': 'b'})
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
        ua.get('http://example.com', json={'a': 'b'}, cb=lambda ua, tx: [print(tx.result.code), Pyjo.IOLoop.stop()])
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), '200\n200\n', 'print(tx.result.body)')

with subtest('delete_p, get_p, head_p, options_p, patch_p, post_p, put_p and query_p'):
    promise = ua.get_p('http://example.com')

    with output() as stdout:

        @ua.get_p('http://example.com', json={'a': 'b'}).then
        def ok_p(tx):
            print(tx.result.code)

        ok_p.catch(lambda err: print(f'Connection error: {err}')).wait()
    is_ok(stdout.getvalue(), '200\n', 'print(tx.result.body)')

with subtest('singleton'):
    agent = Pyjo.UserAgent.object.singleton()
    ok(agent is Pyjo.UserAgent.singleton, 'ua')

    # Change name of user agent for the functions of the module
    Pyjo.UserAgent.singleton.transactor.name = 'MyUA 1.0'
    with output() as stdout:
        print(Pyjo.UserAgent.get('example.com').result.body)
    like_ok(stdout.getvalue(), r'<title>Mojolicious</title>', 'print(...)')
    is_ok(Pyjo.UserAgent.get('example.com').req.headers.user_agent, 'MyUA 1.0', 'name')
    Pyjo.UserAgent.singleton.transactor.name = 'Pyjoyment (Python)'

with subtest('start'):
    tx = ua.start(Pyjo.Transaction.HTTP.new(req=Pyjo.Message.Request.new(url=Pyjo.URL.new('http://example.com'))))
    is_ok(tx.res.code, 200, 'tx')

    with output() as stdout:
        tx = ua.build_tx('GET', 'http://example.com')
        ua.start(tx, lambda ua, tx: [print(tx.result.code), Pyjo.IOLoop.stop()])
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), '200\n', 'print(tx.result.body)')

with subtest('start_p'):
    import Pyjo.Transaction.HTTP

    promise = ua.start_p(
        Pyjo.Transaction.HTTP.new(req=Pyjo.Message.Request.new(url=Pyjo.URL.new('http://example.com')))
    )

    with output() as stdout:
        tx = ua.build_tx('GET', 'http://example.com')

        @ua.start_p(tx).then
        def ok_start(tx):
            print(tx.result.code)

        ok_start.catch(lambda err: print(f'Connection error: {err}')).wait()
    is_ok(stdout.getvalue(), '200\n', 'print(tx.result.body)')

with subtest('websocket'):
    with output() as stdout:

        @ua.websocket('wss://example.com/echo', ['v1.proto'])
        def echo_protocol(ua, tx):
            if not tx.is_websocket:
                return print('WebSocket handshake failed!')
            if not tx.protocol:
                Pyjo.IOLoop.stop()
                return print('Subprotocol negotiation failed!')

        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), 'Subprotocol negotiation failed!\n', 'print(...)')
    isa_ok(echo_protocol, str, 'the decorated name is the id of the connection')

    with output() as stdout:

        def compressed(ua, tx):
            print(tx.compressed)
            tx.finish()
            Pyjo.IOLoop.stop()

        ua.websocket('ws://example.com/echo', {'Sec-WebSocket-Extensions': 'permessage-deflate'}, compressed)
        if not Pyjo.IOLoop.is_running():
            Pyjo.IOLoop.start()
    is_ok(stdout.getvalue(), 'True\n', 'permessage-deflate')

with subtest('websocket_p'):
    promise = ua.websocket_p('ws://example.com/echo')

    with output() as stdout:

        @ua.websocket_p('wss://example.com/echo').then
        def ok_ws(tx):
            promise = Pyjo.Promise.new()
            tx.on('finish', lambda tx, code, reason: promise.resolve())

            @tx.on('message')
            def message(tx, msg):
                print(f'WebSocket message: {msg}')
                tx.finish()

            tx.send('Hi!')
            return promise

        ok_ws.catch(lambda err: print(f'WebSocket error: {err}')).wait()
    is_ok(stdout.getvalue(), 'WebSocket message: echo: Hi!\n', 'print(...)')

with subtest('delete, get, head, options, patch, post, put and query of the module'):
    for name in ('delete', 'get', 'head', 'options', 'patch', 'post', 'put', 'query'):
        request = getattr(Pyjo.UserAgent, name)
        tx = request('example.com')
        tx = request('http://example.com', {'Accept': '*/*'}, b'Content!')
        tx = request('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        tx = request('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})
        is_ok(tx.req.method, name.upper(), f'tx of {name}')

        with output() as stdout:
            print(request('example.com').result.code)
        is_ok(stdout.getvalue(), '200\n', f'print(...) of {name}')
    Pyjo.UserAgent.singleton.close()

done_testing()
