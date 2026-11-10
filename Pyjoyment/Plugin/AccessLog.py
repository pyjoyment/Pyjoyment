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

    # A file, in a format of LogFormat of Apache, with the time of the response in milliseconds
    app.plugin('AccessLog', log='/var/log/myapp/access.log', format='%h %t "%r" %>s %b %{ms}T')

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
is upgraded. The time of ``%t`` is the one of the request, in UTC, as of
Apache, and the one of a line of JSON the one of the message of the log,
after the response.

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
    the default, ``%h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-Agent}i"``.
    ::

        203.0.113.7 - - [06/Nov/2026:09:42:28 +0000] "GET /?q=1 HTTP/1.1" 200 39676 "https://example.com/" "curl/8.7.1"

``common``
    The common log format, without the referrer and the user agent,
    ``%h %l %u %t "%r" %>s %b``. ::

        203.0.113.7 - - [06/Nov/2026:09:42:28 +0000] "GET /?q=1 HTTP/1.1" 200 39676

``json``
    A line of JSON, with the fields of a message of JSON of :mod:`Pyjo.Log`
    and those of the request, ``client``, ``method``, ``path``,
    ``protocol``, ``status``, ``bytes``, ``referrer``, ``user_agent`` and
    ``duration`` in seconds, and ``httpRequest``, which Cloud Logging shows
    as a request, the default with the ``PYJO_LOG_FORMAT`` environment
    variable set to ``json``. ::

        {"time":"2026-11-06T09:42:28.048120Z","level":"info","severity":"INFO","message":"GET /?q=1 200","pid":7,...}

Another format is a string of the directives of ``LogFormat`` of Apache, as
``Plack::Middleware::AccessLog`` takes it, and the text between them, which
is written as it is. ::

    app.plugin('AccessLog', format='%h %t "%r" %>s %b %D "%{X-Request-ID}i"')

``%%``
    A percent sign.

``%a``, ``%h``
    The client, see ``client``.

``%b``
    The bytes of the body, ``-`` for none.

``%B``
    The bytes of the body, ``0`` for none.

``%{name}C``
    A cookie of the request.

``%D``
    The time of the response in microseconds.

``%H``
    The protocol, as ``HTTP/1.1``.

``%{name}i``
    A header of the request.

``%l``
    ``-``, the remote logname of identd.

``%m``
    The method.

``%{name}o``
    A header of the response.

``%p``
    The port of the server.

``%P``
    The process.

``%q``
    The query, with ``?``, or nothing.

``%r``
    The first line of the request.

``%s``, ``%>s``, ``%<s``
    The status.

``%t``
    The time of the request, as ``[06/Nov/2026:09:42:28 +0000]``.

``%{format}t``
    The time of the request in the format of :meth:`Pyjo.Date.Pyjo_Date.strftime`,
    in UTC, or ``sec``, ``msec``, ``usec``, ``msec_frac`` and ``usec_frac`` of
    the epoch, and of the end of the response with the prefix ``end:``.

``%T``
    The time of the response in seconds.

``%{unit}T``
    The time of the response in ``s``, ``ms`` or ``us``.

``%u``
    The user of Basic authentication.

``%U``
    The path, without the query.

``%v``, ``%V``
    The host of the request.

A directive that is not one of them, as one with the statuses of Apache,
``%400,501{User-Agent}i``, raises an exception when the plugin is
registered. The size is the one of the body that the server has written, with
the framing of a chunked response, as nginx has it. A value that is missing
is ``-``, as of Apache, and ``null`` in JSON. A quote, a backslash and a
character that is not printable ASCII, as of a header that a client made up
to forge a line, are escaped as ``\\xhh`` of its bytes, as nginx escapes them.

