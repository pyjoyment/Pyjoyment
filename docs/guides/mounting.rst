Mounting
========

Mounting applications of other frameworks.

This document describes how :mod:`Pyjoyment.Plugin.Mount` runs the
applications of other frameworks next to the routes of an application of
:mod:`Pyjoyment`, in the same process and on the same server: ``WSGI`` and
``ASGI`` applications of Python frameworks, ``FastCGI`` applications, as PHP
on php-fpm, ``CGI`` programs and event functions of AWS Lambda. A whole
application of :mod:`Pyjoyment` is mounted as :doc:`routing` describes it.

Python frameworks
-----------------

A ``WSGI`` application, as one of Flask, runs with :mod:`Pyjo.App.WSGI`, and
an ``ASGI`` application, as one of Starlette, whose ``__call__`` is a
coroutine function, with :mod:`Pyjo.App.ASGI`. The application is the object
itself, or the name of its module and its attribute, as the ``WSGI`` and
``ASGI`` servers take it.

.. literalinclude:: mounting/myapp.py
    :language: python
    :caption: myapp.py

.. literalinclude:: mounting/legacy.py
    :language: python
    :caption: legacy.py

.. literalinclude:: mounting/api.py
    :language: python
    :caption: api.py

The path that an application is mounted under is its ``SCRIPT_NAME`` of
``WSGI``, or its ``root_path`` of ``ASGI``, with which its ``path`` begins, so
the URLs that the application builds, as with ``url_for`` of Flask or
Starlette, have the prefix of the mount.

WSGI
~~~~

A ``WSGI`` application blocks, and it runs in the event loop, which waits for
it as for any other blocking operation, and which it sees as not running, so
that a library that refuses to block in a running loop of :mod:`asyncio`, as
Django, runs, as :func:`Pyjo.IOLoop.blocking` does for other blocking code.
The pre-forking and the pre-threading servers run it in their workers at the
same time, best with few connections for each worker.

.. code-block:: sh

    $ python myapp.py prefork -w 8 -c 1

:doc:`django` serves a project of Django this way, and :doc:`gunicorn`
translates the options of gunicorn.

ASGI
~~~~

An ``ASGI`` application runs as a coroutine of the event loop: with
:mod:`Pyjo.Reactor.Asyncio`, the default reactor, a task of :mod:`asyncio`,
which can await anything of :mod:`asyncio`, and whose responses stream at the
pace of the client, as the server-sent events of ``api.py`` do. Its
WebSockets are WebSockets of the server of :mod:`Pyjoyment`, as the echo of
``api.py``, whose handshake waits for the application to accept it. A reactor
without :mod:`asyncio`, as :mod:`Pyjo.Reactor.Poll`, runs only an application
that awaits nothing but ``receive`` and ``send``.

Lifespan
~~~~~~~~

The lifespan of an ``ASGI`` application starts with its first request in
each process, which waits for its startup, and gets a copy of its state, and
it shuts down once the server has stopped gracefully, as the hook
``after_server_stop`` of :mod:`Pyjoyment` comes then, so that what the
application has started, as a pool of connections, outlives the requests.

Pings
~~~~~

The servers of :mod:`Pyjoyment` close a connection that has been inactive for
their inactivity timeout, 30 seconds by default, as a WebSocket without
messages, so the WebSockets of an ``ASGI`` application are pinged every 20
seconds, as an ``ASGI`` server pings them, which
:attr:`~Pyjo.App.ASGI.Pyjo_App_ASGI.ping_interval` changes. A WebSocket of
:mod:`Pyjoyment` is pinged with
:meth:`~Pyjo.Transaction.WebSocket.Pyjo_Transaction_WebSocket.heartbeat`.

.. code-block:: python

    import Pyjo.App.ASGI

    import api

    # Pings every 60 seconds
    plugin('Mount', {'/api': Pyjo.App.ASGI.new(app=api.app, ping_interval=60)})


    # A WebSocket of Pyjoyment pinged every 20 seconds
    @websocket('/echo')
    def echo(c):
        c.tx.heartbeat()
        c.on('message', lambda c, msg: c.send(f'echo: {msg}'))

MCP servers
~~~~~~~~~~~

A server of the MCP SDK, ``MCPServer`` of the package ``mcp``, is an ``ASGI``
application of Starlette with its transport of Streamable HTTP, whose lifespan
runs the manager of its sessions, so that the tools of an agent of AI run next
to the routes of the application, on the same server. Its path is ``/`` under
the mount, so that a client connects to the URL of the mount with a slash at
the end, as ``http://localhost:3000/mcp/``, which Starlette would otherwise
redirect to on each request.

.. literalinclude:: ../../examples/mount/mount_mcp.py
    :language: python
    :caption: mount_mcp.py

The sessions are kept by the process that has started them, so with the
workers of the pre-forking server the server runs without them, with
``stateless_http=True``, as with any server that has more than one process.
The manager of the sessions runs once, in one event loop, so the server does
not run in the threads of the pre-threading server, whose lifespan fails in
the second one.

