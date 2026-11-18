import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *
from Pyjoyment.Lite import app as lite
from Pyjoyment.Lite import get, plugin

import re


lite.log.level = 'fatal'

PAGE = {'Origin': 'https://app.example.com'}


def application():
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/', lambda c: c.render(text='Hello!'))
    app.routes.get('/api/users', lambda c: c.render(json=[]))
    return app


with subtest('Synopsis'):
    # Pyjoyment
    app = application()
    app.plugin('CORS')
    Pyjo.Test.Pyjo.new(app).get_ok('/', PAGE).status_is(200).header_is('Access-Control-Allow-Origin', '*')

    # Pyjoyment.Lite
    plugin('CORS')
    get('/', {'text': 'Hello!'})
    Pyjo.Test.Pyjo.new().get_ok('/', PAGE).status_is(200).header_is('Access-Control-Allow-Origin', '*')

    # The pages of two sites, with their cookies, for the API only
    app = application()
    app.plugin(
        'CORS',
        origins=['https://app.example.com', 'https://admin.example.com'],
        credentials=True,
        paths=['/api'],
        max_age=600,
    )
    t = Pyjo.Test.Pyjo.new(app)
    (
        t.get_ok('/api/users', {'Origin': 'https://admin.example.com'})
        .header_is('Access-Control-Allow-Origin', 'https://admin.example.com')
        .header_is('Access-Control-Allow-Credentials', 'true')
    )
    t.get_ok('/', PAGE).header_exists_not('Access-Control-Allow-Origin')
    preflight = {**PAGE, 'Access-Control-Request-Method': 'DELETE'}
    t.options_ok('/api/users', preflight).status_is(204).header_is('Access-Control-Max-Age', '600')

with subtest('credentials'):
    app = application()
    app.plugin('CORS', origins=['https://app.example.com'], credentials=True)
    Pyjo.Test.Pyjo.new(app).get_ok('/', PAGE).header_is('Access-Control-Allow-Credentials', 'true')

with subtest('expose'):
    app = application()
    app.plugin('CORS', expose=['Server-Timing', 'X-Request-Id'])
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/', PAGE).header_is('Access-Control-Expose-Headers', 'Server-Timing, X-Request-Id')

with subtest('headers'):
    app = application()
    app.plugin('CORS', headers=['Authorization', 'Content-Type'])
    preflight = {**PAGE, 'Access-Control-Request-Method': 'PUT', 'Access-Control-Request-Headers': 'x-other'}
    t = Pyjo.Test.Pyjo.new(app)
    t.options_ok('/', preflight).header_is('Access-Control-Allow-Headers', 'Authorization, Content-Type')

with subtest('max_age'):
    app = application()
    app.plugin('CORS', max_age=600)
    preflight = {**PAGE, 'Access-Control-Request-Method': 'PUT'}
    Pyjo.Test.Pyjo.new(app).options_ok('/', preflight).header_is('Access-Control-Max-Age', '600')

with subtest('methods'):
    app = application()
    app.plugin('CORS', methods=['GET', 'POST'])
    preflight = {**PAGE, 'Access-Control-Request-Method': 'PUT'}
    Pyjo.Test.Pyjo.new(app).options_ok('/', preflight).header_is('Access-Control-Allow-Methods', 'GET, POST')

with subtest('origins'):
    app = application()
    app.plugin('CORS', origins=['https://app.example.com', 'http://localhost:5173'])
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/', {'Origin': 'http://localhost:5173'}).header_is('Access-Control-Allow-Origin', 'http://localhost:5173')
    t.get_ok('/', {'Origin': 'http://localhost:3000'}).header_exists_not('Access-Control-Allow-Origin')
    app = application()
    app.plugin('CORS', origins=[re.compile(r'^https://pr-\d+\.example\.com$')])
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/', {'Origin': 'https://pr-1.example.com'}).header_is(
        'Access-Control-Allow-Origin', 'https://pr-1.example.com'
    )
    app = application()
    app.plugin('CORS', origins=lambda c, origin: origin.endswith('.example.com'))
    Pyjo.Test.Pyjo.new(app).get_ok('/', PAGE).header_is('Access-Control-Allow-Origin', 'https://app.example.com')

with subtest('paths'):
    app = application()
    app.plugin('CORS', paths=['/api', re.compile(r'^/v\d+/')])
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/api/users', PAGE).header_is('Access-Control-Allow-Origin', '*')
    t.get_ok('/', PAGE).header_exists_not('Access-Control-Allow-Origin')

with subtest('register'):
    app = application()
    plugin = app.plugins.load_plugin('CORS')
    plugin.register(app)
    Pyjo.Test.Pyjo.new(app).get_ok('/', PAGE).header_is('Access-Control-Allow-Origin', '*')
    app = application()
    plugin.register(app, {'origins': ['https://app.example.com']})
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/', PAGE).header_is('Access-Control-Allow-Origin', 'https://app.example.com')

done_testing()
