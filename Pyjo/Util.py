"""
Pyjo.Util - Portable utility functions
======================================
::

    from Pyjo.Util import b64_encode, url_escape, url_unescape

    string = 'test=23'
    escaped = url_escape(string)
    print(url_unescape(escaped))
    print(b64_encode(escaped.encode(), ''))

:mod:`Pyjo.Util` provides portable utility functions for :mod:`Pyjo`.

Next to the functions of Mojolicious, it has functions of its own that turn
statements into expressions, so that they can be used in a lambda, a callback
or a chain: :func:`die`, :func:`getenv`, :func:`isalive`, :func:`notnone`,
:func:`setenv`, :func:`slurp`, :func:`spurt` and :func:`warn`. ::

    home = getenv('HOME') or die('HOME is not defined')

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Util <https://github.com/mojolicious/mojo/blob/v9.52/lib/Mojo/Util.pm>`_
and `Mojo::BaseUtil <https://github.com/mojolicious/mojo/blob/v9.52/lib/Mojo/BaseUtil.pm>`_
of Mojolicious 9.52.

Functions
---------
"""

import ast
import base64
import codecs
import functools
import hashlib
import hmac
import os
import pprint
import re
import secrets
import socket
import sys
import time
import unicodedata
import warnings
import zlib

from collections.abc import Callable, Iterable, Sequence
from gzip import compress as _gzip_compress
from gzip import decompress as _gzip_decompress
from types import FunctionType, ModuleType, TracebackType
from typing import TYPE_CHECKING, Any, NoReturn, Protocol, cast, overload


if TYPE_CHECKING:
    import Pyjo.GetOpt


# "Sun, 06 Nov 1994 08:49:37 GMT" and "Sunday, 06-Nov-94 08:49:37 GMT"
_RE_EXPIRES = re.compile(r'=\s*(\w+\W+\d+\W+\w+\W+\d+\W+\d+:\d+:\d+\W*\w+)')

# Header key/value pairs
_RE_HEADER_NAME = re.compile(r'[,;\s]*([^=;, ]+)\s*')
_RE_HEADER_SEPARATOR = re.compile(r'[;\s]*,\s*')
_RE_PARAM_NAME = re.compile(r'[;\s]*([^=;, ]+)\s*')
_RE_QUOTED_VALUE = re.compile(r'=\s*("(?:\\\\|\\"|[^"])*")')
_RE_UNQUOTED_VALUE = re.compile(r'=\s*([^;, ]*)')

# HTML entities
_RE_ENTITY = re.compile(r'&(?:\#((?:[0-9]{1,7}|x[0-9a-fA-F]{1,6}));|(\w+[;=]?))')


def b64_decode(b64: str | bytes) -> bytes:
    """::

        data = b64_decode(b64)

    Base64 decode bytes, ignoring the characters that are not Base64 and the
    ones after the padding, as ``MIME::Base64`` of Perl does.
    """
    if isinstance(b64, str):
        b64 = b64.encode('latin-1', 'ignore')
    b64 = re.sub(rb'[^A-Za-z0-9+/=]', b'', b64).split(b'=', 1)[0]
    if len(b64) % 4 == 1:
        b64 = b64[:-1]
    return base64.b64decode(b64 + b'=' * (-len(b64) % 4))


def b64_encode(data: bytes, eol: str = '\n') -> str:
    r"""::

        b64 = b64_encode(data)
        b64 = b64_encode(data, "\n")

    Base64 encode bytes, the line ending defaults to a newline.
    """
    b64 = base64.b64encode(data).decode('ascii')
    return ''.join(b64[i : i + 76] + eol for i in range(0, len(b64), 76))


def camelize(string: str) -> str:
    """::

        camelcase = camelize(snakecase)

    Convert ``snake_case`` string to ``CamelCase`` and replace ``-`` with ``::``. ::

        # "FooBar"
        camelize('foo_bar')

        # "FooBar::Baz"
        camelize('foo_bar-baz')

        # "FooBar::Baz"
        camelize('FooBar::Baz')
    """
    if re.match(r'[A-Z]', string):
        return string

    # CamelCase words
    return '::'.join(''.join(_ucfirst(w.lower()) for w in _split('_', part)) for part in _split('-', string))


def class_to_file(class_: str) -> str:
    """::

        file = class_to_file('Foo.Bar')

    Convert a class name to a file. ::

        # "foo_bar"
        class_to_file('Foo.Bar')

        # "foobar"
        class_to_file('FOO.Bar')

        # "foo_bar"
        class_to_file('FooBar')

        # "foobar"
        class_to_file('FOOBar')
    """
    # Left out from Mojolicious: the deprecated package separator "'", which Python has never had
    class_ = class_.replace('.', '')
    class_ = re.sub(r'([A-Z])([A-Z]*)', lambda m: m[1] + m[2].lower(), class_)
    return decamelize(class_)


def class_to_path(class_: str) -> str:
    """::

        path = class_to_path('Foo.Bar')

    Convert class name to path, as a module is found in a directory of
    :data:`sys.path`. ::

        # "Foo/Bar.py"
        class_to_path('Foo.Bar')

        # "FooBar.py"
        class_to_path('FooBar')
    """
    # Left out from Mojolicious: the deprecated package separator "'", which Python has never had
    return '/'.join(class_.split('.')) + '.py'


def decamelize(string: str) -> str:
    """::

        snakecase = decamelize(camelcase)

    Convert ``CamelCase`` string to ``snake_case`` and replace ``::`` with ``-``. ::

        # "foo_bar"
        decamelize('FooBar')

        # "foo_bar-baz"
        decamelize('FooBar::Baz')

        # "foo_bar-baz"
        decamelize('foo_bar-baz')
    """
    if not re.match(r'[A-Z]', string):
        return string

    # snake_case words
    return '-'.join(
        '_'.join(w.lower() for w in re.split(r'([A-Z]{1}[^A-Z]*)', part) if len(w)) for part in _split('::', string)
    )


def decode(charset: str, data: str | bytes) -> str | None:
    """::

        chars = decode('UTF-8', data)

    Decode bytes to characters, or return ``None`` if decoding failed. A string
    of the characters 0-255 is decoded as the bytes it holds, like a Perl byte
    string; one with other characters does not decode.
    """
    if isinstance(data, str):
        try:
            data = data.encode('latin-1')
        except UnicodeEncodeError:
            return None
    try:
        return codecs.lookup(charset).decode(data)[0]
    except (LookupError, UnicodeDecodeError):
        return None


# Left out from Mojolicious: decrypt_cookie, as ChaCha20-Poly1305 of the sessions is not in the standard library


def deprecated(*args: object) -> None:
    """::

        deprecated('foo is DEPRECATED in favor of bar')

    Warn about deprecated feature from perspective of caller, with a
    :exc:`DeprecationWarning`. You can also set the ``PYJO_FATAL_DEPRECATIONS``
    environment variable to make them raise it instead.
    """
    msg = ''.join(map(str, args))
    if os.environ.get('PYJO_FATAL_DEPRECATIONS'):
        raise DeprecationWarning(msg)
    # Unlike Mojolicious: the filters of warnings decide whether the warning is shown, as Python shows a
    # DeprecationWarning by default only where __main__ triggers it, where Mojo always warns
    warnings.warn(msg, DeprecationWarning, stacklevel=3)


def die(e: BaseException | str) -> NoReturn:
    """::

        die(Exception('Something went wrong'))
        die('Exit immediately')

    Raise an exception. :class:`SystemExit` exception is raised
    if parameter is not an exception already. ::

        os.environ.get('HOME') or die('HOME is not defined')
    """
    if isinstance(e, BaseException):
        raise e
    else:
        raise SystemExit(e)


def dumper(*values: object) -> str:
    """::

        python = dumper({'some': 'data'})

    Dump a Python data structure with :mod:`pprint`.
    """
    return ''.join(pprint.pformat(value) + '\n' for value in values)


def encode(charset: str, chars: str) -> bytes:
    """::

        data = encode('UTF-8', chars)

    Encode characters to bytes. A character that the encoding cannot
    represent becomes a replacement character.
    """
    try:
        codecs.lookup(charset)
    except LookupError:
        raise LookupError(f"Unknown encoding '{charset}'") from None
    return chars.encode(charset, 'replace')


# Left out from Mojolicious: encrypt_cookie, as ChaCha20-Poly1305 of the sessions is not in the standard library


def extract_usage(file: 'str | os.PathLike[str] | None' = None, section: str | None = None) -> str:
    """::

        usage = extract_usage()
        usage = extract_usage('/home/sri/foo.py')
        usage = extract_usage(section='myscript')

    Extract usage message from the synopsis of the docstring of a module, its
    first literal block, defaults to using the file this function was called
    from. ::

        # "Usage: APPLICATION test [OPTIONS]\\n"
        extract_usage()

        \"\"\"
        Test command
        ============
        ::

            Usage: APPLICATION test [OPTIONS]
        \"\"\"

    With a section, the first literal block after its heading, as the usage of
    a script that is a function of the module. ::

        # "Usage: myscript [OPTIONS]\\n"
        extract_usage(section='myscript')

        \"\"\"
        Test module
        ===========
        ::

            test = Test.new()

        myscript
        --------
        ::

            Usage: myscript [OPTIONS]
        \"\"\"
    """
    # Unlike Mojolicious: the synopsis of the docstring, which the file is parsed for without running it, where Mojo
    # extracts the section SYNOPSIS of POD
    path = os.fspath(file) if file is not None else sys._getframe(1).f_code.co_filename  # pyright: ignore[reportPrivateUsage]
    with open(path, encoding='utf-8') as handle:
        docstring = ast.get_docstring(ast.parse(handle.read()), clean=False) or ''

    lines = docstring.split('\n')

    # Not in Mojolicious: the section of a heading, as the usage of a script that is a function of the module
    if section is not None:
        start = next(
            (
                i + 2
                for i, line in enumerate(lines[:-1])
                if line.strip() == section and re.fullmatch(r'\s*([-=~^"\'])\1+\s*', lines[i + 1])
            ),
            None,
        )
        if start is None:
            return ''
        lines = lines[start:]

    block: list[str] = []
    for i, line in enumerate(lines):
        if line.rstrip().endswith('::'):
            indent = len(line) - len(line.lstrip())
            for line in lines[i + 1 :]:
                if line.strip() and len(line) - len(line.lstrip()) <= indent:
                    break
                block.append(line)
            break
    usage = unindent('\n'.join(block).strip('\n'))
    return f'{usage}\n' if usage else ''


def generate_secret() -> str:
    """::

        secret = generate_secret()

    Generate a random secret with a cryptographically secure random number
    generator.
    """
    return secrets.token_urlsafe(128)


@overload
def getenv(name: str) -> str | None: ...


@overload
def getenv(name: str, default: str) -> str: ...


def getenv(name: str, default: str | None = None) -> str | None:
    """::

        envvar = getenv(name)
        envvar = getenv(name, default)

    Get the environment variable. Returns default value or ``None``
    if variable is not defined.
    """
    return os.environ.get(name, default)


@overload
def getopt(
    specs: 'dict[str, Pyjo.GetOpt.Target]',
    /,
    *,
    pass_through: bool = False,
    require_order: bool = False,
    env_prefix: str | None = None,
) -> 'Pyjo.GetOpt.Pyjo_GetOpt_Result': ...


@overload
def getopt(
    args: list[str],
    specs: 'dict[str, Pyjo.GetOpt.Target]',
    /,
    *,
    pass_through: bool = False,
    require_order: bool = False,
    env_prefix: str | None = None,
) -> 'Pyjo.GetOpt.Pyjo_GetOpt_Result': ...


def getopt(
    args: 'list[str] | dict[str, Pyjo.GetOpt.Target]',
    specs: 'dict[str, Pyjo.GetOpt.Target] | None' = None,
    /,
    *,
    pass_through: bool = False,
    require_order: bool = False,
    env_prefix: str | None = None,
) -> 'Pyjo.GetOpt.Pyjo_GetOpt_Result':
    """::

        opts = getopt({'H|headers=s': headers, 't|timeout=i': None, 'v|verbose': None})
        opts = getopt(args, {'H|headers=s': headers, 't|timeout=i': None, 'v|verbose': None})
        opts = getopt(args, {'H|headers=s': headers, 't|timeout=i': None}, pass_through=True)
        opts = getopt(args, {'v|verbose': None}, require_order=True)
        opts = getopt(args, {'t|timeout=i': None}, env_prefix='PYJO_')

    Extract options from a list with :mod:`Pyjo.GetOpt`, defaults to using
    the arguments of ``sys.argv``. The target of an option is a list for its
    values, a callback, which gets its name and its value, or ``None`` for
    its value in the result, which is false after an error. With
    ``require_order``, the options end at the first argument that is not one.
    With ``env_prefix``, an option that is not given has the value of the
    environment variable of its name, as ``PYJO_TIMEOUT`` for ``--timeout``,
    see :mod:`Pyjo.GetOpt`. ::

        # Extract "charset" option
        opts = getopt(['--charset', 'UTF-8'], {'charset=s': None})
        print(opts.charset)
    """
    # Unlike Mojolicious: the options in a dict, and the values without a target in the result, as Python has no
    # references to variables, which Mojo passes as the targets
    import Pyjo.GetOpt

    argv = None if isinstance(args, dict) else args
    parser = Pyjo.GetOpt.new(pass_through=pass_through, require_order=require_order, env_prefix=env_prefix)
    for spec, target in (args if isinstance(args, dict) else specs or {}).items():
        parser.option(spec, target)
    return parser.parse(argv)


def gunzip(compressed: bytes) -> bytes:
    """::

        uncompressed = gunzip(compressed)

    Uncompress bytes with :mod:`gzip`.
    """
    try:
        return _gzip_decompress(compressed)
    except (EOFError, OSError, zlib.error) as e:
        raise ValueError(f"Couldn't gunzip: {e}") from e


def gzip(uncompressed: bytes) -> bytes:
    """::

        compressed = gzip(uncompressed)

    Compress bytes with :mod:`gzip`.
    """
    return _gzip_compress(uncompressed)


def header_params(value: str) -> tuple[dict[str, str], str]:
    """::

        params, remainder = header_params('one=foo; two="bar", three=baz')

    Extract HTTP header field parameters until the first comma according to
    :rfc:`5987`.
    """
    params: dict[str, str] = {}
    pos = 0
    while m := _RE_PARAM_NAME.match(value, pos):
        name, pos = m[1], m.end()

        # Quoted value
        if quoted := _RE_QUOTED_VALUE.match(value, pos):
            params.setdefault(name, unquote(quoted[1]))
            pos = quoted.end()

        # Unquoted value
        elif unquoted := _RE_UNQUOTED_VALUE.match(value, pos):
            params.setdefault(name, unquoted[1])
            pos = unquoted.end()

    return params, value[pos:]


def hmac_sha1_sum(data: bytes, secret: bytes) -> str:
    """::

        checksum = hmac_sha1_sum(data, b'passw0rd')

    Generate HMAC-SHA1 checksum for bytes with :mod:`hmac`. ::

        # "11cedfd5ec11adc0ec234466d8a0f2a83736aa68"
        hmac_sha1_sum(b'foo', b'passw0rd')
    """
    return hmac.new(secret, data, hashlib.sha1).hexdigest()


# Not in Mojolicious: HMAC-SHA256 and HMAC-SHA512, as the signatures of webhooks and of the APIs of the cloud ask for them
def hmac_sha256_sum(data: bytes, secret: bytes) -> str:
    """::

        checksum = hmac_sha256_sum(data, b'passw0rd')

    Generate HMAC-SHA256 checksum for bytes with :mod:`hmac`. ::

        # "e54ce0e8e81828088bc8e81b9f2d96816e4a56ffe691d40f1426365e83623c8c"
        hmac_sha256_sum(b'foo', b'passw0rd')
    """
    return hmac.new(secret, data, hashlib.sha256).hexdigest()


