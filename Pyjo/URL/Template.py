"""
Pyjo.URL.Template - URI Templates
=================================
::

    from Pyjo.URL.Template import Template

    template = Template('https://api.github.com/repos/{owner}/{repo}/issues{?state,labels}')
    print(template.expand(owner='pyjoyment', repo='Pyjoyment', state='open'))
    print(template.match('https://api.github.com/repos/pyjoyment/Pyjoyment/issues?state=open'))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.URL.Template

    template = Pyjo.URL.Template.new('file:///project/{+path}')
    print(template.expand({'path': 'src/main.py'}))
    print(template.match('file:///project/src/main.py')['path'])

:mod:`Pyjo.URL.Template` is an implementation of the URI Templates of
:rfc:`6570`, of all its levels: a template is a URI with expressions in braces,
which :meth:`~Pyjo_URL_Template.expand` replaces with the values of their
variables, encoded as the operator of each expression says. ::

    # "/search?q=Hello%20World%21&lang=en"
    Pyjo.URL.Template.new('/search{?q,lang}').expand(q='Hello World!', lang='en')

:meth:`~Pyjo_URL_Template.match` is the opposite, which the RFC leaves to its
implementations: the values of the variables of a URI that the template
expands to, as a server that routes a URI by its template needs them. The URI
is matched from both of its ends, in a time linear in its length, so a URI of
a client cannot make it slow. One expression takes what the others leave: the
one of the reserved expansion ``{+var}``, of a fragment ``{#var}`` or with the
explode modifier ``{var*}``, of which a template has at most one, or else the
last expression of the template. Every other expression ends at the first
character of what follows it in the template, as ``{name}`` ends at the
``/`` of ``{name}/raw``. ::

    # {'owner': 'pyjoyment', 'path': 'src/main.py'}
    Pyjo.URL.Template.new('repo://{owner}/blob/{+path}').match('repo://pyjoyment/blob/src/main.py')

A template is for the URIs that a protocol gives as templates, as the resource
templates of the Model Context Protocol. A request of an application is
dispatched by its routes, whose patterns of :mod:`Pyjoyment.Routes.Pattern`
have placeholders with types, defaults and formats, which a template does not
have.

See also
--------

:mod:`Pyjo.URL`, :mod:`Pyjoyment.Routes.Pattern`, https://mojolicious.org.

It has no counterpart in Mojolicious, and is written from :rfc:`6570`.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.String.Unicode

from Pyjo.Util import decode, url_escape, url_unescape

import builtins
import re

from collections.abc import Mapping
from typing import Any, cast


type Anything = builtins.object

# The first character, the separator, whether the variables are named, the value of an empty named one, and whether
# the reserved characters stay, of each operator, as the table of the appendix A of RFC 6570 has them
_OPERATORS: dict[str, tuple[str, str, bool, str, bool]] = {
    '': ('', ',', False, '', False),
    '+': ('', ',', False, '', True),
    '#': ('#', ',', False, '', True),
    '.': ('.', '.', False, '', False),
    '/': ('/', '/', False, '', False),
    ';': (';', ';', True, '', False),
    '?': ('?', '&', True, '=', False),
    '&': ('&', '&', True, '=', False),
}

# The operators that RFC 6570 reserves for its future extensions
_FUTURE = '=,!@|'

# The tokens of a template, the variables of an expression, and the percent-encoded triplets of a value
_TOKEN = re.compile(r'\{([^{}]*)\}|([^{}]+)|(.)', re.S)
_VARSPEC = re.compile(
    r'((?:[A-Za-z0-9_]|%[0-9A-Fa-f]{2})(?:\.?(?:[A-Za-z0-9_]|%[0-9A-Fa-f]{2}))*)(?::([1-9][0-9]{0,3})|(\*))?'
)
_TRIPLET = re.compile(r'(%[0-9A-Fa-f]{2})')

# The characters that the unreserved expansion keeps, and the ones that the reserved expansion keeps too
_UNRESERVED = r'A-Za-z0-9\-._~'
_RESERVED = r":/?#\[\]@!$&'()*+,;="


class _Expression:
    # An expression of a template, with its operator and its variables, the names with their prefixes and explodes
    __slots__ = ('content', 'explode', 'first', 'ifemp', 'named', 'op', 'reserved', 'sep', 'variables')

    def __init__(self, op: str, variables: list[tuple[str, int | None, bool]]) -> None:
        self.op = op
        self.first, self.sep, self.named, self.ifemp, self.reserved = _OPERATORS[op]
        self.variables = variables
        self.explode = any(explode for _, _, explode in variables)

        # The characters of its content, after its first character, which match takes
        extra = ',' + _RESERVED if self.reserved else ','
        if self.named:
            extra += '=' + self.sep
        elif len(variables) > 1 or self.explode:
            extra += self.sep
        self.content = re.compile(rf'(?:[{_UNRESERVED}{re.escape(extra)}]|%[0-9A-Fa-f]{{2}})*')

    @property
    def wide(self) -> bool:
        # An expression that takes what the others leave, whose value has the separators
        return self.reserved or self.explode

    def expand(self, values: Mapping[str, Any]) -> str:
        items = [
            self._varspec(name, prefix, explode, value)
            for name, prefix, explode in self.variables
            if (value := values.get(name)) is not None and not (isinstance(value, list | tuple | dict) and not value)
        ]
        return self.first + self.sep.join(items) if items else ''

    def values(self, content: str | None) -> dict[str, Any] | None:
        # The values of the variables of the content of the expression, or None for a content that it does not expand to
        if content is None:
            return {}
        if not self.content.fullmatch(content):
            return None
        if self.named:
            return self._named(content)

        # An empty expression without a first character is one without values, as an undefined variable
        if not content and not self.first:
            return {}
        if len(self.variables) == 1:
            name, _, explode = self.variables[0]
            return {name: [_decode(part) for part in content.split(self.sep)] if explode else _decode(content)}
        parts = content.split(self.sep)
        if len(parts) > len(self.variables):
            return None
        return {name: _decode(part) for (name, _, _), part in zip(self.variables, parts, strict=False)}

    def _escape(self, value: str) -> str:
        return _escape(value, self.reserved)

    def _named(self, content: str) -> dict[str, Any] | None:
        names = {name: explode for name, _, explode in self.variables}
        values: dict[str, Any] = {}
        exploded: dict[str, str] = {}
        for item in content.split(self.sep) if content else []:
            name, _, value = item.partition('=')
            value = _decode(value)
            if (explode := names.get(name)) is None:
                if not self.explode:
                    return None
                exploded[name] = value
            elif explode:
                values.setdefault(name, []).append(value)
            else:
                values[name] = value

        # The pairs of an exploded variable whose names are not its own, as the keys of a dict
        if exploded:
            name = next(name for name, _, explode in self.variables if explode)
            if name in values:
                return None
            values[name] = exploded
        return values

    def _varspec(self, name: str, prefix: int | None, explode: bool, value: Any) -> str:
        # A variable of the expression, as the appendix A of RFC 6570 expands it
        if not isinstance(value, list | tuple | dict):
            string = _str(value)
            if prefix is not None:
                string = string[:prefix]
            if self.named:
                return name + ('=' + self._escape(string) if string else self.ifemp)
            return self._escape(string)

        if prefix is not None:
            raise Pyjo.Exception.new(f'Prefix modifier of a variable with a list or a dict: {name}')
        if isinstance(value, dict):
            pairs = [(_str(key), _str(item)) for key, item in cast(dict[Any, Any], value).items()]
        else:
            pairs = [(name, _str(item)) for item in cast(list[Any], value)]

        if not explode:
            if isinstance(value, dict):
                joined = ','.join(f'{self._escape(key)},{self._escape(item)}' for key, item in pairs)
            else:
                joined = ','.join(self._escape(item) for _, item in pairs)
            return f'{name}={joined}' if self.named else joined

        if self.named:
            return self.sep.join(
                self._escape(key) + ('=' + self._escape(item) if item else self.ifemp) for key, item in pairs
            )
        if isinstance(value, dict):
            return self.sep.join(f'{self._escape(key)}={self._escape(item)}' for key, item in pairs)
        return self.sep.join(self._escape(item) for _, item in pairs)


class Pyjo_URL_Template(Pyjo.Base.object):
    """
    :mod:`Pyjo.URL.Template` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(self, template: str = '') -> None:
        """::

            template = Pyjo.URL.Template.new('/search{?q,lang}')

        Construct a new :mod:`Pyjo.URL.Template` object from a template, or
        raise a :mod:`Pyjo.Exception` for one that is not valid.
        """
        self.template = template
        """::

            template = tpl.template

        The template, as a string.
        """

        self._tokens: list[str | _Expression] = []
        for expression, literal, other in _TOKEN.findall(template):
            if other:
                raise Pyjo.Exception.new(f'Unmatched brace in URI template: {template}')
            if literal:
                # A literal of the URI as it is, with the characters that a URI does not have encoded
                self._tokens.append(_escape(literal, True))
                continue
            self._tokens.append(_expression(expression, template))
        self._matcher: tuple[int, list[str | _Expression]] | None = None

    def __str__(self) -> str:
        """::

            string = str(tpl)

        The template.
        """
        return self.template

    @property
    def variables(self) -> list[str]:
        """::

            names = tpl.variables

        The names of the variables of the template, in the order of the
        template, each once. ::

            # ['owner', 'repo', 'state']
            Pyjo.URL.Template.new('/repos/{owner}/{repo}/issues{?state}').variables
        """
        names: dict[str, None] = {}
        for token in self._tokens:
            if isinstance(token, _Expression):
                names.update((name, None) for name, _, _ in token.variables)
        return list(names)

    def expand(self, variables: Mapping[str, Any] | None = None, /, **kwargs: Any) -> Pyjo.String.Unicode.object:
        """::

            url = tpl.expand(q='Hello World!')
            url = tpl.expand({'q': 'Hello World!', 'lang': 'en'})

        Expand the template with the values of its variables, as a
        :class:`dict` or as keyword arguments, and return the URI as a
        :mod:`Pyjo.String.Unicode` object, with the encoding that the RFC
        gives it, which :mod:`Pyjo.URL` would normalize. A value is a string, a number, a list or a
        tuple of them, or a :class:`dict` of them, and ``None``, an empty list
        and an empty dict are undefined, which their expressions leave out. A
        prefix modifier of a list or a dict raises a :mod:`Pyjo.Exception`. ::

            # "/repos/pyjoyment/Pyjoyment/issues?labels=bug,docs"
            template = Pyjo.URL.Template.new('/repos/{owner}/{repo}/issues{?labels}')
            template.expand(owner='pyjoyment', repo='Pyjoyment', labels=['bug', 'docs'])
        """
        values = {**(variables or {}), **kwargs}
        return Pyjo.String.Unicode.new(
            ''.join(token if isinstance(token, str) else token.expand(values) for token in self._tokens)
        )

    def match(self, uri: Anything) -> dict[str, Any] | None:
        """::

            variables = tpl.match('/search?q=Hello%20World%21')

        Match a URI, a string or a :mod:`Pyjo.URL` object, with the template,
        and return the values of the variables that it has, decoded, or
        ``None`` for a URI that does not match. The value of a variable with
        the explode modifier is a list, or a :class:`dict` for the pairs of a
        named one, and a list without it is a string with the commas, as the
        template cannot tell it from a string. A template whose expressions
        cannot be told apart, two of them that take what the others leave, or
        two that follow each other without a literal or the first character
        of an operator between them, raises a :mod:`Pyjo.Exception`. ::

            # {'q': 'Hello World!'}
            Pyjo.URL.Template.new('/search{?q,lang}').match('/search?q=Hello%20World%21')

            # {'path': ['src', 'main.py']}
            Pyjo.URL.Template.new('file:///project{/path*}').match('file:///project/src/main.py')
        """
        wide, tokens = self._compile()
        string = str(uri)

        # The tokens before the expression that takes what the others leave, from the beginning of the URI
        contents: list[tuple[_Expression, str | None]] = []
        start = 0
        for i in range(wide):
            token = tokens[i]
            if isinstance(token, str):
                if not string.startswith(token, start):
                    return None
                start += len(token)
                continue
            if token.first:
                if not string.startswith(token.first, start):
                    contents.append((token, None))
                    continue
                start += 1
            end = string.find(stop, start) if (stop := _first(tokens, i + 1)) else -1
            end = len(string) if end < 0 else end
            contents.append((token, string[start:end]))
            start = end

        # The tokens after it, from the end of the URI
        end = len(string)
        for i in range(len(tokens) - 1, wide, -1):
            token = tokens[i]
            if isinstance(token, str):
                if end - len(token) < start or not string.startswith(token, end - len(token)):
                    return None
                end -= len(token)
                continue
            delimiter = token.first or _last(tokens, i - 1)
            at = string.rfind(delimiter, start, end) if delimiter else -1
            at = start - 1 if at < 0 and not token.first else at

            # The first character of an operator that separates the variables too, once for each of them
            for _ in range(len(token.variables) - 1 if token.first == token.sep else 0):
                if (before := string.rfind(delimiter, start, at)) < 0:
                    break
                at = before
            if token.first:
                # An expression of a first character that is not there, or not its own, is one that is not there
                if at < 0 or token.values(string[at + 1 : end]) is None:
                    contents.append((token, None))
                    continue
                contents.append((token, string[at + 1 : end]))
                end = at
                continue
            contents.append((token, string[at + 1 : end]))
            end = at + 1

        # The expression in between, of what is left
        if wide < len(tokens):
            token = cast(_Expression, tokens[wide])
            middle = string[start:end]
            if token.first:
                if middle and not middle.startswith(token.first):
                    return None
                contents.append((token, middle[1:] if middle else None))
            else:
                contents.append((token, middle))
        elif start != end:
            return None

        values: dict[str, Any] = {}
        for token, content in contents:
            if (found := token.values(content)) is None:
                return None
            values.update(found)
        return values

    def _compile(self) -> tuple[int, list[str | _Expression]]:
        # The tokens of the template, and the index of the expression that takes what the others leave, once
        if (matcher := self._matcher) is not None:
            return matcher
        tokens = self._tokens
        expressions = [i for i, token in enumerate(tokens) if isinstance(token, _Expression)]
        wides = [i for i in expressions if cast(_Expression, tokens[i]).wide]
        if len(wides) > 1:
            raise Pyjo.Exception.new(f'More than one expression of a reserved or exploded value: {self.template}')
        for i in expressions:
            if i + 1 < len(tokens) and isinstance(after := tokens[i + 1], _Expression) and not after.first:
                raise Pyjo.Exception.new(f'Expressions without a literal between them: {self.template}')
        wide = wides[0] if wides else expressions[-1] if expressions else len(tokens)
        self._matcher = (wide, tokens)
        return self._matcher