.. code-block:: python

    plugin('Mount', {'/mcp': mcp.streamable_http_app(streamable_http_path='/', stateless_http=True)})

.. code-block:: sh

    $ python mount_mcp.py prefork -w 4

Paths
-----

The path of a mount is a pattern of a route, which matches the beginning of
the path of a request, as in Mojolicious, so that ``/legacy`` matches
``/legacy.css`` and ``/legacyx`` too, which an application of another
framework answers with ``404 Not Found``, as its ``SCRIPT_NAME`` or
``root_path`` can only end with a slash. A regular expression matches the
whole path instead, as the ones of PromQL do: its group ``path`` is the rest of
the path for the application, and its other named groups are captures.
:func:`Pyjo.q` makes one shorter than :func:`re.compile` does.

.. code-block:: python

    from Pyjo import q
    from Pyjoyment.Lite import *

    # Only /legacy and the paths under it
    plugin('Mount', {q(r'/legacy(?P<path>/.*)?'): 'legacy:app'})

    # The API of each user, whose name is a capture
    plugin('Mount', {q(r'/(?P<user>\w+)/api(?P<path>/.*)?'): 'api:app'})

    # Only one path
    plugin('Mount', {q(r'/status\.json'): 'api:app'})

Static files
------------

The static files of :mod:`Pyjoyment.Static` are served before the routes, so
an application mounted on ``/`` can have its static files served by
Pyjoyment, as the output of ``collectstatic`` of Django, in the place of
whitenoise. ``STATIC_URL`` of ``/static/`` maps onto the directory ``static``
of a directory of :attr:`~Pyjoyment.Static.Pyjoyment_Static.paths`, so the
path is the parent of ``STATIC_ROOT``, which can also have the files of ``/``,
as ``favicon.ico`` and ``robots.txt``, which whitenoise serves from
``WHITENOISE_ROOT``.
:attr:`~Pyjoyment.Static.Pyjoyment_Static.prefix` serves a ``STATIC_ROOT``
of another name, but all the static files of Pyjoyment are then under it.

Pyjoyment serves its own ``/favicon.ico`` and the images of ``/pyjo/``, which
its exception and not found pages use, from
:attr:`~Pyjoyment.Static.Pyjoyment_Static.extra`, after the files of
:attr:`~Pyjoyment.Static.Pyjoyment_Static.paths`, so a ``favicon.ico`` there
is served in its place. An application that serves its ``/favicon.ico`` from
a route, or has none, gets the requests of it without the one of Pyjoyment,
which ``del app.static.extra['favicon.ico']`` removes, and
``app.static.extra = {}`` leaves out the images too.

The names of ``ManifestStaticFilesStorage`` of Django, as
``site.2fcb528ecde1.css``, or of a bundler, have a hash of their content and
never change, so :attr:`~Pyjoyment.Static.Pyjoyment_Static.immutable` lets
browsers keep them for a year, and
:attr:`~Pyjoyment.Static.Pyjoyment_Static.cache_control` makes them
revalidate the other files after a while.

.. code-block:: python

    import re

    from pathlib import Path
    from Pyjoyment.Lite import *

    # STATIC_ROOT = BASE_DIR / 'public' / 'static', for STATIC_URL = '/static/', and favicon.ico and robots.txt in public
    BASE_DIR = Path(__file__).resolve().parent
    app.static.paths = [str(BASE_DIR / 'public')]

    # The hashed names of ManifestStaticFilesStorage never change, the other files are revalidated after a minute
    app.static.immutable = re.compile(r'^static/.+\.[0-9a-f]{12}\.[^/.]+$')
    app.static.cache_control = 'public, max-age=60'

    # The project of Django
    plugin('Mount', {'/': 'legacy:app'})

``CompressedManifestStaticFilesStorage`` of whitenoise writes the ``.gz`` and
``.br`` variants of the files next to them, which
:mod:`Pyjoyment.Static` serves too, as :doc:`rendering` says of
precompressed static files.

FastCGI
-------

A ``FastCGI`` application, as PHP on php-fpm, runs in a process of its own,
which :mod:`Pyjo.App.FastCGI` connects to for each request, through the
TCP/IP socket of ``fcgi://`` or the UNIX domain socket of ``fcgi+unix://``,
the location that is mounted. Its query tells which script answers a path,
without rules of rewriting:

* ``script`` is the one script for every path, as the one entry of an
  application that takes every path, as mod_rewrite sends them all to
  ``index.php``;
* ``document_root`` is the directory of the scripts, as a web server runs
  them: the path up to its first part that ends with ``.php``, or with one of
  the extensions of ``script_extensions``, names the script, and a path that
  ends with a slash names ``index.php``, ``index`` with the first of them;
* both together send every path that names no script of the directory to the
  one script, as ``try_files`` of nginx does for WordPress;
* ``static`` replies with the files of the directory for the paths that name
  them, as the stylesheets and the images of WordPress, before the one
  script, for an application on the same file system as Pyjoyment;
