from Pyjo.File import tempdir
from Pyjo.Test import *

import contextlib
import datetime
import io
import json
import logging
import os
import time


dir = tempdir()

with subtest('Synopsis'):
    from Pyjo.Log import Log

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        # Log to STDERR
        log = Log()
        log.debug('To STDERR')
    like_ok(stderr.getvalue(), r'\[debug\] To STDERR\n', 'to STDERR')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Log

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        # Log to STDERR
        log = Pyjo.Log.new()
        log.debug('To STDERR')
    like_ok(stderr.getvalue(), r'\[debug\] To STDERR\n', 'to STDERR')

    # Customize log file location and minimum log level
    log = Pyjo.Log.new(path=dir.child('pyjo.log'), level='warn')

    # Log messages
    log.trace('Doing stuff')
    log.debug('Not sure what is happening here')
    log.info('FYI: it happened again')
    log.warn('This might be a problem')
    log.error('Garden variety error')
    log.fatal('Boom')
    # Universal newlines, as the log is a file of text, which Windows writes with CRLF
    content = dir.child('pyjo.log').to_path().read_text(encoding='UTF-8')
    unlike_ok(content, r'Doing stuff|Not sure|FYI', 'below the level')
    like_ok(
        content, r'\[warn\] This might be a problem\n.*\[error\] Garden variety error\n.*\[fatal\] Boom\n', 'logged'
    )

with subtest('message'):
    log = Pyjo.Log.new(handle=None)
    log.on('message', lambda log, level, *lines: ...)
    is_ok(len(log.subscribers('message')), 2, 'subscribed')

    log = Pyjo.Log.new(handle=None)
    log.on('message', lambda log, level, *lines: print(f'{level}: ', *lines, sep=''))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        log.info('Hello', 'World')
    is_ok(output.getvalue(), 'info: HelloWorld\n', 'printed')

