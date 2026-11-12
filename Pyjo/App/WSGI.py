"""
Pyjo.App.WSGI - WSGI application
================================
::

    from Pyjo.App.WSGI import WSGI


    def hello(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'Hello World!']


    app = WSGI(app=hello)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.App.WSGI

    app = Pyjo.App.WSGI.new(app=hello)

    # Mount it in an application of Pyjoyment
    import Pyjoyment

    pyjoyment = Pyjoyment.new()
    pyjoyment.plugin('Mount', {'/hello': app})

:mod:`Pyjo.App.WSGI` is an application of :mod:`Pyjo` that runs a ``WSGI``
application, as :pep:`3333` describes it, so that a server of :mod:`Pyjo`
serves it, a route of :mod:`Pyjoyment` embeds it, as
:mod:`Pyjoyment.Plugin.Mount` does, and :mod:`Pyjo.Test.Pyjo` tests it.

The part of the path that a route embeds the application under is
``SCRIPT_NAME``, after the base path of the request, and the rest of the path is
``PATH_INFO``. A route that embeds the application at a part of the path that
does not end with a slash, as ``/php`` of ``/phpx``, which ``SCRIPT_NAME``
cannot be, does not find it. The body of the request is ``wsgi.input``, of the length of
``CONTENT_LENGTH``, also when the request was chunked.

A ``WSGI`` application blocks, and it runs in the event loop, which waits for
it, so that the workers of :mod:`Pyjo.Server.Prefork` and
:mod:`Pyjo.Server.Prethread` serve it at the same time, as for any blocking
operation, with
:attr:`~Pyjo.Server.Daemon.Pyjo_Server_Daemon.max_clients` as low as ``1``.
It is called, and its response iterated and closed, with
:func:`Pyjo.IOLoop.blocking`, so that it sees no running loop of
:mod:`asyncio`, as it would on a ``WSGI`` server, and the ORM of Django and a
blocking request of :mod:`Pyjo.UserAgent` run on
:mod:`Pyjo.Reactor.Asyncio` too. A response that the application has given whole is written with its
``Content-Length``. Another one is written as the application gives it, each
chunk in a tick of the event loop once the one before has been written, and
after an empty chunk, which the application gives while it has none yet, in the
next cycle of the event loop, with the chunked transfer encoding when the
application does not give its ``Content-Length``.

An exception of the application before its response starts is a response
``500``, the exception page of :mod:`Pyjoyment` in a route that embeds it, and
an exception after that is logged and closes the connection.

Attributes
----------

:mod:`Pyjo.App.WSGI` inherits all attributes from :mod:`Pyjo.App` and
implements the following new ones.

See also
--------

:mod:`Pyjoyment`, :mod:`Pyjoyment.Plugin.Mount`, :mod:`Pyjo.Server.WSGI`,
https://mojolicious.org.

It has no counterpart in Mojolicious, it is inspired by
`Mojolicious::Plugin::MountPSGI <https://metacpan.org/pod/Mojolicious::Plugin::MountPSGI>`_ of CPAN; it is the
reverse of :mod:`Pyjo.Server.WSGI`.

Classes
-------
"""

import Pyjo.App
import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Server
import Pyjo.Server.CGI
import Pyjo.Server.Prefork
import Pyjo.Server.Prethread
import Pyjo.Transaction

import contextvars
import io
import sys
import traceback
import weakref
import wsgiref.util

from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast
from wsgiref.types import WSGIApplication, WSGIEnvironment


