"""
Pyjo.DOM.CSS - CSS selector engine
==================================
::

    from Pyjo.DOM.CSS import CSS

    # Select elements from DOM tree
    css = CSS(tree=tree)
    elements = css.select('h1, h2, h3')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.DOM.CSS

    # Select elements from DOM tree
    css = Pyjo.DOM.CSS.new(tree=tree)
    elements = css.select('h1, h2, h3')

:mod:`Pyjo.DOM.CSS` is the CSS selector engine used by :mod:`Pyjo.DOM`, based
on the `HTML Living Standard <https://html.spec.whatwg.org>`_ and
`Selectors Level 3 <https://www.w3.org/TR/css3-selectors/>`_.

Selectors
---------

All CSS selectors that make sense for a standalone parser are supported.

``*``
~~~~~

Any element. ::

    all = css.select('*')

``E``
~~~~~

An element of type ``E``. ::

    title = css.select('title')

``E[foo]``
~~~~~~~~~~

An ``E`` element with a ``foo`` attribute. ::

    links = css.select('a[href]')

``E[foo="bar"]``
~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute value is exactly equal to ``bar``. ::

    case_sensitive = css.select('input[type="hidden"]')
    case_sensitive = css.select('input[type=hidden]')

``E[foo="bar" i]``
~~~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute value is exactly equal to any
(ASCII-range) case-permutation of ``bar``. Note that this selector is
**EXPERIMENTAL** and might change without warning! ::

    case_insensitive = css.select('input[type="hidden" i]')
    case_insensitive = css.select('input[type=hidden i]')
    case_insensitive = css.select('input[class~="foo" i]')

This selector is part of `Selectors Level 4
<https://dev.w3.org/csswg/selectors-4>`_, which is still a work in progress.

``E[foo="bar" s]``
~~~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute value is exactly and case-sensitively
equal to ``bar``. Note that this selector is **EXPERIMENTAL** and might change
without warning! ::

    case_sensitive = css.select('input[type="hidden" s]')

This selector is part of `Selectors Level 4
<https://dev.w3.org/csswg/selectors-4>`_, which is still a work in progress.

``E[foo~="bar"]``
~~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute value is a list of
whitespace-separated values, one of which is exactly equal to ``bar``. ::

    foo = css.select('input[class~="foo"]')
    foo = css.select('input[class~=foo]')

``E[foo^="bar"]``
~~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute value begins exactly with the string
``bar``. ::

    begins_with = css.select('input[name^="f"]')
    begins_with = css.select('input[name^=f]')

``E[foo$="bar"]``
~~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute value ends exactly with the string
``bar``. ::

    ends_with = css.select('input[name$="o"]')
    ends_with = css.select('input[name$=o]')

``E[foo*="bar"]``
~~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute value contains the substring ``bar``. ::

    contains = css.select('input[name*="fo"]')
    contains = css.select('input[name*=fo]')

``E[foo|="en"]``
~~~~~~~~~~~~~~~~

An ``E`` element whose ``foo`` attribute has a hyphen-separated list of values
beginning (from the left) with ``en``. ::

    english = css.select('link[hreflang|=en]')

``E:root``
~~~~~~~~~~

An ``E`` element, root of the document. ::

    root = css.select(':root')

``E:nth-child(n)``
~~~~~~~~~~~~~~~~~~

An ``E`` element, the ``n-th`` child of its parent. ::

    third = css.select('div:nth-child(3)')
    odd = css.select('div:nth-child(odd)')
    even = css.select('div:nth-child(even)')
    top3 = css.select('div:nth-child(-n+3)')

``E:nth-last-child(n)``
~~~~~~~~~~~~~~~~~~~~~~~

An ``E`` element, the ``n-th`` child of its parent, counting from the last one. ::

    third = css.select('div:nth-last-child(3)')
    odd = css.select('div:nth-last-child(odd)')
    even = css.select('div:nth-last-child(even)')
    bottom3 = css.select('div:nth-last-child(-n+3)')

``E:nth-of-type(n)``
~~~~~~~~~~~~~~~~~~~~

An ``E`` element, the ``n-th`` sibling of its type. ::

    third = css.select('div:nth-of-type(3)')
    odd = css.select('div:nth-of-type(odd)')
    even = css.select('div:nth-of-type(even)')
    top3 = css.select('div:nth-of-type(-n+3)')

``E:nth-last-of-type(n)``
~~~~~~~~~~~~~~~~~~~~~~~~~

An ``E`` element, the ``n-th`` sibling of its type, counting from the last one. ::

    third = css.select('div:nth-last-of-type(3)')
    odd = css.select('div:nth-last-of-type(odd)')
    even = css.select('div:nth-last-of-type(even)')
    bottom3 = css.select('div:nth-last-of-type(-n+3)')

``E:first-child``
~~~~~~~~~~~~~~~~~

An ``E`` element, first child of its parent. ::

    first = css.select('div p:first-child')

``E:last-child``
~~~~~~~~~~~~~~~~

An ``E`` element, last child of its parent. ::

    last = css.select('div p:last-child')

``E:first-of-type``
~~~~~~~~~~~~~~~~~~~

An ``E`` element, first sibling of its type. ::

    first = css.select('div p:first-of-type')

``E:last-of-type``
~~~~~~~~~~~~~~~~~~

An ``E`` element, last sibling of its type. ::

    last = css.select('div p:last-of-type')

``E:only-child``
~~~~~~~~~~~~~~~~

An ``E`` element, only child of its parent. ::

    lonely = css.select('div p:only-child')

``E:only-of-type``
~~~~~~~~~~~~~~~~~~

An ``E`` element, only sibling of its type. ::

    lonely = css.select('div p:only-of-type')

``E:empty``
~~~~~~~~~~~

An ``E`` element that has no children (including text nodes). ::

    empty = css.select(':empty')

``E:any-link``
~~~~~~~~~~~~~~

Alias for ``E:link``. Note that this selector is **EXPERIMENTAL** and might
change without warning! This selector is part of `Selectors Level 4
<https://dev.w3.org/csswg/selectors-4>`_, which is still a work in progress.

``E:link``
~~~~~~~~~~

An ``E`` element being the source anchor of a hyperlink of which the target is
not yet visited (``:link``) or already visited (``:visited``). Note that
:mod:`Pyjo.DOM.CSS` is not stateful, therefore ``:any-link``, ``:link`` and
``:visited`` yield exactly the same results. ::

    links = css.select(':any-link')
    links = css.select(':link')
    links = css.select(':visited')

``E:visited``
~~~~~~~~~~~~~

Alias for ``E:link``.

``E:scope``
~~~~~~~~~~~

An ``E`` element being a designated reference element. Note that this selector
is **EXPERIMENTAL** and might change without warning! ::

    scoped = css.select('a:not(:scope > a)')
    scoped = css.select('div :scope p')
    scoped = css.select('~ p')

This selector is part of `Selectors Level 4
<https://dev.w3.org/csswg/selectors-4>`_, which is still a work in progress.

``E:checked``
~~~~~~~~~~~~~

A user interface element ``E`` which is checked (for instance a radio-button or
checkbox). ::

    input = css.select(':checked')

``E.warning``
~~~~~~~~~~~~~

An ``E`` element whose class is "warning". ::

    warning = css.select('div.warning')

``E#myid``
~~~~~~~~~~

An ``E`` element with ``ID`` equal to "myid". ::

    foo = css.select('div#foo')

``E:not(s1, s2)``
~~~~~~~~~~~~~~~~~

An ``E`` element that does not match either compound selector ``s1`` or
compound selector ``s2``. Note that support for compound selectors is
**EXPERIMENTAL** and might change without warning! ::

    others = css.select('div p:not(:first-child, :last-child)')

Support for compound selectors was added as part of `Selectors Level 4
<https://dev.w3.org/csswg/selectors-4>`_, which is still a work in progress.

``E:is(s1, s2)``
~~~~~~~~~~~~~~~~

An ``E`` element that matches compound selector ``s1`` and/or compound selector
``s2``. Note that this selector is **EXPERIMENTAL** and might change without
warning! ::

    headers = css.select(':is(section, article, aside, nav) h1')

This selector is part of `Selectors Level 4
<https://dev.w3.org/csswg/selectors-4>`_, which is still a work in progress.

``E:has(rs1, rs2)``
~~~~~~~~~~~~~~~~~~~

An ``E`` element, if either of the relative selectors ``rs1`` or ``rs2``, when
evaluated with ``E`` as the :scope elements, match an element. Note that this
selector is **EXPERIMENTAL** and might change without warning! ::

    link = css.select('a:has(> img)')

This selector is part of `Selectors Level 4
<https://dev.w3.org/csswg/selectors-4>`_, which is still a work in progress.
Also be aware that this feature is currently marked ``at-risk``, so there is a
high chance that it will get removed completely.

``E:text(string_or_regex)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

An ``E`` element containing text content that substring matches
``string_or_regex`` case-insensitively or that regex matches
``string_or_regex``. For regular expressions use the format ``:text(/.../)``.
Note that this selector is **EXPERIMENTAL** and might change without warning! ::

    # Substring match
    login = css.select(':text(Log in)')

    # Regex match
    login = css.select(':text(/Log ?in/)')

    # Regex match (case-insensitive)
    login = css.select(':text(/(?i:Log ?in)/)')

This is a custom selector for :mod:`Pyjo.DOM` and not part of any spec.

``A|E``
~~~~~~~

An ``E`` element that belongs to the namespace alias ``A`` from `CSS Namespaces
Module Level 3 <https://www.w3.org/TR/css-namespaces-3/>`_. Keyword arguments
passed to selector methods are used to declare namespace aliases. ::

    elem = css.select('lq|elem', lq='http://example.com/q-markup')

Using an empty alias searches for an element that belongs to no namespace. ::

    div = css.select('|div')

``E F``
~~~~~~~

An ``F`` element descendant of an ``E`` element. ::

    headlines = css.select('div h1')

``E > F``
~~~~~~~~~

An ``F`` element child of an ``E`` element. ::

    headlines = css.select('html > body > div > h1')

``E + F``
~~~~~~~~~

An ``F`` element immediately preceded by an ``E`` element. ::

    second = css.select('h1 + h2')

``E ~ F``
~~~~~~~~~

An ``F`` element preceded by an ``E`` element. ::

    second = css.select('h1 ~ h2')

``E, F, G``
~~~~~~~~~~~

Elements of type ``E``, ``F`` and ``G``. ::

    headlines = css.select('h1, h2, h3')

``E[foo=bar][bar=baz]``
~~~~~~~~~~~~~~~~~~~~~~~

An ``E`` element whose attributes match all following attribute selectors. ::

    links = css.select('a[foo^=b][foo$=ar]')


Debugging
---------

You can set the ``PYJO_DOM_CSS_DEBUG`` environment variable to get some
advanced diagnostics information printed to :data:`sys.stderr`. ::

    PYJO_DOM_CSS_DEBUG=1

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::DOM::CSS <https://github.com/mojolicious/mojo/blob/v9.53/lib/Mojo/DOM/CSS.pm>`_
of Mojolicious 9.53.

Classes
-------
"""

