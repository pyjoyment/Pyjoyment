import Pyjo.DOM
import Pyjo.Prove

from Pyjo.Test import *

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

SCRIPTS = {
    'pass.py': """
        from Pyjo.Test import *
        ok(True, 'first')
        with subtest('Nested'):
            ok(True, 'deep')
        done_testing()
    """,
    'fail.py': """
        from Pyjo.Test import *
        ok(True)
        ok(False)
        ok(False)
        done_testing()
    """,
    'skip.py': """
        from Pyjo.Test import *
        plan(skip_all='not now')
    """,
    'first_fails.py': """
        from Pyjo.Test import *
        ok(False)
        done_testing()
    """,
    'noplan.py': """
        from Pyjo.Test import *
        ok(True)
    """,
    'badplan.py': """
        from Pyjo.Test import *
        plan(tests=3)
        ok(True)
    """,
    'die.py': """
        from Pyjo.Test import *
        ok(True)
        raise RuntimeError('boom')
    """,
    'bail.py': """
        from Pyjo.Test import *
        bail_out('no database')
    """,
    'sleep.py': """
        from Pyjo.Test import *
        import time
        ok(True)
        time.sleep(60)
        done_testing()
    """,
    'pid.py': """
        from Pyjo.Test import *
        import os, time
        with open('pid', 'w') as f:
            f.write(str(os.getpid()))
        ok(True)
        time.sleep(60)
        done_testing()
    """,
    'stderr.py': """
        from Pyjo.Test import *
        import sys
        print('first warning', file=sys.stderr)
        ok(True)
        print('second warning', file=sys.stderr)
        done_testing()
    """,
    'directives.py': """
        print('ok 1', 'not ok 2 # TODO later', 'ok 3 # TODO fixed', 'ok 4 # SKIP why', '1..4', sep='\\n')
    """,
    'flood.py': """
        from Pyjo.Test import *
        import sys
        for n in range(1, 11):
            print(f'line {n}', file=sys.stderr)
        ok(True)
        done_testing()
    """,
    'env.py': """
        from Pyjo.Test import *
        import os
        is_ok(os.environ.get('PYJO_PROVE_OPTS'), None, 'no options of the harness')
        done_testing()
    """,
    'verbose.py': """
        from Pyjo.Test import *
        import os
        diag(f"PYJO_HARNESS_IS_VERBOSE={os.environ.get('PYJO_HARNESS_IS_VERBOSE')}")
        ok(True)
        done_testing()
    """,
    'subtest.py': """
        from Pyjo.Test import *
        import sys
        ok(True, 'fine')
        is_ok(1, 2, 'one is <two>')
        with subtest('Nested | pipe'):
            ok(True, 'deep')
            ok(False, 'deeper')
        print('warning \\x1b[31mred\\x1b[0m', file=sys.stderr)
        done_testing()
    """,
    'child.py': """
        from Pyjo.Test import *
        import subprocess, sys
        subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        ok(True)
        done_testing()
    """,
}


def prove(*args, scripts=SCRIPTS, env=None):
    out, err, code = prove_stderr(*args, scripts=scripts, env=env)
    return out, code


def prove_stderr(*args, scripts=SCRIPTS, env=None):
    out, err, code, files = prove_files(*args, scripts=scripts, env=env)
    return out, err, code


# The output, the error, the exit status, and the files that the harness writes
def prove_files(*args, scripts=SCRIPTS, env=None, files=()):
    with tempfile.TemporaryDirectory() as tmp:
        for name, code in scripts.items():
            path = os.path.join(tmp, *name.split('/'))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(textwrap.dedent(code))
        # Not the options of a harness that runs this test
        env = {k: v for k, v in os.environ.items() if k != 'PYJO_PROVE_OPTS'} | {'PYTHONPATH': ROOT} | (env or {})
        p = subprocess.run([sys.executable, '-m', 'Pyjo.Prove', *args], cwd=tmp, env=env, capture_output=True)
        written = {}
        for name in files:
            if os.path.exists(path := os.path.join(tmp, name)):
                # As written, without the newlines of the text mode, which the reports do not have
                with open(path, encoding='utf-8', newline='') as f:
                    written[name] = f.read()
    # Bytes, as the universal newlines of text would turn the carriage returns of the count into newlines; only the CRLF
    # of the text mode of Windows is a newline
    return p.stdout.decode().replace('\r\n', '\n'), p.stderr.decode().replace('\r\n', '\n'), p.returncode, written


def prove_tty(*args, env=None, scripts=SCRIPTS):
    # The output to a terminal, where the terminal turns a newline into a carriage return and a newline
    with tempfile.TemporaryDirectory() as tmp:
        for name, code in scripts.items():
            with open(os.path.join(tmp, name), 'w') as f:
                f.write(textwrap.dedent(code))
        env = (
            {k: v for k, v in os.environ.items() if k not in ('NO_COLOR', 'PYJO_PROVE_OPTS')}
            | {'TERM': 'xterm', 'PYTHONPATH': ROOT}
            | (env or {})
        )
        master, slave = os.openpty()
        p = subprocess.Popen(
            [sys.executable, '-m', 'Pyjo.Prove', *args], cwd=tmp, env=env, stdout=slave, stderr=subprocess.DEVNULL
        )
        os.close(slave)
        out = b''
        try:
            while chunk := os.read(master, 4096):
                out += chunk
        except OSError:
            # Linux reports the end of the output of a terminal as EIO
            pass
        os.close(master)
        p.wait()
    return out.decode().replace('\r\n', '\n'), p.returncode


def colored(code, text):
    return re.escape(f'\033[{code}m{text}\033[0m')


