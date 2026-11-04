import Pyjo.IOLoop
import Pyjo.Reactor
import Pyjo.Reactor.Asyncio
import Pyjo.Server.Daemon
import Pyjo.UserAgent
import Pyjoyment

from Pyjo.Test import *

import asyncio
import gc
import importlib
import os
import sys
import tempfile
import threading


# The garbage collector of Python frees the objects in cycles at any allocation, even in the middle of what the event
# loop does, where Perl frees an object when its last reference goes, at the end of a statement; the finalizers of the
# objects that hold the resources of an event loop clean up at once anywhere else, and at the next tick there

app = Pyjoyment.new()
app.log.level = 'fatal'
app.routes.any('/', {'text': 'works'})


def daemon_in_cycle():
    daemon = Pyjo.Server.Daemon.new(listen=['http://127.0.0.1'], silent=True).start()
    daemon.cycle = daemon
    return daemon.acceptors[0]


with subtest('A finalizer outside of the event loop cleans up at once'):
    id = daemon_in_cycle()
    ok(Pyjo.IOLoop.acceptor(id), 'acceptor has been added')
    gc.collect()
    ok(not Pyjo.IOLoop.acceptor(id), 'acceptor has been removed')

with subtest('A finalizer in the event loop cleans up after the callback'):
    id = daemon_in_cycle()
    seen = []

    def collect(loop):
        gc.collect()
        seen.append(bool(Pyjo.IOLoop.acceptor(id)))

        def later(loop):
            seen.append(bool(Pyjo.IOLoop.acceptor(id)))
            loop.stop()

        loop.timer(0.05, later)

    Pyjo.IOLoop.next_tick(collect)
    Pyjo.IOLoop.start()
    is_deeply_ok(seen, [True, False], 'acceptor removed after the callback')

with subtest('A finalizer in another thread cleans up at the next tick'):
    id = daemon_in_cycle()
    # The garbage collector runs in the thread that allocates, as a thread of name resolution, while the main thread
    # may be in the middle of what the event loop does
    thread = threading.Thread(target=gc.collect)
    thread.start()
    thread.join()
    ok(Pyjo.IOLoop.acceptor(id), 'acceptor is still there')
    Pyjo.IOLoop.timer(0.05, lambda loop: loop.stop())
    Pyjo.IOLoop.start()
    ok(not Pyjo.IOLoop.acceptor(id), 'acceptor removed at the next tick')

with subtest('User agents in cycles, which the garbage collector frees all the time'):
    # PyPy has no thresholds, its garbage collector runs when it does
    threshold = gc.get_threshold() if hasattr(gc, 'get_threshold') else None
    if threshold is not None:
        gc.set_threshold(1, 1, 1)
    errors = []
    try:
        for _ in range(30):
            try:
                ua = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
                ua.cycle = ua
                ua.server.app = app
                ua.server.url()
                if (text := ua.get('/').res.text) != 'works':
                    errors.append(text)
            except Exception as e:
                errors.append(f'{type(e).__name__}: {e}')
    finally:
        if threshold is not None:
            gc.set_threshold(*threshold)
    is_deeply_ok(errors, [], 'no errors')
    del ua
    gc.collect()

with subtest('A finalizer below a frame of a reactor of another distribution or of its event loop cleans up later'):
    # A reactor and an event loop in another directory than Pyjoyment, as of a distribution installed editable
    with tempfile.TemporaryDirectory() as dir:
        os.mkdir(os.path.join(dir, 'pyjo_test_loop'))
        files = {
            'pyjo_test_loop/__init__.py': 'def run(cb):\n    return cb()\n',
            'pyjo_test_other.py': 'def run(cb):\n    return cb()\n',
            'pyjo_test_reactor.py': (
                'import Pyjo.Reactor.Poll\n\n\n'
                'class Pyjo_Reactor_Test(Pyjo.Reactor.Poll.object):\n'
                "    event_loop_modules = ('pyjo_test_loop', 'pyjo_test_unloaded')\n\n"
                '    def call(self, cb):\n'
                '        return cb()\n'
            ),
        }
        for name, content in files.items():
            with open(os.path.join(dir, name), 'w') as fh:
                fh.write(content)
        sys.path.insert(0, dir)
        try:
            loop = importlib.import_module('pyjo_test_loop')
            other = importlib.import_module('pyjo_test_other')
            reactor = importlib.import_module('pyjo_test_reactor').Pyjo_Reactor_Test.new()
            cleaned = []

            def finalizer(name):
                Pyjo.Reactor._finalize(lambda: cleaned.append(name), reactor)

            finalizer('outside')
            is_deeply_ok(cleaned, ['outside'], 'cleaned up at once outside of the event loop')

            reactor.call(lambda: finalizer('reactor'))
            loop.run(lambda: finalizer('loop'))
            other.run(lambda: finalizer('other'))
            is_deeply_ok(cleaned, ['outside', 'other'], 'cleaned up at once in a module of no event loop')
            Pyjo.Reactor._drain()
            is_deeply_ok(cleaned, ['outside', 'other', 'reactor', 'loop'], 'cleaned up later in both')
        finally:
            sys.path.remove(dir)
            for name in ('pyjo_test_loop', 'pyjo_test_other', 'pyjo_test_reactor'):
                sys.modules.pop(name, None)

with subtest('A finalizer below a frame of asyncio with a reactor of asyncio cleans up later'):
    loop = asyncio.new_event_loop()
    try:
        reactor = Pyjo.Reactor.Asyncio.new(loop=loop)
        cleaned = []

        def finalizer():
            Pyjo.Reactor._finalize(lambda: cleaned.append('asyncio'), reactor)

        loop.call_soon(finalizer)
        loop.call_soon(loop.stop)
        loop.run_forever()
        is_deeply_ok(cleaned, [], 'not cleaned up in the event loop')
        Pyjo.Reactor._drain()
        is_deeply_ok(cleaned, ['asyncio'], 'cleaned up later')
    finally:
        loop.close()

done_testing()
