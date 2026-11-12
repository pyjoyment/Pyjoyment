Routing
=======

Routing requests.

This document contains a simple and fun introduction to the :mod:`Pyjoyment`
router and its underlying concepts.

Concepts
--------

Essentials every :mod:`Pyjoyment` developer should know.

Dispatcher
~~~~~~~~~~

The foundation of every web framework is a tiny black box connecting incoming
requests with code generating the appropriate response.

.. code-block:: text

    GET /user/show/1 -> c.render(text='Daniel')

This black box is usually called a dispatcher. There are many
implementations using different strategies to establish these connections,
but pretty much all are based around mapping the path part of the request URL
to some kind of response generator.

.. code-block:: text

    /user/show/2 -> c.render(text='Isabell')
    /user/show/3 -> c.render(text='Sara')
    /user/show/4 -> c.render(text='Stefan')
    /user/show/5 -> c.render(text='Fynn')

While it is very well possible to make all these connections static, it is
also rather inefficient. That's why regular expressions are commonly used to
make the dispatch process more dynamic.

.. code-block:: text

    re.compile(r'/user/show/(\d+)') -> c.render(text=users[m[1]])

Modern dispatchers have pretty much everything HTTP has to offer at their
disposal and can use many more variables than just the request path, such as
request method and headers like ``Host``, ``User-Agent`` and ``Accept``.

.. code-block:: text

    GET /user/show/23 HTTP/1.1
    Host: mojolicious.org
    User-Agent: Pyjoyment (Python)
    Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8

Routes
~~~~~~

While regular expressions are quite powerful they also tend to be unpleasant
to look at and are generally overkill for ordinary path matching.

.. code-block:: text

    re.compile(r'/user/admin/(\d+)') -> c.render(text=users[m[1]])

This is where routes come into play, they have been designed from the ground
up to represent paths with placeholders.

.. code-block:: text

    /user/admin/:id -> c.render(text=users[id])

The only difference between a static path and the route above is the ``:id``
placeholder. One or more placeholders can be anywhere in the route.

.. code-block:: text

    /user/:role/:id

A fundamental concept of the :mod:`Pyjoyment` router is that extracted
placeholder values are turned into a dict.

.. code-block:: text

    /user/admin/23 -> /user/:role/:id -> {'role': 'admin', 'id': '23'}

This dict is basically the center of every :mod:`Pyjoyment` application, you
will learn more about this later on. Internally, routes get compiled to
regular expressions, so you can get the best of both worlds with a little bit
of experience.

.. code-block:: text

    /user/admin/:id -> re.compile(r'^/user/admin/([^/.]+)')

A trailing slash in the path is always optional.

.. code-block:: text

    /user/admin/23/ -> /user/:role/:id -> {'role': 'admin', 'id': '23'}

Reversibility
~~~~~~~~~~~~~

One more huge advantage routes have over regular expressions is that they are
easily reversible, extracted placeholders can be turned back into a path at
any time.

.. code-block:: text

    /sebastian -> /:name -> {'name': 'sebastian'}
    {'name': 'sebastian'} -> /:name -> /sebastian

Every placeholder has a name, even if it's just an empty string.

Standard placeholders
~~~~~~~~~~~~~~~~~~~~~

Standard placeholders are the simplest form of placeholders, they use a colon
prefix and match all characters except ``/`` and ``.``, similar to the
regular expression ``([^/.]+)``.

.. code-block:: text

    /hello              -> /:name/hello -> None
    /sebastian/23/hello -> /:name/hello -> None
    /sebastian.23/hello -> /:name/hello -> None
    /sebastian/hello    -> /:name/hello -> {'name': 'sebastian'}
    /sebastian23/hello  -> /:name/hello -> {'name': 'sebastian23'}
    /sebastian 23/hello -> /:name/hello -> {'name': 'sebastian 23'}

All placeholders can be surrounded by ``<`` and ``>`` to separate them from
the surrounding text.

.. code-block:: text

    /hello             -> /<:name>hello -> None
    /sebastian/23hello -> /<:name>hello -> None
    /sebastian.23hello -> /<:name>hello -> None
    /sebastianhello    -> /<:name>hello -> {'name': 'sebastian'}
    /sebastian23hello  -> /<:name>hello -> {'name': 'sebastian23'}
    /sebastian 23hello -> /<:name>hello -> {'name': 'sebastian 23'}

The colon prefix is optional for standard placeholders that are surrounded by
``<`` and ``>``.

.. code-block:: text

    /i♥mojolicious -> /<one>♥<two> -> {'one': 'i', 'two': 'mojolicious'}

Braces are not placeholders: a pattern is not a URI Template of :rfc:`6570`,
as ``/users/{id}``, which :mod:`Pyjo.URL.Template` expands and matches for the
protocols that give their URIs as templates.

.. _routing-relaxed-placeholders:

