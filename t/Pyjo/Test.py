from Pyjo.Test import *

import os
import re
import subprocess
import sys
import tempfile
import textwrap


def run(code):
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as script:
        script.write(textwrap.dedent(code))
    try:
        p = subprocess.run([sys.executable, script.name], capture_output=True, text=True, env=os.environ)
    finally:
        os.unlink(script.name)
    stderr = re.sub(r'(?m)^([\s#]*#   at ).*( line \d+\.)$', r'\1SCRIPT\2', p.stderr)
    return p.stdout, stderr, p.returncode


with subtest('Passing tests with done_testing'):
    out, err, code = run("""
        from Pyjo.Test import *
        ok(True, 'first')
        ok(1)
        done_testing()
    """)
    is_ok(out, 'ok 1 - first\nok 2\n1..2\n', 'right output')
    is_ok(err, '', 'no diagnostics')
    is_ok(code, 0, 'right exit status')

with subtest('Plan up front'):
    out, err, code = run("""
        from Pyjo.Test import *
        plan(tests=2)
        pass_ok('first')
        pass_ok('second')
    """)
    is_ok(out, '1..2\nok 1 - first\nok 2 - second\n', 'right output')
    is_ok(code, 0, 'right exit status')

with subtest('Failure'):
    out, err, code = run("""
        from Pyjo.Test import *
        is_ok(1, 1, 'same')
        is_ok(1, 2, 'different')
        done_testing()
    """)
    is_ok(out, 'ok 1 - same\nnot ok 2 - different\n1..2\n', 'right output')
    is_ok(
        err,
        "#   Failed test 'different'\n"
        '#   at SCRIPT line 4.\n'
        '#          got: 1\n'
        '#     expected: 2\n'
        '# Looks like you failed 1 test of 2.\n',
        'right diagnostics',
    )
    is_ok(code, 1, 'exit status is the number of failures')

with subtest('Fewer tests than planned'):
    out, err, code = run("""
        from Pyjo.Test import *
        plan(tests=3)
        ok(True)
    """)
    is_ok(out, '1..3\nok 1\n', 'right output')
    is_ok(err, '# Looks like you planned 3 tests but ran 1.\n', 'right diagnostics')
    is_ok(code, 255, 'right exit status')

with subtest('No plan'):
    out, err, code = run("""
        from Pyjo.Test import *
        ok(True)
    """)
    like_ok(err, r'no plan was declared', 'right diagnostics')
    is_ok(code, 254, 'right exit status')

with subtest('Plan as a context manager'):
    out, err, code = run("""
        from Pyjo.Test import *
        with plan():
            ok(True, 'first')
            ok(True, 'second')
    """)
    is_ok(out, 'ok 1 - first\nok 2 - second\n1..2\n', 'right output')
    is_ok(err, '', 'no diagnostics')
    is_ok(code, 0, 'right exit status')

with subtest('Plan as a context manager with the number of tests'):
    out, err, code = run("""
        from Pyjo.Test import *
        with plan(tests=2):
            ok(True, 'first')
            ok(True, 'second')
    """)
    is_ok(out, '1..2\nok 1 - first\nok 2 - second\n', 'right output')
    is_ok(err, '', 'no diagnostics')
    is_ok(code, 0, 'right exit status')

with subtest('Plan as a context manager with fewer tests than planned'):
    out, err, code = run("""
        from Pyjo.Test import *
        with plan(tests=3):
            ok(True)
    """)
    is_ok(out, '1..3\nok 1\n', 'right output')
    is_ok(err, '# Looks like you planned 3 tests but ran 1.\n', 'right diagnostics')
    is_ok(code, 255, 'right exit status')

with subtest('Plan as a context manager with an exception'):
    out, err, code = run("""
        from Pyjo.Test import *
        with plan():
            ok(True)
            raise RuntimeError('Oops')
    """)
    is_ok(out, 'ok 1\n', 'no plan')
    like_ok(err, r'RuntimeError: Oops', 'exception')
    like_ok(err, r'Looks like your test exited with 255 just after 1', 'right diagnostics')
    is_ok(code, 255, 'right exit status')

with subtest('Plan as a context manager with done_testing'):
    out, err, code = run("""
        from Pyjo.Test import *
        with plan():
            ok(True)
            done_testing()
    """)
    is_ok(out, 'ok 1\n1..1\n', 'right output')
    is_ok(err, '', 'no diagnostics')
    is_ok(code, 0, 'right exit status')