import Pyjo.Base

from Pyjo.Util import getenv, trim, warn

import collections
import pprint
import re

from collections.abc import Iterator
from typing import Any, cast


# Any: a node of the tree of Pyjo.DOM.HTML
type Tree = list[Any]

# Any: a selector is a list of compounds, lists of the parts of the selector,
# with the combinators between them, as in Mojo
type Selector = list[Any]

DEBUG = bool(getenv('PYJO_DOM_CSS_DEBUG'))

_ESCAPE = r'\\[^0-9a-fA-F]|\\[0-9a-fA-F]{1,6}'
_ATTR_RE = re.compile(
    rf"""
  \[
  ((?:{_ESCAPE}|[\w\-])+)                               # Key
  (?:
    (\W)?=                                              # Operator
    (?:"((?:\\"|[^"])*)"|'((?:\\'|[^'])*)'|([^\]]+?))   # Value
    (?:\s+(?:(i|I)|s|S))?                               # Case-sensitivity
  )?
  \]
""",
    re.X,
)
_SEPARATOR_RE = re.compile(r'\s*,\s*')
_COMBINATOR_RE = re.compile(r'\s*([>+~])\s*')
_DESCENDANT_RE = re.compile(r'\s+')
_CLASS_ID_RE = re.compile(rf'([.#])((?:{_ESCAPE}\s?|[^,.#:\[\s>~+])+)')
_PSEUDO_CLASS_RE = re.compile(r':([\w\-]+)(?:\(((?:\([^)]+\)|[^)])+)\))?', re.S)
_TAG_RE = re.compile(rf'((?:{_ESCAPE}\s|\\[\s\S]|[^,.#:\[\s>~+])+)')


