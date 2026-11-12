"""
Pyjo.Test.pytest_plugin - Pyjoyment in pytest
=============================================
::

    $ pytest
    $ pytest -v t/basic.py

    # pyproject.toml
    [tool.pytest.ini_options]
    testpaths = ["t", "tests"]
    pythonpath = ["."]

    # tests/conftest.py
    import pytest


    @pytest.fixture
    def app():
        return 'MyApp'


    # tests/test_basic.py
    def test_index(t):
        t.get_ok('/').status_is(200).content_like(r'Pyjoyment')

:mod:`Pyjo.Test.pytest_plugin` is a plugin of `pytest <https://pytest.org>`_,
which pytest loads where Pyjoyment is installed. It runs the test scripts of
:mod:`Pyjo.Test` as :mod:`Pyjo.Prove` does, each as a test of pytest, and lets
the tests of pytest use :mod:`Pyjo.Test` and :mod:`Pyjo.Test.Pyjo`.
:mod:`Pyjo.Prove` stays the runner of the test scripts, and pytest runs the
same scripts for whoever runs ``pytest``, as a test explorer of an IDE or a
coding agent. Pyjoyment does not depend on pytest, and nothing of it but this
plugin imports pytest.

It has no counterpart in Mojolicious.

Test scripts
------------

A file with the extension ``.py`` in the directories of ``pyjo_prove_paths``,
``t`` by default, is a test script, whatever its name, but ``conftest.py``,
and pytest does not import it. The script runs in a process of its own, in the
root directory of pytest, with :func:`Pyjo.Prove.run_script`, and is a test of
pytest of its own, ``t/basic.py``, which passes, fails or is skipped as
:mod:`Pyjo.Prove` reports the script. The report of a failure shows the
failed tests, the standard error of the script with their diagnostic
messages, and what is wrong with the plan or the exit status; the whole TAP
output of the script is its captured standard output. ``Bail out!`` stops the
run.

pytest runs its tests one after another, and so the test scripts, where
:mod:`Pyjo.Prove` runs several at the same time with ``-j``; ``-n`` of
`pytest-xdist <https://pytest-xdist.readthedocs.io>`_ does so, as each test
script is a test of its own.

The scripts get the environment that pytest started with, as
``python -m Pyjo.Prove -l`` gives it to them: the root directory in
``PYTHONPATH``, ``PYJO_HARNESS_ACTIVE``, and ``PYJO_HARNESS_IS_VERBOSE`` with
``-v``.

``pytest`` without arguments runs the directories of ``testpaths``, so a
project whose tests are test scripts names their directory there, in
``pyproject.toml``, as the projects of ``generate app`` and
``generate plugin`` do, with pytest in the dependency group ``dev``, which
``uv run pytest`` installs: ::

    [dependency-groups]
    dev = ["pytest>=9", "pytest-xdist>=3"]

    [tool.pytest.ini_options]
    testpaths = ["t"]
    pythonpath = ["."]

Tests of pytest
---------------

The plugin calls :func:`Pyjo.Test.raise_failures`, so that a failed test of
:mod:`Pyjo.Test` or of :mod:`Pyjo.Test.Pyjo` raises :exc:`AssertionError`
with its name and its diagnostic message, ``plan(skip_all=...)`` skips the
test, and ``Bail out!`` stops the run.

A test stops at its first failed test, after which
:attr:`~Pyjo.Test.Pyjo.Pyjo_Test_Pyjo.success` and
:meth:`~Pyjo.Test.Pyjo.Pyjo_Test_Pyjo.otherwise` have nothing to do. The user
agent of :mod:`Pyjo.Test.Pyjo` blocks, so a test is a function, not a
coroutine. The tests run in one process, where their applications share the
singleton of :mod:`Pyjo.IOLoop` and the environment, which a test script has
of its own. The tests go to a directory of their own, as ``tests``, as
:mod:`Pyjo.Prove` runs every script in ``t``, and ``pythonpath`` of pytest
puts the root directory in :data:`sys.path`, as ``-l`` of :mod:`Pyjo.Prove`
does for the test scripts, so that a test finds the application by the name
of its class.

Ini options
-----------

``pyjo_prove_paths``
    The directories of the test scripts, relative to the configuration file,
    ``t`` of the root directory by default. Without a directory, pytest runs
    no test scripts. ::

        [tool.pytest.ini_options]
        pyjo_prove_paths = ["t", "xt"]

``pyjo_prove_timeout``
    The most seconds a test script may run, no limit by default. A test script
    that runs longer is killed, with the processes it started, and fails. ::

        [tool.pytest.ini_options]
        pyjo_prove_timeout = "60"

Fixtures
--------

``t``
    A :mod:`Pyjo.Test.Pyjo` object of the application of the fixture ``app``,
    which the tests define, and which can be anything that
    :meth:`Pyjo.Test.Pyjo.Pyjo_Test_Pyjo.__init__` takes. The end of the
    test closes it. ::

        @pytest.fixture
        def app():
            return Pyjo.File.curfile().dirname().sibling('myapp.py')


        def test_index(t):
            t.get_ok('/').status_is(200)

See also
--------

:mod:`Pyjoyment`, https://docs.pytest.org.
"""

