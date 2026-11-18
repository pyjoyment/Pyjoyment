import os


os.environ['PYJO_MODE'] = 'development'
# The requests of HTTPS through a reverse proxy, as X-Forwarded-Proto says, for Strict-Transport-Security
os.environ['PYJO_REVERSE_PROXY'] = '1'

import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.File import tempdir
from Pyjo.Test import *
from Pyjoyment.Lite import app, get, plugin

import re


# Not in Mojolicious: Pyjoyment.Plugin.SecurityHeaders, the headers that protect the pages in the browser

app.log.level = 'fatal'

plugin('SecurityHeaders')

get('/', {'text': 'Hello!'})


@get('/own')
def own(c):
    c.res.headers.content_security_policy = "default-src 'none'"
    c.res.headers.referrer_policy = 'no-referrer'
    c.render(text='Own!')


@get('/dies')
def dies(c):
    raise Exception('Oops!')


public = tempdir()
public.child('hello.txt').spew('Hello static!')
app.static.paths.insert(0, public.to_str())

t = Pyjo.Test.Pyjo.new()

HEADERS = {
    'Content-Security-Policy': "base-uri 'self'; frame-ancestors 'self'; object-src 'none'",
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Permissions-Policy': 'camera=(), geolocation=(), microphone=()',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Content-Type-Options': 'nosniff',
}


def application(conf=None):
    # An application of its own, with the options of the plugin
    other = Pyjoyment.new()
    other.log.level = 'fatal'
    other.plugin('SecurityHeaders', conf)
    other.routes.get('/', lambda c: c.render(text='Hello!'))
    return Pyjo.Test.Pyjo.new(other)


with subtest('Every response'):
    for path, code in (('/', 200), ('/hello.txt', 200), ('/missing', 404), ('/dies', 500)):
        t.get_ok(path).status_is(code)
        for name, value in HEADERS.items():
            t.header_is(name, value)

with subtest('Headers of the action'):
    (
        t.get_ok('/own')
        .status_is(200)
        .header_is('Content-Security-Policy', "default-src 'none'")
        .header_is('Referrer-Policy', 'no-referrer')
        .header_is('X-Content-Type-Options', 'nosniff')
    )

with subtest('Strict-Transport-Security'):
    t.get_ok('/', {'Host': 'example.com'}).status_is(200).header_exists_not('Strict-Transport-Security')
    t.get_ok('/', {'Host': 'example.com', 'X-Forwarded-Proto': 'https'}).header_is(
        'Strict-Transport-Security', 'max-age=31536000'
    )
    t.get_ok('/hello.txt', {'Host': 'example.com', 'X-Forwarded-Proto': 'https'}).header_is(
        'Strict-Transport-Security', 'max-age=31536000'
    )
    # Not for localhost, whose servers on every port would be ones of HTTPS only
    for host in ('localhost', 'LocalHost:3000', 'app.localhost'):
        t.get_ok('/', {'Host': host, 'X-Forwarded-Proto': 'https'}).header_exists_not('Strict-Transport-Security')
    other = application({'hsts': {'max_age': 0}})
    other.get_ok('/', {'Host': 'example.com', 'X-Forwarded-Proto': 'https'}).header_is(
        'Strict-Transport-Security', 'max-age=0'
    )
    other = application({'hsts': 'max-age=60; includeSubDomains'})
    other.get_ok('/', {'Host': 'example.com', 'X-Forwarded-Proto': 'https'}).header_is(
        'Strict-Transport-Security', 'max-age=60; includeSubDomains'
    )

with subtest('Left out'):
    other = application(
        {
            'content_type_options': None,
            'csp': False,
            'hsts': None,
            'opener_policy': None,
            'permissions': None,
            'referrer_policy': None,
        }
    )
    other.get_ok('/', {'Host': 'example.com', 'X-Forwarded-Proto': 'https'}).status_is(200)
    for name in (*HEADERS, 'Strict-Transport-Security'):
        other.header_exists_not(name)

with subtest('Permissions-Policy'):
    other = application({'permissions': {'geolocation': ["'self'", 'https://maps.example.com'], 'fullscreen': ['*']}})
    other.get_ok('/').header_is('Permissions-Policy', 'geolocation=(self "https://maps.example.com"), fullscreen=*')
    other = application({'permissions': {'autoplay': 'self'}})
    other.get_ok('/').header_is('Permissions-Policy', 'autoplay=(self)')
    other = application({'permissions': 'camera=()'})
    other.get_ok('/').header_is('Permissions-Policy', 'camera=()')

with subtest('Content-Security-Policy and its reports'):
    other = application(
        {
            'csp': {'default-src': ["'self'"]},
            'csp_report_only': {'default-src': ["'self'"], 'script-src': ["'self'"], 'report-uri': ['/csp-reports']},
        }
    )
    (
        other.get_ok('/')
        .header_is('Content-Security-Policy', "default-src 'self'")
        .header_is(
            'Content-Security-Policy-Report-Only', "default-src 'self'; script-src 'self'; report-uri /csp-reports"
        )
    )

