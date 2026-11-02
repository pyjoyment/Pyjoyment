"""
Pyjo.Log - Simple logger
========================
::

    from Pyjo.Log import Log

    # Log to STDERR
    log = Log()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Log

    # Log to STDERR
    log = Pyjo.Log.new()

    # Customize log file location and minimum log level
    log = Pyjo.Log.new(path='/var/log/pyjo.log', level='warn')

    # Log messages
    log.trace('Doing stuff')
    log.debug('Not sure what is happening here')
    log.info('FYI: it happened again')
    log.warn('This might be a problem')
    log.error('Garden variety error')
    log.fatal('Boom')

:mod:`Pyjo.Log` is a simple logger for :mod:`Pyjo` projects.

The end of a ``with`` block closes the file that the log opened for
:attr:`~Pyjo_Log.path`.

Events
------

:mod:`Pyjo.Log` inherits all events from :mod:`Pyjo.EventEmitter` and can
emit the following new ones.

message
~~~~~~~
::

    log.on('message', lambda log, level, *lines: ...)

Emitted when a new message gets logged. ::

    log.on('message', lambda log, level, *lines: print(f'{level}: ', *lines, sep=''))

JSON
----

With :attr:`~Pyjo_Log.json`, or the ``PYJO_LOG_FORMAT`` environment variable
set to ``json``, which the option ``--log-format`` of the commands of
:mod:`Pyjoyment.Commands` sets, every message is a line of JSON, with the
fields that log collectors, as
Cloud Logging, Datadog and Elastic, recognize: ``time`` in UTC, as of
:rfc:`3339`, ``level``, ``severity`` with the names of Cloud Logging and
syslog, ``message``, ``pid``, and the fields of the message and its context,
as :class:`Field` objects. A message of several lines, as a traceback, stays
one line of JSON. ::

    {"time":"2026-10-19T08:15:42.123450Z","level":"warn","severity":"WARNING","message":"Disk is 95% full","pid":31841}

The levels ``trace`` and ``debug`` are of the severity ``DEBUG``, ``info`` of
``INFO``, ``warn`` of ``WARNING``, ``error`` of ``ERROR`` and ``fatal`` of
``CRITICAL``.

With :attr:`~Pyjo_Log.plain`, or ``PYJO_LOG_FORMAT`` set to ``plain``, a
message has its level only, without the time and the process, for a log that
adds its own time to each line, as the one of GitHub Actions. ::

    [info] Disk is 95% full

The logging module
------------------

:class:`Pyjo.Log.Handler` is a :class:`logging.Handler` that passes the records
of the standard library's :mod:`logging` to a :mod:`Pyjo.Log`. ::

    import logging

    logging.getLogger().addHandler(Pyjo.Log.Handler(log))
    logging.getLogger().warning('Disk is %d%% full', 95)

The levels of :mod:`logging` are mapped to the closest level of the log:
``CRITICAL`` is ``fatal``, ``ERROR`` is ``error``, ``WARNING`` is ``warn``,
``INFO`` is ``info``, ``DEBUG`` is ``debug``, and a level below ``DEBUG`` is
``trace``.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Log <https://github.com/mojolicious/mojo/blob/v9.52/lib/Mojo/Log.pm>`_
of Mojolicious 9.52.
"""

import Pyjo.EventEmitter
import Pyjo.Exception
import Pyjo.File

import builtins
import datetime
import json
import logging
import os
import sys
import time
import weakref

from collections.abc import Callable, Iterable, Iterator, Mapping
from types import TracebackType
from typing import IO, Any, Self, cast


type Anything = builtins.object

# A callback for formatting log messages, it gets the time, the level and the lines
type Format = Callable[..., str]

# Supported log levels
LEVEL = {'trace': 1, 'debug': 2, 'info': 3, 'warn': 4, 'error': 5, 'fatal': 6}

# The severities of Cloud Logging and syslog, which Datadog recognizes too
SEVERITY = {
    'trace': 'DEBUG',
    'debug': 'DEBUG',
    'info': 'INFO',
    'warn': 'WARNING',
    'error': 'ERROR',
    'fatal': 'CRITICAL',
}

# Systemd magic numbers
MAGIC = {'trace': 7, 'debug': 6, 'info': 5, 'warn': 4, 'error': 3, 'fatal': 2}

