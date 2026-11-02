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

A real-time web framework for the Python programming language, ported from
[Mojolicious](https://mojolicious.org), the real-time web framework for Perl.
Pyjoyment keeps the API of Mojolicious with Python names, so its documentation
and experience carry over.

The `Pyjo` package is the web development toolkit, ported from the `Mojo`
modules, which can be used for all kinds of applications independently of the
web framework:

- HTTP and WebSocket client and server.
- Non-blocking I/O web server, which also speaks FastCGI, to a web server in
  front of it and to an application behind it, as PHP on php-fpm, and runs as
  an ASGI, WSGI or CGI application, or as an event function of AWS Lambda.
- HTML/XML parser with CSS selector support.
- JSON with JSON Pointers and JSON Schema, from type hints and validated,
  YAML and TOML, all loaded and dumped.
- JSON-RPC 2.0, its server and its client, over HTTP or any other transport.
- Command line options with `Pyjo.GetOpt`, in the way of Getopt::Long,
  argparse and Cobra, also from environment variables.
- Python-ish templates and template strings, with automatic escaping.
- Containers for URLs, paths, query strings, headers, cookies and HTTP
  messages.
- Event emitter, event loop with TCP, UDP and UNIX domain sockets and child
  processes, logger and utility functions.
- Test scripts which print the [Test Anything Protocol](https://testanything.org/)
  (TAP), with `Pyjo.Test`, inspired by Perl's `Test::More`, and a test
  harness, `Pyjo.Prove`, inspired by Perl's `prove`.

The `Pyjoyment` package is the web framework itself: routes, controllers,
renderer, plugins, `Pyjoyment.Lite` and the command line interface. It
renders JSON, YAML and TOML, and reads its configuration from Python, JSON,
YAML and TOML files.

It mounts the applications of other frameworks under a path or a host, next to
its own routes: WSGI applications, as those of Flask, and ASGI applications, as
those of Starlette and the servers of the MCP SDK, in the same process and on
the same server, whose responses stream at the pace of the client, with their
WebSockets, FastCGI applications, as PHP on php-fpm, which it connects to, CGI
programs, which it runs, as a web server does, with one script for every path
or the scripts of a directory, and event functions of AWS Lambda, which it runs
in a process of their own, as Lambda does.

Both are cloud native: `generate dockerfile` writes the image of an
application, whose server stops gracefully on the `TERM` of its container
and listens on the port of `PORT`, as Knative, Cloud Run, Render, Koyeb and
Heroku set it, and an application runs as an event function of AWS Lambda
too.

Pyjoyment requires Python 3.12 or newer and runs on PyPy on a best-effort
basis. It needs nothing besides the Python standard library.

## Status

Pyjoyment was written against Mojolicious 6 and is being revived as a port of
Mojolicious 9 to Python 3.12 and newer, with `asyncio` as its event loop.
The toolkit, the `Pyjo` package, is ported: URLs, DOM and CSS selectors,
JSON, templates, HTTP messages and cookies, the event loop with promises, the
user agent, and the servers, on their own, preforking, prethreading, with hot
deployment or reloading, and through FastCGI, ASGI, WSGI, CGI and AWS Lambda. So is the web framework, the
`Pyjoyment` package: routes, controllers, the renderer with templates and
template strings, plugins, `Pyjoyment.Lite` and the commands. The tests of
Mojolicious are ported with them, and a ported module names the Mojolicious
version it was ported from in its documentation.

Pyjoyment runs on Linux, macOS and Windows. On Windows, Python has no
`os.fork` and no UNIX domain sockets, so `Pyjo.Server.Prefork`,
`Pyjo.Server.Hot`, `Pyjo.Server.Reload` and `Pyjo.IOLoop.Subprocess` do not
run there, and `Pyjo.Server.Prethread` runs the workers in threads instead.
The event loop watches up to 512 sockets there, with the `select` of Windows,
and a server stops with Ctrl-C, gracefully, or with Ctrl-Break, immediately.

The progress is tracked in [GitHub Issues](https://github.com/pyjoyment/Pyjoyment/issues).

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

## Quick start

These three lines are a whole web application.

```python
from Pyjoyment.Lite import *


get('/', {'text': 'I ♥ Pyjoyment!'})

app.start()
```

To run the example with the built-in development web server, just put the
code into a file and start it with `pyjo-reload`.

```console
$ pyjo-reload hello.py
Web application available at http://127.0.0.1:3000
```

Test it with any HTTP client you prefer.

```console
$ curl http://127.0.0.1:3000/
I ♥ Pyjoyment!
```

## Duct tape for the HTML5 web

Use all the latest Python and HTML features in beautiful single file
prototypes like this one, and grow them easily into well-structured
Model-View-Controller web applications with `pyjo generate app`.

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

The templates of a script of `Pyjoyment.Lite` are in its docstring, after a
line `__DATA__`, and the website is requested without blocking, as the
WebSocket service runs in the event loop.

## Servers

`Pyjo.HelloWorld` is the application that a server runs when it is given
none, and it answers every request with `Your Pyjo is working!`. It runs
natively on the web server of Pyjoyment:

```python
import Pyjo.HelloWorld
import Pyjo.Server.Daemon


Pyjo.Server.Daemon.new(app=Pyjo.HelloWorld.new(), listen=['http://*:3000']).run()
```

on [uvicorn](https://www.uvicorn.org/), an ASGI server
(`pip install uvicorn`):

```python
import Pyjo.HelloWorld
import Pyjo.Server.ASGI

import uvicorn


app = Pyjo.Server.ASGI.new(app=Pyjo.HelloWorld.new()).to_asgi_app()

uvicorn.run(app, port=3000)
```

or on [Werkzeug](https://werkzeug.palletsprojects.com/), a WSGI server
(`pip install werkzeug`):

```python
import Pyjo.HelloWorld
import Pyjo.Server.WSGI

from werkzeug.serving import run_simple


app = Pyjo.Server.WSGI.new(app=Pyjo.HelloWorld.new()).to_wsgi_app()

run_simple('localhost', 3000, app)
```

and answers on port 3000:

```sh
curl http://localhost:3000/
```

On a platform that tells the server the port to listen on with the `PORT`
environment variable, as [Knative](https://knative.dev/),
[Cloud Run](https://cloud.google.com/run), [Render](https://render.com/),
[Koyeb](https://www.koyeb.com/) or [Heroku](https://www.heroku.com/), the
web server of Pyjoyment listens on that port, and `generate dockerfile`
writes the `Dockerfile` of the image of an application, with the port that
the image exposes:

```sh
./myapp.py generate dockerfile --port 8080
```

On [AWS Lambda](https://aws.amazon.com/lambda/), it is an event function,
whose handler `hello_world_lambda.handler` answers the events of API
Gateway, Function URLs and Application Load Balancers:

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

## Distributions

Pyjoyment needs nothing besides the Python standard library, so what needs
another library is a distribution of its own, which adds a module to a
namespace of Pyjoyment, as `Pyjo.Reactor` for a reactor or `Pyjoyment.Plugin`
for a plugin. They are installed from their Git repositories until they are
on PyPI.

- [Pyjo.Reactor.Twisted - Low-level event reactor with Twisted support](https://pyjoyment.readthedocs.io/projects/pyjo-reactor-twisted/en/latest/)

## Documentation

The documentation is on [Read the Docs](https://pyjoyment.readthedocs.io/).

## Examples

### Web scraping

```python
import Pyjo.UserAgent

from Pyjo.String.Unicode import u


# Extract named character references from HTML spec
tx = Pyjo.UserAgent.new().get('https://html.spec.whatwg.org')
for n in tx.res.dom('#named-character-references-table tbody > tr').each():
    u(n.at('td > code').text + ' ' + n.children('td')[1].text).trim().say()
```

### URL manipulation

```python
import Pyjo.URL


# 'ssh+git://git@github.com/pyjoyment/Pyjoyment.git'
url = Pyjo.URL.new('https://github.com/pyjoyment/Pyjoyment')
print(url.set(scheme='ssh+git', userinfo='git', path=f'{url.path}.git').to_unsafe_str())

# 'https://pypi.org/search/?q=Pyjoyment&o=&c=Programming+Language+%3A%3A+Python'
url = Pyjo.URL.new('https://pypi.org/search/')
print(url.set(query=[('q', 'Pyjoyment'), ('o', ''), ('c', 'Programming Language :: Python')]))
```

## Copyright and license

Copyright (C) 2014-2026, Piotr Roszatycki.

Based on Mojolicious: Copyright (C) 2008-2025, Sebastian Riedel and others.

This program is free software, you can redistribute it and/or modify it under
the terms of the Artistic License version 2.0.

The pages of errors bundle [Bootstrap](https://getbootstrap.com), with
Popper, under the MIT License, and [highlight.js](https://highlightjs.org)
under the BSD 3-Clause License, whose texts are next to them in
`Pyjoyment/resources/public/pyjo`.
