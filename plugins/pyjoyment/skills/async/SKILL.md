---
name: async
description: Write non-blocking code with Pyjoyment, of Pyjo and Pyjoyment.Lite alike. Use whenever the code waits for I/O, a timer or another service, for async def actions, Pyjo.Promise (then, all, race, timeout, map), get_p of the user agent, timers, code that blocks the event loop and how to run it in a subprocess or in workers, and the reactors with libraries of asyncio.
---

# Asynchronous code

Pyjoyment serves every connection of a process with one event loop. Code that
waits without the event loop, as `time.sleep`, `requests` or a database driver
without asyncio, stops every other connection while it waits. Code that waits
for the event loop gives a promise, `Pyjo.Promise`, which an `async def`
action awaits.

## Waiting in an action

```python
import Pyjo.Exception
import Pyjo.Promise

from Pyjoyment.Lite import *


# A service that the actions below request, of the application itself, as c.ua() requests a relative URL from it
@get('/api/<n:num>')
async def api(c):
    await Pyjo.Promise.timer(0.1)
    c.render(json={'n': int(c.param('n'))})


# One after another
@get('/sequential')
async def sequential(c):
    one = (await c.ua().get_p('/api/1')).result.json('/n')
    two = (await c.ua().get_p('/api/2')).result.json('/n')
    c.render(json=[one, two])


# At the same time, where all gives the values of each promise as a tuple
@get('/concurrent')
async def concurrent(c):
    one, two = await Pyjo.Promise.all(c.ua().get_p('/api/1'), c.ua().get_p('/api/2'))
    c.render(json=[one[0].result.json('/n'), two[0].result.json('/n')])


# Many, three at a time
@get('/many')
async def many(c):
    results = await Pyjo.Promise.map(lambda n: c.ua().get_p(f'/api/{n}'), *range(1, 7), concurrency=3)
    c.render(json=[result[0].result.json('/n') for result in results])


# A limit of time, as a race with a promise that rejects, whose reason is the Pyjo.Exception that await raises
@get('/limited')
async def limited(c):
    limit = Pyjo.Promise.timeout(float(c.param('limit') or 1), 'Too slow')
    try:
        tx = await Pyjo.Promise.race(c.ua().get_p('/api/1'), limit)
    except Pyjo.Exception.object as e:
        return c.render(json={'error': e.message}, status=504)
    c.render(json=tx.result.json())


app.start()
```

- `await` of a promise gives its value, a tuple of several values, or raises
  the exception that it was rejected with; an exception of an `async def`
  action renders the exception page, as one of any action does.
- `Pyjo.Promise.all`, `all_settled`, `any` and `race` combine promises,
  `Pyjo.Promise.timer(seconds)` fulfills and `Pyjo.Promise.timeout(seconds,
  message)` rejects after a time, `Pyjo.Promise.map` limits the concurrency.
- `Pyjo.Iterator` passes elements through a chain one by one:
  `c(*urls).iterate().map(c.ua().get_p, concurrency=3)` with `async for` gives
  each response in the order of the URLs, three requests at a time, and
  `to_list_p()` gives all of them; a script iterates it with
  `for`, which waits with the event loop.
- `c.ua()` is the user agent of the application: `get_p`, `post_p`,
  `put_p` and the others give a promise of the transaction.

## Code that blocks

```python
import Pyjo.IOLoop

from Pyjoyment.Lite import *

import hashlib


# A subprocess runs what blocks, as a computation or a blocking library, and the promise gives what it returns
@get('/hash')
async def hash_password(c):
    def work(subprocess):
        return hashlib.pbkdf2_hmac('sha256', c.param('password').encode(), b'salt', 100_000).hex()

    digest = await Pyjo.IOLoop.subprocess().run_p(work)
    c.render(text=digest)


app.start()
```

- `Pyjo.IOLoop.subprocess().run_p(work)` runs `work` in a process of its own,
  which `os.fork` makes, so not on Windows; what it returns comes back as
  JSON, so it is a value that JSON encodes.
- The workers of `python app.py prefork -w 8`, or of `prethread`, serve the
  requests of an application whose code blocks anyway, one request at a time
  each with `-c 1`.
- On the default reactor, which runs the event loop of asyncio, an action
  awaits a coroutine or a future of asyncio too, as `asyncio.sleep`, a
  library of asyncio, as asyncpg or aiobotocore, or `asyncio.to_thread` for a
  blocking library that releases the GIL.

## Callbacks and timers

```python
import Pyjo.IOLoop

from Pyjoyment.Lite import *


ticks = 0


# Work in the background of each process, with the event loop of the server
@Pyjo.IOLoop.recurring(0.1)
def tick(loop):
    global ticks
    ticks += 1


# A response later, after a timer, which needs no async def
@get('/delayed')
def delayed(c):
    Pyjo.IOLoop.timer(0.2, lambda loop: c.render(json={'ticks': ticks}))


# A request with a callback, which gets the user agent and the transaction
@get('/callback')
def callback(c):
    c.ua().get('/delayed', lambda ua, tx: c.render(json=tx.result.json()))


app.start()
```

- An action that renders nothing before it returns leaves the response to a
  callback, which renders it later.
- A callback of a timer gets the event loop, `lambda loop: ...`, of an event
  the emitter first, `lambda c, msg: ...`; a promise of the callback style
  reports its error with `.catch(lambda err: c.reply.exception(err))`.

## Reactors

- `Pyjo.Reactor.Asyncio`, the default, runs the event loop of asyncio, so the
  coroutines and the libraries of asyncio work with the ones of Pyjoyment.
  `PYJO_REACTOR=Pyjo.Reactor.Poll` selects the reactor of `select.poll`,
  without asyncio, where a promise works and a coroutine of asyncio does not.
- A coroutine of asyncio awaits a promise of Pyjoyment, and
  `promise.to_future()` gives a future of asyncio.
- `promise.wait()` runs the event loop until the promise settles, in a script;
  in an action, where the event loop runs already, it returns at once, so an
  action awaits.

## Mistakes

- `time.sleep`, `requests`, `urllib.request` or a blocking database driver in
  an action stop every connection. `PYTHONDEVMODE=1` logs a callback that
  blocked the loop, as `Executing <Handle ...> took 2.003 seconds`.
- A blocking request in an action, `c.ua().get(url)` without a callback, does
  not wait for the response, and warns `Blocking request in a running event
  loop of asyncio`: await `get_p` instead.
- A promise without `await`, `tx = c.ua().get_p(url)` and then `tx.result`,
  fails with `a promise gives its value to await or to a callback of then`.
- A long wait, as a stream of events, needs a longer inactivity timeout of its
  connection: `c.inactivity_timeout(300)`.

## Documentation

- Cookbook, the real-time web: https://pyjoyment.readthedocs.io/en/latest/guides/cookbook.html
- Pyjo.Promise: https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_Promise.html
- Pyjo.IOLoop.Subprocess: https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_IOLoop_Subprocess.html