class Pyjo_App_WSGI(Pyjo.App.object):
    """
    :mod:`Pyjo.App.WSGI` inherits all methods from :mod:`Pyjo.App` and
    implements the following new ones.
    """

    def __init__(self, attrs: dict[str, Any] | None = None, /, **kwargs: Any) -> None:
        """::

            app = Pyjo.App.WSGI.new(app=application)

        Construct a new :mod:`Pyjo.App.WSGI` object.
        """
        self.app: WSGIApplication | None = None
        """::

            application = app.app
            app.app = application

        The ``WSGI`` application to run.
        """

        self._server: weakref.ref[Pyjo.Server.object] | None = None
        super().__init__(attrs, **kwargs)

    def handler(self, tx: Any) -> None:
        """::

            app.handler(Pyjo.Transaction.HTTP.new())
            app.handler(Pyjoyment.Controller.new())

        Run the application for the request of the transaction, or of the
        controller of a route that embeds the application, and write its
        response.
        """
        if (application := self.app) is None:
            raise Pyjo.Exception.new('No WSGI application')
        c = None
        if not isinstance(tx, Pyjo.Transaction.object):
            c = tx
            tx = c.tx
            if not Pyjo.App._within(c):  # pyright: ignore[reportPrivateUsage]
                return Pyjo.App._not_found(c)  # pyright: ignore[reportPrivateUsage]
            c.render_later()
        _Call(self, application, tx, c).start()

    def server(self, server: Pyjo.Server.object) -> None:
        """::

            app.server(Pyjo.Server.Prefork.new())

        Called by the server before it starts, and by
        :mod:`Pyjoyment.Plugin.Mount` for the application that it mounts, so
        that ``wsgi.multithread``, ``wsgi.multiprocess`` and ``wsgi.run_once``
        say how the server runs the application: in the threads of the workers
        of :mod:`Pyjo.Server.Prethread`, in the processes of the workers of
        :mod:`Pyjo.Server.Prefork`, or in a process for each request of
        :mod:`Pyjo.Server.CGI`. Under a ``WSGI`` server, as
        :mod:`Pyjo.Server.WSGI` runs an application of :mod:`Pyjoyment`, they
        are those of the environment of the request, which the ``WSGI``
        server sets.
        """
        self._server = weakref.ref(server)

    # wsgi.multithread, wsgi.multiprocess and wsgi.run_once for the server that runs the application, or of the WSGI
    # server, whose environment of the request Pyjo.Server.WSGI keeps
    def _model(self, tx: Any) -> tuple[bool, bool, bool]:
        if 'wsgi.multiprocess' in (env := tx.req.env):
            return bool(env.get('wsgi.multithread')), bool(env['wsgi.multiprocess']), bool(env.get('wsgi.run_once'))
        server = ref() if (ref := self._server) is not None else None
        if isinstance(server, Pyjo.Server.Prethread.object):
            return server.workers > 1, False, False
        if isinstance(server, Pyjo.Server.Prefork.object):
            return False, server.workers > 1, False
        if isinstance(server, Pyjo.Server.CGI.object):
            return False, True, True
        return False, False, False


# A call of the application, whose response is written as the application gives it
class _Call:
    def __init__(self, app: Pyjo_App_WSGI, application: WSGIApplication, tx: Any, c: Any) -> None:
        self.app = app
        self.application = application
        self.c = c
        self.tx = tx
        self.response = _Response()
        # The context of contextvars of the call, its iteration and its close, which a WSGI server gives them in one
        # thread, where the callbacks of an event loop of asyncio each run in a context of their own, as the iterator of
        # stream_with_context of Flask resets its context variables at its end with the tokens of its start
        self.context = contextvars.copy_context()
        self.busy = False
        self.chunked = False
        self.closed = False
        self.done = False

    def start(self) -> None:
        self.tx.on('finish', self._finish)
        try:
            environ = _environ(self.tx, self.c, self.app._model(self.tx))  # pyright: ignore[reportPrivateUsage]
            self._step(Pyjo.IOLoop.blocking(self.context.run, self.response.start, self.application, environ))
        except Exception as e:
            self._error(e)

    def _close(self) -> None:
        self.done = True
        try:
            Pyjo.IOLoop.blocking(self.context.run, self.response.close)
        except Exception as e:
            self.app.log.error(f'WSGI application failed to close: {_message(e)}')

    # End of the response
    def _end(self) -> None:
        content = self.tx.res.content
        (content.write_chunk if self.chunked else content.write)(b'')
        self._rendered()

    def _error(self, e: BaseException) -> None:
        if not self.done:
            self._close()
        message = _message(e)

        # The response has started, so the connection is closed, as the response cannot change
        if self.response.started:
            self.app.log.error(f'WSGI application failed: {message}')
            if (connection := self.tx.connection) is not None and (
                stream := self._loop().stream(connection)
            ) is not None:
                stream.close()
            return

        # The exception page of Pyjoyment
        if (c := self.c) is not None:
            c.helpers.reply.exception(e)
            return

        self.app.log.error(f'WSGI application failed: {message}')
        res = self.tx.res
        res.code = 500
        res.headers.content_type = 'text/plain'
        res.body = b'Internal Server Error'
        self.tx.resume()

    # The end of the transaction, also when the connection is gone before the end of the response
    def _finish(self, *args: Any) -> None:
        self.closed = True
        if not self.busy and not self.done:
            self._close()

    def _headers(self, chunks: list[bytes] | None) -> None:
        response = self.response
        if response.status is None:
            raise Pyjo.Exception.new('WSGI application did not call start_response')
        res = self.tx.res
        code, _, message = response.status.partition(' ')
        res.code = int(code)
        res.message = message or None
        headers = res.headers
        for name, value in response.headers:
            if not wsgiref.util.is_hop_by_hop(name):
                headers.add(name, value)
        response.started = True

        # Whole response
        if response.iterator is None:
            self.done = True
            res.body = b''.join(chunks or [])
            return self._rendered()

        # Response as the application gives it, with the headers only for a HEAD request
        self.chunked = headers.content_length is None and self.tx.req.version == '1.1'
        if self.tx.is_empty:
            self._close()
            return self._end()
        self._step(chunks)

    # A body without a chunk yet tries again after the events of the next cycle of the event loop
    def _later(self) -> None:
        self.busy = True
        self._loop().timer(0, self._tick)

    # The event loop of the connection, which is the one of the server that runs the application: the singleton, or one of
    # its own, as of the server of a blocking request of a user agent, where a step on the singleton, which waits for the
    # blocking request, would never come
    def _loop(self) -> Pyjo.IOLoop.object:
        if (connection := self.tx.connection) is not None:
            for loop in (Pyjo.IOLoop.singleton, *Pyjo.IOLoop._LOOPS):  # pyright: ignore[reportPrivateUsage]
                if loop.stream(connection) is not None:
                    return loop
        return Pyjo.IOLoop.singleton

    # The next chunks of the body once the chunk before has been written, in the next tick of the event loop, so that the
    # application is not called in the middle of what the server does
    def _next(self, *args: Any) -> None:
        self.busy = True
        self._loop().next_tick(self._tick)

    def _rendered(self) -> None:
        if (c := self.c) is not None:
            c.rendered()
        else:
            self.tx.resume()

    # What the application has given: the chunks of the body, none yet, or the end of the body
    def _step(self, chunks: list[bytes] | None) -> None:
        response = self.response
        if not response.started:
            if response.status is None and response.iterator is not None and chunks is not None and not len(chunks):
                return self._later()
            return self._headers(chunks)

        if chunks is None:
            self.done = True
            return self._end()
        if not len(chunks):
            return self._later()
        self._write(chunks)

    def _tick(self, *args: Any) -> None:
        self.busy = False
        if self.closed:
            if not self.done:
                self._close()
            return
        try:
            self._step(Pyjo.IOLoop.blocking(self.context.run, self.response.next))
        except Exception as e:
            self._error(e)

    def _write(self, chunks: list[bytes]) -> None:
        content = self.tx.res.content
        (content.write_chunk if self.chunked else content.write)(b''.join(chunks), self._next)
        self._rendered()


