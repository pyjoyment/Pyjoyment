"""
Pyjo.Asset.File - File storage for HTTP content
===============================================
::

    from Pyjo.Asset.File import File

    # Temporary file
    file = File()
    file.add_chunk(b'foo bar baz')
    if file.contains(b'bar') >= 0:
        print('File contains "bar"')
    print(file.slurp())

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Asset.File

    # Temporary file
    file = Pyjo.Asset.File.new()
    file.add_chunk(b'foo bar baz')
    if file.contains(b'bar') >= 0:
        print('File contains "bar"')
    print(file.slurp())

    # Existing file
    file = Pyjo.Asset.File.new(path='/home/sri/foo.txt')
    file.move_to('/yada.txt')
    print(file.slurp())

:mod:`Pyjo.Asset.File` is a file storage backend for HTTP content.

The end of a ``with`` block closes the file, and deletes it with
:attr:`~Pyjo_Asset_File.cleanup`.

Events
------

:mod:`Pyjo.Asset.File` inherits all events from :mod:`Pyjo.Asset`.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Asset::File <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Asset/File.pm>`_
of Mojolicious 9.49.
"""

import Pyjo.Asset
import Pyjo.Exception
import Pyjo.File

import atexit
import builtins
import os
import sys
import tempfile
import weakref

from types import TracebackType
from typing import IO, Self


type Anything = builtins.object


