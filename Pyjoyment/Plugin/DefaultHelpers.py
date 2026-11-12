"""
Pyjoyment.Plugin.DefaultHelpers - Default helpers plugin
========================================================
::

    # Pyjoyment
    app.plugin('DefaultHelpers')

:mod:`Pyjoyment.Plugin.DefaultHelpers` is a collection of helpers for
:mod:`Pyjoyment`.

This is a core plugin, that means it is always enabled and its code a good
example for learning to build new plugins, you're welcome to fork it.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Helpers
-------

:mod:`Pyjoyment.Plugin.DefaultHelpers` implements the following helpers.

accepts ::

    formats = c.accepts()
    format = c.accepts('html', 'json', 'txt')

Select best possible representation for resource from ``format``
``GET``/``POST`` parameter, ``format`` stash value or ``Accept`` request header
with :meth:`Pyjoyment.Renderer.Pyjoyment_Renderer.accepts`, defaults to
returning the first extension if no preference could be detected. ::

    # Check if JSON is acceptable
    if c.accepts('json'):
        c.render(json={'hello': 'world'})

    # Check if JSON was specifically requested
    if c.accepts('', 'json'):
        c.render(json={'hello': 'world'})

    # Unsupported representation
    if not (format := c.accepts('html', 'json')):
        c.render(data=b'', status=204)

    # Detected representations to select from
    formats = c.accepts()

app ::

    %= app().secrets[0]

Alias for :attr:`Pyjoyment.Controller.Pyjoyment_Controller.app`.

b ::

    %= b(b'Joel is a slug').slugify()

Turn bytes into a :mod:`Pyjo.String.Bytes` object.

c ::

    %= c.c('a', 'b', 'c').shuffle().join()

Turn list into a :mod:`Pyjo.Collection` object. In templates, the variable
``c`` is the controller, which hides the helper.

config ::

    %= config('something')

Alias for :meth:`Pyjo.App.Pyjo_App.config`.

content ::

    %= content('foo', begin
      test
    % end)
    %= content('bar', 'Hello World!')
    %= content('foo')
    %= content('bar')
    %= content()

Store partial rendered content in a named buffer and retrieve it later,
defaults to retrieving the named buffer ``content``, which is used by the
renderer for the ``layout`` and ``extends`` features. New content will be
ignored if the named buffer is already in use.

content_for ::

    % content_for('foo', begin
      test
    % end)
    %= content_for('foo')

Same as ``content``, but appends content to named buffers if they are already
in use. ::

    % content_for('message', begin
      Hello
    % end)
    % content_for('message', begin
      world!
    % end)
    %= content('message')

content_with ::

    % content_with('foo', begin
      test
    % end)
    %= content_with('foo')

Same as ``content``, but replaces content of named buffers if they are already
in use. ::

    % content('message', begin
      world!
    % end)
    % content_with('message', begin
      Hello <%= content('message') %>
    % end)
    %= content('message')

csrf_token ::

    %= csrf_token()

Get CSRF token from ``session``, and generate one if none exists. The token is
masked with a fresh random value on every call to protect against BREACH
attacks.

current_route ::

    % if current_route('login'):
      Welcome to Pyjoyment!
    % end
    %= current_route()

Check or get name of current route.

dumper ::

    %= dumper({'some': 'data'})

Dump a Python data structure with :func:`Pyjo.Util.dumper`, very useful for
debugging.

exception_format ::

    format = c.exception_format()
    c = c.exception_format('txt')

Format for HTTP exceptions (``html``, ``json``, or ``txt``), defaults to the
value of :attr:`Pyjoyment.Pyjoyment_App.exception_format`.

extends ::

    % extends('blue')
    % extends('blue', title='Blue!')

Set ``extends`` stash value, all additional keyword arguments get merged into
the ``stash``.

flash ::

    foo = c.flash('foo')
    c = c.flash({'foo': 'bar'})
    c = c.flash(foo='bar')
    %= flash('foo')

Data storage persistent only for the next request, stored in the ``session``. ::

    # Show message after redirect
    c.flash(message='User created successfully!')
    c.redirect_to('show_user', id=23)

heartbeat ::

    c = c.heartbeat()
    c = c.heartbeat(15)
    c = c.heartbeat(60, 10)
    c = c.heartbeat(None)

Keep a stream alive while it waits, as for a model of language that is silent
for minutes, which the value ``heartbeat`` of the stash of a route sets
before its first action, so that proxies and load balancers with an idle
timeout of their own, and the inactivity timeout of the connection, keep it:
a comment ``: heartbeat`` of Server-Sent Events every ``interval`` seconds,
``20`` by default, once the response is a stream of ``text/event-stream``, or
the pings of a WebSocket, with
:meth:`Pyjo.Transaction.WebSocket.Pyjo_Transaction_WebSocket.heartbeat`,
which closes the connection of a peer that does not answer in ``timeout``
seconds. ``None`` stops it. ::

    # A stream of events whose connection stays open while it waits
    @app.routes.get('/events', {'heartbeat': 15})
    async def events(c):
        c.write_sse()
        async for chunk in llm.stream(c.param('q')):
            c.write_sse({'text': chunk})
        c.finish()

inactivity_timeout ::

    c = c.inactivity_timeout(3600)

Use :func:`Pyjo.IOLoop.stream` to find the current connection and increase
timeout if possible. ::

    # Longer version
    Pyjo.IOLoop.stream(c.tx.connection).timeout = 3600

include ::

    %= include('menubar')
    %= include('menubar', format='txt')

Alias for :meth:`Pyjoyment.Controller.Pyjoyment_Controller.render_to_string`.

is_fresh ::

    boolean = c.is_fresh()
    boolean = c.is_fresh(etag='abc')
    boolean = c.is_fresh(etag='W/"def"')
    boolean = c.is_fresh(last_modified=epoch)

Check freshness of request by comparing the ``If-None-Match`` and
``If-Modified-Since`` request headers to the ``ETag`` and ``Last-Modified``
response headers with :meth:`Pyjoyment.Static.Pyjoyment_Static.is_fresh`. ::

    # Add ETag/Last-Modified headers and check freshness before rendering
    if c.is_fresh(etag='abc', last_modified=1424985708):
        c.rendered(304)
    else:
        c.render(text='I ♥ Pyjoyment!')

layout ::

    % layout('green')
    % layout('green', title='Green!')

Set ``layout`` stash value, all additional keyword arguments get merged into
the ``stash``.

log ::

    log = c.log()

Alternative to :attr:`Pyjoyment.Pyjoyment_App.log` that includes
:attr:`Pyjo.Message.Request.Pyjo_Message_Request.request_id` with every log
message, as the field ``request_id`` of a message of JSON, see
:class:`Pyjo.Log.Field`. ::

    # Log message with context
    c.log().debug('This is a log message with request id')

    # Pass logger with context to model
    log = c.log()
    c.some_model().create({'foo': foo}, log)

param ::

    %= param('foo')

Alias for :meth:`Pyjoyment.Controller.Pyjoyment_Controller.param`.

proxy.get_p ::

    promise = c.proxy.get_p('http://example.com', {'Accept': '*/*'})

Perform non-blocking ``GET`` request and forward response as efficiently as
possible, takes the same arguments as
:attr:`Pyjo.UserAgent.Pyjo_UserAgent.get` and returns a :mod:`Pyjo.Promise`
object. ::

    # Forward with exception handling
    @c.proxy.get_p('http://mojolicious.org').catch
    def catch(err):
        c.log().debug(f'Proxy error: {err}')
        c.render(text='Something went wrong!', status=400)

proxy.post_p ::

    promise = c.proxy.post_p('http://example.com', {'Accept': '*/*'})

Perform non-blocking ``POST`` request and forward response as efficiently as
possible, takes the same arguments as
:attr:`Pyjo.UserAgent.Pyjo_UserAgent.post` and returns a :mod:`Pyjo.Promise`
object. ::

    # Forward with exception handling
    @c.proxy.post_p('example.com', form={'test': 'pass'}).catch
    def catch(err):
        c.log().debug(f'Proxy error: {err}')
        c.render(text='Something went wrong!', status=400)

proxy.start_p ::

    promise = c.proxy.start_p(Pyjo.Transaction.HTTP.new())

Perform non-blocking request for a custom :mod:`Pyjo.Transaction.HTTP` object
and forward response as efficiently as possible, returns a :mod:`Pyjo.Promise`
object. ::

    # Forward with exception handling
    tx = c.ua().build_tx('GET', 'http://mojolicious.org')

    @c.proxy.start_p(tx).catch
    def catch(err):
        c.log().debug(f'Proxy error: {err}')
        c.render(text='Something went wrong!', status=400)

    # Forward with custom request and response headers
    headers = c.req.headers.clone().dehop()
    headers.header('X-Proxy', 'Pyjo')
    tx = c.ua().build_tx('GET', 'http://example.com', headers.to_dict())
    c.proxy.start_p(tx)
    tx.res.content.once('body', lambda content: c.res.headers.header('X-Proxy', 'Pyjo'))

redirect_to ::

    c = c.redirect_to('named', foo='bar')
    c = c.redirect_to('named', {'foo': 'bar'})
    c = c.redirect_to('/index.html')
    c = c.redirect_to('http://example.com/index.html')

Prepare a ``302`` (if the status code is not already ``3xx``) redirect response
with ``Location`` header, takes the same arguments as ``url_for``. ::

    # Moved Permanently
    c.res.code = 301
    c.redirect_to('some_route')

    # Temporary Redirect
    c.res.code = 307
    c.redirect_to('some_route')

reply.asset ::

    c.reply.asset(Pyjo.Asset.File.new())

Reply with a :mod:`Pyjo.Asset.File` or :mod:`Pyjo.Asset.Memory` object using
:meth:`Pyjoyment.Static.Pyjoyment_Static.serve_asset`, and perform content
negotiation with ``Range``, ``If-Modified-Since`` and ``If-None-Match``
headers. ::

    # Serve asset with custom modification time
    asset = Pyjo.Asset.Memory.new()
    asset.add_chunk(b'Hello World!').mtime = 784111777
    c.res.headers.content_type = 'text/plain'
    c.reply.asset(asset)

    # Serve static file if it exists
    if asset := c.app.static.file('images/logo.png'):
        c.res.headers.content_type = 'image/png'
        c.reply.asset(asset)

reply.exception ::

    c = c.reply.exception('Oops!')
    c = c.reply.exception(Pyjo.Exception.new())

Render an exception response in the appropriate format by delegating to more
specific exception helpers.

reply.file ::

    c.reply.file('/etc/passwd')

Reply with a static file from an absolute path anywhere on the file system
using :attr:`Pyjoyment.Pyjoyment_App.static`. ::

    # Longer version
    c.reply.asset(Pyjo.Asset.File.new(path='/etc/passwd'))

    # Serve file from an absolute path with a custom content type
    c.res.headers.content_type = 'application/myapp'
    c.reply.file('/home/sri/foo.txt')

    # Serve file from a secret application directory
    c.reply.file(c.app.home.child('secret', 'file.txt'))

reply.html_exception ::

    c = c.reply.html_exception('Oops!')
    c = c.reply.html_exception(Pyjo.Exception.new())

Render the exception template ``exception.$mode.$format.*`` or
``exception.$format.*`` and set the response status code to ``500``. Also sets
the stash values ``exception`` to a :mod:`Pyjo.Exception` object and
``snapshot`` to a copy of the ``stash`` for use in the templates.

reply.html_not_found ::

    c = c.reply.html_not_found()

Render the not found template ``not_found.$mode.$format.*`` or
``not_found.$format.*`` and set the response status code to ``404``. Also sets
the stash value ``snapshot`` to a copy of the ``stash`` for use in the
templates.

reply.json_exception ::

    c = c.reply.json_exception('Oops!')
    c = c.reply.json_exception(Pyjo.Exception.new())

Render a JSON response and set the response status to ``500``.

reply.json_not_found ::

    c = c.reply.json_not_found()

Render a JSON response and set the response status to ``404``.

reply.not_found ::

    c = c.reply.not_found()

Render a not found response in the appropriate format by delegating to more
specific exception helpers.

reply.static ::

    c.reply.static('images/logo.png')
    c.reply.static('../lib/MyApp.py')

Reply with a static file using :attr:`Pyjoyment.Pyjoyment_App.static`, usually
from the ``public`` directories or ``DATA`` sections of your application. Note
that this helper uses a relative path, but does not protect from traversing to
parent directories. ::

    # Serve file from a relative path with a custom content type
    c.res.headers.content_type = 'application/myapp'
    c.reply.static('foo.txt')

reply.txt_exception ::

    c = c.reply.txt_exception('Oops!')
    c = c.reply.txt_exception(Pyjo.Exception.new())

Render a plain text response and set the response status to ``500``.

reply.txt_not_found ::

    c = c.reply.txt_not_found()

Render a plain text response and set the response status to ``404``.

request_timeout ::

    c = c.request_timeout(120)

The most time in seconds from now to the end of the response, as for a
request that waits for a model of language, which the value
``request_timeout`` of the stash of a route sets before its first action.
When it passes, the actions that are coroutine functions are cancelled where
they wait, with the requests of :mod:`Pyjo.UserAgent` that they wait for, and
the request gets an empty ``504`` response, or the connection closes when the
response has started already, as a stream. A later call replaces the time. ::

    # A route whose response has two minutes at most
    app.routes.post('/chat', {'request_timeout': 120}).to('chat#reply')

respond_to ::

    c = c.respond_to(json={'json': {'message': 'Welcome!'}}, html={'template': 'welcome'}, any=lambda c: ...)

Automatically select best possible representation for resource from ``format``
``GET``/``POST`` parameter, ``format`` stash value or ``Accept`` request
header, defaults to
:attr:`Pyjoyment.Renderer.Pyjoyment_Renderer.default_format` or rendering an
empty ``204`` response. Each representation can be handled with a callback or
a dict containing arguments to be passed to
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.render`. ::

    # Everything else than "json" and "xml" gets a 204 response
    c.respond_to(
        json=lambda c: c.render(json={'just': 'works'}),
        xml={'text': '<just>works</just>'},
        any={'data': b'', 'status': 204},
    )

For more advanced negotiation logic you can also use ``accepts``.

session ::

    %= session('foo')

Alias for :meth:`Pyjoyment.Controller.Pyjoyment_Controller.session`.

stash ::

    %= stash('foo')
    % stash(foo='bar')

Alias for :meth:`Pyjoyment.Controller.Pyjoyment_Controller.stash`. ::

    %= stash('name') or 'Somebody'

timing.begin ::

    c.timing.begin('foo')

Create named timestamp for ``timing.elapsed``.

timing.elapsed ::

    elapsed = c.timing.elapsed('foo')

Return fractional amount of time in seconds since named timstamp has been
created with ``timing.begin`` or ``None`` if no such timestamp exists. ::

    # Log timing information
    c.timing.begin('database_stuff')
    ...
    elapsed = c.timing.elapsed('database_stuff')
    c.app.log.debug(f'Database stuff took {elapsed} seconds')

timing.rps ::

    rps = c.timing.rps(0.001)

Return fractional number of requests that could be performed in one second if
every singe one took the given amount of time in seconds or ``None`` if the
number is too low. ::

    # Log more timing information
    c.timing.begin('web_stuff')
    ...
    elapsed = c.timing.elapsed('web_stuff')
    rps = c.timing.rps(elapsed)
    c.app.log.debug(f'Web stuff took {elapsed} seconds ({rps} per second)')

timing.server_timing ::

    c.timing.server_timing('metric')
    c.timing.server_timing('metric', 'Some Description')
    c.timing.server_timing('metric', 'Some Description', 0.001)

Create ``Server-Timing`` header with optional description and duration. ::

    # "Server-Timing: miss"
    c.timing.server_timing('miss')

    # "Server-Timing: dc;desc=atl"
    c.timing.server_timing('dc', 'atl')

    # "Server-Timing: db;desc=Database;dur=0.0001"
    c.timing.begin('database_stuff')
    ...
    elapsed = c.timing.elapsed('database_stuff')
    c.timing.server_timing('db', 'Database', elapsed)

    # "Server-Timing: miss, dc;desc=atl"
    c.timing.server_timing('miss')
    c.timing.server_timing('dc', 'atl')

title ::

    %= title()
    % title('Welcome!')
    % title('Welcome!', foo='bar')

Get or set ``title`` stash value, all additional keyword arguments get merged
into the ``stash``.

ua ::

    %= ua().get('mojolicious.org').result.dom().at('title').text

Alias for :attr:`Pyjo.App.Pyjo_App.ua`.

url_for ::

    %= url_for('named', foo='bar', baz='yada')

Alias for :meth:`Pyjoyment.Controller.Pyjoyment_Controller.url_for`. ::

    %= url_for('/index.html').set(query={'foo': 'bar'})

url_for_asset ::

    %= url_for_asset('/app.js')

Alias for :meth:`Pyjoyment.Controller.Pyjoyment_Controller.url_for_asset`.

url_for_file ::

    %= url_for_file('/index.html')

Alias for :meth:`Pyjoyment.Controller.Pyjoyment_Controller.url_for_file`.

url_with ::

    %= url_with('named', foo='bar', baz='yada')

Does the same as ``url_for``, but inherits query parameters from the current
request. ::

    %= url_with().set(query={'page': 2})

validation ::

    v = c.validation()

Get :mod:`Pyjoyment.Validator.Validation` object for current request to
validate file uploads as well as ``GET`` and ``POST`` parameters extracted
from the query string and ``application/x-www-form-urlencoded`` or
``multipart/form-data`` message body. Parts of the request body need to be
loaded into memory to parse ``POST`` parameters, so you have to make sure it
is not excessively large. There's a 16MiB limit for requests by default. ::

    # Validate GET/POST parameter
    v = c.validation()
    v.required('title', 'trim').size(3, 50)
    title = v.param('title')

    # Validate file upload
    v = c.validation()
    v.required('tarball').upload().size(1, 1048576)
    tarball = v.param('tarball')

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Plugin::DefaultHelpers
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Plugin/DefaultHelpers.pm>`_ of Mojolicious 9.49.
"""

