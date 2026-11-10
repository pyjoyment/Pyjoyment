import Pyjo.App.ASGI
import Pyjo.App.CGI
import Pyjo.App.FastCGI
import Pyjo.App.Lambda
import Pyjo.File
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo import q
from Pyjo.File import curfile
from Pyjo.Test import *

import importlib
import re
import sys


# The examples of docs/guides/mounting.rst, which includes them, whose modules the mounts name
EXAMPLES = curfile().dirname().dirname().sibling('docs', 'guides', 'mounting')
sys.path.insert(0, EXAMPLES.to_str())

with subtest('Python frameworks'):
    with Pyjo.Test.Pyjo.new(EXAMPLES.child('myapp.py')) as t:
        t.get_ok('/').status_is(200).content_is('Hello from Pyjoyment!')
        t.get_ok('/legacy/foo').status_is(200).content_is('Hello from WSGI at /legacy for /foo!')
        t.get_ok('/api/foo').status_is(200).json_is({'root_path': '/api', 'path': '/api/foo'})
        t.get_ok('/api/events').status_is(200).content_type_is('text/event-stream')
        t.content_is('data: 0\n\ndata: 1\n\ndata: 2\n\n')
        t.websocket_ok('/api/echo').send_ok('hi').message_ok().message_is('echo: hi').finish_ok()


with subtest('Pings'):
    with Pyjo.Test.Pyjo.new(EXAMPLES.child('myapp.py')) as t:
        api = importlib.import_module('api')

        # Pings every 60 seconds
        asgi = Pyjo.App.ASGI.new(app=api.app, ping_interval=60)
        t.app.plugin('Mount', {'/pinged': asgi})
        is_ok(asgi.ping_interval, 60, 'interval of the pings')

        # A WebSocket of Pyjoyment pinged every 20 seconds

        @t.app.routes.websocket('/echo')
        def echo(c):
            c.tx.heartbeat()
            c.on('message', lambda c, msg: c.send(f'echo: {msg}'))

        t.websocket_ok('/pinged/echo').send_ok('hi').message_ok().message_is('echo: hi').finish_ok()
        t.websocket_ok('/echo').send_ok('hi').message_ok().message_is('echo: hi').finish_ok()

with subtest('Paths'):
    # The beginning of the path, which an application of another framework answers with 404
    with Pyjo.Test.Pyjo.new(EXAMPLES.child('myapp.py')) as t:
        t.get_ok('/legacy.css').status_is(404)
        t.get_ok('/legacyx').status_is(404)

    # A regular expression of the whole path
    app = Pyjoyment.new()
    app.log.level = 'fatal'

    # Only /legacy and the paths under it
    app.plugin('Mount', {q(r'/legacy(?P<path>/.*)?'): 'legacy:app'})

    # The API of each user, whose name is a capture
    app.plugin('Mount', {q(r'/(?P<user>\w+)/api(?P<path>/.*)?'): 'api:app'})

    # Only one path
    app.plugin('Mount', {q(r'/status\.json'): 'api:app'})

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/legacy/foo').status_is(200).content_is('Hello from WSGI at /legacy for /foo!')
        t.get_ok('/legacyx').status_is(404)
        t.get_ok('/sri/api/foo').status_is(200).json_is({'root_path': '/sri/api', 'path': '/sri/api/foo'})
        t.get_ok('/status.json').status_is(200).json_is({'root_path': '/status.json', 'path': '/status.json'})
        t.get_ok('/status.jsonx').status_is(404)


