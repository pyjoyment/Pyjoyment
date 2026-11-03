Guides
======

The Pyjoyment Guide to the Galaxy.

Don't panic!
------------

The :mod:`Pyjoyment` documentation is structured into three parts. The
:ref:`tutorial <guides-tutorial>` everyone starts with, the :ref:`guides
<guides-guides>` that explain all major features in detail, and the
:ref:`API <guides-api>` reference listing all available classes.

Some parts of the documentation only use the :mod:`Pyjoyment.Lite` micro web
framework for examples, but that's merely a convenience for the reader.
Almost all features are exactly the same for full :mod:`Pyjoyment`
applications.

Basics
------

Learning Python
~~~~~~~~~~~~~~~

If you are new to Python, we recommend `the Python tutorial
<https://docs.python.org/3/tutorial/>`_ for an introduction to the language,
which is part of the documentation of Python itself. For more books and
documentation, check out `the beginner's guide of python.org
<https://wiki.python.org/moin/BeginnersGuide>`_.

Learning Web Technologies
~~~~~~~~~~~~~~~~~~~~~~~~~

All web development starts with HTML, CSS and JavaScript, to learn the basics
we recommend the `Mozilla Developer Network
<https://developer.mozilla.org/en-US/docs/Web>`_. And if you want to know more
about how browsers and web servers actually communicate, there's also a very
nice introduction to `HTTP <https://developer.mozilla.org/en-US/docs/Web/HTTP>`_.

Conventions
-----------

Modern Python
~~~~~~~~~~~~~

:mod:`Pyjoyment` uses a modern subset of Python exclusively, Python 3.12 and
newer, and therefore all documentation assumes that the modules an example
uses are imported, even if examples don't specifically mention it.

.. code-block:: python

    import Pyjo.IOLoop
    import Pyjo.UserAgent

Some modules, like :mod:`Pyjoyment.Lite` and :mod:`Pyjo`, will import the
functions of their examples for you with ``from Pyjoyment.Lite import *`` and
``from Pyjo import *``.

Type hints
~~~~~~~~~~

:mod:`Pyjoyment` is annotated with type hints, which pyright checks in strict
mode. They are left out of all examples for clarity, so the code of an
example is the same with or without them.

Variable names
~~~~~~~~~~~~~~

For brevity and clarity, example variables will reflect the type of data the
API uses. For instance, ``data`` or ``chars`` to distinguish whether it is
encoded ``bytes`` or decoded characters in a ``str``, ``boolean`` if the
value just indicates true or false, ``c`` to denote a
:mod:`Pyjoyment.Controller` object, or ``app`` to denote the
:mod:`application <Pyjoyment>` object.

When the return value of a method is the object it was called on, this will
be represented by using the same variable name in the example. This does not
mean the return value needs to be assigned back to it, but indicates that
further methods can be called in a chain, as the :mod:`fluent interfaces
<Pyjo.Base>` of :mod:`Pyjo.Base` do.

.. _guides-tutorial:

Tutorial
--------

:doc:`tutorial`
    A fast and fun way to get started developing web applications with
    :mod:`Pyjoyment`. The tutorial introduces the :mod:`Pyjoyment.Lite` micro
    web framework, which is only a thin wrapper around the full web
    framework. The simplified notation introduced in the tutorial is commonly
    used throughout the guides and is therefore considered a prerequisite,
    you should definitely take a look!

.. _guides-guides:

Guides
------

:doc:`growing`
    Starting a :mod:`Pyjoyment.Lite` prototype from scratch and growing it
    into a well-structured :mod:`Pyjoyment` application.

:doc:`routing`
    Simple and fun introduction to the :mod:`Pyjoyment` router.

:doc:`mounting`
    Running the applications of other frameworks, of Python, PHP, CGI and AWS
    Lambda, next to the routes of a :mod:`Pyjoyment` application.

:doc:`rendering`
    Generating content with the :mod:`Pyjoyment` renderer.