class Pyjo_Asset_File(Pyjo.Asset.object):
    """
    :mod:`Pyjo.Asset.File` inherits all methods from :mod:`Pyjo.Asset` and
    implements the following new ones.
    """

    def __init__(
        self,
        *,
        cleanup: bool | None = None,
        end_range: int | None = None,
        handle: IO[bytes] | None = None,
        path: str | os.PathLike[str] | None = None,
        start_range: int = 0,
        tmpdir: str | os.PathLike[str] | None = None,
    ) -> None:
        """::

            file = Pyjo.Asset.File.new()
            file = Pyjo.Asset.File.new(path='/home/sri/test.txt')

        Construct a new :mod:`Pyjo.Asset.File` object.
        """
        super().__init__(end_range=end_range, start_range=start_range)

        self.cleanup = cleanup
        """::

            boolean = file.cleanup
            file.cleanup = boolean

        Delete :attr:`path` automatically once the file is not used anymore.
        """

        self.path = None if path is None else os.fspath(path)
        """::

            path = file.path
            file.path = '/home/sri/foo.txt'

        File path used to create :attr:`handle`.
        """

        self._handle = handle
        self._pid = os.getpid()
        self._tmpdir = None if tmpdir is None else os.fspath(tmpdir)
        _FILES.add(self)

    def __del__(self) -> None:
        # Module globals may be gone at the end of the interpreter
        try:
            if not sys.is_finalizing():
                self.close()
        except Exception:
            pass

    # Not in Mojolicious: a context manager closes the file where it ends, as PyPy frees the object only later
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    @property
    def handle(self) -> IO[bytes]:
        """::

            handle = file.handle
            file.handle = open('/home/sri/foo.txt', 'rb')

        Filehandle, created on demand for :attr:`path`, which can be
        generated automatically and safely based on :attr:`tmpdir`.
        """
        if self._handle is not None:
            return self._handle

        # Open existing file
        path = self.path
        if path is not None and os.path.exists(path):
            self._handle = Pyjo.File.new(path).open('rb', buffering=0)
            return self._handle

        if self.cleanup is None:
            self.cleanup = True

        # Create a temporary file
        if path is None:
            fd, path = tempfile.mkstemp(prefix='pyjo.tmp.', dir=self.tmpdir)
            os.close(fd)
            self.path = path

        # Create a specific file, appended to as Perl's +>> does
        self._handle = Pyjo.File.new(path).open('a+b', buffering=0)
        return self._handle

    @handle.setter
    def handle(self, value: IO[bytes]) -> None:
        self._handle = value

    @property
    def tmpdir(self) -> str:
        """::

            tmpdir = file.tmpdir
            file.tmpdir = '/tmp'

        Temporary directory used to generate :attr:`path`, defaults to the
        value of the ``PYJO_TMPDIR`` environment variable or auto-detection.
        """
        if self._tmpdir is None:
            self._tmpdir = os.environ.get('PYJO_TMPDIR') or tempfile.gettempdir()
        return self._tmpdir

    @tmpdir.setter
    def tmpdir(self, value: str | os.PathLike[str]) -> None:
        self._tmpdir = os.fspath(value)

    def add_chunk(self, chunk: bytes) -> Self:
        """::

            file = file.add_chunk(b'foo bar baz')

        Add chunk of data.
        """
        try:
            written = self.handle.write(chunk)
        except OSError as e:
            error = type(e)(f"Can't write to asset: {e.strerror}" if e.strerror else "Can't write to asset")
            error.errno = e.errno
            raise error from e
        if written != len(chunk):
            raise Pyjo.Exception.new("Can't write to asset: incomplete write")
        return self

    # Not in Mojolicious: what DESTROY does, which Python does when it frees the file, PyPy only later
    def close(self) -> None:
        """::

            file.close()

        Close :attr:`handle` and delete :attr:`path` with :attr:`cleanup`, as
        it happens when the file is freed.
        """
        if (handle := self._handle) is not None:
            handle.close()
        if not self.cleanup or (path := self.path) is None:
            return

        # Only the process that created the file is allowed to remove it
        if os.access(path, os.W_OK) and self._pid == os.getpid():
            Pyjo.File.new(path).remove()

    def contains(self, string: bytes) -> int:
        """::

            position = file.contains(b'bar')

        Check if asset contains a specific string.
        """
        handle = self.handle
        handle.seek(self.start_range, os.SEEK_SET)

        # Calculate window size
        end = self.end_range if self.end_range is not None else self.size
        length = len(string)
        size = length if length > 131072 else 131072
        if size > end - self.start_range:
            size = end - self.start_range

        # Sliding window search
        offset = 0
        window = handle.read(length) or b''
        start = len(window)
        while offset < end:
            # Read as much as possible
            diff = end - (start + offset)
            buffer = handle.read(diff if diff < size else size) or b''
            read = len(buffer)
            window += buffer

            # Search window
            if (pos := window.find(string)) >= 0:
                return offset + pos
            offset += read
            if read == 0 or offset == end:
                return -1

            # Resize window
            window = window[read:]

        return -1

    def get_chunk(self, offset: int, max: int | None = None) -> bytes:
        """::

            chunk = file.get_chunk(offset)
            chunk = file.get_chunk(offset, max)

        Get chunk of data starting from a specific position, defaults to a
        maximum chunk size of ``131072`` bytes (128KiB).
        """
        if max is None:
            max = 131072

        offset += self.start_range
        handle = self.handle
        handle.seek(offset, os.SEEK_SET)

        if (end := self.end_range) is not None:
            if (chunk := end + 1 - offset) <= 0:
                return b''
            return handle.read(chunk if chunk < max else max) or b''
        return handle.read(max) or b''

    @property
    def is_file(self) -> bool:
        """::

            boolean = file.is_file

        True, this is a :mod:`Pyjo.Asset.File` object.
        """
        return True

    def move_to(self, to: Anything) -> Self:
        """::

            file = file.move_to('/home/sri/bar.txt')

        Move asset data into a specific file and disable :attr:`cleanup`.
        """
        # Windows requires that the handle is closed
        self.handle.close()
        self._handle = None

        # Move file and prevent clean up
        Pyjo.File.new(self.path).move_to(to)
        self.path = str(to)
        self.cleanup = False
        return self

    @property
    def mtime(self) -> float:
        """::

            mtime = file.mtime

        Modification time of asset.
        """
        return os.fstat(self.handle.fileno()).st_mtime

    @property
    def size(self) -> int:
        """::

            size = file.size

        Size of asset data in bytes.
        """
        return os.fstat(self.handle.fileno()).st_size

    def slurp(self) -> bytes:
        """::

            content = file.slurp()

        Read all asset data at once.
        """
        handle = self.handle
        handle.seek(0, os.SEEK_SET)
        content = bytearray()
        try:
            while buffer := handle.read(131072):
                content += buffer
        except OSError as e:
            error = type(e)(f"Can't read from asset: {e.strerror}" if e.strerror else "Can't read from asset")
            error.errno = e.errno
            raise error from e
        return bytes(content)

    def to_file(self) -> Self:
        """::

            file = file.to_file()

        Does nothing but return the invocant, since we already have a
        :mod:`Pyjo.Asset.File` object.
        """
        return self


# Not in Mojolicious: the files that exist, which are closed, and deleted with cleanup, at the end of the interpreter, as
# Perl does it then, while __del__ does nothing
_FILES: 'weakref.WeakSet[Pyjo_Asset_File]' = weakref.WeakSet()


@atexit.register
def _close() -> None:
    for file in list(_FILES):
        try:
            file.close()
        except Exception:
            pass


new = Pyjo_Asset_File.new
object = Pyjo_Asset_File
File = Pyjo_Asset_File
