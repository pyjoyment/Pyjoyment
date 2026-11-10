---
name: mount
description: Mount other applications in a Pyjoyment application with the plugin Mount, as WSGI applications of Flask or Django, ASGI applications of Starlette or FastAPI, CGI programs, FastCGI applications as PHP on php-fpm, event functions of AWS Lambda, and other applications of Pyjoyment. Use to serve them and their static files next to the routes of Pyjoyment, and to migrate an application of another framework step by step.
---

# Mounting applications

`plugin('Mount', {'/prefix': application})` adds a route that sends the
requests under a prefix to another application, in the same process and the
same event loop: a script or an object of Pyjoyment, a WSGI or an ASGI
application by `'module:attribute'` or as an object, `Pyjo.App.CGI` for CGI
programs, `fcgi://` for FastCGI, and `Pyjo.App.Lambda` for an event function
of AWS Lambda. A route of a mounted application matches the beginning of a
path, as the routes do in their order, so an application mounted on `/` after
the other routes gets what they do not match.

## Migrating an application step by step

```python
# legacy.py
# A WSGI application of another framework, as one of Flask or Django, which is a function of WSGI to Pyjoyment
def app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [f'Legacy at {environ["SCRIPT_NAME"]} for {environ["PATH_INFO"]}'.encode()]
```

```python
# realtime.py
# An ASGI application, as one of Starlette or FastAPI, which needs the reactor of asyncio, the default one
async def app(scope, receive, send):
    if scope['type'] != 'http':
        return
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
    await send({'type': 'http.response.body', 'body': f'ASGI at {scope["root_path"]} for {scope["path"]}'.encode()})
```

```python
#!/usr/bin/env python3
# cgi-bin/hello.py
# A CGI program, executable, which a process of its own runs for each request
import os

print('Content-Type: text/plain')
print()
print(f'CGI at {os.environ["SCRIPT_NAME"]} for {os.environ["PATH_INFO"]}')
```

```python
# app.py
import Pyjo.App.CGI

from Pyjo.File import curfile
from Pyjoyment.Lite import *


# The routes that the new application has already
@get('/new')
def new(c):
    c.render(text='New in Pyjoyment')


plugin('Mount', {'/realtime': 'realtime:app'})
plugin('Mount', {'/cgi-bin': Pyjo.App.CGI.new(document_root=curfile().sibling('cgi-bin').to_str())})

# The static files of the old application, as the output of collectstatic of Django for STATIC_URL /static/, served
# before the routes, with its hashed names cached for a year
app.static.paths.append(curfile().sibling('public').to_str())
app.static.immutable = r'^static/.+\.[0-9a-f]{12}\.[^/.]+$'
app.static.cache_control = 'public, max-age=60'

# Last, the old application, which gets every request that the routes before do not match
plugin('Mount', {'/': 'legacy:app'})

app.start()
```

- `'module:attribute'` is imported from `sys.path`, where the directory of
  the script comes first, so `legacy.py` next to `app.py` is found.
- A WSGI application runs in the event loop, so one that blocks, as Flask
  with a blocking database, blocks the other requests: `prefork` with more
  workers serves it, as gunicorn would.
- An ASGI application runs with `run_coroutine` of the reactor, which only
  the reactor of asyncio has.
- `Pyjo.App.CGI` needs pipes that the event loop watches, which Windows does
  not have, and an executable program, or `command=[...]` that runs it, as
  `command=['php-cgi'], script_extensions=['.php']`.

## Static files of the mounted application

- `Pyjoyment.Static` serves before the routes, so it can serve the static
  files of the mounted application, in the place of whitenoise: the parent of
  `STATIC_ROOT` in `app.static.paths`, so that `/static/` maps onto it, with
  the files of `/`, as `favicon.ico` and `robots.txt`, next to it.
- The `favicon.ico` of `app.static.paths` comes before the one of Pyjoyment in
  `app.static.extra`, which the mounted application on `/` gets otherwise:
  `del app.static.extra['favicon.ico']` for one that serves it from a route
  or has none, and `app.static.extra = {}` without the images of `/pyjo/` of
  the exception pages too.
- `app.static.immutable`, a regular expression of the paths of hashed names,
  gives them `Cache-Control: public, max-age=31536000, immutable`, and
  `app.static.cache_control`, a string or a function of `(c, rel)`, the other
  files; without them, every page view revalidates every file.
- The `.gz` and `.br` variants of `CompressedManifestStaticFilesStorage` are
  served to the clients that take them, as the skill `deploy` says.

## Other applications

```text
plugin('Mount', {'/blog': '/home/sri/blog.py'})                         a script of Pyjoyment.Lite
plugin('Mount', {'/admin': MyAdmin.new()})                              an application object
plugin('Mount', {'/php': 'fcgi://127.0.0.1:9000?document_root=%2Fvar%2Fwww&script=index.php'})
plugin('Mount', {'/function': Pyjo.App.Lambda.new(function='myfunction.handler')})
plugin('Mount', {'example.com': '/home/sri/myapp.py'})                  a host
plugin('Mount', {re.compile(r'/(?P<user>\w+)/blog(?P<path>/.*)?'): flask_app})
```

## Mistakes

- A mounted application on `/` before the other routes takes their requests
  too, as the first route that matches wins: mount it last.
- `/php` matches `/php.css` too, as a route matches the beginning of a path,
  where the mounted application gets `SCRIPT_NAME` or `root_path` up to the
  slash; a regular expression of the whole path, with its group `path`, is
  exact.
- `PYJO_REACTOR=Pyjo.Reactor.Poll` cannot run an ASGI application.
- The `SCRIPT_NAME` of WSGI and the `root_path` of ASGI carry the prefix: an
  application that builds its URLs from them, as Flask with `url_for`, links
  under the prefix.

## Documentation

- Mounting: https://pyjoyment.readthedocs.io/en/stable/guides/mounting.html
- Pyjoyment.Plugin.Mount: https://pyjoyment.readthedocs.io/en/stable/api/Pyjoyment_Plugin_Mount.html
