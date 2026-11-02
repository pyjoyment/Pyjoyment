import Pyjo.GetOpt

from Pyjo.Test import *

import contextlib
import io
import os
import re
import sys

from unittest.mock import patch


# Not in Mojolicious: the tests of Pyjo.GetOpt, which follows Getopt::Long as Mojo::Util configures it; the expected
# values are those of getopt of Mojo::Util with the same arguments


def parse(args, *options, pass_through=False, require_order=False):
    getopt = Pyjo.GetOpt.new(pass_through=pass_through, require_order=require_order)
    for spec in options:
        getopt.option(spec)
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = getopt.parse(args)
    return result, stderr.getvalue()


with subtest('Strings'):
    args = ['--test=foo']
    result, _ = parse(args, 't|test=s')
    ok(result, 'success')
    is_ok(result.test, 'foo', 'long option with value')
    is_deeply_ok(args, [], 'option removed')
    is_ok(parse(['--t', 'foo'], 't|test=s')[0].test, 'foo', 'short name with two dashes')
    is_ok(parse(['-test', 'foo'], 't|test=s')[0].test, 'foo', 'long name with one dash')
    is_ok(parse(['-test=foo'], 't|test=s')[0].test, 'foo', 'long name with one dash and value')
    is_ok(parse(['-t', '-x'], 't|test=s')[0].test, '-x', 'value that starts with a dash')
    is_ok(parse(['-t', 'a', '-t', 'b'], 't|test=s')[0].test, 'b', 'last value')
    is_ok(parse([], 't|test=s')[0].test, None, 'no value')

with subtest('Numbers'):
    result, _ = parse(['-b', '23', '--ratio', '0.5'], 'b|backlog=i', 'r|ratio=f')
    is_ok(result.backlog, 23, 'integer')
    is_ok(result.ratio, 0.5, 'float')
    result, stderr = parse(['-b', 'x'], 'b|backlog=i')
    ok(not result, 'failure')
    is_ok(result.backlog, None, 'no value')
    like_ok(stderr, r'^Value "x" invalid for option b \(integer number expected\)\n', 'right warning')
    like_ok(parse(['-r', 'x'], 'r|ratio=f')[1], r'^Value "x" invalid for option r \(real number expected\)\n', 'real')
    is_ok(parse(['-c', '5', 'x'], 'c|count:i')[0].count, 5, 'optional number')

with subtest('Optional values'):
    result, _ = parse(['-p', '-l', 'x'], 'p|proxy:s@', 'l|lang=s')
    is_deeply_ok(result.proxy, [''], 'no value')
    is_ok(result.lang, 'x', 'next option')
    is_deeply_ok(parse(['-p', 'net', '-p'], 'p|proxy:s@')[0].proxy, ['net', ''], 'values')
    is_deeply_ok(parse(['--proxy='], 'p|proxy:s@')[0].proxy, [''], 'empty value')
    is_ok(parse(['-c'], 'c|count:i')[0].count, 0, 'no number')
    is_deeply_ok(parse([], 'p|proxy:s@')[0].proxy, [], 'no option')

with subtest('Hashes'):
    result, _ = parse(['-D', 'a=1', '--define', 'b=2=3', '-D', '=x'], 'D|define=s%')
    is_deeply_ok(result.define, {'a': '1', 'b': '2=3', '': 'x'}, 'strings')
    is_deeply_ok(parse(['-I', 'x=5'], 'I|int=i%')[0].int, {'x': 5}, 'integers')
    is_deeply_ok(parse([], 'D|define=s%')[0].define, {}, 'no option')
    result, stderr = parse(['-D', 'a'], 'D|define=s%')
    ok(not result, 'failure')
    like_ok(stderr, r'^Option D, key "a", requires a value\n', 'right warning')
    result, stderr = parse(['-I', 'x=5', '-I', 'y=z'], 'I|int=i%')
    is_deeply_ok(result.int, {'x': 5}, 'value before the error')
    like_ok(stderr, r'^Value "z" invalid for option I \(integer number expected\)\n', 'right warning')
    is_deeply_ok(parse(['-D', 'a'], 'D|define:s%')[0].define, {'a': ''}, 'optional value')

