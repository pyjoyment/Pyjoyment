from Pyjo.Test import *

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def run(code, setup='', after='done_testing()', env=None):
    # The documented code runs as a test script of its own, after the setup,
    # which defines the names it uses, and before `after`, which ends it
    script = '\n'.join(['from Pyjo.Test import *', textwrap.dedent(setup), textwrap.dedent(code), after, ''])
    env = {k: v for k, v in os.environ.items() if k != 'TEST_ONLINE'} | {'PYTHONPATH': ROOT} | (env or {})
    p = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, env=env)
    return p.stdout, p.stderr, p.returncode


def shell(command, cwd):
    # A `python` on PATH which is the interpreter running this test
    bindir = os.path.join(cwd, 'bin')
    os.makedirs(bindir, exist_ok=True)
    if not os.path.exists(os.path.join(bindir, 'python')):
        os.symlink(sys.executable, os.path.join(bindir, 'python'))
    env = dict(os.environ, PATH=os.pathsep.join([bindir, os.environ.get('PATH', '')]))
    env.pop('PYTHONPATH', None)
    p = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, env=env)
    return p.stdout, p.returncode


SYNOPSIS_SETUP = """
    import Pyjo.URL

    class Cls:
        pass

    got, expected, unexpected = 'expected', 'expected', 'unexpected'
    got_complex_structure = expected_complex_structure = {'a': [1, 2]}
    obj, cls = Cls(), Cls
    url = Pyjo.URL.new('http://example.com')
"""

SYNOPSIS = """
    import os

    if not os.getenv('TEST_ONLINE'):
        plan(skip_all='set TEST_ONLINE to enable this test')

    ok(got == expected, 'test name')

    is_ok(got, expected, 'test name')
    isnt_ok(got, unexpected, 'test name')
    like_ok(got, r'expected', 'test name')
    unlike_ok(got, r'unexpected', 'test name')
    cmp_ok(got, '==', expected, 'test name')
    is_deeply_ok(got_complex_structure, expected_complex_structure, 'test name')
    isa_ok(obj, cls)
    throws_ok(lambda: int('x'), ValueError, 'test name')
    that(got).is_(expected, 'test name').unlike(r'unexpected', 'test name')

    with subtest('Parse'):
        is_ok(url.host, 'example.com', 'right host')

    @subtest('Format')
    def _():
        is_ok(str(url), 'http://example.com', 'right format')

    diag("here's what went wrong")
    note('what happens next')

    done_testing()
"""

with subtest('Synopsis'):
    out, err, code = run(SYNOPSIS, setup=SYNOPSIS_SETUP, after='', env={'TEST_ONLINE': '1'})
    is_ok(
        out,
        'ok 1 - test name\n'
        'ok 2 - test name\n'
        'ok 3 - test name\n'
        'ok 4 - test name\n'
        'ok 5 - test name\n'
        'ok 6 - test name\n'
        'ok 7 - test name\n'
        "ok 8 - An object of class 'Cls' isa 'Cls'\n"
        'ok 9 - test name\n'
        'ok 10 - test name\n'
        'ok 11 - test name\n'
        '# Subtest: Parse\n'
        '    ok 1 - right host\n'
        '    1..1\n'
        'ok 12 - Parse\n'
        '# Subtest: Format\n'
        '    ok 1 - right format\n'
        '    1..1\n'
        'ok 13 - Format\n'
        '# what happens next\n'
        '1..13\n',
        'all tests pass',
    )
    is_ok(err, "# here's what went wrong\n", 'diagnostic message')
    is_ok(code, 0, 'right exit status')

    out, err, code = run(SYNOPSIS, setup=SYNOPSIS_SETUP, after='')
    is_ok(out, '1..0 # SKIP set TEST_ONLINE to enable this test\n', 'skipped without TEST_ONLINE')
    is_ok(code, 0, 'right exit status')

