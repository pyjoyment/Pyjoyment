import Pyjo.File

from Pyjo.File import curfile, path, tempdir, tempfile
from Pyjo.Test import *
from Pyjo.Util import decode, encode

import gc
import os
import re
import stat
import sys
import tempfile as _tempfile
import time
import warnings


# The temporary objects of the standard library that Pyjo.File keeps warn when they are removed with it, as tempdir()
# and tempfile() do not
warnings.filterwarnings('ignore', message='Implicitly cleaning up', category=ResourceWarning)


# Perl's File::Basename and File::Spec, which Mojo's tests compare with
def basename(path, suffix=''):
    name = os.path.basename(path.rstrip('/'))
    return name[: -len(suffix)] if suffix and name.endswith(suffix) and name != suffix else name


def catfile(*parts):
    return os.path.normpath(os.path.join(*parts))


with subtest('Constructor'):
    is_ok(Pyjo.File.new(), os.getcwd(), 'same path')
    is_ok(path(), os.getcwd(), 'same path')
    is_ok(path().to_str(), os.getcwd(), 'same path')
    is_ok(path('/foo/bar'), '/foo/bar', 'same path')
    is_ok(path('foo', 'bar', 'baz'), catfile('foo', 'bar', 'baz'), 'same path')

with subtest('Tap into method chain'):
    # Unlike Mojolicious: the path cannot be changed in place, as a str cannot
    is_ok(path('/home').tap(lambda p: p.child('sri')).to_str(), '/home', 'same path')

with subtest('Children'):
    is_ok(path('foo', 'bar').child('baz', 'yada'), catfile(catfile('foo', 'bar'), 'baz', 'yada'), 'same path')

with subtest('Siblings'):
    is_ok(
        path('foo', 'bar').sibling('baz', 'yada'),
        catfile(os.path.dirname(catfile('foo', 'bar')), 'baz', 'yada'),
        'same path',
    )

with subtest('Array'):
    is_deeply_ok(path('foo', 'bar').to_list(), catfile('foo', 'bar').split(os.sep), 'same structure')
    is_deeply_ok(list(path('foo', 'bar')), catfile('foo', 'bar').split(os.sep), 'same structure')

with subtest('Absolute'):
    is_ok(path('file.t').to_abs(), os.path.abspath('file.t'), 'same path')

with subtest('Relative'):
    is_ok(
        path('test.txt').to_abs().to_rel(os.getcwd()),
        os.path.relpath(os.path.abspath('test.txt'), os.getcwd()),
        'same path',
    )

with subtest('Resolved'):
    is_ok(path('.').realpath(), os.path.realpath('.'), 'same path')

with subtest('basename'):
    is_ok(path('file.t').to_abs().basename(), basename(os.path.abspath('file.t')), 'same path')
    is_ok(path('file.t').to_abs().basename('.t'), basename(os.path.abspath('file.t'), '.t'), 'same path')
    is_ok(path('file.t').basename('.t'), basename('file.t', '.t'), 'same path')

with subtest('dirname'):
    is_ok(path('file.t').to_abs().dirname(), os.path.dirname(os.path.abspath('file.t')), 'same path')

with subtest('extname'):
    is_ok(path('.file.txt').extname, 'txt', 'right extension')
    is_ok(path('file.txt').extname, 'txt', 'right extension')
    is_ok(path('file').extname, '', 'no extension')
    is_ok(path('.file').extname, '', 'no extension')
    is_ok(path('home', 'foo', 'file.txt').extname, 'txt', 'right extension')
    is_ok(path('home', 'foo', 'file.txt.gz').extname, 'gz', 'right extension')
    is_ok(path('home', 'foo', '.file.txt.gz').extname, 'gz', 'right extension')
    is_ok(path('home', 'foo', 'file').extname, '', 'no extension')
    is_ok(path('home', 'foo', '.file').extname, '', 'no extension')

with subtest('Current file'):
    ok(curfile().is_abs, 'path is absolute')
    is_ok(curfile(), os.path.realpath(__file__), 'same path')

