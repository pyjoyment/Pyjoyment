from Pyjo.Test import *

import contextlib
import io
import os
import pathlib
import sys
import tempfile
import warnings


# The temporary objects of the standard library that Pyjo.File keeps warn when they are removed with it, as tempdir()
# and tempfile() do not
warnings.filterwarnings('ignore', message='Implicitly cleaning up', category=ResourceWarning)

tmp = tempfile.TemporaryDirectory()
home = pathlib.Path(tmp.name, 'home', 'sri')


# A path as Pyjo.File makes it on Windows, with the separators and the parents of File::Spec::Win32, and as it is
# elsewhere, where the examples of the documentation are
def native(p):
    return os.path.normpath(p) if sys.platform == 'win32' else p


home.mkdir(parents=True)
(home / '.vimrc').write_text('set nocompatible\n', newline='\n')
(home / '.bashrc').write_text('export EDITOR=vim\n', newline='\n')
(home / 'test').write_text('test\n', newline='\n')

with subtest('Synopsis'):
    from Pyjo.File import File

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Portably deal with file system paths
        path = File(str(home / '.vimrc'))
        print(path.slurp())
        print(path.dirname())
        print(path.basename())
        print(path.extname)
        print(path.sibling('.bashrc'))
    is_ok(
        output.getvalue(),
        f"b'set nocompatible\\n'\n{home}\n.vimrc\n\n{home / '.bashrc'}\n",
        'output',
    )

    # Or import the module, as in Google Python Style Guide

    import Pyjo.File

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Portably deal with file system paths
        path = Pyjo.File.new(str(home / '.vimrc'))
        print(path.slurp())
        print(path.dirname())
        print(path.basename())
        print(path.extname)
        print(path.sibling('.bashrc'))
    is_ok(
        output.getvalue(),
        f"b'set nocompatible\\n'\n{home}\n.vimrc\n\n{home / '.bashrc'}\n",
        'output',
    )

    # Use the alternative constructor
    from Pyjo.File import path

    p = path(tmp.name, 'foo', 'bar').make_path()
    p.child('test.txt').spew('Hello Pyjo!')
    is_ok(p.child('test.txt').slurp(), b'Hello Pyjo!', 'spew')

with subtest('Description'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Use the path with the standard library
        p = Pyjo.File.new(str(home / 'test'))
        with open(p) as f:
            print(f.read())
    is_ok(output.getvalue(), 'test\n\n', 'output')

with subtest('new'):
    p = Pyjo.File.new()
    is_ok(p, os.getcwd(), 'current working directory')
    p = Pyjo.File.new('/home/sri/.vimrc')
    is_ok(p, '/home/sri/.vimrc', 'path')
    p = Pyjo.File.new('/home', 'sri', '.vimrc')
    is_ok(p, native('/home/sri/.vimrc'), 'parts')
    p = Pyjo.File.new(pathlib.Path('/home/sri/.vimrc'))
    is_ok(p, native('/home/sri/.vimrc'), 'pathlib.Path')
    p = Pyjo.File.new(tempfile.NamedTemporaryFile())
    ok(os.path.isfile(p), 'temporary file')
    p = Pyjo.File.new(tempfile.TemporaryDirectory())
    ok(os.path.isdir(p), 'temporary directory')

    # "foo/bar/baz.txt" (on UNIX)
    is_ok(Pyjo.File.new('foo', 'bar', 'baz.txt'), native('foo/bar/baz.txt'), 'parts')

with subtest('__bool__'):
    boolean = bool(path(''))
    ok(boolean, 'always true')

with subtest('__fspath__'):
    string = os.fspath(path('/home/sri'))
    is_ok(string, '/home/sri', 'string')

with subtest('__getitem__'):
    part = path('/home/sri')[0]
    is_ok(part, '', 'part')

with subtest('__iter__'):
    parts = []
    for part in path('/home/sri'):
        parts.append(part)
    is_deeply_ok(parts, ['', 'home', 'sri'], 'parts')

with subtest('__len__'):
    size = len(path('/home/sri'))
    is_ok(size, 3, 'size')

with subtest('basename'):
    # ".vimrc" (on UNIX)
    is_ok(path('/home/sri/.vimrc').basename(), '.vimrc', 'basename')

    # "test" (on UNIX)
    is_ok(path('/home/sri/test.txt').basename('.txt'), 'test', 'basename with suffix')

with subtest('child'):
    # "/home/sri/.vimrc" (on UNIX)
    is_ok(path('/home').child('sri', '.vimrc'), native('/home/sri/.vimrc'), 'child')

with subtest('chmod'):
    p = path(str(home / 'test'))
    p = p.chmod(0o644)
    # Windows keeps the bit of read-only of a mode only
    if sys.platform == 'win32':
        skip('no mode of files on Windows', 1)
    else:
        is_ok(p.stat().st_mode & 0o777, 0o644, 'mode')

with subtest('copy_to'):
    p = path(str(home / '.vimrc'))
    destination = p.copy_to(str(home / '..'))
    is_ok(destination, native(str(home / '..' / '.vimrc')), 'directory')
    destination = p.copy_to(str(home / '.vimrc.backup'))
    is_ok(destination, str(home / '.vimrc.backup'), 'file')

with subtest('dirname'):
    # "/home/sri" (on UNIX)
    is_ok(path('/home/sri/.vimrc').dirname(), '/home/sri', 'dirname')

with subtest('download'):
    import Pyjo.IOLoop
    import Pyjo.Server.Daemon
    import Pyjo.UserAgent
    import Pyjoyment

    # The URL of a daemon with an application in place of https://example.com
    app = Pyjoyment.new()
    app.log.level = 'fatal'

    @app.routes.get('/test.tar.gz')
    def tarball(c):
        c.res.headers.accept_ranges = 'bytes'
        c.render(data=(c.req.headers.accept or 'none').encode())

    daemon = Pyjo.Server.Daemon.new(app=app, listen=['http://127.0.0.1'], silent=True).start()
    url = f'http://127.0.0.1:{daemon.ports()[0]}/test.tar.gz'

    def download():
        file = Pyjo.File.tempdir().child('test.tar.gz')
        # Not in the docstring: a blocking user agent on the event loop of the daemon
        ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
        boolean = file.download(url, headers={'Accept': '*/*'}, ua=ua)
        return boolean, file.slurp()

    is_deeply_ok(download(), (True, b'*/*'), 'boolean')
    file = Pyjo.File.tempdir().child('test.tar.gz')
    boolean = file.download(url, ua=Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton))
    ok(boolean, 'boolean')
    daemon.stop()

