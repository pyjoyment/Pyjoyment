[![Home](https://img.shields.io/badge/%F0%9F%8F%A0-Pyjoyment-02a7a0)](https://github.com/pyjoyment/Pyjoyment)
[![GitHub](https://img.shields.io/github/stars/pyjoyment/Pyjoyment?style=flat&label=GitHub%20%E2%AD%90&logo=github)](https://github.com/pyjoyment/Pyjoyment)
[![Documentation](https://img.shields.io/badge/docs-Read_the_Docs-blue?logo=readthedocs&logoColor=white)](https://pyjoyment.readthedocs.io/en/latest/)
[![DeepWiki](https://img.shields.io/badge/Ask-DeepWiki-blue)](https://deepwiki.com/pyjoyment/Pyjoyment)
[![License](https://img.shields.io/github/license/pyjoyment/Pyjoyment.svg)](https://github.com/pyjoyment/Pyjoyment/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/Pyjoyment?logo=pypi&logoColor=white)](https://pypi.org/project/Pyjoyment/)
[![Tests](https://github.com/pyjoyment/Pyjoyment/actions/workflows/tests.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjoyment/actions/workflows/tests.yaml)
[![Trunk Check](https://github.com/pyjoyment/Pyjoyment/actions/workflows/trunk-check.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjoyment/actions/workflows/trunk-check.yaml)

# Pyjoyment

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-white-4x.png">
    <img src="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-black-4x.png" alt="Pyjoyment" width="322">
  </picture>
</p>

**Glue, run and ship Python applications. Zero dependencies.**

Pyjoyment is one environment for the whole life of a Python service: the
toolkit it is made of, the framework that puts its parts together with the
applications of other frameworks, the servers that run them, the files that
deploy them, and the clients that connect them to the services around them.

## Zero dependencies

Pyjoyment has no runtime dependencies. The HTTP and WebSocket server and
client, the event loop, the parsers of HTML, JSON, YAML and TOML, JSON
Schema, the templates and the test harness are all in its package, on top of
the Python standard library. An application that installs Pyjoyment adds one
package to its supply chain, and nothing that the package would pull in
after it. Each release comes with the attestations of its build and an SBOM.

## Next to other frameworks

Pyjoyment does not compete with Flask, Django or FastAPI: it complements
them. It mounts their applications next to its own routes, on the same
server, glues them to other services, and runs and deploys them together.

## Foundation

`Pyjo` is the toolkit, which every other part is made of, and which works on
its own, without the framework:

- HTTP and WebSocket client and server, with TLS.
- Event loop with promises and `async`/`await`, with TCP, UDP and UNIX
  domain sockets, timers and child processes.
- HTML/XML parser with CSS selectors.
- JSON with JSON Pointers and JSON Schema, from type hints and validated,
  YAML and TOML, all loaded and dumped.
- JSON-RPC 2.0, its server and its client, over HTTP or any other transport.
- Templates and template strings, with automatic escaping.
- Containers for URLs, paths, query strings, headers, cookies and HTTP
  messages.
- Command line options, event emitter, logger and utility functions.
- Test library and test harness.

```python
import Pyjo.UserAgent

from Pyjo.String.Unicode import u


# Extract named character references from HTML spec
tx = Pyjo.UserAgent.new().get('https://html.spec.whatwg.org')
for n in tx.res.dom('#named-character-references-table tbody > tr').each():
    u(n.at('td > code').text + ' ' + n.children('td')[1].text).trim().say()
```

### Event loop

The event loop of Pyjoyment is the one of asyncio by default, so the
coroutines and the tasks of the libraries of asyncio run in the same loop as
its servers and clients. A reactor is where the event loop is replaced, when
an application needs another I/O library: `Pyjo.Reactor.Poll` runs without
asyncio, on `select.poll`, and on `select.select` on Windows, with a standard
installation of Python and nothing else. On PyPy, whose JIT compiles it, it
serves requests as fast as the servers of Python whose event loop and HTTP
parser are compiled from C or Rust. A distribution of its own adds another
reactor, as `Pyjo.Reactor.Twisted`, which `PYJO_REACTOR` selects, with no
change of the application.

### Tests

`Pyjo.Test` is a library of assertions and `Pyjo.Prove` a harness for test
scripts that print the [Test Anything Protocol](https://testanything.org/)
(TAP), modelled on `Test::More` and `prove`, the standard ones of Perl, and
`Pyjo.Test.Pyjo` tests an application with its requests, without a server.
The framework itself is tested with them.

An application is tested with any test framework, as an assertion of
`Pyjo.Test` raises `AssertionError` once `raise_failures()` is called, and
pytest is integrated out of the box: Pyjoyment comes with a plugin of pytest,
which pytest loads where Pyjoyment is installed, and which runs the test
scripts of `Pyjo.Test` as tests of pytest, and gives the tests of pytest the
fixture `t`, the `Pyjo.Test.Pyjo` of the application.

## Composition

`Pyjoyment` is the framework: routes, controllers, the renderer with
templates and template strings, plugins, configuration in Python, JSON, YAML
and TOML files, the commands, and `Pyjoyment.Lite`, where a single file is a
whole application:

```python
from Pyjoyment.Lite import *


get('/', {'text': 'I ♥ Pyjoyment!'})

app.start()
```

The applications of other frameworks are its components. The plugin `Mount`
puts each under a path or a host, next to the routes of the application, in
the same process and on the same server:

- WSGI applications, as those of Flask and Django;
- ASGI applications, as those of Starlette and FastAPI and the servers of the
  MCP SDK, whose responses stream at the pace of the client, with their
  WebSockets;
- FastCGI applications, as PHP on php-fpm, which it connects to;
- CGI programs, which it runs, as a web server does;
- event functions of AWS Lambda, which it runs in a process of their own, as
  Lambda does;
- other applications of Pyjoyment.

```python
import Pyjo.App.Lambda

from Pyjo.File import curfile
from Pyjoyment.Lite import *


# The WSGI application of hello_wsgi.py, the ASGI application of hello_asgi.py and the event function of AWS Lambda of
# hello_lambda.py, next to this script, on one server, next to the routes of this application
plugin('Mount', {'/wsgi': 'hello_wsgi:app'})
plugin('Mount', {'/asgi': 'hello_asgi:app'})
plugin('Mount', {'/lambda': Pyjo.App.Lambda.new(function='hello_lambda.handler', task_root=curfile().dirname())})

get('/', {'text': 'I ♥ Pyjoyment!'})

app.start()
```

## Both sides of the interface

Pyjoyment works in two roles for each interface that Python and the web
servers have: it hosts the applications of that interface, and it is one of
them, on the server of another.

| Interface  | Pyjoyment hosts                                | Pyjoyment runs on                                |
| ---------- | ---------------------------------------------- | ------------------------------------------------ |
| WSGI       | Flask, Django, any WSGI application            | any WSGI server, as gunicorn                     |
| ASGI       | Starlette, FastAPI, any ASGI application       | any ASGI server, as uvicorn                      |
| FastCGI    | PHP on php-fpm, any FastCGI application        | a web server in front of it, as nginx            |
| CGI        | CGI programs, as Python or PHP scripts         | a web server that runs CGI programs              |
| AWS Lambda | event functions, as the runtime of Lambda does | Lambda, as an event function or a custom runtime |

```python
import Pyjo.HelloWorld
import Pyjo.Server.ASGI

import uvicorn


app = Pyjo.Server.ASGI.new(app=Pyjo.HelloWorld.new()).to_asgi_app()

uvicorn.run(app, port=3000)
```

## Runtime

The servers of Pyjoyment run an application on its event loop, from one
process to many:

- `daemon`, the non-blocking HTTP and WebSocket server, with TLS;
- `prefork`, with worker processes;
- `prethread`, with worker threads, also on the free-threaded build of
  Python;
- `pyjo-hot`, with worker processes and deployment without downtime, which
  `HUP` starts;
- `pyjo-reload`, for development, which restarts the server when a file
  changes.

Each stops gracefully on `TERM`, finishing the requests in progress, and runs
the hooks of the application around its life, `before_server_start` and
`after_server_stop`, in each process and thread. The plugin `Health` answers
the probes of liveness, readiness and startup, whose readiness fails as soon as
the server starts to stop.

```console
$ pyjo-reload hello.py
Web application available at http://127.0.0.1:3000
```

## Deployment

The commands of an application write what deploys it:

```sh
./myapp.py generate pyproject              # the project, for uv
./myapp.py generate dockerfile             # the image of a container
./myapp.py generate kubernetes             # the manifests of Kubernetes, with Kustomize
./myapp.py generate lambda-zip             # the ZIP files of an event function of AWS Lambda
```

The server listens on the port of `PORT`, as Knative, Cloud Run, Render,
Koyeb and Heroku set it, and stops gracefully on the `TERM` of its container.
On AWS Lambda, an application is an event function, which answers the events
of API Gateway, Function URLs and Application Load Balancers:

```python
import Pyjo.HelloWorld
import Pyjo.Server.Lambda


# The handler "hello_world_lambda.handler" of an event function of AWS Lambda
handler = Pyjo.Server.Lambda.new(app=Pyjo.HelloWorld.new()).to_lambda_app()
```

On a custom runtime, as `provided.al2023`, its `bootstrap` runs it with the
runtime client of Pyjoyment:

```sh
#!/bin/sh
# The bootstrap of a custom runtime of AWS Lambda, as provided.al2023, which runs the handler of the function, as
# "hello_world_lambda.handler" of _HANDLER, with the runtime client of Pyjoyment
exec python3 -m Pyjo.Server.Lambda
```

## Integration

An application talks to the services around it from the same event loop that
serves its requests, without blocking it:

- the user agent of HTTP and WebSocket, with promises and `async`/`await`;
- the client of JSON-RPC 2.0;
- event functions of AWS Lambda, which it runs as the runtime of Lambda does,
  as components of the application;
- the libraries of asyncio, as the asynchronous AWS SDK, whose coroutines run
  in the same event loop.

```python
"""
__DATA__

@@ index.html.ep
% url = url_for('title')
<script>
  const ws = new WebSocket('<%= url.to_abs() %>');
  ws.onmessage = function (event) { document.body.innerHTML += event.data };
  ws.onopen    = function (event) { ws.send('https://mojolicious.org') };
</script>
"""

from Pyjoyment.Lite import *


# Render template "index.html.ep" from the DATA section
@get('/')
def index(c):
    c.render(template='index')


# WebSocket service used by the template to extract the title from a website
@websocket('/title')
def title(c):
    @c.on('message')
    def message(c, msg):
        c.ua().get_p(msg).then(lambda tx: c.send(tx.result.dom().at('title').text))


app.start()
```

### Model Context Protocol

[Pyjo-MCP](https://pyjoyment.readthedocs.io/projects/pyjo-mcp/en/latest/) is
the [Model Context Protocol](https://modelcontextprotocol.io) made of the
parts of Pyjoyment: its server is a route of an application, whose tools,
prompts and resources are functions with the schemas of their type hints, its
client is the user agent, and `Pyjo.MCP.Test` tests a server with the
requests of the client, without starting it. It depends on Pyjoyment and on
nothing else:

```sh
pip install Pyjo-MCP
```

## Installation

Pyjoyment is installed from [PyPI](https://pypi.org/project/Pyjoyment/):

```sh
pip install Pyjoyment
```

or, in a project managed with [uv](https://docs.astral.sh/uv/):

```sh
uv add Pyjoyment
```

A new project or script comes from its generator, which uv runs without
installing Pyjoyment first:

```sh
uvx --from Pyjoyment pyjo generate app MyApp
uvx --from Pyjoyment pyjo generate lite-app myapp.py
```

The skills for coding agents that write applications with Pyjoyment are a
plugin of [Claude Code](https://code.claude.com/docs/en/plugins), whose
`SKILL.md` files other agents read too:

```text
/plugin install pyjoyment --marketplace pyjoyment/Pyjoyment
```

or from the shell, as the extensions of the editors have no `/plugin`:

```sh
claude plugin install pyjoyment --marketplace pyjoyment/Pyjoyment
```

## Status

Pyjoyment is an evolution of [Mojolicious](https://mojolicious.org), the
real-time web framework for Perl. It keeps the API of Mojolicious with Python
names, so its documentation and experience carry over, and the tests of
Mojolicious, ported with each module, are the specification that the code
follows. A ported module names the Mojolicious version it was ported from in
its documentation.

Pyjoyment requires Python 3.12 or newer and runs on PyPy on a best-effort
basis. It runs on Linux, macOS and Windows. On Windows, Python has no
`os.fork` and no UNIX domain sockets, so `Pyjo.Server.Prefork`,
`Pyjo.Server.Hot`, `Pyjo.Server.Reload` and `Pyjo.IOLoop.Subprocess` do not
run there, and `Pyjo.Server.Prethread` runs the workers in threads instead.
The event loop watches up to 512 sockets there, with the `select` of Windows,
and a server stops with Ctrl-C, gracefully, or with Ctrl-Break, immediately.

## Distributions

What needs another library, or follows a specification that is revised more
often than Pyjoyment is released, is a distribution of its own, which adds a
module to a namespace of Pyjoyment, as `Pyjo.Reactor` for a reactor,
`Pyjoyment.Plugin` for a plugin or `Pyjo` for a protocol.

- [Pyjo.MCP - Model Context Protocol for Pyjoyment](https://pyjoyment.readthedocs.io/projects/pyjo-mcp/en/latest/)
- [Pyjo.Reactor.Twisted - Low-level event reactor with Twisted support](https://pyjoyment.readthedocs.io/projects/pyjo-reactor-twisted/en/latest/)

## Documentation

The documentation is on [Read the Docs](https://pyjoyment.readthedocs.io/).

## Copyright and license

Copyright (C) 2014-2026, Piotr Roszatycki.

Based on Mojolicious: Copyright (C) 2008-2025, Sebastian Riedel and others.

This program is free software, you can redistribute it and/or modify it under
the terms of the Artistic License version 2.0.

The pages of errors bundle [Bootstrap](https://getbootstrap.com), with
Popper, under the MIT License, and [highlight.js](https://highlightjs.org)
under the BSD 3-Clause License, whose texts are next to them in
`Pyjoyment/resources/public/pyjo`.
