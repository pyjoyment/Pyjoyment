Growing
=======

Growing Pyjoyment applications.

This document explains the process of starting a :mod:`Pyjoyment.Lite`
prototype from scratch and growing it into a well-structured
:mod:`Pyjoyment` application. The final result of this guide is also
available as an `example application
<https://github.com/pyjoyment/Pyjoyment/tree/main/docs/guides/growing/login>`_.

Concepts
--------

Essentials every :mod:`Pyjoyment` developer should know.

Model View Controller
~~~~~~~~~~~~~~~~~~~~~

MVC is a software architectural pattern for graphical user interface
programming originating in Smalltalk-80, that separates application logic,
presentation and input.

.. mermaid::

    flowchart LR
        Input --> Controller --> Model --> View --> Output
        classDef plain fill:none,stroke:none
        class Input,Output plain

A slightly modified version of the pattern moving some application logic into
the *controller* is the foundation of pretty much every web framework these
days, including :mod:`Pyjoyment`.

.. mermaid::

    %%{init: {'class': {'hideEmptyMembersBox': true}}}%%
    classDiagram
        direction LR
        class Request
        class Response
        class Controller
        class Model
        class View
        Request --> Controller
        Response <-- Controller
        Controller <--> Model
        Controller <--> View
        style Request fill:none,stroke:none
        style Response fill:none,stroke:none

The *controller* receives a request from a user, passes incoming data to the
*model* and retrieves data from it, which then gets turned into an actual
response by the *view*. But note that this pattern is just a guideline that
most of the time results in cleaner more maintainable code, not a rule that
should be followed at all costs.

REpresentational State Transfer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REST is a software architectural style for distributed hypermedia systems
such as the web. While it can be applied to many protocols it is most
commonly used with HTTP these days. In REST terms, when you are opening a URL
like ``http://mojolicious.org/foo`` with your browser, you are basically
asking the web server for the HTML *representation* of the
``http://mojolicious.org/foo`` *resource*.

.. mermaid::

    sequenceDiagram
        participant C as Client
        participant S as Server
        C->>S: http://mojolicious.org/foo
        S-->>C: #lt;html#gt;Mojo rocks!#lt;/html#gt;

The fundamental idea here is that all resources are uniquely addressable with
URLs and every resource can have different representations such as HTML, RSS
or JSON. User interface concerns are separated from data storage concerns and
all session state is kept client-side.

.. mermaid::

    sequenceDiagram
        participant B as Browser
        participant S as Web Server
        B->>S: PUT /foo<br/>Hello World!
        S-->>B: 201 CREATED
        B->>S: GET /foo
        S-->>B: 200 OK<br/>Hello World!
        B->>S: DELETE /foo
        S-->>B: 200 OK

While HTTP methods such as ``PUT``, ``GET`` and ``DELETE`` are not directly
part of REST they go well with it and are commonly used to manipulate
*resources*.

Sessions
~~~~~~~~

HTTP was designed as a stateless protocol, web servers don't know anything
about previous requests, which makes user-friendly login systems tricky.
Sessions solve this problem by allowing web applications to keep stateful
information across several HTTP requests.

.. code-block:: text

    GET /login?user=sebastian&pass=s3cret HTTP/1.1
    Host: mojolicious.org

    HTTP/1.1 200 OK
    Set-Cookie: sessionid=987654321
    Content-Length: 16
    Hello sebastian.

    GET /protected HTTP/1.1
    Host: mojolicious.org
    Cookie: sessionid=987654321

    HTTP/1.1 200 OK
    Set-Cookie: sessionid=987654321
    Content-Length: 22
    Hello again sebastian.

Traditionally all session data was stored on the server-side and only session
IDs were exchanged between browser and web server in the form of cookies.

.. code-block:: text

    Set-Cookie: session=hmac-sha256(base64(json($session)))

In :mod:`Pyjoyment` however we are taking this concept one step further by
storing everything JSON serialized and Base64 encoded in HMAC-SHA256 signed
cookies, which is more compatible with the REST philosophy and reduces
infrastructure requirements.

Test-Driven Development
~~~~~~~~~~~~~~~~~~~~~~~