with subtest('Running tests'):
    with tempfile.TemporaryDirectory() as tmp:
        os.symlink(os.path.join(ROOT, 'Pyjo'), os.path.join(tmp, 'Pyjo'))
        os.makedirs(os.path.join(tmp, 't', 'Pyjo'))
        with open(os.path.join(tmp, 't', 'Pyjo', 'URL.py'), 'w') as f:
            f.write("from Pyjo.Test import *\n\nok(True, 'works')\n\ndone_testing()\n")

        out, code = shell('python -m Pyjo.Prove -I . -r t', tmp)
        like_ok(out, r'(?m)^t/Pyjo/URL\.py \.+ ok$', 'python -m Pyjo.Prove -I . -r t')
        is_ok(code, 0, 'right exit status')

        # A variable before the command is of a shell of POSIX, which the cmd.exe of Windows is not
        if sys.platform == 'win32':
            skip('no shell of POSIX on Windows', 2)
        elif shutil.which('prove'):
            out, code = shell('PYTHONPATH=. prove --ext=py --exec=python -r t', tmp)
            like_ok(out, r'(?m)^t/Pyjo/URL\.py \.+ ok$', 'PYTHONPATH=. prove --ext=py --exec=python -r t')
            is_ok(code, 0, 'right exit status')
        else:
            skip('Perl prove is not installed', 2)

        # A variable before the command is of a shell of POSIX, which the cmd.exe of Windows is not
        if sys.platform == 'win32':
            skip('no shell of POSIX on Windows', 2)
        else:
            out, code = shell('PYTHONPATH=. python t/Pyjo/URL.py', tmp)
            is_ok(out, 'ok 1 - works\n1..1\n', 'PYTHONPATH=. python t/Pyjo/URL.py')
            is_ok(code, 0, 'right exit status')

with subtest('Plans'):
    out, err, code = run(
        """
        with plan():
            ok(True, 'first')
            ok(True, 'second')
        """,
        after='',
    )
    is_ok(out, 'ok 1 - first\nok 2 - second\n1..2\n', 'planned at the end of the block')
    is_ok(code, 0, 'right exit status')

with subtest('Subtests'):
    out, err, code = run("""
        with subtest('Simple'):
            ok(True, 'first')

        @subtest('Decorated')
        def _():
            ok(True, 'second')

        subtest('Callback', lambda: ok(True, 'third'))
    """)
    is_ok(
        out,
        '# Subtest: Simple\n'
        '    ok 1 - first\n'
        '    1..1\n'
        'ok 1 - Simple\n'
        '# Subtest: Decorated\n'
        '    ok 1 - second\n'
        '    1..1\n'
        'ok 2 - Decorated\n'
        '# Subtest: Callback\n'
        '    ok 1 - third\n'
        '    1..1\n'
        'ok 3 - Callback\n'
        '1..3\n',
        'three subtests',
    )
    is_ok(code, 0, 'right exit status')

with subtest('Chains'):
    out, err, code = run(
        r"""
        is_ok(url.host, 'example.com', 'right host').like(r'\.com$', 'top-level domain')

        (
            that(answer)
            .isa(int)
            .cmp('>', 0, 'positive')
            .is_(42, 'meaning of life')
        )
        """,
        setup="import Pyjo.URL\nurl = Pyjo.URL.new('http://example.com')\nanswer = 42",
    )
    is_ok(
        out,
        'ok 1 - right host\nok 2 - top-level domain\n'
        "ok 3 - An object of class 'int' isa 'int'\nok 4 - positive\nok 5 - meaning of life\n1..5\n",
        'every method is a test',
    )
    is_ok(code, 0, 'right exit status')

with subtest('Extensions'):
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'MyTest.py'), 'w') as f:
            f.write(
                textwrap.dedent(
                    """
                    import Pyjo.Test

                    __tracebackhide__ = Pyjo.Test.__tracebackhide__


                    def host_is(url, host, desc=None):
                        return Pyjo.Test.is_ok(url.host, host, desc or f'host is {host}')
                    """
                )
            )
        out, err, code = run(
            "host_is(url, 'example.com')\nhost_is(url, 'example.org')",
            setup="import Pyjo.URL\nfrom MyTest import host_is\nurl = Pyjo.URL.new('http://example.com')",
            env={'PYTHONPATH': os.pathsep.join([ROOT, tmp])},
        )
    is_ok(out, 'ok 1 - host is example.com\nnot ok 2 - host is example.org\n1..2\n', 'assertions of a module')
    like_ok(err, r'#   at <string> line 6\.', 'line of the test')
    is_ok(code, 1, 'right exit status')

