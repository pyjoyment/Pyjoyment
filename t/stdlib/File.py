import Pyjo.File

from Pyjo.File import path, tempdir
from Pyjo.Test import *

import os
import pathlib
import shutil
import tempfile
import warnings

from unittest.mock import patch


# The temporary objects of the standard library that Pyjo.File keeps warn when they are removed with it, as tempdir()
# and tempfile() do not
warnings.filterwarnings('ignore', message='Implicitly cleaning up', category=ResourceWarning)

with subtest('An os.PathLike'):
    dir = tempdir()
    file = dir.child('test.txt')
    isa_ok(file, os.PathLike, 'file')
    is_ok(os.fspath(file), file.to_str(), 'os.fspath()')
    with open(file, 'w') as f:
        f.write('works')
    ok(os.path.isfile(file), 'os.path')
    is_ok(file.slurp(), b'works', 'written with open()')
    shutil.copy(file, dir.child('copy.txt'))
    is_ok(dir.child('copy.txt').slurp(), b'works', 'shutil')
    is_deeply_ok(sorted(os.listdir(dir)), ['copy.txt', 'test.txt'], 'os.listdir()')

with subtest('pathlib'):
    p = pathlib.Path('/home/sri/.vimrc')
    file = Pyjo.File.new(p)
    is_ok(file, str(p), 'from pathlib.Path')
    is_ok(pathlib.Path(file), p, 'pathlib.Path() of it')
    is_ok(file.to_path(), p, 'to_path()')
    isa_ok(file.to_path(), pathlib.Path, 'to_path()')
    is_ok(path(p.parent, p.name), file, 'parts from pathlib')

with subtest('Kept as given'):
    is_ok(path('foo/bar/'), 'foo/bar/', 'unlike pathlib.Path')
    is_ok(str(pathlib.Path('foo/bar/')), os.path.join('foo', 'bar'), 'pathlib.Path normalizes')

with subtest('Temporary files of the standard library'):
    tmp = tempfile.TemporaryDirectory()
    dir = path(tmp)
    is_ok(dir, tmp.name, 'TemporaryDirectory')
    del tmp
    ok(os.path.isdir(dir), 'kept with the object')
    named = tempfile.NamedTemporaryFile()
    file = path(named)
    is_ok(file, named.name, 'NamedTemporaryFile')
    file = tempdir().child('test.txt').spew('works')
    is_ok(file.slurp(), b'works', 'a child keeps the temporary directory')

with subtest('Context manager'):
    with tempdir() as dir:
        file = dir.child('test.txt').spew('works')
        ok(os.path.isfile(file), 'temporary directory')
    ok(not os.path.exists(dir), 'removed at the end of the block')
    ok(not os.path.exists(file), 'with its files, which a child keeps no longer')
    with Pyjo.File.tempfile() as file:
        ok(os.path.isfile(file), 'temporary file')
    ok(not os.path.exists(file), 'removed at the end of the block')
    with path(tempfile.TemporaryDirectory()) as dir:
        ok(os.path.isdir(dir), 'TemporaryDirectory')
    ok(not os.path.exists(dir), 'cleaned up at the end of the block')
    with warnings.catch_warnings(record=True) as warned:
        warnings.simplefilter('always')
        with path(tempfile.NamedTemporaryFile()) as file:
            ok(os.path.isfile(file), 'NamedTemporaryFile')
    ok(not os.path.exists(file), 'closed at the end of the block')
    is_ok(len(warned), 0, 'without a ResourceWarning')
    with path('/home/sri/.vimrc') as file:
        is_ok(file, '/home/sri/.vimrc', 'a path without a temporary file')
    is_ok(file, '/home/sri/.vimrc', 'kept')

with subtest('stat'):
    file = tempdir().child('test.txt').spew('1234')
    isa_ok(file.stat(), os.stat_result, 'os.stat_result')
    is_ok(file.stat(), os.stat(file), 'as os.stat() gives it')

