import Pyjo.File
import Pyjo.Test.Pyjo

from Pyjo.Test import *

import importlib
import os
import re
import sys


# The code of plugins/pyjoyment/skills/api/SKILL.md, each application in the file that its first line names, as a
# coding agent writes it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Skills = importlib.import_module('Skills')

tmp = Pyjo.File.tempdir()
files = {}
for code in Skills.blocks('api'):
    files[re.match(r'# (\S+)\n', code)[1]] = tmp.child(re.match(r'# (\S+)\n', code)[1]).spew(code)
is_deeply_ok(sorted(files), ['rest.py', 'rpc.py'], 'two applications')


def load(name):
    t = Pyjo.Test.Pyjo.new(files[name])
    t.app.log.level = 'fatal'
    # The user agent of the application requests its relative URLs from it, as from the only application of its process
    t.app.ua.server.app = t.app
    return t


with subtest('REST'):
    t = load('rest.py')
    t.get_ok('/items').status_is(200).json_is([{'id': 1, 'name': 'Pen', 'price': 1.5}])
    page = {'Origin': 'https://app.example.com'}
    t.get_ok('/items', page).status_is(200).header_is('Access-Control-Allow-Origin', '*')
    preflight = {**page, 'Access-Control-Request-Method': 'DELETE'}
    t.options_ok('/items/1', preflight).status_is(204).header_like('Access-Control-Allow-Methods', r'DELETE')
    t.post_ok('/items', json={'name': 'Book', 'price': 'cheap'}).status_is(422)
    t.json_is('/errors/0', '/price: Expected number - got string.')
    t.post_ok('/items', json={'name': 'Book', 'price': 9.9, 'tags': ['paper']}).status_is(201)
    t.json_is({'id': 2, 'name': 'Book', 'price': 9.9, 'tags': ['paper']}).header_like('Location', r'/items/2$')
    t.post_ok('/items', 'not JSON').status_is(422).json_is('/errors/0', '/: Expected object - got null.')
    t.get_ok('/items/2').status_is(200).json_is('/name', 'Book')
    t.get_ok('/items?limit=1').status_is(200).json_has('/0').json_hasnt('/1')
    t.patch_ok('/items/2', json={'price': -1}).status_is(422).json_is('/errors/0', '/price: Less than the minimum 0.')
    t.patch_ok('/items/2', json={'price': 5}).status_is(200).json_is('/price', 5)
    t.get_ok('/items/9').status_is(404).content_type_like(r'json')
    t.delete_ok('/items/2').status_is(204).content_is('')
    t.get_ok('/items/2').status_is(404)

with subtest('JSON-RPC'):
    t = load('rpc.py')
    t.post_ok('/rpc', json={'jsonrpc': '2.0', 'method': 'subtract', 'params': [42, 23], 'id': 1}).status_is(200)
    t.json_is({'jsonrpc': '2.0', 'result': 19, 'id': 1})
    t.post_ok('/rpc', json={'jsonrpc': '2.0', 'method': 'subtract', 'params': [42, 'x'], 'id': 2}).status_is(200)
    t.json_is('/error/code', -32602).json_is('/error/data', '/subtrahend: Expected integer - got string.')
    t.get_ok('/difference/10/3').status_is(200).json_is({'difference': 7})

done_testing()
