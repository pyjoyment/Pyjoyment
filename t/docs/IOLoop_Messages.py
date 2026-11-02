import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.IOLoop.ChildProcess
import Pyjo.IOLoop.Messages
import Pyjo.IOLoop.Stream
import Pyjo.Promise

from Pyjo.File import curfile
from Pyjo.Test import *

import io
import os
import socket
import sys

from contextlib import redirect_stdout


if os.name == 'nt':
    plan(skip_all='the standard input and output need pipes that the reactor watches, which Windows does not have')

ENV = {**os.environ, 'PYTHONPATH': os.pathsep.join([curfile().dirname().dirname().dirname().to_str(), *sys.path])}

# A server of lines in capitals, as ./server.py of the examples
SERVER = [sys.executable, '-c', 'import sys\nfor line in sys.stdin:\n    print(line.strip().upper(), flush=True)\n']


# The examples of the standard input and output run in a process of their own, as the stream takes them
def run(code, input):
    result = []
    promise = Pyjo.IOLoop.ChildProcess.new().run_p([sys.executable, '-c', code], input=input, env=ENV)
    promise.then(lambda *args: (result.extend(args), Pyjo.IOLoop.stop()))
    loop()
    code, out, err = result
    return code, bytes(out), bytes(err)


def loop():
    timer = Pyjo.IOLoop.timer(10, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.remove(timer)


# Two streams of a pair of sockets
def pair():
    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)
    streams = Pyjo.IOLoop.Stream.new(a), Pyjo.IOLoop.Stream.new(b)
    for stream in streams:
        stream.start()
    return streams


with subtest('Synopsis'):
    code = """
from Pyjo.IOLoop.Messages import Messages
from Pyjo.IOLoop.Stdio import Stdio

# Echo the lines of the standard input in capitals
messages = Messages(Stdio())
messages.on('message', lambda messages, message: messages.send(message.upper()))

messages.on('close', lambda messages: messages.stream.reactor.stop())
messages.start()
messages.stream.reactor.start()
"""
    is_deeply_ok(run(code, b'hello\nworld\n'), (0, b'HELLO\nWORLD\n', b''), 'echo')

    code = """
import Pyjo.IOLoop.Messages
import Pyjo.IOLoop.Stdio

# Echo the lines of the standard input in capitals
messages = Pyjo.IOLoop.Messages.new(Pyjo.IOLoop.Stdio.new())
messages.on('message', lambda messages, message: messages.send(message.upper()))
messages.on('close', lambda messages: messages.stream.reactor.stop())
messages.start()

# Start reactor if necessary
if not messages.stream.reactor.is_running:
    messages.stream.reactor.start()
"""
    is_deeply_ok(run(code, b'hello\nworld\n'), (0, b'HELLO\nWORLD\n', b''), 'echo until the end')

    # The messages of the Language Server Protocol, framed by Content-Length headers
    stream, peer = pair()
    messages = Pyjo.IOLoop.Messages.new(stream, framing=Pyjo.IOLoop.Messages.ContentLength())
    got = []
    messages.on('message', lambda messages, message: (got.append(message), Pyjo.IOLoop.stop()))
    peer.write(b'Content-Length: 2\r\n\r\n{}')
    loop()
    is_deeply_ok(got, [b'{}'], 'message of LSP')
    stream.close()
    peer.close()

    # The standard output and input of a server in a child process
    child = Pyjo.IOLoop.ChildProcess.new().spawn(SERVER)
    messages = Pyjo.IOLoop.Messages.new(child.stdout, output=child.stdin)
    messages.send('{"jsonrpc": "2.0", "method": "update", "params": [1]}')
    got = []
    messages.on('message', lambda messages, message: (got.append(message), messages.close_gracefully()))
    child.on('close', lambda child, code, signal: Pyjo.IOLoop.stop())
    loop()
    is_deeply_ok(got, [b'{"JSONRPC": "2.0", "METHOD": "UPDATE", "PARAMS": [1]}'], 'message of the server')

with subtest('close_gracefully'):
    child = Pyjo.IOLoop.ChildProcess.new().spawn(SERVER)
    messages = Pyjo.IOLoop.Messages.new(child.stdout, output=child.stdin)
    request = '{"jsonrpc": "2.0", "method": "update", "params": [1], "id": 1}'
    got = []
    messages.on('message', lambda messages, message: got.append(message))
    child.on('close', lambda child, code, signal: Pyjo.IOLoop.stop())

    # The last request of a server of the standard input and output, and its response
    messages.send(request).close_gracefully()

    loop()
    is_deeply_ok(got, [request.upper().encode()], 'response after the end of the output')

