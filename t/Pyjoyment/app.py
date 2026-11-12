import Pyjo.Asset.File
import Pyjo.Date
import Pyjo.File
import Pyjo.Home
import Pyjo.IOLoop
import Pyjo.Test.Pyjo
import Pyjoyment
import Pyjoyment.Controller
import Pyjoyment.Plugin
import Pyjoyment.Routes
import Pyjoyment.Routes.Route

from Pyjo.File import curfile, path
from Pyjo.Test import *

import contextlib
import gc
import os
import re
import sys


# BEGIN { $ENV{MOJO_MODE} = 'development' }, before the mode of the applications is read
# Left out from Mojolicious: PLACK_ENV, as Pyjoyment has no counterpart of it
os.environ['PYJO_MODE'] = 'development'

# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor of Pyjo.Reactor.detect()

# Renamed from Mojolicious: the modules of the tests are in tt/lib, where Mojo has them in t/mojolicious/lib
sys.path.insert(0, curfile().dirname().dirname().dirname().child('tt', 'lib').to_str())

import PyjoymentTest  # noqa: E402  # pyright: ignore[reportMissingImports]


# Not in Mojolicious: the home of the applications of tt/lib is the directory of this test, with the templates, the
# static files and the configuration files of the tests, as Mojo detects t/mojolicious from t/mojolicious/lib
os.environ['PYJO_HOME'] = curfile().dirname().to_str()

# Unlike Mojolicious: the "Server" header is "Pyjoyment (Python)", the names of the applications and the classes are
# the ones of Pyjoyment, as PyjoymentTest for MojoliciousTest, and Perl's die is raise; the name of a class in a
# message is the module and the name of the class in it, as PyjoymentTest.Foo.PyjoymentTest_Foo, and a name of a
# controller is dotted, as Foo.Bar for Foo::Bar


# Not in Mojolicious: local of the environment
@contextlib.contextmanager
def local(**env):
    saved = {name: os.environ.get(name) for name in env}
    for name, value in env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


with subtest('Missing config file'):
    throws_ok(
        lambda: Pyjo.Test.Pyjo.new('PyjoymentConfigTest').app,
        re.compile(r'pyjoyment_config_test\.conf" missing'),
        'right error',
    )
    with local(PYJO_MODE='whatever'):
        is_ok(Pyjo.Test.Pyjo.new('PyjoymentConfigTest').app.config()['it'], 'works', 'right result')

with subtest('Bad deployment plugins'):
    # Unlike Mojolicious: a list and a dict, where Mojo has an array reference and a hash reference
    throws_ok(
        lambda: Pyjo.Test.Pyjo.new('PyjoymentTest').app.plugin('Config', {'default': {'plugins': 'fail'}}),
        re.compile(r'Configuration value "plugins" is not a list'),
        'right error',
    )
    throws_ok(
        lambda: Pyjo.Test.Pyjo.new('PyjoymentTest').app.plugin('Config', {'default': {'plugins': ['fail']}}),
        re.compile(r'Configuration value "plugins" contains an entry that is not a dict'),
        'right error',
    )

# Mode detection
# Left out from Mojolicious: the mode of PLACK_ENV, as Pyjoyment has no counterpart of it
with local(PYJO_MODE='else'):
    is_ok(Pyjo.Test.Pyjo.new('PyjoymentTest').app.mode, 'else', 'right mode')

# Optional home detection
path_ = ['th', 'is', 'mojo', 'dir', 'wil', 'l', 'never-ever', 'exist']
app = Pyjoyment.new(home=Pyjo.Home.new(*path_))
is_ok(app.home, path(*path_), 'right home directory')

with subtest('Config override'):
    t = Pyjo.Test.Pyjo.new('PyjoymentTest')
    ok(not t.app.config().get('config_override'), 'no override')
    ok(not t.app.config().get('foo'), 'no value')
    t = Pyjo.Test.Pyjo.new('PyjoymentTest', {'foo': 'bar'})
    ok(t.app.config().get('config_override'), 'override')
    is_ok(t.app.config()['foo'], 'bar', 'right value')
    t = Pyjo.Test.Pyjo.new(PyjoymentTest.new(), {'foo': 'baz'})
    ok(t.app.config().get('config_override'), 'override')
    is_ok(t.app.config()['foo'], 'baz', 'right value')

    app = Pyjoyment.new()
    t = Pyjo.Test.Pyjo.new(app)
    ok(not t.app.config().get('config_override'), 'no override')
    ok(not t.app.config().get('foo'), 'no value')
    t = Pyjo.Test.Pyjo.new(app, {'foo': 'bar'})
    ok(t.app.config().get('config_override'), 'override')
    is_ok(t.app.config()['foo'], 'bar', 'right value')