A dict of fields is a line of JSON of fields of its own, in the place of the
ones of the request of ``json``, after the fields of a message of JSON of
:mod:`Pyjo.Log`, which a field of the same name does not replace. A field is a
format of ``LogFormat``, whose directive alone is a value of its type, as a
number of ``%>s`` or ``null`` of a header that is missing, and a text with
directives a string, with ``-`` for a value that is missing, or a dict of
fields, a function of the transaction and of the dict of the values of the
request, or a constant. ::

    app.plugin('AccessLog', format={
        'client': '%h',
        'request': '%m %U%q',
        'status': '%>s',
        'bytes': '%B',
        'ms': '%{ms}T',
        'request_id': '%{X-Request-ID}i',
        'http': {'user_agent': '%{User-Agent}i', 'referrer': '%{Referer}i'},
        'service': 'myapp',
    })

    {"time":"...","level":"info","severity":"INFO","message":"GET /?q=1 200","pid":7,"client":"203.0.113.7",
     "request":"GET /?q=1","status":200,"bytes":6,"ms":3,"request_id":null,"http":{"user_agent":"curl/8.7.1",
     "referrer":null},"service":"myapp"}

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
    app.plugin('AccessLog', format='%h %t "%r" %>s %b %{ms}T')
    app.plugin('AccessLog', format={'client': '%h', 'status': '%>s', 'request_id': '%{X-Request-ID}i'})
    app.plugin('AccessLog', format=lambda tx, entry: f'{entry["method"]} {entry["path"]} {entry["status"]}')

    The format of the lines, ``combined``, ``common``, ``json``, one of
    ``LogFormat`` or a dict of the fields of JSON, see `Formats`_, or a
    function of the transaction and of a dict with the values of the
    request, ``client``, ``time``, ``method``, ``path``, ``protocol``,
    ``status``, ``bytes``, ``referrer``, ``user_agent`` and ``duration``,
    which returns the line, defaults to ``json`` with
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

from collections.abc import Callable, Collection, Iterable, Mapping
from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    import Pyjo.Transaction
    import Pyjoyment

type _Transaction = 'Pyjo.Transaction.object'
type _Entry = dict[str, Any]
type _Format = str | Mapping[str, Any] | Callable[[_Transaction, _Entry], str]
type _Item = Callable[[_Transaction, _Entry], Any]
type _Exclude = Iterable[str | re.Pattern[str]] | Callable[[_Transaction], bool]

# The status of a request whose client closed the connection before the response, as nginx logs it
CLIENT_CLOSED = 499

# The formats of LogFormat of Apache by their names, as Plack::Middleware::AccessLog has them
FORMATS = {
    'combined': '%h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-Agent}i"',
    'common': '%h %l %u %t "%r" %>s %b',
}

# A directive of LogFormat, with the modifier of the original or the final status, and its name in braces
DIRECTIVE = re.compile(r'%[<>]?(?:\{([^}]*)\})?([a-zA-Z%])')


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
        if isinstance(format, str) and format != 'json' and format not in FORMATS and '%' not in format:
            names = ', '.join([*FORMATS, 'json'])
            raise Pyjo.Exception.new(
                f'Unknown format "{format}" of the access log, not one of {names} nor of LogFormat'
            )

        # A log of its own writes the line as it is, or the JSON of Pyjo.Log
        if isinstance(target, Pyjo.Log.object):
            log = target
            if format is None:
                format = 'json' if log.json else 'combined'
        else:
            if format is None:
                format = 'json' if Pyjo.Log.new().json else 'combined'
            of_json = format == 'json' or isinstance(format, Mapping)
            log = Pyjo.Log.new(json=True) if of_json else Pyjo.Log.new(json=False, format=_text)
            if target is not None:
                log.path = os.fspath(target)
        level: str = conf.get('level', 'info')
        message = cast(Callable[..., Any], getattr(log, level))

        def write(*lines: Any) -> None:
            # The standard output of the moment, as a test or a command may replace it
            if target is None:
                log.handle = sys.stdout
            message(*lines)

        # A line of text, or the fields of a line of JSON
        line: Callable[[_Transaction, _Entry], str] | None = None
        fields: Callable[[_Transaction, _Entry], list[Pyjo.Log.Field]] = _fields
        if isinstance(format, Mapping):
            fields = _custom(cast(Mapping[str, Any], format))
        elif callable(format):
            line = format
        elif format != 'json':
            line = _compile(FORMATS.get(format, format))
        client = _client(conf.get('client'))
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
                if line is None:
                    write(f'{entry["method"]} {entry["path"]} {status}', *fields(tx, entry))
                else:
                    write(line(tx, entry))

            tx.on('finish', finish)

        app.hook('after_build_tx', after_build_tx)


