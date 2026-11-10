"""
Pyjoyment.Plugin.AccessLog - Access log plugin
==============================================
::

    # Pyjoyment
    app.plugin('AccessLog')

    # Pyjoyment.Lite
    plugin('AccessLog')

    # Lines of JSON, with the client of a header of the gateway, and the errors only
    app.plugin('AccessLog', format='json', client='X-Envoy-External-Address', status=400)

    # A file, with the time of the response at the end of each line
    app.plugin('AccessLog', log='/var/log/myapp/access.log', duration=True)

:mod:`Pyjoyment.Plugin.AccessLog` writes the access log of the application,
as a server of production writes it: one line for each response, with the
client, the request, the status, the size, the referrer and the user agent,
to the standard output by default, as a container has it. ::

    203.0.113.7 - - [06/Nov/2026:09:42:28 +0000] "GET / HTTP/1.1" 200 39676 "-" "Mozilla/5.0 ..."

It sees every response of the application, also of the static files, of the
mounted applications and of the requests that no route takes, as it follows
the transaction from the hook ``after_build_tx``, before the request is
parsed. The line is written once the response has been written, so that it
has the bytes of the body that the server has written, also of a chunked
response, which has no ``Content-Length``, and of one whose client closed the
connection before its end. A request whose client closed the connection before
the application responded is logged with the status ``499``, as nginx logs it,
and a WebSocket with the status ``101`` of its handshake, once the connection
is upgraded. The time of a line of ``combined`` and ``common`` is the one of
the request, in UTC, as of Apache, and the one of a line of JSON the one of
the message of the log, after the response.

A line is written with one write of its own and flushed, so that the lines of
the workers of :mod:`Pyjo.Server.Prefork` and :mod:`Pyjo.Server.Prethread`
on one standard output do not mix, as a write of less than ``PIPE_BUF``,
4096 bytes on Linux, to a pipe is atomic, and a file is locked for it.

The endpoints of :mod:`Pyjoyment.Plugin.Health`, whose probes would fill the
log, are left out by default.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Formats
-------

``combined``
    The combined log format of Apache and nginx, which log analyzers read,
    the default. ::

        203.0.113.7 - - [06/Nov/2026:09:42:28 +0000] "GET /?q=1 HTTP/1.1" 200 39676 "https://example.com/" "curl/8.7.1"

``common``
    The common log format, without the referrer and the user agent. ::

        203.0.113.7 - - [06/Nov/2026:09:42:28 +0000] "GET /?q=1 HTTP/1.1" 200 39676

``json``
    A line of JSON, with the fields of a message of JSON of :mod:`Pyjo.Log`
    and those of the request, ``client``, ``method``, ``path``,
    ``protocol``, ``status``, ``bytes``, ``referrer``, ``user_agent`` and
    ``duration`` in seconds, and ``httpRequest``, which Cloud Logging shows
    as a request, the default with the ``PYJO_LOG_FORMAT`` environment
    variable set to ``json``. ::

        {"time":"2026-11-06T09:42:28.048120Z","level":"info","severity":"INFO","message":"GET /?q=1 200","pid":7,...}

The size is ``-`` for a response without a body, and the other values of
the request that are missing are ``-``, as of Apache, and ``null`` in JSON. A
quote, a backslash and a character that is not printable ASCII, as of a
header that a client made up to forge a line, are escaped as ``\\xhh`` of its
bytes in UTF-8, as nginx escapes them.

Options
-------

:mod:`Pyjoyment.Plugin.AccessLog` supports the following options.

``client`` ::

    app.plugin('AccessLog', client='X-Real-IP')
    app.plugin('AccessLog', client=lambda tx: tx.req.headers.header('Fly-Client-IP'))

    The address of the client, defaults to
    :attr:`Pyjo.Transaction.Pyjo_Transaction.remote_address`, which takes
    ``X-Forwarded-For`` of the trusted proxies with
    :attr:`Pyjo.Server.Pyjo_Server.reverse_proxy`, as the option ``-p`` of
    the servers sets it, the name of a header that a gateway sets, as
    ``X-Envoy-External-Address`` of Istio, whose request without it, as a
    probe of the address of a pod, has the remote address, or a function of
    the transaction.

``duration`` ::

    app.plugin('AccessLog', duration=True)

    Add the time of the response in seconds at the end of a line of
    ``combined`` and ``common``, as the access log of gunicorn has it with
    ``%(L)s``, defaults to false.

``exclude`` ::

    app.plugin('AccessLog', exclude=['/livez', '/readyz', re.compile(r'^/assets/')])
    app.plugin('AccessLog', exclude=lambda tx: tx.req.headers.user_agent == 'kube-probe')

    The paths whose requests are not logged, a path with the paths under it,
    a regular expression of the path, or a function of the transaction,
    defaults to the endpoints of :mod:`Pyjoyment.Plugin.Health`, whose paths
    it takes from the helper ``health.path``. An empty list logs every
    request.

``format`` ::

    app.plugin('AccessLog', format='json')
    app.plugin('AccessLog', format=lambda tx, entry: f'{entry["method"]} {entry["path"]} {entry["status"]}')

    The format of the lines, ``combined``, ``common`` or ``json``, see
    `Formats`_, or a function of the transaction and of a dict with the
    values of the request, ``client``, ``time``, ``method``, ``path``,
    ``protocol``, ``status``, ``bytes``, ``referrer``, ``user_agent`` and
    ``duration``, which returns the line, defaults to ``json`` with
    :attr:`Pyjo.Log.Pyjo_Log.json` of the log and to ``combined``
    otherwise.

``level`` ::

    app.plugin('AccessLog', log=app.log, level='debug')

    The level of the lines in a :mod:`Pyjo.Log` of ``log``, defaults to
    ``info``.

``log`` ::

    app.plugin('AccessLog', log='/var/log/myapp/access.log')
    app.plugin('AccessLog', log=app.log)

    Where the lines go, the standard output by default, the path of a file,
    or a :mod:`Pyjo.Log`, as the log of the application, whose format a line
    gets, as a message of the level of ``level``.

``status`` ::

    app.plugin('AccessLog', status=400)
    app.plugin('AccessLog', status=[404, 499])

    The lowest status that is logged, or the statuses, defaults to all.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious.

Classes
-------
"""

