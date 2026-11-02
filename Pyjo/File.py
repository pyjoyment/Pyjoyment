r"""
Pyjo.File - File system paths
=============================
::

    from Pyjo.File import File

    # Portably deal with file system paths
    path = File('/home/sri/.vimrc')
    print(path.slurp())
    print(path.dirname())
    print(path.basename())
    print(path.extname)
    print(path.sibling('.bashrc'))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.File

    # Portably deal with file system paths
    path = Pyjo.File.new('/home/sri/.vimrc')
    print(path.slurp())
    print(path.dirname())
    print(path.basename())
    print(path.extname)
    print(path.sibling('.bashrc'))

    # Use the alternative constructor
    from Pyjo.File import path
    path = path('/tmp/foo/bar').make_path()
    path.child('test.txt').spew('Hello Pyjo!')

:mod:`Pyjo.File` is a container for file system paths that provides a
friendly API for dealing with different operating systems. It keeps the path
as it is given, and it is an :class:`os.PathLike`, so the standard library
takes it where it takes a path. ::

    # Use the path with the standard library
    path = Pyjo.File.new('/home/sri/test')
    with open(path) as f:
        print(f.read())

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::File <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/File.pm>`_
of Mojolicious 9.49.

Functions
---------
"""

import Pyjo.Base
import Pyjo.Collection
import Pyjo.Exception
import Pyjo.String.Mixin

from Pyjo.Util import decode, encode

import builtins
import inspect
import os
import pathlib
import random
import re
import shutil
import string
import sys
import tempfile as _tempfile
import weakref

from collections.abc import Callable, Iterator
from types import TracebackType
from typing import IO, TYPE_CHECKING, Any, NoReturn, Self, cast


if TYPE_CHECKING:
    import Pyjo.Transaction.HTTP
    import Pyjo.UserAgent


_random = random.SystemRandom()

# File::Spec and File::Basename of Perl follow the system: on Windows a path may have a volume, and both / and \
# separate its levels
_WIN32 = sys.platform == 'win32'

# The bytes of a file as they are, as sysread and syswrite of Perl pass them, where the text mode of the C runtime of
# Windows, the default of os.open there, writes \n as CRLF and reads CRLF as \n
_BINARY: int = getattr(os, 'O_BINARY', 0)


type Anything = builtins.object


