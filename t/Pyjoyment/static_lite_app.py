"""
__DATA__
@@ hidden
Unreachable file.

@@ static.txt (base64)
dGVzdCAxMjMKbGFsYWxh

@@ static_utf8.txt
I ♥ Unicode
"""

import Pyjo.Asset.Memory
import Pyjo.Date
import Pyjo.Test.Pyjo

from Pyjo.File import curfile, tempdir
from Pyjo.Test import *
from Pyjoyment.Lite import get, hook, options, post

import os


# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor of Pyjo.Reactor.detect()

# Not in Mojolicious: the files of the DATA section are in the docstring, as the requests come before the end of the
# script

hook('after_static', lambda c: c.app.log.debug('Static file served'))

get('/hello3.txt', lambda c: c.reply.static('hello2.txt'))


@post('/hello4.txt')
def hello4(c):
    c.res.headers.content_type = 'text/html'
    c.reply.static('hello2.txt')


options('/hello.txt', lambda c: c.render(text='Options!'))


@get('/etag')
def etag(c):
    if c.is_fresh(etag='abc'):
        c.rendered(304)
    else:
        c.render(text='I ♥ Mojolicious!')


@get('/etag_weak')
def etag_weak(c):
    if c.is_fresh(etag='W/"abc"'):
        c.rendered(304)
    else:
        c.render(text='I ♥ Mojolicious!')


@get('/asset')
def asset(c):
    mem = Pyjo.Asset.Memory.new().add_chunk(b'I <3 Assets!')
    c.reply.asset(mem)


get('/file', lambda c: c.reply.file(curfile().sibling('templates2', '42.html.ep')))

t = Pyjo.Test.Pyjo.new()

with subtest('Freshness (Etag)'):
    c = t.app.build_controller()
    ok(not c.is_fresh(), 'content is stale')
    c.res.headers.etag = '"abc"'
    c.req.headers.if_none_match = '"abc"'
    ok(c.is_fresh(), 'content is fresh (strong If-None-Match + strong ETag)')
    c.res.headers.etag = 'W/"abc"'
    ok(c.is_fresh(), 'content is fresh (strong If-None-Match + weak ETag)')
    c.req.headers.if_none_match = 'W/"abc"'
    ok(c.is_fresh(), 'content is fresh (weak If-None-Match + weak ETag)')
    c.res.headers.etag = '"abc"'
    ok(not c.is_fresh(), 'content is not fresh (weak If-None-Match + strong ETag)')
    c.res.headers.etag = '"abc"'
    c.req.headers.if_none_match = ('"fooie"', 'W/"abc"')
    ok(not c.is_fresh(), 'content is not fresh (multiple If-None-Match + strong ETag)')
    c.res.headers.etag = 'W/"abc"'
    c.req.headers.if_none_match = ('W/"fooie"', '"abc"')
    ok(c.is_fresh(), 'content is fresh (multiple If-None-Match + weak ETag)')

with subtest('Freshness (Last-Modified)'):
    c = t.app.build_controller()
    date = Pyjo.Date.new(23)
    c.res.headers.last_modified = date
    c.req.headers.if_modified_since = date
    ok(c.is_fresh(), 'content is fresh')

with subtest('Freshness (Etag and Last-Modified)'):
    c = t.app.build_controller()
    date = Pyjo.Date.new(23)
    c.req.headers.if_none_match = '"abc"'
    c.req.headers.if_modified_since = date
    ok(c.is_fresh(etag='abc', last_modified=date.epoch), 'content is fresh')
    is_ok(c.res.headers.etag, '"abc"', 'right "ETag" value')
    is_ok(c.res.headers.last_modified, str(date), 'right "Last-Modified" value')

    c = t.app.build_controller()
    ok(not c.is_fresh(last_modified=date.epoch), 'content is stale')
    is_ok(c.res.headers.etag, None, 'no "ETag" value')
    is_ok(c.res.headers.last_modified, str(date), 'right "Last-Modified" value')

