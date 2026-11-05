from Pyjo.Test import *

import atexit
import http.client
import importlib
import os
import signal
import socket
import subprocess
import sys
import time


if not hasattr(os, 'fork'):
    plan(skip_all='no os.fork')

# PyPy with its JIT on macOS: the child of a fork crashes now and then with a bus error, under load
if sys.platform == 'darwin' and getattr(sys, 'pypy_translation_info', {}).get('translation.jit'):
    plan(skip_all='PyPy with its JIT on macOS: the child of a fork crashes now and then with SIGBUS')

import Pyjo.IOLoop.Server
import Pyjo.Server.Hot
import Pyjo.Server.Prefork
import Pyjo.Server.Prethread

from Pyjo.File import curfile, tempdir
from Pyjo.Util import extract_usage


ROOT = curfile().dirname().dirname().dirname().to_str()
LIB = curfile().dirname().sibling('lib').to_str()
ENV = dict(os.environ, PYTHONPATH=ROOT)

sys.path.insert(0, LIB)
ServerStart = importlib.import_module('ServerStart')


# An application in a directory of its own, for its hot.pid, and its log, which tells what a server that did not
# answer or did not stop has done
def application(port):
    dir = tempdir()
    return dir.child('myapp.py').spew(
        f"""
import sys, threading
sys.path.insert(0, {LIB!r})
from Pyjoyment.Lite import app, get
app.log.path = {dir.child('myapp.log').to_str()!r}
app.log.level = 'trace'
app.config(hot={{'listen': ['http://127.0.0.1:{port}'], 'workers': 1}})
get('/', {{'text': 'Hello!'}})
get('/thread', lambda c: c.render(text=threading.current_thread().name))
app.start()
""".encode()
    )


def pid(app):
    try:
        return int(app.sibling('hot.pid').slurp().strip())
    except (OSError, ValueError):
        return None


def listening(port):
    try:
        socket.create_connection(('127.0.0.1', port), 0.2).close()
        return True
    except OSError:
        return False


def wait_for(condition):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.1)
    return False


# The server of the application, stopped gracefully, and killed when the test ends before it stops it
def stop(app, port):
    manager = pid(app)
    os.kill(manager, signal.SIGTERM)
    if wait_for(lambda: not listening(port) and not os.path.exists(app.sibling('hot.pid'))):
        return True
    diag(f'Manager {manager} alive: {alive(manager)}, listening: {listening(port)}, hot.pid: {pid(app)}')
    ServerStart.report(app.sibling('myapp.log'), app.to_str())
    return False


def get(app, port, path):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    try:
        conn.request('GET', path)
        return conn.getresponse().read().decode()
    except OSError:
        ServerStart.report(app.sibling('myapp.log'), app.to_str())
        raise
    finally:
        conn.close()


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill(app):
    if manager := pid(app):
        try:
            os.kill(manager, signal.SIGQUIT)
        except OSError:
            pass


def command(*args, **kwargs):
    return subprocess.run([sys.executable, *args], env=ENV, capture_output=True, text=True, **kwargs)


# A server started in the background, again on a new port when it is taken
def daemonized(*args, **kwargs):
    def start():
        port = ServerStart.port()
        myapp = application(port)
        atexit.register(kill, myapp)
        names = {'myapp': myapp.to_str(), 'dir': myapp.dirname().to_str()}
        result = command(*(arg.format(**names) for arg in args), **{k: v.format(**names) for k, v in kwargs.items()})
        return None if ServerStart.in_use(result) else (port, myapp, result)

    return ServerStart.retry(start)


with subtest('Synopsis'):
    code = """
from Pyjo.Server.Hot import Hot

hot = Hot()
hot.run({myapp!r})
"""
    port, myapp, result = daemonized('-c', code)
    is_ok(result.returncode, 0, 'daemonized')
    ok(wait_for(lambda: listening(port) and pid(myapp)), 'listening')
    ok(stop(myapp, port), 'stopped')

    # Or import the module, as in Google Python Style Guide

    code = """
import Pyjo.Server.Hot

hot = Pyjo.Server.Hot.new()
hot.run({myapp!r})
"""
    port, myapp, result = daemonized('-c', code)
    is_ok(result.returncode, 0, 'daemonized')
    ok(wait_for(lambda: listening(port) and pid(myapp)), 'listening')
    ok(stop(myapp, port), 'stopped')

with subtest('Description'):
    port, myapp, result = daemonized('-m', 'Pyjo.Server.Hot', '{myapp}')
    is_ok(result.returncode, 0, 'python -m Pyjo.Server.Hot')
    ok(wait_for(lambda: listening(port) and pid(myapp)), 'listening')
    old = pid(myapp)
    result = command('-m', 'Pyjo.Server.Hot', myapp.to_str())
    is_ok(result.stdout, f'Starting hot deployment for Hot server {old}.\n', 'hot deployment')
    ok(wait_for(lambda: pid(myapp) not in (None, old)), 'new manager')
    ok(wait_for(lambda: not alive(old)), 'old manager stopped')
    ok(stop(myapp, port), 'stopped')

