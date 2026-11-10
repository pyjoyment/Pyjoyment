import Pyjo.Exception
import Pyjo.Log

from Pyjo.File import path, tempdir
from Pyjo.Test import *
from Pyjo.Util import decode

import contextlib
import datetime
import io
import json
import os
import time
import zoneinfo


def eval_(cb):
    try:
        cb()
    except Exception as e:
        return e


dir = tempdir()
path_ = dir.child('test.log')

with subtest('Logging to file'):
    log = Pyjo.Log.new(level='error', path=path_)
    log.error('Works')
    log.fatal('I ♥ Mojolicious')
    log.error(lambda: 'This too')
    log.debug('Does not work')
    log.debug(lambda: ('And this', 'too'))
    del log
    content = decode('UTF-8', path(path_).slurp())
    like_ok(content, r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{5}] \[\d+\] \[error\] Works', 'right error message')
    like_ok(content, r'\[.*\] \[\d+\] \[fatal\] I ♥ Mojolicious', 'right fatal message')
    like_ok(content, r'\[.*\] \[\d+\] \[error\] This too', 'right error message')
    unlike_ok(content, r'\[.*\] \[\d+\] \[debug\] Does not work', 'no debug message')
    unlike_ok(content, r'\[.*\] \[\d+\] \[debug\] And this too\n', 'right debug message')

# Not in Mojolicious: the files of a period of a pattern of path
with subtest('Files of a period'):
    now = [time.struct_time((2026, 11, 10, 23, 59, 59, 1, 314, 0))]
    strftime = time.strftime
    time.strftime = lambda format, t=None: strftime(format, now[0] if t is None else t)
    try:
        log = Pyjo.Log.new(path=dir.child('%Y-%m-%d.log').to_str())
        log.error('First day')
        first = log.handle
        log.error('First day again')
        ok(log.handle is first, 'same file')
        now[0] = time.struct_time((2026, 11, 11, 0, 0, 0, 2, 315, 0))
        log.error('Second day')
        ok(log.handle is not first, 'new file')
        ok(first.closed, 'file of the first day closed')
        log.close()
        log.error('Second day after close')
        log.close()
        is_ok(decode('UTF-8', dir.child('2026-11-10.log').slurp()).count('First day'), 2, 'messages of the first day')
        content = decode('UTF-8', dir.child('2026-11-11.log').slurp())
        like_ok(
            content, r'\[error\] Second day\r?\n.*\[error\] Second day after close\r?\n$', 'messages of the second day'
        )
        unlike_ok(content, r'First day', 'no messages of the first day')

        log = Pyjo.Log.new(path=dir.child('100%%-%Y.log').to_str())
        log.error('Percent')
        log.close()
        like_ok(decode('UTF-8', dir.child('100%-2026.log').slurp()), r'Percent', 'percent sign')
    finally:
        time.strftime = strftime

    if not hasattr(time, 'tzset'):
        skip('time.tzset is not on Windows', 1)
    else:
        tz = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()
        try:
            log = Pyjo.Log.new(path=dir.child('tz-%z.log').to_str())
            log.error('UTC')
            log.close()
            like_ok(decode('UTF-8', dir.child('tz-+0000.log').slurp()), r'UTC', 'TZ of UTC')
        finally:
            if tz is None:
                del os.environ['TZ']
            else:
                os.environ['TZ'] = tz
            time.tzset()

    log = Pyjo.Log.new(path=dir.child('utc-%z.log').to_str(), tz='UTC')
    log.error('UTC of tz')
    log.close()
    like_ok(decode('UTF-8', dir.child('utc-+0000.log').slurp()), r'UTC of tz', 'tz of UTC')
    log = Pyjo.Log.new(path=dir.child('offset-%z.log').to_str(), tz=datetime.timezone(datetime.timedelta(hours=2)))
    log.error('Offset')
    log.close()
    like_ok(decode('UTF-8', dir.child('offset-+0200.log').slurp()), r'Offset', 'tz of tzinfo')
    try:
        zone = zoneinfo.ZoneInfo('Asia/Kolkata')
    except zoneinfo.ZoneInfoNotFoundError:
        skip('no time zone database, as on Windows without tzdata', 1)
    else:
        log = Pyjo.Log.new(path=dir.child('kolkata-%z.log').to_str(), tz='Asia/Kolkata')
        log.error('Kolkata')
        log.close()
        like_ok(decode('UTF-8', dir.child('kolkata-+0530.log').slurp()), r'Kolkata', 'tz of a name')
    throws_ok(
        lambda: Pyjo.Log.new(path=dir.child('%Y.log').to_str(), tz='Nowhere/Nothing').error('x'),
        zoneinfo.ZoneInfoNotFoundError,
        'unknown time zone',
    )

