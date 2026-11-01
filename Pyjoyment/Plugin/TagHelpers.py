"""
Pyjoyment.Plugin.TagHelpers - Tag helpers plugin
================================================
::

    # Pyjoyment
    app.plugin('TagHelpers')

    # Pyjoyment.Lite
    plugin('TagHelpers')

:mod:`Pyjoyment.Plugin.TagHelpers` is a collection of HTML tag helpers for
:mod:`Pyjoyment`, based on the
`HTML Living Standard <https://html.spec.whatwg.org>`_.

Most form helpers can automatically pick up previous input values and will
show them as default. You can also use the helper ``param`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers` to set them manually and let necessary
attributes always be generated automatically. ::

    % if not param('country'):
    %   param('country', 'germany')
    % end
    <%= radio_button('country', 'germany') %> Germany
    <%= radio_button('country', 'france') %> France
    <%= radio_button('country', 'uk') %> UK

For fields that failed validation with the helper ``validation`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers` the ``field-with-error`` class will be
automatically added through ``tag_with_error``, to make styling with CSS
easier. ::

    <input class="field-with-error" name="age" type="text" value="250">

The helpers take the attributes of the tag as keyword arguments. An attribute
whose name is not an identifier of Python, or is a keyword of it, as
``class``, ``for`` or ``data-id``, is passed with ``**``, and an attribute
without a value has the value ``None``. ::

    %= text_field('first_name', **{'class': 'user'}, required=None)

A block of a template, between ``begin`` and ``end``, is the content of the tag
when it is the last positional argument, and the attributes follow it. ::

    %= label_for('first_name', begin
      First name
    %= end, **{'class': 'user'})

This is a core plugin, that means it is always enabled and its code a good
example for learning how to build new plugins, you're welcome to fork it.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Helpers
-------

:mod:`Pyjoyment.Plugin.TagHelpers` implements the following helpers.

asset_tag ::

    %= asset_tag('/app.js')
    %= asset_tag('/app.js', **{'async': 'async'})

Generate ``script``, ``link`` or ``img`` tag for static asset.

button_to ::

    %= button_to('Test', 'some_get_route')
    %= button_to('Test', 'some_get_route', {'id': 23}, **{'class': 'menu'})
    %= button_to('Test', 'http://example.com/test', **{'class': 'menu'})
    %= button_to('Remove', 'some_delete_route')

Generate portable ``form`` tag with ``form_for``, containing a single button. ::

    <form action="/path/to/get/route">
      <input type="submit" value="Test">
    </form>
    <form action="/path/to/get/route/23" class="menu">
      <input type="submit" value="Test">
    </form>
    <form action="http://example.com/test" class="menu">
      <input type="submit" value="Test">
    </form>
    <form action="/path/to/delete/route?_method=DELETE" method="POST">
      <input type="submit" value="Remove">
    </form>

check_box ::

    %= check_box('employed')
    %= check_box('employed', 1)
    %= check_box('employed', 1, checked=None, id='foo')

Generate ``input`` tag of type ``checkbox``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="employed" type="checkbox">
    <input name="employed" type="checkbox" value="1">
    <input checked id="foo" name="employed" type="checkbox" value="1">

color_field ::

    %= color_field('background')
    %= color_field('background', '#ffffff')
    %= color_field('background', '#ffffff', id='foo')

Generate ``input`` tag of type ``color``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="background" type="color">
    <input name="background" type="color" value="#ffffff">
    <input id="foo" name="background" type="color" value="#ffffff">

csrf_button_to ::

    %= csrf_button_to('Remove', 'some_delete_route')

Same as ``button_to``, but also includes a ``csrf_field``. ::

    <form action="/path/to/delete/route?_method=DELETE" method="POST">
      <input name="csrf_token" type="hidden" value="fa6a08...">
      <input type="submit" value="Remove">
    </form>

csrf_field ::

    %= csrf_field()

Generate ``input`` tag of type ``hidden`` with the helper ``csrf_token`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers`. ::

    <input name="csrf_token" type="hidden" value="fa6a08...">

date_field ::

    %= date_field('end')
    %= date_field('end', '2012-12-21')
    %= date_field('end', '2012-12-21', id='foo')

Generate ``input`` tag of type ``date``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="end" type="date">
    <input name="end" type="date" value="2012-12-21">
    <input id="foo" name="end" type="date" value="2012-12-21">

datetime_field ::

    %= datetime_field('end')
    %= datetime_field('end', '2012-12-21T23:59:59')
    %= datetime_field('end', '2012-12-21T23:59:59', id='foo')

Generate ``input`` tag of type ``datetime-local``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="end" type="datetime-local">
    <input name="end" type="datetime-local" value="2012-12-21T23:59:59">
    <input id="foo" name="end" type="datetime-local" value="2012-12-21T23:59:59">

email_field ::

    %= email_field('notify')
    %= email_field('notify', 'nospam@example.com')
    %= email_field('notify', 'nospam@example.com', id='foo')

Generate ``input`` tag of type ``email``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="notify" type="email">
    <input name="notify" type="email" value="nospam@example.com">
    <input id="foo" name="notify" type="email" value="nospam@example.com">

favicon ::

    %= favicon()
    %= favicon('/favicon.ico')

Generate ``link`` tag for favicon, defaulting to the one that comes bundled
with Pyjoyment. ::

    <link href="/favicon.ico" rel="icon">
    <link href="/favicon.ico" rel="icon">

file_field ::

    %= file_field('avatar')
    %= file_field('avatar', id='foo')

Generate ``input`` tag of type ``file``. ::

    <input name="avatar" type="file">
    <input id="foo" name="avatar" type="file">

form_for ::

    %= form_for('login', begin
      %= text_field('first_name')
      %= submit_button()
    %= end)
    %= form_for('login', {'format': 'txt'}, begin
      %= text_field('first_name')
      %= submit_button()
    %= end, method='POST')
    %= form_for('/login', begin
      %= text_field('first_name', disabled='disabled')
      %= submit_button()
    %= end, enctype='multipart/form-data')
    %= form_for('http://example.com/login', begin
      %= text_field('first_name')
      %= submit_button()
    %= end, method='POST')
    %= form_for('some_delete_route', begin
      %= submit_button('Remove')
    %= end)

Generate portable ``form`` tag with
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.url_for`. For routes that do
not allow ``GET``, a ``method`` attribute with the value ``POST`` will be
automatically added. And for methods other than ``GET`` or ``POST``, an
``_method`` query parameter will be added as well. ::

    <form action="/path/to/login">
      <input name="first_name" type="text">
      <input type="submit" value="Ok">
    </form>
    <form action="/path/to/login.txt" method="POST">
      <input name="first_name" type="text">
      <input type="submit" value="Ok">
    </form>
    <form action="/path/to/login" enctype="multipart/form-data">
      <input disabled="disabled" name="first_name" type="text">
      <input type="submit" value="Ok">
    </form>
    <form action="http://example.com/login" method="POST">
      <input name="first_name" type="text">
      <input type="submit" value="Ok">
    </form>
    <form action="/path/to/delete/route?_method=DELETE" method="POST">
      <input type="submit" value="Remove">
    </form>

hidden_field ::

    %= hidden_field('foo', 'bar')
    %= hidden_field('foo', 'bar', id='bar')

Generate ``input`` tag of type ``hidden``. ::

    <input name="foo" type="hidden" value="bar">
    <input id="bar" name="foo" type="hidden" value="bar">

image ::

    %= image('/images/foo.png')
    %= image('/images/foo.png', alt='Foo')

Generate portable ``img`` tag. ::

    <img src="/path/to/images/foo.png">
    <img alt="Foo" src="/path/to/images/foo.png">

input_tag ::

    %= input_tag('first_name')
    %= input_tag('first_name', 'Default')
    %= input_tag('employed', type='checkbox')

Generate ``input`` tag. Previous input values will automatically get picked up
and shown as default. ::

    <input name="first_name">
    <input name="first_name" value="Default">
    <input name="employed" type="checkbox">

javascript ::

    %= javascript('/script.js')
    %= javascript('/script.js', defer=None)
    %= javascript(begin
      const a = 'b';
    %= end)

Generate portable ``script`` tag for JavaScript asset. ::

    <script src="/path/to/script.js"></script>
    <script defer src="/path/to/script.js"></script>
    <script>//<![CDATA[

      const a = 'b';

    //]]></script>

label_for ::

    %= label_for('first_name', 'First name')
    %= label_for('first_name', 'First name', **{'class': 'user'})
    %= label_for('first_name', begin
      First name
    %= end)
    %= label_for('first_name', begin
      First name
    %= end, **{'class': 'user'})

Generate ``label`` tag. ::

    <label for="first_name">First name</label>
    <label class="user" for="first_name">First name</label>
    <label for="first_name">
      First name
    </label>
    <label class="user" for="first_name">
      First name
    </label>

link_to ::

    %= link_to('Home', 'index')
    %= link_to('Home', 'index', {'format': 'txt'}, **{'class': 'menu'})
    %= link_to('index', {'format': 'txt'}, begin
      Home
    %= end, **{'class': 'menu'})
    %= link_to('Contact', 'mailto:sri@example.com')
    <%= link_to('index', begin %>Home<% end) %>
    <%= link_to('/file.txt', begin %>File<% end) %>
    <%= link_to('https://mojolicious.org', begin %>Mojolicious<% end) %>
    <%= link_to(url_for().set(query={'foo': 'bar'}).to_abs(), begin %>Retry<% end) %>

Generate portable ``a`` tag with
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.url_for`, defaults to using
the capitalized link target as content. ::

    <a href="/path/to/index">Home</a>
    <a class="menu" href="/path/to/index.txt">Home</a>
    <a class="menu" href="/path/to/index.txt">
      Home
    </a>
    <a href="mailto:sri@example.com">Contact</a>
    <a href="/path/to/index">Home</a>
    <a href="/path/to/file.txt">File</a>
    <a href="https://mojolicious.org">Mojolicious</a>
    <a href="http://127.0.0.1:3000/current/path?foo=bar">Retry</a>

The first argument to ``link_to`` is the link content, except when the last
positional argument is a callable, such as a template block (created with the
``begin`` and ``end`` keywords); in that case, the link content is omitted at
the start of the argument list, and the block will become the link content.

month_field ::

    %= month_field('vacation')
    %= month_field('vacation', '2012-12')
    %= month_field('vacation', '2012-12', id='foo')

Generate ``input`` tag of type ``month``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="vacation" type="month">
    <input name="vacation" type="month" value="2012-12">
    <input id="foo" name="vacation" type="month" value="2012-12">

number_field ::

    %= number_field('age')
    %= number_field('age', 25)
    %= number_field('age', 25, id='foo', min=0, max=200)

Generate ``input`` tag of type ``number``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="age" type="number">
    <input name="age" type="number" value="25">
    <input id="foo" max="200" min="0" name="age" type="number" value="25">

password_field ::

    %= password_field('pass')
    %= password_field('pass', id='foo')

Generate ``input`` tag of type ``password``. ::

    <input name="pass" type="password">
    <input id="foo" name="pass" type="password">

radio_button ::

    %= radio_button('test')
    %= radio_button('country', 'germany')
    %= radio_button('country', 'germany', checked=None, id='foo')

Generate ``input`` tag of type ``radio``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="test" type="radio">
    <input name="country" type="radio" value="germany">
    <input checked id="foo" name="country" type="radio" value="germany">

range_field ::

    %= range_field('age')
    %= range_field('age', 25)
    %= range_field('age', 25, id='foo', min=0, max=200)

Generate ``input`` tag of type ``range``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="age" type="range">
    <input name="age" type="range" value="25">
    <input id="foo" max="200" min="0" name="age" type="range" value="25">

search_field ::

    %= search_field('q')
    %= search_field('q', 'perl')
    %= search_field('q', 'perl', id='foo')

Generate ``input`` tag of type ``search``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="q" type="search">
    <input name="q" type="search" value="perl">
    <input id="foo" name="q" type="search" value="perl">

select_field ::

    %= select_field('country', ['de', 'en'])
    %= select_field('country', [['Germany', 'de'], 'en'], id='eu')
    %= select_field('country', [['Germany', 'de', {'selected': 'selected'}], 'en'])
    %= select_field('country', [c.c('EU', [['Germany', 'de'], 'en'], {'id': 'eu'})])
    %= select_field('country', [c.c('EU', ['de', 'en']), c.c('Asia', ['cn', 'jp'])])

Generate ``select`` and ``option`` tags from lists and ``optgroup`` tags from
:mod:`Pyjo.Collection` objects. An option is its value or a list of its label,
its value and a dict of its attributes; a group is a collection of its label,
its options and a dict of its attributes. Previous input values will
automatically get picked up and shown as default. ::

    <select name="country">
      <option value="de">de</option>
      <option value="en">en</option>
    </select>
    <select id="eu" name="country">
      <option value="de">Germany</option>
      <option value="en">en</option>
    </select>
    <select name="country">
      <option selected="selected" value="de">Germany</option>
      <option value="en">en</option>
    </select>
    <select name="country">
      <optgroup id="eu" label="EU">
        <option value="de">Germany</option>
        <option value="en">en</option>
      </optgroup>
    </select>
    <select name="country">
      <optgroup label="EU">
        <option value="de">de</option>
        <option value="en">en</option>
      </optgroup>
      <optgroup label="Asia">
        <option value="cn">cn</option>
        <option value="jp">jp</option>
      </optgroup>
    </select>

stylesheet ::

    %= stylesheet('/foo.css')
    %= stylesheet('/foo.css', title='Foo style')
    %= stylesheet(begin
      body {color: #000}
    %= end)

Generate portable ``style`` or ``link`` tag for CSS asset. ::

    <link href="/path/to/foo.css" rel="stylesheet">
    <link href="/path/to/foo.css" rel="stylesheet" title="Foo style">
    <style>/*<![CDATA[*/

      body {color: #000}

    /*]]>*/</style>

submit_button ::

    %= submit_button()
    %= submit_button('Ok!', id='foo')

Generate ``input`` tag of type ``submit``. ::

    <input type="submit" value="Ok">
    <input id="foo" type="submit" value="Ok!">

t ::

    %= t('div', 'test & 123')

Alias for ``tag``. ::

    <div>test &amp; 123</div>

tag ::

    %= tag('br')
    %= tag('div')
    %= tag('div', id='foo', hidden=None)
    %= tag('div', 'test & 123')
    %= tag('div', 'test & 123', id='foo')
    %= tag('div', 'test & 123', data={'my_id': 1, 'Name': 'test'})
    %= tag('div', begin
      test & 123
    %= end)
    <%= tag('div', begin %>test & 123<% end, id='foo') %>

Alias for :meth:`Pyjo.DOM.Pyjo_DOM.new_tag`. ::

    <br>
    <div></div>
    <div hidden id="foo"></div>
    <div>test &amp; 123</div>
    <div id="foo">test &amp; 123</div>
    <div data-my-id="1" data-name="test">test &amp; 123</div>
    <div>
      test & 123
    </div>
    <div id="foo">test & 123</div>

Very useful for reuse in more specific tag helpers. ::

    output = c.tag('meta')
    output = c.tag('meta', charset='UTF-8')
    output = c.tag('div', '<p>This will be escaped</p>')
    output = c.tag('div', lambda: '<p>This will not be escaped</p>')

Results are automatically wrapped in :mod:`Pyjo.String.HTML` objects to
prevent accidental double escaping in ``ep`` templates.

tag_with_error ::

    %= tag_with_error('input', **{'class': 'foo'})

Same as ``tag``, but adds the class ``field-with-error``. ::

    <input class="foo field-with-error">

tel_field ::

    %= tel_field('work')
    %= tel_field('work', '123456789')
    %= tel_field('work', '123456789', id='foo')

Generate ``input`` tag of type ``tel``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="work" type="tel">
    <input name="work" type="tel" value="123456789">
    <input id="foo" name="work" type="tel" value="123456789">

text_area ::

    %= text_area('story')
    %= text_area('story', cols=40)
    %= text_area('story', 'Default', cols=40)
    %= text_area('story', begin
      Default
    %= end, cols=40)

Generate ``textarea`` tag. Previous input values will automatically get picked
up and shown as default. ::

    <textarea name="story"></textarea>
    <textarea cols="40" name="story"></textarea>
    <textarea cols="40" name="story">Default</textarea>
    <textarea cols="40" name="story">
      Default
    </textarea>

text_field ::

    %= text_field('first_name')
    %= text_field('first_name', 'Default')
    %= text_field('first_name', 'Default', **{'class': 'user'})

Generate ``input`` tag of type ``text``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="first_name" type="text">
    <input name="first_name" type="text" value="Default">
    <input class="user" name="first_name" type="text" value="Default">

time_field ::

    %= time_field('start')
    %= time_field('start', '23:59:59')
    %= time_field('start', '23:59:59', id='foo')

Generate ``input`` tag of type ``time``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="start" type="time">
    <input name="start" type="time" value="23:59:59">
    <input id="foo" name="start" type="time" value="23:59:59">

url_field ::

    %= url_field('address')
    %= url_field('address', 'https://mojolicious.org')
    %= url_field('address', 'https://mojolicious.org', id='foo')

Generate ``input`` tag of type ``url``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="address" type="url">
    <input name="address" type="url" value="https://mojolicious.org">
    <input id="foo" name="address" type="url" value="https://mojolicious.org">

week_field ::

    %= week_field('vacation')
    %= week_field('vacation', '2012-W17')
    %= week_field('vacation', '2012-W17', id='foo')

Generate ``input`` tag of type ``week``. Previous input values will
automatically get picked up and shown as default. ::

    <input name="vacation" type="week">
    <input name="vacation" type="week" value="2012-W17">
    <input id="foo" name="vacation" type="week" value="2012-W17">

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Plugin::TagHelpers
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Plugin/TagHelpers.pm>`_ of Mojolicious 9.49.
"""

