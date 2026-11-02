"""
Pyjo.Server.CGI - CGI server
============================
::

    from Pyjo.Server.CGI import CGI

    cgi = CGI()


    @cgi.unsubscribe('request').on('request')
    def request(cgi, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()


    cgi.run()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Server.CGI

    cgi = Pyjo.Server.CGI.new()


    @cgi.unsubscribe('request').on('request')
    def request(cgi, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()


    cgi.run()

:mod:`Pyjo.Server.CGI` is a simple and portable implementation of
:rfc:`3875`.

The response can come later, as the event loop of :mod:`Pyjo.IOLoop` runs
while the script waits for it, and the script writes it once the application
resumes the transaction. The body of chunks is written without the chunked
transfer encoding, as a script returns no header that relates to the
connection of the client, which the web server makes, except in non-parsed
header mode, whose response goes to the client as it is. The request body is
read with the length of ``CONTENT_LENGTH``, so a chunked request, which has
none, reaches the application without its body.

CGI servers
-----------

* uWSGI with its plugin ``cgi``: a chunked request is not answered.
* :mod:`http.server` with ``--cgi``, up to Python 3.14: it sends the output of
  the script as it is, after a status line ``200`` and headers of its own,
  so the status of the response is lost, and the ``Status`` header and the
  ``Date`` header of the script reach the client.

Events
------

:mod:`Pyjo.Server.CGI` inherits all events from :mod:`Pyjo.Server`.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Server::CGI <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Server/CGI.pm>`_
of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.IOLoop
import Pyjo.Message.Response
import Pyjo.Server

import os
import re
import sys

from typing import Any, BinaryIO, cast


class Pyjo_Server_CGI(Pyjo.Server.object):
    """
    :mod:`Pyjo.Server.CGI` inherits all methods from :mod:`Pyjo.Server` and
    implements the following new ones.
    """

    def __init__(self, *, nph: bool | None = None, **kwargs: Any) -> None:
        """::

            cgi = Pyjo.Server.CGI.new()
            cgi = Pyjo.Server.CGI.new(nph=True)

        Construct a new :mod:`Pyjo.Server.CGI` object.
        """
        super().__init__(**kwargs)

        self.nph = nph
        """::

            boolean = cgi.nph
            cgi.nph = boolean

        Activate non-parsed header mode.
        """

    def run(self) -> int | None:
        """::

            status = cgi.run()

        Run CGI.
        """
        self.app.server(self)
        try:
            return self._run()

        # Not in Mojolicious: the end of the server, as it serves one request
        finally:
            self._server_stopped()

    def _run(self) -> int | None:
        tx = self.build_tx()
        req = tx.req.parse(dict(os.environ))
        tx.local_port = int(port) if (port := os.environ.get('SERVER_PORT')) else None
        tx.remote_address = os.environ.get('REMOTE_ADDR')

        # Request body (may block if we try to read too much)
        stdin = cast(BinaryIO, sys.stdin.buffer)
        length = int(req.headers.content_length or 0)
        while not req.is_finished:
            chunk = stdin.read(length if length and length < 131072 else 131072)
            if not chunk:
                break
            req.parse(chunk)
            length -= len(chunk)
            if length <= 0:
                break

        # Unlike Mojolicious: the response once the application resumes the transaction, as the daemon writes it, as the
        # event loop runs while the script waits, where Mojo writes the default response of a later one
        resumed: list[Any] = []
        tx.on('resume', resumed.append)
        self.emit('request', tx)
        while not resumed:
            Pyjo.IOLoop.one_tick()

        # Response start-line
        res = tx.res.fix_headers()
        if self.nph and not _write(res, 'get_start_line_chunk'):
            return None

        # Response headers
        code = res.code or 404
        msg = res.message or res.default_message()
        if not self.nph:
            res.headers.status = f'{code} {msg}'

        # Unlike Mojolicious: the body of chunks without the chunked transfer encoding, as a script returns no header
        # that relates to the connection of the client (RFC 3875 6.3.4), which the web server writes, where Mojo writes
        # the chunks with their sizes
        decode = None
        if not self.nph and res.content.is_chunked:
            res.headers.remove('Transfer-Encoding')
            decode = _Chunks()
        if not _write(res, 'get_header_chunk'):
            return None

        # Response body
        if not tx.is_empty and not _write(res, 'get_body_chunk', decode):
            return None

        # Finish transaction
        tx.closed()

        return res.code


def _write(res: Pyjo.Message.Response.object, method: str, decode: '_Chunks | None' = None) -> bool:
    # Text written to sys.stdout before goes first
    sys.stdout.flush()
    stdout = cast(BinaryIO, sys.stdout.buffer)
    offset = 0
    while True:
        # Not in Mojolicious: no chunk yet, so the event loop runs once before it tries again, where Mojo sleeps for a
        # second
        chunk: bytes | None = getattr(res, method)(offset)
        if chunk is None:
            Pyjo.IOLoop.one_tick()
            continue

        # End of part
        if not (length := len(chunk)):
            break

        # Make sure we can still write
        offset += length
        if stdout.closed:
            return False
        # Not in Mojolicious: the chunks without their sizes
        if decode is not None and not len(chunk := decode(chunk)):
            continue
        stdout.write(chunk)
        stdout.flush()

    return True


# Not in Mojolicious: the body of the chunks of a dynamic response, without the sizes that write_chunk of Pyjo.Content
# writes before them
class _Chunks:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.left = 0

    def __call__(self, chunk: bytes) -> bytes:
        buffer = self.buffer
        buffer += chunk
        body = bytearray()
        while len(buffer):
            if self.left:
                part = buffer[: self.left]
                body += part
                del buffer[: len(part)]
                self.left -= len(part)
                continue

            # The size of the next chunk, after the end of the one before, and none at the end
            if (m := re.match(rb'(?:\r\n)?([0-9a-fA-F]+)\r\n', buffer)) is None:
                break
            left = int(m[1], 16)
            del buffer[: m.end()]
            if not left:
                buffer.clear()
                break
            self.left = left
        return bytes(body)


new = Pyjo_Server_CGI.new
object = Pyjo_Server_CGI
CGI = Pyjo_Server_CGI
