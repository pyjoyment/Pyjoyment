"""
Pyjo.YAML - Minimal YAML loader and dumper
==========================================
::

    from Pyjo.YAML import dump, dump_all, load, load_all

    config = load(\"\"\"\\
    foo: bar
    list:
      - one
      - two
    \"\"\")

    documents = load_all('--- first\\n--- second\\n')

    string = dump({'foo': 'bar', 'list': ['one', 'two']})

:mod:`Pyjo.YAML` loads and dumps the YAML that configuration files and
workflows use, a subset of `YAML 1.2 <https://yaml.org>`_, which
:mod:`Pyjoyment.Plugin.YAMLConfig` reads, as Python has no YAML in its
standard library:

* mappings and sequences in the block style, nested by their indentation, and
  a mapping or a sequence that starts in an item of a sequence
  (``- name: value``, ``- - item``);
* flow sequences and mappings, ``[a, b]`` and ``{a: 1}``, nested, and over
  several lines;
* scalars, plain, in single quotes (with ``''`` for a quote) and in double
  quotes (with the escapes ``\\n``, ``\\t``, ``\\xHH``, ``\\uHHHH`` and the
  others of YAML),
  over several lines too, and the literal ``|`` and folded ``>`` block
  scalars, with their empty lines, and the indicators ``-`` and ``+`` that
  strip and keep the final line breaks;
* comments, documents that ``---`` starts and ``...`` ends, a scalar after
  ``---`` and the directive ``%YAML``.

A plain scalar has the type of the core schema of YAML 1.2: ``null`` and ``~``
are ``None``, ``true`` and ``false`` are booleans, and numbers, with ``0o`` and
``0x`` too, ``.inf`` and ``.nan``, are :class:`int` and :class:`float`, as
``404:`` is a key of :class:`int`. The words and the forms of YAML 1.1, as
``yes``, ``off``, ``0755`` for an octal number and an implicit date, are not of
the core schema, and stay strings or decimal numbers. A quoted scalar and a
block scalar are strings. ::

    # {'foo': [1, True, 'yes', '2']}
    load("foo:\\n  - 1\\n  - true\\n  - yes\\n  - '2'\\n")

A standard tag gives a scalar its type: ``!!str``, ``!!int``, ``!!float``,
``!!bool`` and ``!!null`` of YAML 1.2, and ``!!binary``, Base64 for
:class:`bytes`, and ``!!timestamp``, ISO 8601 for :class:`datetime.date` and
:class:`datetime.datetime`, of YAML 1.1. ::

    # {'port': '8080', 'key': b'hello', 'day': datetime.date(2001, 12, 14)}
    load('port: !!str 8080\\nkey: !!binary aGVsbG8=\\nday: !!timestamp 2001-12-14\\n')

An anchor ``&name`` names a node, a value or a key, in a block or a flow
collection, and an alias ``*name`` after it in the same document is the same
object; an anchor defined again names the node of the aliases after it. The
merge key ``<<`` of YAML 1.1 puts the keys of the mapping that it names, or of
a sequence of mappings, the earlier ones first, into the mapping, under the
keys of the mapping itself. ::

    # {'base': {'a': 1, 'b': 1}, 'copy': {'a': 1, 'b': 2}}
    load('base: &base\\n  a: 1\\n  b: 1\\ncopy:\\n  <<: *base\\n  b: 2\\n')

Other tags, complex keys and the indicator of the indentation of a block
scalar are not supported, and raise an error, as do lines that the subset
does not know.

:func:`dump` writes what the loader reads, in the block style of
configuration files: a :class:`dict` is a mapping, a :class:`list` and a
:class:`tuple` are a sequence, ``{}`` and ``[]`` when they are empty, and a
string is plain where it reads back as the same string, quoted otherwise, and
a literal block scalar when it has several lines. :class:`bytes` and dates
have the tags ``!!binary`` and ``!!timestamp``, and another object is what
:mod:`Pyjo.JSON` encodes, the value of its method ``__json__`` or its string.
A :class:`dict` or a :class:`list` that is there more than once has an anchor
where it is first and an alias after it, which the loader reads back as the
same object, and one inside itself raises an error, as the loader cannot read
it back; a :class:`tuple` has no identity of its own, as the compiler can
share one that is a constant, and it is written again. ::

    # 'name: Pyjoyment\\nlist:\\n  - one\\n  - 2\\nrun: |\\n  make\\n'
    dump({'name': 'Pyjoyment', 'list': ['one', 2], 'run': 'make\\n'})

See also
--------

:mod:`Pyjoyment.Plugin.YAMLConfig`, https://mojolicious.org.

Inspired by `CPAN::Meta::YAML <https://metacpan.org/pod/CPAN::Meta::YAML>`_
of Adam Kennedy and David Golden, which Mojolicious uses, whose regular
expressions of scalars and keys it borrows, with thanks.
"""

import Pyjo.Exception

from Pyjo.Util import b64_encode

import base64
import binascii
import builtins
import collections
import datetime
import math
import re

from collections.abc import Callable, Iterable
from typing import Any, Literal, cast


# The regular expressions of CPAN::Meta::YAML
_DOUBLE_QUOTED = r'"([^\\"]*(?:\\.[^\\"]*)*)"'
_SINGLE_QUOTED = r"'([^']*(?:''[^']*)*)'"
_UNQUOTED_KEY = r'([^:]+(?::+\S(?:[^:]*|.*?(?=:)))*)(?=\s*:(?:\s+|$))'
_TRAILING_COMMENT = r'(?:\s+#.*)?'
_KEY_VALUE_SEPARATOR = r'\s*:(?:\s+(?:#.*)?|$)'