def interrupt(*args):
    # Ctrl-C once the script that sleeps has started; SIGINT may be ignored in the process of the tests
    with tempfile.TemporaryDirectory() as tmp:
        for name in ('pass.py', 'pid.py'):
            with open(os.path.join(tmp, name), 'w') as f:
                f.write(textwrap.dedent(SCRIPTS[name]))
        env = dict(os.environ, PYTHONPATH=ROOT)
        p = subprocess.Popen(
            [sys.executable, '-m', 'Pyjo.Prove', *args, 'pass.py', 'pid.py'],
            cwd=tmp,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
        )
        path = os.path.join(tmp, 'pid')
        deadline = time.monotonic() + 30
        while not os.path.exists(path) and time.monotonic() < deadline:
            time.sleep(0.1)
        time.sleep(0.2)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=30)
        with open(path) as f:
            pid = int(f.read())
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    return out, err, p.returncode, alive


def result(lines):
    r = Pyjo.Prove.Result('test.py')
    for line in textwrap.dedent(lines).strip('\n').split('\n'):
        Pyjo.Prove.parse(r, line)
    Pyjo.Prove.finish(r)
    return r


with subtest('Parse a passing script'):
    r = result("""
        TAP version 14
        ok 1 - first
        # Subtest: Nested
            ok 1 - deep
            not ok 2 - ignored, belongs to the subtest
            1..2
        ok 2 - Nested
        ok 3 # SKIP no network
        not ok 4 # TODO not done yet
        1..4
    """)
    is_ok(r.planned, 4, 'right plan')
    is_ok(r.tests, 4, 'right number of tests')
    is_ok(r.failed, [], 'no failures')
    is_ok(r.skipped, 1, 'one skipped')
    is_ok(r.errors, [], 'no errors')
    ok(r.passed, 'passed')

with subtest('Parse failures'):
    r = result("""
        ok 1
        not ok 2 - bad
        ok 3 # TODO unexpectedly fixed
        1..3
    """)
    is_ok(r.failed, [2], 'right failures')
    is_ok(r.todo_passed, [3], 'TODO test passed')
    ok(not r.passed, 'failed')

with subtest('Parse a skipped script'):
    r = result('1..0 # SKIP not now')
    is_ok(r.skip_all, 'not now', 'right reason')
    ok(r.passed, 'passed')

with subtest('Parse errors'):
    is_ok(result('ok 1').errors, ['No plan found in TAP output'], 'no plan')
    is_ok(result('1..2\nok 1').errors, ['Bad plan.  You planned 2 tests but ran 1.'], 'fewer tests than planned')
    is_ok(
        result('ok 1\nok 3\n1..2').errors,
        ['Tests out of sequence.  Found (3) but expected (2)'],
        'out of sequence',
    )
    is_ok(result('1..1\nok 1\n1..1').errors, ['More than one plan found in TAP output'], 'two plans')
    is_ok(result('Bail out!  broken').bail_out, 'broken', 'bail out')
    is_ok(result('ok 1 - a \\# b # SKIP why').skipped, 1, 'escaped hash in the description')
    r = Pyjo.Prove.Result('test.py', tests=1, exit_status=-9, timed_out=0.5)
    Pyjo.Prove.finish(r)
    is_ok(r.errors, ['Timed out after 0.5 seconds'], 'timed out')

with subtest('Parse test points'):
    r = Pyjo.Prove.Result('test.py')
    for at, line in enumerate(
        [
            'ok 1 - first',
            '# Subtest: Nested',
            '    ok 1 - deep',
            '    not ok 2 - deeper',
            '    1..2',
            'not ok 2 - Nested',
            '# a comment after it',
            'ok 3 - a \\# b # SKIP why',
            'not ok 4 # TODO later',
            '1..4',
        ]
    ):
        Pyjo.Prove.parse(r, line, at=float(at))
    is_deeply_ok(
        [(p.number, p.name, p.ok, p.directive, p.reason) for p in r.points],
        [
            (1, 'first', True, None, ''),
            (2, 'Nested', False, None, ''),
            (3, 'a # b', True, 'skip', 'why'),
            (4, '', False, 'todo', 'later'),
        ],
        'test points',
    )
    is_deeply_ok([p.time for p in r.points], [0.0, 5.0, 2.0, 1.0], 'time since the line before the test point')
    is_deeply_ok(
        r.points[1].diagnostics,
        ['# Subtest: Nested', '    ok 1 - deep', '    not ok 2 - deeper', '    1..2', '# a comment after it'],
        'subtest and comment of a failure',
    )
    is_deeply_ok([p.diagnostics for p in (r.points[0], r.points[2])], [[], []], 'no diagnostics of the others')
    is_deeply_ok(
        [(p.failed, p.skipped) for p in r.points],
        [(False, False), (True, False), (False, True), (False, True)],
        'states',
    )

with subtest('Diagnostics of the standard error'):
    r = result("""
        not ok 1 - one
        # Subtest: Two
            not ok 1 - inner
            1..1
        not ok 2 - Two
        ok 3
        1..3
    """)
    r = Pyjo.Prove.Result(
        'test.py',
        stderr=[
            "#   Failed test 'one'",
            '#   at t/test.py line 3.',
            '#          got: 1',
            "    #   Failed test 'inner'",
            '    #   at t/test.py line 6.',
            "#   Failed test 'Two'",
            '#   at t/test.py line 5.',
            'a warning',
            '# Looks like you failed 2 tests of 3.',
        ],
    )
    for line in [
        'not ok 1 - one',
        '# Subtest: Two',
        '    not ok 1 - inner',
        '    1..1',
        'not ok 2 - Two',
        'ok 3',
        '1..3',
    ]:
        Pyjo.Prove.parse(r, line)
    Pyjo.Prove.finish(r)
    is_deeply_ok(
        r.points[0].diagnostics, ["#   Failed test 'one'", '#   at t/test.py line 3.', '#          got: 1'], 'first'
    )
    is_deeply_ok(
        r.points[1].diagnostics,
        [
            '# Subtest: Two',
            '    not ok 1 - inner',
            '    1..1',
            "    #   Failed test 'inner'",
            '    #   at t/test.py line 6.',
            "#   Failed test 'Two'",
            '#   at t/test.py line 5.',
        ],
        'subtest, with its diagnostics before the ones of the test point',
    )

