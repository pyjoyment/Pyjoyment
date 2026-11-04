import Pyjo.File
import Pyjo.IOLoop
import Pyjo.IOLoop.ChildProcess
import Pyjo.IOLoop.Messages
import Pyjo.IOLoop.Stdio

from Pyjo.File import curfile
from Pyjo.Test import *

import os
import re
import select
import subprocess
import sys


# Not in Mojolicious: the standard input and output as a stream
PYTHON = sys.executable

# The standard error of a child is compared as a whole, where the debug mode of asyncio, as of PYTHONDEVMODE, would log a
# callback that is slow on a busy machine
ENV = {
    **os.environ,
    'PYTHONPATH': os.pathsep.join([curfile().dirname().dirname().dirname().to_str(), *sys.path]),
    'PYJO_ASYNCIO_SLOW_CALLBACK': '10',
}

# A server of lines in capitals, which prints what it gets, runs a program that writes to the file descriptor 1, and
# tells the modes of its descriptors
SERVER = """
import Pyjo.IOLoop.Messages, Pyjo.IOLoop.Stdio, os, subprocess, sys

before = os.get_blocking(0), os.get_blocking(1)
stdio = Pyjo.IOLoop.Stdio.new()
during = os.get_blocking(stdio.handle.fileno())
messages = Pyjo.IOLoop.Messages.new(stdio)
messages.max_message_size = 100

@messages.on('message')
def message(messages, message):
    print('got', message.decode())
    subprocess.run(['echo', 'from a program'])
    messages.send(message.upper())

messages.on('error', lambda messages, err: print('error', err.message, file=sys.stderr))
messages.on('close', lambda messages: stdio.reactor.stop())
messages.start()
stdio.reactor.start()
print('after', before, during, (os.get_blocking(0), os.get_blocking(1)))
"""


