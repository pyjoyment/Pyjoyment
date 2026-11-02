import Pyjoyment
import Pyjoyment.Command

from Pyjo.File import path, tempdir
from Pyjo.Test import *

import contextlib
import io
import os
import re


# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor of Pyjo.Reactor.detect()

with subtest('Application'):
    command = Pyjoyment.Command.new()
    isa_ok(command.app, Pyjoyment.object, 'right application')

with subtest('Creating directories'):
    command = Pyjoyment.Command.new()
    cwd = path()
    dir = tempdir()
    os.chdir(dir)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.create_rel_dir('foo/bar')
    like_ok(buffer.getvalue(), r'[mkdir]', 'right output')
    ok(os.path.isdir(path('foo', 'bar').to_str()), 'directory exists')

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.create_rel_dir('foo/bar')
    like_ok(buffer.getvalue(), r'\[exist\]', 'right output')
    os.chdir(cwd)

with subtest('Generating files'):
    command = Pyjoyment.Command.new()
    cwd = path()
    dir = tempdir()
    is_ok(command.rel_file('foo/bar.txt').basename(), 'bar.txt', 'right result')

    template = """\
@@ foo_bar
% word = args[0]
just <%= word %>!
@@ dies
% raise Exception('template error')
@@ bar_baz
just <%= word %> too!
"""
    # Unlike Mojolicious: the DATA section of the module is its variable __DATA__, which the test sets, as Mojo sets the
    # handle DATA of the package
    Pyjoyment.Command.__DATA__ = template
    os.chdir(dir)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.set(template={}).render_to_rel_file('foo_bar', 'bar/baz.txt', 'works')
    like_ok(buffer.getvalue(), r'(?s)\[mkdir\].*\[write\]', 'right output')
    is_ok(command.rel_file('bar/baz.txt').slurp().decode(), 'just works!\n', 'right result')

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.set(template={'vars': True}).render_to_rel_file('bar_baz', 'bar/two.txt', {'word': 'works'})
    like_ok(buffer.getvalue(), r'(?s)\[exist\].*\[write\]', 'right output')
    is_ok(command.rel_file('bar/two.txt').slurp().decode(), 'just works too!\n', 'right result')

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.chmod_rel_file('bar/baz.txt', 0o700)
    like_ok(buffer.getvalue(), r'\[chmod\]', 'right output')
    ok(os.path.exists(command.rel_file('bar/baz.txt').to_str()), 'file is executable')

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.write_rel_file('123.xml', 'seems\nto\nwork')
    like_ok(buffer.getvalue(), r'(?s)\[exist\].*\[write\]', 'right output')

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.write_rel_file('123.xml', 'fail')
    like_ok(buffer.getvalue(), r'\[exist\]', 'right output')
    is_ok(command.rel_file('123.xml').slurp().decode(), 'seems\nto\nwork', 'right result')

    throws_ok(lambda: command.render_data('dies'), re.compile(r'template error'), 'right error')
    os.chdir(cwd)

with subtest('Quiet'):
    command = Pyjoyment.Command.new()
    cwd = path()
    dir = tempdir()
    os.chdir(dir)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.set(quiet=True).write_rel_file('123.xml', 'fail')
    is_ok(buffer.getvalue(), '', 'no output')
    os.chdir(cwd)

# Unlike Mojolicious: a message is flushed at once, as the standard output of a pipe is buffered in blocks
with subtest('Flushed'):

    class Output(io.StringIO):
        flushed = ''

        def flush(self):
            self.flushed = self.getvalue()
            super().flush()

    output = Output()
    with contextlib.redirect_stdout(output):
        Pyjoyment.Command.new()._loud('  [write] foo')
    is_ok(output.flushed, '  [write] foo\n', 'flushed with its line')

with subtest('Abstract methods'):
    throws_ok(
        lambda: Pyjoyment.Command.new().run(),
        re.compile(r'Method "run" not implemented by subclass'),
        'right error',
    )

done_testing()
