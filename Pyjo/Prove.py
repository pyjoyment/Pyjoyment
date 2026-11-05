r"""
Pyjo.Prove - Run test scripts
=============================
::

    $ python -m Pyjo.Prove t/Pyjo t/docs
    $ python -m Pyjo.Prove -r -j 4 t
    $ pyjo-prove -v t/Pyjo/URL.py

:mod:`Pyjo.Prove` runs test scripts which print the
`Test Anything Protocol <https://testanything.org/>`_ (TAP), such as the ones
written with :mod:`Pyjo.Test`, and reports their results. It is inspired by
Perl's ``prove`` and accepts the options of it that make sense for Python.

A directory runs every script with the extension ``.py`` in it, and with
``-r`` in its subdirectories too. Without arguments it runs ``t``.

A test script passes when it exits with status ``0``, declares a plan, runs as
many tests as planned and none of them fails, except the ``TODO`` tests. A
plan of ``1..0 # SKIP reason`` skips the whole script. ``Bail out!`` stops the
whole run. Indented lines belong to subtests and are not parsed: the parent
test point stands for the whole subtest.

A script with the inline metadata of
`PEP 723 <https://peps.python.org/pep-0723/>`_ is skipped without running when
the Python that runs it does not satisfy its ``requires-python``, as a script
with the syntax of a newer Python, which an older one cannot compile, so that
the script cannot skip itself. ::

    # /// script
    # requires-python = ">=3.14"
    # ///

The summary ends with ``Result: PASS`` when every test script passed,
``Result: FAIL`` when one did not, and ``Result: NOTESTS`` when they passed
without running a test, as when every one of them was skipped. The exit status is ``0`` when every test script passed and ``1`` otherwise.
Ctrl-C (``SIGINT``) stops the run: the test scripts that are running are
killed, with the processes they started, and the harness dies of the signal,
or with ``--trap`` prints the summary of the test scripts that have finished.

Options
-------

``-r``, ``--recurse``
    Run the test scripts in subdirectories too.

``-j N``, ``--jobs N``
    Run up to N test scripts at the same time, or with ``0`` as many as the
    processors that the harness may use. ::

        $ python -m Pyjo.Prove -j 0 -r t

    ``prove`` has no such value.

``-v``, ``--verbose``
    Print the TAP output of each test script, and set the environment
    variable ``PYJO_HARNESS_IS_VERBOSE`` of the test scripts to ``1``, as
    ``prove`` sets ``HARNESS_IS_VERBOSE``, which tells :mod:`Pyjo.Test.Pyjo`
    to log everything.

``-I DIR``, ``--include DIR``
    Add the directory to ``PYTHONPATH`` of the test scripts. Can be repeated.

``-l``, ``--lib``
    Add the current directory to ``PYTHONPATH`` of the test scripts, as
    ``-I .`` does, where ``prove`` adds ``lib``.

``--ext EXT``
    Extension of the test scripts in a directory, ``.py`` by default.

``--exec CMD``
    Command that runs a test script, the current Python interpreter by default.
    A script whose command cannot start fails with the reason.

``--timeout SECONDS``
    The most time a test script may run, no limit by default. A test script
    that runs longer is killed, with the processes it started, and fails.

``--trap``
    Print the summary of the test scripts that have finished when Ctrl-C
    interrupts the run.

``--capture-stderr``
    Keep the standard error of each test script and print it after the line of
    its result, each line after the name of the script, instead of letting it
    through as the script writes it, where the scripts that run at the same
    time with ``-j`` mix it. ::

        t/Pyjo/URL.py ........ ok
        t/Pyjo/URL.py: ResourceWarning: unclosed <socket.socket ...>

    ``prove`` has no such option: its ``--merge`` puts the standard error into
    the TAP output, which shows it with ``-v`` only.

``--stderr-lines N``
    With ``--capture-stderr``, print at most N lines of the standard error of
    a test script, no limit by default: the first half of them and the last
    half, which ends with what the script said last, and between them a line
    that tells how many were left out. ::

        t/Pyjo/URL.py: [922554 lines left out]

``--count``, ``--no-count``, ``--nocount``
    Show the X/Y count of the tests of a test script while it runs or not,
    renewed once a second. By default it is shown when the output goes to a
    terminal, and never with ``-v``. With ``-j``, a line shows the number of
    the tests of all the test scripts, the seconds of the run and the count of
    each test script that runs. ::

        t/Pyjo/URL.py ........ 12/?
        ===(     158;3  12/?  40/40  3/? )======================================

    ``prove`` shows it on a terminal only, even with ``--count``.

``-c``, ``--color``, ``--no-color``, ``--nocolor``
    Color the output or not. By default it is colored when it goes to a
    terminal, unless ``NO_COLOR`` is set or ``TERM`` is ``dumb``: the result of
    a test script that passed and the summary of a run that passed are green,
    what failed is red, what was skipped and the ``TODO`` tests are yellow, and
    so is ``NOTESTS``. With ``--capture-stderr``, the standard error of a
    test script is red.

``--formatter NAME[=FILE]``
    Write the results as the formatter ``NAME`` to the file, or in the place
    of the usual output without one, which only one formatter can do. Can be
    repeated. The formatters are:

    ``console``
        The usual output, a line for each test script and the summary, which
        goes to the standard output unless another formatter writes there.
    ``junit``
        The JUnit XML of the results, which the reporters of CI systems read,
        as :func:`junit` makes it.
    ``markdown``
        The summary of the results in Markdown, as the one of a job of GitHub
        Actions, with a table of what failed and the diagnostics of each test
        script that did not pass, as :func:`markdown` makes it.

    The diagnostics of the failures come from the standard error of the test
    scripts, which ``--capture-stderr`` captures. ::

        $ python -m Pyjo.Prove --formatter junit -r t > report.xml
        $ python -m Pyjo.Prove --capture-stderr --formatter junit=report.xml \\
            --formatter "markdown=$GITHUB_STEP_SUMMARY" -r t

    ``prove`` takes the class of one formatter, which writes in the place of
    the usual output, as ``TAP::Formatter::JUnit``.

Environment
-----------

``PYJO_PROVE_OPTS``
    Options that go before the ones of the command line, which override them,
    split as a shell splits words, as the command of ``--exec`` is, where a
    backslash is kept on Windows, as in its paths. The test scripts do not
    get it, so that a test script that runs :mod:`Pyjo.Prove` itself runs it
    without them. ::

        $ PYJO_PROVE_OPTS='-l -j 4' python -m Pyjo.Prove -r t

    ``prove`` reads its options from ``.proverc`` instead.

``PYJO_HARNESS_ACTIVE``
    Set to ``1`` for the test scripts, as ``prove`` sets ``HARNESS_ACTIVE``,
    which tells :mod:`Pyjoyment.Commands` not to list the commands.

Functions
---------
"""