class Pyjo_DOM_CSS(Pyjo.Base.object):
    """
    :mod:`Pyjo.DOM.CSS` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(self, tree: Tree | None = None) -> None:
        self.tree: Tree | None = tree
        """::

            tree = css.tree
            css.tree = ['root']

        Document Object Model. Note that this structure should only be used very
        carefully since it is very dynamic.
        """

    def matches(self, css: object, **ns: str) -> bool | None:
        """::

            boolean = css.matches('head > title')
            boolean = css.matches('svg|line', svg='http://www.w3.org/2000/svg')

        Check if first node in :attr:`tree` matches the CSS selector. Trailing
        keyword arguments can be used to declare xml namespace aliases.
        """
        tree = self._tree()
        if tree[0] != 'tag':
            return None
        return _match(_compile(css, **ns), tree, tree, _root(tree))

    def select(self, css: object, **ns: str) -> list[Tree]:
        """::

            results = css.select('head > title')
            results = css.select('svg|line', svg='http://www.w3.org/2000/svg')

        Run CSS selector against :attr:`tree`. Trailing keyword arguments can be
        used to declare xml namespace aliases.
        """
        return _select_all(self._tree(), _compile(css, **ns))

    # Not in Mojolicious: the results one by one, as Pyjo.DOM.iterate takes them
    def select_iter(self, css: object, **ns: str) -> Iterator[Tree]:
        """::

            results = css.select_iter('head > title')
            results = css.select_iter('svg|line', svg='http://www.w3.org/2000/svg')

        Same as :meth:`select`, but returns an iterator, which runs the CSS
        selector against :attr:`tree` as its results are taken, in the order of
        the document.
        """
        return _select_iter(self._tree(), _compile(css, **ns))

    def select_one(self, css: object, **ns: str) -> Tree | None:
        """::

            result = css.select_one('head > title')
            result = css.select_one('svg|line', svg='http://www.w3.org/2000/svg')

        Run CSS selector against :attr:`tree` and stop as soon as the first node
        matched. Trailing keyword arguments can be used to declare xml namespace
        aliases.
        """
        return _select_one(self._tree(), _compile(css, **ns))

    def _tree(self) -> Tree:
        assert self.tree is not None
        return self.tree


def _absolutize(group: list[Selector]) -> list[Selector]:
    return [s if _is_scoped(s) else [[['pc', 'scope', None]], ' ', *s] for s in group]


def _all_tags(tree: Tree) -> list[Tree]:
    tags: list[Tree] = []
    queue = tree[1 if tree[0] == 'root' else 4 :]
    while len(queue):
        current = queue.pop(0)
        if current[0] != 'tag':
            continue
        tags.append(current)
        queue[0:0] = current[4:]

    return tags


def _attr(name: str, value_re: re.Pattern[str] | None, current: Tree) -> bool:
    attrs = current[2]
    if name not in attrs:
        return False

    value = attrs[name]
    if value is None and value_re is not None:
        return False
    return value_re is None or bool(value_re.search(cast(str, value)))


def _compile(css: object, **ns: str) -> list[Selector]:
    string = trim(str(css))

    group: list[Selector] = [[]]
    pos = 0
    while True:
        selectors = group[-1]
        if not len(selectors) or not isinstance(selectors[-1], list):
            selectors.append([])
        last = cast(list[Any], selectors[-1])

        # Separator
        if m := _SEPARATOR_RE.match(string, pos):
            group.append([])

        # Combinator
        elif m := _COMBINATOR_RE.match(string, pos):
            if not len(last):
                last.append(['pc', 'scope', None])
            selectors.append(m[1])

        # Descendant combinator
        elif m := _DESCENDANT_RE.match(string, pos):
            if not len(last):
                last.append(['pc', 'scope', None])
            selectors.append(' ')

        # Class or ID
        elif m := _CLASS_ID_RE.match(string, pos):
            name, op = ('class', '~') if m[1] == '.' else ('id', '')
            last.append(['attr', name, _value(op, m[2])])

        # Attributes
        elif m := _ATTR_RE.match(string, pos):
            value = m[3] if m[3] is not None else m[4] if m[4] is not None else m[5]
            last.append(['attr', _unescape(m[1]), _value(m[2] or '', value, m[6])])

        # Pseudo-class
        elif m := _PSEUDO_CLASS_RE.match(string, pos):
            name, args = m[1].lower(), m[2]
            value: Any = args

            # ":text" (raw text)
            if name == 'text':
                value = [re.compile(r[1]) if (r := re.match(r'^/(.+)/$', args)) else re.compile(re.escape(args), re.I)]

            # ":is" and ":not" (contains more selectors)
            if name in ('has', 'is', 'not'):
                value = _compile(args, **ns)

            # ":nth-*" (with An+B notation)
            if name.startswith('nth-'):
                value = _equation(args)

            # ":first-*", ":last-*" (rewrite to ":nth-(last-)*")
            if r := re.match(r'^(?:first-(.+)|(last-.+))$', name):
                name, value = 'nth-' + (r[2] or r[1]), [0, 1]

            last.append(['pc', name, value])

        # Tag
        elif m := _TAG_RE.match(string, pos):
            name = m[1]
            alias = None
            if r := re.match(r'^([^|]*)\|', name):
                name = name[r.end() :]
                alias = r[1] if r[1] != '*' else None
            if alias is not None and len(alias):
                if alias not in ns:
                    return [[['invalid']]]
                namespace = ns[alias]
            else:
                namespace = alias
            last.append(['tag', None if name == '*' else _name(name), _unescape(namespace)])

        else:
            if pos < len(string):
                raise ValueError(f'Unknown CSS selector: {string}')
            break

        pos = m.end()

    if DEBUG:
        warn(f'-- CSS Selector ({string})\n{pprint.pformat(group)}')
    return group


def _equation(equation: str | None) -> list[int]:
    if not equation:
        return [0, 0]

    # "even"
    if re.match(r'^\s*even\s*$', equation, re.I):
        return [2, 0]

    # "odd"
    if re.match(r'^\s*odd\s*$', equation, re.I):
        return [2, 1]

    # "4", "+4" or "-4"
    if m := re.match(r'^\s*((?:\+|-)?\d+)\s*$', equation):
        return [0, int(m[1])]

    # "n", "4n", "+4n", "-4n", "n+1", "4n-1", "+4n-1" (and other variations)
    if not (m := re.match(r'^\s*((?:\+|-)?(?:\d+)?)?n\s*((?:\+|-)\s*\d+)?\s*$', equation, re.I)):
        return [0, 0]
    a = m[1] or ''
    # Unlike Mojolicious: "+" is 1, as "" is, where Perl takes it for the number 0
    return [-1 if a == '-' else 1 if a in ('', '+') else int(a), int(''.join((m[2] or '0').split()))]


def _evaluate(group: list[Selector], tree: Tree, scope: Tree, pool: list[Tree]) -> list[Tree]:
    results: list[Tree] = []
    seen: set[int] = set()
    for selector in group:
        for node in _evaluate_one(selector, tree, scope, pool):
            if id(node) not in seen:
                seen.add(id(node))
                results.append(node)

    return results


def _evaluate_one(selector: Selector, tree: Tree, scope: Tree, pool: list[Tree]) -> list[Tree]:

    # Match the leftmost compound, then propagate forward through combinators
    parts = list(selector)
    compound = parts.pop(0)
    if not isinstance(compound, list):
        return []
    candidates = [n for n in pool if _selector(cast(list[Any], compound), n, tree, scope)]

    while len(parts):
        combinator = parts.pop(0)
        next = parts.pop(0) if len(parts) else None
        if not isinstance(next, list):
            return []

        seen: set[int] = set()
        new: list[Tree] = []
        for node in candidates:
            for cand in _step_forward(combinator, node):
                if id(cand) in seen:
                    continue
                seen.add(id(cand))
                if _selector(cast(list[Any], next), cand, tree, scope):
                    new.append(cand)
        candidates = new

    return candidates


def _is_scoped(selector: Selector) -> bool:
    compounds = [cast(list[list[Any]], c) for c in selector if isinstance(c, list)]
    for pc in (p for c in compounds for p in c if p[0] == 'pc'):
        # Selector with ":scope"
        if pc[1] == 'scope':
            return True

        # Argument of functional pseudo-class with ":scope"
        if pc[1] in ('has', 'is', 'not') and any(_is_scoped(s) for s in pc[2]):
            return True

    return False


def _match(group: list[Selector], current: Tree, tree: Tree, scope: Tree) -> bool | None:
    for selector in group:
        if _match_one(selector, current, tree, scope):
            return True
    return None


# Not in Mojolicious: the pool of _select, as a tree whose descendants and itself the steps back stay within
def _match_one(selector: Selector, current: Tree, tree: Tree, scope: Tree, pool: Tree | None = None) -> bool:

    # Match the rightmost compound, then propagate backward through combinators
    parts = list(reversed(selector))
    compound = parts.pop(0)
    if not isinstance(compound, list) or not _selector(cast(list[Any], compound), current, tree, scope):
        return False

    candidates = [current]
    while len(parts):
        combinator = parts.pop(0)
        next = parts.pop(0) if len(parts) else None
        if not isinstance(next, list):
            return False

        seen: set[int] = set()
        new: list[Tree] = []
        for node in candidates:
            for cand in _step_back(combinator, node, scope) if pool is None else _step_within(combinator, node, pool):
                if id(cand) in seen:
                    continue
                seen.add(id(cand))
                if _selector(cast(list[Any], next), cand, tree, scope):
                    new.append(cand)
        if not len(new):
            return False
        candidates = new

    return True


def _name(name: str) -> re.Pattern[str]:
    return re.compile(rf'(?:^|:){re.escape(_unescape(name) or "")}$')


def _namespace(ns: str, current: Tree) -> bool:
    attr = f'xmlns:{m[1]}' if (m := re.match(r'^([^:]+):', current[1])) else 'xmlns'
    node: Tree | None = current
    while node is not None:
        if node[0] == 'root':
            break
        if attr in node[2]:
            return node[2][attr] == ns

        node = node[3]

    # Failing to match yields true if searching for no namespace, false otherwise
    return not len(ns)


def _pc(name: str, args: Any, current: Tree, tree: Tree, scope: Tree) -> bool:

    # ":scope" (root can only be a :scope)
    if name == 'scope':
        return current is scope
    if current[0] == 'root':
        return False

    # ":checked"
    if name == 'checked':
        return 'checked' in current[2] or 'selected' in current[2]

    # ":not"
    if name == 'not':
        return not _match(args, current, current, scope)

    # ":is"
    if name == 'is':
        return bool(_match(args, current, current, scope))

    # ":has"
    if name == 'has':
        return _select_one(current, args) is not None

    # ":empty"
    if name == 'empty':
        return not any(n[0] not in ('comment', 'pi') for n in current[4:])

    # ":root"
    if name == 'root':
        return current[3] is not None and current[3][0] == 'root'

    # ":text"
    if name == 'text':
        return any(n[0] in ('text', 'raw') and args[0].search(n[1]) for n in current[4:])

    # ":any-link", ":link" and ":visited"
    if name in ('any-link', 'link', 'visited'):
        if current[0] != 'tag' or 'href' not in current[2]:
            return False
        return current[1] in ('a', 'area', 'link')

    # ":only-child" or ":only-of-type"
    if name in ('only-child', 'only-of-type'):
        type = current[1] if name == 'only-of-type' else None
        return all(s is current for s in _siblings(current, type))

    # ":nth-child", ":nth-last-child", ":nth-of-type" or ":nth-last-of-type"
    if isinstance(args, list):
        type = current[1] if name in ('nth-of-type', 'nth-last-of-type') else None
        siblings = _siblings(current, type)
        index = next(i for i, s in enumerate(siblings) if s is current)
        if name in ('nth-last-child', 'nth-last-of-type'):
            index = len(siblings) - 1 - index
        index += 1

        a, b = cast(list[int], args)
        delta = index - b
        if delta == 0:
            return True
        # Perl's % takes the sign of the right operand, as Python's does
        return a != 0 and (delta < 0) == (a < 0) and delta % a == 0

    # Everything else
    return False


def _root(tree: Tree) -> Tree:
    while tree[0] != 'root':
        tree = tree[3]
    return tree


def _select(scope: Tree, group: list[Selector]) -> list[Tree]:

    # Scoped selectors require the whole tree to be searched
    tree = scope
    if any(_is_scoped(s) for s in group):
        group, tree = _absolutize(group), _root(scope)

    # Pool includes $tree so ":scope" can match it, but results exclude it
    tags = _all_tags(tree)
    match = {id(n) for n in _evaluate(group, tree, scope, [tree, *tags])}

    return [n for n in tags if id(n) in match]


# Mojo's _select with $one false
def _select_all(scope: Tree, group: list[Selector]) -> list[Tree]:
    return _select(scope, group)


# Mojo's _select with $one true
def _select_one(scope: Tree, group: list[Selector]) -> Tree | None:

    # Scoped selectors require the whole tree to be searched
    selectors, tree = group, scope
    if any(_is_scoped(s) for s in selectors):
        selectors, tree = _absolutize(selectors), _root(scope)

    # Without combinators the first match in document order can be returned right away
    if all(len(s) == 1 and isinstance(s[0], list) for s in selectors):
        queue: collections.deque[Tree] = collections.deque(tree[1 if tree[0] == 'root' else 4 :])
        while queue:
            current = queue.popleft()
            if current[0] != 'tag':
                continue
            if any(_selector(s[0], current, tree, scope) for s in selectors):
                return current
            queue.extendleft(reversed(current[4:]))
        return None

    results = _select(scope, group)
    return results[0] if len(results) else None


# Not in Mojolicious: the results of _select one by one, in the order of the document, each matched backward within the
# pool that _evaluate starts from, so that the results are the same
def _select_iter(scope: Tree, group: list[Selector]) -> Iterator[Tree]:

    # Scoped selectors require the whole tree to be searched
    tree = scope
    if any(_is_scoped(s) for s in group):
        group, tree = _absolutize(group), _root(scope)

    queue: collections.deque[Tree] = collections.deque(tree[1 if tree[0] == 'root' else 4 :])
    while queue:
        current = queue.popleft()
        if current[0] != 'tag':
            continue
        queue.extendleft(reversed(current[4:]))
        if any(_match_one(s, current, tree, scope, tree) for s in group):
            yield current


def _selector(selector: list[Any], current: Tree, tree: Tree, scope: Tree) -> bool:

    # The root might be the scope
    is_tag = current[0] == 'tag'
    for s in selector:
        type = s[0]

        # Tag
        if is_tag and type == 'tag':
            if s[1] is not None and not s[1].search(current[1]):
                return False
            if s[2] is not None and not _namespace(s[2], current):
                return False

        # Attribute
        elif is_tag and type == 'attr':
            if not _attr(s[1], s[2], current):
                return False

        # Pseudo-class
        elif type == 'pc':
            if not _pc(s[1], s[2], current, tree, scope):
                return False

        # No match
        else:
            return False

    return True


def _siblings(current: Tree, type: str | None = None) -> list[Tree]:
    parent = current[3]
    siblings = [n for n in parent[1 if parent[0] == 'root' else 4 :] if n[0] == 'tag']
    if type is not None:
        siblings = [n for n in siblings if n[1] == type]
    return siblings


def _step_back(combinator: str, node: Tree, scope: Tree) -> list[Tree]:

    # " " (ancestors) and ">" (parent only)
    if combinator in (' ', '>'):
        ancestors: list[Tree] = []
        while node is not scope and node[0] != 'root' and (node := node[3]) is not None:
            ancestors.append(node)
            if combinator == '>' or node is scope:
                break
        return ancestors

    # "~" (preceding siblings) and "+" (immediately preceding)
    if node[0] == 'root':
        return []
    prev: list[Tree] = []
    for sib in _siblings(node):
        if sib is node:
            break
        prev.append(sib)
    return prev[-1:] if combinator == '+' else prev


# Not in Mojolicious: _step_back within a tree and its descendants, the pool of _select, whose siblings are outside
def _step_within(combinator: str, node: Tree, pool: Tree) -> list[Tree]:
    if node is pool or node[0] == 'root':
        return []
    if combinator in (' ', '>'):
        ancestors: list[Tree] = []
        while (parent := node[3]) is not None:
            ancestors.append(node := parent)
            if combinator == '>' or node is pool:
                break
        return ancestors
    return _step_back(combinator, node, pool)


def _step_forward(combinator: str, node: Tree) -> list[Tree]:

    # " " (descendants)
    if combinator == ' ':
        return _all_tags(node)

    # ">" (children only)
    if combinator == '>':
        return [n for n in node[1 if node[0] == 'root' else 4 :] if n[0] == 'tag']

    # "~" (following siblings) and "+" (immediately following)
    if node[0] == 'root':
        return []
    following: list[Tree] = []
    found = False
    for sib in _siblings(node):
        if found:
            following.append(sib)
        if sib is node:
            found = True
    return following[:1] if combinator == '+' else following


def _unescape(value: str | None) -> str | None:
    if value is None:
        return None

    # Remove escaped newlines
    value = value.replace('\\\n', '')

    # Unescape Unicode characters
    value = re.sub(r'\\([0-9a-fA-F]{1,6})\s?', lambda m: _chr(int(m[1], 16)), value)

    # Remove backslash
    return value.replace('\\', '')


def _chr(code: int) -> str:
    # Unlike Mojolicious: Perl makes a character of any number, Python only up
    # to 0x10FFFF, so a larger one is the replacement character
    return chr(code) if code <= 0x10FFFF else '\ufffd'


def _value(op: str, value: str | None, insensitive: str | None = None) -> re.Pattern[str] | None:
    if value is None:
        return None
    escaped = re.escape(_unescape(value) or '')
    flags = re.I if insensitive else 0

    # "~=" (word)
    if op == '~':
        return re.compile(rf'(?:^|\s+){escaped}(?:\s+|$)', flags)

    # "|=" (hyphen-separated)
    if op == '|':
        return re.compile(rf'^{escaped}(?:-|$)', flags)

    # "*=" (contains)
    if op == '*':
        return re.compile(escaped, flags)

    # "^=" (begins with)
    if op == '^':
        return re.compile(rf'^{escaped}', flags)

    # "$=" (ends with)
    if op == '$':
        return re.compile(rf'{escaped}$', flags)

    # Everything else
    return re.compile(rf'^{escaped}$', flags)


new = Pyjo_DOM_CSS.new
object = Pyjo_DOM_CSS
CSS = Pyjo_DOM_CSS
