"""
Pyjo.INI - INI loader and dumper
================================
::

    from Pyjo.INI import dump, load

    config = load('[default]\\nregion = eu-central-1\\noutput = json\\n')

    string = dump({'www': {'listen': '127.0.0.1:9000', 'pm': 'static', 'pm.max_children': 2}})

:mod:`Pyjo.INI` loads and dumps the INI files that well-known programs read
and write, as ``~/.aws/config`` and ``~/.aws/credentials``, ``php.ini`` and
``php-fpm.conf``, ``.editorconfig`` and ``my.cnf``, the format of
:mod:`Pyjoyment.Plugin.INIConfig`. Its syntax is the one of
:mod:`configparser` of the standard library, which botocore reads
``~/.aws/config`` with, and what PHP and the others need besides.

A line ``[section]`` starts a section, whose name is kept as it is, as
``[profile dev]``, and a section that comes again adds its keys. A line
``key = value`` or ``key: value`` sets a key, at the first delimiter of the
line, with the case of the key kept, and a line without a delimiter is a key
of the value ``None``, as ``skip-name-resolve`` of ``my.cnf``. The keys
before the first section are at the top of the dict, as ``root = true`` of
``.editorconfig``. A line that starts with ``;`` or ``#`` is a comment, and
there are no comments after a value, as in :mod:`configparser`. ::

    # {'root': 'true', '*.py': {'indent_size': '4'}}
    load('root = true\\n\\n[*.py]\\nindent_size = 4\\n')

The comments are left out, or kept with ``comments``, each line a key of the
value ``None``, in the order of the file, which :func:`dump` writes as it is,
so that a file that is changed keeps them. The key is a :class:`Comment`, a
string that counts the same comments before it in its dict, so that a
comment that comes again is a key of its own. ::

    # {Comment('; the region', 0): None, 'region': 'eu-central-1'}
    load('; the region\\nregion = eu-central-1\\n', comments=True)

A value is a string. A line indented more than its key continues its value,
whose lines are joined with ``\\n``, and a blank line ends it. An empty value
whose lines are all ``key = value`` is a dict, as the nested settings of
``~/.aws/config``, and a key that comes again in a section is a list of its
values, in their order, as ``extension`` of ``php.ini``. ::

    # {'profile dev': {'s3': {'max_concurrent_requests': '20'}}}
    load('[profile dev]\\ns3 =\\n    max_concurrent_requests = 20\\n')

    # {'PHP': {'extension': ['curl', 'mbstring']}}
    load('[PHP]\\nextension = curl\\nextension = mbstring\\n')

:func:`dump` writes the same: the keys at the top first, then the sections, a
dict of a dict, a list as its key again for each of its values, a dict in a
section as an indented block, ``None`` as a key alone, a key that starts with
``;`` or ``#`` of the value ``None`` as a comment, and ``True`` and ``False`` as
``true`` and ``false``. A key is never quoted, as php-fpm takes a key with a
dot, as ``pm.max_children``, only as it is. ::

    # '[default]\\nregion = eu-central-1\\n'
    dump({'default': {'region': 'eu-central-1'}})

    # '[www]\\n; the workers\\npm.max_children = 2\\n'
    dump({'www': {'; the workers': None, 'pm.max_children': 2}})

What INI cannot hold raises an error: a dict deeper than a dict in a section,
a list in a list, an empty list, a value with spaces at the ends of a line,
an empty line in a value, a line of a value that would be a comment, and a
key or the name of a section that the loader would read otherwise. Another
object is what :mod:`Pyjo.JSON` encodes, the value of its method
``__json__`` or its string.

See also
--------

:mod:`Pyjoyment.Plugin.INIConfig`, :mod:`Pyjo.TOML`, https://mojolicious.org.
"""

import Pyjo.Exception

from Pyjo.YAML import _data  # pyright: ignore[reportPrivateUsage]

import datetime
import re

from typing import Any, Self, cast


# The delimiter of a key and its value, the first of the line, as configparser has it
_RE_DELIMITER = re.compile(r'[=:]')

# The indentation of a line that continues a value or of a block of a dict in a section
_INDENT = '    '


class Comment(str):
    """::

        comment = Comment('; the region')
        comment = Comment('#', 1)

    A line of a comment, the key of the value ``None`` that :func:`load` gives
    with ``comments``, with ``occurrence``, the number of the same comments
    before it in its dict, so that two of them are two keys. It equals only a
    :class:`Comment` of the same line and occurrence. ::

        # {Comment('#', 0): None, Comment('#', 1): None}
        load('#\\n#\\n', comments=True)
    """

    occurrence: int

    def __new__(cls, line: str, occurrence: int = 0) -> Self:
        comment = super().__new__(cls, line)
        comment.occurrence = occurrence
        return comment

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Comment) and str.__eq__(self, other) and self.occurrence == other.occurrence

    def __hash__(self) -> int:
        return hash((str.__str__(self), self.occurrence))

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __repr__(self) -> str:
        return f'Comment({str.__repr__(self)}, {self.occurrence})'