class Pyjo_File(Pyjo.Base.object, Pyjo.String.Mixin.object):
    """
    :mod:`Pyjo.File` inherits all methods from :mod:`Pyjo.Base` and
    :mod:`Pyjo.String.Mixin` and implements the following new ones.
    """

    def __init__(self, *parts: Anything) -> None:
        """::

            path = Pyjo.File.new()
            path = Pyjo.File.new('/home/sri/.vimrc')
            path = Pyjo.File.new('/home', 'sri', '.vimrc')
            path = Pyjo.File.new(pathlib.Path('/home/sri/.vimrc'))
            path = Pyjo.File.new(tempfile.NamedTemporaryFile())
            path = Pyjo.File.new(tempfile.TemporaryDirectory())

        Construct a new :mod:`Pyjo.File` object, defaults to using the current
        working directory. A temporary file or directory is kept as long as the
        object is, or until the end of a ``with`` block. ::

            # "foo/bar/baz.txt" (on UNIX)
            Pyjo.File.new('foo', 'bar', 'baz.txt')
        """
        if any(p is None for p in parts):
            raise ValueError('Invalid path')

        # Not in Mojolicious: a temporary file or directory of the standard
        # library, kept as Mojo keeps the object of File::Temp
        self._temp = parts[0] if len(parts) == 1 and _is_temp(parts[0]) else None
        self._path = (
            _str(parts[0])
            if len(parts) == 1
            else _catfile(*map(_str, parts))
            if len(parts)
            else _canonpath(os.getcwd())
        )

    # Not in Mojolicious: a context manager, which removes the temporary file or directory that the object keeps where the
    # block ends, as PyPy frees the object only when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        if (temp := self._temp) is not None:
            _release(temp)

    def __bool__(self) -> bool:
        """::

            boolean = bool(path)

        Always true.
        """
        return True

    def __fspath__(self) -> str:
        """::

            string = os.fspath(path)

        The path for the standard library, as :meth:`to_str` gives it.
        """
        return self._path

    def __getitem__(self, index: int) -> str:
        """::

            part = path[0]

        A part of the path, as :meth:`to_list` gives it.
        """
        return self.to_list()[index]

    def __iter__(self) -> Iterator[str]:
        """::

            for part in path:
                ...

        Iterate the parts of the path, as :meth:`to_list` gives them.
        """
        return iter(self.to_list())

    def __len__(self) -> int:
        """::

            size = len(path)

        Number of the parts of the path.
        """
        return len(self.to_list())

    def basename(self, *suffixes: str) -> str:
        """::

            name = path.basename()
            name = path.basename('.txt')

        Return the last level of the path, as ``File::Basename`` of Perl does. ::

            # ".vimrc" (on UNIX)
            path('/home/sri/.vimrc').basename()

            # "test" (on UNIX)
            path('/home/sri/test.txt').basename('.txt')
        """
        return _basename(self._path, *suffixes)

    def child(self, *parts: Anything) -> Self:
        """::

            child = path.child('.vimrc')

        Return a new :mod:`Pyjo.File` object relative to the path. A child of
        a temporary directory keeps the directory as long as it is kept. ::

            # "/home/sri/.vimrc" (on UNIX)
            path('/home').child('sri', '.vimrc')
        """
        child = self.new(self._path, *parts)
        # Unlike Mojolicious: Perl keeps the temporary directory of
        # tempdir()->child(...) until the end of the statement, Python frees it
        # as soon as child() returns, so the child keeps it
        child._temp = self._temp
        return child

    def chmod(self, mode: int) -> Self:
        """::

            path = path.chmod(0o644)

        Change file permissions.
        """
        try:
            os.chmod(self._path, mode)
        except OSError as e:
            _croak(e, f'Can\'t chmod file "{self._path}"')
        return self

    def copy_to(self, to: Anything) -> Self:
        """::

            destination = path.copy_to('/home/sri')
            destination = path.copy_to('/home/sri/.vimrc.backup')

        Copy file with :mod:`shutil` and return the destination as a
        :mod:`Pyjo.File` object.
        """
        destination = self._destination(to)
        try:
            shutil.copyfile(self._path, destination)
        except OSError as e:
            _croak(e, f'Can\'t copy file "{self._path}" to "{_str(to)}"')
        return self.new(destination)

    def dirname(self) -> Self:
        """::

            name = path.dirname()

        Return all but the last level of the path, as ``File::Basename`` of Perl
        does, as a :mod:`Pyjo.File` object. ::

            # "/home/sri" (on UNIX)
            path('/home/sri/.vimrc').dirname()
        """
        return self.new(_dirname(self._path))

    def download(
        self, url: Anything, *, headers: dict[str, Any] | None = None, ua: 'Pyjo.UserAgent.object | None' = None
    ) -> bool:
        """::

            boolean = path.download('https://example.com/test.tar.gz')
            boolean = path.download('https://example.com/test.tar.gz', headers={'Accept': '*/*'})
            boolean = path.download('https://example.com/test.tar.gz', ua=Pyjo.UserAgent.new())

        Download file from URL, returns true once the file has been downloaded
        completely. Incomplete downloads are resumed. Follows ``10`` redirects
        by default and does not limit the size of the response, which will be
        streamed memory efficiently. Note that this method is **EXPERIMENTAL**
        and might change without warning!
        """
        import Pyjo.UserAgent

        if ua is None:
            ua = Pyjo.UserAgent.new(max_redirects=10, max_response_size=0)
        tx = _download_error(ua.transactor.download(ua.head(url, headers or {}), self._path))
        return bool(_download_error(ua.start(tx))) if tx is not None else True

    @property
    def extname(self) -> str:
        """::

            ext = path.extname

        Return file extension of the path. ::

            # "js"
            path('/home/sri/test.js').extname
        """
        return m[1] if (m := re.search(r'.+\.([^.]+)$', self.basename())) else ''

    @property
    def is_abs(self) -> bool:
        """::

            boolean = path.is_abs

        Check if the path is absolute. ::

            # True (on UNIX)
            path('/home/sri/.vimrc').is_abs

            # False (on UNIX)
            path('.vimrc').is_abs
        """
        return _is_abs(self._path) > 0

    def list(self, *, dir: bool = False, hidden: bool = False) -> 'Pyjo.Collection.object[Self]':
        """::

            collection = path.list()
            collection = path.list(hidden=True)

        List all files in the directory and return a :mod:`Pyjo.Collection`
        object containing the results as :mod:`Pyjo.File` objects. The list does
        not include ``.`` and ``..``. ::

            # List files
            for file in path('/home/sri/myapp').list().each():
                print(file)

        These options are currently available:

        ``dir``
            Include directories.

        ``hidden``
            Include hidden files.
        """
        if not os.path.isdir(self._path):
            return Pyjo.Collection.new()
        try:
            names = os.listdir(self._path)
        except OSError as e:
            _croak(e, f'Can\'t open directory "{self._path}"')
        if not hidden:
            names = [n for n in names if not n.startswith('.')]
        files = [_catfile(self._path, n) for n in names]
        if not dir:
            files = [f for f in files if not os.path.isdir(f)]

        return Pyjo.Collection.object(self.new(f) for f in sorted(files))

    def list_tree(
        self, *, dir: bool = False, hidden: bool = False, max_depth: int | None = None
    ) -> 'Pyjo.Collection.object[Self]':
        """::

            collection = path.list_tree()
            collection = path.list_tree(hidden=True)

        List all files recursively in the directory and return a
        :mod:`Pyjo.Collection` object containing the results as
        :mod:`Pyjo.File` objects. The list does not include ``.`` and ``..``,
        and symbolic links to directories are not followed. ::

            # List all templates
            for file in path('/home/sri/myapp/templates').list_tree().each():
                print(file)

        These options are currently available:

        ``dir``
            Include directories.

        ``hidden``
            Include hidden files and directories.

        ``max_depth``
            Maximum number of levels to descend when searching for files.
        """
        if not os.path.isdir(self._path):
            return Pyjo.Collection.new()

        results: builtins.list[Self] = []

        def walk(path: str, depth: int) -> None:
            try:
                names = sorted(os.listdir(path))
            except OSError:
                return
            if not hidden:
                names = [n for n in names if not n.startswith('.')]
            for name in names:
                child = self.new(path, name)
                is_dir = os.path.isdir(child)
                if dir or not is_dir:
                    results.append(child)
                if is_dir and not os.path.islink(child) and (not max_depth or depth + 1 < max_depth):
                    walk(child._path, depth + 1)

        walk(self._path, 0)

        return Pyjo.Collection.object(results)

    def lstat(self) -> os.stat_result:
        """::

            stat = path.lstat()

        Return a :class:`os.stat_result` object for the symlink. ::

            # Get symlink size
            print(path('/usr/sbin/sendmail').lstat().st_size)

            # Get symlink modification time
            print(path('/usr/sbin/sendmail').lstat().st_mtime)
        """
        return os.lstat(self._path)

    def make_path(self, mode: int = 0o777) -> Self:
        """::

            path = path.make_path()
            path = path.make_path(mode=0o711)

        Create the directories if they don't already exist, with
        :func:`os.makedirs`.
        """
        os.makedirs(self._path, mode, exist_ok=True)
        return self

    def move_to(self, to: Anything) -> Self:
        """::

            destination = path.move_to('/home/sri')
            destination = path.move_to('/home/sri/.vimrc.backup')

        Move file with :mod:`shutil` and return the destination as a
        :mod:`Pyjo.File` object.
        """
        destination = self._destination(to)
        try:
            shutil.move(self._path, destination)
        except OSError as e:
            _croak(e, f'Can\'t move file "{self._path}" to "{_str(to)}"')
        return self.new(destination)

    def open(self, mode: str = 'r', *args: Any, **kwargs: Any) -> IO[Any]:
        """::

            handle = path.open('r+')
            handle = path.open('rb')
            handle = path.open('r', encoding='UTF-8')

        Open file with :func:`open`.
        """
        try:
            return builtins.open(self._path, mode, *args, **kwargs)
        except OSError as e:
            _croak(e, f'Can\'t open file "{self._path}"')

    def realpath(self) -> Self:
        """::

            realpath = path.realpath()

        Resolve the path with :func:`os.path.realpath` and return the result as
        a :mod:`Pyjo.File` object.
        """
        return self.new(os.path.realpath(self._path))

    def remove(self) -> Self:
        """::

            path = path.remove()

        Delete file.
        """
        if os.path.exists(self._path):
            try:
                os.unlink(self._path)
            except OSError as e:
                _croak(e, f'Can\'t remove file "{self._path}"')
        return self

    def remove_tree(self, *, keep_root: bool = False) -> Self:
        """::

            path = path.remove_tree()
            path = path.remove_tree(keep_root=True)

        Delete this directory and any files and subdirectories it may contain.
        """
        if not os.path.lexists(self._path):
            return self
        if not keep_root:
            shutil.rmtree(self._path)
            return self
        for name in os.listdir(self._path):
            child = os.path.join(self._path, name)
            if os.path.isdir(child) and not os.path.islink(child):
                shutil.rmtree(child)
            else:
                os.unlink(child)
        return self

    def sibling(self, *parts: Anything) -> Self:
        """::

            sibling = path.sibling('.vimrc')

        Return a new :mod:`Pyjo.File` object relative to the directory part of
        the path. ::

            # "/home/sri/.vimrc" (on UNIX)
            path('/home/sri/.bashrc').sibling('.vimrc')

            # "/home/sri/.ssh/known_hosts" (on UNIX)
            path('/home/sri/.bashrc').sibling('.ssh', 'known_hosts')
        """
        return self.new(_dirname(self._path), *parts)

    def slurp(self, encoding: str | None = None) -> bytes | str | None:
        """::

            data = path.slurp()
            chars = path.slurp('UTF-8')

        Read all data at once from the file. If an encoding is provided, an
        attempt will be made to decode the content, and ``None`` is returned if
        it fails.
        """
        try:
            fd = os.open(self._path, os.O_RDONLY | _BINARY)
        except OSError as e:
            _croak(e, f'Can\'t open file "{self._path}"')
        try:
            content = bytearray()
            while buffer := os.read(fd, 131072):
                content += buffer
        except OSError as e:
            _croak(e, f'Can\'t read from file "{self._path}"')
        finally:
            os.close(fd)

        data = bytes(content)
        return decode(encoding, data) if encoding else data

    def spew(self, content: bytes | str, encoding: str | None = None) -> Self:
        """::

            path = path.spew(data)
            path = path.spew(chars, 'UTF-8')

        Write all data at once to the file. If an encoding is provided, an
        attempt to encode the content will be made prior to writing, and
        characters without one are encoded with ``UTF-8``.
        """
        if isinstance(content, str):
            # Unlike Mojolicious: characters without an encoding are UTF-8, where
            # Perl writes the characters 0-255 as bytes and dies of a wider one
            content = encode(encoding, content) if encoding else content.encode('UTF-8')
        try:
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _BINARY, 0o666)
        except OSError as e:
            _croak(e, f'Can\'t open file "{self._path}"')
        try:
            if os.write(fd, content) != len(content):
                raise OSError(f'Can\'t write to file "{self._path}"')
        except OSError as e:
            _croak(e, f'Can\'t write to file "{self._path}"')
        finally:
            os.close(fd)
        return self

    def spurt(self, *chunks: bytes | str) -> Self:
        """::

            path = path.spurt(*chunks)

        Alias for :meth:`spew` that writes multiple chunks.
        """
        if all(isinstance(c, str) for c in chunks):
            return self.spew(''.join(str(c) for c in chunks))
        return self.spew(b''.join(c.encode('UTF-8') if isinstance(c, str) else c for c in chunks))

    def stat(self) -> os.stat_result:
        """::

            stat = path.stat()

        Return a :class:`os.stat_result` object for the path. ::

            # Get file size
            print(path('/home/sri/.bashrc').stat().st_size)

            # Get file modification time
            print(path('/home/sri/.bashrc').stat().st_mtime)
        """
        return os.stat(self._path)

    def to_abs(self) -> Self:
        """::

            absolute = path.to_abs()

        Return absolute path as a :mod:`Pyjo.File` object, the path does not
        need to exist on the file system.
        """
        path = self._path
        if (level := _is_abs(path)) == 2 or (level and not _WIN32):
            return self.new(_canonpath(path))

        # File::Spec::Win32's rel2abs: a path from the root takes the volume of the working directory, and one with a
        # drive and no root the working directory of that drive
        if _WIN32:
            if level:
                volume = re.match(r'(?:[a-zA-Z]:|(?:\\\\|//)[^\\/]+[\\/][^\\/]+)?', os.getcwd())
                assert volume is not None
                return self.new(_canonpath(volume[0] + path))
            if drive := re.match(r'[a-zA-Z]:', path):
                return self.new(_catfile(os.path.abspath(drive[0]), path[2:]))
        return self.new(_catfile(os.getcwd(), path))

    def to_list(self) -> 'builtins.list[str]':
        """::

            parts = path.to_list()

        Split the path on directory separators. ::

            # "home:sri:.vimrc" (on UNIX)
            ':'.join(path('/home/sri/.vimrc').to_list())
        """
        return _splitdir(self._path)

    # Not in Mojolicious: the conversion to pathlib
    def to_path(self) -> pathlib.Path:
        """::

            p = path.to_path()

        Turn the path into :class:`pathlib.Path`.
        """
        return pathlib.Path(self._path)

    def to_rel(self, base: Anything) -> Self:
        """::

            relative = path.to_rel('/some/base/path')

        Return a relative path from the original path to the destination path as
        a :mod:`Pyjo.File` object. ::

            # "sri/.vimrc" (on UNIX)
            path('/home/sri/.vimrc').to_rel('/home')
        """
        return self.new(os.path.relpath(self._path, _str(base)))

    # Renamed from Mojolicious: to_string
    def to_str(self) -> str:
        """::

            string = path.to_str()

        Stringify the path.
        """
        return self._path

    def touch(self) -> Self:
        """::

            path = path.touch()

        Create file if it does not exist or change the modification and access
        time to the current time. ::

            # Safely read file
            print(path('.bashrc').touch().slurp())
        """
        if not os.path.exists(self._path):
            self.open('w').close()
        try:
            os.utime(self._path)
        except OSError as e:
            _croak(e, f'Can\'t touch file "{self._path}"')
        return self

    # Left out from Mojolicious: with_roles, as Pyjoyment has no roles

    def _destination(self, to: Anything) -> str:
        to = _str(to)
        return _catfile(to, _basename(self._path)) if os.path.isdir(to) else to


