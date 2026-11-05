from Pyjo.Test import *

import atexit
import http.client
import importlib
import os
import signal
import subprocess
import sys
import time


if not hasattr(os, 'fork'):
    plan(skip_all='Pyjo.Server.Reload does not support Windows')

# PyPy with its JIT on macOS: the child of a fork crashes now and then with a bus error, under load
if sys.platform == 'darwin' and getattr(sys, 'pypy_translation_info', {}).get('translation.jit'):
    plan(skip_all='PyPy with its JIT on macOS: the child of a fork crashes now and then with SIGBUS')

import Pyjo.IOLoop.Server
import Pyjo.Server.Daemon
import Pyjo.Server.Reload
import Pyjo.Server.Reload.Backend.Poll

from Pyjo.File import curfile, tempdir
from Pyjo.Util import extract_usage


ROOT = curfile().dirname().dirname().dirname().to_str()
LIB = curfile().dirname().sibling('lib').to_str()

sys.path.insert(0, LIB)
ServerStart = importlib.import_module('ServerStart')

dir = tempdir()
# The log of the application tells what a server that did not answer or did not stop has done
log = dir.child('myapp.log')
myapp = dir.child('myapp.py').spew(
    f"""
import sys, threading
sys.path.insert(0, {LIB!r})
from Pyjoyment.Lite import app, get
app.log.path = {log.to_str()!r}
app.log.level = 'trace'
get('/', {{'text': 'Hello!'}})
get('/thread', lambda c: c.render(text=threading.current_thread().name))
app.start()
""".encode()
)


# A server in a process of its own, on a port that the arguments name as {port}, until the port accepts connections,
# started again on a new port when it is taken, and ended when the test ends before it stops it. Its temporary
# directory is the one of the test, where the default process id files of prefork and prethread are not shared with
# the servers of other tests
def server(*args, **kwargs):
    def start():
        port = ServerStart.port()
        process = subprocess.Popen(
            [sys.executable, *(arg.format(port=port) for arg in args)],
            env=dict(os.environ, PYTHONPATH=ROOT, TMPDIR=dir.to_str()),
            stdout=subprocess.PIPE,
            text=True,
            **kwargs,
        )
        atexit.register(end, process)
        # The listen socket of the manager accepts connections before the server answers them
        if ServerStart.listening(port, process) and answers(port):
            return port, process
        process.stdout.close()
        return None

    return ServerStart.retry(start)