TDD is a software development process where the developer starts writing
failing test cases that define the desired functionality and then moves on to
producing code that passes these tests. There are many advantages such as
always having good test coverage and code being designed for testability,
which will in turn often prevent future changes from breaking old code. Much
of :mod:`Pyjoyment` was ported using TDD, with the tests of Mojolicious
first.

Prototype
---------

One of the main differences between :mod:`Pyjoyment` and other web
frameworks is that it also includes :mod:`Pyjoyment.Lite`, a micro web
framework optimized for rapid prototyping.

Differences
~~~~~~~~~~~

You likely know the feeling, you've got a really cool idea and want to try it
as quickly as possible, that's exactly why :mod:`Pyjoyment.Lite` applications
don't need more than a single file.

.. code-block:: text

    myapp.py   # Templates and even static files can be inlined

Full :mod:`Pyjoyment` applications on the other hand are much closer to a
well organized Python project to maximize maintainability.

.. mermaid::

    treeView-beta
        my_app ## Application directory
            MyApp ## Application package
                __init__.py ## Application class
                __main__.py ## Application script
                Controller ## Controller package
                    Example.py ## Controller class
            my_app.yml ## Configuration file
            pyproject.toml ## Project file with the dependencies
            AGENTS.md ## Guide of coding agents
            CLAUDE.md ## Import of AGENTS.md for Claude Code
            t ## Test directory
                basic.py ## Random test
            public ## Static file directory (served automatically)
                assets ## Static assets created by bundlers
                    *generated assets*
                index.html ## Static HTML file
            templates ## Template directory
                layouts ## Template directory for layouts
                    default.html.ep ## Layout template
                example ## Template directory for "Example" controller
                    welcome.html.ep ## Template for "welcome" action

Both application skeletons can be automatically generated with the commands
:mod:`Pyjoyment.Command.Author.generate.lite_app` and
:mod:`Pyjoyment.Command.Author.generate.app`.

.. code-block:: console

    $ pyjo generate lite-app myapp.py
    $ pyjo generate app MyApp

Feature-wise both are almost equal, the only real differences are
organizational, so each one can be gradually transformed into the other.

Foundation
~~~~~~~~~~

We start our new application with a single executable Python script.

.. code-block:: console

    $ mkdir myapp
    $ cd myapp
    $ touch myapp.py
    $ chmod 744 myapp.py

This will be the foundation for our login manager example application.

.. literalinclude:: growing/foundation/myapp.py
    :language: python
    :caption: myapp.py

The built-in development web server makes working on your application a lot
of fun thanks to automatic reloading.

.. code-block:: console

    $ pyjo-reload ./myapp.py
    Web application available at http://127.0.0.1:3000

Just save your changes and they will be automatically in effect the next time
you refresh your browser.

A bird's-eye view
~~~~~~~~~~~~~~~~~

It all starts with an HTTP request like this, sent by your browser.

.. code-block:: text

    GET / HTTP/1.1
    Host: localhost:3000

Once the request has been received by the web server through the event loop,
it will be passed on to :mod:`Pyjoyment`, where it will be handled in a few
simple steps.

1. Check if a static file exists that would meet the requirements.

2. Try to find a route that would meet the requirements.

3. Dispatch the request to this route, usually reaching one or more actions.

4. Process the request, maybe generating a response with the renderer.

5. Return control to the web server, and if no response has been generated
   yet, wait for a non-blocking operation to do so through the event loop.

With our application the router would have found an action in step 2, and
rendered some text in step 4, resulting in an HTTP response like this being
sent back to the browser.

.. code-block:: text

    HTTP/1.1 200 OK
    Content-Length: 12
    Hello World!

Model
~~~~~

In :mod:`Pyjoyment` we consider web applications simple frontends for
existing business logic. That means :mod:`Pyjoyment` is by design entirely
*model* layer agnostic, and you just use whatever Python modules you like
most.

.. code-block:: console

    $ mkdir -p MyApp/Model
    $ touch MyApp/Model/Users.py
    $ chmod 644 MyApp/Model/Users.py

Our login manager will use a plain old Python class abstracting away all
logic related to matching usernames and passwords. The name
``MyApp.Model.Users`` is an arbitrary choice, and is simply used to make the
separation of concerns more visible.

.. literalinclude:: growing/login/MyApp/Model/Users.py
    :language: python
    :caption: MyApp/Model/Users.py

