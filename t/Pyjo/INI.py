from Pyjo.INI import dump, load
from Pyjo.Test import *

import datetime
import re


# Not in Mojolicious: Pyjo.INI, the INI of the files of well-known programs, as ~/.aws/config, php.ini and php-fpm.conf

AWS_CONFIG = """# The default profile
[default]
region = eu-central-1
output = json

[profile dev]
sso_session = my-sso
sso_account_id = 111122223333
region: us-west-2
s3 =
    max_concurrent_requests = 20
    addressing_style = path
cli_pager =

; Single sign-on
[sso-session my-sso]
sso_start_url = https://my-sso-portal.awsapps.com/start
sso_region = us-east-1

[services dev-s3]
s3 =
  endpoint_url = http://localhost:4566
"""

PHP_INI = """[PHP]
; Errors
error_reporting = E_ALL & ~E_DEPRECATED
display_errors = Off
error_log = "/var/log/php.log"
extension = curl
extension = mbstring

[Date]
date.timezone = 'Europe/Warsaw'
"""

with subtest('Load sections and keys'):
    is_deeply_ok(load(''), {}, 'empty')
    is_deeply_ok(
        load('root = true\n\n[*.py]\nindent_style = space\nindent_size: 4\n'),
        {'root': 'true', '*.py': {'indent_style': 'space', 'indent_size': '4'}},
        'keys at the top and a section',
    )
    is_deeply_ok(load('[a]\nx = 1\n[b]\ny = 2\n[a]\nz = 3\n'), {'a': {'x': '1', 'z': '3'}, 'b': {'y': '2'}}, 'again')
    is_deeply_ok(load('[ profile dev ]\nKey = Value\n'), {'profile dev': {'Key': 'Value'}}, 'names and case kept')
    is_deeply_ok(load('a=1\nb : 2\nc = x=y:z\n'), {'a': '1', 'b': '2', 'c': 'x=y:z'}, 'first delimiter')
    is_deeply_ok(
        load('[mysqld]\nskip-name-resolve\nport = 3306\n'),
        {'mysqld': {'skip-name-resolve': None, 'port': '3306'}},
        'no value',
    )
    is_deeply_ok(load('a =\nb = \n'), {'a': '', 'b': ''}, 'empty values')
    is_deeply_ok(load('a = 1\r\n[b]\r\nc = 2\r\n'), {'a': '1', 'b': {'c': '2'}}, 'CRLF')
    is_deeply_ok(load('[b]\n'), {'b': {}}, 'empty section')

with subtest('Load comments'):
    is_deeply_ok(
        load('; one\n# two\n  ; three\na = 1 ; four\nb = # five\n'), {'a': '1 ; four', 'b': '# five'}, 'lines only'
    )

with subtest('Load values of several lines'):
    is_deeply_ok(load('a = one\n  two\n    three\nb = 2\n'), {'a': 'one\ntwo\nthree', 'b': '2'}, 'continued')
    is_deeply_ok(load('a = one\n\n  two\n'), {'a': 'one', 'two': None}, 'blank line ends a value')
    is_deeply_ok(load('a = one\n; comment\n  two\n'), {'a': 'one\ntwo'}, 'comment inside')
    is_deeply_ok(load('[s]\n  a = 1\n  b = 2\n'), {'s': {'a': '1', 'b': '2'}}, 'indented keys')
    is_deeply_ok(load('a =\n  one\n  two\n'), {'a': '\none\ntwo'}, 'after an empty value')
    is_deeply_ok(
        load('[profile dev]\ns3 =\n    max_concurrent_requests = 20\n    addressing_style = path\n'),
        {'profile dev': {'s3': {'max_concurrent_requests': '20', 'addressing_style': 'path'}}},
        'dict',
    )
    is_deeply_ok(load('a =\n  x = 1:2 = 3\n'), {'a': {'x': '1:2 = 3'}}, 'dict at the first "="')
    is_deeply_ok(load('a =\n  x = 1\n  y: 2\n'), {'a': '\nx = 1\ny: 2'}, 'not a dict without "="')