with subtest('Flags'):
    result, _ = parse(['-h', '-v', '-v', '--no-color'], 'h|help', 'v|verbose+', 'color!')
    is_ok(result.help, True, 'flag')
    is_ok(result.verbose, 2, 'incremented')
    is_ok(result.color, False, 'negated')
    is_ok(parse(['--nocolor'], 'color!')[0].color, False, 'negated without dash')
    is_ok(parse(['--color'], 'color!')[0].color, True, 'negatable')
    is_ok(parse([], 'h|help')[0].help, None, 'no flag')

with subtest('Arguments'):
    args = ['a', '-t', 'foo', 'b', '--', '-t', 'bar']
    is_ok(parse(args, 't|test=s')[0].test, 'foo', 'right value')
    is_deeply_ok(args, ['a', 'b', '-t', 'bar'], 'arguments in order, without the end of the options')
    args = ['-', '-t', 'foo']
    parse(args, 't|test=s')
    is_deeply_ok(args, ['-'], 'a dash is an argument')

with subtest('Errors'):
    args = ['--lang', 'de', '--lnag', 'x']
    result, stderr = parse(args, 'l|lang=s')
    ok(not result, 'failure')
    is_ok(result.lang, 'de', 'value before the error')
    is_deeply_ok(args, ['x'], 'unknown option removed')
    like_ok(stderr, r'^Unknown option: lnag\n', 'right warning')
    like_ok(parse(['-T', 'foo'], 't|test=s')[1], r'^Unknown option: T\n', 'case sensitive')
    like_ok(parse(['--tes', 'foo'], 't|test=s')[1], r'^Unknown option: tes\n', 'no abbreviation')
    like_ok(parse(['-tfoo'], 't|test=s')[1], r'^Unknown option: tfoo\n', 'no bundling')
    result, stderr = parse(['-t'], 't|test=s')
    ok(not result, 'failure')
    like_ok(stderr, r'^Option t requires an argument\n', 'right warning')
    like_ok(parse(['--help=x'], 'h|help')[1], r'^Option help does not take an argument\n', 'flag with value')
    throws_ok(
        lambda: Pyjo.GetOpt.new().option('t|test=x'), re.compile(r'^Error in option spec: "t\|test=x"'), 'bad spec'
    )
    throws_ok(
        lambda: Pyjo.GetOpt.new().option('c|concurrency=i', 4),
        re.compile(r'^Invalid option linkage for "c\|concurrency=i"'),
        'a default in the place of the target',
    )

with subtest('Defaults'):
    getopt = Pyjo.GetOpt.new().option('M|method=s', default='GET').option('v|verbose', default=False)
    result = getopt.parse([])
    is_ok(result.method, 'GET', 'default')
    is_ok(result.verbose, False, 'default of a flag')
    is_ok(getopt.parse(['-M', 'POST']).method, 'POST', 'value')
    getopt = Pyjo.GetOpt.new().option('H|header=s@', default=['a'])
    is_deeply_ok(getopt.parse([]).header, ['a'], 'default of a list')
    is_deeply_ok(getopt.parse(['-H', 'b']).header, ['b'], 'values instead of the default')
    is_deeply_ok(getopt.parse([]).header, ['a'], 'default again')

with subtest('Types and choices'):
    import Pyjo.File

    getopt = Pyjo.GetOpt.new().option('home=s', type=Pyjo.File.path)
    result = getopt.parse(['--home', '/tmp'])
    ok(isinstance(result.home, Pyjo.File.object), 'converted')
    is_ok(result.home.to_str(), '/tmp', 'right value')
    getopt = Pyjo.GetOpt.new().option('w|weekday=i', type=lambda value: ['Mon', 'Tue'][value])
    is_ok(getopt.parse(['-w', '1']).weekday, 'Tue', 'converted after the type of the specification')
    result, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(stderr):
        result = getopt.parse(['-w', '5'])
    ok(not result, 'failure')
    like_ok(stderr.getvalue(), r'^Value "5" invalid for option w \(list index out of range\)\n', 'right warning')
    getopt = Pyjo.GetOpt.new().option('m|mode=s', choices=['development', 'production'])
    is_ok(getopt.parse(['-m', 'production']).mode, 'production', 'choice')
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        ok(not getopt.parse(['-m', 'x']), 'failure')
    like_ok(
        stderr.getvalue(),
        r'^Value "x" invalid for option m \(choose from development, production\)\n',
        'right warning',
    )
    getopt = Pyjo.GetOpt.new().option('l|level=i@', choices=[1, 2])
    is_deeply_ok(getopt.parse(['-l', '1', '-l', '2']).level, [1, 2], 'choices of a list after the type')
    called = []
    getopt = Pyjo.GetOpt.new()
    getopt.on('d|day=s', lambda name, value: called.append(value), type=str.upper, choices=['MON'])
    getopt.parse(['-d', 'mon'])
    is_deeply_ok(called, ['MON'], 'callback')