with subtest('Find scripts'):
    with tempfile.TemporaryDirectory() as tmp:
        for name in ('b.py', 'a.py', 'notes.txt', 'sub/c.py'):
            path = os.path.join(tmp, *name.split('/'))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'w').close()
        found = Pyjo.Prove.find_scripts([tmp], '.py', recurse=False)
        is_ok([os.path.relpath(p, tmp) for p in found], ['a.py', 'b.py'], 'sorted, not recursive')
        found = Pyjo.Prove.find_scripts([tmp], '.py', recurse=True)
        is_ok([os.path.relpath(p, tmp) for p in found], ['a.py', 'b.py', os.path.join('sub', 'c.py')], 'recursive')

with subtest('Run passing and skipped scripts'):
    out, code = prove('pass.py', 'skip.py')
    like_ok(out, r'(?m)^pass\.py \.+ ok$', 'passing script')
    like_ok(out, r'(?m)^skip\.py \.+ skipped: not now$', 'skipped script')
    like_ok(out, r'(?m)^All tests successful\.$', 'summary')
    like_ok(out, r'(?m)^Files=2, Tests=2, \d+ wallclock secs$', 'counts')
    like_ok(out, r'(?m)^Result: PASS$', 'result')
    is_ok(code, 0, 'right exit status')

with subtest('Scripts that require a version of Python'):

    def requires(specifier):
        return f"""
            # /// script
            # requires-python = "{specifier}"
            # ///
            from Pyjo.Test import *
            ok(True)
            done_testing()
        """

    version = '.'.join(map(str, sys.version_info[:3]))
    minor = '.'.join(map(str, sys.version_info[:2]))
    scripts = {
        'newer.py': requires('>=99'),
        'older.py': requires('<3'),
        'this.py': requires(f'=={version}'),
        'wildcard.py': requires(f'=={minor}.*'),
        'not_wildcard.py': requires(f'!={minor}.*'),
        'compatible.py': requires(f'~={minor}'),
        'range.py': requires(f'>={minor}, <99'),
        'out_of_range.py': requires(f'>={minor}, <3'),
        'syntax.py': """
            # /// script
            # requires-python = ">=99"
            # ///
            this is not Python
        """,
        'other_block.py': """
            # /// pyproject
            # requires-python = ">=99"
            # ///
            from Pyjo.Test import *
            ok(True)
            done_testing()
        """,
        'invalid.py': requires('3.12'),
        'invalid_wildcard.py': requires('>=3.*'),
        'invalid_toml.py': """
            # /// script
            # requires-python = >=3
            # ///
        """,
    }
    out, code = prove(*scripts, scripts=scripts)
    like_ok(out, r'(?m)^newer\.py \.+ skipped: requires Python >=99$', 'newer Python')
    like_ok(out, r'(?m)^older\.py \.+ skipped: requires Python <3$', 'older Python')
    like_ok(out, r'(?m)^this\.py \.+ ok$', 'this version')
    like_ok(out, r'(?m)^wildcard\.py \.+ ok$', 'wildcard')
    like_ok(out, r'(?m)^not_wildcard\.py \.+ skipped: ', 'excluded wildcard')
    like_ok(out, r'(?m)^compatible\.py \.+ ok$', 'compatible release')
    like_ok(out, r'(?m)^range\.py \.+ ok$', 'range')
    like_ok(out, r'(?m)^out_of_range\.py \.+ skipped: ', 'out of range')
    like_ok(out, r'(?m)^syntax\.py \.+ skipped: requires Python >=99$', 'not compiled')
    like_ok(out, r'(?m)^other_block\.py \.+ ok$', 'other block')
    like_ok(out, r'(?m)^invalid\.py \.+ Dubious$', 'invalid specifier')
    like_ok(out, r'(?m)^  Invalid script metadata: Invalid requires-python: 3\.12$', 'invalid specifier reported')
    like_ok(out, r'(?m)^invalid_wildcard\.py \.+ Dubious$', 'invalid wildcard')
    like_ok(out, r'(?m)^invalid_toml\.py \.+ Dubious$', 'invalid TOML')
    is_ok(code, 1, 'right exit status')

    scripts = {'newer.py': requires('>=99'), 'this.py': requires(f'=={version}')}
    out, code = prove('--exec', f'{sys.executable} -X utf8', *scripts, scripts=scripts)
    like_ok(out, r'(?m)^newer\.py \.+ skipped: requires Python >=99$', 'newer Python of the command')
    like_ok(out, r'(?m)^this\.py \.+ ok$', 'this version of the command')
    is_ok(code, 0, 'right exit status')

    # A command that runs the script, but not the question of its version, which runs the script instead
    scripts = {'unknown.py': requires('>=99')}
    command = f'{sys.executable} -c "import runpy, sys; runpy.run_path(sys.argv[1])"'
    out, code = prove('--exec', command, *scripts, scripts=scripts)
    like_ok(out, r'(?m)^unknown\.py \.+ ok$', 'run when the version of the command is unknown')

    out, code = prove('--exec', 'pyjo-does-not-exist', 'pass.py')
    like_ok(out, r'(?m)^pass\.py \.+ Dubious$', 'a command that cannot run')
    like_ok(out, r"(?m)^  Can't run pyjo-does-not-exist: ", 'reason in the summary')
    is_ok(code, 1, 'right exit status')

