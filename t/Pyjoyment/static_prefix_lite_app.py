"""
__DATA__
@@helpers.html.ep
%= url_for('/foo.png')
%= url_for_file('/foo.png')
%= url_for_asset('/foo.png')
%= url_for_asset('/foo.css')
%= favicon()
%= favicon('/foo.ico')
%= image('/foo.png')
%= image('http://example.com/foo.png')
%= javascript('/foo.js')
%= stylesheet('/foo.css')
%= asset_tag('/app.js')
%= asset_tag('/app.css')
%= asset_tag('/app.png')
%= asset_tag('/foo.css')

@@ hidden
Unreachable file.

@@ static.txt (base64)
dGVzdCAxMjMKbGFsYWxh

@@ static_utf8.txt
I ♥ Unicode
"""

import Pyjo.Test.Pyjo

from Pyjo.File import tempdir
from Pyjo.Test import *
from Pyjoyment.Lite import app, get


# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor of Pyjo.Reactor.detect()

# Not in Mojolicious: the files of the DATA section are in the docstring, as the requests come before the end of the
# script

app.static.prefix = '/static'

get('/hello.txt', {'text': 'Just an action!'})

get('/helpers')

t = Pyjo.Test.Pyjo.new()

with subtest('Action for static file path without prefix'):
    t.get_ok('/hello.txt').status_is(200).content_is('Just an action!')

with subtest('Static file'):
    (
        t.get_ok('/static/hello.txt')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_exists_not('Cache-Control')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '31')
        .content_is('Hello Mojo from a static file!\n')
    )

with subtest('Static asset'):
    (
        t.get_ok('/static/assets/foo.ab1234cd5678ef.css')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_like(r'\* foo\.css asset')
    )

with subtest('Bundled static file'):
    t.get_ok('/static/favicon.ico').status_is(200).content_type_is('image/x-icon')

# Renamed from Mojolicious: the stylesheet of the bundled template is pyjo/pyjo.css, where Mojo has mojo/mojo.css
with subtest('Bundled template'):
    (
        t.get_ok('/doesnotexist')
        .status_is(404)
        .element_exists('link[href=/static/favicon.ico]')
        .element_exists('link[href=/static/pyjo/pyjo.css]')
    )

with subtest('Helpers with prefix'):
    t.get_ok('/helpers').status_is(200).content_is("""\
/foo.png
/static/foo.png
/static/assets/foo.png
/static/assets/foo.ab1234cd5678ef.css
<link href="/static/favicon.ico" rel="icon">
<link href="/static/foo.ico" rel="icon">
<img src="/static/foo.png">
<img src="http://example.com/foo.png">
<script src="/static/foo.js"></script>
<link href="/static/foo.css" rel="stylesheet">
<script src="/static/assets/app.js"></script>
<link href="/static/assets/app.css" rel="stylesheet">
<img src="/static/assets/app.png">
<link href="/static/assets/foo.ab1234cd5678ef.css" rel="stylesheet">
""")

with subtest('Hidden inline file'):
    t.get_ok('/static/hidden').status_is(404).content_unlike(r'Unreachable file')

with subtest('Base64 partial inline file'):
    t.get_ok('/static.txt').status_is(404)
    (
        t.get_ok('/static/static.txt', {'Range': 'bytes=2-5'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Range', 'bytes 2-5/15')
        .header_is('Content-Length', '4')
        .content_is('st 1')
    )

with subtest('UTF-8 encoded inline file'):
    t.get_ok('/static_utf8.txt').status_is(404)
    t.get_ok('/static/static_utf8.txt').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is(
        'I ♥ Unicode\n'
    )

with subtest('File'):
    c = t.app.build_controller()
    is_ok(c.url_for_file('/unknown.css').path, '/static/unknown.css', 'right file path')
    is_ok(c.url_for_file('/foo/bar.css').path, '/static/foo/bar.css', 'right file path')
    is_ok(
        c.url_for_file('https://somesite.com/file.css').to_str(),
        'https://somesite.com/file.css',
        'right absolute file path?',
    )
    is_ok(
        c.url_for_asset('https://somesite.com/file.css').to_str(),
        'https://somesite.com/file.css',
        'right absolute asset path?',
    )

# Not in Mojolicious: the precompressed variants of a file
with subtest('Precompressed variants'):
    dir = tempdir()
    dir.child('compressed.txt').spew('Hello Variants!')
    dir.child('compressed.txt.gz').spew('gzip variant')
    t.app.static.paths.insert(0, dir.to_str())
    # The bodies of the variants as they are, without an Accept-Encoding of the user agent
    t.ua.transactor.compressed = False

    (
        t.get_ok('/static/compressed.txt', {'Accept-Encoding': 'br, gzip'})
        .status_is(200)
        .header_is('Content-Encoding', 'gzip')
        .header_is('Content-Type', 'text/plain;charset=UTF-8')
        .header_is('Vary', 'Accept-Encoding')
        .content_is('gzip variant')
    )
    (
        t.get_ok('/static/compressed.txt')
        .status_is(200)
        .header_exists_not('Content-Encoding')
        .header_is('Vary', 'Accept-Encoding')
        .content_is('Hello Variants!')
    )
    t.get_ok('/compressed.txt', {'Accept-Encoding': 'gzip'}).status_is(404)

    t.ua.transactor.compressed = True
    t.app.static.paths.pop(0)

# Not in Mojolicious: the Cache-Control of the files, with their paths without the prefix
with subtest('Cache-Control'):
    rels = []

    def cache_control(c, rel):
        rels.append(rel)
        return 'public, max-age=60'

    t.app.static.cache_control = cache_control
    t.app.static.immutable = r'^static_utf8\.txt$'
    (
        t.get_ok('/static/static_utf8.txt')
        .status_is(200)
        .header_is('Cache-Control', 'public, max-age=31536000, immutable')
    )
    t.get_ok('/static/hello.txt').status_is(200).header_is('Cache-Control', 'public, max-age=60')
    is_deeply_ok(rels, ['hello.txt'], 'path without the prefix')
    t.app.static.cache_control = None
    t.app.static.immutable = None

done_testing()
