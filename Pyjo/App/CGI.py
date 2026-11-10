"""
Pyjo.App.CGI - CGI application
==============================
::

    from Pyjo.App.CGI import CGI

    app = CGI(script='/usr/lib/cgi-bin/hello.cgi')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.App.CGI

    app = Pyjo.App.CGI.new(script='/usr/lib/cgi-bin/hello.cgi')

    # The programs of a directory, as cgi-bin
    app = Pyjo.App.CGI.new(document_root='/usr/lib/cgi-bin')

    # PHP on php-cgi, with the files of its directory
    app = Pyjo.App.CGI.new(
        command=['php-cgi'], document_root='/var/www', script_extensions=['.php'], static=True
    )

    # Mount it in an application of Pyjoyment
    import Pyjoyment

    pyjoyment = Pyjoyment.new()
    pyjoyment.plugin('Mount', {'/cgi-bin': app})

:mod:`Pyjo.App.CGI` is an application of :mod:`Pyjo` that runs a ``CGI``
program, as :rfc:`3875` describes it, in a process of its own for each
request, which :mod:`Pyjo.IOLoop.ChildProcess` runs, so that a server of :mod:`Pyjo` serves it, a route of
:mod:`Pyjoyment` embeds it, as :mod:`Pyjoyment.Plugin.Mount` does, and
:mod:`Pyjo.Test.Pyjo` tests it.

The environment of the process is the one of ``CGI`` of the request: the part
of the path that a route embeds the application under is ``SCRIPT_NAME``, after
the base path of the request, which a part of the path that does not end with
a slash, as ``/cgi`` of ``/cgix``, cannot be, so that the application is not
found there, the rest of the path is ``PATH_INFO``, ``REQUEST_URI`` is the path
with the query, without the header ``Proxy``, whose ``HTTP_PROXY`` a program
may take for the proxy of its own requests, as with httpoxy, with ``PATH`` of
the process of Pyjoyment, and :attr:`env` adds to them. The program runs in
the directory of its file, and the body of the request goes to its standard
input, each chunk once the one before has been written.

The standard output of the program is its response of ``CGI``, read through
the event loop, as it comes. A response that comes whole, before the program
closes its standard output, is written with its ``Content-Length``. Another one
is written as it comes, each chunk once the one before has been written to the
client, with the chunked transfer encoding when it does not give its
``Content-Length``. What the program writes to its standard error is logged.

A program that does not start or ends before its response is a response
``502``, and one that ends otherwise after the start of the response closes
the connection of the client, as one that is quiet for longer than
:attr:`inactivity_timeout` does, which, until the response starts, the
connection of the client waits for without the inactivity timeout of the
server. The process of a request whose client is gone is killed, with the
processes that it has started, as it runs as the leader of a process group.

The reactor watches the pipes of the process, which it can on POSIX systems,
not on Windows, where the response is ``502``.

Attributes
----------

:mod:`Pyjo.App.CGI` inherits all attributes from :mod:`Pyjo.App` and
implements the following new ones.

See also
--------

:mod:`Pyjoyment`, :mod:`Pyjoyment.Plugin.Mount`, :mod:`Pyjo.App.FastCGI`,
:mod:`Pyjo.IOLoop.ChildProcess`, :mod:`Pyjo.Server.CGI`, https://mojolicious.org.

It has no counterpart in Mojolicious; it is the reverse of
:mod:`Pyjo.Server.CGI`, inspired by ``Mojolicious::Plugin::CGI`` of CPAN.

Classes
-------
"""

import Pyjo.App
import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.IOLoop.ChildProcess
import Pyjo.Message.Response
import Pyjo.Server
import Pyjo.Transaction

import os
import re
import signal
import wsgiref.util

from collections.abc import Sequence
from typing import Any


# Directories of the files of X-Sendfile, or regular expressions of their paths
type Place = str | os.PathLike[str] | re.Pattern[str]
type Sendfile = Place | Sequence[Place]

# The headers of a response by X-Sendfile that the file takes the place of
_SENT = ('content-length', 'x-sendfile')


