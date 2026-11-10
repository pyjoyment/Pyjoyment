import Pyjo.Asset.File
import Pyjo.Asset.Memory
import Pyjoyment

from Pyjo.File import tempdir
from Pyjo.Test import *

import os
import re


with subtest('Synopsis'):
    from Pyjoyment.Static import Static

    static = Static()
    static.classes.append('MyApp.Controller.Foo')
    static.paths.append('/home/sri/public')
    is_deeply_ok(static.classes, ['__main__', 'MyApp.Controller.Foo'], 'classes')
    is_deeply_ok(static.paths, ['/home/sri/public'], 'paths')

    # Or import the module, as in Google Python Style Guide

    import Pyjoyment.Static

    static = Pyjoyment.Static.new()
    static.classes.append('MyApp.Controller.Foo')
    static.paths.append('/home/sri/public')
    is_deeply_ok(static.classes, ['__main__', 'MyApp.Controller.Foo'], 'classes')
    is_deeply_ok(static.paths, ['/home/sri/public'], 'paths')

with subtest('asset_dir'):
    static = Pyjoyment.Static.new()
    dir = static.asset_dir
    is_ok(dir, 'assets', 'default')
    static.asset_dir = 'assets'

with subtest('cache_control'):
    static = Pyjoyment.Static.new()
    cache_control = static.cache_control
    is_ok(cache_control, None, 'default')
    static.cache_control = 'public, max-age=60'
    static.cache_control = lambda c, rel: 'no-cache' if rel.endswith('.html') else 'public, max-age=60'
    is_ok(static.cache_control(None, 'index.html'), 'no-cache', 'function')
    is_ok(static.cache_control(None, 'app.css'), 'public, max-age=60', 'function')

    # Revalidate every file after a minute
    static.cache_control = 'public, max-age=60'
    is_ok(static.cache_control, 'public, max-age=60', 'string')

with subtest('classes'):
    static = Pyjoyment.Static.new()
    classes = static.classes
    is_deeply_ok(classes, ['__main__'], 'default')
    static.classes = ['__main__']

    # Add another class with static files in DATA section
    static.classes.append('Pyjoyment.Plugin.Fun')

    # Add another class with static files in DATA section and higher precedence
    static.classes.insert(0, 'Pyjoyment.Plugin.MoreFun')

    is_deeply_ok(static.classes, ['Pyjoyment.Plugin.MoreFun', '__main__', 'Pyjoyment.Plugin.Fun'], 'classes')

with subtest('encodings'):
    static = Pyjoyment.Static.new()
    encodings = static.encodings
    is_deeply_ok(encodings, {'br': '.br', 'zstd': '.zst', 'gzip': '.gz'}, 'default')
    is_deeply_ok(list(encodings), ['br', 'zstd', 'gzip'], 'order of preference')
    static.encodings = {'gzip': '.gz'}

    # Serve the files as they are only
    static.encodings = {}
    is_deeply_ok(static.encodings, {}, 'off')

with subtest('extra'):
    static = Pyjoyment.Static.new()
    extra = static.extra
    ok(os.path.isfile(extra['favicon.ico']), 'bundled favicon')
    ok(os.path.isfile(extra['pyjo/logo.png']), 'bundled logo')
    static.extra = {'foo/bar.txt': '/home/sri/myapp/bar.txt'}

    # Remove built-in favicon
    static = Pyjoyment.Static.new()
    del static.extra['favicon.ico']
    ok('favicon.ico' not in static.extra, 'removed')

with subtest('immutable'):
    static = Pyjoyment.Static.new()
    immutable = static.immutable
    is_ok(immutable, None, 'default')
    static.immutable = r'\.[0-9a-f]{12}\.[^/.]+$'
    ok(re.search(static.immutable, 'site.2fcb528ecde1.css'), 'hashed name')

    # The names of ManifestStaticFilesStorage of Django
    static.immutable = re.compile(r'\.[0-9a-f]{12}\.[^/.]+$')
    ok(static.immutable.search('admin/css/base.5af66c1b1797.css'), 'hashed name of Django')
    ok(not static.immutable.search('admin/css/base.css'), 'name without a hash')