import argparse
import asyncio
import collections
import contextlib
import io
import operator
import os
import re
import shlex
import signal
import sys
import time
import tomllib

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TextIO


if TYPE_CHECKING:
    import Pyjo.DOM


__all__ = ['Point', 'Result', 'find_scripts', 'finish', 'junit', 'main', 'markdown', 'parse', 'run', 'run_script']


RE_VERSION = re.compile(r'TAP version (\d+)\s*$')
RE_PLAN = re.compile(r'1\.\.(\d+)\s*(?:#\s*(.*?))?\s*$')
RE_TEST = re.compile(
    r'(not )?ok\b\s*(\d+)?\s*(?:-\s*)?((?:\\.|[^#\\])*?)\s*(?:#\s*(skip|todo)\b\s*(.*?))?\s*$',
    re.IGNORECASE,
)
RE_BAIL_OUT = re.compile(r'Bail out!\s*(.*?)\s*$')
RE_SKIP = re.compile(r'skip\b\s*(.*)', re.IGNORECASE)
RE_METADATA = re.compile(r'(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$')
RE_FAILED = re.compile(r'#\s+Failed (?:\(TODO\) )?test\b')
RE_AT = re.compile(r'\bat (.+?) line (\d+)\.?$')
RE_ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')
RE_NOT_XML = re.compile(r'[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]')
RE_SPECIFIER = re.compile(r'\s*(~=|===|==|!=|<=|>=|<|>)\s*v?(\d+(?:\.\d+)*)(\.\*)?\s*')


@dataclass
class Point:
    """
    A test point of the TAP output of a test script, with the lines of its
    subtest and the diagnostics after it when it fails.
    """

    number: int
    name: str = ''
    ok: bool = True
    directive: str | None = None
    reason: str = ''
    time: float = 0.0
    diagnostics: list[str] = field(default_factory=lambda: [])

    @property
    def failed(self) -> bool:
        """::

            failed = point.failed

        True if the test point failed, and is not a ``TODO`` test.
        """
        return not self.ok and self.directive != 'todo'

    @property
    def skipped(self) -> bool:
        """::

            skipped = point.skipped

        True if the test point was skipped, or is a ``TODO`` test that failed,
        as expected.
        """
        return self.directive == 'skip' or (not self.ok and self.directive == 'todo')


@dataclass
class Result:
    """
    Result of a test script: what its TAP output says and how it exited.
    """

    path: str
    planned: int | None = None
    skip_all: str | None = None
    tests: int = 0
    failed: list[int] = field(default_factory=lambda: [])
    todo_passed: list[int] = field(default_factory=lambda: [])
    skipped: int = 0
    bail_out: str | None = None
    exit_status: int = 0
    timed_out: float | None = None
    errors: list[str] = field(default_factory=lambda: [])
    output: list[str] = field(default_factory=lambda: [])
    stderr: list[str] = field(default_factory=lambda: [])
    stderr_left_out: int = 0
    points: list[Point] = field(default_factory=lambda: [])
    time: float = 0.0
    pending: list[str] = field(default_factory=lambda: [])
    mark: float | None = None

    @property
    def passed(self) -> bool:
        """::

            ok = result.passed

        True if the test script passed.
        """
        return not self.failed and not self.errors and self.bail_out is None


def parse(result: Result, line: str, at: float | None = None) -> None:
    """::

        result = Result('t/test.py')
        for line in output.splitlines():
            parse(result, line)
        parse(result, line, at=time.monotonic())

    Parse a line of TAP output into the result, which came at the time ``at``,
    of :func:`time.monotonic`, for the time of its test point.
    """
    result.output.append(line)

    # The lines of a subtest, and its name, belong to the test point that follows them, and a comment to the one before
    # it, as the diagnostics of a failure come after it
    if not line or line[0].isspace() or line.startswith('# Subtest'):
        if line:
            result.pending.append(line)
        return
    if line.startswith('#'):
        if result.points and not result.points[-1].ok:
            result.points[-1].diagnostics.append(line)
        return

    if m := RE_TEST.match(line):
        not_ok, number, name, directive, reason = m.groups()
        result.tests += 1
        point = Point(
            result.tests,
            re.sub(r'\\(.)', r'\1', name or ''),
            not not_ok,
            (directive or '').lower() or None,
            reason or '',
        )
        if at is not None:
            point.time = max(at - (result.mark if result.mark is not None else at), 0.0)
            result.mark = at
        if not_ok:
            point.diagnostics = result.pending
        result.pending = []
        result.points.append(point)
        if number is not None and int(number) != result.tests:
            result.errors.append(f'Tests out of sequence.  Found ({number}) but expected ({result.tests})')
        directive = (directive or '').lower()
        if directive == 'skip':
            result.skipped += 1
        if not_ok and directive != 'todo':
            result.failed.append(result.tests)
        if not not_ok and directive == 'todo':
            result.todo_passed.append(result.tests)
        return

    if m := RE_PLAN.match(line):
        if result.planned is not None:
            result.errors.append('More than one plan found in TAP output')
            return
        result.planned = int(m.group(1))
        if result.planned == 0 and (skip := RE_SKIP.match(m.group(2) or '')):
            result.skip_all = skip.group(1)
        return

    if m := RE_BAIL_OUT.match(line):
        result.bail_out = m.group(1)
        return

    if RE_VERSION.match(line) and len(result.output) > 1:
        result.errors.append('TAP version must be the first line of the output')


