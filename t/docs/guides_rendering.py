import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *

import gzip
import html as html_
import os
import pickle
import re
import subprocess
import sys


# The examples of docs/guides/rendering.rst, which includes them
EXAMPLES = Pyjo.File.curfile().dirname().dirname().sibling('docs', 'guides', 'rendering')


def rendering(name):
    return Pyjo.Test.Pyjo.new(EXAMPLES.child(f'{name}.py'))


def command(name, *args, plugins=None):
    # A script in a process of its own, with the directory of its plugins in front of sys.path, as the namespace
    # Pyjoyment.Plugin is extended when it is imported
    path = [os.getcwd(), *([EXAMPLES.child(plugins).to_str()] if plugins else [])]
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(reversed(path))}
    env.pop('PYJO_EXE', None)
    env.pop('PYJO_HOME', None)

    # The level of the log that Pyjo.Test.Pyjo sets for its own applications
    env.pop('PYJO_LOG_LEVEL', None)
    script = EXAMPLES.child(f'{name}.py').to_str()
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, env=env, timeout=60)


def inline(template, **stash):
    # A snippet of a template, rendered by the handler "ep" of an application
    app = Pyjoyment.new()
    app.routes.get('/').to(cb=lambda c: c.render(inline=template, **stash))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/').status_is(200)
        return t.tx.res.text


with subtest('Renderer'):
    app = Pyjoyment.new()
    r = app.routes
    r.get('/text').to(cb=lambda c: c.render(text='Hello.'))
    r.get('/json').to(cb=lambda c: c.render(json={'x': 3}))
    r.get('/gone').to(cb=lambda c: c.render(text='Oops.', status='410'))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/text').status_is(200).content_type_is('text/html;charset=UTF-8').content_is('Hello.')
        t.get_ok('/json').status_is(200).content_type_is('application/json;charset=UTF-8').content_is('{"x":3}')
        t.get_ok('/gone').status_is(410).content_type_is('text/html;charset=UTF-8').content_is('Oops.')

    renderer = app.renderer
    is_ok(renderer.template_name({'template': 'users/list', 'format': 'html', 'handler': 'ep'}), 'users/list.html.ep')
    is_ok(renderer.template_name({'template': 'foo', 'format': 'txt', 'handler': 'ep'}), 'foo.txt.ep', 'format')
    is_ok(renderer.template_name({'template': 'foo', 'format': 'html', 'handler': 'epl'}), 'foo.html.epl', 'handler')

    c = app.build_controller()
    c.stash(controller='users', action='list')
    is_ok(renderer.template_for(c), 'users/list', 'controller and action')
    c = app.build_controller()
    c.stash(controller='My.Users', action='add')
    is_ok(renderer.template_for(c), 'my/users/add', 'CamelCase')
    c = app.build_controller()
    c.stash(controller='my-users', action='show')
    is_ok(renderer.template_for(c), 'my/users/show', 'dash')

    with rendering('clock') as t:
        t.get_ok('/clock').status_is(200).text_like('body', re.compile(r'^The time is \d\d:\d\d:\d\d\.$'))
        t.get_ok('/hello').status_is(200).content_type_is('text/plain;charset=UTF-8').content_is('Hello World.\n')

