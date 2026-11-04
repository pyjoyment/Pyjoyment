Intro
=====

Pyjoyment is one environment for the whole life of a Python service: the
toolkit it is made of, the framework that puts its parts together with the
applications of other frameworks, the servers that run them, the files that
deploy them, and the clients that connect them to the services around them.

Zero dependencies
-----------------

Pyjoyment has no runtime dependencies. The HTTP and WebSocket server and
client, the event loop, the parsers of HTML, JSON, YAML, TOML and INI,
JSON Schema, the templates and the test harness are all in its package, on
top of the Python standard library. An application that installs Pyjoyment
adds one package to its supply chain, and nothing that the package would
pull in after it. Each release comes with the attestations of its build and an SBOM.

Next to other frameworks
------------------------

Pyjoyment does not compete with Flask, Django or FastAPI: it complements
them. It mounts their applications next to its own routes, on the same
server, glues them to other services, and runs and deploys them together.

Foundation
----------

``Pyjo`` is the toolkit, which every other part is made of, and which works on
its own, without the framework:

* HTTP and WebSocket client and server, with TLS.
* Event loop with promises and ``async``/``await``, with TCP, UDP and UNIX
  domain sockets, timers and child processes.
* HTML/XML parser with CSS selectors.
* JSON with JSON Pointers and JSON Schema, from type hints and validated,
  YAML, TOML and INI, all loaded and dumped.
* JSON-RPC 2.0, its server and its client, over HTTP or any other transport.
* Templates and template strings, with automatic escaping.
* Containers for URLs, paths, query strings, headers, cookies and HTTP
  messages.
* Collections and lazy iterators, whose chains run with ``for`` and ``async for``
  alike.
* Command line options, event emitter, logger and utility functions.
* Test library and test harness.

A script uses the toolkit without a server: the user agent requests the HTML
specification, and the CSS selectors of its DOM pick the rows of the table of
the named character references, whose names and code points the script
prints, as ``Aacute; U+000C1``.

The processing is concurrent. The request blocks here, as a script expects,
and the same request is non-blocking with ``get_p``, whose promise is awaited
or chained, so that a script or an application runs many of them at once in
its event loop and processes each response as it comes. The DOM is searched
with ``iterate``, a lazy chain, which passes the elements on one by one, so that
the first row is printed before the last one is picked:

    .. include:: ../examples/ua/entities.py
       :code: python

Event loop
~~~~~~~~~~

The event loop of Pyjoyment is the one of asyncio by default, so the
coroutines and the tasks of the libraries of asyncio run in the same loop as
its servers and clients. A reactor is where the event loop is replaced, when
an application needs another I/O library: ``Pyjo.Reactor.Poll`` runs without
asyncio, on ``select.poll``, and on ``select.select`` on Windows, with a standard
installation of Python and nothing else. On PyPy, whose JIT compiles it, it
serves requests as fast as the servers of Python whose event loop and HTTP
parser are compiled from C or Rust. A distribution of its own adds another
reactor, as ``Pyjo.Reactor.Twisted``, which ``PYJO_REACTOR`` selects, with no
change of the application.

Tests
~~~~~

``Pyjo.Test`` is a library of assertions and ``Pyjo.Prove`` a harness for test
scripts that print the `Test Anything Protocol <https://testanything.org/>`_
(TAP), modelled on ``Test::More`` and ``prove``, the standard ones of Perl, and
``Pyjo.Test.Pyjo`` tests an application with its requests, without a server.
The framework itself is tested with them.

An application is tested with any test framework, as an assertion of
``Pyjo.Test`` raises ``AssertionError`` once ``raise_failures()`` is called, and
pytest is integrated out of the box: Pyjoyment comes with a plugin of pytest,
which pytest loads where Pyjoyment is installed, and which runs the test
scripts of ``Pyjo.Test`` as tests of pytest, and gives the tests of pytest the
fixture ``t``, the ``Pyjo.Test.Pyjo`` of the application.

Composition
-----------

``Pyjoyment`` is the framework: routes, controllers, the renderer with
templates and template strings, plugins, configuration in Python, JSON, YAML,
TOML and INI files, the commands, and ``Pyjoyment.Lite``, where a single file
is a whole application:

    .. include:: ../examples/pyjoyment/hello.py
       :code: python

