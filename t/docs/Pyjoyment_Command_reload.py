from Pyjo.Test import *

import atexit
import contextlib
import http.client
import importlib
import io
import os
import re
import signal
import subprocess
import sys
import time

from unittest.mock import patch


if not hasattr(os, 'fork'):
    plan(skip_all='Pyjo.Server.Reload does not support Windows')

# PyPy with its JIT on macOS: the child of a fork crashes now and then with a bus error, under load
if sys.platform == 'darwin' and getattr(sys, 'pypy_translation_info', {}).get('translation.jit'):
    plan(skip_all='PyPy with its JIT on macOS: the child of a fork crashes now and then with SIGBUS')

import Pyjo.Home
import Pyjo.Server.Reload
import Pyjoyment
import Pyjoyment.Command.reload

from Pyjo.File import curfile, tempdir


ROOT = curfile().dirname().dirname().dirname().to_str()
LIB = curfile().dirname().sibling('lib').to_str()

sys.path.insert(0, LIB)
ServerStart = importlib.import_module('ServerStart')

# A shorter timeout of the backend, which waits for changes as long as it
os.environ['PYJO_RELOAD_TIMEOUT'] = '0.25'

dir = tempdir()
log = dir.child('reload.log')

myapp = dir.child('myapp.py')


def lite(text):
    myapp.spew(f"from Pyjoyment.Lite import app, get\nget('/', {{'text': {text!r}}})\napp.start()\n".encode())
    _touch(myapp)


# The package of an application in the directory of its project, which python -m runs, as generate app makes it
project = dir.child('project').make_path()
package = project.child('MyReloadApp').make_path()
package.child('__main__.py').spew(b"import Pyjoyment.Commands\n\nPyjoyment.Commands.start_app('MyReloadApp')\n")
controller = package.child('Example.py')


def application(text):
    package.child('__init__.py').spew(
        b'import Pyjoyment\n\n\nclass MyReloadApp(Pyjoyment.object):\n'
        b"    def startup(self):\n        self.routes.get('/').to('Example#welcome')\n\n\n"
        b'new = MyReloadApp.new\nobject = MyReloadApp\n'
    )
    controller.spew(
        f'import Pyjoyment.Controller\n\n\nclass Example(Pyjoyment.Controller.object):\n'
        f'    def welcome(self):\n        self.render(text={text!r})\n\n\nnew = Example.new\nobject = Example\n'.encode()
    )
    _touch(controller)


# A change in the same second as the file was written, which the size of the file does not tell, gets a newer time
def _touch(file):
    mtime = time.time() + 2
    os.utime(file, (mtime, mtime))


