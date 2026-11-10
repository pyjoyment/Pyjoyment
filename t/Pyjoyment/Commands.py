import Pyjo.File

from Pyjo.Test import *

import contextlib
import gc
import importlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import sysconfig
import types
import zipfile


# Renamed from Mojolicious: PYJO_WSGI, as WSGI has no environment variable of its own, where Mojo has PLACK_ENV
os.environ.pop('PYJO_WSGI', None)
# Not in Mojolicious: PYJO_ASGI, as ASGI has no environment variable of its own
os.environ.pop('PYJO_ASGI', None)
# Not in Mojolicious: AWS_LAMBDA_RUNTIME_API, of the runtime of AWS Lambda
os.environ.pop('AWS_LAMBDA_RUNTIME_API', None)
# Left out from Mojolicious: MOJO_REACTOR, as the tests run on the reactor of Pyjo.Reactor.detect()

# Renamed from Mojolicious: the modules of the tests are in tt/lib, where Mojo has them in t/mojolicious/lib
sys.path.insert(0, Pyjo.File.path(__file__).to_abs().dirname().dirname().dirname().child('tt', 'lib').to_str())


# Not in Mojolicious: local of the environment
@contextlib.contextmanager
def local(**env):
    saved = {name: os.environ.get(name) for name in env}
    for name, value in env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# Not in Mojolicious: local *STDOUT, with the output as bytes, which get writes as Mojo prints them
@contextlib.contextmanager
def stdout():
    buffer = io.BytesIO()
    wrapper = io.TextIOWrapper(buffer, write_through=True)
    try:
        with contextlib.redirect_stdout(wrapper):
            yield buffer
    finally:
        wrapper.detach()


# Make sure @ARGV is not changed
# Not in Mojolicious: the option --log-format
with local(PYJO_MODE=None, PYJO_LOG_FORMAT=None):
    argv = sys.argv
    try:
        sys.argv = [argv[0], '-m', 'production', '--log-format', 'json', '-x', 'whatever']
        import Pyjoyment.Commands

        is_ok(os.environ.get('PYJO_MODE'), 'production', 'right mode')
        is_ok(os.environ.get('PYJO_LOG_FORMAT'), 'json', 'right log format')
        is_deeply_ok(sys.argv[1:], ['-m', 'production', '--log-format', 'json', '-x', 'whatever'], 'unchanged')
    finally:
        sys.argv = argv

# Not in Mojolicious: the packages Mojolicious::Command::my_fake_test_command and my_test_command of the Perl test are
# modules in sys.modules, where the commands find them, after the check of sys.argv, as importing Pyjoyment.Command
# imports Pyjoyment.Commands
import Pyjoyment.Command  # noqa: E402
import Pyjoyment.Command.asgi  # noqa: E402
import Pyjoyment.Command.Author.generate  # noqa: E402
import Pyjoyment.Command.Author.generate.app  # noqa: E402
import Pyjoyment.Command.Author.generate.dockerfile  # noqa: E402
import Pyjoyment.Command.Author.generate.kubernetes  # noqa: E402
import Pyjoyment.Command.Author.generate.lambda_zip  # noqa: E402
import Pyjoyment.Command.Author.generate.lite_app  # noqa: E402
import Pyjoyment.Command.Author.generate.plugin  # noqa: E402
import Pyjoyment.Command.Author.generate.pyproject  # noqa: E402
import Pyjoyment.Command.Author.inflate  # noqa: E402
import Pyjoyment.Command.cgi  # noqa: E402
import Pyjoyment.Command.daemon  # noqa: E402
import Pyjoyment.Command.eval  # noqa: E402
import Pyjoyment.Command.fastcgi  # noqa: E402
import Pyjoyment.Command.get  # noqa: E402
import Pyjoyment.Command.prefork  # noqa: E402
import Pyjoyment.Command.routes  # noqa: E402
import Pyjoyment.Command.stdio  # noqa: E402
import Pyjoyment.Command.version  # noqa: E402
import Pyjoyment.Command.wsgi  # noqa: E402

import PyjoymentTest  # noqa: E402  # pyright: ignore[reportMissingImports]


sys.modules['Pyjoyment.Command.my_fake_test_command'] = types.ModuleType('Pyjoyment.Command.my_fake_test_command')


class Pyjoyment_Command_my_test_command(Pyjoyment.Command.object):
    description = 'See, it works'


sys.modules['Pyjoyment.Command.my_test_command'] = types.ModuleType('Pyjoyment.Command.my_test_command')
sys.modules['Pyjoyment.Command.my_test_command'].object = Pyjoyment_Command_my_test_command

# Environment detection
commands = Pyjoyment.Commands.new()
with local(PYJO_WSGI='production'):
    is_ok(commands.detect(), 'wsgi', 'right environment')
# Not in Mojolicious: ASGI
with local(PYJO_ASGI='production'):
    is_ok(commands.detect(), 'asgi', 'right environment')
# Not in Mojolicious: AWS Lambda
with local(AWS_LAMBDA_RUNTIME_API='127.0.0.1:9001'):
    is_ok(commands.detect(), 'lambda', 'right environment')
# Not in Mojolicious: FastCGI, whose web server gives the application its listen socket as the file descriptor 0
if sys.platform == 'win32':
    skip('a socket of Windows is not a file descriptor', 1)
else:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        stdin = os.dup(0)
        try:
            os.dup2(listener.fileno(), 0)
            is_ok(commands.detect(), 'fastcgi', 'right environment')
        finally:
            os.dup2(stdin, 0)
            os.close(stdin)
with local(PATH_INFO='/test'):
    is_ok(commands.detect(), 'cgi', 'right environment')
with local(GATEWAY_INTERFACE='CGI/1.1'):
    is_ok(commands.detect(), 'cgi', 'right environment')
with local(PYJO_WSGI=None, PYJO_ASGI=None, AWS_LAMBDA_RUNTIME_API=None, PATH_INFO=None, GATEWAY_INTERFACE=None):
    is_ok(commands.detect(), None, 'no environment')
with local(PYJO_WSGI='production'):
    ok(callable(Pyjoyment.Commands.new().run()), 'right reference')
    with local(PYJO_NO_DETECT='1'):
        ok(not callable(Pyjoyment.Commands.new().run()), 'not a CODE reference')

# Run command
ok(callable(Pyjoyment.Commands.new().run('wsgi')), 'right reference')
# Not in Mojolicious: ASGI
ok(callable(Pyjoyment.Commands.new().run('asgi')), 'right reference')
# Not in Mojolicious: AWS Lambda
ok(callable(Pyjoyment.Commands.new().run('lambda')), 'right reference')

# Start application
with local(PYJO_APP_LOADER='1'):
    is_ok(type(Pyjoyment.Commands.start_app('PyjoymentTest')), PyjoymentTest.object, 'right class')

# Start application with command
ok(callable(Pyjoyment.Commands.start_app('PyjoymentTest', 'wsgi')), 'right reference')

# Start application with application specific commands
with local(PYJO_APP_LOADER='1'):
    app = Pyjoyment.Commands.start_app('PyjoymentTest')