with subtest('Embedded Python'):
    tags = inline(
        '<% i = 10 %>\n<ul>\n  <% for j in range(1, i + 1): %>\n    <li>\n      <%= j %>\n    </li>\n  <% end %>\n</ul>'
    )
    lines = inline('% i = 10\n<ul>\n  % for j in range(1, i + 1):\n    <li>\n      %= j\n    </li>\n  % end\n</ul>')
    is_ok(re.sub(r'\s+', '', tags), re.sub(r'\s+', '', lines), 'tags and lines')
    is_ok(re.sub(r'\s+', '', lines), '<ul>' + ''.join(f'<li>{j}</li>' for j in range(1, 11)) + '</ul>', 'list')
    is_ok(inline("<%= 'I ♥ Pyjoyment!' %>"), 'I ♥ Pyjoyment!\n', 'escaped')
    is_ok(inline("<%= '<p>I ♥ Pyjoyment!</p>' %>"), '&lt;p&gt;I ♥ Pyjoyment!&lt;/p&gt;\n', 'escaped markup')
    is_ok(inline("<%== '<p>I ♥ Pyjoyment!</p>' %>"), '<p>I ♥ Pyjoyment!</p>\n', 'not escaped')
    is_ok(
        inline("% from Pyjo.String.HTML import html\n<%= html('<p>I ♥ Pyjoyment!</p>') %>"),
        '<p>I ♥ Pyjoyment!</p>\n',
        'markup',
    )
    is_ok(
        inline(
            "<% for i in range(1, 4): %>\n  <%= 'Trim all whitespace characters around this expression' =%>\n<% end %>"
        ),
        '\n' + 'Trim all whitespace characters around this expression\n' * 3,
        'trimmed',
    )
    is_ok(inline('This is <%= 1 + 1 %> a\\\nsingle line'), 'This is 2 asingle line\n', 'escaped newline')
    is_ok(
        inline('This will <%= 1 + 1 %> result\\\\\nin multiple\\\\\nlines'),
        'This will 2 result\\\nin multiple\\\nlines\n',
        'escaped backslash',
    )
    is_ok(inline('There is <%= 1 + 1 %> no newline at the end here\\'), 'There is 2 no newline at the end here', 'end')

    app = Pyjoyment.new()

    @app.routes.get('/')
    def index(c):
        c.stash(name='tester')
        c.stash({'myapp.name': 'tester'})
        c.render(inline='Hello <%= name %> from <%= c.tx.remote_address %>.')

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/').status_is(200).content_is('Hello tester from 127.0.0.1.\n')

    like_ok(html_.unescape(inline("<%= dumper({'foo': 'bar'}) %>")), re.compile(r"\{'foo': 'bar'\}"), 'dumper')

with subtest('Automatic rendering'):
    app = Pyjoyment.new()
    app.renderer.classes.append(__name__)
    r = app.routes
    r.get('/render').to(cb=lambda c: c.render(inline='rendered'))

    @r.get('/later')
    def later(c):
        c.render_later()
        Pyjo.IOLoop.timer(0.01, lambda loop: c.render(text='later'))

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/render').status_is(200).content_is('rendered\n')
        t.get_ok('/later').status_is(200).content_is('later')

with subtest('Rendering templates'):
    app = Pyjoyment.new()
    home = Pyjo.File.tempdir()
    templates = home.child('templates')
    templates.child('foo', 'bar').make_path()
    templates.child('foo', 'bar', 'baz.html.ep').spew('HTML\n')
    templates.child('foo', 'bar', 'baz.txt.epl').spew('<%= 1 + 1 %> TXT\n')
    templates.child('foo', 'bar', 'baz.html+phone.ep').spew('Phone\n')
    templates.child('mail.html.ep').spew('Mail <%= name %>\n')
    templates.child('invoice.pdf.ep').spew('PDF 1.7\n')
    templates.child('reminder.html.ep').spew('Remember\n')
    templates.child('layouts').make_path().child('mail.html.ep').spew('<mail><%= content() %></mail>\n')
    app.renderer.paths = [templates.to_str()]
    r = app.routes
    r.get('/template').to(cb=lambda c: c.render(template='foo/bar/baz'))
    r.get('/txt').to(cb=lambda c: c.render(template='foo/bar/baz', format='txt', handler='epl'))
    r.get('/shortcut').to(cb=lambda c: c.render('foo/bar/baz'))
    r.get('/maybe').to(cb=lambda c: c.render_maybe('localized/baz') or c.render('foo/bar/baz'))
    r.get('/variant').to(cb=lambda c: c.render('foo/bar/baz', variant='phone'))
    r.get('/variant2').to(cb=lambda c: c.render('foo/bar/baz', variant='tablet'))
    strings = {}

    @r.get('/strings')
    def strings_(c):
        strings['html'] = c.render_to_string('mail', name='Pyjo')
        strings['pdf'] = c.render_to_string('invoice', format='pdf')
        strings['layout'] = c.render_to_string('reminder', layout='mail')
        strings['name'] = c.stash('name')
        c.render(data=strings['pdf'], format='pdf')

    r.get('/inline').to(cb=lambda c: c.render(inline='The result is <%= 1 + 1 %>.'))
    r.get('/epl').to(cb=lambda c: c.render(inline="<%= args[0].param('foo') %>", handler='epl'))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/template').status_is(200).content_is('HTML\n')
        t.get_ok('/txt').status_is(200).content_type_is('text/plain;charset=UTF-8').content_is('2 TXT\n')
        t.get_ok('/shortcut').status_is(200).content_is('HTML\n')
        t.get_ok('/maybe').status_is(200).content_is('HTML\n')
        t.get_ok('/variant').status_is(200).content_is('Phone\n')
        t.get_ok('/variant2').status_is(200).content_is('HTML\n')
        t.get_ok('/strings').status_is(200).content_type_is('application/pdf').content_is('PDF 1.7\n')
        t.get_ok('/inline').status_is(200).content_is('The result is 2.\n')
        t.get_ok('/epl?foo=bar').status_is(200).content_is('bar\n')
    is_ok(strings['html'], 'Mail Pyjo\n', 'string')
    is_ok(strings['layout'], '<mail>Remember\n</mail>\n', 'layout')
    is_ok(strings['name'], None, 'localized')

