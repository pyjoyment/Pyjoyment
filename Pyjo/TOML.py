"""
Pyjo.TOML - TOML loader and dumper
==================================
::

    from Pyjo.TOML import dump, load

    config = load('name = "Pyjoyment"\\n\\n[server]\\nworkers = 4\\n')

    string = dump({'name': 'Pyjoyment', 'server': {'workers': 4}})

:mod:`Pyjo.TOML` loads `TOML 1.0 <https://toml.io>`_ with :mod:`tomllib`
of the standard library, which has no writer of TOML, and dumps it, the
format of :mod:`Pyjoyment.Plugin.TOMLConfig` and of the stash value ``toml``
of the renderer of :mod:`Pyjoyment`.

:func:`dump` writes a :class:`dict` as a table, whose keys come first, and
then its tables, ``[server]``, a :class:`dict` of a :class:`dict`, and its
arrays of tables, ``[[products]]``, a :class:`list` of :class:`dict`, whose
tables follow each of them. A table with keys only in its tables has no line
of its own, as ``[a.b]`` defines ``a``. Other lists and tuples are arrays,
whose dicts are inline tables, ``[{ name = "x" }, 2]``. A string is a basic
string, with the escapes of TOML, and a string of several lines is a
multi-line basic string, ``\"\"\"...\"\"\"``. :class:`datetime.datetime`,
:class:`datetime.date` and :class:`datetime.time` are the date-times, the
dates and the times of TOML, an aware one with its offset. A key is bare
where TOML allows it, and quoted otherwise. ::

    # 'name = "app"\\n\\n[server]\\nworkers = 4\\n'
    dump({'name': 'app', 'server': {'workers': 4}})

TOML has no null and no bytes, so ``None`` and :class:`bytes` raise an error,
as do a key that is not a string, a value at the top that is not a table, and
a collection inside itself. Another object is what :mod:`Pyjo.JSON` encodes,
the value of its method ``__json__`` or its string.

See also
--------

:mod:`Pyjoyment.Plugin.TOMLConfig`, :mod:`Pyjo.YAML`, https://mojolicious.org.
"""

import Pyjo.Exception

from Pyjo.Util import _bom  # pyright: ignore[reportPrivateUsage]
from Pyjo.YAML import _data as _yaml_data  # pyright: ignore[reportPrivateUsage]

import datetime
import math
import re
import tomllib

from typing import Any, cast


# A key that does not need its quotes
_RE_BARE = re.compile(r'[A-Za-z0-9_-]+')

# The characters that a basic string escapes, and the ones that a multi-line basic string escapes, without the line
# break and the tab
_RE_ESCAPE = re.compile(r'["\\\x00-\x1f\x7f\ud800-\udfff]')
_RE_ESCAPE_MULTILINE = re.compile(r'["\\\x00-\x08\x0b-\x1f\x7f\ud800-\udfff]')

_ESCAPED = {'"': '\\"', '\\': '\\\\', '\b': '\\b', '\t': '\\t', '\n': '\\n', '\f': '\\f', '\r': '\\r'}


def dump(value: Any, *, sort_keys: bool = False) -> str:
    """::

        string = dump(value)
        string = dump(value, sort_keys=True)

    Dump a table to a TOML string, with the keys of a table in the order of the
    :class:`dict`, or sorted with ``sort_keys``. ::

        # 'name = "Pyjoyment"\\n'
        dump({'name': 'Pyjoyment'})
    """
    table = _data(value)
    if not isinstance(table, dict):
        raise _error(f'needs a table at the top, not a {type(table).__name__}')
    lines: list[str] = []
    _Dumper(lines, sort_keys).table(cast(dict[Any, Any], table), [], None)
    return ''.join(f'{line}\n' for line in lines)


def load(string: str | bytes | bytearray) -> dict[str, Any]:
    """::

        value = load(string)

    Load a TOML string with :func:`tomllib.loads`, whose error is a
    :mod:`Pyjo.Exception`. ::

        # {'name': 'Pyjoyment'}
        load('name = "Pyjoyment"')

    A byte order mark at the start of the string, which an editor on Windows
    writes, is not a part of its first line. Bytes are ``UTF-8``, as TOML is,
    or ``UTF-16`` or ``UTF-32`` with a byte order mark, as Windows PowerShell
    writes ``UTF-16LE``. ::

        # {'name': 'Pyjoyment'}
        load('name = "Pyjoyment"'.encode('UTF-16'))
    """
    if not isinstance(string, str):
        string = _decode(bytes(string))
    try:
        # The byte order mark, which tomllib takes for the start of a statement
        return tomllib.loads(string.removeprefix('\ufeff'))
    except tomllib.TOMLDecodeError as e:
        raise _error(f'failed to parse: {e}') from None


# An object as Pyjo.YAML has it, and a time, which TOML has a type of
def _data(value: Any) -> Any:
    return value if isinstance(value, datetime.time) else _yaml_data(value)