with subtest('Run failing scripts'):
    out, code = prove('fail.py', 'noplan.py', 'badplan.py', 'die.py')
    like_ok(out, r'(?m)^fail\.py \.+ Failed 2/3 subtests$', 'failures')
    like_ok(out, r'(?m)^  Failed tests:  2, 3$', 'failed test numbers')
    like_ok(out, r'(?m)^  No plan found in TAP output$', 'no plan')
    like_ok(out, r'(?m)^  Bad plan\.  You planned 3 tests but ran 1\.$', 'bad plan')
    like_ok(out, r'(?m)^  Non-zero exit status: 255$', 'died')
    like_ok(out, r'(?m)^Result: FAIL$', 'result')
    is_ok(code, 1, 'right exit status')

with subtest('Bail out stops the run'):
    out, code = prove('bail.py', 'pass.py')
    like_ok(out, r'(?m)^bail\.py \.+ Bailout called\.  Further testing stopped:  no database$', 'bail out')
    unlike_ok(out, r'pass\.py', 'next script not run')
    is_ok(code, 1, 'right exit status')

with subtest('Directories, recursion and parallel jobs'):
    scripts = {'t/a.py': SCRIPTS['pass.py'], 't/sub/b.py': SCRIPTS['pass.py'], 't/sub/c.py': SCRIPTS['skip.py']}
    out, code = prove(scripts=scripts)
    like_ok(out, r'(?m)^Files=1, ', 'only the top directory of t by default')
    out, code = prove('-r', '-j', '3', scripts=scripts)
    like_ok(out, r'(?m)^Files=3, Tests=4, ', 'recursive, in parallel')
    is_ok(code, 0, 'right exit status')
    # Not in prove: as many jobs as the processors
    out, code = prove('-r', '-j', '0', scripts=scripts)
    like_ok(out, r'(?m)^Files=3, Tests=4, ', 'recursive, in parallel on the processors')
    is_ok(code, 0, 'right exit status')

with subtest('Timeout'):
    started = time.monotonic()
    out, code = prove('--timeout', '2', 'sleep.py', 'pass.py')
    like_ok(out, r'(?m)^sleep\.py \.+ Timed out$', 'script stopped')
    like_ok(out, r'(?m)^  Timed out after 2 seconds$', 'reason in the summary')
    like_ok(out, r'(?m)^pass\.py \.+ ok$', 'next script still runs')
    is_ok(code, 1, 'right exit status')
    ok(time.monotonic() - started < 30, 'the run does not wait for the script')

    started = time.monotonic()
    out, code = prove('--timeout', '2', 'child.py')
    like_ok(out, r'(?m)^child\.py \.+ Timed out$', 'a process of the script keeps its output open')
    ok(time.monotonic() - started < 30, 'the process of the script is killed with it')

    out, code = prove('--timeout', '30', 'pass.py')
    like_ok(out, r'(?m)^pass\.py \.+ ok$', 'a script within the time')
    is_ok(code, 0, 'right exit status')

# Not in prove: a process that the script starts at once is killed with it, also when the harness is slow to put the
# script in its job of Windows, as the launcher of a virtual environment starts the interpreter at once, in a job of its
# own, whose processes break away from it; the job is a second late here
with subtest('A process that the script starts at once'):
    harness = textwrap.dedent("""
        import sys, time
        import Pyjo.Prove
        job = Pyjo.Prove._job
        Pyjo.Prove._job = lambda pid: (time.sleep(1), job(pid))[1]
        sys.argv[0] = 'prove'
        sys.exit(Pyjo.Prove.main())
    """)
    removed = True
    started = time.monotonic()
    tmp = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp, 'child.py'), 'w') as f:
            f.write(textwrap.dedent(SCRIPTS['child.py']))
        env = {k: v for k, v in os.environ.items() if k != 'PYJO_PROVE_OPTS'} | {'PYTHONPATH': ROOT}
        args = [sys.executable, '-c', harness, '--capture-stderr', '--timeout', '2', 'child.py']
        p = subprocess.run(args, cwd=tmp, env=env, capture_output=True)
    finally:
        try:
            shutil.rmtree(tmp)
        except OSError:
            removed = False
            shutil.rmtree(tmp, ignore_errors=True)
    like_ok(p.stdout.decode().replace('\r\n', '\n'), r'(?m)^child\.py \.+ Timed out$', 'script stopped')
    ok(time.monotonic() - started < 30, 'the run does not wait for the process of the script')
    ok(removed, 'no process of the script left in its directory')

with subtest('Ctrl-C'):
    # Ctrl-C of a console of Windows reaches all its processes, and a signal cannot be sent to one of them
    if sys.platform == 'win32':
        skip('no SIGINT for a process on Windows', 10)
    else:
        out, err, code, alive = interrupt()
        is_ok(code, -signal.SIGINT, 'dies of the signal')
        unlike_ok(out, r'Result:', 'no summary')
        unlike_ok(err, r'Traceback', 'no traceback')
        ok(not alive, 'the running script is killed')

        out, err, code, alive = interrupt('--trap')
        like_ok(out, r'(?m)^pass\.py \.+ ok$', 'finished script')
        like_ok(err, r'(?m)^Test run interrupted!$', 'interrupted')
        like_ok(out, r'(?m)^Files=1, Tests=2, ', 'summary of the finished scripts')
        like_ok(out, r'(?m)^Result: FAIL$', 'result')
        is_ok(code, 1, 'right exit status')
        ok(not alive, 'the running script is killed')