A simple helper can be registered with the function ``helper`` of
:mod:`Pyjoyment.Lite` to make our model available to all actions and
templates. The directory of a script is the first one of ``sys.path``, so
the script imports the model without any setup.

.. literalinclude:: growing/model/myapp.py
    :language: python
    :caption: myapp.py

The method :meth:`~Pyjoyment.Controller.Pyjoyment_Controller.param` is used
to access query parameters, ``POST`` parameters, file uploads and route
placeholders, all at once.

Testing
~~~~~~~

In :mod:`Pyjoyment` we take testing very seriously and try to make it a
pleasant experience.

.. code-block:: console

    $ mkdir t
    $ touch t/login.py
    $ chmod 644 t/login.py

:mod:`Pyjo.Test.Pyjo` is a scriptable HTTP user agent designed specifically
for testing, with many fun state-of-the-art features such as CSS selectors
based on :mod:`Pyjo.DOM`.

.. literalinclude:: growing/prototype/t/login.py
    :language: python
    :caption: t/login.py

Your application won't pass these tests, but from now on you can use them to
check your progress.

.. code-block:: console

    $ pyjo-prove -l
    $ pyjo-prove -l t/login.py
    $ pyjo-prove -l -v t/login.py

Or perform quick requests right from the command line with
:mod:`Pyjoyment.Command.get`.

.. code-block:: console

    $ ./myapp.py get /
    Wrong username or password.

    $ ./myapp.py get -v '/?user=sebastian&pass=secr3t'
    GET /?user=sebastian&pass=secr3t HTTP/1.1
    Accept-Encoding: gzip
    Host: 127.0.0.1:59472
    User-Agent: Pyjoyment (Python)

    HTTP/1.1 200 OK
    Content-Length: 18
    Content-Type: text/html;charset=UTF-8
    Date: Sun, 18 Oct 2026 16:24:42 GMT
    Server: Pyjoyment (Python)

    Welcome sebastian.

State keeping
~~~~~~~~~~~~~

Sessions in :mod:`Pyjoyment` pretty much just work out of the box once you
start using the method :meth:`~Pyjoyment.Controller.Pyjoyment_Controller.session`,
there is no setup required, but we suggest setting a more secure passphrase
with :attr:`~Pyjoyment.Pyjoyment_App.secrets`.

.. code-block:: python

    app.secrets = ['Pyjoyment rocks']

This passphrase is used by the HMAC-SHA256 algorithm to make signed cookies
tamper resistant and can be changed at any time to invalidate all existing
sessions.

.. code-block:: python

    c.session(user='sebastian')
    user = c.session('user')

By default all sessions expire after one hour, for more control you can use
the ``expiration`` session value to set an expiration date in seconds from
now.

.. code-block:: python

    c.session(expiration=3600)

And the whole session can be deleted by using the ``expires`` session value
to set an absolute expiration date in the past.

.. code-block:: python

    c.session(expires=1)

For data that should only be visible on the next request, like a
confirmation message after a ``302`` redirect performed with the helper
``redirect_to`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`, you can use the
flash, accessible through its helper ``flash``.

.. code-block:: python

    c.flash(message='Everything is fine.')
    c.redirect_to('goodbye')

Just remember that all session data gets serialized with :mod:`Pyjo.JSON` and
stored in HMAC-SHA256 signed cookies, which usually have a ``4096`` byte
(4KiB) limit, depending on browser.

Final prototype
~~~~~~~~~~~~~~~

A final ``myapp.py`` prototype passing all of the tests above could look like
this.

.. literalinclude:: growing/prototype/myapp.py
    :language: python
    :caption: myapp.py

And the directory structure should be looking like this now.

.. mermaid::

    treeView-beta
        myapp
            myapp.py
            MyApp
                Model
                    Users.py
            t
                login.py

Our templates are using quite a few features of the renderer,
:doc:`rendering` explains them all in great detail.

Well-structured application
---------------------------

Due to the flexibility of :mod:`Pyjoyment` there are many variations of the
actual growing process, but this should give you a good overview of the
possibilities.

Inflating templates
~~~~~~~~~~~~~~~~~~~

All templates and static files inlined in the ``__DATA__`` section of the
docstring can be automatically turned into separate files in the
``templates`` and ``public`` directories with the command
:mod:`Pyjoyment.Command.Author.inflate`.