import Pyjo.Date
import Pyjo.Exception
import Pyjo.Log
import Pyjoyment.Plugin

from Pyjo.Util import steady_time

import json
import os
import re
import sys

from collections.abc import Callable, Collection, Iterable
from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    import Pyjo.Transaction
    import Pyjoyment

type _Transaction = 'Pyjo.Transaction.object'
type _Format = str | Callable[[_Transaction, dict[str, Any]], str]
type _Exclude = Iterable[str | re.Pattern[str]] | Callable[[_Transaction], bool]

# The status of a request whose client closed the connection before the response, as nginx logs it
CLIENT_CLOSED = 499

FORMATS = ('combined', 'common', 'json')


class Pyjoyment_Plugin_AccessLog(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.AccessLog` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> None:
        """::

            plugin.register(Pyjoyment.new())
            plugin.register(Pyjoyment.new(), {'format': 'json'})

        Register the hook in :mod:`Pyjoyment` application.
        """
        conf = conf or {}
        target: Pyjo.Log.object | str | os.PathLike[str] | None = conf.get('log')
        format: _Format | None = conf.get('format')
        if isinstance(format, str) and format not in FORMATS:
            raise Pyjo.Exception.new(f'Unknown format "{format}" of the access log, not one of {", ".join(FORMATS)}')

        # A log of its own writes the line as it is, or the JSON of Pyjo.Log
        if isinstance(target, Pyjo.Log.object):
            log = target
            if format is None:
                format = 'json' if log.json else 'combined'
        else:
            if format is None:
                format = 'json' if Pyjo.Log.new().json else 'combined'
            log = Pyjo.Log.new(json=True) if format == 'json' else Pyjo.Log.new(json=False, format=_text)
            if target is not None:
                log.path = os.fspath(target)
        level: str = conf.get('level', 'info')
        message = cast(Callable[..., Any], getattr(log, level))

        def write(*lines: Any) -> None:
            # The standard output of the moment, as a test or a command may replace it
            if target is None:
                log.handle = sys.stdout
            message(*lines)

        client = _client(conf.get('client'))
        duration: bool = bool(conf.get('duration'))
        excluded = _exclude(app, conf.get('exclude'))
        logged = _status(conf.get('status'))

        def after_build_tx(tx: _Transaction, app: 'Pyjoyment.object') -> None:
            time, started = Pyjo.Date.new(), steady_time()
            sent = {'offset': 0, 'body': False}

            def progress(msg: Any, state: str | None = None, offset: int = 0) -> None:
                if state == 'body':
                    sent['offset'], sent['body'] = max(sent['offset'], offset), True

            tx.res.on('progress', progress)

            def finish(tx: _Transaction) -> None:
                req, res = tx.req, tx.res
                # A connection closed before a whole request has nothing to log
                if not req.is_finished and res.code is None:
                    return
                if excluded(tx):
                    return
                status = res.code if res.code is not None else CLIENT_CLOSED
                if not logged(status):
                    return
                entry = _entry(tx, client(tx), time, status, _bytes(tx, sent), steady_time() - started)
                if callable(format):
                    write(format(tx, entry))
                elif format == 'json':
                    write(f'{entry["method"]} {entry["path"]} {status}', *_fields(tx, entry))
                else:
                    write(_line(entry, format == 'combined', duration))

            tx.on('finish', finish)

        app.hook('after_build_tx', after_build_tx)


def _bytes(tx: _Transaction, sent: dict[str, Any]) -> int:
    # The bytes of the body that the server has taken, as the offset of its last chunk, and the whole body of a static
    # response, whose last chunk ends it without another one, as its Content-Length, which is the one of its range
    req, res = tx.req, tx.res
    if req.method == 'HEAD' or res.code is None:
        return 0
    if res.is_finished and not res.content.is_dynamic:
        length = res.headers.content_length
        return int(length) if length is not None and length.isdigit() else res.body_size
    return sent['offset'] if sent['body'] else 0


def _client(option: str | Callable[[_Transaction], str | None] | None) -> Callable[[_Transaction], str | None]:
    if option is None:
        return lambda tx: tx.remote_address
    if callable(option):
        return option
    name = option
    return lambda tx: tx.req.headers.header(name) or tx.remote_address


def _entry(
    tx: _Transaction, client: str | None, time: Pyjo.Date.object, status: int, bytes: int, duration: float
) -> dict[str, Any]:
    req = tx.req
    headers = req.headers
    return {
        'client': client,
        'time': time,
        'method': req.method,
        'path': req.url.to_abs().path_query,
        'protocol': f'HTTP/{req.version}',
        'status': status,
        'bytes': bytes,
        'referrer': headers.referrer,
        'user_agent': headers.user_agent,
        'duration': duration,
    }


def _escape(value: Any) -> str:
    # Apache and nginx escape what would end the field or the line, and what is not printable
    if value is None or value == '':
        return '-'
    return re.sub(r'["\\]|[^\x20-\x7e]', _hex, str(value))


def _exclude(app: 'Pyjoyment.object', option: _Exclude | None) -> Callable[[_Transaction], bool]:
    if callable(option):
        return option
    if option is not None:
        patterns = list(option)
        return lambda tx: _matches(tx.req.url.path.to_route(), patterns)

    # The endpoints of Health, which may be registered after this plugin, once the first request comes
    probes: list[str | re.Pattern[str]] | None = None

    def health(tx: _Transaction) -> bool:
        nonlocal probes
        if probes is None:
            probes = []
            if app.renderer.get_helper('health.path') is not None:
                path = app.build_controller().helpers.health.path
                probes = [p for e in ('livez', 'readyz', 'healthz') if (p := path(e))]
        return _matches(tx.req.url.path.to_route(), probes)

    return health


def _fields(tx: _Transaction, entry: dict[str, Any]) -> list[Pyjo.Log.Field]:
    req = tx.req
    status, bytes, duration = entry['status'], entry['bytes'], entry['duration']
    request: dict[str, Any] = {
        'requestMethod': entry['method'],
        'requestUrl': req.url.to_abs().to_str(),
        'status': status,
        'responseSize': str(bytes),
        'userAgent': entry['user_agent'],
        'remoteIp': entry['client'],
        'referer': entry['referrer'],
        'latency': f'{duration:.6f}s',
        'protocol': entry['protocol'],
    }
    fields = {
        **{name: entry[name] for name in ('client', 'method', 'path', 'protocol', 'status', 'bytes')},
        'referrer': entry['referrer'],
        'user_agent': entry['user_agent'],
        'duration': round(duration, 6),
        'httpRequest': {name: value for name, value in request.items() if value is not None},
    }
    return [Pyjo.Log.Field(name, value, f'{name}={json.dumps(value)}') for name, value in fields.items()]


def _hex(m: re.Match[str]) -> str:
    # The bytes of a header, which are characters of Latin-1, and the UTF-8 of any other character
    char = m[0]
    return ''.join(f'\\x{b:02X}' for b in char.encode('latin-1' if ord(char) < 256 else 'utf-8'))


def _line(entry: dict[str, Any], combined: bool, duration: bool) -> str:
    date: Pyjo.Date.object = entry['time']
    time = date.to_datetime()
    month = Pyjo.Date.MONTHS[time.month - 1]
    request = _escape(f'{entry["method"]} {entry["path"]} {entry["protocol"]}')
    line = (
        f'{_escape(entry["client"])} - - [{time.day:02d}/{month}/{time.year}:{time:%H:%M:%S} +0000] '
        f'"{request}" {entry["status"]} {entry["bytes"] or "-"}'
    )
    if combined:
        line += f' "{_escape(entry["referrer"])}" "{_escape(entry["user_agent"])}"'
    if duration:
        line += f' {entry["duration"]:.3f}'
    return line


def _matches(path: str, patterns: Iterable[str | re.Pattern[str]]) -> bool:
    for pattern in patterns:
        if isinstance(pattern, re.Pattern):
            if pattern.search(path):
                return True
        elif path == pattern or path.startswith(f'{pattern.rstrip("/")}/'):
            return True
    return False


def _status(option: int | Collection[int] | None) -> Callable[[int], bool]:
    if option is None:
        return lambda status: True
    if isinstance(option, int):
        lowest = option
        return lambda status: status >= lowest
    statuses = set(option)
    return lambda status: status in statuses


def _text(time: float, level: str, *lines: Any) -> str:
    # The line as it is, without the time and the level of a message of a log
    return f'{lines[0]}\n'


new = Pyjoyment_Plugin_AccessLog.new
object = Pyjoyment_Plugin_AccessLog
AccessLog = Pyjoyment_Plugin_AccessLog