with subtest('Rendering text, data and JSON'):
    app = Pyjoyment.new()
    r = app.routes
    r.get('/text').to(cb=lambda c: c.render(text='I ♥ Pyjoyment!'))
    r.get('/data').to(cb=lambda c: c.render(data=b'\x00\x01'))
    r.get('/json').to(cb=lambda c: c.render(json={'foo': [1, 'test', 3]}))
    r.get('/status').to(cb=lambda c: c.render(text='Oops.', status=500))
    r.get('/txt').to(cb=lambda c: c.render(text='Hello.', format='txt'))
    r.get('/png').to(cb=lambda c: c.render(data=b'\x89PNG', format='png'))
    r.get('/md').to(cb=lambda c: c.render(text='# Hello', format='md'))
    app.types.type('md', 'text/markdown')
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/text').status_is(200).content_is('I ♥ Pyjoyment!')
        is_ok(t.tx.res.body, 'I ♥ Pyjoyment!'.encode(), 'encoded')
        t.get_ok('/data').status_is(200)
        is_ok(t.tx.res.body, b'\x00\x01', 'bytes')
        t.get_ok('/json').status_is(200).json_is({'foo': [1, 'test', 3]})
        t.get_ok('/status').status_is(500).content_is('Oops.')
        t.get_ok('/txt').status_is(200).content_type_is('text/plain;charset=UTF-8')
        t.get_ok('/png').status_is(200).content_type_is('image/png')
        t.get_ok('/md').status_is(200).content_type_is('text/markdown')

with subtest('Stash data'):
    app = Pyjoyment.new()

    @app.routes.get('/')
    def stash(c):
        c.stash(description='web framework')
        c.stash(frameworks=['Catalyst', 'Mojolicious', 'Pyjoyment'])
        c.stash(spinoffs={'minion': 'job queue'})
        c.render(
            inline='%= description\n'
            '%= frameworks[1]\n'
            "%= spinoffs['minion']\n"
            '% for framework in frameworks:\n'
            '  <%= framework %> is a <%= description %>.\n'
            '% end\n'
            "% if (description := spinoffs.get('minion')):\n"
            '  Minion is a <%= description %>.\n'
            '% end\n'
            "% if (spinoffs := stash('spinoffs')):\n"
            "  Minion is a <%= spinoffs['minion'] %>.\n"
            '% end\n'
        )

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/').status_is(200).content_is(
            'web framework\nMojolicious\njob queue\n'
            '  Catalyst is a web framework.\n'
            '  Mojolicious is a web framework.\n'
            '  Pyjoyment is a web framework.\n'
            '  Minion is a job queue.\n'
            '  Minion is a job queue.\n'
        )