# The output, the error and the exit code of a script, whose input is written and ended
def run(code, input=b'', timeout=10):
    child = Pyjo.IOLoop.ChildProcess.new()
    result = []
    child.run_p([PYTHON, '-c', code], input=input, env=ENV).then(
        lambda *args: (result.extend(args), Pyjo.IOLoop.stop())
    )
    timer = Pyjo.IOLoop.timer(timeout, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.remove(timer)
    code, out, err = result
    return code, bytes(out), bytes(err).decode()


if os.name == 'nt':
    with subtest('Windows'):
        throws_ok(
            lambda: Pyjo.IOLoop.Stdio.new(),
            re.compile(r'^Standard input and output need pipes that the reactor watches'),
            'no stream',
        )
    done_testing()
    sys.exit()

with subtest('Pipes'):
    code, out, err = run(SERVER, b'hello\nworld\r\n')
    is_ok(code, 0, 'right exit code')
    is_ok(out, b'HELLO\nWORLD\nafter (True, True) False (True, True)\n', 'messages, and the output given back')
    like_ok(
        err, re.compile(r'^got hello\nfrom a program\ngot world\nfrom a program\n$'), 'print and a program on stderr'
    )

with subtest('End of input'):
    code, out, err = run(SERVER)
    is_ok(code, 0, 'right exit code')
    is_ok(out, b'after (True, True) False (True, True)\n', 'no messages')
    is_ok(err, '', 'no error')

with subtest('Message over the maximum size'):
    code, out, err = run(SERVER, b'one\n' + b'x' * 101 + b'\ntwo\n')
    is_ok(code, 0, 'right exit code')
    is_ok(out, b'ONE\nafter (True, True) False (True, True)\n', 'closed after the message that is too long')
    like_ok(err, re.compile(r'^error Maximum message size exceeded$', re.M), 'right error')

with subtest('Responses after the end of input'):
    code = """
import Pyjo.IOLoop.Stdio

stdio = Pyjo.IOLoop.Stdio.new()
stdio.on('read', lambda stdio, chunk: stdio.reactor.timer(0.2, lambda reactor: stdio.write(chunk.upper())))
stdio.on('end', lambda stdio: stdio.reactor.timer(0.5, lambda reactor: stdio.close_gracefully()))
stdio.on('close', lambda stdio: stdio.reactor.stop())
stdio.start()
stdio.reactor.start()
"""
    is_deeply_ok(run(code, b'late'), (0, b'LATE', ''), 'written after the end of input')

with subtest('Promises of the chunks and of the messages'):
    code = """
import Pyjo.IOLoop.Stdio, Pyjo.Promise

stdio = Pyjo.IOLoop.Stdio.new()

@Pyjo.Promise.coroutine
async def main():
    async for chunk in stdio:
        await stdio.write_p(chunk.upper())
    await stdio.write_p(b'|end')
    stdio.close()

main().wait()
"""
    is_deeply_ok(run(code, b'hello'), (0, b'HELLO|end', ''), 'chunks until the end of the input, then a write')
    code = """
import Pyjo.IOLoop.Messages, Pyjo.IOLoop.Stdio, Pyjo.Promise

messages = Pyjo.IOLoop.Messages.new(Pyjo.IOLoop.Stdio.new())

@Pyjo.Promise.coroutine
async def main():
    count = 0
    async for message in messages:
        count += 1
        await messages.send_p(message.upper())
    await messages.send_p(f'{count} messages')
    messages.close_gracefully()

main().wait()
"""
    is_deeply_ok(run(code, b'one\ntwo\n'), (0, b'ONE\nTWO\n2 messages\n', ''), 'messages until the end')

with subtest('Drain callback'):
    code = """
import Pyjo.IOLoop.Stdio, sys

stdio = Pyjo.IOLoop.Stdio.new()
stdio.write(b'x' * 1000000, lambda stdio: print('drained', stdio.bytes_written, stdio.is_writing))
stdio.on('close', lambda stdio: stdio.reactor.stop())
stdio.start()
stdio.reactor.start()
"""
    code, out, err = run(code)
    is_deeply_ok((code, len(out), err), (0, 1000000, 'drained 1000000 False\n'), 'written before the end')

with subtest('One stream at a time'):
    code = """
import Pyjo.IOLoop.Stdio, os

with Pyjo.IOLoop.Stdio.new() as stdio:
    try:
        Pyjo.IOLoop.Stdio.new()
    except Exception as e:
        print(e.message)
with Pyjo.IOLoop.Stdio.new() as stdio:
    stdio.write(b'again')
    stdio.close_gracefully()
    stdio.on('close', lambda stdio: stdio.reactor.stop())
    stdio.start()
    stdio.reactor.start()
print(' and back')
"""
    code, out, err = run(code)
    is_deeply_ok((code, out), (0, b'again and back\n'), 'a second stream after the first')
    is_ok(err, 'Standard input and output are a stream already\n', 'not two at a time')

with subtest('Output closed by its reader'):
    code = """
import Pyjo.IOLoop.Stdio, sys

stdio = Pyjo.IOLoop.Stdio.new()
stdio.on('read', lambda stdio, chunk: stdio.write(chunk * 100))
stdio.on('close', lambda stdio: (print('closed', file=sys.stderr), stdio.reactor.stop()))
stdio.start()
stdio.reactor.start()
"""
    child = Pyjo.IOLoop.ChildProcess.new().spawn([PYTHON, '-c', code], env=ENV)
    err = []
    child.stderr.on('read', lambda stream, chunk: err.append(chunk))
    child.stdout.close()
    child.stdin.write(b'x' * 1000)
    child.on('close', lambda child, code, signal: Pyjo.IOLoop.stop())
    timer = Pyjo.IOLoop.timer(10, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.remove(timer)
    child.stdin.close()
    is_ok(child.exit_code, 0, 'right exit code')
    is_ok(b''.join(err), b'closed\n', 'closed')

with subtest('Files'):
    with Pyjo.File.tempdir() as dir:
        dir.child('input').spew(b'hello\nworld\n')
        with open(dir.child('input').to_str(), 'rb') as input, open(dir.child('output').to_str(), 'wb') as output:
            result = subprocess.run(
                [PYTHON, '-c', SERVER], stdin=input, stdout=output, stderr=subprocess.PIPE, env=ENV, timeout=10
            )
        is_ok(result.returncode, 0, 'right exit code')
        is_ok(dir.child('output').slurp(), b'HELLO\nWORLD\nafter (True, True) True (True, True)\n', 'file of output')

with subtest('Terminal'):
    # Imported here, as pty imports termios, which Windows does not have
    import pty

    main, sub = pty.openpty()
    process = subprocess.Popen([PYTHON, '-c', SERVER], stdin=sub, stdout=sub, stderr=subprocess.PIPE, env=ENV)
    os.close(sub)
    output = b''
    os.write(main, b'hello\n')
    while b'HELLO' not in output and select.select([main], [], [], 10)[0]:
        output += os.read(main, 1024)

    # The end of input of a terminal
    os.write(main, b'\x04')
    while select.select([main], [], [], 10)[0]:
        try:
            chunk = os.read(main, 1024)
        except OSError:
            break
        if not chunk:
            break
        output += chunk
    os.close(main)
    is_ok(process.wait(10), 0, 'right exit code')
    process.stderr.close()
    like_ok(output.decode(), re.compile(r'HELLO\r?\n'), 'message')
    like_ok(output.decode(), re.compile(r'after \(True, True\) True \(True, True\)'), 'terminal in blocking mode')

with subtest('Null device'):
    result = subprocess.run([PYTHON, '-c', SERVER], stdin=subprocess.DEVNULL, capture_output=True, env=ENV, timeout=10)
    is_ok(result.returncode, 0, 'right exit code')
    is_ok(result.stdout, b'after (True, True) True (True, True)\n', 'no messages')

done_testing()