t = Pyjo.Test.Pyjo.new('PyjoymentTest')

with subtest('Preload namespaces'):
    is_deeply_ok(t.app.preload_namespaces, ['PyjoymentTest.Controller'], 'right namespaces')
    ok('PyjoymentTest.Controller.Foo.Bar' in sys.modules, 'preloaded controller')

# Application is already available
is_ok(t.app.routes.find('something').to_str(), '/test4/:something', 'right pattern')
is_ok(t.app.routes.find('test3').pattern.defaults['namespace'], 'PyjoymentTest2.Foo', 'right namespace')
is_ok(t.app.routes.find('withblock').pattern.defaults['controller'], 'foo', 'right controller')
is_ok(type(t.app.routes.find('something')), Pyjoyment.Routes.Route.object, 'right class')
is_ok(type(t.app.routes.find('something').root), Pyjoyment.Routes.object, 'right class')
is_ok(t.app.sessions.cookie_domain, '.example.com', 'right domain')
is_ok(t.app.sessions.cookie_path, '/bar', 'right path')
is_deeply_ok(
    t.app.commands.namespaces,
    ['Pyjoyment.Command.Author', 'Pyjoyment.Command', 'PyjoymentTest.Command'],
    'right namespaces',
)
is_ok(t.app, t.app.commands.app, 'applications are equal')
is_ok(t.app.static.file('hello.txt').slurp(), b'Hello Mojo from a development static file!\n', 'right content')
is_ok(t.app.static.file('does_not_exist.html'), None, 'no file')
is_ok(t.app.moniker, 'pyjoyment_test', 'right moniker')
is_ok(t.app.secrets[0], t.app.moniker, 'secret defaults to moniker')
is_ok(t.app.renderer.template_handler({'template': 'foo/bar/index', 'format': 'html'}), 'epl', 'right handler')
is_ok(str(t.app.build_controller().req.url), '', 'no URL')
is_ok(t.app.build_controller().render_to_string('does_not_exist'), None, 'no result')
is_ok(t.app.build_controller().render_to_string(inline='%= c', c='foo'), 'foo\n', 'right result')

# Missing methods and functions (AUTOLOAD)
throws_ok(
    lambda: t.app.missing,
    re.compile(r'^Can\'t locate object method "missing" via package "PyjoymentTest\.PyjoymentTest"'),
    'right error',
)
# Unlike Mojolicious: the message of Python for a function that a module does not have
throws_ok(
    lambda: Pyjoyment.missing(),  # pyright: ignore[reportAttributeAccessIssue]
    re.compile(r"^module 'Pyjoyment' has no attribute 'missing'"),
    'right error',
)
c = t.app.build_controller()
throws_ok(
    lambda: c.missing,
    re.compile(rf'^Can\'t locate object method "missing" via package "{type(c).__module__}\.{type(c).__qualname__}"'),
    'right error',
)
throws_ok(
    lambda: Pyjoyment.Controller.missing(),  # pyright: ignore[reportAttributeAccessIssue]
    re.compile(r"^module 'Pyjoyment\.Controller' has no attribute 'missing'"),
    'right error',
)
throws_ok(
    lambda: t.app.routes.missing,
    re.compile(r'^Can\'t locate object method "missing" via package "Pyjoyment\.Routes\.Pyjoyment_Routes"'),
    'right error',
)
throws_ok(
    lambda: Pyjoyment.Routes.Route.missing(),  # pyright: ignore[reportAttributeAccessIssue]
    re.compile(r"^module 'Pyjoyment\.Routes\.Route' has no attribute 'missing'"),
    'right error',
)

