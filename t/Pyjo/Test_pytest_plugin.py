import Pyjo.File

from Pyjo.Test import *

import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys


if importlib.util.find_spec('pytest') is None:
    plan(skip_all='pytest is required, as of the dependency group "pytest"')

root = Pyjo.File.curfile().dirname().dirname().dirname()

# The plugin of the entry point where Pyjoyment is installed, as uv installs it, or of the checkout otherwise
entry_point = any(e.value == 'Pyjo.Test.pytest_plugin' for e in importlib.metadata.entry_points(group='pytest11'))
plugin = [] if entry_point else ['-p', 'Pyjo.Test.pytest_plugin']

# The project of tt/pytest in a temporary directory, as pytest writes into it
tmp = Pyjo.File.tempdir()
project = tmp.child('project').to_str()
shutil.copytree(root.child('tt', 'pytest').to_str(), project)


def pytest(*args):
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([root.to_str(), *filter(None, [env.get('PYTHONPATH')])])
    p = subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            '-p',
            'no:cacheprovider',
            '-o',
            'console_output_style=classic',
            *plugin,
            *args,
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )
    return p.stdout.replace('\\', '/'), p.returncode


with subtest('Test scripts'):
    out, code = pytest('-rfEs', 't')
    like_ok(out, r'(?m)^t/died\.py F$', 'died')
    like_ok(out, r'(?m)^t/fail\.py F$', 'failed')
    like_ok(out, r'(?m)^t/pass\.py \.$', 'passed')
    like_ok(out, r'(?m)^t/requires\.py s$', 'skipped for requires-python')
    like_ok(out, r'(?m)^t/skip\.py s$', 'skipped')
    like_ok(out, r'(?m)^t/test_named\.py \.$', 'test script with the name of a test module')
    like_ok(out, r'(?m)^FAILED t/fail\.py - Failed: Failed 1/2 subtests', 'summary of the failure')
    like_ok(out, r'(?m)^_+ t/fail\.py \(TAP\) _+$', 'headline of the failure')
    like_ok(out, r'(?m)^    not ok 1 - right status\nnot ok 2 - Group$', 'failed tests')
    like_ok(out, r'(?m)^    #          got: 200\n    #     expected: 404$', 'diagnostics')
    like_ok(out, r'(?m)^Non-zero exit status: 1$', 'exit status')
    like_ok(out, r'(?m)^-+ Captured stdout call -+\nok 1 - same\n# Subtest: Group$', 'TAP output')
    like_ok(out, r'(?m)^FAILED t/died\.py - Failed: No plan found', 'summary of the death')
    like_ok(out, r'(?m)^RuntimeError: Died in the middle$', 'exception')
    like_ok(out, r'(?m)^SKIPPED \[1\] t/requires\.py: requires Python >=99$', 'reason of requires-python')
    like_ok(out, r'(?m)^SKIPPED \[1\] t/skip\.py: set TEST_ONLINE to enable this test$', 'reason')
    like_ok(out, r'(?m)^=+ 2 failed, 2 passed, 2 skipped in ', 'right summary')
    is_ok(code, 1, 'right exit status')

with subtest('pytest-xdist'):
    if importlib.util.find_spec('xdist') is None:
        plan(skip_all='pytest-xdist is required, as of the dependency group "pytest"')
    out, code = pytest('-rfEs', '-n', '2', 't')
    like_ok(out, r'(?m)^FAILED t/fail\.py - Failed: Failed 1/2 subtests', 'summary of the failure')
    like_ok(out, r'(?m)^SKIPPED \[1\] t/skip\.py: set TEST_ONLINE to enable this test$', 'reason')
    like_ok(out, r'(?m)^=+ 2 failed, 2 passed, 2 skipped in ', 'right summary')
    is_ok(code, 1, 'right exit status')

with subtest('Passing test scripts'):
    out, code = pytest('t/pass.py', 't/skip.py')
    like_ok(out, r'(?m)^=+ 1 passed, 1 skipped in ', 'right summary')
    is_ok(code, 0, 'right exit status')

with subtest('Verbose'):
    out, code = pytest('-v', 't/pass.py')
    like_ok(out, r'(?m)^t/pass\.py PASSED\b', 'the test script as a test')
    is_ok(code, 0, 'right exit status')

with subtest('Bail out of a test script'):
    out, code = pytest('-o', 'pyjo_prove_paths=xt', 'xt/bail.py', 'xt/sleep.py')
    like_ok(out, r'(?m)^xt/bail\.py F$', 'failed')
    like_ok(out, r'(?m)^Bail out!  No database connection$', 'reason')
    like_ok(out, r'(?m)^!+ Interrupted: Bail out!  No database connection !+$', 'run interrupted')
    like_ok(out, r'(?m)^=+ 1 failed in ', 'no more test scripts')
    is_ok(code, 2, 'right exit status')