is_ok(app.start('test_command'), 'works!', 'right result')
is_ok(app.start('test-command'), 'works!', 'right result')
is_ok(app.start('_test2-command'), 'works 2!', 'right result')
is_ok(Pyjoyment.Commands.start_app('PyjoymentTest', 'test_command'), 'works!', 'right result')
is_ok(Pyjoyment.Commands.start_app('PyjoymentTest', 'test-command'), 'works!', 'right result')
is_ok(Pyjoyment.Commands.start_app('PyjoymentTest', '_test2-command'), 'works 2!', 'right result')

# Application specific help
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), local(PYJO_HARNESS_ACTIVE='0'):
    app.start()
like_ok(
    buffer.getvalue(), r'(?s)Usage: APPLICATION COMMAND \[OPTIONS\].*_test2-command.*cgi.*test-comm', 'right output'
)

with subtest('Commands starting with a dash are not allowed'), local(PYJO_HARNESS_ACTIVE='0'):
    throws_ok(lambda: app.start('-test2-command'), re.compile(r'Invalid command "-test2-command"\.'), 'not allowed')

# Do not pick up options for detected environments
with local(PYJO_MODE=None, PYJO_WSGI='testing'):
    argv = sys.argv
    try:
        sys.argv = [argv[0], 'wsgi', '-m', 'production']
        ok(callable(Pyjoyment.Commands.start_app('PyjoymentTest')), 'right reference')
        is_ok(os.environ.get('PYJO_MODE'), None, 'no mode')
    finally:
        sys.argv = argv

# mojo
is_deeply_ok(commands.namespaces, ['Pyjoyment.Command.Author', 'Pyjoyment.Command'], 'right namespaces')
ok(commands.description, 'has a description')
like_ok(commands.message, r'COMMAND', 'has a message')
like_ok(commands.hint, r'help', 'has a hint')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), local(PYJO_HARNESS_ACTIVE='0'):
    commands.run()
like_ok(
    buffer.getvalue(), r'(?s)Usage: APPLICATION COMMAND \[OPTIONS\].*daemon.*my-test-command.*version', 'right output'
)
like_ok(buffer.getvalue(), r'See, it works', 'description has been picked up')
unlike_ok(buffer.getvalue(), r'my-fake-test-command', 'fake command has been ignored')

# help
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    commands.run('help', 'generate', 'lite-app')
like_ok(buffer.getvalue(), r'Usage: APPLICATION generate lite-app \[OPTIONS\] \[NAME\]', 'right output')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    commands.run('generate', 'help', 'lite-app')
like_ok(buffer.getvalue(), r'Usage: APPLICATION generate lite-app \[OPTIONS\] \[NAME\]', 'right output')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    commands.run('generate', 'app', '-h')
like_ok(buffer.getvalue(), r'Usage: APPLICATION generate app \[OPTIONS\] \[NAME\]', 'right output')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    commands.run('generate', 'lite-app', '--help')
like_ok(buffer.getvalue(), r'Usage: APPLICATION generate lite-app \[OPTIONS\] \[NAME\]', 'right output')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), local(PYJO_HARNESS_ACTIVE='0'):
    commands.run('help')
like_ok(buffer.getvalue(), r'Usage: APPLICATION COMMAND \[OPTIONS\]', 'right output')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), local(PYJO_HARNESS_ACTIVE='0'):
    commands.run('--help')
like_ok(buffer.getvalue(), r'Usage: APPLICATION COMMAND \[OPTIONS\]', 'right output')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), local(PYJO_HARNESS_ACTIVE='0'):
    commands.run('-h')
like_ok(buffer.getvalue(), r'Usage: APPLICATION COMMAND \[OPTIONS\]', 'right output')

# get
get = Pyjoyment.Command.get.new()
ok(get.description, 'has a description')
like_ok(get.usage, r'get', 'has usage information')
with stdout() as buffer:
    get.run('/')
like_ok(buffer.getvalue().decode(), r'Your Pyjoyment is working!', 'right output')
template = "<p></p><p><%= param('just') %> <%= c.req.headers.header('X-Test') %></p>"
get.app.plugins.once('before_dispatch', lambda c: c.render(inline=template))
with stdout() as buffer:
    get.run('-f', 'just=works', '-H', 'X-Test: fine', '/html', 'p', '1', 'text')
like_ok(buffer.getvalue().decode(), r'works fine', 'right output')
get.app.plugins.once('before_dispatch', lambda c: c.render(json={'works': 'too'}))
with stdout() as buffer:
    get.run('/json', '/works')
like_ok(buffer.getvalue().decode(), r'too', 'right output')
buffer = io.StringIO()
with contextlib.redirect_stderr(buffer):
    throws_ok(lambda: get.run('--unknown'), re.compile(r'Usage: APPLICATION get'), 'unknown option')
like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')

# cgi
cgi = Pyjoyment.Command.cgi.new()
ok(cgi.description, 'has a description')
like_ok(cgi.usage, r'cgi', 'has usage information')
buffer = io.StringIO()
with contextlib.redirect_stderr(buffer):
    throws_ok(lambda: cgi.run('--unknown'), re.compile(r'Usage: APPLICATION cgi'), 'unknown option')
like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')

# cpanify
# Left out from Mojolicious: the command cpanify, as uv publish uploads distributions to PyPI

with subtest('daemon'):
    with subtest('Description'):
        command = Pyjoyment.Command.daemon.new()
        ok(command.description, 'has a description')
        like_ok(command.usage, r'daemon', 'has usage information')

    with subtest('Unknown option'):
        command = Pyjoyment.Command.daemon.new()
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            throws_ok(lambda: command.run('--unknown'), re.compile(r'Usage: APPLICATION daemon'), 'unknown option')
        like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')

    with subtest('Proxy boolean'):
        command = Pyjoyment.Command.daemon.new()
        daemon = command.build_server('-p')
        ok(daemon.reverse_proxy, 'right value')
        is_deeply_ok(daemon.trusted_proxies, [], 'right value')

    with subtest('Trusted proxies'):
        command = Pyjoyment.Command.daemon.new()
        daemon = command.build_server('-p', '127.0.0.0/8', '-p', '10.0.0.0/8')
        ok(daemon.reverse_proxy, 'right value')
        is_deeply_ok(daemon.trusted_proxies, ['127.0.0.0/8', '10.0.0.0/8'], 'right value')

    with subtest('Trusted proxies from environment'), local(PYJO_TRUSTED_PROXIES='127.0.0.0/8,10.0.0.0/8'):
        command = Pyjoyment.Command.daemon.new()
        daemon = command.build_server()
        ok(daemon.reverse_proxy, 'right value')
        is_deeply_ok(daemon.trusted_proxies, ['127.0.0.0/8', '10.0.0.0/8'], 'right value')

    with subtest('Proxy boolean and trusted'):
        command = Pyjoyment.Command.daemon.new()
        daemon = command.build_server('-p', '-p', '127.0.0.0/8', '-p', '10.0.0.0/8')
        ok(daemon.reverse_proxy, 'right value')
        is_deeply_ok(daemon.trusted_proxies, ['127.0.0.0/8', '10.0.0.0/8'], 'right value')

