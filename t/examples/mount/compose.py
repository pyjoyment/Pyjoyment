import Pyjo.Test.Pyjo

from Pyjo.File import curfile
from Pyjo.Test import *

import os
import sys


if os.name == 'nt':
    plan(skip_all='Lambda functions need pipes that the event loop watches, which Windows does not have')

# The application of examples/mount/compose.py, which the test loads without starting a server, with the directory of the
# script in sys.path, as Python has it when it runs the script, so that hello_wsgi.py and hello_asgi.py are found
examples = curfile().dirname().dirname().dirname().sibling('examples', 'mount')
sys.path.insert(0, examples.to_str())
t = Pyjo.Test.Pyjo.new(examples.child('compose.py'))

with subtest('Pyjoyment'):
    t.get_ok('/').status_is(200).content_is('I ♥ Pyjoyment!')

with subtest('WSGI'):
    t.get_ok('/wsgi/foo').status_is(200).content_type_is('text/plain').content_is('Hello WSGI at /wsgi for /foo!')

with subtest('ASGI'):
    t.get_ok('/asgi/foo').status_is(200).content_type_is('text/plain').content_is('Hello ASGI at /asgi for /asgi/foo!')
    t.get_ok('/asgi/events').status_is(200).content_type_is('text/event-stream')
    t.content_is('data: 0\n\ndata: 1\n\ndata: 2\n\n')

with subtest('Lambda'):
    t.get_ok('/lambda/foo').status_is(200).content_type_is('text/plain')
    t.content_is('Hello Lambda at lambda for /lambda/foo!')

with subtest('Not found'):
    t.get_ok('/foo').status_is(404)

done_testing()