with subtest('Capture the standard error'):
    out, err, code = prove_stderr('stderr.py', 'pass.py')
    like_ok(err, r'(?m)^first warning$', 'standard error passes through by default')
    unlike_ok(err, r'stderr\.py: ', 'without the name of the script')

    out, err, code = prove_stderr('-j', '2', '--capture-stderr', 'stderr.py', 'pass.py')
    like_ok(out, r'(?m)^stderr\.py \.+ ok$', 'script passes')
    is_ok(err, 'stderr.py: first warning\nstderr.py: second warning\n', 'after the name of the script, in order')
    is_ok(code, 0, 'right exit status')

    out, err, code = prove_stderr('--capture-stderr', '--timeout', '2', 'child.py')
    like_ok(out, r'(?m)^child\.py \.+ Timed out$', 'a process of the script keeps its output open')

# The event loop of the harness without the debug mode of asyncio, which the development mode of Python turns on, as it
# would write the slow callbacks of the harness to the standard error, among the lines of the scripts
with subtest('Development mode'):
    code = textwrap.dedent("""
        import asyncio
        import sys

        import Pyjo.Prove

        run = Pyjo.Prove.run

        async def checked(*args, **kwargs):
            print(f'debug: {asyncio.get_running_loop().get_debug()}', file=sys.stderr)
            return await run(*args, **kwargs)

        Pyjo.Prove.run = checked
        sys.exit(Pyjo.Prove.main(['pass.py']))
    """)
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'pass.py'), 'w') as f:
            f.write(textwrap.dedent(SCRIPTS['pass.py']))
        env = {k: v for k, v in os.environ.items() if k != 'PYJO_PROVE_OPTS'} | {
            'PYTHONPATH': ROOT,
            'PYTHONDEVMODE': '1',
        }
        p = subprocess.run([sys.executable, '-c', code], cwd=tmp, env=env, capture_output=True)
    like_ok(p.stderr.decode().replace('\r\n', '\n'), r'(?m)^debug: False$', 'no debug mode of asyncio')
    is_ok(p.returncode, 0, 'right exit status')

with subtest('Limit the lines of the standard error'):
    out, err, code = prove_stderr('--capture-stderr', 'flood.py')
    is_ok(err, ''.join(f'flood.py: line {n}\n' for n in range(1, 11)), 'all lines by default')

    out, err, code = prove_stderr('--capture-stderr', '--stderr-lines', '4', 'flood.py')
    is_ok(
        err,
        'flood.py: line 1\nflood.py: line 2\nflood.py: [6 lines left out]\nflood.py: line 9\nflood.py: line 10\n',
        'the first half and the last half',
    )
    is_ok(code, 0, 'right exit status')

    out, err, code = prove_stderr('--capture-stderr', '--stderr-lines', '3', 'flood.py')
    is_ok(
        err,
        'flood.py: line 1\nflood.py: line 2\nflood.py: [7 lines left out]\nflood.py: line 10\n',
        'the larger half first',
    )

    out, err, code = prove_stderr('--capture-stderr', '--stderr-lines', '1', 'flood.py')
    is_ok(err, 'flood.py: line 1\nflood.py: [9 lines left out]\n', 'one line')

    out, err, code = prove_stderr('--capture-stderr', '--stderr-lines', '0', 'flood.py')
    is_ok(err, 'flood.py: [10 lines left out]\n', 'no lines')

    out, err, code = prove_stderr('--capture-stderr', '--stderr-lines', '10', 'flood.py')
    is_ok(err, ''.join(f'flood.py: line {n}\n' for n in range(1, 11)), 'as many lines as the limit')

    out, err, code = prove_stderr('--capture-stderr', '--stderr-lines', '-1', 'flood.py')
    like_ok(err, r'invalid number of lines: -1', 'negative number of lines')
    is_ok(code, 2, 'right exit status')

with subtest('Run without tests'):
    out, code = prove('skip.py')
    like_ok(out, r'(?m)^All tests successful\.$', 'summary')
    like_ok(out, r'(?m)^Files=1, Tests=0, ', 'counts')
    like_ok(out, r'(?m)^Result: NOTESTS$', 'result')
    is_ok(code, 0, 'right exit status')

