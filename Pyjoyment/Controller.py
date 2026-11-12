"""
Pyjoyment.Controller - Controller base class
============================================
::

    # Controller
    from Pyjoyment.Controller import Controller

    class MyApp_Controller_Foo(Controller):

        # Action
        def bar(self):
            name = self.param('name')
            self.res.headers.cache_control = 'max-age=1, no-cache'
            self.render(json={'hello': name})

    object = MyApp_Controller_Foo

    # Or import the module, as in Google Python Style Guide

    # Controller
    import Pyjoyment.Controller

    class MyApp_Controller_Foo(Pyjoyment.Controller.object):

        # Action
        def bar(self):
            name = self.param('name')
            self.res.headers.cache_control = 'max-age=1, no-cache'
            self.render(json={'hello': name})

    object = MyApp_Controller_Foo

:mod:`Pyjoyment.Controller` is the base class for your :mod:`Pyjoyment`
controllers. It is also the default controller class unless you set
:attr:`Pyjoyment.Pyjoyment_App.controller_class`.

A controller is a context manager for the callbacks of a delayed response: an
exception that the ``with`` block does not catch is replied with the helper
``reply.exception`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`, as an exception
that goes on to the event loop would leave the request without a response. ::

    # Exception in a callback of a delayed response
    def later(self):
        @Pyjo.IOLoop.next_tick
        def tick(loop):
            with self:
                self.render(text=self.param('name').upper())

Helpers
-------

In addition to the attributes and methods below you can also call helpers
provided by :attr:`~Pyjoyment_Controller.app` on :mod:`Pyjoyment.Controller`
objects. This includes all helpers from
:mod:`Pyjoyment.Plugin.DefaultHelpers` and :mod:`Pyjoyment.Plugin.TagHelpers`. ::

    # Call helpers
    c.layout('green')
    c.title('Welcome!')

    # Longer version
    c.helpers.layout('green')

Type checkers and editors know the types of these helpers, and of the helpers
of an application that :class:`Helper` declares.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Controller <https://github.com/mojolicious/mojo/blob/v9.53/lib/Mojolicious/Controller.pm>`_
of Mojolicious 9.53.
"""

# No imports, for security reasons!
import Pyjo.Base
import Pyjo.Exception
import Pyjo.String.Bytes
import Pyjo.String.HTML
import Pyjo.URL
import Pyjo.Util
import Pyjoyment.Routes.Match

import functools
import io
import re
import sys
import weakref

from collections.abc import Callable
from types import TracebackType
from typing import TYPE_CHECKING, Any, Concatenate, Self, cast, overload


if TYPE_CHECKING:
    import Pyjo.Message.Request
    import Pyjo.Message.Response
    import Pyjo.Transaction
    import Pyjoyment
    import Pyjoyment.Plugin.DefaultHelpers
    import Pyjoyment.Plugin.TagHelpers

    # Not in Mojolicious: the types of the helpers of the default plugins, which type checkers take from here, while
    # __getattr__ finds the helpers in the renderer at run time, and any other helper is Any
    class _Helpers(Pyjoyment.Plugin.DefaultHelpers.Helpers, Pyjoyment.Plugin.TagHelpers.Helpers):
        def __getattr__(self, name: str) -> Any: ...

    class _Base(Pyjo.Base.object, _Helpers): ...

else:
    _Base = Pyjo.Base.object


_ABSOLUTE = re.compile(r'^(?:[^:/?#]+:|//|#)')

_MISSING: Any = Pyjo.Base.object()