with subtest('Freshness (multiple Etag values)'):
    c = t.app.build_controller()
    c.req.headers.if_none_match = '"cba", "abc"'
    ok(c.is_fresh(etag='abc'), 'content is fresh')
    c = t.app.build_controller()
    c.req.headers.if_none_match = '"abc", "cba"'
    ok(c.is_fresh(etag='abc'), 'content is fresh')
    c = t.app.build_controller()
    c.req.headers.if_none_match = ' "xyz" , "abc","cba" '
    ok(c.is_fresh(etag='abc'), 'content is fresh')
    c = t.app.build_controller()
    c.req.headers.if_none_match = '"cba", "abc"'
    ok(not c.is_fresh(etag='cab'), 'content is stale')

with subtest('Static file'):
    with t.app.log.capture('trace') as logs:
        (
            t.get_ok('/hello.txt')
            .status_is(200)
            .header_is('Server', 'Pyjoyment (Python)')
            .header_exists_not('Cache-Control')
            .header_is('Accept-Ranges', 'bytes')
            .header_is('Content-Length', '31')
            .content_is('Hello Mojo from a static file!\n')
        )
        like_ok(str(logs), r'Static file served', 'right message')
        unlike_ok(str(logs), r'200 OK', 'no status message')

with subtest('Static file (HEAD)'):
    (
        t.head_ok('/hello.txt')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '31')
        .content_is('')
    )

with subtest('Route for method other than GET and HEAD'):
    (
        t.options_ok('/hello.txt')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Content-Length', '8')
        .content_is('Options!')
    )

with subtest('Unknown method'):
    t.put_ok('/hello.txt').status_is(404).header_is('Server', 'Pyjoyment (Python)')

with subtest('Partial static file'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=2-8'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_exists_not('Cache-Control')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '7')
        .header_is('Content-Range', 'bytes 2-8/31')
        .content_is('llo Moj')
    )

with subtest('Partial static file, no end'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=8-'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '23')
        .header_is('Content-Range', 'bytes 8-30/31')
        .content_is('jo from a static file!\n')
    )

with subtest('Partial static file, no start'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=-8'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '9')
        .header_is('Content-Range', 'bytes 0-8/31')
        .content_is('Hello Moj')
    )

with subtest('Partial static file, starting at first byte'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=0-8'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '9')
        .header_is('Content-Range', 'bytes 0-8/31')
        .content_is('Hello Moj')
    )

with subtest('Partial static file, invalid range'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=8-1'})
        .status_is(416)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('')
    )

with subtest('Partial static file, first byte'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=0-0'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '1')
        .header_is('Content-Range', 'bytes 0-0/31')
        .content_is('H')
    )

with subtest('Partial static file, end outside of range'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=25-31'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Content-Length', '6')
        .header_is('Content-Range', 'bytes 25-30/31')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('file!\n')
    )

with subtest('Partial static file, end way outside of range'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=25-300'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Content-Length', '6')
        .header_is('Content-Range', 'bytes 25-30/31')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('file!\n')
    )

with subtest('Partial static file, invalid range'):
    (
        t.get_ok('/hello.txt', {'Range': 'bytes=32-33'})
        .status_is(416)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('')
    )

with subtest('Render single byte static file'):
    (
        t.get_ok('/hello3.txt')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '1')
        .content_is('X')
    )