def hmac_sha512_sum(data: bytes, secret: bytes) -> str:
    """::

        checksum = hmac_sha512_sum(data, b'passw0rd')

    Generate HMAC-SHA512 checksum for bytes with :mod:`hmac`. ::

        # "cd43bd8e691c5aff08152da9918221d91cc1c0f4cb63a80b5e1160387b98791f..."
        hmac_sha512_sum(b'foo', b'passw0rd')
    """
    return hmac.new(secret, data, hashlib.sha512).hexdigest()


def html_attr_unescape(string: str) -> str:
    """::

        string = html_attr_unescape(escaped)

    Same as :func:`html_unescape`, but handles special rules from the
    `HTML Living Standard <https://html.spec.whatwg.org>`_ for HTML
    attributes. ::

        # "foo=bar&ltest=baz"
        html_attr_unescape('foo=bar&ltest=baz')

        # "foo=bar<est=baz"
        html_attr_unescape('foo=bar&lt;est=baz')
    """
    return _html(string, True)


def html_unescape(string: str) -> str:
    """::

        string = html_unescape(escaped)

    Unescape all HTML entities in string. ::

        # "<div>"
        html_unescape('&lt;div&gt;')
    """
    return _html(string, False)


def humanize_bytes(size: int | float) -> str:
    """::

        string = humanize_bytes(1234)

    Turn number of bytes into a simplified human readable format. ::

        # "1B"
        humanize_bytes(1)

        # "7.5GiB"
        humanize_bytes(8007188480)

        # "13GiB"
        humanize_bytes(13443399680)

        # "-685MiB"
        humanize_bytes(-717946880)
    """
    prefix = '-' if size < 0 else ''

    if (size := abs(size)) < 1024:
        return f'{prefix}{size}B'
    if (size := size / 1024) < 1024:
        return f'{prefix}{_round(size)}KiB'
    if (size := size / 1024) < 1024:
        return f'{prefix}{_round(size)}MiB'
    if (size := size / 1024) < 1024:
        return f'{prefix}{_round(size)}GiB'
    return f'{prefix}{_round(size / 1024)}TiB'


def isalive(obj: object) -> bool:
    """::

        boolean = isalive(weakref.proxy(obj))

    Check if object behind weak reference proxy still exists.
    """
    try:
        obj.__class__
        return True
    except ReferenceError:
        return False


def md5_bytes(data: bytes) -> bytes:
    """::

        checksum = md5_bytes(data)

    Generate binary MD5 checksum for bytes with :mod:`hashlib`.
    """
    return hashlib.md5(data).digest()


def md5_sum(data: bytes) -> str:
    """::

        checksum = md5_sum(data)

    Generate MD5 checksum for bytes with :mod:`hashlib`. ::

        # "acbd18db4cc2f85cedef654fccc4a4d8"
        md5_sum(b'foo')
    """
    return hashlib.md5(data).hexdigest()


def monkey_patch(target: type | ModuleType, **patch: Callable[..., Any]) -> None:
    """::

        monkey_patch(cls, foo=lambda: ...)
        monkey_patch(module, foo=lambda: ...)
        monkey_patch(cls, foo=lambda: ..., bar=lambda: ...)

    Monkey patch functions into a class or a module, with names of their
    own. ::

        monkey_patch(MyApp,
                     one=lambda: print('One!'),
                     two=lambda: print('Two!'),
                     three=lambda: print('Three!'))
    """
    # Unlike Mojolicious: a class or a module, not the name of a package, which Mojo creates when it does not exist
    if isinstance(target, type):
        module, prefix = target.__module__, target.__qualname__ + '.'
    else:
        module, prefix = target.__name__, ''
    for name, cb in patch.items():
        if isinstance(cb, FunctionType):
            cb.__module__, cb.__name__, cb.__qualname__ = module, name, prefix + name
        setattr(target, name, cb)


def network_contains(cidr: str, addr: str) -> bool:
    """::

        boolean = network_contains(network, address)

    Check that a given address is contained within a network in CIDR form. If
    the network is a single address, the addresses must be equivalent. ::

        # True
        network_contains('10.0.0.0/8', '10.10.10.10')
        network_contains('10.10.10.10', '10.10.10.10')
        network_contains('fc00::/7', 'fc00::c0:ff:ee')

        # False
        network_contains('10.0.0.0/29', '10.10.10.10')
        network_contains('10.10.10.12', '10.10.10.10')
        network_contains('fc00::/7', '::1')
    """
    if not len(cidr) or not len(addr):
        return False

    # Parse inputs
    net, slash, mask = cidr.partition('/')
    v6 = ':' in net
    if v6 != (':' in addr):
        return False

    # Convert addresses to binary
    family = socket.AF_INET6 if v6 else socket.AF_INET
    try:
        net_bytes, addr_bytes = socket.inet_pton(family, net), socket.inet_pton(family, addr)
    except OSError:
        return False
    length = 128 if v6 else 32

    # Apply mask if given
    addr_int = int.from_bytes(addr_bytes)
    if slash:
        bits = int(mask) if mask.isdigit() else 0
        addr_int &= int(('1' * bits).ljust(length, '0')[:length], 2)

    # Compare
    return int.from_bytes(net_bytes) ^ addr_int == 0


def notnone[T](*args: T | Callable[[], T] | None) -> T | None:
    """::

        value = notnone(value, another_value, default_value)
        value = notnone(value, lambda: default_value)

    Return the first argument that is not ``None``. An argument that is
    callable is called, and its value is returned (lazy evaluation). ::

        from Pyjo.Util import getenv

        def print_log(msg, **kwargs):
            level = notnone(kwargs.get('log_level'), lambda: int(getenv('LOG_LEVEL', '3')))
            ...
    """
    for a in args:
        if a is not None:
            # cast: a T that is callable itself is called too
            return cast(Callable[[], T], a)() if callable(a) else a
    return None


def punycode_decode(punycode: str) -> str:
    """::

        string = punycode_decode(punycode)

    Punycode decode string as described in :rfc:`3492`. ::

        # "bücher"
        punycode_decode('bcher-kva')
    """
    return punycode.encode('ascii').decode('punycode')


def punycode_encode(string: str) -> str:
    """::

        punycode = punycode_encode(string)

    Punycode encode string as described in :rfc:`3492`. ::

        # "bcher-kva"
        punycode_encode('bücher')
    """
    return string.encode('punycode').decode('ascii')


re_b_quote = re.compile(rb'(["\\])')
re_u_quote = re.compile(r'(["\\])')


@overload
def quote(string: str) -> str: ...


@overload
def quote(string: bytes) -> bytes: ...


def quote(string: str | bytes) -> str | bytes:
    """::

        quoted = quote(string)

    Quote string.
    """
    if isinstance(string, bytes):
        string = re_b_quote.sub(rb'\\\1', string)
        return b'"' + string + b'"'
    else:
        string = re_u_quote.sub(r'\\\1', string)
        return '"' + string + '"'


def random_bytes(count: int) -> bytes:
    """::

        random = random_bytes(count)

    Generate ``count`` bytes worth of high entropy randomness.
    """
    if not isinstance(count, int) or count < 0:  # pyright: ignore[reportUnnecessaryIsInstance]
        import Pyjo.Exception

        raise Pyjo.Exception.new('Byte count must be a defined, non-negative integer')
    return secrets.token_bytes(count)


def scope_guard(cb: Callable[[], object]) -> '_Guard':
    """::

        with scope_guard(lambda: ...):
            ...

    Create anonymous scope guard object that will execute the passed callback
    when the ``with`` block ends. ::

        # Execute callback at end of block
        with scope_guard(lambda: print('Mojo!')):
            print('Hello')
    """
    # Unlike Mojolicious: a context manager, not an object that calls back when it is destroyed, as PyPy frees an
    # object only when its garbage collector runs
    return _Guard(cb)


def secure_compare(one: str | bytes, two: str | bytes) -> bool:
    """::

        boolean = secure_compare(string1, string2)

    Constant time comparison algorithm to prevent timing attacks. The secret
    string should be the second argument, to avoid leaking information about
    the length of the string.
    """
    return hmac.compare_digest(
        one.encode('UTF-8') if isinstance(one, str) else one, two.encode('UTF-8') if isinstance(two, str) else two
    )


def setenv(name: str, value: str | None) -> None:
    """::

        setenv(name, value)

    Set the environment variable or remove it if value is ``None``.
    """
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def sha1_bytes(data: bytes) -> bytes:
    """::

        checksum = sha1_bytes(data)

    Generate binary SHA1 checksum for bytes with :mod:`hashlib`.
    """
    return hashlib.sha1(data).digest()


def sha1_sum(data: bytes) -> str:
    """::

        checksum = sha1_sum(data)

    Generate SHA1 checksum for bytes with :mod:`hashlib`. ::

        # "0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33"
        sha1_sum(b'foo')
    """
    return hashlib.sha1(data).hexdigest()


# Not in Mojolicious: SHA-256 and SHA-512, as the digests of the APIs of the cloud and of the integrity of packages
def sha256_bytes(data: bytes) -> bytes:
    """::

        checksum = sha256_bytes(data)

    Generate binary SHA256 checksum for bytes with :mod:`hashlib`.
    """
    return hashlib.sha256(data).digest()


def sha256_sum(data: bytes) -> str:
    """::

        checksum = sha256_sum(data)

    Generate SHA256 checksum for bytes with :mod:`hashlib`. ::

        # "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
        sha256_sum(b'foo')
    """
    return hashlib.sha256(data).hexdigest()


def sha512_bytes(data: bytes) -> bytes:
    """::

        checksum = sha512_bytes(data)

    Generate binary SHA512 checksum for bytes with :mod:`hashlib`.
    """
    return hashlib.sha512(data).digest()


def sha512_sum(data: bytes) -> str:
    """::

        checksum = sha512_sum(data)

    Generate SHA512 checksum for bytes with :mod:`hashlib`. ::

        # "f7fbba6e0636f890e56fbbf3283e524c6fa3204ae298382d624741d0dc663832..."
        sha512_sum(b'foo')
    """
    return hashlib.sha512(data).hexdigest()


def slurp(path: str | os.PathLike[str], charset: str = 'utf-8') -> str:
    """::

        string = slurp('/etc/passwd')
        string = slurp('/etc/passwd', 'utf-8')

    Read all data at once from file as characters.
    """
    with open(path, 'rb') as f:
        return f.read().decode(charset)


def slugify(value: str | int, allow_unicode: bool = False) -> str:
    """::

        slug = slugify(string)
        slug = slugify(string, boolean)

    Returns a URL slug generated from the input string. Non-word characters are
    removed, the string is trimmed and lowercased, and whitespace characters
    are replaced by a dash. By default, non-ASCII characters are normalized to
    ASCII word characters or removed, but if a true value is passed as the
    second parameter, all word characters will be allowed in the result
    according to unicode semantics. ::

        # "joel-is-a-slug"
        slugify('Joel is a slug')

        # "this-is-my-resume"
        slugify('This is: my - résumé! ☃ ')

        # "this-is-my-résumé"
        slugify('This is: my - résumé! ☃ ', True)
    """
    if allow_unicode:
        # Perl's \w matches the combining marks, Python's does not
        value = ''.join(
            c
            for c in unicodedata.normalize('NFKC', str(value))
            if re.match(r'[\w\s-]', c) or unicodedata.category(c).startswith('M')
        )
    else:
        value = re.sub(r'[^a-zA-Z0-9_\t\n\x0b\f\r -]+', '', unicodedata.normalize('NFKD', str(value)))
    return re.sub(r'[-\s]+', '-', trim(value).lower())


def split_cookie_header(string: str) -> list[list[tuple[str, str | None]]]:
    """::

        tree = split_cookie_header('a=b; expires=Thu, 07 Aug 2008 07:07:59 GMT')

    Same as :func:`split_header`, but handles ``expires`` values from
    :rfc:`6265`.
    """
    return _header(string, True)


def split_header(string: str) -> list[list[tuple[str, str | None]]]:
    """::

        tree = split_header('foo="bar baz"; test=123, yada')

    Split HTTP header value into key/value pairs, each comma separated part gets
    its own list of ``(key, value)`` tuples, and keys without a value get
    ``None`` assigned. ::

        # 'one'
        split_header('one; two="three four", five=six')[0][0][0]

        # 'two'
        split_header('one; two="three four", five=six')[0][1][0]

        # 'three four'
        split_header('one; two="three four", five=six')[0][1][1]

        # 'five'
        split_header('one; two="three four", five=six')[1][0][0]

        # 'six'
        split_header('one; two="three four", five=six')[1][0][1]
    """
    return _header(string, False)


def spurt(content: str, path: str | os.PathLike[str], charset: str = 'utf-8') -> int:
    """::

        written = spurt(string, '/etc/passwd')
        written = spurt(string, '/etc/passwd', 'utf-8')

    Write all characters at once to file, and return the number of bytes
    written.
    """
    with open(path, 'wb') as f:
        return f.write(content.encode(charset))


def steady_time() -> float:
    """::

        time = steady_time()

    High resolution time elapsed from an arbitrary fixed point in the past,
    resilient to time jumps if a monotonic clock is available through
    :func:`time.monotonic`.
    """
    return time.monotonic()


def tablify(rows: Sequence[Sequence[object]]) -> str:
    r"""::

        table = tablify([['foo', 'bar'], ['baz', 'yada']])

    Row-oriented generator for text tables. ::

        # "foo   bar\nyada  yada\nbaz   yada\n"
        tablify([['foo', 'bar'], ['yada', 'yada'], ['baz', 'yada']])
    """
    table = [[re.sub(r'[\r\n]', '', str(v) if v is not None else '') for v in row] for row in rows]

    spec: list[int] = []
    for row in table:
        for i, v in enumerate(row):
            if i >= len(spec):
                spec.append(len(v))
            elif len(v) >= spec[i]:
                spec[i] = len(v)

    return ''.join(
        '  '.join(v.ljust(spec[i]) if i < len(spec) - 1 else v for i, v in enumerate(row)) + '\n' for row in table
    )


def term_escape(string: str) -> str:
    r"""::

        escaped = term_escape(string)

    Escape all POSIX control characters except for ``\n``. ::

        # "foo\\x09bar\\x0d\n"
        term_escape("foo\tbar\r\n")
    """
    return re.sub(r'[\x00-\x09\x0b-\x1f\x7f\x80-\x9f]', lambda m: f'\\x{ord(m[0]):02x}', string)


def trim(string: str) -> str:
    """::

        trimmed = trim(string)

    Trim whitespace characters from both ends of string. ::

        # "foo bar"
        trim('  foo bar  ')
    """
    return re.sub(r'\s+\Z', '', re.sub(r'\A\s+', '', string))


def unindent(string: str) -> str:
    r"""::

        unindented = unindent(string)

    Unindent multi-line string. ::

        # "foo\nbar\nbaz\n"
        unindent("  foo\n  bar\n  baz\n")
    """
    indents = [len(m[0]) for line in string.split('\n') if (m := re.match(r'[ \t]*', line)) and len(m[0])]
    if indents:
        string = re.sub(rf'^[ \t]{{0,{min(indents)}}}', '', string, flags=re.M)
    return string


@overload
def unquote(string: str) -> str: ...


@overload
def unquote(string: bytes) -> bytes: ...


def unquote(string: str | bytes) -> str | bytes:
    """::

        string = unquote(quoted)

    Unquote string.
    """
    if isinstance(string, str):
        string, n = re.subn(r'^"(.*)"$', lambda m: m[1], string)
        return string.replace('\\\\', '\\').replace('\\"', '"') if n else string
    string, n = re.subn(rb'^"(.*)"$', lambda m: m[1], bytes(string))
    return string.replace(b'\\\\', b'\\').replace(b'\\"', b'"') if n else string


@overload
def url_escape(string: str, pattern: str | None = None) -> str: ...


@overload
def url_escape(string: bytes, pattern: bytes | None = None) -> bytes: ...