import Pyjo.Prove
import Pyjo.Test

import asyncio
import os
import sys
import unittest

from collections.abc import Generator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest


if TYPE_CHECKING:
    import Pyjo.Test.Pyjo


# The most lines of the standard error of a test script in the report of its failure, the first half and the last
# half, as a script that fails in a loop can write megabytes of it
STDERR_LINES = 1000

_env_key = pytest.StashKey[dict[str, str]]()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini('pyjo_prove_paths', 'the directories of the test scripts of Pyjo.Test', type='paths', default=['t'])
    parser.addini('pyjo_prove_timeout', 'the most seconds a test script of Pyjo.Test may run', default='')


def pytest_configure(config: pytest.Config) -> None:
    # The environment that pytest started with, before a test changes it, as the import of Pyjo.Test.Pyjo sets
    # PYJO_LOG_LEVEL; a test script that runs the harness does not get its options, as with Pyjo.Prove
    env = {name: value for name, value in os.environ.items() if name != 'PYJO_PROVE_OPTS'}
    env['PYTHONPATH'] = os.pathsep.join(['.', *filter(None, [env.get('PYTHONPATH')])])
    env['PYJO_HARNESS_ACTIVE'] = '1'
    if config.get_verbosity() > 0:
        env['PYJO_HARNESS_IS_VERBOSE'] = '1'
    config.stash[_env_key] = env
    Pyjo.Test.raise_failures()


def pytest_unconfigure(config: pytest.Config) -> None:
    Pyjo.Test.raise_failures(False)


# A wrapper, which replaces what the other plugins make of a test script, as the module of pytest for a test_*.py
@pytest.hookimpl(wrapper=True)
def pytest_collect_file(
    file_path: Path, parent: pytest.Collector
) -> Generator[None, list[pytest.Collector | None], list[pytest.Collector | None]]:
    collectors = yield
    if _is_script(file_path, parent.config):
        # The test of pytest without a collector of the file, as it has one test, whose node is the path alone
        config = parent.config
        try:
            nodeid = file_path.relative_to(config.rootpath).as_posix()
        except ValueError:
            nodeid = file_path.as_posix()
        # pytest leaves the keyword arguments of from_parent without types
        item = ScriptItem.from_parent(  # pyright: ignore[reportUnknownMemberType]
            parent, name=file_path.name, path=file_path, nodeid=nodeid
        )
        return [cast(pytest.Collector, item)]
    return collectors


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    # The exception of the test, before the plugin of pytest for unittest replaces a unittest.SkipTest
    error = call.excinfo.value if call.excinfo is not None else None
    report = yield
    if isinstance(error, Pyjo.Test.BailOut):
        item.session.shouldstop = f'Bail out!  {error}'

    # A skipped test script or test of Pyjo.Test is reported at its own place, not at the one that raised the skip
    longrepr = report.longrepr
    if report.skipped and isinstance(longrepr, tuple):
        if isinstance(item, ScriptItem) or isinstance(error, unittest.SkipTest):
            path, line = item.reportinfo()[:2]
            # A place without a line, as of a test script, which pytest shows as the path alone
            report.longrepr = cast(Any, (os.fspath(path), line + 1 if line is not None else None, longrepr[2]))
    return report


