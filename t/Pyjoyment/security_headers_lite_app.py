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

LEGACY = {
    'csp-report': {
        'document-uri': 'https://example.com/',
        'blocked-uri': 'inline',
        'violated-directive': 'script-src-elem',
        'original-policy': "script-src 'self'; report-uri /csp-reports",
        'disposition': 'report',
        'line-number': 3,
    }
}
REPORTS = [
    {
        'type': 'csp-violation',
        'url': 'https://example.com/',
        'body': {
            'documentURL': 'https://example.com/',
            'blockedURL': 'https://evil.com/x.js',
            'effectiveDirective': 'script-src-elem',
            'disposition': 'enforce',
        },
    },
    {'type': 'deprecation', 'url': 'https://example.com/', 'body': {'id': 'foo'}},
]

with subtest('Reports'):
    other = application(
        {
            'reports': '/csp-reports',
            'csp': {'default-src': ["'self'"]},
            'csp_report_only': {'script-src': ["'self'"]},
            'permissions': None,
        }
    )
    reports = []
    other.app.hook('csp_report', lambda c, report: reports.append(report))
    (
        other.get_ok('/')
        .status_is(200)
        .header_is('Content-Security-Policy', "default-src 'self'; report-uri /csp-reports; report-to csp")
        .header_is('Content-Security-Policy-Report-Only', "script-src 'self'; report-uri /csp-reports; report-to csp")
        .header_is('Reporting-Endpoints', 'csp="/csp-reports"')
    )

    # A report of report-uri, as the fields of the Reporting API
    with other.app.log.capture('warn') as logs:
        (
            other.post_ok('/csp-reports', {'Content-Type': 'application/csp-report'}, json=LEGACY)
            .status_is(204)
            .content_is('')
        )
    like_ok(
        str(logs),
        r'\[warn\] .*CSP violation of script-src-elem: inline in https://example\.com/ \(report only\)',
        'right message',
    )
    is_deeply_ok(
        reports.pop(),
        {
            'documentURL': 'https://example.com/',
            'blockedURL': 'inline',
            'effectiveDirective': 'script-src-elem',
            'originalPolicy': "script-src 'self'; report-uri /csp-reports",
            'disposition': 'report',
            'lineNumber': 3,
        },
        'violation of report-uri',
    )

    # The reports of report-to, of which only the violations of CSP
    with other.app.log.capture('warn') as logs:
        other.post_ok('/csp-reports', {'Content-Type': 'application/reports+json'}, json=REPORTS).status_is(204)
    like_ok(
        str(logs), r'CSP violation of script-src-elem: https://evil\.com/x\.js in https://example\.com/\n', 'message'
    )
    is_deeply_ok(reports, [REPORTS[0]['body']], 'violations of report-to')
    reports.clear()

    # What a client could forge the log with
    forged = {'csp-report': {'blocked-uri': 'x\n[error] forged', 'document-uri': 'y' * 1000}}
    with other.app.log.capture('warn') as logs:
        other.post_ok('/csp-reports', json=forged).status_is(204)
    like_ok(str(logs), r'CSP violation of -: x\?\[error\] forged in y{200}\n', 'control characters and length')
    is_ok(len(reports), 1, 'one violation')
    reports.clear()

    # Not a report
    for body in ({'json': {'foo': 'bar'}}, {'json': [1, 2]}, {'json': 'foo'}):
        other.post_ok('/csp-reports', **body).status_is(400).content_is('Invalid report')
    other.post_ok('/csp-reports', 'not JSON').status_is(400)
    other.get_ok('/csp-reports').status_is(404)
    is_ok(len(reports), 0, 'no violations')

    # A body that is too large
    other = application({'reports': '/csp-reports', 'max_report_size': 100})
    other.post_ok('/csp-reports', json=LEGACY).status_is(413).content_is('Report too large')

    # A policy of its own endpoint, or of a string, is kept
    other = application(
        {'reports': '/csp-reports', 'csp': "default-src 'self'", 'csp_report_only': {'report-uri': ['/elsewhere']}}
    )
    (
        other.get_ok('/')
        .header_is('Content-Security-Policy', "default-src 'self'")
        .header_is('Content-Security-Policy-Report-Only', 'report-uri /elsewhere')
        .header_is('Reporting-Endpoints', 'csp="/csp-reports"')
    )

    # With the nonce and the options of a response
    other = application({'reports': '/csp-reports', 'csp': {'script-src': ["'self'"]}})
    other.app.routes.get('/inline', lambda c: c.render(inline=INLINE))
    other.app.routes.get('/own').to(
        cb=lambda c: c.render(text='Own!'), security_headers={'csp': {'img-src': ["'self'"]}}
    )
    other.get_ok('/inline').header_like(
        'Content-Security-Policy', r"^script-src 'self' 'nonce-[^']+'; report-uri /csp-reports; report-to csp$"
    )
    other.get_ok('/own').header_is('Content-Security-Policy', "img-src 'self'; report-uri /csp-reports; report-to csp")

    # The prefix of an application that is mounted
    embedded = Pyjoyment.new()
    embedded.log.level = 'fatal'
    embedded.plugin('SecurityHeaders', {'reports': '/csp-reports', 'csp': {'default-src': ["'self'"]}})
    embedded.routes.get('/', lambda c: c.render(text='Embedded!'))
    outer = Pyjoyment.new()
    outer.log.level = 'fatal'
    outer.plugin('Mount', {'/app': embedded})
    mounted = Pyjo.Test.Pyjo.new(outer)
    (
        mounted.get_ok('/app/')
        .status_is(200)
        .content_is('Embedded!')
        .header_is('Content-Security-Policy', "default-src 'self'; report-uri /app/csp-reports; report-to csp")
        .header_is('Reporting-Endpoints', 'csp="/app/csp-reports"')
    )
    mounted.post_ok('/app/csp-reports', json=LEGACY).status_is(204)

with subtest('Unknown option'):
    throws_ok(
        lambda: Pyjoyment.new().plugin('SecurityHeaders', {'cps': {}}),
        Exception,
        'Unknown option of SecurityHeaders: cps',
    )

done_testing()