# Colors, as Term::ANSIColor has yellow, red and white on red
COLORS = {'warn': '33', 'error': '31', 'fatal': '37;41'}

# A handle that is not set yet, as None is no handle
_UNSET: Any = builtins.object()


class Pyjo_Log(Pyjo.EventEmitter.object):
    """
    :mod:`Pyjo.Log` inherits all methods from :mod:`Pyjo.EventEmitter` and
    implements the following new ones.
    """

    def __init__(
        self,
        *,
        color: bool | None = None,
        format: Format | None = None,
        handle: IO[str] | None = _UNSET,
        history: list[list[Any]] | None = None,
        json: bool | None = None,
        level: str = 'trace',
        max_history_size: int = 10,
        path: str | os.PathLike[str] | None = None,
        plain: bool | None = None,
        short: bool | None = None,
    ) -> None:
        """::

            log = Pyjo.Log.new()
            log = Pyjo.Log.new(level='warn')

        Construct a new :mod:`Pyjo.Log` object and subscribe to the
        ``message`` event with the default logger.
        """
        super().__init__()

        self._color: bool | None = color
        self._json: bool | None = json

        self.history: list[list[Any]] = history if history is not None else []
        """::

            history = log.history
            log.history = [[time.time(), 'debug', 'That went wrong']]

        The last few logged messages.
        """

        self.level = level
        """::

            level = log.level
            log.level = 'debug'

        Active log level, defaults to ``trace``. Available log levels are
        ``trace``, ``debug``, ``info``, ``warn``, ``error`` and ``fatal``, in
        that order.
        """

        self.max_history_size = max_history_size
        """::

            size = log.max_history_size
            log.max_history_size = 5

        Maximum number of logged messages to store in :attr:`history`,
        defaults to ``10``.
        """

        self.path = path
        """::

            path = log.path
            log.path = '/var/log/pyjo.log'

        Log file path used by :attr:`handle`.
        """

        self._plain: bool | None = plain
        self._short: bool | None = short

        self._capturing = False
        self._context: list[Any] = []
        self._format = format
        self._handle = handle
        self._finalizer: weakref.finalize[[], Any] | None = None
        self._parent: Pyjo_Log | None = None

        self.on('message', _message)

    # Not in Mojolicious: a context manager, which closes the file that the log opened for path where the block ends, as
    # PyPy frees the object only when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    @property
    def color(self) -> bool:
        """::

            boolean = log.color
            log.color = boolean

        Colorize log messages with the levels ``warn``, ``error`` and
        ``fatal`` using ANSI escape sequences, defaults to the value of the
        ``PYJO_LOG_COLOR`` environment variable.
        """
        if self._color is None:
            self._color = bool(os.environ.get('PYJO_LOG_COLOR'))
        return self._color

    @color.setter
    def color(self, value: bool) -> None:
        self._color = value

    # Not in Mojolicious: JSON Lines for log collectors
    @property
    def json(self) -> bool:
        """::

            boolean = log.json
            log.json = boolean

        Generate log messages as lines of JSON, see `JSON`_, defaults to true
        when the ``PYJO_LOG_FORMAT`` environment variable is ``json``, and
        false when it is ``text``, ``plain`` or not set. It takes precedence
        over :attr:`plain`, :attr:`short` and :attr:`color`.
        """
        if self._json is None:
            self._json = (os.environ.get('PYJO_LOG_FORMAT') or '').lower() == 'json'
        return self._json

    @json.setter
    def json(self, value: bool) -> None:
        self._json = value

    # Not in Mojolicious: messages without the time and the process, as a log of CI adds its own time
    @property
    def plain(self) -> bool:
        """::

            boolean = log.plain
            log.plain = boolean

        Generate log messages with their level only, without the time and the
        process, as ``[info] Hello``, for a log that adds its own time, as the
        one of GitHub Actions, defaults to true when the ``PYJO_LOG_FORMAT``
        environment variable is ``plain``. It takes precedence over
        :attr:`short` and :attr:`color`.
        """
        if self._plain is None:
            self._plain = (os.environ.get('PYJO_LOG_FORMAT') or '').lower() == 'plain'
        return self._plain

    @plain.setter
    def plain(self, value: bool) -> None:
        self._plain = value

    @property
    def short(self) -> bool:
        """::

            boolean = log.short
            log.short = boolean

        Generate short log messages without a timestamp but with journald log
        level prefix, suitable for systemd environments, defaults to the value
        of the ``PYJO_LOG_SHORT`` environment variable.
        """
        if self._short is None:
            self._short = bool(os.environ.get('PYJO_LOG_SHORT'))
        return self._short

    @short.setter
    def short(self, value: bool) -> None:
        self._short = value

    @property
    def format(self) -> Format:
        """::

            cb = log.format
            log.format = lambda time, level, *lines: ...

        A callback for formatting log messages. ::

            log.format = lambda time, level, *lines: '[2018-11-08 14:20:13.77168] [28320] [info] I ♥ Pyjoyment\\n'
        """
        if self._format is None:
            self._format = (
                _json
                if self.json
                else _plain
                if self.plain
                else _short
                if self.short
                else _color
                if self.color
                else _default
            )
        return self._format

    @format.setter
    def format(self, value: Format) -> None:
        self._format = value

    @property
    def handle(self) -> IO[str] | None:
        """::

            handle = log.handle
            log.handle = io.StringIO()

        Log text stream used by the default ``message`` event, defaults to
        opening :attr:`path` for appending in UTF-8 or :data:`sys.stderr`.
        """
        if self._handle is _UNSET:
            # STDERR, or the file
            path = self.path
            if path is None:
                self._handle = sys.stderr
            else:
                handle = self._handle = Pyjo.File.new(path).open('a', encoding='UTF-8')

                # Not in Mojolicious: the file is closed with the object, as Perl closes it with the last reference
                self._finalizer = weakref.finalize(self, handle.close)
        return self._handle

    @handle.setter
    def handle(self, value: IO[str] | None) -> None:
        self._handle = value

    def _release(self) -> None:
        # The file that the log opened for path, which it opens again when it is used again
        if (finalizer := self._finalizer) is not None:
            self._finalizer = None
            self._handle = _UNSET
            finalizer()

    def append(self, msg: str) -> None:
        """::

            log.append('[2018-11-08 14:20:13.77168] [28320] [info] I ♥ Pyjoyment\\n')

        Append message to :attr:`handle`.
        """
        if (handle := self.handle) is None:
            return
        fd = _fileno(handle)
        _flock(fd, True)
        try:
            handle.write(msg)
            handle.flush()
        except OSError as e:
            error = type(e)(f"Can't write to log: {e.strerror}" if e.strerror else "Can't write to log")
            error.errno = e.errno
            raise error from e
        finally:
            _flock(fd, False)

    def capture(self, level: str | None = None) -> '_Capture':
        """::

            with log.capture() as messages:
                ...
            with log.capture('debug') as messages:
                ...

        Capture log messages until the end of the ``with`` block, useful for
        testing log messages. The messages stay in the returned object after
        the block. ::

            # Test your log messages
            with log.capture('trace') as messages:
                log.fatal('Something very bad happened')
                log.trace('Just some debug information')
            like_ok(str(messages), r'Something very bad happened', 'logs contain fatal message')
            like_ok(messages[-1], r'Just some debug information', 'trace message was last')
        """
        if self._capturing:
            Pyjo.Exception.object.throw('Log messages are already being captured')
        self._capturing = True

        original = self.level
        self.level = level or original
        subscribers = self.subscribers('message')
        self.unsubscribe('message')

        def restore() -> None:
            self.level = original
            self.unsubscribe('message')
            self._capturing = False
            for cb in subscribers:
                self.on('message', cb)

        capture = _Capture(restore)
        messages = capture.messages

        def message(log: Pyjo_Log, level: str, *lines: Any) -> None:
            messages.append(log.format(time.time(), level, *lines))

        self.on('message', message)

        return capture

    # Not in Mojolicious: the release of the file of path, which Perl does in DESTROY, also at the end of a with block
    def close(self) -> None:
        """::

            log.close()

        Close the file that the log opened for :attr:`path`, as the end of a
        ``with`` block does, which it opens again when it is used again.
        """
        self._release()

    def context(self, *context: Any) -> Self:
        """::

            new = log.context('[extra]', '[information]')

        Construct a new child :mod:`Pyjo.Log` object that will include context
        information with every log message. ::

            # Log with context
            log = Pyjo.Log.new()
            context = log.context('[17a60115]')
            context.debug('This is a log message with context information')
            context.info('And another')

        The items of a dict are :class:`Field` objects, which a message of
        JSON has as fields of its own, and the other formats as
        ``name=value``. ::

            # Log with the fields of a context
            context = log.context({'user': 'sri'})
        """
        log = self.new(level=self.level)
        log._parent = self._parent or self
        # Not in Mojolicious: the items of a dict as fields
        log._context = [
            field
            for item in context
            for field in (
                [Field(name, value) for name, value in cast(Mapping[str, Any], item).items()]
                if isinstance(item, Mapping)
                else [item]
            )
        ]
        return log

    def debug(self, *msgs: Any) -> Self:
        """::

            log = log.debug('You screwed up, but that is ok')
            log = log.debug('All', 'cool')
            log = log.debug(lambda: ...)

        Emit ``message`` event and log ``debug`` message.
        """
        return self._log('debug', *msgs) if 2 >= LEVEL[self.level] else self

    def error(self, *msgs: Any) -> Self:
        """::

            log = log.error('You really screwed up this time')
            log = log.error('Wow', 'seriously')
            log = log.error(lambda: ...)

        Emit ``message`` event and log ``error`` message.
        """
        return self._log('error', *msgs) if 5 >= LEVEL[self.level] else self

    def fatal(self, *msgs: Any) -> Self:
        """::

            log = log.fatal('Its over...')
            log = log.fatal('Bye', 'bye')
            log = log.fatal(lambda: ...)

        Emit ``message`` event and log ``fatal`` message.
        """
        return self._log('fatal', *msgs) if 6 >= LEVEL[self.level] else self

    def info(self, *msgs: Any) -> Self:
        """::

            log = log.info('You are bad, but you prolly know already')
            log = log.info('Ok', 'then')
            log = log.info(lambda: ...)

        Emit ``message`` event and log ``info`` message.
        """
        return self._log('info', *msgs) if 3 >= LEVEL[self.level] else self

    def is_level(self, level: str) -> bool:
        """::

            boolean = log.is_level('debug')

        Check active log :attr:`level`. ::

            # True
            log.set(level='debug').is_level('debug')
            log.set(level='debug').is_level('info')

            # False
            log.set(level='info').is_level('debug')
            log.set(level='fatal').is_level('warn')
        """
        return LEVEL[level] >= LEVEL[self.level]

    def trace(self, *msgs: Any) -> Self:
        """::

            log = log.trace('Whatever')
            log = log.trace('Who', 'cares')
            log = log.trace(lambda: ...)

        Emit ``message`` event and log ``trace`` message.
        """
        return self._log('trace', *msgs) if 1 >= LEVEL[self.level] else self

    def warn(self, *msgs: Any) -> Self:
        """::

            log = log.warn('Dont do that Dave...')
            log = log.warn('No', 'really')
            log = log.warn(lambda: ...)

        Emit ``message`` event and log ``warn`` message.
        """
        return self._log('warn', *msgs) if 4 >= LEVEL[self.level] else self

    def _log(self, level: str, *msgs: Any) -> Self:
        if msgs and callable(msgs[0]):
            result: Any = msgs[0]()
            msgs = tuple(cast(Iterable[Any], result)) if isinstance(result, (tuple, list)) else (result,)
        msgs = (*self._context, *msgs)
        (self._parent or self).emit('message', level, *msgs)
        # Unlike Mojolicious: Mojo returns what emit() returns, the parent of a context, where the POD says the log
        return self