# Not in Mojolicious: the time of the messages in a time zone
with subtest('Time zone'):
    log = Pyjo.Log.new(tz='UTC', color=False, json=False, plain=False, short=False)
    like_ok(log.format(1760861742.12345, 'info', 'x'), r'^\[2025-10-19 08:15:42\.12345\] ', 'default format in UTC')
    log.tz = datetime.timezone(datetime.timedelta(hours=2))
    like_ok(log.format(1760861742.12345, 'info', 'x'), r'^\[2025-10-19 10:15:42\.12345\] ', 'format again')
    log = Pyjo.Log.new(tz='UTC', color=True)
    like_ok(log.format(1760861742.12345, 'info', 'x'), r'\[2025-10-19 08:15:42\.12345\] ', 'color in UTC')
    log = Pyjo.Log.new(json=True)
    is_ok(json.loads(log.format(1760861742.12345, 'info', 'x'))['time'], '2025-10-19T08:15:42.123450Z', 'JSON in UTC')
    log.tz = datetime.timezone(datetime.timedelta(hours=-3, minutes=-30))
    is_ok(json.loads(log.format(1760861742.12345, 'info', 'x'))['time'], '2025-10-19T04:45:42.123450-03:30', 'offset')
    log.tz = 'UTC'
    is_ok(json.loads(log.format(1760861742.12345, 'info', 'x'))['time'], '2025-10-19T08:15:42.123450Z', 'JSON of tz')
    log = Pyjo.Log.new(format=lambda time, level, *lines: 'own\n')
    log.tz = 'UTC'
    is_ok(log.format(0, 'info', 'x'), 'own\n', 'format of its own kept')

with subtest('Logging to STDERR'):
    log = Pyjo.Log.new(level='error', path=path_)
    with contextlib.redirect_stderr(io.StringIO()) as handle:
        log = Pyjo.Log.new()
        log.error('Just works')
        log.fatal('I ♥ Mojolicious')
        log.debug('Works too')
        log.debug(lambda: ('And this', 'too'))
    content = handle.getvalue()
    like_ok(content, r'\[.*\] \[error\] Just works\n', 'right error message')
    like_ok(content, r'\[.*\] \[fatal\] I ♥ Mojolicious\n', 'right fatal message')
    like_ok(content, r'\[.*\] \[debug\] Works too\n', 'right debug message')
    like_ok(content, r'\[.*\] \[debug\] And this too\n', 'right debug message')