Relaxed placeholders
~~~~~~~~~~~~~~~~~~~~

Relaxed placeholders are just like standard placeholders, but use a hash
prefix and match all characters except ``/``, similar to the regular
expression ``([^/]+)``.

.. code-block:: text

    /hello              -> /#name/hello -> None
    /sebastian/23/hello -> /#name/hello -> None
    /sebastian.23/hello -> /#name/hello -> {'name': 'sebastian.23'}
    /sebastian/hello    -> /#name/hello -> {'name': 'sebastian'}
    /sebastian23/hello  -> /#name/hello -> {'name': 'sebastian23'}
    /sebastian 23/hello -> /#name/hello -> {'name': 'sebastian 23'}

They can be especially useful for manually matching file names with
extensions, rather than using `format detection <Formats_>`_.

.. code-block:: text

    /music/song.mp3 -> /music/#filename -> {'filename': 'song.mp3'}

Wildcard placeholders
~~~~~~~~~~~~~~~~~~~~~

Wildcard placeholders are just like the two types of placeholders above, but
use an asterisk prefix and match absolutely everything, including ``/`` and
``.``, similar to the regular expression ``(.+)``.

.. code-block:: text

    /hello              -> /*name/hello -> None
    /sebastian/23/hello -> /*name/hello -> {'name': 'sebastian/23'}
    /sebastian.23/hello -> /*name/hello -> {'name': 'sebastian.23'}
    /sebastian/hello    -> /*name/hello -> {'name': 'sebastian'}
    /sebastian23/hello  -> /*name/hello -> {'name': 'sebastian23'}
    /sebastian 23/hello -> /*name/hello -> {'name': 'sebastian 23'}

They can be useful for manually matching entire file paths.

.. code-block:: text

    /music/rock/song.mp3 -> /music/*filepath -> {'filepath': 'rock/song.mp3'}

Basics
------

Most commonly used features every :mod:`Pyjoyment` developer should know
about.

Minimal route
~~~~~~~~~~~~~

The attribute :attr:`~Pyjoyment.Pyjoyment_App.routes` contains a router you
can use to generate route structures.

.. literalinclude:: routing/minimal/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

The minimal route above will load and instantiate the class of the module
``MyApp.Controller.Foo`` and call its ``welcome`` method. Routes are usually
configured in the ``startup`` method of the application class, but the router
can be accessed from everywhere (even at runtime).

.. literalinclude:: routing/minimal/MyApp/Controller/Foo.py
    :language: python
    :caption: MyApp/Controller/Foo.py

All routes match in the same order in which they were defined, and matching
stops as soon as a suitable route has been found. Routes are indexed by the
text their patterns start with, so routes that cannot match a path are skipped
right away, and the routing performance stays the same even for applications
with many routes. Only routes starting with a placeholder, like ``/:name``,
always have to be tried. A routing cache will also be used automatically to
handle sudden traffic spikes more gracefully.

For convenience, the application object also has shortcut methods like
:meth:`~Pyjoyment.Pyjoyment_App.get` and :meth:`~Pyjoyment.Pyjoyment_App.under`,
which generate routes directly on :attr:`~Pyjoyment.Pyjoyment_App.routes`. ::

    # Same as "self.routes.get(...)"
    self.get('/welcome').to(controller='foo', action='welcome')

Routing destination
~~~~~~~~~~~~~~~~~~~

After you start a new route with methods like
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.get`, you can also give
it a destination in the form of a dict using the chained method
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.to`.

.. code-block:: python

    # /welcome -> {'controller': 'foo', 'action': 'welcome'}
    r.get('/welcome').to(controller='foo', action='welcome')

Now if the route matches an incoming request it will use the content of this
dict to try and find appropriate code to generate a response.

HTTP methods
~~~~~~~~~~~~

There are already shortcuts for the most common HTTP request methods like
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.post`, and for more
control :meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.any` accepts an
optional list with arbitrary request methods as first argument.

.. code-block:: python

    # PUT /hello  -> None
    # GET /hello  -> {'controller': 'foo', 'action': 'hello'}
    r.get('/hello').to(controller='foo', action='hello')

    # PUT /hello -> {'controller': 'foo', 'action': 'hello'}
    r.put('/hello').to(controller='foo', action='hello')

    # POST /hello -> {'controller': 'foo', 'action': 'hello'}
    r.post('/hello').to(controller='foo', action='hello')

    # GET|POST /bye  -> {'controller': 'foo', 'action': 'bye'}
    r.any(['GET', 'POST'], '/bye').to(controller='foo', action='bye')

    # * /whatever -> {'controller': 'foo', 'action': 'whatever'}
    r.any('/whatever').to(controller='foo', action='whatever')

There is one small exception, ``HEAD`` requests are considered equal to
``GET``, but content will not be sent with the response even if it is
present.

.. code-block:: python

    # GET /test  -> {'controller': 'bar', 'action': 'test'}
    # HEAD /test -> {'controller': 'bar', 'action': 'test'}
    r.get('/test').to(controller='bar', action='test')

You can also use the ``_method`` query parameter to override the request
method. This can be very useful when submitting forms with browsers that only
support ``GET`` and ``POST``.

.. code-block:: python

    # PUT  /stuff             -> {'controller': 'baz', 'action': 'stuff'}
    # POST /stuff?_method=PUT -> {'controller': 'baz', 'action': 'stuff'}
    r.put('/stuff').to(controller='baz', action='stuff')

IRIs
~~~~

IRIs are handled transparently, that means paths are guaranteed to be
unescaped and decoded from bytes to characters.

.. code-block:: python

    # GET /☃ (Unicode snowman) -> {'controller': 'foo', 'action': 'snowman'}
    r.get('/☃').to(controller='foo', action='snowman')

Stash
~~~~~

The generated dict of a matching route is actually the center of the whole
:mod:`Pyjoyment` request cycle. We call it the stash, and it persists until a
response has been generated.

.. code-block:: python

    # /bye -> {'controller': 'foo', 'action': 'bye', 'mymessage': 'Bye'}
    r.get('/bye').to(controller='foo', action='bye', mymessage='Bye')

There are a few stash values with special meaning, such as ``controller`` and
``action``, but you can generally fill it with whatever data you need to
generate a response. Once dispatched the whole stash content can be changed
at any time.

.. code-block:: python

    def bye(self):

        # Get message from stash
        msg = self.stash('mymessage')

        # Change message in stash
        self.stash(mymessage='Welcome')

You can use :meth:`~Pyjoyment.Pyjoyment_App.defaults` to set default stash
values that will be available everywhere in the application.

.. code-block:: python

    app.defaults(mymessage='Howdy')

For a full list of reserved stash values see
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.stash`.

Nested routes
~~~~~~~~~~~~~

It is also possible to build tree structures from routes to remove repetitive
code. A route with children can't match on its own though, only the actual
endpoints of these nested routes can.

.. code-block:: python

    # /foo     -> None
    # /foo/bar -> {'controller': 'foo', 'action': 'bar'}
    foo = r.any('/foo').to(controller='foo')
    foo.get('/bar').to(action='bar')

The stash is simply inherited from route to route and newer values override
old ones.

.. code-block:: python

    # /cats      -> {'controller': 'cats', 'action': 'index'}
    # /cats/nyan -> {'controller': 'cats', 'action': 'nyan'}
    # /cats/lol  -> {'controller': 'cats', 'action': 'default'}
    cats = r.any('/cats').to(controller='cats', action='default')
    cats.get('/').to(action='index')
    cats.get('/nyan').to(action='nyan')
    cats.get('/lol')

Special stash values
~~~~~~~~~~~~~~~~~~~~

When the dispatcher sees ``controller`` and ``action`` values in the stash it
will always try to turn them into a class and method to dispatch to. The
``controller`` value gets converted from ``snake_case`` to ``CamelCase``
using :func:`~Pyjo.Util.camelize` and appended to one or more namespaces,
defaulting to a controller namespace based on the application class
(``MyApp.Controller``), as well as the bare application class (``MyApp``),
and these namespaces are searched in that order. The action value is not
changed at all, so both values are case-sensitive.

.. literalinclude:: routing/special/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

.. literalinclude:: routing/special/MyApp/Controller/Foo.py
    :language: python
    :caption: MyApp/Controller/Foo.py

Controller classes are perfect for organizing code in larger projects. There
are more dispatch strategies, but because controllers are the most commonly
used ones they also got a special shortcut in the form of
``controller#action``.

.. code-block:: python

    # /bye -> {'controller': 'foo', 'action': 'bye', 'mymessage': 'Bye'}
    r.get('/bye').to('foo#bye', mymessage='Bye')

During camelization ``-`` characters get replaced with ``.``, this allows
multi-level ``controller`` hierarchies.

.. code-block:: python

    # / -> MyApp.Controller.Foo.Bar.hi
    r.get('/').to('foo-bar#hi')

You can also just specify the ``controller`` in CamelCase form instead of
snake_case.

.. code-block:: python

    # / -> MyApp.Controller.Foo.Bar.hi
    r.get('/').to('Foo.Bar#hi')

For security reasons the dispatcher will always check if the ``controller``
is actually a subclass of :mod:`Pyjoyment.Controller` or :mod:`Pyjoyment`
before dispatching to it.

The values ``inactivity_timeout`` and ``request_timeout`` are the timeouts of
a route, which are set before its first action: the inactivity timeout of the
connection, as the helper ``inactivity_timeout`` sets it, and the most time
to the end of the response, as the helper ``request_timeout`` sets it, after
which the actions are cancelled and the request gets a ``504`` response. A
request that waits for a model of language, which can be silent for minutes,
needs both, and the routes of :ref:`under <routing-under>` give them to all
the routes of a group.

.. code-block:: python

    # Ten minutes of silence, and two minutes to the end of the response at most
    r.post('/chat', {'inactivity_timeout': 600, 'request_timeout': 120}).to('chat#reply')

    # The same for every route of a group
    llm = r.under('/llm', {'inactivity_timeout': 600, 'request_timeout': 120})
    llm.post('/complete').to('llm#complete')

Namespaces
~~~~~~~~~~

You can use the ``namespace`` stash value to change the namespace of a whole
route with all its children.

.. code-block:: python

    # /bye -> MyApp.MyController.Foo.Bar.bye
    r.get('/bye').to(namespace='MyApp.MyController', controller='Foo.Bar', action='bye')

The ``controller`` is always converted from ``snake_case`` to ``CamelCase``
with :func:`~Pyjo.Util.camelize`, and then appended to this ``namespace``.

.. code-block:: python

    # /bye -> MyApp.MyController.Foo.Bar.bye
    r.get('/bye').to('foo-bar#bye', namespace='MyApp.MyController')

    # /hey -> MyApp.MyController.Foo.Bar.hey
    r.get('/hey').to('Foo.Bar#hey', namespace='MyApp.MyController')

You can also change the default namespaces for all routes in the application
with the router attribute :attr:`~Pyjoyment.Routes.Pyjoyment_Routes.namespaces`,
which usually defaults to a namespace based on the application class
(``MyApp.Controller``), as well as the bare application class (``MyApp``).

.. code-block:: python

    r.namespaces = ['MyApp.MyController']

Route to callback
~~~~~~~~~~~~~~~~~

The ``cb`` stash value, which won't be inherited by nested routes, can be
used to bypass controllers and execute a callback instead.

.. code-block:: python

    r.get('/bye').to(cb=lambda c: c.render(text='Good bye.'))

But just like in :mod:`Pyjoyment.Lite` you can also pass the callback
directly, or decorate it with the route, which usually looks much better.

.. code-block:: python

    @r.get('/bye')
    def bye(c):
        c.render(text='Good bye.')

Named routes
~~~~~~~~~~~~

Naming your routes will allow backreferencing in many methods and helpers
throughout the whole framework, most of which internally rely on
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.url_for` for this.

.. code-block:: python

    # /foo/marcus -> {'controller': 'foo', 'action': 'bar', 'user': 'marcus'}
    r.get('/foo/:user').to('foo#bar').set(name='baz')

    # Generate URL "/foo/marcus" for route "baz" (in previous request context)
    url = c.url_for('baz')

    # Generate URL "/foo/jan" for route "baz"
    url = c.url_for('baz', user='jan')

    # Generate URL "http://127.0.0.1:3000/foo/jan" for route "baz"
    url = c.url_for('baz', user='jan').to_abs()

You can assign a name with
:attr:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.name`, or let the
router generate one automatically, which would be equal to the route itself
without non-word characters, custom names have a higher precedence though.

.. code-block:: python

    # /foo/bar ("foobar")
    r.get('/foo/bar').to('test#stuff')

    # Generate URL "/foo/bar"
    url = c.url_for('foobar')

To refer to the current route you can use the reserved name ``current`` or
no name at all.

.. code-block:: python

    # Generate URL for current route
    url = c.url_for('current')
    url = c.url_for()

To check or get the name of the current route you can use the helper
``current_route`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`.

.. code-block:: python

    # Name for current route
    name = c.current_route()

    # Check route name in code shared by multiple routes
    if c.current_route('login'):
        c.stash(button='green')

Optional placeholders
~~~~~~~~~~~~~~~~~~~~~

Extracted placeholder values will simply redefine older stash values if they
already exist.

.. code-block:: python

    # /bye -> {'controller': 'foo', 'action': 'bar', 'mymessage': 'bye'}
    # /hey -> {'controller': 'foo', 'action': 'bar', 'mymessage': 'hey'}
    r.get('/:mymessage').to('foo#bar', mymessage='hi')

One more interesting effect, a placeholder automatically becomes optional if
there is already a stash value of the same name present, this works similar
to the regular expression ``([^/.]+)?``.

.. code-block:: python

    # / -> {'controller': 'foo', 'action': 'bar', 'mymessage': 'hi'}
    r.get('/:mymessage').to('foo#bar', mymessage='hi')

    # /test/123     -> {'controller': 'foo', 'action': 'bar', 'mymessage': 'hi'}
    # /test/bye/123 -> {'controller': 'foo', 'action': 'bar', 'mymessage': 'bye'}
    r.get('/test/:mymessage/123').to('foo#bar', mymessage='hi')

And if two optional placeholders are only separated by a slash, that slash
can become optional as well.

Restrictive placeholders
~~~~~~~~~~~~~~~~~~~~~~~~

A very easy way to make placeholders more restrictive are alternatives, you
just make a list of possible values, which then work similar to the regular
expression ``(bender|leela)``.

.. code-block:: python

    # /fry    -> None
    # /bender -> {'controller': 'foo', 'action': 'bar', 'name': 'bender'}
    # /leela  -> {'controller': 'foo', 'action': 'bar', 'name': 'leela'}
    r.get('/:name', name=['bender', 'leela']).to('foo#bar')

You can also adjust the regular expressions behind placeholders directly,
just make sure not to use ``^`` and ``$`` or capturing groups ``(...)``,
because placeholders become part of a larger regular expression internally,
non-capturing groups ``(?:...)`` are fine though.

.. code-block:: python

    # /23   -> {'controller': 'foo', 'action': 'bar', 'number': '23'}
    # /test -> None
    r.get('/:number', number=re.compile(r'\d+')).to('foo#bar')

    # /23   -> None
    # /test -> {'controller': 'foo', 'action': 'bar', 'name': 'test'}
    r.get('/:name', name=re.compile(r'[a-zA-Z]+')).to('foo#bar')

This way you get easily readable routes and the raw power of regular
expressions.

Placeholder types
~~~~~~~~~~~~~~~~~

And if you have multiple routes using restrictive placeholders you can also
turn them into placeholder types with
:meth:`~Pyjoyment.Routes.Pyjoyment_Routes.add_type`.

.. code-block:: python

    # A type with alternatives
    r.add_type('futurama_name', ['bender', 'leela'])

    # /fry    -> None
    # /bender -> {'controller': 'foo', 'action': 'bar', 'name': 'bender'}
    # /leela  -> {'controller': 'foo', 'action': 'bar', 'name': 'leela'}
    r.get('/<name:futurama_name>').to('foo#bar')

Placeholder types work just like restrictive placeholders, they are just
reusable with the ``<placeholder:type>`` notation.

.. code-block:: python

    # A type adjusting the regular expression
    r.add_type('upper', re.compile(r'[A-Z]+'))

    # /user/ROOT -> {'controller': 'users', 'action': 'show', 'name': 'ROOT'}
    # /user/root -> None
    # /user/23   -> None
    r.get('/user/<name:upper>').to('users#show')

Some types like ``num`` are used so commonly that they are available by
default.

.. code-block:: python

    # /article/12   -> {'controller': 'articles', 'action': 'show', 'id': '12'}
    # /article/test -> None
    r.get('/article/<id:num>').to('articles#show')

For a full list of available placeholder types see also the types of
:mod:`Pyjoyment.Routes`.

Introspection
~~~~~~~~~~~~~

The command :mod:`Pyjoyment.Command.routes` can be used from the command line
to list all available routes together with names and underlying regular
expressions.

.. code-block:: console

    $ ./myapp.py routes -v
    /foo/:name  ....  POST  fooname  ^/foo/([^/.]+)
    /bar        ..U.  *     bar      ^/bar
      +/baz     ...W  GET   baz      ^/baz
    /yada       ....  *     yada     ^/yada

.. _routing-under:

Under
~~~~~

To share code with multiple nested routes you can use
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.under`, because unlike
normal nested routes, the routes generated with it have their own
intermediate destination and result in additional dispatch cycles when they
match.

.. code-block:: python

    # /foo     -> None
    # /foo/bar -> {'controller': 'foo', 'action': 'baz'}
    #             {'controller': 'foo', 'action': 'bar'}
    foo = r.under('/foo').to('foo#baz')
    foo.get('/bar').to('#bar')

The actual action code for this destination needs to return a true value or
the dispatch chain will be broken, this can be a very powerful tool for
authentication.

.. code-block:: python

    # /blackjack -> {'cb': ...}
    #               {'controller': 'hideout', 'action': 'blackjack'}
    @r.under('/')
    def auth(c):

        # Authenticated
        if c.req.headers.header('X-Bender'):
            return True

        # Not authenticated
        c.render(text="You're not Bender.", status=401)
        return None

    auth.get('/blackjack').to('hideout#blackjack')

Broken dispatch chains can be continued by calling
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.proceed`, this allows for
example, non-blocking operations to finish before reaching the next dispatch
cycle.

.. code-block:: python

    @r.under('/maybe')
    def maybe(c):

        # Wait 3 seconds and then give visitors a 50% chance to continue
        @Pyjo.IOLoop.timer(3)
        def timer(loop):

            # Loser
            if not random.randrange(2):
                return c.render(text='No luck.')

            # Winner
            c.proceed()

        return None

    maybe.get('/').to('maybe#winner')

Every destination is just a snapshot of the stash at the time the route
matched, and only the ``format`` value is shared by all of them. For a little
more power you can introspect the preceding and succeeding destinations with
:attr:`~Pyjoyment.Controller.Pyjoyment_Controller.match`.

.. code-block:: python

    # Action of the fourth dispatch cycle
    action = c.match.stack[3]['action']

.. _routing-formats:

Formats
~~~~~~~

File extensions like ``.html`` and ``.txt`` at the end of a route can be
detected and stored in the stash value ``format``. Use a restrictive
placeholder to declare the possible values.

.. code-block:: python

    # /foo.txt -> None
    # /foo.rss -> {'controller': 'foo', 'action': 'bar', 'format': 'rss'}
    # /foo.xml -> {'controller': 'foo', 'action': 'bar', 'format': 'xml'}
    r.get('/foo', format=['rss', 'xml']).to('foo#bar')

This for example, allows multiple templates in different formats to share
the same action code. And just like with placeholders you can use a default
value to make the format optional.

.. code-block:: python

    # /foo      -> {'controller': 'foo', 'action': 'bar', 'format': None}
    # /foo.html -> {'controller': 'foo', 'action': 'bar', 'format': 'html'}
    # /foo.txt  -> {'controller': 'foo', 'action': 'bar', 'format': 'txt'}
    r.get('/foo', format=['html', 'txt']).to('foo#bar', format=None)

Formats can be inherited by nested routes.

.. code-block:: python

    # /foo      -> {'controller': 'foo', 'action': 'one', 'format': None}
    # /foo.html -> {'controller': 'foo', 'action': 'one', 'format': 'html'}
    # /foo.json -> {'controller': 'foo', 'action': 'one', 'format': 'json'}
    # /bar      -> {'controller': 'bar', 'action': 'two', 'format': None}
    # /bar.html -> {'controller': 'bar', 'action': 'two', 'format': 'html'}
    # /bar.json -> {'controller': 'bar', 'action': 'two', 'format': 'json'}
    with_format = r.any('/', format=['html', 'json']).to(format=None)
    with_format.get('/foo').to('foo#one')
    with_format.get('/bar').to('bar#two')

A ``format`` value can also be passed to
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.url_for`.

.. code-block:: python

    # /foo/23.txt -> {'controller': 'foo', 'action': 'bar', 'id': '23', 'format': 'txt'}
    r.get('/foo/:id', format=['txt']).to('foo#bar').set(name='baz')

    # Generate URL "/foo/24.txt" for route "baz"
    url = c.url_for('baz', id=24, format='txt')

WebSockets
~~~~~~~~~~

With the method
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.websocket` you can
restrict access to WebSocket handshakes, which are normal ``GET`` requests
with some additional information.

.. code-block:: python

    # /echo (WebSocket handshake)
    r.websocket('/echo').to('foo#echo')

.. literalinclude:: routing/websockets/MyApp/Controller/Foo.py
    :language: python
    :caption: MyApp/Controller/Foo.py

The connection gets established when you respond to the WebSocket handshake
request with a ``101`` response status, which happens automatically if you
subscribe to an event with
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.on` or send a message with
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.send` right away.

.. code-block:: text

    GET /echo HTTP/1.1
    Host: mojolicious.org
    User-Agent: Pyjoyment (Python)
    Connection: Upgrade
    Upgrade: websocket
    Sec-WebSocket-Key: IDM3ODE4NDk2MjA1OTcxOQ==
    Sec-WebSocket-Version: 13

    HTTP/1.1 101 Switching Protocols
    Server: Pyjoyment (Python)
    Date: Tue, 03 Feb 2015 17:08:24 GMT
    Connection: Upgrade
    Upgrade: websocket
    Sec-WebSocket-Accept: SWsp5N2iNxPbHlcOTIw8ERvyVPY=

Catch-all route
~~~~~~~~~~~~~~~

Since routes match in the order in which they were defined, you can catch
all requests that did not match in your last route with an optional wildcard
placeholder.

.. code-block:: python

    # * /*
    @r.any('/*whatever', {'whatever': ''})
    def whatever(c):
        whatever = c.param('whatever')
        c.render(text=f'/{whatever} did not match.', status=404)

Conditions
~~~~~~~~~~

Conditions such as ``headers``, ``agent`` and ``host`` from
:mod:`Pyjoyment.Plugin.HeaderCondition` can be applied to any route with the
method :meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.requires`, and
allow even more powerful route constructs.

.. code-block:: python

    # / (Origin: http://python.org)
    r.get('/').requires(headers={'Origin': re.compile(r'python\.org')}).to('foo#bar')

    # / (Firefox)
    r.get('/').requires(agent=re.compile(r'Firefox')).to('browser-test#firefox')

    # / (Internet Explorer)
    r.get('/').requires(agent=re.compile(r'Internet Explorer')).to('browser-test#ie')

    # http://docs.mojolicious.org/Mojolicious
    r.get('/').requires(host='docs.mojolicious.org').to('perldoc#index')

Just be aware that conditions are too complex for the routing cache, which
normally speeds up recurring requests, and can therefore reduce performance.

Hooks
~~~~~

Hooks operate outside the routing system and allow you to extend the
framework itself by sharing code with all requests indiscriminately through
:meth:`~Pyjoyment.Pyjoyment_App.hook`, which makes them a very powerful tool
especially for plugins.

.. literalinclude:: routing/hooks/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

Post-processing the response to add or remove headers is a very common use.

.. code-block:: python

    # Make sure static files are cached
    @app.hook('after_static')
    def after_static(c):
        c.res.headers.cache_control = 'max-age=3600, must-revalidate'

    # Remove a default header
    @app.hook('after_dispatch')
    def after_dispatch(c):
        c.res.headers.remove('Server')

Same for pre-processing the request.

.. code-block:: python

    # Choose template variant based on request headers
    @app.hook('before_dispatch')
    def before_dispatch(c):
        if not (agent := c.req.headers.user_agent):
            return
        if re.search(r'Internet Explorer', agent):
            c.stash(variant='ie')

Or more advanced extensions to add monitoring to your application.

.. code-block:: python

    # Forward exceptions to a web service
    @app.hook('after_dispatch')
    def after_dispatch(c):
        if not (e := c.stash('exception')):
            return
        c.ua().post_p('https://example.com/bugs', form={'exception': str(e)})

You can even extend much of the core functionality.

.. code-block:: python

    # Pass route name as argument to actions
    @app.hook('around_action')
    def around_action(next, c, action, last):
        return action(c, c.current_route())

For a full list of available hooks see :meth:`~Pyjoyment.Pyjoyment_App.hook`.

Advanced
--------

Less commonly used and more powerful features.

Shortcuts
~~~~~~~~~

To make route generation more expressive, you can also add your own
shortcuts with :meth:`~Pyjoyment.Routes.Pyjoyment_Routes.add_shortcut`.

.. code-block:: python

    # Simple "resource" shortcut
    def resource(r, name):

        # Prefix for resource
        resource = r.any(f'/{name}').to(f'{name}#')

        # Render a list of resources
        resource.get('/').to('#index').set(name=name)

        # Render a form to create a new resource (submitted to "store")
        resource.get('/create').to('#create').set(name=f'create_{name}')

        # Store newly created resource (submitted by "create")
        resource.post().to('#store').set(name=f'store_{name}')

        # Render a specific resource
        resource.get('/:id').to('#show').set(name=f'show_{name}')

        # Render a form to edit a resource (submitted to "update")
        resource.get('/:id/edit').to('#edit').set(name=f'edit_{name}')

        # Store updated resource (submitted by "edit")
        resource.put('/:id').to('#update').set(name=f'update_{name}')

        # Remove a resource
        resource.delete('/:id').to('#remove').set(name=f'remove_{name}')

        return resource

    r.add_shortcut('resource', resource)

    # GET /users         -> {'controller': 'users', 'action': 'index'}
    # GET /users/create  -> {'controller': 'users', 'action': 'create'}
    # POST /users        -> {'controller': 'users', 'action': 'store'}
    # GET /users/23      -> {'controller': 'users', 'action': 'show', 'id': '23'}
    # GET /users/23/edit -> {'controller': 'users', 'action': 'edit', 'id': '23'}
    # PUT /users/23      -> {'controller': 'users', 'action': 'update', 'id': '23'}
    # DELETE /users/23   -> {'controller': 'users', 'action': 'remove', 'id': '23'}
    r.resource('users')

Rearranging routes
~~~~~~~~~~~~~~~~~~

From application startup until the first request has arrived, all routes can
still be moved around or even removed with methods like
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.add_child` and
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.remove`.

.. code-block:: python

    # GET /example/show -> {'controller': 'example', 'action': 'show'}
    show = r.get('/show').to('example#show')
    r.any('/example').add_child(show)

    # Nothing
    r.get('/secrets/show').to('secrets#show').set(name='show_secrets')
    r.find('show_secrets').remove()

Especially for rearranging routes created by plugins this can be very useful,
to find routes by their name you can use
:meth:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.find`.

.. code-block:: python

    # GET /example/test -> {'controller': 'example', 'action': 'test'}
    r.get('/something/else').to('something#else').set(name='test')
    test = r.find('test')
    test.pattern.parse('/example/test')
    test.pattern.defaults = {'controller': 'example', 'action': 'test'}

Even the route pattern and destination can still be changed with
:meth:`~Pyjoyment.Routes.Pattern.Pyjoyment_Routes_Pattern.parse` and
:attr:`~Pyjoyment.Routes.Pattern.Pyjoyment_Routes_Pattern.defaults`.

Adding conditions
~~~~~~~~~~~~~~~~~

You can also add your own conditions with the method
:meth:`~Pyjoyment.Routes.Pyjoyment_Routes.add_condition`. All conditions are
basically router plugins that run every time a new request arrives, and which
need to return a true value for the route to match.

.. code-block:: python

    # A condition that randomly allows a route to match
    def random_condition(route, c, captures, num):

        # Loser
        if random.randrange(num):
            return None

        # Winner
        return True

    r.add_condition('random', random_condition)

    # /maybe (25% chance)
    r.get('/maybe').requires(random=4).to('foo#bar')

Use whatever request information you need.

.. code-block:: python

    # A condition to check query parameters (useful for mock web services)
    def query(route, c, captures, values):

        for key in values:
            param = c.req.url.query.param(key)
            if param is None or param != values[key]:
                return None

        return True

    r.add_condition('query', query)

    # /hello?to=world&test=1
    r.get('/hello').requires(query={'test': '1', 'to': 'world'}).to('foo#bar')

Condition plugins
~~~~~~~~~~~~~~~~~

You can also package your conditions as reusable plugins, in the namespace
``Pyjoyment.Plugin``, which a directory ``Pyjoyment/Plugin`` of your project
extends.

.. literalinclude:: routing/werewolf/Pyjoyment/Plugin/WerewolfCondition.py
    :language: python
    :caption: Pyjoyment/Plugin/WerewolfCondition.py

Now just load the plugin and you are ready to use the condition in all your
applications.

.. literalinclude:: routing/werewolf/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

Mount applications
~~~~~~~~~~~~~~~~~~

The easiest way to embed one application into another is
:mod:`Pyjoyment.Plugin.Mount`, which allows you to mount whole self-contained
applications under a domain and/or prefix.

.. code-block:: python

    from Pyjoyment.Lite import *

    # Whole application mounted under "/prefix"
    plugin('Mount', {'/prefix': '/home/sri/myapp/myapp.py'})

    # Mount application with subdomain
    plugin('Mount', {'test.example.com': '/home/sri/myapp2.py'})

    # Normal route
    @get('/')
    def index(c):
        c.render(text='Hello World!')

    app.start()

:mod:`Pyjoyment.Plugin.Mount` mounts the applications of other frameworks
too, ``WSGI``, ``ASGI``, ``FastCGI`` and ``CGI`` applications and event
functions of AWS Lambda, which :doc:`mounting` describes.

Embed applications
~~~~~~~~~~~~~~~~~~

For a little more power you can also embed applications by using them
instead of a controller. This allows for example, the use of the
:mod:`Pyjoyment.Lite` domain specific language in normal :mod:`Pyjoyment`
controllers.

.. literalinclude:: routing/embed_lite/MyApp/Controller/Bar.py
    :language: python
    :caption: MyApp/Controller/Bar.py

With the attribute
:attr:`~Pyjoyment.Routes.Route.Pyjoyment_Routes_Route.partial`, you can allow
the route to partially match and use only the remaining path in the embedded
application, the base path will be passed along in the ``path`` stash value.

.. code-block:: python

    # /foo/*
    r.any('/foo').set(partial=True).to('bar#', name='Pyjo')

A minimal embeddable application is nothing more than a subclass of
:mod:`Pyjoyment`, containing a ``handler`` method accepting
:mod:`Pyjoyment.Controller` objects.

.. literalinclude:: routing/embed/MyApp/Controller/Bar.py
    :language: python
    :caption: MyApp/Controller/Bar.py

The host application will only share very little information with the
embedded application through the stash. So you cannot currently use route
placeholders in routes leading to embedded applications, since that would
cause problems with :meth:`~Pyjoyment.Controller.Pyjoyment_Controller.url_for`.

Application plugins
~~~~~~~~~~~~~~~~~~~

You can even package applications as self-contained reusable plugins.

.. literalinclude:: routing/app_plugin/Pyjoyment/Plugin/MyEmbeddedApp.py
    :language: python
    :caption: Pyjoyment/Plugin/MyEmbeddedApp.py

An application of :mod:`Pyjoyment.Lite` is the one of its module, so the
embedded application is a module of its own.

.. literalinclude:: routing/app_plugin/EmbeddedApp.py
    :language: python
    :caption: EmbeddedApp.py

The ``app`` stash value, which won't be inherited by nested routes, can be
used for already instantiated applications. Now just load the plugin and
you're done.

.. literalinclude:: routing/app_plugin/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

More
----

You can continue with :doc:`index` now or take a look at the `Mojolicious
wiki <https://github.com/mojolicious/mojo/wiki>`_, which contains a lot more
documentation and examples by many different authors.

Ported from `Mojolicious::Guides::Routing
<https://github.com/mojolicious/mojo/blob/v9.53/lib/Mojolicious/Guides/Routing.pod>`_
of Mojolicious 9.53.