class Pyjo_App_CGI(Pyjo.App.object):
    """
    :mod:`Pyjo.App.CGI` inherits all methods from :mod:`Pyjo.App` and
    implements the following new ones.
    """

    def __init__(self, attrs: dict[str, Any] | None = None, /, **kwargs: Any) -> None:
        """::

            app = Pyjo.App.CGI.new(script='/usr/lib/cgi-bin/hello.cgi')

        Construct a new :mod:`Pyjo.App.CGI` object.
        """
        self.command: list[str] | None = None
        """::

            command = app.command
            app.command = ['php-cgi']

        Command that runs the script, with its file as the last argument, as an
        interpreter, the script itself otherwise, which has to be executable.
        With it, ``REDIRECT_STATUS`` is ``200``, as Apache gives it to the
        command of ``Action``, without which php-cgi runs no script.
        """

        self.document_root: str | os.PathLike[str] | None = None
        """::

            root = app.document_root
            app.document_root = '/usr/lib/cgi-bin'

        Directory of the scripts, which takes the script of each request from
        its path, as a web server does: the path after the mount, up to its
        first part that is a file of the directory, or that ends with one of
        :attr:`script_extensions`, names the script, whose file is
        ``SCRIPT_FILENAME`` and whose path after the mount is ``SCRIPT_NAME``,
        the rest of the path is ``PATH_INFO``, and a path that ends with a
        slash names ``index`` with the first of :attr:`script_extensions` in
        it, as ``index.php``. A path with ``..``, or that names no file, or no
        script of :attr:`script_extensions`, is not found. With :attr:`script`, a path that names no script of the
        directory is the one of :attr:`script`, as the one entry of an
        application that takes every path, as with ``try_files`` of nginx.
        ``SCRIPT_FILENAME`` of :attr:`env` takes its place.
        """

        self.env: dict[str, str] = {}
        """::

            env = app.env
            app.env = {'PERL5LIB': '/usr/local/lib/perl5'}

        Variables that are added to the environment of ``CGI`` of each
        request, and replace the ones of the same name.
        """

        self.inactivity_timeout: float = 60
        """::

            timeout = app.inactivity_timeout
            app.inactivity_timeout = 300

        Maximum amount of time in seconds the standard output of the program
        can be inactive before the process gets killed, defaults to ``60``.
        Until the response starts, the connection of the client waits for it
        without the inactivity timeout of the server, so that this one gives
        the response ``502`` to a program that takes longer.
        """

        self.nph: bool | None = None
        """::

            boolean = app.nph
            app.nph = True

        The program writes the start line of an HTTP response, in non-parsed
        header mode, as :mod:`Pyjo.Server.CGI` does with its attribute ``nph``,
        which takes the place of the header ``Status``, true by default for a
        script whose file name starts with ``nph-``, as web servers have it.
        """

        self.public_source: bool = False
        """::

            boolean = app.public_source
            app.public_source = True

        The static files of the application that mounts this one, as the
        ``public`` directory of :mod:`Pyjoyment.Static`, may have the scripts of
        :attr:`document_root` or :attr:`script` on purpose, false by default,
        with which :meth:`server` fails, as those static files are served
        before the route of the mount, so their source instead of their output.
        """

        self.script: str | None = None
        """::

            script = app.script
            app.script = '/usr/lib/cgi-bin/hello.cgi'
            app.script = 'index.php'

        Script of the application for every path, with the path after the
        mount as ``PATH_INFO``, or for every path that names no script of
        :attr:`document_root`, in which it is then.
        """

        self.script_extensions: list[str] | None = None
        """::

            extensions = app.script_extensions
            app.script_extensions = ['.php']

        Extensions of the names of the scripts of :attr:`document_root`, every
        file of which is a script without them, as cgi-bin.
        """

        self.sendfile: Sendfile | None = None
        """::

            places = app.sendfile
            app.sendfile = '/var/www/private'
            app.sendfile = ['/var/www/private', '/var/www/media']
            app.sendfile = re.compile(r'/var/www/[^/]+/private/.*')

        Directories of the files that the program may reply with by the header
        ``X-Sendfile``, as Apache and lighttpd take it, with the path of the
        file, absolute or in one of them, or regular expressions of the whole
        path of such a file, once its symbolic links are resolved, as the
        private files that are not in :attr:`document_root`, none by default,
        which passes the header on as it is. A route that embeds the
        application replies then with the file, as the helper ``reply.file`` of
        :mod:`Pyjoyment` does, with the status and the other headers of the
        program, and a file that they do not allow is not found.
        """

        self.static: bool = False
        """::

            boolean = app.static
            app.static = True

        Reply with a file of :attr:`document_root` for a path that names it and
        no script of :attr:`script_extensions`, as ``try_files`` of nginx does,
        as the helper ``reply.file`` of :mod:`Pyjoyment` does, with ranges and
        conditional requests, false by default. A route that embeds the
        application replies with them, as :mod:`Pyjoyment.Plugin.Mount` makes.
        """

        super().__init__(attrs, **kwargs)

    def handler(self, tx: Any) -> None:
        """::

            app.handler(Pyjo.Transaction.HTTP.new())
            app.handler(Pyjoyment.Controller.new())

        Run the program for the request of the transaction, or of the
        controller of a route that embeds the application, and write its
        response.
        """
        if self.script is None and self.document_root is None and 'SCRIPT_FILENAME' not in self.env:
            raise Pyjo.Exception.new('No CGI application')
        config = {
            'extensions': self.script_extensions,
            'inactivity': self.inactivity_timeout,
            'root': os.fspath(self.document_root) if self.document_root is not None else None,
            'script': self.script,
            'sendfile': _places(self.sendfile),
            'static': self.static,
        }
        _Call.run(self, config, tx)

    def server(self, server: Pyjo.Server.object) -> None:
        """::

            app.server(Pyjo.Server.new())

        Fail before the server starts when the static files of the application
        that mounts this one, as the ``public`` directory of
        :mod:`Pyjoyment.Static`, have the scripts of :attr:`document_root` or
        :attr:`script`, unless :attr:`public_source` is true.
        """
        _public(self, server, self.document_root, self.script, self.public_source)


