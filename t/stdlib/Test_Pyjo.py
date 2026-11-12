import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *

import os
import socket
import subprocess
import sys
import textwrap


with subtest('Context manager'):
    app = Pyjoyment.new()
    app.routes.any('/', {'text': 'works'})
    with Pyjo.Test.Pyjo.new(app) as t:
        t.get_ok('/').content_is('works')
        port = t.ua.server.url().port
    throws_ok(lambda: socket.create_connection(('127.0.0.1', port)), ConnectionRefusedError, 'server closed at the end')

with subtest('close'):
    app = Pyjoyment.new()
    app.routes.any('/', {'text': 'works'})
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/').content_is('works')
    port = t.ua.server.url().port
    t.close()
    throws_ok(lambda: socket.create_connection(('127.0.0.1', port)), ConnectionRefusedError, 'server closed')

with subtest('unittest'):
    # A module of unittest.TestCase, which python -m unittest runs as a module of tests of an application
    root = Pyjo.File.curfile().dirname().dirname().dirname().to_str()
    with Pyjo.File.tempdir() as tmp:
        tmp.child('test_app.py').spurt(
            textwrap.dedent("""\
                import Pyjo.IOLoop
                import Pyjo.Promise
                import Pyjo.Test
                import Pyjo.Test.Pyjo
                import Pyjoyment

                import unittest


                def build_app():
                    app = Pyjoyment.new()
                    app.log.level = 'fatal'
                    app.plugin('Health', checks={'timer': lambda c: Pyjo.Promise.timer(0.01)})
                    app.routes.get('/', {'text': 'Hello'})

                    async def later(c):
                        await Pyjo.Promise.timer(0.01)
                        c.render(text='Later')

                    app.routes.get('/later').to(cb=later)
                    return app


                def setUpModule():
                    unittest.enterModuleContext(Pyjo.Test.raise_failures())


                class TestApp(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls):
                        cls.t = cls.enterClassContext(Pyjo.Test.Pyjo.new(build_app()))

                    def test_index(self):
                        self.t.get_ok('/').status_is(200).content_is('Hello')

                    def test_promise(self):
                        self.t.get_ok('/later').status_is(200).content_is('Later')
                        self.t.get_ok('/readyz').status_is(200)

                    def test_wrong_content(self):
                        self.t.get_ok('/').status_is(200).content_is('Bye')

                    def test_skip_all(self):
                        Pyjo.Test.plan(skip_all='not today')

                    def test_subtests(self):
                        with Pyjo.Test.subtest('Index'):
                            self.t.get_ok('/').status_is(200)
                        with self.subTest(path='/later'):
                            self.t.get_ok('/later').status_is(200)


                class TestAsync(unittest.IsolatedAsyncioTestCase):
                    async def test_blocking(self):
                        with Pyjo.Test.Pyjo.new(build_app()) as t:
                            # A reactor of the event loop of asyncio runs in the one of the test
                            if type(Pyjo.IOLoop.singleton.reactor).new().is_running:
                                with self.assertRaisesRegex(RuntimeError, 'Blocking request in a running event loop'):
                                    t.get_ok('/')
                            else:
                                t.get_ok('/').status_is(200)
            """)
        )
        env = dict(os.environ, PYTHONPATH=root)
        p = subprocess.run(
            [sys.executable, '-m', 'unittest', '-v', 'test_app'],
            cwd=tmp.to_str(),
            capture_output=True,
            text=True,
            env=env,
        )
    err = p.stderr.replace('\r\n', '\n')
    like_ok(err, r'(?m)^test_index \(test_app\.TestApp\.test_index\) \.\.\. ok$', 'passed')
    like_ok(err, r'(?m)^test_promise \(test_app\.TestApp\.test_promise\) \.\.\. ok$', 'responses of promises')
    like_ok(err, r'(?m)^test_subtests \(test_app\.TestApp\.test_subtests\) \.\.\. ok$', 'subtests')
    like_ok(err, r"(?m)^test_skip_all \(test_app\.TestApp\.test_skip_all\) \.\.\. skipped 'not today'$", 'skipped')
    like_ok(err, r'(?m)^test_wrong_content \(test_app\.TestApp\.test_wrong_content\) \.\.\. FAIL$', 'failed')
    like_ok(
        err, r"(?m)^AssertionError: Failed test 'exact match for content'\n +got: 'Hello'\n +expected: 'Bye'$", 'why'
    )
    like_ok(err, r'(?m)^test_blocking \(test_app\.TestAsync\.test_blocking\) \.\.\. ok$', 'IsolatedAsyncioTestCase')
    like_ok(err, r'(?m)^FAILED \(failures=1, skipped=1\)$', 'right summary')
    unlike_ok(err, r'ResourceWarning', 'closed at the end of the class')
    is_ok(p.stdout, '', 'no TAP')
    is_ok(p.returncode, 1, 'right exit status')

done_testing()
