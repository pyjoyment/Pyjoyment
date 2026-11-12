"""
Pyjo.Test.Pyjo - Testing Pyjo
=============================
::

    from Pyjo.Test import *

    import Pyjo.Test.Pyjo

    t = Pyjo.Test.Pyjo.new('MyApp')

    # HTML/XML
    t.get_ok('/welcome').status_is(200).text_is('div#message', 'Hello!')

    # JSON
    (
        t.post_ok('/search.json', form={'q': 'Python'})
        .status_is(200)
        .header_is('Server', 'Pyjoyment (Python)')
        .header_isnt('X-Bender', 'Bite my shiny metal ass!')
        .json_is('/results/4/title', 'Python rocks!')
        .json_like('/results/7/title', re.compile(r'Python'))
    )

    # WebSocket
    t.websocket_ok('/echo').send_ok('hello').message_ok().message_is('echo: hello').finish_ok()

    # Server-Sent Events (SSE)
    (
        t.get_sse_ok('/events')
        .status_is(200)
        .sse_ok()
        .sse_type_is('message')
        .sse_text_is('hello pyjo')
        .sse_finish_ok()
    )

    done_testing()

:mod:`Pyjo.Test.Pyjo` is a test user agent based on :mod:`Pyjo.UserAgent`, it
is usually used together with :mod:`Pyjo.Test` to test :mod:`Pyjoyment`
applications. Just run your tests with :mod:`Pyjo.Prove`. ::

    $ python -m Pyjo.Prove -l -v
    $ python -m Pyjo.Prove -l -v t/foo.py

If it is not already defined, the ``PYJO_LOG_LEVEL`` environment variable
will be set to ``trace`` or ``fatal``, depending on the value of the
``PYJO_HARNESS_IS_VERBOSE`` environment variable, which
``python -m Pyjo.Prove -v`` sets, or without it of ``HARNESS_IS_VERBOSE``,
which Perl's ``prove -v`` sets. And to make it easier to test HTTPS/WSS web
services :attr:`Pyjo.UserAgent.Pyjo_UserAgent.insecure` will be activated by
default for :attr:`~Pyjo_Test_Pyjo.ua`.

The end of a ``with`` block closes the connections and the servers of its
:attr:`~Pyjo_Test_Pyjo.ua`.

A test of :class:`unittest.TestCase` makes it once for its class, after
:func:`Pyjo.Test.raise_failures`, with
:meth:`~unittest.TestCase.enterClassContext`, which closes it at the end of
the class: ::

    import unittest

    import Pyjo.Test
    import Pyjo.Test.Pyjo


    def setUpModule():
        unittest.enterModuleContext(Pyjo.Test.raise_failures())


    class TestMyApp(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.t = cls.enterClassContext(Pyjo.Test.Pyjo.new('MyApp'))

        def test_welcome(self):
            self.t.get_ok('/welcome').status_is(200).text_is('div#message', 'Hello!')

A request of a test blocks, as it runs the event loop until the response, so
the test is a method of a :class:`unittest.TestCase`: in the running event
loop of a :class:`unittest.IsolatedAsyncioTestCase`, the default reactor
raises ``Blocking request in a running event loop``.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Test::Mojo <https://github.com/mojolicious/mojo/blob/v9.49/lib/Test/Mojo.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Base
import Pyjo.File
import Pyjo.IOLoop
import Pyjo.JSON.Pointer
import Pyjo.Server
import Pyjo.Test
import Pyjo.UserAgent

from Pyjo.JSON import j
from Pyjo.Util import decode

import os
import re

from collections.abc import Callable
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self, cast


if TYPE_CHECKING:
    import Pyjo.Transaction.HTTP


# Silent or loud tests
# Unlike Mojolicious: PYJO_HARNESS_IS_VERBOSE of Pyjo.Prove, and HARNESS_IS_VERBOSE of prove without it
if not os.environ.get('PYJO_LOG_LEVEL'):
    verbose = os.environ.get('PYJO_HARNESS_IS_VERBOSE', os.environ.get('HARNESS_IS_VERBOSE'))
    os.environ['PYJO_LOG_LEVEL'] = 'trace' if verbose else 'fatal'

# Not in Mojolicious: pytest leaves the frames of this module out of the traceback of a failed test, as those of
# Pyjo.Test
__tracebackhide__ = Pyjo.Test.__tracebackhide__


class Pyjo_Test_Pyjo(Pyjo.Base.object):
    """
    :mod:`Pyjo.Test.Pyjo` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(self, app: Any = None, config: dict[str, Any] | None = None, /) -> None:
        """::

            t = Pyjo.Test.Pyjo.new()
            t = Pyjo.Test.Pyjo.new('MyApp')
            t = Pyjo.Test.Pyjo.new('MyApp', {'foo': 'bar'})
            t = Pyjo.Test.Pyjo.new(Pyjo.File.new('/path/to/myapp.py'))
            t = Pyjo.Test.Pyjo.new(Pyjo.File.new('/path/to/myapp.py'), {'foo': 'bar'})
            t = Pyjo.Test.Pyjo.new(MyApp.new())
            t = Pyjo.Test.Pyjo.new(MyApp.new(), {'foo': 'bar'})

        Construct a new :mod:`Pyjo.Test.Pyjo` object. In addition to a class
        name or :mod:`Pyjo.File` object pointing to the application script,
        you can pass along a dict with configuration values that will be used
        to override the application configuration. The special configuration
        value ``config_override`` will be set in
        :meth:`Pyjoyment.Pyjoyment_App.config` as well, which is used to
        disable configuration plugins for tests. ::

            # Load application script relative to the "t" directory
            from Pyjo.File import curfile

            t = Pyjo.Test.Pyjo.new(curfile().dirname().sibling('myapp.py'))
        """
        super().__init__()

        self.handler: Callable[..., Any] = _handler
        """::

            cb = t.handler
            t.handler = lambda name, *args: ...

        A callback to connect :mod:`Pyjo.Test.Pyjo` with :mod:`Pyjo.Test`,
        which gets the name of a function of ``Test::More``, as ``is``, and
        its arguments. ::

            def handler(name, *args):
                return {'is': is_ok, 'like': like_ok, 'ok': ok}[name](*args)

            t.handler = handler
        """

        self.message: list[Any] | None = None
        """::

            msg = t.message
            t.message = ['text', b'bytes']

        Current WebSocket message represented as a list containing the frame
        type and payload. ::

            # More specific tests
            from Pyjo.JSON import decode_json

            hash = decode_json(t.message[1])
            is_ok(type(hash), dict, 'right reference')
            is_ok(hash['foo'], 'bar', 'right value')

            # Test custom message
            t.message = ['binary', b'bytes']
            t.json_message_has('/foo/bar').json_message_hasnt('/bar').json_message_is('/foo/baz', {'yada': [1, 2, 3]})
        """

        self.sse: dict[str, Any] | None = None
        """::

            event = t.sse
            t.sse = {'type': 'message', 'text': 'working!'}

        Current Server-Sent Event (SSE) represented as a dict. Note that this
        attribute is **EXPERIMENTAL** and may change without warning!
        """

        self.success: bool | None = None
        """::

            boolean = t.success
            t.success = boolean

        True if the last test was successful. ::

            # Build custom tests
            def location_is(t, value, desc=''):
                desc = desc or f'Location: {value}'
                t.success = bool(is_ok(t.tx.res.headers.location, value, desc))
                return t

            t.get_ok('/').status_is(302)
            location_is(t, 'https://mojolicious.org').otherwise(lambda t: diag('Must have been Joel!'))
        """

        self.tx: Pyjo.Transaction.HTTP.object | None = None
        """::

            tx = t.tx
            t.tx = Pyjo.Transaction.HTTP.new()

        Current transaction, usually a :mod:`Pyjo.Transaction.HTTP` or
        :mod:`Pyjo.Transaction.WebSocket` object. ::

            # More specific tests
            is_ok(t.tx.res.json()['foo'], 'bar', 'right value')
            ok(t.tx.res.content.is_multipart, 'multipart content')
            is_ok(t.tx.previous.res.code, 302, 'right status')
        """

        self._ua: Pyjo.UserAgent.object | None = None
        self._finished: list[Any] | None = None
        self._messages: list[list[Any]] = []
        self._sse_events: list[dict[str, Any]] = []
        self._sse_finished: bool | None = None

        if app is None:
            return

        cfg: dict[str, Any] = {'config': {'config_override': 1, **config}} if config is not None else {}
        if isinstance(app, (str, type)):
            self.app = Pyjo.Server.new().build_app(app, **cfg)
        elif isinstance(app, (Pyjo.File.object, os.PathLike)):
            self.app = Pyjo.Server.new().load_app(app, **cfg)  # pyright: ignore[reportUnknownArgumentType]
        else:
            if cfg:
                app.config(cfg['config'])
            self.app = app

    # Not in Mojolicious: a context manager, which closes the connections and the servers of its user agent where the
    # block ends, as PyPy frees the object only when its garbage collector runs
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    @property
    def ua(self) -> Pyjo.UserAgent.object:
        """::

            ua = t.ua
            t.ua = Pyjo.UserAgent.new()

        User agent used for testing, defaults to a :mod:`Pyjo.UserAgent`
        object. ::

            # Allow redirects
            t.ua.max_redirects = 10
            t.get_ok('/redirect').status_is(200).content_like(re.compile(r'redirected'))

            # Switch protocol from HTTP to HTTPS
            t.ua.server.url('https')
            t.get_ok('/secure').status_is(200).content_like(re.compile(r'secure'))

            # Use absolute URL for request with Basic authentication
            url = t.ua.server.url().set(userinfo='sri:secr3t').set(path='/secrets.json')
            t.post_ok(url, json={'limit': 10}).status_is(200).json_is('/1/content', 'Pyjo rocks!')

            # Customize all transactions (including followed redirects)
            t.ua.on('start', lambda ua, tx: tx.req.headers.set(accept_language='en-US'))
            t.get_ok('/hello').status_is(200).content_like(re.compile(r'Howdy'))
        """
        if self._ua is None:
            self._ua = Pyjo.UserAgent.new(insecure=True, ioloop=Pyjo.IOLoop.singleton)
        return self._ua

    @ua.setter
    def ua(self, value: Pyjo.UserAgent.object) -> None:
        self._ua = value

    @property
    def app(self) -> Any:
        """::

            app = t.app
            t.app = Pyjoyment.new()

        Access application with :attr:`Pyjo.UserAgent.Server.Pyjo_UserAgent_Server.app`. ::

            # Change log level
            t.app.log.level = 'fatal'

            # Test application directly
            is_ok(t.app.defaults('foo'), 'bar', 'right value')
            ok(t.app.routes.find('echo').is_websocket, 'WebSocket route')
            c = t.app.build_controller()
            ok(c.render(template='foo'), 'rendering was successful')
            is_ok(c.res.code, 200, 'right status')
            is_ok(c.res.body, b'Foo!', 'right content')

            # Change application behavior
            @t.app.hook('before_dispatch')
            def before_dispatch(c):
                if c.req.url.path.contains('/user'):
                    c.render(text='This request did not reach the router.')

            t.get_ok('/user').status_is(200).content_like(re.compile(r'not reach the router'))

            # Extract additional information
            stash = {}
            t.app.hook('after_dispatch', lambda c: stash.update(c.stash()))
            t.get_ok('/hello').status_is(200)
            is_ok(stash['foo'], 'bar', 'right value')
        """
        return self.ua.server.app

    @app.setter
    def app(self, value: Any) -> None:
        self.ua.server.app = value

    def attr_is(self, selector: str, attr: str, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.attr_is('img.cat', 'alt', 'Grumpy cat')
            t = t.attr_is('img.cat', 'alt', 'Grumpy cat', 'right alt text')

        Checks text content of attribute with :meth:`Pyjo.DOM.Pyjo_DOM.attr` at
        the CSS selectors first matching HTML/XML element for exact match with
        :meth:`Pyjo.DOM.Pyjo_DOM.at`.
        """
        desc = _desc(desc, f'exact match for attribute "{attr}" at selector "{selector}"')
        return self.test('is', self._attr(selector, attr), value, desc)

    def attr_isnt(self, selector: str, attr: str, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.attr_isnt('img.cat', 'alt', 'Calm cat')
            t = t.attr_isnt('img.cat', 'alt', 'Calm cat', 'different alt text')

        Opposite of :meth:`attr_is`.
        """
        desc = _desc(desc, f'no match for attribute "{attr}" at selector "{selector}"')
        return self.test('isnt', self._attr(selector, attr), value, desc)

    def attr_like(self, selector: str, attr: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.attr_like('img.cat', 'alt', re.compile(r'Grumpy'))
            t = t.attr_like('img.cat', 'alt', re.compile(r'Grumpy'), 'right alt text')

        Checks text content of attribute with :meth:`Pyjo.DOM.Pyjo_DOM.attr` at
        the CSS selectors first matching HTML/XML element for similar match
        with :meth:`Pyjo.DOM.Pyjo_DOM.at`.
        """
        desc = _desc(desc, f'similar match for attribute "{attr}" at selector "{selector}"')
        return self.test('like', self._attr(selector, attr), regex, desc)

    def attr_unlike(self, selector: str, attr: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.attr_unlike('img.cat', 'alt', re.compile(r'Calm'))
            t = t.attr_unlike('img.cat', 'alt', re.compile(r'Calm'), 'different alt text')

        Opposite of :meth:`attr_like`.
        """
        desc = _desc(desc, f'no similar match for attribute "{attr}" at selector "{selector}"')
        return self.test('unlike', self._attr(selector, attr), regex, desc)

    # Not in Mojolicious: the release of the user agent, which Perl does in DESTROY, also at the end of a with block
    def close(self) -> None:
        """::

            t.close()

        Close the connections and the servers of :attr:`ua`, as the end of a
        ``with`` block does.
        """
        if self._ua is not None:
            self._ua.close()

    def content_is(self, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.content_is('working!')
            t = t.content_is('working!', 'right content')

        Check response content for exact match after retrieving it from
        :attr:`Pyjo.Message.Pyjo_Message.text`.
        """
        return self.test('is', self._tx.res.text, value, _desc(desc, 'exact match for content'))

    def content_isnt(self, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.content_isnt('working!')
            t = t.content_isnt('working!', 'different content')

        Opposite of :meth:`content_is`.
        """
        return self.test('isnt', self._tx.res.text, value, _desc(desc, 'no match for content'))

    def content_like(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.content_like(re.compile(r'working!'))
            t = t.content_like(re.compile(r'working!'), 'right content')

        Check response content for similar match after retrieving it from
        :attr:`Pyjo.Message.Pyjo_Message.text`.
        """
        return self.test('like', self._tx.res.text, regex, _desc(desc, 'content is similar'))

    def content_type_is(self, type: str, desc: str | None = None) -> Self:
        """::

            t = t.content_type_is('text/html')
            t = t.content_type_is('text/html', 'right content type')

        Check response ``Content-Type`` header for exact match.
        """
        return self.test('is', self._tx.res.headers.content_type, type, _desc(desc, f'Content-Type: {type}'))

    def content_type_isnt(self, type: str, desc: str | None = None) -> Self:
        """::

            t = t.content_type_isnt('text/html')
            t = t.content_type_isnt('text/html', 'different content type')

        Opposite of :meth:`content_type_is`.
        """
        return self.test('isnt', self._tx.res.headers.content_type, type, _desc(desc, f'not Content-Type: {type}'))

    def content_type_like(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.content_type_like(re.compile(r'text'))
            t = t.content_type_like(re.compile(r'text'), 'right content type')

        Check response ``Content-Type`` header for similar match.
        """
        return self.test('like', self._tx.res.headers.content_type, regex, _desc(desc, 'Content-Type is similar'))

    def content_type_unlike(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.content_type_unlike(re.compile(r'text'))
            t = t.content_type_unlike(re.compile(r'text'), 'different content type')

        Opposite of :meth:`content_type_like`.
        """
        desc = _desc(desc, 'Content-Type is not similar')
        return self.test('unlike', self._tx.res.headers.content_type, regex, desc)

    def content_unlike(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.content_unlike(re.compile(r'working!'))
            t = t.content_unlike(re.compile(r'working!'), 'different content')

        Opposite of :meth:`content_like`.
        """
        return self.test('unlike', self._tx.res.text, regex, _desc(desc, 'content is not similar'))

    def delete_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.delete_ok('http://example.com/foo')
            t = t.delete_ok('/foo')
            t = t.delete_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.delete_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.delete_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``DELETE`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.delete`, except
        for the callback.
        """
        return self._build_ok('DELETE', url, *args, **kwargs)

    def element_count_is(self, selector: str, count: int, desc: str | None = None) -> Self:
        """::

            t = t.element_count_is('div.foo[x=y]', 5)
            t = t.element_count_is('html body div', 30, 'thirty elements')

        Checks the number of HTML/XML elements matched by the CSS selector
        with :meth:`Pyjo.DOM.Pyjo_DOM.find`.
        """
        size = len(self._dom().find(selector))
        return self.test('is', size, count, _desc(desc, f'element count for selector "{selector}"'))

    def element_exists(self, selector: str, desc: str | None = None) -> Self:
        """::

            t = t.element_exists('div.foo[x=y]')
            t = t.element_exists('html head title', 'has a title')

        Checks for existence of the CSS selectors first matching HTML/XML
        element with :meth:`Pyjo.DOM.Pyjo_DOM.at`. ::

            # Check attribute values
            (
                t.get_ok('/login')
                .element_exists('label[for=email]')
                .element_exists('input[name=email][type=text][value*="example.com"]')
                .element_exists('label[for=pass]')
                .element_exists('input[name=pass][type=password]')
                .element_exists('input[type=submit][value]')
            )
        """
        desc = _desc(desc, f'element for selector "{selector}" exists')
        return self.test('ok', self._dom().at(selector), desc)

    def element_exists_not(self, selector: str, desc: str | None = None) -> Self:
        """::

            t = t.element_exists_not('div.foo[x=y]')
            t = t.element_exists_not('html head title', 'has no title')

        Opposite of :meth:`element_exists`.
        """
        return self.test('ok', not self._dom().at(selector), _desc(desc, f'no element for selector "{selector}"'))

    def finish_ok(self, *args: Any) -> Self:
        """::

            t = t.finish_ok()
            t = t.finish_ok(1000)
            t = t.finish_ok(1003, 'Cannot accept data!')

        Close WebSocket connection gracefully.
        """
        if self._tx.is_websocket:
            self._tx.finish(*args)
        while self._finished is None:
            Pyjo.IOLoop.one_tick()
        return self.test('ok', 1, 'closed WebSocket')

    def finished_ok(self, code: int) -> Self:
        """::

            t = t.finished_ok(1000)

        Wait for WebSocket connection to be closed gracefully and check status.
        """
        while self._finished is None:
            Pyjo.IOLoop.one_tick()
        status = self._finished[0] if len(self._finished) else None
        if not (ok := status == code):
            Pyjo.Test.diag(f'WebSocket closed with status {status}')
        return self.test('ok', ok, f'WebSocket closed with status {code}')

    def get_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.get_ok('http://example.com/foo')
            t = t.get_ok('/foo')
            t = t.get_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.get_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.get_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``GET`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.get`, except
        for the callback. ::

            # Run tests against remote host
            t.get_ok('https://github.com').status_is(200)

            # Use relative URL for request with Basic authentication
            t.get_ok('//sri:secr3t@/secrets.json').status_is(200).json_is('/1/content', 'Pyjo rocks!')

            # Run additional tests on the transaction
            t.get_ok('/foo').status_is(200)
            is_ok(t.tx.res.dom().at('input').val, 'whatever', 'right value')
        """
        return self._build_ok('GET', url, *args, **kwargs)

    def get_sse_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.get_sse_ok('http://example.com/events')
            t = t.get_sse_ok('/events')
            t = t.get_sse_ok('/events', {'Accept': 'text/event-stream'}, 'Content!')
            t = t.get_sse_ok('/events', {'Accept': 'text/event-stream'}, form={'a': 'b'})
            t = t.get_sse_ok('/events', {'Accept': 'text/event-stream'}, json={'a': 'b'})

        Perform a ``GET`` request to establish a Server-Sent Events (SSE)
        connection, takes the same arguments as
        :meth:`Pyjo.UserAgent.Pyjo_UserAgent.get`, except for the callback.
        Note that this method is **EXPERIMENTAL** and may change without
        warning!
        """
        return self._build_sse_ok('GET', url, *args, **kwargs)

    def head_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.head_ok('http://example.com/foo')
            t = t.head_ok('/foo')
            t = t.head_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.head_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.head_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``HEAD`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.head`, except
        for the callback.
        """
        return self._build_ok('HEAD', url, *args, **kwargs)

    def header_exists(self, name: str, desc: str | None = None) -> Self:
        """::

            t = t.header_exists('ETag')
            t = t.header_exists('ETag', 'header exists')

        Check if response header exists.
        """
        exists = bool(len(self._tx.res.headers.every_header(name)))
        return self.test('ok', exists, _desc(desc, f'header "{name}" exists'))

    def header_exists_not(self, name: str, desc: str | None = None) -> Self:
        """::

            t = t.header_exists_not('ETag')
            t = t.header_exists_not('ETag', 'header is missing')

        Opposite of :meth:`header_exists`.
        """
        missing = not len(self._tx.res.headers.every_header(name))
        return self.test('ok', missing, _desc(desc, f'no "{name}" header'))

    def header_is(self, name: str, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.header_is('ETag', '"abc321"')
            t = t.header_is('ETag', '"abc321"', 'right header')

        Check response header for exact match.
        """
        desc = _desc(desc, f'{name}: {"" if value is None else value}')
        return self.test('is', self._tx.res.headers.header(name), value, desc)

    def header_isnt(self, name: str, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.header_isnt('Etag', '"abc321"')
            t = t.header_isnt('ETag', '"abc321"', 'different header')

        Opposite of :meth:`header_is`.
        """
        desc = _desc(desc, f'not {name}: {"" if value is None else value}')
        return self.test('isnt', self._tx.res.headers.header(name), value, desc)

    def header_like(self, name: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.header_like('ETag', re.compile(r'abc'))
            t = t.header_like('ETag', re.compile(r'abc'), 'right header')

        Check response header for similar match.
        """
        return self.test('like', self._tx.res.headers.header(name), regex, _desc(desc, f'{name} is similar'))

    def header_unlike(self, name: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.header_unlike('ETag', re.compile(r'abc'))
            t = t.header_unlike('ETag', re.compile(r'abc'), 'different header')

        Opposite of :meth:`header_like`.
        """
        return self.test('unlike', self._tx.res.headers.header(name), regex, _desc(desc, f'{name} is not similar'))

    def json_has(self, p: str, desc: str | None = None) -> Self:
        """::

            t = t.json_has('/foo')
            t = t.json_has('/minibar', 'has a minibar')

        Check if JSON response contains a value that can be identified using
        the given JSON Pointer with :mod:`Pyjo.JSON.Pointer`.
        """
        desc = _desc(desc, f'has value for JSON Pointer "{p}"')
        return self.test('ok', bool(Pyjo.JSON.Pointer.new(self._tx.res.json()).contains(p)), desc)

    def json_hasnt(self, p: str, desc: str | None = None) -> Self:
        """::

            t = t.json_hasnt('/foo')
            t = t.json_hasnt('/minibar', 'no minibar')

        Opposite of :meth:`json_has`.
        """
        desc = _desc(desc, f'has no value for JSON Pointer "{p}"')
        return self.test('ok', not Pyjo.JSON.Pointer.new(self._tx.res.json()).contains(p), desc)

    def json_is(self, *args: Any) -> Self:
        """::

            t = t.json_is({'foo': [1, 2, 3]})
            t = t.json_is('/foo', [1, 2, 3])
            t = t.json_is('/foo/1', 2, 'right value')

        Check the value extracted from JSON response using the given JSON
        Pointer with :mod:`Pyjo.JSON.Pointer`, which defaults to the root value
        if it is omitted. ::

            # Use an empty JSON Pointer to test the whole JSON response with a test description
            t.json_is('', {'foo': [1, 2, 3]}, 'right object')
        """
        p, data, desc = _json_args(args)
        return self.test('is_deeply', self._tx.res.json(p), data, _desc(desc, f'exact match for JSON Pointer "{p}"'))

    def json_like(self, p: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.json_like('/foo/1', re.compile(r'^\\d+$'))
            t = t.json_like('/foo/1', re.compile(r'^\\d+$'), 'right value')

        Check the value extracted from JSON response using the given JSON
        Pointer with :mod:`Pyjo.JSON.Pointer` for similar match.
        """
        desc = _desc(desc, f'similar match for JSON Pointer "{p}"')
        return self.test('like', self._tx.res.json(p), regex, desc)

    def json_message_has(self, p: str, desc: str | None = None) -> Self:
        """::

            t = t.json_message_has('/foo')
            t = t.json_message_has('/minibar', 'has a minibar')

        Check if JSON WebSocket message contains a value that can be
        identified using the given JSON Pointer with :mod:`Pyjo.JSON.Pointer`.
        """
        return self.test('ok', self._json('contains', p), _desc(desc, f'has value for JSON Pointer "{p}"'))

    def json_message_hasnt(self, p: str, desc: str | None = None) -> Self:
        """::

            t = t.json_message_hasnt('/foo')
            t = t.json_message_hasnt('/minibar', 'no minibar')

        Opposite of :meth:`json_message_has`.
        """
        return self.test('ok', not self._json('contains', p), _desc(desc, f'has no value for JSON Pointer "{p}"'))

    def json_message_is(self, *args: Any) -> Self:
        """::

            t = t.json_message_is({'foo': [1, 2, 3]})
            t = t.json_message_is('/foo', [1, 2, 3])
            t = t.json_message_is('/foo/1', 2, 'right value')

        Check the value extracted from JSON WebSocket message using the given
        JSON Pointer with :mod:`Pyjo.JSON.Pointer`, which defaults to the root
        value if it is omitted.
        """
        p, data, desc = _json_args(args)
        return self.test('is_deeply', self._json('get', p), data, _desc(desc, f'exact match for JSON Pointer "{p}"'))

    def json_message_like(self, p: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.json_message_like('/foo/1', re.compile(r'^\\d+$'))
            t = t.json_message_like('/foo/1', re.compile(r'^\\d+$'), 'right value')

        Check the value extracted from JSON WebSocket message using the given
        JSON Pointer with :mod:`Pyjo.JSON.Pointer` for similar match.
        """
        desc = _desc(desc, f'similar match for JSON Pointer "{p}"')
        return self.test('like', self._json('get', p), regex, desc)

    def json_message_unlike(self, p: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.json_message_unlike('/foo/1', re.compile(r'^\\d+$'))
            t = t.json_message_unlike('/foo/1', re.compile(r'^\\d+$'), 'different value')

        Opposite of :meth:`json_message_like`.
        """
        desc = _desc(desc, f'no similar match for JSON Pointer "{p}"')
        return self.test('unlike', self._json('get', p), regex, desc)

    def json_unlike(self, p: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.json_unlike('/foo/1', re.compile(r'^\\d+$'))
            t = t.json_unlike('/foo/1', re.compile(r'^\\d+$'), 'different value')

        Opposite of :meth:`json_like`.
        """
        desc = _desc(desc, f'no similar match for JSON Pointer "{p}"')
        return self.test('unlike', self._tx.res.json(p), regex, desc)

    def message_is(self, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.message_is({'binary': b'bytes'})
            t = t.message_is({'text': b'bytes'})
            t = t.message_is('working!')
            t = t.message_is('working!', 'right message')

        Check WebSocket message for exact match.
        """
        return self._message('is', value, _desc(desc, 'exact match for message'))

    def message_isnt(self, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.message_isnt({'binary': b'bytes'})
            t = t.message_isnt({'text': b'bytes'})
            t = t.message_isnt('working!')
            t = t.message_isnt('working!', 'different message')

        Opposite of :meth:`message_is`.
        """
        return self._message('isnt', value, _desc(desc, 'no match for message'))

    def message_like(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.message_like({'binary': re.compile(rb'bytes')})
            t = t.message_like({'text': re.compile(rb'bytes')})
            t = t.message_like(re.compile(r'working!'))
            t = t.message_like(re.compile(r'working!'), 'right message')

        Check WebSocket message for similar match.
        """
        return self._message('like', regex, _desc(desc, 'message is similar'))

    def message_ok(self, desc: str | None = None) -> Self:
        """::

            t = t.message_ok()
            t = t.message_ok('got a message')

        Wait for next WebSocket message to arrive. ::

            # Wait for message and perform multiple tests on it
            (
                t.websocket_ok('/time')
                .message_ok()
                .message_like(re.compile(r'\\d+'))
                .message_unlike(re.compile(r'\\w+'))
                .finish_ok()
            )
        """
        return self.test('ok', bool(self._wait()), _desc(desc, 'message received'))

    def message_unlike(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.message_unlike({'binary': re.compile(rb'bytes')})
            t = t.message_unlike({'text': re.compile(rb'bytes')})
            t = t.message_unlike(re.compile(r'working!'))
            t = t.message_unlike(re.compile(r'working!'), 'different message')

        Opposite of :meth:`message_like`.
        """
        return self._message('unlike', regex, _desc(desc, 'message is not similar'))

    def options_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.options_ok('http://example.com/foo')
            t = t.options_ok('/foo')
            t = t.options_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.options_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.options_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``OPTIONS`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.options`, except
        for the callback.
        """
        return self._build_ok('OPTIONS', url, *args, **kwargs)

    def otherwise(self, cb: Callable[[Self], Any]) -> Self:
        """::

            t = t.otherwise(lambda t: ...)

        Execute callback if the value of :attr:`success` is false. ::

            # Diagnostics
            (
                t.get_ok('/bad')
                .otherwise(lambda t: diag('Must have been Glen!'))
                .status_is(200)
                .otherwise(lambda t: diag(t.tx.res.dom().at('title').text))
            )
        """
        if not self.success:
            cb(self)
        return self

    # Renamed from Mojolicious: or is otherwise, as or is a keyword of Python, and or_ is its alias
    or_ = otherwise

    def patch_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.patch_ok('http://example.com/foo')
            t = t.patch_ok('/foo')
            t = t.patch_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.patch_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.patch_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``PATCH`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.patch`, except
        for the callback.
        """
        return self._build_ok('PATCH', url, *args, **kwargs)

    def post_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.post_ok('http://example.com/foo')
            t = t.post_ok('/foo')
            t = t.post_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.post_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.post_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``POST`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.post`, except
        for the callback. ::

            # Test file upload
            upload = {'foo': {'content': 'bar', 'filename': 'baz.txt'}}
            t.post_ok('/upload', form=upload).status_is(200)

            # Test JSON API
            t.post_ok('/hello.json', json={'hello': 'world'}).status_is(200).json_is({'bye': 'world'})
        """
        return self._build_ok('POST', url, *args, **kwargs)

    def post_sse_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.post_sse_ok('http://example.com/events')
            t = t.post_sse_ok('/events')
            t = t.post_sse_ok('/events', {'Accept': 'text/event-stream'}, 'Content!')
            t = t.post_sse_ok('/events', {'Accept': 'text/event-stream'}, form={'a': 'b'})
            t = t.post_sse_ok('/events', {'Accept': 'text/event-stream'}, json={'a': 'b'})

        Perform a ``POST`` request to establish a Server-Sent Events (SSE)
        connection, takes the same arguments as
        :meth:`Pyjo.UserAgent.Pyjo_UserAgent.post`, except for the callback.
        Note that this method is **EXPERIMENTAL** and may change without
        warning!
        """
        return self._build_sse_ok('POST', url, *args, **kwargs)

    def put_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.put_ok('http://example.com/foo')
            t = t.put_ok('/foo')
            t = t.put_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.put_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.put_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``PUT`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.put`, except
        for the callback.
        """
        return self._build_ok('PUT', url, *args, **kwargs)

    def query_ok(self, url: Any, *args: Any, **kwargs: Any) -> Self:
        """::

            t = t.query_ok('http://example.com/foo')
            t = t.query_ok('/foo')
            t = t.query_ok('/foo', {'Accept': '*/*'}, 'Content!')
            t = t.query_ok('/foo', {'Accept': '*/*'}, form={'a': 'b'})
            t = t.query_ok('/foo', {'Accept': '*/*'}, json={'a': 'b'})

        Perform a ``QUERY`` request and check for transport errors, takes the
        same arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.query`, except
        for the callback.
        """
        return self._build_ok('QUERY', url, *args, **kwargs)

    def request_ok(self, tx: 'Pyjo.Transaction.HTTP.object') -> Self:
        """::

            t = t.request_ok(Pyjo.Transaction.HTTP.new())

        Perform request and check for transport errors. ::

            # Request with custom method
            tx = t.ua.build_tx('FOO', '/test.json', json={'foo': 1})
            t.request_ok(tx).status_is(200).json_is({'success': 1})

            # Request with custom cookie
            tx = t.ua.build_tx('GET', '/account')
            tx.req.cookies({'name': 'user', 'value': 'sri'})
            t.request_ok(tx).status_is(200).text_is('head > title', 'Hello sri')

            # Custom WebSocket handshake
            tx = t.ua.build_websocket_tx('/foo')
            tx.req.headers.remove('User-Agent')
            t.request_ok(tx).message_ok().message_is('bar').finish_ok()
        """
        return self._request_ok(tx, tx.req.url.to_str())

    def reset_session(self) -> Self:
        """::

            t = t.reset_session()

        Reset user agent session.
        """
        self.ua.cookie_jar.empty()
        self.tx = None
        return self

    def send_ok(self, msg: Any, desc: str | None = None) -> Self:
        """::

            t = t.send_ok({'binary': b'bytes'})
            t = t.send_ok({'text': b'bytes'})
            t = t.send_ok({'json': {'test': [1, 2, 3]}})
            t = t.send_ok([fin, rsv1, rsv2, rsv3, op, payload])
            t = t.send_ok('chars')
            t = t.send_ok('chars', 'sent successfully')

        Send message or frame via WebSocket. ::

            # Send JSON object as "Text" message
            (
                t.websocket_ok('/echo.json')
                .send_ok({'json': {'test': 'I ♥ Pyjoyment!'}})
                .message_ok()
                .json_message_is('/test', 'I ♥ Pyjoyment!')
                .finish_ok()
            )
        """
        desc = _desc(desc, 'send message')
        if not self._tx.is_websocket:
            return self.test('ok', 0, desc)

        self._tx.send(msg, _stop)
        Pyjo.IOLoop.start()
        return self.test('ok', 1, desc)

    def sse_finish_ok(self) -> Self:
        """::

            t = t.sse_finish_ok()

        Close Server-Sent Events connection. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        # Unlike Mojolicious: the error is interrupted by Pyjo.Test.Pyjo, where Mojo names Test::Mojo
        self._tx.res.error = {'message': 'Interrupted by Pyjo.Test.Pyjo'}

        # Unlike Mojolicious: the connection is closed too, as the user agent finds the error only when it reads, so that
        # a stream without events, which Mojo waits for until its next event or its inactivity timeout, ends at once
        if (id := self._tx.connection) is not None and (stream := Pyjo.IOLoop.singleton.stream(id)) is not None:
            stream.close_gracefully()
        while not self._sse_finished:
            Pyjo.IOLoop.one_tick()
        return self.test('ok', 1, 'closed SSE connection')

    def sse_finished_ok(self) -> Self:
        """::

            t = t.sse_finished_ok()

        Wait for Server-Sent Events connection to be closed. Note that this
        method is **EXPERIMENTAL** and may change without warning!
        """
        while not self._sse_finished:
            Pyjo.IOLoop.one_tick()
        return self.test('ok', 1, 'SSE connection has been closed')

    def sse_ok(self, desc: str | None = None) -> Self:
        """::

            t = t.sse_ok()
            t = t.sse_ok('got an event')

        Wait for next Server-Sent Event to arrive. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('ok', bool(self._sse_wait()), _desc(desc, 'event received'))

    def sse_id_is(self, id: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_id_is(123)
            t = t.sse_id_is(123, 'right id')

        Check Server-Sent Event id for exact match. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('is', self._event('id'), id, _desc(desc, 'exact match for SSE event id'))

    def sse_id_isnt(self, id: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_id_isnt(123)
            t = t.sse_id_isnt(123, 'different id')

        Opposite of :meth:`sse_id_is`. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('isnt', self._event('id'), id, _desc(desc, 'no match for SSE event id'))

    def sse_text_is(self, text: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_text_is('working!')
            t = t.sse_text_is('working!', 'right text')

        Check Server-Sent Event text for exact match. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('is', self._event('text'), text, _desc(desc, 'exact match for SSE event text'))

    def sse_text_isnt(self, text: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_text_isnt('working!')
            t = t.sse_text_isnt('working!', 'different text')

        Opposite of :meth:`sse_text_is`. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('isnt', self._event('text'), text, _desc(desc, 'no match for SSE event text'))

    def sse_text_like(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_text_like(re.compile(r'working'))
            t = t.sse_text_like(re.compile(r'working'), 'right text')

        Check Server-Sent Event text for exact match. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('like', self._event('text'), regex, _desc(desc, 'similar match for SSE event text'))

    def sse_text_unlike(self, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_text_unlike(re.compile(r'working'))
            t = t.sse_text_unlike(re.compile(r'working'), 'different text')

        Opposite of :meth:`sse_text_like`. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('unlike', self._event('text'), regex, _desc(desc, 'no similar match for SSE event text'))

    def sse_type_is(self, type: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_type_is('message')
            t = t.sse_type_is('message', 'right type')

        Check Server-Sent Event type for exact match. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('is', self._event('type'), type, _desc(desc, 'exact match for SSE event type'))

    def sse_type_isnt(self, type: Any, desc: str | None = None) -> Self:
        """::

            t = t.sse_type_isnt('message')
            t = t.sse_type_isnt('message', 'different type')

        Opposite of :meth:`sse_type_is`. Note that this method is
        **EXPERIMENTAL** and may change without warning!
        """
        return self.test('isnt', self._event('type'), type, _desc(desc, 'no match for SSE event type'))

    def status_is(self, status: int, desc: str | None = None) -> Self:
        """::

            t = t.status_is(200)
            t = t.status_is(200, 'right status')

        Check response status for exact match.
        """
        res = self._tx.res
        desc = _desc(desc, f'{status} {res.default_message(status)}')
        return self.test('is', res.code, status, desc)

    def status_isnt(self, status: int, desc: str | None = None) -> Self:
        """::

            t = t.status_isnt(200)
            t = t.status_isnt(200, 'different status')

        Opposite of :meth:`status_is`.
        """
        res = self._tx.res
        desc = _desc(desc, f'not {status} {res.default_message(status)}')
        return self.test('isnt', res.code, status, desc)

    def test(self, name: str, *args: Any) -> Self:
        """::

            t = t.test('is', 'first value', 'second value', 'right value')

        Call :mod:`Pyjo.Test` functions through :attr:`handler`, by the names
        of the functions of ``Test::More`` (``ok``, ``is``, ``isnt``,
        ``like``, ``unlike`` and ``is_deeply``), used to implement
        :mod:`Pyjo.Test.Pyjo` extensions. The result will be stored in
        :attr:`success`.
        """
        self.success = bool(self.handler(name, *args))
        return self

    def text_is(self, selector: str, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.text_is('div.foo[x=y]', 'Hello!')
            t = t.text_is('html head title', 'Hello!', 'right title')

        Checks text content of the CSS selectors first matching HTML/XML
        element for exact match with :meth:`Pyjo.DOM.Pyjo_DOM.at`.
        """
        return self.test('is', self._text(selector), value, _desc(desc, f'exact match for selector "{selector}"'))

    def text_isnt(self, selector: str, value: Any, desc: str | None = None) -> Self:
        """::

            t = t.text_isnt('div.foo[x=y]', 'Hello!')
            t = t.text_isnt('html head title', 'Hello!', 'different title')

        Opposite of :meth:`text_is`.
        """
        return self.test('isnt', self._text(selector), value, _desc(desc, f'no match for selector "{selector}"'))

    def text_like(self, selector: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.text_like('div.foo[x=y]', re.compile(r'Hello'))
            t = t.text_like('html head title', re.compile(r'Hello'), 'right title')

        Checks text content of the CSS selectors first matching HTML/XML
        element for similar match with :meth:`Pyjo.DOM.Pyjo_DOM.at`.
        """
        desc = _desc(desc, f'similar match for selector "{selector}"')
        return self.test('like', self._text(selector), regex, desc)

    def text_unlike(self, selector: str, regex: Any, desc: str | None = None) -> Self:
        """::

            t = t.text_unlike('div.foo[x=y]', re.compile(r'Hello'))
            t = t.text_unlike('html head title', re.compile(r'Hello'), 'different title')

        Opposite of :meth:`text_like`.
        """
        desc = _desc(desc, f'no similar match for selector "{selector}"')
        return self.test('unlike', self._text(selector), regex, desc)

    def websocket_ok(self, url: Any, *args: Any) -> Self:
        """::

            t = t.websocket_ok('http://example.com/echo')
            t = t.websocket_ok('/echo')
            t = t.websocket_ok('/echo', {'DNT': 1}, ['v1.proto'])

        Open a WebSocket connection with transparent handshake, takes the same
        arguments as :meth:`Pyjo.UserAgent.Pyjo_UserAgent.websocket`, except
        for the callback. ::

            # WebSocket with permessage-deflate compression
            (
                t.websocket_ok('/', {'Sec-WebSocket-Extensions': 'permessage-deflate'})
                .send_ok('y' * 50000)
                .message_ok()
                .message_is('z' * 50000)
                .finish_ok()
            )
        """
        return self._request_ok(self.ua.build_websocket_tx(url, *args), url)

    @property
    def _tx(self) -> Any:
        if self.tx is None:
            raise AttributeError('No transaction to test, make a request first')
        return self.tx

    def _attr(self, selector: str, attr: str) -> str | None:
        if (e := self._dom().at(selector)) is None:
            return None
        value = e.attr(attr)
        return value if value is not None else ''

    def _build_ok(self, method: str, url: Any, *args: Any, **kwargs: Any) -> Self:
        return self._request_ok(self.ua.build_tx(method, url, *args, **kwargs), url)

    def _build_sse_ok(self, method: str, url: Any, *args: Any, **kwargs: Any) -> Self:
        return self._sse_ok(self.ua.build_tx(method, url, *args, **kwargs), url)

    def _dom(self) -> Any:
        return self._tx.res.dom()

    def _event(self, name: str) -> Any:
        return (self.sse or {}).get(name)

    def _json(self, method: str, p: str) -> Any:
        message = self.message or []
        payload = message[1] if len(message) > 1 else None
        return getattr(Pyjo.JSON.Pointer.new(j(payload) if payload is not None else None), method)(p)

    def _message(self, name: str, value: Any, desc: str) -> Self:
        type, msg = (self.message or [None, None])[:2]

        # Type check
        if isinstance(value, dict):
            expect = 'text' if 'text' in value else 'binary'
            value = cast(dict[str, Any], value)[expect]
            if (type or '') != expect:
                msg = ''

        # Decode text frame if there is no type check
        elif (type or '') == 'text':
            msg = decode('UTF-8', msg)

        return self.test(name, msg if msg is not None else '', value, desc)

    def _request_ok(self, tx: Any, url: Any) -> Self:
        # Establish WebSocket connection
        if tx.req.is_handshake:
            self._finished, self._messages = None, []

            def handshake(ua: Any, tx: Any) -> None:
                self.tx = tx
                if not tx.is_websocket:
                    self._finished = []

                def finish(tx: Any, *args: Any) -> None:
                    self._finished = list(args)

                def binary(tx: Any, msg: bytes) -> None:
                    self._messages.append(['binary', msg])

                def text(tx: Any, msg: bytes) -> None:
                    self._messages.append(['text', msg])

                tx.on('finish', finish)
                tx.on('binary', binary)
                tx.on('text', text)
                Pyjo.IOLoop.stop()

            self.ua.start(tx, handshake)
            Pyjo.IOLoop.start()

            return self.test('ok', self._tx.is_websocket, _desc(None, f'WebSocket handshake with {url}'))

        # Perform request
        self.tx = self.ua.start(tx)
        err = self._tx.error
        if not (ok := not err or not err.get('message') or err.get('code')) and err:
            Pyjo.Test.diag(err['message'])
        return self.test('ok', bool(ok), _desc(None, f'{tx.req.method.upper()} {url}'))

    def _sse_ok(self, tx: Any, url: Any) -> Self:
        ok = None
        self._sse_finished, self._sse_events = None, []

        def sse(content: Any, event: dict[str, Any] | None) -> None:
            nonlocal ok
            if event:
                self._sse_events.append(event)
            else:
                ok = 1
                Pyjo.IOLoop.stop()

        tx.res.content.on('sse', sse)

        def start(ua: Any, tx: Any) -> None:
            self.tx = tx

        cb = self.ua.on('start', start)

        def finish(ua: Any, tx: Any) -> None:
            self._sse_finished = True
            self.ua.unsubscribe('start', cb)
            Pyjo.IOLoop.stop()

        self.ua.start(tx, finish)
        Pyjo.IOLoop.start()

        return self.test('ok', ok, _desc(None, f'SSE connection established: {tx.req.method.upper()} {url}'))

    def _sse_wait(self) -> dict[str, Any] | None:
        while not self._sse_finished and not len(self._sse_events):
            Pyjo.IOLoop.one_tick()
        self.sse = self._sse_events.pop(0) if len(self._sse_events) else None
        return self.sse

    def _text(self, selector: str) -> str | None:
        if (e := self._dom().at(selector)) is None:
            return None
        return e.text

    def _wait(self) -> list[Any] | None:
        while self._finished is None and not len(self._messages):
            Pyjo.IOLoop.one_tick()
        self.message = self._messages.pop(0) if len(self._messages) else None
        return self.message


# Unlike Mojolicious: the strings are characters, which Mojo encodes to UTF-8 for Test::More
def _desc(desc: str | None, default: str) -> str:
    return desc or default


# A regular expression of Pyjo.Test
type _Pattern = str | bytes | re.Pattern[str] | re.Pattern[bytes] | tuple[str | bytes, str]


# like and unlike of Test::More, which match the string of a value, as a number, and match bytes, the characters
# 0-255 of Perl, with a pattern of characters
def _like(function: Callable[..., Pyjo.Test.Result]) -> Callable[..., Pyjo.Test.Result]:
    def like(got: Any, regex: _Pattern, desc: str | None = None) -> Pyjo.Test.Result:
        pattern = regex.pattern if isinstance(regex, re.Pattern) else regex[0] if isinstance(regex, tuple) else regex
        if isinstance(got, bytes) and not isinstance(pattern, bytes):
            got = got.decode('latin-1')
        elif got is not None and not isinstance(got, str | bytes):
            got = str(got)
        return function(got, regex, desc)

    return like


# The functions of Pyjo.Test by the names of the functions of Test::More
_FUNCTIONS: dict[str, Callable[..., Any]] = {
    'is': Pyjo.Test.is_ok,
    'is_deeply': Pyjo.Test.is_deeply_ok,
    'isnt': Pyjo.Test.isnt_ok,
    'like': _like(Pyjo.Test.like_ok),
    'ok': Pyjo.Test.ok,
    'unlike': _like(Pyjo.Test.unlike_ok),
}


def _handler(name: str, *args: Any) -> Any:
    return _FUNCTIONS[name](*args)


def _json_args(args: tuple[Any, ...]) -> tuple[str, Any, str | None]:
    values = list(args)
    if len(values) > 1:
        return values[0], values[1], values[2] if len(values) > 2 else None
    return '', values[0] if len(values) else None, None


def _stop(tx: Any) -> None:
    Pyjo.IOLoop.stop()


new = Pyjo_Test_Pyjo.new
object = Pyjo_Test_Pyjo
