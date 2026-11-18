import os


# The requests of HTTPS through a reverse proxy, as X-Forwarded-Proto says, for Strict-Transport-Security
os.environ['PYJO_REVERSE_PROXY'] = '1'

import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *
from Pyjoyment.Lite import app as lite
from Pyjoyment.Lite import get, plugin

import re


lite.log.level = 'fatal'

HTTPS = {'Host': 'example.com', 'X-Forwarded-Proto': 'https'}


def application():
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.routes.get('/', lambda c: c.render(text='Hello!'))
    return app


def embed(c):
    c.render(text='Embedded!')


with subtest('Synopsis'):
    # Pyjoyment
    app = application()
    app.plugin('SecurityHeaders')
    t = Pyjo.Test.Pyjo.new(app)
    (
        t.get_ok('/', HTTPS)
        .status_is(200)
        .header_is('Strict-Transport-Security', 'max-age=31536000')
        .header_is('Content-Security-Policy', "base-uri 'self'; frame-ancestors 'self'; object-src 'none'")
        .header_is('Permissions-Policy', 'camera=(), geolocation=(), microphone=()')
        .header_is('X-Content-Type-Options', 'nosniff')
        .header_is('Referrer-Policy', 'strict-origin-when-cross-origin')
        .header_is('Cross-Origin-Opener-Policy', 'same-origin')
        .header_exists_not('Content-Security-Policy-Report-Only')
        .header_exists_not('Cross-Origin-Embedder-Policy')
        .header_exists_not('Cross-Origin-Resource-Policy')
    )

    # Pyjoyment.Lite
    plugin('SecurityHeaders')
    get('/', {'text': 'Hello!'})
    t = Pyjo.Test.Pyjo.new()
    t.get_ok('/').status_is(200).header_is('X-Content-Type-Options', 'nosniff')

    # A policy of its own, tried out with the reports of the browser before it is enforced
    app = application()
    app.plugin(
        'SecurityHeaders',
        csp_report_only={'default-src': ["'self'"], 'img-src': ["'self'", 'data:']},
        permissions={'camera': [], 'geolocation': ['self'], 'microphone': []},
    )
    t = Pyjo.Test.Pyjo.new(app)
    (
        t.get_ok('/')
        .status_is(200)
        .header_is('Content-Security-Policy-Report-Only', "default-src 'self'; img-src 'self' data:")
        .header_is('Content-Security-Policy', "base-uri 'self'; frame-ancestors 'self'; object-src 'none'")
        .header_is('Permissions-Policy', 'camera=(), geolocation=(self), microphone=()')
    )

    # Another policy for the responses of a route
    app.routes.get('/embed').to(cb=embed, security_headers={'csp': {'frame-ancestors': ['https:']}})
    t.get_ok('/embed').status_is(200).header_is('Content-Security-Policy', 'frame-ancestors https:')
    t.get_ok('/').status_is(200).header_like('Content-Security-Policy', r"^base-uri 'self'")

with subtest('content_type_options'):
    app = application()
    app.plugin('SecurityHeaders', content_type_options=None)
    Pyjo.Test.Pyjo.new(app).get_ok('/').status_is(200).header_exists_not('X-Content-Type-Options')

with subtest('csp'):
    app = application()
    app.plugin('SecurityHeaders', csp={'default-src': ["'self'"], 'upgrade-insecure-requests': []})
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/').header_is('Content-Security-Policy', "default-src 'self'; upgrade-insecure-requests")
    app = application()
    app.plugin('SecurityHeaders', csp="default-src 'self'")
    Pyjo.Test.Pyjo.new(app).get_ok('/').header_is('Content-Security-Policy', "default-src 'self'")

with subtest('csp_report_only'):
    app = application()
    app.plugin('SecurityHeaders', csp_report_only={'default-src': ["'self'"], 'report-uri': ['/csp-reports']})
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/').header_is('Content-Security-Policy-Report-Only', "default-src 'self'; report-uri /csp-reports")

with subtest('embedder_policy'):
    app = application()
    app.plugin('SecurityHeaders', embedder_policy='require-corp')
    Pyjo.Test.Pyjo.new(app).get_ok('/').header_is('Cross-Origin-Embedder-Policy', 'require-corp')

with subtest('hsts'):
    app = application()
    app.plugin('SecurityHeaders', hsts={'max_age': 300})
    Pyjo.Test.Pyjo.new(app).get_ok('/', HTTPS).header_is('Strict-Transport-Security', 'max-age=300')
    app = application()
    app.plugin('SecurityHeaders', hsts={'max_age': 63072000, 'include_subdomains': True, 'preload': True})
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/', HTTPS).header_is('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload')