* ``sendfile`` lets the application reply with a file of its directories by
  the header ``X-Sendfile``, as private files, also more than one, repeated
  in the query, and the attribute of :mod:`Pyjo.App.FastCGI` takes regular
  expressions of the whole path of the file too.

The paths are the ones that php-fpm sees, which may be in another container,
so Pyjoyment does not look for the files.

The static files of :mod:`Pyjoyment.Static`, as the directory ``public``
next to the application, are served before the routes, so the scripts of a
``document_root`` or a ``script`` in them would be served as files, with
their source, as ``public/index.php`` of Laravel or Symfony with the
configuration of its database. The server does not start then, for the
paths that are on the file system of Pyjoyment, unless ``public_source``
says that it is on purpose. The scripts go to another directory, as ``www``
next to the application, whose files ``static`` serves, and ``public`` keeps
the files of Pyjoyment.

.. code-block:: python

    # PHP of www next to the script, with its files
    www = curfile().sibling('www').to_str()
    plugin('Mount', {'/': Pyjo.App.FastCGI.new(url='fcgi://127.0.0.1:9000', document_root=www, static=True)})

.. code-block:: python

    # Every path to the one entry of the application
    plugin('Mount', {'/app': 'fcgi://127.0.0.1:9000?script=/srv/app/public/index.php'})

    # The scripts of a directory
    plugin('Mount', {'/php': 'fcgi+unix://%2Frun%2Fphp%2Fphp-fpm.sock?document_root=/var/www/php'})

    # WordPress: its scripts, its files, and its index.php for every other path
    plugin('Mount', {'/blog': 'fcgi://127.0.0.1:9000?document_root=/var/www/wordpress&script=index.php&static=1'})

The query also takes ``inactivity_timeout`` and ``connect_timeout``, in
seconds, for an application that answers slowly, which the client waits for
without the inactivity timeout of the server until the response starts, and
``max_connections``, the number of idle connections that are kept for the
next requests, as ``fastcgi_keep_conn`` of nginx keeps them, where php-fpm
keeps a worker of its ``pm.max_children`` for each of them, also while it is
idle. The attributes of :mod:`Pyjo.App.FastCGI` take the same, and more, as
parameters of its own for the environment of each request.

CGI
---

A ``CGI`` program runs in a process of its own for each request, which
:mod:`Pyjo.App.CGI` starts, mounted as an object of it, as a string is the
path of a script of :mod:`Pyjoyment`. Its attributes tell which program
answers a path, as for ``FastCGI``:

* ``script`` is the one program for every path;
* ``document_root`` is the directory of the programs, as cgi-bin: the path up
  to its first part that is a file of the directory names the program;
* ``command`` runs the scripts with an interpreter, as php-cgi, and
  ``script_extensions`` tells them from the other files, which are not run,
  and which ``static`` replies with.

The programs are not in the static files of the application, as for
``FastCGI``, unless ``public_source`` says that it is on purpose. A program
whose name starts with ``nph-`` writes the start line of its response, as ``nph`` tells of the others. The event loop reads the pipes of
the process, which it can on POSIX systems, not on Windows.

.. code-block:: python

    import Pyjo.App.CGI

    # The programs of cgi-bin
    plugin('Mount', {'/cgi-bin': Pyjo.App.CGI.new(document_root='/usr/lib/cgi-bin')})

    # PHP on php-cgi, with its files
    php = Pyjo.App.CGI.new(command=['php-cgi'], document_root='/var/www/php', script_extensions=['.php'], static=True)
    plugin('Mount', {'/php': php})

AWS Lambda
----------

An event function of AWS Lambda runs in a process of its own, which
:mod:`Pyjo.App.Lambda` starts on the first request and keeps for the next
ones, which it gets one after another through the Runtime API of Lambda, as
an execution environment of Lambda does, mounted as an object of it. A handler
of Python, ``module.function`` in the directory of ``task_root``, runs with the
runtime client of :mod:`Pyjo.Server.Lambda`, also one of another framework
that runs an event loop of its own, as Mangum, and ``command`` runs a function
of another runtime. The request is an event of the payload format of
``payload``, ``2.0`` of Function URLs and HTTP APIs by default, ``1.0`` of
REST APIs or ``alb``, and the path of the mount is its stage, so that the same
function runs here, live and in the tests of :mod:`Pyjo.Test.Pyjo`, as on AWS.

.. code-block:: python

    import Pyjo.App.Lambda

    # The handler "handler" of myfunction.py of the directory of the function
    plugin('Mount', {'/function': Pyjo.App.Lambda.new(function='myfunction.handler', task_root='functions')})

    # Another runtime, with the events of a REST API
    plugin('Mount', {'/node': Pyjo.App.Lambda.new(command=['node', 'runtime.js'], payload='1.0')})

More
----

The page of :doc:`/examples` has PHP on php-fpm with the pool of php-fpm that
runs it, PHP on php-cgi, a program of Python in cgi-bin, and event functions of
AWS Lambda, also Starlette on Mangum, and an application of Pyjoyment on
:mod:`Pyjo.Server.Lambda` in the same file.

You can continue with :doc:`index` now.