# A server in a process of its own, on a port that the arguments name as {port}, until the port accepts connections,
# started again on a new port when it is taken, and ended when the test ends before it stops it
def server(*args, cwd=None):
    def start():
        port = ServerStart.port()
        with open(log, 'ab') as handle:
            process = subprocess.Popen(
                [sys.executable, *(arg.format(port=port) for arg in args)],
                cwd=cwd,
                env=dict(os.environ, PYTHONPATH=ROOT, TMPDIR=dir.to_str()),
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
        atexit.register(end, process)
        if ServerStart.listening(port, process):
            return port, process
        return None

    return ServerStart.retry(start)


def end(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()


def get(port):
    # The connection is closed also when the request fails, as PyPy would close it only with its garbage collector
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    try:
        conn.request('GET', '/')
        return conn.getresponse().read()
    except OSError:
        return None
    finally:
        conn.close()


def answers(port, body):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if get(port) == body:
            return True
        time.sleep(0.1)
    ServerStart.report(log, myapp.to_str())
    return False


def stop(process):
    process.send_signal(signal.SIGINT)
    return process.wait(30)


with subtest('Synopsis'):
    app = Pyjoyment.new()
    reload = Pyjoyment.Command.reload.new(app=app)
    like_ok(
        reload.usage, r'^Usage: APPLICATION reload \[OPTIONS\] \[COMMAND\] \[ARGS\]\n\n  \./myapp\.py reload\n', 'usage'
    )

    # ./myapp.py reload
    lite('Hello Reload!')
    port, process = server(myapp.to_str(), 'reload', '-l', 'http://127.0.0.1:{port}')
    ok(answers(port, b'Hello Reload!'), 'started')
    lite('Hello Again!')
    ok(answers(port, b'Hello Again!'), 'restarted when the script changes')
    is_ok(stop(process), 0, 'stopped')

    # ./myapp.py reload prefork -w 1
    port, process = server(myapp.to_str(), 'reload', '-l', 'http://127.0.0.1:{port}', 'prefork', '-w', '1')
    ok(answers(port, b'Hello Again!'), 'server command with its arguments')
    is_ok(stop(process), 0, 'stopped')

    # ./myapp.py reload -l http://127.0.0.1:8080 -w assets/css prefork -w 3
    server_ = reload.build_server('-l', 'http://127.0.0.1:8080', '-w', 'assets/css')
    is_deeply_ok(server_.daemon.listen, ['http://127.0.0.1:8080'], 'listen')
    is_deeply_ok(server_.backend.watch, ['assets/css'], 'watch')
    is_ok(server_.silent, True, 'silent')

    # ./myapp.py reload -m production -l https://*:443 -l http://[::]:3000
    server_ = reload.build_server('-l', 'https://*:443', '-l', 'http://[::]:3000')
    is_deeply_ok(server_.daemon.listen, ['https://*:443', 'http://[::]:3000'], 'listen twice')

    # ./myapp.py reload -w /usr/local/lib -w public -w myapp.conf
    server_ = reload.build_server('-w', '/usr/local/lib', '-w', 'public', '-w', 'myapp.conf')
    is_deeply_ok(server_.backend.watch, ['/usr/local/lib', 'public', 'myapp.conf'], 'watch three')

    # ./myapp.py reload -x 'npx webpack --watch'
    server_ = reload.build_server('-x', 'npx webpack --watch', '-v')
    is_deeply_ok(server_.exec, ['npx webpack --watch'], 'exec')
    is_ok(server_.silent, False, 'verbose')

    # python -m MyApp reload
    application('Hello Package!')
    port, process = server('-m', 'MyReloadApp', 'reload', '-l', 'http://127.0.0.1:{port}', cwd=project.to_str())
    ok(answers(port, b'Hello Package!'), 'package started')
    application('Hello Controller!')
    ok(answers(port, b'Hello Controller!'), 'restarted when a module of the package changes')
    is_ok(stop(process), 0, 'stopped')

with subtest('Options'):
    with patch.dict(os.environ):
        server_ = reload.build_server('-b', 'Poll')
        is_ok(os.environ.get('PYJO_RELOAD_BACKEND'), 'Poll', 'backend')
        isa_ok(server_, Pyjo.Server.Reload.object, 'server')
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        throws_ok(lambda: reload.build_server('--unknown'), re.compile(r'^Usage: APPLICATION reload'), 'usage')
    like_ok(stderr.getvalue(), r'^Unknown option: unknown', 'warning')

with subtest('Watch'):
    is_deeply_ok(reload.build_server().backend.watch, ['lib', 'templates'], 'not the package outside of the home')
    sys.path.insert(0, project.to_str())
    try:
        app = importlib.import_module('MyReloadApp').object.new()
        app.home = Pyjo.Home.new(project.to_str())
        watch = Pyjoyment.Command.reload.new(app=app).build_server().backend.watch
        is_deeply_ok(watch, ['lib', 'templates', package.to_str()], 'the package in the home')
        app.home = Pyjo.Home.new(dir.child('elsewhere').to_str())
        watch = Pyjoyment.Command.reload.new(app=app).build_server().backend.watch
        is_deeply_ok(watch, ['lib', 'templates'], 'not the package outside of another home')
    finally:
        sys.path.remove(project.to_str())

with subtest('Attributes'):
    reload = Pyjoyment.Command.reload.new()
    like_ok(reload.description, r'Start application', 'description')
    reload.usage = 'Foo'
    is_ok(reload.usage, 'Foo', 'usage')
    with patch.dict(os.environ, {'PYJO_EXE': myapp.to_str()}):
        is_ok(reload.script, myapp.to_str(), 'script of PYJO_EXE')
    with patch.dict(os.environ), patch.object(sys, 'argv', ['/srv/MyApp/__main__.py']):
        os.environ.pop('PYJO_EXE', None)
        is_ok(reload.script, '/srv/MyApp/__main__.py', 'script of sys.argv')

with subtest('run'):
    with patch.dict(os.environ), patch.object(sys, 'argv', ['-c']):
        os.environ.pop('PYJO_EXE', None)
        throws_ok(
            lambda: Pyjoyment.Command.reload.new().run(),
            re.compile(r"Can't find the script of the application"),
            'no script',
        )

done_testing()