with subtest('JSON'):
    log = Pyjo.Log.new(json=True)
    record = json.loads(log.format(1760861742.12345, 'warn', 'Disk is 95% full'))
    is_deeply_ok(
        record,
        {
            'time': '2025-10-19T08:15:42.123450Z',
            'level': 'warn',
            'severity': 'WARNING',
            'message': 'Disk is 95% full',
            'pid': os.getpid(),
        },
        'line of JSON',
    )
    is_deeply_ok(
        [
            json.loads(log.format(0, level, 'x'))['severity']
            for level in ('trace', 'debug', 'info', 'warn', 'error', 'fatal')
        ],
        ['DEBUG', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        'severities',
    )

with subtest('Files of a period'):
    # A file of each day
    log = Pyjo.Log.new(path=dir.child('%Y-%m-%d.log').to_str())
    log.error('Of today')
    log.close()
    like_ok(dir.child(time.strftime('%Y-%m-%d.log')).slurp().decode(), r'\[error\] Of today\n$', 'file of the day')

    # A file of each hour, with the offset of the time zone
    log = Pyjo.Log.new(path=dir.child('%Y-%m-%dT%H%z.log').to_str())
    log.error('Of this hour')
    log.close()
    like_ok(dir.child(time.strftime('%Y-%m-%dT%H%z.log')).slurp().decode(), r'Of this hour\n$', 'file of the hour')

    # A file of each day in UTC
    log = Pyjo.Log.new(path=dir.child('utc-%Y-%m-%d.log').to_str(), tz='UTC')
    log.error('Of the day in UTC')
    log.close()
    name = datetime.datetime.now(datetime.UTC).strftime('utc-%Y-%m-%d.log')
    like_ok(dir.child(name).slurp().decode(), r'Of the day in UTC\n$', 'file of the day in UTC')

with subtest('The logging module'):
    log = Pyjo.Log.new(handle=None)
    logger = logging.getLogger('t.docs.Log')
    logger.propagate = False
    with log.capture() as messages:
        logger.addHandler(Pyjo.Log.Handler(log))
        logger.warning('Disk is %d%% full', 95)
    like_ok(messages[0], r'\[warn\] Disk is 95% full\n$', 'passed to the log')

with subtest('color'):
    log = Pyjo.Log.new()
    boolean = log.color
    is_ok(boolean, False, 'default')
    log.color = True
    like_ok(log.format(time.time(), 'error', 'Red'), r'^\x1b\[31m', 'colored')

with subtest('format'):
    log = Pyjo.Log.new()
    cb = log.format
    like_ok(cb(time.time(), 'info', 'Default'), r'\[info\] Default\n$', 'default')
    log.format = lambda time, level, *lines: '[2018-11-08 14:20:13.77168] [28320] [info] I ♥ Pyjoyment\n'
    is_ok(log.format(time.time(), 'debug'), '[2018-11-08 14:20:13.77168] [28320] [info] I ♥ Pyjoyment\n', 'custom')

with subtest('handle'):
    log = Pyjo.Log.new()
    handle = log.handle
    ok(handle is not None, 'STDERR')
    log.handle = io.StringIO()
    log.info('In memory')
    like_ok(log.handle.getvalue(), r'\[info\] In memory\n', 'logged')

with subtest('history'):
    log = Pyjo.Log.new(handle=None)
    history = log.history
    is_ok(history, [], 'empty')
    log.history = [[time.time(), 'debug', 'That went wrong']]
    is_ok(log.history[0][2], 'That went wrong', 'set')

with subtest('json'):
    log = Pyjo.Log.new()
    boolean = log.json
    is_ok(boolean, False, 'default')
    log.json = True
    like_ok(log.format(time.time(), 'info', 'JSON'), r'^\{"time":.*"message":"JSON".*\}\n$', 'json')

with subtest('level'):
    log = Pyjo.Log.new()
    level = log.level
    is_ok(level, 'trace', 'default')
    log.level = 'debug'
    is_ok(log.level, 'debug', 'set')

with subtest('max_history_size'):
    log = Pyjo.Log.new()
    size = log.max_history_size
    is_ok(size, 10, 'default')
    log.max_history_size = 5
    is_ok(log.max_history_size, 5, 'set')

with subtest('path'):
    log = Pyjo.Log.new()
    path = log.path
    is_ok(path, None, 'default')
    log.path = '/var/log/pyjo.log'
    is_ok(log.path, '/var/log/pyjo.log', 'set')

with subtest('short'):
    log = Pyjo.Log.new()
    boolean = log.short
    is_ok(boolean, False, 'default')
    log.short = True
    like_ok(log.format(time.time(), 'info', 'Short'), r'^<5>\[\d+\] \[i\] Short\n$', 'short')

with subtest('tz'):
    log = Pyjo.Log.new()
    tz = log.tz
    is_ok(tz, None, 'default')
    log.tz = 'UTC'
    is_ok(log.tz, 'UTC', 'UTC')
    log.tz = 'Europe/Warsaw'
    is_ok(log.tz, 'Europe/Warsaw', 'name')

with subtest('append'):
    log = Pyjo.Log.new(handle=io.StringIO())
    log.append('[2018-11-08 14:20:13.77168] [28320] [info] I ♥ Pyjoyment\n')
    is_ok(log.handle.getvalue(), '[2018-11-08 14:20:13.77168] [28320] [info] I ♥ Pyjoyment\n', 'appended')

with subtest('capture'):
    log = Pyjo.Log.new(handle=None)
    with log.capture() as messages:
        log.trace('Captured')
    is_ok(len(messages), 1, 'captured')
    with log.capture('debug') as messages:
        log.trace('Not captured')
    is_ok(len(messages), 0, 'below the level')

    # Test your log messages
    with log.capture('trace') as messages:
        log.fatal('Something very bad happened')
        log.trace('Just some debug information')
    like_ok(str(messages), r'Something very bad happened', 'logs contain fatal message')
    like_ok(messages[-1], r'Just some debug information', 'trace message was last')

with subtest('close'):
    import Pyjo.Log

    log = Pyjo.Log.new(path=tempdir().child('test.log'))
    log.info('First')
    handle = log.handle
    log.close()
    ok(handle.closed, 'file closed')


with subtest('context'):
    log = Pyjo.Log.new(handle=None)
    new = log.context('[extra]', '[information]')
    with log.capture() as messages:
        new.info('Message')
    like_ok(messages[0], r'\[info\] \[extra\] \[information\] Message\n$', 'context')

    with contextlib.redirect_stderr(io.StringIO()) as stderr:
        # Log with context
        log = Pyjo.Log.new()
        context = log.context('[17a60115]')
        context.debug('This is a log message with context information')
        context.info('And another')
    like_ok(stderr.getvalue(), r'\[debug\] \[17a60115\] This is a log message with context information\n', 'debug')
    like_ok(stderr.getvalue(), r'\[info\] \[17a60115\] And another\n', 'info')

    # Log with the fields of a context
    context = log.context({'user': 'sri'})
    with log.capture() as messages:
        context.info('Fields')
    like_ok(messages[0], r'\[info\] user=sri Fields\n$', 'fields')


with subtest('Logging methods'):
    log = Pyjo.Log.new(handle=None)
    with log.capture() as messages:
        log = log.debug('You screwed up, but that is ok')
        log = log.debug('All', 'cool')
        log = log.debug(lambda: 'Lazy')
        log = log.error('You really screwed up this time')
        log = log.error('Wow', 'seriously')
        log = log.error(lambda: ('Lazy', 'too'))
        log = log.fatal('Its over...')
        log = log.fatal('Bye', 'bye')
        log = log.fatal(lambda: 'Lazy')
        log = log.info('You are bad, but you prolly know already')
        log = log.info('Ok', 'then')
        log = log.info(lambda: 'Lazy')
        log = log.trace('Whatever')
        log = log.trace('Who', 'cares')
        log = log.trace(lambda: 'Lazy')
        log = log.warn('Dont do that Dave...')
        log = log.warn('No', 'really')
        log = log.warn(lambda: 'Lazy')
    isa_ok(log, Pyjo.Log.object, 'chained')
    is_ok(len(messages), 18, 'all logged')
    like_ok(messages[1], r'\[debug\] All cool\n$', 'lines joined')
    like_ok(messages[5], r'\[error\] Lazy too\n$', 'lazy lines')

with subtest('is_level'):
    log = Pyjo.Log.new()
    boolean = log.is_level('debug')
    ok(boolean, 'active')

    # True
    ok(log.set(level='debug').is_level('debug'), 'true')
    ok(log.set(level='debug').is_level('info'), 'true')

    # False
    ok(not log.set(level='info').is_level('debug'), 'false')
    ok(not log.set(level='fatal').is_level('warn'), 'false')

with subtest('new'):
    log = Pyjo.Log.new()
    is_ok(len(log.subscribers('message')), 1, 'default logger')
    log = Pyjo.Log.new(level='warn')
    is_ok(log.level, 'warn', 'level')

with subtest('Field'):
    field = Pyjo.Log.Field('user', 'sri')
    is_ok(str(field), 'user=sri', 'field')
    field = Pyjo.Log.Field('request_id', 'abc123', '[abc123]')
    is_ok(str(field), '[abc123]', 'text')

    # Log with a field
    log = Pyjo.Log.new(json=True, handle=None)
    with log.capture() as messages:
        log.info('Disk is full', Pyjo.Log.Field('disk', '/dev/sda1'))
    record = json.loads(messages[0])
    is_ok(record['message'], 'Disk is full', 'message')
    is_ok(record['disk'], '/dev/sda1', 'field')

    name = field.name
    is_ok(name, 'request_id', 'name')
    value = field.value
    is_ok(value, 'abc123', 'value')

with subtest('Handler'):
    log = Pyjo.Log.new(handle=None)
    handler = Pyjo.Log.Handler(log)
    is_ok(handler.level, logging.NOTSET, 'all levels')
    handler = Pyjo.Log.Handler(log, logging.INFO)
    is_ok(handler.level, logging.INFO, 'level')

done_testing()