# What the application gives: the status and the headers of start_response, the chunks of the body, and
# the iterator of the rest of the body
class _Response:
    def __init__(self) -> None:
        self.headers: list[tuple[str, str]] = []
        self.iterator: Iterator[bytes] | None = None
        self.result: Iterable[bytes] | None = None
        self.started = False
        self.status: str | None = None
        self.written: list[bytes] = []

    def close(self) -> None:
        if callable(close := getattr(self.result, 'close', None)):
            close()

    # The chunks of the next chunk of the body, with what the write of start_response has written, none yet for an empty
    # one, as the application may call start_response when its body is iterated, or none at the end of the body
    def next(self) -> list[bytes] | None:
        if (iterator := self.iterator) is None:
            return None
        try:
            chunk = next(iterator)
            chunks = self.written + ([bytes(chunk)] if len(chunk) else [])
        except StopIteration:
            self.iterator = None
            self.close()
            chunks = self.written
        except BaseException:
            self.close()
            raise
        self.written = []
        return chunks if len(chunks) or self.iterator is not None else None

    def start(self, application: WSGIApplication, environ: WSGIEnvironment) -> list[bytes] | None:
        result = self.result = application(environ, self.start_response)

        # A body in a list is whole
        if isinstance(result, list | tuple):
            chunks = [*self.written, *(bytes(chunk) for chunk in cast(list[bytes], result))]
            self.written = []
            self.close()
            return chunks

        try:
            self.iterator = iter(result)
        except BaseException:
            self.close()
            raise
        return self.next()

    def start_response(
        self, status: str, headers: list[tuple[str, str]], exc_info: Any = None
    ) -> Callable[[bytes], Any]:
        if exc_info is not None:
            try:
                if self.started:
                    raise exc_info[1].with_traceback(exc_info[2])
            finally:
                exc_info = None
        elif self.status is not None:
            raise AssertionError('start_response has already been called')
        self.status, self.headers = status, list(headers)
        return self.write

    def write(self, data: bytes) -> None:
        self.written.append(bytes(data))


# The body of the request, which the application reads
class _Input(io.RawIOBase):
    def __init__(self, content: Any) -> None:
        self._content = content
        self._offset = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any, /) -> int:
        chunk = self._content.get_body_chunk(self._offset)
        if not chunk:
            return 0
        size = min(len(buffer), len(chunk))
        buffer[:size] = chunk[:size]
        self._offset += size
        return size


# The environment of PEP 3333 for the request of the transaction: the one of CGI, with the keys of WSGI
def _environ(tx: Any, c: Any, model: tuple[bool, bool, bool]) -> WSGIEnvironment:
    multithread, multiprocess, run_once = model
    environ: WSGIEnvironment = {
        **Pyjo.App._cgi(tx, c),  # pyright: ignore[reportPrivateUsage]
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https' if tx.req.is_secure else 'http',
        'wsgi.input': io.BufferedReader(_Input(tx.req.content)),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': multithread,
        'wsgi.multiprocess': multiprocess,
        'wsgi.run_once': run_once,
        'wsgi.input_terminated': True,
    }
    return environ


# An exception with its traceback, for the log
def _message(e: BaseException) -> str:
    return ''.join(traceback.format_exception(e)).rstrip()


new = Pyjo_App_WSGI.new
object = Pyjo_App_WSGI
WSGI = Pyjo_App_WSGI
