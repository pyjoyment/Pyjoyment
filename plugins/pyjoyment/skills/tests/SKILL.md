---
name: tests
description: Test code that uses Pyjoyment with Pyjo.Test and Pyjo.Test.Pyjo, ported from Test::More and Test::Mojo. Use for test scripts that print TAP with subtests and assertions as is_ok, like_ok and is_deeply_ok, requests to an application without a server with get_ok, post_ok, status_is, json_is and text_is, WebSockets and Server-Sent Events, the harness pyjo-prove, tests of pytest with the fixture t, and the tests of unittest.TestCase that a project has already, as the ones of Django.
---

# Tests

A test of Pyjoyment is a script that prints [TAP](https://testanything.org/),
as a test of Perl does: `Pyjo.Test` has the functions of `Test::More`, with
`_ok` where the name would be a keyword of Python, and `Pyjo.Test.Pyjo` the
chains of `Test::Mojo`, which request the application without a server, in
the event loop of the test. `pyjo-prove` runs the scripts, as `prove` does,
and pytest runs them too, with its own tests next to them.

## An application and its test script

```python
# app.py
from Pyjoyment.Lite import *


app.secrets = ['Change this secret']


@get('/')
def index(c):
    c.render(inline='<h1>Hello <%= name %>!</h1>', name=c.param('name') or 'World')


@post('/login')
def login(c):
    v = c.validation()
    v.required('user').size(1, 20)
    if v.has_error():
        return c.render(json={'error': 'invalid user'}, status=400)
    c.session({'user': v.param('user')})
    c.render(json={'user': v.param('user')})


@get('/me')
def me(c):
    c.render(json={'user': c.session('user')})


@websocket('/echo')
def echo(c):
    c.on('message', lambda c, msg: c.send(f'echo: {msg}'))


app.start()
```

```python
# t/basic.py
import Pyjo.Test.Pyjo

from Pyjo.File import curfile
from Pyjo.Test import *


# The application of the script next to the directory of the tests, without a server
t = Pyjo.Test.Pyjo.new(curfile().dirname().sibling('app.py'))

with subtest('Page'):
    t.get_ok('/').status_is(200).text_is('h1', 'Hello World!')
    t.get_ok('/?name=Sara').status_is(200).content_like(r'Hello Sara')

# The test object keeps the cookies, as a browser does
with subtest('Session'):
    t.post_ok('/login', form={'user': ''}).status_is(400).json_is('/error', 'invalid user')
    t.post_ok('/login', form={'user': 'joe'}).status_is(200).json_is({'user': 'joe'})
    t.get_ok('/me').status_is(200).json_is('/user', 'joe')

with subtest('WebSocket'):
    t.websocket_ok('/echo').send_ok('hi').message_ok().message_is('echo: hi').finish_ok()

with subtest('Values'):
    is_ok(1 + 1, 2, 'sum')
    is_deeply_ok({'a': [1, 2]}, {'a': [1, 2]}, 'structure')
    like_ok('Hello World', r'World', 'match')

done_testing()
```

- An assertion returns a result, true or false, as `ok` of `Test::More`, and
  the chains of `Pyjo.Test.Pyjo` continue after a failure, which they report
  with the request and the response.
- `Pyjo.Test.Pyjo.new()` takes the path of a script of `Pyjoyment.Lite`, as
  above, the name of the class of an application, as `'MyApp'`, an
  application, or nothing in a script that is the application itself.
- The requests: `get_ok`, `post_ok` (`form=`, `json=`, a dict of headers,
  the body), `put_ok`, `patch_ok`, `delete_ok`, `head_ok`, `options_ok`;
  the response: `status_is`, `header_is`, `content_is`, `content_like`,
  `json_is` with a JSON Pointer or the whole document, `json_has`, `text_is`
  and `element_exists` with a CSS selector; `t.tx` is the last transaction.
- WebSockets: `websocket_ok`, `send_ok`, `message_ok`, `message_is`,
  `json_message_is`, `finish_ok`; Server-Sent Events: `get_sse_ok`, `sse_ok`,
  `sse_text_is`, `sse_finished_ok`.

## pytest

```python
# tests/conftest.py
import pytest

from Pyjo.File import curfile


# The application of the fixture t
@pytest.fixture
def app():
    return curfile().dirname().sibling('app.py')
```

```python
# tests/test_app.py
def test_index(t):
    t.get_ok('/').status_is(200).text_is('h1', 'Hello World!')


def test_login(t):
    t.post_ok('/login', form={'user': 'joe'}).status_is(200)
    t.get_ok('/me').status_is(200).json_is('/user', 'joe')
```

- The plugin of pytest comes with Pyjoyment: pytest runs each script of `t`
  as a test of its own, and the fixture `t` is a `Pyjo.Test.Pyjo` of the
  fixture `app`, where an assertion that fails raises `AssertionError`.

## Tests of unittest that a project has

```python
# tests/test_existing.py
import Pyjo.Test
import Pyjo.Test.Pyjo

from Pyjo.File import curfile

import unittest


# The assertions raise AssertionError in this module, and print TAP again after it
def setUpModule():
    unittest.enterModuleContext(Pyjo.Test.raise_failures())


# The application among the tests that the project runs with unittest already, with one tester for the class
class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = cls.enterClassContext(Pyjo.Test.Pyjo.new(curfile().dirname().sibling('app.py')))

    def test_index(self):
        self.t.get_ok('/').status_is(200).text_is('h1', 'Hello World!')
```

- This is for a project whose tests are of `unittest.TestCase` already, as
  a project of Django with `manage.py test`: the routes of Pyjoyment in front
  of it are tested where its other tests are. New tests are scripts of `t` or
  tests of pytest, which runs the modules of unittest too.
- Without `raise_failures()`, a failure prints TAP, which unittest does not
  read: it reports `OK`, and the process ends with 254.
- A request of `Pyjo.Test.Pyjo` blocks until the response, so the test is a
  method of `unittest.TestCase`, not of `IsolatedAsyncioTestCase`, whose
  running event loop it cannot wait in.

## Commands

```sh
pyjo-prove -l -r t                   # the scripts of t, with the current directory in PYTHONPATH
pyjo-prove -l -v t/basic.py          # one script, with its TAP
pyjo-prove -l -j 4 -r t              # four scripts at a time
python t/basic.py                    # one script, without the harness
pytest                               # the scripts of t and the tests of pytest
python -m unittest discover -s tests # the tests of unittest
PYTHONDEVMODE=1 pyjo-prove -l -r t   # and the ResourceWarning of what a test leaves open
```

## Mistakes

- A test script ends with `done_testing()`, or the harness reports that it
  has no plan.
- The test client of another framework, or `requests` against a server that
  the test starts, has no event loop of the application: `Pyjo.Test.Pyjo`
  requests it in the event loop of the test.
- A `Pyjo.UserAgent` of its own, with `ua.server.app = app`, runs an event
  loop of its own, where a response that a promise of the application
  settles, as `/readyz` of `Health`, does not come on `Pyjo.Reactor.Poll`:
  `Pyjo.Test.Pyjo` has its user agent on `Pyjo.IOLoop.singleton`, as a user
  agent of `ioloop=Pyjo.IOLoop.singleton` does.
- A test does not request remote hosts: the event `start` of the user agent of
  the application sends a request to an application of the test instead, as
  `t.app.ua.on('start', lambda ua, tx: ...)` with a new host and port of
  `tx.req.url`.
- `t.get_ok(...)` of a stream of Server-Sent Events gives an empty body: a
  stream is tested with `get_sse_ok` and `sse_ok`.
- `throws_ok` with a message or a pattern catches an `Exception` only:
  `SystemExit` of a command is checked with the class, `throws_ok(cb,
  SystemExit)`. The text of a `Pyjo.Exception` ends with a new line, so its
  message is checked with a pattern, `re.compile(r'^Not found')`.
- A test that imports a script of `Pyjoyment.Lite` runs its `app.start()`:
  `Pyjo.Server.new().load_app('app.py')` gives its application without a
  command. A test named as the module that it imports, `t/app.py` for
  `app.py` with `-l`, imports itself.
- The log of the application is checked with `app.log.capture('info')`,
  whose messages have the format of the log, with the time: `app.log.format =
  lambda time, level, *lines: ...` makes them exact.

## Documentation

- Testing: https://pyjoyment.readthedocs.io/en/stable/guides/testing.html
- Pyjo.Test.Pyjo: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_Test_Pyjo.html
- Pyjo.Test: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_Test.html
- The plugin of pytest: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_Test_pytest_plugin.html