def url_escape(string: str | bytes, pattern: str | bytes | None = None) -> str | bytes:
    r"""::

        escaped = url_escape(string)
        escaped = url_escape(string, r'^A-Za-z0-9\-._~')

    Percent encode unsafe characters in string as described in :rfc:`3986`,
    the pattern used defaults to ``^A-Za-z0-9\-._~``. ::

        # "foo%3Bbar"
        url_escape('foo;bar')
    """
    if isinstance(string, str):
        regex = _url_pattern(pattern.decode('latin-1') if isinstance(pattern, bytes) else pattern or r'^A-Za-z0-9\-._~')
        return regex.sub(lambda m: f'%{ord(m[0]):02X}', string)
    regex = _url_pattern(pattern.encode('latin-1') if isinstance(pattern, str) else pattern or rb'^A-Za-z0-9\-._~')
    return regex.sub(lambda m: b'%%%02X' % m[0][0], string)


@overload
def url_unescape(string: str) -> str: ...


@overload
def url_unescape(string: bytes) -> bytes: ...


def url_unescape(string: str | bytes) -> str | bytes:
    """::

        string = url_unescape(escaped)

    Decode percent encoded characters in string as described in :rfc:`3986`.
    A percent encoded byte in a string becomes the character with the same
    code, as in Perl. ::

        # "foo;bar"
        url_unescape('foo%3Bbar')
    """
    if isinstance(string, str):
        return re.sub(r'%([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16)), string)
    return re.sub(rb'%([0-9a-fA-F]{2})', lambda m: bytes([int(m[1], 16)]), string)


def warn(*args: object) -> None:
    """::

        warn(string)
        warn(string, value)

    Output the arguments to ``sys.stderr``, joined as Perl's ``warn`` joins a
    list, with a newline at the end unless there is one already.
    """
    msg = ''.join(map(str, args))
    if not msg.endswith('\n'):
        msg += '\n'
    print(msg, end='', file=sys.stderr)


# Characters that should be escaped in XML
XML = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}

# Numeric character references to C1 controls are remapped through windows-1252 (WHATWG HTML)
_C1 = {
    0x80: 0x20AC,
    0x82: 0x201A,
    0x83: 0x0192,
    0x84: 0x201E,
    0x85: 0x2026,
    0x86: 0x2020,
    0x87: 0x2021,
    0x88: 0x02C6,
    0x89: 0x2030,
    0x8A: 0x0160,
    0x8B: 0x2039,
    0x8C: 0x0152,
    0x8E: 0x017D,
    0x91: 0x2018,
    0x92: 0x2019,
    0x93: 0x201C,
    0x94: 0x201D,
    0x95: 0x2022,
    0x96: 0x2013,
    0x97: 0x2014,
    0x98: 0x02DC,
    0x99: 0x2122,
    0x9A: 0x0161,
    0x9B: 0x203A,
    0x9C: 0x0153,
    0x9E: 0x017E,
    0x9F: 0x0178,
}


# Not in Mojolicious: markup, as the __html__ protocol of markupsafe, Jinja and Django marks it
class Markup(Protocol):
    def __html__(self) -> str: ...


def xml_escape(string: str | Markup | None) -> str:
    """::

        escaped = xml_escape(string)

    Escape unsafe characters ``&``, ``<``, ``>``, ``"`` and ``'`` in string,
    but do not escape markup: an object with the method ``__html__``, as
    :mod:`Pyjo.String.HTML`, which gives the markup. ::

        # "&lt;div&gt;"
        xml_escape('<div>')

        # "<div>"
        from Pyjo.String.HTML import html
        xml_escape(html('<div>'))
    """
    # Unlike Mojolicious: markup is what has __html__, not every Pyjo.String.Unicode, as Mojo leaves every
    # Mojo::ByteStream, which u() and Pyjo.Collection.join make of any string
    # The markup as a plain string, which a string joins as it is, where the markup itself would escape the string
    if (markup := getattr(string, '__html__', None)) is not None:
        return str(markup())
    string = str(string) if string is not None else ''
    return re.sub(r'[&<>"\']', lambda m: XML[m[0]], string)


