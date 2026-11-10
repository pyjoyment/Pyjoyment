import Pyjo.File
import Pyjo.IOLoop
import Pyjo.Log
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
    for option in (
        '-p, --port',
        '-G, --graceful-timeout',
        '-t, --target',
        '-u, --user',
        '-c, --compress',
        '-a, --apt-package',
    ):
        like_ok(stdout, re.escape(option), option)
    stdout, status = run('app.py', 'generate', 'lambda-zip', '--help')
    like_ok(stdout, re.escape('-c, --compress'), '-c, --compress of lambda-zip')
    like_ok(stdout, re.escape('-e, --compress-encoding'), '-e, --compress-encoding of lambda-zip')

with subtest('Access log'):
    skill = Skills.read('deploy')
    section = re.search(r'^## Access log\n(.*?)^## ', skill, re.M | re.S)[1]
    (example,) = re.findall(r'^```text\n(.*?)\n```$', section, re.M | re.S)
    like_ok(example, r'^\S+ - - \[\d\d/\w{3}/\d{4}:\d\d:\d\d:\d\d \+0000\] "GET / HTTP/1\.1" 200 \d+ "-" ".+"$', 'line')
    calls = re.findall(r"`(plugin\('AccessLog'.*?\))`", section)
    is_ok(len(calls), 4, 'calls of the plugin')
    for call in calls:
        t = Pyjo.Test.Pyjo.new(app)
        t.app.log.level = 'fatal'
        # The plugin of the call, whose lines go to a log of the test, not to the output of the test
        log = Pyjo.Log.new()
        code = call.replace('log=app.log', 'log=log') if 'log=app.log' in call else call[:-1] + ', log=log)'
        eval(code, {'plugin': t.app.plugin, 'log': log})
        with log.capture() as messages:
            t.get_ok('/missing' if 'status=' in call else '/', {'X-Envoy-External-Address': '203.0.113.7'})
            while not len(messages):
                Pyjo.IOLoop.timer(0.01, lambda loop: None)
                Pyjo.IOLoop.one_tick()
        like_ok(messages[0], r'"GET /(?:missing)? HTTP/1\.1" (?:200|404) ', call)
    for option in ('format=', 'duration=True', 'exclude=', 'status=', 'log='):
        like_ok(section, re.escape(option), f'option {option}')

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
    like_ok(dockerfile, r"RUN find public .*\n.*\n +-exec sh -c 'gzip -k -f -9 -n", 'gzip variants in the image')
    like_ok(dockerfile, r'command -v brotli .* brotli -k -f -q 11', 'brotli variants if the image has it')
    like_ok(dockerfile, r'command -v zstd .* zstd -q -k -f -19', 'zstd variants if the image has it')
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

with subtest('Cache-Control'):
    skill = Skills.read('deploy')
    immutable = re.search(r"`app\.static\.immutable`.*?`r'(.+?)'`", skill, re.S)[1]
    cache_control = re.search(r"`app\.static\.cache_control`.*?`'(.+?)'`", skill, re.S)[1]
    t = Pyjo.Test.Pyjo.new(app)
    t.app.log.level = 'fatal'
    t.app.mode = 'production'
    public = Pyjo.File.tempdir()
    public.child('assets').make_path().child('app.ab1234cd.js').spew('alert(1);\n')
    public.child('robots.txt').spew('User-agent: *\n')
    t.app.static.paths = [public.to_str()]
    t.app.static.immutable = immutable
    t.app.static.cache_control = cache_control
    t.get_ok('/assets/app.ab1234cd.js').status_is(200).header_is('Cache-Control', 'public, max-age=31536000, immutable')
    t.get_ok('/robots.txt').status_is(200).header_is('Cache-Control', 'public, max-age=60')

done_testing()