# eval
eval_ = Pyjoyment.Command.eval.new()
ok(eval_.description, 'has a description')
like_ok(eval_.usage, r'eval', 'has usage information')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    eval_.run('-v', 'app.controller_class')
like_ok(buffer.getvalue(), r'Pyjoyment\.Controller', 'right output')
throws_ok(lambda: eval_.run('-v', "raise Exception('TEST')"), re.compile(r'TEST'), 'right output')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    eval_.run('-v', "import Pyjo.Promise; Pyjo.Promise.new().resolve('Zoidberg')")
like_ok(buffer.getvalue(), r'Zoidberg', 'right output')
throws_ok(
    lambda: eval_.run('-v', "import Pyjo.Promise; Pyjo.Promise.new().reject('DOOM')"),
    re.compile(r'DOOM'),
    'right output',
)
buffer = io.StringIO()
with contextlib.redirect_stderr(buffer):
    throws_ok(lambda: eval_.run('--unknown'), re.compile(r'Usage: APPLICATION eval'), 'unknown option')
like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')

# fastcgi
# Not in Mojolicious: the command fastcgi, for the listen socket that a web server gives a FastCGI application
fastcgi = Pyjoyment.Command.fastcgi.new()
ok(fastcgi.description, 'has a description')
like_ok(fastcgi.usage, r'fastcgi', 'has usage information')
buffer = io.StringIO()
with contextlib.redirect_stderr(buffer):
    throws_ok(lambda: fastcgi.run('--unknown'), re.compile(r'Usage: APPLICATION fastcgi'), 'unknown option')
like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')

# generate
generator = Pyjoyment.Command.Author.generate.new()
is_deeply_ok(generator.namespaces, ['Pyjoyment.Command.Author.generate'], 'right namespaces')
ok(generator.description, 'has a description')
like_ok(generator.message, r'generate', 'has a message')
like_ok(generator.hint, r'help', 'has a hint')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer), local(PYJO_HARNESS_ACTIVE='0'):
    generator.run()
like_ok(buffer.getvalue(), r'(?s)Usage: APPLICATION generate GENERATOR \[OPTIONS\].*lite-app.*plugin', 'right output')

# generate app
app = Pyjoyment.Command.Author.generate.app.new()
ok(app.description, 'has a description')
like_ok(app.usage, r'app', 'has usage information')
cwd = Pyjo.File.path()
dir = Pyjo.File.tempdir()
os.chdir(dir)
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    app.run()
like_ok(buffer.getvalue(), r'my_app', 'right output')
# Renamed from Mojolicious: the __main__ module of the package, where Mojo has script/my_app
ok(os.path.exists(app.rel_file('my_app/MyApp/__main__.py').to_str()), 'script exists')
# Unlike Mojolicious: the package in the directory of the project, where Mojo has lib/MyApp.pm
ok(os.path.exists(app.rel_file('my_app/MyApp/__init__.py').to_str()), 'application class exists')
ok(os.path.exists(app.rel_file('my_app/MyApp/Controller/Example.py').to_str()), 'controller exists')
ok(os.path.exists(app.rel_file('my_app/my_app.yml').to_str()), 'config file exists')
# Renamed from Mojolicious: t/basic.py, where Mojo has t/basic.t
ok(os.path.exists(app.rel_file('my_app/t/basic.py').to_str()), 'test exists')
# Not in Mojolicious: pyproject.toml of the application
ok(os.path.exists(app.rel_file('my_app/pyproject.toml').to_str()), 'pyproject.toml exists')
ok(os.path.isdir(app.rel_file('my_app/public/assets').to_str()), 'assets directory exists')
ok(os.path.exists(app.rel_file('my_app/public/index.html').to_str()), 'static file exists')
ok(os.path.exists(app.rel_file('my_app/templates/layouts/default.html.ep').to_str()), 'layout exists')
ok(os.path.exists(app.rel_file('my_app/templates/example/welcome.html.ep').to_str()), 'template exists')
# Not in Mojolicious: the guide of the coding agents, which CLAUDE.md imports
agents = app.rel_file('my_app/AGENTS.md').slurp('UTF-8')
like_ok(agents, r'uv run python -m MyApp daemon', 'AGENTS.md with the commands')
like_ok(agents, r'claude plugin install pyjoyment --marketplace pyjoyment/Pyjoyment', 'AGENTS.md with the skills')
is_ok(app.rel_file('my_app/CLAUDE.md').slurp('UTF-8'), '@AGENTS.md\n', 'CLAUDE.md imports AGENTS.md')
# Not in Mojolicious: the application starts with the configuration of a test, which has no secrets, as Perl takes the
# value of a missing key for undef
code = "import Pyjo.Test.Pyjo; Pyjo.Test.Pyjo.new('MyApp', {'enable_weather': 1}).get_ok('/').status_is(200)"
env = {**os.environ, 'PYTHONPATH': os.pathsep.join([cwd.to_str(), app.rel_file('my_app').to_str()])}
result = subprocess.run(
    [sys.executable, '-c', code], cwd=app.rel_file('my_app').to_str(), env=env, capture_output=True, encoding='UTF-8'
)
ok(re.search(r'^ok 2 - 200 OK$', result.stdout, re.M), 'configuration of a test')
os.chdir(cwd)

