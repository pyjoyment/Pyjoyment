import Pyjo.File
import Pyjo.Home
import Pyjoyment
import Pyjoyment.Command.Author.generate.dockerfile

from Pyjo.Test import *

import contextlib
import io
import os
import re
import sys


cwd = Pyjo.File.path()
exe = os.environ.pop('PYJO_EXE', None)
python = f'{sys.version_info.major}.{sys.version_info.minor}'


def generate(dir, *args):
    os.chdir(dir)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            dockerfile.run(*args)
    finally:
        os.chdir(cwd)
    return dir.child('Dockerfile').slurp().decode()


with subtest('Synopsis'):
    application = Pyjoyment.new()
    dockerfile = Pyjoyment.Command.Author.generate.dockerfile.new(app=application)
    like_ok(
        dockerfile.usage,
        r'^Usage: APPLICATION generate dockerfile \[OPTIONS\]\n\n  \./myapp\.py generate dockerfile\n',
        'usage',
    )
    like_ok(dockerfile.usage, r'-u, --user <name>', 'option')
    like_ok(dockerfile.usage, r'-p, --port <port>', 'option of the port')
    like_ok(dockerfile.usage, r'-G, --graceful-timeout <seconds>', 'option of the graceful timeout')

    # python -m MyApp generate dockerfile
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    content = generate(tmp)
    like_ok(content, r'(?m)^COPY pyproject\.toml \./$', 'pyproject.toml')
    like_ok(content, r'(?m)^RUN uv sync --no-install-project$', 'dependencies')
    like_ok(content, r'(?m)^CMD \["python", "-m", "Pyjoyment", "prefork"\]$', 'package of the application')
    unlike_ok(content, r'USER', 'no user')

    # python -m MyApp generate dockerfile --user app
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    content = generate(tmp, '--user', 'app')
    like_ok(content, r'(?m)^RUN useradd --system app\nUSER app$', 'user')

    # python -m MyApp generate dockerfile --port 8080
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    content = generate(tmp, '--port', '8080')
    like_ok(content, r'(?m)^ARG PORT=8080\nENV PORT=\$\{PORT\}\nEXPOSE \$\{PORT\}$', 'port')

    # python -m MyApp generate dockerfile --graceful-timeout 8
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    content = generate(tmp, '--graceful-timeout', '8')
    like_ok(content, r'(?m)^ENV PYJO_GRACEFUL_TIMEOUT=8$', 'graceful timeout')

    # python -m MyApp generate dockerfile --compress public
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    content = generate(tmp, '--compress', 'public')
    like_ok(content, r'(?m)^RUN find public -type f -size \+859c \\$', 'variants')

    # python -m MyApp generate dockerfile --apt-package brotli --apt-package zstd --compress public
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    content = generate(tmp, '--apt-package', 'brotli', '--apt-package', 'zstd', '--compress', 'public')
    like_ok(content, r'(?m)^    && apt-get install --yes --no-install-recommends brotli zstd \\$', 'packages')
    like_ok(content, r'(?m)^    && if command -v brotli >/dev/null; then brotli ', 'brotli variants')

    # python -m MyApp generate dockerfile --apt-package brotli --compress public --compress-encoding br --compress-encoding gzip
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    content = generate(
        tmp,
        '--apt-package',
        'brotli',
        '--compress',
        'public',
        '--compress-encoding',
        'br',
        '--compress-encoding',
        'gzip',
    )
    like_ok(content, r"(?m)^    -exec sh -c 'brotli .*\n    && gzip .*' sh \{\} \+$", 'encodings')
    unlike_ok(content, r'zstd', 'no other encoding')

    # ./myapp.py generate dockerfile
    tmp = Pyjo.File.tempdir()
    tmp.child('myapp.py').spew('')
    tmp.child('pyproject.toml').spew('[project]\nname = "myapp"\n')
    application.home = Pyjo.Home.new(tmp.to_str())
    os.environ['PYJO_EXE'] = tmp.child('myapp.py').to_str()
    try:
        content = generate(tmp)
    finally:
        os.environ.pop('PYJO_EXE', None)
    like_ok(content, r'(?m)^COPY pyproject\.toml \./$', 'pyproject.toml of the script')
    like_ok(content, r'(?m)^CMD \["python", "myapp\.py", "prefork"\]$', 'script of the application')

with subtest('Description'):
    application = Pyjoyment.new()
    dockerfile = Pyjoyment.Command.Author.generate.dockerfile.new(app=application)
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    tmp.child('uv.lock').spew('')
    content = generate(tmp)
    stages = re.findall(r'(?m)^FROM .*$', content)
    is_deeply_ok(stages, [f'FROM python:{python}-slim AS builder', f'FROM python:{python}-slim'], 'two stages')
    like_ok(content, r'(?m)^COPY --from=ghcr\.io/astral-sh/uv:(?:\d+\.\d+\.\d+|latest) /uv /bin/$', 'uv')
    like_ok(content, r'(?m)^COPY pyproject\.toml uv\.lock \./\nRUN uv sync --no-install-project --locked$', 'uv.lock')
    like_ok(content, r'(?s)AS builder\n.*\bUV_NO_DEV=1\b.*\nFROM python', 'uv in the first stage')
    like_ok(content.split(f'FROM python:{python}-slim\n')[1], r'(?s)\A(?!.*\buv\b)', 'no uv in the second stage')
    like_ok(tmp.child('.dockerignore').slurp().decode(), r'(?m)^\.venv$', '.dockerignore')

    tmp = Pyjo.File.tempdir()
    tmp.child('myapp.py').spew('# /// script\n# dependencies = ["Pyjoyment"]\n# ///\n')
    tmp.child('myapp.py.lock').spew('')
    application.home = Pyjo.Home.new(tmp.to_str())
    os.environ['PYJO_EXE'] = tmp.child('myapp.py').to_str()
    try:
        content = generate(tmp)
    finally:
        os.environ.pop('PYJO_EXE', None)
    like_ok(
        content,
        r'(?m)^COPY myapp\.py myapp\.py\.lock \./\nRUN uv venv && uv sync --script myapp\.py --active --locked$',
        'lock of the script',
    )

with subtest('Attributes'):
    dockerfile = Pyjoyment.Command.Author.generate.dockerfile.new()
    patterns = dockerfile.compress_patterns
    ok('*.css' in patterns and '*.js' in patterns, 'formats of text')
    ok('*.png' not in patterns and '*.pdf' not in patterns, 'not the formats compressed already')
    dockerfile.compress_patterns = ('*.css', '*.js')
    is_ok(dockerfile.compress_patterns, ('*.css', '*.js'), 'patterns')
    is_ok(dockerfile.description, 'Generate "Dockerfile"', 'description')
    like_ok(dockerfile.usage, r'generate dockerfile', 'usage')

if exe is not None:
    os.environ['PYJO_EXE'] = exe

done_testing()
