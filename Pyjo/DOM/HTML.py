"""
Pyjo.DOM.HTML - HTML/XML engine
===============================
::

    from Pyjo.DOM.HTML import HTML

    # Turn HTML into DOM tree
    html = HTML()
    html.parse('<div><p id="a">Test</p><p id="b">123</p></div>')
    tree = html.tree

    # Or import the module, as in Google Python Style Guide

    import Pyjo.DOM.HTML

    # Turn HTML into DOM tree
    html = Pyjo.DOM.HTML.new()
    html.parse('<div><p id="a">Test</p><p id="b">123</p></div>')
    tree = html.tree

:mod:`Pyjo.DOM.HTML` is the HTML/XML engine used by :mod:`Pyjo.DOM`, based on
the `HTML Living Standard <https://html.spec.whatwg.org>`_ and the
`Extensible Markup Language (XML) 1.0 <https://www.w3.org/TR/xml/>`_.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::DOM::HTML <https://github.com/mojolicious/mojo/blob/v9.53/lib/Mojo/DOM/HTML.pm>`_
of Mojolicious 9.53.

Functions
---------
"""

import Pyjo.Base

from Pyjo.Util import (
    _bom,  # pyright: ignore[reportPrivateUsage]
    decode,
    html_attr_unescape,
    html_unescape,
    xml_escape,
)

import builtins
import codecs
import re

from collections.abc import Callable
from typing import Any, Self, cast


type Anything = builtins.object

# Any: a node is a list of its type, its content and its parent, and a tag also
# of its name, its attributes and its child nodes, as in Mojo
type Tree = list[Any]

_ATTR = r"""
  ([^<>=\s/0-9.\-][^<>=\s/]*|/)                        # Key
  (?:
    \s*=\s*
    (?s:(?P<quote>["'])(.*?)(?P=quote)|([^>\s]*))      # Value
  )?
  \s*
"""
_ATTR_RE = re.compile(_ATTR, re.X)
_MARKUP = {
    'doctype': re.compile(
        r"""
    <!DOCTYPE(
    \s+\w+                                        # Doctype
    (?:(?:\s+\w+)?(?:\s+(?:"[^"]*"|'[^']*'))+)?   # External ID
    (?:\s+\[.+?\])?                               # Int Subset
    \s*)>
""",
        re.X | re.I | re.S,
    ),
    'comment': re.compile(r'<!--(.*?)(?:--!?|(?<=<!--)-?(?=>))>', re.S),
    'cdata': re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.I | re.S),
    'pi': re.compile(r'<\?(.*?)\?>', re.S),
}
_TAG_RE = re.compile(r'<(/\s*)?([^<>\s/0-9.\-][^<>\s/]*)\s*')
_TEXT_RE = re.compile(r'[^<]+')
_STRAY_RE = re.compile(r'=\s*')

# HTML elements that only contain raw text
RAW = {'script', 'style'}

# HTML elements that only contain raw text and entities
RCDATA = {'title', 'textarea'}

# HTML elements with optional end tags
END = {'body': 'head', 'optgroup': 'optgroup', 'option': 'option'}

# HTML elements that break paragraphs
for _name in (
    *'address article aside blockquote details dialog div dl fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6'.split(),
    *'header hgroup hr main menu nav ol p pre section table ul'.split(),
):
    END[_name] = 'p'

# Container HTML elements that create their own scope
SCOPE = {'math', 'svg'}

# SVG and MathML elements that are HTML integration points
INTEGRATION = {'desc', 'foreignobject', 'mi', 'mn', 'mo', 'ms', 'mtext', 'title'}