with subtest('Static files'):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    BASE_DIR = Pyjo.File.tempdir()
    static = BASE_DIR.child('public', 'static').make_path()
    static.child('site.2fcb528ecde1.css').spew('body {}\n')
    static.child('site.css').spew('body {}\n')
    BASE_DIR.child('public', 'robots.txt').spew('User-agent: *\n')

    # STATIC_ROOT = BASE_DIR / 'public' / 'static', for STATIC_URL = '/static/'
    app.static.paths = [str(BASE_DIR.child('public'))]

    # The hashed names of ManifestStaticFilesStorage never change, the other files are revalidated after a minute
    app.static.immutable = re.compile(r'^static/.+\.[0-9a-f]{12}\.[^/.]+$')
    app.static.cache_control = 'public, max-age=60'

    # The project of Django, with its own /favicon.ico
    app.plugin('Mount', {'/': 'legacy:app'})

    with Pyjo.Test.Pyjo.new(app) as t:
        (
            t.get_ok('/static/site.2fcb528ecde1.css')
            .status_is(200)
            .header_is('Cache-Control', 'public, max-age=31536000, immutable')
        )
        t.get_ok('/static/site.css').status_is(200).header_is('Cache-Control', 'public, max-age=60')
        t.get_ok('/robots.txt').status_is(200).content_is('User-agent: *\n')
        t.get_ok('/favicon.ico').status_is(200).content_is('Hello from WSGI at  for /favicon.ico!')
        t.get_ok('/pyjo/logo.png').status_is(200).content_type_is('image/png')
        t.get_ok('/foo').status_is(200).content_is('Hello from WSGI at  for /foo!')

    app.static.extra = {}
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/pyjo/logo.png').status_is(200).content_is('Hello from WSGI at  for /pyjo/logo.png!')


with subtest('FastCGI'):
    app = Pyjoyment.new()

    # Every path to the one entry of the application
    app.plugin('Mount', {'/app': 'fcgi://127.0.0.1:9000?script=/srv/app/public/index.php'})

    # The scripts of a directory
    app.plugin('Mount', {'/php': 'fcgi+unix://%2Frun%2Fphp%2Fphp-fpm.sock?document_root=/var/www/php'})

    # WordPress: its scripts, its files, and its index.php for every other path
    app.plugin('Mount', {'/blog': 'fcgi://127.0.0.1:9000?document_root=/var/www/wordpress&script=index.php&static=1'})

    mounts = {str(route.pattern.unparsed): route.pattern.defaults['app'] for route in app.routes.children}
    ok(all(isinstance(fcgi, Pyjo.App.FastCGI.object) for fcgi in mounts.values()), 'FastCGI applications')
    like_ok(str(mounts['/app'].url), r'\?script=/srv/app/public/index\.php$', 'one script')
    like_ok(str(mounts['/php'].url), r'^fcgi\+unix://.*\?document_root=/var/www/php$', 'directory')
    like_ok(str(mounts['/blog'].url), r'document_root=/var/www/wordpress&script=index\.php&static=1$', 'WordPress')


with subtest('CGI'):
    app = Pyjoyment.new()

    # The programs of cgi-bin
    app.plugin('Mount', {'/cgi-bin': Pyjo.App.CGI.new(document_root='/usr/lib/cgi-bin')})

    # PHP on php-cgi, with its files
    php = Pyjo.App.CGI.new(command=['php-cgi'], document_root='/var/www/php', script_extensions=['.php'], static=True)
    app.plugin('Mount', {'/php': php})

    mounts = {str(route.pattern.unparsed): route.pattern.defaults['app'] for route in app.routes.children}
    ok(all(isinstance(cgi, Pyjo.App.CGI.object) for cgi in mounts.values()), 'CGI applications')
    is_ok(mounts['/cgi-bin'].document_root, '/usr/lib/cgi-bin', 'directory of the programs')
    is_deeply_ok(mounts['/php'].command, ['php-cgi'], 'command of the scripts')


with subtest('AWS Lambda'):
    app = Pyjoyment.new()

    # The handler "handler" of myfunction.py of the directory of the function
    app.plugin('Mount', {'/function': Pyjo.App.Lambda.new(function='myfunction.handler', task_root='functions')})

    # Another runtime, with the events of a REST API
    app.plugin('Mount', {'/node': Pyjo.App.Lambda.new(command=['node', 'runtime.js'], payload='1.0')})

    mounts = {str(route.pattern.unparsed): route.pattern.defaults['app'] for route in app.routes.children}
    ok(all(isinstance(fcn, Pyjo.App.Lambda.object) for fcn in mounts.values()), 'Lambda functions')
    is_ok(mounts['/function'].function, 'myfunction.handler', 'handler of the function')
    is_ok(mounts['/node'].payload, '1.0', 'payload format')

done_testing()