with subtest('Plan as a context manager in a subtest'):
    out, err, code = run("""
        from Pyjo.Test import *
        with subtest('Inner'):
            with plan():
                ok(True)
        done_testing()
    """)
    is_ok(out, '# Subtest: Inner\n    ok 1\n    1..1\nok 1 - Inner\n1..1\n', 'right output')
    is_ok(code, 0, 'right exit status')

with subtest('Skip all'):
    out, err, code = run("""
        from Pyjo.Test import *
        plan(skip_all='not now')
        ok(False)
    """)
    is_ok(out, '1..0 # SKIP not now\n', 'right output')
    is_ok(code, 0, 'right exit status')

with subtest('Import only'):
    out, err, code = run("""
        import Pyjo.Test
    """)
    is_ok(out + err, '', 'no output')
    is_ok(code, 0, 'right exit status')

with subtest('Subtests'):
    out, err, code = run("""
        from Pyjo.Test import *

        ok(1, 'first')

        with subtest('Parse'):
            is_ok(1, 1, 'right one')

            @subtest('Nested')
            def _():
                ok(1, 'deep')

            ok(1)

        @subtest('Skipped')
        def _():
            plan(skip_all='not now')

        subtest('Empty', lambda: None)
        done_testing()
    """)
    is_ok(
        out,
        'ok 1 - first\n'
        '# Subtest: Parse\n'
        '    ok 1 - right one\n'
        '    # Subtest: Nested\n'
        '        ok 1 - deep\n'
        '        1..1\n'
        '    ok 2 - Nested\n'
        '    ok 3\n'
        '    1..3\n'
        'ok 2 - Parse\n'
        '# Subtest: Skipped\n'
        '    1..0 # SKIP not now\n'
        'ok 3 # skip not now\n'
        '# Subtest: Empty\n'
        '    1..0\n'
        '    # No tests run!\n'
        'not ok 4 - No tests run for subtest "Empty"\n'
        '1..4\n',
        'same output as Test::More',
    )
    is_ok(code, 1, 'empty subtest fails')

with subtest('Failing subtest'):
    out, err, code = run("""
        from Pyjo.Test import *
        with subtest('Inner'):
            ok(True, 'good')
            ok(False, 'bad')
        done_testing()
    """)
    is_ok(
        out,
        '# Subtest: Inner\n    ok 1 - good\n    not ok 2 - bad\n    1..2\nnot ok 1 - Inner\n1..1\n',
        'right output',
    )
    is_ok(
        err,
        "    #   Failed test 'bad'\n"
        '    #   at SCRIPT line 5.\n'
        '    # Looks like you failed 1 test of 2.\n'
        "#   Failed test 'Inner'\n"
        '#   at SCRIPT line 3.\n'
        '# Looks like you failed 1 test of 1.\n',
        'diagnostics are indented like the subtest',
    )
    is_ok(code, 1, 'right exit status')

with subtest('Subtest with its own plan and done_testing'):
    out, err, code = run("""
        from Pyjo.Test import *
        with subtest('Planned'):
            plan(tests=1)
            ok(True)
        with subtest('Done'):
            ok(True)
            done_testing(1)
        done_testing()
    """)
    is_ok(
        out,
        '# Subtest: Planned\n    1..1\n    ok 1\nok 1 - Planned\n'
        '# Subtest: Done\n    ok 1\n    1..1\nok 2 - Done\n1..2\n',
        'right output',
    )
    is_ok(code, 0, 'right exit status')

with subtest('Callback returns the result'):
    out, err, code = run("""
        from Pyjo.Test import *
        print('#', subtest('Good', lambda: ok(True)))
        print('#', subtest('Bad', lambda: ok(False)))
        done_testing()
    """)
    like_ok(out, r'# True\n', 'passed subtest returns True')
    like_ok(out, r'# False\n', 'failed subtest returns False')