# Not in Mojolicious: a field of a JSON message
class Field(str):
    """::

        field = Pyjo.Log.Field('user', 'sri')
        field = Pyjo.Log.Field('request_id', 'abc123', '[abc123]')

    A field of a message of JSON, as a line of a message or of a context, see
    `JSON`_, which the other formats have as its text, ``name=value`` by
    default. A field does not replace the fields that every message of JSON
    has, and a value that JSON has no type for is a string. ::

        # Log with a field
        log.info('Disk is full', Pyjo.Log.Field('disk', '/dev/sda1'))
    """

    name: str
    """::

        name = field.name

    Name of the field.
    """

    value: Any
    """::

        value = field.value

    Value of the field.
    """

    def __new__(cls, name: str, value: Any, text: str | None = None) -> Self:
        field = super().__new__(cls, f'{name}={value}' if text is None else text)
        field.name, field.value = name, value
        return field


class _Capture:
    def __init__(self, restore: Callable[[], None]) -> None:
        self.messages: list[str] = []
        self._restore: Callable[[], None] | None = restore

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        if (restore := self._restore) is not None:
            self._restore = None
            restore()

    # Left out from Mojolicious: the bool overload, an empty capture is false as an empty container is

    def __getitem__(self, index: int) -> str:
        return self.messages[index]

    def __iter__(self) -> Iterator[str]:
        return iter(self.messages)

    def __len__(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        return ''.join(self.messages)


# Not in Mojolicious: a handler of the logging module
class Handler(logging.Handler):
    """::

        handler = Pyjo.Log.Handler(log)
        handler = Pyjo.Log.Handler(log, logging.INFO)

    A :class:`logging.Handler` that formats the records of :mod:`logging` and
    logs them with the given :mod:`Pyjo.Log`, at the closest level.
    """

    def __init__(self, log: Pyjo_Log, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self.log = log

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            log = self.log
            level = _level(record.levelno)
            if log.is_level(level):
                getattr(log, level)(msg)
        except Exception:
            self.handleError(record)


def _color(time: float, level: str, *lines: Any) -> str:
    msg = _default(time, level, *lines)
    return f'\x1b[{COLORS[level]}m{msg}\x1b[0m' if level in COLORS else msg


def _default(time_: float, level: str, *lines: Any) -> str:
    t = time.localtime(time_)
    # The fraction of the seconds is the one of the time as a string
    fraction = str(time_).split('.')[1] if '.' in str(time_) else '0'
    seconds = float(f'{t.tm_sec}.{fraction}')
    timestamp = f'{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d} {t.tm_hour:02d}:{t.tm_min:02d}:{seconds:08.5f}'
    return f'[{timestamp}] [{os.getpid()}] [{level}] {" ".join(map(str, lines))}\n'


def _fileno(handle: IO[str]) -> int | None:
    try:
        return handle.fileno()
    except (AttributeError, OSError, ValueError):
        return None


# Perl ignores what flock returns, as on a handle that cannot be locked
def _flock(fd: int | None, lock: bool) -> None:
    if fd is None or sys.platform == 'win32':
        return
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX if lock else fcntl.LOCK_UN)
    except OSError:
        pass


# The closest level of Pyjo.Log for a level of the logging module
def _json(time_: float, level: str, *lines: Any) -> str:
    timestamp = datetime.datetime.fromtimestamp(time_, datetime.UTC).isoformat(timespec='microseconds')
    record: dict[str, Any] = {
        'time': timestamp.removesuffix('+00:00') + 'Z',
        'level': level,
        'severity': SEVERITY[level],
        'message': ' '.join(str(line) for line in lines if not isinstance(line, Field)),
        'pid': os.getpid(),
    }
    for line in lines:
        if isinstance(line, Field):
            record.setdefault(line.name, line.value)
    return json.dumps(record, ensure_ascii=False, separators=(',', ':'), default=str) + '\n'


def _level(levelno: int) -> str:
    if levelno >= logging.CRITICAL:
        return 'fatal'
    if levelno >= logging.ERROR:
        return 'error'
    if levelno >= logging.WARNING:
        return 'warn'
    if levelno >= logging.INFO:
        return 'info'
    if levelno >= logging.DEBUG:
        return 'debug'
    return 'trace'


def _message(log: Pyjo_Log, level: str, *lines: Any) -> None:
    max = log.max_history_size
    history = log.history
    msg = [time.time(), level, *lines]
    history.append(msg)
    while len(history) > max:
        history.pop(0)

    log.append(log.format(*msg))


def _plain(time: float, level: str, *lines: Any) -> str:
    return f'[{level}] {" ".join(map(str, lines))}\n'


def _short(time: float, level: str, *lines: Any) -> str:
    magic, short = f'<{MAGIC[level]}>', level[0]
    return f'{magic}[{os.getpid()}] [{short}] {" ".join(map(str, lines))}\n'


new = Pyjo_Log.new
object = Pyjo_Log
Log = Pyjo_Log