with subtest('Helpers'):
    app = Pyjoyment.new()
    like_ok(inline('%= dumper([1, 2, 3])'), re.compile(r'\[1, 2, 3\]'), 'template')
    like_ok(app.dumper([1, 2, 3]), re.compile(r'\[1, 2, 3\]'), 'application')
    c = app.build_controller()
    like_ok(c.dumper([1, 2, 3]), re.compile(r'\[1, 2, 3\]'), 'controller')
    like_ok(c.helpers.dumper([1, 2, 3]), re.compile(r'\[1, 2, 3\]'), 'helpers')
    is_ok(
        inline("%= link_to('Pyjoyment', 'https://pyjoyment.readthedocs.io')"),
        '<a href="https://pyjoyment.readthedocs.io">Pyjoyment</a>\n',
        'tag helper',
    )

with subtest('Static files'):
    with rendering('static_files') as t:
        t.get_ok('/').status_is(200).text_is('title', 'Static')
        t.get_ok('/some_download').status_is(200).content_type_is('image/png')
        t.header_is('Content-Disposition', 'attachment; filename=bar.png;')
        # The example serves /etc/passwd, which Windows does not have
        if sys.platform == 'win32':
            skip('no /etc/passwd on Windows', 3)
        else:
            t.get_ok('/leak').status_is(200).content_is(Pyjo.File.path('/etc/passwd').slurp().decode())

    app = Pyjoyment.new()
    app.static.paths = [EXAMPLES.child('public').to_str()]

    # Serve static files only with a "/static" prefix
    app.static.prefix = '/static'

    app.routes.get('/url').to(cb=lambda c: c.render(text=c.url_for_file('/index.html').to_str()))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/index.html').status_is(404)
        t.get_ok('/static/index.html').status_is(200).text_is('title', 'Static')
        t.get_ok('/url').status_is(200).content_is('/static/index.html')

with subtest('Static assets'):
    app = Pyjoyment.new()
    public = Pyjo.File.tempdir()
    assets = public.child('assets')
    assets.child('foo').make_path()
    assets.child('myapp.ab1234cd5678ef.js').spew('alert(1);\n')
    assets.child('foo', 'bar.development.js').spew('alert(2);\n')
    assets.child('foo', 'bar.ab1234cd5678ef.js').spew('alert(3);\n')
    app.static.paths = [public.to_str()]
    app.static.warmup()
    c = app.build_controller()
    is_ok(c.url_for_asset('/myapp.js').to_str(), '/assets/myapp.ab1234cd5678ef.js', 'url_for_asset')
    is_ok(c.asset_tag('/myapp.js'), '<script src="/assets/myapp.ab1234cd5678ef.js"></script>', 'asset_tag')
    is_ok(c.url_for_asset('/foo/bar.js').to_str(), '/assets/foo/bar.development.js', 'development')
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/assets/myapp.ab1234cd5678ef.js').status_is(200).header_is('Cache-Control', 'no-cache')

with subtest('Static assets, Cache-Control'):
    app = Pyjoyment.new()
    public = Pyjo.File.tempdir()
    public.child('assets').make_path().child('myapp.ab1234cd5678ef.js').spew('alert(1);\n')
    public.child('index.html').spew('<p>Static</p>\n')
    app.static.paths = [public.to_str()]

    # Revalidate static files after a minute, and never the assets with checksums
    app.static.cache_control = 'public, max-age=60'
    app.static.immutable = r'^assets/.+\.[0-9a-f]{8,}\.[^/]+$'

    app.mode = 'production'
    with Pyjo.Test.Pyjo.new(app) as t:
        (
            t.get_ok('/assets/myapp.ab1234cd5678ef.js')
            .status_is(200)
            .header_is('Cache-Control', 'public, max-age=31536000, immutable')
        )
        t.get_ok('/index.html').status_is(200).header_is('Cache-Control', 'public, max-age=60')
    app.mode = 'development'
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/assets/myapp.ab1234cd5678ef.js').status_is(200).header_is('Cache-Control', 'no-cache')