with subtest('Load keys that come again'):
    is_deeply_ok(load('a = 1\na = 2\na = 3\n'), {'a': ['1', '2', '3']}, 'list')
    is_deeply_ok(load('[s]\na = 1\n[s]\na = 2\n'), {'s': {'a': ['1', '2']}}, 'in a section that comes again')
    is_deeply_ok(load('a =\n  x = 1\n  x = 2\n'), {'a': {'x': ['1', '2']}}, 'in a dict')

with subtest('Load with unquote'):
    is_deeply_ok(load('a = "x"\nb = \'y\'\n'), {'a': '"x"', 'b': "'y'"}, 'kept')
    is_deeply_ok(
        load('a = "x"\nb = \'y\'\nc = "z\'\nd = "\ne = ""\n', unquote=True),
        {'a': 'x', 'b': 'y', 'c': '"z\'', 'd': '"', 'e': ''},
        'taken off',
    )
    is_deeply_ok(load('a =\n  x = "1"\n', unquote=True), {'a': {'x': '1'}}, 'in a dict')

with subtest('Load errors'):
    throws_ok(lambda: load('[a\n'), re.compile(r'^INI line 1: no name of the section'), 'no bracket')
    throws_ok(lambda: load('[ ]\n'), re.compile(r'^INI line 1: no name of the section'), 'no name')
    throws_ok(lambda: load('a = 1\n= 2\n'), re.compile(r'^INI line 2: no key'), 'no key')
    throws_ok(
        lambda: load('a\n  b\n'), re.compile(r'^INI line 2: continues the key "a", which has no value'), 'continued'
    )
    throws_ok(lambda: load('a = 1\n[a]\n'), re.compile(r'^INI line 2: the section "a" is a key too'), 'section')

with subtest('Load the files of well-known programs'):
    is_deeply_ok(
        load(AWS_CONFIG),
        {
            'default': {'region': 'eu-central-1', 'output': 'json'},
            'profile dev': {
                'sso_session': 'my-sso',
                'sso_account_id': '111122223333',
                'region': 'us-west-2',
                's3': {'max_concurrent_requests': '20', 'addressing_style': 'path'},
                'cli_pager': '',
            },
            'sso-session my-sso': {
                'sso_start_url': 'https://my-sso-portal.awsapps.com/start',
                'sso_region': 'us-east-1',
            },
            'services dev-s3': {'s3': {'endpoint_url': 'http://localhost:4566'}},
        },
        '~/.aws/config',
    )
    is_deeply_ok(
        load(PHP_INI, unquote=True),
        {
            'PHP': {
                'error_reporting': 'E_ALL & ~E_DEPRECATED',
                'display_errors': 'Off',
                'error_log': '/var/log/php.log',
                'extension': ['curl', 'mbstring'],
            },
            'Date': {'date.timezone': 'Europe/Warsaw'},
        },
        'php.ini',
    )

with subtest('Dump keys and values'):
    is_ok(dump({}), '', 'empty')
    is_ok(
        dump({'listen': '127.0.0.1:9000', 'pm.max_children': 2}),
        'listen = 127.0.0.1:9000\npm.max_children = 2\n',
        'keys',
    )
    is_ok(
        dump({'a': True, 'b': False, 'c': -12, 'd': 1.5, 'e': '', 'f': None, 'g': 'x = y; z'}),
        'a = true\nb = false\nc = -12\nd = 1.5\ne =\nf\ng = x = y; z\n',
        'types',
    )
    is_ok(
        dump({'a': datetime.date(2026, 11, 3), 'b': datetime.datetime(2026, 11, 3, 12, 30)}),
        'a = 2026-11-03\nb = 2026-11-03T12:30:00\n',
        'dates',
    )
    is_ok(dump({'a': 'one\ntwo', 'b': '\nthree'}), 'a = one\n    two\nb =\n    three\n', 'several lines')
    is_ok(dump({'extension': ['curl', 'mbstring']}), 'extension = curl\nextension = mbstring\n', 'list')