with subtest('Checks'):
    ok(path(__file__).to_abs().is_abs, 'path is absolute')
    ok(not path('file.t').is_abs, 'path is not absolute')

with subtest('Temporary directory'):
    dir = tempdir()
    p = str(dir)
    ok(os.path.isdir(p), 'directory exists')
    del dir
    # Not in Mojolicious: PyPy frees objects only when its garbage collector runs
    gc.collect()
    ok(not os.path.isdir(p), 'directory does not exist anymore')
    dir = tempdir('mytestXXXXX')
    ok(os.path.isdir(dir), 'directory exists')
    like_ok(dir.basename(), r'mytest.{5}$', 'right format')
    del dir
    gc.collect()

with subtest('Temporary directory (separate object)'):
    dir = Pyjo.File.new(_tempfile.TemporaryDirectory())
    p = str(dir)
    ok(os.path.isdir(p), 'directory exists')
    del dir
    gc.collect()
    ok(not os.path.isdir(p), 'directory does not exist anymore')

with subtest('Temporary file'):
    dir = tempdir()
    file = tempfile(dir=dir)
    p = str(file)
    ok(os.path.isfile(p), 'file exists')
    is_ok(file.dirname(), dir, 'same directory')
    is_ok(file.spew('test').slurp(), b'test', 'right result')
    is_ok(file.spurt('just', 'a', 'test', '123').slurp(), b'justatest123', 'right result')
    del file
    gc.collect()
    ok(not os.path.isfile(p), 'file does not exist anymore')

with subtest('Persistent temporary file'):
    if sys.platform == 'win32':
        plan(skip_all='cannot move open file')
    dir = tempdir()
    file = tempfile(dir=dir)
    file.spew('works')
    is_ok(file.slurp(), b'works', 'right content')
    file2 = tempfile(dir=dir)
    file.move_to(file2)
    ok(os.path.exists(file2), 'file exists')
    ok(not os.path.exists(file), 'file does not exist anymore')
    del file
    gc.collect()
    is_ok(file2.slurp(), b'works', 'right content')
    ok(os.path.exists(file2), 'file still exists')

with subtest('open'):
    file = tempfile()
    file.spew('test\n123\n')
    # Unlike Mojolicious: the modes are those of open() in Python, "rb" for "<"
    handle = file.open('rb')
    is_deeply_ok(handle.readlines(), [b'test\n', b'123\n'], 'right structure')
    handle.close()
    handle = file.open('r')
    is_deeply_ok(handle.readlines(), ['test\n', '123\n'], 'right structure')
    handle.close()
    # Left out from Mojolicious: the flags of os.open(), like O_RDONLY, as open()
    # does not take them
    file.spew(encode('UTF-8', '♥'))
    handle = file.open('r', encoding='UTF-8')
    is_deeply_ok(handle.readlines(), ['♥'], 'right structure')
    handle.close()
    dir = tempdir()
    throws_ok(lambda: dir.child('does_not_exist').open('r'), re.compile(r"^Can't open file"), 'right error')
    throws_ok(lambda: dir.child('does_not_exist').slurp(), re.compile(r"^Can't open file"), 'right error')
    throws_ok(lambda: dir.child('foo').make_path().spew('fail'), re.compile(r"^Can't open file"), 'right error')

with subtest('make_path'):
    dir = tempdir()
    subdir = dir.child('foo', 'bar')
    ok(not os.path.isdir(subdir), 'directory does not exist anymore')
    subdir.make_path()
    ok(os.path.isdir(subdir), 'directory exists')
    # Left out from Mojolicious: the error option of File::Path, as
    # os.makedirs() raises its errors
    nextdir = dir.child('foo', 'foobar').make_path()
    ok(os.path.isdir(nextdir), 'directory exists')