with subtest('Reserved stash value'):
    ok(not t.app.routes.is_reserved('foo'), 'not reserved')
    ok(t.app.routes.is_reserved('action'), 'is reserved')
    ok(t.app.routes.is_reserved('app'), 'is reserved')
    ok(t.app.routes.is_reserved('cb'), 'is reserved')
    ok(t.app.routes.is_reserved('controller'), 'is reserved')
    ok(t.app.routes.is_reserved('data'), 'is reserved')
    ok(t.app.routes.is_reserved('extends'), 'is reserved')
    ok(t.app.routes.is_reserved('format'), 'is reserved')
    ok(t.app.routes.is_reserved('handler'), 'is reserved')
    ok(t.app.routes.is_reserved('inline'), 'is reserved')
    ok(t.app.routes.is_reserved('json'), 'is reserved')
    ok(t.app.routes.is_reserved('layout'), 'is reserved')
    ok(t.app.routes.is_reserved('namespace'), 'is reserved')
    ok(t.app.routes.is_reserved('path'), 'is reserved')
    ok(t.app.routes.is_reserved('status'), 'is reserved')
    ok(t.app.routes.is_reserved('template'), 'is reserved')
    ok(t.app.routes.is_reserved('text'), 'is reserved')
    ok(t.app.routes.is_reserved('variant'), 'is reserved')

    # Not in Mojolicious: YAML and TOML
    ok(t.app.routes.is_reserved('yaml'), 'is reserved')
    ok(t.app.routes.is_reserved('toml'), 'is reserved')

    # Not in Mojolicious: the timeouts of a route and its heartbeat
    ok(t.app.routes.is_reserved('inactivity_timeout'), 'is reserved')
    ok(t.app.routes.is_reserved('request_timeout'), 'is reserved')
    ok(t.app.routes.is_reserved('heartbeat'), 'is reserved')

with subtest('Reserved stash value (in placeholder)'):
    throws_ok(
        lambda: t.app.routes.any('/:controller'),
        re.compile(r'Route pattern "/:controller" contains a reserved stash value'),
        'right error',
    )
    throws_ok(
        lambda: t.app.routes.any('/:action'),
        re.compile(r'Route pattern "/:action" contains a reserved stash value'),
        'right error',
    )
    throws_ok(
        lambda: t.app.routes.any('/foo/:text'),
        re.compile(r'Route pattern "/foo/:text" contains a reserved stash value'),
        'right error',
    )
    throws_ok(
        lambda: t.app.routes.any('/foo/<text:num>'),
        re.compile(r'Route pattern "/foo/<text:num>" contains a reserved stash value'),
        'right error',
    )

# Unknown hooks
ok(not t.app.plugins.emit_chain('does_not_exist'), 'hook has been emitted')
ok(t.app.plugins.emit_hook('does_not_exist'), 'hook has been emitted')
ok(t.app.plugins.emit_hook_reverse('does_not_exist'), 'hook has been emitted')

# Custom hooks
custom = 0


@t.app.hook('custom_hook')
def custom_hook(value):
    global custom
    custom += value


t.app.plugins.emit_hook('custom_hook', 1)
is_ok(custom, 1, 'hook has been emitted')
t.app.plugins.emit_hook_reverse('custom_hook', 2)
is_ok(custom, 3, 'hook has been emitted again')
t.app.hook('custom_chain', lambda next, *args: next() * 2)
t.app.hook('custom_chain', lambda next, *args: args[-1])
is_ok(t.app.plugins.emit_chain('custom_chain', 4), 8, 'hook has been emitted')

# PyjoymentTest.Command.test_command (with abbreviation)
# Left out from Mojolicious: the option "--to" for "--too", as Pyjo.GetOpt does not abbreviate the names of the
# options, which the configuration "default" of Getopt::Long does

# Plugin.Test.SomePlugin2.register (security violation)
(
    t.get_ok('/plugin-test-some_plugin2/register')
    .status_isnt(404)
    .status_is(500)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_unlike(r'Something')
    .content_like(r'Class "PyjoymentTest\.Plugin\.Test\.SomePlugin2" is not a controller')
)

# Plugin.Test.SomePlugin2.register (security violation again)
with t.app.log.capture('trace') as logs:
    (
        t.get_ok('/plugin-test-some_plugin2/register')
        .status_isnt(404)
        .status_is(500)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_unlike(r'Something')
        .content_like(r'Class "PyjoymentTest\.Plugin\.Test\.SomePlugin2" is not a controller')
    )
like_ok(str(logs), r'Class "PyjoymentTest\.Plugin\.Test\.SomePlugin2" is not a controller', 'right message')
del logs

