import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Reactor.Asyncio

from Pyjo.Test import *

import importlib
import os
import re
import subprocess
import sys


# The project of plugins/pyjoyment/skills/mount/SKILL.md, each block of code in the file that its first comment with a
# path names, as a coding agent writes it, whose application runs its command get, which requests it without a server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Skills = importlib.import_module('Skills')

root = Pyjo.File.curfile().dirname().dirname().dirname()
env = dict(os.environ)
env['PYTHONPATH'] = os.pathsep.join([root.to_str(), *filter(None, [env.get('PYTHONPATH')])])
env['PYJO_LOG_LEVEL'] = 'fatal'

tmp = Pyjo.File.tempdir()
names = []
for code in Skills.blocks('mount'):
    names.append(re.search(r'^# (\S+\.py)$', code, re.M)[1])
    file = tmp.child(*names[-1].split('/'))
    file.dirname().make_path()
    file.spew(code)
is_deeply_ok(sorted(names), ['app.py', 'cgi-bin/hello.py', 'legacy.py', 'realtime.py'], 'files of the project')
tmp.child('cgi-bin', 'hello.py').chmod(0o755)


def get(path):
    p = subprocess.run(
        [sys.executable, 'app.py', 'get', path], cwd=tmp.to_str(), env=env, capture_output=True, text=True, timeout=60
    )
    return p.stdout.rstrip('\n')


with subtest('Routes of Pyjoyment'):
    is_ok(get('/new'), 'New in Pyjoyment', 'new route')

with subtest('WSGI'):
    is_ok(get('/old/page'), 'Legacy at  for /old/page', 'the rest of the paths')
    is_ok(get('/'), 'Legacy at  for /', 'root')

with subtest('ASGI'):
    if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
        skip('needs Pyjo.Reactor.Asyncio, which runs an ASGI application', 1)
    else:
        is_ok(get('/realtime/events'), 'ASGI at /realtime for /realtime/events', 'prefix')

with subtest('CGI'):
    if sys.platform == 'win32':
        skip('Windows has no pipes that the event loop watches', 1)
    else:
        is_ok(get('/cgi-bin/hello.py/x'), 'CGI at /cgi-bin/hello.py for /x', 'program')

with subtest('Static files'):
    static = tmp.child('public', 'static').make_path()
    static.child('site.2fcb528ecde1.css').spew('body {}\n')
    static.child('site.css').spew('body {}\n')
    p = subprocess.run(
        [sys.executable, 'app.py', 'get', '-v', '/static/site.2fcb528ecde1.css'],
        cwd=tmp.to_str(),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    like_ok(p.stdout + p.stderr, r'(?m)^Cache-Control: public, max-age=31536000, immutable\r?$', 'hashed name')
    p = subprocess.run(
        [sys.executable, 'app.py', 'get', '-v', '/static/site.css'],
        cwd=tmp.to_str(),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    like_ok(p.stdout + p.stderr, r'(?m)^Cache-Control: public, max-age=60\r?$', 'other files')
    is_ok(get('/favicon.ico'), 'Legacy at  for /favicon.ico', 'favicon of the mounted application')

done_testing()