with subtest('generate dockerfile'):
    dockerfile = Pyjoyment.Command.Author.generate.dockerfile.new()
    ok(dockerfile.description, 'has a description')
    like_ok(dockerfile.usage, r'dockerfile', 'has usage information')
    dir = Pyjo.File.tempdir()
    os.chdir(dir)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        dockerfile.run()
    like_ok(buffer.getvalue(), r'Dockerfile', 'right output')
    ok(os.path.exists(app.rel_file('Dockerfile').to_str()), 'Dockerfile exists')
    # Not in Mojolicious: .dockerignore and the user
    ok(os.path.exists(app.rel_file('.dockerignore').to_str()), '.dockerignore exists')
    unlike_ok(app.rel_file('Dockerfile').slurp().decode(), r'USER', 'no user')
    app.rel_file('Dockerfile').remove()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        dockerfile.run('-u', 'app')
    like_ok(app.rel_file('Dockerfile').slurp().decode(), r'(?m)^USER app$', 'right user')
    # Not in Mojolicious: the port, which the image sets for the server and exposes
    like_ok(
        app.rel_file('Dockerfile').slurp().decode(),
        r'(?m)^ARG PORT=3000\nENV PORT=\$\{PORT\}\nEXPOSE \$\{PORT\}$',
        'right port',
    )
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('-p', '8080')
    like_ok(app.rel_file('Dockerfile').slurp().decode(), r'(?m)^ARG PORT=8080$', 'right port')
    unlike_ok(app.rel_file('Dockerfile').slurp().decode(), r'PYJO_GRACEFUL_TIMEOUT', 'no graceful timeout')
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('-G', '8')
    like_ok(
        app.rel_file('Dockerfile').slurp().decode(),
        r'(?m)^ENV PORT=\$\{PORT\}\nENV PYJO_GRACEFUL_TIMEOUT=8\nEXPOSE',
        'right graceful timeout',
    )
    # Not in Mojolicious: the HEALTHCHECK of the liveness of Pyjoyment.Plugin.Health, or of the path of the option
    unlike_ok(app.rel_file('Dockerfile').slurp().decode(), r'HEALTHCHECK', 'no healthcheck')
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('-H', '/')
    like_ok(
        app.rel_file('Dockerfile').slurp().decode(),
        r'(?m)^EXPOSE \$\{PORT\}\nHEALTHCHECK --timeout=3s --start-period=30s --start-interval=1s CMD \["python", "-c", '
        + r'"import http\.client, .*c\.request\(\'GET\', \'/\'\); sys\.exit\(c\.getresponse\(\)\.status != 200\)"\]\nCMD ',
        'right healthcheck',
    )
    healthcheck = re.search(r'(?m)^HEALTHCHECK .* CMD (.*)$', app.rel_file('Dockerfile').slurp().decode())
    is_ok(json.loads(healthcheck[1])[:2], ['python', '-c'], 'right command')
    app.rel_file('Dockerfile').remove()
    dockerfile.app.plugin('Health')
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run()
    like_ok(app.rel_file('Dockerfile').slurp().decode(), r"c\.request\('GET', '/livez'\)", 'right healthcheck')
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('--healthcheck', '')
    unlike_ok(app.rel_file('Dockerfile').slurp().decode(), r'HEALTHCHECK', 'no healthcheck')
    # Not in Mojolicious: the image of an event function of AWS Lambda, whose command is the runtime itself, without
    # what a server has, also the HEALTHCHECK of Pyjoyment.Plugin.Health
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('--target', 'lambda')
    content = app.rel_file('Dockerfile').slurp().decode()
    cmd = json.loads(re.search(r'(?m)^CMD (.*)$', content)[1])
    is_ok(cmd[0], 'python', 'right command')
    ok('prefork' not in cmd, 'no server')
    unlike_ok(content, r'PORT|EXPOSE|HEALTHCHECK|PYJO_GRACEFUL_TIMEOUT', 'nothing of a server')
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('-t', 'lambda', '-u', 'app')
    like_ok(app.rel_file('Dockerfile').slurp().decode(), r'(?m)^USER app\nCMD ', 'right user')
    # Not in Mojolicious: the gzip variants of the static files
    unlike_ok(app.rel_file('Dockerfile').slurp().decode(), r'gzip', 'no variants')
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('-c', 'public')
    content = app.rel_file('Dockerfile').slurp().decode()
    like_ok(
        content,
        r'(?m)^COPY \. \.\nENV PATH=.*\nRUN find public -type f -size \+859c \\\n'
        + r"    \\\( -name '\*\.css' -o -name '\*\.csv' -o .* -o -name '\*\.xml' \\\) \\\n"
        + r'    -exec gzip -k -f -9 -n \{\} \+\n',
        'right variants',
    )
    like_ok(content, r"-name '\*\.js' -o -name '\*\.json'", 'JavaScript')
    unlike_ok(content, r'png|woff|pdf', 'no formats that are compressed already')
    app.rel_file('Dockerfile').remove()
    with contextlib.redirect_stdout(io.StringIO()):
        dockerfile.run('--compress', 'public', '--compress', 'my static', '-C', '*.css', '--compress-pattern', '*.js')
    like_ok(
        app.rel_file('Dockerfile').slurp().decode(),
        r"(?m)^RUN find public 'my static' -type f -size \+859c \\\n    \\\( -name '\*\.css' -o -name '\*\.js' \\\) \\\n",
        'right paths and patterns',
    )
    throws_ok(
        lambda: dockerfile.run('-C', '*.css'),
        re.compile(r'^Option --compress-pattern needs --compress'),
        'patterns without a path',
    )
    throws_ok(lambda: dockerfile.run('-t', 'kubernetes'), re.compile(r'^Unknown target: kubernetes'), 'unknown target')
    throws_ok(
        lambda: dockerfile.run('-t', 'lambda', '-p', '8080'),
        re.compile(r'^Option --port is not for the target lambda'),
        'option of a server',
    )
    throws_ok(
        lambda: dockerfile.run('-t', 'lambda', '-G', '8'),
        re.compile(r'^Option --graceful-timeout is not for the target lambda'),
        'option of a server',
    )
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        throws_ok(
            lambda: dockerfile.run('--unknown'), re.compile(r'Usage: APPLICATION generate dockerfile'), 'unknown option'
        )
    like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')
    os.chdir(cwd)

# Not in Mojolicious: generate kubernetes
with subtest('generate kubernetes'):
    kubernetes = Pyjoyment.Command.Author.generate.kubernetes.new()
    ok(kubernetes.description, 'has a description')
    like_ok(kubernetes.usage, r'kubernetes', 'has usage information')
    dir = Pyjo.File.tempdir()
    os.chdir(dir)
    app.rel_file('app.txt').spew('Hello\n')
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        kubernetes.run()
    like_ok(buffer.getvalue(), r'kubernetes.dev.deployment\.yaml', 'right output')
    for name in ('base/kustomization.yaml', 'base/deployment.yaml', 'base/probes.yaml', 'base/service.yaml'):
        ok(os.path.exists(app.rel_file(f'kubernetes/{name}').to_str()), f'{name} exists')
    for name in ('prod/kustomization.yaml', 'prod/deployment.yaml', 'dev/kustomization.yaml', 'dev/deployment.yaml'):
        ok(os.path.exists(app.rel_file(f'kubernetes/{name}').to_str()), f'{name} exists')
    is_ok(app.rel_file('kubernetes/dev/files/app.txt').slurp(), b'Hello\n', 'copy of the application')
    like_ok(app.rel_file('kubernetes/dev/kustomization.yaml').slurp().decode(), r'"app\.txt=files/app\.txt"', 'file')
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        kubernetes.run('-p', '8080', '--host-path')
    like_ok(buffer.getvalue(), r'\[exist\] .*kubernetes.base.deployment\.yaml', 'base kept')
    like_ok(app.rel_file('kubernetes/dev/deployment.yaml').slurp().decode(), r'hostPath:', 'host path')
    ok(not os.path.exists(app.rel_file('kubernetes/dev/files').to_str()), 'no copy of the application')
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        throws_ok(
            lambda: kubernetes.run('--unknown'), re.compile(r'Usage: APPLICATION generate kubernetes'), 'unknown option'
        )
    like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')
    os.chdir(cwd)