with subtest('Pass through'):
    args = ['-t', 'foo', '-x', 'bar', '--', '-y']
    result, stderr = parse(args, 't|test=s', pass_through=True)
    ok(result, 'success')
    is_ok(result.test, 'foo', 'right value')
    is_deeply_ok(args, ['-x', 'bar', '--', '-y'], 'unknown options and the end of the options kept')
    is_ok(stderr, '', 'no warning')

with subtest('Require order'):
    args = ['-t', 'foo', 'myapp.py', '-t', 'bar', '--', '-y']
    result, stderr = parse(args, 't|test=s', require_order=True)
    ok(result, 'success')
    is_ok(result.test, 'foo', 'right value')
    is_deeply_ok(args, ['myapp.py', '-t', 'bar', '--', '-y'], 'everything after the first argument kept')
    is_ok(stderr, '', 'no warning')
    args = ['-t', 'foo', '--', '-y']
    result, stderr = parse(args, 't|test=s', require_order=True)
    is_deeply_ok(args, ['-y'], 'end of the options removed')

with subtest('Targets'):
    getopt = Pyjo.GetOpt.new()
    listen = []
    getopt.option('l|listen=s', listen)
    called = []

    @getopt.on('b|backlog=i')
    def backlog(name, value):
        called.append((name, value))

    getopt.on('k|insecure', lambda name, value: called.append((name, value)))
    result = getopt.parse(['-l', 'a', '--listen', 'b', '-b', '5', '-k'])
    ok(result, 'success')
    is_deeply_ok(listen, ['a', 'b'], 'list')
    is_deeply_ok(called, [('backlog', 5), ('insecure', True)], 'callbacks')
    define = {}
    getopt = Pyjo.GetOpt.new().option('D|define=s%', define)
    getopt.on('x=s%', lambda name, value: called.append((name, value)))
    getopt.parse(['-D', 'a=1', '-x', 'b=2'])
    is_deeply_ok(define, {'a': '1'}, 'dict')
    is_deeply_ok(called[-1], ('x', ('b', '2')), 'callback of a hash')
    ok(callable(backlog), 'decorator returns the callback')
    ok(not hasattr(result, 'listen'), 'no value of a target in the result')

with subtest('Environment variables as targets'):
    names = ('PYJO_TEST_MODE', 'PYJO_TEST_FLAG', 'PYJO_TEST_COLOR', 'PYJO_TEST_COUNT')
    try:
        getopt = Pyjo.GetOpt.new()
        getopt.option('m|mode=s', Pyjo.GetOpt.env('PYJO_TEST_MODE'))
        getopt.option('f|flag', Pyjo.GetOpt.env('PYJO_TEST_FLAG'))
        getopt.option('color!', Pyjo.GetOpt.env('PYJO_TEST_COLOR'))
        getopt.option('c|count=i', Pyjo.GetOpt.env('PYJO_TEST_COUNT'))
        ok(getopt.parse(['-m', 'production', '-f', '--no-color', '-c', '3']), 'success')
        is_deeply_ok([os.environ.get(name) for name in names], ['production', '1', '0', '3'], 'values of the options')
        ok(getopt.parse(['--color']), 'success')
        is_ok(os.environ['PYJO_TEST_COLOR'], '1', 'flag again')
    finally:
        for name in names:
            os.environ.pop(name, None)
    getopt.parse([])
    is_ok(os.environ.get('PYJO_TEST_MODE'), None, 'not set without the option')