with subtest('Exceptions'):
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'test_url.py'), 'w') as f:
            f.write(
                textwrap.dedent("""\
                    import unittest

                    import Pyjo.Test
                    import Pyjo.URL


                    def setUpModule():
                        Pyjo.Test.raise_failures()


                    def tearDownModule():
                        Pyjo.Test.raise_failures(False)


                    class TestURL(unittest.TestCase):
                        def test_host(self):
                            url = Pyjo.URL.new('HtTp://Example.Com')
                            Pyjo.Test.is_ok(url.host, 'Example.Com', 'right host')
                """)
            )
        env = dict(os.environ, PYTHONPATH=ROOT)
        p = subprocess.run(
            [sys.executable, '-m', 'unittest', '-v', 'test_url'], cwd=tmp, capture_output=True, text=True, env=env
        )
        like_ok(p.stderr, r'(?m)^test_host \(test_url\.TestURL\.test_host\) \.\.\. ok$', 'test of unittest')
        is_ok(p.stdout, '', 'no TAP')
        is_ok(p.returncode, 0, 'right exit status')

with subtest('bail_out'):
    out, err, code = run(
        """
        if not connected:
            bail_out('No database connection')
        """,
        setup='connected = False',
    )
    is_ok(out, 'Bail out!  No database connection\n', 'bailed out')
    is_ok(code, 255, 'right exit status')

with subtest('cmp_ok'):
    out, err, code = run(
        """
        # ok(got == expected)
        cmp_ok(got, '==', expected, 'this == that')
        """,
        setup='got, expected = 42, 42',
    )
    is_ok(out, 'ok 1 - this == that\n1..1\n', 'passed')

with subtest('diag'):
    out, err, code = run(
        """
        if not in_ok(users, 'foo', "There's a foo user"):
            diag("Since there's no foo, check that /etc/bar is set up right")
        """,
        setup="users = ['bar']",
    )
    is_ok(out, "not ok 1 - There's a foo user\n1..1\n", 'failed')
    like_ok(err, r"(?m)^# Since there's no foo, check that /etc/bar is set up right$", 'diagnostic message')
    is_ok(code, 1, 'right exit status')

with subtest('done_testing'):
    out, err, code = run(
        """
        ok(True)
        done_testing()
        """,
        after='',
    )
    is_ok(out, 'ok 1\n1..1\n', 'without a number')
    out, err, code = run(
        """
        ok(True)
        done_testing(1)
        """,
        after='',
    )
    is_ok(out, 'ok 1\n1..1\n', 'with a number')
    is_ok(code, 0, 'right exit status')

with subtest('fail_ok'):
    out, err, code = run("""
        fail_ok('This should not happen')
    """)
    is_ok(out, 'not ok 1 - This should not happen\n1..1\n', 'failed')
    is_ok(code, 1, 'right exit status')

with subtest('in_ok'):
    out, err, code = run("""
        in_ok(['foo', 'bar'], 'foo', 'foo is in the list')
    """)
    is_ok(out, 'ok 1 - foo is in the list\n1..1\n', 'passed')

with subtest('is_deeply_ok'):
    out, err, code = run("""
        is_deeply_ok([[1, 2], [3, [4, 5]]], [[1, 2], [3]], 'deep structure')
    """)
    is_ok(out, 'not ok 1 - deep structure\n1..1\n', 'failed')
    like_ok(
        err,
        r'(?m)^#     Structures begin differing at:\n'
        r'#          got\[1\]\[1\] = \[4, 5\]\n'
        r'#     expected\[1\]\[1\] = Does not exist$',
        'where the structures differ',
    )

with subtest('is_ok'):
    out, err, code = run(
        """
        is_ok(ultimate_answer(), 42, 'meaning of life')
        """,
        setup="""
        def ultimate_answer():
            return 42
        """,
    )
    is_ok(out, 'ok 1 - meaning of life\n1..1\n', 'passed')