with subtest('Settings'):
    hot = Pyjo.Server.Hot.new()
    app = hot.prefork.app
    app.config(hot={'listen': ['http://*:80'], 'workers': 10})
    hot.configure('hot')
    is_deeply_ok(hot.prefork.listen, ['http://*:80'], 'listen')
    is_ok(hot.prefork.workers, 10, 'workers')

with subtest('threads'):
    hot = Pyjo.Server.Hot.new()
    hot.prefork.app.config(hot={'threads': True, 'workers': 2})
    hot.configure('hot')
    isa_ok(hot.prefork, Pyjo.Server.Prethread.object, 'workers are threads')
    is_deeply_ok(hot.prefork.listen, ['http://*:8080'], 'listen')
    is_ok(hot.prefork.workers, 2, 'settings')

    # The option --threads, with a hot deployment
    port, myapp, result = daemonized('-m', 'Pyjo.Server.Hot', '--threads', '{myapp}')
    is_ok(result.returncode, 0, 'python -m Pyjo.Server.Hot --threads')
    ok(wait_for(lambda: listening(port) and pid(myapp)), 'listening')
    is_ok(get(myapp, port, '/thread'), 'Pyjo.Server.Prethread', 'served by a thread')
    old = pid(myapp)
    result = command('-m', 'Pyjo.Server.Hot', '--threads', myapp.to_str())
    is_ok(result.stdout, f'Starting hot deployment for Hot server {old}.\n', 'hot deployment')
    ok(wait_for(lambda: pid(myapp) not in (None, old)), 'new manager')
    ok(wait_for(lambda: not alive(old)), 'old manager stopped')
    is_ok(get(myapp, port, '/thread'), 'Pyjo.Server.Prethread', 'served by a thread of the new manager')
    ok(stop(myapp, port), 'stopped')

    # Without it, a worker process
    port, myapp, result = daemonized('-m', 'Pyjo.Server.Hot', '{myapp}')
    ok(wait_for(lambda: listening(port) and pid(myapp)), 'listening')
    is_ok(get(myapp, port, '/thread'), 'MainThread', 'served by a process')
    ok(stop(myapp, port), 'stopped')

with subtest('pyjo-hot'):
    result = subprocess.run(
        [sys.executable, '-m', 'Pyjo.Server.Hot', '--help'], env=ENV, capture_output=True, text=True
    )
    # The usage of the section pyjo-hot, as script/hypnotoad dies with its usage
    is_ok(result.returncode, 1, 'help')
    is_ok(result.stderr, extract_usage(Pyjo.Server.Hot.__file__, section='pyjo-hot'), 'usage')
    like_ok(result.stderr, r'^Usage: pyjo-hot \[OPTIONS\] \[APPLICATION\]\n', 'usage of pyjo-hot')
    for option in ('--foreground', '--stop', '--test', '--threads'):
        like_ok(result.stderr, rf'{option}', option)

with subtest('new'):
    hot = Pyjo.Server.Hot.new()
    isa_ok(hot, Pyjo.Server.Hot.object, 'hot')
    hot = Pyjo.Server.Hot.new(upgrade_timeout=15)
    is_ok(hot.upgrade_timeout, 15, 'upgrade_timeout')

with subtest('prefork'):
    prefork = hot.prefork
    isa_ok(prefork, Pyjo.Server.Prefork.object, 'default')
    is_deeply_ok(prefork.listen, ['http://*:8080'], 'listen')
    hot.prefork = Pyjo.Server.Prefork.new()
    isnt_ok(hot.prefork, prefork, 'set')

with subtest('upgrade_timeout'):
    timeout = Pyjo.Server.Hot.new().upgrade_timeout
    is_ok(timeout, 180, 'default')
    hot.upgrade_timeout = 15
    is_ok(hot.upgrade_timeout, 15, 'set')

with subtest('configure'):
    hot = Pyjo.Server.Hot.new()
    hot.prefork.app.config(hot={'upgrade_timeout': 45})
    is_ok(hot.configure('hot'), None, 'configured')
    is_ok(hot.upgrade_timeout, 45, 'from the application')

with subtest('run'):
    code = """
import Pyjo.Server.Hot

hot = Pyjo.Server.Hot.new()
hot.run('myapp.py')
"""
    port, myapp, result = daemonized('-c', code, cwd='{dir}')
    is_ok(result.returncode, 0, 'relative path of the application')
    ok(wait_for(lambda: listening(port) and pid(myapp)), 'listening')
    ok(stop(myapp, port), 'stopped')

with subtest('main'):
    # The server is started again on a new port when it is taken
    def start():
        port = ServerStart.port()
        myapp = application(port)
        code = f"""
import Pyjo.Server.Hot

Pyjo.Server.Hot.main(['-f', {myapp.to_str()!r}])
"""
        process = subprocess.Popen([sys.executable, '-c', code], env=ENV, stdout=subprocess.DEVNULL)
        atexit.register(lambda: process.poll() is None and process.kill())
        return (port, myapp, process) if ServerStart.listening(port, process) else None

    port, myapp, process = ServerStart.retry(start)
    ok(wait_for(lambda: listening(port) and pid(myapp)), 'listening')
    process.send_signal(signal.SIGTERM)
    is_ok(process.wait(30), 0, 'command line interface in the foreground')
    ok(not os.path.exists(myapp.sibling('hot.pid')), 'no process id file')

done_testing()
