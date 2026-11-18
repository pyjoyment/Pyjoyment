---
name: api
description: Build JSON APIs with Pyjoyment. Use for endpoints that read and render JSON, the validation of a request body with Pyjo.JSON.Schema from type hints or from its builder z after zod, errors as JSON with the JSON Pointers of the invalid values, status codes, CORS, and JSON-RPC 2.0 servers and clients with Pyjo.JSON.RPC, whose methods validate their parameters with the schema of their type hints.
---

# JSON APIs

An endpoint reads JSON with `c.req.json()`, a JSON Pointer into it with
`c.req.json('/name')`, and renders JSON with `c.render(json=...)`.
`Pyjo.JSON.Schema` makes JSON Schema 2020-12 from type hints, as the ones of a
`TypedDict` or of the parameters of a function, or with its builder `z`,
after zod, and validates a value with it; `Pyjo.JSON.RPC` serves JSON-RPC 2.0
on a route.

## REST

```python
# rest.py
from Pyjo.JSON.Schema import Schema, z
from Pyjoyment.Lite import *

from typing import NotRequired, TypedDict


# CORS, for the pages of every other site, with the answers of the preflight requests of PUT, PATCH and DELETE
plugin('CORS')


class Item(TypedDict):
    name: str
    price: float
    tags: NotRequired[list[str]]


# The schema of the type hints, and one of the builder, whose fields are optional
ITEM = Schema.of(Item)
PATCH = z.object(name=z.string().min(1).optional(), price=z.number().min(0).optional())

items = {1: {'name': 'Pen', 'price': 1.5}}


def invalid(c, result):
    c.render(json={'errors': [str(error) for error in result.errors]}, status=422)


@get('/items')
def index(c):
    limit = int(c.param('limit') or 10)
    c.render(json=[{'id': id, **item} for id, item in list(items.items())[:limit]])


@post('/items')
def create(c):
    item = c.req.json()
    if not (result := ITEM.validate(item)):
        return invalid(c, result)
    id = max(items, default=0) + 1
    items[id] = item
    c.res.headers.location = c.url_for('item', id=id).to_abs()
    c.render(json={'id': id, **item}, status=201)


@get('/items/<id:num>', 'item')
def show(c):
    if (item := items.get(int(c.param('id')))) is None:
        return c.reply.json_not_found()
    c.render(json={'id': int(c.param('id')), **item})


@patch('/items/<id:num>')
def update(c):
    if (item := items.get(int(c.param('id')))) is None:
        return c.reply.json_not_found()
    if not (result := PATCH.validate(changes := c.req.json())):
        return invalid(c, result)
    item.update(changes)
    c.render(json={'id': int(c.param('id')), **item})


@delete('/items/<id:num>')
def remove(c):
    items.pop(int(c.param('id')), None)
    c.rendered(204)


app.start()
```

- An error of the validation is a `str` with the JSON Pointer of the value,
  as `/price: Expected number - got string.`; `result` is false when the
  value is not valid.
- `Schema.of(T)` takes a type, `Schema.parameters(function)` the parameters
  of a function, `Schema.new({...})` a schema written by hand, and `schema.data`
  is the schema as JSON, for the documentation of the API.
- `c.req.json()` is `None` for a body that is not JSON: the validation of an
  object reports it as `/: Expected object - got null.`.
- `c.rendered(204)` ends a response without a body; `c.reply.json_not_found()`
  renders 404 as JSON.
- `plugin('CORS', origins=['https://app.example.com'], credentials=True, paths=['/api'])`
  lets the pages of a frontend read the API with the cookies of its user; the
  origins are also those of `plugin('AllowedHosts', origins=...)`, which
  rejects the other ones.

## JSON-RPC

```python
# rpc.py
import Pyjo.JSON.RPC

from Pyjoyment.Lite import *


rpc = Pyjo.JSON.RPC.new()


# A method of JSON-RPC, whose params the schema of its type hints validates
@rpc.method(schema=True)
def subtract(minuend: int, subtrahend: int) -> int:
    """Subtract two numbers."""
    return minuend - subtrahend


post('/rpc', rpc.to_action())


# A client, which sends its requests with the user agent of the application
@get('/difference/<a:num>/<b:num>')
async def difference(c):
    client = Pyjo.JSON.RPC.Client.new(lambda request: c.ua().post_p('/rpc', json=request).then(lambda tx: tx.res.json()))
    c.render(json={'difference': await client.call_p('subtract', int(c.param('a')), int(c.param('b')))})


app.start()
```

- `params` that the schema does not validate give `-32602`, `Invalid params`,
  with the errors as its `data`; an exception of a method gives `-32603`
  without its message, and `Pyjo.JSON.RPC.Error(code, message, data)` an
  error of its own.
- A method can be an `async def`, or return a promise; a request without an
  `id` is a notification, without a response, and a batch is an array.

## Mistakes

- A response is rendered once: `return c.render(...)` after an error, so the
  action does not go on to render a second one.
- `c.param('limit')` is a string or `None`: convert it, as `int(...)`, and
  validate it.
- A placeholder or a value of the stash cannot be named `json`, `data`,
  `text`, `status` or `format`, which `render` and the router reserve.
- `json.dumps` of Python with `c.render(data=...)` or `text=` skips the
  `Content-Type` of JSON, which `c.render(json=...)` sets.
- `Access-Control-Allow-Origin` set by hand misses the preflight requests,
  which a browser sends before a `PUT` or a request of JSON, and `Vary: Origin`;
  `credentials=True` needs origins of their own, as browsers refuse `*` with
  cookies, and reflecting any `Origin` would let every site read the data of the
  user.

## Documentation

- Pyjo.JSON.Schema: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_JSON_Schema.html
- Pyjo.JSON.RPC: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_JSON_RPC.html
- Rendering JSON: https://pyjoyment.readthedocs.io/en/stable/guides/rendering.html
- Pyjoyment.Plugin.CORS: https://pyjoyment.readthedocs.io/en/stable/api/Pyjoyment_Plugin_CORS.html