class Pyjoyment_Controller(_Base):
    """
    :mod:`Pyjoyment.Controller` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(
        self,
        app: 'Pyjoyment.object | None' = None,
        match: Pyjoyment.Routes.Match.object | None = None,
        stash: dict[str, Any] | None = None,
        tx: 'Pyjo.Transaction.object | None' = None,
    ) -> None:
        """::

            c = Pyjoyment.Controller.new()
            c = Pyjoyment.Controller.new(app=Pyjoyment.new(), tx=Pyjo.Transaction.HTTP.new())

        Construct a new :mod:`Pyjoyment.Controller` object.
        """
        self._app: weakref.ref[Pyjoyment.object] | None = None
        self._match = match
        self._stash = stash if stash is not None else {}
        self._tx: weakref.ref[Pyjo.Transaction.object] | None = None
        # The transaction that the application builds for the controller, which Mojo keeps in the hash of the
        # object, past the weakening of the attribute
        self._own_tx: Pyjo.Transaction.object | None = None

        self.app = app
        self.tx = tx

    # Not in Mojolicious: a context manager, which replies with the exception that the block does not catch, as an
    # exception that goes on from a callback to the event loop would leave the request without a response
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> bool:
        if not isinstance(value, Exception):
            return False
        self.helpers.reply.exception(value)
        return True

    # Unlike Mojolicious: Mojo registers the helpers with Mojo::DynamicMethods, Python looks them up in the renderer of
    # the application when a method is not found
    def __getattr__(self, name: str) -> Any:
        app = self._app() if self._app is not None and not name.startswith('_') else None
        if app is not None and (helper := app.renderer.get_helper(name)) is not None:
            return helper(self) if isinstance(helper, type) else _Helper(helper, self)
        package = f'{type(self).__module__}.{type(self).__qualname__}'

        # The location of the caller, which croak adds to the message, the one of the attribute for the type of a helper
        caller = sys._getframe(1)  # pyright: ignore[reportPrivateUsage]
        if caller.f_code is _HELPER_GET and caller.f_back is not None:
            caller = caller.f_back
        at = f'at {caller.f_code.co_filename} line {caller.f_lineno}'

        # Not in Mojolicious: the attribute or the helper that the name most likely meant, as "req" for "request" of
        # another framework
        mean = ''
        if app is not None:
            names = [*dir(self), *(h.split('.')[0] for h in app.renderer.helpers)]
            if (suggestion := Pyjo.Util._suggest(name, names)) is not None:  # pyright: ignore[reportPrivateUsage]
                mean = f' Did you mean "{suggestion}"?'
        raise AttributeError(
            f'Can\'t locate object method "{name}" via package "{package}" {at}.{mean}\n', name=name, obj=self
        )

    @property
    def app(self) -> 'Pyjoyment.object':
        """::

            app = c.app
            c.app = Pyjoyment.new()

        A reference back to the application that dispatched to this
        controller, usually a :mod:`Pyjoyment` object. Note that this attribute
        is weakened. ::

            # Use application logger
            c.app.log.debug('Hello Pyjo')

            # Generate path
            path = c.app.home.child('templates', 'foo', 'bar.html.ep')
        """
        # None when the application is gone, as the weakened attribute of Mojo is undef then
        return cast('Pyjoyment.object', self._app() if self._app is not None else None)

    @app.setter
    def app(self, value: 'Pyjoyment.object | None') -> None:
        self._app = weakref.ref(value) if value is not None else None

    @property
    def match(self) -> Pyjoyment.Routes.Match.object:
        """::

            m = c.match
            c.match = Pyjoyment.Routes.Match.new()

        Router results for the current request, defaults to a
        :mod:`Pyjoyment.Routes.Match` object. ::

            # Introspect
            name = c.match.endpoint.name
            foo = c.match.endpoint.pattern.defaults['foo']
            action = c.match.stack[-1]['action']
        """
        if self._match is None:
            self._match = Pyjoyment.Routes.Match.new(root=self.app.routes)
        return self._match

    @match.setter
    def match(self, value: Pyjoyment.Routes.Match.object) -> None:
        self._match = value

    @property
    def tx(self) -> 'Pyjo.Transaction.object | None':
        """::

            tx = c.tx
            c.tx = Pyjo.Transaction.HTTP.new()

        The transaction that is currently being processed, usually a
        :mod:`Pyjo.Transaction.HTTP` or :mod:`Pyjo.Transaction.WebSocket`
        object. Note that this attribute is weakened. So the object needs to be
        referenced elsewhere as well when you're performing non-blocking
        operations and the underlying connection might get closed early. ::

            # Check peer information
            address = c.tx.remote_address
            port = c.tx.remote_port

            # Increase size limit for WebSocket messages to 16MiB
            if c.tx.is_websocket:
                c.tx.max_websocket_size = 16777216

            # Perform non-blocking operation without knowing the connection status
            tx = c.tx
            Pyjo.IOLoop.timer(2, lambda loop: c.app.log.debug('Finished' if tx.is_finished else 'In progress'))
        """
        return self._tx() if self._tx is not None else None

    @tx.setter
    def tx(self, value: 'Pyjo.Transaction.object | None') -> None:
        self._tx = weakref.ref(value) if value is not None else None
        if value is not self._own_tx:
            self._own_tx = None

    # Renamed from Mojolicious: continue, which is a keyword of Python
    def proceed(self) -> None:
        """::

            c.proceed()

        Continue dispatch chain from an intermediate destination with
        :meth:`Pyjoyment.Routes.Pyjoyment_Routes.proceed`. ``continue_`` is an
        alias, the name of Mojolicious with an underscore.
        """
        self.app.routes.proceed(self)

    # The name of Mojolicious, with an underscore as continue is a keyword of Python
    continue_ = proceed

    @overload
    def cookie(self, name: str, /) -> str | None: ...

    @overload
    def cookie(self, name: str, value: str, options: dict[str, Any] | None = None, /) -> Self: ...

    def cookie(self, name: str, /, *args: Any) -> str | None | Self:
        """::

            value = c.cookie('foo')
            c = c.cookie('foo', 'bar')
            c = c.cookie('foo', 'bar', {'path': '/'})

        Access request cookie values and create new response cookies. If there
        are multiple values sharing the same name, and you want to access more
        than just the last one, you can use :meth:`every_cookie`. ::

            # Create response cookie with domain and expiration date
            c.cookie('user', 'sri', {'domain': 'example.com', 'expires': time.time() + 60})

            # Create secure response cookie
            c.cookie('secret', 'I <3 Pyjoyment', {'secure': True, 'httponly': True})
        """
        # Response cookie
        if args:
            # Cookie too big
            values: dict[str, Any] = {'name': name, 'value': args[0], **(args[1] if len(args) > 1 and args[1] else {})}
            if len(values['value'] or '') > 4096:
                self.helpers.log().error(f'Cookie "{name}" is bigger than 4KiB')

            self.res.cookies(values)
            return self

        # Request cookies
        if (cookie := self.req.cookie(name)) is None:
            return None
        return cookie.value

    # Left out from Mojolicious: encrypted_cookie, as encrypt_cookie and decrypt_cookie of Pyjo.Util are left out

    def every_cookie(self, name: str) -> list[str]:
        """::

            values = c.every_cookie('foo')

        Similar to :meth:`cookie`, but returns all request cookie values sharing
        the same name as a list. ::

            # Get first cookie value
            first = c.every_cookie('foo')[0]
        """
        return [cookie.value or '' for cookie in self.req.every_cookie(name)]

    # Left out from Mojolicious: every_encrypted_cookie, as encrypt_cookie and decrypt_cookie of Pyjo.Util are left out

    def every_param(self, name: str) -> 'list[Any]':
        """::

            values = c.every_param('foo')

        Similar to :meth:`param`, but returns all values sharing the same name
        as a list. ::

            # Get first value
            first = c.every_param('foo')[0]
        """
        # Captured unreserved values
        captures = self.stash().setdefault('mojo.captures', {})
        if name in captures and not self.app.routes.is_reserved(name):
            value = captures[name]
            return cast(list[Any], value) if isinstance(value, list) else [value]

        # Uploads or param values
        req = self.req
        uploads: list[Any] = req.every_upload(name)
        return uploads if uploads else req.every_param(name)

    def every_signed_cookie(self, name: str) -> list[str]:
        """::

            values = c.every_signed_cookie('foo')

        Similar to :meth:`signed_cookie`, but returns all signed request cookie
        values sharing the same name as a list. ::

            # Get first signed cookie value
            first = c.every_signed_cookie('foo')[0]
        """
        secrets = self.app.secrets
        results: list[str] = []
        for value in self.every_cookie(name):
            # Check signature with rotating secrets
            if m := re.search(r'--([^\-]+)$', value):
                signature, value = m[1], value[: m.start()]

                if any(Pyjo.Util.secure_compare(signature, _hmac(f'{name}={value}', secret)) for secret in secrets):
                    results.append(value)

                else:
                    self.helpers.log().trace(f'Cookie "{name}" has bad signature')

            else:
                self.helpers.log().trace(f'Cookie "{name}" is not signed')

        return results

    def finish(self, *args: Any) -> Self:
        """::

            c = c.finish()
            c = c.finish(1000)
            c = c.finish(1003, 'Cannot accept data!')
            c = c.finish(b'Bye!')

        Close WebSocket connection or long poll stream gracefully. This method
        will automatically respond to WebSocket handshake requests with a
        ``101`` response status, to establish the WebSocket connection.
        """
        # WebSocket
        tx: Any = self._transaction()
        if tx.is_websocket:
            tx.finish(*args)
            return self if tx.established else self.rendered(101)

        # Chunked stream
        if tx.res.content.is_chunked:
            return self.write_chunk(*args).write_chunk(b'') if args else self.write_chunk(b'')

        # Normal stream
        return self.write(*args).write(b'') if args else self.write(b'')

    @property
    def helpers(self) -> '_Helpers':
        """::

            helpers = c.helpers

        Return a proxy object containing the current controller object and on
        which helpers provided by :attr:`app` can be called. This includes all
        helpers from :mod:`Pyjoyment.Plugin.DefaultHelpers` and
        :mod:`Pyjoyment.Plugin.TagHelpers`. ::

            # Make sure to use the "title" helper and not the controller method
            c.helpers.title('Welcome!')

            # Use a nested helper instead of the "reply" controller method
            c.helpers.reply.not_found()
        """
        return cast(Any, self.app.renderer.get_helper(''))(self)

    @overload
    def on(self, name: str, cb: None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

    @overload
    def on(self, name: str, cb: Callable[..., Any]) -> Callable[..., Any]: ...

    def on(self, name: str, cb: Callable[..., Any] | None = None) -> Any:
        """::

            cb = c.on('finish', lambda c: ...)

            @c.on('finish')
            def cb(c): ...

        Subscribe to events of :attr:`tx`, which is usually a
        :mod:`Pyjo.Transaction.HTTP` or :mod:`Pyjo.Transaction.WebSocket`
        object. This method will automatically respond to WebSocket handshake
        requests with a ``101`` response status, to establish the WebSocket
        connection. ::

            # Do something after the transaction has been finished
            @c.on('finish')
            def finish(c):
                c.app.log.debug('All data has been sent')

            # Receive WebSocket message
            @c.on('message')
            def message(c, msg):
                c.app.log.debug(f'Message: {msg}')

            # Receive JSON object via WebSocket message
            @c.on('json')
            def json(c, hash):
                c.app.log.debug(f'Test: {hash["test"]}')

            # Receive WebSocket "Binary" message
            @c.on('binary')
            def binary(c, data):
                c.app.log.debug(f'Received {len(data)} bytes')
        """
        if cb is None:

            def decorator(cb: Callable[..., Any]) -> Callable[..., Any]:
                return self.on(name, cb)

            return decorator

        tx: Any = self._transaction()
        if tx.is_websocket and not tx.established:
            self.rendered(101)

        def event(tx: Any, *args: Any) -> Any:
            try:
                return cb(self, *args)
            except TypeError as e:
                # Not in Mojolicious: the arguments of a callback, which Perl does not check
                Pyjo.Util._call_hint(e, f'the callbacks of the event "{name}" get the controller first')  # pyright: ignore[reportPrivateUsage]
                raise

        return tx.on(name, event)

    @overload
    def param(self, name: str, /) -> Any: ...

    @overload
    def param(self, name: str, value: Any, /, *values: Any) -> Self: ...

    def param(self, name: str, /, *values: Any) -> Any:
        """::

            value = c.param('foo')
            c = c.param('foo', 'ba;r')
            c = c.param('foo', 'ba;r', 'baz')
            c = c.param('foo', ['ba;r', 'baz'])

        Access route placeholder values that are not reserved stash values,
        file uploads as well as ``GET`` and ``POST`` parameters extracted from
        the query string and ``application/x-www-form-urlencoded`` or
        ``multipart/form-data`` message body, in that order. If there are
        multiple values sharing the same name, and you want to access more than
        just the last one, you can use :meth:`every_param`. Parts of the request
        body need to be loaded into memory to parse ``POST`` parameters, so you
        have to make sure it is not excessively large. There's a 16MiB limit for
        requests by default. ::

            # Get first value
            first = c.every_param('foo')[0]

        For more control you can also access request information directly. ::

            # Only GET parameters
            foo = c.req.query_params.param('foo')

            # Only POST parameters
            foo = c.req.body_params.param('foo')

            # Only GET and POST parameters
            foo = c.req.param('foo')

            # Only file uploads
            foo = c.req.upload('foo')
        """
        if not values:
            every = self.every_param(name)
            return every[-1] if every else None
        captures: dict[str, Any] = self.stash().setdefault('mojo.captures', {})
        captures[name] = list(values) if len(values) > 1 else next(iter(values))
        return self

    def render(self, template: str | None = None, /, **args: Any) -> Any:
        """::

            boolean = c.render()
            boolean = c.render(foo='bar', baz=23)
            boolean = c.render(template='foo/index')
            boolean = c.render(template='index', format='html')
            boolean = c.render(data=data)
            boolean = c.render(text='Hello!')
            boolean = c.render(json={'foo': 'bar'})
            boolean = c.render(yaml={'foo': 'bar'})
            boolean = c.render(toml={'foo': 'bar'})
            boolean = c.render(handler='something')
            boolean = c.render('foo/index')

        Render content with :attr:`Pyjoyment.Pyjoyment_App.renderer` and emit
        hooks ``before_render`` as well as ``after_render``, or raises an
        exception if no response could be generated. All additional keyword
        arguments get merged into the :meth:`stash`. ::

            # Render characters
            c.render(text='I ♥ Pyjoyment!')

            # Render characters (alternative)
            c.stash(text='I ♥ Pyjoyment!').render()

            # Render binary data
            from Pyjo.JSON import encode_json
            c.render(data=encode_json({'test': 'I ♥ Pyjoyment!'}))

            # Render JSON
            c.render(json={'test': 'I ♥ Pyjoyment!'})

            # Render YAML, in the style of index.yaml of a chart repository of Helm
            c.render(yaml={'entries': {'test': [{'version': '1.0.0'}]}})

            # Render TOML, of a table
            c.render(toml={'server': {'workers': 4}})

            # Render inline template
            c.render(inline='<%= 1 + 1 %>')

            # Render template "foo/bar.html.ep"
            c.render(template='foo/bar', format='html', handler='ep')

            # Render template "test.*.*" with arbitrary values "foo" and "bar"
            c.render(template='test', foo='test', bar=23)

            # Render template "test.xml.*"
            c.render(template='test', format='xml')

            # Render template "test.xml.*" (alternative)
            c.render('test', format='xml')
        """

        # Template may be first argument
        if template:
            args['template'] = template
        app = self.app
        plugins = app.plugins.emit_hook('before_render', self, args)

        # Localize "extends" and "layout" to allow argument overrides
        maybe, ts = args.get('mojo.maybe'), args.get('mojo.string')
        stash = self.stash()
        saved = [(key, stash[key]) for key in ('layout', 'extends') if key in stash]

        # Rendering to string
        if ts or maybe:
            saved.extend((key, stash.get(key, _MISSING)) for key in args)
        try:
            if ts:
                stash.pop('layout', None)
                stash.pop('extends', None)

            # All other arguments just become part of the stash
            stash.update(args)
            renderer = app.renderer
            output, format = renderer.render(self) or (None, None)

            # Maybe no 404
            if ts:
                if output is None:
                    return None
                return Pyjo.String.Bytes.new(output) if isinstance(output, bytes) else Pyjo.String.HTML.new(output)
            if output is None:
                if maybe:
                    return None
                raise Pyjo.Exception.new('Could not render a response')

            # The hooks change the output through a file object, as Mojo passes a reference to it
            ref = io.BytesIO(output) if isinstance(output, bytes) else io.StringIO(output)
            plugins.emit_hook('after_render', self, ref, format)
            return renderer.respond(self, ref.getvalue(), format, stash.get('status'))

        finally:
            for key, value in reversed(saved):
                if value is _MISSING:
                    stash.pop(key, None)
                else:
                    stash[key] = value

    def render_later(self) -> Self:
        """::

            c = c.render_later()

        Disable automatic rendering to delay response generation, only
        necessary if automatic rendering would result in a response. ::

            # Delayed rendering
            c.render_later()
            Pyjo.IOLoop.timer(2, lambda loop: c.render(text='Delayed by 2 seconds!'))
        """
        return self.stash({'mojo.rendered': True})

    def render_maybe(self, template: str | None = None, /, **args: Any) -> Any:
        """::

            boolean = c.render_maybe()
            boolean = c.render_maybe(foo='bar', baz=23)
            boolean = c.render_maybe('foo/index', format='html')

        Try to render content, but do not call
        :meth:`Pyjoyment.Plugin.DefaultHelpers` ``reply.not_found`` if no
        response could be generated, all arguments get localized automatically
        and are only available during this render operation, takes the same
        arguments as :meth:`render`. ::

            # Render template "index_local" only if it exists
            c.render_maybe('index_local') or c.render('index')
        """
        return self.render(template, **args, **{'mojo.maybe': True})

    def render_to_string(
        self, template: str | None = None, /, **args: Any
    ) -> Pyjo.String.HTML.object | Pyjo.String.Bytes.object | None:
        """::

            output = c.render_to_string('foo/index', format='pdf')

        Try to render content and return it wrapped in a
        :mod:`Pyjo.String.HTML` object, markup that templates do not escape, or
        a :mod:`Pyjo.String.Bytes` object or return ``None``, all arguments get
        localized automatically and are only available during this render
        operation, takes the same arguments as :meth:`render`. ::

            # Render inline template
            two = c.render_to_string(inline='<%= 1 + 1 %>')
        """
        return self.render(template, **args, **{'mojo.string': True})

    def rendered(self, status: int | str | None = None) -> Self:
        """::

            c = c.rendered()
            c = c.rendered(302)

        Finalize response and emit hook ``after_dispatch``, defaults to using a
        ``200`` response code. ::

            # Custom response
            c.res.headers.content_type = 'text/plain'
            c.res.body = b'Hello World!'
            c.rendered(200)
        """
        # Make sure we have a status
        if status:
            self.res.code = int(status)

        # Finish transaction
        stash = self.stash()
        if not stash.get('mojo.finished'):
            stash['mojo.finished'] = True
            res = self.res
            if not status and not res.code:
                res.code = 200

            # Disable auto rendering and stop timer
            app = self.render_later().app
            if not stash.get('mojo.static'):

                def message() -> str:
                    timing = self.helpers.timing
                    elapsed = timing.elapsed('mojo.timer')
                    elapsed = elapsed if elapsed is not None else 0
                    rps = timing.rps(elapsed)
                    code = res.code
                    msg = res.message or res.default_message(code)
                    return f'{code} {msg} ({elapsed:.15g}s, {rps if rps is not None else "??"}/s)'

                self.helpers.log().trace(message)

            app.plugins.emit_hook_reverse('after_dispatch', self)
            app.sessions.store(self)
        cast(Any, self._transaction()).resume()
        return self

    @property
    def req(self) -> 'Pyjo.Message.Request.object':
        """::

            req = c.req

        Get :mod:`Pyjo.Message.Request` object from :attr:`tx`. ::

            # Longer version
            req = c.tx.req

            # Extract request information
            id = c.req.request_id
            method = c.req.method
            url = c.req.url.to_abs()
            info = c.req.url.to_abs().userinfo
            host = c.req.url.to_abs().host
            agent = c.req.headers.user_agent
            custom = c.req.headers.header('Custom-Header')
            data = c.req.body
            string = c.req.text
            hash = c.req.params.to_dict()
            all = c.req.uploads
            value = c.req.json()
            foo = c.req.json('/23/foo')
            dom = c.req.dom()
            bar = c.req.dom('div.bar').first().text
        """
        return self._transaction().req

    @property
    def res(self) -> 'Pyjo.Message.Response.object':
        """::

            res = c.res

        Get :mod:`Pyjo.Message.Response` object from :attr:`tx`. ::

            # Longer version
            res = c.tx.res

            # Force file download by setting a response header
            c.res.headers.content_disposition = 'attachment; filename=foo.png;'

            # Use a custom response header
            c.res.headers.header('Custom-Header', 'whatever')

            # Make sure response is cached correctly
            c.res.headers.cache_control = 'public, max-age=300'
            c.res.headers.append('Vary', 'Accept-Encoding')
        """
        return self._transaction().res

    def send(self, msg: Any, cb: Callable[[Self], Any] | None = None) -> Self:
        """::

            c = c.send({'binary': data})
            c = c.send({'text': data})
            c = c.send({'json': {'test': [1, 2, 3]}})
            c = c.send([fin, rsv1, rsv2, rsv3, op, payload])
            c = c.send(chars)
            c = c.send(chars, lambda c: ...)

        Send message or frame non-blocking via WebSocket, the optional drain
        callback will be executed once all data has been written. This method
        will automatically respond to WebSocket handshake requests with a
        ``101`` response status, to establish the WebSocket connection. ::

            # Send "Text" message
            c.send('I ♥ Pyjoyment!')

            # Send JSON object as "Text" message
            c.send({'json': {'test': 'I ♥ Pyjoyment!'}})

            # Send JSON object as "Binary" message
            from Pyjo.JSON import encode_json
            c.send({'binary': encode_json({'test': 'I ♥ Pyjoyment!'})})

            # Send "Ping" frame
            from Pyjo.WebSocket import WS_PING
            c.send([1, 0, 0, 0, WS_PING, b'Hello World!'])

            # Make sure the first message has been written before continuing
            c.send('First message!', lambda c: c.send('Second message!'))

        For mostly idle WebSockets you might also want to increase the
        inactivity timeout with the helper ``inactivity_timeout`` of
        :mod:`Pyjoyment.Plugin.DefaultHelpers`, which usually defaults to
        ``30`` seconds. ::

            # Increase inactivity timeout for connection to 300 seconds
            c.inactivity_timeout(300)
        """
        tx: Any = self._transaction()
        if not tx.is_websocket:
            raise Pyjo.Exception.new('No WebSocket connection to send message to')
        tx.send(msg, _drain(self, cb))
        return self if tx.established else self.rendered(101)

    @overload
    def session(self) -> dict[str, Any]: ...  # pyright: ignore[reportOverlappingOverload]

    @overload
    def session(self, name: str, /) -> Any: ...

    @overload
    def session(self, values: dict[str, Any], /) -> Self: ...

    @overload
    def session(self, **values: Any) -> Self: ...

    def session(self, *args: Any, **values: Any) -> Any:
        """::

            session = c.session()
            foo = c.session('foo')
            c = c.session({'foo': 'bar'})
            c = c.session(foo='bar')

        Persistent data storage for the next few requests, all session data
        gets serialized with :mod:`Pyjo.JSON` and stored Base64 encoded in
        HMAC-SHA256 signed cookies, to prevent tampering. Note that cookies
        usually have a ``4096`` byte (4KiB) limit, depending on browser. ::

            # Manipulate session
            c.session()['foo'] = 'bar'
            foo = c.session()['foo']
            del c.session()['foo']

            # Expiration date in seconds from now (persists between requests)
            c.session(expiration=604800)

            # Expiration date as absolute epoch time (only valid for one request)
            c.session(expires=time.time() + 604800)

            # Delete whole session by setting an expiration date in the past
            c.session(expires=1)
        """
        stash = self.stash()
        if 'mojo.active_session' not in stash:
            self.app.sessions.load(self)

        # Dict
        session: dict[str, Any] = stash.setdefault('mojo.session', {})
        if not args and not values:
            return session

        # Get
        if len(args) == 1 and not isinstance(args[0], dict) and not values:
            return session.get(args[0])

        # Set
        for arg in args:
            session.update(arg)
        session.update(values)

        return self

    @overload
    def signed_cookie(self, name: str, /) -> str | None: ...

    @overload
    def signed_cookie(self, name: str, value: str, options: dict[str, Any] | None = None, /) -> Self: ...

    def signed_cookie(
        self, name: str, value: str | None = None, options: dict[str, Any] | None = None, /
    ) -> str | None | Self:
        """::

            value = c.signed_cookie('foo')
            c = c.signed_cookie('foo', 'bar')
            c = c.signed_cookie('foo', 'bar', {'path': '/'})

        Access signed request cookie values and create new signed response
        cookies. If there are multiple values sharing the same name, and you
        want to access more than just the last one, you can use
        :meth:`every_signed_cookie`. Cookies are cryptographically signed with
        HMAC-SHA256, to prevent tampering, and the ones failing signature
        verification will be automatically discarded.
        """
        # Request cookie
        if value is None:
            every = self.every_signed_cookie(name)
            return every[-1] if every else None

        # Response cookie
        sum = _hmac(f'{name}={value}', self.app.secrets[0])
        return self.cookie(name, f'{value}--{sum}', options)

    # stash(**values) with no values is stash(), which the first overload types
    @overload
    def stash(self) -> dict[str, Any]: ...  # pyright: ignore[reportOverlappingOverload]

    @overload
    def stash(self, name: str, /) -> Any: ...

    @overload
    def stash(self, values: dict[str, Any], /) -> Self: ...

    @overload
    def stash(self, **values: Any) -> Self: ...

    def stash(self, *args: Any, **values: Any) -> Any:
        """::

            hash = c.stash()
            foo = c.stash('foo')
            c = c.stash({'foo': 'bar', 'baz': 23})
            c = c.stash(foo='bar', baz=23)

        Non-persistent data storage and exchange for the current request,
        application wide default values can be set with
        :meth:`Pyjoyment.Pyjoyment_App.defaults`. Some stash values have a
        special meaning and are reserved, the full list is currently
        ``action``, ``app``, ``cb``, ``controller``, ``data``, ``extends``,
        ``format``, ``handler``, ``inactivity_timeout``, ``inline``,
        ``json``, ``layout``, ``namespace``, ``path``, ``request_timeout``,
        ``status``, ``template``, ``text``, ``toml``, ``variant`` and
        ``yaml``. Note that all stash values with a ``mojo.*`` prefix are
        reserved for internal use. ::

            # Remove value
            foo = c.stash().pop('foo')

            # Assign multiple values at once
            c.stash(foo='test', bar=23)
        """
        return Pyjo.Util._stash('stash', self, args, values)  # pyright: ignore[reportPrivateUsage]

    def url_for(
        self, target: 'str | dict[str, Any] | Pyjo.URL.object | None' = None, /, *args: dict[str, Any], **values: Any
    ) -> Pyjo.URL.object:
        """::

            url = c.url_for()
            url = c.url_for(name='sebastian')
            url = c.url_for({'name': 'sebastian'})
            url = c.url_for('test', name='sebastian')
            url = c.url_for('test', {'name': 'sebastian'})
            url = c.url_for('/index.html')
            url = c.url_for('//example.com/index.html')
            url = c.url_for('http://example.com/index.html')
            url = c.url_for('mailto:sri@example.com')
            url = c.url_for('#whatever')

        Generate a portable :mod:`Pyjo.URL` object with base for a path, URL or
        route. ::

            # Rebuild URL for the current route
            c.url_for()

            # Rebuild URL for the current route, but replace the "name" placeholder value
            c.url_for(name='sebastian')

            # Absolute URL for the current route
            c.url_for().to_abs()

            # Build URL for route "test" with two placeholder values
            c.url_for('test', name='sebastian', foo='bar')

            # "http://127.0.0.1:3000/index.html" if application was started with Pyjo.Server.Reload
            c.url_for('/index.html').to_abs()

            # "https://127.0.0.1:443/index.html" if application was started with Pyjo.Server.Reload
            c.url_for('/index.html').to_abs().set(scheme='https', port=443)

            # "/index.html?foo=bar" if application is deployed under "/"
            c.url_for('/index.html').set(query={'foo': 'bar'})

            # "/myapp/index.html?foo=bar" if application is deployed under "/myapp"
            c.url_for('/index.html').set(query={'foo': 'bar'})

        You can also use the helper ``url_with`` of
        :mod:`Pyjoyment.Plugin.DefaultHelpers` to inherit query parameters from
        the current request. ::

            # "/list?q=mojo&page=2" if current request was for "/list?q=mojo&page=1"
            c.url_with().set(query={'page': 2})
        """
        if target is None:
            target = ''

        # Absolute URL
        if isinstance(target, Pyjo.URL.object):
            return target
        if isinstance(target, str) and _ABSOLUTE.match(target):
            return Pyjo.URL.new(target)

        # Base
        url = Pyjo.URL.new()
        req = self.req
        url.base = req.url.base.clone()
        base = url.base
        base.userinfo = None

        # Relative URL
        path = url.path
        if isinstance(target, str) and target.startswith('/'):
            if (prefix := self.stash().get('path')) is not None:
                real = req.url.path.to_route()
                if m := re.search(rf'/?{re.escape(prefix)}$', real):
                    real = real[: m.start()] + target + real[m.end() :]
                target = real
            url.parse(target)

        # Route
        else:
            generated = self.match.path_for(target, *args, **values)
            if generated.get('path'):
                path.parse(generated['path'])
            if generated.get('websocket'):
                base.scheme = 'wss' if base.protocol == 'https' else 'ws'

        # Make path absolute (skip parsing if there is no base path and nothing would need to be decoded)
        base_path = base.path
        if base_path.to_str() == '' and '%' not in path.to_str():
            return url
        path.parts[0:0] = base_path.parts
        base_path.parts = []
        base_path.trailing_slash = False

        return url

    def url_for_asset(self, asset: str) -> Pyjo.URL.object:
        """::

            url = c.url_for_asset('/app.js')

        Generate a portable :mod:`Pyjo.URL` object with base for a static
        asset. In ``development`` mode the asset directories are scanned again
        every time, so assets that have just been rebuilt with a different name
        are found too.
        """
        if _ABSOLUTE.match(asset):
            return self.url_for(asset)

        # Bundlers can rebuild assets with new names at any time during development
        app = self.app
        if app.mode == 'development':
            app.static.warmup()
        return self.url_for(app.static.asset_path(asset))

    def url_for_file(self, file: str) -> Pyjo.URL.object:
        """::

            url = c.url_for_file('/index.html')

        Generate a portable :mod:`Pyjo.URL` object with base for a static file.
        """
        return self.url_for(file if _ABSOLUTE.match(file) else self.app.static.file_path(file))

    def write(self, chunk: bytes | None = None, cb: Callable[[Self], Any] | None = None) -> Self:
        """::

            c = c.write()
            c = c.write(b'')
            c = c.write(data)
            c = c.write(data, lambda c: ...)

        Write dynamic content non-blocking, the optional drain callback will be
        executed once all data has been written. Calling this method without a
        chunk of data will finalize the response headers and allow for dynamic
        content to be written later. ::

            # Keep connection alive (with Content-Length header)
            c.res.headers.content_length = 6
            c.write(b'Hel', lambda c: c.write(b'lo!'))

            # Close connection when finished (without Content-Length header)
            c.write(b'Hel', lambda c: c.write(b'lo!', lambda c: c.finish()))

        You can call :meth:`finish` or write an empty chunk of data at any time
        to end the stream. ::

            HTTP/1.1 200 OK
            Date: Sat, 13 Sep 2014 16:48:29 GMT
            Content-Length: 6
            Server: Pyjoyment (Python)

            Hello!

            HTTP/1.1 200 OK
            Connection: close
            Date: Sat, 13 Sep 2014 16:48:29 GMT
            Server: Pyjoyment (Python)

            Hello!

        For Comet (long polling) you might also want to increase the inactivity
        timeout with the helper ``inactivity_timeout`` of
        :mod:`Pyjoyment.Plugin.DefaultHelpers`, which usually defaults to
        ``30`` seconds. ::

            # Increase inactivity timeout for connection to 300 seconds
            c.inactivity_timeout(300)
        """
        self.res.content.write(chunk, _drain(self, cb))
        return self.rendered()

    def write_chunk(self, chunk: bytes | None = None, cb: Callable[[Self], Any] | None = None) -> Self:
        """::

            c = c.write_chunk()
            c = c.write_chunk(b'')
            c = c.write_chunk(data)
            c = c.write_chunk(data, lambda c: ...)

        Write dynamic content non-blocking with chunked transfer encoding, the
        optional drain callback will be executed once all data has been
        written. Calling this method without a chunk of data will finalize the
        response headers and allow for dynamic content to be written later. ::

            # Make sure previous chunk has been written before continuing
            c.write_chunk(b'H', lambda c: c.write_chunk(b'ell', lambda c: c.finish(b'o!')))

        You can call :meth:`finish` or write an empty chunk of data at any time
        to end the stream. ::

            HTTP/1.1 200 OK
            Date: Sat, 13 Sep 2014 16:48:29 GMT
            Transfer-Encoding: chunked
            Server: Pyjoyment (Python)

            1
            H
            3
            ell
            2
            o!
            0
        """
        self.res.content.write_chunk(chunk, _drain(self, cb))
        return self.rendered()

    def write_sse(self, event: dict[str, Any] | None = None, cb: Callable[[Self], Any] | None = None) -> Self:
        """::

            c = c.write_sse()
            c = c.write_sse(event)
            c = c.write_sse(event, lambda c: ...)

        Write Server-Sent Event (SSE) non-blocking, the optional drain callback
        will be executed once all data has been written. Calling this method
        without an event will finalize the response headers and allow for
        events to be written later. Note that this method is **EXPERIMENTAL**
        and might change without warning! ::

            # Send event with default "message" type
            c.write_sse({'text': 'Hello World!'})

            # You can send comments in regular intervals to keep the connection alive
            c.write_sse({'comment': 'Keep connection alive!'})

            # Make sure previous event has been written before continuing (id and type are optional)
            c.write_sse(
                {'id': 23, 'type': 'greeting', 'text': 'Hello World!'},
                lambda c: c.write_sse({'id': 24, 'type': 'farewell', 'text': 'Goodbye World!'}, lambda c: c.finish()),
            )
        """
        self.res.content.write_sse(event, _drain(self, cb))
        return self.rendered()

    def _transaction(self) -> 'Pyjo.Transaction.object':
        if (tx := self.tx) is None:
            raise Pyjo.Exception.new('Transaction already destroyed')
        return tx


# A drain callback of the transaction or the content that the controller gets
def _drain[C](c: C, cb: Callable[[C], Any] | None) -> Any:
    if cb is None:
        return None

    def drain(*args: Any) -> None:
        cb(c)

    return drain


# A helper bound to the controller, whose missing attribute names the call of the helper, as c.ua.get_p(...) is a
# common mistake for c.ua().get_p(...)
class _Helper(functools.partial[Any]):
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'", name=name, obj=self)
        app = self.args[0].app
        helpers: dict[str, Any] = app.renderer.helpers if app is not None else {}
        helper = next((h for h, cb in helpers.items() if cb is self.func), getattr(self.func, '__name__', 'helper'))
        raise AttributeError(
            f'Helper "{helper}" has no attribute "{name}", call the helper first: {helper}().{name}',
            name=name,
            obj=self,
        )


# Not in Mojolicious: Perl has no type checkers, and mojo.js declares the types of its helpers in an interface that
# TypeScript merges
class Helper[**P, R]:
    """::

        users = Pyjoyment.Controller.Helper(users)

    Declare the type of a helper, for type checkers and editors, as an
    attribute of a class with the name of the helper. The type is the one of
    the function of the helper, without the controller that the helper gets
    first, so that ``c.users()`` returns what ``users(c)`` does. The helper
    itself is still found by its name in the renderer of the application, as
    any other helper, so an application or a plugin can replace it with
    :meth:`Pyjoyment.Pyjoyment_App.helper`. It is not an action, as a route
    only reaches the methods of a controller. ::

        import Pyjoyment.Controller

        # The helper, which startup registers with app.helper('users', users)
        def users(c: Pyjoyment.Controller.object) -> MyApp.Model.Users.object:
            return c.app.users

        # The base class of the controllers of the application
        class Controller(Pyjoyment.Controller.object):
            users = Pyjoyment.Controller.Helper(users)

        class Users(Controller):
            def index(self) -> None:
                self.render(json=self.users().list())

    A plugin declares the types of its helpers in a class of its own, which
    the base class of the controllers inherits, as
    :class:`Pyjoyment.Plugin.DefaultHelpers.Helpers` declares the default
    helpers, which :mod:`Pyjoyment.Controller` and :mod:`Pyjoyment` have for
    type checkers. A prefix of nested helpers is a class of its own too::

        class Reply:
            not_found = Pyjoyment.Controller.Helper(_not_found)

        class Helpers:
            reply: Reply
    """

    def __init__(self, cb: Callable[Concatenate[Any, P], R]) -> None:
        self.cb = cb
        self.name = ''

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    @overload
    def __get__(self, obj: None, owner: type | None = None) -> Self: ...

    @overload
    def __get__(self, obj: Any, owner: type | None = None) -> Callable[P, R]: ...

    def __get__(self, obj: Any, owner: type | None = None) -> Self | Callable[P, R]:
        return self if obj is None else cast(Any, type(obj)).__getattr__(obj, self.name)


# The code of a helper that is got through its type, whose frame __getattr__ skips for the location of the caller
_HELPER_GET = vars(Helper)['__get__'].__code__


def _hmac(data: str, secret: str) -> str:
    return Pyjo.Util.hmac_sha256_sum(data.encode(), secret.encode())


new = Pyjoyment_Controller.new
object = Pyjoyment_Controller
Controller = Pyjoyment_Controller