with subtest('Timeout'):
    out, code = pytest('-o', 'pyjo_prove_paths=xt', '-o', 'pyjo_prove_timeout=1', 'xt/sleep.py')
    like_ok(out, r'(?m)^FAILED xt/sleep\.py - Failed: Timed out after 1 seconds$', 'timed out')
    is_ok(code, 1, 'right exit status')

with subtest('No test scripts'):
    out, code = pytest('-o', 'pyjo_prove_paths=', 't/pass.py')
    like_ok(out, r'(?m)^=+ no tests ran in ', 'no test scripts')
    is_ok(code, 5, 'right exit status')

with subtest('Tests of pytest'):
    out, code = pytest('-rfEs', 'tests')
    like_ok(out, r'(?m)^tests/test_app\.py \.F$', 'tests of the application')
    like_ok(out, r'(?m)^tests/test_functions\.py \.FFs\.F$', 'tests of the functions')
    like_ok(out, r'(?m)^tests/test_unittest\.py \.sF$', 'tests of unittest')
    like_ok(out, r"(?m)^E       AssertionError: Failed test 'exact match for content'$", 'name of the failed test')
    like_ok(out, r"(?m)^E                got: 'Hello'\nE           expected: 'Bye'$", 'got and expected')
    like_ok(out, r'(?m)^tests/test_app\.py:6: AssertionError$', 'the line of the test')
    unlike_ok(out, r'Pyjo/Test/', 'no frames of Pyjo.Test')
    like_ok(out, r"(?m)^E       AssertionError: Failed test 'greeting'$", 'name of the failed link of a chain')
    like_ok(out, r'(?m)^tests/test_functions\.py:32: AssertionError$', 'the line of the chain')
    like_ok(out, r"(?m)^E       AssertionError: Failed test 'deep structure'$", 'name of the deep structure')
    like_ok(out, r"(?m)^E                got\['a'\]\[1\] = 2\nE           expected\['a'\]\[1\] = 3$", 'difference')
    like_ok(out, r'(?m)^-+ Captured stderr call -+\n# a diagnostic message$', 'diagnostic message')
    like_ok(out, r'(?m)^SKIPPED \[1\] tests/test_functions\.py:19: not today$', 'skipped test')
    like_ok(out, r'(?m)^tests/test_unittest\.py:22: AssertionError$', 'the line of the test of unittest')
    like_ok(out, r'(?m)^SKIPPED \[1\] tests/test_unittest\.py:24: not today$', 'skipped test of unittest')
    like_ok(out, r'(?m)^=+ 5 failed, 4 passed, 2 skipped in ', 'right summary')
    is_ok(code, 1, 'right exit status')

with subtest('Tests of pytest after a module of unittest'):
    # The mode of the plugin, which the module restores at its end, so that a failed test after it still fails
    out, code = pytest('tests/test_unittest.py', 'tests/test_functions.py')
    like_ok(out, r'(?m)^tests/test_unittest\.py \.sF\ntests/test_functions\.py \.FFs\.F$', 'in this order')
    like_ok(out, r'(?m)^=+ 4 failed, 3 passed, 2 skipped in ', 'right summary')
    is_ok(code, 1, 'right exit status')

with subtest('Passing tests of pytest'):
    out, code = pytest('tests/test_app.py::test_index', 'tests/test_functions.py::test_pass')
    like_ok(out, r'(?m)^=+ 2 passed in ', 'right summary')
    is_ok(code, 0, 'right exit status, not the one of a test script without a plan')

with subtest('Bail out of a test of pytest'):
    out, code = pytest('-o', 'pyjo_prove_paths=', 'xt/test_bail.py')
    like_ok(out, r'(?m)^FAILED xt/test_bail\.py::test_bail_out - Pyjo\.Test\.BailOut: No database', 'failed')
    like_ok(out, r'(?m)^!+ Interrupted: Bail out!  No database connection !+$', 'run interrupted')
    like_ok(out, r'(?m)^=+ 1 failed in ', 'no more tests')
    is_ok(code, 2, 'right exit status')

with subtest('Everything'):
    out, code = pytest()
    like_ok(out, r'(?m)^testpaths: t, tests$', 'testpaths')
    like_ok(out, r'(?m)^=+ 7 failed, 6 passed, 4 skipped in ', 'right summary')
    is_ok(code, 1, 'right exit status')

done_testing()