The applications of other frameworks are its components. The plugin ``Mount``
puts each under a path or a host, next to the routes of the application, in
the same process and on the same server:

* WSGI applications, as those of Flask and Django;
* ASGI applications, as those of Starlette and FastAPI and the servers of the
  MCP SDK, whose responses stream at the pace of the client, with their
  WebSockets;
* FastCGI applications, as PHP on php-fpm, which it connects to;
* CGI programs, which it runs, as a web server does;
* event functions of AWS Lambda, which it runs in a process of their own, as
  Lambda does;
* other applications of Pyjoyment.

    .. include:: ../examples/mount/compose.py
       :code: python

Both sides of the interface
---------------------------

Pyjoyment works in two roles for each interface that Python and the web
servers have: it hosts the applications of that interface, and it is one of
them, on the server of another.

+------------+----------------------------+----------------------------+
| Interface  | Pyjoyment hosts            | Pyjoyment runs on          |
+============+============================+============================+
| WSGI       | Flask, Django, any WSGI    | any WSGI server, as        |
|            | application                | gunicorn                   |
+------------+----------------------------+----------------------------+
| ASGI       | Starlette, FastAPI, any    | any ASGI server, as        |
|            | ASGI application           | uvicorn                    |
+------------+----------------------------+----------------------------+
| FastCGI    | PHP on php-fpm, any        | a web server in front of   |
|            | FastCGI application        | it, as Caddy               |
+------------+----------------------------+----------------------------+
| CGI        | CGI programs, as Python or | a web server that runs CGI |
|            | PHP scripts                | programs                   |
+------------+----------------------------+----------------------------+
| AWS Lambda | event functions, as the    | Lambda, as an event        |
|            | runtime of Lambda does     | function or a custom       |
|            |                            | runtime                    |
+------------+----------------------------+----------------------------+

``Pyjo.HelloWorld``, the application that answers ``Your Pyjo is working!``, on
uvicorn, as the ASGI application that ``Pyjo.Server.ASGI`` makes of it:

    .. include:: ../examples/servers/hello_world_uvicorn.py
       :code: python

Runtime
-------

The servers of Pyjoyment run an application on its event loop, from one
process to many:

* ``daemon``, the non-blocking HTTP and WebSocket server, with TLS;
* ``prefork``, with worker processes, for Linux, macOS and other systems with
  ``fork``;
* ``prethread``, with worker threads, for Windows, and for the free-threaded
  build of Python anywhere;
* ``pyjo-hot``, with worker processes and deployment without downtime, which
  ``HUP`` starts, for systems with ``fork``;
* ``pyjo-reload``, for development, which restarts the server when a file
  changes.

Each stops gracefully on ``TERM``, finishing the requests in progress, and runs
the hooks of the application around its life, ``before_server_start`` and
``after_server_stop``, in each process and thread. The plugin ``Health`` answers
the probes of liveness, readiness and startup, whose readiness fails as soon as
the server starts to stop.

::

    $ pyjo-reload hello.py
    Web application available at http://127.0.0.1:3000

Deployment
----------

The commands of an application write what deploys it: ::

    ./myapp.py generate pyproject              # the project, for uv
    ./myapp.py generate dockerfile             # the image of a container
    ./myapp.py generate kubernetes             # the manifests of Kubernetes, with Kustomize
    ./myapp.py generate lambda-zip             # the ZIP files of an event function of AWS Lambda

The server listens on the port of ``PORT``, as Knative, Cloud Run, Render,
Koyeb and Heroku set it, and stops gracefully on the ``TERM`` of its container.
On AWS Lambda, an application is an event function, which answers the events
of API Gateway, Function URLs and Application Load Balancers:

    .. include:: ../examples/servers/hello_world_lambda.py
       :code: python

On a custom runtime, as ``provided.al2023``, its ``bootstrap`` runs it with the
runtime client of Pyjoyment:

    .. include:: ../examples/servers/bootstrap
       :code: sh