# Foo.fun (with a lot of different tests)
url = t.ua.server.url()
url.path = '/fun/time'
(
    t.get_ok(url, {'X-Test': 'Hi there!'})
    .status_isnt(404)
    .status_is(200)
    .status_is(200, 'with description')
    .status_isnt(500)
    .status_isnt(500, 'with description')
    .header_is('X-Bender', None)
    .header_is('Server', 'Pyjoyment (Python)')
    .header_is('Server', 'Pyjoyment (Python)', 'with description')
    .header_isnt('Server', 'Whatever')
    .header_isnt('Server', 'Whatever', 'with description')
    .header_like('Server', r'Pyjoyment')
    .header_like('Server', r'Pyjoyment', 'with description')
    .header_unlike('Server', r'Bender')
    .header_unlike('Server', r'Bender', 'with description')
    .content_type_is('text/html;charset=UTF-8')
    .content_type_is('text/html;charset=UTF-8', 'with description')
    .content_type_isnt('text/plain')
    .content_type_isnt('text/plain', 'with description')
    .content_type_like(r'html')
    .content_type_like(r'html', 'with description')
    .content_type_unlike(r'plain')
    .content_type_unlike(r'plain', 'with description')
    .content_isnt('Have')
    .content_isnt('Have', 'with description')
    .content_is('<p>Have fun!</p>')
    .content_is('<p>Have fun!</p>', 'with description')
    .content_like(r'fun')
    .content_like(r'fun', 'with description')
    .content_unlike(r'boring')
    .content_unlike(r'boring', 'with description')
    .element_exists('p')
    .element_exists('p', 'with description')
    .element_exists_not('b')
    .element_exists_not('b', 'with description')
    .text_is('p', 'Have fun!')
    .text_is('p', 'Have fun!', 'with description')
    .text_is('notfound', None)
    .text_isnt('p', 'Have')
    .text_isnt('p', 'Have', 'with description')
    .text_like('p', r'fun')
    .text_like('p', r'fun', 'with description')
    .text_unlike('p', r'boring')
    .text_unlike('p', r'boring', 'with description')
)

# Foo.joy (testing HTML attributes in template)
(
    t.get_ok('/fun/joy')
    .status_is(200)
    .attr_is('p.joy', 'style', 'background-color: darkred;')
    .attr_is('p.joy', 'style', 'background-color: darkred;', 'with description')
    .attr_is('p.joy', 'data-foo', '0')
    .attr_is('p.joy', 'data-empty', '')
    .attr_is('notfound', 'style', None)
    .attr_isnt('p.joy', 'style', 'float: left;')
    .attr_isnt('p.joy', 'style', 'float: left;', 'with description')
    .attr_like('p.joy', 'style', r'color')
    .attr_like('p.joy', 'style', r'color', 'with description')
    .attr_unlike('p.joy', 'style', r'^float')
    .attr_unlike('p.joy', 'style', r'^float', 'with description')
)

# Foo.baz (missing action without template)
with t.app.log.capture('trace') as logs:
    (
        t.get_ok('/foo/baz')
        .status_is(500)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_unlike(r'Something')
        .content_like(r'Route without action and nothing to render')
    )
like_ok(str(logs), r'Action not found in controller', 'right message')
del logs

# Foo.yada (action-less template)
(t.get_ok('/foo/yada').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_like(r'look ma! no action!'))

# Not in Mojolicious: the module with a syntax error in a temporary directory, as the linters check the files of tt/lib,
# which is a part of the package PyjoymentTest
syntax_error = Pyjo.File.tempdir()
syntax_error.child('SyntaxError.py').spew(
    b'import Pyjoyment.Controller\n\n\nclass SyntaxError(Pyjoyment.Controller.object):\n    def foo(self):\n        (\n'
)
PyjoymentTest.__path__.append(syntax_error.to_str())

# SyntaxError.foo (syntax error in controller)
# Unlike Mojolicious: the message of Python for the syntax error, where Perl has "Missing right curly"
(
    t.get_ok('/syntax_error/foo')
    .status_is(500)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'was never closed')
)

# Foo.syntaxerror (syntax error in template)
with t.app.log.capture('trace') as logs:
    (
        t.get_ok('/foo/syntaxerror')
        .status_is(500)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_like(r'was never closed')
    )
like_ok(str(logs), r'Rendering template "syntaxerror.html.epl"', 'right message')
like_ok(str(logs), r'was never closed', 'right message')
like_ok(str(logs), r'Template "exception.development.html.ep" not found', 'right message')
like_ok(str(logs), r'Rendering template "exception.html.epl"', 'right message')
like_ok(str(logs), r'500 Internal Server Error', 'right message')
del logs