# Not in Mojolicious: generate lambda-zip, with the uv of t/lib/FakeUV.py
with subtest('generate lambda-zip'):
    sys.path.insert(0, Pyjo.File.curfile().dirname().sibling('lib').to_str())
    import FakeUV  # pyright: ignore[reportMissingImports]

    lambda_zip = Pyjoyment.Command.Author.generate.lambda_zip.new()
    ok(lambda_zip.description, 'has a description')
    like_ok(lambda_zip.usage, r'lambda-zip', 'has usage information')
    uv = Pyjo.File.tempdir()
    _uv = Pyjoyment.Command.Author.generate.lambda_zip._uv
    Pyjoyment.Command.Author.generate.lambda_zip._uv = FakeUV.command
    version = f'{sys.version_info.major}.{sys.version_info.minor}'

    def generate(*args, **env):
        uv.child('log').spew('')
        with stdout() as buffer, local(FAKE_UV_LOG=uv.child('log').to_str(), **env):
            lambda_zip.run(*args)
        return buffer.getvalue().decode(), FakeUV.calls(uv.child('log'))

    def entries(path):
        with zipfile.ZipFile(app.rel_file(path).to_str()) as archive:
            return {info.filename: info for info in archive.infolist()}

    dir = Pyjo.File.tempdir()
    os.chdir(dir)
    app.rel_file('pyproject.toml').spew('[project]\nname = "my_app"\n')
    app.rel_file('MyApp').make_path()
    app.rel_file('MyApp/__init__.py').spew('pass\n')
    app.rel_file('MyApp/__pycache__').make_path().child('__init__.cpython-0.pyc').spew('')
    app.rel_file('wrapper.py').spew('#!/usr/bin/env python3\n')
    app.rel_file('.git').make_path().child('config').spew('')
    app.rel_file('.env').spew('SECRET=1\n')
    with local(PYJO_EXE=None):
        output, calls = generate()
    like_ok(output, r'\[write\] .*dist.python\.zip', 'right output')
    like_ok(output, r'\[write\] .*dist.pyjoyment\.zip', 'right output')
    like_ok(output, r'\[write\] .*dist.function\.zip', 'right output')
    is_ok(calls[0][:3], ['python', 'install', '--no-bin'], 'Python')
    is_ok(calls[0][-1], f'cpython-{version}-linux-x86_64-gnu', 'right Python')
    pip = next(call for call in calls if call[:2] == ['pip', 'install'])
    is_ok(calls[calls.index(pip) - 1], ['python', 'install', '--no-bin', version], 'Python of the machine before')
    is_ok(pip[pip.index('--python') + 1], f'{version}+gil', 'Python with the GIL')
    is_ok(pip[pip.index('--python-platform') + 1], 'x86_64-manylinux_2_34', 'right platform')
    is_ok(pip[pip.index('-r') + 1], 'pyproject.toml', 'dependencies of the project')
    ok(not any(call[0] == 'export' for call in calls), 'nothing exported')
    python = entries('dist/python.zip')
    is_ok(python[f'python/bin/python{version}'].external_attr >> 16, 0o100755, 'executable interpreter')
    ok('python/bin/python3' not in python, 'no symbolic link')
    is_ok(python[f'python/lib/python{version}/os.py'].date_time, (1980, 1, 1, 0, 0, 0), 'fixed time')
    is_ok(python[f'python/lib/python{version}/os.py'].external_attr >> 16, 0o100644, 'right mode')
    ok(
        any(re.fullmatch(rf'python/lib/python{version}/__pycache__/os\..*\.pyc', name) for name in python),
        'standard library compiled',
    )
    ok(f'python/lib/python{version}/lib-dynload/_json.so' in python, 'extension')
    unlike_ok(' '.join(python), r'idlelib|site-packages|config-|_tkinter|include', 'nothing unused')
    with zipfile.ZipFile(app.rel_file('dist/python.zip').to_str()) as archive:
        data = archive.read(f'python/lib/python{version}/_sysconfigdata__linux.py').decode()
    is_ok(data, 'build_time_vars = {"prefix": \'/opt/python\'}\n', 'prefix of the layer')
    site = f'python/lib/python{version}/site-packages'
    pyjoyment = entries('dist/pyjoyment.zip')
    ok(f'{site}/Pyjo/__init__.py' in pyjoyment, 'Pyjo in the layer')
    ok(f'{site}/Pyjoyment/__init__.py' in pyjoyment, 'Pyjoyment in the layer')
    ok(f'{site}/pyjoyment-0.0.2.dist-info/METADATA' in pyjoyment, 'metadata of Pyjoyment in the layer')
    is_ok(pyjoyment[f'{site}/Pyjoyment/__init__.py'].external_attr >> 16, 0o100644, 'right mode')
    bytecode = next(name for name in pyjoyment if name.startswith(f'{site}/Pyjoyment/__pycache__/__init__.'))
    with zipfile.ZipFile(app.rel_file('dist/pyjoyment.zip').to_str()) as archive:
        ok(f'/opt/{site}/Pyjoyment/__init__.py'.encode() in archive.read(bytecode), 'Pyjoyment compiled for the layer')
    unlike_ok(' '.join(pyjoyment), r'foo', 'only Pyjoyment in the layer')
    function = entries('dist/function.zip')
    is_ok(function['bootstrap'].external_attr >> 16, 0o100755, 'executable bootstrap')
    with zipfile.ZipFile(app.rel_file('dist/function.zip').to_str()) as archive:
        bootstrap = archive.read('bootstrap').decode()
    like_ok(bootstrap, r'^#!/bin/sh\n', 'shell')
    like_ok(
        bootstrap, rf'(?m)^exec /opt/python/bin/python{version} -m Pyjoyment\.HelloWorld$', 'package of the application'
    )
    ok('MyApp/__init__.py' in function, 'application')
    is_ok(function['MyApp/__init__.py'].external_attr >> 16, 0o100644, 'right mode')
    is_ok(function['wrapper.py'].external_attr >> 16, 0o100755, 'executable script')
    ok(any(name.startswith('MyApp/__pycache__/__init__.') for name in function), 'application compiled')
    with zipfile.ZipFile(app.rel_file('dist/function.zip').to_str()) as archive:
        bytecode = next(name for name in function if name.startswith('MyApp/__pycache__/__init__.'))
        ok(b'/var/task/MyApp/__init__.py' in archive.read(bytecode), 'application compiled for the function')
    with zipfile.ZipFile(app.rel_file('dist/python.zip').to_str()) as archive:
        bytecode = next(name for name in python if name.startswith(f'python/lib/python{version}/__pycache__/os.'))
        ok(f'/opt/python/lib/python{version}/os.py'.encode() in archive.read(bytecode), 'compiled for the layer')
    ok('MyApp/__pycache__/__init__.cpython-0.pyc' not in function, 'not the bytecode of the machine')
    ok('foo/__init__.py' in function, 'dependency')
    unlike_ok(' '.join(function), r'(?:^| )(?:\.git|\.env|\.lock|bin/|dist/|python/|Pyjo|pyjoyment)', 'nothing else')
    zips = [app.rel_file(f'dist/{name}').slurp() for name in ('function.zip', 'python.zip', 'pyjoyment.zip')]
    crcs = {n: i.CRC for z in ('function', 'python', 'pyjoyment') for n, i in entries(f'dist/{z}.zip').items()}
    with local(PYJO_EXE=None):
        output, calls = generate()
    like_ok(output, r'\[write\] .*dist.function\.zip', 'written anew')
    is_deeply_ok(
        {n: i.CRC for z in ('function', 'python', 'pyjoyment') for n, i in entries(f'dist/{z}.zip').items()},
        crcs,
        'same contents',
    )
    is_ok(
        [app.rel_file(f'dist/{name}').slurp() for name in ('function.zip', 'python.zip', 'pyjoyment.zip')],
        zips,
        'same files',
    )

    # The same bytecode on another number of processors, which Python, as 3.15 and the free-threaded build, would give
    # otherwise to the modules that a process compiles after others
    compiled = []
    for cpus in ('1', '4'):
        modules = Pyjo.File.tempdir()
        for module in Pyjo.File.path(sysconfig.get_paths()['stdlib']).list().grep(re.compile(r'\.py$')):
            module.copy_to(modules)
        with local(PYTHONHASHSEED='0', PYTHON_CPU_COUNT=cpus):
            code = Pyjoyment.Command.Author.generate.lambda_zip._COMPILE
            subprocess.run([sys.executable, '-c', code, modules.to_str(), '/opt/python'], check=True)
        compiled.append({path.basename(): path.slurp() for path in modules.child('__pycache__').list()})
    ok(len(compiled[0]) > 64, 'modules of more than one chunk')
    is_deeply_ok([name for name, data in compiled[0].items() if compiled[1].get(name) != data], [], 'same bytecode')

    # No collection of the garbage while a module is compiled, whose moment in a free-threaded Python changes the
    # bytecode of the modules after it, at random, so the sitecustomize of the interpreters of the chunks collects at
    # every allocation and logs a collection inside py_compile.compile
    if not hasattr(gc, 'callbacks'):
        skip('PyPy has no thresholds nor callbacks of the garbage collector', 2)
    else:
        site = Pyjo.File.tempdir()
        site.child('sitecustomize.py').spew(
            'import gc, os, sys\n'
            'def collected(phase, info):\n'
            '    frame = sys._getframe()\n'
            '    while frame and (frame.f_code.co_name, os.path.basename(frame.f_code.co_filename)) != (\n'
            '        "compile", "py_compile.py"\n'
            '    ):\n'
            '        frame = frame.f_back\n'
            '    if frame:\n'
            '        with open(os.environ["GC_LOG"], "a") as log:\n'
            '            log.write(phase + "\\n")\n'
            'gc.set_threshold(1)\n'
            'gc.callbacks.append(collected)\n'
        )
        modules = Pyjo.File.tempdir()
        Pyjo.File.path(sysconfig.get_paths()['stdlib']).child('os.py').copy_to(modules)
        with local(PYTHONHASHSEED='0', PYTHONPATH=site.to_str(), GC_LOG=site.child('log').to_str()):
            code = Pyjoyment.Command.Author.generate.lambda_zip._COMPILE
            subprocess.run([sys.executable, '-c', code, modules.to_str(), '/opt/python'], check=True)
        ok(modules.child('__pycache__').list().size, 'module compiled')
        ok(not os.path.exists(site.child('log')), 'no collection')

    # The architecture, the free-threaded build and the lock of the project
    app.rel_file('uv.lock').spew('')
    with local(PYJO_EXE=None):
        output, calls = generate('--arch', 'arm64', '-p', '3.15t')
    is_ok(calls[0][-1], 'cpython-3.15t-linux-aarch64-gnu', 'right Python')
    export = next(call for call in calls if call[0] == 'export')
    ok('--frozen' in export and '--no-dev' in export and '--no-emit-project' in export, 'locked dependencies')
    pip = next(call for call in calls if call[:2] == ['pip', 'install'])
    is_ok(
        calls[calls.index(pip) - 1], ['python', 'install', '--no-bin', '3.15t'], 'free-threaded Python of the machine'
    )
    is_ok(pip[pip.index('--python') + 1], '3.15t', 'free-threaded Python')
    is_ok(pip[pip.index('--python-platform') + 1], 'aarch64-manylinux_2_34', 'right platform')
    is_ok(pip[pip.index('-r') + 1], export[export.index('-o') + 1], 'exported dependencies')
    ok('python/bin/python3.15t' in entries('dist/python.zip'), 'free-threaded interpreter')
    ok(
        'python/lib/python3.15t/site-packages/Pyjoyment/__init__.py' in entries('dist/pyjoyment.zip'),
        'Pyjoyment of the free-threaded Python',
    )

    # Python in the function, without a layer
    app.rel_file('dist').remove_tree()
    with local(PYJO_EXE=None):
        output, calls = generate('--no-layer')
    unlike_ok(output, r'python\.zip|pyjoyment\.zip', 'no layer')
    ok(not os.path.exists(app.rel_file('dist/python.zip')), 'no layer of Python')
    ok(not os.path.exists(app.rel_file('dist/pyjoyment.zip')), 'no layer of Pyjoyment')
    function = entries('dist/function.zip')
    ok('Pyjoyment/__init__.py' in function, 'Pyjoyment in the function')
    is_ok(function[f'python/bin/python{version}'].external_attr >> 16, 0o100755, 'executable interpreter')
    ok(f'python/lib/python{version}/os.py' in function, 'standard library')
    with zipfile.ZipFile(app.rel_file('dist/function.zip').to_str()) as archive:
        data = archive.read(f'python/lib/python{version}/_sysconfigdata__linux.py').decode()
    like_ok(data, r"'/var/task/python'", 'prefix of the function')
    with zipfile.ZipFile(app.rel_file('dist/function.zip').to_str()) as archive:
        bootstrap = archive.read('bootstrap').decode()
    like_ok(bootstrap, rf'(?m)^exec "\$LAMBDA_TASK_ROOT/python/bin/python{version}" -m ', 'interpreter of the function')

    # Only the function, for the layers that are published already, and the layers of an earlier build
    generate()
    with local(PYJO_EXE=None):
        output, calls = generate('--function-only', '-p', '3.14.2')
    like_ok(output, r'\[layer\] Pyjoyment 0\.0\.2 for Python 3\.14\r?\n', 'version of Pyjoyment')
    unlike_ok(output, r'python\.zip|pyjoyment\.zip', 'no layers')
    ok(not os.path.exists(app.rel_file('dist/python.zip')), 'layer of Python of an earlier build removed')
    ok(not os.path.exists(app.rel_file('dist/pyjoyment.zip')), 'layer of Pyjoyment of an earlier build removed')
    ok(not any(call[-1].startswith('cpython-') for call in calls), 'no Python of a layer')
    function = entries('dist/function.zip')
    ok('MyApp/__init__.py' in function, 'application')
    unlike_ok(' '.join(function), r'(?:^| )(?:python/|Pyjo)', 'no Python and Pyjoyment')
    with zipfile.ZipFile(app.rel_file('dist/function.zip').to_str()) as archive:
        bootstrap = archive.read('bootstrap').decode()
    like_ok(bootstrap, r'(?m)^exec /opt/python/bin/python3\.14 -m ', 'Python of the layer')
    with local(PYJO_EXE=None):
        output, calls = generate('--function-only', '-p', '3.15t')
    like_ok(output, r'\[layer\] Pyjoyment 0\.0\.2 for Python 3\.15t\r?\n', 'version of the free-threaded Python')
    with zipfile.ZipFile(app.rel_file('dist/function.zip').to_str()) as archive:
        bootstrap = archive.read('bootstrap').decode()
    like_ok(bootstrap, r'(?m)^exec /opt/python/bin/python3\.15t -m ', 'free-threaded Python of the layer')

    # The runtime of Python of Lambda, without Python and the bootstrap, and the layers of an earlier build
    generate()
    with local(PYJO_EXE=None):
        output, calls = generate('--runtime', 'python3.14')
    unlike_ok(output, r'python\.zip', 'no layer of Python')
    is_ok(
        [call for call in calls if call[0] == 'python'],
        [['python', 'install', '--no-bin', '3.14']],
        'Python of the machine',
    )
    ok(not os.path.exists(app.rel_file('dist/python.zip')), 'layer of Python of an earlier build removed')
    pip = next(call for call in calls if call[:2] == ['pip', 'install'])
    is_ok(pip[pip.index('--python') + 1], '3.14+gil', 'Python of the runtime')
    ok(
        'python/lib/python3.14/site-packages/Pyjoyment/__init__.py' in entries('dist/pyjoyment.zip'),
        'layer of Pyjoyment',
    )
    function = entries('dist/function.zip')
    ok('MyApp/__init__.py' in function, 'application')
    unlike_ok(' '.join(function), r'(?:^| )(?:bootstrap|python/|Pyjo)', 'no bootstrap, Python and Pyjoyment')
    with local(PYJO_EXE=None):
        output, calls = generate('-r', 'python3.14', '-p', '3.14')
    ok(os.path.exists(app.rel_file('dist/pyjoyment.zip')), 'same version')
    with local(PYJO_EXE=None):
        output, calls = generate('--runtime', 'python3.14', '--function-only')
    like_ok(output, r'\[layer\] Pyjoyment 0\.0\.2 for Python 3\.14\r?\n', 'version of Pyjoyment on the runtime')
    ok(not os.path.exists(app.rel_file('dist/pyjoyment.zip')), 'layer of Pyjoyment of an earlier build removed')
    function = entries('dist/function.zip')
    ok('MyApp/__init__.py' in function, 'application on the runtime')
    unlike_ok(' '.join(function), r'(?:^| )(?:bootstrap|python/|Pyjo)', 'only the application on the runtime')
    os.chdir(cwd)

    # A Lite script with the inline metadata of PEP 723, and its lock
    dir = Pyjo.File.tempdir()
    os.chdir(dir)
    app.rel_file('my app.py').spew('# /// script\n# dependencies = ["Pyjoyment"]\n# ///\n')
    with local(PYJO_EXE=app.rel_file('my app.py').to_abs().to_str()):
        lambda_zip.app.home = Pyjo.File.path().to_abs()
        output, calls = generate()
        export = next(call for call in calls if call[0] == 'export')
        is_ok(export[:3], ['export', '--script', 'my app.py'], 'dependencies of the script')
        ok('--frozen' not in export, 'not locked')
        app.rel_file('my app.py.lock').spew('')
        output, calls = generate()
        ok('--frozen' in next(call for call in calls if call[0] == 'export'), 'locked')
    with zipfile.ZipFile(app.rel_file('dist/function.zip').to_str()) as archive:
        like_ok(archive.read('bootstrap').decode(), r"(?m)^exec /opt/python/bin/python\S+ 'my app\.py'$", 'script')

    # Errors
    throws_ok(lambda: lambda_zip.run('-a', 'riscv64'), re.compile(r'^Unknown architecture: riscv64'), 'architecture')
    throws_ok(lambda: lambda_zip.run('-p', 'pypy3.11'), re.compile(r'^Unknown version of Python: pypy3\.11'), 'version')
    throws_ok(lambda: lambda_zip.run('-r', 'provided.al2'), re.compile(r'^Unknown runtime: provided\.al2$'), 'runtime')
    throws_ok(
        lambda: lambda_zip.run('--function-only', '--no-layer'),
        re.compile(r'^Options --function-only and --no-layer exclude each other'),
        'only the function and no layer',
    )
    throws_ok(
        lambda: lambda_zip.run('-r', 'python3.14', '-p', '3.15'),
        re.compile(r'^Option --python is not for the runtime python3\.14'),
        'version of the runtime',
    )
    dir = Pyjo.File.tempdir()
    os.chdir(dir)
    app.rel_file('pyproject.toml').spew('[project]\nname = "my_app"\n')
    with local(FAKE_UV_NO_PYJOYMENT='1', PYJO_EXE=None):
        throws_ok(
            lambda: generate('-r', 'python3.14'),
            re.compile(r'^Pyjoyment is not among the dependencies'),
            'no Pyjoyment',
        )
        generate('-r', 'python3.14', '--no-layer')
    ok(not os.path.exists(app.rel_file('dist/pyjoyment.zip')), 'no Pyjoyment without a layer')
    os.chdir(cwd)
    with local(FAKE_UV_LOG=uv.child('log').to_str(), FAKE_UV_FAIL='python'), contextlib.redirect_stdout(io.StringIO()):
        throws_ok(
            lambda: lambda_zip.run(),
            re.compile(r'^Command "uv python install" failed with exit status 2'),
            'failed command',
        )
    Pyjoyment.Command.Author.generate.lambda_zip._uv = _uv
    with local(PATH=''):
        throws_ok(lambda: lambda_zip.run(), re.compile(r'^Command "uv" not found'), 'no uv')
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        throws_ok(
            lambda: lambda_zip.run('--unknown'), re.compile(r'Usage: APPLICATION generate lambda-zip'), 'unknown option'
        )
    like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')
    os.chdir(cwd)

