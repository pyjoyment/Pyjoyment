from Pyjo.Test import *


with subtest('Synopsis'):
    from Pyjo.TOML import dump, load

    config = load('name = "Pyjoyment"\n\n[server]\nworkers = 4\n')
    is_deeply_ok(config, {'name': 'Pyjoyment', 'server': {'workers': 4}}, 'load')

    string = dump({'name': 'Pyjoyment', 'server': {'workers': 4}})
    is_ok(string, 'name = "Pyjoyment"\n\n[server]\nworkers = 4\n', 'dump')

with subtest('Description'):
    # 'name = "app"\n\n[server]\nworkers = 4\n'
    is_ok(dump({'name': 'app', 'server': {'workers': 4}}), 'name = "app"\n\n[server]\nworkers = 4\n', 'tables')

with subtest('dump'):
    string = dump({'name': 'Pyjoyment'})
    string = dump({'name': 'Pyjoyment', 'license': 'Artistic-2.0'}, sort_keys=True)
    is_ok(string, 'license = "Artistic-2.0"\nname = "Pyjoyment"\n', 'sorted')
    string = dump({'name': 'Pyjoyment'})

    # 'name = "Pyjoyment"\n'
    is_ok(string, 'name = "Pyjoyment"\n', 'string')

with subtest('load'):
    value = load('name = "Pyjoyment"')

    # {'name': 'Pyjoyment'}
    is_deeply_ok(value, {'name': 'Pyjoyment'}, 'value')

    # {'name': 'Pyjoyment'}
    is_deeply_ok(load('name = "Pyjoyment"'.encode('UTF-16')), {'name': 'Pyjoyment'}, 'UTF-16')

done_testing()