with subtest('Usage'):
    usage = """Usage: APPLICATION test [OPTIONS]

  ./myapp.py test -v

Options:
  -h, --help   Show this summary of available options
      --home <path>  Path to home directory of your application, defaults to the value of PYJO_HOME or
      auto-detection
  -p, --proxy [<network>]       Activate reverse proxy support
  -V      Print returned data structure
  -v, --verbose
          Print return value

Options (for all commands):
  -m, --mode <name>   Operating mode

Text after the options.
"""
    formatted = Pyjo.GetOpt.format_usage(usage)
    is_ok(
        formatted,
        """Usage: APPLICATION test [OPTIONS]

  ./myapp.py test -v

Options:
  -h, --help                Show this summary of available options
      --home <path>         Path to home directory of your application,
                            defaults to the value of PYJO_HOME or
                            auto-detection
  -p, --proxy [<network>]   Activate reverse proxy support
  -V                        Print returned data structure
  -v, --verbose             Print return value

Options (for all commands):
  -m, --mode <name>   Operating mode

Text after the options.
""",
        'laid out',
    )
    is_ok(Pyjo.GetOpt.format_usage(formatted), formatted, 'idempotent')
    is_ok(
        Pyjo.GetOpt.format_usage('Usage: test\n\n  -h   Not options\n'),
        'Usage: test\n\n  -h   Not options\n',
        'no block',
    )
    like_ok(
        Pyjo.GetOpt.format_usage(usage, width=50),
        r'\n      --home <path>         Path to home directory\n                            of your application,\n',
        'width',
    )
    like_ok(
        Pyjo.GetOpt.format_usage('Options:\n  -x   ' + 'a' * 100 + ' b\n'),
        r'^Options:\n  -x   a{100}\n       b\n$',
        'long word not broken',
    )

with subtest('Environment'):
    env = {
        'TEST_MODE': 'production',
        'TEST_WORKERS': '12',
        'TEST_VERBOSE': '1',
        'TEST_COLOR': 'false',
        'TEST_COUNT': '3',
        'TEST_LISTEN': 'http://*:80,https://*:443',
        'TEST_DEFINE': 'a=1,b=2',
        'TEST_PROXY': '',
        'TEST_EMPTY': '',
        'TEST_V': '1',
        'TEST_TIMEOUT': '7',
    }
    with patch.dict(os.environ, env):
        getopt = Pyjo.GetOpt.new(env_prefix='TEST_')
        for spec in ('m|mode=s', 'w|workers=i', 'verbose', 'color!', 'count+', 'l|listen=s@', 'D|define=s%', 'empty=s'):
            getopt.option(spec)
        getopt.option('v').option('p|proxy:s').option('t|timeout=i', default=30)
        args = ['-w', '4', 'myapp.py']
        result = getopt.parse(args)
        ok(result, 'success')
        is_ok(result.mode, 'production', 'string')
        is_ok(result.workers, 4, 'command line first')
        is_ok(result.verbose, True, 'flag')
        is_ok(result.color, False, 'false flag')
        is_ok(result.count, 3, 'counter')
        is_deeply_ok(result.listen, ['http://*:80', 'https://*:443'], 'list of values with commas')
        is_deeply_ok(result.define, {'a': '1', 'b': '2'}, 'dict of keys and values with commas')
        is_ok(result.proxy, None, 'empty variable of an optional value')
        is_ok(result.empty, None, 'empty variable')
        is_ok(result.v, None, 'no variable of an option of one letter')
        is_ok(result.timeout, 7, 'variable before the default')
        is_deeply_ok(args, ['myapp.py'], 'arguments')

        for value in ('0', 'false', 'FALSE', 'no', 'off'):
            with patch.dict(os.environ, {'TEST_VERBOSE': value}):
                is_ok(Pyjo.GetOpt.new(env_prefix='TEST_').option('verbose').parse([]).verbose, False, f'false {value}')

        # Targets
        listen = []
        called = []
        getopt = Pyjo.GetOpt.new(env_prefix='TEST_').option('l|listen=s', listen)
        getopt.on('w|workers=i', lambda name, value: called.append((name, value)))
        ok(getopt.parse([]), 'success')
        is_deeply_ok(listen, ['http://*:80', 'https://*:443'], 'list target')
        is_deeply_ok(called, [('workers', 12)], 'callback')

        # Without the prefix
        is_ok(Pyjo.GetOpt.new().option('m|mode=s').parse([]).mode, None, 'no variables without a prefix')

    with patch.dict(os.environ, {'TEST_WORKERS': 'many'}):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = Pyjo.GetOpt.new(env_prefix='TEST_').option('w|workers=i').parse([])
        ok(not result, 'invalid value')
        is_ok(stderr.getvalue(), 'Value "many" invalid for option TEST_WORKERS (integer number expected)\n', 'warning')

with subtest('sys.argv'):
    argv = sys.argv
    try:
        sys.argv = [argv[0], '-t', 'foo', 'bar']
        is_ok(Pyjo.GetOpt.new().option('t|test=s').parse().test, 'foo', 'right value')
        is_deeply_ok(sys.argv, [argv[0], 'bar'], 'options removed')
    finally:
        sys.argv = argv

done_testing()