# generate lite_app
app = Pyjoyment.Command.Author.generate.lite_app.new()
ok(app.description, 'has a description')
like_ok(app.usage, r'lite-app', 'has usage information')
dir = Pyjo.File.tempdir()
os.chdir(dir)
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    app.run()
like_ok(buffer.getvalue(), r'myapp\.py', 'right output')
ok(os.path.exists(app.rel_file('myapp.py').to_str()), 'app exists')
os.chdir(cwd)

# generate makefile
# Renamed from Mojolicious: generate pyproject, where Mojo has generate makefile
pyproject = Pyjoyment.Command.Author.generate.pyproject.new()
ok(pyproject.description, 'has a description')
like_ok(pyproject.usage, r'pyproject', 'has usage information')
dir = Pyjo.File.tempdir()
os.chdir(dir)
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    pyproject.run()
like_ok(buffer.getvalue(), r'pyproject\.toml', 'right output')
ok(os.path.exists(app.rel_file('pyproject.toml').to_str()), 'pyproject.toml exists')
os.chdir(cwd)

# generate plugin
plugin = Pyjoyment.Command.Author.generate.plugin.new()
ok(plugin.description, 'has a description')
like_ok(plugin.usage, r'plugin', 'has usage information')
dir = Pyjo.File.tempdir()
os.chdir(dir)
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    plugin.run()
like_ok(buffer.getvalue(), r'MyPlugin\.py', 'right output')
ok(os.path.exists(app.rel_file('Pyjoyment-Plugin-MyPlugin/Pyjoyment/Plugin/MyPlugin.py').to_str()), 'class exists')
ok(os.path.exists(app.rel_file('Pyjoyment-Plugin-MyPlugin/t/basic.py').to_str()), 'test exists')
ok(os.path.exists(app.rel_file('Pyjoyment-Plugin-MyPlugin/pyproject.toml').to_str()), 'pyproject.toml exists')
# Not in Mojolicious: the guide of the coding agents, which CLAUDE.md imports
agents = app.rel_file('Pyjoyment-Plugin-MyPlugin/AGENTS.md').slurp('UTF-8')
like_ok(agents, r"plugin\('MyPlugin'\)", 'AGENTS.md with the plugin')
is_ok(app.rel_file('Pyjoyment-Plugin-MyPlugin/CLAUDE.md').slurp('UTF-8'), '@AGENTS.md\n', 'CLAUDE.md imports AGENTS.md')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    plugin.run('-f', 'MyApp.Ext.Test')
like_ok(buffer.getvalue(), r'Test\.py', 'right output')
ok(os.path.exists(app.rel_file('MyApp-Ext-Test/MyApp/Ext/Test.py').to_str()), 'class exists')
ok(os.path.exists(app.rel_file('MyApp-Ext-Test/t/basic.py').to_str()), 'test exists')
ok(os.path.exists(app.rel_file('MyApp-Ext-Test/pyproject.toml').to_str()), 'pyproject.toml exists')
buffer = io.StringIO()
with contextlib.redirect_stderr(buffer):
    throws_ok(lambda: plugin.run('--unknown'), re.compile(r'Usage: APPLICATION generate plugin'), 'unknown option')