with subtest('remove'):
    dir = tempdir()
    dir.child('test.txt').spew('test!')
    ok(os.path.exists(dir.child('test.txt')), 'file exists')
    is_ok(dir.child('test.txt').slurp(), b'test!', 'right content')
    ok(not os.path.exists(dir.child('test.txt').remove().touch().remove().remove()), 'file no longer exists')
    throws_ok(lambda: dir.child('foo').make_path().remove(), re.compile(r"^Can't remove file"), 'right error')

with subtest('remove_tree'):
    dir = tempdir()
    dir.child('foo', 'bar').make_path().child('test.txt').spew('test!')
    is_ok(dir.child('foo', 'bar', 'test.txt').slurp(), b'test!', 'right content')
    subdir = dir.child('foo', 'foobar').make_path()
    ok(os.path.exists(subdir.child('bar').make_path().child('test.txt').spew('test')), 'file created')
    ok(os.path.isdir(subdir.remove_tree(keep_root=True)), 'directory still exists')
    ok(not os.path.exists(subdir.child('bar')), 'children have been removed')
    ok(not os.path.exists(dir.child('foo').remove_tree().to_str()), 'directory has been removed')

with subtest('move_to'):
    dir = tempdir()
    destination = dir.child('dest.txt')
    source = dir.child('src.txt').spew('works!')
    ok(os.path.isfile(source), 'file exists')
    ok(not os.path.isfile(destination), 'file does not exists')
    is_ok(source.move_to(destination).to_str(), destination, 'same path')
    ok(not os.path.isfile(source), 'file no longer exists')
    ok(os.path.isfile(destination), 'file exists')
    is_ok(destination.slurp(), b'works!', 'right content')
    subdir = dir.child('test').make_path()
    destination2 = destination.move_to(subdir)
    is_ok(destination2, subdir.child(destination.basename()), 'same path')
    ok(not os.path.isfile(destination), 'file no longer exists')
    ok(os.path.isfile(destination2), 'file exists')
    is_ok(destination2.slurp(), b'works!', 'right content')

with subtest('copy_to'):
    dir = tempdir()
    destination = dir.child('dest.txt')
    source = dir.child('src.txt').spew('works!')
    ok(os.path.isfile(source), 'file exists')
    ok(not os.path.isfile(destination), 'file does not exists')
    is_ok(source.copy_to(destination).to_str(), destination, 'same path')
    ok(os.path.isfile(source), 'file still exists')
    ok(os.path.isfile(destination), 'file also exists now')
    is_ok(source.slurp(), b'works!', 'right content')
    is_ok(destination.slurp(), b'works!', 'right content')
    subdir = dir.child('test').make_path()
    destination2 = destination.copy_to(subdir)
    is_ok(destination2, subdir.child(destination.basename()), 'same path')
    ok(os.path.isfile(destination), 'file still exists')
    ok(os.path.isfile(destination2), 'file also exists now')
    is_ok(destination.slurp(), b'works!', 'right content')
    is_ok(destination2.slurp(), b'works!', 'right content')

with subtest('Change permissions'):
    dir = tempdir()
    throws_ok(lambda: dir.child('does_not_exist').chmod(0o644), re.compile(r"^Can't chmod file"), 'right error')

with subtest('stat'):
    dir = tempdir()
    is_ok(dir.child('test.txt').spew('1234').stat().st_size, 4, 'right size')

with subtest('lstat'):
    dir = tempdir()
    orig = dir.child('test.txt').spew('')
    link = orig.sibling('test.link')
    try:
        os.symlink(orig, link)
    except (AttributeError, NotImplementedError, OSError):
        plan(skip_all='symlink unimplemented')
    is_ok(link.stat().st_size, 0, 'target file is empty')
    # Unlike Mojolicious: a symbolic link of Windows, a reparse point of NTFS, has the size 0, where the one of POSIX has
    # the length of its target, so lstat is known there by the link it sees
    if sys.platform == 'win32':
        ok(stat.S_ISLNK(link.lstat().st_mode), 'link is not empty')
    else:
        isnt_ok(link.lstat().st_size, 0, 'link is not empty')