with subtest('Subtest with reruns'):
    out, err, code = run("""
        from Pyjo.Test import *
        plan(tests=2)
        ok(True, 'first')
        runs = []

        @subtest('Flaky', reruns=2)
        def _():
            runs.append(1)
            ok(True, 'good')
            if len(runs) == 1:
                raise RuntimeError('boom')
            ok(len(runs) == 3, f'run {len(runs)}')
    """)
    is_ok(
        out,
        '1..2\nok 1 - first\n# Subtest: Flaky\n    ok 1 - good\n    ok 2 - run 3\n    1..2\nok 2 - Flaky\n',
        'only the last run counts',
    )
    is_ok(
        err,
        '# # Subtest: Flaky\n'
        '#     ok 1 - good\n'
        '#     1..1\n'
        '# not ok 2 - Flaky\n'
        "# #   Failed test 'Flaky'\n"
        '# #   at SCRIPT line 7.\n'
        '# RuntimeError: boom\n'
        '# Rerunning subtest "Flaky" (1 of 2)\n'
        '# # Subtest: Flaky\n'
        '#     ok 1 - good\n'
        '#     not ok 2 - run 2\n'
        "#     #   Failed test 'run 2'\n"
        '#     #   at SCRIPT line 13.\n'
        '#     1..2\n'
        '#     # Looks like you failed 1 test of 2.\n'
        '# not ok 2 - Flaky\n'
        "# #   Failed test 'Flaky'\n"
        '# #   at SCRIPT line 7.\n'
        '# Rerunning subtest "Flaky" (2 of 2)\n',
        'the failed runs are diagnostic messages',
    )
    is_ok(code, 0, 'right exit status')

    out, err, code = run("""
        from Pyjo.Test import *
        with subtest('Outer'):
            subtest('Inner', lambda: ok(False, 'never'), reruns=1)
        done_testing()
    """)
    is_ok(
        out,
        '# Subtest: Outer\n'
        '    # Subtest: Inner\n'
        '        not ok 1 - never\n'
        '        1..1\n'
        '    not ok 1 - Inner\n'
        '    1..1\n'
        'not ok 1 - Outer\n'
        '1..1\n',
        'the last run fails',
    )
    like_ok(err, r'(?m)^    #     not ok 1 - never\n', 'the failed run in the nested subtest')
    like_ok(err, r'(?m)^    # Rerunning subtest "Inner" \(1 of 1\)\n', 'rerun')
    is_ok(code, 1, 'right exit status')

    out, err, code = run("""
        from Pyjo.Test import *
        subtest('Dies', lambda: 1 / 0, reruns=1)
    """)
    is_ok(out, '# Subtest: Dies\n    1..0\nnot ok 1 - Dies\n', 'the last exception')
    like_ok(err, r'(?m)^# ZeroDivisionError: division by zero\n# Rerunning', 'rerun after the exception')
    like_ok(err, r'(?m)^ZeroDivisionError: division by zero\n', 'raised again')
    is_ok(code, 255, 'right exit status')

    out, err, code = run("""
        from Pyjo.Test import *
        subtest('Inner', lambda: bail_out('no database'), reruns=1)
    """)
    is_ok(out, '# Subtest: Inner\nBail out!  no database\n', 'no rerun of a bail out')
    is_ok(code, 255, 'right exit status')

    out, err, code = run("""
        import Pyjo.Test
        from Pyjo.Test import *
        try:
            with subtest('Block', reruns=1):
                ok(True)
        except Pyjo.Test.Error as e:
            print(e)
    """)
    is_ok(out, 'A subtest with reruns runs a function, not a block of a with statement\n', 'not a with statement')

    out, err, code = run("""
        import Pyjo.Test
        from Pyjo.Test import *
        Pyjo.Test.raise_failures()
        runs = []
        print(subtest('Flaky', lambda: runs.append(1) or ok(len(runs) == 2, 'second'), reruns=1))
    """)
    is_ok(out, 'True\n', 'no TAP')
    is_ok(err, '# AssertionError: Failed test \'second\'\n# Rerunning subtest "Flaky" (1 of 1)\n', 'rerun')
    is_ok(code, 0, 'right exit status')

with subtest('Exception'):
    out, err, code = run("""
        from Pyjo.Test import *
        ok(True)
        raise RuntimeError('boom')
    """)
    like_ok(err, r'RuntimeError: boom', 'traceback')
    like_ok(err, r'# Looks like your test exited with 255 just after 1\.', 'right diagnostics')
    is_ok(code, 255, 'right exit status')

with subtest('Exception in a subtest'):
    out, err, code = run("""
        from Pyjo.Test import *
        with subtest('Dies'):
            ok(True)
            raise RuntimeError('boom')
    """)
    is_ok(out, '# Subtest: Dies\n    ok 1\n    1..1\nnot ok 1 - Dies\n', 'subtest fails')
    is_ok(code, 255, 'right exit status')

with subtest('Bail out'):
    out, err, code = run("""
        from Pyjo.Test import *
        with subtest('Inner'):
            bail_out('no database')
        ok(True)
    """)
    is_ok(out, '# Subtest: Inner\nBail out!  no database\n', 'right output')
    is_ok(code, 255, 'right exit status')