def finish(result: Result) -> None:
    """::

        finish(result)

    Check the result once the test script has exited: the plan, the number of
    tests and the exit status. The diagnostics of the failures in the standard
    error that was captured, as :mod:`Pyjo.Test` and ``Test::More`` write them,
    go to the test points that failed, in their order, with the diagnostics of
    the subtest before each of them.
    """
    _diagnostics(result)
    if result.bail_out is not None:
        return
    if result.timed_out is not None:
        result.errors.append(f'Timed out after {result.timed_out:g} seconds')
        return
    if result.planned is None:
        result.errors.append('No plan found in TAP output')
    elif result.planned != result.tests:
        result.errors.append(f'Bad plan.  You planned {result.planned} tests but ran {result.tests}.')
    if result.exit_status:
        result.errors.append(f'Non-zero exit status: {result.exit_status}')


async def run_script(
    path: str,
    command: Sequence[str],
    env: dict[str, str],
    *,
    verbose: bool = False,
    stream: bool = False,
    timeout: float | None = None,
    capture_stderr: bool = False,
    stderr_lines: int | None = None,
    color: bool = False,
    progress: Callable[[Result], object] | None = None,
    cwd: str | None = None,
) -> Result:
    """::

        result = await run_script('t/test.py', [sys.executable], dict(os.environ))
        result = await run_script('t/test.py', [sys.executable], dict(os.environ), timeout=60)
        result = await run_script('t/test.py', [sys.executable], dict(os.environ), capture_stderr=True)
        result = await run_script('t/test.py', [sys.executable], dict(os.environ), capture_stderr=True, stderr_lines=100)
        result = await run_script('t/test.py', [sys.executable], dict(os.environ), progress=print)
        result = await run_script('t/test.py', [sys.executable], dict(os.environ), cwd='project')

    Run a test script and parse its TAP output. The standard error of the
    script goes to the standard error of this process, or with
    ``capture_stderr`` to the lines of :attr:`Result.stderr`, at most
    ``stderr_lines`` of them, the first half and the last half, with the number
    of the lines between them in :attr:`Result.stderr_left_out`. With ``verbose``
    and ``stream``, the TAP output is printed as it comes, colored with
    ``color``. ``progress`` is called with the result when the script starts
    and after each of its tests. A script that runs
    longer than ``timeout`` seconds is killed, with the processes it started.
    A script whose ``requires-python`` the Python of the command does not
    satisfy is skipped without running.
    The script runs in the directory ``cwd``, the current one by default, which
    its path is relative to.
    """
    result = Result(path)
    try:
        requires = _requires_python(os.path.join(cwd, path) if cwd is not None else path)
        if requires is not None and (version := await _python(command)) is not None:
            if not _satisfies(version, requires):
                result.planned = 0
                result.skip_all = f'requires Python {requires}'
                return result
    except ValueError as e:
        result.errors.append(f'Invalid script metadata: {e}')
        return result

    # The script leads a process group of its own, so that the processes it starts are killed with it, or on Windows
    # joins a job, before it runs, as it starts suspended, so that a process that it starts at once joins the job too, as
    # the interpreter that the launcher of a virtual environment starts in a job of its own, whose processes break away
    # from it; a command that cannot start fails the script with the reason, and the run goes on
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE if capture_stderr else None,
            env=env,
            cwd=cwd,
            process_group=0 if hasattr(os, 'killpg') else None,
            creationflags=_SUSPENDED,
        )
    except OSError as e:
        result.errors.append(f"Can't run {command[0]}: {e.strerror or e}")
        return result
    job = _job(process.pid)
    if not _resume(process.pid):
        _kill(process, job)
    assert process.stdout is not None
    started = result.mark = time.monotonic()
    if progress is not None:
        progress(result)
    stderr = (
        asyncio.create_task(_read_lines(process.stderr, result, stderr_lines)) if process.stderr is not None else None
    )
    try:
        async with asyncio.timeout(timeout):
            while raw := await process.stdout.readline():
                line = raw.decode('utf-8', 'replace').rstrip('\r\n')
                tests = result.tests
                parse(result, line, at=time.monotonic())
                if progress is not None and result.tests != tests:
                    progress(result)
                if verbose and stream:
                    print(_tap_line(line, color), flush=True)
            result.exit_status = await process.wait()
    except TimeoutError:
        result.timed_out = timeout
        _kill(process, job)
        result.exit_status = await process.wait()
    finally:
        # Ctrl-C reaches the foreground process group only, not the one of the script, which the harness waits for,
        # so that it does not outlive the harness
        if process.returncode is None:
            _kill(process, job)
            await process.wait()
        _close_job(job)
        # A process that the script started may keep the standard error open after the script exits
        if stderr is not None:
            try:
                await asyncio.wait_for(stderr, 5)
            except TimeoutError:
                pass
    result.time = time.monotonic() - started
    finish(result)
    return result


def find_scripts(paths: Sequence[str], ext: str, recurse: bool) -> list[str]:
    """::

        scripts = find_scripts(['t'], '.py', recurse=True)

    Expand directories into the test scripts in them, sorted by name. The
    names of the scripts found in a directory have ``/`` between their
    levels on every system, as ``prove`` gives them.
    """
    scripts: list[str] = []
    for path in paths:
        if not os.path.isdir(path):
            scripts.append(path)
            continue
        found: list[str] = []
        for root, dirs, files in os.walk(path):
            dirs.sort()
            # The names with /, as prove gives them on every system
            found.extend(os.path.join(root, f).replace(os.sep, '/') for f in files if f.endswith(ext))
            if not recurse:
                break
        scripts.extend(sorted(found))
    return scripts