# HTML table elements with optional end tags
TABLE = {'colgroup', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr'}

# HTML elements with optional end tags and scoping rules
CLOSE: dict[str, tuple[set[str], set[str]]] = {'li': ({'li'}, {'ul', 'ol'}), 'tr': ({'tr'}, {'table'})}
for _name in ('colgroup', 'tbody', 'tfoot', 'thead'):
    CLOSE[_name] = (TABLE, {'table'})
for _name in ('dd', 'dt'):
    CLOSE[_name] = ({'dd', 'dt'}, {'dl'})
for _name in ('rp', 'rt'):
    CLOSE[_name] = ({'rp', 'rt'}, {'ruby'})
for _name in ('td', 'th'):
    CLOSE[_name] = ({'th', 'td'}, {'table'})

# HTML parent elements that signal no more content when closed, but that are also phrasing content
NO_MORE_CONTENT = {'ruby': ['rt', 'rp'], 'select': ['option', 'optgroup']}

# HTML elements without end tags
EMPTY = set('area base br col embed hr img input keygen link menuitem meta param source track wbr'.split())

# HTML elements categorized as phrasing content (and obsolete inline elements)
PHRASING = set(
    (
        'a abbr area audio b bdi bdo br button canvas cite code data datalist del dfn em embed i iframe img input ins kbd '
        'keygen label link map mark math meta meter noscript object output picture progress q ruby s samp script select '
        'slot small span strong sub sup svg template textarea time u var video wbr '
        'acronym applet basefont big font strike tt'
    ).split()
)

# HTML elements that don't get their self-closing flag acknowledged
BLOCK = set(
    (
        'a address applet article aside b big blockquote body button caption center code col colgroup dd details dialog '
        'dir div dl dt em fieldset figcaption figure font footer form frameset h1 h2 h3 h4 h5 h6 head header hgroup html '
        'i iframe li listing main marquee menu nav nobr noembed noframes noscript object ol optgroup option p plaintext '
        'pre rp rt s script section select small strike strong style summary table tbody td template textarea tfoot th '
        'thead title tr tt u ul xmp'
    ).split()
)


class Pyjo_DOM_HTML(Pyjo.Base.object):
    """
    :mod:`Pyjo.DOM.HTML` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(self, tree: Tree | None = None, **kwargs: bool | None) -> None:
        self.tree: Tree = tree if tree is not None else ['root']
        """::

            tree = html.tree
            html.tree = ['root']

        Document Object Model. Note that this structure should only be used very
        carefully since it is very dynamic.
        """
        self._xml: bool | None = None
        self._xml_set = False
        if 'xml' in kwargs:
            self.xml = kwargs['xml']

    @property
    def xml(self) -> bool | None:
        """::

            boolean = html.xml
            html.xml = boolean

        Disable HTML semantics in parser and activate case-sensitivity, defaults
        to auto-detection based on a leading XML declaration.
        """
        return self._xml

    @xml.setter
    def xml(self, value: bool | None) -> None:
        self._xml = value
        self._xml_set = True

    def parse(self, html: Anything) -> Self:
        """::

            html = html.parse('<foo bar="baz">I ♥ Pyjoyment!</foo>')

        Parse HTML/XML fragment. Bytes are a whole document, whose encoding is
        found as the HTML Living Standard sniffs it: a byte order mark, the
        ``encoding`` of an XML declaration, a ``<meta charset>`` or
        ``<meta http-equiv="Content-Type">`` in the first 1024 bytes, and
        ``UTF-8`` by default.
        """
        # Not in Mojolicious: bytes, which Mojo::DOM takes as characters
        string = _decode(bytes(html)) if isinstance(html, (bytes, bytearray)) else str(html)

        # Detect XML from a leading declaration
        if not self._xml_set and re.match(r'﻿?\s*<\?xml[\s?]', string, re.I):
            self.xml = True

        xml = self.xml
        tree: Tree = ['root']
        current = [tree]
        unclosed: set[str] = set()
        pos = 0
        while (offset := pos) < len(string):
            # Text
            if m := _TEXT_RE.match(string, offset):
                pos = m.end()
                _node(current[0], 'text', html_unescape(m[0]))
                continue

            # DOCTYPE, comment, CDATA and processing instruction (only trying the regex for the opener keeps failures fast)
            next = string[offset + 1 : offset + 2]
            if next in ('!', '?'):
                opener = string[offset : offset + 9].upper()
                type = (
                    'comment'
                    if opener[:4] == '<!--'
                    else 'doctype'
                    if opener == '<!DOCTYPE'
                    else 'cdata'
                    if opener == '<![CDATA['
                    else 'pi'
                    if next == '?'
                    else None
                )

                if type and type not in unclosed:
                    if m := _MARKUP[type].match(string, offset):
                        pos, value = m.end(), m[1]

                        # DOCTYPE, CDATA (outside of foreign content) and processing instructions end at the first ">"
                        # in HTML
                        i = -1 if xml or type == 'comment' else value.find('>')
                        if i >= 0 and not (type == 'cdata' and _foreign(current[0])):
                            pos = m.start(1) + i + 1
                            value = value[:i]

                        _node(current[0], type, value)
                        continue

                    # Without an end for this one, there is none for later ones either (DOCTYPE can fail for other
                    # reasons)
                    if type != 'doctype':
                        unclosed.add(type)

            # Tag
            if m := _TAG_RE.match(string, offset):
                pos = m.end()
                is_end, tag = m[1] is not None, m[2] if xml else m[2].lower()

                # Stray "=" right after the tag name (like an empty attribute name)
                if stray := _STRAY_RE.match(string, pos):
                    pos = stray.end()

                # Attributes
                attrs: dict[str, str | None] = {}
                closing = False
                while a := _ATTR_RE.match(string, pos):
                    pos = a.end()
                    key = a[1] if xml else a[1].lower()
                    value = a[3] if a[3] is not None else a[4]

                    # Empty tag
                    if key == '/':
                        closing = True
                        continue

                    attrs[key] = html_attr_unescape(value) if value is not None else value

                # Incomplete tag
                if not string.startswith('>', pos):
                    pos = offset

                # End
                elif is_end:
                    pos += 1

                    # No more content
                    if not xml and (tags := NO_MORE_CONTENT.get(tag)):
                        for t in tags:
                            _end(t, xml, current)

                    _end(tag, xml, current)
                    continue

                # Start
                else:
                    pos += 1

                    # "image" is an alias for "img"
                    if not xml and tag == 'image':
                        tag = 'img'
                    _start(tag, attrs, xml, current)

                    # Element without end tag (self-closing)
                    if not xml and tag in EMPTY or (xml or tag not in BLOCK) and closing:
                        _end(tag, xml, current)

                    # Raw text elements (not in foreign content)
                    if xml or tag not in RAW and tag not in RCDATA or _foreign(current[0][3]):
                        continue

                    if tag == 'script':
                        script, found_end, pos = _script_content(string, pos)
                        if len(script):
                            _node(current[0], 'raw', script)
                        if found_end:
                            _end(tag, False, current)
                        continue

                    # Without an end tag for this element, there is none for later elements of the same type either
                    if tag in unclosed:
                        continue
                    if not (
                        raw := re.compile(rf'(.*?)</{re.escape(tag)}(?=[\s/>])[^>]*>?', re.S | re.I).match(string, pos)
                    ):
                        unclosed.add(tag)
                        continue
                    pos = raw.end()
                    if tag in RCDATA:
                        _node(current[0], 'text', html_unescape(raw[1]))
                    else:
                        _node(current[0], 'raw', raw[1])
                    _end(tag, False, current)
                    continue

            # Runaway "<"
            _node(current[0], 'text', '<')
            pos = offset + 1

        self.tree = tree
        return self

    def render(self) -> str:
        """::

            string = html.render()

        Render DOM to HTML/XML.
        """
        return _render(self.tree, self.xml)

    def tag(self, name: str, content: str | Callable[[], str] | None = None, /, **attrs: Any) -> Self:
        """::

            html = html.tag('div', 'safe content', id='foo')

        Generate HTML/XML tag.
        """
        self.tree = ['root', _tag(name, content, attrs)]
        return self


def tag_to_html(name: str, content: str | Callable[[], str] | None = None, /, **attrs: Any) -> str:
    """::

        string = tag_to_html('div', 'safe content', id='foo')

    Generate HTML/XML tag and render it right away. This is a significantly
    faster alternative to :meth:`~Pyjo_DOM_HTML.tag` for template systems that
    have to generate a lot of tags.
    """
    return _render(_tag(name, content, attrs), None)


# The encoding of an XML declaration at the start, and a charset of a meta element, of either form, outside of comments
_XML_ENCODING_RE = re.compile(rb'\s*<\?xml\s[^>]*?\bencoding\s*=\s*["\']([^"\'\s]+)', re.I)
_META_CHARSET_RE = re.compile(rb'<meta\s[^>]*?\bcharset\s*=\s*["\']?\s*([^"\'\s;/>]+)', re.I)
_COMMENT_RE = re.compile(rb'<!--.*?-->', re.S)


# Not in Mojolicious: the bytes of a whole document, decoded as the HTML Living Standard sniffs their encoding, after a
# byte order mark and the charset of the transport, with the default of Pyjoyment, and as the bytes they are when they
# do not decode, as Pyjo.Message.text has them
def _decode(data: bytes, charset: str | None = None, default: str | None = 'UTF-8') -> str:
    found, rest = _bom('UTF-8', data)
    if len(rest) != len(data):
        candidates = [found]
    else:
        head = _COMMENT_RE.sub(b'', data[:1024])
        xml, meta = _XML_ENCODING_RE.match(head), _META_CHARSET_RE.search(head)
        # A UTF-16 that an ASCII prescan has read is not one, as the HTML Living Standard says
        candidates = [charset, *(_ascii(m[1]) for m in (xml, meta) if m), default]
    for candidate in candidates:
        if (encoding := _encoding(candidate)) is not None:
            return text if (text := decode(encoding, rest)) is not None else rest.decode('latin-1')
    return rest.decode('latin-1')


def _ascii(label: bytes) -> str:
    encoding = label.decode('ascii', 'replace')
    return 'UTF-8' if _encoding(encoding) in ('utf-16-le', 'utf-16-be', 'utf-16') else encoding


# The name of a label that Python knows, where the labels of ASCII and Latin-1 are windows-1252, as WHATWG has them
def _encoding(label: str | None) -> str | None:
    if label is None:
        return None
    try:
        name = codecs.lookup(label).name
    except LookupError:
        return None
    return 'cp1252' if name in ('ascii', 'iso8859-1') else name


def _end(end: str, xml: bool | None, current: list[Tree]) -> None:

    # Search stack for start tag
    next: Tree | None = current[0]
    while next is not None:
        # Ignore useless end tag
        if next[0] == 'root':
            return

        # Don’t traverse a container tag
        if next[1] in SCOPE and next[1] != end:
            return

        # Right tag
        if next[1] == end:
            current[0] = next[3]
            return

        # Phrasing content can only cross phrasing content
        if not xml and end in PHRASING and next[1] not in PHRASING:
            return

        next = next[3]


def _foreign(next: Tree) -> bool:

    # Search stack for SVG and MathML elements, but stop at HTML integration points
    while next[0] != 'root':
        if next[1] in SCOPE:
            return True
        if next[1] in INTEGRATION:
            return False
        if next[1] == 'annotation-xml' and re.match(
            r'(?:text/html|application/xhtml\+xml)\Z', next[2].get('encoding') or '', re.I
        ):
            return False
        next = next[3]

    return False


def _node(current: Tree, type: str, content: str) -> None:
    current.append([type, content, current])


def _render(tree: Tree, xml: bool | None) -> str:

    # Tag
    type = tree[0]
    if type == 'tag':
        # Start tag
        tag = tree[1]
        result = f'<{tag}'

        # Attributes
        for key in sorted(tree[2]):
            value = tree[2][key]
            if value is None:
                result += f' {key}="{key}"' if xml else f' {key}'
                continue
            result += f' {key}="' + xml_escape(value if isinstance(value, str) else str(value)) + '"'

        # No children
        if len(tree) <= 4:
            return f'{result} />' if xml else f'{result}>' if tag in EMPTY else f'{result}></{tag}>'

        # Children
        result += '>' + ''.join(_render(n, xml) for n in tree[4:])

        # End tag
        return f'{result}</{tag}>'

    # Text (escaped)
    if type == 'text':
        return xml_escape(tree[1])

    # Raw text
    if type == 'raw':
        return tree[1]

    # Root
    if type == 'root':
        return ''.join(_render(n, xml) for n in tree[1:])

    # DOCTYPE
    if type == 'doctype':
        return '<!DOCTYPE' + tree[1] + '>'

    # Comment
    if type == 'comment':
        return '<!--' + tree[1] + '-->'

    # CDATA
    if type == 'cdata':
        return '<![CDATA[' + tree[1] + ']]>'

    # Processing instruction
    if type == 'pi':
        return '<?' + tree[1] + '?>'

    # Everything else
    return ''


_SCRIPT_END_RE = re.compile(r'</script(?=[\s/>])[^>]*>?', re.S | re.I)
_SCRIPT_END_TAG_RE = re.compile(r'</script(?=[\s/>])', re.S | re.I)


def _script_content(html: str, pos: int) -> tuple[str, bool, int]:
    start = pos

    state = 0

    while True:
        pos = re.compile(r'[^<]*' if state == 0 else r'[^<\-]*', re.S).match(html, pos).end()  # pyright: ignore[reportOptionalMemberAccess]

        p = pos
        if p >= len(html):
            return html[start:], False, pos

        if state == 0:
            if m := _SCRIPT_END_RE.match(html, pos):
                return html[start:p], True, m.end()
            elif html.startswith('<!--', pos):
                pos, state = pos + 4, 1
            else:
                pos = p + 1
        elif state == 1:
            if m := _SCRIPT_END_RE.match(html, pos):
                return html[start:p], True, m.end()
            elif html.startswith('-->', pos):
                pos, state = pos + 3, 0
            elif m := re.compile(r'<script(?=[\s/>])', re.S | re.I).match(html, pos):
                pos, state = m.end(), 2
            else:
                pos = p + 1
        else:
            if m := _SCRIPT_END_TAG_RE.match(html, pos):
                pos, state = m.end(), 1
            elif html.startswith('-->', pos):
                pos, state = pos + 3, 0
            else:
                pos = p + 1


def _start(start: str, attrs: dict[str, str | None], xml: bool | None, current: list[Tree]) -> None:

    # Autoclose optional HTML elements
    if not xml and current[0][0] != 'root':
        if end := END.get(start):
            _end(end, False, current)

        elif close := CLOSE.get(start):
            allowed, scope = close

            # Close allowed parent elements in scope
            parent = current[0]
            while parent[0] != 'root' and parent[1] not in scope:
                if parent[1] in allowed:
                    _end(parent[1], False, current)
                parent = parent[3]

    # New tag
    new: Tree = ['tag', start, attrs, current[0]]
    current[0].append(new)
    current[0] = new


def _tag(name: str, content: str | Callable[[], str] | None, attrs: dict[str, Any]) -> Tree:
    tree: Tree = ['tag', name, None, None]

    # Content
    if content is not None:
        tree.append(['raw', content()] if callable(content) else ['text', content])

    # Attributes
    tree[2] = attrs = dict(attrs)
    if not isinstance(data := attrs.get('data'), dict):
        return tree
    del attrs['data']
    for key, value in cast(dict[Any, Any], data).items():
        attrs['data-' + str(key).replace('_', '-').lower()] = value
    return tree


new = Pyjo_DOM_HTML.new
object = Pyjo_DOM_HTML
HTML = Pyjo_DOM_HTML