def curfile() -> Pyjo_File:
    """::

        path = curfile()

    Construct a new :mod:`Pyjo.File` object for the absolute path to the
    current source file.
    """
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    return Pyjo_File(os.path.realpath(caller.f_code.co_filename if caller is not None else ''))


def path(*parts: Anything) -> Pyjo_File:
    """::

        path = path()
        path = path('/home/sri/.vimrc')
        path = path('/home', 'sri', '.vimrc')
        path = path(tempfile.TemporaryDirectory())

    Construct a new :mod:`Pyjo.File` object, defaults to using the current
    working directory. ::

        # "foo/bar/baz.txt" (on UNIX)
        path('foo', 'bar', 'baz.txt')
    """
    return Pyjo_File(*parts)


def tempdir(template: str | None = None, **kwargs: Any) -> Pyjo_File:
    """::

        path = tempdir()
        path = tempdir('tempXXXXX')

    Construct a new :mod:`Pyjo.File` object for a temporary directory, made
    with :func:`tempfile.mkdtemp` and its keyword arguments, which is removed
    with the object or at the end of a ``with`` block, as Perl's
    ``File::Temp`` removes it, without the :exc:`ResourceWarning` that
    :class:`tempfile.TemporaryDirectory` gives when it is not cleaned up
    explicitly. The ``X`` characters at the end of a
    template are random, and a directory with a template is made in the
    current working directory, as ``File::Temp`` makes it. ::

        # Longer version, which warns when the directory is removed with the object
        path = path(tempfile.TemporaryDirectory())
    """
    if template is not None:
        return Pyjo_File(_Temp(_mkdir(template, **kwargs), _rmtree))
    return Pyjo_File(_Temp(cast(str, _tempfile.mkdtemp(**kwargs)), _rmtree))


