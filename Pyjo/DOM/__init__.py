r"""
Pyjo.DOM - Minimalistic HTML/XML DOM parser with CSS selectors
==============================================================
::

    from Pyjo.DOM import DOM

    # Parse
    dom = DOM('<div><p id="a">Test</p><p id="b">123</p></div>')

    # Find
    print(dom.at('#b').text)
    print(dom.find('p').map('text').join("\n"))
    print(dom.find('[id]').map('attr', 'id').join("\n"))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.DOM

    # Parse
    dom = Pyjo.DOM.new('<div><p id="a">Test</p><p id="b">123</p></div>')

    # Find
    print(dom.at('#b').text)
    print(dom.find('p').map('text').join("\n"))
    print(dom.find('[id]').map('attr', 'id').join("\n"))

    # Iterate
    dom.find('p[id]').reverse().each(lambda e, num: print(e['id']))

    # Loop
    for e in dom.find('p[id]').each():
        print(e['id'], ':', e.text)

    # Modify
    dom.find('div p').last().append('<p id="c">456</p>')
    dom.at('#c').prepend(dom.new_tag('p', '789', id='d'))
    dom.find(':not(p)').map('strip')

    # Render
    print(dom)

:mod:`Pyjo.DOM` is a minimalistic and relaxed HTML/XML DOM parser with CSS
selector support. It will even try to interpret broken HTML and XML, so you
should not use it for validation or sanitization. Its interpretation of broken
markup can differ from that of a web browser.

Nodes and elements
------------------

When we parse an HTML/XML fragment, it gets turned into a tree of nodes. ::

    <!DOCTYPE html>
    <html>
      <head><title>Hello</title></head>
      <body>World!</body>
    </html>

There are currently eight different kinds of nodes, ``cdata``, ``comment``,
``doctype``, ``pi``, ``raw``, ``root``, ``tag`` and ``text``. Elements are
nodes of the type ``tag``. ::

    root
    |- doctype (html)
    +- tag (html)
       |- tag (head)
       |  +- tag (title)
       |     +- text (Hello)
       +- tag (body)
          +- text (World!)

While all node types are represented as :mod:`Pyjo.DOM` objects, some methods
like :meth:`~Pyjo_DOM.attr` and :attr:`~Pyjo_DOM.namespace` only apply to
elements.

HTML and XML
------------

:mod:`Pyjo.DOM` defaults to HTML semantics, that means all tags and attribute
names are lowercased and selectors need to be lowercase as well. ::

    # HTML semantics
    dom = Pyjo.DOM.new('<P ID="greeting">Hi!</P>')
    print(dom.at('p[id]').text)

If the document starts with an XML declaration, the parser will automatically
switch into XML mode and everything becomes case-sensitive. ::

    # XML semantics
    dom = Pyjo.DOM.new('<?xml version="1.0"?><P ID="greeting">Hi!</P>')
    print(dom.at('P[ID]').text)

HTML or XML semantics can also be forced with the :attr:`~Pyjo_DOM.xml`
attribute. ::

    # Force HTML semantics
    dom = Pyjo.DOM.new().set(xml=False).parse('<P ID="greeting">Hi!</P>')
    print(dom.at('p[id]').text)

    # Force XML semantics
    dom = Pyjo.DOM.new().set(xml=True).parse('<P ID="greeting">Hi!</P>')
    print(dom.at('P[ID]').text)

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::DOM <https://github.com/mojolicious/mojo/blob/v9.51/lib/Mojo/DOM.pm>`_
of Mojolicious 9.51.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Collection
import Pyjo.DOM.CSS
import Pyjo.DOM.HTML
import Pyjo.String.Mixin

import builtins
import re

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any, Self, cast, overload


if TYPE_CHECKING:
    import Pyjo.Iterator


type Anything = builtins.object

# Any: a node of the tree of Pyjo.DOM.HTML
type Tree = list[Any]


class _hybridmethod[C, **P, R]:
    """A method that is called on the class or on an object, as Perl's can be."""

    def __init__(self, func: Callable[..., R]) -> None:
        self.func = func
        self.__doc__ = func.__doc__

    def __get__(self, obj: Anything, objtype: type | None = None) -> Callable[..., R]:
        def bound(*args: Any, **kwargs: Any) -> R:
            return self.func(obj if obj is not None else objtype, *args, **kwargs)

        bound.__doc__ = self.__doc__
        return bound