with subtest('Colors'):
    out, err, code = prove_stderr('-j', '2', '--capture-stderr', 'pass.py', 'fail.py', 'stderr.py')
    unlike_ok(out, r'\033', 'no colors when the output is not a terminal')
    unlike_ok(err, r'\033', 'no colors when the standard error is not a terminal')

    out, err, code = prove_stderr('--color', '--capture-stderr', 'pass.py', 'skip.py', 'stderr.py', 'directives.py')
    like_ok(out, rf'(?m)^pass\.py \.+ {colored(32, "ok")}$', 'green ok')
    like_ok(out, rf'(?m)^skip\.py \.+ {colored(33, "skipped: not now")}$', 'yellow skipped')
    like_ok(out, rf'(?m)^{colored(32, "All tests successful.")}$', 'green summary')
    like_ok(out, rf'(?m)^{colored(33, "directives.py: TODO passed:  3")}$', 'yellow TODO passed')
    like_ok(out, rf'(?m)^Result: {colored(32, "PASS")}$', 'green PASS')
    like_ok(err, rf'(?m)^{colored(31, "stderr.py: first warning")}$', 'red standard error')
    is_ok(code, 0, 'right exit status')

    out, code = prove('--color', 'fail.py', 'die.py', 'bail.py')
    like_ok(out, rf'(?m)^fail\.py \.+ {colored(31, "Failed 2/3 subtests")}$', 'red failure')
    like_ok(out, rf'(?m)^die\.py \.+ {colored(31, "Dubious")}$', 'red dubious')
    like_ok(out, rf'(?m)^bail\.py \.+ {colored(31, "Bailout called.  Further testing stopped:  no database")}$', 'red')
    like_ok(out, rf'(?m)^  {colored(31, "Failed tests:  2, 3")}$', 'red failed tests')
    like_ok(out, rf'(?m)^  {colored(31, "Non-zero exit status: 255")}$', 'red error')
    like_ok(out, rf'(?m)^  {colored(31, "Bail out:  no database")}$', 'red bail out')
    like_ok(out, rf'(?m)^Result: {colored(31, "FAIL")}$', 'red FAIL')

    out, code = prove('--color', '--timeout', '2', 'sleep.py')
    like_ok(out, rf'(?m)^sleep\.py \.+ {colored(31, "Timed out")}$', 'red timeout')

    out, code = prove('--color', 'skip.py')
    like_ok(out, rf'(?m)^Result: {colored(33, "NOTESTS")}$', 'yellow NOTESTS')

    out, code = prove('--color', '-v', 'fail.py', 'directives.py')
    like_ok(out, r'(?m)^ok 1$', 'passed test point as it is')
    like_ok(out, rf'(?m)^{colored(31, "not ok 2")}$', 'red failed test point')
    like_ok(out, rf'(?m)^{colored(33, "not ok 2 # TODO later")}$', 'yellow TODO test point')
    like_ok(out, rf'(?m)^{colored(33, "ok 4 # SKIP why")}$', 'yellow skipped test point')

    out, code = prove('--color', '-v', '-j', '2', 'fail.py', 'pass.py')
    like_ok(out, rf'(?m)^{colored(31, "not ok 2")}$', 'red failed test point of parallel jobs')

    out, code = prove('--color', '--no-color', 'pass.py')
    unlike_ok(out, r'\033', 'no colors with --no-color')
    out, code = prove('-c', 'pass.py')
    like_ok(out, rf'(?m)^pass\.py \.+ {colored(32, "ok")}$', 'colors with -c')
    out, code = prove('--color', '--nocolor', 'pass.py')
    unlike_ok(out, r'\033', 'no colors with --nocolor')

with subtest('Colors on a terminal'):
    if not hasattr(os, 'openpty'):
        skip('no terminal', 5)
    else:
        out, code = prove_tty('--no-count', 'pass.py')
        like_ok(out, rf'(?m)^pass\.py \.+ {colored(32, "ok")}$', 'colors by default')
        out, code = prove_tty('--no-count', '--no-color', 'pass.py')
        unlike_ok(out, r'\033', 'no colors with --no-color')
        out, code = prove_tty('--no-count', 'pass.py', env={'NO_COLOR': '1'})
        unlike_ok(out, r'\033', 'no colors with NO_COLOR')
        out, code = prove_tty('--no-count', '--color', 'pass.py', env={'NO_COLOR': '1'})
        like_ok(out, rf'(?m)^pass\.py \.+ {colored(32, "ok")}$', '--color over NO_COLOR')
        out, code = prove_tty('--no-count', 'pass.py', env={'TERM': 'dumb'})
        unlike_ok(out, r'\033', 'no colors on a dumb terminal')

with subtest('Count'):
    out, code = prove('pass.py')
    unlike_ok(out, r'/\?', 'no count when the output is not a terminal')

    out, code = prove('--count', 'pass.py', 'skip.py')
    like_ok(out, r'^\rpass\.py \.+ \rpass\.py \.+ 1/\? ', 'name, then the count of the first test')
    like_ok(out, r'\r +\rpass\.py \.+ ok\n', 'count cleared before the result')
    like_ok(out, r'\r +\rskip\.py \.+ skipped: not now\n', 'count of a skipped script cleared')
    out, code = prove('--count', '--nocount', 'pass.py')
    unlike_ok(out, r'/\?', 'no count with --nocount')
    out, code = prove('--count', '-v', 'pass.py')
    unlike_ok(out, r'/\?', 'no count with -v')

    out, code = prove('--count', '--color', 'first_fails.py')
    like_ok(out, rf'\rfirst_fails\.py \.+ {colored(31, "1/? ")}', 'red count of a failure')

    out, code = prove('--count', '-j', '2', 'pass.py', 'fail.py')
    like_ok(out, r'\r===\( +\d+;\d+  \d/\?  \d/\? \)=+', 'line of the scripts that run')
    like_ok(out, r'\r +\rfail\.py \.+ Failed 2/3 subtests\n', 'line cleared before the result')

with subtest('Count on a terminal'):
    if not hasattr(os, 'openpty'):
        skip('no terminal', 3)
    else:
        out, code = prove_tty('--no-color', 'pass.py')
        like_ok(out, r'\rpass\.py \.+ 1/\? ', 'count by default')
        out, code = prove_tty('--no-color', '--no-count', 'pass.py')
        unlike_ok(out, r'/\?', 'no count with --no-count')
        out, code = prove_tty('--no-color', '-v', 'pass.py')
        unlike_ok(out, r'/\?', 'no count with -v')

