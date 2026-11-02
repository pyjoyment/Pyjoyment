---
name: lite
description: Build a web application with Pyjoyment.Lite, the single-file form of Pyjoyment, ported from Mojolicious::Lite. Use for its routes and placeholders, actions, rendering of text, JSON and templates, helpers, hooks, sessions, under and groups, WebSockets, Server-Sent Events, and the commands that run the script.
---

# Pyjoyment.Lite

A script of `Pyjoyment.Lite` is a whole application: `from Pyjoyment.Lite import *`
gives it the functions of the routes and `app`, each route is a decorator of
its action, and `app.start()` as the last line runs the command of its
arguments. An action gets the controller `c` and generates the response with
its methods; what it returns is not the response.

## Routes and responses

```python
from Pyjoyment.Lite import *


@get('/')
def index(c):
    c.render(text='Hello World!')


# /hello and /hello/Sara, as a placeholder with a default is optional
@get('/hello/:name', {'name': 'World'})
def hello(c):
    c.render(json={'hello': c.param('name')})


# /users/23 but not /users/joe, as <id:num> takes digits only, in the route named "user"
@get('/users/<id:num>', 'user')
def user(c):
    c.render(json={'id': int(c.param('id'))})


# /files/a/b.txt, as a wildcard takes the slashes and the dots too
@get('/files/*file')
def files(c):
    c.render(text=c.param('file'))


# /report.json and /report.txt, with the format of the extension
@get('/report', format=['json', 'txt'])
def report(c):
    c.respond_to(json={'json': {'total': 1}}, txt={'text': 'total: 1'})


@post('/users')
def create(c):
    c.render(json=c.req.json(), status=201)


@get('/old')
def old(c):
    c.redirect_to('user', id=23)


# Each response, after its action
@hook('after_dispatch')
def powered_by(c):
    c.res.headers.header('X-Powered-By', 'Pyjoyment')


app.start()
```

- `get`, `post`, `put`, `patch`, `delete` (`del_`), `options`, `any` (all
  methods, or a list as `any(['GET', 'POST'], '/x')`) and `websocket`.
- `:name` takes up to the next `/` or `.`, `<name>` is the same, `#name`
  takes dots too, `*name` takes anything; `<name:num>` is a type, and a
  constraint restricts a placeholder to values, as `get('/:lang', lang=['en', 'pl'])`.
- The values of the placeholders, the query and the form are in `c.param()`,
  the placeholders also in the stash, `c.stash('name')`.
- `c.render(text=...)`, `json=...`, `data=b'...'` for bytes, a template by
  its name, with `status=...`; `c.reply.not_found()`, `c.redirect_to(...)`,
  `c.url_for(...)`; the request is `c.req`, the response `c.res`.
- A route is named after its pattern, as `users` for `/users`, unless it is
  given a name, as the string after the pattern and its defaults.

## Templates, layouts and helpers

```python
"""
__DATA__

@@ index.html.ep
% title('Welcome')
% layout('default')
<p>Hello <%= name %>, <%= greeting() %>!</p>

@@ layouts/default.html.ep
<!DOCTYPE html>
<html>
  <head><title><%= c.title() %></title></head>
  <body><%= content() %></body>
</html>
"""

from Pyjoyment.Lite import *


# A helper is a method of the controller and a function of the templates
@helper('greeting')
def greeting(c):
    return 'welcome back' if c.session('user') else 'welcome'


@get('/')
def index(c):
    c.render('index', name=c.param('name') or 'stranger')


app.start()
```

- The templates of a script are in its docstring after a line `__DATA__`,
  each after `@@ name.format.handler`, or in `templates/` next to it, as
  `templates/index.html.ep`; static files are in `public/`.
- A value of the stash is a variable of the template, so it hides a helper of
  the same name: the layout calls the helper `title` as `c.title()`.

## Sessions, under and groups

```python
from Pyjoyment.Lite import *


# The secret that signs the cookie of the session
app.secrets = ['Change this secret']


@post('/login')
def login(c):
    if c.param('password') != 'secret':
        return c.render(text='Wrong password', status=403)
    c.session({'user': c.param('user')})
    c.flash(message='Logged in')
    c.redirect_to('/admin/dashboard')


@get('/logout')
def logout(c):
    c.session(expires=1)
    c.redirect_to('/')


# The routes of the group after under, only for a user who logged in
with group():

    @under('/admin')
    def admin(c):
        if c.session('user'):
            return True
        c.render(text='Log in first', status=401)
        return None

    @get('/dashboard')
    def dashboard(c):
        c.render(text=f'{c.flash("message") or "Hello"}, {c.session("user")}')


app.start()
```

- `@under` lets the routes after it in its group, or in the script, run when
  it returns a true value, and renders the response itself otherwise.
- The session is a signed cookie: `c.session('name')`, `c.session({'name': value})`,
  and `c.flash(...)` for the next request only.

## WebSockets and Server-Sent Events

```python
import Pyjo.Promise

from Pyjoyment.Lite import *


@websocket('/echo')
def echo(c):
    @c.on('message')
    def message(c, msg):
        c.send(f'echo: {msg}')


# Events written as they come, without blocking the other connections
@get('/count')
async def count(c):
    c.write_sse()
    for n in range(1, 4):
        c.write_sse({'text': str(n)})
        await Pyjo.Promise.timer(0.1)
    c.finish()


app.start()
```

- The callback of an event of the controller gets the controller first, as
  `message(c, msg)`; `json` instead of `message` decodes JSON, and
  `c.send({'json': document})` encodes it.
- An action that waits is an `async def`, which awaits promises, as
  `Pyjo.Promise.timer`, instead of blocking the event loop.

## Commands

```sh
uv add --script app.py Pyjoyment                    # from PyPI, for uv run app.py ..., or pip install Pyjoyment
python app.py daemon                                # http://127.0.0.1:3000
python app.py daemon -l 'http://*:8080'             # another port
python app.py prefork -w 4                          # workers in processes of their own
pyjo-reload app.py                                  # restarts when the files change
python app.py routes                                # the routes and their names
python app.py get /users/23                         # a request without a server
uvx --from Pyjoyment pyjo generate lite-app app.py  # a new script
PYJO_MODE=production python app.py daemon
```

## Mistakes

- The routes are tried in their order, and the first one that matches wins,
  so a wildcard route hides the routes after it.
- `@under` covers the routes after it, not the ones before: a group, `with
  group():`, keeps it to the routes of its block.
- `app.secrets` signs the sessions: the default is the name of the script,
  which the log reports as a passphrase to change.
- A script without `app.start()` as its last line does nothing.
- A placeholder cannot have the name of a reserved value of the stash, as
  `path`, `format`, `template`, `text`, `json`, `data` or `status`, which
  raises `Route pattern "/files/*path" contains a reserved stash value`.
- An action that returns `'Hello'` or a dict renders nothing: Pyjoyment
  reports it, `Action returned a str, which is not a response`.
- `print` in an action goes to the standard output, which a pipe, as the one
  of a container, buffers in blocks, without the time and the request:
  `c.log().info(...)` writes to the standard error at once, with the request
  id, as JSON with `PYJO_LOG_FORMAT=json`, and `app.log` outside a request.

## Documentation

- Tutorial: https://pyjoyment.readthedocs.io/en/latest/guides/tutorial.html
- Routing: https://pyjoyment.readthedocs.io/en/latest/guides/routing.html
- Rendering: https://pyjoyment.readthedocs.io/en/latest/guides/rendering.html
- Pyjoyment.Lite: https://pyjoyment.readthedocs.io/en/latest/api/Pyjoyment_Lite.html
