Distributions
=============

Pyjoyment needs nothing besides the Python standard library, so what needs
another library is a distribution of its own, and so is what follows a
specification that is revised more often than Pyjoyment is released. A
distribution adds a module to a namespace of Pyjoyment, as ``Pyjo.Reactor``
for a reactor, ``Pyjoyment.Plugin`` for a plugin or ``Pyjo`` for a protocol.
A distribution is installed from PyPI, as ``pip install Pyjo-MCP``, or from its
Git repository while it is not there.

Reactors
--------

A reactor runs the I/O and the timers of :mod:`Pyjo.IOLoop` on another event
loop, which ``PYJO_REACTOR`` selects before :mod:`Pyjo.IOLoop` is loaded. Its
API is the one of :mod:`Pyjo.Reactor`, which :mod:`Pyjo.IOLoop` calls, so an
application uses it through :mod:`Pyjo.IOLoop`, as it uses
:mod:`Pyjo.Reactor.Asyncio` and :mod:`Pyjo.Reactor.Poll`, and needs nothing
of its own for it. A reactor passes the whole test suite of Pyjoyment.

- `Pyjo.Reactor.Twisted - Low-level event reactor with Twisted support
  <https://pyjoyment.readthedocs.io/projects/pyjo-reactor-twisted/en/latest/>`_

Protocols
---------

A protocol is a package of the namespace ``Pyjo``, with a server and a client
made with Pyjoyment: a route of an application of :mod:`Pyjoyment` and the user
agent of :mod:`Pyjo.UserAgent`.

- `Pyjo.MCP - Model Context Protocol for Pyjoyment
  <https://pyjoyment.readthedocs.io/projects/pyjo-mcp/en/latest/>`_,
  with a `tutorial of its servers
  <https://pyjoyment.readthedocs.io/projects/pyjo-mcp/en/latest/guides/tutorial.html>`_