def tempfile(**kwargs: Any) -> Pyjo_File:
    """::

        path = tempfile()
        path = tempfile(dir='/tmp')

    Construct a new :mod:`Pyjo.File` object for a temporary file, made with
    :func:`tempfile.mkstemp` and its keyword arguments, which is removed with
    the object or at the end of a ``with`` block, as Perl's ``File::Temp``
    removes it, without the :exc:`ResourceWarning` that
    :func:`tempfile.NamedTemporaryFile` gives when it is not closed
    explicitly. ::

        # Longer version, which warns when the file is removed with the object
        path = path(tempfile.NamedTemporaryFile(dir='/tmp'))
    """
    handle, name = cast(tuple[int, str], _tempfile.mkstemp(**kwargs))
    os.close(handle)
    return Pyjo_File(_Temp(name, _unlink))


# A temporary file or directory of File::Temp, removed with the object without a ResourceWarning
class _Temp:
    def __init__(self, name: str, remove: Callable[[str], Anything]) -> None:
        self.name = name
        self.remove = weakref.finalize(self, remove, name)


# Remove a temporary file or directory now, once, where the object would remove it when it goes
def _release(temp: Anything) -> None:
    if isinstance(temp, _Temp):
        temp.remove()
    elif isinstance(temp, _tempfile.TemporaryDirectory):
        cast(_tempfile.TemporaryDirectory[str], temp).cleanup()
    else:
        cast(Any, temp).close()