with subtest('list/list_tree'):
    is_deeply_ok(path('does_not_exist').list().to_list(), [], 'no files')
    is_deeply_ok(curfile().list().to_list(), [], 'no files')
    # Unlike Mojolicious: the files that Mojo has in t/mojo/lib/Mojo are made in
    # a temporary directory, as Pyjoyment's tests have no such files
    fixtures = tempdir()
    lib = fixtures.child('Mojo')
    for name in (
        '.hidden.txt',
        '.test/hidden.txt',
        'BaseTest/Base1.pm',
        'BaseTest/Base2.pm',
        'BaseTest/Base3.pm',
        'DeprecationTest.pm',
        'LoaderException.pm',
        'LoaderException2.pm',
        'LoaderTest/A.pm',
        'LoaderTest/B.pm',
        'LoaderTest/C.pm',
        'LoaderTest/D.txt',
        'LoaderTest/E/F.pm',
        'LoaderTest/E/G.txt',
        'LoaderTestException/A.pm',
        'Server/Morbo/Backend/TestBackend.pm',
        'TestConnectProxy.pm',
    ):
        lib.child(*name.split('/')).dirname().make_path().child(lib.child(*name.split('/')).basename()).spew('')
    files = [
        path(lib).child(*n.split('/'))
        for n in ('DeprecationTest.pm', 'LoaderException.pm', 'LoaderException2.pm', 'TestConnectProxy.pm')
    ]
    is_deeply_ok(path(lib).list().map('to_str').to_list(), files, 'right files')
    files.insert(0, lib.child('.hidden.txt').to_str())
    is_deeply_ok(path(lib).list(hidden=True).map('to_str').to_list(), files, 'right files')
    files = [
        path(lib).child(*n.split('/'))
        for n in (
            'BaseTest',
            'DeprecationTest.pm',
            'LoaderException.pm',
            'LoaderException2.pm',
            'LoaderTest',
            'LoaderTestException',
            'Server',
            'TestConnectProxy.pm',
        )
    ]
    is_deeply_ok(path(lib).list(dir=True).map('to_str').to_list(), files, 'right files')
    hidden = [path(lib).child(*n.split('/')) for n in ('.hidden.txt', '.test')]
    is_deeply_ok(path(lib).list(dir=True, hidden=True).map('to_str').to_list(), [*hidden, *files], 'right files')

    is_deeply_ok(path('does_not_exist').list_tree().to_list(), [], 'no files')
    is_deeply_ok(curfile().list_tree().to_list(), [], 'no files')
    files = [
        path(lib).child(*n.split('/'))
        for n in (
            'BaseTest/Base1.pm',
            'BaseTest/Base2.pm',
            'BaseTest/Base3.pm',
            'DeprecationTest.pm',
            'LoaderException.pm',
            'LoaderException2.pm',
            'LoaderTest/A.pm',
            'LoaderTest/B.pm',
            'LoaderTest/C.pm',
            'LoaderTest/D.txt',
            'LoaderTest/E/F.pm',
            'LoaderTest/E/G.txt',
            'LoaderTestException/A.pm',
            'Server/Morbo/Backend/TestBackend.pm',
            'TestConnectProxy.pm',
        )
    ]
    is_deeply_ok(path(lib).list_tree().map('to_str').to_list(), files, 'right files')
    hidden = [path(lib).child(*n.split('/')) for n in ('.hidden.txt', '.test/hidden.txt')]
    is_deeply_ok(path(lib).list_tree(hidden=True).map('to_str').to_list(), [*hidden, *files], 'right files')
    all = [
        path(lib).child(*n.split('/'))
        for n in (
            '.hidden.txt',
            '.test',
            '.test/hidden.txt',
            'BaseTest',
            'BaseTest/Base1.pm',
            'BaseTest/Base2.pm',
            'BaseTest/Base3.pm',
            'DeprecationTest.pm',
            'LoaderException.pm',
            'LoaderException2.pm',
            'LoaderTest',
            'LoaderTest/A.pm',
            'LoaderTest/B.pm',
            'LoaderTest/C.pm',
            'LoaderTest/D.txt',
            'LoaderTest/E',
            'LoaderTest/E/F.pm',
            'LoaderTest/E/G.txt',
            'LoaderTestException',
            'LoaderTestException/A.pm',
            'Server',
            'Server/Morbo',
            'Server/Morbo/Backend',
            'Server/Morbo/Backend/TestBackend.pm',
            'TestConnectProxy.pm',
        )
    ]
    is_deeply_ok(path(lib).list_tree(dir=True, hidden=True).map('to_str').to_list(), all, 'right files')
    one = [
        path(lib).child(*n.split('/'))
        for n in ('DeprecationTest.pm', 'LoaderException.pm', 'LoaderException2.pm', 'TestConnectProxy.pm')
    ]
    is_deeply_ok(path(lib).list_tree(max_depth=1).map('to_str').to_list(), one, 'right files')
    one_dir = [
        path(lib).child(*n.split('/'))
        for n in (
            'BaseTest',
            'DeprecationTest.pm',
            'LoaderException.pm',
            'LoaderException2.pm',
            'LoaderTest',
            'LoaderTestException',
            'Server',
            'TestConnectProxy.pm',
        )
    ]
    is_deeply_ok(path(lib).list_tree(dir=True, max_depth=1).map('to_str').to_list(), one_dir, 'right files')
    two = [
        path(lib).child(*n.split('/'))
        for n in (
            'BaseTest/Base1.pm',
            'BaseTest/Base2.pm',
            'BaseTest/Base3.pm',
            'DeprecationTest.pm',
            'LoaderException.pm',
            'LoaderException2.pm',
            'LoaderTest/A.pm',
            'LoaderTest/B.pm',
            'LoaderTest/C.pm',
            'LoaderTest/D.txt',
            'LoaderTestException/A.pm',
            'TestConnectProxy.pm',
        )
    ]
    is_deeply_ok(path(lib).list_tree(max_depth=2).map('to_str').to_list(), two, 'right files')
    three = [
        path(lib).child(*n.split('/'))
        for n in (
            '.hidden.txt',
            '.test',
            '.test/hidden.txt',
            'BaseTest',
            'BaseTest/Base1.pm',
            'BaseTest/Base2.pm',
            'BaseTest/Base3.pm',
            'DeprecationTest.pm',
            'LoaderException.pm',
            'LoaderException2.pm',
            'LoaderTest',
            'LoaderTest/A.pm',
            'LoaderTest/B.pm',
            'LoaderTest/C.pm',
            'LoaderTest/D.txt',
            'LoaderTest/E',
            'LoaderTest/E/F.pm',
            'LoaderTest/E/G.txt',
            'LoaderTestException',
            'LoaderTestException/A.pm',
            'Server',
            'Server/Morbo',
            'Server/Morbo/Backend',
            'TestConnectProxy.pm',
        )
    ]
    is_deeply_ok(path(lib).list_tree(dir=True, hidden=True, max_depth=3).map('to_str').to_list(), three, 'right files')