with subtest('Options of the response'):
    other = application()
    other.app.routes.get('/frame').to(cb=lambda c: c.render(text='Frame!'), security_headers={'csp': None})
    other.app.routes.get('/typo').to(cb=lambda c: c.render(text='Typo!'), security_headers={'cps': None})
    other.get_ok('/frame').status_is(200).header_exists_not('Content-Security-Policy').header_is(
        'X-Content-Type-Options', 'nosniff'
    )
    other.get_ok('/').header_is('Content-Security-Policy', HEADERS['Content-Security-Policy'])
    # An unknown option of the response is logged, as the response has been rendered already
    with other.app.log.capture('error') as logs:
        other.get_ok('/typo').status_is(200).content_is('Typo!')
        for name, value in HEADERS.items():
            other.header_is(name, value)
    like_ok(str(logs), r'\[error\] .*Unknown option of SecurityHeaders: cps', 'right message')

INLINE = """
%= javascript(begin
  const a = 'b';
%= end)
%= stylesheet(begin
  body {color: #000}
%= end)
%= javascript('/app.js')
"""


def nonce_of(t, header='Content-Security-Policy'):
    # The nonce of the policy, which every inline script and style of the page has, and no style attribute
    m = re.search(r"'nonce-([A-Za-z0-9+/=]+)'", t.tx.res.headers.header(header) or '')
    if not ok(m, 'nonce in the policy'):
        return None
    dom = t.tx.res.dom()
    inline = dom.find('script:not([src]), style')
    ok(len(inline) > 0, 'inline scripts or styles')
    is_deeply_ok(sorted({e.attr('nonce') for e in inline}), [m[1]], 'nonce of every inline script and style')
    is_ok(len(dom.find('[style]')), 0, 'no style attributes')
    return m[1]


with subtest('Nonce'):
    other = application({'csp': {'default-src': ["'self'"], 'script-src': ["'self'"], 'img-src': ["'self'", 'data:']}})
    other.app.routes.get('/inline', lambda c: c.render(inline=INLINE))
    other.app.routes.get('/cached', lambda c: c.res.headers.set(cache_control='no-store') and c.render(inline=INLINE))
    other.app.routes.get('/dies', lambda c: c.helpers.reply.exception('Oops!'))
    other.get_ok('/inline').status_is(200).header_is('Cache-Control', 'private')
    nonce = nonce_of(other)
    like_ok(
        other.tx.res.headers.content_security_policy,
        rf"^default-src 'self' 'nonce-{re.escape(nonce)}'; script-src 'self' 'nonce-{re.escape(nonce)}'; img-src 'self' data:$",
        'nonce in the directives of the scripts and the styles',
    )
    other.element_exists('script[src="/app.js"]:not([nonce])')
    other.get_ok('/inline')
    isnt_ok(nonce_of(other), nonce, 'a new nonce for each response')
    other.get_ok('/cached').status_is(200).header_is('Cache-Control', 'no-store')
    other.get_ok('/').status_is(200).header_is(
        'Content-Security-Policy', "default-src 'self'; script-src 'self'; img-src 'self' data:"
    ).header_exists_not('Cache-Control')

    # The bundled pages, of production and of development
    for mode in ('production', 'development'):
        other.app.mode = mode
        other.get_ok('/missing').status_is(404).header_is('Cache-Control', 'private')
        nonce_of(other)
        other.get_ok('/dies').status_is(500).header_is('Cache-Control', 'private')
        nonce_of(other)
    other.app.mode = 'development'

    # The policy of the report-only header gets the nonce too
    other = application({'csp': None, 'csp_report_only': {'default-src': ["'self'"]}})
    other.app.routes.get('/inline', lambda c: c.render(inline=INLINE))
    other.get_ok('/inline').status_is(200).header_exists_not('Content-Security-Policy')
    nonce_of(other, 'Content-Security-Policy-Report-Only')

    # A policy without the directives of the scripts and the styles restricts neither
    other = application()
    other.app.routes.get('/inline', lambda c: c.render(inline=INLINE))
    (
        other.get_ok('/inline')
        .status_is(200)
        .header_is('Content-Security-Policy', HEADERS['Content-Security-Policy'])
        .header_exists_not('Cache-Control')
        .element_exists('script[nonce]')
    )

    # Without the plugin, no nonce
    plain = Pyjoyment.new()
    plain.log.level = 'fatal'
    plain.routes.get('/inline', lambda c: c.render(inline=INLINE))
    Pyjo.Test.Pyjo.new(plain).get_ok('/inline').status_is(200).element_exists('script:not([nonce])').element_exists_not(
        '[nonce]'
    )

with subtest('Unknown option'):
    throws_ok(
        lambda: Pyjoyment.new().plugin('SecurityHeaders', {'cps': {}}),
        Exception,
        'Unknown option of SecurityHeaders: cps',
    )

done_testing()