_RE_DOUBLE = re.compile(rf'^{_DOUBLE_QUOTED}{_TRAILING_COMMENT}\Z')
_RE_SINGLE = re.compile(rf'^{_SINGLE_QUOTED}{_TRAILING_COMMENT}\Z')
_RE_KEY_DOUBLE = re.compile(rf'^\s*{_DOUBLE_QUOTED}{_KEY_VALUE_SEPARATOR}')
_RE_KEY_SINGLE = re.compile(rf'^\s*{_SINGLE_QUOTED}{_KEY_VALUE_SEPARATOR}')
_RE_KEY_UNQUOTED = re.compile(rf'^\s*{_UNQUOTED_KEY}{_KEY_VALUE_SEPARATOR}')
_RE_BLANK = re.compile(r'^\s*(?:#.*)?\Z')

# Not in CPAN::Meta::YAML: the name of an anchor or an alias, an anchor of a key and an alias as a key
_ANCHOR = r'[^\s,\[\]{}]+'
_RE_KEY_ALIAS = re.compile(rf'^\s*\*({_ANCHOR}){_KEY_VALUE_SEPARATOR}')
_RE_KEY_ANCHOR = re.compile(rf'^(\s*)&({_ANCHOR})\s+')

_ESCAPES = {
    '0': '\x00',
    'L': '\u2028',
    'N': '\x85',
    'P': '\u2029',
    'a': '\x07',
    'b': '\x08',
    'e': '\x1b',
    'f': '\x0c',
    'n': '\x0a',
    'r': '\x0d',
    't': '\x09',
    'v': '\x0b',
    'z': '\x00',
    '\\': '\\',
    '_': '\xa0',
}


def dump(
    value: Any,
    *,
    indent: int = 2,
    indent_sequences: bool = True,
    quote: Literal["'", '"'] | None = None,
    quote_keys: Literal["'", '"'] | None = None,
    multiline: bool = True,
    explicit_start: bool = False,
    version: Literal['1.1', '1.2'] = '1.1',
    anchors: bool = True,
    sort_keys: bool = False,
) -> str:
    """::

        string = dump(value)
        string = dump(value, sort_keys=True)
        string = dump(value, indent=4, indent_sequences=False, quote='"')

    Dump a value to a YAML string of one document, with the options:

    * ``indent``, the number of spaces of a level of the indentation, ``2``
      by default;
    * ``indent_sequences``, whether a sequence below a key is indented,
      ``True`` by default, or has its items at the column of the key;
    * ``quote``, the quotes of every string value, ``"'"`` or ``'"'``, or
      ``None`` by default, for quotes only where a string needs them, single
      ones unless it needs the escapes of the double ones, which a string
      gets with any of them;
    * ``quote_keys``, the same for the keys, which are quoted only where they
      need it by default;
    * ``multiline``, whether a string of several lines is a literal block
      scalar, ``True`` by default, or a quoted scalar; a string whose lines a
      block scalar cannot keep, as one with a first line that starts with a
      space, is quoted anyway;
    * ``explicit_start``, whether the document starts with ``---``,
      ``False`` by default; a scalar document always does;
    * ``version``, the YAML whose reader gets the strings back: ``'1.1'`` by
      default quotes also the strings that YAML 1.1 reads as other types,
      as ``yes``, ``off``, ``1_000``, ``12:30`` and ``2001-12-14``, which
      PyYAML reads so, and ``'1.2'`` only those of the core schema of YAML
      1.2, as ``true``, ``null`` and ``1.5``;
    * ``anchors``, whether a :class:`dict` or a :class:`list` that is there
      more than once has an anchor where it is first and an alias after it,
      ``True`` by default, or is written again; an anchor has the name of the
      key of the collection, or of the sequence of the item, with the
      characters that are not ``A-Z``, ``a-z``, ``0-9``, ``_`` and ``-`` as
      ``_``, ``id`` without a key, and a number from ``2`` for another
      anchor of the same name.
    * ``sort_keys``, whether the keys of a mapping are sorted, ``False`` by
      default, for the order of the :class:`dict`. ::

        # 'foo:\\n- "bar"\\n'
        dump({'foo': ['bar']}, indent_sequences=False, quote='"')
    """
    return dump_all(
        [value],
        indent=indent,
        indent_sequences=indent_sequences,
        quote=quote,
        quote_keys=quote_keys,
        multiline=multiline,
        explicit_start=explicit_start,
        version=version,
        anchors=anchors,
        sort_keys=sort_keys,
    )


def dump_all(
    values: Iterable[Any],
    *,
    indent: int = 2,
    indent_sequences: bool = True,
    quote: Literal["'", '"'] | None = None,
    quote_keys: Literal["'", '"'] | None = None,
    multiline: bool = True,
    explicit_start: bool = False,
    version: Literal['1.1', '1.2'] = '1.1',
    anchors: bool = True,
    sort_keys: bool = False,
) -> str:
    """::

        string = dump_all(values)

    Dump values to a YAML string of documents, one for each value, with the
    options of :func:`dump`, where the documents after the first one start
    with ``---``. ::

        # '--- first\\n--- second\\n'
        dump_all(['first', 'second'])
    """
    dumper = _Dumper(indent, indent_sequences, quote, quote_keys, multiline, version, anchors, sort_keys)
    lines: list[str] = []
    for i, value in enumerate(values):
        lines += dumper.document(value, explicit_start or i > 0)
    return ''.join(f'{line}\n' for line in lines)


