r"""
Pyjo.String.Bytes - String of bytes
===================================
::

    from Pyjo.String.Bytes import Bytes

    # Manipulate bytes
    data = Bytes(b'foo bar baz')
    print(data.md5_sum())

    # Or import the module, as in Google Python Style Guide

    import Pyjo.String.Bytes

    # Manipulate bytes
    data = Pyjo.String.Bytes.new(b'foo bar baz')
    print(data.md5_sum())

    # Chain methods
    data = Pyjo.String.Bytes.new(b'foo bar baz').quote()
    string = data.unquote().b64_encode('')
    print(string)

    # Use the alternative constructor
    from Pyjo.String.Bytes import b
    string = b(b'foobarbaz').b64_encode('').say()

:mod:`Pyjo.String.Bytes` is a :class:`bytes` that provides a more friendly
API for many of the functions in :mod:`Pyjo.Util`. Its counterpart for
characters is :mod:`Pyjo.String.Unicode`, and both have every method: a
method that needs characters decodes the bytes with ``UTF-8``, or as the
characters 0-255 when they are not ``UTF-8``, and encodes the result the
same way. A method that turns bytes into other bytes returns a
:mod:`Pyjo.String.Bytes` object, and one that makes characters, like
:meth:`~Pyjo_String_Bytes.md5_sum`, a :mod:`Pyjo.String.Unicode` object. ::

    # Use it as bytes
    data = Pyjo.String.Bytes.new(b'foo')
    print(data.upper())

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::ByteStream <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/ByteStream.pm>`_
of Mojolicious 9.49.

Functions
---------
"""

import Pyjo.Base
import Pyjo.Collection
import Pyjo.String.Unicode
import Pyjo.Util

import builtins
import re
import sys

from collections.abc import Callable
from typing import IO, Any, Self, cast


type Anything = builtins.object


