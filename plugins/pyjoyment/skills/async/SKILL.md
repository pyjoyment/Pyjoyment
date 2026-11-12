---
name: async
description: Write non-blocking code with Pyjoyment, of Pyjo and Pyjoyment.Lite alike. Use whenever the code waits for I/O, a timer or another service, for async def actions, Pyjo.Promise (then, all, race, timeout, map), get_p of the user agent, timers, code that blocks the event loop and how to run it in a subprocess or in workers, the code of a library that a script and an action share with Pyjo.Steps, and the reactors with libraries of asyncio.
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
- An `async def` action whose client goes away before its response ends is
  cancelled where it waits: its `finally` blocks run, `except Exception` does
  not catch the cancellation, and the request of `get_p` that it waits for
  closes its connection. `promise.cancel()` does it for a promise of a
  request or of a coroutine.

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
  each with `-c 1`, and `Pyjo.IOLoop.blocking(cb, *args)` calls such code with
  no running loop of asyncio, for a library that refuses to block in one, as
  the ORM of Django.
- On the default reactor, which runs the event loop of asyncio, an action
  awaits a coroutine or a future of asyncio too, as `asyncio.sleep`, a
  library of asyncio, as asyncpg or aiobotocore, or `asyncio.to_thread` for a
  blocking library that releases the GIL.

## Code for a script and an action

```python
import Pyjo.Exception

from Pyjo.Steps import Request, Sleep, Steps
from Pyjoyment.Lite import *


# The code of a library, written once for a script and for an action, which awaits only the steps of Pyjo.Steps
async def fetch(ua, url, tries=3):
    for attempt in range(tries):
        tx = await Request(ua.build_tx('GET', url))
        if tx.res.code != 503:
            return tx.result.json()
        await Sleep(0.1 * 2**attempt)
    raise Pyjo.Exception.new(f'Unavailable: {url}')


# A service that is busy at every other request, of the application itself
busy = False


@get('/api')
def api(c):
    global busy
    busy = not busy
    if busy:
        return c.render(json={'error': 'Busy'}, status=503)
    c.render(json={'answer': 42})


# The same steps in an action, non-blocking, with the user agent of the application
@get('/data')
async def data(c):
    c.render(json=await Steps(fetch(c.ua(), '/api')).run_p(c.ua()))


app.start()
```

- `Pyjo.Steps` runs a coroutine that awaits a `Request` of a transaction, a
  `Command` of a program, `Command(['hostname'])`, with `env=` and
  `timeout=`, which gives its exit code, output and error, a `Sleep` of
  seconds, and the `Steps` of another coroutine.
- `Steps(fetch(ua, url)).run(ua)` runs them blocking in a script, with
  `ua.start`, `subprocess.run` and `time.sleep`; `run_p(ua)` gives a promise
  and runs them with `start_p`, `Pyjo.IOLoop.ChildProcess` and a timer, which
  leave the event loop to the other connections.
- An error of a connection or a program that cannot be run is a
  `Pyjo.Exception` that `await` raises in the coroutine, which catches it as
  any exception; a response with an error status is not an error, the
  transaction gives it, as `tx.res.code` above.
- `Request(tx, ua)` starts a transaction with a user agent of its own, as one
  whose event `start` adds credentials; the user agent of `run` or `run_p` is
  the default.
- A generator that yields the steps, and takes other steps with
  `yield from`, runs as a coroutine does.

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
  in an action or a coroutine of asyncio, as in `asyncio.run` or a notebook of
  Jupyter, where the event loop runs already, it returns at once, so they
  await.

## Mistakes

- `Pyjo.Iterator.new(items)` takes a list, and `c(*items)` and
  `Pyjo.Collection.new(*items)` take the elements: `Pyjo.Collection.new(items)`
  is a collection of one element, the list. `map` of an iterator takes a
  coroutine function as it takes a function that gives a promise.

- `time.sleep`, `requests`, `urllib.request` or a blocking database driver in
  an action stop every connection. `PYTHONDEVMODE=1` logs a callback that
  blocked the loop, as `Executing <Handle ...> took 2.003 seconds`.
- A blocking request in an action or a coroutine, `c.ua().get(url)` without a
  callback, cannot wait for the response in the event loop of asyncio that
  runs, and raises `RuntimeError: Blocking request in a running event loop`:
  await `get_p` instead.
- A promise without `await`, `tx = c.ua().get_p(url)` and then `tx.result`,
  fails with `a promise gives its value to await or to a callback of then`.
- `await Steps(...)` in an action gives its steps to the event loop, which
  does not know them, `Task got bad yield: <Pyjo.Steps.Request ...>`: await
  `Steps(...).run_p(c.ua())`. Inside the steps, a promise or a coroutine of
  asyncio is a `TypeError`, as nothing runs the event loop for `run`.
- A long wait, as a stream of events or a model of language that is silent
  for minutes, needs a longer inactivity timeout of its connection:
  `c.inactivity_timeout(300)`, or the value of the stash of its route,
  `get('/chat', {'inactivity_timeout': 600}, chat)`, or of a group with
  `under`. `request_timeout` there, or `c.request_timeout(120)`, bounds the
  whole response: the actions are cancelled, and the request gets `504`.
  `heartbeat` there, or `c.heartbeat(15)`, writes a comment of Server-Sent
  Events, or a ping of a WebSocket, while the stream waits, for a proxy with
  an idle timeout of its own.

## Documentation

- Cookbook, the real-time web: https://pyjoyment.readthedocs.io/en/stable/guides/cookbook.html
- Pyjo.Promise: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_Promise.html
- Pyjo.IOLoop.Subprocess: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_IOLoop_Subprocess.html
- Pyjo.Steps: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_Steps.html