with subtest('Include directories'):
    scripts = {
        'mymod.py': 'NAME = "mine"\n',
        't/import.py': """
            from Pyjo.Test import *
            import mymod
            is_ok(mymod.NAME, 'mine')
            done_testing()
        """,
    }
    out, code = prove('t/import.py', scripts=scripts)
    like_ok(out, r'(?m)^t/import\.py \.+ Dubious$', 'module not found')
    out, code = prove('-I', '.', 't/import.py', scripts=scripts)
    like_ok(out, r'(?m)^t/import\.py \.+ ok$', 'module found with -I')
    out, code = prove('-l', 't/import.py', scripts=scripts)
    like_ok(out, r'(?m)^t/import\.py \.+ ok$', 'module found with -l')
    out, code = prove('--lib', 't/import.py', scripts=scripts)
    like_ok(out, r'(?m)^t/import\.py \.+ ok$', 'module found with --lib')

with subtest('Options from the environment'):
    out, code = prove('pass.py', env={'PYJO_PROVE_OPTS': '-v'})
    like_ok(out, r'(?m)^ok 1 - first$', 'option from PYJO_PROVE_OPTS')
    out, code = prove('--no-color', 'pass.py', env={'PYJO_PROVE_OPTS': '--color'})
    unlike_ok(out, r'\033', 'the command line overrides PYJO_PROVE_OPTS')
    out, code = prove('pass.py', env={'PYJO_PROVE_OPTS': f"--exec '{sys.executable} -X utf8'"})
    like_ok(out, r'(?m)^pass\.py \.+ ok$', 'split as a shell splits words')
    out, code = prove('env.py', env={'PYJO_PROVE_OPTS': '--color'})
    like_ok(out, r'Result: \033\[32mPASS', 'test script does not get PYJO_PROVE_OPTS')
    out, err, code = prove_stderr('pass.py', env={'PYJO_PROVE_OPTS': "'"})
    like_ok(err, r'PYJO_PROVE_OPTS: No closing quotation', 'invalid quoting')
    is_ok(code, 2, 'right exit status')

with subtest('Verbose'):
    out, code = prove('-v', 'pass.py')
    like_ok(out, r'(?m)^ok 1 - first$', 'TAP output shown')
    like_ok(out, r'(?m)^    ok 1 - deep$', 'subtest output shown')
    out, err, code = prove_stderr('-v', 'verbose.py', env={'PYJO_HARNESS_IS_VERBOSE': ''})
    like_ok(err, r'PYJO_HARNESS_IS_VERBOSE=1$', 'PYJO_HARNESS_IS_VERBOSE for the test scripts')
    out, err, code = prove_stderr('verbose.py', env={'PYJO_HARNESS_IS_VERBOSE': ''})
    like_ok(err, r'PYJO_HARNESS_IS_VERBOSE=\n', 'no PYJO_HARNESS_IS_VERBOSE without -v')

with subtest('JUnit XML'):
    out, err, code, files = prove_files(
        '--capture-stderr',
        '--formatter',
        'junit=report.xml',
        'pass.py',
        'subtest.py',
        'skip.py',
        'directives.py',
        'die.py',
        files=['report.xml'],
    )
    is_ok(code, 1, 'right exit status')
    like_ok(out, r'(?m)^Result: FAIL$', 'usual output')
    xml = files['report.xml']
    like_ok(xml, r'^<\?xml version="1\.0" encoding="UTF-8"\?>\n<testsuites ', 'declaration')
    unlike_ok(xml, r'\x1b', 'no escapes of the terminal')
    report = Pyjo.DOM.new(xml)
    ok(report.xml, 'XML')
    suites = report.at('testsuites')
    is_deeply_ok(
        {k: suites.attr(k) for k in ('name', 'tests', 'failures', 'errors', 'skipped')},
        {'name': 'Pyjo.Prove', 'tests': '12', 'failures': '2', 'errors': '1', 'skipped': '3'},
        'totals',
    )
    is_deeply_ok(
        report.find('testsuite').map(lambda e: e.attr('name')).to_list(),
        ['pass.py', 'subtest.py', 'skip.py', 'directives.py', 'die.py'],
        'a test suite for each script',
    )
    suite = report.at('testsuite[name="subtest.py"]')
    is_deeply_ok(
        {k: suite.attr(k) for k in ('tests', 'failures', 'errors', 'skipped')},
        {'tests': '3', 'failures': '2', 'errors': '0', 'skipped': '0'},
        'no error of the exit status of the failures',
    )
    is_deeply_ok(
        suite.find('testcase').map(lambda e: e.attr('name')).to_list(),
        ['1 - fine', '2 - one is <two>', '3 - Nested | pipe'],
        'a test case for each test point',
    )
    case = suite.at('testcase[name="2 - one is <two>"]')
    is_ok(case.attr('classname'), 'subtest.py', 'class name')
    is_ok(case.attr('file'), 'subtest.py', 'file')
    is_ok(case.attr('line'), '5', 'line of the assertion')
    like_ok(case.attr('time'), r'^\d+\.\d{3}$', 'time')
    is_ok(case.at('failure').attr('message'), 'not ok 2 - one is <two>', 'message of the failure')
    like_ok(
        case.at('failure').text,
        r"^#   Failed test 'one is <two>'\n#   at .*subtest\.py line 5\.\n#          got: 1",
        'diagnostics',
    )
    case = suite.at('testcase[name="3 - Nested | pipe"]')
    is_ok(case.attr('line'), '8', 'line of the assertion of the subtest')
    like_ok(case.at('failure').text, r'^# Subtest: Nested \| pipe\n    ok 1 - deep\n    not ok 2 - deeper', 'subtest')
    ok(suite.at('testcase[name="1 - fine"] > *') is None, 'passed')
    like_ok(suite.at('system-out').text, r'^ok 1 - fine\nnot ok 2', 'TAP output of a script that failed')
    like_ok(suite.at('system-err').text, r'(?m)^warning red$', 'standard error')
    ok(report.at('testsuite[name="pass.py"] system-out') is None, 'no TAP output of a script that passed')
    is_ok(report.at('testsuite[name="skip.py"] testcase').attr('name'), 'skip.py', 'test case of the script')
    is_ok(report.at('testsuite[name="skip.py"] skipped').attr('message'), 'not now', 'skipped script')
    is_deeply_ok(
        report.find('testsuite[name="directives.py"] testcase')
        .map(lambda e: e.at('skipped') and e.at('skipped').attr('message'))
        .to_list(),
        [None, 'later', None, 'why'],
        'TODO test and skipped test',
    )
    error = report.at('testsuite[name="die.py"] testcase[name="die.py"] error')
    is_ok(error.attr('message'), 'No plan found in TAP output', 'error of the script')
    is_ok(error.text, 'No plan found in TAP output\nNon-zero exit status: 255', 'errors of the script')