def load(string: str) -> Any:
    """::

        value = load(string)

    Load a YAML string and return its document, or its last one when there
    are several, as the ``Load`` of ``YAML`` of Perl does, or ``None`` for an
    empty string. ::

        # {'foo': 'bar'}
        load('foo: bar')
    """
    documents = load_all(string)
    return documents[-1] if documents else None


def load_all(string: str) -> list[Any]:
    """::

        values = load_all(string)

    Load a YAML string and return a list of all its documents. ::

        # ['first', 'second']
        load_all('--- first\\n--- second\\n')
    """
    return _Loader(string).documents()


def _error(message: str) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'YAML {message}')


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _unquote_double(string: str) -> str:
    def unescape(m: re.Match[str]) -> str:
        if (code := m[1] or m[2] or m[3]) is not None:
            return chr(int(code, 16))
        return _ESCAPES.get(m[4], m[4])

    return re.sub(
        r'\\(?:x([0-9a-fA-F]{2})|u([0-9a-fA-F]{4})|U(0010[0-9a-fA-F]{4}|000[0-9a-fA-F]{5})|(["\\/ \t0LNP_abefnrtvz]))',
        unescape,
        string,
    )


# Not in CPAN::Meta::YAML: the type of a plain scalar of the core schema of YAML 1.2, where CPAN::Meta::YAML keeps a
# string, as Perl takes "8080" for 8080, and Python does not
def _resolve(string: str) -> Any:
    if re.fullmatch(r'~|null|Null|NULL', string):
        return None
    if re.fullmatch(r'true|True|TRUE', string):
        return True
    if re.fullmatch(r'false|False|FALSE', string):
        return False
    if re.fullmatch(r'[-+]?[0-9]+', string):
        return int(string)
    if re.fullmatch(r'0o[0-7]+', string):
        return int(string[2:], 8)
    if re.fullmatch(r'0x[0-9a-fA-F]+', string):
        return int(string[2:], 16)
    if re.fullmatch(r'[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?', string):
        return float(string)
    if m := re.fullmatch(r'([-+]?)\.(?:inf|Inf|INF)', string):
        return float(f'{m[1]}inf')
    if re.fullmatch(r'\.(?:nan|NaN|NAN)', string):
        return float('nan')
    return string


# The standard tags of the scalars, of the core schema of YAML 1.2 and, for the types of Python they have, of YAML 1.1
def _tag_binary(value: str) -> bytes:
    try:
        return base64.b64decode(re.sub(r'\s+', '', value), validate=True)
    except binascii.Error as e:
        raise ValueError(str(e)) from None


def _tag_bool(value: str) -> bool:
    if (resolved := _resolve(value)) is True or resolved is False:
        return resolved
    raise ValueError(value)


def _tag_float(value: str) -> float:
    if isinstance(resolved := _resolve(value), (int, float)) and not isinstance(resolved, bool):
        return float(resolved)
    raise ValueError(value)


def _tag_int(value: str) -> int:
    if isinstance(resolved := _resolve(value), int) and not isinstance(resolved, bool):
        return resolved
    raise ValueError(value)


def _tag_null(value: str) -> None:
    if value not in ('', '~') and _resolve(value) is not None:
        raise ValueError(value)


def _tag_timestamp(value: str) -> datetime.date | datetime.datetime:
    if re.fullmatch(r'\d{4}-\d\d-\d\d', value):
        return datetime.date.fromisoformat(value)
    return datetime.datetime.fromisoformat(re.sub(r'(?<=\d)[tT](?=\d)', 'T', value))


_TAGS: dict[str, Callable[[str], Any]] = {
    'binary': _tag_binary,
    'bool': _tag_bool,
    'float': _tag_float,
    'int': _tag_int,
    'null': _tag_null,
    'str': str,
    'timestamp': _tag_timestamp,
}


def _unquote_single(string: str) -> str:
    return string.replace("''", "'")


