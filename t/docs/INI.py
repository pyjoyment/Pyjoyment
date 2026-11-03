from Pyjo.Test import *


with subtest('Synopsis'):
    from Pyjo.INI import dump, load

    config = load('[default]\nregion = eu-central-1\noutput = json\n')
    is_deeply_ok(config, {'default': {'region': 'eu-central-1', 'output': 'json'}}, 'load')

    string = dump({'www': {'listen': '127.0.0.1:9000', 'pm': 'static', 'pm.max_children': 2}})
    is_ok(string, '[www]\nlisten = 127.0.0.1:9000\npm = static\npm.max_children = 2\n', 'dump')

with subtest('Description'):
    # {'root': 'true', '*.py': {'indent_size': '4'}}
    is_deeply_ok(
        load('root = true\n\n[*.py]\nindent_size = 4\n'),
        {'root': 'true', '*.py': {'indent_size': '4'}},
        'keys at the top',
    )

    # {'profile dev': {'s3': {'max_concurrent_requests': '20'}}}
    is_deeply_ok(
        load('[profile dev]\ns3 =\n    max_concurrent_requests = 20\n'),
        {'profile dev': {'s3': {'max_concurrent_requests': '20'}}},
        'dict',
    )

    # {'PHP': {'extension': ['curl', 'mbstring']}}
    is_deeply_ok(
        load('[PHP]\nextension = curl\nextension = mbstring\n'), {'PHP': {'extension': ['curl', 'mbstring']}}, 'list'
    )

    # '[default]\nregion = eu-central-1\n'
    is_ok(dump({'default': {'region': 'eu-central-1'}}), '[default]\nregion = eu-central-1\n', 'dump')

with subtest('dump'):
    string = dump({'a': 1})
    string = dump({'b': 1, 'a': 2}, sort_keys=True)
    is_ok(string, 'a = 2\nb = 1\n', 'sorted')

    # 'listen = 127.0.0.1:9000\npm.max_children = 2\n'
    is_ok(
        dump({'listen': '127.0.0.1:9000', 'pm.max_children': 2}),
        'listen = 127.0.0.1:9000\npm.max_children = 2\n',
        'keys',
    )

with subtest('load'):
    value = load('a = 1')
    value = load('a = "1"', unquote=True)
    is_deeply_ok(value, {'a': '1'}, 'unquote')

    # {'PHP': {'error_log': '"/var/log/php.log"'}}
    is_deeply_ok(load('[PHP]\nerror_log = "/var/log/php.log"\n'), {'PHP': {'error_log': '"/var/log/php.log"'}}, 'kept')

    # {'PHP': {'error_log': '/var/log/php.log'}}
    is_deeply_ok(
        load('[PHP]\nerror_log = "/var/log/php.log"\n', unquote=True), {'PHP': {'error_log': '/var/log/php.log'}}, 'off'
    )

done_testing()
