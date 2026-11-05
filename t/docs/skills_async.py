import Pyjo.File
import Pyjo.Test.Pyjo

from Pyjo.Test import *

import hashlib
import importlib
import os
import sys


# The code of plugins/pyjoyment/skills/async/SKILL.md, each application in a file of its own, as a coding agent writes
# it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Skills = importlib.import_module('Skills')

code = Skills.blocks('async')
is_ok(len(code), 4, 'four applications')

tmp = Pyjo.File.tempdir()


def load(n):
    file = tmp.child(f'app{n}.py').spew(code[n])
    t = Pyjo.Test.Pyjo.new(file)
    t.app.log.level = 'fatal'
    # The user agent of the application requests its relative URLs from it, as from the only application of its process,
    # where Pyjoyment.Lite makes the first application of the process the one of all the user agents
    t.app.ua.server.app = t.app
    return t


with subtest('Waiting in an action'):
    t = load(0)
    t.get_ok('/api/7').status_is(200).json_is({'n': 7})
    t.get_ok('/sequential').status_is(200).json_is([1, 2])
    t.get_ok('/concurrent').status_is(200).json_is([1, 2])
    t.get_ok('/many').status_is(200).json_is([1, 2, 3, 4, 5, 6])
    t.get_ok('/limited').status_is(200).json_is({'n': 1})
    t.get_ok('/limited?limit=0.01').status_is(504).json_is({'error': 'Too slow'})

with subtest('Code that blocks'):
    if not hasattr(os, 'fork'):
        skip('needs os.fork', 1)
    else:
        t = load(1)
        digest = hashlib.pbkdf2_hmac('sha256', b'secret', b'salt', 100_000).hex()
        t.get_ok('/hash?password=secret').status_is(200).content_is(digest)

with subtest('Code for a script and an action'):
    t = load(2)
    t.get_ok('/data').status_is(200).json_is({'answer': 42})
    t.get_ok('/data').status_is(200).json_is({'answer': 42})

    # The same steps blocking, as a script runs them, with the function of the loaded application
    from Pyjo.Steps import Steps

    path = tmp.child('app2.py').to_abs().to_str()
    module = next(m for m in list(sys.modules.values()) if getattr(m, '__file__', None) == path)
    is_ok(Steps(module.fetch(t.app.ua, '/api')).run(t.app.ua), {'answer': 42}, 'blocking')

with subtest('Callbacks and timers'):
    t = load(3)
    t.get_ok('/delayed').status_is(200)
    ok(t.tx.res.json('/ticks') >= 1, 'background work')
    t.get_ok('/callback').status_is(200)
    ok(t.tx.res.json('/ticks') >= 1, 'response of the callback')

done_testing()