class _Loader:
    def __init__(self, string: str) -> None:
        self.anchors: dict[str, Any] = {}
        # A deque, whose popleft takes the first line as shift of Perl does, where pop(0) of a list moves all the others
        self.lines = collections.deque(re.split(r'\r\r?\n|\r|\n', string.removeprefix('\ufeff')))

        # The line break at the end ends the last line, it does not start an empty one
        if self.lines[-1] == '':
            self.lines.pop()

    def alias(self, name: str) -> Any:
        if name not in self.anchors:
            raise _error(f"found an unknown alias '*{name}'")
        return self.anchors[name]

    def block(self, string: str, indent: int | None) -> str:
        if not (m := re.search(r'^([|>])([+-]?)\s*(?:#.*)?\Z', string)):
            raise _error(f"does not support a feature in line '{string}'")

        # The lines more indented than the key, with the empty ones among them
        lines = self.lines
        block: list[str] = []
        depth: int | None = None
        while lines:
            if not lines[0].strip():
                block.append('')
                lines.popleft()
                continue
            if depth is None:
                if indent is not None and _indent(lines[0]) <= indent:
                    break
                depth = _indent(lines[0])
            if _indent(lines[0]) < depth:
                break
            block.append(lines.popleft()[depth:])

        # The empty lines at the end, which the chomping indicator keeps, strips or clips to one line break
        trailing = len(block) - len(content := _rstrip_empty(block))
        text = '\n'.join(content) if m[1] == '|' else _fold(content)
        if m[2] == '-' or not content:
            return text
        return text + '\n' * (1 + trailing if m[2] == '+' else 1)

    def documents(self) -> list[Any]:
        documents: list[Any] = []
        explicit = False
        lines = self.lines

        # The directive of the version
        if self.skip() and re.search(r'^%YAML[: ][\d.]+', lines[0]):
            lines.popleft()

        while self.skip():
            # The anchors of a document are its own
            self.anchors = {}

            # The start of a document, with a scalar after it
            if m := re.search(r'^---\s*(?:(.+?)\s*)?\Z', lines[0]):
                lines.popleft()
                if m[1] is not None and not re.search(r'^(?:#.+|%YAML[: ][\d.]+)\Z', m[1]):
                    documents.append(self.scalar(m[1], None))
                    continue
                explicit = True

            # An empty document
            if not self.skip() or re.search(r'^(?:---|\.\.\.)', lines[0]):
                documents.append(None)
                while lines and not lines[0].startswith('---'):
                    lines.popleft()
                explicit = False

            # Only the first document can do without its start
            elif not explicit and documents:
                raise _error(f"failed to classify the line '{lines[0]}'")

            # A sequence
            elif re.search(r'^\s*-(?:\s|$|-+$)', lines[0]):
                documents.append(self.sequence(0))

            # A flow collection
            elif re.search(r'^\s*[\[{]', lines[0]):
                documents.append(self.scalar(lines.popleft().strip(), None))

            # A mapping
            else:
                documents.append(self.mapping(_indent(lines[0])))

        return documents

    def end_of_document(self) -> bool:
        lines = self.lines
        if not self.skip():
            return True
        if not re.search(r'^(?:---|\.\.\.)', lines[0]):
            return False
        while lines and not lines[0].startswith('---'):
            lines.popleft()
        return True

    def flow(self, string: str) -> Any:
        # The lines of the collection, until its brackets are closed
        text = string
        while (end := _flow_end(text)) is None:
            if not self.lines:
                raise _error(f"failed to find the end of the flow collection '{string}'")
            if not _RE_BLANK.search(line := self.lines.popleft()):
                text += ' ' + line.strip()
        if (rest := text[end:].strip()) and not rest.startswith('#'):
            raise _error(f"found illegal characters after the flow collection '{text}'")
        return _Flow(text[:end], self).value()

    def mapping(self, indent: int, outer: int | None = None) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        merges: list[Any] = []
        lines = self.lines
        while not self.end_of_document():
            if (depth := _indent(lines[0])) < indent:
                break
            if depth > indent:
                raise _error(f"found bad indenting in line '{lines[0]}'")

            # Not in CPAN::Meta::YAML: the anchor of the key
            line = lines[0]
            anchor = None
            if m := _RE_KEY_ANCHOR.search(line):
                anchor = m[2]
                line = m[1] + line[m.end() :]

            # The key, quoted or not, or an alias, and the rest of the line
            if m := _RE_KEY_ALIAS.search(line):
                quote = '*'
                key = self.alias(m[1])
            elif re.search(r'^\s*[!&*]', line):
                raise _error(f"does not support a feature in line '{line}'")
            elif m := _key(line):
                quote = line.lstrip()[:1]
                if quote == "'":
                    key = _unquote_single(m[1])
                elif quote == '"':
                    key = _unquote_double(m[1])
                else:
                    key = _resolve(m[1].rstrip())
            elif re.search(r'^\s*\?', line):
                raise _error(f"does not support a feature in line '{line}'")
            else:
                raise _error(f"failed to classify line '{line}'")
            rest = line[m.end() :]
            lines.popleft()
            try:
                hash(key)
            except TypeError:
                raise _error(f"found a key that is not hashable in line '{line}'") from None
            if anchor is not None:
                self.anchors[anchor] = key

            # A value on the line, or below it, or none
            value = self.scalar(rest, indent) if rest else self.value(indent)
            if key == '<<' and quote not in ("'", '"', '*'):
                merges.append(value)
            else:
                mapping[key] = value

        return _merge(mapping, merges)

    def plain(self, string: str, indent: int | None) -> str:
        if re.search(r'^(?:-(?:\s|$)|[@%`])', string) or re.search(r':(?:\s|$)', string):
            raise _error(f"found illegal characters in plain scalar: '{string}'")
        plain = re.sub(r'\s+#.*\Z', '', string)
        if plain != string or indent is None:
            return plain

        # The lines more indented than the key, folded, which a comment ends
        lines = self.lines
        empty = 0
        while lines and (indent < _indent(lines[0]) or not lines[0].strip()):
            line = lines[0].strip()
            if line.startswith('#'):
                break
            lines.popleft()
            if not line:
                empty += 1
                continue
            if re.search(r':(?:\s|$)', line):
                raise _error(f"found illegal characters in plain scalar: '{line}'")
            continued = re.sub(r'\s+#.*\Z', '', line)
            plain += ('\n' * empty if empty else ' ') + continued
            empty = 0
            if continued != line:
                break
        return plain

    def quoted(self, string: str) -> str:
        double = string.startswith('"')
        pattern = _RE_DOUBLE if double else _RE_SINGLE

        # The lines of the scalar, until its quote is closed, folded
        text = string
        empty = 0
        while not (m := pattern.search(text)):
            if not self.lines:
                raise _error(f"failed to find the end of the quoted scalar '{string}'")
            line = self.lines.popleft().strip()
            if not line:
                empty += 1
                continue
            text = text.rstrip(' \t')
            if double and re.search(r'(?<!\\)(?:\\\\)*\\\Z', text) and not empty:
                text = text[:-1] + line
            else:
                text += ('\n' * empty if empty else ' ') + line
            empty = 0
        return _unquote_double(m[1]) if double else _unquote_single(m[1])

    def scalar(self, string: str, indent: int | None, item: bool = False) -> Any:
        string = string.rstrip()

        # Not in CPAN::Meta::YAML: an alias, the node of its anchor
        if string.startswith('*'):
            if not (m := re.search(rf'^\*({_ANCHOR})(?:\s+#.*)?\Z', string)):
                raise _error(f"found illegal characters after the alias '{string}'")
            return self.alias(m[1])

        # Not in CPAN::Meta::YAML: the properties of a node, an anchor and a standard tag, in either order
        anchor = tag = None
        while m := re.search(rf'^(?:&({_ANCHOR})|!!(\w+))(?:\s+|\Z)', string):
            if m[1] is not None and anchor is None:
                anchor = m[1]
            elif m[2] is not None and tag is None:
                tag = m[2]
            else:
                raise _error(f"found a property twice in line '{string}'")
            string = string[m.end() :]

        # A node below the anchor
        if anchor is not None and tag is None and (not string or string.startswith('#')):
            value = self.value(-1 if indent is None else indent, item)

        # The tag, which gives a scalar its type
        elif tag is not None:
            if (convert := _TAGS.get(tag)) is None or string.startswith(('[', '{')):
                raise _error(f"does not support a feature in line '!!{tag} {string}'")
            text = self.text(string, indent, False)
            try:
                value = convert(text)
            except ValueError:
                raise _error(f"found an invalid value of the tag !!{tag}: '{text}'") from None

        else:
            value = self.text(string, indent, True)

        # Unlike PyYAML: an anchor can be defined again, as in YAML 1.2, and an alias is the node of the last one
        if anchor is not None:
            self.anchors[anchor] = value
        return value

    def sequence(self, indent: int, outer: int | None = None) -> list[Any]:
        sequence: list[Any] = []
        lines = self.lines
        while not self.end_of_document():
            if (depth := _indent(lines[0])) < indent:
                break
            if depth > indent:
                raise _error(f"found bad indenting in line '{lines[0]}'")

            # Not in CPAN::Meta::YAML: a sequence that starts on the line of the item
            if m := re.search(r'^(\s*-\s+)-(?:\s|\Z)', lines[0]):
                lines[0] = lines[0].replace('-', ' ', 1)
                sequence.append(self.sequence(len(m[1])))

            # A mapping that starts on the line of the item
            elif (m := re.search(r'^(\s*-\s+)(?![\[{!|>])', lines[0])) and _is_key(lines[0][m.end() :]):
                lines[0] = lines[0].replace('-', ' ', 1)
                sequence.append(self.mapping(len(m[1]), indent))

            # An item whose value is below it, or none
            elif re.search(r'^\s*-\s*(?:#.*)?\Z', lines[0]):
                lines.popleft()
                sequence.append(self.value(indent, True))

            # An item with a value
            elif m := re.search(r'^\s*-\s+(.+?)\s*\Z', lines[0]):
                lines.popleft()
                sequence.append(self.scalar(m[1], indent, True))

            # The key of a mapping after a sequence at its indentation
            elif outer is not None and indent == outer:
                break

            else:
                raise _error(f"failed to classify line '{lines[0]}'")

        return sequence

    def skip(self) -> bool:
        # The empty lines and the lines of comments, before the next line of the structure
        lines = self.lines
        while lines and _RE_BLANK.search(lines[0]):
            lines.popleft()
        return bool(lines)

    def text(self, string: str, indent: int | None, resolve: bool) -> Any:
        if string.startswith(('[', '{')):
            return self.flow(string)
        if string.startswith(("'", '"')):
            return self.quoted(string)
        if re.search(r'^[!&*]', string):
            raise _error(f"does not support a feature in line '{string}'")
        if string.startswith(('|', '>')):
            return self.block(string, indent)
        plain = self.plain(string, indent)
        return _resolve(plain) if resolve else plain

    def value(self, indent: int, item: bool = False) -> Any:
        # A sequence, a mapping or a scalar below its key or its item, or nothing
        lines = self.lines
        if not self.skip() or re.search(r'^(?:---|\.\.\.)', lines[0]):
            return None
        depth = _indent(lines[0])
        if m := re.search(r'^(\s*)-(?:\s|\Z)', lines[0]):
            if item and len(m[1]) == indent:
                return None
            if len(m[1]) < indent or item and len(m[1]) <= indent:
                return None
            return self.sequence(len(m[1]), indent)
        if depth <= indent:
            return None
        if _is_key(lines[0]):
            return self.mapping(depth, indent)
        if re.search(r'^\s*\?', lines[0]):
            raise _error(f"does not support a feature in line '{lines[0]}'")
        return self.scalar(lines.popleft().strip(), indent)