with subtest('isa_ok'):
    out, err, code = run(
        """
        obj = SomeClass()
        isa_ok(obj, SomeClass)
        isa_ok(123, (int, float))
        """,
        setup="""
        class SomeClass:
            pass
        """,
    )
    is_ok(
        out,
        "ok 1 - An object of class 'SomeClass' isa 'SomeClass'\n"
        "ok 2 - An object of class 'int' isa 'int, float'\n"
        '1..2\n',
        'passed',
    )

with subtest('isnt_ok'):
    out, err, code = run(
        """
        isnt_ok(foo, '', 'got some foo')
        """,
        setup="foo = 'foo'",
    )
    is_ok(out, 'ok 1 - got some foo\n1..1\n', 'passed')

with subtest('like_ok'):
    out, err, code = run(
        """
        like_ok(got, r'expected', 'test name')
        like_ok(got, (r'expected', 'i'), 'test name')
        like_ok(got, re.compile(r'expected'), 'test name')
        """,
        setup="""
        import re

        got = 'the expected value'
        """,
    )
    is_ok(out, 'ok 1 - test name\nok 2 - test name\nok 3 - test name\n1..3\n', 'passed')

with subtest('none_ok'):
    out, err, code = run(
        """
        none_ok(req.headers.transfer_encoding, 'no "Transfer-Encoding" value')
        """,
        setup="""
        import Pyjo.Message.Request

        req = Pyjo.Message.Request.new()
        """,
    )
    is_ok(out, 'ok 1 - no "Transfer-Encoding" value\n1..1\n', 'passed')

with subtest('not_in_ok'):
    out, err, code = run(
        """
        not_in_ok(os.environ, 'DISPLAY', 'DISPLAY is not set')
        """,
        setup="""
        import os

        os.environ.pop('DISPLAY', None)
        """,
    )
    is_ok(out, 'ok 1 - DISPLAY is not set\n1..1\n', 'passed')

with subtest('note'):
    out, err, code = run(
        """
        note(f'Tempfile is {tempfile}')
        """,
        setup="tempfile = '/tmp/test.txt'",
        after='pass_ok()\ndone_testing()',
    )
    is_ok(out, '# Tempfile is /tmp/test.txt\nok 1\n1..1\n', 'TAP comment')

with subtest('ok'):
    out, err, code = run(
        """
        ok(3**4 == 81, 'simple exponential')
        ok(isinstance(film, Film), 'set_db()')
        ok(None not in items, 'all items defined')
        """,
        setup="""
        class Film:
            pass

        film = Film()
        items = [1, 2, 3]
        """,
    )
    is_ok(out, 'ok 1 - simple exponential\nok 2 - set_db()\nok 3 - all items defined\n1..3\n', 'passed')

with subtest('pass_ok'):
    out, err, code = run("""
        pass_ok('step 1')
    """)
    is_ok(out, 'ok 1 - step 1\n1..1\n', 'passed')

with subtest('plan'):
    out, err, code = run(
        """
        plan(tests=3)
        """,
        after='ok(True)\nok(True)\nok(True)',
    )
    is_ok(out, '1..3\nok 1\nok 2\nok 3\n', 'planned')
    is_ok(code, 0, 'right exit status')
    out, err, code = run(
        """
        if not os.getenv('TEST_ONLINE'):
            plan(skip_all='set TEST_ONLINE to enable this test')
        """,
        setup='import os',
        after='',
    )
    is_ok(out, '1..0 # SKIP set TEST_ONLINE to enable this test\n', 'skipped')
    is_ok(code, 0, 'right exit status')

    out, err, code = run(
        """
        with plan():
            ok(True)
        """,
        after='',
    )
    is_ok(out, 'ok 1\n1..1\n', 'planned at the end of the block')
    is_ok(code, 0, 'right exit status')
    out, err, code = run(
        """
        with plan(tests=1):
            ok(True)
        """,
        after='',
    )
    is_ok(out, '1..1\nok 1\n', 'planned up front')
    is_ok(code, 0, 'right exit status')

with subtest('plan_skip_all'):
    out, err, code = run(
        """
        plan_skip_all('set TEST_ONLINE to enable this test')
        """,
        after='',
    )
    is_ok(out, '1..0 # SKIP set TEST_ONLINE to enable this test\n', 'skipped')
    is_ok(code, 0, 'right exit status')

