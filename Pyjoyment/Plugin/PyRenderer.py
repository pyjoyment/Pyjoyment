"""
Pyjoyment.Plugin.PyRenderer - Template string renderer plugin
=============================================================
::

    # Pyjoyment
    app.plugin('PyRenderer')

    # A template of a function
    @app.template('index.html')
    def index(c, name):
        return t'<p>Hello {name}!</p>'

    c.render('index', name='Joe')

    # An inline t-string of Python 3.14
    c.render(inline=t'<p>Hello {name}!</p>')

    # The same on any Python
    c.render(inline=t('<p>Hello {name}!</p>', name=name))

:mod:`Pyjoyment.Plugin.PyRenderer` is a renderer for ``py`` templates, which
are template strings, t-strings of
`PEP 750 <https://peps.python.org/pep-0750/>`_ or of
:func:`Pyjo.String.Template.t`, rendered by :mod:`Pyjo.String.Template`, which
escapes the values that they interpolate, unless they are markup, as the
helpers of :mod:`Pyjoyment.Plugin.TagHelpers` return. ::

    from Pyjo.String.Template import t

    # "<p>Hello &lt;script&gt;!</p>"
    name = '<script>'
    c.render(inline=t('<p>Hello {name}!</p>', name=name))

    # "<p><a href="/">Home</a></p>"
    c.render(inline=t('<p>{link}</p>', link=c.link_to('Home', '/')))

A template string is code, which cannot be read from a file of data as a
template of :mod:`Pyjoyment.Plugin.EPRenderer` is, so a template is a function
that returns one, registered with :meth:`Pyjoyment.Pyjoyment_App.template`,
or the function ``template`` of :mod:`Pyjoyment.Lite`, by its name with the
format, as ``index.html``. The function gets the controller and the values
of the stash that it names as its parameters, as the variables of an ``ep``
template, or all of them with ``**``, and it can set the values of the stash
that the renderer reads, as a layout. ::

    # A template with a layout
    @app.template('hello.html')
    def hello(c, name):
        c.layout('default')
        c.title('Hello')
        return t'<p>Hello {name}!</p>'

    # The layout, which gets the content and the title
    @app.template('layouts/default.html')
    def default(c, **stash):
        return t'<title>{c.title()}</title><body>{c.content()}</body>'

A template can also be a file in
:attr:`Pyjoyment.Renderer.Pyjoyment_Renderer.paths` with the extension ``py``,
as ``templates/index.html.py``, a module of Python whose function ``render``
is the function of the template. The file is
compiled once and kept in the cache of the renderer, without the bytecode
that an import writes next to it, and an exception in it shows the lines of
the file. ::

    # templates/hello.html.py
    def render(c, name):
        return t'<p>Hello {name}!</p>'

An inline template that is a template string is rendered by it, unless
another handler is given. Its values are evaluated where it is written, so it
gets the values of the stash as the code around it does, ``c.stash('name')``,
and a layout does not apply to it, as to any inline template.

This is a core plugin, that means it is always enabled and its code a good
example for learning to build new plugins, you're welcome to fork it.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Inspired by `Mojolicious::Plugin::EPLRenderer
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Plugin/EPLRenderer.pm>`_ of Mojolicious 9.49.
"""

import Pyjo.Exception
import Pyjo.File
import Pyjo.String.Template
import Pyjoyment.Plugin

from Pyjo.Util import encode, md5_sum

import inspect
import io
import types

from collections.abc import Callable
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import Pyjoyment
    import Pyjoyment.Controller
    import Pyjoyment.Renderer


class Pyjoyment_Plugin_PyRenderer(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.PyRenderer` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> None:
        """::

            plugin.register(Pyjoyment.new())

        Register renderer in :mod:`Pyjoyment` application.
        """
        app.renderer.add_handler('py', _handler)


def _handler(
    renderer: 'Pyjoyment.Renderer.object',
    c: 'Pyjoyment.Controller.object',
    output: io.StringIO,
    options: dict[str, Any],
) -> None:
    log = c.helpers.log()

    # Inline
    inline = options.get('inline')
    if inline is not None:
        if not Pyjo.String.Template.is_template(inline):
            return
        template = Pyjo.String.Template.t(inline)
        name = md5_sum(encode('UTF-8', '{}'.join(template.strings)))
        log.trace(f'Rendering inline template "{name}"')
        output.write(template.render())
        return

    if (name := renderer.template_name(options)) is None:
        return

    # Function
    if (cb := renderer.templates.get(name.removesuffix('.py'))) is not None:
        log.trace(f'Rendering template "{name}" of a function')

    # File
    elif (path := renderer.template_path(options)) is not None:
        key = md5_sum(encode('UTF-8', f'py:{path}'))
        if (cb := renderer.cache.get(key)) is not None:
            log.trace(f'Rendering cached template "{name}"')
        else:
            log.trace(f'Rendering template "{name}"')
            renderer.cache.set(key, cb := _load(path, key, renderer.encoding))

    # No template
    else:
        log.debug(f'Template "{name}" not found')
        return

    output.write(Pyjo.String.Template.escape(_call(cb, c, c.stash())))


# The function "render" of a file, which is compiled from its source, as importlib would write its bytecode next to it,
# with the path of the file, from which a traceback reads the lines of the template
def _load(path: str, key: str, encoding: str | None) -> Callable[..., Any]:
    file = Pyjo.File.path(path)
    if encoding is None:
        source = file.slurp().decode('latin-1')
    elif (source := file.slurp(encoding)) is None:
        raise Pyjo.Exception.new(f'Template "{path}" has invalid encoding')
    try:
        code = compile(source, path, 'exec', dont_inherit=True)
    except SyntaxError as e:
        raise Pyjo.Exception.new(f'{e.msg} at {path} line {e.lineno}.\n') from None

    module = types.ModuleType(f'{__name__}.{key}')
    module.__file__ = path

    # No spec, as a spec without a loader makes linecache warn, which then reads the lines from the file
    del module.__spec__
    exec(code, module.__dict__)
    if not callable(cb := module.__dict__.get('render')):
        raise Pyjo.Exception.new(f'Template "{path}" has no function "render"')
    return cb


# The controller and the values of the stash that the function names, or all of them for **
def _call(cb: Callable[..., Any], c: 'Pyjoyment.Controller.object', stash: dict[str, Any]) -> Any:
    parameters = list(inspect.signature(cb).parameters.values())
    rest = parameters[1:]
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in rest):
        values = {k: v for k, v in stash.items() if k.isidentifier() and k != parameters[0].name}
    else:
        values = {p.name: stash[p.name] for p in rest if p.name in stash}
    return cb(c, **values)


new = Pyjoyment_Plugin_PyRenderer.new
object = Pyjoyment_Plugin_PyRenderer
PyRenderer = Pyjoyment_Plugin_PyRenderer