# The scripts of an application in the static files of the application that mounts it, as public of Pyjoyment.Static,
# which serves them as files, with their source, before the route of the mount, as the document root of Laravel and
# Symfony is public too, which the server is told of before it starts; the paths of FastCGI are the ones of its
# application, so only those that are on the same file system are found
def _public(app: Any, server: Any, root: Any, script: str | None, public: bool) -> None:
    # The static files of an application of Pyjoyment, which Pyjo does not import
    paths: list[str] = list(getattr(getattr(server.app, 'static', None), 'paths', None) or [])
    if public or not paths:
        return
    dirs: list[str] = [os.fspath(root)] if root is not None else []
    if script is not None:
        dirs.append(os.path.dirname(os.path.join(dirs[0] if dirs else '', script)))
    for dir in [os.path.realpath(d) for d in dirs]:
        for path in [os.path.realpath(p) for p in paths]:
            if _within(dir, path):
                raise Pyjo.Exception.new(
                    f'Scripts of {type(app).__module__} in {dir} are in the static files of {path}, which would serve '
                    'their source: move them to another directory, as www, whose files static=True serves, '
                    'or set public_source=True'
                )


# Whether a directory is in another one, which is not on another drive of Windows, where commonpath fails
def _within(dir: str, top: str) -> bool:
    try:
        return os.path.commonpath([dir, top]) == top
    except ValueError:
        return False


