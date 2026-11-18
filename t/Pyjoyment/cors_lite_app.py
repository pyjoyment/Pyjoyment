import os


os.environ['PYJO_MODE'] = 'development'

import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.File import tempdir
from Pyjo.Test import *
from Pyjoyment.Lite import any, app, get, plugin

import re


# Not in Mojolicious: Pyjoyment.Plugin.CORS, the Cross-Origin Resource Sharing of the pages of other sites

app.log.level = 'fatal'

plugin('CORS')

get('/', {'text': 'Hello!'})

actions = []


@any('/any')
def any_method(c):
    actions.append(c.req.method)
    c.render(text='Any!')


@get('/own')
def own(c):
    c.res.headers.access_control_allow_origin = 'https://own.example.com'
    c.render(text='Own!')


public = tempdir()
public.child('font.woff2').spew('woff2')
app.static.paths.insert(0, public.to_str())

t = Pyjo.Test.Pyjo.new()

PAGE = {'Origin': 'https://app.example.com'}
PREFLIGHT = {
    'Origin': 'https://app.example.com',
    'Access-Control-Request-Method': 'PUT',
    'Access-Control-Request-Headers': 'content-type, x-token',
}


def application(conf):
    # An application of its own, with the options of the plugin
    other = Pyjoyment.new()
    other.log.level = 'fatal'
    other.plugin('CORS', conf)
    other.routes.get('/', lambda c: c.render(text='Hello!'))
    other.routes.get('/api/users', lambda c: c.render(json=[]))
    other.routes.any('/api/any', lambda c: c.render(text='Any!'))
    return Pyjo.Test.Pyjo.new(other)


with subtest('Every origin'):
    (
        t.get_ok('/', PAGE)
        .status_is(200)
        .content_is('Hello!')
        .header_is('Access-Control-Allow-Origin', '*')
        .header_exists_not('Access-Control-Allow-Credentials')
        .header_exists_not('Vary')
    )
    t.get_ok('/font.woff2', PAGE).status_is(200).header_is('Access-Control-Allow-Origin', '*')
    t.get_ok('/missing', PAGE).status_is(404).header_is('Access-Control-Allow-Origin', '*')
    t.get_ok('/').status_is(200).header_exists_not('Access-Control-Allow-Origin')
    t.get_ok('/own', PAGE).status_is(200).header_is('Access-Control-Allow-Origin', 'https://own.example.com')

with subtest('Preflight'):
    (
        t.options_ok('/any', PREFLIGHT)
        .status_is(204)
        .content_is('')
        .header_is('Access-Control-Allow-Origin', '*')
        .header_is('Access-Control-Allow-Methods', 'GET, HEAD, POST, PUT, PATCH, DELETE')
        .header_is('Access-Control-Allow-Headers', 'content-type, x-token')
        .header_is('Vary', 'Access-Control-Request-Headers')
        .header_exists_not('Access-Control-Max-Age')
    )
    is_deeply_ok(actions, [], 'no action for a preflight request')
    t.options_ok('/missing', PREFLIGHT).status_is(204).header_is('Access-Control-Allow-Origin', '*')

    # An OPTIONS request that is not a preflight one reaches the routes
    t.options_ok('/any', PAGE).status_is(200).content_is('Any!').header_is('Access-Control-Allow-Origin', '*')
    t.options_ok('/any').status_is(200).content_is('Any!')
    is_deeply_ok(actions, ['OPTIONS', 'OPTIONS'], 'actions of the other requests')

