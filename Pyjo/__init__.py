"""
Pyjo - Web development toolkit
==============================
::

    # HTTP/WebSocket user agent
    import Pyjo.UserAgent
    ua = Pyjo.UserAgent.new()
    print(ua.get('www.mojolicious.org').result.headers.server)

    # HTML/XML DOM parser with CSS selectors
    import Pyjo.DOM
    dom = Pyjo.DOM.new('<div><b>Hello Pyjo!</b></div>')
    print(dom.at('div > b').text)

    # Python-ish templates
    import Pyjo.Template
    mt = Pyjo.Template.new(vars=True)
    print(mt.render('Hello <%= what %>!', {'what': 'Pyjo'}))

    # HTTP/WebSocket server
    import Pyjo.Server.Daemon
    daemon = Pyjo.Server.Daemon.new(listen=['http://*:8080'])

    @daemon.unsubscribe('request').on('request')
    def request(daemon, tx):
        tx.res.code = 200
        tx.res.body = b'Hello Pyjo!'
        tx.resume()

    daemon.run()

    # Event loop
    import Pyjo.IOLoop
    for seconds in range(1, 6):
        Pyjo.IOLoop.timer(seconds, lambda loop, seconds=seconds: print(seconds))
    Pyjo.IOLoop.start()

A powerful web development toolkit, with all the basic tools and helpers
needed to write simple web applications and higher level web frameworks, such
as :mod:`Pyjoyment`. Some of the most commonly used tools are
:mod:`Pyjo.UserAgent`, :mod:`Pyjo.DOM`, :mod:`Pyjo.JSON`,
:mod:`Pyjo.Server.Daemon`, :mod:`Pyjo.Server.Prefork`, :mod:`Pyjo.IOLoop` and
:mod:`Pyjo.Template`.

One-liners
----------
::

    $ python -m Pyjo 'g("mojolicious.org").dom().at("title").text'

A collection of functions for fun Python one-liners, which
``from Pyjo import *`` imports, and with which ``python -m Pyjo`` runs its
code: the value of an expression is printed, and the arguments after the code
are in :data:`sys.argv`. Ten redirects will be followed by default, you can
change this behavior with the ``PYJO_MAX_REDIRECTS`` environment variable. ::

    $ PYJO_MAX_REDIRECTS=0 python -m Pyjo 'g("example.com").code'

Proxy detection is enabled by default, but you can disable it with the
``PYJO_PROXY`` environment variable. ::

    $ PYJO_PROXY=0 python -m Pyjo 'g("example.com").body'

TLS certificate verification can be disabled with the ``PYJO_INSECURE``
environment variable. ::

    $ PYJO_INSECURE=1 python -m Pyjo 'g("https://127.0.0.1:3000").body'

If it is not already defined, ``python -m Pyjo`` will set the
``PYJO_LOG_LEVEL`` environment variable to ``fatal``.

:mod:`Pyjo` is a namespace package that may be split across multiple
distributions, as another reactor in :mod:`Pyjo.Reactor` comes from one of its
own.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo.pm>`_
and `ojo <https://github.com/mojolicious/mojo/blob/v9.49/lib/ojo.pm>`_ of
Mojolicious 9.49.

Functions
---------
"""

import os
import sys
import time

from collections.abc import AsyncIterable, Callable, Iterable
from pkgutil import extend_path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import Pyjo.Collection
    import Pyjo.DOM
    import Pyjo.File
    import Pyjo.Iterator
    import Pyjo.JSON.Schema
    import Pyjo.Message.Response
    import Pyjo.String.Bytes
    import Pyjo.String.Unicode
    import Pyjo.URL
    import Pyjo.UserAgent

    import re


# Not in Mojolicious: a namespace package, as Python does not merge a regular package from every directory of sys.path
__path__ = extend_path(__path__, __name__)