with subtest('plan_tests'):
    out, err, code = run(
        """
        plan_tests(3)
        """,
        after='ok(True)\nok(True)\nok(True)',
    )
    is_ok(out, '1..3\nok 1\nok 2\nok 3\n', 'planned')
    is_ok(code, 0, 'right exit status')

with subtest('raise_failures'):
    out, err, code = run(
        """
        raise_failures()
        try:
            ok(False, 'raised')
        except AssertionError as e:
            print(e)
        raise_failures(False)
        """,
        after='ok(True)\ndone_testing()',
    )
    is_ok(out, "Failed test 'raised'\nok 1\n1..1\n", 'raised, then printed')
    is_ok(code, 0, 'right exit status')

with subtest('skip'):
    out, err, code = run(
        """
        if os.getenv('TEST_ONLINE'):
            ok(Pyjo.UserAgent.new().get('https://mojolicious.org').result.is_success, 'online request')
        else:
            skip('set TEST_ONLINE to enable this test', 1)
        """,
        setup="""
        import Pyjo.UserAgent

        import os
        """,
    )
    is_ok(out, 'ok 1 # skip set TEST_ONLINE to enable this test\n1..1\n', 'skipped')
    is_ok(code, 0, 'right exit status')

with subtest('Result'):
    out, err, code = run(
        """
        isa_ok(answer, str).is_('42', 'meaning of life') or diag('the answer is lost')
        """,
        setup='answer = 42',
    )
    is_ok(out, "not ok 1 - An object of class 'int' isa 'str'\nnot ok 2 - meaning of life\n1..2\n", 'failed')
    like_ok(err, r'(?m)^# the answer is lost$', 'diagnostic message')

with subtest('Result.got'):
    result = is_ok(42, 42)
    got = result.got
    is_ok(got, 42, 'got')
    result = throws_ok(lambda: int('x'), ValueError)
    isa_ok(result.got, ValueError, 'exception')

with subtest('Result.passed'):
    result = is_ok(42, 42)
    boolean = result.passed
    is_ok(boolean, True, 'passed')

with subtest('Result.__bool__'):
    result = is_ok(42, 42)
    boolean = bool(result)
    is_ok(boolean, True, 'true')

with subtest('Result.cmp'):
    out, err, code = run("ok(count, 'some').cmp('<', 10, 'small enough')", setup='count = 3')
    is_ok(out, 'ok 1 - some\nok 2 - small enough\n1..2\n', 'passed')

with subtest('Result.in_'):
    out, err, code = run("isa_ok(names, list).in_('foo', \"there's a foo\")", setup="names = ['foo']")
    like_ok(out, r"(?m)^ok 2 - there's a foo$", 'passed')
    is_ok(code, 0, 'right exit status')

with subtest('Result.is_'):
    out, err, code = run("isa_ok(answer, int).is_(42, 'meaning of life')", setup='answer = 42')
    like_ok(out, r'(?m)^ok 2 - meaning of life$', 'passed')
    is_ok(code, 0, 'right exit status')

with subtest('Result.is_deeply'):
    out, err, code = run("isa_ok(got, dict).is_deeply({'a': [1, 2]}, 'deep structure')", setup="got = {'a': [1, 2]}")
    like_ok(out, r'(?m)^ok 2 - deep structure$', 'passed')
    is_ok(code, 0, 'right exit status')

with subtest('Result.isa'):
    out, err, code = run("throws_ok(lambda: {}['x'], KeyError).isa(LookupError)")
    is_ok(out, "ok 1\nok 2 - An object of class 'KeyError' isa 'LookupError'\n1..2\n", 'passed')

with subtest('Result.isnt'):
    out, err, code = run("isa_ok(foo, str).isnt('', 'got some foo')", setup="foo = 'bar'")
    like_ok(out, r'(?m)^ok 2 - got some foo$', 'passed')
    is_ok(code, 0, 'right exit status')

with subtest('Result.like'):
    out, err, code = run("isa_ok(got, str).like(r'expected', 'test name')", setup="got = 'the expected value'")
    like_ok(out, r'(?m)^ok 2 - test name$', 'passed')
    is_ok(code, 0, 'right exit status')