with subtest('__aiter__, iterate, message_p and send_p'):
    stream, peer = pair()
    messages = Pyjo.IOLoop.Messages.new(stream)
    other = Pyjo.IOLoop.Messages.new(peer)
    got = []

    # Echo in capitals, one message after another
    @Pyjo.Promise.coroutine
    async def echo(iterator):
        async for message in iterator:
            await messages.send_p(message.upper())

    echoed = echo(aiter(messages))

    @Pyjo.Promise.coroutine
    async def talk():
        first = other.message_p()
        promise = other.send_p(b'Hello')
        await promise
        await other.send_p('Hello')
        got.append(await first)
        got.append(await other.message_p())
        peer.close_gracefully()

    talk().wait()
    echoed.wait()
    is_deeply_ok(got, [b'HELLO', b'HELLO'], 'echoed')
    is_ok(messages.message_p().wait(), None, 'end')

    import Pyjo.JSON

    stream, peer = pair()
    messages = Pyjo.IOLoop.Messages.new(stream)
    requests = []

    @Pyjo.Promise.coroutine
    async def decode():
        # The messages as JSON, in a chain
        async for request in messages.iterate().map(Pyjo.JSON.decode_json):
            requests.append(request)

    promise = decode()
    peer.write(b'{"id": 1}\n{"id": 2}\n').close_gracefully()
    promise.wait()
    is_deeply_ok(requests, [{'id': 1}, {'id': 2}], 'JSON')

    stream, peer = pair()
    messages = Pyjo.IOLoop.Messages.new(stream)
    printed = []

    @Pyjo.Promise.coroutine
    async def read(iterator):
        async for message in iterator:
            printed.append(message)
        while (message := await messages.message_p()) is not None:
            printed.append(message)

    promise = read(messages.iterate())
    peer.write(b'one\ntwo\n').close_gracefully()
    promise.wait()
    is_deeply_ok(printed, [b'one', b'two'], 'until the end')

with subtest('close_gracefully_p and once_p'):
    stream, peer = pair()
    messages = Pyjo.IOLoop.Messages.new(stream)
    other = Pyjo.IOLoop.Messages.new(peer)
    received = other.message_p()

    @Pyjo.Promise.coroutine
    async def bye():
        await messages.send_p('Bye!')
        await messages.close_gracefully_p()

    bye().wait()
    promise = messages.close_gracefully_p()
    promise.wait()
    messages.once_p('close').wait()
    got = []
    received.then(got.append).wait()
    is_deeply_ok(got, [b'Bye!'], 'sent, then closed')
    peer.close()

with subtest('Framing of its own'):
    # Messages of netstrings, as 3:abc,
    class Netstrings:
        def decode(self, buffer, max_size):
            if (colon := buffer.find(b':')) < 0:
                return None
            length = int(buffer[:colon])
            if max_size and length > max_size:
                raise Pyjo.Exception.new('Maximum message size exceeded')
            if len(buffer) < colon + length + 2:
                return None
            message = bytes(buffer[colon + 1 : colon + 1 + length])
            del buffer[: colon + length + 2]
            return message

        def encode(self, message):
            return b'%d:%s,' % (len(message), message)

    stream, peer = pair()
    messages = Pyjo.IOLoop.Messages.new(stream, framing=Netstrings())
    got = []
    errors = []
    messages.on('message', lambda messages, message: got.append(message))
    messages.on('error', lambda messages, err: errors.append(err.message))
    messages.on('close', lambda messages: Pyjo.IOLoop.stop())
    messages.max_message_size = 5
    sent = []
    peer.on('read', lambda stream, chunk: sent.append(chunk))
    messages.send(b'abc')
    peer.write(b'3:abc,0:,6:abcdef,')
    loop()
    is_deeply_ok(sent, [b'3:abc,'], 'frame')
    is_deeply_ok(got, [b'abc', b''], 'messages')
    is_deeply_ok(errors, ['Maximum message size exceeded'], 'too large')
    peer.close()

with subtest('Events'):
    stream, peer = pair()
    messages = Pyjo.IOLoop.Messages.new(stream)
    with redirect_stdout(io.StringIO()) as stdout:
        messages.on('message', lambda messages, message: print(f'Message: {message!r}'))
        messages.on('error', lambda messages, err: print(f'This looks bad: {err}'))
        messages.on('close', lambda messages: Pyjo.IOLoop.stop())
        messages.max_message_size = 5
        peer.write(b'hello\n123456\n')
        loop()
    like_ok(stdout.getvalue(), r"^Message: b'hello'\nThis looks bad: Maximum message size exceeded", 'printed')
    peer.close()

    code = """
import Pyjo.IOLoop.Messages
import Pyjo.IOLoop.Stdio

messages = Pyjo.IOLoop.Messages.new(Pyjo.IOLoop.Stdio.new())
messages.on('message', lambda messages, message: messages.stream.reactor.timer(0.1, lambda reactor: messages.send(message)))
messages.on('end', lambda messages: messages.stream.reactor.timer(0.3, lambda reactor: messages.close_gracefully()))
messages.on('close', lambda messages: messages.stream.reactor.stop())
messages.start()
messages.stream.reactor.start()
"""
    is_deeply_ok(run(code, b'late\n'), (0, b'late\n', b''), 'closed after the end')

done_testing()