async def run(
    scripts: Sequence[str],
    command: Sequence[str] | None = None,
    env: dict[str, str] | None = None,
    *,
    jobs: int = 1,
    verbose: bool = False,
    timeout: float | None = None,
    trap: bool = False,
    capture_stderr: bool = False,
    stderr_lines: int | None = None,
    color: bool | None = None,
    count: bool | None = None,
    console: bool = True,
) -> list[Result]:
    """::

        results = asyncio.run(run(['t/a.py', 't/b.py'], jobs=2))
        results = asyncio.run(run(['t/a.py', 't/b.py'], jobs=0))
        results = asyncio.run(run(['t/a.py', 't/b.py'], timeout=60, trap=True))
        results = asyncio.run(run(['t/a.py', 't/b.py'], jobs=2, capture_stderr=True))
        results = asyncio.run(run(['t/a.py', 't/b.py'], jobs=2, capture_stderr=True, stderr_lines=1000))
        results = asyncio.run(run(['t/a.py', 't/b.py'], color=False))
        results = asyncio.run(run(['t/a.py', 't/b.py'], count=False))
        results = asyncio.run(run(['t/a.py', 't/b.py'], console=False))

    Run the test scripts, up to ``jobs`` of them at the same time, or with
    ``0`` as many as the processors that the process may use, print a line
    for each of them and a summary, and return the results in the order of
    the scripts. With ``trap``, a run that
    Ctrl-C interrupts prints the summary and returns the results of the test
    scripts that have finished. The output is colored with ``color``, and the
    tests of the test scripts are counted while they run with ``count``, both
    by default when the output goes to a terminal, the count without
    ``verbose`` only. Without ``console``, nothing goes to the standard output,
    as when another formatter writes there, and the standard error that was
    captured still goes to the standard error.
    """
    command = list(command or [sys.executable])
    env = dict(os.environ if env is None else env)
    # Not in prove: no number of jobs, which is as many as the processors that the process may use
    if jobs == 0:
        jobs = _cpu_count()
    # Not in prove: PYJO_HARNESS_ACTIVE and PYJO_HARNESS_IS_VERBOSE, where prove sets HARNESS_ACTIVE and
    # HARNESS_IS_VERBOSE
    env['PYJO_HARNESS_ACTIVE'] = '1'
    if verbose:
        env['PYJO_HARNESS_IS_VERBOSE'] = '1'
    width = max((len(s) for s in scripts), default=0) + 3
    semaphore = asyncio.Semaphore(max(jobs, 1))
    bailed_out = asyncio.Event()
    started = time.monotonic()
    out_color = _color_default(sys.stdout) if color is None else color
    err_color = _color_default(sys.stderr) if color is None else color
    counter = (
        _Count(width, jobs > 1, out_color)
        if console and not verbose and (_tty(sys.stdout) if count is None else count)
        else None
    )

    finished: dict[int, Result] = {}
    interrupted = False

    async def one(i: int, path: str) -> None:
        async with semaphore:
            if bailed_out.is_set():
                return
            stream = jobs <= 1
            if stream and verbose and console:
                print(f'{path} ..', flush=True)
            result = await run_script(
                path,
                command,
                env,
                verbose=verbose and console,
                stream=stream,
                timeout=timeout,
                capture_stderr=capture_stderr,
                stderr_lines=stderr_lines,
                color=out_color,
                progress=counter.update if counter is not None else None,
            )
            if counter is not None:
                counter.finish(result)
            if verbose and not stream and console:
                print(f'{path} ..', *(_tap_line(line, out_color) for line in result.output), sep='\n', flush=True)
            if console:
                print(_status_line(result, width, out_color), flush=True)
            lines = [f'{path}: {line}' for line in result.stderr]
            if result.stderr_left_out:
                lines.insert(_head(stderr_lines or 0), f'{path}: [{result.stderr_left_out} lines left out]')
            for line in lines:
                print(_paint(line, 'red', err_color), file=sys.stderr, flush=True)
            if counter is not None:
                counter.show(refresh=True)
            if result.bail_out is not None:
                bailed_out.set()
            finished[i] = result

    try:
        if jobs <= 1:
            for i, path in enumerate(scripts):
                await one(i, path)
        else:
            await asyncio.gather(*(one(i, path) for i, path in enumerate(scripts)))
    except asyncio.CancelledError:
        # Ctrl-C, which asyncio.run() turns into the cancellation of the run
        if not trap:
            raise
        interrupted = True
        if counter is not None:
            counter.clear()
        if console:
            print(flush=True)

    done = [finished[i] for i in sorted(finished)]
    if console:
        _summary(done, time.monotonic() - started, interrupted, color=out_color, err_color=err_color)
    return done


def junit(results: Sequence[Result]) -> 'Pyjo.DOM.object':
    """::

        report = junit(results)
        Path('report.xml').write_text(str(report))

    The JUnit XML of the results, as the reporters of CI systems read it, as a
    :mod:`Pyjo.DOM` object: a ``testsuite`` for each test script, with a
    ``testcase`` for each of its test points, whose ``failure`` has the
    diagnostics of a test point that failed, the lines of its subtest and the
    comments after it, and whose ``skipped`` has the reason of a test point
    that was skipped, or is a ``TODO`` test that failed. A ``testcase`` named
    after the script stands for what the script did wrong as a whole, as an
    ``error``, as dying, a bad plan or a timeout, or for all its tests that it
    skipped. A test case has the ``line`` of the first ``at FILE line N`` of
    its diagnostics, which :mod:`Pyjo.Test` writes, where the reporters
    annotate the failure. The TAP output of a script that did not pass, and
    the standard error that was captured, are its ``system-out`` and
    ``system-err``.
    """
    import Pyjo.DOM

    report = Pyjo.DOM.new('<?xml version="1.0" encoding="UTF-8"?>\n<testsuites/>')
    root = report.at('testsuites')
    assert root is not None
    totals: collections.Counter[str] = collections.Counter()
    for result in results:
        counts: collections.Counter[str] = collections.Counter()
        cases: list[Pyjo.DOM.object] = []
        for point in result.points:
            name = _point_name(point)
            case = report.new_tag(
                'testcase', classname=result.path, name=_xml(name), file=result.path, time=f'{point.time:.3f}'
            )
            if point.failed:
                counts['failures'] += 1
                _junit_line(case, point.diagnostics)
                _junit_child(case, 'failure', '\n'.join(point.diagnostics), message=f'not ok {name}', type='TAP')
            elif point.skipped:
                counts['skipped'] += 1
                reason = point.reason or ('TODO' if point.directive == 'todo' else 'skipped')
                _junit_child(case, 'skipped', None, message=reason)
            cases.append(case)
        problems = _problems(result)
        if problems or result.skip_all is not None:
            case = report.new_tag('testcase', classname=result.path, name=result.path, file=result.path, time='0.000')
            if problems:
                counts['errors'] += 1
                _junit_child(case, 'error', '\n'.join([*problems, *result.pending]), message=problems[0], type='TAP')
            else:
                counts['skipped'] += 1
                _junit_child(case, 'skipped', None, message=result.skip_all or 'skipped')
            cases.append(case)
        suite = report.new_tag(
            'testsuite',
            name=result.path,
            tests=str(len(cases)),
            failures=str(counts['failures']),
            errors=str(counts['errors']),
            skipped=str(counts['skipped']),
            time=f'{result.time:.3f}',
            file=result.path,
        )
        tag = suite.at('testsuite')
        assert tag is not None
        for case in cases:
            tag.append_content(case)
        if not result.passed:
            _junit_child(suite, 'system-out', '\n'.join(result.output))
        if result.stderr:
            stderr = list(result.stderr)
            if result.stderr_left_out:
                stderr.insert(_head(len(stderr)), f'[{result.stderr_left_out} lines left out]')
            _junit_child(suite, 'system-err', '\n'.join(stderr))
        root.append_content(suite).append_content('\n')
        totals.update(counts, tests=len(cases))
    root.attr(
        name='Pyjo.Prove',
        tests=str(totals['tests']),
        failures=str(totals['failures']),
        errors=str(totals['errors']),
        skipped=str(totals['skipped']),
        time=f'{sum(result.time for result in results):.3f}',
    )
    return report