with subtest('extname'):
    # "js"
    is_ok(path('/home/sri/test.js').extname, 'js', 'extname')

with subtest('is_abs'):
    # True (on UNIX)
    ok(path('/home/sri/.vimrc').is_abs, 'absolute')

    # False (on UNIX)
    ok(not path('.vimrc').is_abs, 'relative')

with subtest('list'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # List files
        for file in path(str(home)).list().each():
            print(file)
    is_ok(output.getvalue(), f'{home / "test"}\n', 'output')

with subtest('list_tree'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # List all templates
        for file in path(tmp.name, 'home').list_tree().each():
            print(file)
    is_ok(output.getvalue(), f'{home / "test"}\n', 'output')

with subtest('lstat'):
    link = home / 'link'
    link.symlink_to(home / 'test')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Get symlink size
        print(path(str(link)).lstat().st_size)

        # Get symlink modification time
        print(path(str(link)).lstat().st_mtime)
    # A symbolic link of Windows, a reparse point of NTFS, has the size 0, where the one of POSIX has the length of
    # its target
    if sys.platform == 'win32':
        skip('no size of a symbolic link on Windows', 1)
    else:
        is_ok(output.getvalue().split('\n')[0], str(len(str(home / 'test'))), 'size')

with subtest('make_path'):
    p = path(tmp.name, 'a', 'b')
    p = p.make_path()
    p = p.make_path(mode=0o711)
    ok(os.path.isdir(p), 'directory')

with subtest('move_to'):
    p = path(str(home / '.vimrc.backup'))
    destination = p.move_to(str(home / '..'))
    is_ok(destination, native(str(home / '..' / '.vimrc.backup')), 'directory')
    destination = destination.move_to(str(home / '.vimrc.backup'))
    is_ok(destination, str(home / '.vimrc.backup'), 'file')

with subtest('open'):
    p = path(str(home / 'test'))
    handle = p.open('r+')
    handle.close()
    handle = p.open('rb')
    is_ok(handle.read(), b'test\n', 'bytes')
    handle.close()
    handle = p.open('r', encoding='UTF-8')
    is_ok(handle.read(), 'test\n', 'characters')
    handle.close()

with subtest('realpath'):
    realpath = path(str(home / 'link')).realpath()
    is_ok(realpath, os.path.realpath(home / 'test'), 'realpath')

with subtest('remove'):
    p = path(str(home / '.vimrc.backup'))
    p = p.remove()
    ok(not os.path.exists(p), 'removed')

with subtest('remove_tree'):
    p = path(tmp.name, 'a')
    p = p.remove_tree(keep_root=True)
    ok(os.path.isdir(p), 'kept')
    p = p.remove_tree()
    ok(not os.path.exists(p), 'removed')

with subtest('sibling'):
    # "/home/sri/.vimrc" (on UNIX)
    is_ok(path('/home/sri/.bashrc').sibling('.vimrc'), native('/home/sri/.vimrc'), 'sibling')

    # "/home/sri/.ssh/known_hosts" (on UNIX)
    is_ok(path('/home/sri/.bashrc').sibling('.ssh', 'known_hosts'), native('/home/sri/.ssh/known_hosts'), 'sibling')

with subtest('slurp'):
    p = path(str(home / 'test'))
    data = p.slurp()
    is_ok(data, b'test\n', 'bytes')
    chars = p.slurp('UTF-8')
    is_ok(chars, 'test\n', 'characters')

    # "♥" of a file of b'\xff\xfee&'
    p = path(tmp.name, 'bom.txt').spew(b'\xff\xfee&')
    is_ok(p.slurp('UTF-8'), '♥', 'byte order mark')

with subtest('spew'):
    p = path(tmp.name, 'spew.txt')
    p = p.spew(b'data')
    is_ok(p.slurp(), b'data', 'bytes')
    p = p.spew('♥', 'UTF-8')
    is_ok(p.slurp('UTF-8'), '♥', 'characters')

    # b'\xef\xbb\xbf\xe2\x99\xa5'
    is_ok(p.spew('♥', 'UTF-8-SIG').slurp(), b'\xef\xbb\xbf\xe2\x99\xa5', 'UTF-8 with a byte order mark')
    is_ok(p.slurp('UTF-8'), '♥', 'read back')

    # b'\xff\xfee&'
    is_ok(p.spew('\ufeff♥', 'UTF-16LE').slurp(), b'\xff\xfee&', 'UTF-16LE with a byte order mark')
    is_ok(p.slurp('UTF-8'), '♥', 'read back')
    is_ok(p.spew('♥', 'UTF-16').slurp('UTF-8'), '♥', 'UTF-16 in the byte order of the machine, read back')

with subtest('spurt'):
    p = p.spurt(b'da', b'ta')
    is_ok(p.slurp(), b'data', 'chunks')

with subtest('stat'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Get file size
        print(path(str(home / '.bashrc')).stat().st_size)

        # Get file modification time
        print(path(str(home / '.bashrc')).stat().st_mtime)
    is_ok(output.getvalue().split('\n')[0], '18', 'size')

with subtest('to_abs'):
    absolute = path('test.txt').to_abs()
    is_ok(absolute, os.path.join(os.getcwd(), 'test.txt'), 'absolute')

with subtest('to_list'):
    # "home:sri:.vimrc" (on UNIX)
    is_ok(':'.join(path('/home/sri/.vimrc').to_list()), ':home:sri:.vimrc', 'parts')

with subtest('to_path'):
    p = path('/home/sri/.vimrc').to_path()
    is_ok(p, pathlib.Path('/home/sri/.vimrc'), 'pathlib.Path')

with subtest('to_rel'):
    # "sri/.vimrc" (on UNIX)
    is_ok(path('/home/sri/.vimrc').to_rel('/home'), native('sri/.vimrc'), 'to_rel')

with subtest('to_str'):
    string = path('/home/sri').to_str()
    is_ok(string, '/home/sri', 'string')

with subtest('touch'):
    p = path(str(home / '.bashrc'))
    p = p.touch()
    ok(os.path.exists(p), 'exists')

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Safely read file
        print(p.touch().slurp())
    is_ok(output.getvalue(), "b'export EDITOR=vim\\n'\n", 'output')

with subtest('curfile'):
    p = Pyjo.File.curfile()
    is_ok(p, os.path.realpath(__file__), 'current file')

with subtest('path'):
    p = path()
    is_ok(p, os.getcwd(), 'current working directory')
    p = path('/home/sri/.vimrc')
    is_ok(p, '/home/sri/.vimrc', 'path')
    p = path('/home', 'sri', '.vimrc')
    is_ok(p, native('/home/sri/.vimrc'), 'parts')
    p = path(tempfile.TemporaryDirectory())
    ok(os.path.isdir(p), 'temporary directory')

    # "foo/bar/baz.txt" (on UNIX)
    is_ok(path('foo', 'bar', 'baz.txt'), native('foo/bar/baz.txt'), 'parts')

with subtest('tempdir'):
    p = Pyjo.File.tempdir()
    ok(os.path.isdir(p), 'temporary directory')
    p = Pyjo.File.tempdir('tempXXXXX', dir=tmp.name)
    like_ok(p.basename(), r'^temp.{5}$', 'template')

    # Longer version
    p = path(tempfile.TemporaryDirectory())
    ok(os.path.isdir(p), 'temporary directory')

with subtest('tempfile'):
    p = Pyjo.File.tempfile()
    ok(os.path.isfile(p), 'temporary file')
    p = Pyjo.File.tempfile(dir=tmp.name)
    is_ok(p.dirname(), os.path.realpath(tmp.name) if p.dirname() != tmp.name else tmp.name, 'directory')

    # Longer version
    # Not in the docstring: a with block, which closes the temporary file that the path keeps where it ends
    with path(tempfile.NamedTemporaryFile(dir=tmp.name)) as p:
        ok(os.path.isfile(p), 'temporary file')
    ok(not os.path.exists(p), 'closed')

tmp.cleanup()

done_testing()