class _Flow:
    # A flow collection, in one string, with the anchors of its document
    def __init__(self, text: str, loader: _Loader) -> None:
        self.loader = loader
        self.text = text
        self.pos = 0

    def entry(self, end: str) -> tuple[Any, bool]:
        # A node, or a pair of a key and a value, as a mapping is an entry of a sequence
        if (c := self.peek()) in ('"', "'"):
            key: Any = self.quoted()
        elif c in ('[', '{', '*', '&'):
            return self.node(), False
        else:
            key = self.plain(end)
        if self.peek() == ':':
            self.pos += 1
            value = None if self.peek() in (',', end) else self.node()
            return {key if c in ('"', "'") else _resolve(key): value}, True
        return (key if c in ('"', "'") else _resolve(key)), False

    def error(self) -> Pyjo.Exception.object:
        return _error(f"failed to parse the flow collection '{self.text}' at offset {self.pos}")

    def mapping(self) -> dict[Any, Any]:
        mapping: dict[Any, Any] = {}
        merges: list[Any] = []
        self.pos += 1
        while (c := self.peek()) != '}':
            key = self.quoted() if c in ('"', "'") else _resolve(self.plain('}'))
            value = None
            if self.peek() == ':':
                self.pos += 1
                value = None if self.peek() in (',', '}') else self.node()
            if key == '<<' and c not in ('"', "'"):
                merges.append(value)
            else:
                mapping[key] = value
            if self.peek() == ',':
                self.pos += 1
            elif self.peek() != '}':
                raise self.error()
        self.pos += 1
        return _merge(mapping, merges)

    def name(self) -> str:
        # The name of an anchor or an alias, after its indicator
        if not (m := re.compile(_ANCHOR).match(self.text, self.pos + 1)):
            raise self.error()
        self.pos = m.end()
        return m[0]

    def node(self) -> Any:
        c = self.peek()
        if c == '*':
            return self.loader.alias(self.name())
        if c == '&':
            anchor = self.name()
            self.loader.anchors[anchor] = value = self.node()
            return value
        if c == '[':
            return self.sequence()
        if c == '{':
            return self.mapping()
        if c in ('"', "'"):
            return self.quoted()
        return _resolve(self.plain(None))

    def peek(self) -> str:
        text = self.text
        while self.pos < len(text) and text[self.pos] in ' \t':
            self.pos += 1
        if self.pos >= len(text):
            raise self.error()
        return text[self.pos]

    def plain(self, end: str | None) -> str:
        text = self.text
        start = self.pos
        while self.pos < len(text):
            c = text[self.pos]
            if c in ',[]{}' or c == ':' and (self.pos + 1 == len(text) or text[self.pos + 1] in ' ,[]{}'):
                break
            self.pos += 1
        plain = text[start : self.pos].strip()
        if not plain or re.search(r'^[!&*@`|>%#]|^-(?:\s|$)', plain):
            raise self.error()
        return plain

    def quoted(self) -> str:
        text = self.text
        quote = text[self.pos]
        pattern = _DOUBLE_QUOTED if quote == '"' else _SINGLE_QUOTED
        if not (m := re.compile(pattern).match(text, self.pos)):
            raise self.error()
        self.pos = m.end()
        return _unquote_double(m[1]) if quote == '"' else _unquote_single(m[1])

    def sequence(self) -> list[Any]:
        sequence: list[Any] = []
        self.pos += 1
        while self.peek() != ']':
            sequence.append(self.entry(']')[0])
            if self.peek() == ',':
                self.pos += 1
            elif self.peek() != ']':
                raise self.error()
        self.pos += 1
        return sequence

    def value(self) -> Any:
        value = self.node()
        if self.text[self.pos :].strip():
            raise self.error()
        return value