def markdown(results: Sequence[Result], elapsed: float, title: str = 'Pyjo.Prove') -> str:
    """::

        summary = markdown(results, 37.2)
        summary = markdown(results, 37.2, title='Tests of Pyjo')

    The summary of the results in Markdown, as GitHub Actions shows it as the
    summary of a job: the numbers of the files and of the tests that passed,
    were skipped and failed, as the test cases of :func:`junit` count them,
    with a test script that skipped all its tests or failed as a whole as one
    of them, the time, and the result, ``PASS``,
    ``FAIL`` or ``NOTESTS``, with a table of what failed, and the diagnostics
    and the standard error of each test script that did not pass, folded.
    """
    points = [point for result in results for point in result.points]
    failed = [result for result in results if not result.passed]
    failures = sum(point.failed for point in points) + sum(bool(_problems(result)) for result in results)
    skipped = sum(point.skipped for point in points) + sum(r.skip_all is not None for r in results)
    passed = sum(not point.failed and not point.skipped for point in points)
    status = 'FAIL' if failed else 'PASS' if points else 'NOTESTS'
    lines = [
        f'### {title}',
        '',
        '| Files | Tests | Passed ✅ | Skipped ⚠️ | Failed ❌ | Time ⏱️ |',
        '| ---: | ---: | ---: | ---: | ---: | ---: |',
        f'| {len(results)} | {passed + skipped + failures} | {passed} | {skipped} | {failures} | {elapsed:.0f}s |',
        '',
        f'Result: **{status}**',
    ]
    if failed:
        lines += ['', '| Test | Result |', '| :--- | :--- |']
        for result in failed:
            path = _cell(result.path)
            lines += [f'| {path} {_cell(_point_name(point))} | ❌ failed |' for point in result.points if point.failed]
            lines += [f'| {path} | ❌ {_cell(problem)} |' for problem in _problems(result)]
        for result in failed:
            # The diagnostics of the failures, and the standard error but them, as warnings and tracebacks
            details = [line for point in result.points if point.failed for line in point.diagnostics]
            details += [*result.pending, *(line for line in result.stderr if not line.lstrip().startswith('#'))]
            details = [RE_ANSI.sub('', line) for line in details]
            if len(details) > _DETAILS:
                details[_DETAILS // 2 : -_DETAILS // 2] = [f'[{len(details) - _DETAILS} lines left out]']
            if details:
                fence = '`' * max([4, *(len(m) + 1 for m in re.findall(r'`{3,}', '\n'.join(details)))])
                lines += ['', f'<details><summary>{_html(result.path)}</summary>', '', f'{fence}text', *details]
                lines += [fence, '', '</details>']
    return '\n'.join(lines) + '\n'


def main(argv: Sequence[str] | None = None) -> int:
    """::

        sys.exit(main(['-r', 't']))

    Command line interface: parse the options, after the ones of
    ``PYJO_PROVE_OPTS``, run the test scripts and return the exit status.
    """
    parser = argparse.ArgumentParser(prog='pyjo-prove', description='Run test scripts which print TAP.')
    parser.add_argument('-r', '--recurse', action='store_true', help='run the test scripts in subdirectories too')
    parser.add_argument('-j', '--jobs', type=int, default=1, metavar='N', help='run up to N test scripts at once')
    parser.add_argument('-v', '--verbose', action='store_true', help='print the TAP output of each test script')
    parser.add_argument(
        '-I', '--include', action='append', default=[], metavar='DIR', help='add the directory to PYTHONPATH'
    )
    # Unlike prove: the current directory, where the modules of a project of Python are, as prove adds lib
    parser.add_argument(
        '-l', '--lib', dest='include', action='append_const', const='.', help='add the current directory to PYTHONPATH'
    )
    parser.add_argument('--ext', default='.py', help='extension of the test scripts, .py by default')
    parser.add_argument('--exec', dest='command', metavar='CMD', help='command that runs a test script')
    parser.add_argument(
        '--timeout', type=float, metavar='SECONDS', help='the most time a test script may run, no limit by default'
    )
    parser.add_argument('--trap', action='store_true', help='print the summary when Ctrl-C interrupts the run')
    # Not in prove: --capture-stderr, as --merge of prove shows the standard error with -v only, among the TAP output
    parser.add_argument(
        '--capture-stderr', action='store_true', help='print the standard error of a test script after its result'
    )
    # Not in prove: --stderr-lines, for --capture-stderr
    parser.add_argument(
        '--stderr-lines',
        type=_lines,
        metavar='N',
        help='print at most N lines of the standard error of a test script with --capture-stderr',
    )
    parser.add_argument(
        '--count', action='store_const', const=True, help='show the X/Y count of the tests, by default on a terminal'
    )
    parser.add_argument(
        '--no-count', '--nocount', dest='count', action='store_const', const=False, help='do not show the count'
    )
    parser.add_argument(
        '-c', '--color', action='store_const', const=True, help='color the output, by default on a terminal'
    )
    # Both forms, which Getopt::Long of prove accepts for its --nocolor
    parser.add_argument('--no-color', '--nocolor', dest='color', action='store_const', const=False, help='do not color')
    # Unlike prove: a formatter writes to a file too, so that there are several, as the one of --formatter of prove,
    # which is a class, writes in the place of the output
    parser.add_argument(
        '--formatter',
        action='append',
        default=[],
        metavar='NAME[=FILE]',
        help='write the results as console, junit or markdown, to FILE or in the place of the output',
    )
    parser.add_argument('paths', nargs='*', default=['t'], help='test scripts and directories, t by default')
    # Not in prove: PYJO_PROVE_OPTS, where prove reads .proverc
    try:
        opts = _split(os.environ.get('PYJO_PROVE_OPTS', ''))
    except ValueError as e:
        parser.error(f'PYJO_PROVE_OPTS: {e}')
    args = parser.parse_args([*opts, *(sys.argv[1:] if argv is None else argv)])
    formatters: list[tuple[str, str | None]] = []
    for value in args.formatter:
        name, _, file = value.partition('=')
        if name not in _FORMATTERS:
            parser.error(f'--formatter: unknown formatter {name!r}, one of {", ".join(_FORMATTERS)}')
        formatters.append((name, file or None))
    names, files = [name for name, _ in formatters], [file for _, file in formatters]
    if files.count(None) > 1:
        parser.error('--formatter: one formatter writes in the place of the output, not more')
    # The console in the place of the output, unless another formatter writes there
    if None not in files and 'console' not in names:
        formatters.insert(0, ('console', None))

    ext = args.ext if args.ext.startswith('.') else f'.{args.ext}'
    scripts = find_scripts(args.paths, ext, args.recurse)
    if not scripts:
        print('No tests found.', file=sys.stderr)
        return 1

    # A test script that runs the harness does not get the options of this one, as prove leaves out HARNESS_OPTIONS
    env = {name: value for name, value in os.environ.items() if name != 'PYJO_PROVE_OPTS'}
    if args.include:
        env['PYTHONPATH'] = os.pathsep.join([*args.include, *filter(None, [env.get('PYTHONPATH')])])

    command = _split(args.command) if args.command else [sys.executable]
    console = [file for name, file in formatters if name == 'console']
    started = time.monotonic()
    with contextlib.ExitStack() as stack:
        if console and console[0] is not None:
            stack.enter_context(contextlib.redirect_stdout(stack.enter_context(_open(console[0]))))
        try:
            results = asyncio.run(
                run(
                    scripts,
                    command,
                    env,
                    jobs=args.jobs,
                    verbose=args.verbose,
                    timeout=args.timeout,
                    trap=args.trap,
                    capture_stderr=args.capture_stderr,
                    stderr_lines=args.stderr_lines,
                    color=args.color,
                    count=args.count,
                    console=bool(console),
                )
            )
        except KeyboardInterrupt:
            # Die of the signal, as a process that does not handle it does, without a traceback
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGINT)
            raise
    elapsed = time.monotonic() - started
    for name, file in formatters:
        if name == 'console':
            continue
        report = f'{junit(results)}\n' if name == 'junit' else markdown(results, elapsed)
        if file is None:
            # In UTF-8, as the file of a formatter and as the JUnit XML declares, not in the encoding of the locale, as
            # cp1252 of Windows before Python 3.15, which has no marks of the summary in Markdown
            stdout: TextIO = sys.stdout
            if isinstance(stdout, io.TextIOWrapper):
                stdout.reconfigure(encoding='utf-8')
            stdout.write(report)
            stdout.flush()
        else:
            with _open(file) as output:
                output.write(report)
    return 0 if len(results) == len(scripts) and all(r.passed for r in results) else 1