# Unlike Mojolicious: the exceptions end with one newline, as the template exception.html.epl renders the first line of
# the exception, where the message of Mojo ends with the newline that it has, and the template adds another one

# Exceptional.this_one_dies (action dies)
(t.get_ok('/exceptional/this_one_dies').status_is(500).header_is('Server', 'Pyjoyment (Python)').content_is('doh!\n'))

# Exceptional.this_one_might_die (bridge dies)
(
    t.get_ok('/exceptional_too/this_one_dies')
    .status_is(500)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('double doh!\n')
)

# Exceptional.this_one_dies (action behind bridge dies)
(
    t.get_ok('/exceptional_too/this_one_dies', {'X-DoNotDie': 1})
    .status_is(500)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('doh!\n')
)

# Exceptional.this_one_does_not_exist (action does not exist)
(
    t.get_ok('/exceptional/this_one_does_not_exist')
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Exceptional.this_one_does_not_exist (action behind bridge does not exist)
(
    t.get_ok('/exceptional_too/this_one_does_not_exist', {'X-DoNotDie': 1})
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Foo.fun
(
    t.get_ok('/fun/time', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('X-Bender', None)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('<p>Have fun!</p>')
)

# Foo.fun
url = t.ua.server.url()
with t.app.log.capture('trace') as logs:
    url.path = '/fun/time'
    (
        t.get_ok(url, {'X-Test': 'Hi there!'})
        .status_is(200)
        .header_is('X-Bender', None)
        .header_is('Server', 'Pyjoyment (Python)')
        .content_is('<p>Have fun!</p>')
    )
like_ok(str(logs), r'Rendering cached template "foo/fun\.html\.ep" from DATA section', 'right message')
del logs

# Foo.fun
(
    t.get_ok('/happy/fun/time', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('X-Bender', None)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('<p>Have fun!</p>')
)

# Foo.test
(
    t.get_ok('/foo/test', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('X-Bender', 'Bite my shiny metal ass!')
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'/bar/test')
)

# Foo.index
(
    t.get_ok('/foo', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'<body>\s+23\nHello Mojo from the template /foo! He')
)

# Foo.Bar.index
(
    t.get_ok('/foo-bar', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Hello Mojo from the other template /foo-bar!')
)

# Foo.something
(
    t.put_ok('/somethingtest', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('/test4/42')
)
(
    t.post_ok('/somethingtest?_method=PUT', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('/test4/42')
)
(
    t.get_ok('/somethingtest?_method=PUT', {'X-Test': 'Hi there!'})
    .status_is(500)
    .content_like(r'Controller "PyjoymentTest\.Somethingtest" does not exist')
)

# Foo.url_for_missing
(
    t.get_ok('/something_missing', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('does_not_exist')
)

# Foo.templateless
(
    t.get_ok('/foo/templateless', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Hello Mojo from a templateless renderer!')
)

# Foo.withlayout
(
    t.get_ok('/foo/withlayout', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Same old in green Seems to work!')
)

# Foo.withBlock
(
    t.get_ok('/withblock.txt', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_type_isnt('text/html')
    .content_type_is('text/plain;charset=UTF-8')
    .content_like(r'Hello Baerbel\.\s+Hello Wolfgang\.')
)

# PyjoymentTest2.Foo.test
(
    t.get_ok('/test2', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('X-Bender', 'Bite my shiny metal ass!')
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'/test2')
)

# PyjoymentTestController.index
(
    t.get_ok('/test3', {'X-Test': 'Hi there!'})
    .status_is(500)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Namespace "PyjoymentTest2\.Foo" requires a controller')
)

# PyjoymentTest.Foo.Bar (no action)
(
    t.get_ok('/test1', {'X-Test': 'Hi there!'})
    .status_is(500)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(
        r'Controller "PyjoymentTest\.Controller\.Foo\.Bar\.PyjoymentTest_Controller_Foo_Bar" requires an action'
    )
)

# PyjoymentTestController.index (no namespace)
(
    t.get_ok('/test6', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('X-Bender', 'Bite my shiny metal ass!')
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('/test6')
)

# PyjoymentTest.Foo.Bar.test (controller class shortcut)
(
    t.get_ok('/test7', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('Class works!\n')
)

# PyjoymentTest.Foo.Bar.test (controller class)
(
    t.get_ok('/test8', {'X-Test': 'Hi there!'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('Class works!\n')
)

# PyjoymentTest3.Bar.index (controller class in development namespace)
(t.get_ok('/test9').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Development namespace works!'))

# PyjoymentTest3.Baz.index (controller class precedence)
(
    t.get_ok('/test10')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('Development namespace has high precedence!')
)

# 404
(
    t.get_ok('/', {'X-Test': 'Hi there!'})
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Static file /another/file (no extension)
(
    t.get_ok('/another/file')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_type_is('application/octet-stream')
    .content_like(r'Hello Mojolicious!')
)

# Static directory /another
with t.app.log.capture('trace') as logs:
    t.get_ok('/another').status_is(500).header_is('Server', 'Pyjoyment (Python)')
like_ok(str(logs), r'Controller "PyjoymentTest\.Another" does not exist', 'right message')
del logs

# Check Last-Modified header for static files
path_ = curfile().sibling('public_dev', 'hello.txt')
size = Pyjo.Asset.File.new(path=path_.to_str()).size
mtime = Pyjo.Date.new(Pyjo.Asset.File.new(path=path_.to_str()).mtime).to_str()

# Static file /hello.txt
(
    t.get_ok('/hello.txt')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .header_is('Last-Modified', mtime)
    .header_like('ETag', r'^"\w+"$')
    .header_is('Content-Length', str(size))
    .content_type_is('text/plain;charset=UTF-8')
    .content_like(r'Hello Mojo from a development static file!')
)

# Renamed from Mojolicious: Pyjoyment, the directory of this test, where Mojo has mojolicious

# Try to access a file which is not under the web root via path traversal
(
    t.get_ok('/../../Pyjoyment/secret.txt')
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Try to access a file which is not under the web root via path traversal (goes
# back and forth one directory)
(
    t.get_ok('/another/../../../Pyjoyment/secret.txt')
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Try to access a file which is not under the web root via path traversal
# (triple dot)
(
    t.get_ok('/.../Pyjoyment/secret.txt')
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Try to access a file which is not under the web root via path traversal
# (backslashes)
(
    t.get_ok('/..\\..\\Pyjoyment\\secret.txt')
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Try to access a file which is not under the web root via path traversal
# (escaped backslashes)
(
    t.get_ok('/..%5C..%5CPyjoyment%5Csecret.txt')
    .status_is(404)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Page Not Found')
)

# Check that backslashes in query or fragment parts don't block access
t.get_ok('/another/file?one=\\1#two=\\2').status_is(200).content_like(r'Hello Mojolicious!')

# Check If-Modified-Since
(
    t.get_ok('/hello.txt', {'If-Modified-Since': mtime})
    .status_is(304)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('')
)

# Check If-None-Match
etag = t.tx.res.headers.etag
(
    t.get_ok('/hello.txt', {'If-None-Match': etag})
    .status_is(304)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('')
)

# Check weak If-None-Match against strong ETag
(
    t.get_ok('/hello.txt', {'If-None-Match': f'W/"{etag}"'})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Hello Mojo from a development static file!')
)

# Check If-None-Match and If-Last-Modified
(
    t.get_ok('/hello.txt', {'If-None-Match': etag, 'If-Last-Modified': mtime})
    .status_is(304)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('')
)

# Bad If-None-Match with correct If-Modified-Since
(
    t.get_ok('/hello.txt', {'If-None-Match': '"123"', 'If-Modified-Since': mtime})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Hello Mojo from a development static file!')
)

# Bad If-Modified-Since with correct If-None-Match
(
    t.get_ok('/hello.txt', {'If-Modified-Since': Pyjo.Date.new(23), 'If-None-Match': etag})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Hello Mojo from a development static file!')
)

# Embedded development static file
(
    t.get_ok('/some/static/file.txt')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('Development static file with high precedence.\n')
)

# Embedded development template
(
    t.get_ok('/just/some/template')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('Development template with high precedence.\n')
)

with local(PYJO_LOG_LEVEL=None):
    # Check default development mode log level
    is_ok(Pyjoyment.new().log.level, 'trace', 'right log level')

    # Check non-development mode log level
    is_ok(Pyjoyment.new().set(mode='test').log.level, 'info', 'right log level')

# Make sure we can override attributes with constructor arguments
is_ok(PyjoymentTest.new(mode='test').mode, 'test', 'right mode')
is_ok(PyjoymentTest.new({'mode': 'test'}).mode, 'test', 'right mode')

# Persistent error
app = PyjoymentTest.new()
tx = t.ua.build_tx('GET', '/foo')
app.handler(tx)
is_ok(tx.res.code, 200, 'right status')
like_ok(tx.res.text, r'Hello Mojo from the template /foo! Hello World!', 'right content')
tx = t.ua.build_tx('GET', '/foo/willdie')
app.handler(tx)
is_ok(tx.res.code, 500, 'right status')
# Renamed from Mojolicious: Foo.py, the module of the controller, where Mojo has Foo.pm
like_ok(tx.res.text, r'Foo\.py', 'right content')
tx = t.ua.build_tx('GET', '/foo')
app.handler(tx)
is_ok(tx.res.code, 200, 'right status')
like_ok(tx.res.text, r'Hello Mojo from the template /foo! Hello World!', 'right content')

t = Pyjo.Test.Pyjo.new('SingleFileTestApp')

# SingleFileTestApp.Foo.index
(
    t.get_ok('/foo')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_like(r'Same old in green Seems to work!')
)

# SingleFileTestApp (helper)
t.get_ok('/helper').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Welcome aboard!')

# PluginWithEmbeddedApp (lite app in plugin)
t.get_ok('/plugin/foo').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('plugin works!')

# SingleFileTestApp.Foo.conf (config file)
t.get_ok('/foo/conf').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('works!')

# SingleFileTestApp.Foo.data_template
t.get_ok('/foo/data_template').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('23 works!\n')

# SingleFileTestApp.Foo.data_template
(
    t.get_ok('/foo/data_template2')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('This one works too!\n')
)

# SingleFileTestApp.Foo.data_static
(
    t.get_ok('/foo/data_static')
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('And this one... ALL GLORY TO THE HYPNOTOAD!\n')
)

# SingleFileTestApp.Foo.routes
(
    t.get_ok('/foo/routes')
    .status_is(200)
    .header_is('X-Bender', 'Bite my shiny metal ass!')
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('/foo/routes')
)

# SingleFileTestApp.Redispatch.handler
t.app.log.level = 'trace'
t.app.log.unsubscribe('message')
with t.app.log.capture() as logs:
    t.get_ok('/redispatch').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Redispatch!')
like_ok(str(logs), r'Routing to application "SingleFileTestApp\.Redispatch"', 'right message')
del logs

# SingleFileTestApp.Redispatch.render
t.get_ok('/redispatch/render').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Render!')

# SingleFileTestApp.Redispatch.handler (targeting an existing method)
t.get_ok('/redispatch/secret').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Redispatch!')

# SingleFileTestApp.Redispatch.secret
(t.get_ok('/redispatch/secret?rly=1').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Secret!'))

with subtest('Override deployment plugins'):
    t = Pyjo.Test.Pyjo.new(
        'SingleFileTestApp',
        {'plugins': [{'PyjoymentTest.Plugin.DeploymentPlugin': {'name': 'override_helper'}}]},
    )
    is_ok(t.app.override_helper(), 'deployment plugins work!', 'right value')

t = Pyjo.Test.Pyjo.new('PyjoymentTest')

# PyjoymentTestController.Foo.plugin_upper_case
(t.get_ok('/plugin/upper_case').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('WELCOME aboard!'))

# PyjoymentTestController.Foo.plugin_camel_case
(t.get_ok('/plugin/camel_case').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Welcome aboard!'))

# PyjoymentTestController.Foo.stage2
(
    t.get_ok('/staged', {'X-Pass': 1})
    .status_is(200)
    .header_is('Server', 'Pyjoyment (Python)')
    .content_is('Welcome aboard!')
)

# PyjoymentTestController.Foo.stage1
t.get_ok('/staged').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Go away!')

# PyjoymentTestController.Foo.suspended
with t.app.log.capture('trace') as logs:
    (
        t.get_ok('/suspended')
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_is('X-Suspended', '0, 1, 1, 2')
        .content_is('<p>Have fun!</p>')
    )
like_ok(str(logs), r'GET "/suspended"', 'right message')
like_ok(
    str(logs), r'Routing to controller "PyjoymentTest\.Foo\.PyjoymentTest_Foo" and action "suspended"', 'right message'
)
like_ok(str(logs), r'Routing to controller "PyjoymentTest\.Foo\.PyjoymentTest_Foo" and action "fun"', 'right message')
like_ok(str(logs), r'Rendering template "foo/fun.html.ep" from DATA section', 'right message')
like_ok(str(logs), r'200 OK', 'right message')
del logs

# PyjoymentTest.Foo.longpoll
stash = None


@t.app.plugins.once('before_dispatch')
def before_dispatch(c):
    global stash
    stash = c.stash()


t.get_ok('/longpoll').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('Poll!')
while not stash.get('finished'):
    Pyjo.IOLoop.one_tick()
is_ok(stash['finished'], 1, 'finish event has been emitted once')
# Not in Mojolicious: the garbage collector, as PyPy frees the controller only when it runs
gc.collect()
ok(stash.get('destroyed'), 'controller has been destroyed')

# PyjoymentTest.Foo.config
t.get_ok('/stash_config').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('123')

# Shortcuts to controller#action
t.get_ok('/shortcut/ctrl-act').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('ctrl-act')
t.get_ok('/shortcut/ctrl').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('ctrl')
t.get_ok('/shortcut/act').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('act')

# Session with domain
(
    t.get_ok('/foo/session')
    .status_is(200)
    .header_like('Set-Cookie', r'; domain=\.example\.com')
    .header_like('Set-Cookie', r'; path=/bar')
    .content_is('Bender rockzzz!')
)

# Mixed formats
(
    t.get_ok('/rss.xml')
    .status_is(200)
    .content_type_is('application/rss+xml')
    .content_like(r'<\?xml version="1.0" encoding="UTF-8"\?><rss />')
)

# Missing controller has no side effects
t.get_ok('/side_effects-test/index').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('pass')
t.get_ok('/side_effects/index').status_is(404).header_is('Server', 'Pyjoyment (Python)')
t.get_ok('/side_effects/index').status_is(404).header_is('Server', 'Pyjoyment (Python)')
t.get_ok('/side_effects-test/index').status_is(200).header_is('Server', 'Pyjoyment (Python)').content_is('pass')

# Transaction already destroyed
throws_ok(lambda: Pyjoyment.Controller.new().finish(), re.compile(r'Transaction already destroyed'), 'right error')
throws_ok(
    lambda: Pyjoyment.Controller.new().on('finish', lambda c: None),
    re.compile(r'Transaction already destroyed'),
    'right error',
)
throws_ok(lambda: Pyjoyment.Controller.new().req, re.compile(r'Transaction already destroyed'), 'right error')
throws_ok(lambda: Pyjoyment.Controller.new().res, re.compile(r'Transaction already destroyed'), 'right error')
throws_ok(
    lambda: Pyjoyment.Controller.new().send('whatever'), re.compile(r'Transaction already destroyed'), 'right error'
)

# Abstract methods
throws_ok(
    lambda: Pyjoyment.Plugin.object.register(Pyjoyment.Plugin.new(), Pyjoyment.new(), {}),
    re.compile(r'Method "register" not implemented by subclass'),
    'right error',
)

with subtest('Route shortcuts'):
    app_ = Pyjoyment.new()
    for method in ('delete', 'get', 'options', 'patch', 'post', 'put', 'query'):
        route = getattr(app_, method)('/shortcut', lambda c, method=method: c.render(text=method))
        isa_ok(route, Pyjoyment.Routes.Route.object, 'right class')
        is_deeply_ok(route.methods(), [method.upper()], 'right methods')
    app_.any(['PUT'], '/any', lambda c: c.render(text='any'))

    def under(c):
        if c.req.headers.header('X-Pass'):
            return True
        c.render(text='denied', status=403)
        return None

    app_.under('/under', under).get('/inner', lambda c: c.render(text='inner'))

    @app_.websocket('/ws')
    def ws(c):
        c.on('message', lambda c, msg: c.send(f'echo: {msg}'))

    t = Pyjo.Test.Pyjo.new(app_)
    for method in ('delete', 'get', 'options', 'patch', 'post', 'put', 'query'):
        getattr(t, f'{method}_ok')('/shortcut').status_is(200).content_is(method)
    t.put_ok('/any').status_is(200).content_is('any')
    t.get_ok('/any').status_is(404)
    t.get_ok('/under/inner', {'X-Pass': 1}).status_is(200).content_is('inner')
    t.get_ok('/under/inner').status_is(403).content_is('denied')
    t.websocket_ok('/ws').send_ok('hi').message_ok().message_is('echo: hi').finish_ok()


done_testing()