with subtest('Summary in Markdown'):
    out, err, code, files = prove_files(
        '--capture-stderr',
        '--formatter=markdown=summary.md',
        'pass.py',
        'subtest.py',
        'skip.py',
        'die.py',
        files=['summary.md'],
    )
    md = files['summary.md']
    like_ok(md, r'^### Pyjo\.Prove\n\n\| Files \| Tests \| Passed ✅ \| Skipped ⚠️ \| Failed ❌ \| Time ⏱️ \|\n', 'table')
    like_ok(md, r'(?m)^\| 4 \| 8 \| 4 \| 1 \| 3 \| \d+s \|$', 'numbers')
    like_ok(md, r'(?m)^Result: \*\*FAIL\*\*$', 'result')
    like_ok(md, r'(?m)^\| subtest\.py 2 - one is &lt;two&gt; \| ❌ failed \|$', 'failed test point')
    like_ok(md, r'(?m)^\| subtest\.py 3 - Nested \\\| pipe \| ❌ failed \|$', 'pipe of a cell')
    like_ok(md, r'(?m)^\| die\.py \| ❌ No plan found in TAP output \|$', 'error of a script')
    unlike_ok(md, r'subtest\.py \| ❌ Non-zero exit status', 'no error of the exit status of the failures')
    like_ok(md, r"<details><summary>subtest\.py</summary>\n\n````text\n#   Failed test 'one is <two>'\n", 'diagnostics')
    like_ok(md, r'(?m)^warning red$', 'standard error, without its escapes')
    like_ok(md, r'(?m)^RuntimeError: boom$', 'traceback')
    unlike_ok(md, r'pass\.py', 'nothing of a script that passed')

    out, err, code, files = prove_files('--formatter', 'markdown=summary.md', 'pass.py', files=['summary.md'])
    is_ok(
        files['summary.md'],
        '### Pyjo.Prove\n\n| Files | Tests | Passed ✅ | Skipped ⚠️ | Failed ❌ | Time ⏱️ |\n'
        '| ---: | ---: | ---: | ---: | ---: | ---: |\n| 1 | 2 | 2 | 0 | 0 | 0s |\n\nResult: **PASS**\n',
        'summary of a run that passed',
    )

    with tempfile.TemporaryDirectory() as tmp:
        summary = os.path.join(tmp, 'summary.md')
        with open(summary, 'w') as f:
            f.write('Before\n')
        prove('--formatter', f'markdown={summary}', 'pass.py')
        # In UTF-8, as the harness writes it, and not in the encoding of the locale of Windows before Python 3.15
        with open(summary, encoding='utf-8') as f:
            like_ok(f.read(), r'^### Pyjo\.Prove\n', 'written over')

with subtest('Formatters'):
    out, err, code, files = prove_files(
        '--formatter',
        'junit=report.xml',
        '--formatter',
        'markdown=summary.md',
        'pass.py',
        files=['report.xml', 'summary.md'],
    )
    like_ok(out, r'^pass\.py \.+ ok\nAll tests successful\.\n', 'usual output')
    like_ok(files['report.xml'], r'^<\?xml ', 'JUnit XML')
    like_ok(files['summary.md'], r'^### Pyjo\.Prove\n', 'summary')

    out, code = prove('--formatter', 'junit', 'pass.py')
    like_ok(
        out,
        r'(?s)^<\?xml version="1\.0" encoding="UTF-8"\?>\n<testsuites .*</testsuites>\n\Z',
        'JUnit XML in the place of the output',
    )
    unlike_ok(out, r'Result: PASS', 'no usual output')
    is_ok(code, 0, 'right exit status')

    out, code = prove('--formatter', 'markdown', '--formatter', 'junit=report.xml', 'fail.py')
    like_ok(out, r'^### Pyjo\.Prove\n', 'summary in the place of the output')
    is_ok(code, 1, 'right exit status')

    out, err, code, files = prove_files(
        '--formatter', 'console=console.txt', '--formatter', 'markdown', 'pass.py', files=['console.txt']
    )
    like_ok(out, r'^### Pyjo\.Prove\n', 'summary in the place of the output')
    like_ok(files['console.txt'], r'^pass\.py \.+ ok\nAll tests successful\.\n', 'usual output to a file')

    out, err, code = prove_stderr('--formatter', 'junit', '--formatter', 'markdown', 'pass.py')
    like_ok(
        err, r'--formatter: one formatter writes in the place of the output, not more', 'two in the place of the output'
    )
    is_ok(code, 2, 'right exit status')
    out, err, code = prove_stderr('--formatter', 'xml', 'pass.py')
    like_ok(err, r"--formatter: unknown formatter 'xml', one of console, junit, markdown", 'unknown formatter')
    is_ok(code, 2, 'right exit status')

done_testing()
