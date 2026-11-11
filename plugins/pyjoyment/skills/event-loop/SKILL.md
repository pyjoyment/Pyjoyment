---
name: event-loop
description: Write network programs on the event loop of Pyjo without the web framework, with Pyjo.IOLoop, ported from Mojo::IOLoop. Use for servers and clients of TCP, TLS and UNIX domain sockets with their streams, UDP with Pyjo.IOLoop.Datagram, programs in processes of their own with Pyjo.IOLoop.ChildProcess, timers, an HTTP server of Pyjo.Server.Daemon without an application, and their callbacks, promises and coroutines.
---

# The event loop

`Pyjo.IOLoop` is the event loop of Pyjoyment and of Pyjo: the servers, the
clients and the timers of a process run in it, each in a callback, a promise
or a coroutine, until the loop stops. `Pyjo.IOLoop.server`, `client` and
`timer` use the loop of the process, `Pyjo.IOLoop.singleton`, which
`Pyjo.IOLoop.start()` runs and `loop.stop()` ends.

## A server and a client of TCP

```python
# echo.py
import Pyjo.IOLoop


# A server of TCP, on a port that the system picks, which answers each chunk that it reads
@Pyjo.IOLoop.server(address='127.0.0.1', port=0)
def server(loop, stream, id):
    stream.on('read', lambda stream, chunk: stream.write(b'echo: ' + chunk))


port = Pyjo.IOLoop.acceptor(server).port


# A client of it, which stops the event loop once the answer comes
@Pyjo.IOLoop.client(address='127.0.0.1', port=port)
def client(loop, err, stream):
    if err:
        raise SystemExit(err)

    @stream.on('read')
    def read(stream, chunk):
        print(chunk.decode())
        loop.stop()

    stream.write(b'hello')


# A limit of time, as an event loop runs until it is stopped
Pyjo.IOLoop.timer(5, lambda loop: loop.stop())
Pyjo.IOLoop.start()
```

- A callback of the event loop gets the loop first, of an event the emitter
  first: `read(stream, chunk)`, `close(stream)`, `error(stream, err)`,
  `timeout(stream)`.
- `stream.write(chunk)`, `stream.close_gracefully()` after what is written,
  `stream.timeout = 15` of inactivity; `tls=True` makes it TLS, and
  `path='/tmp/sock'` a UNIX domain socket.
- `Pyjo.IOLoop.recurring(seconds)` repeats, `Pyjo.IOLoop.remove(id)` ends a
  server, a connection or a timer, `Pyjo.IOLoop.next_tick(cb)` runs a callback
  as soon as possible.

## Promises and coroutines

```python
# coroutines.py
import Pyjo.IOLoop
import Pyjo.Promise


@Pyjo.IOLoop.server(address='127.0.0.1', port=0)
def server(loop, stream, id):
    stream.on('read', lambda stream, chunk: stream.write(chunk.upper()))


port = Pyjo.IOLoop.acceptor(server).port


# A coroutine as a promise, which runs in the event loop that wait() runs until the promise settles
@Pyjo.Promise.coroutine
async def main():
    stream = await Pyjo.IOLoop.client_p(address='127.0.0.1', port=port)
    await stream.write_p(b'hello')
    print((await stream.read_p()).decode())
    stream.close()


main().wait()
```

- `client_p` gives the stream, `read_p` its next chunk, `write_p` waits until
  it is written; `async for chunk in stream` reads until the stream ends.
- `stream.iterate()`, `messages.iterate()` and `e.events(name)` are
  `Pyjo.Iterator` objects, whose chain, as `.map(bytes.upper)`, works with
  `async for`, and with `for` in a script, which waits with the event loop.
- `wait()` runs the event loop in a script until the promise settles; code
  that the event loop runs awaits instead.

## Processes and UDP

```python
# processes.py
import Pyjo.IOLoop.ChildProcess
import Pyjo.IOLoop.Datagram
import Pyjo.Promise

import sys


@Pyjo.Promise.coroutine
async def main():
    # A program in a process of its own, with its exit code, its output and its error
    code, out, err = await Pyjo.IOLoop.ChildProcess.new().run_p([sys.executable, '-c', 'print("from the child")'])
    print(code, out.decode().strip())

    # A server of UDP that answers, and a client of it
    server = Pyjo.IOLoop.Datagram.new()
    server.on('message', lambda server, data, peer: server.send(b'pong ' + data, peer))
    server.bind(address='127.0.0.1', port=0)
    client = await Pyjo.IOLoop.Datagram.new().connect_p(address='127.0.0.1', port=server.port)
    await client.send_p(b'ping')
    data, peer = await client.recv_p(timeout=5)
    print(data.decode())
    client.close()
    server.close()


main().wait()
```

- `ChildProcess` runs a program with its standard input, output and error as
  streams that the event loop reads, `spawn(args)` with the events `spawn`,
  `exit` and `close`, or `run_p(args, input=b'...')`; it needs pipes that the
  event loop watches, which Windows does not have.
- `Pyjo.IOLoop.subprocess().run_p(function)` runs a function of Python in a
  fork of the process, for what blocks.

## An HTTP server without the framework

```python
# daemon.py
import Pyjo.IOLoop
import Pyjo.Server.Daemon
import Pyjo.UserAgent


# The server answers each transaction itself, with no application
with (
    Pyjo.Server.Daemon.new(listen=['http://127.0.0.1'], silent=True) as daemon,
    Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton) as ua,
):

    @daemon.unsubscribe('request').on('request')
    def request(daemon, tx):
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'Hello {tx.req.url.path}!'.encode()
        tx.resume()

    # A blocking request in the same event loop, which runs it until the response
    port = daemon.start().ports()[0]
    print(ua.get(f'http://127.0.0.1:{port}/world').result.text)
```

- `listen=['http://*:8080']`, `https://` with the certificate and the key in
  its query, as `?cert=/path/server.crt&key=/path/server.key`, or
  `http+unix://%2Ftmp%2Fmyapp.sock` of a UNIX domain socket, with its path
  escaped; `daemon.run()` runs it until a
  signal stops it.

## Mistakes

- Code that blocks in a callback, as `time.sleep` or a blocking request, stops
  every connection of the loop. A blocking request in a callback raises
  `Blocking request in a running event loop` on the default reactor, unless
  `Pyjo.IOLoop.blocking(cb, *args)` calls it, which also lets a library that
  refuses a running loop of asyncio, as Django, run.
- An event loop that nothing stops runs for ever: a script stops it, or a
  promise that `wait()` waits for settles.
- A stream that nothing closes keeps its socket open; the end of a `with` block
  closes a server, a user agent or a loop, and `PYTHONDEVMODE=1` reports a
  `ResourceWarning` of what stayed open.
- A server on port 0 has a port that the system picks: `acceptor(id).port`,
  or `ports()` of a daemon.

## Documentation

- Pyjo.IOLoop: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_IOLoop.html
- Pyjo.IOLoop.Stream: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_IOLoop_Stream.html
- Pyjo.IOLoop.Datagram: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_IOLoop_Datagram.html
- Pyjo.IOLoop.ChildProcess: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_IOLoop_ChildProcess.html
- Pyjo.Server.Daemon: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_Server_Daemon.html