# File::Temp's newdir with a template
def _mkdir(template: str, dir: str = '.') -> str:
    prefix = template.rstrip('X')
    size = len(template) - len(prefix)
    chars = string.ascii_letters + string.digits
    while True:
        name = os.path.abspath(os.path.join(dir, prefix + ''.join(_random.choice(chars) for _ in range(size))))
        try:
            os.mkdir(name, 0o700)
            return name
        except FileExistsError:
            continue


def _rmtree(name: str) -> None:
    shutil.rmtree(name, ignore_errors=True)


def _unlink(name: str) -> None:
    try:
        os.unlink(name)
    except OSError:
        pass


# File::Basename's basename
def _basename(path: str, *suffixes: str) -> str:
    path = _strip_trailing_sep(path)
    basename, dirname = _fileparse(path)
    tail = ''
    for suffix in suffixes:
        if basename.endswith(suffix):
            basename, tail = basename[: -len(suffix)], suffix + tail
    if len(tail) and not len(basename):
        basename = tail
    return basename if len(basename) else dirname


# File::Spec's canonpath
def _canonpath(path: str) -> str:
    if _WIN32:
        return _canon_cat(path) if len(path) else path
    path = re.sub(r'/{2,}', '/', path)
    path = re.sub(r'(?:/\.)+(?:/|\Z)', '/', path)
    if path != './':
        path = re.sub(r'^(?:\./)+', '', path, flags=re.S)
    path = re.sub(r'^/(?:\.\./)+', '/', path)
    path = re.sub(r'^/\.\.$', '/', path)
    if path != '/':
        path = re.sub(r'/\Z', '', path)
    return path