with subtest('list_tree with symlinks'):
    dir = tempdir()
    real = dir.child('real').make_path()
    inside = real.child('deep.txt').spew('')
    link = dir.child('link')
    try:
        os.symlink(real, link)
    except (AttributeError, NotImplementedError, OSError):
        plan(skip_all='symlink unimplemented')
    top = dir.child('top.txt').spew('')
    is_deeply_ok(dir.list_tree().map('to_str').to_list(), sorted([inside.to_str(), top.to_str()]), 'right files')
    is_deeply_ok(
        dir.list_tree(dir=True).map('to_str').to_list(),
        sorted([inside.to_str(), link.to_str(), real.to_str(), top.to_str()]),
        'right files',
    )

    loop = dir.child('loop')
    os.symlink(dir, loop)
    is_deeply_ok(
        dir.list_tree(dir=True).map('to_str').to_list(),
        sorted([inside.to_str(), link.to_str(), loop.to_str(), real.to_str(), top.to_str()]),
        'right files',
    )

with subtest('touch'):
    dir = tempdir()
    file = dir.child('test.txt')
    ok(not os.path.exists(file), 'file does not exist')
    ok(os.path.exists(file.touch()), 'file exists')
    is_ok(file.spew('test!').slurp(), b'test!', 'right content')
    is_ok(file.touch().slurp(), b'test!', 'right content')
    future = int(time.time()) + 1000
    os.utime(file.to_str(), (future, future))
    is_ok(file.stat().st_mtime, future, 'right mtime')
    isnt_ok(file.touch().stat().st_mtime, future, 'different mtime')