# The functions of ojo, which the modules they use are imported for when they are called, so that a module of Pyjo
# does not import them
__all__ = ['a', 'b', 'c', 'd', 'f', 'g', 'h', 'i', 'j', 'l', 'n', 'o', 'p', 'q', 'r', 't', 'u', 'w', 'x', 'z']

_agent: 'Pyjo.UserAgent.object | None' = None


# Unlike Mojolicious: the user agent of the functions is one of their own, whose server gets the application of
# Pyjoyment.Lite when a makes it, where ojo makes the application for the package that uses it and takes its user agent,
# as a module of Pyjo imports Pyjoyment only when a function needs it
# Left out from Mojolicious: the hook around_action that sets $_ to the controller, as an action gets it as its argument
def _ua() -> 'Pyjo.UserAgent.object':
    global _agent
    if _agent is None:
        import Pyjo.UserAgent

        _agent = Pyjo.UserAgent.new()
        if os.environ.get('PYJO_MAX_REDIRECTS') is None:
            _agent.max_redirects = 10
        if os.environ.get('PYJO_PROXY') is None:
            _agent.proxy.detect()
    return _agent


def a(*args: Any, **constraints: Any) -> Any:
    """::

        app = a('/hello', lambda c: c.render(json={'hello': 'world'}))

    Create a route with ``any`` of :mod:`Pyjoyment.Lite` and return the
    current :mod:`Pyjoyment.Lite` object, the application of the module that
    calls it. ::

        $ python -m Pyjo 'a("/hello", {"text": "Hello Pyjo!"}).start()' daemon
    """
    import Pyjoyment.Lite

    functions = Pyjoyment.Lite._functions(sys._getframe(1))  # pyright: ignore[reportPrivateUsage]
    ua = _ua()
    ua.server.app = functions['app']
    functions['any'](*args, **constraints)
    return ua.server.app


def b(*parts: object) -> 'Pyjo.String.Bytes.object':
    """::

        stream = b(b'lalala')

    Turn bytes into a :mod:`Pyjo.String.Bytes` object. ::

        $ python -m Pyjo 'b(g("mojolicious.org").body).html_unescape().say()'
    """
    import Pyjo.String.Bytes

    return Pyjo.String.Bytes.b(*parts)


def c[T](*elements: T) -> 'Pyjo.Collection.object[T]':
    """::

        collection = c(1, 2, 3)

    Turn list into a :mod:`Pyjo.Collection` object.
    """
    import Pyjo.Collection

    return Pyjo.Collection.c(*elements)


def d(*args: Any, **kwargs: Any) -> 'Pyjo.Message.Response.object':
    """::

        res = d('example.com')
        res = d('http://example.com', {'Accept': '*/*'}, b'Hi!')
        res = d('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        res = d('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})

    Perform ``DELETE`` request with :attr:`Pyjo.UserAgent.Pyjo_UserAgent.delete`
    and return resulting :mod:`Pyjo.Message.Response` object.
    """
    return _ua().delete(*args, **kwargs).result


def f(*parts: object) -> 'Pyjo.File.object':
    """::

        path = f('/home/sri/foo.txt')

    Turn string into a :mod:`Pyjo.File` object. ::

        $ python -m Pyjo 'r(j(f("hello.json").slurp()))'
    """
    import Pyjo.File

    return Pyjo.File.path(*parts)


def g(*args: Any, **kwargs: Any) -> 'Pyjo.Message.Response.object':
    """::

        res = g('example.com')
        res = g('http://example.com', {'Accept': '*/*'}, b'Hi!')
        res = g('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        res = g('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})

    Perform ``GET`` request with :attr:`Pyjo.UserAgent.Pyjo_UserAgent.get` and
    return resulting :mod:`Pyjo.Message.Response` object. ::

        $ python -m Pyjo 'g("mojolicious.org").dom("h1").map("text").join("\\n")'
    """
    return _ua().get(*args, **kwargs).result