The public layers of `Pyjoyment-Lambda-Layers
<https://github.com/pyjoyment/Pyjoyment-Lambda-Layers>`_ bring Python, of any
version, and Pyjoyment to such a function, which carries its application only,
as ``generate lambda-zip --function-only`` writes it.

Integration
-----------

An application talks to the services around it from the same event loop that
serves its requests, without blocking it:

* the user agent of HTTP and WebSocket, with promises and ``async``/``await``;
* the client of JSON-RPC 2.0;
* event functions of AWS Lambda, which it runs as the runtime of Lambda does,
  as components of the application;
* the libraries of asyncio, as the asynchronous AWS SDK, whose coroutines run
  in the same event loop.

A page of the application opens a WebSocket to it and sends it a URL, which
the application requests with its user agent, without blocking the other
connections, and sends back the title of the page. The template of the page is
in the docstring of the script, after the line ``_DATA__``:

    .. include:: ../examples/pyjoyment/title.py
       :code: python

Model Context Protocol
~~~~~~~~~~~~~~~~~~~~~~

`Pyjo-MCP <https://pyjoyment.readthedocs.io/projects/pyjo-mcp/en/stable/>`_ is
the `Model Context Protocol <https://modelcontextprotocol.io>`_ made of the
parts of Pyjoyment: its server is a route of an application, whose tools,
prompts and resources are functions with the schemas of their type hints, its
client is the user agent, and ``Pyjo.MCP.Test`` tests a server with the
requests of the client, without starting it. It depends on Pyjoyment and on
nothing else: ::

    pip install Pyjo-MCP

Interoperability
----------------

The tests of Pyjoyment run it with the software on the other side of each
interface:

* **WSGI:** on Gunicorn, uWSGI, Waitress and Werkzeug, and Flask mounted in
  Pyjoyment.
* **ASGI:** on uvicorn and Hypercorn, both on asyncio and on uvloop, on Daphne
  and on Granian, and Starlette and the servers of the MCP SDK mounted in
  Pyjoyment.
* **FastCGI:** behind Caddy, and PHP on php-fpm mounted in Pyjoyment.
* **CGI**, for the legacy applications: on the CGI server of ``http.server``
  and on uWSGI, and the CGI scripts of Python and of PHP on php-cgi mounted in
  Pyjoyment.
* **AWS Lambda:** on the images of Lambda for Python and on the custom runtime
  ``provided.al2023``, with the emulator of the Runtime API, and Starlette on
  Mangum as an event function that Pyjoyment runs.
* **Containers:** the image of ``generate dockerfile`` on Docker, and the
  manifests of ``generate kubernetes`` on a cluster of kind.
* **Event loops:** asyncio, the loop of ``Pyjo.Reactor.Poll``, and Twisted,
  whose reactor passes the whole test suite of Pyjoyment.
* **Libraries:** pytest, with pytest-xdist, the asynchronous AWS SDK on the
  event loop of the server, and the JSON Schemas of pydantic next to those of
  the type hints of ``Pyjo.JSON.Schema``.

Inside the application, the classes of ``Pyjo`` take the types of the Python
standard library and turn back into them, so that the code around Pyjoyment
needs no adapters:

* ``Pyjo.URL`` from and to the ``SplitResult`` of ``urllib.parse``;
* ``Pyjo.Date`` from and to ``datetime``, and ``float(date)`` is the epoch;
* ``Pyjo.File`` is a path-like object, and ``to_path()`` is a ``pathlib.Path``;
* ``Pyjo.Headers`` from and to the ``Message`` of ``email.message``;
* the requests and the responses of HTTP from and to those of
  ``urllib.request`` and ``http.client``;
* the cookies from the ``Morsel`` of ``http.cookies``;
* ``Pyjo.Collection`` is a ``list``, ``Pyjo.String.Unicode`` a ``str``, and a promise
  is awaited in a coroutine of asyncio.

The text files that Pyjoyment reads are Unicode, not only UTF-8: a byte order
mark of UTF-8, UTF-16 or UTF-32, as Windows PowerShell and the editors of
Windows write it, gives the encoding of a configuration file, a template or a
document of JSON or YAML, so that a file made on Windows loads as it is.