with subtest('Render partial single byte static file'):
    (
        t.get_ok('/hello3.txt', {'Range': 'bytes=0-0'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Length', '1')
        .header_is('Content-Range', 'bytes 0-0/1')
        .content_is('X')
    )

with subtest('Render static file with custom content type'):
    (
        t.post_ok('/hello4.txt')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_type_is('text/html')
        .header_is('Content-Length', '1')
        .content_is('X')
    )

with subtest('Fresh content'):
    (
        t.get_ok('/etag')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('ETag', '"abc"')
        .content_is('I ♥ Mojolicious!')
    )
    (
        t.get_ok('/etag_weak')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('ETag', 'W/"abc"')
        .content_is('I ♥ Mojolicious!')
    )
    (
        t.get_ok('/etag', {'If-None-Match': 'W/"abc"'})
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('ETag', '"abc"')
        .content_is('I ♥ Mojolicious!')
    )

with subtest('Stale content'):
    (
        t.get_ok('/etag', {'If-None-Match': '"abc"'})
        .status_is(304)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('ETag', '"abc"')
        .content_is('')
    )
    (
        t.get_ok('/etag_weak', {'If-None-Match': '"abc"'})
        .status_is(304)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('ETag', 'W/"abc"')
        .content_is('')
    )
    (
        t.get_ok('/etag_weak', {'If-None-Match': 'W/"abc"'})
        .status_is(304)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('ETag', 'W/"abc"')
        .content_is('')
    )

with subtest('Fresh asset'):
    t.get_ok('/asset').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('I <3 Assets!')

with subtest('Stale asset'):
    etag = t.tx.res.headers.etag
    t.get_ok('/asset', {'If-None-Match': etag}).status_is(304).header_is('Server', 'Pyjoyment (Python)').content_is('')

with subtest('Partial asset'):
    (
        t.get_ok('/asset', {'Range': 'bytes=3-5'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_exists_not('Cache-Control')
        .content_is('3 A')
    )

with subtest('File'):
    (
        t.get_ok('/file', {'Range': 'bytes=4-9'})
        .status_is(206)
        .content_type_is('application/octet-stream')
        .header_is('Server', 'Pyjoyment (Python)')
        .content_is('answer')
    )

with subtest('Empty file'):
    t.get_ok('/hello4.txt').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('')

with subtest('Partial empty file'):
    (
        t.get_ok('/hello4.txt', {'Range': 'bytes=0-0'})
        .status_is(416)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('')
    )

with subtest('Hidden inline file'):
    t.get_ok('/hidden').status_is(404).content_unlike(r'Unreachable file')

with subtest('Base64 static inline file, If-Modified-Since'):
    # The time the program started, as Perl's $^T
    modified = Pyjo.Date.new(Pyjo.Asset.Memory.MTIME - 1)
    (
        t.get_ok('/static.txt', {'If-Modified-Since': modified})
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('test 123\nlalala')
    )
    modified = t.tx.res.headers.last_modified
    (
        t.get_ok('/static.txt', {'If-Modified-Since': modified})
        .status_is(304)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_is('')
    )

with subtest('Base64 static inline file'):
    (
        t.get_ok('/static.txt')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('test 123\nlalala')
    )

with subtest('Base64 static inline file, If-Modified-Since'):
    modified = Pyjo.Date.new(Pyjo.Asset.Memory.MTIME - 1)
    (
        t.get_ok('/static.txt', {'If-Modified-Since': modified})
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('test 123\nlalala')
    )
    modified = t.tx.res.headers.last_modified
    (
        t.get_ok('/static.txt', {'If-Modified-Since': modified})
        .status_is(304)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_is('')
    )

with subtest('Base64 partial inline file'):
    (
        t.get_ok('/static.txt', {'Range': 'bytes=2-5'})
        .status_is(206)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .header_is('Content-Range', 'bytes 2-5/15')
        .header_is('Content-Length', '4')
        .content_is('st 1')
    )

with subtest('Base64 partial inline file, invalid range'):
    (
        t.get_ok('/static.txt', {'Range': 'bytes=45-50'})
        .status_is(416)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Accept-Ranges', 'bytes')
        .content_is('')
    )

with subtest('UTF-8 encoded inline file'):
    t.get_ok('/static_utf8.txt').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('I ♥ Unicode\n')

with subtest('Assets'):
    c = t.app.build_controller()
    is_ok(c.url_for_asset('/unknown.css').path, '/assets/unknown.css', 'right asset path')
    is_ok(c.url_for_asset('foo.css').path, '/assets/foo.ab1234cd5678ef.css', 'right asset path')
    is_ok(c.url_for_asset('/foo.css').path, '/assets/foo.ab1234cd5678ef.css', 'right asset path')
    is_ok(c.url_for_asset('/foo.js').path, '/assets/foo.ab1234cd5678ef.js', 'right asset path')
    is_ok(c.url_for_asset('/foo/bar/baz.js').path, '/assets/foo/bar/baz.development.js', 'right asset path')
    is_ok(c.url_for_asset('/foo/bar.js').path, '/assets/foo/bar.321.js', 'right asset path')
    is_ok(
        c.url_for_asset('/foo/bar/test.min.js').path, '/assets/foo/bar/test.ab1234cd5678ef.min.js', 'right asset path'
    )
    is_ok(c.url_for_asset('/foo/bar/yada.css').path, '/assets/foo/bar/yada.css', 'right asset path')

    (
        t.get_ok('/assets/foo.ab1234cd5678ef.css')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Cache-Control', 'no-cache')
        .content_like(r'\* foo\.css asset')
    )
    (
        t.get_ok('/assets/foo.ab1234cd5678ef.js')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Cache-Control', 'no-cache')
        .content_like(r'\* foo\.js asset')
    )
    (
        t.get_ok('/assets/foo/bar.321.js')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Cache-Control', 'no-cache')
        .content_like(r'\* foo\/bar\.js asset')
    )
    (
        t.get_ok('/assets/foo/bar/baz.development.js')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Cache-Control', 'no-cache')
        .content_like(r'\* foo\/bar\/baz\.js development asset')
    )
    (
        t.get_ok('/assets/foo/bar/baz.123.js')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Cache-Control', 'no-cache')
        .content_like(r'\* foo\/bar\/baz\.js asset')
    )
    (
        t.get_ok('/assets/foo/bar/test.ab1234cd5678ef.min.js')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Cache-Control', 'no-cache')
        .content_like(r'\* foo\/bar\/test\.min\.js asset')
    )
    (
        t.get_ok('/assets/foo/bar/yada.css')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('Cache-Control', 'no-cache')
        .content_like(r'\* foo\/bar\/yada\.css asset')
    )

    t.app.mode = 'production'
    (
        t.get_ok('/assets/foo.ab1234cd5678ef.css')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_exists_not('Cache-Control')
        .content_like(r'\* foo\.css asset')
    )

with subtest('Assets rebuilt during development'):
    dir = tempdir()
    assets = dir.child('assets').make_path()
    t.app.static.paths.insert(0, dir.to_str())
    c = t.app.build_controller()

    t.app.mode = 'development'
    is_ok(c.url_for_asset('/rebuilt.js').path, '/assets/rebuilt.js', 'asset has not been built yet')
    assets.child('rebuilt.ab1234.js').spew('production')
    is_ok(c.url_for_asset('/rebuilt.js').path, '/assets/rebuilt.ab1234.js', 'new asset has been found')
    assets.child('rebuilt.development.js').spew('development')
    is_ok(c.url_for_asset('/rebuilt.js').path, '/assets/rebuilt.development.js', 'development asset has precedence')
    t.get_ok('/assets/rebuilt.development.js').status_is(200).content_is('development')

    t.app.mode = 'production'
    assets.child('other.ab1234.js').spew('production')
    is_ok(c.url_for_asset('/other.js').path, '/assets/other.js', 'assets are not rebuilt in production')

    t.app.static.paths.pop(0)
    t.app.static.warmup()


with subtest('File'):
    c = t.app.build_controller()
    is_ok(c.url_for_file('/unknown.css').path, '/unknown.css', 'right file path')
    is_ok(c.url_for_file('/foo/bar.css').path, '/foo/bar.css', 'right file path')

# Not in Mojolicious: the precompressed variants of a file
with subtest('Precompressed variants'):
    dir = tempdir()
    for name, content in (
        ('compressed.txt', 'Hello Variants!'),
        ('compressed.txt.br', 'br variant'),
        ('compressed.txt.zst', 'zstd variant'),
        ('compressed.txt.gz', 'gzip variant'),
        ('plain.txt', 'Hello Plain!'),
        ('stale.txt', 'Hello Stale!'),
        ('stale.txt.gz', 'stale variant'),
    ):
        file = dir.child(name).spew(content)
        mtime = 1000000000 if name != 'stale.txt.gz' else 999999999
        os.utime(file.to_str(), (mtime, mtime))
    t.app.static.paths.insert(0, dir.to_str())
    # The bodies of the variants as they are, without an Accept-Encoding of the user agent
    t.ua.transactor.compressed = False

    (
        t.get_ok('/compressed.txt', {'Accept-Encoding': 'br, zstd, gzip'})
        .status_is(200)
        .header_is('Content-Encoding', 'br')
        .header_is('Content-Type', 'text/plain;charset=UTF-8')
        .header_is('Content-Length', '10')
        .header_is('Vary', 'Accept-Encoding')
        .content_is('br variant')
    )
    etag = t.tx.res.headers.etag
    like_ok(etag, r'^"[0-9a-f]{32}-br"$', 'ETag of the variant')
    (
        t.get_ok('/compressed.txt', {'Accept-Encoding': 'gzip'})
        .status_is(200)
        .header_is('Content-Encoding', 'gzip')
        .header_is('Vary', 'Accept-Encoding')
        .content_is('gzip variant')
    )
    t.get_ok('/compressed.txt', {'Accept-Encoding': 'x-gzip'}).status_is(200).content_is('gzip variant')
    (
        t.get_ok('/compressed.txt', {'Accept-Encoding': 'zstd, gzip'})
        .status_is(200)
        .header_is('Content-Encoding', 'zstd')
        .content_is('zstd variant')
    )
    (
        t.get_ok('/compressed.txt', {'Accept-Encoding': 'br;q=0.5, gzip'})
        .status_is(200)
        .header_is('Content-Encoding', 'gzip')
        .content_is('gzip variant')
    )
    (
        t.head_ok('/compressed.txt', {'Accept-Encoding': 'gzip'})
        .status_is(200)
        .header_is('Content-Encoding', 'gzip')
        .header_is('Content-Length', '12')
        .content_is('')
    )
    t.get_ok('/compressed.txt', {'Accept-Encoding': '*'}).status_is(200).content_is('br variant')
    t.get_ok('/compressed.txt', {'Accept-Encoding': '*, br;q=0'}).status_is(200).content_is('zstd variant')
    for accept in ('identity', 'br;q=0, zstd;q=0, gzip;q=0', 'deflate', 'gzip;q=0.5, identity', 'gzip;q=2'):
        (
            t.get_ok('/compressed.txt', {'Accept-Encoding': accept})
            .status_is(200)
            .header_exists_not('Content-Encoding')
            .header_is('Vary', 'Accept-Encoding')
            .content_is('Hello Variants!')
        )
    (
        t.get_ok('/compressed.txt')
        .status_is(200)
        .header_exists_not('Content-Encoding')
        .header_is('Vary', 'Accept-Encoding')
        .content_is('Hello Variants!')
    )
    original = t.tx.res.headers.etag
    isnt_ok(original, etag, 'ETag of the file')
    (
        t.get_ok('/compressed.txt', {'Accept-Encoding': 'br', 'If-None-Match': original})
        .status_is(200)
        .header_is('Content-Encoding', 'br')
        .content_is('br variant')
    )
    t.get_ok('/compressed.txt', {'Accept-Encoding': 'br', 'If-None-Match': etag}).status_is(304).content_is('')
    t.get_ok('/compressed.txt', {'If-None-Match': etag}).status_is(200).content_is('Hello Variants!')
    (
        t.get_ok('/compressed.txt', {'Accept-Encoding': 'gzip', 'Range': 'bytes=0-4'})
        .status_is(206)
        .header_exists_not('Content-Encoding')
        .header_is('Vary', 'Accept-Encoding')
        .content_is('Hello')
    )
    (
        t.get_ok('/stale.txt', {'Accept-Encoding': 'gzip'})
        .status_is(200)
        .header_exists_not('Content-Encoding')
        .header_exists_not('Vary')
        .content_is('Hello Stale!')
    )
    (
        t.get_ok('/plain.txt', {'Accept-Encoding': 'gzip'})
        .status_is(200)
        .header_exists_not('Content-Encoding')
        .header_exists_not('Vary')
        .content_is('Hello Plain!')
    )
    (
        t.get_ok('/compressed.txt.gz', {'Accept-Encoding': 'gzip'})
        .status_is(200)
        .header_exists_not('Content-Encoding')
        .header_is('Content-Type', 'application/x-gzip')
        .content_is('gzip variant')
    )

    t.app.static.encodings = {}
    (
        t.get_ok('/compressed.txt', {'Accept-Encoding': 'br, zstd, gzip'})
        .status_is(200)
        .header_exists_not('Content-Encoding')
        .header_exists_not('Vary')
        .content_is('Hello Variants!')
    )
    t.app.static.encodings = {'gzip': '.gz'}
    t.get_ok('/compressed.txt', {'Accept-Encoding': 'br, zstd, gzip'}).status_is(200).content_is('gzip variant')

    t.app.static.encodings = {'br': '.br', 'zstd': '.zst', 'gzip': '.gz'}
    t.ua.transactor.compressed = True
    t.app.static.paths.pop(0)

done_testing()