:doc:`testing`
    Powerful yet elegant testing techniques and tools for :mod:`Pyjoyment`
    and other web applications.

:doc:`cookbook`
    Cooking with :mod:`Pyjoyment`, recipes for every taste.

:doc:`contributing`
    Become a part of the ongoing :mod:`Pyjoyment` development.

:doc:`faq`
    Answers to the most frequently asked questions.

.. toctree::
    :hidden:

    tutorial
    growing
    routing
    mounting
    rendering
    testing
    cookbook
    contributing
    faq

Highlights
----------

:mod:`Pyjoyment` and :mod:`Pyjoyment.Lite` are the sum of many parts, built
on top of the :mod:`Pyjo` web development toolkit. Small building blocks
that can be used independently for all kinds of applications, these are the
most prominent ones.

:mod:`Pyjo.UserAgent`
    Full featured non-blocking I/O HTTP and WebSocket user agent.

:mod:`Pyjo.DOM`
    Very fun and minimalistic HTML/XML DOM parser with CSS selector support.

:mod:`Pyjo.JSON`
    Minimalistic JSON implementation that just works.

:mod:`Pyjo.Server.Daemon`
    Full featured, highly portable non-blocking I/O HTTP and WebSocket
    server, with self-restart support through :mod:`Pyjo.Server.Reload`,
    perfect for development and testing.

:mod:`Pyjo.Server.Prefork`
    Full featured, UNIX optimized, preforking non-blocking I/O HTTP and
    WebSocket server with support for zero downtime software upgrades (hot
    deployment) through :mod:`Pyjo.Server.Hot`.

:mod:`Pyjo.Server.Prethread`
    The same server with threads for its worker processes, which run at the
    same time on a free-threaded Python.

:mod:`Pyjo.Server.CGI`, :mod:`Pyjo.Server.WSGI`, :mod:`Pyjo.Server.ASGI`
    Transparent CGI, WSGI and ASGI support out of the box.

:mod:`Pyjo.Server.FastCGI`, :mod:`Pyjo.Server.Lambda`
    FastCGI behind a web server, and the event functions of AWS Lambda.

:mod:`Pyjo.Server.Stdio`
    A protocol on the standard input and output, as the transport stdio of
    MCP or LSP.

:mod:`Pyjo.IOLoop`
    A minimalistic event loop with support for multiple reactor backends,
    on the event loop of :mod:`asyncio` by default.

:mod:`Pyjo.Template`
    Very Python-ish and minimalistic template system.

:mod:`Pyjoyment.Plugin.PyRenderer`
    Templates of the template strings of Python, with auto-escaping and
    without a template language.

:mod:`Pyjo.Test.Pyjo`
    Testing toolkit for web applications.

:mod:`Pyjo`
    Fun one-liners using everything above.

.. Left out from Mojolicious: "FULL-STACK", as Mojo::Pg and Minion have no ports yet

.. _guides-api:

API
---

This is the class hierarchy of the :mod:`Pyjoyment` distribution.