# A request to an application, whose response of CGI is written as it comes, which a subclass sends and reads
class _Response:
    name = 'CGI'

    # The path of the mount itself, which a server takes for the whole path in SCRIPT_NAME without PATH_INFO
    mount_path = ''

    def __init__(self, app: Any, config: dict[str, Any], tx: Any, c: Any) -> None:
        self.app = app
        self.extensions: list[str] | None = config['extensions']
        self.inactivity: float = config['inactivity']
        self.root: str | None = config['root']
        self.script: str | None = config['script']
        self.sendfile: list[str | re.Pattern[str]] | None = config['sendfile']
        self.static: bool = config['static']
        self.waiting: tuple[str, float] | None = None
        self.c = c
        self.tx = tx
        self.aborted = False
        self.chunked = False
        self.closed = False
        self.done = False
        self.head = bytearray()
        self.headers: list[tuple[str, str]] | None = None
        self.nph = False
        self.offset = 0
        self.parser: Any = None
        self.pending: list[bytes] = []
        self.sent = 0
        self.started = False
        self.stream: Any = None

        # The chunks that wait to be written to the client, after which its connection closes when it is closing
        self.writing = 0
        self.closing = False

    # The request of the transaction, or of the controller of a route that embeds the application
    @classmethod
    def run(cls, app: Any, config: dict[str, Any], tx: Any, *args: Any) -> None:
        c = None
        if not isinstance(tx, Pyjo.Transaction.object):
            c = tx
            tx = c.tx
            if not Pyjo.App._within(c):  # pyright: ignore[reportPrivateUsage]
                return Pyjo.App._not_found(c)  # pyright: ignore[reportPrivateUsage]
            c.render_later()
        cls(app, config, tx, c, *args).start()

    def start(self) -> None:
        self.tx.on('finish', self._finish)
        params = {**Pyjo.App._cgi(self.tx, self.c), **_extra(self.tx)}  # pyright: ignore[reportPrivateUsage]

        # Not the header Proxy, whose HTTP_PROXY an application may take for the proxy of its own requests, as httpoxy
        # (CVE-2016-5385) does, as nginx and Apache leave it out
        params.pop('HTTP_PROXY', None)

        # A file of the directory of the scripts, as try_files of nginx serves it
        root, extensions = self.root, self.extensions
        if (c := self.c) is not None and self.static and root is not None and extensions is not None:
            if (file := _file(root, params['PATH_INFO'], extensions)) is not None:
                self.done = True
                return c.helpers.reply.file(file)

        env = self.app.env

        # The script of the path in the directory of the scripts, or the one script for a path that names none
        if root is not None and 'SCRIPT_FILENAME' not in env:
            if not self._script(params, root):
                return self._not_found()

        else:
            # The one script for every path
            if (script := self.script) is not None and 'SCRIPT_FILENAME' not in env:
                params['SCRIPT_FILENAME'] = _chars(script)
            if not params['PATH_INFO'] and params['SCRIPT_NAME']:
                params['PATH_INFO'] = self.mount_path
        params.update(self._defaults())
        params.update({name: _chars(value) for name, value in env.items()})

        # The connection of the client waits for the response without its inactivity timeout, which the one of the
        # application takes the place of, so that an application that takes longer gives 502
        if (connection := self.tx.connection) is not None and (stream := Pyjo.IOLoop.stream(connection)) is not None:
            self.waiting = (connection, stream.timeout)
            stream.timeout = 0

        self._open(params)

    # The connection of the client, once what has been written to it is
    def _close(self) -> None:
        if (connection := self.tx.connection) is not None and (stream := Pyjo.IOLoop.stream(connection)) is not None:
            stream.close_gracefully()

    # The variables of the environment of the application before the ones of the attribute env
    def _defaults(self) -> dict[str, str]:
        return {}

    # End of the response
    def _end(self) -> None:
        self.done = True
        content = self.tx.res.content
        (content.write_chunk if self.chunked else content.write)(b'')
        self._rendered()
        self._stop()

    def _failed(self, message: str) -> None:
        if self.done:
            return
        self.aborted = True

        # The response has started, so the connection is closed, as the response cannot change, once the chunks that
        # wait have been written
        if self.started:
            self.done = True
            if not self.closed:
                self.app.log.error(message)
                if self.writing:
                    self.closing = True
                else:
                    self._close()
            return self._stop()

        self.done = True
        self._stop()
        self._waited()
        self.app.log.error(message)
        res = self.tx.res
        res.code = 502
        res.headers.content_type = 'text/plain'
        res.body = b'Bad Gateway'
        self._rendered()

    # The end of the transaction, also when the connection of the client is gone before the end of the response
    def _finish(self, *args: Any) -> None:
        self.closed = True
        if not self.done:
            self.aborted = True
        self._stop()

    # The response of CGI of the output that has come
    def _flush(self, ended: bool) -> None:
        if self.headers is None:
            if ended:
                self._failed(f'{self.name} application ended without a response')
            return

        # Whole response
        res = self.tx.res
        if not self.started:
            self.started = True
            self._waited()
            if self._sendfile():
                return
            _status(res, self.headers)
            if ended:
                self.done = True
                res.body = b''.join(self.pending)
                self.pending = []
                self._rendered()
                return self._stop()

            # Response as it comes, with the headers only for a HEAD request
            self.chunked = res.headers.content_length is None and self.tx.req.version == '1.1'
            if self.tx.is_empty:
                return self._end()

        if len(self.pending):
            chunk, self.pending = b''.join(self.pending), []
            content = res.content
            stream = self.stream

            # The next output once the chunk has been written to the client
            def drained(*args: Any) -> None:
                self.writing -= 1
                if self.closing and not self.writing:
                    return self._close()
                if (stream := self.stream) is not None and not self.done:
                    stream.start()

            if stream is not None and not ended:
                stream.stop()
            self.sent += len(chunk)
            self.writing += 1
            (content.write_chunk if self.chunked else content.write)(chunk, drained)
            self._rendered()
        if ended:
            self._end()

    def _not_found(self) -> None:
        self.done = True
        if (c := self.c) is not None:
            return c.helpers.reply.not_found()
        res = self.tx.res
        res.code = 404
        res.headers.content_type = 'text/plain'
        res.body = b'Not Found'
        self.tx.resume()

    # The request to the application, with its parameters
    def _open(self, params: dict[str, str]) -> None:
        raise NotImplementedError('Method "_open" not implemented by subclass')

    def _rendered(self) -> None:
        if (c := self.c) is not None:
            c.rendered()
        else:
            self.tx.resume()

    # The script of the path in the directory of the scripts, as nginx has it with fastcgi_split_path_info and
    # $document_root$fastcgi_script_name, or the one script for a path that names none
    def _script(self, params: dict[str, str], root: str) -> bool:
        extensions = self.extensions or []
        if (script := self.script) is not None and not _names_script(params['PATH_INFO'], extensions):
            params['PATH_INFO'] = f'/{script.lstrip("/")}'
        return _script(params, root, extensions)

    # The file of the header X-Sendfile of the application, which sendfile allows
    def _sendfile(self) -> bool:
        if (c := self.c) is None or not (places := self.sendfile) or (headers := self.headers) is None:
            return False
        if (value := next((value for name, value in headers if name.lower() == 'x-sendfile'), None)) is None:
            return False
        self.done = True
        self._stop()
        if (file := _allowed(places, value)) is None:
            self.app.log.error(f'{self.name} application sent the file "{value}", which sendfile does not allow')
            c.helpers.reply.not_found()
            return True
        _status(self.tx.res, [(name, value) for name, value in headers if name.lower() not in _SENT])
        c.helpers.reply.file(file)
        return True

    # The body of a response of non-parsed header mode, without its transfer encoding
    def _body(self, content: Any, chunk: bytes) -> None:
        if len(chunk):
            self.pending.append(chunk)

    # The HTTP response of non-parsed header mode, whose status takes the place of the header Status, and whose body is
    # the one of its length, of its chunks, or up to the end of the output
    def _nph(self, chunk: bytes) -> None:
        if (parser := self.parser) is None:
            self.parser = parser = Pyjo.Message.Response.new()
            parser.content.unsubscribe('read').on('read', self._body)
            if self.tx.is_empty:
                parser.content.skip_body = True
        parser.parse(chunk)
        if (error := parser.error) is not None:
            return self._failed(f'{self.name} application sent an invalid response: {error["message"]}')
        if self.headers is None and (parser.content.is_parsing_body or parser.is_finished):
            headers = parser.headers
            self.headers = [('Status', f'{parser.code} {parser.message or ""}'.rstrip())] + [
                (name, value) for name in headers.names() for value in headers.every_header(name)
            ]

    # The headers of the response of CGI, and the start of its body
    def _stdout(self, content: bytes) -> None:
        if self.nph:
            return self._nph(content)
        if self.headers is not None:
            if len(content):
                self.pending.append(content)
            return
        self.head += content
        if (m := re.search(rb'\r?\n\r?\n', self.head)) is None:
            return
        head, body = bytes(self.head[: m.start()]), bytes(self.head[m.end() :])
        self.head = bytearray()
        lines = re.split(r'\r?\n', head.decode('latin-1'))
        self.headers = [
            (name.strip(), value.strip()) for name, _, value in (line.partition(':') for line in lines) if name.strip()
        ]
        if len(body):
            self.pending.append(body)

    # The end of the request to the application
    def _stop(self) -> None:
        raise NotImplementedError('Method "_stop" not implemented by subclass')

    # The inactivity timeout of the connection of the client again, once the response starts
    def _waited(self) -> None:
        if (waiting := self.waiting) is not None:
            self.waiting = None
            connection, timeout = waiting
            if (stream := Pyjo.IOLoop.stream(connection)) is not None:
                stream.timeout = timeout


