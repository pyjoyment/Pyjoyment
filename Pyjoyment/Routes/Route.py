"""
Pyjoyment.Routes.Route - Route
==============================
::

    from Pyjoyment.Routes.Route import Route

    r = Route()

    # Or import the module, as in Google Python Style Guide

    import Pyjoyment.Routes.Route

    r = Pyjoyment.Routes.Route.new()

:mod:`Pyjoyment.Routes.Route` is the route container used by
:mod:`Pyjoyment.Routes`.

Shortcuts
---------

In addition to the attributes and methods below you can also call shortcuts
provided by :attr:`~Pyjoyment_Routes_Route.root` on
:mod:`Pyjoyment.Routes.Route` objects. ::

    # Add a "firefox" shortcut
    r.root.add_shortcut('firefox', lambda r, path: r.get(path).requires(agent=re.compile(r'Firefox')))

    # Use "firefox" shortcut to generate routes
    r.firefox('/welcome').to('firefox#welcome')
    r.firefox('/bye').to('firefox#bye')

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Routes::Route
<https://github.com/mojolicious/mojo/blob/v9.52/lib/Mojolicious/Routes/Route.pm>`_ of Mojolicious 9.52.
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.Util
import Pyjoyment.Routes.Pattern

import functools
import re
import sys
import weakref

from collections.abc import Callable
from typing import Any, Self, cast, overload


# Reserved stash values
# Not in Mojolicious: toml and yaml, which the renderer renders as json
# Unlike Mojolicious: the timeouts of a route, inactivity_timeout and request_timeout, are reserved too
_RESERVED = frozenset(
    'action app cb controller data extends format handler inactivity_timeout inline json layout namespace path '
    'request_timeout status template text toml variant yaml'.split()
)


# The children without a text that their paths start with, and the ones with it, by its length and by the text
type _PrefixIndex = tuple[list[int], dict[int, dict[str, list[int]]]]


class Pyjoyment_Routes_Route(Pyjo.Base.object):
    """
    :mod:`Pyjoyment.Routes.Route` inherits all methods from :mod:`Pyjo.Base`
    and implements the following new ones.
    """

    def __init__(self) -> None:
        """::

            r = Pyjoyment.Routes.Route.new()

        Construct a new :mod:`Pyjoyment.Routes.Route` object.
        """
        self.children: list[Pyjoyment_Routes_Route] = []
        """::

            children = r.children
            r.children = [Pyjoyment.Routes.Route.new()]

        The children of this route, used for nesting routes.
        """

        self.inline: bool | None = None
        """::

            boolean = r.inline
            r.inline = boolean

        Allow :meth:`under` semantics for this route.
        """

        self.partial: bool | None = None
        """::

            boolean = r.partial
            r.partial = boolean

        Route has no specific end, remaining characters will be captured in
        ``path``.
        """

        self.pattern: Pyjoyment.Routes.Pattern.object = Pyjoyment.Routes.Pattern.new()
        """::

            pattern = r.pattern
            r.pattern = Pyjoyment.Routes.Pattern.new()

        Pattern for this route, defaults to a :mod:`Pyjoyment.Routes.Pattern`
        object.
        """

        self._custom = False
        self._has_websocket: bool | None = None
        self._methods: list[str] | None = None
        self._name: str | None = None
        self._parent: weakref.ref[Pyjoyment_Routes_Route] | None = None
        self._prefix_index: _PrefixIndex | None = None
        self._requires: list[tuple[str, Any]] | None = None
        self._websocket = False

    # Not in Mojolicious: a route is a decorator of its callback, as the functions of Pyjoyment.Lite and the methods of
    # the routes are used without one
    def __call__(self, cb: Callable[..., Any]) -> Self:
        """::

            @r.get('/foo')
            def foo(c):
                c.render(text='Hello World!')

        Set the callback of the route, as a decorator, and return the route.
        """
        return self.to(cb=cb)

    # Unlike Mojolicious: Mojo registers the shortcuts of a root with Mojo::DynamicMethods, Python looks them up in the
    # root when a method is not found
    def __getattr__(self, name: str) -> Any:
        if not name.startswith('_'):
            shortcuts: dict[str, Callable[..., Any]] = vars(self._chain()[0]).get('shortcuts', {})
            if dynamic := shortcuts.get(name):
                return functools.partial(dynamic, self)
        package = f'{type(self).__module__}.{type(self).__qualname__}'

        # The location of the caller, which croak adds to the message
        caller = sys._getframe(1)  # pyright: ignore[reportPrivateUsage]
        at = f'at {caller.f_code.co_filename} line {caller.f_lineno}'
        raise AttributeError(
            f'Can\'t locate object method "{name}" via package "{package}" {at}.\n', name=name, obj=self
        )

    @property
    def parent(self) -> 'Pyjoyment_Routes_Route | None':
        """::

            parent = r.parent
            r.parent = Pyjoyment.Routes.Route.new()

        The parent of this route, usually a :mod:`Pyjoyment.Routes.Route`
        object. Note that this attribute is weakened.
        """
        return self._parent() if self._parent is not None else None

    @parent.setter
    def parent(self, value: 'Pyjoyment_Routes_Route | None') -> None:
        self._parent = weakref.ref(value) if value is not None else None

    def add_child(self, route: 'Pyjoyment_Routes_Route') -> Self:
        """::

            r = r.add_child(Pyjoyment.Routes.Route.new())

        Add a child to this route, it will be automatically removed from its
        current parent if necessary. ::

            # Reattach route
            r.add_child(r.find('foo'))
        """
        _invalidate(self)
        self.children.append(route.remove().set(parent=self))
        route.pattern.types = self.root.types
        return self

    def any(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.any()
            route = r.any('/:foo')
            route = r.any('/:foo', lambda c: ...)
            route = r.any('/:foo', lambda c: ..., 'name')
            route = r.any('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.any('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))
            route = r.any(['GET', 'POST'], '/:foo', lambda c: ...)
            route = r.any(['GET', 'POST'], '/:foo', foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching any of the listed
        HTTP request methods or all. ::

            # Route with pattern and destination
            r.any('/user').to('user#whatever')

        All arguments are optional, but some have to appear in a certain order,
        like the list of the HTTP methods to match, which comes first, and the
        restrictive placeholders, which are keyword arguments. ::

            # Route with HTTP methods, pattern, restrictive placeholders and destination
            r.any(['DELETE', 'PUT'], '/:foo', foo=re.compile(r'\\w+')).to('foo#bar')

        There are also two supported string values, containing the route
        pattern and the route name, defaulting to the pattern ``/`` and a name
        based on the pattern. ::

            # Route with pattern, name and destination
            r.any('/:foo', 'foo_route').to('foo#bar')

        Route conditions are activated with :meth:`requires`. ::

            # Route with pattern, condition and destination
            r.any('/').requires(agent=re.compile(r'Firefox')).to('foo#bar')

        A dict is used to specify optional placeholders and default values for
        the stash. ::

            # Route with pattern, optional placeholder and destination
            r.any('/:foo', {'foo': 'bar'}).to('foo#bar')

        And a callable can be used to specify a ``cb`` value to be merged into
        the default values for the stash. ::

            # Route with pattern and a closure as destination
            r.any('/:foo', lambda c: c.render(text='Hello World!'))
        """
        if args and isinstance(methods := args[0], list):
            return self._generate_route(cast(list[str], methods), *args[1:], **constraints)
        return self._generate_route([], *args, **constraints)

    def delete(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.delete()
            route = r.delete('/:foo')
            route = r.delete('/:foo', lambda c: ...)
            route = r.delete('/:foo', lambda c: ..., 'name')
            route = r.delete('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.delete('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only ``DELETE``
        requests, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.delete('/user').to('user#remove')
        """
        return self._generate_route('DELETE', *args, **constraints)

    def find(self, name: str) -> 'Pyjoyment_Routes_Route | None':
        """::

            route = r.find('foo')

        Find child route by name, custom names have precedence over
        automatically generated ones. ::

            # Change default parameters of a named route
            r.find('show_user').to(foo='bar')
        """
        return self._index().get(name)

    def get(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.get()
            route = r.get('/:foo')
            route = r.get('/:foo', lambda c: ...)
            route = r.get('/:foo', lambda c: ..., 'name')
            route = r.get('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.get('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only ``GET``
        requests, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.get('/user').to('user#show')
        """
        return self._generate_route('GET', *args, **constraints)

    @property
    def has_custom_name(self) -> bool:
        """::

            boolean = r.has_custom_name

        Check if this route has a custom name.
        """
        return self._custom

    @property
    def has_websocket(self) -> bool:
        """::

            boolean = r.has_websocket

        Check if this route has a WebSocket ancestor and cache the result for
        future checks.
        """
        if self._has_websocket is None:
            self._has_websocket = any(route.is_websocket for route in self._chain())
        return self._has_websocket

    @property
    def is_endpoint(self) -> bool:
        """::

            boolean = r.is_endpoint

        Check if this route qualifies as an endpoint.
        """
        return not self.inline and not self.children

    def is_reserved(self, name: str) -> bool:
        """::

            boolean = r.is_reserved('controller')

        Check if string is a reserved stash value.
        """
        return name in _RESERVED

    @property
    def is_websocket(self) -> bool:
        """::

            boolean = r.is_websocket

        Check if this route is a WebSocket.
        """
        return self._websocket

    @overload
    def methods(self) -> list[str] | None: ...

    @overload
    def methods(self, method: str | list[str], /, *methods: str) -> Self: ...

    def methods(self, *methods: str | list[str]) -> list[str] | None | Self:
        """::

            methods = r.methods()
            r = r.methods('GET')
            r = r.methods('GET', 'POST')
            r = r.methods(['GET', 'POST'])

        Restrict HTTP methods this route is allowed to handle, defaults to no
        restrictions. ::

            # Route with two methods and destination
            r.any('/foo').methods('GET', 'POST').to('foo#bar')
        """
        if not methods:
            return self._methods
        first = methods[0]
        names = [
            method.upper() for method in (first if isinstance(first, list) else methods) if isinstance(method, str)
        ]
        if names:
            self._methods = names
        return self

    @property
    def name(self) -> str | None:
        """::

            name = r.name
            r.name = 'foo'

        The name of this route, defaults to an automatically generated name
        based on the route pattern. Note that the name ``current`` is reserved
        for referring to the current route. ::

            # Route with destination and custom name
            r.get('/user').to('user#show').set(name='show_user')
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name, self._custom = value, True

    def options(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.options()
            route = r.options('/:foo')
            route = r.options('/:foo', lambda c: ...)
            route = r.options('/:foo', lambda c: ..., 'name')
            route = r.options('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.options('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only ``OPTIONS``
        requests, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.options('/user').to('user#overview')
        """
        return self._generate_route('OPTIONS', *args, **constraints)

    def parse(self, pattern: str | None = None, /, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> Self:
        """::

            r = r.parse('/user/:id')
            r = r.parse('/user/:id', id=re.compile(r'\\d+'))
            r = r.parse(format=['json', 'yaml'])

        Parse pattern.
        """
        self._name = re.sub(r'\W+', '', self.pattern.parse(pattern, **constraints).unparsed or '')
        return self

    def patch(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.patch()
            route = r.patch('/:foo')
            route = r.patch('/:foo', lambda c: ...)
            route = r.patch('/:foo', lambda c: ..., 'name')
            route = r.patch('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.patch('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only ``PATCH``
        requests, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.patch('/user').to('user#update')
        """
        return self._generate_route('PATCH', *args, **constraints)

    def post(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.post()
            route = r.post('/:foo')
            route = r.post('/:foo', lambda c: ...)
            route = r.post('/:foo', lambda c: ..., 'name')
            route = r.post('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.post('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only ``POST``
        requests, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.post('/user').to('user#create')
        """
        return self._generate_route('POST', *args, **constraints)

    def put(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.put()
            route = r.put('/:foo')
            route = r.put('/:foo', lambda c: ...)
            route = r.put('/:foo', lambda c: ..., 'name')
            route = r.put('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.put('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only ``PUT``
        requests, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.put('/user').to('user#replace')
        """
        return self._generate_route('PUT', *args, **constraints)

    def query(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.query()
            route = r.query('/:foo')
            route = r.query('/:foo', lambda c: ...)
            route = r.query('/:foo', lambda c: ..., 'name')
            route = r.query('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.query('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only ``QUERY``
        requests, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.query('/user').to('user#search')
        """
        return self._generate_route('QUERY', *args, **constraints)

    def remove(self) -> Self:
        """::

            r = r.remove()

        Remove route from parent. ::

            # Remove route completely
            r.find('foo').remove()

            # Reattach route to new parent
            r.any('/foo').add_child(r.find('bar').remove())
        """
        if (parent := self.parent) is None:
            return self
        _invalidate(parent)
        parent.children[:] = [child for child in parent.children if child is not self]
        self.parent = None
        return self

    def render(self, values: dict[str, Any]) -> str:
        """::

            path = r.render({'foo': 'bar'})

        Render route with parameters into a path.
        """
        path = ''.join(
            route.pattern.render(values, not route.children and not route.partial) for route in self._chain()
        )
        return path or '/'

    # requires(**conditions) with no conditions is requires(), which the first overload types
    @overload
    def requires(self) -> list[tuple[str, Any]] | None: ...  # pyright: ignore[reportOverlappingOverload]

    @overload
    def requires(self, conditions: list[tuple[str, Any]], /) -> Self: ...

    @overload
    def requires(self, **conditions: Any) -> Self: ...

    def requires(self, *args: list[tuple[str, Any]], **conditions: Any) -> list[tuple[str, Any]] | None | Self:
        """::

            requires = r.requires()
            r = r.requires(foo=1)
            r = r.requires(foo=1, bar={'baz': 'yada'})
            r = r.requires([('foo', 1), ('bar', {'baz': 'yada'})])

        Activate conditions for this route. Note that this automatically
        disables the routing cache, since conditions are too complex for
        caching. ::

            # Route with condition and destination
            r.get('/foo').requires(host=re.compile(r'mojolicious\\.org')).to('foo#bar')
        """
        # Routes with conditions can't be cached
        if not args and not conditions:
            return self._requires
        if not (requires := args[0] if args else list(conditions.items())):
            return self
        self._requires = requires
        self.root.cache.max_keys = 0

        return self

    @property
    def root(self) -> Any:
        """::

            root = r.root

        The :mod:`Pyjoyment.Routes` object this route is a descendant of.
        """
        # The root has the attributes of Pyjoyment.Routes, which is a subclass of this one
        return self._chain()[0]

    @property
    def suggested_method(self) -> str:
        """::

            method = r.suggested_method

        Suggested HTTP method for reaching this route, ``GET`` and ``POST`` are
        preferred.
        """
        via: set[str] = set()
        for route in self._chain():
            if not (methods := route.methods()):
                continue
            via = {method for method in methods if method in via} if via else set(methods)

        if 'POST' in via and 'GET' not in via:
            return 'POST'
        return 'GET' if 'GET' in via else (sorted(via)[0] if via else 'GET')

    # to(**defaults) with no defaults is to(), which the first overload types
    @overload
    def to(self) -> dict[str, Any]: ...  # pyright: ignore[reportOverlappingOverload]

    @overload
    def to(self, shortcut: Any, /, *args: Any, **defaults: Any) -> Self: ...

    @overload
    def to(self, **defaults: Any) -> Self: ...

    def to(self, *args: Any, **defaults: Any) -> dict[str, Any] | Self:
        """::

            defaults = r.to()
            r = r.to(action='foo')
            r = r.to({'action': 'foo'})
            r = r.to('controller#action')
            r = r.to('controller#action', foo='bar')
            r = r.to('controller#action', {'foo': 'bar'})
            r = r.to(Pyjoyment.new())
            r = r.to(Pyjoyment.new(), foo='bar')
            r = r.to(Pyjoyment.new(), {'foo': 'bar'})
            r = r.to('MyApp')
            r = r.to('MyApp', foo='bar')
            r = r.to('MyApp', {'foo': 'bar'})

        Set default parameters for this route.
        """
        pattern = self.pattern
        if not args and not defaults:
            return pattern.defaults
        shortcut, defaults = Pyjo.Util._options(args, defaults)  # pyright: ignore[reportPrivateUsage]

        if shortcut:
            # Application
            if not isinstance(shortcut, str) or re.match(r'^[\w.]+$', shortcut):
                defaults['app'] = shortcut

            # Controller and action
            elif m := re.match(r'^([\w\-.]+)?#(\w+)?$', shortcut):
                if m[1] is not None:
                    defaults['controller'] = m[1]
                if m[2] is not None:
                    defaults['action'] = m[2]

        pattern.defaults.update(defaults)

        return self

    def to_str(self) -> str:
        """::

            string = r.to_str()

        Stringify the whole route.
        """
        return ''.join(route.pattern.unparsed or '' for route in self._chain())

    def under(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.under(lambda c: ...)
            route = r.under('/:foo', lambda c: ...)
            route = r.under('/:foo', {'foo': 'bar'})
            route = r.under('/:foo', foo=re.compile(r'\\w+'))
            route = r.under(format=['json', 'yaml'])

        Generate :mod:`Pyjoyment.Routes.Route` object for a nested route with
        its own intermediate destination, takes the same arguments as
        :meth:`any` (except for the HTTP methods to match, which are not
        available). ::

            # Longer version
            r.any('/:foo', lambda c: ...).set(inline=True)

            # Intermediate destination and prefix shared between two routes
            auth = r.under('/user').to('user#auth')
            auth.get('/show').to('#show')
            auth.post('/create').to('#create')
        """
        return self._generate_route('under', *args, **constraints)

    def websocket(self, *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint') -> 'Pyjoyment_Routes_Route':
        """::

            route = r.websocket()
            route = r.websocket('/:foo')
            route = r.websocket('/:foo', lambda c: ...)
            route = r.websocket('/:foo', lambda c: ..., 'name')
            route = r.websocket('/:foo', {'foo': 'bar'}, lambda c: ...)
            route = r.websocket('/:foo', lambda c: ..., foo=re.compile(r'\\w+'))

        Generate :mod:`Pyjoyment.Routes.Route` object matching only WebSocket
        handshakes, takes the same arguments as :meth:`any` (except for the HTTP
        methods to match, which are implied). ::

            # Route with destination
            r.websocket('/echo').to('example#echo')
        """
        route = self.get(*args, **constraints)
        route._websocket = True
        return route

    def _chain(self) -> 'list[Pyjoyment_Routes_Route]':
        chain: list[Pyjoyment_Routes_Route] = [self]
        parent: Pyjoyment_Routes_Route | None = self
        while (parent := parent.parent) is not None:
            chain.insert(0, parent)
        return chain

    # Unlike Mojolicious: Mojo takes pairs of strings between the pattern and the name for conditions and a list for
    # the constraints, Python takes the constraints as keyword arguments, so the conditions go to requires
    def _generate_route(
        self, methods: str | list[str], *args: Any, **constraints: 'Pyjoyment.Routes.Pattern.Constraint'
    ) -> 'Pyjoyment_Routes_Route':
        defaults: dict[str, Any] = {}
        name = pattern = None
        for arg in args:
            # First string is the pattern
            if isinstance(arg, str) and pattern is None:
                pattern = arg

            # Last string is the route name
            elif isinstance(arg, str):
                name = arg

            # Defaults
            elif isinstance(arg, dict):
                defaults.update(cast(dict[str, Any], arg))

            # Callback
            elif callable(arg):
                defaults['cb'] = arg

        route = self._route(pattern, **constraints).to(defaults)
        if methods == 'under':
            route.inline = True
        else:
            route.methods(methods)

        if name is not None:
            route.name = name
        return route

    def _candidates(self, path: str) -> 'list[Pyjoyment_Routes_Route]':

        # Index children by the text their patterns start with (routes are frozen after the first request)
        children = self.children
        if not children:
            return children
        if (index := self._prefix_index) is None:
            index = self._prefix_index = ([], {})
            for i, child in enumerate(children):
                if (prefixes := child._prefixes()) is not None:
                    for prefix in prefixes:
                        index[1].setdefault(len(prefix), {}).setdefault(prefix, []).append(i)
                else:
                    index[0].append(i)

        # Children that could match the path, in their original order
        if not (text := index[1]):
            return children
        found = set(index[0])
        for length, prefixes in text.items():
            if hit := prefixes.get(path[:length]):
                found.update(hit)
        return [children[i] for i in sorted(found)]

    # Text one of the paths matched by this route has to start with (None if it could be anything)
    def _prefixes(self) -> list[str] | None:

        # Custom regexes and pattern classes could match anything
        pattern = self.pattern
        regex, compiled = pattern.regex, pattern._compiled  # pyright: ignore[reportPrivateUsage]
        if type(pattern) is not Pyjoyment.Routes.Pattern.object or (regex is not None and regex is not compiled):
            return None
        if tree := pattern.tree:
            first = tree[0]
            return [first[1]] if first[0] == 'text' else None

        # Routes with an empty pattern pass the path on to their children
        children = self.children
        if self.partial or not children:
            return None
        prefixes: list[str] = []
        for child in children:
            if (child_prefixes := child._prefixes()) is None:
                return None
            prefixes.extend(child_prefixes)
        return prefixes

    def _index(self) -> 'dict[str, Pyjoyment_Routes_Route]':
        auto: dict[str, Pyjoyment_Routes_Route] = {}
        custom: dict[str, Pyjoyment_Routes_Route] = {}
        children = list(self.children)
        while children:
            child = children.pop(0)
            names = custom if child.has_custom_name else auto
            names.setdefault(child.name or '', child)
            children.extend(child.children)

        return {**auto, **custom}

    def _route(
        self, pattern: str | None, **constraints: 'Pyjoyment.Routes.Pattern.Constraint'
    ) -> 'Pyjoyment_Routes_Route':
        route = self.add_child(Pyjoyment_Routes_Route.new().parse(pattern, **constraints)).children[-1]
        new_pattern = route.pattern
        if any(self.is_reserved(placeholder) for placeholder in new_pattern.placeholders):
            raise Pyjo.Exception.new(f'Route pattern "{new_pattern.unparsed}" contains a reserved stash value')

        old_pattern = self.pattern
        if 'format' in (constraints := old_pattern.constraints) and new_pattern.constraints.get('format') is None:
            new_pattern.constraints['format'] = constraints['format']
        if 'format' in (defaults := old_pattern.defaults) and new_pattern.defaults.get('format') is None:
            new_pattern.defaults['format'] = defaults['format']

        return route


def _invalidate(route: Pyjoyment_Routes_Route | None) -> None:
    while route is not None:
        route._prefix_index = None  # pyright: ignore[reportPrivateUsage]
        route = route.parent


new = Pyjoyment_Routes_Route.new
object = Pyjoyment_Routes_Route
Route = Pyjoyment_Routes_Route