class Pyjo_DOM(Pyjo.Base.object, Pyjo.String.Mixin.object):
    """
    :mod:`Pyjo.DOM` inherits all methods from :mod:`Pyjo.Base` and
    :mod:`Pyjo.String.Mixin` and implements the following new ones.
    """

    def __init__(self, html: object = None) -> None:
        """::

            dom = Pyjo.DOM.new()
            dom = Pyjo.DOM.new('<foo bar="baz">I ♥ Pyjoyment!</foo>')

        Construct a new :mod:`Pyjo.DOM` object and :meth:`parse` HTML/XML
        fragment if necessary.
        """
        self._html = Pyjo.DOM.HTML.new()
        if html is not None:
            self.parse(html)

    def __bool__(self) -> bool:
        """::

            boolean = bool(dom)

        Always true.
        """
        return True

    def __contains__(self, name: object) -> bool:
        """::

            boolean = 'id' in dom

        Check if this element has the attribute.
        """
        return name in self.attr()

    def __delitem__(self, name: str) -> None:
        """::

            del dom['id']

        Remove an attribute of this element.
        """
        self.attr().pop(name, None)

    @overload
    def __getitem__(self, key: str) -> str | None: ...

    @overload
    def __getitem__(self, key: int) -> 'Pyjo_DOM': ...

    @overload
    def __getitem__(self, key: slice) -> 'Pyjo.Collection.object[Pyjo_DOM]': ...

    def __getitem__(self, key: str | int | slice) -> 'str | None | Pyjo_DOM | Pyjo.Collection.object[Pyjo_DOM]':
        """::

            value = dom['id']
            node = dom[0]

        An attribute of this element, as :meth:`attr` gives it, or a child node,
        as :attr:`child_nodes` has it. ::

            # "test"
            dom.parse('<div id="test">Test</div>').at('div')['id']

            # "<!-- Test -->"
            dom.parse('<!-- Test --><b>123</b>')[0]
        """
        if isinstance(key, str):
            return self.attr(key)
        if isinstance(key, slice):
            return Pyjo.Collection.object(self.child_nodes[key])
        return self.child_nodes[key]

    def __iter__(self) -> Iterator['Pyjo_DOM']:
        """::

            for node in dom:
                ...

        Iterate the child nodes, as :attr:`child_nodes` has them.
        """
        return iter(self.child_nodes)

    def __len__(self) -> int:
        """::

            size = len(dom)

        Number of child nodes.
        """
        return len(_nodes(self.tree))

    def __setitem__(self, name: str, value: str | None) -> None:
        """::

            dom['id'] = 'test'

        Set an attribute of this element, as :meth:`attr` does.
        """
        self.attr({name: value})

    @property
    def all_text(self) -> str:
        r"""::

            text = dom.all_text

        Extract text content from all descendant nodes of this element. For
        HTML documents ``script`` and ``style`` elements are excluded. ::

            # "foo\nbarbaz\n"
            dom.parse("<div>foo\n<p>bar</p>baz\n</div>").at('div').all_text
        """
        return _text(_nodes(self.tree), self.xml, True)

    def ancestors(self, css: object = None) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.ancestors()
            collection = dom.ancestors('div ~ p')

        Find all ancestor elements of this node matching the CSS selector and
        return a :mod:`Pyjo.Collection` object containing these elements as
        :mod:`Pyjo.DOM` objects. All selectors from :mod:`Pyjo.DOM.CSS` are
        supported. ::

            # List tag names of ancestor elements
            print(dom.ancestors().map('tag').join("\\n"))
        """
        return _select(self._collect(_ancestors(self.tree)), css)

    def append(self, new: object) -> Self:
        """::

            dom = dom.append('<p>I ♥ Pyjoyment!</p>')
            dom = dom.append(Pyjo.DOM.new())

        Append HTML/XML fragment to this node (for all node types other than
        ``root``). ::

            # "<div><h1>Test</h1><h2>123</h2></div>"
            dom.parse('<div><h1>Test</h1></div>').at('h1').append('<h2>123</h2>').root

            # "<p>Test 123</p>"
            dom.parse('<p>Test</p>').at('p').child_nodes.first().append(' 123').root
        """
        return self._add(1, new)

    def append_content(self, new: object) -> Self:
        """::

            dom = dom.append_content('<p>I ♥ Pyjoyment!</p>')
            dom = dom.append_content(Pyjo.DOM.new())

        Append HTML/XML fragment (for ``root`` and ``tag`` nodes) or raw
        content to this node's content. ::

            # "<div><h1>Test123</h1></div>"
            dom.parse('<div><h1>Test</h1></div>').at('h1').append_content('123').root

            # "<!-- Test 123 --><br>"
            dom.parse('<!-- Test --><br>').child_nodes.first().append_content('123 ').root

            # "<p>Test<i>123</i></p>"
            dom.parse('<p>Test</p>').at('p').append_content('<i>123</i>').root
        """
        return self._content(True, False, new)

    def at(self, css: object, **ns: str) -> 'Pyjo_DOM | None':
        r"""::

            result = dom.at('div ~ p')
            result = dom.at('svg|line', svg='http://www.w3.org/2000/svg')

        Find first descendant element of this element matching the CSS
        selector and return it as a :mod:`Pyjo.DOM` object, or ``None`` if none
        could be found. All selectors from :mod:`Pyjo.DOM.CSS` are supported. ::

            # Find first element with "svg" namespace definition
            namespace = dom.at('[xmlns\:svg]')['xmlns:svg']

        Trailing keyword arguments can be used to declare xml namespace
        aliases. ::

            # "<rect></rect>"
            dom.parse('<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>').at(
                'svg|rect', svg='http://www.w3.org/2000/svg'
            )
        """
        if (result := self._css().select_one(css, **ns)) is None:
            return None
        return self._build(result, self.xml)

    # attr(**values) with no values is attr(), which the first overload types
    @overload
    def attr(self) -> dict[str, str | None]: ...  # pyright: ignore[reportOverlappingOverload]

    @overload
    def attr(self, name: str, /) -> str | None: ...

    @overload
    def attr(self, name: str, value: str | None, /) -> Self: ...

    @overload
    def attr(self, values: dict[str, Any], /) -> Self: ...

    @overload
    def attr(self, **values: Any) -> Self: ...

    def attr(self, *args: Any, **kwargs: Any) -> Any:
        """::

            attrs = dom.attr()
            foo = dom.attr('foo')
            dom = dom.attr({'foo': 'bar'})
            dom = dom.attr('foo', 'bar')
            dom = dom.attr(foo='bar')

        This element's attributes. ::

            # Remove an attribute
            del dom.attr()['id']

            # Attribute without value
            dom.attr(selected=None)

            # List id attributes
            print(dom.find('*').map('attr', 'id').compact().join("\\n"))
        """

        # Hash
        tree = self.tree
        attrs: dict[str, Any] = tree[2] if tree[0] == 'tag' else {}
        if not len(args) and not len(kwargs):
            return attrs

        # Get
        if len(args) == 1 and not len(kwargs) and not isinstance(args[0], dict):
            return attrs.get(args[0])

        # Set
        values = cast(dict[str, Any], args[0] if len(args) == 1 else dict(zip(args[::2], args[1::2], strict=True)))
        attrs.update(values, **kwargs)

        return self

    @property
    def child_nodes(self) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.child_nodes

        Return a :mod:`Pyjo.Collection` object containing all child nodes of
        this element as :mod:`Pyjo.DOM` objects. ::

            # "<p><b>123</b></p>"
            dom.parse('<p>Test<b>123</b></p>').at('p').child_nodes.first().remove()

            # "<!DOCTYPE html>"
            dom.parse('<!DOCTYPE html><b>123</b>').child_nodes.first()

            # " Test "
            dom.parse('<b>123</b><!-- Test -->').child_nodes.last().content
        """
        return self._collect(_nodes(self.tree))

    def children(self, css: object = None) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.children()
            collection = dom.children('div ~ p')

        Find all child elements of this element matching the CSS selector and
        return a :mod:`Pyjo.Collection` object containing these elements as
        :mod:`Pyjo.DOM` objects. All selectors from :mod:`Pyjo.DOM.CSS` are
        supported. ::

            # Show tag name of random child element
            print(dom.children().shuffle().first().tag)
        """
        return _select(self._collect(_nodes(self.tree, True)), css)

    @property
    def content(self) -> str:
        """::

            string = dom.content
            dom.content = '<p>I ♥ Pyjoyment!</p>'
            dom.content = Pyjo.DOM.new()

        Return this node's content or replace it with HTML/XML fragment (for
        ``root`` and ``tag`` nodes) or raw content. ::

            # "<b>Test</b>"
            dom.parse('<div><b>Test</b></div>').at('div').content

            # "<div><h1>123</h1></div>"
            dom.parse('<div><h1>Test</h1></div>').at('h1').set(content='123').root

            # "<p><i>123</i></p>"
            dom.parse('<p>Test</p>').at('p').set(content='<i>123</i>').root

            # "<div><h1></h1></div>"
            dom.parse('<div><h1>Test</h1></div>').at('h1').set(content='').root

            # " Test "
            dom.parse('<!-- Test --><br>').child_nodes.first().content

            # "<div><!-- 123 -->456</div>"
            dom.parse('<div><!-- Test -->456</div>').at('div').child_nodes.first().set(content=' 123 ').root
        """
        type = self.type
        if type in ('root', 'tag'):
            html = Pyjo.DOM.HTML.new(xml=self.xml)
            return ''.join(html.set(tree=n).render() for n in _nodes(self.tree))

        return self.tree[1]

    @content.setter
    def content(self, value: object) -> None:
        type = self.type
        if type in ('root', 'tag'):
            self._content(False, True, value)
            return

        self.tree[1] = value if isinstance(value, str) else str(value)

    @property
    def descendant_nodes(self) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.descendant_nodes

        Return a :mod:`Pyjo.Collection` object containing all descendant nodes
        of this element as :mod:`Pyjo.DOM` objects. ::

            # "<p><b>123</b></p>"
            dom.parse('<p><!-- Test --><b>123<!-- 456 --></b></p>').descendant_nodes.grep(
                lambda e: e.type == 'comment'
            ).map('remove').first()

            # "<p><b>test</b>test</p>"
            dom.parse('<p><b>123</b>456</p>').at('p').descendant_nodes.grep(
                lambda e: e.type == 'text'
            ).map('content', 'test').first().root
        """
        return self._collect(_all(_nodes(self.tree)))

    def find(self, css: object, **ns: str) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        r"""::

            collection = dom.find('div ~ p')
            collection = dom.find('svg|line', svg='http://www.w3.org/2000/svg')

        Find all descendant elements of this element matching the CSS selector
        and return a :mod:`Pyjo.Collection` object containing these elements as
        :mod:`Pyjo.DOM` objects. All selectors from :mod:`Pyjo.DOM.CSS` are
        supported. ::

            # Find a specific element and extract information
            id = dom.find('div')[23]['id']

            # Extract information from multiple elements
            headers = dom.find('h1, h2, h3').map('text').each()

            # Count all the different tags
            counts = dom.find('*').reduce(lambda a, b: a | {b.tag: a.get(b.tag, 0) + 1}, {})

            # Find elements with a class that contains dots
            divs = dom.find('div.foo\.bar').each()

        Trailing keyword arguments can be used to declare xml namespace
        aliases. ::

            # "<rect></rect>"
            dom.parse('<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>').find(
                'svg|rect', svg='http://www.w3.org/2000/svg'
            ).first()
        """
        return self._collect(self._css().select(css, **ns))

    def following(self, css: object = None) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.following()
            collection = dom.following('div ~ p')

        Find all sibling elements after this node matching the CSS selector and
        return a :mod:`Pyjo.Collection` object containing these elements as
        :mod:`Pyjo.DOM` objects. All selectors from :mod:`Pyjo.DOM.CSS` are
        supported. ::

            # List tags of sibling elements after this node
            print(dom.following().map('tag').join("\\n"))
        """
        return _select(self._collect(_siblings(self.tree, True, True)), css)

    @property
    def following_nodes(self) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.following_nodes

        Return a :mod:`Pyjo.Collection` object containing all sibling nodes
        after this node as :mod:`Pyjo.DOM` objects. ::

            # "C"
            dom.parse('<p>A</p><!-- B -->C').at('p').following_nodes.last().content
        """
        return self._collect(_siblings(self.tree, False, True))

    # Not in Mojolicious: the matches one by one, in a lazy chain
    def iterate(self, css: object, **ns: str) -> 'Pyjo.Iterator.object[Pyjo_DOM]':
        """::

            iterator = dom.iterate('div ~ p')
            iterator = dom.iterate('svg|line', svg='http://www.w3.org/2000/svg')

        Same as :meth:`find`, but returns a lazy :mod:`Pyjo.Iterator`, which
        finds the descendant elements as they are taken, in the order of the
        document, so that the first one is processed before the last one is
        found. ::

            # Print the text of each paragraph as soon as it is found
            dom.iterate('p').map('all_text').each(lambda text, num: print(text))

            # Find no more elements after the first one with a link
            link = dom.iterate('p').first(lambda p: p.at('a[href]'))
        """
        import Pyjo.Iterator

        return Pyjo.Iterator.new(_Matches(self, css, ns))

    def matches(self, css: object, **ns: str) -> bool | None:
        """::

            boolean = dom.matches('div ~ p')
            boolean = dom.matches('svg|line', svg='http://www.w3.org/2000/svg')

        Check if this element matches the CSS selector. All selectors from
        :mod:`Pyjo.DOM.CSS` are supported. ::

            # True
            dom.parse('<p class="a">A</p>').at('p').matches('.a')
            dom.parse('<p class="a">A</p>').at('p').matches('p[class]')

            # False
            dom.parse('<p class="a">A</p>').at('p').matches('.b')
            dom.parse('<p class="a">A</p>').at('p').matches('p[id]')

        Trailing keyword arguments can be used to declare xml namespace
        aliases. ::

            # True
            dom.parse('<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>').matches(
                'svg|rect', svg='http://www.w3.org/2000/svg'
            )
        """
        return self._css().matches(css, **ns)

    @property
    def namespace(self) -> str | None:
        r"""::

            namespace = dom.namespace

        Find this element's namespace, or return ``None`` if none could be
        found. ::

            # "http://www.w3.org/2000/svg"
            Pyjo.DOM.new('<svg xmlns:svg="http://www.w3.org/2000/svg"><svg:circle>3.14</svg:circle></svg>').at(
                'svg\:circle'
            ).namespace

            # Find namespace for an element with namespace prefix
            namespace = dom.at('svg > svg\:circle').namespace

            # Find namespace for an element that may or may not have a namespace prefix
            namespace = dom.at('svg > circle').namespace
        """
        if (tree := self.tree)[0] != 'tag':
            return None

        # Extract namespace prefix and search parents
        ns = f'xmlns:{m[1]}' if (m := re.match(r'^(.*?):', tree[1])) else None
        for node in (tree, *_ancestors(tree)):
            # Namespace for prefix
            attrs = node[2]
            if ns:
                if ns in attrs:
                    return attrs[ns]

            # Namespace attribute
            elif attrs.get('xmlns') is not None:
                return attrs['xmlns']

        return None

    @_hybridmethod
    def new_tag(
        self_or_cls: 'Pyjo_DOM | type[Pyjo_DOM]',
        name: str,
        content: str | Callable[[], str] | None = None,
        /,
        **attrs: Any,
    ) -> 'Pyjo_DOM':  # noqa: N805
        """::

            tag = Pyjo.DOM.object.new_tag('div')
            tag = dom.new_tag('div')
            tag = dom.new_tag('div', id='foo', hidden=None)
            tag = dom.new_tag('div', 'safe content')
            tag = dom.new_tag('div', 'safe content', id='foo')
            tag = dom.new_tag('div', 'safe content', data={'pyjo': 'rocks'})
            tag = dom.new_tag('div', lambda: 'unsafe content', id='foo')

        Construct a new :mod:`Pyjo.DOM` object for an HTML/XML tag with or
        without attributes and content. The ``data`` attribute may contain a
        dict with key/value pairs to generate attributes from. ::

            # "<br>"
            dom.new_tag('br')

            # "<div></div>"
            dom.new_tag('div')

            # "<div hidden id="foo"></div>"
            dom.new_tag('div', id='foo', hidden=None)

            # "<div>test &amp; 123</div>"
            dom.new_tag('div', 'test & 123')

            # "<div id="foo">test &amp; 123</div>"
            dom.new_tag('div', 'test & 123', id='foo')

            # "<div data-bar="test" data-foo="1">test &amp; 123</div>"
            dom.new_tag('div', 'test & 123', data={'foo': 1, 'Bar': 'test'})

            # "<div id="foo">test & 123</div>"
            dom.new_tag('div', lambda: 'test & 123', id='foo')

            # "<div>Hello<b>Pyjo!</b></div>"
            dom.parse('<div>Hello</div>').at('div').append_content(dom.new_tag('b', 'Pyjo!')).root
        """
        new = self_or_cls.new()
        new._html.tag(name, content, **attrs)
        if isinstance(self_or_cls, Pyjo_DOM):
            new._html.xml = self_or_cls._html.xml
        return new

    @property
    def next(self) -> 'Pyjo_DOM | None':
        """::

            sibling = dom.next

        Return :mod:`Pyjo.DOM` object for next sibling element, or ``None`` if
        there are no more siblings. ::

            # "<h2>123</h2>"
            dom.parse('<div><h1>Test</h1><h2>123</h2></div>').at('h1').next
        """
        return self._maybe(_sibling(self.tree, True, True, 0))

    @property
    def next_node(self) -> 'Pyjo_DOM | None':
        """::

            sibling = dom.next_node

        Return :mod:`Pyjo.DOM` object for next sibling node, or ``None`` if
        there are no more siblings. ::

            # "456"
            dom.parse('<p><b>123</b><!-- Test -->456</p>').at('b').next_node.next_node

            # " Test "
            dom.parse('<p><b>123</b><!-- Test -->456</p>').at('b').next_node.content
        """
        return self._maybe(_sibling(self.tree, False, True, 0))

    @property
    def parent(self) -> 'Pyjo_DOM | None':
        """::

            parent = dom.parent

        Return :mod:`Pyjo.DOM` object for parent of this node, or ``None`` if
        this node has no parent. ::

            # "<b><i>Test</i></b>"
            dom.parse('<p><b><i>Test</i></b></p>').at('i').parent
        """
        if (tree := self.tree)[0] == 'root':
            return None
        return self._maybe(_parent(tree))

    def parse(self, html: object) -> Self:
        """::

            dom = dom.parse('<foo bar="baz">I ♥ Pyjoyment!</foo>')

        Parse HTML/XML fragment with :mod:`Pyjo.DOM.HTML`. ::

            # Parse XML
            dom = Pyjo.DOM.new().set(xml=True).parse('<foo>I ♥ Pyjoyment!</foo>')
        """
        self._html.parse(html)
        return self

    def preceding(self, css: object = None) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.preceding()
            collection = dom.preceding('div ~ p')

        Find all sibling elements before this node matching the CSS selector and
        return a :mod:`Pyjo.Collection` object containing these elements as
        :mod:`Pyjo.DOM` objects. All selectors from :mod:`Pyjo.DOM.CSS` are
        supported. ::

            # List tags of sibling elements before this node
            print(dom.preceding().map('tag').join("\\n"))
        """
        return _select(self._collect(_siblings(self.tree, True, False)), css)

    @property
    def preceding_nodes(self) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        """::

            collection = dom.preceding_nodes

        Return a :mod:`Pyjo.Collection` object containing all sibling nodes
        before this node as :mod:`Pyjo.DOM` objects. ::

            # "A"
            dom.parse('A<!-- B --><p>C</p>').at('p').preceding_nodes.first().content
        """
        return self._collect(_siblings(self.tree, False, False))

    def prepend(self, new: object) -> Self:
        """::

            dom = dom.prepend('<p>I ♥ Pyjoyment!</p>')
            dom = dom.prepend(Pyjo.DOM.new())

        Prepend HTML/XML fragment to this node (for all node types other than
        ``root``). ::

            # "<div><h1>Test</h1><h2>123</h2></div>"
            dom.parse('<div><h2>123</h2></div>').at('h2').prepend('<h1>Test</h1>').root

            # "<p>Test 123</p>"
            dom.parse('<p>123</p>').at('p').child_nodes.first().prepend('Test ').root
        """
        return self._add(0, new)

    def prepend_content(self, new: object) -> Self:
        """::

            dom = dom.prepend_content('<p>I ♥ Pyjoyment!</p>')
            dom = dom.prepend_content(Pyjo.DOM.new())

        Prepend HTML/XML fragment (for ``root`` and ``tag`` nodes) or raw
        content to this node's content. ::

            # "<div><h2>Test123</h2></div>"
            dom.parse('<div><h2>123</h2></div>').at('h2').prepend_content('Test').root

            # "<!-- Test 123 --><br>"
            dom.parse('<!-- 123 --><br>').child_nodes.first().prepend_content(' Test').root

            # "<p><i>123</i>Test</p>"
            dom.parse('<p>Test</p>').at('p').prepend_content('<i>123</i>').root
        """
        return self._content(False, False, new)

    @property
    def previous(self) -> 'Pyjo_DOM | None':
        """::

            sibling = dom.previous

        Return :mod:`Pyjo.DOM` object for previous sibling element, or ``None``
        if there are no more siblings. ::

            # "<h1>Test</h1>"
            dom.parse('<div><h1>Test</h1><h2>123</h2></div>').at('h2').previous
        """
        return self._maybe(_sibling(self.tree, True, False, -1))

    @property
    def previous_node(self) -> 'Pyjo_DOM | None':
        """::

            sibling = dom.previous_node

        Return :mod:`Pyjo.DOM` object for previous sibling node, or ``None`` if
        there are no more siblings. ::

            # "123"
            dom.parse('<p>123<!-- Test --><b>456</b></p>').at('b').previous_node.previous_node

            # " Test "
            dom.parse('<p>123<!-- Test --><b>456</b></p>').at('b').previous_node.content
        """
        return self._maybe(_sibling(self.tree, False, False, -1))

    def remove(self) -> 'Pyjo_DOM | None':
        """::

            parent = dom.remove()

        Remove this node and return :attr:`root` (for ``root`` nodes) or
        :attr:`parent`. ::

            # "<div></div>"
            dom.parse('<div><h1>Test</h1></div>').at('h1').remove()

            # "<p><b>456</b></p>"
            dom.parse('<p>123<b>456</b></p>').at('p').child_nodes.first().remove().root
        """
        return self.replace('')

    def replace(self, new: object) -> 'Pyjo_DOM | None':
        """::

            parent = dom.replace('<div>I ♥ Pyjoyment!</div>')
            parent = dom.replace(Pyjo.DOM.new())

        Replace this node with HTML/XML fragment and return :attr:`root` (for
        ``root`` nodes) or :attr:`parent`. ::

            # "<div><h2>123</h2></div>"
            dom.parse('<div><h1>Test</h1></div>').at('h1').replace('<h2>123</h2>')

            # "<p><b>123</b></p>"
            dom.parse('<p>Test</p>').at('p').child_nodes[0].replace('<b>123</b>').root
        """
        if (tree := self.tree)[0] == 'root':
            return self.parse(new)
        return self._replace(_parent(tree), tree, _nodes(self._parse(new)))

    @property
    def root(self) -> 'Pyjo_DOM':
        """::

            root = dom.root

        Return :mod:`Pyjo.DOM` object for ``root`` node.
        """
        if not (tree := _ancestors(self.tree, True)):
            return self
        return self._build(tree[0], self.xml)

    @property
    def selector(self) -> str | None:
        """::

            selector = dom.selector

        Get a unique CSS selector for this element. ::

            # "ul:nth-child(1) > li:nth-child(2)"
            dom.parse('<ul><li>Test</li><li>123</li></ul>').find('li').last().selector

            # "p:nth-child(1) > b:nth-child(1) > i:nth-child(1)"
            dom.parse('<p><b><i>Test</i></b></p>').at('i').selector
        """
        if (tree := self.tree)[0] != 'tag':
            return None
        return ' > '.join(
            reversed([f'{n[1]}:nth-child({len(_siblings(n, True, False)) + 1})' for n in (tree, *_ancestors(tree))])
        )

    def strip(self) -> 'Pyjo_DOM | None':
        """::

            parent = dom.strip()

        Remove this element while preserving its content and return
        :attr:`parent`. ::

            # "<div>Test</div>"
            dom.parse('<div><h1>Test</h1></div>').at('h1').strip()
        """
        if (tree := self.tree)[0] != 'tag':
            return self
        return self._replace(tree[3], tree, _nodes(tree))

    @property
    def tag(self) -> str | None:
        """::

            tag = dom.tag
            dom.tag = 'div'

        This element's tag name. ::

            # List tag names of child elements
            print(dom.children().map('tag').join("\\n"))
        """
        if (tree := self.tree)[0] != 'tag':
            return None
        return tree[1]

    @tag.setter
    def tag(self, tag: str) -> None:
        if (tree := self.tree)[0] != 'tag' or not tag:
            return
        tree[1] = tag

    @property
    def text(self) -> str:
        r"""::

            text = dom.text

        Extract text content from this element only (not including child
        elements). ::

            # "bar"
            dom.parse("<div>foo<p>bar</p>baz</div>").at('p').text

            # "foo\nbaz\n"
            dom.parse("<div>foo\n<p>bar</p>baz\n</div>").at('div').text

        To extract text content from all descendant nodes see :attr:`all_text`.
        """
        return _text(_nodes(self.tree), False, False)

    # Renamed from Mojolicious: to_string
    def to_str(self) -> str:
        """::

            string = dom.to_str()

        Render this node and its content to HTML/XML. ::

            # "<b>Test</b>"
            dom.parse('<div><b>Test</b></div>').at('div b').to_str()
        """
        return self._html.render()

    @property
    def tree(self) -> Tree:
        """::

            tree = dom.tree
            dom.tree = ['root']

        Document Object Model. Note that this structure should only be used very
        carefully since it is very dynamic.
        """
        return self._html.tree

    @tree.setter
    def tree(self, tree: Tree) -> None:
        self._html.tree = tree

    @property
    def type(self) -> str:
        """::

            type = dom.type

        This node's type, usually ``cdata``, ``comment``, ``doctype``, ``pi``,
        ``raw``, ``root``, ``tag`` or ``text``. ::

            # "cdata"
            dom.parse('<![CDATA[Test]]>').child_nodes.first().type

            # "comment"
            dom.parse('<!-- Test -->').child_nodes.first().type

            # "doctype"
            dom.parse('<!DOCTYPE html>').child_nodes.first().type

            # "pi"
            dom.parse('<?xml version="1.0"?>').child_nodes.first().type

            # "raw"
            dom.parse('<script>Test</script>').at('script').child_nodes.first().type

            # "root"
            dom.parse('<p>Test</p>').type

            # "tag"
            dom.parse('<p>Test</p>').at('p').type

            # "text"
            dom.parse('<p>Test</p>').at('p').child_nodes.first().type
        """
        return self.tree[0]

    @property
    def val(self) -> str | list[str] | None:
        """::

            value = dom.val

        Extract value from form element (such as ``button``, ``input``,
        ``option``, ``select`` and ``textarea``), or return ``None`` if this
        element has no value. In the case of ``select`` with ``multiple``
        attribute, find ``option`` elements with ``selected`` attribute and
        return a list with all values, or ``None`` if none could be found. ::

            # "a"
            dom.parse('<input name=test value=a>').at('input').val

            # "b"
            dom.parse('<textarea>b</textarea>').at('textarea').val

            # "c"
            dom.parse('<option value="c">Test</option>').at('option').val

            # "d"
            dom.parse('<select><option selected>d</option></select>').at('select').val

            # "e"
            dom.parse('<select multiple><option selected>e</option></select>').at('select').val[0]

            # "on"
            dom.parse('<input name=test type=checkbox>').at('input').val
        """

        # "option"
        if (tag := self.tag) == 'option':
            return value if (value := self['value']) is not None else self.text

        # "input" ("type=checkbox" and "type=radio")
        type = self['type'] or ''
        if tag == 'input' and type in ('radio', 'checkbox'):
            return value if (value := self['value']) is not None else 'on'

        # "textarea", "input" or "button"
        if tag != 'select':
            return self.text if tag == 'textarea' else self['value']

        # "select"
        v = (
            self.find('option:checked:not([disabled])')
            .grep(lambda e: not e.ancestors('optgroup[disabled]').size)
            .map('val')
        )
        if 'multiple' in self:
            return v.to_list() if v.size else None
        return v.last()

    # Left out from Mojolicious: with_roles, as Pyjoyment has no roles

    def wrap(self, new: object) -> Self:
        """::

            dom = dom.wrap('<div></div>')
            dom = dom.wrap(Pyjo.DOM.new())

        Wrap HTML/XML fragment around this node (for all node types other than
        ``root``), placing it as the last child of the first innermost element. ::

            # "<p>123<b>Test</b></p>"
            dom.parse('<b>Test</b>').at('b').wrap('<p>123</p>').root

            # "<div><p><b>Test</b></p>123</div>"
            dom.parse('<b>Test</b>').at('b').wrap('<div><p></p>123</div>').root

            # "<p><b>Test</b></p><p>123</p>"
            dom.parse('<b>Test</b>').at('b').wrap('<p></p><p>123</p>').root

            # "<p><b>Test</b></p>"
            dom.parse('<p>Test</p>').at('p').child_nodes.first().wrap('<b>').root
        """
        return self._wrap(False, new)

    def wrap_content(self, new: object) -> Self:
        """::

            dom = dom.wrap_content('<div></div>')
            dom = dom.wrap_content(Pyjo.DOM.new())

        Wrap HTML/XML fragment around this node's content (for ``root`` and
        ``tag`` nodes), placing it as the last children of the first innermost
        element. ::

            # "<p><b>123Test</b></p><p></p>"
            dom.parse('<p>Test<p>').at('p').wrap_content('<b>123</b>').root

            # "<p><b>Test</b></p><p>123</p>"
            dom.parse('<b>Test</b>').wrap_content('<p></p><p>123</p>')
        """
        return self._wrap(True, new)

    @property
    def xml(self) -> bool | None:
        """::

            boolean = dom.xml
            dom.xml = boolean

        Disable HTML semantics in parser and activate case-sensitivity, defaults
        to auto-detection based on XML declarations.
        """
        return self._html.xml

    @xml.setter
    def xml(self, xml: bool | None) -> None:
        self._html.xml = xml

    def _add(self, offset: int, new: object) -> Self:
        if (tree := self.tree)[0] == 'root':
            return self

        if (parent := _parent(tree)) is None:
            return self
        i = _offset(parent, tree) + offset
        parent[i:i] = _link(parent, _nodes(self._parse(new)))

        return self

    def _build(self, tree: Tree, xml: bool | None) -> 'Pyjo_DOM':
        return self.new().set(tree=tree, xml=xml)

    def _collect(self, nodes: list[Tree]) -> 'Pyjo.Collection.object[Pyjo_DOM]':
        xml = self.xml
        return Pyjo.Collection.object(self._build(n, xml) for n in nodes)

    def _content(self, start: bool, offset: bool, new: object) -> Self:
        tree = self.tree
        if tree[0] not in ('root', 'tag'):
            old = self.content
            self.content = old + str(new) if start else str(new) + old
            return self

        i = len(tree) if start else _start(tree)
        tree[i : i + (len(tree) - 1 if offset else 0)] = _link(tree, _nodes(self._parse(new)))

        return self

    def _css(self) -> 'Pyjo.DOM.CSS.object':
        return Pyjo.DOM.CSS.new(tree=self.tree)

    def _maybe(self, tree: Tree | None) -> 'Pyjo_DOM | None':
        return self._build(tree, self.xml) if tree is not None else None

    def _parse(self, new: object) -> Tree:
        if not isinstance(new, Pyjo_DOM):
            return Pyjo.DOM.HTML.new(xml=self.xml).parse(new).tree
        tree = _clone(new.tree)
        return tree if tree[0] == 'root' else _fragment(tree)

    def _replace(self, parent: Tree | None, child: Tree, nodes: list[Tree]) -> 'Pyjo_DOM | None':
        if parent is not None:
            i = _offset(parent, child)
            parent[i : i + 1] = _link(parent, nodes)
        return self.parent

    def _wrap(self, content: bool, new: object) -> Self:
        tree = self.tree
        if tree[0] == 'root' and not content:
            return self
        if tree[0] not in ('root', 'tag') and content:
            return self

        # Find innermost tag
        current = None
        first = _nodes(parsed := self._parse(new), True)
        while len(first):
            current = first[0]
            first = _nodes(current, True)
        if current is None:
            return self

        # Wrap content
        if content:
            current.extend(_link(current, _nodes(tree)))
            start = _start(tree)
            tree[start:] = _link(tree, _nodes(parsed))
            return self

        # Wrap element
        self._replace(_parent(tree), tree, _nodes(parsed))
        current.extend(_link(current, [tree]))
        return self


def _all(nodes: list[Tree]) -> list[Tree]:
    return [m for n in nodes for m in ([n, *_all(_nodes(n))] if n[0] == 'tag' else [n])]


def _ancestors(tree: Tree, root: bool = False) -> list[Tree]:
    # Unlike Mojolicious: Mojo takes the second child node of a root for its
    # parent, so the root of a root with a text node after the first one is
    # that text node
    if tree[0] == 'root' or (parent := _parent(tree)) is None:
        return []
    ancestors: list[Tree] = [parent]
    while parent[0] == 'tag' and (parent := parent[3]) is not None:
        ancestors.append(parent)
    return ancestors[-1:] if root else ancestors[:-1]


def _clone(tree: Tree, parent: Tree | None = None) -> Tree:
    if tree[0] == 'tag':
        new: Tree = ['tag', tree[1], dict(tree[2]), parent]
        new.extend(_clone(n, new) for n in tree[4:])
    elif tree[0] == 'root':
        new = ['root']
        new.extend(_clone(n, new) for n in tree[1:])
    else:
        new = [tree[0], tree[1], parent]
    return new


def _fragment(*nodes: Tree) -> Tree:
    root: Tree = ['root', *nodes]
    _link(root, list(nodes), True)
    return root


def _link(parent: Tree, children: list[Tree], fragment: bool = False) -> list[Tree]:

    # Link parent to children (raw text is only allowed in script and style elements)
    raw = fragment or parent[0] == 'tag' and parent[1] in ('script', 'style')
    for node in children:
        if node[0] == 'raw' and not raw:
            node[0] = 'text'
        node[3 if node[0] == 'tag' else 2] = parent

    return children


def _nodes(tree: Tree | None, tags: bool = False) -> list[Tree]:
    if tree is None:
        return []
    nodes = tree[_start(tree) :]
    return [n for n in nodes if n[0] == 'tag'] if tags else nodes


def _offset(parent: Tree, child: Tree) -> int:
    i = _start(parent)
    while i < len(parent) and parent[i] is not child:
        i += 1
    return i


def _parent(tree: Tree) -> Tree | None:
    return tree[3 if tree[0] == 'tag' else 2]


def _select(collection: 'Pyjo.Collection.object[Pyjo_DOM]', css: object) -> 'Pyjo.Collection.object[Pyjo_DOM]':
    return collection.grep('matches', css) if css else collection


# Mojo's _siblings with $i defined
def _sibling(tree: Tree, tags: bool, tail: bool, i: int) -> Tree | None:
    if tree[0] == 'root':
        return None
    nodes = _siblings(tree, tags, tail)
    return nodes[i] if -len(nodes) <= i < len(nodes) else None


def _siblings(tree: Tree, tags: bool, tail: bool) -> list[Tree]:
    if tree[0] == 'root':
        return []

    nodes = _nodes(_parent(tree))
    if (match := next((i for i, n in enumerate(nodes) if n is tree), None)) is None:
        return []
    nodes = nodes[match + 1 :] if tail else nodes[:match]

    return [n for n in nodes if n[0] == 'tag'] if tags else nodes


def _start(tree: Tree) -> int:
    return 1 if tree[0] == 'root' else 4


def _text(nodes: list[Tree], xml: bool | None, all: bool) -> str:
    text = ''
    queue = list(nodes)
    while len(queue):
        node = queue.pop(0)
        type = node[0]

        # Text
        if type in ('text', 'cdata', 'raw'):
            text += node[1]

        # Nested tag
        elif type == 'tag' and all:
            if xml or node[1] not in ('script', 'style'):
                queue[0:0] = _nodes(node)

    return text


# The matches of a selector, found anew for each iteration of a Pyjo.Iterator
class _Matches:
    def __init__(self, dom: Pyjo_DOM, css: object, ns: dict[str, str]) -> None:
        self.dom, self.css, self.ns = dom, css, ns

    def __iter__(self) -> Iterator[Pyjo_DOM]:
        dom, xml = self.dom, self.dom.xml
        return (
            dom.new().set(tree=tree, xml=xml)
            for tree in Pyjo.DOM.CSS.new(tree=dom.tree).select_iter(self.css, **self.ns)
        )


new = Pyjo_DOM.new
object = Pyjo_DOM
DOM = Pyjo_DOM