# Not in CPAN::Meta::YAML: the merge keys of a mapping, << of YAML 1.1, which PyYAML reads too: the keys of the
# mappings that they name, of the earlier ones first, with the keys of the mapping itself over them
def _merge(mapping: dict[Any, Any], merges: list[Any]) -> dict[Any, Any]:
    if not merges:
        return mapping
    merged: dict[Any, Any] = {}
    for merge in merges:
        sources: list[Any] = cast(list[Any], merge) if isinstance(merge, list) else [merge]
        for source in reversed(sources):
            if not isinstance(source, dict):
                raise _error('found a merge key with a value that is not a mapping or a sequence of mappings')
            merged.update(cast(dict[Any, Any], source))
    merged.update(mapping)
    return merged


# The key at the start of a line, quoted, which only the pattern of its quotes reads, or not
def _key(line: str) -> re.Match[str] | None:
    if (stripped := line.lstrip()).startswith("'"):
        return _RE_KEY_SINGLE.search(line)
    if stripped.startswith('"'):
        return _RE_KEY_DOUBLE.search(line)
    return _RE_KEY_UNQUOTED.search(line)


def _is_key(line: str) -> bool:
    line = _RE_KEY_ANCHOR.sub(r'\1', line, count=1)
    return _key(line) is not None or _RE_KEY_ALIAS.search(line) is not None


# The end of the flow collection at the start of a string, after its closing bracket, or None while it is open
def _flow_end(text: str) -> int | None:
    depth = 0
    quote = ''
    i = 0
    while i < len(text):
        c = text[i]
        if quote == '"':
            if c == '\\':
                i += 1
            elif c == '"':
                quote = ''
        elif quote == "'":
            if c == "'" and text[i + 1 : i + 2] == "'":
                i += 1
            elif c == "'":
                quote = ''
        elif c in ('"', "'"):
            quote = c
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