import Pyjo.Asset
import Pyjo.Asset.File
import Pyjo.Collection
import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Log
import Pyjo.Promise
import Pyjo.String.Bytes
import Pyjo.String.HTML
import Pyjo.String.Unicode
import Pyjo.URL
import Pyjo.UserAgent
import Pyjoyment.Plugin

from Pyjo.Util import dumper, random_bytes
from Pyjoyment.Controller import Helper

import functools
import time
import weakref

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    import Pyjoyment
    import Pyjoyment.Controller
    import Pyjoyment.Validator.Validation

    type Controller = Pyjoyment.Controller.object


class Pyjoyment_Plugin_DefaultHelpers(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.DefaultHelpers` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> None:
        """::

            plugin.register(Pyjoyment.new())

        Register helpers in :mod:`Pyjoyment` application.
        """
        # Controller alias helpers
        app.helper('app', _app)
        for name in ('param', 'stash', 'session', 'url_for', 'url_for_asset', 'url_for_file'):
            app.helper(name, _alias(name))

        # Stash key shortcuts (should not generate log messages)
        for name in ('extends', 'layout', 'title'):
            app.helper(name, _stash_key(name))

        app.helper('accepts', _accepts)
        app.helper('b', _b)
        # Not in Mojolicious: u, as Pyjo.String.Unicode is the Mojo::ByteStream of characters
        app.helper('u', _u)
        app.helper('c', _c)
        app.helper('config', _config)

        app.helper('content', functools.partial(_content, False, False))
        app.helper('content_for', functools.partial(_content, True, False))
        app.helper('content_with', functools.partial(_content, False, True))

        app.helper('csrf_token', _csrf_token)
        app.helper('current_route', _current_route)
        app.helper('exception_format', _exception_format)
        app.helper('flash', _flash)
        app.helper('heartbeat', _heartbeat)
        app.helper('inactivity_timeout', _inactivity_timeout)
        app.helper('is_fresh', _is_fresh)
        app.helper('redirect_to', _redirect_to)
        app.helper('request_timeout', _request_timeout)
        app.helper('respond_to', _respond_to)
        app.helper('url_with', _url_with)
        app.helper('validation', _validation)

        app.helper('dumper', _dumper)
        app.helper('include', _include)

        app.helper('log', _log)

        app.helper('proxy.get_p', functools.partial(_proxy_method_p, 'GET'))
        app.helper('proxy.post_p', functools.partial(_proxy_method_p, 'POST'))
        app.helper('proxy.start_p', _proxy_start_p)

        app.helper('reply.asset', _asset)
        app.helper('reply.file', _file)
        app.helper('reply.static', _static)

        app.helper('reply.exception', _exception)
        app.helper('reply.not_found', _not_found)
        app.helper('reply.http_exception', _http_exception)
        app.helper('reply.http_not_found', _http_not_found)
        app.helper('reply.html_exception', functools.partial(_development, 'exception'))
        app.helper('reply.html_not_found', functools.partial(_development, 'not_found'))
        app.helper('reply.json_exception', _json_exception)
        app.helper('reply.json_not_found', _json_not_found)
        app.helper('reply.txt_exception', _txt_exception)
        app.helper('reply.txt_not_found', _txt_not_found)

        app.helper('timing.begin', _timing_begin)
        app.helper('timing.elapsed', _timing_elapsed)
        app.helper('timing.rps', _timing_rps)
        app.helper('timing.server_timing', _timing_server_timing)

        app.helper('ua', _ua)


def _accepts(c: 'Controller', *formats: str) -> list[str] | str | None:
    return c.app.renderer.accepts(c, *formats)


def _alias(name: str) -> Callable[..., Any]:
    def helper(c: 'Controller', *args: Any, **values: Any) -> Any:
        return getattr(c, name)(*args, **values)

    return helper


def _app(c: 'Controller') -> 'Pyjoyment.object':
    return c.app


def _asset(c: 'Controller', asset: Pyjo.Asset.object) -> 'Controller':
    c.app.static.serve_asset(c, asset)
    return c.rendered()


def _b(c: 'Controller', *args: Any) -> Pyjo.String.Bytes.object:
    return Pyjo.String.Bytes.new(*args)


def _block(content: Any) -> Any:
    return content() if callable(content) else content


def _c(c: 'Controller', *args: Any) -> Pyjo.Collection.object[Any]:
    return Pyjo.Collection.new(*args)


def _config(c: 'Controller', *args: Any, **values: Any) -> Any:
    return c.app.config(*args, **values)


def _content(append: bool, replace: bool, c: 'Controller', name: str | None = None, content: Any = None) -> Any:
    name = name or 'content'

    hash = c.stash().setdefault('mojo.content', {})
    if content is not None:
        if append:
            # Joined as strings, as Mojo does: the concatenation of markup would escape a string that is not markup
            hash[name] = str(hash.get(name) or '') + str(_block(content))
        if replace:
            hash[name] = _block(content)
        elif hash.get(name) is None:
            hash[name] = _block(content)

    content = hash.get(name)
    return Pyjo.String.HTML.new(content if content is not None else '')


def _convert_to_exception(e: Any) -> Pyjo.Exception.object:
    return e if isinstance(e, Pyjo.Exception.object) else Pyjo.Exception.new(e)


def _csrf_token(c: 'Controller') -> str:
    # Generate token and store it in the session
    session = c.session()
    if not session.get('csrf_token'):
        session['csrf_token'] = random_bytes(20).hex()

    # Mask token to protect against BREACH attacks
    mask = random_bytes(20)
    return mask.hex() + bytes(a ^ b for a, b in zip(mask, bytes.fromhex(session['csrf_token']), strict=False)).hex()


def _current_route(c: 'Controller', *args: str) -> str | bool | None:
    if (route := c.match.endpoint) is None:
        return ''
    return route.name == args[0] if args else route.name


def _development(page: str, c: 'Controller', e: Any = None) -> 'Controller':
    if page == 'exception':
        c.helpers.log().error((e := _convert_to_exception(e)).inspect())

    # Filtered stash snapshot
    stash = c.stash()
    stash['snapshot'] = {
        key: 'DUMMY' if key == 'app' else value
        for key, value in stash.items()
        if not key.startswith('mojo.') and value is not None
    }
    stash['exception'] = e if page == 'exception' else None

    # Render with fallbacks
    app = c.app
    mode = app.mode
    options = {
        'format': stash.get('format') or app.renderer.default_format,
        'handler': None,
        'status': 500 if page == 'exception' else 404,
        'template': f'{page}.{mode}',
    }
    # Renamed from Mojolicious: the bundled templates are in pyjo/, where Mojo has them in mojo/
    bundled = 'pyjo/' + ('debug' if mode == 'development' else page)
    if _fallbacks(c, options, page, bundled):
        return c
    _fallbacks(c, {**options, 'format': 'html'}, page, bundled)
    return c


def _dumper(c: 'Controller', *values: Any) -> str:
    return dumper(*values)


def _exception(c: 'Controller', e: Any = None) -> Any:
    return c.helpers.reply.http_exception(e)


def _exception_format(c: 'Controller', *args: str) -> Any:
    stash = c.stash()
    if not stash.get('mojo.exception_format'):
        stash['mojo.exception_format'] = c.app.exception_format
    if not args:
        return stash['mojo.exception_format']
    stash['mojo.exception_format'] = args[0]
    return c


def _fallbacks(c: 'Controller', options: dict[str, Any], template: str, bundled: str) -> bool:
    # Mode specific template
    if c.render_maybe(**options):
        return True

    # Normal template
    if c.render_maybe(**{**options, 'template': template}):
        return True

    # Inline template
    stash = c.stash()
    if options['format'] != 'html':
        return False
    stash.pop('extends', None)
    stash.pop('layout', None)
    return bool(c.render_maybe(bundled, **{**options, 'handler': 'ep'}))


def _file(c: 'Controller', path: Any) -> 'Controller':
    return _asset(c, Pyjo.Asset.File.new(path=str(path)))


def _flash(c: 'Controller', *args: Any, **values: Any) -> Any:
    # Check old flash
    session = c.session()
    if len(args) == 1 and not isinstance(args[0], dict) and not values:
        return flash.get(args[0]) if (flash := session.get('flash')) is not None else None

    # Initialize new flash and merge values
    new_flash = session.setdefault('new_flash', {})
    for arg in args:
        new_flash.update(arg)
    new_flash.update(values)

    return c


def _http_exception(c: 'Controller', e: Any) -> Any:
    format = c.exception_format()
    if format == 'txt':
        return c.helpers.reply.txt_exception(e)
    if format == 'json':
        return c.helpers.reply.json_exception(e)
    return c.helpers.reply.html_exception(e)


def _http_not_found(c: 'Controller') -> Any:
    format = c.exception_format()
    if format == 'txt':
        return c.helpers.reply.txt_not_found()
    if format == 'json':
        return c.helpers.reply.json_not_found()
    return c.helpers.reply.html_not_found()


# Not in Mojolicious: the comments of Server-Sent Events that keep a stream alive, which Mojolicious leaves to the
# application, and the pings of a WebSocket
def _heartbeat(c: 'Controller', interval: float | None = 20, timeout: float | None = 20) -> 'Controller':
    if (tx := c.tx) is None:
        return c
    if tx.is_websocket:
        cast(Any, tx).heartbeat(interval, timeout)
        return c

    stash = c.stash()
    loop = Pyjo.IOLoop.singleton
    if (old := stash.pop('pyjo.heartbeat', None)) is not None:
        loop.remove(old)
    if interval is None or tx.is_finished:
        return c

    # Weakly, as the loop keeps the timer, and the transaction its subscribers
    ref = weakref.ref(c)

    def beat(loop: Pyjo.IOLoop.object) -> None:
        if (c := ref()) is None or (tx := c.tx) is None or tx.is_finished:
            return
        res = c.res
        if res.content.is_dynamic and (res.headers.content_type or '').startswith('text/event-stream'):
            c.write_sse({'comment': 'heartbeat'})

    id = stash['pyjo.heartbeat'] = loop.recurring(interval, beat)

    def finish(tx: Any) -> None:
        loop.remove(id)

    tx.on('finish', finish)
    return c


def _inactivity_timeout(c: 'Controller', timeout: float) -> 'Controller':
    tx: Any = c.tx
    if stream := Pyjo.IOLoop.stream(tx.connection or ''):
        stream.timeout = timeout
    return c


def _include(c: 'Controller', *args: Any, **values: Any) -> Pyjo.String.HTML.object | Pyjo.String.Bytes.object | None:
    return c.render_to_string(*args, **values)


def _is_fresh(c: 'Controller', *, etag: str | None = None, last_modified: float | None = None) -> bool:
    return c.app.static.is_fresh(c, etag=etag, last_modified=last_modified)


def _json_exception(c: 'Controller', e: Any) -> Any:
    c.stash()['exception'] = _convert_to_exception(e)
    if c.app.mode == 'development':
        return c.render(json={'error': e}, status=500)
    return c.render(json={'error': 'Internal Server Error'}, status=500)


def _json_not_found(c: 'Controller') -> Any:
    return c.render(json={'error': 'Not Found'}, status=404)


def _log(c: 'Controller') -> Pyjo.Log.object:
    stash = c.stash()
    if not stash.get('mojo.log'):
        # Not in Mojolicious: the request id as a field of its own of a message of JSON
        id = c.req.request_id
        stash['mojo.log'] = c.app.log.context(Pyjo.Log.Field('request_id', id, f'[{id}]'))
    return stash['mojo.log']


def _not_found(c: 'Controller') -> Any:
    return c.helpers.reply.http_not_found()


def _proxy_method_p(method: str, c: 'Controller', *args: Any, **kwargs: Any) -> Pyjo.Promise.object:
    return _proxy_start_p(c, c.ua().build_tx(method, *args, **kwargs))


def _proxy_start_p(c: 'Controller', source_tx: Any) -> Pyjo.Promise.object:
    tx: Any = c.render_later().tx

    promise = Pyjo.Promise.new()
    source = weakref.ref(source_tx)

    def body(source_content: Any) -> None:
        source_tx = source()
        if source_tx is None:
            return

        source_res = source_tx.res
        res = tx.res
        content = res.content
        res.code = source_res.code
        res.message = source_res.message
        headers = source_res.headers.clone().dehop()
        content.headers = headers
        promise.resolve()

        source_stream = Pyjo.IOLoop.stream(source_tx.connection)
        if not (stream := Pyjo.IOLoop.stream(tx.connection)):
            return

        write = content.write_chunk if source_content.is_chunked else content.write

        def read(source_content: Any, data: bytes) -> None:
            write(data if len(data) else None)
            tx.resume()

            # Throttle transparently when backpressure rises
            if stream.can_write:
                return
            source_stream.stop()

            @stream.once('drain')
            def drain(stream: Any) -> None:
                source_stream.start()

        source_content.unsubscribe('read').on('read', read)

        def finish(source_res: Any) -> None:
            write(b'')
            tx.resume()

        source_res.once('finish', finish)

    source_tx.res.content.set(auto_upgrade=False, auto_decompress=False).once('body', body)

    @source_tx.once('finish')
    def finish(source_tx: Any) -> None:
        promise.reject(_tx_error(source_tx))

    def ignore(*args: Any) -> None:
        pass

    c.ua().start_p(source_tx).catch(ignore)

    return promise


def _redirect_to(c: 'Controller', *args: Any, **values: Any) -> 'Controller':
    # Don't override 3xx status
    res = c.res
    res.headers.location = c.url_for(*args, **values).to_str()
    return c.rendered(None if res.is_redirect else 302)


# Not in Mojolicious: the deadline of a request, which Mojolicious leaves to the inactivity timeout of its connection
def _request_timeout(c: 'Controller', timeout: float) -> 'Controller':
    stash = c.stash()
    loop = Pyjo.IOLoop.singleton
    if (old := stash.pop('pyjo.request_timeout', None)) is not None:
        loop.remove(old)
    if (tx := c.tx) is None or tx.is_finished:
        return c

    # Weakly, as the loop keeps the timer, and the transaction its subscribers
    ref = weakref.ref(c)

    def expired(loop: Pyjo.IOLoop.object) -> None:
        if (c := ref()) is not None:
            _expire(c, timeout)

    id = stash['pyjo.request_timeout'] = loop.timer(timeout, expired)

    def finish(tx: Any) -> None:
        loop.remove(id)

    tx.on('finish', finish)
    return c


def _expire(c: 'Controller', timeout: float) -> None:
    stash = c.stash()
    stash.pop('pyjo.request_timeout', None)
    if (tx := c.tx) is None or tx.is_finished:
        return
    c.app.log.info(f'Request timeout of {timeout:g} seconds')

    # The actions that wait, which nothing renders the response of anymore
    stash['pyjo.cancelled'] = True
    for action in stash.get('pyjo.actions', ()):
        if (promise := action()) is not None:
            promise.cancel()

    # A response that has not started yet, or the end of its connection
    if not stash.get('mojo.finished') and not c.res.content.is_dynamic and not tx.is_websocket:
        c.res.body = b''
        c.rendered(504)
    elif (id := tx.connection) is not None:
        Pyjo.IOLoop.remove(id)


def _respond_to(c: 'Controller', *args: dict[str, Any], **values: Any) -> 'Controller':
    targets = args[0] if args else values

    # Find target
    target = None
    renderer = c.app.renderer
    formats: list[str] = renderer.accepts(c) or []  # pyright: ignore[reportAssignmentType]
    for format in formats or [renderer.default_format]:
        if not (target := targets.get(format)):
            continue
        c.stash()['format'] = format
        break

    # Fallback
    if not target:
        if not (target := targets.get('any')):
            return c.rendered(204)
        c.stash().pop('format', None)

    # Dispatch
    if callable(target):
        target(c)
    else:
        c.render(**target)

    return c


def _timing_begin(c: 'Controller', name: str) -> None:
    c.stash().setdefault('mojo.timing', {})[name] = time.time()


def _timing_elapsed(c: 'Controller', name: str) -> float | None:
    if (started := c.stash().get('mojo.timing', {}).get(name)) is None:
        return None
    return time.time() - started


def _timing_rps(c: 'Controller', elapsed: float | str) -> str | None:
    return None if float(elapsed) == 0 else f'{1 / float(elapsed):.3f}'


def _timing_server_timing(c: 'Controller', metric: str, desc: str | None = None, dur: Any = None) -> None:
    value = metric
    if desc is not None:
        value += f';desc="{desc}"'
    if dur is not None:
        value += f';dur={dur}'
    c.res.headers.append('Server-Timing', value)


def _tx_error(tx: Any) -> str:
    error: dict[str, Any] = tx.error or {}
    return str(error.get('message') or 'Unknown error')


def _txt_exception(c: 'Controller', e: Any) -> Any:
    c.stash()['exception'] = _convert_to_exception(e)
    if c.app.mode == 'development':
        return c.render(text=str(e), format='txt', status=500)
    return c.render(text='Internal Server Error', format='txt', status=500)


def _txt_not_found(c: 'Controller') -> Any:
    return c.render(text='Not Found', format='txt', status=404)


def _static(c: 'Controller', file: str) -> 'Controller':
    if not c.app.static.serve(c, file):
        raise Pyjo.Exception.new(f'Static file "{file}" not found')
    return c.rendered()


def _stash_key(name: str) -> Callable[..., Any]:
    def helper(c: 'Controller', *args: Any, **values: Any) -> Any:
        if not args and not values:
            return c.stash(name)
        return c.stash({name: args[0]} if args else {}, **values)

    return helper


def _url_with(c: 'Controller', *args: Any, **values: Any) -> Pyjo.URL.object:
    url = c.url_for(*args, **values)
    url.query = c.req.url.query.clone()
    return url


def _u(c: 'Controller', *args: Any) -> Pyjo.String.Unicode.object:
    return Pyjo.String.Unicode.new(*args)


def _ua(c: 'Controller') -> Pyjo.UserAgent.object:
    return c.app.ua


def _validation(c: 'Controller') -> 'Pyjoyment.Validator.Validation.object':
    stash = c.stash()
    if (v := stash.get('mojo.validation')) is not None:
        return v

    req = c.req
    token = c.session().get('csrf_token')
    header = req.headers.header('X-CSRF-Token')
    hash: dict[str, Any] = dict(req.params.to_dict())
    if token and header and hash.get('csrf_token') is None:
        hash['csrf_token'] = header
    for name in [upload.name for upload in req.uploads()]:
        if name is not None:
            hash[name] = req.every_upload(name)
    v = c.app.validator.validation().set(input=hash, csrf_token=token)
    stash['mojo.validation'] = v
    return v


# Not in Mojolicious: the types of the helpers, for type checkers, which Pyjoyment.Controller and Pyjoyment have
class ProxyHelpers:
    """
    The types of the nested helpers ``proxy.*``, for type checkers.
    """

    get_p = Helper(functools.partial(_proxy_method_p, 'GET'))
    post_p = Helper(functools.partial(_proxy_method_p, 'POST'))
    start_p = Helper(_proxy_start_p)


class ReplyHelpers:
    """
    The types of the nested helpers ``reply.*``, for type checkers.
    """

    asset = Helper(_asset)
    file = Helper(_file)
    static = Helper(_static)

    exception = Helper(_exception)
    not_found = Helper(_not_found)
    http_exception = Helper(_http_exception)
    http_not_found = Helper(_http_not_found)
    html_exception = Helper(functools.partial(_development, 'exception'))
    html_not_found = Helper(functools.partial(_development, 'not_found'))
    json_exception = Helper(_json_exception)
    json_not_found = Helper(_json_not_found)
    txt_exception = Helper(_txt_exception)
    txt_not_found = Helper(_txt_not_found)


class TimingHelpers:
    """
    The types of the nested helpers ``timing.*``, for type checkers.
    """

    begin = Helper(_timing_begin)
    elapsed = Helper(_timing_elapsed)
    rps = Helper(_timing_rps)
    server_timing = Helper(_timing_server_timing)


class Helpers:
    """
    The types of the helpers of :mod:`Pyjoyment.Plugin.DefaultHelpers`, for
    type checkers and editors, which :mod:`Pyjoyment.Controller` and
    :mod:`Pyjoyment` have, while the helpers themselves are found in the
    renderer of the application at run time. See
    :class:`Pyjoyment.Controller.Helper`.
    """

    app = Helper(_app)
    param = Helper(_alias('param'))
    stash = Helper(_alias('stash'))
    session = Helper(_alias('session'))
    url_for = Helper(_alias('url_for'))
    url_for_asset = Helper(_alias('url_for_asset'))
    url_for_file = Helper(_alias('url_for_file'))

    extends = Helper(_stash_key('extends'))
    layout = Helper(_stash_key('layout'))
    title = Helper(_stash_key('title'))

    accepts = Helper(_accepts)
    b = Helper(_b)
    u = Helper(_u)
    c = Helper(_c)
    config = Helper(_config)

    content = Helper(functools.partial(_content, False, False))
    content_for = Helper(functools.partial(_content, True, False))
    content_with = Helper(functools.partial(_content, False, True))

    csrf_token = Helper(_csrf_token)
    current_route = Helper(_current_route)
    exception_format = Helper(_exception_format)
    flash = Helper(_flash)
    heartbeat = Helper(_heartbeat)
    inactivity_timeout = Helper(_inactivity_timeout)
    is_fresh = Helper(_is_fresh)
    redirect_to = Helper(_redirect_to)
    request_timeout = Helper(_request_timeout)
    respond_to = Helper(_respond_to)
    url_with = Helper(_url_with)
    validation = Helper(_validation)

    dumper = Helper(_dumper)
    include = Helper(_include)

    log = Helper(_log)

    proxy: ProxyHelpers
    reply: ReplyHelpers
    timing: TimingHelpers

    ua = Helper(_ua)


new = Pyjoyment_Plugin_DefaultHelpers.new
object = Pyjoyment_Plugin_DefaultHelpers
DefaultHelpers = Pyjoyment_Plugin_DefaultHelpers