# A request to a program, in a process of its own
class _Call(_Response):
    def __init__(self, app: Pyjo_App_CGI, config: dict[str, Any], tx: Any, c: Any) -> None:
        super().__init__(app, config, tx, c)
        self.child: Pyjo.IOLoop.ChildProcess.object | None = None
        self.command = app.command

    def _closed(self, stream: Any) -> None:
        self.stream = None
        if self.done or self.closed:
            return
        self._flush(True)

    def _defaults(self) -> dict[str, str]:
        defaults = {'PATH': path} if (path := os.environ.get('PATH')) is not None else {}
        if self.command is not None:
            defaults['REDIRECT_STATUS'] = '200'
        return defaults

    def _error(self, stream: Any, err: Any) -> None:
        self._failed(f'CGI application failed: {err}')

    # The standard error of the program
    def _log(self, stream: Any, chunk: bytes) -> None:
        if message := chunk.decode('utf-8', 'replace').rstrip():
            self.app.log.warn(f'CGI application: {message}')

    # The program, or the command that runs the script, in the directory of its file
    def _open(self, params: dict[str, str]) -> None:
        file = params['SCRIPT_FILENAME'].encode('latin-1')
        nph = self.app.nph
        self.nph = os.path.basename(file).startswith(b'nph-') if nph is None else nph
        env = {name.encode('latin-1'): value.encode('latin-1') for name, value in params.items()}
        self.child = child = Pyjo.IOLoop.spawn(
            [*(self.command or []), file], cwd=os.path.dirname(file) or None, detached=True, env=env
        )
        child.on('error', self._unstarted)
        if (stream := child.stdout) is None or (errors := child.stderr) is None:
            return

        # The standard output, the response, and the standard error, which is logged until its end
        self.stream = stream
        stream.timeout = self.inactivity
        stream.on('read', self._read)
        stream.on('close', self._closed)
        stream.on('error', self._error)
        stream.on('timeout', self._timeout)
        errors.on('read', self._log)
        self._write()

    def _read(self, stream: Any, chunk: bytes) -> None:
        if self.done:
            return
        self._stdout(chunk)
        if not self.done:
            self._flush(False)

    # The program of the first parts of the path that are a file of the directory, as cgi-bin, or of the path up to its
    # first part with one of the extensions, which is a file of the directory, as the command runs no other file
    def _script(self, params: dict[str, str], root: str) -> bool:
        if (extensions := self.extensions) is not None:
            if not super()._script(params, root):
                return False
            return _is_script(params['SCRIPT_FILENAME'], extensions) and _program(params, root)
        for path in (params['PATH_INFO'], f'/{self.script.lstrip("/")}' if self.script is not None else None):
            if path is None:
                continue
            parts = (path or '/').split('/')
            if '..' in parts:
                return False
            for end in range(2, len(parts) + 1):
                if _inside(root, os.fsdecode('/'.join(parts[1:end]).encode('latin-1'))) is not None:
                    _split(params, root, parts, end)
                    return True
        return False

    # The end of the request, with the process of a response that has failed, or of a client that is gone, which the
    # end of its output does not end
    def _stop(self) -> None:
        if (stream := self.stream) is not None:
            self.stream = None
            stream.close()
        if (child := self.child) is not None:
            self.child = None
            if (stdin := child.stdin) is not None:
                stdin.close()
            if self.aborted:
                child.kill(signal.SIGKILL)

    def _timeout(self, stream: Any) -> None:
        self._failed('CGI application inactive')

    def _unstarted(self, child: Any, err: Any) -> None:
        self._failed(f"Can't run CGI application: {getattr(err, 'strerror', None) or err}")

    # The body of the request on the standard input, a chunk once the one before has been written, and its end
    def _write(self, *args: Any) -> None:
        if (child := self.child) is None or (stdin := child.stdin) is None:
            return
        chunk = self.tx.req.content.get_body_chunk(self.offset) or b''
        if not len(chunk):
            return stdin.close_gracefully()
        self.offset += len(chunk)
        stdin.write(chunk, self._write)