# The formatters of --formatter, the console, which writes the usual output, first
_FORMATTERS = ('console', 'junit', 'markdown')


# The file of a formatter, whose lines end with LF on every system, where the text mode of Windows writes CRLF
def _open(path: str) -> TextIO:
    return open(path, 'w', encoding='utf-8', newline='\n')


# The version of the Python that a command runs, asked once for a command other than this Python
_PYTHONS: dict[tuple[str, ...], tuple[int, ...] | None] = {}

_OPERATORS: dict[str, Callable[[tuple[int, ...], tuple[int, ...]], bool]] = {
    '===': operator.eq,
    '==': operator.eq,
    '!=': operator.ne,
    '<=': operator.le,
    '>=': operator.ge,
    '<': operator.lt,
    '>': operator.gt,
}


async def _python(command: Sequence[str]) -> tuple[int, ...] | None:
    key = tuple(command)
    if key not in _PYTHONS:
        if list(command) == [sys.executable]:
            _PYTHONS[key] = tuple(sys.version_info[:3])
        else:
            _PYTHONS[key] = None
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    '-c',
                    'import sys; print(*sys.version_info[:3])',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                out, _ = await process.communicate()
                if process.returncode == 0 and len(version := tuple(int(n) for n in out.split())) == 3:
                    _PYTHONS[key] = version
            except (OSError, ValueError):
                pass
    return _PYTHONS[key]


def _cpu_count() -> int:
    # The processors that the process may use, as its affinity limits them, which Python 3.12 reports on Linux only
    if sys.version_info >= (3, 13):
        count = os.process_cpu_count()
    elif sys.platform == 'linux':
        count = len(os.sched_getaffinity(0))
    else:
        count = os.cpu_count()
    return count or 1


# The requires-python of the inline metadata of PEP 723, as its reference implementation reads it
def _requires_python(path: str) -> str | None:
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            source = f.read()
    except OSError:
        return None
    blocks = [m for m in RE_METADATA.finditer(source) if m.group('type') == 'script']
    if not blocks:
        return None
    if len(blocks) > 1:
        raise ValueError('Multiple script blocks found')
    content = ''.join(
        line[2:] if line.startswith('# ') else line[1:] for line in blocks[0].group('content').splitlines(keepends=True)
    )
    requires = tomllib.loads(content).get('requires-python')
    if requires is not None and not isinstance(requires, str):
        raise ValueError('requires-python is not a string')
    return requires