with subtest('paths'):
    static = Pyjoyment.Static.new()
    paths = static.paths
    is_deeply_ok(paths, [], 'default')
    static.paths = ['/home/sri/public']

    # Add another "public" directory
    static.paths.append('/home/sri/public')

    # Add another "public" directory with higher precedence
    static.paths.insert(0, '/home/sri/themes/blue/public')

    is_deeply_ok(static.paths, ['/home/sri/themes/blue/public', '/home/sri/public', '/home/sri/public'], 'paths')

with subtest('prefix'):
    static = Pyjoyment.Static.new()
    prefix = static.prefix
    is_ok(prefix, None, 'default')
    static.prefix = '/static'

with subtest('asset_path'):
    static = Pyjoyment.Static.new()
    path = static.asset_path('/app.js')
    is_ok(path, '/assets/app.js', 'asset path')

with subtest('dispatch'):
    static = Pyjoyment.Static.new()
    app = Pyjoyment.new()
    c = app.build_controller()
    c.req.url.parse('/favicon.ico')
    boolean = static.dispatch(c)
    ok(boolean, 'served')
    is_ok(c.res.code, 200, 'right status')

with subtest('file'):
    dir = tempdir()
    dir.child('images').make_path().child('logo.png').spew(b'PNG')
    dir.child('foo').make_path().child('bar.html').spew(b'<p>bar</p>')
    static = Pyjoyment.Static.new()
    static.paths.append(dir.to_str())
    asset = static.file('images/logo.png')
    isa_ok(asset, Pyjo.Asset.File.object, 'file')
    asset = static.file('../lib/MyApp.py')
    is_ok(asset, None, 'does not exist')

    content = static.file('foo/bar.html').slurp()
    is_ok(content, b'<p>bar</p>', 'content')

with subtest('file_path'):
    static = Pyjoyment.Static.new()
    path = static.file_path('/index.html')
    is_ok(path, '/index.html', 'without prefix')
    static.prefix = '/static'
    is_ok(static.file_path('/index.html'), '/static/index.html', 'with prefix')

with subtest('is_fresh'):
    static = Pyjoyment.Static.new()
    app = Pyjoyment.new()
    boolean = static.is_fresh(app.build_controller(), etag='abc')
    ok(not boolean, 'stale without If-None-Match')
    boolean = static.is_fresh(app.build_controller(), etag='W/"def"')
    ok(not boolean, 'stale without If-None-Match')
    c = app.build_controller()
    c.req.headers.if_none_match = '"abc"'
    ok(static.is_fresh(c, etag='abc'), 'fresh')

with subtest('serve'):
    static = Pyjoyment.Static.new()
    app = Pyjoyment.new()
    c = app.build_controller()
    boolean = static.serve(c, 'pyjo/logo.png')
    ok(boolean, 'served')
    is_ok(c.res.headers.content_type, 'image/png', 'right "Content-Type" value')
    c = app.build_controller()
    boolean = static.serve(c, '../lib/MyApp.py')
    ok(not boolean, 'not served')

with subtest('serve_asset'):
    static = Pyjoyment.Static.new()
    app = Pyjoyment.new()
    c = app.build_controller()
    static.serve_asset(c, Pyjo.Asset.Memory.new().add_chunk(b'Hello'))
    is_ok(c.res.code, 200, 'right status')
    is_ok(c.res.headers.accept_ranges, 'bytes', 'right "Accept-Ranges" value')

with subtest('warmup'):
    static = Pyjoyment.Static.new()
    static.warmup()
    is_ok(static.asset_path('/app.js'), '/assets/app.js', 'warmed up')

done_testing()