with subtest('Precompressed static files'):
    app = Pyjoyment.new()
    public = Pyjo.File.tempdir()
    public.child('app.css').spew('body { color: red }\n')
    public.child('app.css.br').spew('br')
    public.child('app.css.zst').spew('zstd')
    public.child('app.css.gz').spew('gzip')
    app.static.paths = [public.to_str()]
    with Pyjo.Test.Pyjo.new(app) as t:
        t.ua.transactor.compressed = False
        (
            t.get_ok('/app.css', {'Accept-Encoding': 'gzip, br, zstd'})
            .status_is(200)
            .header_is('Content-Encoding', 'br')
            .header_like('Content-Type', r'^text/css')
            .header_is('Vary', 'Accept-Encoding')
            .content_is('br')
        )
        t.get_ok('/app.css', {'Accept-Encoding': 'gzip, zstd'}).status_is(200).content_is('zstd')

        # Look for gzip variants only
        app.static.encodings = {'gzip': '.gz'}
        t.get_ok('/app.css', {'Accept-Encoding': 'gzip, br, zstd'}).status_is(200).content_is('gzip')

        # Serve static files only as they are
        app.static.encodings = {}
        (
            t.get_ok('/app.css', {'Accept-Encoding': 'gzip, br, zstd'})
            .status_is(200)
            .header_exists_not('Content-Encoding')
            .header_exists_not('Vary')
            .content_is('body { color: red }\n')
        )

with subtest('Content negotiation'):
    app = Pyjoyment.new()
    templates = Pyjo.File.tempdir()
    templates.child('hello.html.ep').spew('<%= content("head") %>Hello <%= message %>.\n')
    app.renderer.paths = [templates.to_str()]
    r = app.routes

    @r.get('/hello', format=['json', 'xml']).to(format=None)
    def hello(c):
        c.respond_to(json={'json': {'hello': 'world'}}, xml={'text': '<hello>world</hello>'})

    @r.get('/hello2', format=['json', 'html', 'png']).to(format=None)
    def hello2(c):
        c.respond_to(
            json={'json': {'hello': 'world'}},
            html={'template': 'hello', 'message': 'world'},
            any={'text': '', 'status': 204},
        )

    @r.get('/hello3', format=['json', 'html']).to(format=None)
    def hello3(c):
        def html(c):
            c.content_for('head', '<meta name="author" content="sri">')
            c.render(template='hello', message='world')

        c.respond_to(json={'json': {'hello': 'world'}}, html=html)

    @r.get('/accepts', format=['html', 'xml', 'txt']).to(format=None)
    def accepts(c):
        c.render(text=str(c.accepts('html', 'xml')))

    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/hello', {'Accept': 'application/json'}).status_is(200).json_is({'hello': 'world'})
        t.get_ok('/hello', {'Accept': 'application/xml'}).status_is(200).content_is('<hello>world</hello>')
        t.get_ok('/hello.json').status_is(200).json_is({'hello': 'world'})
        t.get_ok('/hello.xml').status_is(200).content_is('<hello>world</hello>')
        t.get_ok('/hello?_format=json').status_is(200).json_is({'hello': 'world'})
        t.get_ok('/hello?_format=xml').status_is(200).content_is('<hello>world</hello>')
        t.get_ok('/hello2', {'Accept': 'application/json'}).status_is(200).json_is({'hello': 'world'})
        t.get_ok('/hello2', {'Accept': 'text/html'}).status_is(200).content_is('Hello world.\n')
        t.get_ok('/hello2', {'Accept': 'image/png'}).status_is(204)
        t.get_ok('/hello2.png').status_is(204)
        t.get_ok('/hello2?_format=html').status_is(200).content_is('Hello world.\n')
        t.get_ok('/hello3.html').status_is(200).content_is('<meta name="author" content="sri">Hello world.\n')
        t.get_ok('/accepts').status_is(200).content_is('html')
        t.get_ok('/accepts', {'Accept': 'text/html'}).status_is(200).content_is('html')
        t.get_ok('/accepts', {'Accept': 'text/xml'}).status_is(200).content_is('xml')
        t.get_ok('/accepts', {'Accept': 'text/plain'}).status_is(200).content_is('None')
        t.get_ok('/accepts.xml').status_is(200).content_is('xml')
        t.get_ok('/accepts.txt').status_is(200).content_is('None')
        t.get_ok('/accepts?_format=html').status_is(200).content_is('html')