# The version specifiers of PEP 440 for a release, without pre-, post- and development releases
def _satisfies(version: tuple[int, ...], specifier: str) -> bool:
    satisfied = True
    for clause in specifier.split(','):
        if (m := RE_SPECIFIER.fullmatch(clause)) is None or (m.group(3) and m.group(1) not in ('==', '!=')):
            raise ValueError(f'Invalid requires-python: {specifier}')
        op, release, wildcard = m.groups()
        want = tuple(int(n) for n in release.split('.'))
        if wildcard:
            satisfied = satisfied and (version[: len(want)] == want) == (op == '==')
        elif op == '~=':
            if len(want) < 2:
                raise ValueError(f'Invalid requires-python: {specifier}')
            satisfied = (
                satisfied and _pad(version, want) >= _pad(want, version) and version[: len(want) - 1] == want[:-1]
            )
        else:
            satisfied = satisfied and _OPERATORS[op](_pad(version, want), _pad(want, version))
    return satisfied


def _pad(version: tuple[int, ...], other: tuple[int, ...]) -> tuple[int, ...]:
    return version + (0,) * (len(other) - len(version))


def _name(path: str, width: int) -> str:
    return f'{path} {"." * (width - len(path))}'


def _status_line(result: Result, width: int, color: bool = False) -> str:
    name = _name(result.path, width)
    if result.bail_out is not None:
        return f'{name} {_paint(f"Bailout called.  Further testing stopped:  {result.bail_out}", "red", color)}'
    if result.timed_out is not None:
        return f'{name} {_paint("Timed out", "red", color)}'
    if result.passed and result.skip_all is not None:
        return f'{name} {_paint(f"skipped: {result.skip_all}", "yellow", color)}'
    if result.passed:
        return f'{name} {_paint("ok", "green", color)}'
    if result.failed:
        return f'{name} {_paint(f"Failed {len(result.failed)}/{result.tests} subtests", "red", color)}'
    return f'{name} {_paint("Dubious", "red", color)}'


# A test point of the TAP output, at any level of subtests: one that failed is red, one with a directive yellow
def _tap_line(line: str, color: bool) -> str:
    if color and (m := RE_TEST.match(line.lstrip())):
        if m.group(4):
            return _paint(line, 'yellow', color)
        if m.group(1):
            return _paint(line, 'red', color)
    return line


_COLORS = {'green': '32', 'red': '31', 'yellow': '33'}


def _paint(text: str, name: str, color: bool) -> str:
    return f'\033[{_COLORS[name]}m{text}\033[0m' if color else text


# Not in prove: NO_COLOR (https://no-color.org) and TERM=dumb, which turn off the colors of Python itself too
def _color_default(stream: TextIO | None) -> bool:
    return _tty(stream) and not os.environ.get('NO_COLOR') and os.environ.get('TERM') != 'dumb'


def _tty(stream: TextIO | None) -> bool:
    try:
        return stream is not None and stream.isatty()
    except (OSError, ValueError):
        return False


# The width of the line of prove for the count of the test scripts that run at the same time
_RULER_WIDTH = 72
_RULER_TRAILER = '... )==='


class _Count:
    # The X/Y count of the tests of the test scripts that run, on a line that a carriage return renews, at most once a
    # second, as prove does: the count of the one test script that runs, or with jobs, a line of all of them
    def __init__(self, width: int, parallel: bool, color: bool) -> None:
        self.width = width
        self.parallel = parallel
        self.color = color
        self.active: dict[int, Result] = {}
        self.counted: dict[int, int] = {}
        self.tests = 0
        self.started = time.monotonic()
        self.second: int | None = None
        self.length = 0

    def update(self, result: Result) -> None:
        key = id(result)
        if key not in self.active:
            self.active[key] = result
            self.counted[key] = 0
            if not self.parallel:
                self.second = None
                self._write(f'{_name(result.path, self.width)} ')
            else:
                self.show(refresh=True)
            return
        self.tests += result.tests - self.counted[key]
        self.counted[key] = result.tests
        self.show()

    def finish(self, result: Result) -> None:
        self.active.pop(id(result), None)
        self.counted.pop(id(result), None)
        self.clear()

    def show(self, refresh: bool = False) -> None:
        second = int(time.monotonic())
        if not self.active or (second == self.second and not refresh):
            return
        self.second = second
        if not self.parallel:
            result = next(iter(self.active.values()))
            name = f'{_name(result.path, self.width)} '
            count = f'{result.tests}/{result.planned or "?"} '
            self._write(f'{name}{_paint(count, "red", self.color and bool(result.failed))}', len(name) + len(count))
            return
        ruler = f'===( {self.tests:7d};{int(time.monotonic() - self.started)}  '
        for r in self.active.values():
            planned = str(r.planned or '?')
            ruler += f'{r.tests:{len(planned)}d}/{planned}  '
        ruler = f'{ruler[:-1]})==='
        if len(ruler) > _RULER_WIDTH:
            ruler = ruler[: _RULER_WIDTH - len(_RULER_TRAILER)] + _RULER_TRAILER
        self._write(ruler.ljust(_RULER_WIDTH, '='))

    def clear(self) -> None:
        if self.length:
            sys.stdout.write(f'\r{" " * self.length}\r')
            sys.stdout.flush()
            self.length = 0

    # The length is the one on the screen, without the escape sequences of the colors
    def _write(self, line: str, length: int | None = None) -> None:
        sys.stdout.write(f'\r{line}')
        sys.stdout.flush()
        self.length = len(line) if length is None else length


