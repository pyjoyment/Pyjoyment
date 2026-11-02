---
name: distributions
description: Make a distribution of its own for Pyjoyment, as a reactor on another event loop or a plugin that needs a library, in a repository next to the checkout, with its package in a namespace of Pyjoyment, its tests with the suite of Pyjoyment, the reactor of an event loop that is unique in a process, the state in the kernel, and the direction of the dependencies. Use when creating or changing such a distribution.
---

# Distributions of Their Own

What needs a dependency is a distribution of its own, never a part of
Pyjoyment: a reactor on another event loop, as Pyjo-Reactor-Twisted, or a
plugin that needs a library. Each lives in a repository of its own, next to
the checkout of Pyjoyment, so that one does not pull the dependencies of
another, and follows the conventions of this file, which its own `AGENTS.md`
points to; its documentation leaves out the paragraph "It has no counterpart
in Mojolicious", which is obvious there. What it teaches about Pyjoyment comes
back here.

- **The package.** A distribution adds a module to a namespace of Pyjoyment,
  `Pyjo.Reactor` or `Pyjoyment.Plugin`, which `extend_path` keeps open: its
  wheel has only the module (`only-include` of hatchling), without the
  `__init__.py` of the packages, which are those of Pyjoyment. It depends on
  Pyjoyment of PyPI, of the release that has what it needs. One that needs a
  change of Pyjoyment that is not released yet takes Pyjoyment from its Git
  repository with `tool.uv.sources` until the release, never from a path to
  the checkout next to it: uv applies the sources of a dependency of Git, so
  whoever installs the distribution from Git would get a subdirectory of its
  repository that does not exist. Its tests
  lay the checkout next to it over the one of Git with `uv run --with-editable
../Pyjoyment`, so that they test what is there.
- **Pyright and the namespace.** Pyright takes the regular package `Pyjo` of
  Pyjoyment of `.venv` for an import of `Pyjo.X`, which hides the module of
  the checkout that `extend_path` finds at run time. A module of the
  distribution imports its package relatively, as `from .. import MCP`; code
  outside of the package, as a script in the root of a repository that has a
  module of `Pyjo` beside it, takes the module from `importlib.import_module`
  as `Any`, with a comment that says why.
- **The tests.** Its CI checks out Pyjoyment next to it and runs the whole
  suite of Pyjoyment with the distribution, as `PYJO_REACTOR` set to the
  reactor, on the Pythons of the matrix of Pyjoyment, daily too, as Pyjoyment
  changes more often. A test of its own covers only what the suite does not,
  as the port of the test of a reactor of Mojolicious (`reactor_ev.t`).
- **A reactor on an event loop that is unique in a process**, as the reactor
  of Twisted, is a subclass of `Pyjo.Reactor.Poll`, as `Mojo::Reactor::EV` is,
  and `new` returns a `Pyjo.Reactor.Poll` object while another object uses the
  loop. A loop that cannot run a second time, as `reactor.run()` of Twisted, is
  driven one iteration at a time by `one_tick`, with the I/O before the timers,
  as the reactor of poll has them: with the timers first, a recurring timer of
  no time starves the I/O. While the loop runs, started by something else,
  `start` and `one_tick` return right away, as `Pyjo.Reactor.Asyncio` does.
- **State in the kernel.** Pyjoyment closes some sockets before it removes
  them from the reactor, and forks the workers of `Pyjo.Server.Prefork`, the
  servers of `Pyjo.Server.Hot` and `Pyjo.Server.Reload`, and the subprocesses.
  A loop that keeps its state in the kernel, as epoll or kqueue, loses a
  socket that is closed before it is removed, and shares the state with the
  child of a fork, so a reactor prefers a loop with its state in the process,
  as poll or select, gives the child of a fork what is its own, as the waker
  of the loop, and is tested on Linux, as macOS has no epoll to show it.
- **Hang-ups.** A loop that drops a handle at a hang-up or an error without
  data, as a refused connection, still calls the watcher, as
  `Pyjo.Reactor.Poll` does: the watcher finds the error of the socket, as
  `Pyjo.IOLoop.Client` does to try the next address.
- **References.** The callbacks that a loop of the whole process keeps refer
  to the reactor weakly, and a callback does not refer to itself, as a
  recurring timer that schedules itself from its closure would: the cycle
  keeps the callback, and what it refers to, as a controller, until the
  garbage collector runs, which `t/Pyjoyment/longpolling_lite_app.py` catches.
  A finalizer removes what an object leaves in the loop.
- **The direction of the dependencies.** A distribution depends on
  Pyjoyment, never the other way: its code imports Pyjoyment, its CI checks
  Pyjoyment out, and its documentation may link to the one of Pyjoyment, with
  intersphinx too. Pyjoyment knows a distribution only by a plain link on the
  page of the documentation that lists them, which the distribution adds with
  a pull request: no import, no autodoc, no intersphinx and no CI of a
  distribution, which would make Pyjoyment depend on its dependencies, and
  fail its build with -W where the site of the distribution does not answer.
- **The formats.** The docstrings are reStructuredText, as those of
  Pyjoyment, so that they read the same; the README and `AGENTS.md` are
  Markdown, which GitHub and PyPI render, as those of Pyjoyment.
