from Pyjo.Test import *


with subtest('Synopsis'):
    from Pyjo.INI import Comment, dump, load

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

    # {Comment('; the region', 0): None, 'region': 'eu-central-1'}
    is_deeply_ok(
        load('; the region\nregion = eu-central-1\n', comments=True),
        {Comment('; the region', 0): None, 'region': 'eu-central-1'},
        'comments',
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

    # '[www]\n; the workers\npm.max_children = 2\n'
    is_ok(
        dump({'www': {'; the workers': None, 'pm.max_children': 2}}),
        '[www]\n; the workers\npm.max_children = 2\n',
        'dump of a comment',
    )

with subtest('Comment'):
    comment = Comment('; the region')
    comment = Comment('#', 1)
    is_ok(comment.occurrence, 1, 'occurrence')

    # {Comment('#', 0): None, Comment('#', 1): None}
    is_deeply_ok(load('#\n#\n', comments=True), {Comment('#', 0): None, Comment('#', 1): None}, 'two keys')

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
    value = load('# a\na = 1', comments=True)
    is_deeply_ok(value, {Comment('# a'): None, 'a': '1'}, 'comments')
    value = load('a = "1"', unquote=True)
    is_deeply_ok(value, {'a': '1'}, 'unquote')

    # {'PHP': {'error_log': '"/var/log/php.log"'}}
    is_deeply_ok(load('[PHP]\nerror_log = "/var/log/php.log"\n'), {'PHP': {'error_log': '"/var/log/php.log"'}}, 'kept')

    # {'PHP': {'error_log': '/var/log/php.log'}}
    is_deeply_ok(
        load('[PHP]\nerror_log = "/var/log/php.log"\n', unquote=True), {'PHP': {'error_log': '/var/log/php.log'}}, 'off'
    )

done_testing()