like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')
os.chdir(cwd)

# inflate
inflate = Pyjoyment.Command.Author.inflate.new()
ok(inflate.description, 'has a description')
like_ok(inflate.usage, r'inflate', 'has usage information')

with subtest('prefork'):
    with subtest('Description'):
        command = Pyjoyment.Command.prefork.new()
        ok(command.description, 'has a description')
        like_ok(command.usage, r'prefork', 'has usage information')

    with subtest('Unknown option'):
        command = Pyjoyment.Command.prefork.new()
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            throws_ok(lambda: command.run('--unknown'), re.compile(r'Usage: APPLICATION prefork'), 'unknown option')
        like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')

    with subtest('Proxy boolean'):
        command = Pyjoyment.Command.prefork.new()
        prefork = command.build_server('-p')
        ok(prefork.reverse_proxy, 'right value')
        is_deeply_ok(prefork.trusted_proxies, [], 'right value')

    with subtest('Trusted proxies'):
        command = Pyjoyment.Command.prefork.new()
        prefork = command.build_server('-p', '127.0.0.0/8', '-p', '10.0.0.0/8')
        ok(prefork.reverse_proxy, 'right value')
        is_deeply_ok(prefork.trusted_proxies, ['127.0.0.0/8', '10.0.0.0/8'], 'right value')

    with subtest('Trusted proxies from environment'), local(PYJO_TRUSTED_PROXIES='127.0.0.0/8,10.0.0.0/8'):
        command = Pyjoyment.Command.prefork.new()
        prefork = command.build_server()
        ok(prefork.reverse_proxy, 'right value')
        is_deeply_ok(prefork.trusted_proxies, ['127.0.0.0/8', '10.0.0.0/8'], 'right value')

    with subtest('Proxy boolean and trusted'):
        command = Pyjoyment.Command.prefork.new()
        prefork = command.build_server('-p', '-p', '127.0.0.0/8', '-p', '10.0.0.0/8')
        ok(prefork.reverse_proxy, 'right value')
        is_deeply_ok(prefork.trusted_proxies, ['127.0.0.0/8', '10.0.0.0/8'], 'right value')

