---
name: migration
description: Write or port a Python web application to Pyjoyment from Flask, FastAPI, Starlette or Django. Use when code for Pyjoyment looks like one of them, as a view that returns its response, a global request, routes with {id}, Jinja, or requests and time.sleep in a handler, and to map their idioms to the ones of Pyjoyment.
---

# Migration from Flask, FastAPI and Django

Pyjoyment is a port of Mojolicious to Python. Its API follows Mojolicious, not
Flask, so the habits of other frameworks run, but often do something else:

- An action gets the controller `c` and generates the response with its
  methods, as `c.render(...)`. What it returns is not the response.
- The values of the request come from the controller: `c.param('name')` and
  `c.req`. There is no global `request`.
- Everything runs on one event loop. Code that blocks, as `requests` or
  `time.sleep`, stops every connection while it waits.

Pyjoyment comes from PyPI, `uv add Pyjoyment` or `pip install Pyjoyment`,
and needs no other library.

## An application

```python
from Pyjoyment.Lite import *


@get('/')
def index(c):
    c.render(text='Hello World!')


# /users/23?full=1, where <id> or :id is a placeholder and <id:num> takes digits only, in the route "user"
@get('/users/<id:num>', 'user')
def user(c):
    c.render(json={'id': int(c.param('id')), 'full': c.param('full') == '1'})


@post('/users')
def create(c):
    c.render(json=c.req.json(), status=201)


# A route is named after its pattern, as "users" for /users, unless it is given a name
@get('/me')
def me(c):
    c.redirect_to('user', id=23)


app.start()
```

```sh
python app.py daemon                 # http://127.0.0.1:3000
pyjo-reload app.py                   # restarts when the files change
python app.py routes                 # the routes
python app.py get '/users/23?full=1' # a request without a server
```

## Idioms

| Flask, FastAPI, Django                                        | Pyjoyment                                                                                                                                     |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `@app.route('/x', methods=['POST'])`, `@app.post('/x')`       | `@post('/x')`, `@any(['GET', 'POST'], '/x')`                                                                                                  |
| `/<int:id>`, `/{id}`, `path('users/<int:id>/', view)`         | `/<id:num>` or `/:id`, as braces are literal                                                                                                  |
| `request.args`, `request.form`, `request.GET`, path params    | `c.param('q')`, also of placeholders, `c.req.query_params`, `c.req.body_params`                                                               |
| `request.get_json()`, a model of pydantic                     | `c.req.json()`, validated with `Pyjo.JSON.Schema`                                                                                             |
| `request.files['f']`                                          | `c.req.upload('f')`                                                                                                                           |
| `request.headers`, `request.cookies`                          | `c.req.headers.header('X-Name')`, `c.cookie('name')`                                                                                          |
| `return 'Hi'`, `jsonify(...)`, `JSONResponse`, `HttpResponse` | `c.render(text='Hi')`, `c.render(json=...)`, `status=201`                                                                                     |
| `render_template('page.html', a=1)`, `render(request, ...)`   | `c.render('page', a=1)` with `templates/page.html.ep`                                                                                         |
| `redirect(url_for('name'))`                                   | `c.redirect_to('user', id=23)` of a route named as `@get('/users/<id:num>', 'user')`                                                          |
| `abort(404)`, `raise HTTPException(404)`, `Http404`           | `c.reply.not_found()`                                                                                                                         |
| `response.headers['X'] = 'y'`, `set_cookie`                   | `c.res.headers.header('X', 'y')`, `c.cookie('name', 'value')`                                                                                 |
| `session['user']`, `flash(...)`                               | `c.session('user')`, `c.session({'user': name})`, `c.flash(message='Hi')`                                                                     |
| `before_request`, middleware                                  | `hook('before_dispatch', cb)`, or `@under` for the routes after it                                                                            |
| a blueprint, `APIRouter`, `include()`                         | `with group():` and `@under('/admin')`                                                                                                        |
| `Depends(current_user)`                                       | a helper, `@helper('user')`, called as `c.user()`                                                                                             |
| `app.config`, `settings.py`                                   | `plugin('TOMLConfig')` of `app.toml`, and `app.config`                                                                                        |
| `static/`                                                     | `public/`, next to the script                                                                                                                 |
| `requests`, `httpx` in a handler                              | `await c.ua().get_p(url)` in an `async def` action                                                                                            |
| `requests.get(url)` in a script                               | `Pyjo.UserAgent.get(url).result`, of the user agent of the module, which follows redirects                                                    |
| `TestClient`, `app.test_client()`, `django.test.Client`       | `Pyjo.Test.Pyjo`                                                                                                                              |
| `flask run`, `uvicorn app:app`, `manage.py runserver`         | `python app.py daemon`, `prefork` with workers                                                                                                |
| a WSGI or ASGI server                                         | `application = app.start()`, `PYJO_ASGI=1 uvicorn app:application`                                                                            |
| the ORM of Django, SQLAlchemy                                 | none: a library of asyncio awaited in `async def`, or a blocking one in workers of `prefork`; a project that keeps Django: the skill `django` |
| `hashlib`, `hmac`, `base64`, `secrets.compare_digest`         | `sha256_sum`, `hmac_sha256_sum` and `hmac_sha256_bytes`, `b64_encode`, `b64url_encode` for URLs, `secure_compare` of `Pyjo.Util`, which chain |
| `pathlib.Path(f).read_bytes()`, `tempfile.TemporaryDirectory` | `Pyjo.File.path(f).slurp()`, `with Pyjo.File.tempdir() as tmp:`                                                                               |