with subtest('Rendering exception and not_found pages'):
    with rendering('divide') as t:
        t.get_ok('/divide/8/by/2').status_is(200).content_is('4')
        t.get_ok('/divide/8/by/x').status_is(404)
        t.get_ok('/divide/8/by/0').status_is(500).text_like('#error', re.compile(r'Division by zero!'))

    os.environ['PYJO_MODE'] = 'production'
    try:
        with rendering('exception_template') as t:
            t.get_ok('/dies').status_is(500).text_is('title', 'Server error')
            t.text_like('p', re.compile(r'^Intentional error')).text_like('pre', re.compile(r"'action'|'cb'"))
    finally:
        del os.environ['PYJO_MODE']

    with rendering('exception_format') as t:
        t.get_ok('/json').status_is(500).json_like('/error', re.compile(r'^Just a test'))
        t.get_ok('/txt').status_is(500).content_type_like(re.compile(r'text/plain')).content_like(r'Just a test')

    with rendering('before_render') as t:
        t.get_ok('/', {'Accept': 'application/json'}).status_is(500).json_like('/exception', r'This should not happen!')
        t.get_ok('/', {'Accept': 'text/html'}).status_is(500).content_type_like(re.compile(r'html'))

with subtest('Layouts'):
    with rendering('layout') as t:
        t.get_ok('/').status_is(200).text_is('title', 'MyApp').text_like('body', re.compile(r'Hello World!'))
    with rendering('layout_title') as t:
        t.get_ok('/').status_is(200).text_is('title', 'Hi there').text_like('body', re.compile(r'Hello World!'))

    app = Pyjoyment.new()
    app.renderer.classes = ['__main__' if __name__ == '__main__' else __name__]
    home = Pyjo.File.tempdir()
    templates = home.child('templates')
    templates.child('layouts').make_path().child('mylayout.html.ep').spew('<my><%= content() %></my>\n')
    templates.child('mytemplate.html.ep').spew('Mine\n')
    app.renderer.paths = [templates.to_str()]
    app.routes.get('/').to(cb=lambda c: c.render(template='mytemplate', layout='mylayout'))
    app.routes.get('/defaults').to(cb=lambda c: c.render(template='mytemplate'))
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/').status_is(200).content_is('<my>Mine\n</my>\n')
        app.defaults(layout='mylayout')
        t.get_ok('/defaults').status_is(200).content_is('<my>Mine\n</my>\n')

with subtest('Partial templates'):
    with rendering('partial') as t:
        t.get_ok('/').status_is(200).text_is('head title', 'Howdy').text_is('body', 'Bar')

with subtest('Reusable template blocks'):
    with rendering('blocks') as t:
        t.get_ok('/').status_is(200).content_like(r'Hello Wolfgang\.\s+Hello Baerbel\.')

with subtest('Adding helpers'):
    with rendering('debug_helper') as t:
        with t.app.log.capture('debug') as messages:
            t.get_ok('/').status_is(200)
        like_ok(str(messages), r'\[debug\] Hello from an action!', 'action')
        like_ok(str(messages), r'\[debug\] Hello from a template!', 'template')

    with rendering('trim_newline') as t:
        t.get_ok('/').status_is(200).content_like(r'^\s*Some text\.\s*2\s*More text\.$')
        unlike_ok(t.tx.res.text.rstrip('\n'), re.compile(r'\n'), 'no newlines')

    with rendering('cache_control') as t:
        t.get_ok('/news').status_is(200).header_is('Cache-Control', 'private, max-age=0, no-cache')
        t.content_is('Always up to date.')
        t.get_ok('/some_older_story').status_is(200).header_is('Cache-Control', 'public, max-age=300')
        t.content_is('This one can be cached for a bit.')

with subtest('Content blocks'):
    with rendering('content_for') as t:
        t.get_ok('/').status_is(200).element_exists('head meta[http-equiv="Content-Type"]')
        t.element_exists('head meta[http-equiv="Pragma"]').text_is('body div', 'Hello World!')