def h(*args: Any, **kwargs: Any) -> 'Pyjo.Message.Response.object':
    """::

        res = h('example.com')
        res = h('http://example.com', {'Accept': '*/*'}, b'Hi!')
        res = h('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        res = h('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})

    Perform ``HEAD`` request with :attr:`Pyjo.UserAgent.Pyjo_UserAgent.head` and
    return resulting :mod:`Pyjo.Message.Response` object.
    """
    return _ua().head(*args, **kwargs).result


# Not in Mojolicious: a lazy iterator, as c makes a collection
def i[T](iterable: Iterable[T] | AsyncIterable[T] = ()) -> 'Pyjo.Iterator.object[T]':
    """::

        iterator = i(range(1, 4))

    Turn iterable or asynchronous iterable into a :mod:`Pyjo.Iterator`
    object. ::

        # "2, 4, 6"
        i(range(1, 4)).map(lambda n: n * 2).join(', ')
    """
    import Pyjo.Iterator

    return Pyjo.Iterator.new(iterable)


def j(value: Any) -> Any:
    """::

        data = j([1, 2, 3])
        data = j({'foo': 'bar'})
        value = j(data)

    Encode Python data structure or decode JSON with :func:`Pyjo.JSON.j`. ::

        $ python -m Pyjo 'f("hello.json").spew(j({"hello": "world!"}))'
    """
    import Pyjo.JSON

    return Pyjo.JSON.j(value)


def l(*args: Any) -> 'Pyjo.URL.object':  # noqa: E743
    """::

        url = l('https://mojolicious.org')

    Turn a string into a :mod:`Pyjo.URL` object. ::

        $ python -m Pyjo 'l("/perldoc").to_abs(l("https://mojolicious.org"))'
    """
    import Pyjo.URL

    return Pyjo.URL.new(*args)


def n(cb: Callable[[], object], count: int = 1) -> None:
    """::

        n(lambda: ...)
        n(lambda: ..., 100)

    Benchmark callback and print the results to ``sys.stderr``, with an
    optional number of iterations, which defaults to ``1``. ::

        $ python -m Pyjo 'n(lambda: print(g("mojolicious.org").code))'
    """
    # Not in Mojolicious: the timing of Benchmark, which Python does not have, without the time of an empty loop
    start, times = time.perf_counter(), os.times()
    for _ in range(count):
        cb()
    wall, end = time.perf_counter() - start, os.times()
    usr, sys_ = end.user - times.user, end.system - times.system
    line = f'{wall:2g} wallclock secs ({usr:5.2f} usr + {sys_:5.2f} sys = {usr + sys_:5.2f} CPU)'
    if usr + sys_ > 0:
        line += f' @ {count / (usr + sys_):5.2f}/s (n={count})'
    print(line, file=sys.stderr)


def o(*args: Any, **kwargs: Any) -> 'Pyjo.Message.Response.object':
    """::

        res = o('example.com')
        res = o('http://example.com', {'Accept': '*/*'}, b'Hi!')
        res = o('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        res = o('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})

    Perform ``OPTIONS`` request with
    :attr:`Pyjo.UserAgent.Pyjo_UserAgent.options` and return resulting
    :mod:`Pyjo.Message.Response` object.
    """
    return _ua().options(*args, **kwargs).result


def p(*args: Any, **kwargs: Any) -> 'Pyjo.Message.Response.object':
    """::

        res = p('example.com')
        res = p('http://example.com', {'Accept': '*/*'}, b'Hi!')
        res = p('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        res = p('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})

    Perform ``POST`` request with :attr:`Pyjo.UserAgent.Pyjo_UserAgent.post` and
    return resulting :mod:`Pyjo.Message.Response` object.
    """
    return _ua().post(*args, **kwargs).result


