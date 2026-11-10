import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *


# Not in Mojolicious: an application mounted on / serves its own /favicon.ico, as the plugin removes the bundled one of
# Pyjoyment.Static, which is served before the routes, and keeps the images of /pyjo/


def wsgi(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [f'WSGI for {environ["PATH_INFO"]!r}'.encode()]


def mounted(key):
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.plugin('Mount', {key: wsgi})
    return app


with subtest('Mounted on /'):
    app = mounted('/')
    ok('favicon.ico' not in app.static.extra, 'no bundled favicon')
    ok('pyjo/logo.png' in app.static.extra, 'bundled images')
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/favicon.ico').status_is(200).content_is("WSGI for '/favicon.ico'")
        t.get_ok('/pyjo/logo.png').status_is(200).content_type_is('image/png')
        t.get_ok('/foo').status_is(200).content_is("WSGI for '/foo'")

with subtest('Mounted on a path'):
    app = mounted('/wsgi')
    ok('favicon.ico' in app.static.extra, 'bundled favicon')
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/favicon.ico').status_is(200).content_type_is('image/x-icon')
        t.get_ok('/wsgi/foo').status_is(200).content_is("WSGI for '/foo'")

with subtest('Mounted on a host'):
    app = mounted('example.com')
    ok('favicon.ico' in app.static.extra, 'bundled favicon of the other hosts')

with subtest('Mounted on a host and /'):
    app = mounted('example.com/')
    ok('favicon.ico' in app.static.extra, 'bundled favicon of the other hosts')

done_testing()
