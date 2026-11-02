Status
======

Pyjoyment is an evolution of `Mojolicious <https://mojolicious.org>`_, the
real-time web framework for Perl. It keeps the API of Mojolicious with Python
names, so its documentation and experience carry over, and the tests of
Mojolicious, ported with each module, are the specification that the code
follows. A ported module names the Mojolicious version it was ported from in
its documentation.

Pyjoyment requires Python 3.12 or newer and runs on PyPy on a best-effort
basis. It runs on Linux, macOS and Windows. On Windows, Python has no
``os.fork`` and no UNIX domain sockets, so ``Pyjo.Server.Prefork``,
``Pyjo.Server.Hot``, ``Pyjo.Server.Reload`` and ``Pyjo.IOLoop.Subprocess`` do not
run there, and ``Pyjo.Server.Prethread`` runs the workers in threads instead.
The event loop watches up to 512 sockets there, with the ``select`` of Windows,
and a server stops with Ctrl-C, gracefully, or with Ctrl-Break, immediately.