with subtest('Forms'):
    with rendering('form') as t:
        t.ua.max_redirects = 1
        t.get_ok('/').status_is(200).element_exists('form[action="/nothing?_method=PUT"][method="POST"]')
        t.element_exists('input[name="whatever"][value="I ♥ Pyjoyment!"]')
        t.post_ok('/nothing?_method=PUT', form={'whatever': 'test'}).status_is(200)
        t.text_is('p', 'We did nothing with your value (test).')
        t.get_ok('/').status_is(200).element_exists_not('p')

with subtest('Form validation'):
    with rendering('validation') as t:
        t.get_ok('/').status_is(200).element_exists('input[name="user"]').element_exists_not('.field-with-error')
        t.get_ok('/?user=sri').status_is(200).text_like('html body', re.compile(r'Thank you sri\.'))
        t.get_ok('/?user=SRI').status_is(200).element_exists('input.field-with-error[name="user"][value="SRI"]')
        t.element_exists('label.field-with-error[for="user"]')
        t.get_ok('/?user=sri&pass=s3cr3tpass&pass_again=s3cr3tpass').status_is(200).text_like('body', r'Thank you')
        t.get_ok('/?user=sri&pass=s3cr3tpass&pass_again=other').status_is(200)
        t.element_exists('input.field-with-error[name="pass_again"]')
        t.get_ok('/?user=sri&pass=short').status_is(200).element_exists('input.field-with-error[name="pass"]')

with subtest('Adding form validation checks'):
    with rendering('range_check') as t:
        t.ua.max_redirects = 1
        t.get_ok('/').status_is(200).element_exists('input[name="number"]')
        t.post_ok('/test', form={'number': '7'}).status_is(200).text_is('p', 'Thanks, the number 7 was valid.')
        t.post_ok('/test', form={'number': '42'}).status_is(200).text_like('p', r'between 3 and 23')
        t.post_ok('/test').status_is(200).text_like('p', r'Value is required\.')

with subtest('Cross-site request forgery'):
    with rendering('csrf') as t:
        t.get_ok('/').status_is(200).element_exists('input[name="csrf_token"]')
        token = t.tx.res.dom().at('input[name="csrf_token"]').attr('value')
        t.post_ok('/', form={'city': 'Berlin'}).status_is(403).content_is('Bad CSRF token!')
        t.post_ok('/', form={'city': 'Berlin', 'csrf_token': token}).status_is(200)
        t.content_is('Low orbit ion cannon pointed at Berlin!')
        t.post_ok('/', {'X-CSRF-Token': t.app.build_controller().csrf_token()}, form={'city': 'Paris'})
        t.status_is(403)

with subtest('Template inheritance'):
    with rendering('inheritance') as t:
        t.get_ok('/first').status_is(200).text_is('title', 'Hello')
        t.content_like(r'Default header\s+<div>Hello World!</div>\s+Default footer')
        t.get_ok('/third').status_is(200).content_like(r'New header\s+<div>Hello World!</div>\s+New footer')

with subtest('Custom responses'):
    # The examples serve /etc/passwd, which Windows does not have
    if sys.platform == 'win32':
        skip('no /etc/passwd on Windows', 11)
    else:
        passwd = Pyjo.File.path('/etc/passwd').slurp().decode()
        with rendering('leak_asset') as t:
            t.get_ok('/leak').status_is(200).content_type_is('text/plain').content_is(passwd)
            t.get_ok('/leak', {'Range': 'bytes=0-3'}).status_is(206).content_is(passwd[:4])
        with rendering('leak_rendered') as t:
            t.get_ok('/leak').status_is(200).content_type_is('text/plain').content_is(passwd)

with subtest('Helper plugins'):
    result = command('debug_plugin', 'get', '/', plugins='debug_helper_plugin')
    is_ok(result.stdout, 'Hello!', 'plugin')
    like_ok(result.stderr, re.compile(r'\[debug\] .*It works!'), 'helper')