# File::Spec's catfile
def _catfile(*parts: str) -> str:
    if _WIN32:
        if not len(parts) or parts[0] == '':
            return _canon_cat('/', *parts[1:])
        if re.match(r'[a-zA-Z]:\Z', parts[0]):
            return _canon_cat(parts[0] + '\\', *parts[1:])
        return _canon_cat(*parts)
    return _canonpath('/'.join(parts))


# File::Spec::Win32's _canon_cat
def _canon_cat(first: str, *rest: str) -> str:
    volume = ''
    if m := re.match(r'([A-Za-z]:)([\\/]?)', first):
        volume = m[1].upper() + ('\\' if m[2] else '')
    elif m := re.match(r'(?:\\\\|//)([^\\/]+)(?:[\\/]([^\\/]+))?[\\/]?', first, re.S):
        volume = f'\\\\{m[1]}' + (f'\\{m[2]}' if m[2] is not None else '') + '\\'
    elif m := re.match(r'[\\/]', first):
        volume = '\\'
    if m:
        first = first[m.end() :]
    path = '\\'.join((first, *rest))

    path = re.sub(r'[\\/]+', r'\\', path)
    path = re.sub(r'(?:(?:\A|\\)\.(?:\\\.)*(?:\\|\Z))+', r'\\', path)
    while True:
        path, n = re.subn(
            r'(?:(?:\A|\\)[^\\]+\\\.\.(?<!\A\.\.\\\.\.)(?<!\\\.\.\\\.\.)(?:\\|\Z))+', r'\\', path, count=1, flags=re.S
        )
        if not n:
            break
    path = re.sub(r'\A\\', '', path)
    path = re.sub(r'\\\Z', '', path)

    if volume.endswith('\\'):
        path = re.sub(r'\A\.\.(?:\\\.\.)*(?:\\|\Z)', '', path)
        if path == '' and (m := re.match(r'(\\\\.*)\\\Z', volume, re.S)):
            return m[1]
    return volume + path if len(path) or len(volume) else '.'