@pytest.fixture
def t(app: Any) -> Iterator['Pyjo.Test.Pyjo.Pyjo_Test_Pyjo']:
    # Imported by the first test that uses it, after pytest_configure took the environment
    import Pyjo.Test.Pyjo

    with Pyjo.Test.Pyjo.new(app) as t:
        yield t


class ScriptItem(pytest.Item):
    """
    The test of pytest that runs a test script.
    """

    def runtest(self) -> None:
        """::

            item.runtest()

        Run the test script with :func:`Pyjo.Prove.run_script`, and fail or
        skip as its result says.
        """
        config = self.config
        path = Path(os.path.relpath(self.path, config.rootpath)).as_posix()
        timeout = str(config.getini('pyjo_prove_timeout')).strip()
        # Without the debug mode of asyncio, as Pyjo.Prove runs its event loop, which would write its own slow callbacks
        # to the standard error of the test
        result = asyncio.run(
            Pyjo.Prove.run_script(
                path,
                [sys.executable],
                config.stash[_env_key],
                timeout=float(timeout) if timeout else None,
                capture_stderr=True,
                stderr_lines=STDERR_LINES,
                cwd=str(config.rootpath),
            ),
            debug=False,
        )
        stderr = list(result.stderr)
        if result.stderr_left_out:
            stderr.insert(STDERR_LINES // 2, f'[{result.stderr_left_out} lines left out]')

        self.add_report_section('call', 'stdout', '\n'.join(result.output))

        if result.bail_out is not None:
            self.session.shouldstop = f'Bail out!  {result.bail_out}'
            pytest.fail('\n'.join([f'Bail out!  {result.bail_out}', *stderr]), pytrace=False)

        # The first line is the one of the short summary of pytest, the status of Pyjo.Prove
        if result.failed:
            failed = [line for line in result.output if _failed(line)]
            summary = f'Failed {len(result.failed)}/{result.tests} subtests'
            pytest.fail('\n'.join([summary, *failed, *stderr, *result.errors]), pytrace=False)
        if result.errors:
            pytest.fail('\n'.join([*result.errors, *stderr]), pytrace=False)

        if result.skip_all is not None:
            pytest.skip(result.skip_all or 'no reason given')

    def reportinfo(self) -> tuple[Path, None, str]:
        """::

            path, line, name = item.reportinfo()

        The path of the test script, without a line, and its name in the
        headline of the report of a failure, as ``t/basic.py (TAP)``.
        """
        # Not the node alone: pytest shows the dots of a name that ends the node as ::, of Class.method
        return self.path, None, f'{self.nodeid} (TAP)'


def _failed(line: str) -> bool:
    m = Pyjo.Prove.RE_TEST.match(line.lstrip())
    return m is not None and m.group(1) is not None and (m.group(4) or '').lower() != 'todo'


def _is_script(path: Path, config: pytest.Config) -> bool:
    if path.suffix != '.py' or path.name == 'conftest.py':
        return False
    for directory in config.getini('pyjo_prove_paths'):
        # The default is not resolved by pytest, the paths of the configuration file are
        if path.is_relative_to(directory if isinstance(directory, Path) else config.rootpath / directory):
            return True
    return False
