from Pyjo.Test import *

import importlib
import importlib.util
import os
import sys
import tempfile


# The examples of Pyjo.HelloWorld of examples/servers, on the port 3000 replaced by a free one: natively, and with the
# servers of the dependency group "servers" when it is installed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
ServerProcess = importlib.import_module('ServerProcess')

EXAMPLES = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', 'servers')
VARIANTS = [
    ('natively', 'hello_world.py', None),
    ('uvicorn', 'hello_world_uvicorn.py', 'uvicorn'),
    ('Werkzeug', 'hello_world_werkzeug.py', 'werkzeug'),
]

with tempfile.TemporaryDirectory() as dir:
    for name, example, module in VARIANTS:
        if module is not None and not importlib.util.find_spec(module):
            continue

        with subtest(name):
            with open(os.path.join(EXAMPLES, example)) as file:
                source = file.read()
            script = os.path.join(dir, example)
            port = ServerProcess.free_port()
            with open(script, 'w') as file:
                file.write(source.replace('3000', str(port)))

            server = ServerProcess.Server(dir, [sys.executable, script], port)
            try:
                status, headers, body = server.request('GET', '/')
                is_ok(status, 200, 'right status')
                is_ok(body, b'Your Pyjo is working!', 'right content')
            except Exception:
                diag(server.output())
                raise
            finally:
                server.close()

done_testing()
