import Pyjo.File
import Pyjo.YAML

from Pyjo.Test import *
from Pyjo.Util import b64_encode

import os
import re
import shlex
import shutil
import subprocess
import sys


ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
ONELINER = os.path.join(os.path.dirname(__file__), '..', 'lib', 'OneLiner.py')
SITECUSTOMIZE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib', 'oneliner'))
PWSH = shutil.which('pwsh')
PROMPTS = {'console': '$ ', 'pwsh-session': 'PS> '}

# The one-liners of docs/guides/oneliners.rst, each command of its console blocks with the output that follows it, run
# in a directory with the files of the page, which the commands of a block change for the next ones
GUIDES = Pyjo.File.curfile().dirname().dirname().sibling('docs', 'guides')
PAGE = GUIDES.child('oneliners.rst').slurp('UTF-8')
EXAMPLES = GUIDES.child('oneliners')

DEPLOYMENT = Pyjo.YAML.load(EXAMPLES.child('deployment.yaml').slurp('UTF-8'))
COREDNS = {
    'apiVersion': 'apps/v1',
    'kind': 'Deployment',
    'metadata': {'name': 'coredns', 'namespace': 'kube-system'},
    'spec': {
        'template': {'spec': {'containers': [{'name': 'coredns', 'image': 'registry.k8s.io/coredns/coredns:v1.12.0'}]}}
    },
}
SERVICE = {
    'apiVersion': 'v1',
    'kind': 'Service',
    'metadata': {'name': 'myapp'},
    'spec': {'selector': {'app': 'myapp'}, 'ports': [{'port': 80, 'targetPort': 3000}]},
}


def pod(name, phase):
    return {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name}, 'status': {'phase': phase}}


def items(*objects):
    return Pyjo.YAML.dump({'apiVersion': 'v1', 'kind': 'List', 'items': list(objects)})


# What the commands of the pipes print, which the one-liners read from the standard input
STDIN = {
    'kubectl get deployments -A -o yaml': items(DEPLOYMENT, COREDNS),
    'kubectl get pods -A -o yaml': items(
        pod('myapp-7d4b9c8f6d-q8w4z', 'Running'), pod('myapp-7d4b9c8f6d-x2k9p', 'Pending')
    ),
    'kubectl get secret myapp -o yaml': Pyjo.YAML.dump(
        {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {'name': 'myapp'},
            'data': {'password': b64_encode(b's3cr3t')},
        }
    ),
    'kubectl get configmap myapp -o yaml': Pyjo.YAML.dump(
        {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': 'myapp'},
            'data': {'config.yaml': EXAMPLES.child('config.yaml').slurp('UTF-8')},
        }
    ),
    'kustomize build .': Pyjo.YAML.dump_all([SERVICE, DEPLOYMENT]),
}


def blocks():
    for shell, block in re.findall(r'^\.\. code-block:: (console|pwsh-session)\n\n((?:    .*\n|\n)+)', PAGE, re.M):
        commands = []
        prompt = '    ' + PROMPTS[shell]
        for line in block.rstrip('\n').split('\n'):
            if line.startswith(prompt):
                commands.append((line[len(prompt) :], []))
            else:
                commands[-1][1].append(line[4:])
        yield shell, commands


def run_pwsh(command, cwd):
    # A command of PowerShell, whose python is an alias of the interpreter, not a function, which would not pass the
    # standard input of a pipe on, and whose remote services the mock of sitecustomize answers
    script = os.path.join(cwd, 'command.ps1')
    with open(script, 'w', encoding='utf-8') as handle:
        handle.write(f"$ErrorActionPreference = 'Stop'\nSet-Alias python '{sys.executable}'\n{command}\n")
    env = {k: v for k, v in os.environ.items() if k not in ('PYJO_LOG_LEVEL', 'PYJO_MODE')}
    env |= {'PYTHONPATH': os.pathsep.join([SITECUSTOMIZE, os.path.abspath(ROOT)]), 'PYJO_PROXY': '0'}
    result = subprocess.run(
        [PWSH, '-NoProfile', '-NonInteractive', '-File', script],
        capture_output=True,
        env=env,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    os.remove(script)
    terminal = result.stdout + result.stderr
    return result.returncode, terminal.decode().replace('\r\n', '\n'), result.stderr.decode(errors='replace')


def run(command, cwd):
    # The command of a pipe gives the standard input, and the variables before python -m Pyjo its environment
    stdin = b''
    if ' | ' in command:
        producer, command = command.split(' | ', 1)
        stdin = STDIN[producer].encode()
    args = shlex.split(command)
    env = {k: v for k, v in os.environ.items() if k not in ('PYJO_LOG_LEVEL', 'PYJO_MODE')}
    env |= {'PYTHONPATH': ROOT, 'PYJO_PROXY': '0'}
    while '=' in args[0]:
        name, value = args.pop(0).split('=', 1)
        env[name] = value

    # The redirections of the shell, of the standard input from a file and of the standard output to one, as bytes
    stdout = None
    while len(args) > 2 and args[-2] in ('<', '>'):
        if args[-2] == '<':
            with open(os.path.join(cwd, args[-1]), 'rb') as handle:
                stdin = handle.read()
        else:
            stdout = args[-1]
        del args[-2:]
    if args[:3] != ['python', '-m', 'Pyjo']:
        return None
    result = subprocess.run(
        [sys.executable, ONELINER, *args[3:]], capture_output=True, env=env, cwd=cwd, input=stdin, timeout=60
    )
    if stdout is not None:
        with open(os.path.join(cwd, stdout), 'wb') as handle:
            handle.write(result.stdout)

    # What the terminal shows, the standard output that is not redirected and the standard error, with the line breaks
    # of print, which are CRLF on Windows
    terminal = (b'' if stdout is not None else result.stdout) + result.stderr
    return result.returncode, terminal.decode().replace('\r\n', '\n'), result.stderr.decode(errors='replace')


dir = Pyjo.File.tempdir()
for path in EXAMPLES.list():
    shutil.copy(path.to_str(), dir.to_str())

for shell, commands in blocks():
    for command, output in commands:
        with subtest(command):
            if shell == 'pwsh-session' and PWSH is None:
                skip('pwsh is required for the commands of PowerShell', 3)
                continue
            result = (run_pwsh if shell == 'pwsh-session' else run)(command, dir.to_str())
            if not ok(result is not None, 'a one-liner of python -m Pyjo'):
                continue
            returncode, terminal, stderr = result
            if not is_ok(returncode, 0, 'right exit status'):
                diag(stderr)
            if output:
                is_ok(terminal.rstrip('\n'), '\n'.join(output).rstrip('\n'), 'right output')

with subtest('Fixtures'):
    is_deeply_ok(
        sorted(STDIN), sorted(set(re.findall(r'^    \$ (.+?) \| python', PAGE, re.M))), 'every pipe of the page'
    )

done_testing()