def xor_encode(data: bytes, key: bytes) -> bytes:
    """::

        encoded = xor_encode(data, key)

    XOR encode string with variable length key.
    """
    size = len(data)
    key = (bytes(key) * (size // len(key) + 1))[:size]
    return (int.from_bytes(data) ^ int.from_bytes(key)).to_bytes(size)


ENTITIES = {
    'Aacute;': '\xc1',
    'Aacute': '\xc1',
    'aacute;': '\xe1',
    'aacute': '\xe1',
    'Abreve;': '\u0102',
    'abreve;': '\u0103',
    'ac;': '\u223e',
    'acd;': '\u223f',
    'acE;': '\u223e\u0333',
    'Acirc;': '\xc2',
    'Acirc': '\xc2',
    'acirc;': '\xe2',
    'acirc': '\xe2',
    'acute;': '\xb4',
    'acute': '\xb4',
    'Acy;': '\u0410',
    'acy;': '\u0430',
    'AElig;': '\xc6',
    'AElig': '\xc6',
    'aelig;': '\xe6',
    'aelig': '\xe6',
    'af;': '\u2061',
    'Afr;': '\U0001d504',
    'afr;': '\U0001d51e',
    'Agrave;': '\xc0',
    'Agrave': '\xc0',
    'agrave;': '\xe0',
    'agrave': '\xe0',
    'alefsym;': '\u2135',
    'aleph;': '\u2135',
    'Alpha;': '\u0391',
    'alpha;': '\u03b1',
    'Amacr;': '\u0100',
    'amacr;': '\u0101',
    'amalg;': '\u2a3f',
    'AMP;': '\x26',
    'AMP': '\x26',
    'amp;': '\x26',
    'amp': '\x26',
    'And;': '\u2a53',
    'and;': '\u2227',
    'andand;': '\u2a55',
    'andd;': '\u2a5c',
    'andslope;': '\u2a58',
    'andv;': '\u2a5a',
    'ang;': '\u2220',
    'ange;': '\u29a4',
    'angle;': '\u2220',
    'angmsd;': '\u2221',
    'angmsdaa;': '\u29a8',
    'angmsdab;': '\u29a9',
    'angmsdac;': '\u29aa',
    'angmsdad;': '\u29ab',
    'angmsdae;': '\u29ac',
    'angmsdaf;': '\u29ad',
    'angmsdag;': '\u29ae',
    'angmsdah;': '\u29af',
    'angrt;': '\u221f',
    'angrtvb;': '\u22be',
    'angrtvbd;': '\u299d',
    'angsph;': '\u2222',
    'angst;': '\xc5',
    'angzarr;': '\u237c',
    'Aogon;': '\u0104',
    'aogon;': '\u0105',
    'Aopf;': '\U0001d538',
    'aopf;': '\U0001d552',
    'ap;': '\u2248',
    'apacir;': '\u2a6f',
    'apE;': '\u2a70',
    'ape;': '\u224a',
    'apid;': '\u224b',
    'apos;': '\x27',
    'ApplyFunction;': '\u2061',
    'approx;': '\u2248',
    'approxeq;': '\u224a',
    'Aring;': '\xc5',
    'Aring': '\xc5',
    'aring;': '\xe5',
    'aring': '\xe5',
    'Ascr;': '\U0001d49c',
    'ascr;': '\U0001d4b6',
    'Assign;': '\u2254',
    'ast;': '\x2a',
    'asymp;': '\u2248',
    'asympeq;': '\u224d',
    'Atilde;': '\xc3',
    'Atilde': '\xc3',
    'atilde;': '\xe3',
    'atilde': '\xe3',
    'Auml;': '\xc4',
    'Auml': '\xc4',
    'auml;': '\xe4',
    'auml': '\xe4',
    'awconint;': '\u2233',
    'awint;': '\u2a11',
    'backcong;': '\u224c',
    'backepsilon;': '\u03f6',
    'backprime;': '\u2035',
    'backsim;': '\u223d',
    'backsimeq;': '\u22cd',
    'Backslash;': '\u2216',
    'Barv;': '\u2ae7',
    'barvee;': '\u22bd',
    'Barwed;': '\u2306',
    'barwed;': '\u2305',
    'barwedge;': '\u2305',
    'bbrk;': '\u23b5',
    'bbrktbrk;': '\u23b6',
    'bcong;': '\u224c',
    'Bcy;': '\u0411',
    'bcy;': '\u0431',
    'bdquo;': '\u201e',
    'becaus;': '\u2235',
    'Because;': '\u2235',
    'because;': '\u2235',
    'bemptyv;': '\u29b0',
    'bepsi;': '\u03f6',
    'bernou;': '\u212c',
    'Bernoullis;': '\u212c',
    'Beta;': '\u0392',
    'beta;': '\u03b2',
    'beth;': '\u2136',
    'between;': '\u226c',
    'Bfr;': '\U0001d505',
    'bfr;': '\U0001d51f',
    'bigcap;': '\u22c2',
    'bigcirc;': '\u25ef',
    'bigcup;': '\u22c3',
    'bigodot;': '\u2a00',
    'bigoplus;': '\u2a01',
    'bigotimes;': '\u2a02',
    'bigsqcup;': '\u2a06',
    'bigstar;': '\u2605',
    'bigtriangledown;': '\u25bd',
    'bigtriangleup;': '\u25b3',
    'biguplus;': '\u2a04',
    'bigvee;': '\u22c1',
    'bigwedge;': '\u22c0',
    'bkarow;': '\u290d',
    'blacklozenge;': '\u29eb',
    'blacksquare;': '\u25aa',
    'blacktriangle;': '\u25b4',
    'blacktriangledown;': '\u25be',
    'blacktriangleleft;': '\u25c2',
    'blacktriangleright;': '\u25b8',
    'blank;': '\u2423',
    'blk12;': '\u2592',
    'blk14;': '\u2591',
    'blk34;': '\u2593',
    'block;': '\u2588',
    'bne;': '\x3d\u20e5',
    'bnequiv;': '\u2261\u20e5',
    'bNot;': '\u2aed',
    'bnot;': '\u2310',
    'Bopf;': '\U0001d539',
    'bopf;': '\U0001d553',
    'bot;': '\u22a5',
    'bottom;': '\u22a5',
    'bowtie;': '\u22c8',
    'boxbox;': '\u29c9',
    'boxDL;': '\u2557',
    'boxDl;': '\u2556',
    'boxdL;': '\u2555',
    'boxdl;': '\u2510',
    'boxDR;': '\u2554',
    'boxDr;': '\u2553',
    'boxdR;': '\u2552',
    'boxdr;': '\u250c',
    'boxH;': '\u2550',
    'boxh;': '\u2500',
    'boxHD;': '\u2566',
    'boxHd;': '\u2564',
    'boxhD;': '\u2565',
    'boxhd;': '\u252c',
    'boxHU;': '\u2569',
    'boxHu;': '\u2567',
    'boxhU;': '\u2568',
    'boxhu;': '\u2534',
    'boxminus;': '\u229f',
    'boxplus;': '\u229e',
    'boxtimes;': '\u22a0',
    'boxUL;': '\u255d',
    'boxUl;': '\u255c',
    'boxuL;': '\u255b',
    'boxul;': '\u2518',
    'boxUR;': '\u255a',
    'boxUr;': '\u2559',
    'boxuR;': '\u2558',
    'boxur;': '\u2514',
    'boxV;': '\u2551',
    'boxv;': '\u2502',
    'boxVH;': '\u256c',
    'boxVh;': '\u256b',
    'boxvH;': '\u256a',
    'boxvh;': '\u253c',
    'boxVL;': '\u2563',
    'boxVl;': '\u2562',
    'boxvL;': '\u2561',
    'boxvl;': '\u2524',
    'boxVR;': '\u2560',
    'boxVr;': '\u255f',
    'boxvR;': '\u255e',
    'boxvr;': '\u251c',
    'bprime;': '\u2035',
    'Breve;': '\u02d8',
    'breve;': '\u02d8',
    'brvbar;': '\xa6',
    'brvbar': '\xa6',
    'Bscr;': '\u212c',
    'bscr;': '\U0001d4b7',
    'bsemi;': '\u204f',
    'bsim;': '\u223d',
    'bsime;': '\u22cd',
    'bsol;': '\x5c',
    'bsolb;': '\u29c5',
    'bsolhsub;': '\u27c8',
    'bull;': '\u2022',
    'bullet;': '\u2022',
    'bump;': '\u224e',
    'bumpE;': '\u2aae',
    'bumpe;': '\u224f',
    'Bumpeq;': '\u224e',
    'bumpeq;': '\u224f',
    'Cacute;': '\u0106',
    'cacute;': '\u0107',
    'Cap;': '\u22d2',
    'cap;': '\u2229',
    'capand;': '\u2a44',
    'capbrcup;': '\u2a49',
    'capcap;': '\u2a4b',
    'capcup;': '\u2a47',
    'capdot;': '\u2a40',
    'CapitalDifferentialD;': '\u2145',
    'caps;': '\u2229\ufe00',
    'caret;': '\u2041',
    'caron;': '\u02c7',
    'Cayleys;': '\u212d',
    'ccaps;': '\u2a4d',
    'Ccaron;': '\u010c',
    'ccaron;': '\u010d',
    'Ccedil;': '\xc7',
    'Ccedil': '\xc7',
    'ccedil;': '\xe7',
    'ccedil': '\xe7',
    'Ccirc;': '\u0108',
    'ccirc;': '\u0109',
    'Cconint;': '\u2230',
    'ccups;': '\u2a4c',
    'ccupssm;': '\u2a50',
    'Cdot;': '\u010a',
    'cdot;': '\u010b',
    'cedil;': '\xb8',
    'cedil': '\xb8',
    'Cedilla;': '\xb8',
    'cemptyv;': '\u29b2',
    'cent;': '\xa2',
    'cent': '\xa2',
    'CenterDot;': '\xb7',
    'centerdot;': '\xb7',
    'Cfr;': '\u212d',
    'cfr;': '\U0001d520',
    'CHcy;': '\u0427',
    'chcy;': '\u0447',
    'check;': '\u2713',
    'checkmark;': '\u2713',
    'Chi;': '\u03a7',
    'chi;': '\u03c7',
    'cir;': '\u25cb',
    'circ;': '\u02c6',
    'circeq;': '\u2257',
    'circlearrowleft;': '\u21ba',
    'circlearrowright;': '\u21bb',
    'circledast;': '\u229b',
    'circledcirc;': '\u229a',
    'circleddash;': '\u229d',
    'CircleDot;': '\u2299',
    'circledR;': '\xae',
    'circledS;': '\u24c8',
    'CircleMinus;': '\u2296',
    'CirclePlus;': '\u2295',
    'CircleTimes;': '\u2297',
    'cirE;': '\u29c3',
    'cire;': '\u2257',
    'cirfnint;': '\u2a10',
    'cirmid;': '\u2aef',
    'cirscir;': '\u29c2',
    'ClockwiseContourIntegral;': '\u2232',
    'CloseCurlyDoubleQuote;': '\u201d',
    'CloseCurlyQuote;': '\u2019',
    'clubs;': '\u2663',
    'clubsuit;': '\u2663',
    'Colon;': '\u2237',
    'colon;': '\x3a',
    'Colone;': '\u2a74',
    'colone;': '\u2254',
    'coloneq;': '\u2254',
    'comma;': '\x2c',
    'commat;': '\x40',
    'comp;': '\u2201',
    'compfn;': '\u2218',
    'complement;': '\u2201',
    'complexes;': '\u2102',
    'cong;': '\u2245',
    'congdot;': '\u2a6d',
    'Congruent;': '\u2261',
    'Conint;': '\u222f',
    'conint;': '\u222e',
    'ContourIntegral;': '\u222e',
    'Copf;': '\u2102',
    'copf;': '\U0001d554',
    'coprod;': '\u2210',
    'Coproduct;': '\u2210',
    'COPY;': '\xa9',
    'COPY': '\xa9',
    'copy;': '\xa9',
    'copy': '\xa9',
    'copysr;': '\u2117',
    'CounterClockwiseContourIntegral;': '\u2233',
    'crarr;': '\u21b5',
    'Cross;': '\u2a2f',
    'cross;': '\u2717',
    'Cscr;': '\U0001d49e',
    'cscr;': '\U0001d4b8',
    'csub;': '\u2acf',
    'csube;': '\u2ad1',
    'csup;': '\u2ad0',
    'csupe;': '\u2ad2',
    'ctdot;': '\u22ef',
    'cudarrl;': '\u2938',
    'cudarrr;': '\u2935',
    'cuepr;': '\u22de',
    'cuesc;': '\u22df',
    'cularr;': '\u21b6',
    'cularrp;': '\u293d',
    'Cup;': '\u22d3',
    'cup;': '\u222a',
    'cupbrcap;': '\u2a48',
    'CupCap;': '\u224d',
    'cupcap;': '\u2a46',
    'cupcup;': '\u2a4a',
    'cupdot;': '\u228d',
    'cupor;': '\u2a45',
    'cups;': '\u222a\ufe00',
    'curarr;': '\u21b7',
    'curarrm;': '\u293c',
    'curlyeqprec;': '\u22de',
    'curlyeqsucc;': '\u22df',
    'curlyvee;': '\u22ce',
    'curlywedge;': '\u22cf',
    'curren;': '\xa4',
    'curren': '\xa4',
    'curvearrowleft;': '\u21b6',
    'curvearrowright;': '\u21b7',
    'cuvee;': '\u22ce',
    'cuwed;': '\u22cf',
    'cwconint;': '\u2232',
    'cwint;': '\u2231',
    'cylcty;': '\u232d',
    'Dagger;': '\u2021',
    'dagger;': '\u2020',
    'daleth;': '\u2138',
    'Darr;': '\u21a1',
    'dArr;': '\u21d3',
    'darr;': '\u2193',
    'dash;': '\u2010',
    'Dashv;': '\u2ae4',
    'dashv;': '\u22a3',
    'dbkarow;': '\u290f',
    'dblac;': '\u02dd',
    'Dcaron;': '\u010e',
    'dcaron;': '\u010f',
    'Dcy;': '\u0414',
    'dcy;': '\u0434',
    'DD;': '\u2145',
    'dd;': '\u2146',
    'ddagger;': '\u2021',
    'ddarr;': '\u21ca',
    'DDotrahd;': '\u2911',
    'ddotseq;': '\u2a77',
    'deg;': '\xb0',
    'deg': '\xb0',
    'Del;': '\u2207',
    'Delta;': '\u0394',
    'delta;': '\u03b4',
    'demptyv;': '\u29b1',
    'dfisht;': '\u297f',
    'Dfr;': '\U0001d507',
    'dfr;': '\U0001d521',
    'dHar;': '\u2965',
    'dharl;': '\u21c3',
    'dharr;': '\u21c2',
    'DiacriticalAcute;': '\xb4',
    'DiacriticalDot;': '\u02d9',
    'DiacriticalDoubleAcute;': '\u02dd',
    'DiacriticalGrave;': '\x60',
    'DiacriticalTilde;': '\u02dc',
    'diam;': '\u22c4',
    'Diamond;': '\u22c4',
    'diamond;': '\u22c4',
    'diamondsuit;': '\u2666',
    'diams;': '\u2666',
    'die;': '\xa8',
    'DifferentialD;': '\u2146',
    'digamma;': '\u03dd',
    'disin;': '\u22f2',
    'div;': '\xf7',
    'divide;': '\xf7',
    'divide': '\xf7',
    'divideontimes;': '\u22c7',
    'divonx;': '\u22c7',
    'DJcy;': '\u0402',
    'djcy;': '\u0452',
    'dlcorn;': '\u231e',
    'dlcrop;': '\u230d',
    'dollar;': '\x24',
    'Dopf;': '\U0001d53b',
    'dopf;': '\U0001d555',
    'Dot;': '\xa8',
    'dot;': '\u02d9',
    'DotDot;': '\u20dc',
    'doteq;': '\u2250',
    'doteqdot;': '\u2251',
    'DotEqual;': '\u2250',
    'dotminus;': '\u2238',
    'dotplus;': '\u2214',
    'dotsquare;': '\u22a1',
    'doublebarwedge;': '\u2306',
    'DoubleContourIntegral;': '\u222f',
    'DoubleDot;': '\xa8',
    'DoubleDownArrow;': '\u21d3',
    'DoubleLeftArrow;': '\u21d0',
    'DoubleLeftRightArrow;': '\u21d4',
    'DoubleLeftTee;': '\u2ae4',
    'DoubleLongLeftArrow;': '\u27f8',
    'DoubleLongLeftRightArrow;': '\u27fa',
    'DoubleLongRightArrow;': '\u27f9',
    'DoubleRightArrow;': '\u21d2',
    'DoubleRightTee;': '\u22a8',
    'DoubleUpArrow;': '\u21d1',
    'DoubleUpDownArrow;': '\u21d5',
    'DoubleVerticalBar;': '\u2225',
    'DownArrow;': '\u2193',
    'Downarrow;': '\u21d3',
    'downarrow;': '\u2193',
    'DownArrowBar;': '\u2913',
    'DownArrowUpArrow;': '\u21f5',
    'DownBreve;': '\u0311',
    'downdownarrows;': '\u21ca',
    'downharpoonleft;': '\u21c3',
    'downharpoonright;': '\u21c2',
    'DownLeftRightVector;': '\u2950',
    'DownLeftTeeVector;': '\u295e',
    'DownLeftVector;': '\u21bd',
    'DownLeftVectorBar;': '\u2956',
    'DownRightTeeVector;': '\u295f',
    'DownRightVector;': '\u21c1',
    'DownRightVectorBar;': '\u2957',
    'DownTee;': '\u22a4',
    'DownTeeArrow;': '\u21a7',
    'drbkarow;': '\u2910',
    'drcorn;': '\u231f',
    'drcrop;': '\u230c',
    'Dscr;': '\U0001d49f',
    'dscr;': '\U0001d4b9',
    'DScy;': '\u0405',
    'dscy;': '\u0455',
    'dsol;': '\u29f6',
    'Dstrok;': '\u0110',
    'dstrok;': '\u0111',
    'dtdot;': '\u22f1',
    'dtri;': '\u25bf',
    'dtrif;': '\u25be',
    'duarr;': '\u21f5',
    'duhar;': '\u296f',
    'dwangle;': '\u29a6',
    'DZcy;': '\u040f',
    'dzcy;': '\u045f',
    'dzigrarr;': '\u27ff',
    'Eacute;': '\xc9',
    'Eacute': '\xc9',
    'eacute;': '\xe9',
    'eacute': '\xe9',
    'easter;': '\u2a6e',
    'Ecaron;': '\u011a',
    'ecaron;': '\u011b',
    'ecir;': '\u2256',
    'Ecirc;': '\xca',
    'Ecirc': '\xca',
    'ecirc;': '\xea',
    'ecirc': '\xea',
    'ecolon;': '\u2255',
    'Ecy;': '\u042d',
    'ecy;': '\u044d',
    'eDDot;': '\u2a77',
    'Edot;': '\u0116',
    'eDot;': '\u2251',
    'edot;': '\u0117',
    'ee;': '\u2147',
    'efDot;': '\u2252',
    'Efr;': '\U0001d508',
    'efr;': '\U0001d522',
    'eg;': '\u2a9a',
    'Egrave;': '\xc8',
    'Egrave': '\xc8',
    'egrave;': '\xe8',
    'egrave': '\xe8',
    'egs;': '\u2a96',
    'egsdot;': '\u2a98',
    'el;': '\u2a99',
    'Element;': '\u2208',
    'elinters;': '\u23e7',
    'ell;': '\u2113',
    'els;': '\u2a95',
    'elsdot;': '\u2a97',
    'Emacr;': '\u0112',
    'emacr;': '\u0113',
    'empty;': '\u2205',
    'emptyset;': '\u2205',
    'EmptySmallSquare;': '\u25fb',
    'emptyv;': '\u2205',
    'EmptyVerySmallSquare;': '\u25ab',
    'emsp;': '\u2003',
    'emsp13;': '\u2004',
    'emsp14;': '\u2005',
    'ENG;': '\u014a',
    'eng;': '\u014b',
    'ensp;': '\u2002',
    'Eogon;': '\u0118',
    'eogon;': '\u0119',
    'Eopf;': '\U0001d53c',
    'eopf;': '\U0001d556',
    'epar;': '\u22d5',
    'eparsl;': '\u29e3',
    'eplus;': '\u2a71',
    'epsi;': '\u03b5',
    'Epsilon;': '\u0395',
    'epsilon;': '\u03b5',
    'epsiv;': '\u03f5',
    'eqcirc;': '\u2256',
    'eqcolon;': '\u2255',
    'eqsim;': '\u2242',
    'eqslantgtr;': '\u2a96',
    'eqslantless;': '\u2a95',
    'Equal;': '\u2a75',
    'equals;': '\x3d',
    'EqualTilde;': '\u2242',
    'equest;': '\u225f',
    'Equilibrium;': '\u21cc',
    'equiv;': '\u2261',
    'equivDD;': '\u2a78',
    'eqvparsl;': '\u29e5',
    'erarr;': '\u2971',
    'erDot;': '\u2253',
    'Escr;': '\u2130',
    'escr;': '\u212f',
    'esdot;': '\u2250',
    'Esim;': '\u2a73',
    'esim;': '\u2242',
    'Eta;': '\u0397',
    'eta;': '\u03b7',
    'ETH;': '\xd0',
    'ETH': '\xd0',
    'eth;': '\xf0',
    'eth': '\xf0',
    'Euml;': '\xcb',
    'Euml': '\xcb',
    'euml;': '\xeb',
    'euml': '\xeb',
    'euro;': '\u20ac',
    'excl;': '\x21',
    'exist;': '\u2203',
    'Exists;': '\u2203',
    'expectation;': '\u2130',
    'ExponentialE;': '\u2147',
    'exponentiale;': '\u2147',
    'fallingdotseq;': '\u2252',
    'Fcy;': '\u0424',
    'fcy;': '\u0444',
    'female;': '\u2640',
    'ffilig;': '\ufb03',
    'fflig;': '\ufb00',
    'ffllig;': '\ufb04',
    'Ffr;': '\U0001d509',
    'ffr;': '\U0001d523',
    'filig;': '\ufb01',
    'FilledSmallSquare;': '\u25fc',
    'FilledVerySmallSquare;': '\u25aa',
    'fjlig;': '\x66\x6a',
    'flat;': '\u266d',
    'fllig;': '\ufb02',
    'fltns;': '\u25b1',
    'fnof;': '\u0192',
    'Fopf;': '\U0001d53d',
    'fopf;': '\U0001d557',
    'ForAll;': '\u2200',
    'forall;': '\u2200',
    'fork;': '\u22d4',
    'forkv;': '\u2ad9',
    'Fouriertrf;': '\u2131',
    'fpartint;': '\u2a0d',
    'frac12;': '\xbd',
    'frac12': '\xbd',
    'frac13;': '\u2153',
    'frac14;': '\xbc',
    'frac14': '\xbc',
    'frac15;': '\u2155',
    'frac16;': '\u2159',
    'frac18;': '\u215b',
    'frac23;': '\u2154',
    'frac25;': '\u2156',
    'frac34;': '\xbe',
    'frac34': '\xbe',
    'frac35;': '\u2157',
    'frac38;': '\u215c',
    'frac45;': '\u2158',
    'frac56;': '\u215a',
    'frac58;': '\u215d',
    'frac78;': '\u215e',
    'frasl;': '\u2044',
    'frown;': '\u2322',
    'Fscr;': '\u2131',
    'fscr;': '\U0001d4bb',
    'gacute;': '\u01f5',
    'Gamma;': '\u0393',
    'gamma;': '\u03b3',
    'Gammad;': '\u03dc',
    'gammad;': '\u03dd',
    'gap;': '\u2a86',
    'Gbreve;': '\u011e',
    'gbreve;': '\u011f',
    'Gcedil;': '\u0122',
    'Gcirc;': '\u011c',
    'gcirc;': '\u011d',
    'Gcy;': '\u0413',
    'gcy;': '\u0433',
    'Gdot;': '\u0120',
    'gdot;': '\u0121',
    'gE;': '\u2267',
    'ge;': '\u2265',
    'gEl;': '\u2a8c',
    'gel;': '\u22db',
    'geq;': '\u2265',
    'geqq;': '\u2267',
    'geqslant;': '\u2a7e',
    'ges;': '\u2a7e',
    'gescc;': '\u2aa9',
    'gesdot;': '\u2a80',
    'gesdoto;': '\u2a82',
    'gesdotol;': '\u2a84',
    'gesl;': '\u22db\ufe00',
    'gesles;': '\u2a94',
    'Gfr;': '\U0001d50a',
    'gfr;': '\U0001d524',
    'Gg;': '\u22d9',
    'gg;': '\u226b',
    'ggg;': '\u22d9',
    'gimel;': '\u2137',
    'GJcy;': '\u0403',
    'gjcy;': '\u0453',
    'gl;': '\u2277',
    'gla;': '\u2aa5',
    'glE;': '\u2a92',
    'glj;': '\u2aa4',
    'gnap;': '\u2a8a',
    'gnapprox;': '\u2a8a',
    'gnE;': '\u2269',
    'gne;': '\u2a88',
    'gneq;': '\u2a88',
    'gneqq;': '\u2269',
    'gnsim;': '\u22e7',
    'Gopf;': '\U0001d53e',
    'gopf;': '\U0001d558',
    'grave;': '\x60',
    'GreaterEqual;': '\u2265',
    'GreaterEqualLess;': '\u22db',
    'GreaterFullEqual;': '\u2267',
    'GreaterGreater;': '\u2aa2',
    'GreaterLess;': '\u2277',
    'GreaterSlantEqual;': '\u2a7e',
    'GreaterTilde;': '\u2273',
    'Gscr;': '\U0001d4a2',
    'gscr;': '\u210a',
    'gsim;': '\u2273',
    'gsime;': '\u2a8e',
    'gsiml;': '\u2a90',
    'GT;': '\x3e',
    'GT': '\x3e',
    'Gt;': '\u226b',
    'gt;': '\x3e',
    'gt': '\x3e',
    'gtcc;': '\u2aa7',
    'gtcir;': '\u2a7a',
    'gtdot;': '\u22d7',
    'gtlPar;': '\u2995',
    'gtquest;': '\u2a7c',
    'gtrapprox;': '\u2a86',
    'gtrarr;': '\u2978',
    'gtrdot;': '\u22d7',
    'gtreqless;': '\u22db',
    'gtreqqless;': '\u2a8c',
    'gtrless;': '\u2277',
    'gtrsim;': '\u2273',
    'gvertneqq;': '\u2269\ufe00',
    'gvnE;': '\u2269\ufe00',
    'Hacek;': '\u02c7',
    'hairsp;': '\u200a',
    'half;': '\xbd',
    'hamilt;': '\u210b',
    'HARDcy;': '\u042a',
    'hardcy;': '\u044a',
    'hArr;': '\u21d4',
    'harr;': '\u2194',
    'harrcir;': '\u2948',
    'harrw;': '\u21ad',
    'Hat;': '\x5e',
    'hbar;': '\u210f',
    'Hcirc;': '\u0124',
    'hcirc;': '\u0125',
    'hearts;': '\u2665',
    'heartsuit;': '\u2665',
    'hellip;': '\u2026',
    'hercon;': '\u22b9',
    'Hfr;': '\u210c',
    'hfr;': '\U0001d525',
    'HilbertSpace;': '\u210b',
    'hksearow;': '\u2925',
    'hkswarow;': '\u2926',
    'hoarr;': '\u21ff',
    'homtht;': '\u223b',
    'hookleftarrow;': '\u21a9',
    'hookrightarrow;': '\u21aa',
    'Hopf;': '\u210d',
    'hopf;': '\U0001d559',
    'horbar;': '\u2015',
    'HorizontalLine;': '\u2500',
    'Hscr;': '\u210b',
    'hscr;': '\U0001d4bd',
    'hslash;': '\u210f',
    'Hstrok;': '\u0126',
    'hstrok;': '\u0127',
    'HumpDownHump;': '\u224e',
    'HumpEqual;': '\u224f',
    'hybull;': '\u2043',
    'hyphen;': '\u2010',
    'Iacute;': '\xcd',
    'Iacute': '\xcd',
    'iacute;': '\xed',
    'iacute': '\xed',
    'ic;': '\u2063',
    'Icirc;': '\xce',
    'Icirc': '\xce',
    'icirc;': '\xee',
    'icirc': '\xee',
    'Icy;': '\u0418',
    'icy;': '\u0438',
    'Idot;': '\u0130',
    'IEcy;': '\u0415',
    'iecy;': '\u0435',
    'iexcl;': '\xa1',
    'iexcl': '\xa1',
    'iff;': '\u21d4',
    'Ifr;': '\u2111',
    'ifr;': '\U0001d526',
    'Igrave;': '\xcc',
    'Igrave': '\xcc',
    'igrave;': '\xec',
    'igrave': '\xec',
    'ii;': '\u2148',
    'iiiint;': '\u2a0c',
    'iiint;': '\u222d',
    'iinfin;': '\u29dc',
    'iiota;': '\u2129',
    'IJlig;': '\u0132',
    'ijlig;': '\u0133',
    'Im;': '\u2111',
    'Imacr;': '\u012a',
    'imacr;': '\u012b',
    'image;': '\u2111',
    'ImaginaryI;': '\u2148',
    'imagline;': '\u2110',
    'imagpart;': '\u2111',
    'imath;': '\u0131',
    'imof;': '\u22b7',
    'imped;': '\u01b5',
    'Implies;': '\u21d2',
    'in;': '\u2208',
    'incare;': '\u2105',
    'infin;': '\u221e',
    'infintie;': '\u29dd',
    'inodot;': '\u0131',
    'Int;': '\u222c',
    'int;': '\u222b',
    'intcal;': '\u22ba',
    'integers;': '\u2124',
    'Integral;': '\u222b',
    'intercal;': '\u22ba',
    'Intersection;': '\u22c2',
    'intlarhk;': '\u2a17',
    'intprod;': '\u2a3c',
    'InvisibleComma;': '\u2063',
    'InvisibleTimes;': '\u2062',
    'IOcy;': '\u0401',
    'iocy;': '\u0451',
    'Iogon;': '\u012e',
    'iogon;': '\u012f',
    'Iopf;': '\U0001d540',
    'iopf;': '\U0001d55a',
    'Iota;': '\u0399',
    'iota;': '\u03b9',
    'iprod;': '\u2a3c',
    'iquest;': '\xbf',
    'iquest': '\xbf',
    'Iscr;': '\u2110',
    'iscr;': '\U0001d4be',
    'isin;': '\u2208',
    'isindot;': '\u22f5',
    'isinE;': '\u22f9',
    'isins;': '\u22f4',
    'isinsv;': '\u22f3',
    'isinv;': '\u2208',
    'it;': '\u2062',
    'Itilde;': '\u0128',
    'itilde;': '\u0129',
    'Iukcy;': '\u0406',
    'iukcy;': '\u0456',
    'Iuml;': '\xcf',
    'Iuml': '\xcf',
    'iuml;': '\xef',
    'iuml': '\xef',
    'Jcirc;': '\u0134',
    'jcirc;': '\u0135',
    'Jcy;': '\u0419',
    'jcy;': '\u0439',
    'Jfr;': '\U0001d50d',
    'jfr;': '\U0001d527',
    'jmath;': '\u0237',
    'Jopf;': '\U0001d541',
    'jopf;': '\U0001d55b',
    'Jscr;': '\U0001d4a5',
    'jscr;': '\U0001d4bf',
    'Jsercy;': '\u0408',
    'jsercy;': '\u0458',
    'Jukcy;': '\u0404',
    'jukcy;': '\u0454',
    'Kappa;': '\u039a',
    'kappa;': '\u03ba',
    'kappav;': '\u03f0',
    'Kcedil;': '\u0136',
    'kcedil;': '\u0137',
    'Kcy;': '\u041a',
    'kcy;': '\u043a',
    'Kfr;': '\U0001d50e',
    'kfr;': '\U0001d528',
    'kgreen;': '\u0138',
    'KHcy;': '\u0425',
    'khcy;': '\u0445',
    'KJcy;': '\u040c',
    'kjcy;': '\u045c',
    'Kopf;': '\U0001d542',
    'kopf;': '\U0001d55c',
    'Kscr;': '\U0001d4a6',
    'kscr;': '\U0001d4c0',
    'lAarr;': '\u21da',
    'Lacute;': '\u0139',
    'lacute;': '\u013a',
    'laemptyv;': '\u29b4',
    'lagran;': '\u2112',
    'Lambda;': '\u039b',
    'lambda;': '\u03bb',
    'Lang;': '\u27ea',
    'lang;': '\u27e8',
    'langd;': '\u2991',
    'langle;': '\u27e8',
    'lap;': '\u2a85',
    'Laplacetrf;': '\u2112',
    'laquo;': '\xab',
    'laquo': '\xab',
    'Larr;': '\u219e',
    'lArr;': '\u21d0',
    'larr;': '\u2190',
    'larrb;': '\u21e4',
    'larrbfs;': '\u291f',
    'larrfs;': '\u291d',
    'larrhk;': '\u21a9',
    'larrlp;': '\u21ab',
    'larrpl;': '\u2939',
    'larrsim;': '\u2973',
    'larrtl;': '\u21a2',
    'lat;': '\u2aab',
    'lAtail;': '\u291b',
    'latail;': '\u2919',
    'late;': '\u2aad',
    'lates;': '\u2aad\ufe00',
    'lBarr;': '\u290e',
    'lbarr;': '\u290c',
    'lbbrk;': '\u2772',
    'lbrace;': '\x7b',
    'lbrack;': '\x5b',
    'lbrke;': '\u298b',
    'lbrksld;': '\u298f',
    'lbrkslu;': '\u298d',
    'Lcaron;': '\u013d',
    'lcaron;': '\u013e',
    'Lcedil;': '\u013b',
    'lcedil;': '\u013c',
    'lceil;': '\u2308',
    'lcub;': '\x7b',
    'Lcy;': '\u041b',
    'lcy;': '\u043b',
    'ldca;': '\u2936',
    'ldquo;': '\u201c',
    'ldquor;': '\u201e',
    'ldrdhar;': '\u2967',
    'ldrushar;': '\u294b',
    'ldsh;': '\u21b2',
    'lE;': '\u2266',
    'le;': '\u2264',
    'LeftAngleBracket;': '\u27e8',
    'LeftArrow;': '\u2190',
    'Leftarrow;': '\u21d0',
    'leftarrow;': '\u2190',
    'LeftArrowBar;': '\u21e4',
    'LeftArrowRightArrow;': '\u21c6',
    'leftarrowtail;': '\u21a2',
    'LeftCeiling;': '\u2308',
    'LeftDoubleBracket;': '\u27e6',
    'LeftDownTeeVector;': '\u2961',
    'LeftDownVector;': '\u21c3',
    'LeftDownVectorBar;': '\u2959',
    'LeftFloor;': '\u230a',
    'leftharpoondown;': '\u21bd',
    'leftharpoonup;': '\u21bc',
    'leftleftarrows;': '\u21c7',
    'LeftRightArrow;': '\u2194',
    'Leftrightarrow;': '\u21d4',
    'leftrightarrow;': '\u2194',
    'leftrightarrows;': '\u21c6',
    'leftrightharpoons;': '\u21cb',
    'leftrightsquigarrow;': '\u21ad',
    'LeftRightVector;': '\u294e',
    'LeftTee;': '\u22a3',
    'LeftTeeArrow;': '\u21a4',
    'LeftTeeVector;': '\u295a',
    'leftthreetimes;': '\u22cb',
    'LeftTriangle;': '\u22b2',
    'LeftTriangleBar;': '\u29cf',
    'LeftTriangleEqual;': '\u22b4',
    'LeftUpDownVector;': '\u2951',
    'LeftUpTeeVector;': '\u2960',
    'LeftUpVector;': '\u21bf',
    'LeftUpVectorBar;': '\u2958',
    'LeftVector;': '\u21bc',
    'LeftVectorBar;': '\u2952',
    'lEg;': '\u2a8b',
    'leg;': '\u22da',
    'leq;': '\u2264',
    'leqq;': '\u2266',
    'leqslant;': '\u2a7d',
    'les;': '\u2a7d',
    'lescc;': '\u2aa8',
    'lesdot;': '\u2a7f',
    'lesdoto;': '\u2a81',
    'lesdotor;': '\u2a83',
    'lesg;': '\u22da\ufe00',
    'lesges;': '\u2a93',
    'lessapprox;': '\u2a85',
    'lessdot;': '\u22d6',
    'lesseqgtr;': '\u22da',
    'lesseqqgtr;': '\u2a8b',
    'LessEqualGreater;': '\u22da',
    'LessFullEqual;': '\u2266',
    'LessGreater;': '\u2276',
    'lessgtr;': '\u2276',
    'LessLess;': '\u2aa1',
    'lesssim;': '\u2272',
    'LessSlantEqual;': '\u2a7d',
    'LessTilde;': '\u2272',
    'lfisht;': '\u297c',
    'lfloor;': '\u230a',
    'Lfr;': '\U0001d50f',
    'lfr;': '\U0001d529',
    'lg;': '\u2276',
    'lgE;': '\u2a91',
    'lHar;': '\u2962',
    'lhard;': '\u21bd',
    'lharu;': '\u21bc',
    'lharul;': '\u296a',
    'lhblk;': '\u2584',
    'LJcy;': '\u0409',
    'ljcy;': '\u0459',
    'Ll;': '\u22d8',
    'll;': '\u226a',
    'llarr;': '\u21c7',
    'llcorner;': '\u231e',
    'Lleftarrow;': '\u21da',
    'llhard;': '\u296b',
    'lltri;': '\u25fa',
    'Lmidot;': '\u013f',
    'lmidot;': '\u0140',
    'lmoust;': '\u23b0',
    'lmoustache;': '\u23b0',
    'lnap;': '\u2a89',
    'lnapprox;': '\u2a89',
    'lnE;': '\u2268',
    'lne;': '\u2a87',
    'lneq;': '\u2a87',
    'lneqq;': '\u2268',
    'lnsim;': '\u22e6',
    'loang;': '\u27ec',
    'loarr;': '\u21fd',
    'lobrk;': '\u27e6',
    'LongLeftArrow;': '\u27f5',
    'Longleftarrow;': '\u27f8',
    'longleftarrow;': '\u27f5',
    'LongLeftRightArrow;': '\u27f7',
    'Longleftrightarrow;': '\u27fa',
    'longleftrightarrow;': '\u27f7',
    'longmapsto;': '\u27fc',
    'LongRightArrow;': '\u27f6',
    'Longrightarrow;': '\u27f9',
    'longrightarrow;': '\u27f6',
    'looparrowleft;': '\u21ab',
    'looparrowright;': '\u21ac',
    'lopar;': '\u2985',
    'Lopf;': '\U0001d543',
    'lopf;': '\U0001d55d',
    'loplus;': '\u2a2d',
    'lotimes;': '\u2a34',
    'lowast;': '\u2217',
    'lowbar;': '\x5f',
    'LowerLeftArrow;': '\u2199',
    'LowerRightArrow;': '\u2198',
    'loz;': '\u25ca',
    'lozenge;': '\u25ca',
    'lozf;': '\u29eb',
    'lpar;': '\x28',
    'lparlt;': '\u2993',
    'lrarr;': '\u21c6',
    'lrcorner;': '\u231f',
    'lrhar;': '\u21cb',
    'lrhard;': '\u296d',
    'lrm;': '\u200e',
    'lrtri;': '\u22bf',
    'lsaquo;': '\u2039',
    'Lscr;': '\u2112',
    'lscr;': '\U0001d4c1',
    'Lsh;': '\u21b0',
    'lsh;': '\u21b0',
    'lsim;': '\u2272',
    'lsime;': '\u2a8d',
    'lsimg;': '\u2a8f',
    'lsqb;': '\x5b',
    'lsquo;': '\u2018',
    'lsquor;': '\u201a',
    'Lstrok;': '\u0141',
    'lstrok;': '\u0142',
    'LT;': '\x3c',
    'LT': '\x3c',
    'Lt;': '\u226a',
    'lt;': '\x3c',
    'lt': '\x3c',
    'ltcc;': '\u2aa6',
    'ltcir;': '\u2a79',
    'ltdot;': '\u22d6',
    'lthree;': '\u22cb',
    'ltimes;': '\u22c9',
    'ltlarr;': '\u2976',
    'ltquest;': '\u2a7b',
    'ltri;': '\u25c3',
    'ltrie;': '\u22b4',
    'ltrif;': '\u25c2',
    'ltrPar;': '\u2996',
    'lurdshar;': '\u294a',
    'luruhar;': '\u2966',
    'lvertneqq;': '\u2268\ufe00',
    'lvnE;': '\u2268\ufe00',
    'macr;': '\xaf',
    'macr': '\xaf',
    'male;': '\u2642',
    'malt;': '\u2720',
    'maltese;': '\u2720',
    'Map;': '\u2905',
    'map;': '\u21a6',
    'mapsto;': '\u21a6',
    'mapstodown;': '\u21a7',
    'mapstoleft;': '\u21a4',
    'mapstoup;': '\u21a5',
    'marker;': '\u25ae',
    'mcomma;': '\u2a29',
    'Mcy;': '\u041c',
    'mcy;': '\u043c',
    'mdash;': '\u2014',
    'mDDot;': '\u223a',
    'measuredangle;': '\u2221',
    'MediumSpace;': '\u205f',
    'Mellintrf;': '\u2133',
    'Mfr;': '\U0001d510',
    'mfr;': '\U0001d52a',
    'mho;': '\u2127',
    'micro;': '\xb5',
    'micro': '\xb5',
    'mid;': '\u2223',
    'midast;': '\x2a',
    'midcir;': '\u2af0',
    'middot;': '\xb7',
    'middot': '\xb7',
    'minus;': '\u2212',
    'minusb;': '\u229f',
    'minusd;': '\u2238',
    'minusdu;': '\u2a2a',
    'MinusPlus;': '\u2213',
    'mlcp;': '\u2adb',
    'mldr;': '\u2026',
    'mnplus;': '\u2213',
    'models;': '\u22a7',
    'Mopf;': '\U0001d544',
    'mopf;': '\U0001d55e',
    'mp;': '\u2213',
    'Mscr;': '\u2133',
    'mscr;': '\U0001d4c2',
    'mstpos;': '\u223e',
    'Mu;': '\u039c',
    'mu;': '\u03bc',
    'multimap;': '\u22b8',
    'mumap;': '\u22b8',
    'nabla;': '\u2207',
    'Nacute;': '\u0143',
    'nacute;': '\u0144',
    'nang;': '\u2220\u20d2',
    'nap;': '\u2249',
    'napE;': '\u2a70\u0338',
    'napid;': '\u224b\u0338',
    'napos;': '\u0149',
    'napprox;': '\u2249',
    'natur;': '\u266e',
    'natural;': '\u266e',
    'naturals;': '\u2115',
    'nbsp;': '\xa0',
    'nbsp': '\xa0',
    'nbump;': '\u224e\u0338',
    'nbumpe;': '\u224f\u0338',
    'ncap;': '\u2a43',
    'Ncaron;': '\u0147',
    'ncaron;': '\u0148',
    'Ncedil;': '\u0145',
    'ncedil;': '\u0146',
    'ncong;': '\u2247',
    'ncongdot;': '\u2a6d\u0338',
    'ncup;': '\u2a42',
    'Ncy;': '\u041d',
    'ncy;': '\u043d',
    'ndash;': '\u2013',
    'ne;': '\u2260',
    'nearhk;': '\u2924',
    'neArr;': '\u21d7',
    'nearr;': '\u2197',
    'nearrow;': '\u2197',
    'nedot;': '\u2250\u0338',
    'NegativeMediumSpace;': '\u200b',
    'NegativeThickSpace;': '\u200b',
    'NegativeThinSpace;': '\u200b',
    'NegativeVeryThinSpace;': '\u200b',
    'nequiv;': '\u2262',
    'nesear;': '\u2928',
    'nesim;': '\u2242\u0338',
    'NestedGreaterGreater;': '\u226b',
    'NestedLessLess;': '\u226a',
    'NewLine;': '\x0a',
    'nexist;': '\u2204',
    'nexists;': '\u2204',
    'Nfr;': '\U0001d511',
    'nfr;': '\U0001d52b',
    'ngE;': '\u2267\u0338',
    'nge;': '\u2271',
    'ngeq;': '\u2271',
    'ngeqq;': '\u2267\u0338',
    'ngeqslant;': '\u2a7e\u0338',
    'nges;': '\u2a7e\u0338',
    'nGg;': '\u22d9\u0338',
    'ngsim;': '\u2275',
    'nGt;': '\u226b\u20d2',
    'ngt;': '\u226f',
    'ngtr;': '\u226f',
    'nGtv;': '\u226b\u0338',
    'nhArr;': '\u21ce',
    'nharr;': '\u21ae',
    'nhpar;': '\u2af2',
    'ni;': '\u220b',
    'nis;': '\u22fc',
    'nisd;': '\u22fa',
    'niv;': '\u220b',
    'NJcy;': '\u040a',
    'njcy;': '\u045a',
    'nlArr;': '\u21cd',
    'nlarr;': '\u219a',
    'nldr;': '\u2025',
    'nlE;': '\u2266\u0338',
    'nle;': '\u2270',
    'nLeftarrow;': '\u21cd',
    'nleftarrow;': '\u219a',
    'nLeftrightarrow;': '\u21ce',
    'nleftrightarrow;': '\u21ae',
    'nleq;': '\u2270',
    'nleqq;': '\u2266\u0338',
    'nleqslant;': '\u2a7d\u0338',
    'nles;': '\u2a7d\u0338',
    'nless;': '\u226e',
    'nLl;': '\u22d8\u0338',
    'nlsim;': '\u2274',
    'nLt;': '\u226a\u20d2',
    'nlt;': '\u226e',
    'nltri;': '\u22ea',
    'nltrie;': '\u22ec',
    'nLtv;': '\u226a\u0338',
    'nmid;': '\u2224',
    'NoBreak;': '\u2060',
    'NonBreakingSpace;': '\xa0',
    'Nopf;': '\u2115',
    'nopf;': '\U0001d55f',
    'Not;': '\u2aec',
    'not;': '\xac',
    'not': '\xac',
    'NotCongruent;': '\u2262',
    'NotCupCap;': '\u226d',
    'NotDoubleVerticalBar;': '\u2226',
    'NotElement;': '\u2209',
    'NotEqual;': '\u2260',
    'NotEqualTilde;': '\u2242\u0338',
    'NotExists;': '\u2204',
    'NotGreater;': '\u226f',
    'NotGreaterEqual;': '\u2271',
    'NotGreaterFullEqual;': '\u2267\u0338',
    'NotGreaterGreater;': '\u226b\u0338',
    'NotGreaterLess;': '\u2279',
    'NotGreaterSlantEqual;': '\u2a7e\u0338',
    'NotGreaterTilde;': '\u2275',
    'NotHumpDownHump;': '\u224e\u0338',
    'NotHumpEqual;': '\u224f\u0338',
    'notin;': '\u2209',
    'notindot;': '\u22f5\u0338',
    'notinE;': '\u22f9\u0338',
    'notinva;': '\u2209',
    'notinvb;': '\u22f7',
    'notinvc;': '\u22f6',
    'NotLeftTriangle;': '\u22ea',
    'NotLeftTriangleBar;': '\u29cf\u0338',
    'NotLeftTriangleEqual;': '\u22ec',
    'NotLess;': '\u226e',
    'NotLessEqual;': '\u2270',
    'NotLessGreater;': '\u2278',
    'NotLessLess;': '\u226a\u0338',
    'NotLessSlantEqual;': '\u2a7d\u0338',
    'NotLessTilde;': '\u2274',
    'NotNestedGreaterGreater;': '\u2aa2\u0338',
    'NotNestedLessLess;': '\u2aa1\u0338',
    'notni;': '\u220c',
    'notniva;': '\u220c',
    'notnivb;': '\u22fe',
    'notnivc;': '\u22fd',
    'NotPrecedes;': '\u2280',
    'NotPrecedesEqual;': '\u2aaf\u0338',
    'NotPrecedesSlantEqual;': '\u22e0',
    'NotReverseElement;': '\u220c',
    'NotRightTriangle;': '\u22eb',
    'NotRightTriangleBar;': '\u29d0\u0338',
    'NotRightTriangleEqual;': '\u22ed',
    'NotSquareSubset;': '\u228f\u0338',
    'NotSquareSubsetEqual;': '\u22e2',
    'NotSquareSuperset;': '\u2290\u0338',
    'NotSquareSupersetEqual;': '\u22e3',
    'NotSubset;': '\u2282\u20d2',
    'NotSubsetEqual;': '\u2288',
    'NotSucceeds;': '\u2281',
    'NotSucceedsEqual;': '\u2ab0\u0338',
    'NotSucceedsSlantEqual;': '\u22e1',
    'NotSucceedsTilde;': '\u227f\u0338',
    'NotSuperset;': '\u2283\u20d2',
    'NotSupersetEqual;': '\u2289',
    'NotTilde;': '\u2241',
    'NotTildeEqual;': '\u2244',
    'NotTildeFullEqual;': '\u2247',
    'NotTildeTilde;': '\u2249',
    'NotVerticalBar;': '\u2224',
    'npar;': '\u2226',
    'nparallel;': '\u2226',
    'nparsl;': '\u2afd\u20e5',
    'npart;': '\u2202\u0338',
    'npolint;': '\u2a14',
    'npr;': '\u2280',
    'nprcue;': '\u22e0',
    'npre;': '\u2aaf\u0338',
    'nprec;': '\u2280',
    'npreceq;': '\u2aaf\u0338',
    'nrArr;': '\u21cf',
    'nrarr;': '\u219b',
    'nrarrc;': '\u2933\u0338',
    'nrarrw;': '\u219d\u0338',
    'nRightarrow;': '\u21cf',
    'nrightarrow;': '\u219b',
    'nrtri;': '\u22eb',
    'nrtrie;': '\u22ed',
    'nsc;': '\u2281',
    'nsccue;': '\u22e1',
    'nsce;': '\u2ab0\u0338',
    'Nscr;': '\U0001d4a9',
    'nscr;': '\U0001d4c3',
    'nshortmid;': '\u2224',
    'nshortparallel;': '\u2226',
    'nsim;': '\u2241',
    'nsime;': '\u2244',
    'nsimeq;': '\u2244',
    'nsmid;': '\u2224',
    'nspar;': '\u2226',
    'nsqsube;': '\u22e2',
    'nsqsupe;': '\u22e3',
    'nsub;': '\u2284',
    'nsubE;': '\u2ac5\u0338',
    'nsube;': '\u2288',
    'nsubset;': '\u2282\u20d2',
    'nsubseteq;': '\u2288',
    'nsubseteqq;': '\u2ac5\u0338',
    'nsucc;': '\u2281',
    'nsucceq;': '\u2ab0\u0338',
    'nsup;': '\u2285',
    'nsupE;': '\u2ac6\u0338',
    'nsupe;': '\u2289',
    'nsupset;': '\u2283\u20d2',
    'nsupseteq;': '\u2289',
    'nsupseteqq;': '\u2ac6\u0338',
    'ntgl;': '\u2279',
    'Ntilde;': '\xd1',
    'Ntilde': '\xd1',
    'ntilde;': '\xf1',
    'ntilde': '\xf1',
    'ntlg;': '\u2278',
    'ntriangleleft;': '\u22ea',
    'ntrianglelefteq;': '\u22ec',
    'ntriangleright;': '\u22eb',
    'ntrianglerighteq;': '\u22ed',
    'Nu;': '\u039d',
    'nu;': '\u03bd',
    'num;': '\x23',
    'numero;': '\u2116',
    'numsp;': '\u2007',
    'nvap;': '\u224d\u20d2',
    'nVDash;': '\u22af',
    'nVdash;': '\u22ae',
    'nvDash;': '\u22ad',
    'nvdash;': '\u22ac',
    'nvge;': '\u2265\u20d2',
    'nvgt;': '\x3e\u20d2',
    'nvHarr;': '\u2904',
    'nvinfin;': '\u29de',
    'nvlArr;': '\u2902',
    'nvle;': '\u2264\u20d2',
    'nvlt;': '\x3c\u20d2',
    'nvltrie;': '\u22b4\u20d2',
    'nvrArr;': '\u2903',
    'nvrtrie;': '\u22b5\u20d2',
    'nvsim;': '\u223c\u20d2',
    'nwarhk;': '\u2923',
    'nwArr;': '\u21d6',
    'nwarr;': '\u2196',
    'nwarrow;': '\u2196',
    'nwnear;': '\u2927',
    'Oacute;': '\xd3',
    'Oacute': '\xd3',
    'oacute;': '\xf3',
    'oacute': '\xf3',
    'oast;': '\u229b',
    'ocir;': '\u229a',
    'Ocirc;': '\xd4',
    'Ocirc': '\xd4',
    'ocirc;': '\xf4',
    'ocirc': '\xf4',
    'Ocy;': '\u041e',
    'ocy;': '\u043e',
    'odash;': '\u229d',
    'Odblac;': '\u0150',
    'odblac;': '\u0151',
    'odiv;': '\u2a38',
    'odot;': '\u2299',
    'odsold;': '\u29bc',
    'OElig;': '\u0152',
    'oelig;': '\u0153',
    'ofcir;': '\u29bf',
    'Ofr;': '\U0001d512',
    'ofr;': '\U0001d52c',
    'ogon;': '\u02db',
    'Ograve;': '\xd2',
    'Ograve': '\xd2',
    'ograve;': '\xf2',
    'ograve': '\xf2',
    'ogt;': '\u29c1',
    'ohbar;': '\u29b5',
    'ohm;': '\u03a9',
    'oint;': '\u222e',
    'olarr;': '\u21ba',
    'olcir;': '\u29be',
    'olcross;': '\u29bb',
    'oline;': '\u203e',
    'olt;': '\u29c0',
    'Omacr;': '\u014c',
    'omacr;': '\u014d',
    'Omega;': '\u03a9',
    'omega;': '\u03c9',
    'Omicron;': '\u039f',
    'omicron;': '\u03bf',
    'omid;': '\u29b6',
    'ominus;': '\u2296',
    'Oopf;': '\U0001d546',
    'oopf;': '\U0001d560',
    'opar;': '\u29b7',
    'OpenCurlyDoubleQuote;': '\u201c',
    'OpenCurlyQuote;': '\u2018',
    'operp;': '\u29b9',
    'oplus;': '\u2295',
    'Or;': '\u2a54',
    'or;': '\u2228',
    'orarr;': '\u21bb',
    'ord;': '\u2a5d',
    'order;': '\u2134',
    'orderof;': '\u2134',
    'ordf;': '\xaa',
    'ordf': '\xaa',
    'ordm;': '\xba',
    'ordm': '\xba',
    'origof;': '\u22b6',
    'oror;': '\u2a56',
    'orslope;': '\u2a57',
    'orv;': '\u2a5b',
    'oS;': '\u24c8',
    'Oscr;': '\U0001d4aa',
    'oscr;': '\u2134',
    'Oslash;': '\xd8',
    'Oslash': '\xd8',
    'oslash;': '\xf8',
    'oslash': '\xf8',
    'osol;': '\u2298',
    'Otilde;': '\xd5',
    'Otilde': '\xd5',
    'otilde;': '\xf5',
    'otilde': '\xf5',
    'Otimes;': '\u2a37',
    'otimes;': '\u2297',
    'otimesas;': '\u2a36',
    'Ouml;': '\xd6',
    'Ouml': '\xd6',
    'ouml;': '\xf6',
    'ouml': '\xf6',
    'ovbar;': '\u233d',
    'OverBar;': '\u203e',
    'OverBrace;': '\u23de',
    'OverBracket;': '\u23b4',
    'OverParenthesis;': '\u23dc',
    'par;': '\u2225',
    'para;': '\xb6',
    'para': '\xb6',
    'parallel;': '\u2225',
    'parsim;': '\u2af3',
    'parsl;': '\u2afd',
    'part;': '\u2202',
    'PartialD;': '\u2202',
    'Pcy;': '\u041f',
    'pcy;': '\u043f',
    'percnt;': '\x25',
    'period;': '\x2e',
    'permil;': '\u2030',
    'perp;': '\u22a5',
    'pertenk;': '\u2031',
    'Pfr;': '\U0001d513',
    'pfr;': '\U0001d52d',
    'Phi;': '\u03a6',
    'phi;': '\u03c6',
    'phiv;': '\u03d5',
    'phmmat;': '\u2133',
    'phone;': '\u260e',
    'Pi;': '\u03a0',
    'pi;': '\u03c0',
    'pitchfork;': '\u22d4',
    'piv;': '\u03d6',
    'planck;': '\u210f',
    'planckh;': '\u210e',
    'plankv;': '\u210f',
    'plus;': '\x2b',
    'plusacir;': '\u2a23',
    'plusb;': '\u229e',
    'pluscir;': '\u2a22',
    'plusdo;': '\u2214',
    'plusdu;': '\u2a25',
    'pluse;': '\u2a72',
    'PlusMinus;': '\xb1',
    'plusmn;': '\xb1',
    'plusmn': '\xb1',
    'plussim;': '\u2a26',
    'plustwo;': '\u2a27',
    'pm;': '\xb1',
    'Poincareplane;': '\u210c',
    'pointint;': '\u2a15',
    'Popf;': '\u2119',
    'popf;': '\U0001d561',
    'pound;': '\xa3',
    'pound': '\xa3',
    'Pr;': '\u2abb',
    'pr;': '\u227a',
    'prap;': '\u2ab7',
    'prcue;': '\u227c',
    'prE;': '\u2ab3',
    'pre;': '\u2aaf',
    'prec;': '\u227a',
    'precapprox;': '\u2ab7',
    'preccurlyeq;': '\u227c',
    'Precedes;': '\u227a',
    'PrecedesEqual;': '\u2aaf',
    'PrecedesSlantEqual;': '\u227c',
    'PrecedesTilde;': '\u227e',
    'preceq;': '\u2aaf',
    'precnapprox;': '\u2ab9',
    'precneqq;': '\u2ab5',
    'precnsim;': '\u22e8',
    'precsim;': '\u227e',
    'Prime;': '\u2033',
    'prime;': '\u2032',
    'primes;': '\u2119',
    'prnap;': '\u2ab9',
    'prnE;': '\u2ab5',
    'prnsim;': '\u22e8',
    'prod;': '\u220f',
    'Product;': '\u220f',
    'profalar;': '\u232e',
    'profline;': '\u2312',
    'profsurf;': '\u2313',
    'prop;': '\u221d',
    'Proportion;': '\u2237',
    'Proportional;': '\u221d',
    'propto;': '\u221d',
    'prsim;': '\u227e',
    'prurel;': '\u22b0',
    'Pscr;': '\U0001d4ab',
    'pscr;': '\U0001d4c5',
    'Psi;': '\u03a8',
    'psi;': '\u03c8',
    'puncsp;': '\u2008',
    'Qfr;': '\U0001d514',
    'qfr;': '\U0001d52e',
    'qint;': '\u2a0c',
    'Qopf;': '\u211a',
    'qopf;': '\U0001d562',
    'qprime;': '\u2057',
    'Qscr;': '\U0001d4ac',
    'qscr;': '\U0001d4c6',
    'quaternions;': '\u210d',
    'quatint;': '\u2a16',
    'quest;': '\x3f',
    'questeq;': '\u225f',
    'QUOT;': '\x22',
    'QUOT': '\x22',
    'quot;': '\x22',
    'quot': '\x22',
    'rAarr;': '\u21db',
    'race;': '\u223d\u0331',
    'Racute;': '\u0154',
    'racute;': '\u0155',
    'radic;': '\u221a',
    'raemptyv;': '\u29b3',
    'Rang;': '\u27eb',
    'rang;': '\u27e9',
    'rangd;': '\u2992',
    'range;': '\u29a5',
    'rangle;': '\u27e9',
    'raquo;': '\xbb',
    'raquo': '\xbb',
    'Rarr;': '\u21a0',
    'rArr;': '\u21d2',
    'rarr;': '\u2192',
    'rarrap;': '\u2975',
    'rarrb;': '\u21e5',
    'rarrbfs;': '\u2920',
    'rarrc;': '\u2933',
    'rarrfs;': '\u291e',
    'rarrhk;': '\u21aa',
    'rarrlp;': '\u21ac',
    'rarrpl;': '\u2945',
    'rarrsim;': '\u2974',
    'Rarrtl;': '\u2916',
    'rarrtl;': '\u21a3',
    'rarrw;': '\u219d',
    'rAtail;': '\u291c',
    'ratail;': '\u291a',
    'ratio;': '\u2236',
    'rationals;': '\u211a',
    'RBarr;': '\u2910',
    'rBarr;': '\u290f',
    'rbarr;': '\u290d',
    'rbbrk;': '\u2773',
    'rbrace;': '\x7d',
    'rbrack;': '\x5d',
    'rbrke;': '\u298c',
    'rbrksld;': '\u298e',
    'rbrkslu;': '\u2990',
    'Rcaron;': '\u0158',
    'rcaron;': '\u0159',
    'Rcedil;': '\u0156',
    'rcedil;': '\u0157',
    'rceil;': '\u2309',
    'rcub;': '\x7d',
    'Rcy;': '\u0420',
    'rcy;': '\u0440',
    'rdca;': '\u2937',
    'rdldhar;': '\u2969',
    'rdquo;': '\u201d',
    'rdquor;': '\u201d',
    'rdsh;': '\u21b3',
    'Re;': '\u211c',
    'real;': '\u211c',
    'realine;': '\u211b',
    'realpart;': '\u211c',
    'reals;': '\u211d',
    'rect;': '\u25ad',
    'REG;': '\xae',
    'REG': '\xae',
    'reg;': '\xae',
    'reg': '\xae',
    'ReverseElement;': '\u220b',
    'ReverseEquilibrium;': '\u21cb',
    'ReverseUpEquilibrium;': '\u296f',
    'rfisht;': '\u297d',
    'rfloor;': '\u230b',
    'Rfr;': '\u211c',
    'rfr;': '\U0001d52f',
    'rHar;': '\u2964',
    'rhard;': '\u21c1',
    'rharu;': '\u21c0',
    'rharul;': '\u296c',
    'Rho;': '\u03a1',
    'rho;': '\u03c1',
    'rhov;': '\u03f1',
    'RightAngleBracket;': '\u27e9',
    'RightArrow;': '\u2192',
    'Rightarrow;': '\u21d2',
    'rightarrow;': '\u2192',
    'RightArrowBar;': '\u21e5',
    'RightArrowLeftArrow;': '\u21c4',
    'rightarrowtail;': '\u21a3',
    'RightCeiling;': '\u2309',
    'RightDoubleBracket;': '\u27e7',
    'RightDownTeeVector;': '\u295d',
    'RightDownVector;': '\u21c2',
    'RightDownVectorBar;': '\u2955',
    'RightFloor;': '\u230b',
    'rightharpoondown;': '\u21c1',
    'rightharpoonup;': '\u21c0',
    'rightleftarrows;': '\u21c4',
    'rightleftharpoons;': '\u21cc',
    'rightrightarrows;': '\u21c9',
    'rightsquigarrow;': '\u219d',
    'RightTee;': '\u22a2',
    'RightTeeArrow;': '\u21a6',
    'RightTeeVector;': '\u295b',
    'rightthreetimes;': '\u22cc',
    'RightTriangle;': '\u22b3',
    'RightTriangleBar;': '\u29d0',
    'RightTriangleEqual;': '\u22b5',
    'RightUpDownVector;': '\u294f',
    'RightUpTeeVector;': '\u295c',
    'RightUpVector;': '\u21be',
    'RightUpVectorBar;': '\u2954',
    'RightVector;': '\u21c0',
    'RightVectorBar;': '\u2953',
    'ring;': '\u02da',
    'risingdotseq;': '\u2253',
    'rlarr;': '\u21c4',
    'rlhar;': '\u21cc',
    'rlm;': '\u200f',
    'rmoust;': '\u23b1',
    'rmoustache;': '\u23b1',
    'rnmid;': '\u2aee',
    'roang;': '\u27ed',
    'roarr;': '\u21fe',
    'robrk;': '\u27e7',
    'ropar;': '\u2986',
    'Ropf;': '\u211d',
    'ropf;': '\U0001d563',
    'roplus;': '\u2a2e',
    'rotimes;': '\u2a35',
    'RoundImplies;': '\u2970',
    'rpar;': '\x29',
    'rpargt;': '\u2994',
    'rppolint;': '\u2a12',
    'rrarr;': '\u21c9',
    'Rrightarrow;': '\u21db',
    'rsaquo;': '\u203a',
    'Rscr;': '\u211b',
    'rscr;': '\U0001d4c7',
    'Rsh;': '\u21b1',
    'rsh;': '\u21b1',
    'rsqb;': '\x5d',
    'rsquo;': '\u2019',
    'rsquor;': '\u2019',
    'rthree;': '\u22cc',
    'rtimes;': '\u22ca',
    'rtri;': '\u25b9',
    'rtrie;': '\u22b5',
    'rtrif;': '\u25b8',
    'rtriltri;': '\u29ce',
    'RuleDelayed;': '\u29f4',
    'ruluhar;': '\u2968',
    'rx;': '\u211e',
    'Sacute;': '\u015a',
    'sacute;': '\u015b',
    'sbquo;': '\u201a',
    'Sc;': '\u2abc',
    'sc;': '\u227b',
    'scap;': '\u2ab8',
    'Scaron;': '\u0160',
    'scaron;': '\u0161',
    'sccue;': '\u227d',
    'scE;': '\u2ab4',
    'sce;': '\u2ab0',
    'Scedil;': '\u015e',
    'scedil;': '\u015f',
    'Scirc;': '\u015c',
    'scirc;': '\u015d',
    'scnap;': '\u2aba',
    'scnE;': '\u2ab6',
    'scnsim;': '\u22e9',
    'scpolint;': '\u2a13',
    'scsim;': '\u227f',
    'Scy;': '\u0421',
    'scy;': '\u0441',
    'sdot;': '\u22c5',
    'sdotb;': '\u22a1',
    'sdote;': '\u2a66',
    'searhk;': '\u2925',
    'seArr;': '\u21d8',
    'searr;': '\u2198',
    'searrow;': '\u2198',
    'sect;': '\xa7',
    'sect': '\xa7',
    'semi;': '\x3b',
    'seswar;': '\u2929',
    'setminus;': '\u2216',
    'setmn;': '\u2216',
    'sext;': '\u2736',
    'Sfr;': '\U0001d516',
    'sfr;': '\U0001d530',
    'sfrown;': '\u2322',
    'sharp;': '\u266f',
    'SHCHcy;': '\u0429',
    'shchcy;': '\u0449',
    'SHcy;': '\u0428',
    'shcy;': '\u0448',
    'ShortDownArrow;': '\u2193',
    'ShortLeftArrow;': '\u2190',
    'shortmid;': '\u2223',
    'shortparallel;': '\u2225',
    'ShortRightArrow;': '\u2192',
    'ShortUpArrow;': '\u2191',
    'shy;': '\xad',
    'shy': '\xad',
    'Sigma;': '\u03a3',
    'sigma;': '\u03c3',
    'sigmaf;': '\u03c2',
    'sigmav;': '\u03c2',
    'sim;': '\u223c',
    'simdot;': '\u2a6a',
    'sime;': '\u2243',
    'simeq;': '\u2243',
    'simg;': '\u2a9e',
    'simgE;': '\u2aa0',
    'siml;': '\u2a9d',
    'simlE;': '\u2a9f',
    'simne;': '\u2246',
    'simplus;': '\u2a24',
    'simrarr;': '\u2972',
    'slarr;': '\u2190',
    'SmallCircle;': '\u2218',
    'smallsetminus;': '\u2216',
    'smashp;': '\u2a33',
    'smeparsl;': '\u29e4',
    'smid;': '\u2223',
    'smile;': '\u2323',
    'smt;': '\u2aaa',
    'smte;': '\u2aac',
    'smtes;': '\u2aac\ufe00',
    'SOFTcy;': '\u042c',
    'softcy;': '\u044c',
    'sol;': '\x2f',
    'solb;': '\u29c4',
    'solbar;': '\u233f',
    'Sopf;': '\U0001d54a',
    'sopf;': '\U0001d564',
    'spades;': '\u2660',
    'spadesuit;': '\u2660',
    'spar;': '\u2225',
    'sqcap;': '\u2293',
    'sqcaps;': '\u2293\ufe00',
    'sqcup;': '\u2294',
    'sqcups;': '\u2294\ufe00',
    'Sqrt;': '\u221a',
    'sqsub;': '\u228f',
    'sqsube;': '\u2291',
    'sqsubset;': '\u228f',
    'sqsubseteq;': '\u2291',
    'sqsup;': '\u2290',
    'sqsupe;': '\u2292',
    'sqsupset;': '\u2290',
    'sqsupseteq;': '\u2292',
    'squ;': '\u25a1',
    'Square;': '\u25a1',
    'square;': '\u25a1',
    'SquareIntersection;': '\u2293',
    'SquareSubset;': '\u228f',
    'SquareSubsetEqual;': '\u2291',
    'SquareSuperset;': '\u2290',
    'SquareSupersetEqual;': '\u2292',
    'SquareUnion;': '\u2294',
    'squarf;': '\u25aa',
    'squf;': '\u25aa',
    'srarr;': '\u2192',
    'Sscr;': '\U0001d4ae',
    'sscr;': '\U0001d4c8',
    'ssetmn;': '\u2216',
    'ssmile;': '\u2323',
    'sstarf;': '\u22c6',
    'Star;': '\u22c6',
    'star;': '\u2606',
    'starf;': '\u2605',
    'straightepsilon;': '\u03f5',
    'straightphi;': '\u03d5',
    'strns;': '\xaf',
    'Sub;': '\u22d0',
    'sub;': '\u2282',
    'subdot;': '\u2abd',
    'subE;': '\u2ac5',
    'sube;': '\u2286',
    'subedot;': '\u2ac3',
    'submult;': '\u2ac1',
    'subnE;': '\u2acb',
    'subne;': '\u228a',
    'subplus;': '\u2abf',
    'subrarr;': '\u2979',
    'Subset;': '\u22d0',
    'subset;': '\u2282',
    'subseteq;': '\u2286',
    'subseteqq;': '\u2ac5',
    'SubsetEqual;': '\u2286',
    'subsetneq;': '\u228a',
    'subsetneqq;': '\u2acb',
    'subsim;': '\u2ac7',
    'subsub;': '\u2ad5',
    'subsup;': '\u2ad3',
    'succ;': '\u227b',
    'succapprox;': '\u2ab8',
    'succcurlyeq;': '\u227d',
    'Succeeds;': '\u227b',
    'SucceedsEqual;': '\u2ab0',
    'SucceedsSlantEqual;': '\u227d',
    'SucceedsTilde;': '\u227f',
    'succeq;': '\u2ab0',
    'succnapprox;': '\u2aba',
    'succneqq;': '\u2ab6',
    'succnsim;': '\u22e9',
    'succsim;': '\u227f',
    'SuchThat;': '\u220b',
    'Sum;': '\u2211',
    'sum;': '\u2211',
    'sung;': '\u266a',
    'Sup;': '\u22d1',
    'sup;': '\u2283',
    'sup1;': '\xb9',
    'sup1': '\xb9',
    'sup2;': '\xb2',
    'sup2': '\xb2',
    'sup3;': '\xb3',
    'sup3': '\xb3',
    'supdot;': '\u2abe',
    'supdsub;': '\u2ad8',
    'supE;': '\u2ac6',
    'supe;': '\u2287',
    'supedot;': '\u2ac4',
    'Superset;': '\u2283',
    'SupersetEqual;': '\u2287',
    'suphsol;': '\u27c9',
    'suphsub;': '\u2ad7',
    'suplarr;': '\u297b',
    'supmult;': '\u2ac2',
    'supnE;': '\u2acc',
    'supne;': '\u228b',
    'supplus;': '\u2ac0',
    'Supset;': '\u22d1',
    'supset;': '\u2283',
    'supseteq;': '\u2287',
    'supseteqq;': '\u2ac6',
    'supsetneq;': '\u228b',
    'supsetneqq;': '\u2acc',
    'supsim;': '\u2ac8',
    'supsub;': '\u2ad4',
    'supsup;': '\u2ad6',
    'swarhk;': '\u2926',
    'swArr;': '\u21d9',
    'swarr;': '\u2199',
    'swarrow;': '\u2199',
    'swnwar;': '\u292a',
    'szlig;': '\xdf',
    'szlig': '\xdf',
    'Tab;': '\x09',
    'target;': '\u2316',
    'Tau;': '\u03a4',
    'tau;': '\u03c4',
    'tbrk;': '\u23b4',
    'Tcaron;': '\u0164',
    'tcaron;': '\u0165',
    'Tcedil;': '\u0162',
    'tcedil;': '\u0163',
    'Tcy;': '\u0422',
    'tcy;': '\u0442',
    'tdot;': '\u20db',
    'telrec;': '\u2315',
    'Tfr;': '\U0001d517',
    'tfr;': '\U0001d531',
    'there4;': '\u2234',
    'Therefore;': '\u2234',
    'therefore;': '\u2234',
    'Theta;': '\u0398',
    'theta;': '\u03b8',
    'thetasym;': '\u03d1',
    'thetav;': '\u03d1',
    'thickapprox;': '\u2248',
    'thicksim;': '\u223c',
    'ThickSpace;': '\u205f\u200a',
    'thinsp;': '\u2009',
    'ThinSpace;': '\u2009',
    'thkap;': '\u2248',
    'thksim;': '\u223c',
    'THORN;': '\xde',
    'THORN': '\xde',
    'thorn;': '\xfe',
    'thorn': '\xfe',
    'Tilde;': '\u223c',
    'tilde;': '\u02dc',
    'TildeEqual;': '\u2243',
    'TildeFullEqual;': '\u2245',
    'TildeTilde;': '\u2248',
    'times;': '\xd7',
    'times': '\xd7',
    'timesb;': '\u22a0',
    'timesbar;': '\u2a31',
    'timesd;': '\u2a30',
    'tint;': '\u222d',
    'toea;': '\u2928',
    'top;': '\u22a4',
    'topbot;': '\u2336',
    'topcir;': '\u2af1',
    'Topf;': '\U0001d54b',
    'topf;': '\U0001d565',
    'topfork;': '\u2ada',
    'tosa;': '\u2929',
    'tprime;': '\u2034',
    'TRADE;': '\u2122',
    'trade;': '\u2122',
    'triangle;': '\u25b5',
    'triangledown;': '\u25bf',
    'triangleleft;': '\u25c3',
    'trianglelefteq;': '\u22b4',
    'triangleq;': '\u225c',
    'triangleright;': '\u25b9',
    'trianglerighteq;': '\u22b5',
    'tridot;': '\u25ec',
    'trie;': '\u225c',
    'triminus;': '\u2a3a',
    'TripleDot;': '\u20db',
    'triplus;': '\u2a39',
    'trisb;': '\u29cd',
    'tritime;': '\u2a3b',
    'trpezium;': '\u23e2',
    'Tscr;': '\U0001d4af',
    'tscr;': '\U0001d4c9',
    'TScy;': '\u0426',
    'tscy;': '\u0446',
    'TSHcy;': '\u040b',
    'tshcy;': '\u045b',
    'Tstrok;': '\u0166',
    'tstrok;': '\u0167',
    'twixt;': '\u226c',
    'twoheadleftarrow;': '\u219e',
    'twoheadrightarrow;': '\u21a0',
    'Uacute;': '\xda',
    'Uacute': '\xda',
    'uacute;': '\xfa',
    'uacute': '\xfa',
    'Uarr;': '\u219f',
    'uArr;': '\u21d1',
    'uarr;': '\u2191',
    'Uarrocir;': '\u2949',
    'Ubrcy;': '\u040e',
    'ubrcy;': '\u045e',
    'Ubreve;': '\u016c',
    'ubreve;': '\u016d',
    'Ucirc;': '\xdb',
    'Ucirc': '\xdb',
    'ucirc;': '\xfb',
    'ucirc': '\xfb',
    'Ucy;': '\u0423',
    'ucy;': '\u0443',
    'udarr;': '\u21c5',
    'Udblac;': '\u0170',
    'udblac;': '\u0171',
    'udhar;': '\u296e',
    'ufisht;': '\u297e',
    'Ufr;': '\U0001d518',
    'ufr;': '\U0001d532',
    'Ugrave;': '\xd9',
    'Ugrave': '\xd9',
    'ugrave;': '\xf9',
    'ugrave': '\xf9',
    'uHar;': '\u2963',
    'uharl;': '\u21bf',
    'uharr;': '\u21be',
    'uhblk;': '\u2580',
    'ulcorn;': '\u231c',
    'ulcorner;': '\u231c',
    'ulcrop;': '\u230f',
    'ultri;': '\u25f8',
    'Umacr;': '\u016a',
    'umacr;': '\u016b',
    'uml;': '\xa8',
    'uml': '\xa8',
    'UnderBar;': '\x5f',
    'UnderBrace;': '\u23df',
    'UnderBracket;': '\u23b5',
    'UnderParenthesis;': '\u23dd',
    'Union;': '\u22c3',
    'UnionPlus;': '\u228e',
    'Uogon;': '\u0172',
    'uogon;': '\u0173',
    'Uopf;': '\U0001d54c',
    'uopf;': '\U0001d566',
    'UpArrow;': '\u2191',
    'Uparrow;': '\u21d1',
    'uparrow;': '\u2191',
    'UpArrowBar;': '\u2912',
    'UpArrowDownArrow;': '\u21c5',
    'UpDownArrow;': '\u2195',
    'Updownarrow;': '\u21d5',
    'updownarrow;': '\u2195',
    'UpEquilibrium;': '\u296e',
    'upharpoonleft;': '\u21bf',
    'upharpoonright;': '\u21be',
    'uplus;': '\u228e',
    'UpperLeftArrow;': '\u2196',
    'UpperRightArrow;': '\u2197',
    'Upsi;': '\u03d2',
    'upsi;': '\u03c5',
    'upsih;': '\u03d2',
    'Upsilon;': '\u03a5',
    'upsilon;': '\u03c5',
    'UpTee;': '\u22a5',
    'UpTeeArrow;': '\u21a5',
    'upuparrows;': '\u21c8',
    'urcorn;': '\u231d',
    'urcorner;': '\u231d',
    'urcrop;': '\u230e',
    'Uring;': '\u016e',
    'uring;': '\u016f',
    'urtri;': '\u25f9',
    'Uscr;': '\U0001d4b0',
    'uscr;': '\U0001d4ca',
    'utdot;': '\u22f0',
    'Utilde;': '\u0168',
    'utilde;': '\u0169',
    'utri;': '\u25b5',
    'utrif;': '\u25b4',
    'uuarr;': '\u21c8',
    'Uuml;': '\xdc',
    'Uuml': '\xdc',
    'uuml;': '\xfc',
    'uuml': '\xfc',
    'uwangle;': '\u29a7',
    'vangrt;': '\u299c',
    'varepsilon;': '\u03f5',
    'varkappa;': '\u03f0',
    'varnothing;': '\u2205',
    'varphi;': '\u03d5',
    'varpi;': '\u03d6',
    'varpropto;': '\u221d',
    'vArr;': '\u21d5',
    'varr;': '\u2195',
    'varrho;': '\u03f1',
    'varsigma;': '\u03c2',
    'varsubsetneq;': '\u228a\ufe00',
    'varsubsetneqq;': '\u2acb\ufe00',
    'varsupsetneq;': '\u228b\ufe00',
    'varsupsetneqq;': '\u2acc\ufe00',
    'vartheta;': '\u03d1',
    'vartriangleleft;': '\u22b2',
    'vartriangleright;': '\u22b3',
    'Vbar;': '\u2aeb',
    'vBar;': '\u2ae8',
    'vBarv;': '\u2ae9',
    'Vcy;': '\u0412',
    'vcy;': '\u0432',
    'VDash;': '\u22ab',
    'Vdash;': '\u22a9',
    'vDash;': '\u22a8',
    'vdash;': '\u22a2',
    'Vdashl;': '\u2ae6',
    'Vee;': '\u22c1',
    'vee;': '\u2228',
    'veebar;': '\u22bb',
    'veeeq;': '\u225a',
    'vellip;': '\u22ee',
    'Verbar;': '\u2016',
    'verbar;': '\x7c',
    'Vert;': '\u2016',
    'vert;': '\x7c',
    'VerticalBar;': '\u2223',
    'VerticalLine;': '\x7c',
    'VerticalSeparator;': '\u2758',
    'VerticalTilde;': '\u2240',
    'VeryThinSpace;': '\u200a',
    'Vfr;': '\U0001d519',
    'vfr;': '\U0001d533',
    'vltri;': '\u22b2',
    'vnsub;': '\u2282\u20d2',
    'vnsup;': '\u2283\u20d2',
    'Vopf;': '\U0001d54d',
    'vopf;': '\U0001d567',
    'vprop;': '\u221d',
    'vrtri;': '\u22b3',
    'Vscr;': '\U0001d4b1',
    'vscr;': '\U0001d4cb',
    'vsubnE;': '\u2acb\ufe00',
    'vsubne;': '\u228a\ufe00',
    'vsupnE;': '\u2acc\ufe00',
    'vsupne;': '\u228b\ufe00',
    'Vvdash;': '\u22aa',
    'vzigzag;': '\u299a',
    'Wcirc;': '\u0174',
    'wcirc;': '\u0175',
    'wedbar;': '\u2a5f',
    'Wedge;': '\u22c0',
    'wedge;': '\u2227',
    'wedgeq;': '\u2259',
    'weierp;': '\u2118',
    'Wfr;': '\U0001d51a',
    'wfr;': '\U0001d534',
    'Wopf;': '\U0001d54e',
    'wopf;': '\U0001d568',
    'wp;': '\u2118',
    'wr;': '\u2240',
    'wreath;': '\u2240',
    'Wscr;': '\U0001d4b2',
    'wscr;': '\U0001d4cc',
    'xcap;': '\u22c2',
    'xcirc;': '\u25ef',
    'xcup;': '\u22c3',
    'xdtri;': '\u25bd',
    'Xfr;': '\U0001d51b',
    'xfr;': '\U0001d535',
    'xhArr;': '\u27fa',
    'xharr;': '\u27f7',
    'Xi;': '\u039e',
    'xi;': '\u03be',
    'xlArr;': '\u27f8',
    'xlarr;': '\u27f5',
    'xmap;': '\u27fc',
    'xnis;': '\u22fb',
    'xodot;': '\u2a00',
    'Xopf;': '\U0001d54f',
    'xopf;': '\U0001d569',
    'xoplus;': '\u2a01',
    'xotime;': '\u2a02',
    'xrArr;': '\u27f9',
    'xrarr;': '\u27f6',
    'Xscr;': '\U0001d4b3',
    'xscr;': '\U0001d4cd',
    'xsqcup;': '\u2a06',
    'xuplus;': '\u2a04',
    'xutri;': '\u25b3',
    'xvee;': '\u22c1',
    'xwedge;': '\u22c0',
    'Yacute;': '\xdd',
    'Yacute': '\xdd',
    'yacute;': '\xfd',
    'yacute': '\xfd',
    'YAcy;': '\u042f',
    'yacy;': '\u044f',
    'Ycirc;': '\u0176',
    'ycirc;': '\u0177',
    'Ycy;': '\u042b',
    'ycy;': '\u044b',
    'yen;': '\xa5',
    'yen': '\xa5',
    'Yfr;': '\U0001d51c',
    'yfr;': '\U0001d536',
    'YIcy;': '\u0407',
    'yicy;': '\u0457',
    'Yopf;': '\U0001d550',
    'yopf;': '\U0001d56a',
    'Yscr;': '\U0001d4b4',
    'yscr;': '\U0001d4ce',
    'YUcy;': '\u042e',
    'yucy;': '\u044e',
    'Yuml;': '\u0178',
    'yuml;': '\xff',
    'yuml': '\xff',
    'Zacute;': '\u0179',
    'zacute;': '\u017a',
    'Zcaron;': '\u017d',
    'zcaron;': '\u017e',
    'Zcy;': '\u0417',
    'zcy;': '\u0437',
    'Zdot;': '\u017b',
    'zdot;': '\u017c',
    'zeetrf;': '\u2128',
    'ZeroWidthSpace;': '\u200b',
    'Zeta;': '\u0396',
    'zeta;': '\u03b6',
    'Zfr;': '\u2128',
    'zfr;': '\U0001d537',
    'ZHcy;': '\u0416',
    'zhcy;': '\u0436',
    'zigrarr;': '\u21dd',
    'Zopf;': '\u2124',
    'zopf;': '\U0001d56b',
    'Zscr;': '\U0001d4b5',
    'zscr;': '\U0001d4cf',
    'zwj;': '\u200d',
    'zwnj;': '\u200c',
}


# A hint for the TypeError of the call of a callback itself, not of its body, which a function of Python raises when it
# is called with other arguments than its parameters, where a sub of Perl takes any of @_
def _call_hint(e: TypeError, hint: str) -> None:  # pyright: ignore[reportUnusedFunction]
    if e.__traceback__ is not None and e.__traceback__.tb_next is None:
        e.args = (f'{e}: {hint}', *e.args[1:])


def _entity(point: str | None, name: str | None, attr: bool) -> str:

    # Code point
    if name is None:
        assert point is not None
        code = int(point[1:], 16) if point.startswith('x') else int(point)
        if code == 0 or code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
            return '\ufffd'
        return chr(_C1.get(code, code))

    # Named character reference
    rest = last = ''
    while len(name):
        if name in ENTITIES and (not attr or name.endswith(';') or not re.match(r'[A-Za-z0-9=]', last)):
            return ENTITIES[name] + rest[::-1]
        last = name[-1]
        rest += last
        name = name[:-1]
    return '&' + rest[::-1]


class _Guard:
    def __init__(self, cb: Callable[[], object]) -> None:
        self.cb = cb

    def __enter__(self) -> None:
        pass

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.cb()


def _header(string: str, cookie: bool) -> list[list[tuple[str, str | None]]]:
    tree: list[list[tuple[str, str | None]]] = []
    part: list[tuple[str, str | None]] = []
    pos = 0
    while m := _RE_HEADER_NAME.match(string, pos):
        name, value, pos = m[1], None, m.end()
        expires = cookie and len(part) > 0 and name.lower() == 'expires'

        # Special "expires" value
        if expires and (v := _RE_EXPIRES.match(string, pos)):
            value, pos = v[1], v.end()

        # Quoted value
        elif v := _RE_QUOTED_VALUE.match(string, pos):
            value, pos = unquote(v[1]), v.end()

        # Unquoted value
        elif v := _RE_UNQUOTED_VALUE.match(string, pos):
            value, pos = v[1], v.end()

        part.append((name, value))

        # Separator
        if not (m := _RE_HEADER_SEPARATOR.match(string, pos)):
            continue
        pos = m.end()
        tree.append(part)
        part = []

    # Take care of final part
    if part:
        tree.append(part)
    return tree


def _html(string: str, attr: bool) -> str:
    return _RE_ENTITY.sub(lambda m: _entity(m[1], m[2], attr), string)


# The name and the values of a call: none, a dict of values, a name, or a name and a dict, with the keyword arguments
# as the pairs of names and values that Mojo takes after them; the modules of Pyjoyment use it, as Mojo::Util::_options
def _options(args: tuple[Any, ...], values: dict[str, Any]) -> tuple[Any, dict[str, Any]]:  # pyright: ignore[reportUnusedFunction]
    name: Any = None
    if len(args) == 2 or (len(args) == 1 and not isinstance(args[0], dict)):
        name, args = args[0], args[1:]
    if len(args) > 1 or (args and not isinstance(args[0], dict)):
        raise TypeError(f'Unexpected positional arguments: {args!r}')
    return name, ({**cast(dict[str, Any], args[0]), **values} if args else dict(values))


def _round(number: float) -> str:
    return f'{int(number * 10 + 0.5) / 10 if number < 10 else int(number + 0.5):.15g}'


# The values of a dict that an object keeps under a name, as the stash of a controller and the config and the defaults
# of an application: the dict, a value, or the object after it merges a dict or keyword arguments
def _stash(name: str, obj: Any, args: tuple[Any, ...], values: dict[str, Any]) -> Any:  # pyright: ignore[reportUnusedFunction]
    attr = f'_{name}'
    stash: dict[Any, Any] | None = getattr(obj, attr, None)
    if stash is None:
        setattr(obj, attr, stash := {})

    # Dict
    if not args and not values:
        return stash

    # Get
    if len(args) == 1 and not isinstance(args[0], dict) and not values:
        return stash.get(args[0])

    # Set
    for arg in args:
        stash.update(cast(dict[Any, Any], arg))
    stash.update(values)

    return obj


# Perl's split, which drops the empty fields at the end
def _split(pattern: str, string: str) -> list[str]:
    fields = re.split(pattern, string)
    while fields and fields[-1] == '':
        fields.pop()
    return fields


# The name that a mistake of the name of an attribute most likely meant: one that the name starts with or that starts
# with the name, of three letters at least, as "req" for "request", or else the closest one
def _suggest(name: str, names: Iterable[str]) -> str | None:  # pyright: ignore[reportUnusedFunction]
    import difflib

    others = [n for n in names if n != name and not n.startswith('_')]
    if prefixes := [n for n in others if len(n) > 2 and (name.startswith(n) or n.startswith(name))]:
        return difflib.get_close_matches(name, prefixes, n=1, cutoff=0)[0]
    return next(iter(difflib.get_close_matches(name, others, n=1)), None)


# Perl's ucfirst
def _ucfirst(string: str) -> str:
    return string[:1].title() + string[1:]


@functools.cache
def _url_pattern[T: (str, bytes)](pattern: T) -> re.Pattern[T]:
    if isinstance(pattern, str):
        return re.compile('[' + pattern.replace('[', '\\[') + ']')
    return re.compile(b'[' + pattern.replace(b'[', b'\\[') + b']')