# The first half of the lines, and the last half in a queue that leaves out the lines before them
async def _read_lines(stream: asyncio.StreamReader, result: Result, limit: int | None) -> None:
    head = None if limit is None else _head(limit)
    tail = collections.deque[str](maxlen=None if limit is None else limit // 2)
    try:
        while raw := await stream.readline():
            line = raw.decode('utf-8', 'replace').rstrip('\r\n')
            if head is None or len(result.stderr) < head:
                result.stderr.append(line)
                continue
            if len(tail) == tail.maxlen:
                result.stderr_left_out += 1
            tail.append(line)
    finally:
        result.stderr.extend(tail)


def _head(limit: int) -> int:
    return (limit + 1) // 2


# Not in prove: the words of a command line of Windows, whose paths have backslashes, which a shell of POSIX takes for
# escapes, so they are split as there, and the quotes around a word are removed
def _split(line: str) -> list[str]:
    if sys.platform != 'win32':
        return shlex.split(line)
    return [re.sub(r'\A(["\'])(.*)\1\Z', r'\2', word, flags=re.S) for word in shlex.split(line, posix=False)]


def _lines(value: str) -> int:
    if (lines := int(value)) < 0:
        raise argparse.ArgumentTypeError(f'invalid number of lines: {value}')
    return lines


# Not in prove: Windows has no process group that a signal kills, and a job, which the processes that the script starts
# join, kills them with the script, also when the script has ended before them, as a process group does elsewhere
if sys.platform == 'win32':
    import ctypes

    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    # NtResumeProcess resumes the threads of a process, its one thread of a process that starts suspended, as
    # psutil.Process.resume does on Windows
    _ntdll = ctypes.WinDLL('ntdll')
    _ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
    _ntdll.NtResumeProcess.restype = ctypes.c_long

    # PROCESS_SET_QUOTA and PROCESS_TERMINATE, which AssignProcessToJobObject needs, PROCESS_SUSPEND_RESUME, and
    # CREATE_SUSPENDED
    _ASSIGN = 0x0100 | 0x0001
    _RESUME = 0x0800
    _SUSPENDED = 0x00000004
else:
    _SUSPENDED = 0


def _job(pid: int) -> int | None:
    if sys.platform != 'win32' or not (job := _kernel32.CreateJobObjectW(None, None)):
        return None
    process = _kernel32.OpenProcess(_ASSIGN, False, pid)
    assigned = bool(process) and bool(_kernel32.AssignProcessToJobObject(job, process))
    if process:
        _kernel32.CloseHandle(process)
    if not assigned:
        _kernel32.CloseHandle(job)
        return None
    return job


def _resume(pid: int) -> bool:
    if sys.platform != 'win32':
        return True
    if not (process := _kernel32.OpenProcess(_RESUME, False, pid)):
        return False
    resumed = _ntdll.NtResumeProcess(process) >= 0
    _kernel32.CloseHandle(process)
    return resumed


def _close_job(job: int | None) -> None:
    if sys.platform == 'win32' and job is not None:
        _kernel32.CloseHandle(job)


def _kill(process: asyncio.subprocess.Process, job: int | None) -> None:
    try:
        if sys.platform == 'win32':
            if job is None or not _kernel32.TerminateJobObject(job, 1):
                process.kill()
        elif hasattr(os, 'killpg'):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


# The diagnostics of the failures in the standard error, which go to the test points that failed, as Pyjo.Test writes
# them apart from the TAP output, with the ones of a subtest before the one of the test point of the subtest
def _diagnostics(result: Result) -> None:
    failed = iter([point for point in result.points if point.failed])
    nested: list[str] = []
    current: list[str] | None = None
    for line in result.stderr:
        if RE_FAILED.match(line):
            current = point.diagnostics if (point := next(failed, None)) is not None else None
            if current is not None:
                current += [*nested, line]
            nested = []
        elif line[:1].isspace():
            nested.append(line)
            current = None
        elif current is not None and line.startswith('#') and not line.startswith('# Looks like'):
            current.append(line)
        else:
            current = None


# The lines of the diagnostics and of the standard error of a test script in the summary in Markdown, at most
_DETAILS = 200


def _cell(text: str) -> str:
    # The text of a cell of a table of Markdown, with its pipes escaped
    return _html(text).replace('|', '\\|')


def _html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _junit_child(parent: 'Pyjo.DOM.object', name: str, text: str | None, **attrs: str) -> None:
    # An element in the element of a fragment that new_tag has made
    tag = parent.children().first()
    assert tag is not None
    values = {key: _xml(value) for key, value in attrs.items()}
    tag.append_content(parent.new_tag(name, _xml(text), **values) if text else parent.new_tag(name, **values))


def _junit_line(case: 'Pyjo.DOM.object', diagnostics: list[str]) -> None:
    # The line of the first place of the diagnostics, which is the one of the assertion that failed in a subtest
    for line in diagnostics:
        if m := RE_AT.search(line):
            if (tag := case.children().first()) is not None:
                tag.attr(line=m.group(2))
            return


# What a test script did wrong as a whole, without the exit status of the number of its failures, which Pyjo.Test and
# Test::More exit with, up to 254
def _problems(result: Result) -> list[str]:
    problems = [f'Bail out!  {result.bail_out}'] if result.bail_out is not None else []
    status = f'Non-zero exit status: {min(len(result.failed), 254)}' if result.failed else None
    return problems + [error for error in result.errors if error != status]


def _point_name(point: Point) -> str:
    return f'{point.number} - {point.name}' if point.name else str(point.number)


def _xml(text: str | None) -> str | None:
    # Text without the escapes of the terminal and the characters that XML 1.0 does not allow
    return RE_NOT_XML.sub('', RE_ANSI.sub('', text)) if text is not None else None


def _summary(
    results: list[Result], elapsed: float, interrupted: bool = False, *, color: bool = False, err_color: bool = False
) -> None:
    failed = [r for r in results if not r.passed]
    tests = sum(r.tests for r in results)

    if interrupted:
        print(_paint('Test run interrupted!', 'red', err_color), file=sys.stderr, flush=True)

    if failed:
        print('\nTest Summary Report\n-------------------')
        for r in failed:
            print(f'{r.path} (Tests: {r.tests} Failed: {len(r.failed)})')
            if r.failed:
                failures = f'Failed {"tests" if len(r.failed) > 1 else "test"}:  {", ".join(map(str, r.failed))}'
                print(f'  {_paint(failures, "red", color)}')
            if r.bail_out is not None:
                print(f'  {_paint(f"Bail out:  {r.bail_out}", "red", color)}')
            for error in r.errors:
                print(f'  {_paint(error, "red", color)}')
    elif not interrupted:
        print(_paint('All tests successful.', 'green', color))

    todo_passed = [r for r in results if r.todo_passed]
    for r in todo_passed:
        print(_paint(f'{r.path}: TODO passed:  {", ".join(map(str, r.todo_passed))}', 'yellow', color))

    print(f'Files={len(results)}, Tests={tests}, {elapsed:.0f} wallclock secs')
    status, name = ('FAIL', 'red') if failed or interrupted else ('PASS', 'green') if tests else ('NOTESTS', 'yellow')
    print(f'Result: {_paint(status, name, color)}', flush=True)


if __name__ == '__main__':
    sys.exit(main())