with subtest('Dangerous paths'):
    throws_ok(lambda: path('foo', None, 'bar'), re.compile(r'Invalid path'), 'right error')
    throws_ok(lambda: path(None), re.compile(r'Invalid path'), 'right error')

with subtest('I/O'):
    dir = tempdir()
    file = dir.child('test.txt').spew('just works!')
    is_ok(file.slurp(), b'just works!', 'right content')
    write = os.write
    os.write = lambda fd, data: 5
    try:
        throws_ok(lambda: file.spew('just\nworks!'), re.compile(r"Can't write to file \".*"), 'right error')
    finally:
        os.write = write

with subtest('I/O with encoding'):
    dir = tempdir()
    file = dir.child('test.txt').spew('♥1', 'UTF-8')
    is_ok(file.slurp('UTF-8'), '♥1', 'right content')
    is_ok(decode('UTF-8', file.slurp()), '♥1', 'right content')
    is_ok(file.spew('works too!').slurp(), b'works too!', 'right content')

    with subtest('I/O with manual encoding'):
        file.spew(encode('UTF-8', '♥1'))
        is_ok(file.slurp('UTF-8'), '♥1', 'right content')
        is_ok(decode('UTF-8', file.slurp()), '♥1', 'right content')

    # Unlike Mojolicious: characters without an encoding are written as UTF-8,
    # where Perl dies of a "Wide character"
    is_ok(file.spew('♥1').slurp('UTF-8'), '♥1', 'right content')

# Unlike Mojolicious: the byte order mark of a whole file switches UTF-8 to its encoding, as Windows PowerShell writes
# UTF-16LE with one, where Mojo decodes it as U+FEFF
with subtest('I/O with byte order mark'):
    dir = tempdir()
    file = dir.child('bom.txt')
    for data, name in (
        (b'\xef\xbb\xbf' + '♥1\r\n'.encode(), 'UTF-8'),
        (b'\xff\xfe' + '♥1\r\n'.encode('UTF-16LE'), 'UTF-16LE'),
        (b'\xfe\xff' + '♥1\r\n'.encode('UTF-16BE'), 'UTF-16BE'),
        (b'\xff\xfe\x00\x00' + '♥1\r\n'.encode('UTF-32LE'), 'UTF-32LE'),
        (b'\x00\x00\xfe\xff' + '♥1\r\n'.encode('UTF-32BE'), 'UTF-32BE'),
    ):
        is_ok(file.spew(data).slurp('UTF-8'), '♥1\r\n', name)
        is_ok(file.slurp('utf8'), '♥1\r\n', f'{name} for another name of UTF-8')
        is_ok(file.slurp(), data, f'{name} as bytes')
    is_ok(file.spew(b'\xef\xbb\xbf').slurp('UTF-8'), '', 'only a byte order mark')
    is_ok(file.spew(b'\xff\xfe\x00').slurp('UTF-8'), None, 'odd UTF-16')
    is_ok(file.spew(b'\xff\xfeab').slurp('latin-1'), '\xff\xfeab', 'another encoding stays')
    is_ok(file.spew(b'a\xef\xbb\xbfb').slurp('UTF-8'), 'a\ufeffb', 'byte order mark after the start')
    is_ok(file.spew(b'\xef\xbb\xbf\xef\xbb\xbfa').slurp('UTF-8'), '\ufeffa', 'one byte order mark only')

done_testing()
