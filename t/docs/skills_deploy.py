import Pyjo.File
import Pyjo.Test.Pyjo

from Pyjo.Test import *

import importlib
import os
import re
import subprocess
import sys


# The application of plugins/pyjoyment/skills/deploy/SKILL.md in the file that its first line names, as a coding agent
# writes it, with its probes, and the generators and the options of the servers that the skill names
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Skills = importlib.import_module('Skills')

root = Pyjo.File.curfile().dirname().dirname().dirname()
env = dict(os.environ)
env['PYTHONPATH'] = os.pathsep.join([root.to_str(), *filter(None, [env.get('PYTHONPATH')])])
env['PYJO_LOG_LEVEL'] = 'fatal'

tmp = Pyjo.File.tempdir()
(code,) = Skills.blocks('deploy')
app = tmp.child(re.match(r'# (\S+)\n', code)[1]).spew(code)
is_ok(app.basename(), 'app.py', 'application')


def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=tmp.to_str(), env=env, capture_output=True, text=True, timeout=60)
    return p.stdout, p.returncode


with subtest('Probes'):
    t = Pyjo.Test.Pyjo.new(app)
    t.app.log.level = 'fatal'
    t.get_ok('/').status_is(200).content_is('Hello from development')
    t.get_ok('/livez').status_is(200).content_is('ok')
    t.get_ok('/healthz').status_is(200)
    t.get_ok('/readyz').status_is(200).content_is('ok')

with subtest('Generators'):
    for generator in (['pyproject'], ['dockerfile', '-p', '8080'], ['kubernetes', '-i', 'myapp']):
        stdout, status = run('app.py', 'generate', *generator)
        is_ok(status, 0, f'generate {generator[0]}')
    ok(os.path.isfile(tmp.child('pyproject.toml').to_str()), 'pyproject.toml')
    dockerfile = tmp.child('Dockerfile').slurp().decode()
    like_ok(dockerfile, r'CMD \["python", "app.py", "prefork"\]', 'prefork')
    like_ok(dockerfile, r'HEALTHCHECK .*/livez', 'HEALTHCHECK of /livez')
    for name in ('base/kustomization.yaml', 'dev/kustomization.yaml', 'prod/kustomization.yaml'):
        ok(os.path.isfile(tmp.child('kubernetes', *name.split('/')).to_str()), f'kubernetes/{name}')
    like_ok(tmp.child('kubernetes', 'base', 'probes.yaml').slurp().decode(), r'/readyz', 'readiness probe')

with subtest('Options of the servers'):
    stdout, status = run('app.py', 'prefork', '--help')
    for option in ('-w, --workers', '-l, --listen', '-p, --proxy', '-G, --graceful-timeout', '-S, --shutdown-delay'):
        like_ok(stdout, re.escape(option), option)
    stdout, status = run('app.py', 'generate', 'dockerfile', '--help')
    for option in ('-p, --port', '-G, --graceful-timeout', '-t, --target', '-u, --user', '-c, --compress'):
        like_ok(stdout, re.escape(option), option)

with subtest('Precompressed static files'):
    skill = Skills.read('deploy')
    t = Pyjo.Test.Pyjo.new(app)
    t.app.log.level = 'fatal'
    is_ok(
        re.search(r'`app\.static\.encodings`, `(\{[^`]+\})` by', skill)[1],
        repr(t.app.static.encodings),
        'default encodings',
    )
    tmp.child('Dockerfile').remove()
    stdout, status = run('app.py', 'generate', 'dockerfile', '--compress', 'public')
    is_ok(status, 0, 'generate dockerfile --compress')
    dockerfile = tmp.child('Dockerfile').slurp().decode()
    like_ok(dockerfile, r'RUN find public .*\n.*\n +-exec gzip -k -f -9 -n', 'gzip variants in the image')
    for ext in ('css', 'js', 'mjs', 'json', 'map', 'svg', 'html', 'txt', 'csv', 'xml', 'wasm', 'ttf', 'otf'):
        like_ok(dockerfile, rf"-name '\*\.{ext}'", f'{ext} compressed')
    for ext in ('png', 'jpg', 'gif', 'webp', 'avif', 'mp4', 'woff', 'woff2', 'pdf', 'zip', 'gz'):
        unlike_ok(dockerfile, rf"-name '\*\.{ext}'", f'{ext} not compressed')

    # The commands of the skill on files of the formats that it compresses and leaves out
    public = tmp.child('public').make_path()
    public.child('app.css').spew('body { color: #333 }\n' * 100)
    public.child('app.js').spew('alert(1);\n' * 10)
    public.child('logo.png').spew(b'\x89PNG\r\n' * 300)
    (command,) = (b for b in Skills.blocks('deploy', 'sh') if b.startswith('find '))
    command = command.split('\n')[0].rstrip(' \\') + ' -exec gzip -k -f -9 -n {} +'
    if os.name == 'nt':
        # The find of Windows is not the one of POSIX
        public.child('app.css.gz').spew('gzip')
    else:
        p = subprocess.run(['sh', '-c', command], cwd=tmp.to_str(), capture_output=True, text=True, timeout=60)
        is_ok(p.returncode, 0, 'find of the skill')
    ok(os.path.isfile(public.child('app.css.gz').to_str()), 'variant of a stylesheet')
    ok(not os.path.exists(public.child('app.js.gz').to_str()), 'no variant of a small file')
    ok(not os.path.exists(public.child('logo.png.gz').to_str()), 'no variant of an image')

    t.app.static.paths = [public.to_str()]
    t.ua.transactor.compressed = False
    (
        t.get_ok('/app.css', {'Accept-Encoding': 'br, zstd, gzip'})
        .status_is(200)
        .header_is('Content-Encoding', 'gzip')
        .header_like('Content-Type', r'^text/css')
        .header_is('Vary', 'Accept-Encoding')
    )

done_testing()
