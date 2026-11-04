r"""
Pyjo.String.Unicode - String of characters
==========================================
::

    from Pyjo.String.Unicode import Unicode

    # Manipulate string
    string = Unicode('foo_bar_baz')
    print(string.camelize())

    # Or import the module, as in Google Python Style Guide

    import Pyjo.String.Unicode

    # Manipulate string
    string = Pyjo.String.Unicode.new('foo_bar_baz')
    print(string.camelize())

    # Chain methods
    string = Pyjo.String.Unicode.new('foo bar baz').quote()
    string = string.unquote().encode('UTF-8').b64_encode('')
    print(string)

    # Use the alternative constructor
    from Pyjo.String.Unicode import u
    string = u('foobarbaz').b64_encode('').say()

:mod:`Pyjo.String.Unicode` is a :class:`str` that provides a more friendly
API for many of the functions in :mod:`Pyjo.Util`. Its counterpart for bytes
is :mod:`Pyjo.String.Bytes`, and both have every method: a method that needs
bytes encodes the string with ``UTF-8``. A method that turns a string into
another one returns a :mod:`Pyjo.String.Unicode` object, and one that makes
bytes, like :meth:`~Pyjo_String_Unicode.md5_bytes`, a
:mod:`Pyjo.String.Bytes` object. ::

    # Use it as a str
    string = Pyjo.String.Unicode.new('foo')
    print(string.upper())

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
import Pyjo.String.Bytes
import Pyjo.Util

import builtins
import re
import sys

from collections.abc import Callable
from typing import IO, Any, Self


type Anything = builtins.object


class Pyjo_String_Unicode(str):
    """
    :mod:`Pyjo.String.Unicode` inherits all methods from :class:`str` and
    implements the following new ones.
    """

    def __new__(cls, *parts: Anything) -> Self:
        return super().__new__(cls, ''.join(map(_str, parts)))

    def __repr__(self) -> str:
        return f'{self.__module__}.new({super().__repr__()})'

    # Left out from Mojolicious: the "bool" operator, that makes every
    # bytestream true, as "0" is false in Perl; a str is false only when empty

    def b64_decode(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.b64_decode()

        Base64 decode string with :func:`Pyjo.Util.b64_decode`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.b64_decode(self.to_str()))

    def b64_encode(self, eol: str = '\n') -> Self:
        r"""::

            string = string.b64_encode()
            string = string.b64_encode("\n")

        Base64 encode string with :func:`Pyjo.Util.b64_encode`. ::

            # "Zm9vIGJhciBiYXo="
            u('foo bar baz').b64_encode('')
        """
        return self.new(Pyjo.Util.b64_encode(self.to_bytes(), eol))

    # Not in Mojolicious: Base64 for URLs, as Pyjo.Util has it
    def b64url_decode(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.b64url_decode()

        Base64 decode string in the variant for URLs with
        :func:`Pyjo.Util.b64url_decode`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.b64url_decode(self.to_str()))

    def b64url_encode(self) -> Self:
        """::

            string = string.b64url_encode()

        Base64 encode string in the variant for URLs with
        :func:`Pyjo.Util.b64url_encode`. ::

            # "Zm9vIGJhciBiYXo"
            u('foo bar baz').b64url_encode()
        """
        return self.new(Pyjo.Util.b64url_encode(self.to_bytes()))

    def camelize(self) -> Self:
        """::

            string = string.camelize()

        Camelize string with :func:`Pyjo.Util.camelize`.
        """
        return self.new(Pyjo.Util.camelize(self.to_str()))

    def clone(self) -> Self:
        """::

            string2 = string.clone()

        Return a new :mod:`Pyjo.String.Unicode` object cloned from this string.
        """
        return self.new(self.to_str())

    def decamelize(self) -> Self:
        """::

            string = string.decamelize()

        Decamelize string with :func:`Pyjo.Util.decamelize`.
        """
        return self.new(Pyjo.Util.decamelize(self.to_str()))

    def decode(self, encoding: str = 'UTF-8', errors: str = 'strict') -> Self:
        """::

            string = string.decode()
            string = string.decode('iso-8859-1')

        Decode string of the characters 0-255, as the bytes they are, defaults
        to using ``UTF-8``. ::

            # "♥"
            u('%E2%99%A5').url_unescape().decode()
        """
        # Unlike Mojolicious: invalid input raises an exception, as bytes.decode()
        # does, and Mojo::ByteStream becomes undef
        return self.new(self.to_str().encode('latin-1').decode(encoding, errors))

    def encode(self, encoding: str = 'UTF-8', errors: str = 'strict') -> 'Pyjo.String.Bytes.object':
        """::

            data = string.encode()
            data = string.encode('iso-8859-1')

        Encode string to a :mod:`Pyjo.String.Bytes` object, defaults to using
        ``UTF-8``. ::

            # b"%E2%99%A5"
            u('♥').encode().url_escape()
        """
        # Unlike Mojolicious: a character that the encoding cannot represent raises
        # an exception, as str.encode() does, and Mojo replaces it
        return Pyjo.String.Bytes.new(self.to_str().encode(encoding, errors))

    def gunzip(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.gunzip()

        Uncompress string with :func:`Pyjo.Util.gunzip`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.gunzip(self.to_bytes()))

    def gzip(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.gzip()

        Compress string with :func:`Pyjo.Util.gzip`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.gzip(self.to_bytes()))

    # Not in Mojolicious: the binary HMAC, as Pyjo.Util has it
    def hmac_sha1_bytes(self, secret: str | bytes) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.hmac_sha1_bytes('passw0rd')

        Generate binary HMAC-SHA1 checksum for string with
        :func:`Pyjo.Util.hmac_sha1_bytes`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.hmac_sha1_bytes(self.to_bytes(), _bytes(secret)))

    def hmac_sha1_sum(self, secret: str | bytes) -> Self:
        """::

            string = string.hmac_sha1_sum('passw0rd')

        Generate HMAC-SHA1 checksum for string with
        :func:`Pyjo.Util.hmac_sha1_sum`. ::

            # "7fbdc89263974a89210ea71f171c77d3f8c21471"
            u('foo bar baz').hmac_sha1_sum('secr3t')
        """
        return self.new(Pyjo.Util.hmac_sha1_sum(self.to_bytes(), _bytes(secret)))

    # Not in Mojolicious: HMAC-SHA256 and HMAC-SHA512, as Pyjo.Util has them
    def hmac_sha256_bytes(self, secret: str | bytes) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.hmac_sha256_bytes('passw0rd')

        Generate binary HMAC-SHA256 checksum for string with
        :func:`Pyjo.Util.hmac_sha256_bytes`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.hmac_sha256_bytes(self.to_bytes(), _bytes(secret)))

    def hmac_sha256_sum(self, secret: str | bytes) -> Self:
        """::

            string = string.hmac_sha256_sum('passw0rd')

        Generate HMAC-SHA256 checksum for string with
        :func:`Pyjo.Util.hmac_sha256_sum`. ::

            # "cfd435b7e14cb5ed539ee154ce73ef0edea9ad480d54d2ca8894075b79386471"
            u('foo bar baz').hmac_sha256_sum('secr3t')
        """
        return self.new(Pyjo.Util.hmac_sha256_sum(self.to_bytes(), _bytes(secret)))

    def hmac_sha512_bytes(self, secret: str | bytes) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.hmac_sha512_bytes('passw0rd')

        Generate binary HMAC-SHA512 checksum for string with
        :func:`Pyjo.Util.hmac_sha512_bytes`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.hmac_sha512_bytes(self.to_bytes(), _bytes(secret)))

    def hmac_sha512_sum(self, secret: str | bytes) -> Self:
        """::

            string = string.hmac_sha512_sum('passw0rd')

        Generate HMAC-SHA512 checksum for string with
        :func:`Pyjo.Util.hmac_sha512_sum`.
        """
        return self.new(Pyjo.Util.hmac_sha512_sum(self.to_bytes(), _bytes(secret)))

    def html_unescape(self) -> Self:
        """::

            string = string.html_unescape()

        Unescape all HTML entities in string with
        :func:`Pyjo.Util.html_unescape`. ::

            # "%3Chtml%3E"
            u('&lt;html&gt;').html_unescape().url_escape()
        """
        return self.new(Pyjo.Util.html_unescape(self.to_str()))

    def humanize_bytes(self) -> Self:
        """::

            string = string.humanize_bytes()

        Turn number of bytes into a simplified human readable format for string
        with :func:`Pyjo.Util.humanize_bytes`.
        """
        return self.new(Pyjo.Util.humanize_bytes(_number(self.to_str())))

    def md5_bytes(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.md5_bytes()

        Generate binary MD5 checksum for string with :func:`Pyjo.Util.md5_bytes`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.md5_bytes(self.to_bytes()))

    def md5_sum(self) -> Self:
        """::

            string = string.md5_sum()

        Generate MD5 checksum for string with :func:`Pyjo.Util.md5_sum`.
        """
        return self.new(Pyjo.Util.md5_sum(self.to_bytes()))

    @classmethod
    def new(cls, *parts: Anything) -> Self:
        """::

            string = Pyjo.String.Unicode.new('test123')

        Construct a new :mod:`Pyjo.String.Unicode` object.
        """
        return cls(*parts)

    def punycode_decode(self) -> Self:
        """::

            string = string.punycode_decode()

        Punycode decode string with :func:`Pyjo.Util.punycode_decode`.
        """
        return self.new(Pyjo.Util.punycode_decode(self.to_str()))

    def punycode_encode(self) -> Self:
        """::

            string = string.punycode_encode()

        Punycode encode string with :func:`Pyjo.Util.punycode_encode`.
        """
        return self.new(Pyjo.Util.punycode_encode(self.to_str()))

    def quote(self) -> Self:
        """::

            string = string.quote()

        Quote string with :func:`Pyjo.Util.quote`.
        """
        return self.new(Pyjo.Util.quote(self.to_str()))

    def say(self, handle: IO[str] | None = None) -> Self:
        """::

            string = string.say()
            string = string.say(sys.stderr)

        Print string to handle and append a newline, defaults to using
        :data:`sys.stdout`.
        """
        print(self.to_str(), file=handle if handle is not None else sys.stdout)
        return self

    def secure_compare(self, string: str | bytes) -> bool:
        """::

            boolean = string.secure_compare(string2)

        Compare string with :func:`Pyjo.Util.secure_compare`.
        """
        return Pyjo.Util.secure_compare(self.to_str(), string)

    def sha1_bytes(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.sha1_bytes()

        Generate binary SHA1 checksum for string with
        :func:`Pyjo.Util.sha1_bytes`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.sha1_bytes(self.to_bytes()))

    def sha1_sum(self) -> Self:
        """::

            string = string.sha1_sum()

        Generate SHA1 checksum for string with :func:`Pyjo.Util.sha1_sum`.
        """
        return self.new(Pyjo.Util.sha1_sum(self.to_bytes()))

    # Not in Mojolicious: SHA-256 and SHA-512, as Pyjo.Util has them
    def sha256_bytes(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.sha256_bytes()

        Generate binary SHA256 checksum for string with
        :func:`Pyjo.Util.sha256_bytes`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.sha256_bytes(self.to_bytes()))

    def sha256_sum(self) -> Self:
        """::

            string = string.sha256_sum()

        Generate SHA256 checksum for string with :func:`Pyjo.Util.sha256_sum`.
        """
        return self.new(Pyjo.Util.sha256_sum(self.to_bytes()))

    def sha512_bytes(self) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.sha512_bytes()

        Generate binary SHA512 checksum for string with
        :func:`Pyjo.Util.sha512_bytes`.
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.sha512_bytes(self.to_bytes()))

    def sha512_sum(self) -> Self:
        """::

            string = string.sha512_sum()

        Generate SHA512 checksum for string with :func:`Pyjo.Util.sha512_sum`.
        """
        return self.new(Pyjo.Util.sha512_sum(self.to_bytes()))

    @property
    def size(self) -> int:
        """::

            size = string.size

        Size of string.
        """
        return len(self)

    def slugify(self, allow_unicode: bool = False) -> Self:
        """::

            string = string.slugify()
            string = string.slugify(boolean)

        Generate URL slug for string with :func:`Pyjo.Util.slugify`.
        """
        return self.new(Pyjo.Util.slugify(self.to_str(), allow_unicode))

    # Perl's split, which Mojo uses, is not str.split()
    def split(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, pattern: str | re.Pattern[str], limit: int = 0
    ) -> 'Pyjo.Collection.object[Self | None]':
        """::

            collection = string.split(',')
            collection = string.split(',', -1)

        Turn string into :mod:`Pyjo.Collection` object containing
        :mod:`Pyjo.String.Unicode` objects. The pattern is a regular
        expression, and the fields at the end that are empty are left out,
        unless the limit is negative. ::

            # "One,Two,Three"
            u('one,two,three').split(',').map('camelize').join(',')

            # "One,Two,Three,,,"
            u('one,two,three,,,').split(',', -1).map('camelize').join(',')
        """
        return Pyjo.Collection.object(
            [None if f is None else self.new(f) for f in split(pattern, self.to_str(), limit)]
        )

    def tap(self, cb: Callable[..., Any] | str, *args: Any, **kwargs: Any) -> Self:
        """::

            string = string.tap(lambda s: ...)

        Alias for :meth:`Pyjo.Base.tap`.
        """
        Pyjo.Base.tap(self, cb, *args, **kwargs)
        return self

    def term_escape(self) -> Self:
        """::

            string = string.term_escape()

        Escape POSIX control characters in string with
        :func:`Pyjo.Util.term_escape`. ::

            # Print binary checksum to terminal
            u('foo').sha1_bytes().term_escape().say()
        """
        return self.new(Pyjo.Util.term_escape(self.to_str()))

    # Not in Mojolicious: the counterpart of to_str() in Pyjo.String.Mixin
    def to_bytes(self) -> bytes:
        """::

            data = string.to_bytes()

        Turn string into :class:`bytes`, encoded with ``UTF-8``.
        """
        return self.to_str().encode('UTF-8')

    def to_str(self) -> str:
        """::

            string = string.to_str()

        Turn string into :class:`str`.
        """
        return str.__str__(self)

    def trim(self) -> Self:
        """::

            string = string.trim()

        Trim whitespace characters from both ends of string with
        :func:`Pyjo.Util.trim`.
        """
        return self.new(Pyjo.Util.trim(self.to_str()))

    def unindent(self) -> Self:
        """::

            string = string.unindent()

        Unindent string with :func:`Pyjo.Util.unindent`.
        """
        return self.new(Pyjo.Util.unindent(self.to_str()))

    def unquote(self) -> Self:
        """::

            string = string.unquote()

        Unquote string with :func:`Pyjo.Util.unquote`.
        """
        return self.new(Pyjo.Util.unquote(self.to_str()))

    def url_escape(self, pattern: str | None = None) -> Self:
        r"""::

            string = string.url_escape()
            string = string.url_escape(r'^A-Za-z0-9\-._~')

        Percent encode all unsafe characters in string with
        :func:`Pyjo.Util.url_escape`. ::

            # b"%E2%98%83"
            u('☃').encode().url_escape()
        """
        return self.new(Pyjo.Util.url_escape(self.to_str(), pattern))

    def url_unescape(self) -> Self:
        """::

            string = string.url_unescape()

        Decode percent encoded characters in string with
        :func:`Pyjo.Util.url_unescape`. ::

            # "&lt;html&gt;"
            u('%3Chtml%3E').url_unescape().xml_escape()
        """
        return self.new(Pyjo.Util.url_unescape(self.to_str()))

    # Left out from Mojolicious: with_roles, as Pyjoyment has no roles

    def xml_escape(self) -> Self:
        """::

            string = string.xml_escape()

        Escape only the characters ``&``, ``<``, ``>``, ``"`` and ``'`` in
        string with :func:`Pyjo.Util.xml_escape`.
        """
        return self.new(Pyjo.Util.xml_escape(self.to_str()))

    def xor_encode(self, key: str | bytes) -> 'Pyjo.String.Bytes.object':
        """::

            data = string.xor_encode(key)

        XOR encode string with :func:`Pyjo.Util.xor_encode`. ::

            # b"%04%0E%15B%03%1B%10"
            u('foo bar').xor_encode('baz').url_escape()
        """
        return Pyjo.String.Bytes.new(Pyjo.Util.xor_encode(self.to_bytes(), _bytes(key)))


def u(*parts: Anything) -> Pyjo_String_Unicode:
    """::

        string = u('test123')

    Construct a new :mod:`Pyjo.String.Unicode` object.
    """
    return Pyjo_String_Unicode(*parts)


# Not in Mojolicious: Perl's split, for Pyjo.String.Bytes too
def split(pattern: str | re.Pattern[str], string: str, limit: int = 0) -> list[str | None]:
    """::

        fields = split(',', '1,2,3')

    Split string as Perl's ``split`` does: the pattern is a regular
    expression, a match of no length at the beginning of the string or right
    after another match makes no field, the groups of the pattern are fields
    too, and the fields at the end that are empty are left out, unless the
    limit is negative. A positive limit is the largest number
    of fields, the pattern ``' '`` splits on whitespace after leading
    whitespace, and ``'^'`` matches at the beginning of every line.
    """
    if pattern == ' ':
        string, pattern = re.sub(r'\A\s+', '', string), r'\s+'
    regex = re.compile(pattern) if isinstance(pattern, str) else pattern
    if regex.pattern == '^':
        regex = re.compile('^', regex.flags | re.M)
    if not len(string):
        return []

    fields: list[str | None] = []
    pos = count = 0
    for m in regex.finditer(string):
        if limit > 0 and count >= limit - 1:
            break
        if m.start() == m.end() == pos:
            continue
        fields.append(string[pos : m.start()])
        fields.extend(m.groups())
        pos = m.end()
        count += 1
    fields.append(string[pos:])

    if limit == 0:
        while len(fields) and not fields[-1]:
            fields.pop()
    return fields


def _bytes(value: str | bytes) -> bytes:
    return value.encode('UTF-8') if isinstance(value, str) else value


def _number(string: str) -> int | float:
    try:
        return int(string)
    except ValueError:
        return float(string)


def _str(part: Anything) -> str:
    if isinstance(part, (bytes, bytearray)):
        try:
            return bytes(part).decode('UTF-8')
        except UnicodeDecodeError:
            return bytes(part).decode('latin-1')
    return str(part)


new = Pyjo_String_Unicode.new
object = Pyjo_String_Unicode
Unicode = Pyjo_String_Unicode