def _block(letter: str, name: str) -> _Item | None:
    # A directive with a name in braces
    if letter == 'C':
        return lambda tx, entry: cookie.value if (cookie := tx.req.cookie(name)) is not None else None
    if letter == 'i':
        return lambda tx, entry: tx.req.headers.header(name)
    if letter == 'o':
        return lambda tx, entry: tx.res.headers.header(name)
    if letter == 't':
        return _time(name)
    if letter == 'T' and (factor := UNITS.get(name)) is not None:
        return lambda tx, entry: int(entry['duration'] * factor)
    return None


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


def _clf(date: Pyjo.Date.object) -> str:
    # The time of the common log format, in UTC, with the names of the months of HTTP, which no locale changes
    time = date.to_datetime()
    return f'[{time.day:02d}/{Pyjo.Date.MONTHS[time.month - 1]}/{time.year}:{time:%H:%M:%S} +0000]'


def _client(option: str | Callable[[_Transaction], str | None] | None) -> Callable[[_Transaction], str | None]:
    if option is None:
        return lambda tx: tx.remote_address
    if callable(option):
        return option
    name = option
    return lambda tx: tx.req.headers.header(name) or tx.remote_address


def _compile(format: str) -> Callable[[_Transaction, _Entry], str]:
    # The text as it is and the values of the directives, escaped, with "-" for a value that is missing
    parts = _parse(format)

    def line(tx: _Transaction, entry: _Entry) -> str:
        return ''.join(part if isinstance(part, str) else _value(part(tx, entry)) for part in parts)

    return line


def _custom(format: Mapping[str, Any]) -> Callable[[_Transaction, _Entry], list[Pyjo.Log.Field]]:
    # The fields of a line of JSON, of a format of LogFormat each
    fields = {name: _field(spec) for name, spec in format.items()}

    def custom(tx: _Transaction, entry: _Entry) -> list[Pyjo.Log.Field]:
        values = {name: item(tx, entry) for name, item in fields.items()}
        return [Pyjo.Log.Field(name, value, f'{name}={json.dumps(value)}') for name, value in values.items()]

    return custom


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


def _escape(value: str) -> str:
    # Apache and nginx escape what would end the field or the line, and what is not printable
    return re.sub(r'["\\]|[^\x20-\x7e]', _hex, value)


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


def _field(spec: Any) -> _Item:
    # The value of a field of JSON: a directive alone with the type of its value, as a number or null, the text of a
    # format with "-" for a value that is missing, a dict of fields, a function, or a constant
    if isinstance(spec, Mapping):
        fields = {name: _field(value) for name, value in cast(Mapping[str, Any], spec).items()}
        return lambda tx, entry: {name: item(tx, entry) for name, item in fields.items()}
    if callable(spec):
        return cast(_Item, spec)
    if not isinstance(spec, str):
        return lambda tx, entry: spec
    parts = _parse(spec)
    items = [part for part in parts if not isinstance(part, str)]
    if len(items) == 1 and not ''.join(part for part in parts if isinstance(part, str)):
        return items[0]
    if not items:
        text = ''.join(part for part in parts if isinstance(part, str))
        return lambda tx, entry: text

    def item(tx: _Transaction, entry: _Entry) -> str:
        return ''.join(
            part if isinstance(part, str) else '-' if (value := part(tx, entry)) is None else str(value)
            for part in parts
        )

    return item


def _hex(m: re.Match[str]) -> str:
    # The bytes of a header, which are characters of Latin-1, and the UTF-8 of any other character
    char = m[0]
    return ''.join(f'\\x{b:02X}' for b in char.encode('latin-1' if ord(char) < 256 else 'utf-8'))


def _matches(path: str, patterns: Iterable[str | re.Pattern[str]]) -> bool:
    for pattern in patterns:
        if isinstance(pattern, re.Pattern):
            if pattern.search(path):
                return True
        elif path == pattern or path.startswith(f'{pattern.rstrip("/")}/'):
            return True
    return False