with subtest('Skip, note and diag'):
    out, err, code = run("""
        from Pyjo.Test import *
        skip('no network', 2)
        note('a note')
        diag('a diag')
        done_testing()
    """)
    is_ok(out, 'ok 1 # skip no network\nok 2 # skip no network\n# a note\n1..2\n', 'right output')
    is_ok(err, '# a diag\n', 'diag goes to the standard error')

with subtest('Test names'):
    out, err, code = run("""
        from Pyjo.Test import *
        ok(True, 'a # in the name')
        isa_ok(1, int)
        done_testing()
    """)
    is_ok(out, "ok 1 - a \\# in the name\nok 2 - An object of class 'int' isa 'int'\n1..2\n", 'right names')

with subtest('Assertions'):
    out, err, code = run("""
        import re
        import sys
        from Pyjo.Test import *
        like_ok('Hello', ('hello', 'i'), 'like with flags')
        unlike_ok('Hello', r'bye', 'unlike')
        cmp_ok(2, '>', 1, 'cmp_ok')
        cmp_ok(None, 'is', None, 'cmp_ok is')
        in_ok([1, 2], 1, 'in_ok')
        not_in_ok([1, 2], 3, 'not_in_ok')
        none_ok(None, 'none_ok')
        is_deeply_ok({'a': [1, (2, 3)]}, {'a': [1, (2, 3)]}, 'is_deeply_ok')
        throws_ok(lambda: int('x'), ValueError, 'throws_ok class')
        throws_ok(lambda: int('x'), re.compile(r'invalid literal'), 'throws_ok regex')
        throws_ok(lambda: [][0], 'list index out of range', 'throws_ok message')
        throws_ok(lambda: sys.exit('bye'), SystemExit, 'throws_ok class that is not an Exception')
        isnt_ok(1, 2, 'isnt_ok')
        done_testing()
    """)
    is_ok(err, '', 'no diagnostics')
    is_ok(code, 0, 'all assertions pass')

with subtest('Deep structure differences'):
    out, err, code = run("""
        from Pyjo.Test import *
        is_deeply_ok({'a': [1, 2]}, {'a': [1, 3]}, 'differ')
        done_testing()
    """)
    like_ok(
        err,
        r"#     Structures begin differing at:\n#          got\['a'\]\[1\] = 2\n#     expected\['a'\]\[1\] = 3\n",
        'right diagnostics',
    )
    is_ok(code, 1, 'right exit status')

with subtest('Chains'):
    out, err, code = run("""
        from Pyjo.Test import *
        result = is_ok('42', '42', 'is').isnt('', 'isnt').like(r'^4', 'like').unlike(r'5', 'unlike')
        result = result.cmp('<', '5', 'cmp').isa(str, 'isa').ok('ok')
        print('#', bool(result), result.got)
        in_ok([1, None], 1, 'in').not_in(2, 'not in').is_deeply([1, None], 'is deeply').in_(None, 'in again')
        none_ok(None, 'none').none('none again')
        error = throws_ok(lambda: {}['x'], KeyError, 'throws').isa(LookupError, 'isa lookup')
        print('#', bool(error), repr(error.got))
        print('#', bool(ok(1).is_(1)), bool(ok(0, 'zero').is_(0, 'is zero')))
        result = that([1])
        print('#', bool(result), result.got)
        result.isa(list, 'that isa').in_(1, 'that in')
        done_testing()
    """)
    is_ok(
        out,
        'ok 1 - is\nok 2 - isnt\nok 3 - like\nok 4 - unlike\nok 5 - cmp\nok 6 - isa\nok 7 - ok\n# True 42\n'
        'ok 8 - in\nok 9 - not in\nok 10 - is deeply\nok 11 - in again\nok 12 - none\nok 13 - none again\n'
        "ok 14 - throws\nok 15 - isa lookup\n# True KeyError('x')\nok 16\nok 17\nnot ok 18 - zero\n"
        'ok 19 - is zero\n# True False\n# True [1]\nok 20 - that isa\nok 21 - that in\n1..21\n',
        'every link is a test',
    )
    is_ok(code, 1, 'one failure')

    out, err, code = run("""
        from Pyjo.Test import *
        result = (
            is_ok(1, 1, 'same')
            .is_(2, 'different')
            .is_(1, 'again')
        )
        if not result:
            diag('the chain failed')
        done_testing()
    """)
    is_ok(out, 'ok 1 - same\nnot ok 2 - different\nok 3 - again\n1..3\n', 'the chain goes on after a failure')
    is_ok(
        err,
        "#   Failed test 'different'\n"
        '#   at SCRIPT line 5.\n'
        '#          got: 1\n'
        '#     expected: 2\n'
        '# the chain failed\n'
        '# Looks like you failed 1 test of 3.\n',
        'the line of the link, and false after a failure',
    )
    is_ok(code, 1, 'right exit status')

    # The exception of throws_ok keeps no frame of the callback, whose objects, as a socket, are freed at once
    if sys.implementation.name == 'pypy':
        skip('PyPy frees objects only when its garbage collector runs', 3)
    else:
        out, err, code = run("""
            import gc
            import weakref
            from Pyjo.Test import *

            class Resource:
                pass

            def main():
                refs = []

                def fail():
                    resource = Resource()
                    refs.append(weakref.ref(resource))
                    raise ValueError('bad')

                result = throws_ok(fail, ValueError, 'raised').isa(Exception, 'an exception')
                print('#', refs[0]() is None, type(result.got).__name__)

            gc.disable()
            main()
            done_testing()
        """)
        is_ok(out, 'ok 1 - raised\nok 2 - an exception\n# True ValueError\n1..2\n', 'freed without the collector')
        is_ok(err, '', 'no diagnostics')
        is_ok(code, 0, 'right exit status')