with subtest('Formatting'):
    log = Pyjo.Log.new()
    like_ok(log.format(time.time(), 'debug', 'Test 123'), r'^\[.*\] \[debug\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'debug', 'Test', '1', '2', '3'), r'^\[.*\] \[debug\] Test 1 2 3\n$', 'right format')
    like_ok(
        log.format(time.time(), 'error', 'I ♥ Mojolicious'), r'^\[.*\] \[error\] I ♥ Mojolicious\n$', 'right format'
    )
    like_ok(
        log.format(int(time.time()), 'error', 'I ♥ Mojolicious'),
        r'^\[.*\] \[error\] I ♥ Mojolicious\n$',
        'right format',
    )
    log.format = lambda time, level, *lines: ':'.join(map(str, (level, time, *lines)))
    like_ok(log.format(time.time(), 'debug', 'Test', '1', '2', '3'), r'^debug:[0-9.]+:Test:1:2:3$', 'right format')

with subtest('Short log messages (systemd)'):
    log = Pyjo.Log.new()
    ok(not log.short, 'long messages')
    like_ok(log.format(time.time(), 'debug', 'Test 123'), r'^\[.*\] \[debug\] Test 123\n$', 'right format')
    os.environ['PYJO_LOG_SHORT'] = '1'
    log = Pyjo.Log.new()
    ok(log.short, 'short messages')
    log = Pyjo.Log.new(short=True)
    ok(log.short, 'short messages')
    like_ok(log.format(time.time(), 'trace', 'Test 123'), r'^<7>\[\d+\] \[t\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'debug', 'Test 123'), r'^<6>\[\d+\] \[d\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'info', 'Test 123'), r'^<5>\[\d+\] \[i\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'warn', 'Test 123'), r'^<4>\[\d+\] \[w\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'error', 'Test 123'), r'^<3>\[\d+\] \[e\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'fatal', 'Test 123'), r'^<2>\[\d+\] \[f\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'debug', 'Test', '1', '2', '3'), r'^<6>\[\d+\] \[d\] Test 1 2 3\n$', 'right format')
    del os.environ['PYJO_LOG_SHORT']

with subtest('Colorized log messages'):
    log = Pyjo.Log.new()
    ok(not log.color, 'plain messages')
    like_ok(log.format(time.time(), 'debug', 'Test 123'), r'^\[.*\] \[debug\] Test 123\n$', 'right format')
    os.environ['PYJO_LOG_COLOR'] = '1'
    log = Pyjo.Log.new()
    ok(log.color, 'colored messages')
    log = Pyjo.Log.new(color=True)
    ok(log.color, 'colored messages')
    like_ok(log.format(time.time(), 'debug', 'Test 123'), r'^\[.+\] \[\d+\] \[debug\] Test 123\n$', 'right format')
    like_ok(log.format(time.time(), 'info', 'Test 123'), r'^\[.+\] \[\d+\] \[info\] Test 123\n$', 'right format')
    like_ok(
        log.format(time.time(), 'warn', 'Test 123'),
        r'^\x1b\[33m\[.+\] \[\d+\] \[warn\] Test 123\n\x1b\[0m$',
        'right format',
    )
    like_ok(
        log.format(time.time(), 'error', 'Test 123'),
        r'^\x1b\[31m\[.+\] \[\d+\] \[error\] Test 123\n\x1b\[0m$',
        'right format',
    )
    like_ok(
        log.format(time.time(), 'fatal', 'Test 123'),
        r'^\x1b\[37;41m\[.+\] \[\d+\] \[fatal\] Test 123\n\x1b\[0m$',
        'right format',
    )
    like_ok(
        log.format(1613484767, 'error', 'Test', '1', '2', '3'),
        r'^\x1b\[31m\[.+\] \[\d+\] \[error\] Test 1 2 3\n\x1b\[0m$',
        'right format',
    )
    del os.environ['PYJO_LOG_COLOR']

# Not in Mojolicious: messages without the time and the process, as a log of CI adds its own time
with subtest('Plain log messages'):
    log = Pyjo.Log.new()
    ok(not log.plain, 'time and process')
    os.environ['PYJO_LOG_FORMAT'] = 'plain'
    log = Pyjo.Log.new()
    ok(log.plain, 'plain of the environment')
    ok(not log.json, 'not JSON')
    is_ok(log.format(time.time(), 'info', 'Test 123'), '[info] Test 123\n', 'right format')
    is_ok(log.format(time.time(), 'debug', 'Test', '1', '2', '3'), '[debug] Test 1 2 3\n', 'right format of lines')
    del os.environ['PYJO_LOG_FORMAT']
    log = Pyjo.Log.new(plain=True, short=True, color=True)
    is_ok(log.format(time.time(), 'error', 'Test 123'), '[error] Test 123\n', 'before short and color')
    log = Pyjo.Log.new(plain=True, json=True)
    like_ok(log.format(time.time(), 'info', 'Test 123'), r'^\{"time":', 'JSON before plain')
    log = Pyjo.Log.new(plain=True)
    context = log.context(Pyjo.Log.Field('request_id', 'abc', '[abc]'))
    buffer = io.StringIO()
    log.handle = buffer
    context.info('Hello')
    is_ok(buffer.getvalue(), '[info] [abc] Hello\n', 'with the context')

# Not in Mojolicious: JSON Lines with the fields that log collectors recognize, as Cloud Logging, Datadog and Elastic
with subtest('JSON log messages'):
    log = Pyjo.Log.new()
    ok(not log.json, 'text messages')
    os.environ['PYJO_LOG_FORMAT'] = 'json'
    log = Pyjo.Log.new()
    ok(log.json, 'JSON messages')
    os.environ['PYJO_LOG_FORMAT'] = 'JSON'
    ok(Pyjo.Log.new().json, 'JSON messages')
    os.environ['PYJO_LOG_FORMAT'] = 'text'
    ok(not Pyjo.Log.new().json, 'text messages')
    del os.environ['PYJO_LOG_FORMAT']
    log = Pyjo.Log.new(json=True, short=True, color=True)
    ok(log.json, 'JSON messages')
    msg = log.format(1760861742.12345, 'warn', 'Test', 1, '2')
    like_ok(msg, r'^\{.*\}\n$', 'one line')
    record = json.loads(msg)
    is_deeply_ok(list(record), ['time', 'level', 'severity', 'message', 'pid'], 'right fields in order')
    is_ok(record['time'], '2025-10-19T08:15:42.123450Z', 'time in UTC')
    is_ok(record['level'], 'warn', 'level')
    is_ok(record['severity'], 'WARNING', 'severity')
    is_ok(record['message'], 'Test 1 2', 'message')
    is_ok(record['pid'], os.getpid(), 'pid')
    severities = {level: json.loads(log.format(0, level, 'Test'))['severity'] for level in Pyjo.Log.LEVEL}
    is_deeply_ok(
        severities,
        {
            'trace': 'DEBUG',
            'debug': 'DEBUG',
            'info': 'INFO',
            'warn': 'WARNING',
            'error': 'ERROR',
            'fatal': 'CRITICAL',
        },
        'severities',
    )
    msg = log.format(0, 'error', 'I ♥ Pyjoyment\nTraceback "/"')
    is_ok(msg.count('\n'), 1, 'multiple lines in one line')
    like_ok(msg, r'"message":"I ♥ Pyjoyment\\nTraceback \\"/\\""', 'characters and escapes')
    is_ok(json.loads(log.format(0, 'info', object))['message'], str(object), 'stringified')

    with contextlib.redirect_stderr(io.StringIO()) as handle:
        log = Pyjo.Log.new(json=True)
        log.info('Just works')
    is_ok(json.loads(handle.getvalue())['message'], 'Just works', 'logged')

with subtest('Events'):
    log = Pyjo.Log.new(level='trace')
    msgs = []
    log.unsubscribe('message').on('message', lambda log, level, *lines: msgs.extend([level, *lines]))
    log.trace('Test', 1, 2, 3)
    is_deeply_ok(msgs, ['trace', 'Test', 1, 2, 3], 'right message')
    msgs.clear()
    log.debug('Test', 1, 2, 3)
    is_deeply_ok(msgs, ['debug', 'Test', 1, 2, 3], 'right message')
    msgs.clear()
    log.info('Test', 1, 2, 3)
    is_deeply_ok(msgs, ['info', 'Test', 1, 2, 3], 'right message')
    msgs.clear()
    log.warn('Test', 1, 2, 3)
    is_deeply_ok(msgs, ['warn', 'Test', 1, 2, 3], 'right message')
    msgs.clear()
    log.error('Test', 1, 2, 3)
    is_deeply_ok(msgs, ['error', 'Test', 1, 2, 3], 'right message')
    msgs.clear()
    log.fatal('Test', 1, 2, 3)
    is_deeply_ok(msgs, ['fatal', 'Test', 1, 2, 3], 'right message')

with subtest('History'):
    with contextlib.redirect_stderr(io.StringIO()) as handle:
        log = Pyjo.Log.new().set(max_history_size=2).set(level='info')
        log.error('First')
        log.fatal('Second')
        log.debug('Third')
        log.info('Fourth', 'Fifth')
        history = log.history
    content = handle.getvalue()
    like_ok(
        content,
        rf'\[\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}\.\d{{5}}\] \[{os.getpid()}\] \[error\] First\n',
        'right error message',
    )
    like_ok(content, r'\[.*\] \[info\] Fourth Fifth\n', 'right info message')
    unlike_ok(content, r'debug', 'no debug message')
    like_ok(str(history[0][0]), r'^[0-9.]+$', 'right epoch time')
    is_ok(history[0][1], 'fatal', 'right level')
    is_ok(history[0][2], 'Second', 'right message')
    is_ok(history[1][1], 'info', 'right level')
    is_ok(history[1][2], 'Fourth', 'right message')
    is_ok(history[1][3], 'Fifth', 'right message')
    is_ok(len(history), 2, 'no more messages')

with subtest('Capturing'):
    log = Pyjo.Log.new()
    is_ok(log.level, 'trace', 'rigth level')

    with log.capture() as logs:
        is_ok(log.level, 'trace', 'rigth level')
        is_ok(str(logs), '', 'empty log')
        is_ok(len(logs), 0, 'empty log')
    is_ok(log.level, 'trace', 'rigth level')

    with log.capture('info') as logs:
        is_ok(log.level, 'info', 'rigth level')
    is_ok(log.level, 'trace', 'rigth level')

    with log.capture() as logs:
        log.trace('First')
        log.debug('Second')
        log.fatal('Third')
        like_ok(str(logs), r'\[trace\].+First\n.+\[debug\].+Second\n.+\[fatal\].+Third\n', 'right messages')
        like_ok(logs[0], r'First', 'right message')
        like_ok(logs[1], r'Second', 'right message')
        like_ok(logs[2], r'Third', 'right message')
        is_ok(len(logs), 3, 'no more messages')

    with log.capture('info') as logs:
        log.trace('First')
        log.debug('Second')
        log.fatal('Third')
        unlike_ok(str(logs), r'First', 'no trace messages')
        unlike_ok(str(logs), r'Second', 'no debug messages')
        like_ok(str(logs), r'.+Third\n', 'right message')
        like_ok(logs[0], r'Third', 'right message')
        is_ok(len(logs), 1, 'no more messages')

    log = Pyjo.Log.new(short=True)
    with log.capture() as logs:
        log.trace('First')
        log.debug('Second')
        log.fatal('Third')
        like_ok(str(logs), r'\[t\].+First\n.+\[d\].+Second\n.+\[f\].+Third\n', 'right messages')

    with log.capture() as logs:
        err = eval_(lambda: log.capture())
        like_ok(str(err), r'Log messages are already being captured', 'right error')

with subtest('"trace"'):
    log = Pyjo.Log.new()
    log.level = 'trace'
    is_ok(log.level, 'trace', 'right level')
    ok(log.is_level('trace'), '"trace" log level is active')
    ok(log.is_level('debug'), '"debug" log level is active')
    ok(log.is_level('info'), '"info" log level is active')
    ok(log.is_level('warn'), '"warn" log level is active')
    ok(log.is_level('error'), '"error" log level is active')

with subtest('"debug"'):
    log = Pyjo.Log.new()
    log.level = 'debug'
    is_ok(log.level, 'debug', 'right level')
    ok(not log.is_level('trace'), '"trace" log level is inactive')
    ok(log.is_level('debug'), '"debug" log level is active')
    ok(log.is_level('info'), '"info" log level is active')
    ok(log.is_level('warn'), '"warn" log level is active')
    ok(log.is_level('error'), '"error" log level is active')

with subtest('"info"'):
    log = Pyjo.Log.new()
    log.level = 'info'
    is_ok(log.level, 'info', 'right level')
    ok(not log.is_level('trace'), '"trace" log level is inactive')
    ok(not log.is_level('debug'), '"debug" log level is inactive')
    ok(log.is_level('info'), '"info" log level is active')
    ok(log.is_level('warn'), '"warn" log level is active')
    ok(log.is_level('error'), '"error" log level is active')

with subtest('"warn"'):
    log = Pyjo.Log.new()
    log.level = 'warn'
    is_ok(log.level, 'warn', 'right level')
    ok(not log.is_level('trace'), '"trace" log level is inactive')
    ok(not log.is_level('debug'), '"debug" log level is inactive')
    ok(not log.is_level('info'), '"info" log level is inactive')
    ok(log.is_level('warn'), '"warn" log level is active')
    ok(log.is_level('error'), '"error" log level is active')

with subtest('"error"'):
    log = Pyjo.Log.new()
    log.level = 'error'
    is_ok(log.level, 'error', 'right level')
    ok(not log.is_level('trace'), '"trace" log level is inactive')
    ok(not log.is_level('debug'), '"debug" log level is inactive')
    ok(not log.is_level('info'), '"info" log level is inactive')
    ok(not log.is_level('warn'), '"warn" log level is inactive')
    ok(log.is_level('error'), '"error" log level is active')

with subtest('"fatal"'):
    log = Pyjo.Log.new()
    log.level = 'fatal'
    is_ok(log.level, 'fatal', 'right level')
    ok(not log.is_level('trace'), '"trace" log level is inactive')
    ok(not log.is_level('debug'), '"debug" log level is inactive')
    ok(not log.is_level('info'), '"info" log level is inactive')
    ok(not log.is_level('warn'), '"warn" log level is inactive')
    ok(not log.is_level('error'), '"error" log level is inactive')

with subtest('Context'):
    log = Pyjo.Log.new(level='warn')
    context = log.context('[123]')
    is_ok(context.level, 'warn')
    with contextlib.redirect_stderr(io.StringIO()) as handle:
        log = Pyjo.Log.new()
        context.debug('Fail')
        context.error('Just works')
        log.warn('No context')
        context.fatal('Mojolicious rocks')
    buffer = handle.getvalue()
    unlike_ok(buffer, r'\[debug\]', 'no debug message')
    like_ok(buffer, r'\[.*\] \[error\] \[123\] Just works\n', 'right error message')
    like_ok(buffer, r'\[.*\] \[warn\] No context\n', 'right warn message')
    like_ok(buffer, r'\[.*\] \[fatal\] \[123\] Mojolicious rocks\n', 'right fatal message')

with subtest('Nested context'):
    path_ = dir.child('nested.log')
    log = Pyjo.Log.new(path=path_)
    with contextlib.redirect_stderr(io.StringIO()) as handle:
        log.context('[123]').context('[456]').error('Grandchild')
    del log
    is_ok(handle.getvalue(), '', 'nothing on STDERR')
    like_ok(decode('UTF-8', path(path_).slurp()), r'\[.*\] \[error\] \[456\] Grandchild', 'right error message')

# Not in Mojolicious: the fields of a context, which a JSON message has as fields of its own
with subtest('Context fields'):
    log = Pyjo.Log.new()
    context = log.context(Pyjo.Log.Field('request_id', 'abc123', '[abc123]'), {'user': 'sri', 'tries': 3})
    with contextlib.redirect_stderr(io.StringIO()) as handle:
        context.info('Text')
    like_ok(handle.getvalue(), r'\[.*\] \[info\] \[abc123\] user=sri tries=3 Text\n', 'fields as text')
    log = Pyjo.Log.new(json=True)
    context = log.context(Pyjo.Log.Field('request_id', 'abc123', '[abc123]'), {'user': 'sri', 'tries': 3})
    with contextlib.redirect_stderr(io.StringIO()) as handle:
        context.info('JSON', Pyjo.Log.Field('message', 'Not this'), Pyjo.Log.Field('extra', [1, 2]))
    record = json.loads(handle.getvalue())
    is_deeply_ok(
        list(record), ['time', 'level', 'severity', 'message', 'pid', 'request_id', 'user', 'tries', 'extra'], 'fields'
    )
    is_ok(record['message'], 'JSON', 'message without fields')
    is_ok(record['request_id'], 'abc123', 'request id')
    is_ok(record['user'], 'sri', 'field of a dict')
    is_ok(record['tries'], 3, 'number')
    is_deeply_ok(record['extra'], [1, 2], 'field of a message')

    field = Pyjo.Log.Field('user', 'sri')
    is_ok(str(field), 'user=sri', 'text of a field')
    is_ok(field.name, 'user', 'name')
    is_ok(field.value, 'sri', 'value')
    with contextlib.redirect_stderr(io.StringIO()) as handle:
        Pyjo.Log.new(json=True).info('Values', Pyjo.Log.Field('when', time))
    like_ok(json.loads(handle.getvalue())['when'], r"^<module 'time'", 'value that JSON has no type for')

done_testing()