with subtest('Origins of their own'):
    other = application(
        {
            'origins': ['https://APP.example.com', re.compile(r'^https://pr-\d+\.example\.com$')],
            'credentials': True,
            'headers': ['Content-Type'],
            'methods': ['GET', 'PUT'],
            'expose': ['Server-Timing', 'X-Request-Id'],
            'max_age': 600,
        }
    )
    (
        other.get_ok('/', PAGE)
        .status_is(200)
        .header_is('Access-Control-Allow-Origin', 'https://app.example.com')
        .header_is('Access-Control-Allow-Credentials', 'true')
        .header_is('Access-Control-Expose-Headers', 'Server-Timing, X-Request-Id')
        .header_is('Vary', 'Origin')
    )
    other.get_ok('/', {'Origin': 'https://pr-12.example.com'}).header_is(
        'Access-Control-Allow-Origin', 'https://pr-12.example.com'
    )
    (
        other.get_ok('/', {'Origin': 'https://evil.com'})
        .status_is(200)
        .content_is('Hello!')
        .header_exists_not('Access-Control-Allow-Origin')
        .header_exists_not('Access-Control-Allow-Credentials')
        .header_is('Vary', 'Origin')
    )
    other.get_ok('/').status_is(200).header_exists_not('Access-Control-Allow-Origin').header_is('Vary', 'Origin')
    (
        other.options_ok('/api/any', PREFLIGHT)
        .status_is(204)
        .header_is('Access-Control-Allow-Origin', 'https://app.example.com')
        .header_is('Access-Control-Allow-Methods', 'GET, PUT')
        .header_is('Access-Control-Allow-Headers', 'Content-Type')
        .header_is('Access-Control-Allow-Credentials', 'true')
        .header_is('Access-Control-Max-Age', '600')
        .header_is('Vary', 'Origin')
        .header_exists_not('Access-Control-Expose-Headers')
    )
    # The preflight request of another origin gets no headers of CORS, and reaches no action
    (
        other.options_ok('/api/any', {**PREFLIGHT, 'Origin': 'https://evil.com'})
        .status_is(204)
        .header_exists_not('Access-Control-Allow-Origin')
        .header_exists_not('Access-Control-Allow-Methods')
        .header_is('Vary', 'Origin')
    )

    other = application({'origins': lambda c, origin: origin.endswith('.example.com')})
    other.get_ok('/', PAGE).header_is('Access-Control-Allow-Origin', 'https://app.example.com')
    other.get_ok('/', {'Origin': 'https://evil.com'}).header_exists_not('Access-Control-Allow-Origin')

with subtest('Paths'):
    other = application({'paths': ['/api/', re.compile(r'^/v\d+/')]})
    other.get_ok('/api/users', PAGE).status_is(200).header_is('Access-Control-Allow-Origin', '*')
    other.get_ok('/', PAGE).status_is(200).header_exists_not('Access-Control-Allow-Origin')
    other.options_ok('/api/any', PREFLIGHT).status_is(204).header_is('Access-Control-Allow-Origin', '*')
    other.options_ok('/', PREFLIGHT).status_is(404).header_exists_not('Access-Control-Allow-Origin')
    other.options_ok('/v2/x', PREFLIGHT).status_is(204)
    other.options_ok('/apix', PREFLIGHT).status_is(404)

with subtest('AllowedHosts'):
    # The origins of CORS among the origins of AllowedHosts, which rejects the other ones before
    other = Pyjoyment.new()
    other.log.level = 'fatal'
    other.plugin('AllowedHosts', origins=['https://app.example.com'])
    other.plugin('CORS', origins=['https://app.example.com'])
    other.routes.get('/', lambda c: c.render(text='Hello!'))
    other = Pyjo.Test.Pyjo.new(other)
    other.get_ok('/', PAGE).status_is(200).header_is('Access-Control-Allow-Origin', 'https://app.example.com')
    other.options_ok('/', PREFLIGHT).status_is(204).header_is('Access-Control-Allow-Origin', 'https://app.example.com')
    other.get_ok('/', {'Origin': 'https://evil.com'}).status_is(403).header_exists_not('Access-Control-Allow-Origin')

with subtest('Errors of the options'):
    throws_ok(
        lambda: Pyjoyment.new().plugin('CORS', credentials=True),
        Exception,
        'Option credentials of CORS needs origins of its own',
    )
    throws_ok(lambda: Pyjoyment.new().plugin('CORS', origin=['x']), Exception, 'Unknown option of CORS: origin')

done_testing()