.. code-block:: console

    $ ./myapp.py inflate

Those directories have a higher precedence, so inflating can also be a great
way to allow your users to customize their applications.

Simplified application class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the heart of every full :mod:`Pyjoyment` application and always gets
instantiated during server startup.

.. code-block:: console

    $ touch MyApp/__init__.py
    $ chmod 644 MyApp/__init__.py

We will start by extracting all actions from ``myapp.py`` and turn them into
simplified hybrid routes in the :mod:`Pyjoyment.Routes` router, none of the
actual action code needs to be changed. A route is a decorator of its action
here too.

.. literalinclude:: growing/hybrid/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

The ``startup`` method gets called right after instantiation and is the place
where the whole application gets set up. Since full :mod:`Pyjoyment`
applications can use nested routes they have no need for ``group`` blocks.

Simplified application script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``myapp.py`` itself can now be turned into a simplified application script
to allow running tests again.

.. literalinclude:: growing/hybrid/myapp.py
    :language: python
    :caption: myapp.py

And the directory structure of our hybrid application should be looking like
this.

.. mermaid::

    treeView-beta
        myapp
            myapp.py
            MyApp
                __init__.py
                Model
                    Users.py
            t
                login.py
            templates
                layouts
                    default.html.ep
                index.html.ep
                protected.html.ep

Controller class
~~~~~~~~~~~~~~~~

Hybrid routes are a nice intermediate step, but to maximize maintainability
it makes sense to split our action code from its routing information.

.. code-block:: console

    $ mkdir MyApp/Controller
    $ touch MyApp/Controller/Login.py
    $ chmod 644 MyApp/Controller/Login.py

Once again the actual action code does not need to change, we just rename
``c`` to ``self`` since the controller is now the invocant.

.. literalinclude:: growing/login/MyApp/Controller/Login.py
    :language: python
    :caption: MyApp/Controller/Login.py

All :mod:`Pyjoyment.Controller` controllers are plain old Python classes and
get instantiated on demand. The module names its class with ``object``, as
the modules of :mod:`Pyjoyment` do.

Application class
~~~~~~~~~~~~~~~~~

The application class ``MyApp/__init__.py`` can now be reduced to model and
routing information.

.. literalinclude:: growing/login/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

The router allows many different route variations, :doc:`routing` explains
them all in great detail.

Templates
~~~~~~~~~

Templates are our views, and usually bound to controllers, so they need to be
moved into the appropriate directories.

.. code-block:: console

    $ mkdir templates/login
    $ mv templates/index.html.ep templates/login/index.html.ep
    $ mv templates/protected.html.ep templates/login/protected.html.ep

Script
~~~~~~

Finally ``myapp.py`` can be moved into the package of the application as
``MyApp/__main__.py``, as :mod:`Pyjoyment.Command.Author.generate.app` has
it.

.. code-block:: console

    $ mv myapp.py MyApp/__main__.py

The script stays the same, and ``python -m MyApp`` starts it, as ``-m`` puts
the current directory, the one of the project, on ``sys.path``.

.. literalinclude:: growing/login/MyApp/__main__.py
    :language: python
    :caption: MyApp/__main__.py

.. code-block:: console

    $ python -m MyApp daemon
    Web application available at http://127.0.0.1:3000

Simplified tests
~~~~~~~~~~~~~~~~

Full :mod:`Pyjoyment` applications are a little easier to test, so
``t/login.py`` can be simplified.

.. literalinclude:: growing/login/t/login.py
    :language: python
    :caption: t/login.py

And our final directory structure should be looking like this.

.. mermaid::

    treeView-beta
        myapp
            MyApp
                __init__.py
                __main__.py
                Controller
                    Login.py
                Model
                    Users.py
            t
                login.py
            templates
                layouts
                    default.html.ep
                login
                    index.html.ep
                    protected.html.ep

Test-driven development takes a little getting used to, but can be a very
powerful tool.

More
----

You can continue with :doc:`index` now or take a look at the `Mojolicious
wiki <https://github.com/mojolicious/mojo/wiki>`_, which contains a lot more
documentation and examples by many different authors.

Ported from `Mojolicious::Guides::Growing
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Guides/Growing.pod>`_
of Mojolicious 9.49.