def _decode(value: str) -> str:
    # A percent-encoded value of UTF-8, or of its bytes as characters where they are not UTF-8, as Pyjo.URL decodes
    data = url_unescape(value.encode())
    decoded = decode('UTF-8', data)
    return decoded if decoded is not None else data.decode('latin-1')


def _escape(value: str, reserved: bool) -> str:
    # A value percent-encoded as UTF-8, with the reserved characters and the percent-encoded triplets of a reserved one
    if not reserved:
        return url_escape(value.encode(), f'^{_UNRESERVED}'.encode()).decode()
    return ''.join(
        part if _TRIPLET.fullmatch(part) else url_escape(part.encode(), f'^{_UNRESERVED}{_RESERVED}'.encode()).decode()
        for part in _TRIPLET.split(value)
    )


def _expression(expression: str, template: str) -> _Expression:
    # An expression of a template, its operator and the list of its variables
    op = expression[:1] if expression[:1] in _OPERATORS else ''
    if not expression or expression[:1] in _FUTURE:
        raise Pyjo.Exception.new(f'Invalid expression in URI template: {{{expression}}} of {template}')
    variables: list[tuple[str, int | None, bool]] = []
    for varspec in expression[len(op) :].split(','):
        if (spec := _VARSPEC.fullmatch(varspec)) is None:
            raise Pyjo.Exception.new(f'Invalid expression in URI template: {{{expression}}} of {template}')
        variables.append((spec[1], int(spec[2]) if spec[2] else None, bool(spec[3])))
    return _Expression(op, variables)


def _first(tokens: list[str | _Expression], i: int) -> str:
    # The first character of a token, which ends the expression before it, or nothing at the end of the template
    if i >= len(tokens):
        return ''
    token = tokens[i]
    return token[0] if isinstance(token, str) else token.first


def _last(tokens: list[str | _Expression], i: int) -> str:
    # The last character of the literal before an expression without a first character
    token = tokens[i]
    return token[-1] if isinstance(token, str) else ''


def _str(value: Any) -> str:
    # A value as a string, a boolean as in JSON
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


new = Pyjo_URL_Template.new
object = Pyjo_URL_Template
Template = Pyjo_URL_Template