with subtest('The paths of Windows on any system'):
    # The rules of File::Spec::Win32 and of File::Basename for MSWin32, as Perl gives them
    with patch.object(Pyjo.File, '_WIN32', True):
        is_ok(path('a/b', 'c').to_str(), 'a\\b\\c', 'catfile')
        is_ok(path('C:', 'a').to_str(), 'C:\\a', 'catfile of a drive')
        is_ok(
            path('C:\\Users\\x\\t\\Pyjo\\x.py').sibling('..', 'lib').to_str(),
            'C:\\Users\\x\\t\\lib',
            'sibling of a parent',
        )
        is_ok(path('C:\\a\\b.txt').dirname().to_str(), 'C:\\a', 'dirname')
        is_ok(path('C:\\a').dirname().to_str(), 'C:\\', 'dirname of the root of a drive')
        is_ok(path('C:\\a\\b.txt').basename('.txt'), 'b', 'basename')
        is_ok(path('C:\\a\\').basename(), 'a', 'basename with a trailing separator')
        is_deeply_ok(path('C:\\a/b').to_list(), ['C:', 'a', 'b'], 'both separators')
        is_deeply_ok(path('\\\\host\\share\\a').to_list(), ['', '', 'host', 'share', 'a'], 'UNC path')
        ok(path('\\a').is_abs, 'from the root')
        ok(not path('C:a').is_abs, 'drive without the root')
        ok(path('C:/a').is_abs, 'drive with the root')
        is_ok(path('C:/a/./b/../c/').to_abs().to_str(), 'C:\\a\\c', 'canonpath')

with subtest('Bytes as they are'):
    dir = tempdir()
    data = b'a\nb\r\nc\x1ad'
    file = dir.child('spew.bin').spew(data)
    with open(file, 'rb') as f:
        is_ok(f.read(), data, 'spew() writes them, without the CRLF of the text mode of Windows')
    with open(dir.child('slurp.bin'), 'wb') as f:
        f.write(data)
    is_ok(dir.child('slurp.bin').slurp(), data, 'slurp() reads them, past the Ctrl-Z of the text mode of Windows')

with subtest('exists, is_file and is_dir, as os.path has them'):
    dir = tempdir()
    file = dir.child('file.txt').spew('')
    missing = dir.child('missing')
    is_deeply_ok([dir.exists, dir.is_file, dir.is_dir], [True, False, True], 'directory')
    is_deeply_ok([file.exists, file.is_file, file.is_dir], [True, True, False], 'file')
    is_deeply_ok([missing.exists, missing.is_file, missing.is_dir], [False, False, False], 'missing')
    is_deeply_ok(
        dir.list(dir=True).map('is_dir').to_list(), [False], 'a property, which a method name of a collection takes'
    )

    with subtest('Symbolic links'):
        try:
            os.symlink(file, dir.child('link'))
            os.symlink(missing, dir.child('broken'))
        except (AttributeError, NotImplementedError, OSError):
            plan(skip_all='symlink unimplemented')
        link, broken = dir.child('link'), dir.child('broken')
        is_deeply_ok([link.exists, link.is_file, link.is_dir], [True, True, False], 'followed')
        is_deeply_ok([broken.exists, broken.is_file, broken.is_dir], [False, False, False], 'broken')

    with subtest('Without the permission'):
        if os.name == 'nt' or os.geteuid() == 0:
            plan(skip_all='the permissions of a directory do not keep out Windows or root')
        locked = dir.child('locked').make_path()
        inside = locked.child('inside.txt').spew('')
        locked.chmod(0)
        try:
            is_deeply_ok([inside.exists, inside.is_file, inside.is_dir], [False, False, False], 'cannot be checked')
        finally:
            locked.chmod(0o700)

with subtest('expanduser, as os.path has it'):
    home = tempdir()
    with patch.dict(os.environ, {'HOME': home.to_str(), 'USERPROFILE': home.to_str()}):
        expanded = path('~', '.aws', 'config').expanduser()
        isa_ok(expanded, Pyjo.File.object, 'a new object')
        is_ok(expanded.to_str(), os.path.join(home, '.aws', 'config'), 'home directory of ~')
        is_ok(path('~').expanduser().to_str(), home.to_str(), 'only ~')
        is_ok(path('a', '~').expanduser().to_str(), path('a', '~').to_str(), 'not at the beginning')
        is_ok(path('/tmp/a').expanduser().to_str(), '/tmp/a', 'as it is without ~')
    if os.name != 'nt':
        name = '~no-such-user-of-pyjoyment/a'
        is_ok(path(name).expanduser().to_str(), name, 'as it is for an unknown user')

done_testing()
