"""
Pyjo.Asset.Memory - In-memory storage for HTTP content
======================================================
::

    from Pyjo.Asset.Memory import Memory

    mem = Memory()
    mem.add_chunk(b'foo bar baz')
    print(mem.slurp())

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Asset.Memory

    mem = Pyjo.Asset.Memory.new()
    mem.add_chunk(b'foo bar baz')
    print(mem.slurp())

:mod:`Pyjo.Asset.Memory` is an in-memory storage backend for HTTP content.

Events
------

:mod:`Pyjo.Asset.Memory` inherits all events from :mod:`Pyjo.Asset` and can
emit the following new ones.

upgrade
~~~~~~~
::

    mem.on('upgrade', lambda mem, file: ...)

Emitted when asset gets upgraded to a :mod:`Pyjo.Asset.File` object. ::

    mem.on('upgrade', lambda mem, file: file.set(tmpdir='/tmp'))

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Asset::Memory <https://github.com/mojolicious/mojo/blob/v9.51/lib/Mojo/Asset/Memory.pm>`_
of Mojolicious 9.51.
"""

import Pyjo.Asset
import Pyjo.Asset.File
import Pyjo.Exception
import Pyjo.File

import builtins
import os
import time

from typing import Self


type Anything = builtins.object

# The time the program started, as Perl's $^T: the time this module is loaded
MTIME = time.time()


class Pyjo_Asset_Memory(Pyjo.Asset.object):
    """
    :mod:`Pyjo.Asset.Memory` inherits all methods from :mod:`Pyjo.Asset`
    and implements the following new ones.
    """

    def __init__(
        self,
        *,
        auto_upgrade: bool | None = None,
        end_range: int | None = None,
        max_memory_size: int | None = None,
        mtime: float | None = None,
        start_range: int = 0,
    ) -> None:
        """::

            mem = Pyjo.Asset.Memory.new()
            mem = Pyjo.Asset.Memory.new(max_memory_size=1024, auto_upgrade=True)

        Construct a new :mod:`Pyjo.Asset.Memory` object.
        """
        super().__init__(end_range=end_range, start_range=start_range)

        self.auto_upgrade = auto_upgrade
        """::

            boolean = mem.auto_upgrade
            mem.auto_upgrade = boolean

        Try to detect if content size exceeds :attr:`max_memory_size` limit
        and automatically upgrade to a :mod:`Pyjo.Asset.File` object.
        """

        self._max_memory_size: int | None = max_memory_size

        self._content = bytearray()
        self._frozen = False
        self._mtime = mtime if mtime is not None else MTIME

    @property
    def max_memory_size(self) -> int:
        """::

            size = mem.max_memory_size
            mem.max_memory_size = 1024

        Maximum size in bytes of data to keep in memory before automatically
        upgrading to a :mod:`Pyjo.Asset.File` object, defaults to the value
        of the ``PYJO_MAX_MEMORY_SIZE`` environment variable or ``262144``
        (256KiB).
        """
        if self._max_memory_size is None:
            self._max_memory_size = int(os.environ.get('PYJO_MAX_MEMORY_SIZE') or 262144)
        return self._max_memory_size

    @max_memory_size.setter
    def max_memory_size(self, value: int) -> None:
        self._max_memory_size = value

    @property
    def mtime(self) -> float:
        """::

            mtime = mem.mtime
            mem.mtime = 1408567500

        Modification time of asset, defaults to the time the program started,
        as Perl's ``$^T``.
        """
        return self._mtime

    @mtime.setter
    def mtime(self, value: float) -> None:
        self._mtime = value

    def add_chunk(self, chunk: bytes) -> Pyjo.Asset.object:
        """::

            mem = mem.add_chunk(b'foo bar baz')
            file = mem.add_chunk(b'abc' * 262144)

        Add chunk of data and upgrade to :mod:`Pyjo.Asset.File` object if
        necessary.
        """
        if self._frozen:
            raise Pyjo.Exception.new('Asset has been upgraded and is now frozen')
        if self.auto_upgrade and (self.size + len(chunk)) > self.max_memory_size:
            file = Pyjo.Asset.File.new()
            self.emit('upgrade', file)
            self._frozen = True
            return file.add_chunk(self.slurp() + chunk)

        self._content += chunk
        return self

    def contains(self, string: bytes) -> int:
        """::

            position = mem.contains(b'bar')

        Check if asset contains a specific string.
        """
        start = self.start_range
        pos = self._content.find(string, start)
        if start and pos >= 0:
            pos -= start
        end = self.end_range

        return -1 if end and (pos + len(string)) >= end else pos

    def get_chunk(self, offset: int, max: int | None = None) -> bytes:
        """::

            chunk = mem.get_chunk(offset)
            chunk = mem.get_chunk(offset, max)

        Get chunk of data starting from a specific position, defaults to a
        maximum chunk size of ``131072`` bytes (128KiB).
        """
        if max is None:
            max = 131072

        offset += self.start_range
        if (end := self.end_range) is not None and (offset + max) > end:
            max = end + 1 - offset

        return bytes(self._content[offset : offset + max]) if max > 0 else b''

    def move_to(self, to: Anything) -> Self:
        """::

            mem = mem.move_to('/home/sri/foo.txt')

        Move asset data into a specific file.
        """
        Pyjo.File.new(to).spew(bytes(self._content))
        return self

    @property
    def size(self) -> int:
        """::

            size = mem.size

        Size of asset data in bytes.
        """
        return len(self._content)

    def slurp(self) -> bytes:
        """::

            content = mem.slurp()

        Read all asset data at once.
        """
        return bytes(self._content)

    def to_file(self) -> Pyjo.Asset.File.object:
        """::

            file = mem.to_file()

        Convert asset to :mod:`Pyjo.Asset.File` object.
        """
        return Pyjo.Asset.File.new().add_chunk(self.slurp())


new = Pyjo_Asset_Memory.new
object = Pyjo_Asset_Memory
Memory = Pyjo_Asset_Memory