with subtest('Dump sections'):
    is_ok(
        dump({'root': True, '*.py': {'indent_size': 4}, 'Makefile': {'indent_style': 'tab'}}),
        'root = true\n\n[*.py]\nindent_size = 4\n\n[Makefile]\nindent_style = tab\n',
        'keys at the top first',
    )
    is_ok(dump({'b': {}, 'a': 1}), 'a = 1\n\n[b]\n', 'keys at the top before an empty section')
    is_ok(
        dump(
            {'profile dev': {'region': 'us-west-2', 's3': {'max_concurrent_requests': 20, 'addressing_style': 'path'}}}
        ),
        '[profile dev]\nregion = us-west-2\ns3 =\n    max_concurrent_requests = 20\n    addressing_style = path\n',
        'dict',
    )
    is_ok(dump({'s': {'a': {'x': [1, 2]}}}), '[s]\na =\n    x = 1\n    x = 2\n', 'list in a dict')
    is_ok(dump({'s': {'a': [{'x': 1}, {'x': 2}]}}), '[s]\na =\n    x = 1\na =\n    x = 2\n', 'list of dicts')

with subtest('Dump the order of the keys'):
    value = {'b': 1, 'a': {'d': 2, 'c': {'f': 3, 'e': 4}}}
    is_ok(dump(value), 'b = 1\n\n[a]\nd = 2\nc =\n    f = 3\n    e = 4\n', 'order of the dicts')
    is_ok(dump(value, sort_keys=True), 'b = 1\n\n[a]\nc =\n    e = 4\n    f = 3\nd = 2\n', 'sorted')

with subtest('Dump objects'):

    class Value:
        def __json__(self):
            return {'a': 1}

    class Name:
        def __str__(self):
            return 'name'

    is_ok(dump({'s': Value(), 'n': Name()}), 'n = name\n\n[s]\na = 1\n', '__json__ and __str__')

with subtest('Dump errors'):
    throws_ok(lambda: dump(['a']), re.compile(r'^INI needs a dict at the top, not a list'), 'not a dict')
    throws_ok(lambda: dump({1: 'a'}), re.compile(r"^INI does not support a key of the type 'int'"), 'key type')
    throws_ok(lambda: dump({1: {}}), re.compile(r"^INI does not support a section of the type 'int'"), 'section type')
    for key in ('', ' a', 'a=b', 'a:b', '[a', ';a', '#a', 'a\nb'):
        throws_ok(lambda key=key: dump({key: 1}), re.compile(r'^INI does not support the key '), f'key {key!r}')
    for name in ('', 'a]', ' a', 'a\nb'):
        throws_ok(
            lambda name=name: dump({name: {}}), re.compile(r'^INI does not support the section '), f'section {name!r}'
        )
    throws_ok(lambda: dump({'a': b'x'}), re.compile(r"^INI does not support a value of the type 'bytes'"), 'bytes')
    throws_ok(lambda: dump({'a': []}), re.compile(r'^INI does not support the empty list of the key "a"'), 'empty list')
    throws_ok(
        lambda: dump({'a': [[1]]}), re.compile(r'^INI does not support a list in the list of the key "a"'), 'list'
    )
    throws_ok(
        lambda: dump({'a': [{'x': 1}]}), re.compile(r'^INI does not support the dict of the key "a" there'), 'top'
    )
    throws_ok(
        lambda: dump({'s': {'a': {'x': {}}}}), re.compile(r'^INI does not support the dict of the key "x"'), 'deep'
    )
    throws_ok(lambda: dump({'s': {'a': {'x': None}}}), re.compile(r'"x" without a value in a dict'), 'None in a dict')
    throws_ok(lambda: dump({'s': {'a': {'x': '1\n2'}}}), re.compile(r'several lines of the key "x" in a dict'), 'lines')
    for string in (' a', 'a ', 'a\n b', 'a\r\nb'):
        throws_ok(
            lambda string=string: dump({'a': string}),
            re.compile(r'^INI does not support the spaces'),
            f'value {string!r}',
        )
    for string in ('a\n', 'a\n\nb', 'a\n;b', 'a\n#b'):
        throws_ok(
            lambda string=string: dump({'a': string}),
            re.compile(r'an empty line or a comment in the value'),
            f'value {string!r}',
        )
    throws_ok(lambda: dump({'a': '\nx = 1'}), re.compile(r'value of the key "a", which would be a dict'), 'dict')

with subtest('Dump round trip'):
    for name, string in (('~/.aws/config', AWS_CONFIG), ('php.ini', PHP_INI)):
        value = load(string)
        is_deeply_ok(load(dump(value)), value, name)

done_testing()