def _time(spec: str) -> _Item | None:
    # The time of the request, or of the end of the response, in the format of strftime or as the epoch
    end = spec.startswith('end:')
    spec = spec.removeprefix('begin:').removeprefix('end:')
    epochs: dict[str, Callable[[float], Any]] = {
        'sec': lambda epoch: int(epoch),
        'msec': lambda epoch: int(epoch * 1000),
        'usec': lambda epoch: int(epoch * 1_000_000),
        'msec_frac': lambda epoch: f'{int(epoch * 1000) % 1000:03d}',
        'usec_frac': lambda epoch: f'{int(epoch * 1_000_000) % 1_000_000:06d}',
    }

    def item(tx: _Transaction, entry: _Entry) -> Any:
        epoch = float(entry['time'].epoch or 0) + (entry['duration'] if end else 0)
        if (cb := epochs.get(spec)) is not None:
            return cb(epoch)
        return Pyjo.Date.new(epoch).strftime(spec)

    return item


def _parse(format: str) -> list[str | _Item]:
    # The text between the directives and the directives of a format of LogFormat
    parts: list[str | _Item] = []
    position = 0
    texts: list[str] = []
    for m in DIRECTIVE.finditer(format):
        texts.append(format[position : m.start()])
        parts.append(texts[-1])
        position = m.end()
        name, letter = m[1], m[2]
        if letter == '%' and name is None:
            parts.append('%')
        elif (item := DIRECTIVES.get(letter) if name is None else _block(letter, name)) is not None:
            parts.append(item)
        else:
            raise Pyjo.Exception.new(f'Unknown directive "{m[0]}" of the access log')
    texts.append(format[position:])
    parts.append(texts[-1])
    if any('%' in text for text in texts):
        raise Pyjo.Exception.new(f'Unknown directive of the access log in "{format}"')
    return [part for part in parts if part != '']


def _status(option: int | Collection[int] | None) -> Callable[[int], bool]:
    if option is None:
        return lambda status: True
    if isinstance(option, int):
        lowest = option
        return lambda status: status >= lowest
    statuses = set(option)
    return lambda status: status in statuses


def _user(tx: _Transaction) -> str | None:
    # The user of Basic authentication, which the request has as the user information of its base URL
    info = tx.req.url.base.userinfo
    return info.split(':', 1)[0] if info else None


def _value(value: Any) -> str:
    return '-' if value is None else _escape(str(value))


def _text(time: float, level: str, *lines: Any) -> str:
    # The line as it is, without the time and the level of a message of a log
    return f'{lines[0]}\n'


# The directives of LogFormat of Apache without a name
DIRECTIVES: dict[str, _Item] = {
    'a': lambda tx, entry: entry['client'],
    'b': lambda tx, entry: entry['bytes'] or None,
    'B': lambda tx, entry: entry['bytes'],
    'D': lambda tx, entry: int(entry['duration'] * 1_000_000),
    'h': lambda tx, entry: entry['client'],
    'H': lambda tx, entry: entry['protocol'],
    'l': lambda tx, entry: None,
    'm': lambda tx, entry: entry['method'],
    'p': lambda tx, entry: tx.local_port,
    'P': lambda tx, entry: os.getpid(),
    'q': lambda tx, entry: f'?{query}' if (query := tx.req.url.query.to_str()) else '',
    'r': lambda tx, entry: f'{entry["method"]} {entry["path"]} {entry["protocol"]}',
    's': lambda tx, entry: entry['status'],
    't': lambda tx, entry: _clf(entry['time']),
    'T': lambda tx, entry: int(entry['duration']),
    'u': lambda tx, entry: _user(tx),
    'U': lambda tx, entry: tx.req.url.to_abs().path.to_str(),
    'v': lambda tx, entry: tx.req.url.to_abs().host,
    'V': lambda tx, entry: tx.req.url.to_abs().host,
}

# The units of the time of the response of %{unit}T
UNITS = {'s': 1, 'ms': 1000, 'us': 1_000_000}

new = Pyjoyment_Plugin_AccessLog.new
object = Pyjoyment_Plugin_AccessLog
AccessLog = Pyjoyment_Plugin_AccessLog