class Pyjo_String_Bytes(bytes):
    """
    :mod:`Pyjo.String.Bytes` inherits all methods from :class:`bytes` and
    implements the following new ones.
    """

    def __new__(cls, *parts: Anything) -> Self:
        return super().__new__(cls, b''.join(map(_bytes, parts)))

    def __repr__(self) -> str:
        return f'{self.__module__}.new({super().__repr__()})'

    def __str__(self) -> str:
        """::

            string = str(data)

        Alias for :meth:`to_str`.
        """
        return self.to_str()

    # Left out from Mojolicious: the "bool" operator, that makes every
    # bytestream true, as "0" is false in Perl; bytes are false only when empty

    def b64_decode(self) -> Self:
        """::

            data = data.b64_decode()

        Base64 decode bytes with :func:`Pyjo.Util.b64_decode`.
        """
        return self.new(Pyjo.Util.b64_decode(self.to_bytes()))

    def b64_encode(self, eol: str = '\n') -> 'Pyjo.String.Unicode.object':
        r"""::

            string = data.b64_encode()
            string = data.b64_encode("\n")

        Base64 encode bytes with :func:`Pyjo.Util.b64_encode`. ::

            # "Zm9vIGJhciBiYXo="
            b(b'foo bar baz').b64_encode('')
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.b64_encode(self.to_bytes(), eol))

    def camelize(self) -> Self:
        """::

            data = data.camelize()

        Camelize bytes with :func:`Pyjo.Util.camelize`.
        """
        return self._chars(Pyjo.Util.camelize)

    def clone(self) -> Self:
        """::

            data2 = data.clone()

        Return a new :mod:`Pyjo.String.Bytes` object cloned from these bytes.
        """
        return self.new(self.to_bytes())

    def decamelize(self) -> Self:
        """::

            data = data.decamelize()

        Decamelize bytes with :func:`Pyjo.Util.decamelize`.
        """
        return self._chars(Pyjo.Util.decamelize)

    def decode(self, encoding: str = 'UTF-8', errors: str = 'strict') -> 'Pyjo.String.Unicode.object':
        """::

            string = data.decode()
            string = data.decode('iso-8859-1')

        Decode bytes to a :mod:`Pyjo.String.Unicode` object, defaults to using
        ``UTF-8``. ::

            # "♥"
            b(b'%E2%99%A5').url_unescape().decode()
        """
        # Unlike Mojolicious: invalid input raises an exception, as bytes.decode()
        # does, and Mojo::ByteStream becomes undef
        return Pyjo.String.Unicode.new(self.to_bytes().decode(encoding, errors))

    def encode(self, encoding: str = 'UTF-8', errors: str = 'strict') -> Self:
        """::

            data = data.encode()
            data = data.encode('iso-8859-1')

        Encode the characters of bytes, defaults to using ``UTF-8``.
        """
        # Unlike Mojolicious: a character that the encoding cannot represent raises
        # an exception, as str.encode() does, and Mojo replaces it
        return self.new(self.to_str().encode(encoding, errors))

    def gunzip(self) -> Self:
        """::

            data = data.gunzip()

        Uncompress bytes with :func:`Pyjo.Util.gunzip`.
        """
        return self.new(Pyjo.Util.gunzip(self.to_bytes()))

    def gzip(self) -> Self:
        """::

            data = data.gzip()

        Compress bytes with :func:`Pyjo.Util.gzip`.
        """
        return self.new(Pyjo.Util.gzip(self.to_bytes()))

    def hmac_sha1_sum(self, secret: str | bytes) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.hmac_sha1_sum(b'passw0rd')

        Generate HMAC-SHA1 checksum for bytes with
        :func:`Pyjo.Util.hmac_sha1_sum`. ::

            # "7fbdc89263974a89210ea71f171c77d3f8c21471"
            b(b'foo bar baz').hmac_sha1_sum(b'secr3t')
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.hmac_sha1_sum(self.to_bytes(), _bytes(secret)))

    # Not in Mojolicious: HMAC-SHA256 and HMAC-SHA512, as Pyjo.Util has them
    def hmac_sha256_sum(self, secret: str | bytes) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.hmac_sha256_sum(b'passw0rd')

        Generate HMAC-SHA256 checksum for bytes with
        :func:`Pyjo.Util.hmac_sha256_sum`. ::

            # "cfd435b7e14cb5ed539ee154ce73ef0edea9ad480d54d2ca8894075b79386471"
            b(b'foo bar baz').hmac_sha256_sum(b'secr3t')
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.hmac_sha256_sum(self.to_bytes(), _bytes(secret)))

    def hmac_sha512_sum(self, secret: str | bytes) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.hmac_sha512_sum(b'passw0rd')

        Generate HMAC-SHA512 checksum for bytes with
        :func:`Pyjo.Util.hmac_sha512_sum`.
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.hmac_sha512_sum(self.to_bytes(), _bytes(secret)))

    def html_unescape(self) -> Self:
        """::

            data = data.html_unescape()

        Unescape all HTML entities in bytes with :func:`Pyjo.Util.html_unescape`. ::

            # b"%3Chtml%3E"
            b(b'&lt;html&gt;').html_unescape().url_escape()
        """
        return self._chars(Pyjo.Util.html_unescape)

    def humanize_bytes(self) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.humanize_bytes()

        Turn number of bytes into a simplified human readable format for bytes
        with :func:`Pyjo.Util.humanize_bytes`.
        """
        return Pyjo.String.Unicode.new(self.to_str()).humanize_bytes()

    def md5_bytes(self) -> Self:
        """::

            data = data.md5_bytes()

        Generate binary MD5 checksum for bytes with :func:`Pyjo.Util.md5_bytes`.
        """
        return self.new(Pyjo.Util.md5_bytes(self.to_bytes()))

    def md5_sum(self) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.md5_sum()

        Generate MD5 checksum for bytes with :func:`Pyjo.Util.md5_sum`.
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.md5_sum(self.to_bytes()))

    @classmethod
    def new(cls, *parts: Anything) -> Self:
        """::

            data = Pyjo.String.Bytes.new(b'test123')

        Construct a new :mod:`Pyjo.String.Bytes` object. A :class:`str` is
        encoded with ``UTF-8``.
        """
        return cls(*parts)

    def punycode_decode(self) -> Self:
        """::

            data = data.punycode_decode()

        Punycode decode bytes with :func:`Pyjo.Util.punycode_decode`.
        """
        return self._chars(Pyjo.Util.punycode_decode)

    def punycode_encode(self) -> Self:
        """::

            data = data.punycode_encode()

        Punycode encode bytes with :func:`Pyjo.Util.punycode_encode`.
        """
        return self._chars(Pyjo.Util.punycode_encode)

    def quote(self) -> Self:
        """::

            data = data.quote()

        Quote bytes with :func:`Pyjo.Util.quote`.
        """
        return self.new(Pyjo.Util.quote(self.to_bytes()))

    def say(self, handle: IO[Any] | None = None) -> Self:
        """::

            data = data.say()
            data = data.say(sys.stderr)

        Print bytes to handle and append a newline, defaults to using
        :data:`sys.stdout`.
        """
        text: IO[Any] = handle if handle is not None else sys.stdout
        # A text handle writes bytes to its buffer
        out = cast(IO[bytes], getattr(text, 'buffer', text))
        if out is not text:
            text.flush()
        out.write(self.to_bytes() + b'\n')
        out.flush()
        return self

    def secure_compare(self, data: str | bytes) -> bool:
        """::

            boolean = data.secure_compare(data2)

        Compare bytes with :func:`Pyjo.Util.secure_compare`.
        """
        return Pyjo.Util.secure_compare(self.to_bytes(), data)

    def sha1_bytes(self) -> Self:
        """::

            data = data.sha1_bytes()

        Generate binary SHA1 checksum for bytes with
        :func:`Pyjo.Util.sha1_bytes`.
        """
        return self.new(Pyjo.Util.sha1_bytes(self.to_bytes()))

    def sha1_sum(self) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.sha1_sum()

        Generate SHA1 checksum for bytes with :func:`Pyjo.Util.sha1_sum`.
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.sha1_sum(self.to_bytes()))

    # Not in Mojolicious: SHA-256 and SHA-512, as Pyjo.Util has them
    def sha256_bytes(self) -> Self:
        """::

            data = data.sha256_bytes()

        Generate binary SHA256 checksum for bytes with
        :func:`Pyjo.Util.sha256_bytes`.
        """
        return self.new(Pyjo.Util.sha256_bytes(self.to_bytes()))

    def sha256_sum(self) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.sha256_sum()

        Generate SHA256 checksum for bytes with :func:`Pyjo.Util.sha256_sum`.
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.sha256_sum(self.to_bytes()))

    def sha512_bytes(self) -> Self:
        """::

            data = data.sha512_bytes()

        Generate binary SHA512 checksum for bytes with
        :func:`Pyjo.Util.sha512_bytes`.
        """
        return self.new(Pyjo.Util.sha512_bytes(self.to_bytes()))

    def sha512_sum(self) -> 'Pyjo.String.Unicode.object':
        """::

            string = data.sha512_sum()

        Generate SHA512 checksum for bytes with :func:`Pyjo.Util.sha512_sum`.
        """
        return Pyjo.String.Unicode.new(Pyjo.Util.sha512_sum(self.to_bytes()))

    @property
    def size(self) -> int:
        """::

            size = data.size

        Size of bytes.
        """
        return len(self)

    def slugify(self, allow_unicode: bool = False) -> Self:
        """::

            data = data.slugify()
            data = data.slugify(boolean)

        Generate URL slug for bytes with :func:`Pyjo.Util.slugify`.
        """
        return self._chars(lambda string: Pyjo.Util.slugify(string, allow_unicode))

    # Perl's split, which Mojo uses, is not bytes.split()
    def split(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, pattern: str | bytes | re.Pattern[str] | re.Pattern[bytes], limit: int = 0
    ) -> 'Pyjo.Collection.object[Self | None]':
        """::

            collection = data.split(b',')
            collection = data.split(b',', -1)

        Turn bytes into :mod:`Pyjo.Collection` object containing
        :mod:`Pyjo.String.Bytes` objects, as
        :meth:`Pyjo.String.Unicode.Pyjo_String_Unicode.split` does. ::

            # b"One,Two,Three"
            b(b'one,two,three').split(b',').map('camelize').join(',').encode()
        """
        # The bytes are characters 0-255 for the regular expression, as in Perl
        if isinstance(pattern, re.Pattern):
            source = pattern.pattern
            flags = pattern.flags
            if isinstance(source, bytes):
                source, flags = source.decode('latin-1'), flags | re.ASCII
            pattern = re.compile(source, flags)
        elif isinstance(pattern, bytes):
            pattern = pattern.decode('latin-1')
        else:
            pattern = pattern.encode('UTF-8').decode('latin-1')
        fields = Pyjo.String.Unicode.split(pattern, self.to_bytes().decode('latin-1'), limit)
        return Pyjo.Collection.object([None if f is None else self.new(f.encode('latin-1')) for f in fields])

    def tap(self, cb: Callable[..., Any] | str, *args: Any, **kwargs: Any) -> Self:
        """::

            data = data.tap(lambda d: ...)

        Alias for :meth:`Pyjo.Base.tap`.
        """
        Pyjo.Base.tap(self, cb, *args, **kwargs)
        return self

    def term_escape(self) -> Self:
        """::

            data = data.term_escape()

        Escape POSIX control characters in bytes with
        :func:`Pyjo.Util.term_escape`. ::

            # Print binary checksum to terminal
            b(b'foo').sha1_bytes().term_escape().say()
        """
        return self._chars(Pyjo.Util.term_escape)

    # Not in Mojolicious: the counterpart of to_str() in Pyjo.String.Mixin
    def to_bytes(self) -> bytes:
        """::

            data = data.to_bytes()

        Turn bytes into :class:`bytes`.
        """
        return bytes(self)

    def to_str(self) -> str:
        """::

            string = data.to_str()

        Turn bytes into :class:`str`, decoded with ``UTF-8``, or as the
        characters 0-255 when they are not ``UTF-8``.
        """
        return _decode(self.to_bytes())[0]

    def trim(self) -> Self:
        """::

            data = data.trim()

        Trim whitespace characters from both ends of bytes with
        :func:`Pyjo.Util.trim`.
        """
        return self._chars(Pyjo.Util.trim)

    def unindent(self) -> Self:
        """::

            data = data.unindent()

        Unindent bytes with :func:`Pyjo.Util.unindent`.
        """
        return self._chars(Pyjo.Util.unindent)

    def unquote(self) -> Self:
        """::

            data = data.unquote()

        Unquote bytes with :func:`Pyjo.Util.unquote`.
        """
        return self.new(Pyjo.Util.unquote(self.to_bytes()))

    def url_escape(self, pattern: bytes | None = None) -> Self:
        r"""::

            data = data.url_escape()
            data = data.url_escape(rb'^A-Za-z0-9\-._~')

        Percent encode all unsafe characters in bytes with
        :func:`Pyjo.Util.url_escape`. ::

            # b"%E2%98%83"
            b('☃').url_escape()
        """
        return self.new(Pyjo.Util.url_escape(self.to_bytes(), pattern))

    def url_unescape(self) -> Self:
        """::

            data = data.url_unescape()

        Decode percent encoded characters in bytes with
        :func:`Pyjo.Util.url_unescape`. ::

            # b"&lt;html&gt;"
            b(b'%3Chtml%3E').url_unescape().xml_escape()
        """
        return self.new(Pyjo.Util.url_unescape(self.to_bytes()))

    # Left out from Mojolicious: with_roles, as Pyjoyment has no roles

    def xml_escape(self) -> Self:
        """::

            data = data.xml_escape()

        Escape only the characters ``&``, ``<``, ``>``, ``"`` and ``'`` in
        bytes with :func:`Pyjo.Util.xml_escape`.
        """
        return self._chars(Pyjo.Util.xml_escape)

    def xor_encode(self, key: str | bytes) -> Self:
        """::

            data = data.xor_encode(key)

        XOR encode bytes with :func:`Pyjo.Util.xor_encode`. ::

            # b"%04%0E%15B%03%1B%10"
            b(b'foo bar').xor_encode(b'baz').url_escape()
        """
        return self.new(Pyjo.Util.xor_encode(self.to_bytes(), _bytes(key)))

    def _chars(self, func: Callable[[str], str]) -> Self:
        string, encoding = _decode(self.to_bytes())
        result = func(string)
        try:
            return self.new(result.encode(encoding))
        except UnicodeEncodeError:
            return self.new(result.encode('UTF-8'))


def b(*parts: Anything) -> Pyjo_String_Bytes:
    """::

        data = b(b'test123')

    Construct a new :mod:`Pyjo.String.Bytes` object.
    """
    return Pyjo_String_Bytes(*parts)


def _bytes(part: Anything) -> bytes:
    if isinstance(part, (bytes, bytearray)):
        return bytes(part)
    return str(part).encode('UTF-8')


def _decode(data: bytes) -> tuple[str, str]:
    try:
        return data.decode('UTF-8'), 'UTF-8'
    except UnicodeDecodeError:
        return data.decode('latin-1'), 'latin-1'


new = Pyjo_String_Bytes.new
object = Pyjo_String_Bytes
Bytes = Pyjo_String_Bytes