# A server that the test has not stopped, as after a failure, with TERM, as Reload stops the process group of its server
# then, which KILL of Reload would leave running with the standard error of the test, which the harness waits for
def end(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()


def answers(port):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        # The connection is closed also when the request fails, as PyPy would close it only with its garbage collector
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        try:
            conn.request('GET', '/')
            if conn.getresponse().status == 200:
                return True
        except OSError:
            pass
        finally:
            conn.close()
        time.sleep(0.1)
    return False


def stop(process):
    process.send_signal(signal.SIGINT)
    try:
        status = process.wait(30)
    except subprocess.TimeoutExpired:
        ServerStart.report(log, myapp.to_str())
        raise
    output = process.stdout.read()
    process.stdout.close()
    return status, output


with subtest('Synopsis'):
    code = f"""
from Pyjo.Server.Reload import Reload

reload = Reload()
reload.daemon.listen = ['http://127.0.0.1:{{port}}']
reload.run({myapp.to_str()!r})
"""
    port, process = server('-c', code)
    status, output = stop(process)
    is_ok(status, 0, 'stopped')
    like_ok(output, rf'Web application available at http://127.0.0.1:{port}', 'listening')

    # Or import the module, as in Google Python Style Guide

    code = f"""
import Pyjo.Server.Reload

reload = Pyjo.Server.Reload.new()
reload.daemon.listen = ['http://127.0.0.1:{{port}}']
reload.run({myapp.to_str()!r})
"""
    port, process = server('-c', code)
    status, output = stop(process)
    is_ok(status, 0, 'stopped')
    like_ok(output, rf'Web application available at http://127.0.0.1:{port}', 'listening')

    code = f"""
import Pyjo.Server.Reload

reload = Pyjo.Server.Reload.new()
reload.daemon.listen = ['http://127.0.0.1:{{port}}']
reload.run({myapp.to_str()!r}, 'prefork', '-w', '1')
"""
    port, process = server('-c', code)
    status, output = stop(process)
    is_ok(status, 0, 'stopped')
    like_ok(output, rf'Web application available at http://127.0.0.1:{port}', 'prefork')

    started = dir.child('started.txt')
    command = dir.child('command.py').spew(
        f"import pathlib, sys\npathlib.Path({started.to_str()!r}).write_text('1')\nsys.stdin.read()\n".encode()
    )
    code = f"""
import Pyjo.Server.Reload

reload = Pyjo.Server.Reload.new(exec=[{f'{sys.executable} {command}'!r}])
reload.daemon.listen = ['http://127.0.0.1:{{port}}']
reload.run({myapp.to_str()!r})
"""
    port, process = server('-c', code)
    ServerStart.wait_for(lambda: os.path.exists(started), 'the command')
    status, output = stop(process)
    is_ok(status, 0, 'stopped')
    ok(os.path.exists(started), 'command')

with subtest('Description'):
    port, process = server('-m', 'Pyjo.Server.Reload', '-l', 'http://127.0.0.1:{port}', myapp.to_str())
    status, output = stop(process)
    is_ok(status, 0, 'python -m Pyjo.Server.Reload')
    like_ok(output, rf'Web application available at http://127.0.0.1:{port}', 'listening')

with subtest('Server command'):
    port, process = server('-m', 'Pyjo.Server.Reload', '-l', 'http://127.0.0.1:{port}', myapp.to_str(), 'prethread')
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    try:
        conn.request('GET', '/thread')
        is_ok(conn.getresponse().read(), b'Pyjo.Server.Prethread', 'served by a thread')
    except OSError:
        ServerStart.report(log, myapp.to_str())
        raise
    finally:
        conn.close()
    status, output = stop(process)
    is_ok(status, 0, 'stopped')

with subtest('pyjo-reload'):
    result = subprocess.run(
        [sys.executable, '-m', 'Pyjo.Server.Reload', '--help'],
        env=dict(os.environ, PYTHONPATH=ROOT),
        capture_output=True,
        text=True,
    )
    # The usage of the section pyjo-reload, as script/morbo dies with its usage
    is_ok(result.returncode, 1, 'help')
    is_ok(result.stderr, extract_usage(Pyjo.Server.Reload.__file__, section='pyjo-reload'), 'usage')
    like_ok(
        result.stderr, r'^Usage: pyjo-reload \[OPTIONS\] APPLICATION \[COMMAND\] \[ARGS\]\n', 'usage of pyjo-reload'
    )
    for option in ('--backend', '--listen', '--log-format', '--mode', '--verbose', '--watch', '--exec'):
        like_ok(result.stderr, rf'{option}', option)

with subtest('new'):
    reload = Pyjo.Server.Reload.new()
    isa_ok(reload, Pyjo.Server.Reload.object, 'reload')
    reload = Pyjo.Server.Reload.new(silent=False)
    is_ok(reload.silent, False, 'silent')

with subtest('backend'):
    backend = reload.backend
    isa_ok(backend, Pyjo.Server.Reload.Backend.Poll.object, 'default')
    reload.backend = Pyjo.Server.Reload.Backend.Poll.new()
    isnt_ok(reload.backend, backend, 'set')

with subtest('daemon'):
    daemon = reload.daemon
    isa_ok(daemon, Pyjo.Server.Daemon.object, 'default')
    reload.daemon = Pyjo.Server.Daemon.new()
    isnt_ok(reload.daemon, daemon, 'set')

with subtest('exec'):
    commands = Pyjo.Server.Reload.new().exec
    is_deeply_ok(commands, [], 'default')
    reload.exec = ['npx webpack --watch', 'npx tailwindcss -i app.css -o public/assets/app.css --watch']
    is_ok(len(reload.exec), 2, 'set')

with subtest('silent'):
    boolean = Pyjo.Server.Reload.new().silent
    is_ok(boolean, True, 'default')
    reload.silent = False
    is_ok(reload.silent, False, 'set')

with subtest('run'):
    code = """
import Pyjo.Server.Reload

reload = Pyjo.Server.Reload.new()
reload.daemon.listen = ['http://127.0.0.1:{port}']
reload.run('myapp.py')
"""
    port, process = server('-c', code, cwd=dir.to_str())
    status, output = stop(process)
    is_ok(status, 0, 'relative path of the application')
    code = code.replace("reload.run('myapp.py')", "reload.run('myapp.py', 'prefork', '-w', '1')")
    port, process = server('-c', code, cwd=dir.to_str())
    status, output = stop(process)
    is_ok(status, 0, 'server command')

with subtest('main'):
    code = f"""
import Pyjo.Server.Reload

Pyjo.Server.Reload.main(['-l', 'http://127.0.0.1:{{port}}', {myapp.to_str()!r}])
"""
    port, process = server('-c', code)
    status, output = stop(process)
    is_ok(status, 0, 'command line interface')
    code = code.replace(f'{myapp.to_str()!r}])', f"{myapp.to_str()!r}, 'prefork', '-w', '2'])")
    port, process = server('-c', code)
    status, output = stop(process)
    is_ok(status, 0, 'server command')

done_testing()