def _error(message: str) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'TOML {message}')


# The bytes of a whole file, UTF-8, or the encoding of their byte order mark, which a file of Windows PowerShell has
def _decode(data: bytes) -> str:
    charset, data = _bom('UTF-8', data)
    try:
        return data.decode(charset)
    except UnicodeDecodeError:
        raise _error(f'found input that is not {charset[:6]}') from None


class _Dumper:
    def __init__(self, lines: list[str], sort_keys: bool = False) -> None:
        self.lines = lines
        self.sort_keys = sort_keys
        self.parents: set[int] = set()

    def enter(self, value: Any) -> None:
        if id(value) in self.parents:
            raise _error('found a collection inside itself')
        self.parents.add(id(value))

    def header(self, header: str) -> None:
        if self.lines:
            self.lines.append('')
        self.lines.append(header)

    def inline(self, value: Any) -> str:
        # A value on the line of its key or in an array
        value = _data(value)
        if isinstance(value, dict):
            mapping = cast(dict[Any, Any], value)
            self.enter(mapping)
            pairs = [f'{_key(key)} = {self.inline(item)}' for key, item in self.items(mapping)]
            self.parents.remove(id(mapping))
            return f'{{ {", ".join(pairs)} }}' if pairs else '{}'
        if isinstance(value, (list, tuple)):
            sequence = cast(list[Any] | tuple[Any, ...], value)
            self.enter(sequence)
            items = [self.inline(item) for item in sequence]
            self.parents.remove(id(sequence))
            return f'[{", ".join(items)}]'
        return _scalar(value)

    def table(self, table: dict[Any, Any], path: list[str], header: str | None) -> None:
        self.enter(table)
        keys: list[tuple[str, Any]] = []
        tables: list[tuple[str, dict[Any, Any]]] = []
        arrays: list[tuple[str, list[dict[Any, Any]]]] = []
        for key, value in self.items(table):
            name = _key(key)
            value = _data(value)
            if isinstance(value, dict):
                tables.append((name, cast(dict[Any, Any], value)))
            elif _is_array_of_tables(value):
                arrays.append((name, [_data(item) for item in cast(list[Any] | tuple[Any, ...], value)]))
            else:
                keys.append((name, value))

        # The line of the table, which a table with keys only in its tables does without
        if header is not None and (header.startswith('[[') or keys or not tables and not arrays):
            self.header(header)
        for name, value in keys:
            self.lines.append(f'{name} = {self.multiline(value)}')
        for name, value in tables:
            self.table(value, [*path, name], f'[{".".join([*path, name])}]')
        for name, items in arrays:
            for item in items:
                self.table(item, [*path, name], f'[[{".".join([*path, name])}]]')
        self.parents.remove(id(table))

    def items(self, mapping: dict[Any, Any]) -> list[tuple[Any, Any]]:
        # The keys and the values of a table, in its order or sorted
        items = list(mapping.items())
        if self.sort_keys:
            items.sort(key=lambda item: str(item[0]))
        return items

    def multiline(self, value: Any) -> str:
        # A string of several lines in a multi-line basic string, whose line break after the quotes is not its own
        if isinstance(value, str) and '\n' in value:
            string = str.__str__(value)
            return '"""\n' + _RE_ESCAPE_MULTILINE.sub(_escape, string) + '"""'
        return self.inline(value)


def _escape(m: re.Match[str]) -> str:
    if (escaped := _ESCAPED.get(c := m[0])) is not None:
        return escaped
    if 0xD800 <= ord(c) <= 0xDFFF:
        raise _error(f'does not support the surrogate \\u{ord(c):04x}')
    return f'\\u{ord(c):04X}'


# A list of tables, which is an array of tables, where an empty list is an array
def _is_array_of_tables(value: Any) -> bool:
    if not value or not isinstance(value, (list, tuple)):
        return False
    return all(isinstance(_data(item), dict) for item in cast(list[Any] | tuple[Any, ...], value))


def _key(key: Any) -> str:
    if not isinstance(key, str):
        raise _error(f"does not support a key of the type '{type(key).__name__}'")
    string = str.__str__(key)
    return string if _RE_BARE.fullmatch(string) else _string(string)


def _scalar(value: Any) -> str:
    if isinstance(value, str):
        return _string(str.__str__(value))
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return int.__repr__(value)
    if isinstance(value, float):
        if math.isnan(value):
            return 'nan'
        if math.isinf(value):
            return 'inf' if value > 0 else '-inf'
        return float.__repr__(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, datetime.time):
        if value.tzinfo is not None:
            raise _error('does not support a time with an offset')
        return value.isoformat()
    raise _error(f"does not support a value of the type '{type(value).__name__}'")


def _string(string: str) -> str:
    return '"' + _RE_ESCAPE.sub(_escape, string) + '"'