def dump(value: Any, *, sort_keys: bool = False) -> str:
    """::

        string = dump(value)
        string = dump(value, sort_keys=True)

    Dump a dict to an INI string, with the keys of a dict in the order of the
    :class:`dict`, or sorted with ``sort_keys``. ::

        # 'listen = 127.0.0.1:9000\\npm.max_children = 2\\n'
        dump({'listen': '127.0.0.1:9000', 'pm.max_children': 2})
    """
    table = _data(value)
    if not isinstance(table, dict):
        raise _error(f'needs a dict at the top, not a {type(table).__name__}')
    lines: list[str] = []
    sections: list[tuple[str, dict[Any, Any]]] = []
    for key, item in _items(cast(dict[Any, Any], table), sort_keys):
        item = _data(item)
        if _is_comment(key, item):
            lines.append(_comment(key))
        elif isinstance(item, dict):
            sections.append((_section(key), cast(dict[Any, Any], item)))
        else:
            _pairs(lines, _key(key), item, 0, sort_keys)
    for name, section in sections:
        if lines:
            lines.append('')
        lines.append(f'[{name}]')
        for key, item in _items(section, sort_keys):
            item = _data(item)
            if _is_comment(key, item):
                lines.append(_comment(key))
            else:
                _pairs(lines, _key(key), item, 1, sort_keys)
    return ''.join(f'{line}\n' for line in lines)


def load(string: str, *, comments: bool = False, unquote: bool = False) -> dict[str, Any]:
    """::

        value = load(string)
        value = load(string, comments=True)
        value = load(string, unquote=True)

    Load an INI string, whose error is a :mod:`Pyjo.Exception`, without its
    comments, or with them with ``comments``, and with the quotes around a
    value kept, as :mod:`configparser` keeps them, or taken off with
    ``unquote``, as PHP does. ::

        # {'PHP': {'error_log': '"/var/log/php.log"'}}
        load('[PHP]\\nerror_log = "/var/log/php.log"\\n')

        # {'PHP': {'error_log': '/var/log/php.log'}}
        load('[PHP]\\nerror_log = "/var/log/php.log"\\n', unquote=True)

    A byte order mark at the start of the string, which an editor on Windows
    writes, is not a part of its first line.
    """
    loader = _Loader(comments, unquote)
    # The byte order mark, which would be the start of the name of the first section, where configparser raises an error
    for number, line in enumerate(string.removeprefix('\ufeff').splitlines(), 1):
        loader.line(number, line)
    loader.end()
    return loader.result


class _Loader:
    def __init__(self, comments: bool, unquote: bool) -> None:
        self.comments = comments
        self.unquote = unquote
        self.result: dict[str, Any] = {}
        self.section = self.result
        # The key whose value is read, the indentation of its line, and the lines of its value, None for a key without a
        # delimiter
        self.key: str | None = None
        self.indent = 0
        self.lines: list[str] | None = None
        # The comments between the lines of the value that is read, which come after its key
        self.pending: list[str] = []

    def comment(self, line: str) -> None:
        occurrence = sum(1 for key in self.section if isinstance(key, Comment) and str.__eq__(key, line))
        self.section[Comment(line, occurrence)] = None

    def end(self) -> None:
        # The value of the key that is read, which a key that comes again in a section adds to a list
        if self.key is None:
            return
        key, value = self.key, self.value()
        self.key = None
        _add(self.section, key, value)
        for line in self.pending:
            self.comment(line)
        self.pending.clear()

    def line(self, number: int, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            self.end()
            return
        if stripped[0] in ';#':
            if self.comments and self.key is not None:
                self.pending.append(stripped)
            elif self.comments:
                self.comment(stripped)
            return
        indent = len(line) - len(line.lstrip())
        if self.key is not None and indent > self.indent:
            if self.lines is None:
                raise _error(f'line {number}: continues the key "{self.key}", which has no value')
            self.lines.append(stripped)
            return
        self.end()
        if stripped.startswith('['):
            if not stripped.endswith(']') or not (name := stripped[1:-1].strip()):
                raise _error(f'line {number}: no name of the section')
            section = self.result.setdefault(name, {})
            if not isinstance(section, dict):
                raise _error(f'line {number}: the section "{name}" is a key too')
            self.section = cast(dict[str, Any], section)
            return
        if match := _RE_DELIMITER.search(stripped):
            key, lines = stripped[: match.start()].rstrip(), [stripped[match.end() :].lstrip()]
        else:
            key, lines = stripped, None
        if not key:
            raise _error(f'line {number}: no key')
        self.key, self.indent, self.lines = key, indent, lines

    def unquoted(self, value: str) -> str:
        if self.unquote and len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            return value[1:-1]
        return value

    def value(self) -> Any:
        if self.lines is None:
            return None
        first, *rest = self.lines
        # A block of keys and values after an empty value, which botocore splits at the first "=" only
        if not first and rest and all('=' in line for line in rest):
            nested: dict[str, Any] = {}
            for line in rest:
                key, value = line.split('=', 1)
                _add(nested, key.rstrip(), self.unquoted(value.lstrip()))
            return nested
        return self.unquoted('\n'.join(self.lines))


def _add(mapping: dict[str, Any], key: str, value: Any) -> None:
    if key not in mapping:
        mapping[key] = value
    elif isinstance(existing := mapping[key], list):
        cast(list[Any], existing).append(value)
    else:
        mapping[key] = [existing, value]


def _comment(key: Any) -> str:
    # The line of a comment, which the loader reads back as the same comment
    string = str.__str__(key)
    if '\n' in string or '\r' in string or string != string.strip():
        raise _error(f'does not support the comment "{string}"')
    return string


def _error(message: str) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'INI {message}')