# The lines of a folded block scalar: a line break between two lines is a space, an empty line a line break, and the
# lines more indented keep their line breaks
def _fold(lines: list[str]) -> str:
    folded = ''
    previous: str | None = None
    empty = 0
    for line in lines:
        if not line:
            empty += 1
            continue
        if previous is None:
            folded = '\n' * empty + line
        elif not empty and not previous[:1].isspace() and not line[:1].isspace():
            folded += ' ' + line
        elif previous[:1].isspace() or line[:1].isspace():
            folded += '\n' * (1 + empty) + line
        else:
            folded += '\n' * empty + line
        previous = line
        empty = 0
    return folded


def _rstrip_empty(lines: list[str]) -> list[str]:
    end = len(lines)
    while end and not lines[end - 1]:
        end -= 1
    return lines[:end]


# The characters that a double quoted scalar escapes, which a single quoted and a plain one cannot have, and the ones
# that a literal block scalar cannot have either, which are the same without the line break and the tab
_RE_ESCAPE = re.compile(r'["\\\x00-\x1f\x7f-\x9f\u2028\u2029\ufeff\ud800-\udfff\ufffe\uffff]')
_RE_UNQUOTABLE = re.compile(r'[\x00-\x1f\x7f-\x9f\u2028\u2029\ufeff\ud800-\udfff\ufffe\uffff]')
_RE_UNLITERAL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029\ufeff\ud800-\udfff\ufffe\uffff]')

_ESCAPED = {
    '\x00': '\\0',
    '\x07': '\\a',
    '\x08': '\\b',
    '\x09': '\\t',
    '\x0a': '\\n',
    '\x0b': '\\v',
    '\x0c': '\\f',
    '\x0d': '\\r',
    '\x1b': '\\e',
    '"': '\\"',
    '\\': '\\\\',
    '\x85': '\\N',
    '\u2028': '\\L',
    '\u2029': '\\P',
}

# The plain scalars that YAML 1.1 reads as other types than a string, as PyYAML does: booleans, numbers with
# underscores, of base 2 and 60, and timestamps
_RE_YAML11 = re.compile(
    r'[yYnN]|yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF|='
    r'|[-+]?(?:0b[01_]+|0x[0-9a-fA-F_]+|[0-9][0-9_]*(?::[0-5]?[0-9])*(?:\.[0-9_]*)?|\.[0-9_]+)(?:[eE][-+]?[0-9]+)?'
    r'|[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:(?:[Tt]|[ \t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}.*)?'
)


