import Pyjo.File

from Pyjo.Test import *

import importlib
import importlib.metadata
import importlib.util
import os
import re
import subprocess
import sys


# The project of plugins/pyjoyment/skills/tests/SKILL.md, each block of code in the file that its first line names, as
# a coding agent writes it, whose tests run as the skill runs them
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Skills = importlib.import_module('Skills')

root = Pyjo.File.curfile().dirname().dirname().dirname()
env = dict(os.environ)
env['PYTHONPATH'] = os.pathsep.join([root.to_str(), *filter(None, [env.get('PYTHONPATH')])])
for name in ('PYJO_HARNESS_ACTIVE', 'PYJO_HARNESS_IS_VERBOSE', 'PYJO_LOG_LEVEL'):
    env.pop(name, None)

tmp = Pyjo.File.tempdir()
files = {}
for code in Skills.blocks('tests'):
    name = re.match(r'# (\S+)\n', code)[1]
    tmp.child(*name.split('/')).dirname().make_path()
    tmp.child(*name.split('/')).spew(code)
    files[name] = code
is_deeply_ok(
    sorted(files),
    ['app.py', 't/basic.py', 'tests/conftest.py', 'tests/test_app.py', 'tests/test_existing.py'],
    'files of the project',
)


def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=tmp.to_str(), env=env, capture_output=True, text=True)
    return p.stdout, p.returncode


with subtest('pyjo-prove'):
    stdout, status = run('-m', 'Pyjo.Prove', '-l', '-r', 't')
    is_ok(status, 0, 'passed')
    like_ok(stdout, r't/basic\.py \.+ ok', 'script')
    like_ok(stdout, r'All tests successful\.', 'all')

with subtest('The script without the harness'):
    stdout, status = run('t/basic.py')
    is_ok(status, 0, 'passed')
    like_ok(stdout, re.compile(r'^ok 1 - Page$', re.M), 'Page')
    like_ok(stdout, re.compile(r'^ok 4 - Values$', re.M), 'Values')
    like_ok(stdout, re.compile(r'^1\.\.4$', re.M), 'plan')

with subtest('unittest'):
    p = subprocess.run(
        [sys.executable, '-m', 'unittest', 'discover', '-v', '-s', 'tests'],
        cwd=tmp.to_str(),
        env=env,
        capture_output=True,
        text=True,
    )
    is_ok(p.returncode, 0, 'passed')
    like_ok(p.stderr, r'(?m)^test_index \(test_existing\.TestApp\.test_index\) \.\.\. ok$', 'test of unittest')
    is_ok(p.stdout, '', 'no TAP')

with subtest('pytest'):
    if importlib.util.find_spec('pytest') is None:
        skip('pytest is required, as of the dependency group "pytest"', 4)
    else:
        # The plugin of the entry point where Pyjoyment is installed, as uv installs it, or of the checkout otherwise
        entry_point = any(
            e.value == 'Pyjo.Test.pytest_plugin' for e in importlib.metadata.entry_points(group='pytest11')
        )
        plugin = [] if entry_point else ['-p', 'Pyjo.Test.pytest_plugin']
        stdout, status = run('-m', 'pytest', '-p', 'no:cacheprovider', *plugin, '-v', '.')
        is_ok(status, 0, 'passed')
        like_ok(stdout, r't/basic\.py PASSED', 'script')
        like_ok(stdout, r'tests/test_app\.py::test_login PASSED', 'test of pytest')
        like_ok(stdout, r'tests/test_existing\.py::TestApp::test_index PASSED', 'test of unittest')

done_testing()