# Not in Mojolicious: a regular expression, as qr// of Perl makes it, which re.compile makes long in a one-liner
def q(pattern: str, flags: int = 0) -> 're.Pattern[str]':
    """::

        regex = q(r'/phpinfo\\.php')
        regex = q(r'/php(?P<path>/.*)?')

    Compile a regular expression with :func:`re.compile`, as ``qr//`` does in
    Perl, as the whole path that :mod:`Pyjoyment.Plugin.Mount` mounts an
    application under. ::

        $ python -m Pyjo 'bool(q(r"\\d+").fullmatch("42"))'
    """
    import re

    return re.compile(pattern, flags)


def r(*values: object) -> str:
    """::

        python = r({'data': 'structure'})

    Dump a Python data structure with :func:`Pyjo.Util.dumper`. ::

        $ python -m Pyjo 'r(g("example.com").headers.to_dict())'
    """
    import Pyjo.Util

    return Pyjo.Util.dumper(*values)


def t(*args: Any, **kwargs: Any) -> 'Pyjo.Message.Response.object':
    """::

        res = t('example.com')
        res = t('http://example.com', {'Accept': '*/*'}, b'Hi!')
        res = t('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        res = t('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})

    Perform ``PATCH`` request with :attr:`Pyjo.UserAgent.Pyjo_UserAgent.patch`
    and return resulting :mod:`Pyjo.Message.Response` object.
    """
    return _ua().patch(*args, **kwargs).result


# Not in Mojolicious: characters, as Pyjo.String.Unicode is Mojo::ByteStream for them, where b is for bytes
def u(*parts: object) -> 'Pyjo.String.Unicode.object':
    """::

        stream = u('lalala')

    Turn string into a :mod:`Pyjo.String.Unicode` object. ::

        $ python -m Pyjo 'u(g("mojolicious.org").text).html_unescape().say()'
    """
    import Pyjo.String.Unicode

    return Pyjo.String.Unicode.u(*parts)


# Renamed from Mojolicious: u, as u is for characters, as in Pyjo.String.Unicode
def w(*args: Any, **kwargs: Any) -> 'Pyjo.Message.Response.object':
    """::

        res = w('example.com')
        res = w('http://example.com', {'Accept': '*/*'}, b'Hi!')
        res = w('http://example.com', {'Accept': '*/*'}, form={'a': 'b'})
        res = w('http://example.com', {'Accept': '*/*'}, json={'a': 'b'})

    Perform ``PUT`` request with :attr:`Pyjo.UserAgent.Pyjo_UserAgent.put` and
    return resulting :mod:`Pyjo.Message.Response` object.
    """
    return _ua().put(*args, **kwargs).result


def x(*args: Any) -> 'Pyjo.DOM.object':
    """::

        dom = x('<div>Hello!</div>')

    Turn HTML/XML input into :mod:`Pyjo.DOM` object. ::

        $ python -m Pyjo 'x(f("test.html").slurp()).at("title").text'
    """
    import Pyjo.DOM

    return Pyjo.DOM.new(*args)


# Not in Mojolicious: the builder of Pyjo.JSON.Schema, as z of zod, which imports the module when one of its methods is
# read, so that from Pyjo import * does not import it
class _Builder:
    def __getattr__(self, name: str) -> Any:
        import Pyjo.JSON.Schema

        return getattr(Pyjo.JSON.Schema.z, name)

    def __repr__(self) -> str:
        return 'Pyjo.JSON.Schema.z'


if TYPE_CHECKING:
    z = Pyjo.JSON.Schema.z
else:
    z = _Builder()
    """::

        schema = z.object(name=z.string(), stars=z.int().min(0))

    The builder of :mod:`Pyjo.JSON.Schema`, its class ``z``, after ``z`` of
    zod, whose schemas validate a value, as the JSON of a response. ::

        $ python -m Pyjo 'z.object(port=z.int()).validate(j(f("config.json").slurp()))'
        $ python -m Pyjo 'z.object(id=z.int()).validate(g("api.github.com/repos/pyjoyment/Pyjoyment").json()).is_valid'
    """
