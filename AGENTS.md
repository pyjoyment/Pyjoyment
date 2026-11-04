# Agent Guide: Pyjoyment

## Overview

Pyjoyment is a port of [Mojolicious](https://mojolicious.org) to Python. The
`Pyjo` package mirrors the `Mojo::*` toolkit (URL, DOM, HTTP messages, user
agent, servers, event loop), and the `Pyjoyment` package is reserved for the
`Mojolicious::*` framework layer (routes, controllers, renderer, `Lite`).

`Pyjo` does not import `Pyjoyment`. Where a module of `Pyjo`, as an adapter
of another framework, needs what only the framework has, as the static files
of `reply.file` or its exception page, it takes it from the controller that a
route gives it, as `c.helpers.reply.file`, and goes without it when it runs
on its own.

The code was written against Mojo 6.x. The project is being revived: the
target is Mojolicious 9 on Python 3.12+, with asyncio as the only I/O core.
The plan, its order and its progress live in GitHub Issues, starting from the
open umbrella issue about the revival; this file describes how the project
works and why, not what is left to do.

## Design Principles

These are deliberate. A change that looks like a cleanup but goes against one
of them is a regression.

- **The spirit of Mojo over strict PEP 8.** Pyjoyment uses Python creatively,
  the way Mojo bends Perl. Module and class names follow Mojo
  (`Pyjo.URL`, `Pyjo.IOLoop.Client`), objects are created with `Class.new()`,
  and setters return `self` so calls chain. The constructor of Python is
  correct too: a module ends with `new = Pyjo_URL.new`, `object = Pyjo_URL`
  and the class under the name of the module, `URL = Pyjo_URL`, so that
  `from Pyjo.URL import URL` and `URL(...)` work. The documentation keeps
  `import Pyjo.URL` and `Pyjo.URL.new(...)`, as the Google Python Style Guide
  imports modules, not classes. A module has no such name where it would
  hide a builtin (`Pyjo.Exception`), the package (`Pyjo.Test.Pyjo`,
  `Pyjoyment`) or a name that the module has (`TLS` of `Pyjo.IOLoop.TLS`,
  `Template` of `Pyjo.String.Template`), and a module of a command is named
  after the command, not after a class.
- **Every statement has an expression form.** Helpers in `Pyjo.Util` such as
  `die`, `setenv`, `slurp` and `spurt` look redundant next to `raise`,
  `os.environ[...] = ...` and `pathlib`, but statements cannot appear in a
  lambda, a callback or a chain, and these can. Do not replace them with the
  standard library equivalent.
- **Every return value chains.** Functions return the framework's own types so
  the next method is available: `slurp` returns a string, `Collection.join`
  returns `Pyjo.String.Unicode`, DOM queries return `Pyjo.Collection`, and the
  assertions of `Pyjo.Test` return a `Pyjo.Test.Result`, which is true or
  false, as the `bool` of `Test::More`, and tests the value again, as the one
  that `that` makes of a value does. A
  function of the standard library that would wrap the chain from the front
  has a method form that continues it, such as `Collection.zip`, the
  conversions like `to_set()` and `Collection.get`, the expression form of an
  index with a default. A method that only repeats what a postfix operator
  does, like `item(0)` for `[0]`, is not needed.
- **Builtin types are never patched.** New types that subclass or mirror a
  standard one and add framework behaviour are welcome, even when they look
  redundant: `Pyjo.Collection(list)`, `Pyjo.String.Unicode(str)`,
  `Pyjo.String.Bytes(bytes)`, and `Pyjo.String.Mixin`, which lets URL, Path,
  Headers and others behave like strings. Monkey-patching `str`, `list` or any
  other builtin is not.
- **The standard library comes first at the boundary.** Inside, a module keeps
  Mojolicious' semantics; at its boundary, it works with the Python standard
  library. Constructors take the standard types
  (`Pyjo.URL.new(urlsplit(...))`, `Pyjo.Date.new(datetime(...))`), objects
  implement the protocols that the standard library's constructors use, with
  the meaning it expects (`float(date)` is the epoch), and explicit
  conversions are methods named after the library or the type
  (`url.to_urllib()`, `date.to_datetime()`). Where a Mojo method has the name
  of such a conversion, the conversion keeps it, and the Mojo method gets a
  name that says what it renders: Mojo's `to_datetime` is `to_rfc3339`.
- **A parser takes the text and its bytes.** A function that parses a format,
  as `decode_json` of `Pyjo.JSON`, `load` of `Pyjo.YAML`, `Pyjo.INI` and
  `Pyjo.TOML`, and `Pyjo.DOM`, takes a string and bytes, and decodes the bytes
  as a whole document: UTF-8, or the encoding of its byte order mark, which a
  file of Windows PowerShell has, or the one that the format detects
  otherwise, as JSON and YAML do from the null bytes of the first character,
  and HTML as the HTML Living Standard sniffs it, from an XML declaration or a
  `<meta charset>`, after the charset of `Content-Type` in `msg.dom()`. Only
  a whole file or stream is detected, so that one document is not decoded in
  different ways; a part of a message, as the parameters of a URL, a header or
  a frame of a WebSocket, is decoded with its charset alone. A function that
  gives several documents, as `load_all`, gives a `Pyjo.Collection`, as every
  return value chains.
- **Asyncio is the event loop, the reactor is where it is replaced.** Mojo's
  reactor exists because Perl has no standard event loop; Python has one.
  `Pyjo.Reactor.Asyncio` is the API of `Mojo::Reactor` on the asyncio event
  loop, so the I/O of Pyjoyment and the coroutines and tasks of asyncio run in
  the same loop. Only a reactor uses the event loop: everything else goes
  through the methods of `Pyjo.Reactor`, and ruff's TID251 rejects
  `import asyncio` outside `Pyjo/Reactor/`, the test harness, the tests and
  the examples. Another reactor, on uvloop, Trio, gevent or anything else,
  comes from another distribution, in the namespace `Pyjo.Reactor` that
  `extend_path` keeps open, and `PYJO_REACTOR` selects it, as
  `Mojo::Reactor::EV` replaces `Mojo::Reactor::Poll`. `Pyjo.Reactor.Poll`, the port of
  `Mojo::Reactor::Poll` on `select.poll`, or `select.select` on Windows, is a reactor without asyncio that
  runs the same tests, the example of such a reactor. Mojo 9 moved from
  callbacks and `Mojo::IOLoop::Delay` to promises and async/await; a promise
  is a port of `Mojo::Promise`, which follows the Promise of ECMAScript, and
  awaiting it, the counterpart of Mojo's `AWAIT_*` methods, is `__await__`,
  which asks the reactor for what to wait on, so that it works with the event
  loop of any reactor.
- **Concurrency lives in the reactor and the servers.** The reactor runs the
  I/O, the timers and the coroutines, and the workers of
  `Pyjo.Server.Prefork` and `Pyjo.Server.Prethread` run what blocks, with
  `max_clients` as low as 1. Nothing else brings a concurrency of its own: an
  adapter of another framework, as `Pyjo.App.WSGI`, has no pool of threads
  and forks nothing, so a blocking WSGI application blocks the event loop, as
  any blocking operation does, `Pyjo.App.ASGI` runs its application with
  `run_coroutine` of the reactor, and `Pyjo.App.CGI` runs the program of
  each request, which a CGI program is, with `Pyjo.IOLoop.ChildProcess`,
  whose pipes the reactor reads and writes, and which it reaps with a timer,
  without waiting for it. `Pyjo.App.Lambda` runs an event function of
  AWS Lambda in a process of its own too, which gets its invocations one
  after another from a Runtime API that a server on the event loop serves,
  as an execution environment of Lambda does, as a handler called in the
  event loop could not run an event loop of its own, as Mangum does. A package that needs the next cycle of the
  event loop asks the reactor for it, and guards itself against being called
  again from inside the event loop. What only a server knows, as how it runs
  an application, which the flags `wsgi.multithread`, `wsgi.multiprocess`
  and `wsgi.run_once` say, comes from the server, through `server` of the
  application and the hook `before_server_start`, or from the environment of
  an outer WSGI server, best-effort, not from an environment variable, which
  every server of the process and its children would share. The end of a
  server is the counterpart of its start: `server_stopped` of the application
  and the hook `after_server_stop`, once the server has stopped gracefully,
  in each process and thread that has run the application, with the event
  loop no longer running, which the server runs until the promise that they
  return is settled. What an application starts for a server, as the
  lifespan of an ASGI application, ends there, not at the beginning of a
  graceful stop, while requests are still served, nor in `atexit`, which a
  worker of `Pyjo.Server.Prefork` leaves with `os._exit`, as the child of a
  fork has the handlers of the manager, and which comes after the loop of an
  ASGI server is closed.
- **Python 3.12 is the minimum, template strings come with 3.14.** t-strings
  (PEP 750) keep interpolations separate from the literal text, which gives
  templates auto-escaping without a template language. The `t"..."` syntax is
  written by the user, not by the library: the library only accepts
  `string.templatelib.Template` objects, so it supports them where the module
  exists and stays importable on Python 3.12 and 3.13, where PyPy is. On
  every Python, `t()` of `Pyjo.String.Template` takes a string with the
  fields of `str.format` in their place, without `eval`: a t-string is safe
  because it is code, not data, and a string that `eval` reads would run the
  code of whoever wrote it.
- **PyPy is supported on a best-effort basis.** Helper code for PyPy is fine,
  and a test may be skipped on PyPy where PyPy clearly differs from CPython,
  with the reason in the skip message.
- **No runtime dependencies.** Development tools are fine; `dependencies` in
  `pyproject.toml` stays empty.
- **What an area needs, in patterns that port.** The core is a complete set of
  components of its own, and each gives what its area needs, not the whole of
  a standard or of a library that it follows: `Pyjo.YAML` is the YAML of
  configuration files, the builder of `Pyjo.JSON.Schema` the part of zod
  that JSON Schema has, and its validation the keywords of JSON Schema 2020-12
  that the schemas of tools and of APIs have, which reports the others instead
  of ignoring them. Its API takes the patterns of the languages that code
  comes from, Perl and JavaScript, whose idioms Mojolicious shares, and Python,
  where they make the work easier, so that code of Mojolicious, of Node.js or
  of a library of Python ports with few changes: `Pyjo.JSON.Schema` takes the
  type hints of Python and the chains of zod. A feature that Mojolicious does
  not have is welcome by this measure. A standard does not replace a pattern of
  Mojolicious that does more for its area: the routes keep the placeholders of
  Mojolicious, with their types, defaults, formats and the partial match of
  nested routes, which recognize a request, and the URI Templates of RFC 6570
  of `Pyjo.URL.Template` are for the URIs that a protocol gives as templates,
  as MCP and OpenAPI do, whose plugin turns such a template into the pattern
  of a route.

## Development Environment

Tools are declared in `mise.toml` and pinned with checksums in `mise.lock`
(lockfile format 3, which needs mise 2026.9.16 or newer).

```sh
mise install
```

An agent shell does not inherit mise activation, so the `python` on its `PATH`
may not be the pinned one, and nothing warns about it: tests can pass on a
Python the project does not use. Run tools through mise:

```sh
mise exec -- python --version
```

`mise -C <dir>` (`--cd`) does not only take the tools of the `mise.toml` of
`<dir>`: it changes the working directory to `<dir>` before it runs the
command, so that the relative paths of the command, as of a test script, of
`PYTHONPATH=.` or of a file that the command writes, are taken from there,
not from the directory it is called in. Run the command from the checkout
without it, or give it absolute paths:

```sh
mise -C ../Pyjoyment exec -- python -m Pyjo.Prove -l t/Pyjo/URL.py  # t/ of ../Pyjoyment
```

`uv.lock` locks the Python dependencies; there are none at run time yet. After
a change to `pyproject.toml`, run `mise exec -- uv lock`; CI checks that the
lock matches with `uv lock --check`.

`mise install` re-locks only the platform it runs on. After changing a tool
version, run `mise lock` so every platform in `mise.lock` is refreshed; CI
installs with `--locked` and fails on a tool that is not in the lock.

`pyjo-reload` (`Pyjo.Server.Reload`) runs the server command of the
application, `daemon` by default, as a new interpreter of the script, with
`os.fork` and `os.execvp` in a process group of its own, and runs it again when
a file that it watches changes: the script of the application, and `lib` and
`templates` by default, or the paths of `-w` in their place. The manager
creates the listen sockets once and passes them on in `PYJO_LISTEN` and
`PYJO_REUSE`, and the path of its modules in `PYTHONPATH`, as Morbo passes
`PERL5LIB`. Each server loads the toolkit anew, so a change of a module of the
checkout, or `uv sync` of a newer Pyjoyment, takes effect at the next restart,
which a change of a file that it watches or HUP makes; an installed package is
not watched. The manager stops a server with QUIT, which stops the servers of
Pyjoyment immediately, where TERM stops them gracefully and would wait for the
connections that a browser keeps alive, and with TERM of its process group,
which stops the subprocesses and the commands of `-x`, and KILL after 5
seconds. A server ignores QUIT until it sets a handler of its own, as QUIT
would dump the core of one that is still starting.

## Tests

The tests are scripts that print [TAP](https://testanything.org/), written
with `Pyjo.Test`, which is inspired by Perl's `Test::More`, and `Pyjo.Prove`,
inspired by Perl's `prove`, runs them, on the reactor of asyncio and, with
`PYJO_REACTOR`, on `Pyjo.Reactor.Poll`, as CI does on every Python:

```sh
PYTHONDEVMODE=1 mise exec -- python -m Pyjo.Prove -l -j 4 --capture-stderr --stderr-lines 1000 -r t
PYJO_REACTOR=Pyjo.Reactor.Poll PYTHONDEVMODE=1 mise exec -- python -m Pyjo.Prove -l -j 4 --capture-stderr --stderr-lines 1000 -r t
```

A change of the code comes with a test of it, which leaves nothing open, as a
`ResourceWarning` of the development mode of Python fails CI. The layout of
`t` and `tt`, the tests ported from Mojolicious, the matrix of CI with PyPy,
the free-threaded build and Windows, the tests of the servers, of JSON Schema
and of Docker, pytest, and the benchmarks of a change made for speed are the
skill `framework-tests`, in `.claude/skills/framework-tests/SKILL.md`.

## Porting from Mojolicious

The target is **Mojolicious 9**. A module is ported anew from a release of
it, its tests first, from `t/mojo/*.t`, then the module, then its POD into
the docstrings, and its documentation names the release. Code that differs
from Mojolicious has a marker, so that the diff of a newer Mojolicious applies
around it:

- `# Not in Mojolicious:` for what Mojolicious does not have, as a method or
  a branch for Python only;
- `# Renamed from Mojolicious:` for a method with another name than the
  translations give it;
- `# Left out from Mojolicious:` for what is left out on purpose;
- `# Unlike Mojolicious:` for behaviour that differs on purpose, with what Mojo
  does and why;
- `# TODO:` for what waits for a module that is not ported yet.

The procedure, the markers and the translations of Perl into Python, which a
port and any change of ported code follow, are the skill `porting`, in
`.claude/skills/porting/SKILL.md` and `translations.md` next to it.

## Standard Input and Output

`Pyjo.IOLoop.Stdio` takes the standard input and output of the process for a
protocol, as the transport stdio of MCP or LSP, where a stray byte breaks the
protocol, and `Pyjo.IOLoop.Messages`, `Pyjo.Server.Stdio` and `serve` of
`Pyjo.JSON.RPC` carry the messages on it. How they do it, and why, is the
skill `stdio-protocols`, in `.claude/skills/stdio-protocols/SKILL.md`.

## Distributions of Their Own

What needs a dependency is a distribution of its own, never a part of
Pyjoyment: a reactor on another event loop, as Pyjo-Reactor-Twisted, or a
plugin that needs a library. Each lives in a repository of its own, next to
the checkout of Pyjoyment, depends on Pyjoyment and never the other way, and
follows the conventions of this file, which its own `AGENTS.md` points to. Its
package, its tests with the suite of Pyjoyment, its reactor and its
documentation are the skill `distributions`, in
`.claude/skills/distributions/SKILL.md`; what it teaches about Pyjoyment comes
back here.

## Linting and Formatting

[Trunk](https://docs.trunk.io) runs the linters and formatters configured in
`.trunk/trunk.yaml`: ruff for Python (lint, import order and formatting),
Biome for CSS, HTML, JavaScript, JSON, Markdown and YAML (lint and
formatting), taplo for TOML, yamllint, actionlint, and shellcheck and shfmt
for the shell scripts. shellcheck runs
with all its checks but the ones that `.shellcheckrc` disables, and shfmt
formats as `.editorconfig` says, with the branches of `case` indented: the
definition of shfmt in `.trunk/trunk.yaml` runs it without the flags that
would make it ignore `.editorconfig`. actionlint is the one of the
maintained fork kjanat/actionlint, whose releases continue those of
rhysd/actionlint after 1.7.12: `downloads` in `.trunk/trunk.yaml` replaces the
URLs of the plugin with those of the fork, whose files have the same names.
Biome reads `biome.jsonc`, which leaves out the files that
Pyjoyment keeps as they are, as the bundled libraries, the sources of the
images and the files of the tests, so that the extension of Biome of an
editor checks the same files.
The version of Biome is the pinned one of `.trunk/trunk.yaml`, where `!` keeps
it from `trunk upgrade`, and which Renovate bumps: `package.json` has only the
packages that the bundle and the tests need. Renovate cannot run
`biome migrate`, so the workflow Biome Migrate runs it with
`npx --yes @biomejs/biome@<version>` of that version, migrates `biome.jsonc`
on the branch of Renovate and commits it with the token of the workflow, as
Bundle Check does, as the author that `gitIgnoredAuthors` of
`.renovaterc.json` names, so that Renovate keeps updating the branch, and
starts the checks of the commit with `workflow_dispatch`; anywhere else, a
`biome.jsonc` that this Biome would migrate fails the check.
The definition of Biome in `.trunk/trunk.yaml` runs it in the sandbox of Trunk
with a copy of `biome.jsonc`, as Biome takes the options of its parser, as
the front matter of Markdown, only for the files under the directory of its
configuration, without the `.gitignore` of the repository, and matches its
report at every line, where the plugin of Trunk reports only the first issue
of a batch. yamllint checks what Biome does not,
as the duplicated keys.

The `trunk` launcher is not pinned in
`mise.toml` (mise only has it as an npm package); install it with
`mise use -g trunk` or the installer from the Trunk documentation. The
launcher downloads the CLI version named in `trunk.yaml`.

```sh
trunk fmt          # format changed files
trunk check        # lint changed files
trunk check --all  # lint everything, as CI does
```

Without `--fix` or `--no-fix`, `trunk check` asks whether to apply each
autofix and waits for an answer, which hangs a non-interactive shell such as
an agent's. Pass one of them there.

`trunk-fmt-pre-commit` formats staged files on commit and
`trunk-check-pre-push` checks before a push, once Trunk has installed its git
hooks (any `trunk` command does). The hook formats with the configuration that
is staged, so a change to the formatter configuration goes in its own commit,
before the code that depends on it.

A commit that only reformats code goes into `.git-blame-ignore-revs`, so that
`git blame` and GitHub's blame view skip it. The trunk action
`git-blame-ignore-revs` points `blame.ignoreRevsFile` at the file locally.

The workflow Automated trunk upgrade runs `trunk upgrade` every day, and
`trunk fmt --all` after it, and keeps its changes in the pull request of the
branch `automated/trunk-upgrade`, which a comment `/rerun` runs again. It
works with the token of the workflow, whose push leaves the runs of
`pull_request` waiting for an approval, so it starts Build, Tests and Trunk
Check, which the ruleset of `main` requires, on the branch with
`workflow_dispatch`, as Bundle Check does. A linter that the upgrade enables is
kept or disabled there, with its configuration in the root of the repository,
where the extensions of the editors find it, not in `.trunk/configs`.

The linters are there to keep plain mistakes out, not to enforce PEP 8: the
project bends Python's conventions on purpose, and a rule that fights its
style is turned off. Every disabled rule or linter carries a comment with the
linter's own message for it, not just the code (`B018 "Found useless
expression..."`, not `B018`), and why it does not fit. A single false
positive is silenced where it happens (`# noqa: B023`), with a comment on the
line above.

The ruff configuration lives in `pyproject.toml`. Its rule list is explicit:
newer ruff versions enable many more rules by default, including one that
rejects the Mojo-style module names. Formatting uses single quotes and a line
length of 120. Imports list `Pyjo` modules before the standard library, like
Mojo modules list `Mojo::*` before core modules.

New code targets Python 3.12 and newer: no compatibility shims for older
versions. The ruff `UP` rules and `target-version` keep it that way; with a
newer target, the formatter would use syntax such as `except A, B:` (PEP 758,
Python 3.14), which also looks like Python 2's `except A, e:`. A test of
t-strings, which only Python 3.14 compiles, is listed under
`per-file-target-version` of ruff and `executionEnvironments` of pyright in
`pyproject.toml`, with `pythonVersion = "3.14"`.

## Type Hints

Modules are annotated as they are ported, and pyright checks them in strict
mode; the code that has not been ported yet is not type-checked. The
configuration in `pyproject.toml` turns type checking off for everything and
lists the annotated modules under `strict`. A ported module goes on that list
in the same change. Trunk passes the changed files to pyright explicitly,
which makes pyright ignore `include` and `exclude`, so the per-file mode is
what limits the checks. Examples that need libraries the project does not
install are excluded from pyright in `.trunk/trunk.yaml`, and so is
`Pyjo.Test.pytest_plugin`, which imports pytest, so it is not on the strict
list: check it in strict mode with pytest installed, from a configuration
outside the repository that names it in `include` and the virtual
environment with pytest in `venvPath` and `venv`. pyright, as Python with a
script, resolves an import against the directory of the file first, so a
module named `pytest.py` would import itself.

Trunk reports only the issues that a change introduces, and counts an issue
in a file that already exists upstream as existing, even when the file has
just been put on the strict list. Check a newly strict module with
`trunk check --show-existing` or with `.trunk/tools/pyright` directly.

Python 3.12 evaluates the annotations of a function when it defines it, so
a module in an import cycle, like `Pyjo.String.Unicode` and
`Pyjo.String.Bytes`, quotes the annotations that name the other module. So
does a package that names its own submodules, as `Pyjo.DOM.CSS` in
`Pyjo/DOM/__init__.py`: `Pyjo.DOM` is not an attribute of `Pyjo` until the
package is loaded.

A module that ends with `object = Pyjo_X` cannot use `object` in its
annotations: they are evaluated lazily (PEP 649, Python 3.14), when `object`
is the class. Such a module declares `type Anything = builtins.object` and
uses that. pyright on Python 3.12 does not see it, as it evaluates the
annotations where they are, but a distribution on Python 3.14 calls the
methods of the class, so `t/stdlib/annotations.py` checks it.

Annotations use the Python 3.12 syntax: generics with type parameters
(`class Collection[T](list[T])`, `def f[T](x: T) -> T`), `type` aliases,
`Self` for methods that return `self` so that chains keep their type, and
`@overload` for functions with several call forms, like `Pyjo.Test.subtest`.
A descriptor class with an overloaded `__get__` types what Mojo makes with
`monkey_patch`: a `property` made by a call is `Any` to pyright.
A class method that returns instances of the class, like `parse`, is generic
(`def parse[C: Pyjo_Cookie](cls: type[C], ...) -> list[C]`): with `list[Self]`,
pyright rejects the method of a subclass as an incompatible override. A
ported module that uses one that is not ported yet gets annotations on the
signatures it uses, while the module itself stays off the strict list. Where
Mojo-style magic cannot be typed, `Any` is fine, with a comment that says why.
`Pyjo/py.typed` and `Pyjoyment/py.typed` (PEP 561) tell type checkers that the
packages are typed, so that pyright in strict mode takes the annotations of a
module of Pyjoyment that a distribution of its own uses, as a controller,
instead of failing on a library without stubs.

The helpers, which `__getattr__` of `Pyjoyment.Controller` and of `Pyjoyment`
finds in the renderer, take their types from the classes `Helpers` of
`Pyjoyment.Plugin.DefaultHelpers` and `Pyjoyment.Plugin.TagHelpers`, which the
two classes inherit for type checkers only, under `TYPE_CHECKING`, so that
their bases and the lookup of a helper at run time stay those of Mojo. Each
attribute of such a class is a `Pyjoyment.Controller.Helper` of the function
that `register` registers, whose type is the one of the function without the
controller, so the signature is written once, and a prefix of nested helpers
is an annotation with a class of its own. A new helper of a default plugin
goes into its class with the same function, which
`t/Pyjoyment/helper_types_lite_app.py` compares with the helpers that the
plugin registers. The return type of the function is what an application
gets, so a helper that returns `Any` is `Any` there. The test is on the strict
list, with `reportUnnecessaryTypeIgnoreComment`, so that a call that pyright
rejects, as a helper without its call, stays rejected.

## Session and Temporary Files

Files created while working on a task, such as scratch scripts, command
output, a clone of the Mojo repository, or build artifacts, must never be
written into the tracked working tree, or they leak into git history. Write
them to a temporary directory outside the repository.

Never `git add -A` or `git add .` blindly: review `git status` first and stage
only the files the change actually touches.

## Security

Never read, display, reference, or include the contents of the following files:

- `.env`, `.env.*`, `.envrc`
- `.pypirc`
- `*.jks`, `*.keystore`, `*.p12`, `*.pfx`, `*.pem`, `*.key`

The same list is git-ignored in `.gitignore` and enforced for Claude Code by
the `permissions.deny` rules in `.claude/settings.json`. Change all three
together. The one exception is the keys of `Pyjo/IOLoop/certs`,
`server.key`, of the default certificate for TLS servers (as in Mojo), and
`client.key`, of a certificate of a client for the tests of the distributions:
they are tracked, and `.gitignore` whitelists them, because hatchling builds
packages from the `.gitignore` patterns and would otherwise leave them out of
the wheel.

The certificate `server.crt` is for `localhost` and `127.0.0.1`, `client.crt`
for a client, and a CA of its own, `ca.crt`, signs them, so that the tests can
verify them. The key of the CA is not in the repository, as whoever trusts
`ca.crt`, which the wheel has, as a developer who adds it to the trust store
of a system for `https://localhost`, would trust any certificate that the key
signs, for any name. The maintainer keeps it outside of the repository, as
`Pyjo/IOLoop/certs/README.md` says, and signs a new certificate of the set
with it; without it, all of them are made again with a new CA, with OpenSSL 3
(RSA 2048, a hundred years, `basicConstraints`, `keyUsage`,
`extendedKeyUsage=serverAuth` and `subjectAltName=DNS:localhost,IP:127.0.0.1`
for the server, `extendedKeyUsage=clientAuth` for the client).

The certificates of the tests in `t/certs` are the other exception: their
keys are tracked, and `.gitignore` lets `t/certs/*.key` in, as the tests of
TLS need them. Another CA of its own, `t/certs/ca.crt`, whose key is kept
outside of the repository too, signs `server` (`localhost`, `127.0.0.1`,
`::1`, `serverAuth`), `mojo_server` (`mojolicious.org`) and `client`
(`clientAuth`), and `bad` is self-signed. They are made with the commands in
`t/certs/README.md`. Claude Code does not read these keys either: the rules
of `.claude/settings.json` stay as they are, and the tests read the keys.

## Documentation

`README.md` is for a user, the front page of the repository on GitHub and of
the project on PyPI, and this file is for whoever changes the code: how it
works and why. The docstrings are ported from the POD of Mojolicious, the
guides of `docs/guides` from `Mojolicious::Guides`, and Sphinx builds them
with `-W`, as the workflow Docs does:

```sh
mise exec -- uv run --with-requirements docs/requirements.txt sphinx-build -W --keep-going -b html docs docs/_build/html
```

How README.md and the pages of `docs` repeat each other, how the examples are
included and tested, and how a guide is ported and grows, is the skill
`framework-docs`, in `.claude/skills/framework-docs/SKILL.md`.

Documentation describes how things are and has to stay true without anyone
maintaining it. Keep out of it whatever goes stale on its own: issue and pull
request numbers, dates, counts that change without the document changing, and
the record of how it got there (decisions taken, alternatives rejected, status
lines). State the rule or the fact instead. The history belongs in the issue
and the pull request.

## Skills for Coding Agents

The skills for the coding agents that write applications with Pyjoyment are
the plugin `pyjoyment` of Claude Code in `plugins/pyjoyment`, a skill in each
`skills/<name>/SKILL.md`, which the marketplace of
`.claude-plugin/marketplace.json` of the repository lists, so that
`/plugin install pyjoyment --marketplace pyjoyment/Pyjoyment` installs it. The
plugin is not in the root of the repository, as Claude Code warns of the
`CLAUDE.md` of the root of a plugin. It has no version, so that Claude Code
updates it with each commit, instead of a version that a change of a skill
would have to bump. Its icon, `.claude-plugin/icon.png`, is the joystick of
`Pyjoyment/resources/public/favicon.svg`, rendered with
`rsvg-convert -w 512 -h 512`, as Claude Code takes no SVG for it.

A skill is the idioms, the mistakes, the commands and the links to the
documentation of its subject, not a copy of a guide, as it goes into the
context of an agent, and the description of each says when it applies, so
that the skills do not overlap. Its front matter has only the fields of the
format of Agent Skills, `name` and `description` above all, which other agents
read too, as Claude Code ignores what it does not know, but other agents
reject it. `t/docs/skills.py` checks the marketplace, the plugin and the front
matter of each skill, and a test of a skill, as `t/docs/skills_migration.py`,
runs its code, which `blocks` of `t/lib/Skills.py` takes from its `SKILL.md`,
so that an example that went stale does not teach an agent the wrong thing.
`claude plugin validate .` and `claude plugin validate ./plugins/pyjoyment`
check them as Claude Code reads them. Biome formats them with `frontmatter` of
`markdown.parser` of `biome.jsonc`, without which it reads the front matter of
a `SKILL.md` as Markdown, and turns its YAML into a heading.

The skills of whoever changes Pyjoyment itself are skills of the project, in
`.claude/skills`, which Claude Code loads by their descriptions, and other
agents read as the files that this file names: `porting`, `framework-tests`,
`framework-docs`, `stdio-protocols` and `distributions`. Each holds what a
change of its subject needs, so that this file keeps the principles and what
every change needs. A skill of the project has the same front matter as one
of the plugin, which `t/docs/skills.py` checks too.

## Releases

A release is a tag of the version of `pyproject.toml`, without a `v`, as
`0.1.0`. The workflow Automated version sets the version with `uv version`,
the components of its `--bump` from a list, as `patch dev` or `minor rc`, or
the version of `manual`, in the pull request of the branch
`automated/version`. After a release, a pre-release goes with the release
that it comes before, as PEP 440 orders `0.2.0.dev1` before `0.2.0`, so `dev`
alone after `0.2.0` fails. Automated tag tags the merge commit of that pull
request when it is merged, or with a comment `/tag` of a
maintainer on it, and starts Release on the tag with `workflow_dispatch`, as
a tag of the token of a workflow starts no workflow; a tag that is pushed
starts Release too. A development version, as `0.1.1.dev1`, is not tagged.

Release builds the sdist and the wheel with an SBOM of SPDX, which Syft makes
of `package-lock.json` only: the JavaScript libraries that `npm run bundle`
copies into the package are all of others that the package has, and
`uv.lock` has only the dependency groups, which the package does not install.
The sdist takes the SBOM, which `.gitignore` ignores, as an artifact of
hatchling. `actions/attest` attests the build provenance of the files and
their SBOM, and Release makes a draft of the GitHub release with them, whose
notes, generated from the pull requests, are rewritten before it is
published. A release that failed is run again after its GitHub release is
deleted, which immutable releases would not allow, as the tag of a deleted
one cannot be used again.

The workflow PyPI, run manually, publishes the sdist and the wheel of the
latest published release, or of the release of the tag of its input, on PyPI
once their attestations of Release verify, with the attestations of PEP 740,
in the environment `publishing`, which waits for an approval and takes `main`
and tags only. The trusted publisher of PyPI names `pypi.yaml` and that
environment. The action of PyPI runs on x86-64, as its image has no build for
ARM.

```sh
gh attestation verify pyjoyment-0.1.1.tar.gz -R pyjoyment/Pyjoyment
gh attestation verify pyjoyment-0.1.1.tar.gz -R pyjoyment/Pyjoyment --predicate-type https://spdx.dev/Document/v2.3
```

## Commits and Pull Requests

- Commit subjects are short and in the imperative or descriptive style of the
  history, optionally prefixed with the module:
  `Pyjo.IOLoop.Client: port is converted to int`.
- Keep mechanical changes (formatting, import order, renames) and functional
  changes in separate commits.
- A pull request description lists the changes and a validation checklist;
  check an item only once it has been verified.
- A pull request fixes what it finds at the cause, also in another module than
  the one it is about, as the reactor of a change of an adapter, in a commit
  of its own, rather than working around it in a test: Pyjoyment is a
  framework, and a defect that one module shows is often in the one below it.
- A change of `AGENTS.md` alone, as what a distribution of its own teaches, is
  committed on `main` directly, without a pull request.