# psgi
# Renamed from Mojolicious: wsgi, where Mojo has psgi
wsgi = Pyjoyment.Command.wsgi.new()
ok(wsgi.description, 'has a description')
like_ok(wsgi.usage, r'wsgi', 'has usage information')
# Not in Mojolicious: ASGI
asgi = Pyjoyment.Command.asgi.new()
ok(asgi.description, 'has a description')
like_ok(asgi.usage, r'asgi', 'has usage information')
# Not in Mojolicious: AWS Lambda, whose module has the name of a keyword of Python
lambda_ = importlib.import_module('Pyjoyment.Command.lambda').new()
ok(lambda_.description, 'has a description')
like_ok(lambda_.usage, r'lambda', 'has usage information')

# routes
routes = Pyjoyment.Command.routes.new()
ok(routes.description, 'has a description')
like_ok(routes.usage, r'routes', 'has usage information')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    routes.run()
like_ok(buffer.getvalue(), r'/\*whatever', 'right output')
unlike_ok(buffer.getvalue(), r'/\(\.\+\)\?', 'not verbose')
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    routes.run('-v')
like_ok(buffer.getvalue(), r'/\*whatever', 'right output')
like_ok(buffer.getvalue(), r'/\(\.\+\)\?', 'verbose')
buffer = io.StringIO()
with contextlib.redirect_stderr(buffer):
    throws_ok(lambda: routes.run('--unknown'), re.compile(r'Usage: APPLICATION routes'), 'unknown option')
like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')

# stdio
# Not in Mojolicious: the command stdio, for a protocol on the standard input and output
stdio = Pyjoyment.Command.stdio.new()
ok(stdio.description, 'has a description')
like_ok(stdio.usage, r'stdio', 'has usage information')
buffer = io.StringIO()
with contextlib.redirect_stderr(buffer):
    throws_ok(lambda: stdio.run('--unknown'), re.compile(r'Usage: APPLICATION stdio'), 'unknown option')
like_ok(buffer.getvalue(), r'Unknown option: unknown', 'right output')
throws_ok(lambda: stdio.run('foo'), re.compile(r'Usage: APPLICATION stdio'), 'no arguments')

# version
version = Pyjoyment.Command.version.new()
ok(version.description, 'has a description')
like_ok(version.usage, r'version', 'has usage information')
version.app.ua.server.app = version.app


@version.app.ua.once('start')
def start(ua, tx):
    tx.req.via_proxy = False
    tx.req.url = ua.server.url().set(path='/')


# Unlike Mojolicious: the JSON API of PyPI, where Mojo asks MetaCPAN for the version
version.app.plugins.once('before_dispatch', lambda c: c.render(json={'info': {'version': 1000}}))
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    version.run()
# Renamed from Mojolicious: Python, where Mojo shows Perl
like_ok(buffer.getvalue(), r'Python', 'right output')
like_ok(buffer.getvalue(), r'You might want to update your Pyjoyment to 1000!', 'right output')

# Hooks
app = Pyjoyment.new()


@app.hook('before_command')
def before_command(command, args):
    if not isinstance(command, Pyjoyment.Command.eval.object):
        return
    command.app.config()['test'] = 'works!'
    args.insert(0, '-v')


buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    app.start('eval', "app.config()['test']")
like_ok(buffer.getvalue(), r'works!', 'right output')

# Not in Mojolicious: the option --log-format of all commands, which sets PYJO_LOG_FORMAT before the application starts
with subtest('Log format'):
    root = Pyjo.File.curfile().dirname().dirname().dirname().to_str()
    dir = Pyjo.File.tempdir()
    script = dir.child('myapp.py').spew("from Pyjoyment.Lite import *\n\nget('/', {'text': 'Hello'})\n\napp.start()\n")
    env = {**os.environ, 'PYTHONPATH': root, 'PYJO_LOG_LEVEL': 'trace'}
    for name in ('PYJO_HOME', 'PYJO_LOG_FORMAT', 'PYJO_MODE'):
        env.pop(name, None)
    run = [sys.executable, script.to_str(), 'get']
    result = subprocess.run([*run, '--log-format', 'json', '/'], env=env, capture_output=True, text=True)
    is_ok(result.stdout, 'Hello', 'right output')
    record = json.loads(result.stderr.splitlines()[0])
    is_ok(record['message'], 'GET "/"', 'JSON')
    like_ok(record['request_id'], r'^[\w-]+$', 'request id')
    result = subprocess.run([*run, '--log-format', 'text', '/'], env=env, capture_output=True, text=True)
    like_ok(result.stderr, r'^\[.+\] \[\d+\] \[trace\] \[[\w-]+\] GET "/"\n', 'text')
    result = subprocess.run([*run, '/'], env={**env, 'PYJO_LOG_FORMAT': 'json'}, capture_output=True, text=True)
    is_ok(json.loads(result.stderr.splitlines()[0])['message'], 'GET "/"', 'environment variable')

done_testing()