with subtest('Result.none'):
    out, err, code = run(
        """isnt_ok(req.headers.transfer_encoding, 'chunked').none('no "Transfer-Encoding" value')""",
        setup='import Pyjo.Message.Request\nreq = Pyjo.Message.Request.new()',
    )
    is_ok(out, 'ok 1\nok 2 - no "Transfer-Encoding" value\n1..2\n', 'passed')

with subtest('Result.not_in'):
    out, err, code = run("in_ok(names, 'foo').not_in('bar', 'no bar')", setup="names = ['foo']")
    is_ok(out, 'ok 1\nok 2 - no bar\n1..2\n', 'passed')

with subtest('Result.ok'):
    out, err, code = run("isa_ok(items, list).ok('not empty')", setup='items = [1]')
    like_ok(out, r'(?m)^ok 2 - not empty$', 'passed')
    is_ok(code, 0, 'right exit status')

with subtest('Result.unlike'):
    out, err, code = run(
        "like_ok(got, r'expected').unlike(r'unexpected', 'test name')", setup="got = 'the expected value'"
    )
    is_ok(out, 'ok 1\nok 2 - test name\n1..2\n', 'passed')

with subtest('subtest'):
    out, err, code = run(
        """
        with subtest('Parse'):
            ok(True)

        @subtest('Parse')
        def _():
            ok(True)

        passed = subtest('Parse', lambda: ok(True))
        """,
        after="is_ok(passed, True, 'passed')\ndone_testing()",
    )
    is_ok(
        out,
        ''.join(f'# Subtest: Parse\n    ok 1\n    1..1\nok {i} - Parse\n' for i in (1, 2, 3)) + 'ok 4 - passed\n1..4\n',
        'three subtests',
    )

    # The user agent fails the first time, and the delay is recorded instead of slept
    out, err, code = run(
        """
        @subtest('Remote host', reruns=2, reruns_delay=10)
        def _():
            ok(Pyjo.UserAgent.new().get('https://mojolicious.org').result.is_success, 'online request')
        """,
        setup="""
        import Pyjo.UserAgent

        import time
        import types

        requests, delays = [], []

        def new():
            requests.append(1)
            result = types.SimpleNamespace(is_success=len(requests) > 1)
            return types.SimpleNamespace(get=lambda url: types.SimpleNamespace(result=result))

        Pyjo.UserAgent.new = new
        time.sleep = delays.append
        """,
        after="is_ok(delays, [10], 'delayed once')\ndone_testing()",
    )
    is_ok(
        out,
        '# Subtest: Remote host\n    ok 1 - online request\n    1..1\nok 1 - Remote host\nok 2 - delayed once\n1..2\n',
        'the last run',
    )
    like_ok(err, r'(?m)^#     not ok 1 - online request\n', 'the failed run is a diagnostic message')
    like_ok(err, r'(?m)^# Rerunning subtest "Remote host" \(1 of 2\)\n', 'rerun')
    is_ok(code, 0, 'right exit status')

with subtest('that'):
    out, err, code = run("that(answer).isa(int).is_(42, 'meaning of life')", setup='answer = 42')
    is_ok(out, "ok 1 - An object of class 'int' isa 'int'\nok 2 - meaning of life\n1..2\n", 'no test of its own')

with subtest('throws_ok'):
    out, err, code = run(
        """
        throws_ok(lambda: [1, 2, 3][3], IndexError, 'no more elements')
        throws_ok(lambda: int('x'), "invalid literal for int() with base 10: 'x'", 'right message')
        throws_ok(lambda: int('x'), re.compile(r'invalid literal'), 'right message')
        """,
        setup='import re',
    )
    is_ok(out, 'ok 1 - no more elements\nok 2 - right message\nok 3 - right message\n1..3\n', 'passed')

with subtest('unlike_ok'):
    out, err, code = run(
        """
        unlike_ok(got, r'unexpected', 'test name')
        """,
        setup="got = 'the expected value'",
    )
    is_ok(out, 'ok 1 - test name\n1..1\n', 'passed')

done_testing()