with subtest('max_report_size'):
    app = application()
    app.plugin('SecurityHeaders', reports='/csp-reports', max_report_size=16384)
    t = Pyjo.Test.Pyjo.new(app)
    t.post_ok('/csp-reports', json={'csp-report': {'blocked-uri': 'x' * 20000}}).status_is(413)

with subtest('opener_policy'):
    app = application()
    app.plugin('SecurityHeaders', opener_policy='same-origin-allow-popups')
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/').header_is('Cross-Origin-Opener-Policy', 'same-origin-allow-popups')

with subtest('permissions'):
    app = application()
    app.plugin('SecurityHeaders', permissions={'camera': [], 'fullscreen': ['self'], 'geolocation': '*'})
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/').header_is('Permissions-Policy', 'camera=(), fullscreen=(self), geolocation=*')

with subtest('referrer_policy'):
    app = application()
    app.plugin('SecurityHeaders', referrer_policy='no-referrer')
    Pyjo.Test.Pyjo.new(app).get_ok('/').header_is('Referrer-Policy', 'no-referrer')

with subtest('reports'):
    app = application()
    app.plugin('SecurityHeaders', reports='/csp-reports', csp_report_only={'default-src': ["'self'"]})
    t = Pyjo.Test.Pyjo.new(app)
    (
        t.get_ok('/')
        .header_is('Content-Security-Policy-Report-Only', "default-src 'self'; report-uri /csp-reports; report-to csp")
        .header_is('Reporting-Endpoints', 'csp="/csp-reports"')
    )
    report = {'csp-report': {'blocked-uri': 'inline', 'effective-directive': 'script-src-elem'}}
    t.post_ok('/csp-reports', {'Content-Type': 'application/csp-report'}, json=report).status_is(204)

with subtest('resource_policy'):
    app = application()
    app.plugin('SecurityHeaders', resource_policy='same-site')
    Pyjo.Test.Pyjo.new(app).get_ok('/').header_is('Cross-Origin-Resource-Policy', 'same-site')

with subtest('csp_nonce'):
    app = application()
    app.plugin('SecurityHeaders', csp={'script-src': ["'self'"]})
    app.routes.get('/nonce', lambda c: c.render(text=c.csp_nonce()))
    template = (
        '%= javascript(begin\n'
        '  hljs.highlightAll();\n'
        '%= end)\n'
        '<script nonce="<%= csp_nonce() %>">hljs.highlightAll();</script>\n'
        "%= javascript('/app.js', nonce=c.csp_nonce())\n"
    )
    app.routes.get('/page', lambda c: c.render(inline=template))
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/nonce').status_is(200)
    nonce = t.tx.res.text
    t.header_is('Content-Security-Policy', f"script-src 'self' 'nonce-{nonce}'").header_is('Cache-Control', 'private')
    t.get_ok('/page').status_is(200)
    nonces = {e.attr('nonce') for e in t.tx.res.dom('script')}
    is_ok(len(nonces), 1, 'one nonce')
    like_ok(t.tx.res.headers.content_security_policy, rf"'nonce-{re.escape(nonces.pop())}'$", 'nonce of the page')

with subtest('csp_report'):
    app = application()
    app.plugin('SecurityHeaders', reports='/csp-reports')

    @app.hook('csp_report')
    def csp_report(c, report):
        c.app.log.info(f'{report["effectiveDirective"]} blocked {report["blockedURL"]}')

    t = Pyjo.Test.Pyjo.new(app)
    report = {'csp-report': {'blocked-uri': 'inline', 'effective-directive': 'script-src-elem'}}
    with app.log.capture('info') as logs:
        t.post_ok('/csp-reports', json=report).status_is(204)
    like_ok(str(logs), r'\[info\] .*script-src-elem blocked inline', 'hook')

with subtest('security_headers'):
    app = application()
    app.plugin('SecurityHeaders')
    app.routes.get('/embed').to(cb=embed, security_headers={'csp': {'frame-ancestors': ['https:']}})
    app.routes.get('/stash', lambda c: c.stash(security_headers={'permissions': None}).render(text='Stash!'))
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/embed').header_is('Content-Security-Policy', 'frame-ancestors https:')
    t.get_ok('/stash').status_is(200).header_exists_not('Permissions-Policy').header_is(
        'Referrer-Policy', 'strict-origin-when-cross-origin'
    )

with subtest('register'):
    app = application()
    plugin = app.plugins.load_plugin('SecurityHeaders')
    plugin.register(app)
    Pyjo.Test.Pyjo.new(app).get_ok('/', HTTPS).header_is('Strict-Transport-Security', 'max-age=31536000')
    app = application()
    plugin.register(app, {'hsts': {'max_age': 300}})
    Pyjo.Test.Pyjo.new(app).get_ok('/', HTTPS).header_is('Strict-Transport-Security', 'max-age=300')

done_testing()