## Validation, dependencies and middleware

```python
from Pyjo.JSON.Schema import Schema
from Pyjoyment.Lite import *

from typing import TypedDict


class Item(TypedDict):
    name: str
    price: float


ITEM = Schema.of(Item)


# A dependency of FastAPI is a helper
@helper('user')
def user(c):
    return c.req.headers.header('X-User')


# Runs before the routes after it, which it lets in with a true value
@under
def authenticated(c):
    if c.user():
        return True
    c.render(json={'error': 'unauthorized'}, status=401)
    return None


@post('/items')
def create(c):
    item = c.req.json()
    if not (result := ITEM.validate(item)):
        return c.render(json={'errors': [str(e) for e in result.errors]}, status=422)
    c.render(json={'item': item, 'by': c.user()}, status=201)


app.start()
```

## Requests of other services

```python
from Pyjoyment.Lite import *


# The user agent of the application waits without blocking the other connections, as requests or httpx would
@get('/title')
async def title(c):
    tx = await c.ua().get_p('https://example.com/')
    c.render(text=tx.result.dom().at('title').text)


app.start()
```

## Mistakes that run but do something else

- `@get('/users/{id}')` answers `404`: the braces are literal, the
  placeholder is `<id>` or `:id`.
- A script of `Pyjoyment.Lite` without `app.start()` as its last line does
  nothing, without a message. For AWS Lambda it is `handler = app.start()`.
- `requests`, `time.sleep` or a database driver without asyncio in an action
  stop the event loop for every connection: use `c.ua()`,
  `await Pyjo.Promise.timer(1)`, a library of asyncio, or the workers of
  `prefork` for what has to block.
- Jinja and `render_template` work outside of the renderer, without its
  helpers, layouts and the templates of `__DATA__`: use `ep` templates.
- The test client of another framework with pytest has no event loop of the
  application: use `Pyjo.Test.Pyjo`, `t.get_ok('/').status_is(200)`, which
  pytest runs too.

Pyjoyment names the fix in the messages of the mistakes that end with an
error, as an action that returns its response (`Action returned a str, which
is not a response`), a helper without its call (`Helper "ua" has no attribute
"get_p", call the helper first`), or `c.request` (`Did you mean "req"?`).

## Documentation

- Tutorial: https://pyjoyment.readthedocs.io/en/stable/guides/tutorial.html
- Routing: https://pyjoyment.readthedocs.io/en/stable/guides/routing.html
- Rendering: https://pyjoyment.readthedocs.io/en/stable/guides/rendering.html
- Testing: https://pyjoyment.readthedocs.io/en/stable/guides/testing.html
- Mounting an application of another framework, to migrate it step by step:
  https://pyjoyment.readthedocs.io/en/stable/guides/mounting.html