# A file that one of the directories has, with an absolute path or one in it, or that a regular expression matches,
# once its symbolic links are resolved
def _allowed(places: list[str | re.Pattern[str]], path: str) -> str | None:
    for place in places:
        if isinstance(place, str):
            if (file := _inside(place, path)) is not None:
                return file
        elif os.path.isabs(path) and os.path.isfile(file := os.path.realpath(path)) and place.fullmatch(file):
            return file
    return None


# Characters of the bytes of a string of the system, as the parameters have them
def _chars(value: str) -> str:
    return os.fsencode(value).decode('latin-1')


# The parameters that CGI servers add, which the applications of PHP need
def _extra(tx: Any) -> dict[str, str]:
    req = tx.req
    url = req.url
    uri = url.path.to_abs_str()
    if base := url.base.path.to_str().rstrip('/'):
        uri = base + uri
    if query := url.query.to_str():
        uri += f'?{query}'
    extra = {'GATEWAY_INTERFACE': 'CGI/1.1', 'REQUEST_URI': uri, 'SERVER_SOFTWARE': 'Pyjoyment (Python)'}
    if req.is_secure:
        extra['HTTPS'] = 'on'
    return extra


# A file of the directory for a path that names no script and no directory, as try_files of nginx takes it
def _file(root: str, path: str, extensions: list[str]) -> str | None:
    if not path or path.endswith('/') or _names_script(path, extensions) or '..' in path.split('/'):
        return None
    return _inside(root, os.fsdecode(path.lstrip('/').encode('latin-1')))