- :mod:`Pyjo`
- :mod:`Pyjo.Base`

  - :mod:`Pyjo.App`

    - :mod:`Pyjo.App.ASGI`
    - :mod:`Pyjo.App.CGI`
    - :mod:`Pyjo.App.FastCGI`
    - :mod:`Pyjo.App.Lambda`
    - :mod:`Pyjo.App.WSGI`
    - :mod:`Pyjo.HelloWorld`
    - :mod:`Pyjoyment`

      - :mod:`Pyjoyment.HelloWorld`
      - :mod:`Pyjoyment.Lite`

  - :mod:`Pyjo.Cache`
  - :mod:`Pyjo.Cookie`

    - :mod:`Pyjo.Cookie.Request`
    - :mod:`Pyjo.Cookie.Response`

  - :mod:`Pyjo.DOM`
  - :mod:`Pyjo.DOM.CSS`
  - :mod:`Pyjo.DOM.HTML`
  - :mod:`Pyjo.Date`
  - :mod:`Pyjo.EventEmitter`

    - :mod:`Pyjo.Asset`

      - :mod:`Pyjo.Asset.File`
      - :mod:`Pyjo.Asset.Memory`

    - :mod:`Pyjo.Content`

      - :mod:`Pyjo.Content.MultiPart`
      - :mod:`Pyjo.Content.Single`

    - :mod:`Pyjo.IOLoop`
    - :mod:`Pyjo.IOLoop.ChildProcess`
    - :mod:`Pyjo.IOLoop.Client`
    - :mod:`Pyjo.IOLoop.Datagram`
    - :mod:`Pyjo.IOLoop.Messages`
    - :mod:`Pyjo.IOLoop.Server`
    - :mod:`Pyjo.IOLoop.Stream`

      - :mod:`Pyjo.IOLoop.Stdio`

    - :mod:`Pyjo.IOLoop.Subprocess`
    - :mod:`Pyjo.IOLoop.TLS`
    - :mod:`Pyjo.JSON.RPC`
    - :mod:`Pyjo.Log`
    - :mod:`Pyjo.Message`

      - :mod:`Pyjo.Message.Request`
      - :mod:`Pyjo.Message.Response`

    - :mod:`Pyjo.Reactor`

      - :mod:`Pyjo.Reactor.Asyncio`
      - :mod:`Pyjo.Reactor.Poll`

    - :mod:`Pyjo.Server`

      - :mod:`Pyjo.Server.ASGI`
      - :mod:`Pyjo.Server.CGI`
      - :mod:`Pyjo.Server.Daemon`

        - :mod:`Pyjo.Server.Prefork`

          - :mod:`Pyjo.Server.Prethread`

      - :mod:`Pyjo.Server.Lambda`
      - :mod:`Pyjo.Server.Stdio`
      - :mod:`Pyjo.Server.WSGI`

    - :mod:`Pyjo.Transaction`

      - :mod:`Pyjo.Transaction.HTTP`
      - :mod:`Pyjo.Transaction.WebSocket`

    - :mod:`Pyjo.UserAgent`
    - :mod:`Pyjoyment.Plugins`

  - :mod:`Pyjo.Exception`
  - :mod:`Pyjo.File`

    - :mod:`Pyjo.Home`

  - :mod:`Pyjo.GetOpt`
  - :mod:`Pyjo.Headers`
  - :mod:`Pyjo.Iterator`
  - :mod:`Pyjo.JSON.Pointer`
  - :mod:`Pyjo.JSON.Schema`
  - :mod:`Pyjo.Parameters`
  - :mod:`Pyjo.Path`
  - :mod:`Pyjo.Promise`
  - :mod:`Pyjo.Server.FastCGI`
  - :mod:`Pyjo.Server.Hot`
  - :mod:`Pyjo.Server.Reload`
  - :mod:`Pyjo.Server.Reload.Backend`

    - :mod:`Pyjo.Server.Reload.Backend.Poll`

  - :mod:`Pyjo.String.Template`
  - :mod:`Pyjo.Template`
  - :mod:`Pyjo.Test.Pyjo`
  - :mod:`Pyjo.URL`
  - :mod:`Pyjo.URL.Template`
  - :mod:`Pyjo.Upload`
  - :mod:`Pyjo.UserAgent.CookieJar`
  - :mod:`Pyjo.UserAgent.Proxy`
  - :mod:`Pyjo.UserAgent.Server`
  - :mod:`Pyjo.UserAgent.Transactor`
  - :mod:`Pyjoyment.Command`

    - :mod:`Pyjoyment.Command.Author.generate.app`
    - :mod:`Pyjoyment.Command.Author.generate.dockerfile`
    - :mod:`Pyjoyment.Command.Author.generate.kubernetes`
    - :mod:`Pyjoyment.Command.Author.generate.lambda_zip`
    - :mod:`Pyjoyment.Command.Author.generate.lite_app`
    - :mod:`Pyjoyment.Command.Author.generate.plugin`
    - :mod:`Pyjoyment.Command.Author.generate.pyproject`
    - :mod:`Pyjoyment.Command.Author.inflate`
    - :mod:`Pyjoyment.Command.asgi`
    - :mod:`Pyjoyment.Command.cgi`
    - :mod:`Pyjoyment.Command.daemon`
    - :mod:`Pyjoyment.Command.eval`
    - :mod:`Pyjoyment.Command.fastcgi`
    - :mod:`Pyjoyment.Command.get`
    - :mod:`Pyjoyment.Command.lambda`
    - :mod:`Pyjoyment.Command.prefork`

      - :mod:`Pyjoyment.Command.prethread`

    - :mod:`Pyjoyment.Command.routes`
    - :mod:`Pyjoyment.Command.stdio`
    - :mod:`Pyjoyment.Command.version`
    - :mod:`Pyjoyment.Command.wsgi`
    - :mod:`Pyjoyment.Commands`

      - :mod:`Pyjoyment.Command.Author.generate`

  - :mod:`Pyjoyment.Controller`
  - :mod:`Pyjoyment.Plugin`

    - :mod:`Pyjoyment.Plugin.Config`

      - :mod:`Pyjoyment.Plugin.JSONConfig`

        - :mod:`Pyjoyment.Plugin.INIConfig`
        - :mod:`Pyjoyment.Plugin.TOMLConfig`
        - :mod:`Pyjoyment.Plugin.YAMLConfig`

    - :mod:`Pyjoyment.Plugin.AllowedHosts`
    - :mod:`Pyjoyment.Plugin.DefaultHelpers`
    - :mod:`Pyjoyment.Plugin.EPLRenderer`

      - :mod:`Pyjoyment.Plugin.EPRenderer`

    - :mod:`Pyjoyment.Plugin.Health`
    - :mod:`Pyjoyment.Plugin.HeaderCondition`
    - :mod:`Pyjoyment.Plugin.Mount`
    - :mod:`Pyjoyment.Plugin.PyRenderer`
    - :mod:`Pyjoyment.Plugin.TagHelpers`

  - :mod:`Pyjoyment.Renderer`
  - :mod:`Pyjoyment.Routes.Match`
  - :mod:`Pyjoyment.Routes.Pattern`
  - :mod:`Pyjoyment.Routes.Route`

    - :mod:`Pyjoyment.Routes`

  - :mod:`Pyjoyment.Sessions`
  - :mod:`Pyjoyment.Static`
  - :mod:`Pyjoyment.Types`
  - :mod:`Pyjoyment.Validator`
  - :mod:`Pyjoyment.Validator.Validation`

- :mod:`Pyjo.Collection`
- :mod:`Pyjo.INI`
- :mod:`Pyjo.JSON`
- :mod:`Pyjo.Loader`
- :mod:`Pyjo.Prove`
- :mod:`Pyjo.SSE`
- :mod:`Pyjo.String.Bytes`
- :mod:`Pyjo.String.Mixin`
- :mod:`Pyjo.String.Unicode`

  - :mod:`Pyjo.String.HTML`

- :mod:`Pyjo.TOML`
- :mod:`Pyjo.Test`
- :mod:`Pyjo.Test.pytest_plugin`
- :mod:`Pyjo.Util`
- :mod:`Pyjo.WebSocket`
- :mod:`Pyjo.YAML`
- :mod:`Pyjoyment.Command.Author`

More
----

A lot more documentation and examples by many different authors can be found
in the `Mojolicious wiki <https://github.com/mojolicious/mojo/wiki>`_, which
Pyjoyment is ported from.

.. Left out from Mojolicious: "SUPPORT", as the forum and the IRC channel are those of Mojolicious

Ported from `Mojolicious::Guides
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Guides.pod>`_
of Mojolicious 9.49.