import Pyjo.Collection
import Pyjo.String.HTML
import Pyjo.URL
import Pyjoyment.Plugin

from Pyjo.DOM.HTML import tag_to_html
from Pyjoyment.Controller import Helper

import functools

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    import Pyjoyment
    import Pyjoyment.Controller

    type Controller = Pyjoyment.Controller.object


class Pyjoyment_Plugin_TagHelpers(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.TagHelpers` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> None:
        """::

            plugin.register(Pyjoyment.new())

        Register helpers in :mod:`Pyjoyment` application.
        """
        # Text field variations
        time = ('date', 'month', 'time', 'week')
        for name in (*time, 'color', 'email', 'number', 'range', 'search', 'tel', 'text', 'url'):
            app.helper(f'{name}_field', functools.partial(_field, name))
        app.helper('datetime_field', functools.partial(_field, 'datetime-local'))

        app.helper('asset_tag', _asset_tag)
        app.helper('csrf_field', _csrf_field)
        app.helper('form_for', _form_for)
        app.helper('hidden_field', _hidden_field)
        app.helper('javascript', _javascript)
        app.helper('label_for', _label_for)
        app.helper('link_to', _link_to)
        app.helper('select_field', _select_field)
        app.helper('stylesheet', _stylesheet)
        app.helper('submit_button', _submit_button)
        app.helper('tag_with_error', _tag_with_error)
        app.helper('text_area', _text_area)

        app.helper('button_to', functools.partial(_button_to, False))
        app.helper('check_box', functools.partial(_field, 'checkbox'))
        app.helper('csrf_button_to', functools.partial(_button_to, True))
        app.helper('favicon', _favicon)
        app.helper('file_field', functools.partial(_empty_field, 'file'))
        app.helper('image', _image)
        app.helper('input_tag', _input)
        app.helper('password_field', functools.partial(_empty_field, 'password'))
        app.helper('radio_button', functools.partial(_field, 'radio'))

        # "t" is just a shortcut for the "tag" helper
        for name in ('t', 'tag'):
            app.helper(name, _tag_helper)


def _asset_tag(c: 'Controller', target: str, /, **attrs: Any) -> Pyjo.String.HTML.object:
    url = c.url_for_asset(target)

    helpers: Any = c.helpers
    if target.endswith('.js'):
        return helpers.javascript(url, **attrs)
    if target.endswith('.css'):
        return helpers.stylesheet(url, **attrs)
    return helpers.image(url, **attrs)


def _button_to(csrf: bool, c: 'Controller', text: Any, /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    prefix = _csrf_field(c) if csrf else ''
    return _form_for(c, *args, lambda: prefix + _submit_button(c, text), **attrs)


def _content(content: Any) -> 'str | Callable[[], str] | None':
    # A number is its string, as Perl stringifies it
    if content is None or isinstance(content, str):
        return content
    if callable(content):
        return cast(Callable[[], str], content)
    return str(content)


def _csrf_field(c: 'Controller', /, **attrs: Any) -> Pyjo.String.HTML.object:
    helpers: Any = c.helpers
    return _hidden_field(c, 'csrf_token', helpers.csrf_token(), **attrs)


def _empty_field(type: str, c: 'Controller', name: str, /, **attrs: Any) -> Pyjo.String.HTML.object:
    return _validation(c, name, 'input', None, **{'name': name, **attrs, 'type': type})


def _favicon(c: 'Controller', file: Any = None, /) -> Pyjo.String.HTML.object:
    return _tag('link', rel='icon', href=_file_url(c, file if file is not None else 'favicon.ico'))


def _field(type: str, c: 'Controller', name: str, /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    return _input(c, name, *args, **{**attrs, 'type': type})


def _file_url(c: 'Controller', url: Any) -> Pyjo.URL.object:
    return url if isinstance(url, Pyjo.URL.object) else c.url_for_file(url)


def _form_for(c: 'Controller', target: Any, /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    url: list[Any] = [target]
    rest = list(args)
    if rest and isinstance(rest[0], dict):
        url.append(rest.pop(0))

    # Method detection
    r = c.app.routes.lookup(url[0]) if isinstance(url[0], str) else None
    method = r.suggested_method if r is not None else 'GET'
    post = {'method': 'POST'} if method != 'GET' else {}

    action = c.url_for(*url)
    if post and method != 'POST':
        action.query = {'_method': method}
    return _tag('form', *rest, **{'action': action, **post, **attrs})


def _hidden_field(c: 'Controller', name: str, value: Any, /, **attrs: Any) -> Pyjo.String.HTML.object:
    return _tag('input', **{'name': name, 'value': value, **attrs, 'type': 'hidden'})


def _image(c: 'Controller', url: Any, /, **attrs: Any) -> Pyjo.String.HTML.object:
    return _tag('img', **{'src': _file_url(c, url), **attrs})


def _input(c: 'Controller', name: str, /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    if args:
        attrs = {'value': args[0], **attrs}

    if values := [str(v) for v in c.every_param(name) if v is not None]:
        # Checkbox or radiobutton
        type = attrs.get('type') or ''
        if type == 'checkbox' or type == 'radio':
            value = attrs.get('value')
            value = 'on' if value is None else str(value)
            attrs.pop('checked', None)
            if value in values:
                attrs['checked'] = None

        # Others
        else:
            attrs['value'] = values[-1]

    return _validation(c, name, 'input', None, **{'name': name, **attrs})


def _javascript(c: 'Controller', /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    rest = list(args)
    content = f'//<![CDATA[\n{rest.pop()()}\n//]]>' if rest and callable(rest[-1]) else ''
    src = {'src': _file_url(c, rest[0])} if rest else {}
    return _tag('script', lambda: content, **{**src, **attrs})


def _label_for(c: 'Controller', name: str, content: Any = None, /, **attrs: Any) -> Pyjo.String.HTML.object:
    return _validation(c, name, 'label', content, **{'for': name, **attrs})


def _link_to(c: 'Controller', content: Any, /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    url: list[Any] = [content]
    rest = list(args)

    # Content
    if rest and callable(rest[-1]):
        content = rest.pop()
    else:
        url = [rest.pop(0)] if rest else [content]

    # Captures
    if rest and isinstance(rest[0], dict):
        url.append(rest.pop(0))

    return _tag('a', content, **{'href': c.url_for(*url), **attrs})


# Unlike Mojolicious: the attributes of an option or a group are a dict after its value, where Mojo takes a flat list of
# names and values, as a list of Python keeps them as one value
def _option(values: set[str], pair: Any) -> Pyjo.String.HTML.object:
    if not isinstance(pair, list | tuple):
        pair = [pair, pair]
    pair = list(cast(list[Any] | tuple[Any, ...], pair))
    attrs: dict[str, Any] = {'value': pair[1], **(pair[2] if len(pair) > 2 else {})}
    if values:
        attrs.pop('selected', None)
    if str(pair[1]) in values:
        attrs['selected'] = None

    return _tag('option', pair[0], **attrs)


def _select_field(c: 'Controller', name: str, options: list[Any], /, **attrs: Any) -> Pyjo.String.HTML.object:
    values = {str(v) for v in c.every_param(name) if v is not None}

    groups = ''
    for group in options:
        # "optgroup" tag
        if isinstance(group, Pyjo.Collection.object):
            items = list(cast(Pyjo.Collection.object[Any], group))
            label, group_values = items[0], items[1]
            group_attrs: dict[str, Any] = items[2] if len(items) > 2 else {}
            content = ''.join(_option(values, value) for value in group_values)
            groups += _tag('optgroup', lambda content=content: content, **{'label': label, **group_attrs})

        # "option" tag
        else:
            groups += _option(values, group)

    return _validation(c, name, 'select', lambda: groups, **{'name': name, **attrs})


def _stylesheet(c: 'Controller', /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    rest = list(args)
    content = f'/*<![CDATA[*/\n{rest.pop()()}\n/*]]>*/' if rest and callable(rest[-1]) else ''
    if not rest:
        return _tag('style', lambda: content, **attrs)
    return _tag('link', **{'rel': 'stylesheet', 'href': _file_url(c, rest[0]), **attrs})


def _submit_button(c: 'Controller', value: Any = None, /, **attrs: Any) -> Pyjo.String.HTML.object:
    return _tag('input', **{'value': value if value is not None else 'Ok', **attrs, 'type': 'submit'})


def _tag(name: str, content: Any = None, /, **attrs: Any) -> Pyjo.String.HTML.object:
    return Pyjo.String.HTML.new(tag_to_html(name, _content(content), **attrs))


def _tag_helper(c: 'Controller', name: str, content: Any = None, /, **attrs: Any) -> Pyjo.String.HTML.object:
    return _tag(name, content, **attrs)


def _tag_with_error(c: 'Controller', tag: str, content: Any = None, /, **attrs: Any) -> Pyjo.String.HTML.object:
    attrs['class'] = f'{attrs["class"]} field-with-error' if attrs.get('class') else 'field-with-error'
    return _tag(tag, content, **attrs)


def _text_area(c: 'Controller', name: str, /, *args: Any, **attrs: Any) -> Pyjo.String.HTML.object:
    rest = list(args)
    cb = rest.pop() if rest and callable(rest[-1]) else None
    content = rest[0] if rest else None
    if (value := c.param(name)) is not None:
        content = value
    elif content is None:
        content = cb if cb is not None else ''

    return _validation(c, name, 'textarea', content, **{'name': name, **attrs})


def _validation(c: 'Controller', name: str, tag: str, content: Any, /, **attrs: Any) -> Pyjo.String.HTML.object:
    if not c.helpers.validation().has_error(name):
        return _tag(tag, content, **attrs)
    return c.helpers.tag_with_error(tag, content, **attrs)


# Not in Mojolicious: the types of the helpers, for type checkers, which Pyjoyment.Controller and Pyjoyment have
class Helpers:
    """
    The types of the helpers of :mod:`Pyjoyment.Plugin.TagHelpers`, for type
    checkers and editors, which :mod:`Pyjoyment.Controller` and
    :mod:`Pyjoyment` have, while the helpers themselves are found in the
    renderer of the application at run time. See
    :class:`Pyjoyment.Controller.Helper`.
    """

    color_field = Helper(functools.partial(_field, 'color'))
    date_field = Helper(functools.partial(_field, 'date'))
    datetime_field = Helper(functools.partial(_field, 'datetime-local'))
    email_field = Helper(functools.partial(_field, 'email'))
    month_field = Helper(functools.partial(_field, 'month'))
    number_field = Helper(functools.partial(_field, 'number'))
    range_field = Helper(functools.partial(_field, 'range'))
    search_field = Helper(functools.partial(_field, 'search'))
    tel_field = Helper(functools.partial(_field, 'tel'))
    text_field = Helper(functools.partial(_field, 'text'))
    time_field = Helper(functools.partial(_field, 'time'))
    url_field = Helper(functools.partial(_field, 'url'))
    week_field = Helper(functools.partial(_field, 'week'))

    asset_tag = Helper(_asset_tag)
    csrf_field = Helper(_csrf_field)
    form_for = Helper(_form_for)
    hidden_field = Helper(_hidden_field)
    javascript = Helper(_javascript)
    label_for = Helper(_label_for)
    link_to = Helper(_link_to)
    select_field = Helper(_select_field)
    stylesheet = Helper(_stylesheet)
    submit_button = Helper(_submit_button)
    tag_with_error = Helper(_tag_with_error)
    text_area = Helper(_text_area)

    button_to = Helper(functools.partial(_button_to, False))
    check_box = Helper(functools.partial(_field, 'checkbox'))
    csrf_button_to = Helper(functools.partial(_button_to, True))
    favicon = Helper(_favicon)
    file_field = Helper(functools.partial(_empty_field, 'file'))
    image = Helper(_image)
    input_tag = Helper(_input)
    password_field = Helper(functools.partial(_empty_field, 'password'))
    radio_button = Helper(functools.partial(_field, 'radio'))

    t = Helper(_tag_helper)
    tag = Helper(_tag_helper)


new = Pyjoyment_Plugin_TagHelpers.new
object = Pyjoyment_Plugin_TagHelpers
TagHelpers = Pyjoyment_Plugin_TagHelpers