with subtest('Bundling assets with plugins'):
    for plugins in ('alert_assets', 'alert_assets_data'):
        result = command('alert_me', 'get', '/alert_me', plugins=plugins)
        like_ok(result.stdout, re.compile(r'<script src="/alertassets\.js"></script>'), f'{plugins} template')
        result = command('alert_me', 'get', '/alertassets.js', plugins=plugins)
        like_ok(result.stdout, re.compile(r'^alert\("Hello World!"\);\n+$'), f'{plugins} static file')

with subtest('Post-processing dynamic content'):
    with rendering('compressed') as t:
        # The user agent decompresses the response by default
        def raw(ua, tx):
            tx.res.content.auto_decompress = False

        t.ua.once('start', raw)
        t.get_ok('/', {'Accept-Encoding': 'gzip'}).status_is(200).header_is('Content-Encoding', 'gzip')
        t.header_is('Vary', 'Accept-Encoding')
        like_ok(gzip.decompress(t.tx.res.body).decode(), re.compile(r'Compressed content\.'), 'compressed')
        t.get_ok('/', {'Accept-Encoding': 'identity'}).status_is(200).header_exists_not('Content-Encoding')
        t.text_is('body', 'Compressed content.')

with subtest('Streaming'):
    with rendering('streaming') as t:
        t.get_ok('/').status_is(200).header_is('Content-Length', '12').content_is('Hello World!')
    with rendering('streaming_finish') as t:
        t.get_ok('/').status_is(200).header_is('Connection', 'close').content_is('Hello World!')

with subtest('Chunked transfer encoding'):
    with rendering('chunked') as t:
        t.get_ok('/').status_is(200).header_is('Transfer-Encoding', None)
        t.content_is('<html><head><title>Example</title></head><body>Example</body></html>')
    result = command('chunked', 'get', '-v', '/')
    like_ok(result.stderr, re.compile(r'^Transfer-Encoding: chunked$', re.M), 'chunked')

with subtest('Encoding'):
    app = Pyjoyment.new()
    app.renderer.encoding = 'koi8-r'
    is_ok(app.renderer.encoding, 'koi8-r', 'encoding')
    with rendering('heart') as t:
        t.get_ok('/heart').status_is(200).content_is('I ♥ Pyjoyment!\n')

with subtest('Base64 encoded DATA files'):
    with rendering('favicon') as t:
        t.get_ok('/').status_is(200).content_is('I ♥ Pyjoyment!')
        t.get_ok('/favicon.ico').status_is(200)
        is_ok(t.tx.res.body, EXAMPLES.child('public', 'foo', 'bar.png').slurp(), 'decoded')

with subtest('Customizing the template syntax'):
    with rendering('mustache') as t:
        t.get_ok('/').status_is(200).content_is('Hello Anonymous.\n')
        t.get_ok('/sri').status_is(200).content_is('Hello sri.\n')

with subtest('Adding your favorite template system'):
    is_ok(command('mine', 'get', '/inline', plugins='my_renderer').stdout, 'Hello Pyjoyment inline!', 'inline')
    is_ok(command('mine', 'get', '/data', plugins='my_renderer').stdout, 'Hello Pyjoyment from the DATA section!\n')

with subtest('Adding a handler to generate binary data'):
    with rendering('pickled') as t:
        t.get_ok('/').status_is(200)
        is_deeply_ok(pickle.loads(t.tx.res.body), {'i': '♥ pyjoyment'}, 'pickled')

        # Explicit "handler" value
        t.app.routes.get('/explicit').to(cb=lambda c: c.render(pickle={'i': 'explicit'}, handler='pickle'))

        # Implicit "handler" value (with "before_render" hook)
        t.app.routes.get('/implicit').to(cb=lambda c: c.render(pickle={'i': 'implicit'}))

        t.get_ok('/explicit').status_is(200)
        is_deeply_ok(pickle.loads(t.tx.res.body), {'i': 'explicit'}, 'explicit')
        t.get_ok('/implicit').status_is(200)
        is_deeply_ok(pickle.loads(t.tx.res.body), {'i': 'implicit'}, 'implicit')

done_testing()