def _is_comment(key: Any, value: Any) -> bool:
    return isinstance(key, str) and key[:1] in (';', '#') and value is None


def _items(mapping: dict[Any, Any], sort_keys: bool) -> list[tuple[Any, Any]]:
    # The keys and the values of a dict, in its order or sorted
    items = list(mapping.items())
    if sort_keys:
        items.sort(key=lambda item: str(item[0]))
    return items


def _key(key: Any) -> str:
    string = _name(key, 'key')
    if _RE_DELIMITER.search(string) or string[0] in '[;#':
        raise _error(f'does not support the key "{string}"')
    return string


def _name(name: Any, kind: str) -> str:
    if not isinstance(name, str):
        raise _error(f"does not support a {kind} of the type '{type(name).__name__}'")
    string = str.__str__(name)
    if not string or string != string.strip() or '\n' in string or '\r' in string:
        raise _error(f'does not support the {kind} "{string}"')
    return string


def _pairs(lines: list[str], key: str, value: Any, level: int, sort_keys: bool) -> None:
    # The lines of a key at the top (0), in a section (1) or in a block of a dict in a section (2)
    indent = _INDENT if level == 2 else ''
    if isinstance(value, (list, tuple)):
        items = [_data(item) for item in cast(list[Any] | tuple[Any, ...], value)]
        if not items:
            raise _error(f'does not support the empty list of the key "{key}"')
        for item in items:
            if isinstance(item, (list, tuple)):
                raise _error(f'does not support a list in the list of the key "{key}"')
            _pairs(lines, key, item, level, sort_keys)
    elif isinstance(value, dict):
        if level != 1:
            raise _error(f'does not support the dict of the key "{key}" there')
        lines.append(f'{key} =')
        for name, item in _items(cast(dict[Any, Any], value), sort_keys):
            _pairs(lines, _key(name), _data(item), 2, sort_keys)
    elif value is None:
        if level == 2:
            raise _error(f'does not support the key "{key}" without a value in a dict')
        lines.append(f'{indent}{key}')
    else:
        first, *rest = _text(key, value)
        if rest and level == 2:
            raise _error(f'does not support the value of several lines of the key "{key}" in a dict')
        lines.append(f'{indent}{key} = {first}'.rstrip())
        lines.extend(f'{_INDENT}{line}' for line in rest)


def _section(name: Any) -> str:
    string = _name(name, 'section')
    if ']' in string:
        raise _error(f'does not support the section "{string}"')
    return string


def _text(key: str, value: Any) -> list[str]:
    # The lines of a value, which the loader reads back as the same string
    if isinstance(value, bool):
        return ['true' if value else 'false']
    if isinstance(value, int):
        return [int.__repr__(value)]
    if isinstance(value, float):
        return [float.__repr__(value)]
    if isinstance(value, (datetime.datetime, datetime.date)):
        return [value.isoformat()]
    if not isinstance(value, str):
        raise _error(f"does not support a value of the type '{type(value).__name__}'")
    first, *rest = str.__str__(value).split('\n')
    if '\r' in value or any(line != line.strip() for line in (first, *rest)):
        raise _error(f'does not support the spaces at the ends of a line of the value of the key "{key}"')
    if any(not line or line[0] in ';#' for line in rest):
        raise _error(f'does not support an empty line or a comment in the value of the key "{key}"')
    if not first and rest and all('=' in line for line in rest):
        raise _error(f'does not support the value of the key "{key}", which would be a dict')
    return [first, *rest]
