import Pyjo.File
import Pyjo.Server
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *

import os
import re
import sys


with subtest('Synopsis'):
    from Pyjo.App.CGI import CGI

    app = CGI(script='/usr/lib/cgi-bin/hello.cgi')
    is_ok(app.script, '/usr/lib/cgi-bin/hello.cgi', 'script')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.App.CGI

    app = Pyjo.App.CGI.new(script='/usr/lib/cgi-bin/hello.cgi')
    is_ok(app.script, '/usr/lib/cgi-bin/hello.cgi', 'script')

    # The programs of a directory, as cgi-bin
    app = Pyjo.App.CGI.new(document_root='/usr/lib/cgi-bin')
    is_ok(app.document_root, '/usr/lib/cgi-bin', 'directory')

    # PHP on php-cgi, with the files of its directory
    app = Pyjo.App.CGI.new(command=['php-cgi'], document_root='/var/www', script_extensions=['.php'], static=True)
    is_deeply_ok(app.command, ['php-cgi'], 'command')
    is_deeply_ok(app.script_extensions, ['.php'], 'extensions')
    is_ok(app.static, True, 'static files')

    # Mount it in an application of Pyjoyment
    import Pyjoyment

    pyjoyment = Pyjoyment.new()
    pyjoyment.log.level = 'fatal'

    # A program of the Python of the test, which answers the request of the example, where the event loop watches pipes
    if os.name == 'nt':
        skip('CGI applications need pipes that the event loop watches', 2)
    else:
        tmp = Pyjo.File.tempdir()
        hello = tmp.child('hello.cgi')
        hello.spew(f"#!{sys.executable}\nprint('Content-Type: text/plain\\n\\nHello CGI!', end='')\n".encode())
        os.chmod(hello.to_str(), 0o755)
        app = Pyjo.App.CGI.new(document_root=tmp.to_str())
        pyjoyment.plugin('Mount', {'/cgi-bin': app})
        Pyjo.Test.Pyjo.new(pyjoyment).get_ok('/cgi-bin/hello.cgi').status_is(200).content_is('Hello CGI!')

with subtest('command'):
    app = Pyjo.App.CGI.new()
    command = app.command
    is_ok(command, None, 'the script itself')
    app.command = ['php-cgi']
    is_deeply_ok(app.command, ['php-cgi'], 'command')

with subtest('document_root'):
    app = Pyjo.App.CGI.new()
    root = app.document_root
    is_ok(root, None, 'no directory')
    app.document_root = '/usr/lib/cgi-bin'
    is_ok(app.document_root, '/usr/lib/cgi-bin', 'directory')

with subtest('env'):
    app = Pyjo.App.CGI.new()
    env = app.env
    is_deeply_ok(env, {}, 'no variables')
    app.env = {'PERL5LIB': '/usr/local/lib/perl5'}
    is_deeply_ok(app.env, {'PERL5LIB': '/usr/local/lib/perl5'}, 'variables')

with subtest('inactivity_timeout'):
    app = Pyjo.App.CGI.new()
    timeout = app.inactivity_timeout
    is_ok(timeout, 60, 'default')
    app.inactivity_timeout = 300
    is_ok(app.inactivity_timeout, 300, 'timeout')

with subtest('nph'):
    app = Pyjo.App.CGI.new()
    boolean = app.nph
    is_ok(boolean, None, 'by the file name')
    app.nph = True
    is_ok(app.nph, True, 'non-parsed headers')

with subtest('public_source'):
    app = Pyjo.App.CGI.new()
    boolean = app.public_source
    is_ok(boolean, False, 'not on purpose')
    app.public_source = True
    is_ok(app.public_source, True, 'on purpose')

with subtest('script'):
    app = Pyjo.App.CGI.new()
    script = app.script
    is_ok(script, None, 'no script')
    app.script = '/usr/lib/cgi-bin/hello.cgi'
    is_ok(app.script, '/usr/lib/cgi-bin/hello.cgi', 'script')
    app.script = 'index.php'
    is_ok(app.script, 'index.php', 'script of the directory')

with subtest('script_extensions'):
    app = Pyjo.App.CGI.new()
    extensions = app.script_extensions
    is_ok(extensions, None, 'every file')
    app.script_extensions = ['.php']
    is_deeply_ok(app.script_extensions, ['.php'], 'extensions')

with subtest('sendfile'):
    import re

    app = Pyjo.App.CGI.new()
    places = app.sendfile
    is_ok(places, None, 'none')
    app.sendfile = '/var/www/private'
    is_ok(app.sendfile, '/var/www/private', 'directory')
    app.sendfile = ['/var/www/private', '/var/www/media']
    is_deeply_ok(app.sendfile, ['/var/www/private', '/var/www/media'], 'directories')
    app.sendfile = re.compile(r'/var/www/[^/]+/private/.*')
    ok(app.sendfile.fullmatch('/var/www/blog/private/file.pdf'), 'regular expression')

with subtest('static'):
    app = Pyjo.App.CGI.new()
    boolean = app.static
    is_ok(boolean, False, 'no static files')
    app.static = True
    is_ok(app.static, True, 'static files')

with subtest('server'):
    app = Pyjo.App.CGI.new(document_root='/usr/lib/cgi-bin')
    is_ok(app.server(Pyjo.Server.new()), None, 'no static files')
    public = Pyjo.File.tempdir()
    mounting = Pyjoyment.new()
    mounting.static.paths = [public.to_str()]
    app.document_root = public.to_str()
    throws_ok(lambda: app.server(Pyjo.Server.new(app=mounting)), re.compile(r'would serve their source'), 'in them')
    app.public_source = True
    is_ok(app.server(Pyjo.Server.new(app=mounting)), None, 'on purpose')

done_testing()
