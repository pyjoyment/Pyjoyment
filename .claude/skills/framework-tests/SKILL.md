---
name: framework-tests
description: Write and run the tests of Pyjoyment itself, with the layout of t and tt, the tests ported from Mojolicious, Pyjo.Prove, both reactors, CI on every Python, PyPy, the free-threaded build and Windows, ResourceWarning, the tests of t/servers, of JSON Schema and of the Docker smoke test, pytest, and the benchmarks. Use when adding or changing a test of the framework, when CI fails, or when a change is made for speed.
---

# Tests of Pyjoyment

The tests are scripts that print [TAP](https://testanything.org/), written
with `Pyjo.Test`, which is inspired by Perl's `Test::More`. They run with
`Pyjo.Prove`, a TAP harness inspired by Perl's `prove`:

```sh
mise exec -- python -m Pyjo.Prove -l -j 4 -r t
```

A single file runs on its own as well:
`PYTHONPATH=. mise exec -- python t/Pyjo/URL.py`. Perl's `prove` still works,
because the output is standard TAP: `.proverc` supplies its
`--ext=py --exec=python`, and `PYTHONPATH` the directory of the modules, as
the `-l` of `prove` adds `lib` to the path of Perl, not of Python:

```sh
PYTHONPATH=. mise exec -- prove -r -j 4 t
```

`.proverc` cannot set the variable itself: `prove` keeps the quotes of an
option of the file, so a command with arguments, as `env PYTHONPATH=. python`,
does not fit in its `--exec`.

A test that requests remote hosts, as `t/Pyjo/UserAgent_online.py`, is
skipped unless `TEST_ONLINE` is set, as in Mojolicious. Its hosts are those of
GitHub, which the runners of GitHub Actions reach the most reliably, as are
the pages that the examples of the guides request, where Mojolicious requests
its own site, which Pyjoyment does not have yet, so CI sets `TEST_ONLINE` in
every job of its matrix. The requests to them are in a subtest with
`reruns=2, reruns_delay=10`, so that a failure of the network runs it again
instead of failing the job; such a subtest is a decorator or has a callback,
as the block of `with` runs once, and makes its user agent itself, so that a
rerun does not take the connections that the run before it kept alive.

CI runs the tests with `--timeout 120`: a test script that hangs, such as a
reactor that never stops, is killed with the processes it started and fails
with its name, instead of the job running out of time. The slowest script
takes a few seconds, and a script online up to a minute more, with the reruns
of a subtest of a remote host that fails.

A server that a test starts in a process of its own, as those of
`Pyjo.Server.Hot`, `Pyjo.Server.Reload` and `Pyjo.Server.Prefork`, listens on
a port of `port` of `t/lib/ServerStart.py`, not of `generate_port`, which is
free when it is found, but not necessarily when the process binds it a second
later: a server of a test that runs at the same time, which listens on a port
that the system picks, or an outgoing connection, whose local port the system
picks, can get it, and the test then takes that server for its own. The system
picks them from its ephemeral ports, from 32768 on Linux and 49152 on macOS
and Windows, so `port` finds one below them, and a lock of its byte in a file
of the temporary directory, with `fcntl` or the `msvcrt` of Windows, which the
system releases when the test ends, keeps it from the other tests. Such a test starts its server with `retry`, which tries
again on new ports when a port is taken anyway, and waits for it with a limit
of time, so that a server that does not start fails the test instead of
hanging it. A server that runs in the process of the test can listen on the
port 0 instead, which `ports()` gives.

- `t/Pyjo/` holds the module tests, ported from Mojo's `t/mojo/*.t`. A
  file has the name of Mojo's test with the part of the module as Pyjoyment
  names it: `reactor_detect.t` is `Reactor_detect.py`, `ioloop_tls.t` is
  `IOLoop_TLS.py`, and `tls.t` is `TLS.py`.
- `t/Pyjoyment/` holds the tests of the framework, ported from Mojo's
  `t/mojolicious/*.t` and named the same way: `types.t` is `Types.py`. A test
  of an application, as the `*_lite_app.t` ones, is not one of a module, so it
  keeps the name of Mojo, as a capital letter tells a module:
  `log_lite_app.t` is `log_lite_app.py`. `ojo.t` is `t/Pyjo/init.py`, as the
  functions of `ojo` are those of `Pyjo`, in `Pyjo/__init__.py`, where
  `Pyjo.py` would import itself for `from Pyjo import *`, as the directory of
  a script is the first one of `sys.path`, and `t/test/mojo.t`, the test of
  `Test::Mojo`, is `t/Pyjo/Test_Pyjo.py`.
- `t/certs/` holds the certificates of the tests, as `t/mojo/certs` in Mojo.
- `t/cookies/` holds the cookie files of the tests, as `t/mojo/cookies` in
  Mojo.
- `t/docs/` checks that the code in the module documentation is correct: it
  is the same code as in the docstrings, in the same order, with `print` and
  the comments that show a result turned into assertions. Documented code
  that prints TAP itself or ends the script, as in `Pyjo.Test`, runs as a
  script of its own, and the test checks its output and exit status.
  A test of a guide, as `guides_tutorial.py`, loads the applications of
  its examples from their files and checks what the guide says of them.
  `usages.py` checks the usages of the commands and of the scripts of the
  servers: their options are the ones that they pass to `getopt`, which it
  captures by running them with an unknown option in a temporary directory,
  and their blocks of options are laid out as `format_usage` of
  `Pyjo.GetOpt` lays them out, which a failure shows to paste.
- `t/stdlib/` checks the interaction with the Python standard library,
  written for Pyjoyment, as Mojolicious has no counterpart.
- `t/examples/` checks the code of some scripts of `examples/` with assertions,
  in versions of its own, in the directories of the groups of `examples/`,
  which `examples/README.md` lists. The scripts themselves are not run by the tests, as
  some need the network or libraries the project does not install; they are
  reviewed by hand, the Perl ones, the Mojolicious counterparts of the Python
  ones, against the target Mojolicious.
- `t/servers/` runs `Pyjo.Server.ASGI`, `Pyjo.Server.WSGI` and
  `Pyjo.Server.CGI` on real ASGI, WSGI and CGI servers, and the examples of
  the quick start in `README.md`, each in a process of its own, as the ASGI server of the tests in `t/lib` and the validator of
  `wsgiref` cannot show how a server differs, and mounts the applications of
  other frameworks, as Flask and Starlette, with `Pyjoyment.Plugin.Mount`, and
  an application of Pyjoyment on WSGI or on ASGI in one of `Pyjoyment.Lite`,
  as the examples `mount_wsgi_inception.py` and `mount_asgi_inception.py` do,
  on the WSGI and the ASGI servers, and PHP on php-fpm with
  `Pyjo.App.FastCGI` and on php-cgi with `Pyjo.App.CGI`, which `setup-php`
  installs in CI, and without which the tests are skipped, and Starlette on
  Mangum as an event function of AWS Lambda with `Pyjo.App.Lambda`, and the
  server of the MCP SDK of the example `mount_mcp.py`, which the client of the
  SDK calls, on the daemon and without sessions on the workers of prefork, and
  the example `aws/s3.py` with aiobotocore, the asynchronous AWS SDK, against
  a mock of S3 on the daemon in the same event loop, and compares the schemas
  of the type hints of `Pyjo.JSON.Schema` with the ones of pydantic, which the
  MCP SDK gives its tools, and what `Pyjo.INI` loads of the files of AWS with what
  botocore reads of them. The servers, the frameworks, aiobotocore, with
  botocore, and pydantic are in the dependency group `servers`, not in
  `dependencies`; without it, the tests are skipped.
- `t/lib/` holds helpers shared by the tests. Run on their own, they skip with
  `plan(skip_all=...)`, so `-r t` reports them as skipped instead of failing.
- `tt/` holds the Python files that the tests use as data, as the templates
  of files of `Pyjoyment.Plugin.PyRenderer`, the modules of `tt/lib` and the
  applications of `tt/external`, which `Pyjoyment.Plugin.Mount` mounts,
  outside `t/`, as `-r t` runs every Python file there. `tt/templates_native` holds the ones with the
  t-strings of Python 3.14, which only the tests of 3.14 render, and which
  ruff and pyright check as Python 3.14. `tt/pytest` is a project of test
  scripts and tests of pytest, which the tests of
  `Pyjo.Test.pytest_plugin` copy to a temporary directory and run pytest
  on. A test does not write files into `t/` or `tt/`: what it makes goes to
  a temporary directory.

A test script imports the test functions and groups its tests in subtests,
like Mojo's tests do; Python keywords give some functions an `_ok` suffix
(`is_ok`, `isnt_ok`, `like_ok`, `is_deeply_ok`):

```python
from Pyjo.Test import *

import Pyjo.URL

with subtest('Simple'):
    url = Pyjo.URL.new('HtTp://Example.Com')
    is_ok(url.host, 'Example.Com', 'right host')

done_testing()
```

A test of the project ends with `done_testing()`, as Mojo's tests do, so that
the diff of a newer Mojolicious applies to it; `with plan():`, which issues the
plan at the end of its block, is for the tests of the code that uses
Pyjoyment, and for the tests of `Pyjo.Test` itself.

The exit status comes from an `atexit` handler that `Pyjo.Test` registers,
and only once a test function has been called, so importing the module (as
Sphinx does) has no effect. Older test files still wrap their body in
`if __name__ == '__main__':`, which is no longer needed.

The tests run on the reactor that `Pyjo.Reactor.detect()` gives, the asyncio
one, where Mojo's tests set `MOJO_REACTOR` to `Mojo::Reactor::Poll`. The
matrix of CI runs all of them on each Python a second time, in a job of its
own, on `Pyjo.Reactor.Poll`, as a reactor without asyncio has to pass them
too. A test of what needs the loop of asyncio, as `Pyjo.Server.ASGI`, whose
reactor runs in the loop of the ASGI server, or a coroutine that awaits
`asyncio.sleep`, is skipped on another reactor:

```sh
PYJO_REACTOR=Pyjo.Reactor.Poll mise exec -- python -m Pyjo.Prove -l -j 4 --capture-stderr --stderr-lines 1000 -r t
```

CI runs them on Windows too, on the Python of `mise.toml` and on both
reactors. A test of what Windows does not have, as `os.fork`, UNIX domain
sockets, the signals of POSIX, a command of a shell of POSIX or the mode of a
file, skips there with the reason. A test of paths compares them as Windows
makes them, with the drive, both separators and the short names of 8.3 that
`os.path.realpath` resolves, as `C:\Users\RUNNER~1` of the runner, and a test
that captures output reads it with LF, as Windows writes CRLF in text mode. A
test signals its own process with `signal.raise_signal`, as `os.kill` of
Windows terminates the process, and stops a server of a process of its own
with `CTRL_BREAK_EVENT` in a process group of its own, as Windows sends no INT
or TERM to one process, and the `python.exe` of a virtual environment is a
launcher that starts the interpreter as a process of its own, which outlives
for a moment a launcher that is terminated, with its files still open. It closes a file before it removes its directory, as
Windows removes no file that is open.

CI runs the tests in `t/servers` on Python 3.12 and 3.15, the oldest and the
newest supported, of setup-python, with the dependency group `servers`
installed by uv in `.venv`, so that the servers and their libraries are tested
on both ends; locally, `.venv-3.12` keeps the other version apart:

```sh
mise exec -- uv run --python 3.15 \
  --only-group servers python -m Pyjo.Prove -l --timeout 120 -r t/servers
UV_PROJECT_ENVIRONMENT=.venv-3.12 mise exec -- uv run --python 3.12 \
  --only-group servers python -m Pyjo.Prove -l --timeout 120 -r t/servers
```

A server is a library of its own, so the known differences of a server are
expected results with a comment: a fix of the server fails the test, which
tells that the documentation of `Pyjo.Server.ASGI`, `Pyjo.Server.WSGI` or
`Pyjo.Server.CGI` can change. The server processes do not get
`PYTHONWARNINGS` or `PYTHONDEVMODE`, as the warnings of the servers and their
libraries are not ours. Renovate bumps the dependency groups in one pull
request.

The schemas of `Pyjo.JSON.Schema` are compared with the ones of the libraries
that its two forms follow: `t/servers/JSON_Schema_pydantic.py` with pydantic,
for the type hints, and `t/Pyjo/JSON_Schema_zod.py` with `z.toJSONSchema()`
of zod, for the builder, whose code in JavaScript runs on the Node.js of
`mise.toml`, with zod of the `devDependencies` of `package.json`, which
`npm ci --ignore-scripts` installs, as the job of CI on the Python of
`mise.toml` does; without it, the test is skipped. A difference of a library,
as the bounds of the safe integers of JavaScript that zod gives an integer, is
left out by a normalization with a comment of its own, so that a new one fails
the test. A major release of zod needs no approval in the Dependency
Dashboard, as the test checks it.

The validation of `Pyjo.JSON.Schema` runs the official test suite of JSON
Schema, JSON-Schema-Test-Suite, for draft 2020-12, in
`t/Pyjo/JSON_Schema_suite.py`, from the files of the suite in `node_modules`,
which the same `npm ci` installs, so that the repository does not keep a copy
of them; without it, the test is skipped. The suite is not on npm, so the
`devDependencies` take it from its repository of GitHub, at a commit, not at
a tag: the tags of the suite, as `Test-JSON-Schema-Acceptance-1.039`, are not
versions that the manager of npm of Renovate updates, which skips them as an
unversioned reference, and a commit is a digest that it updates to the last
commit of the suite, with `package-lock.json`. The test lists the files and
the cases that it leaves out with the reason, as the keywords that the
validation does not support, and fails when a case that it leaves out passes,
so that a newer suite tells what the list can lose.

uWSGI is the package `uwsgi`, built from its source with a C compiler, as the
wheels of `pyuwsgi` have no plugin `cgi`. `extra-build-variables` in
`pyproject.toml` builds the plugin into it with `UWSGI_EMBED_PLUGINS=cgi`, and
uv keeps such a build apart from one without the variable in its cache.
`http.server --cgi` runs the CGI tests too, on a Python that still has
`CGIHTTPRequestHandler`, which Python 3.15 removed, as the run of CI on
Python 3.12.

The workflow Docker Smoke Test builds and runs the images of
`generate dockerfile`, for an application, a Lite script with
`pyproject.toml` and one with the inline metadata of PEP 723, and checks that
they serve their pages and stop gracefully on the TERM of `docker stop`: the
Lite script with `pyproject.toml` in an image of `generate dockerfile --port`,
which exposes its port, and the one with the inline metadata on the port of
`PORT` of the container, as Knative sets it, and the application in an image
of `generate dockerfile --graceful-timeout`, whose workers stop with it. Its
variant `lambda` runs a Lite script that ends with `handler = app.start()` as
an event function in the image of AWS Lambda for Python, whose emulator of the
Runtime API it invokes with the events of the payload formats 2.0 and 1.0,
its variant `lambda-stream` runs the same script with
`PYJO_LAMBDA_INVOKE_MODE=RESPONSE_STREAM` through the wrapper of
`examples/lambda_stream`, which the emulator runs in the place of the runtime
client of the image, as it has no `AWS_LAMBDA_EXEC_WRAPPER`, and checks the
format of the stream, as the emulator gives the whole stream at its end, with
the content type `application/octet-stream`, its variant `lambda-image` runs a
Lite script with `pyproject.toml` in an image of `generate dockerfile --target
lambda`, whose command is the runtime of the function itself, under the
emulator of the Runtime API, which the image has not, so the script mounts the
binary of its release as the entry point of the container, of `RIE_VERSION` of
the workflow, which Renovate bumps, or the latest one, and invokes it buffered
and streaming, its variant `lambda-zip` runs the same script in the ZIP files of
`generate lambda-zip`, extracted where Lambda extracts them, the layers in `/opt`
and the function in `/var/task`, in the image of the custom runtime
`provided.al2023`, whose emulator runs the `bootstrap` of the function, and
checks that the Python of python-build-standalone reads the certificates of
Amazon Linux, which its OpenSSL looks for in `/etc/ssl`, and finds Pyjoyment in
its layer, and in the ZIP files of `generate lambda-zip --runtime python3.14`
in the image of the runtime of Python, whose function has no Pyjoyment of its
own, so that its invocations tell that the runtime finds the layer, and its
variant
`fastcgi` runs a Lite script that listens for FastCGI, with
`PYJO_LISTEN`, behind Caddy in a container of its own on the same network,
whose image `Dockerfile.caddy` pins, so that Renovate bumps it, and checks the
pages through Caddy, and its variant `kubernetes` runs a Lite script with the
plugin Health in the manifests of `generate kubernetes` on a cluster of kind of
its own, with a kubeconfig of its own, which the node of `KIND_NODE_IMAGE` of
the workflow mounts the temporary directory of: `dev` with the application in
a ConfigMap and a change of it in a new one, `dev` with `--host-path` reloaded
when the script changes, and `prod` on the image of `generate dockerfile`,
loaded with `kind load`, rolled out again without a failed request. The
script of `dev` takes the wheel of the checkout from `/wheel`, which an overlay
of the test mounts over the one of `dev`, as the ConfigMap has the
application, not its dependencies, which uv installs in the pod. CI installs
kind and kubectl with `helm/kind-action`, of the versions of the workflow,
which Renovate bumps.
The image gets the wheel of the checkout, as the version that is tested is not
on PyPI, which is the only change of the generated `Dockerfile`. The workflow
runs only `tt/docker-smoke/smoke.sh`, which runs the script of a variant, as
`app.sh`, with the steps they share in `lib.sh`, so that the logic of the test
is in files of its own, which run locally as well, with Docker:

```sh
mise exec -- tt/docker-smoke/smoke.sh app
```

CI sets `PYTHONWARNINGS=error::SyntaxWarning,error::DeprecationWarning`, so an
invalid escape sequence or a deprecated API fails the build, before a new
Python removes it; the weekly run catches the deprecations of a new Python
release. Python keeps an unknown escape such as `"\:"` as a backslash
followed by the character, which is often exactly what a CSS selector or a
regular expression ported from Perl needs; write it as `"\\:"` or as a raw
string so it survives the Python release that turns the warning into an error.

CI runs the tests in the development mode of Python, `PYTHONDEVMODE=1` (or
`python -X dev`), which shows the `ResourceWarning` of a socket, a file or a
temporary directory that nothing closed. Python writes it to the standard
error, often from the garbage collector, where it cannot fail a test, so CI
fails when `ResourceWarning:` appears in the output. CI runs the scripts at
the same time, whose standard error would mix, so it passes
`--capture-stderr`: the standard error of a script follows the line of its
result, each line after the name of the script, which tells the script that
leaked. It passes `--color` too, as the log of GitHub Actions shows colors
while the output goes to a pipe, not to a terminal; the color of a line of
the standard error is around the whole line, so `ResourceWarning:` is still
in it. It writes the JUnit XML of the results with `--formatter junit=FILE`,
which the action `mikepenz/action-junit-report` turns into the annotations of
the failed tests, and the summary of the job with `--formatter markdown=FILE`,
whose diagnostics of the failures come from the standard error that
`--capture-stderr` captures, as `Pyjo.Test` writes them there and not into the
TAP output, as `Test::More` does.
Each job of the tests uploads its JUnit XML, also the one of pytest, as an
artifact named `junit-` and the name of the job, from which the job `Tests`
makes the summary of the summaries of all the jobs, with
`.github/scripts/test-report.py`, as its summary and as a comment of the pull
request, which each run edits, found by the marker it starts with.
`--stderr-lines 1000` keeps the first and the last lines of the
standard error of a script, as a script that fails in a loop, like an I/O
watcher of `Pyjo.Reactor.Poll` that raises each time the reactor calls it, can
write hundreds of megabytes of it, which the log of GitHub Actions takes
minutes to take in; a `ResourceWarning` among the lines left out does not
fail CI, but such a script fails anyway. The development mode is the debug
mode of asyncio too, whose loop logs a callback that takes longer than 0.1
seconds, which TLS and the applications of the tests do on a busy runner, so
CI sets `PYJO_ASYNCIO_SLOW_CALLBACK=5`, which `Pyjo.Reactor.Asyncio` gives the
loops that it makes, as asyncio has no variable of its own for it; a line of
`Executing <Handle ...> took` is a callback that blocked the loop that long.
A test closes what it
gets, as the handle of an `accept` or `connect` event or a connection of
`http.client`, where Perl closes it with the last reference. To find where a
leaked object was made:

```sh
PYTHONPATH=. mise exec -- python -W default::ResourceWarning -X tracemalloc=50 t/Pyjo/IOLoop.py
```

PyPy has no `_tracemalloc`: it ignores `-X tracemalloc` without a word, and its
`ResourceWarning` names no place. A leak of PyPy alone, as of an object that
CPython closes with its last reference, is found with `gc.collect()` and a
line to the standard error after each subtest, which puts the warning next to
the subtest that leaked it. PyPy skips some tests on macOS, as the one of
`Pyjo.Server.Prefork`, so such a leak may show on Linux only, as in a
container of the image `pypy:3.12-slim`. An object that a forked process
inherits is freed by the garbage collector of the child too, so a leak of one
test can show in the workers of the next one.

CI runs the tests on every supported CPython version and on PyPy. PyPy frees
objects only when its garbage collector runs, not when the last reference
goes, so code must not rely on that: resizing a `bytearray` that a regex
iterator still scans raises `BufferError`, and `__del__` may not run at all
before the interpreter exits.

CI runs them on the free-threaded build of the newest CPython too, without
the global interpreter lock, on which the threads of `Pyjo.Server.Prethread`
run at the same time. It counts the references of a function made at the top
level of a module in a deferred way, so it frees such a function, and what
only the function refers to, only when its garbage collector runs, and a
test that checks that an object is freed without the garbage collector makes
its callback in a function. The garbage collector then frees all of them
together and calls their `__del__` in any order, so a resource that an object
opens for itself, as the loop of its own of `Pyjo.Reactor.Asyncio`, is closed
by `weakref.finalize`, whose callback the garbage collector calls before
them. Locally, uv installs the free-threaded build next to the one of
`mise.toml`, as mise has it only as a flavor of all its versions of Python:

```sh
PYTHONDEVMODE=1 mise exec -- uv run --no-project --python 3.15t python -m Pyjo.Prove -l -j 4 -r t
```

A test script with the syntax of a newer Python, as the t-strings of Python
3.14, cannot skip itself on an older one with `plan(skip_all=...)`, as that
Python does not compile it. It names the version in the inline metadata of
PEP 723, and `Pyjo.Prove` skips it without running it; Perl's `prove` does
not read it.

```python
# /// script
# requires-python = ">=3.14"
# ///
```

pytest runs the test scripts too, through `Pyjo.Test.pytest_plugin`, which
`[project.entry-points.pytest11]` registers, so that pytest loads it wherever
Pyjoyment is installed, with nothing of Pyjoyment importing pytest. It is
for whoever runs `pytest` by habit, as a coding agent or the test explorer of
an IDE, not a second runner of the project: each script is one test of
pytest, which `Pyjo.Prove.run_script` runs in a process of its own, as
`Pyjo.Prove` does, not a fork of the process of pytest, whose modules,
threads and environment the script would inherit, and which Windows does not
have. pytest collects its items before it runs them, and the subtests of a
script are known only from its TAP output, so a script is not split into
tests. The wrapper of `pytest_collect_file` replaces what other plugins make
of a file of the directories of `pyjo_prove_paths`, as the module of pytest
for a `t/test_*.py`. `testpaths = ["t"]` of `pyproject.toml` makes `pytest`
without arguments run the whole suite, and pytest-xdist of the group
`pytest` runs the scripts at the same time, as `-j` of `Pyjo.Prove`, where
pytest alone runs them one after another, four times slower:

```sh
mise exec -- uv run --group pytest pytest -n 4
```

The plugin also calls `Pyjo.Test.raise_failures`, so that the functions of
`Pyjo.Test`, and with them the chains of `Pyjo.Test.Pyjo`, raise
`AssertionError` in a test of pytest: printing TAP there, the `atexit`
handler of `Pyjo.Test` would see tests without a plan and replace the exit
status of pytest with 254. A skip is `unittest.SkipTest`, which pytest and
unittest both know, so `Pyjo.Test` imports nothing of pytest. The module
variable `__tracebackhide__` of `Pyjo.Test` and `Pyjo.Test.Pyjo`, which pytest
reads from the globals of a frame too, leaves their frames out of the
traceback of a failed test. The plugin takes the environment of the scripts
when pytest starts, as the import of `Pyjo.Test.Pyjo` sets `PYJO_LOG_LEVEL`,
and imports `Pyjo.Test.Pyjo` only in the fixture `t`.

The tests of the plugin, `t/Pyjo/Test_pytest_plugin.py`,
`t/docs/Test_pytest_plugin.py` and the section of pytest of
`t/docs/guides_testing.py`, run pytest in a process of their own, and skip
without pytest, which is in the dependency group `pytest`, not in
`dependencies`. CI runs them in the job `pytest`, with the group installed by
uv, which installs the project too, so that pytest loads the plugin of its
entry point, where the tests pass `-p Pyjo.Test.pytest_plugin` without it,
and runs all the test scripts with pytest and pytest-xdist there:

```sh
mise exec -- uv run --group pytest python -m Pyjo.Prove -l t/Pyjo/Test_pytest_plugin.py t/docs/Test_pytest_plugin.py
```

## Benchmarks

`benchmarks/` measures hello world servers with one connection and one
request at a time: Pyjoyment on its own servers, through ASGI and WSGI, and
other Python servers next to it. `benchmarks/README.md` says how to run them
and how to measure well; it is also the recipe for a measurement of another
kind. A change made for speed is measured with `benchmarks/ab.sh`, the
version before and after interleaved on a machine that is otherwise quiet,
and a gain below the noise with the function calls per request of
`benchmarks/profile.sh`. The results, with the machine, the versions and the
load average, go to the issue or the pull request, not to the repository.