# Directories or regular expressions, as a list
def _places(value: Sendfile | None) -> list[str | re.Pattern[str]] | None:
    if value is None:
        return None
    places = [value] if isinstance(value, (str, os.PathLike, re.Pattern)) else list(value)
    return [place if isinstance(place, re.Pattern) else os.fspath(place) for place in places]


# A file in a directory, also once its symbolic links are resolved, so that no link leads out of it
def _inside(directory: str, path: str) -> str | None:
    base = os.path.realpath(directory)
    file = os.path.realpath(os.path.join(base, path))
    if os.path.commonpath([base, file]) != base or not os.path.isfile(file):
        return None
    return file


# A program of the directory of the scripts
def _program(params: dict[str, str], root: str) -> bool:
    return _inside(root, os.fsdecode(params['SCRIPT_FILENAME'].encode('latin-1'))) is not None


def _is_script(part: str, extensions: list[str]) -> bool:
    return any(part.endswith(extension) for extension in extensions)


# A path that names a script, by the extension of one of its parts
def _names_script(path: str, extensions: list[str]) -> bool:
    return any(_is_script(part, extensions) for part in path.split('/'))


# The script of the path in the directory of the scripts, up to its first part with one of the extensions, unless the
# path has ..
def _script(params: dict[str, str], root: str, extensions: list[str]) -> bool:
    parts = (params['PATH_INFO'] or '/').split('/')
    if '..' in parts:
        return False
    end = next((i + 1 for i, part in enumerate(parts) if _is_script(part, extensions)), len(parts))
    _split(params, root, parts, end)
    if end == len(parts) and params['SCRIPT_FILENAME'].endswith('/') and extensions:
        params['SCRIPT_FILENAME'] += f'index{extensions[0]}'
        params['SCRIPT_NAME'] += f'index{extensions[0]}'
    return True


# The script of the first parts of the path, and the rest of the path
def _split(params: dict[str, str], root: str, parts: list[str], end: int) -> None:
    script, rest = '/'.join(parts[:end]), '/'.join(parts[end:])
    root = _chars(root)
    params['SCRIPT_FILENAME'] = root.rstrip('/') + script
    params['SCRIPT_NAME'] += script
    params['PATH_INFO'] = f'/{rest}' if end < len(parts) else ''
    params['DOCUMENT_ROOT'] = root


# The status of a response of CGI from its header Status, or a redirect for a header Location, and its other headers
def _status(res: Any, headers: list[tuple[str, str]]) -> None:
    res.code = 200
    location = False
    for name, value in headers:
        if name.lower() == 'status':
            code, _, message = value.partition(' ')
            res.code = int(code)
            res.message = message or None
            continue
        if name.lower() == 'location':
            location = True
        if not wsgiref.util.is_hop_by_hop(name):
            res.headers.add(name, value)
    if location and not any(name.lower() == 'status' for name, _ in headers):
        res.code = 302


new = Pyjo_App_CGI.new
object = Pyjo_App_CGI
CGI = Pyjo_App_CGI
