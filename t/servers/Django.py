import Pyjo.File

from Pyjo.Test import *

import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys


# The project of Django of the guide, and the examples of Django, which Pyjoyment.Plugin.Mount mounts, of the dependency
# group "servers": uv run --only-group servers python -m Pyjo.Prove t/servers
if not importlib.util.find_spec('django'):
    plan(skip_all='needs the dependency group "servers", without django')

# The servers in processes of their own, as the settings of Django are once in a process, and the reactor is chosen
# before Pyjoyment is imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
ServerProcess = importlib.import_module('ServerProcess')
Server = ServerProcess.Server
Skills = importlib.import_module('Skills')

ROOT = Pyjo.File.path(ServerProcess.ROOT)
PROJECT = ROOT.child('docs', 'guides', 'django')
EXAMPLES = ROOT.child('examples', 'servers')
PYTHON = sys.executable
DAEMON = ['daemon', '-l', 'http://127.0.0.1:{port}']

# The API of GitHub, whose latest release of Pyjoyment the examples request
MOCK = """
from Pyjoyment.Lite import *

get('/repos/pyjoyment/Pyjoyment/releases/latest', {'json': {'tag_name': '1.2.3'}})

app.start()
"""


def project(tmp):
    # A copy of the project, with its database, and the files of collectstatic and of / in the parent of STATIC_ROOT
    shutil.copytree(PROJECT.to_str(), tmp.to_str(), dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
    env = os.environ | {'PYTHONPATH': os.pathsep.join([tmp.to_str(), ROOT.to_str()])}
    subprocess.run([PYTHON, 'manage.py', 'migrate', '-v', '0'], cwd=tmp.to_str(), env=env, check=True)
    public = tmp.child('public')
    public.child('static').make_path().child('site.2fcb528ecde1.css').spew('body {}\n')
    public.child('robots.txt').spew('User-agent: *\n')
    return tmp


def body(response):
    return response[2].decode()


# The changes of the sections of ASGI of the guide and of the skill to their script of WSGI
ASGI = (
    (r"\n# A WSGI application blocks.*\nos\.environ\.setdefault\('PYJO_REACTOR', .*\)\n", '\n'),
    (r'(\nfrom django\.conf import settings)', r'\nfrom asgiref.sync import sync_to_async  # noqa: E402\1'),
    (r"checks=\{'database': database\}", "checks={'database': sync_to_async(database)}"),
    (r"'config\.wsgi:application'", "'config.asgi:application'"),
)


def asgi(script):
    for pattern, replacement in ASGI:
        script, count = re.subn(pattern, replacement, script)
        is_ok(count, 1, f'changed {replacement.strip()}')
    return script


with subtest('WSGI on the reactor of Poll'):
    with Pyjo.File.tempdir() as tmp:
        project(tmp)
        # The reactor of the script, not the one of the environment of the test
        server = Server(tmp.to_str(), [PYTHON, '-m', 'config.server', *DAEMON], env={'PYJO_REACTOR': None})
        try:
            is_ok(body(server.request('GET', '/')), '0 notes, http from 127.0.0.1', 'view with a query')
            status, headers, data = server.request(
                'POST', '/notes', 'text=Hello', {'Content-Type': 'application/x-www-form-urlencoded'}
            )
            is_ok(status, 200, 'POST')
            is_deeply_ok(json.loads(data), {'notes': ['Hello']}, 'note saved')
            is_ok(body(server.request('GET', '/')), '1 notes, http from 127.0.0.1', 'note counted')
            is_ok(body(server.request('GET', '/healthz')), 'ok', '/healthz of the project')
            is_ok(server.request('GET', '/livez')[0], 200, '/livez')
            is_ok(server.request('GET', '/readyz?verbose')[0], 200, '/readyz with the database')
            like_ok(body(server.request('GET', '/readyz?verbose')), r'\[\+\]database ok', 'check of the database')
            status, headers, data = server.request('GET', '/static/site.2fcb528ecde1.css')
            is_ok(data, b'body {}\n', 'static file')
            is_ok(headers['Cache-Control'], 'public, max-age=31536000, immutable', 'hashed name cached for a year')
            status, headers, data = server.request('GET', '/robots.txt')
            is_ok(headers['Cache-Control'], 'public, max-age=60', 'file of /')
            is_ok(server.request('GET', '/missing')[0], 404, 'not found of Django')
            is_ok(server.request('GET', '/static/notes/notes.css')[0], 404, 'no files of the apps without DEBUG')

            # The address of the pod as Host, as the kubelet sends it, which ALLOWED_HOSTS rejects
            pod = {'Host': '10.1.2.3:8080'}
            is_ok(server.request('GET', '/healthz', headers=pod)[0], 400, '/healthz of Django with the pod as Host')
            is_ok(server.request('GET', '/readyz', headers=pod)[0], 200, '/readyz with the pod as Host')
            is_ok(server.request('GET', '/livez', headers=pod)[0], 200, '/livez with the pod as Host')
        finally:
            log = server.output()
            server.close()
        like_ok(log, r'\] "GET / HTTP/1\.1" 200 ', 'access log')
        like_ok(log, r':\d\d \+0000\] "GET /', 'time zone of TIME_ZONE')
        unlike_ok(log, r'"GET /(?:livez|readyz)', 'no probes in the access log')

with subtest('Static files of the apps with DEBUG'):
    with Pyjo.File.tempdir() as tmp:
        project(tmp)
        env = {'PYJO_REACTOR': None, 'DJANGO_DEBUG': '1'}
        server = Server(tmp.to_str(), [PYTHON, '-m', 'config.server', *DAEMON], env=env)
        try:
            like_ok(body(server.request('GET', '/static/notes/notes.css')), r'margin: 0', 'file of an app')
            status, headers, data = server.request('GET', '/static/site.2fcb528ecde1.css')
            is_ok(headers['Cache-Control'], 'public, max-age=31536000, immutable', 'collected file of Pyjoyment first')
        finally:
            server.close()

with subtest('Reverse proxy'):
    with Pyjo.File.tempdir() as tmp:
        project(tmp)
        server = Server(tmp.to_str(), [PYTHON, '-m', 'config.server', *DAEMON, '-p'], env={'PYJO_REACTOR': None})
        try:
            headers = {'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '203.0.113.9'}
            is_ok(body(server.request('GET', '/', headers=headers)), '0 notes, https from 203.0.113.9', 'forwarded')
        finally:
            server.close()

with subtest('WSGI on the reactor of asyncio'):
    with Pyjo.File.tempdir() as tmp:
        project(tmp)
        env = {'PYJO_REACTOR': 'Pyjo.Reactor.Asyncio'}
        server = Server(tmp.to_str(), [PYTHON, '-m', 'config.server', *DAEMON], env=env)
        try:
            is_ok(server.request('GET', '/')[0], 500, 'query in the event loop of asyncio')
            is_ok(body(server.request('GET', '/healthz')), 'ok', 'view without a query')
            is_ok(server.request('GET', '/readyz')[0], 503, 'check of the database fails')
        finally:
            log = server.output()
            server.close()
        like_ok(log, r'You cannot call this from an async context', 'SynchronousOnlyOperation')

with subtest('ASGI'):
    with Pyjo.File.tempdir() as tmp:
        project(tmp)
        # The script of the guide with the changes of its section of ASGI
        script = asgi(tmp.child('config', 'server.py').slurp().decode())
        tmp.child('config', 'server_asgi.py').spew(script)
        server = Server(tmp.to_str(), [PYTHON, '-m', 'config.server_asgi', *DAEMON], env={'PYJO_REACTOR': None})
        try:
            is_ok(body(server.request('GET', '/')), '0 notes, http from 127.0.0.1', 'view with a query in a thread')
            is_ok(server.request('GET', '/readyz')[0], 200, 'check of the database in a thread')
        finally:
            server.close()

with subtest('Examples'):
    with Pyjo.File.tempdir() as tmp:
        tmp.child('mock.py').spew(MOCK)
        mock = Server(tmp.to_str(), [PYTHON, 'mock.py', *DAEMON])
        try:
            env = {'PYJO_REACTOR': None, 'GITHUB_API_URL': f'http://127.0.0.1:{mock.port}'}
            for name in ('django_wsgi.py', 'django_asgi.py'):
                with Pyjo.File.tempdir() as dir:
                    server = Server(dir.to_str(), [PYTHON, EXAMPLES.child(name).to_str(), *DAEMON], env=env)
                    try:
                        is_ok(body(server.request('GET', '/')), 'Hello from Django at /!', f'{name}: view')
                        status, headers, data = server.request('GET', '/release')
                        is_deeply_ok(json.loads(data), {'status': 200, 'release': '1.2.3'}, f'{name}: user agent')
                    finally:
                        server.close()
        finally:
            mock.close()

with subtest('Skill'):
    # The script and the views of the skill django, which request the mock of the API of GitHub, the script on WSGI with
    # the workers of prefork, and on ASGI
    script, views = Skills.blocks('django')
    with Pyjo.File.tempdir() as tmp:
        tmp.child('mock.py').spew(MOCK)
        mock = Server(tmp.to_str(), [PYTHON, 'mock.py', *DAEMON])
        try:
            with Pyjo.File.tempdir() as dir:
                project(dir)
                dir.child('config', 'server.py').spew(script)
                dir.child('config', 'server_asgi.py').spew(asgi(script))
                dir.child('releases.py').spew(views.replace('https://api.github.com', f'http://127.0.0.1:{mock.port}'))
                urls = dir.child('config', 'urls.py')
                urls.spew(
                    urls.slurp().decode()
                    + '\nfrom releases import release, release_async  # noqa: E402\n\n'
                    + "urlpatterns += [path('release', release), path('release-async', release_async)]\n"
                )
                prefork = ['prefork', '-w', '2', '-c', '1', '-r', '1', '-l', 'http://127.0.0.1:{port}']
                for module, command, path in (
                    ('config.server', prefork if sys.platform != 'win32' else DAEMON, '/release'),
                    ('config.server_asgi', DAEMON, '/release-async'),
                ):
                    server = Server(dir.to_str(), [PYTHON, '-m', module, *command], env={'PYJO_REACTOR': None})
                    try:
                        is_ok(server.request('GET', '/readyz')[0], 200, f'{module}: /readyz')
                        status, headers, data = server.request('GET', path)
                        is_deeply_ok(json.loads(data), {'release': '1.2.3'}, f'{module}: {path}')
                        is_ok(headers['Connection'], 'close' if 'prefork' in command else None, f'{module}: connection')
                        is_ok(
                            server.request('GET', '/static/site.2fcb528ecde1.css')[1]['Cache-Control'],
                            'public, max-age=31536000, immutable',
                            f'{module}: static file',
                        )
                    finally:
                        server.close()
        finally:
            mock.close()

done_testing()