def _download_error(tx: 'Pyjo.Transaction.HTTP.object') -> 'Pyjo.Transaction.HTTP.object | None':
    if not (err := tx.error):
        return tx
    if err['message'] in ('Download complete', 'Download incomplete'):
        return None
    if code := err.get('code'):
        raise Pyjo.Exception.new(f'{code} response: {err["message"]}')
    raise Pyjo.Exception.new(f'Download error: {err["message"]}')


def _croak(e: OSError, message: str) -> NoReturn:
    error = type(e)(f'{message}: {e.strerror}' if e.strerror else message)
    error.errno = e.errno
    raise error from e


# File::Basename's dirname
def _dirname(path: str) -> str:
    basename, dirname = _fileparse(path)
    dirname = _strip_trailing_sep(dirname)
    if not len(basename):
        basename, dirname = _fileparse(dirname)
        dirname = _strip_trailing_sep(dirname)
    return dirname


# File::Basename's fileparse
def _fileparse(path: str) -> tuple[str, str]:
    if _WIN32:
        m = re.match(r'((?:.*[:\\/])?)(.*)', path, re.S)
        assert m is not None
        return m[2], m[1] if re.search(r'[\\/]\Z', m[1]) else m[1] + '.\\'
    m = re.match(r'^(.*/)?(.*)$', path, re.S)
    assert m is not None
    return m[2], m[1] or './'


# File::Spec's file_name_is_absolute, 2 for a path with a volume on Windows
def _is_abs(path: str) -> int:
    if not _WIN32:
        return 1 if path.startswith('/') else 0
    if m := re.match(r'[a-zA-Z]:|(?:\\\\|//)[^\\/]+[\\/][^\\/]+', path):
        return 2 if m[0][1] != ':' or re.match(r'[a-zA-Z]:[\\/]', path) else 0
    return 1 if re.match(r'[\\/]', path) else 0


def _is_temp(value: Anything) -> bool:
    return isinstance(value, (_Temp, _tempfile.TemporaryDirectory)) or type(value).__name__ == '_TemporaryFileWrapper'


# File::Spec's splitdir
def _splitdir(path: str) -> 'builtins.list[str]':
    if not _WIN32:
        return path.split('/')
    if not re.search(r'[\\/]\Z', path):
        return re.split(r'[\\/]', path) if len(path) else []
    return [*re.split(r'[\\/]', path)[:-1], '']


# File::Basename's _strip_trailing_sep
def _strip_trailing_sep(path: str) -> str:
    if _WIN32:
        return re.sub(r'([^:])[\\/]*\Z', r'\1', path)
    return re.sub(r'(.)/*\Z', r'\1', path, flags=re.S)


def _str(value: Anything) -> str:
    if _is_temp(value):
        return str(cast(Any, value).name)
    if isinstance(value, os.PathLike):
        return str(os.fspath(value))  # pyright: ignore[reportUnknownArgumentType]
    return str(value)


new = Pyjo_File.new
object = Pyjo_File
File = Pyjo_File