class _Dumper:
    def __init__(
        self,
        indent: int,
        indent_sequences: bool,
        quote: str | None,
        quote_keys: str | None,
        multiline: bool,
        version: str,
        anchors: bool,
        sort_keys: bool = False,
    ) -> None:
        if indent < 1:
            raise ValueError(f'indent must be 1 or more, not {indent}')
        for name, value in (('quote', quote), ('quote_keys', quote_keys)):
            if value not in (None, "'", '"'):
                raise ValueError(f"""{name} must be "'", '"' or None, not {value!r}""")
        if version not in ('1.1', '1.2'):
            raise ValueError(f"version must be '1.1' or '1.2', not {version!r}")
        self.anchors = anchors
        self.sort_keys = sort_keys
        self.counts: dict[int, int] = {}
        self.indent = indent
        self.indent_sequences = indent_sequences
        self.multiline = multiline
        self.names: dict[int, str] = {}
        self.parents: set[int] = set()
        self.quote = quote
        self.quote_keys = quote_keys
        self.yaml11 = version == '1.1'

    def collection(self, value: Any, column: int, name: str) -> list[str] | None:
        # The lines of a collection that is not empty, which is not a scalar, or None
        if not value or not isinstance(value, (dict, list, tuple)):
            return None
        collection = cast(dict[Any, Any] | list[Any] | tuple[Any, ...], value)
        if id(collection) in self.parents:
            raise _error('found a collection inside itself')
        self.parents.add(id(collection))
        if isinstance(collection, dict):
            lines = self.mapping(collection, column)
        else:
            lines = self.sequence(collection, column, name)
        self.parents.remove(id(collection))
        return lines

    def count(self, value: Any) -> None:
        # The times that each dict and list is there, and the ones inside it, the first time
        if isinstance(value, tuple):
            for item in cast(tuple[Any, ...], value):
                self.count(item)
        elif isinstance(value, (dict, list)):
            collection = cast(dict[Any, Any] | list[Any], value)
            self.counts[id(collection)] = count = self.counts.get(id(collection), 0) + 1
            if count == 1:
                for item in collection.values() if isinstance(collection, dict) else collection:
                    self.count(item)

    def document(self, value: Any, start: bool) -> list[str]:
        # The anchors of a document are its own
        self.counts = {}
        self.names = {}
        if self.anchors:
            self.count(value)

        if (lines := self.collection(value := _data(value), 0, 'id')) is not None:
            return ['---', *lines] if start else lines

        # A scalar after the start of its document, where the loader reads it
        text, block = self.scalar(value, 0)
        return [f'--- {text}', *block]

    def key(self, key: Any) -> str:
        if isinstance(key, str):
            return self.string(str.__str__(key), 0, self.quote_keys, False, True)[0]
        if (text := _plain_value(key)) is None:
            raise _error(f"does not support a key of the type '{type(key).__name__}'")
        return text

    def literal(self, string: str, column: int) -> tuple[str, list[str]] | None:
        # A literal block scalar, unless the loader would not read its lines back: its first line that is not empty
        # starts with a space, which needs the indicator of the indentation, or a line has only spaces
        body = string.rstrip('\n')
        lines = body.split('\n')
        first = next((line for line in lines if line), '')
        if not first or first[:1].isspace() or _RE_UNLITERAL.search(body):
            return None
        if any(line and not line.strip() for line in lines):
            return None

        # The final line breaks, which the chomping indicator strips, clips to one or keeps
        breaks = len(string) - len(body)
        chomping = '-' if breaks == 0 else '' if breaks == 1 else '+'
        pad = ' ' * (column + self.indent)
        return f'|{chomping}', [pad + line if line else '' for line in lines + [''] * (breaks - 1)]

    def mapping(self, mapping: dict[Any, Any], column: int) -> list[str]:
        lines: list[str] = []
        items = list(mapping.items())
        if self.sort_keys:
            items.sort(key=lambda item: str(item[0]))
        for key, value in items:
            prefix = ' ' * column + (text := self.key(key)) + ':'
            name = key if isinstance(key, str) else text
            value = _data(value)
            nested = column + self.indent if isinstance(value, dict) or self.indent_sequences else column
            if (reference := self.reference(value, name)).startswith('*'):
                lines.append(f'{prefix} {reference}')
            elif (below := self.collection(value, nested, name)) is not None:
                lines += [f'{prefix} {reference}' if reference else prefix, *below]
            else:
                text, block = self.scalar(value, column)
                lines += [f'{prefix} {reference} {text}' if reference else f'{prefix} {text}', *block]
        return lines

    def plain(self, string: str, key: bool) -> bool:
        # A string that the loader reads back as the same string without quotes
        if not string or string != string.strip() or _RE_UNQUOTABLE.search(string):
            return False
        if string[0] in '?:,[]{}#&*!|>\'"%@`' or re.search(r'^(?:-(?:\s|\Z|--)|\.\.\.)|\s#|:(?:\s|\Z)', string):
            return False
        if key and (string[0] == '-' or string == '<<'):
            return False
        if not isinstance(_resolve(string), str):
            return False
        return not (self.yaml11 and _RE_YAML11.fullmatch(string))

    def reference(self, value: Any, name: str) -> str:
        # The anchor of a dict or a list that is there more than once, where it is first, with the name of its key and
        # a number for another one of the name, and its alias after it
        if not isinstance(value, (dict, list)) or self.counts.get(key := id(cast(Any, value)), 0) < 2:
            return ''
        if (anchor := self.names.get(key)) is None:
            anchor = name = re.sub(r'[^0-9A-Za-z_-]+', '_', name).strip('_') or 'id'
            number = 1
            while anchor in self.names.values():
                number += 1
                anchor = f'{name}{number}'
            self.names[key] = anchor
            return f'&{anchor}'
        if key in self.parents:
            raise _error('found a collection inside itself')
        return f'*{anchor}'

    def scalar(self, value: Any, column: int) -> tuple[str, list[str]]:
        if isinstance(value, str):
            return self.string(str.__str__(value), column, self.quote, self.multiline)
        if (text := _plain_value(value)) is not None:
            return text, []
        if isinstance(value, dict):
            return '{}', []
        if isinstance(value, (list, tuple)):
            return '[]', []
        if isinstance(value, (bytes, bytearray)):
            return '!!binary ' + b64_encode(bytes(value), ''), []
        if isinstance(value, datetime.date):
            return '!!timestamp ' + value.isoformat(), []
        raise _error(f"does not support a value of the type '{type(value).__name__}'")

    def sequence(self, sequence: list[Any] | tuple[Any, ...], column: int, name: str) -> list[str]:
        lines: list[str] = []
        pad = ' ' * column
        for item in sequence:
            # A collection that starts on the line of the item, or below its anchor
            item = _data(item)
            if (reference := self.reference(item, name)).startswith('*'):
                lines.append(f'{pad}- {reference}')
            elif (nested := self.collection(item, column + 2, name)) is not None:
                if reference:
                    lines += [f'{pad}- {reference}', *nested]
                else:
                    lines += [f'{pad}- {nested[0][column + 2 :]}', *nested[1:]]
            else:
                text, block = self.scalar(item, column)
                lines += [f'{pad}- {reference} {text}' if reference else f'{pad}- {text}', *block]
        return lines

    def string(
        self, string: str, column: int, quote: str | None, multiline: bool, key: bool = False
    ) -> tuple[str, list[str]]:
        if multiline and '\n' in string and (block := self.literal(string, column)) is not None:
            return block
        if quote is None and self.plain(string, key):
            return string, []
        if quote != '"' and not _RE_UNQUOTABLE.search(string):
            return "'" + string.replace("'", "''") + "'", []
        return '"' + _RE_ESCAPE.sub(_escape, string) + '"', []


# An object that Pyjo.JSON encodes, as the value of its __json__ method, or as a string where its class has its own
# __str__
def _data(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str, bytes, bytearray, dict, list, tuple, datetime.date)):
        return cast(Any, value)
    if (method := getattr(value, '__json__', None)) is not None:
        return method()
    if type(value).__str__ is not builtins.object.__str__:
        return str(value)
    return value


def _escape(m: re.Match[str]) -> str:
    if (escaped := _ESCAPED.get(c := m[0])) is not None:
        return escaped
    return f'\\x{ord(c):02x}' if ord(c) < 0x100 else f'\\u{ord(c):04x}'


# The text of a null, a boolean or a number, which the loader reads back as the same value
def _plain_value(value: Any) -> str | None:
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return int.__repr__(value)
    if isinstance(value, float):
        if math.isnan(value):
            return '.nan'
        if math.isinf(value):
            return '.inf' if value > 0 else '-.inf'
        return float.__repr__(value)
    return None
