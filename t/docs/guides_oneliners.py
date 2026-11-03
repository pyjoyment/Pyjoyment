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
    for block in re.findall(r'^\.\. code-block:: console\n\n((?:    .*\n|\n)+)', PAGE, re.M):
        commands = []
        for line in block.rstrip('\n').split('\n'):
            if line.startswith('    $ '):
                commands.append((line[6:], []))
            else:
                commands[-1][1].append(line[4:])
        yield commands


def run(command, cwd):
    # The command of a pipe gives the standard input, and the variables before python -m Pyjo its environment
    stdin = None
    if ' | ' in command:
        producer, command = command.split(' | ', 1)
        stdin = STDIN[producer]
    args = shlex.split(command)
    env = {k: v for k, v in os.environ.items() if k not in ('PYJO_LOG_LEVEL', 'PYJO_MODE')}
    env |= {'PYTHONPATH': ROOT, 'PYJO_PROXY': '0'}
    while '=' in args[0]:
        name, value = args.pop(0).split('=', 1)
        env[name] = value
    if args[:3] != ['python', '-m', 'Pyjo']:
        return None
    return subprocess.run(
        [sys.executable, ONELINER, *args[3:]], capture_output=True, text=True, env=env, cwd=cwd, input=stdin, timeout=60
    )


dir = Pyjo.File.tempdir()
for path in EXAMPLES.list():
    shutil.copy(path.to_str(), dir.to_str())

for commands in blocks():
    for command, output in commands:
        with subtest(command):
            result = run(command, dir.to_str())
            if not ok(result is not None, 'a one-liner of python -m Pyjo'):
                continue
            if not is_ok(result.returncode, 0, 'right exit status'):
                diag(result.stderr)
            if output:
                is_ok(result.stdout.rstrip('\n'), '\n'.join(output).rstrip('\n'), 'right output')

with subtest('Fixtures'):
    is_deeply_ok(
        sorted(STDIN), sorted(set(re.findall(r'^    \$ (.+?) \| python', PAGE, re.M))), 'every pipe of the page'
    )

done_testing()