with subtest('Exceptions'):
    out, err, code = run("""
        import Pyjo.Test
        from Pyjo.Test import *
        Pyjo.Test.raise_failures()
        ok(True, 'passed')
        try:
            is_ok(1, 2, 'different')
        except AssertionError as e:
            print(e)
        try:
            ok(False)
        except AssertionError as e:
            print(e)
    """)
    is_ok(out, "Failed test 'different'\n         got: 1\n    expected: 2\nFailed test\n", 'raised, no TAP')
    is_ok(err, '', 'no diagnostics')
    is_ok(code, 0, 'no plan needed')

    out, err, code = run("""
        import Pyjo.Test
        from Pyjo.Test import *
        Pyjo.Test.raise_failures()
        print(bool(is_ok(1, 1, 'same').isnt(2, 'other')))
        try:
            is_ok(1, 1, 'same').like(r'2', 'like').is_(2, 'never')
        except AssertionError as e:
            print(e)
    """)
    is_ok(out, "True\nFailed test 'like'\n                  1\n    doesn't match '2'\n", 'the first failure raises')
    is_ok(err, '', 'no diagnostics')
    is_ok(code, 0, 'right exit status')

    out, err, code = run("""
        import unittest
        import Pyjo.Test
        from Pyjo.Test import *
        Pyjo.Test.raise_failures()
        print(bool(plan(tests=3)), done_testing(), skip('later', 2))
        with subtest('Skipped'):
            plan(skip_all='not here')
            ok(False, 'never')
        print(subtest('Passed', lambda: ok(True)))
        diag('a diagnostic message')
        note('a note')
        try:
            plan(skip_all='not now')
        except unittest.SkipTest as e:
            print(f'skipped: {e}')
        try:
            bail_out('No database connection')
        except Pyjo.Test.BailOut as e:
            print(f'bailed out: {e}')
    """)
    is_ok(
        out,
        'True True True\nTrue\n# a note\nskipped: not now\nbailed out: No database connection\n',
        'plans, skips, subtests and bail out',
    )
    is_ok(err, '# a diagnostic message\n', 'diagnostic message')
    is_ok(code, 0, 'right exit status')

    out, err, code = run("""
        import Pyjo.Test
        from Pyjo.Test import *
        Pyjo.Test.raise_failures()
        with subtest('Failed'):
            ok(False, 'inner')
    """)
    like_ok(err, r"(?m)^AssertionError: Failed test 'inner'$", 'raised out of the subtest')
    is_ok(out, '', 'no TAP')
    is_ok(code, 1, 'died of the exception')

    out, err, code = run("""
        import Pyjo.Test
        from Pyjo.Test import *
        Pyjo.Test.raise_failures()
        Pyjo.Test.raise_failures(False)
        ok(True)
        done_testing()
    """)
    is_ok(out, 'ok 1\n1..1\n', 'TAP again')
    is_ok(code, 0, 'right exit status')

    out, err, code = run("""
        import Pyjo.Test
        from Pyjo.Test import *
        with Pyjo.Test.raise_failures():
            with Pyjo.Test.raise_failures(False):
                ok(True, 'printed')
            with Pyjo.Test.raise_failures():
                pass
            try:
                ok(False, 'raised')
            except AssertionError as e:
                print(e)
        ok(True, 'printed again')
        done_testing()
    """)
    is_ok(out, "ok 1 - printed\nFailed test 'raised'\nok 2 - printed again\n1..2\n", 'the mode before each block')
    is_ok(code, 0, 'right exit status')

done_testing()
