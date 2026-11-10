Rendering
=========

Rendering content.

This document explains content generation with the :mod:`Pyjoyment`
renderer.

Concepts
--------

Essentials every :mod:`Pyjoyment` developer should know.

Renderer
~~~~~~~~

The renderer is a tiny black box turning stash data into actual responses
utilizing multiple template systems and data encoding modules.

.. code-block:: text

    {'text': 'Hello.'}                   -> 200 OK, text/html, 'Hello.'
    {'json': {'x': 3}}                   -> 200 OK, application/json, '{"x":3}'
    {'text': 'Oops.', 'status': '410'}   -> 410 Gone, text/html, 'Oops.'

Templates can be automatically detected if enough information is provided by
the developer or routes. Template names are expected to follow the
``template.format.handler`` scheme, with ``template`` defaulting to
``controller/action`` or the route name, ``format`` defaulting to ``html``
and ``handler`` to ``ep``.

.. code-block:: text

    {'controller': 'users', 'action': 'list'} -> 'users/list.html.ep'
    {'template': 'foo', 'format': 'txt'}      -> 'foo.txt.ep'
    {'template': 'foo', 'handler': 'epl'}     -> 'foo.html.epl'

The ``controller`` value gets converted from ``CamelCase`` to ``snake_case``
using :func:`~Pyjo.Util.decamelize` and ``-`` characters replaced with
``/``.

.. code-block:: text

    {'controller': 'My.Users', 'action': 'add'}  -> 'my/users/add.html.ep'
    {'controller': 'my-users', 'action': 'show'} -> 'my/users/show.html.ep'

All templates should be in the ``templates`` directories of the application,
which can be customized with
:attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.paths`, or one of the
``__DATA__`` sections from
:attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.classes`.

.. literalinclude:: rendering/clock.py
    :language: python
    :caption: clock.py

The renderer can be easily extended to support additional template systems
with plugins, but more about that later.

Embedded Python
~~~~~~~~~~~~~~~

:mod:`Pyjoyment` includes a minimalistic but very powerful template system
out of the box called Embedded Python or ``ep`` for short. It is based on
:mod:`Pyjo.Template` and allows the embedding of Python code right into
actual content using a small set of special tags and line start characters.

.. code-block:: text

    <% Python code %>
    <%= Python expression, replaced with XML escaped result %>
    <%== Python expression, replaced with result %>
    <%# Comment, useful for debugging %>
    <%% Replaced with "<%", useful for generating templates %>
    % Python code line, treated as "<% line =%>" (explained later)
    %= Python expression line, treated as "<%= line %>"
    %== Python expression line, treated as "<%== line %>"
    %# Comment line, useful for debugging
    %% Replaced with "%", useful for generating templates

Tags and lines work pretty much the same, but depending on context one will
usually look a bit better. A line that ends with ``:`` opens a block, which
``end`` closes, as the indentation of a template does not matter.

.. code-block:: text

    <% i = 10 %>
    <ul>
      <% for j in range(1, i + 1): %>
        <li>
          <%= j %>
        </li>
      <% end %>
    </ul>

.. code-block:: text

    % i = 10
    <ul>
      % for j in range(1, i + 1):
        <li>
          %= j
        </li>
      % end
    </ul>

Aside from differences in whitespace handling, both examples generate
similar Python code, a naive translation could look like this.

.. code-block:: python

    output = ''
    i = 10
    output += '<ul>'
    for j in range(1, i + 1):
        output += '<li>'
        output += xml_escape(str(j))
        output += '</li>'
    output += '</ul>'
    return output

An additional equal sign can be used to disable escaping of the characters
``<``, ``>``, ``&``, ``'`` and ``"`` in results from Python expressions,
which is the default to prevent XSS attacks against your application.

.. code-block:: text

    <%= 'I ♥ Pyjoyment!' %>
    <%== '<p>I ♥ Pyjoyment!</p>' %>

Only markup, an object with the method ``__html__``, as
:mod:`Pyjo.String.HTML`, is excluded from automatic escaping.

.. code-block:: text

    % from Pyjo.String.HTML import html
    <%= html('<p>I ♥ Pyjoyment!</p>') %>

Whitespace characters around tags can be trimmed by adding an additional
equal sign to the end of a tag.

.. code-block:: text

    <% for i in range(1, 4): %>
      <%= 'Trim all whitespace characters around this expression' =%>
    <% end %>

Newline characters can be escaped with a backslash.

.. code-block:: text

    This is <%= 1 + 1 %> a\
    single line

And a backslash in front of a newline character can be escaped with another
backslash.

.. code-block:: text

    This will <%= 1 + 1 %> result\\
    in multiple\\
    lines

A newline character gets appended automatically to every template, unless the
last character is a backslash. And empty lines at the end of a template are
ignored.

.. code-block:: text

    There is <%= 1 + 1 %> no newline at the end here\

At the beginning of the template, stash values that are valid names of
Python get automatically initialized as normal variables, and the controller
object as both ``self`` and ``c``.

.. code-block:: python

    c.stash(name='tester')

.. code-block:: text

    Hello <%= name %> from <%= c.tx.remote_address %>.

A prefix like ``myapp.*`` is commonly used for stash values that you don't
want to expose in templates.

.. code-block:: python

    c.stash({'myapp.name': 'tester'})

There are also many helper functions available, but more about that later.

.. code-block:: text

    <%= dumper({'foo': 'bar'}) %>

Basics
------

Most commonly used features every :mod:`Pyjoyment` developer should know
about.

Automatic rendering
~~~~~~~~~~~~~~~~~~~

The renderer can be manually started by calling the method
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render`, but that's
usually not necessary, because it will get automatically called if nothing
has been rendered after the router finished its work. This also means you can
have routes pointing only to templates without actual actions.

.. code-block:: python

    c.render()

There is one big difference though, by calling it manually you can make sure
that templates use the current controller object, and not the default
controller specified with the attribute
:attr:`~Pyjoyment.Pyjoyment_App.controller_class`.

.. code-block:: python

    c.render_later()

You can also disable automatic rendering with the method
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render_later`, which can
be very useful to delay rendering when a non-blocking operation has to be
performed first.

Rendering templates
~~~~~~~~~~~~~~~~~~~

The renderer will always try to detect the right template, but you can also
use the ``template`` stash value to render a specific one. Everything before
the last slash will be interpreted as the subdirectory path in which to find
the template.

.. code-block:: python

    # foo/bar/baz.*.*
    c.render(template='foo/bar/baz')

Choosing a specific ``format`` and ``handler`` is just as easy.

.. code-block:: python

    # foo/bar/baz.txt.epl
    c.render(template='foo/bar/baz', format='txt', handler='epl')

Because rendering a specific template is the most common task it also has a
shortcut.

.. code-block:: python

    c.render('foo/bar/baz')

If you're not sure in advance if a template actually exists, you can also use
the method :meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render_maybe`
to try multiple alternatives.

.. code-block:: python

    c.render_maybe('localized/baz') or c.render('foo/bar/baz')

Rendering to strings
~~~~~~~~~~~~~~~~~~~~

Sometimes you might want to use the rendered result directly instead of
generating a response, for example, to send emails, this can be done with
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render_to_string`.

.. code-block:: python

    html = c.render_to_string('mail')

No encoding will be performed, making it easy to reuse the result in other
templates or to generate binary data.

.. code-block:: python

    pdf = c.render_to_string('invoice', format='pdf')
    c.render(data=pdf, format='pdf')

All arguments passed will get localized automatically and are only available
during this render operation.

Template variants
~~~~~~~~~~~~~~~~~

To make your application look great on many different devices you can also
use the ``variant`` stash value to choose between different variants of your
templates.

.. code-block:: python

    # foo/bar/baz.html+phone.ep
    # foo/bar/baz.html.ep
    c.render('foo/bar/baz', variant='phone')

This can be done very liberally since it only applies when a template with
the correct name actually exists and falls back to the generic one otherwise.

Rendering inline templates
~~~~~~~~~~~~~~~~~~~~~~~~~~

Some renderers such as ``ep`` allow templates to be passed ``inline``.

.. code-block:: python

    c.render(inline='The result is <%= 1 + 1 %>.')

Since auto-detection depends on a path you might have to supply a
``handler`` too.

.. code-block:: python

    c.render(inline="<%= args[0].param('foo') %>", handler='epl')

Rendering text
~~~~~~~~~~~~~~

Characters can be rendered to bytes with the ``text`` stash value, the given
content will be automatically encoded with
:attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.encoding`.

.. code-block:: python

    c.render(text='I ♥ Pyjoyment!')

Rendering data
~~~~~~~~~~~~~~

Bytes can be rendered with the ``data`` stash value, no encoding will be
performed.

.. code-block:: python

    c.render(data=data)

Rendering JSON
~~~~~~~~~~~~~~

The ``json`` stash value allows you to pass Python data structures to the
renderer which get directly encoded to JSON with :mod:`Pyjo.JSON`.

.. code-block:: python

    c.render(json={'foo': [1, 'test', 3]})

Status code
~~~~~~~~~~~

Response status codes can be changed with the ``status`` stash value.

.. code-block:: python

    c.render(text='Oops.', status=500)

Content type
~~~~~~~~~~~~

The ``Content-Type`` header of the response is actually based on the MIME
type mapping of the ``format`` stash value.

.. code-block:: python

    # Content-Type: text/plain
    c.render(text='Hello.', format='txt')

    # Content-Type: image/png
    c.render(data=data, format='png')

These mappings can be easily extended or changed with
:attr:`~Pyjoyment.Pyjoyment_App.types`.

.. code-block:: python

    # Add new MIME type
    app.types.type('md', 'text/markdown')

Stash data
~~~~~~~~~~

Any of the native Python data types can be passed to templates through the
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.stash`.

.. code-block:: python

    c.stash(description='web framework')
    c.stash(frameworks=['Catalyst', 'Mojolicious', 'Pyjoyment'])
    c.stash(spinoffs={'minion': 'job queue'})

.. code-block:: text

    %= description
    %= frameworks[1]
    %= spinoffs['minion']

Since everything is just Python normal control structures just work.

.. code-block:: text

    % for framework in frameworks:
      <%= framework %> is a <%= description %>.
    % end

    % if (description := spinoffs.get('minion')):
      Minion is a <%= description %>.
    % end

For templates that might get rendered in different ways and where you're not
sure if a stash value will actually be set, you can just use the helper
``stash`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`.

.. code-block:: text

    % if (spinoffs := stash('spinoffs')):
      Minion is a <%= spinoffs['minion'] %>.
    % end

Helpers
~~~~~~~

Helpers are little functions you can use in templates as well as application
and controller code.

.. code-block:: text

    # Template
    %= dumper([1, 2, 3])

.. code-block:: python

    # Application
    serialized = app.dumper([1, 2, 3])

    # Controller
    serialized = c.dumper([1, 2, 3])

We differentiate between default helpers, which are more general purpose like
``dumper`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`, and tag helpers like
``link_to`` of :mod:`Pyjoyment.Plugin.TagHelpers`, which are template
specific and mostly used to generate HTML tags.

.. code-block:: text

    %= link_to('Pyjoyment', 'https://pyjoyment.readthedocs.io')

In controllers you can also use the attribute
:attr:`~Pyjoyment.Controller.Pyjoyment_Controller.helpers` to fully qualify
helper calls and ensure that they don't conflict with existing methods you
may already have.

.. code-block:: python

    serialized = c.helpers.dumper([1, 2, 3])

A list of all built-in helpers can be found in
:mod:`Pyjoyment.Plugin.DefaultHelpers` and
:mod:`Pyjoyment.Plugin.TagHelpers`.

Static files
~~~~~~~~~~~~

Static files are automatically served from the ``public`` directories of the
application, which can be customized with
:attr:`~Pyjoyment.Static.Pyjoyment_Static.paths`, or one of the ``__DATA__``
sections from :attr:`~Pyjoyment.Static.Pyjoyment_Static.classes`. And if
that's not enough you can also serve them manually with the helpers
``reply.static`` and ``reply.file`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers`.

.. literalinclude:: rendering/static_files.py
    :language: python
    :caption: static_files.py

By default static files do not use a prefix and are simply served with a
higher precedence than routes. This can be changed with
:attr:`~Pyjoyment.Static.Pyjoyment_Static.prefix`.

.. code-block:: python

    # Serve static files only with a "/static" prefix
    app.static.prefix = '/static'

To allow for the prefix to be configured dynamically, you can use
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.url_for_file` to generate
URLs with it. Many tag helpers will also use the prefix automatically when it
makes sense.

Static assets
~~~~~~~~~~~~~

While Pyjoyment does not have any special support for frontend frameworks
like `Vue.js <https://vuejs.org>`_ and `React <https://reactjs.org>`_, the
``public/assets`` directory is reserved for static assets created by
bundlers like `Webpack <https://webpack.js.org>`_ and `Rollup.js
<https://rollupjs.org>`_ ahead of time. Asset files can be of any type, they
just have to follow the ``[name].[checksum].[extensions]`` naming scheme,
like ``myapp.ab1234cd5678ef.js``. You can then use
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.url_for_asset` or the
helper ``asset_tag`` of :mod:`Pyjoyment.Plugin.TagHelpers` to generate URLs
without having to know the checksum.

.. code-block:: python

    # "/assets/myapp.ab1234cd5678ef.js"
    c.url_for_asset('/myapp.js')

    # "<script src="/assets/myapp.ab1234cd5678ef.js"></script>"
    c.asset_tag('/myapp.js')

If your application runs in ``development`` mode, all assets will be served
with a ``Cache-Control: no-cache`` header, to speed up development by
preventing browser caching. Additionally all assets following the
``[name].development.[extensions]`` naming scheme, like
``myapp.development.js``, have a higher precedence than assets with
checksums. That way you can just overwrite your assets during development,
instead of having to manually delete them each time they are rebuilt with a
different checksum.

.. code-block:: python

    # "/assets/foo/bar.development.js"
    c.url_for_asset('/foo/bar.js')

Webpack `configuration <https://webpack.js.org/configuration/>`_ example
(``webpack.config.js``):

.. code-block:: javascript

    import Path from '@mojojs/path';

    const isDev = process.env.PYJO_MODE === 'development';

    export default {
      output: {
        filename: isDev ? '[name].development.js' : '[name].[chunkhash].js',
        path: Path.currentFile().sibling('public', 'assets').toString(),
        publicPath: ''
      },

      // Add your own rules and entry point here
    };

Rollup `configuration <https://rollupjs.org/guide/en/#configuration-files>`_
example (``rollup.config.js``):

.. code-block:: javascript

    import Path from '@mojojs/path';

    const isDev = process.env.PYJO_MODE === 'development';

    export default {
      output: {
        entryFileNames: isDev ? '[name].development.[ext]' : '[name].[hash].[ext]',
        dir: Path.currentFile().sibling('public', 'assets').toString(),
        format: 'iife'
      },

      // Add your own rules and entry point here
    };

Vite `configuration <https://vite.dev/config/>`_ example
(``vite.config.js``):

.. code-block:: javascript

    import Path from '@mojojs/path';

    const isDev = process.env.PYJO_MODE === 'development';

    export default {
      // Pyjoyment already serves the "public" directory
      publicDir: false,
      build: {
        outDir: Path.currentFile().sibling('public', 'assets').toString(),
        rollupOptions: {
          output: {
            entryFileNames: isDev ? '[name].development.js' : '[name].[hash].js',
            assetFileNames: isDev ? '[name].development.[ext]' : '[name].[hash].[ext]'
          }
        }
      },

      // Add your own plugins and entry point here
    };

During development you can let :mod:`Pyjo.Server.Reload` start your bundler
in watch mode, so it rebuilds assets whenever their sources change. The
``PYJO_MODE`` environment variable will be set for it too, and because assets
are found again for every request in ``development`` mode and not cached by
browsers, there is no need to restart your application.

.. code-block:: console

    $ pyjo-reload -x 'npx webpack --watch' ./myapp.py
    $ pyjo-reload -x 'npx rollup -c -w' ./myapp.py
    $ pyjo-reload -x 'npx vite build --watch' ./myapp.py

Precompressed static files
~~~~~~~~~~~~~~~~~~~~~~~~~~

Static files are served as they are, the
:attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.compress` of the renderer only
compresses content that is generated dynamically. Files that are built ahead
of time, like the assets of a bundler, can be compressed ahead of time too,
with the highest levels of compression, which would be too slow for every
request. A variant next to the file, with the extension of its encoding in
:attr:`~Pyjoyment.Static.Pyjoyment_Static.encodings`, like ``app.css.br``,
``app.css.zst`` and ``app.css.gz``, is served to the clients that accept its
encoding, with a ``Content-Encoding`` header and the ``Content-Type`` of the
original file.

.. code-block:: console

    $ find public -type f -size +1k \( -name '*.css' -o -name '*.js' -o -name '*.svg' \) \
        -exec gzip -k -f -9 -n {} + -exec brotli -k -f -q 11 {} + -exec zstd -q -k -f -19 {} +

Compress the formats of text, which shrink a lot: CSS, JavaScript, JSON,
source maps, SVG, HTML, plain text, XML, WebAssembly, and fonts in TrueType
and OpenType. Leave out the formats that are compressed already, as the PNG,
JPEG, GIF, WebP and AVIF images, video, audio, the WOFF and WOFF2 fonts, PDF
documents and archives, whose variants would only be larger, and files of
less than about a kilobyte, which gain nothing. A variant that is not smaller
than its file is better removed.

Variants are preferred in the order of
:attr:`~Pyjoyment.Static.Pyjoyment_Static.encodings` and checked for every
request, so there is nothing to restart when they change. A variant older
than its file is ignored, so that a build that changes a file without
compressing it again does not serve the old content, and a ``Range`` request
always gets a part of the original file. Every response of a file with
variants has a ``Vary: Accept-Encoding`` header, so that caches keep them
apart, and each variant has an ``ETag`` of its own.

.. code-block:: python

    # Look for gzip variants only
    app.static.encodings = {'gzip': '.gz'}

    # Serve static files only as they are
    app.static.encodings = {}

The ``Dockerfile`` of
:mod:`Pyjoyment.Command.Author.generate.dockerfile` writes the ``gzip``
variants in the image with ``--compress``, for the formats of text or the
patterns of ``--compress-pattern``.

.. code-block:: console

    $ ./myapp.py generate dockerfile --compress public

For production you just run the bundler once before deploying your
application, with ``PYJO_MODE`` set accordingly.

.. code-block:: console

    $ PYJO_MODE=production npx webpack

Everything else is up to your bundler of choice, so you need to consult its
documentation for further information. And where you keep your asset
sources, such as ``.vue`` and ``.jsx`` files, is not important, as long as
your bundler can find them. Using a directory named ``assets`` or
``frontend`` in your application root directory is a good best practice
though.

Content negotiation
~~~~~~~~~~~~~~~~~~~

For resources with different representations and that require truly RESTful
content negotiation you can also use the helper ``respond_to`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers` instead of
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render`.

.. code-block:: python

    # /hello (Accept: application/json) -> "json"
    # /hello (Accept: application/xml)  -> "xml"
    # /hello.json                       -> "json"
    # /hello.xml                        -> "xml"
    # /hello?_format=json               -> "json"
    # /hello?_format=xml                -> "xml"
    c.respond_to(json={'json': {'hello': 'world'}}, xml={'text': '<hello>world</hello>'})

The best possible representation will be automatically selected from the
``_format`` ``GET``/``POST`` parameter, ``format`` stash value or ``Accept``
request header and stored in the ``format`` stash value. To change MIME type
mappings for the ``Accept`` request header or the ``Content-Type`` response
header you can use :attr:`~Pyjoyment.Pyjoyment_App.types`.

.. code-block:: python

    def html(c):
        c.content_for('head', '<meta name="author" content="sri">')
        c.render(template='hello', message='world')

    c.respond_to(json={'json': {'hello': 'world'}}, html=html)

Callbacks can be used for representations that are too complex to fit into a
single render call.

.. code-block:: python

    # /hello (Accept: application/json) -> "json"
    # /hello (Accept: text/html)        -> "html"
    # /hello (Accept: image/png)        -> "any"
    # /hello.json                       -> "json"
    # /hello.html                       -> "html"
    # /hello.png                        -> "any"
    # /hello?_format=json               -> "json"
    # /hello?_format=html               -> "html"
    # /hello?_format=png                -> "any"
    c.respond_to(
        json={'json': {'hello': 'world'}},
        html={'template': 'hello', 'message': 'world'},
        any={'text': '', 'status': 204},
    )

And if no viable representation could be found, the ``any`` fallback will be
used or an empty ``204`` response rendered automatically.

.. code-block:: python

    # /hello                      -> "html"
    # /hello (Accept: text/html)  -> "html"
    # /hello (Accept: text/xml)   -> "xml"
    # /hello (Accept: text/plain) -> None
    # /hello.html                 -> "html"
    # /hello.xml                  -> "xml"
    # /hello.txt                  -> None
    # /hello?_format=html         -> "html"
    # /hello?_format=xml          -> "xml"
    # /hello?_format=txt          -> None
    if format := c.accepts('html', 'xml'):
        ...

For even more advanced negotiation logic you can also use the helper
``accepts`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`.

Rendering ``exception`` and ``not_found`` pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By now you've probably already encountered the built-in ``404`` (Not Found)
and ``500`` (Server Error) pages, that get rendered automatically when you
make a mistake. Those are fallbacks for when your own exception handling
fails, which can be especially helpful during development. You can also
render them manually with the helpers ``reply.exception`` and
``reply.not_found`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`.

.. literalinclude:: rendering/divide.py
    :language: python
    :caption: divide.py

You can change the templates of those pages, since you most likely want to
show your users something more closely related to your application in
production. The renderer will always try to find
``exception.$mode.$format.*`` or ``not_found.$mode.$format.*`` before
falling back to the built-in default templates.

.. literalinclude:: rendering/exception_template.py
    :language: python
    :caption: exception_template.py

The default exception format is ``html``, but that can be changed at
application and controller level. By default there are handlers for
``html``, ``txt`` and ``json`` available. There are also various exception
helpers in :mod:`Pyjoyment.Plugin.DefaultHelpers` for you to overload to
change the default behavior.

.. literalinclude:: rendering/exception_format.py
    :language: python
    :caption: exception_format.py

The hook ``before_render`` of :meth:`~Pyjoyment.Pyjoyment_App.hook` makes
even more advanced customizations possible by allowing you to intercept and
modify the arguments passed to the renderer.

.. literalinclude:: rendering/before_render.py
    :language: python
    :caption: before_render.py

Layouts
~~~~~~~

Most of the time when using ``ep`` templates you will want to wrap your
generated content in an HTML skeleton, thanks to layouts that's absolutely
trivial.

.. literalinclude:: rendering/layout.py
    :language: python
    :caption: layout.py

You just select the right layout template with the helper ``layout`` and
place the result of the current template with the helper ``content`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers`. You can also pass along normal stash
values to the ``layout`` helper.

.. literalinclude:: rendering/layout_title.py
    :language: python
    :caption: layout_title.py

Instead of the ``layout`` helper you could also just use the ``layout`` stash
value, or call :meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render`
with the ``layout`` argument.

.. code-block:: python

    c.render(template='mytemplate', layout='mylayout')

To set a ``layout`` stash value application-wide you can use
:meth:`~Pyjoyment.Pyjoyment_App.defaults`.

.. code-block:: python

    app.defaults(layout='mylayout')

Layouts can also be used with
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render_to_string`, but the
``layout`` value needs to be passed as a render argument (not a stash value).

.. code-block:: python

    html = c.render_to_string('reminder', layout='mail')

Partial templates
~~~~~~~~~~~~~~~~~

You can break up bigger templates into smaller, more manageable chunks. These
partial templates can also be shared with other templates. Just use the
helper ``include`` of :mod:`Pyjoyment.Plugin.DefaultHelpers` to include one
template into another.

.. literalinclude:: rendering/partial.py
    :language: python
    :caption: partial.py

You can name partial templates however you like, but a leading underscore is
a commonly used naming convention.

Reusable template blocks
~~~~~~~~~~~~~~~~~~~~~~~~

It's never fun to repeat yourself, that's why you can build reusable template
blocks in ``ep`` that work very similar to normal Python functions, with the
``begin`` and ``end`` keywords. Just be aware that both keywords are part of
the surrounding tag and not actual Python code, so there can only be
whitespace after ``begin`` and before ``end``.

.. literalinclude:: rendering/blocks.py
    :language: python
    :caption: blocks.py

A naive translation of the template to Python code could look like this.

.. code-block:: python

    output = ''

    def block(*args):
        name = args[0]
        output = ''
        output += 'Hello '
        output += xml_escape(str(name))
        output += '.'
        return Pyjo.String.HTML.new(output)

    output += xml_escape(block('Wolfgang'))
    output += xml_escape(block('Baerbel'))
    return output

While template blocks cannot be shared between templates, they are most
commonly used to pass parts of a template to helpers.

Adding helpers
~~~~~~~~~~~~~~

You should always try to keep your actions small and reuse as much code as
possible. Helpers make this very easy, they get passed the current controller
object as first argument, and you can use them to do pretty much anything an
action could do.

.. literalinclude:: rendering/debug_helper.py
    :language: python
    :caption: debug_helper.py

Helpers can also accept template blocks as last argument, this for example,
allows very pleasant to use tag helpers and filters. Wrapping the helper
result into a :mod:`Pyjo.String.HTML` object can prevent accidental double
escaping.

.. literalinclude:: rendering/trim_newline.py
    :language: python
    :caption: trim_newline.py

Similar to stash values, you can use a prefix like ``myapp.*`` to keep
helpers from getting exposed in templates as functions, and to organize them
into namespaces as your application grows. Every prefix automatically
becomes a helper that returns a proxy object containing the current
controller object and on which you can call the nested helpers.

.. literalinclude:: rendering/cache_control.py
    :language: python
    :caption: cache_control.py

While helpers can also be redefined, this should only be done very carefully
to avoid conflicts.

Content blocks
~~~~~~~~~~~~~~

The helper ``content_for`` of :mod:`Pyjoyment.Plugin.DefaultHelpers` allows
you to pass whole blocks of content from one template to another. This can
be very useful when your layout has distinct sections, such as sidebars,
where content should be inserted by the template.

.. literalinclude:: rendering/content_for.py
    :language: python
    :caption: content_for.py

Forms
~~~~~

To build HTML forms more efficiently you can use tag helpers like
``form_for`` of :mod:`Pyjoyment.Plugin.TagHelpers`, which can automatically
select a request method for you if a route name is provided. And since most
browsers only allow forms to be submitted with ``GET`` and ``POST``, but not
request methods like ``PUT`` or ``DELETE``, they are spoofed with an
``_method`` query parameter.

.. literalinclude:: rendering/form.py
    :language: python
    :caption: form.py

The helpers ``flash`` and ``redirect_to`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers` are often used together to prevent
double form submission, allowing users to receive a confirmation message that
will vanish if they decide to reload the page they've been redirected to.

Form validation
~~~~~~~~~~~~~~~

You can use the helper ``validation`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers` to validate ``GET`` and ``POST``
parameters submitted to your application. All unknown fields will be ignored
by default, so you have to decide which should be
:meth:`~Pyjoyment.Validator.Validation.Pyjoyment_Validator_Validation.required`
or
:meth:`~Pyjoyment.Validator.Validation.Pyjoyment_Validator_Validation.optional`
before you can perform checks on their values. Every check is performed right
away, so you can use the results immediately to build more advanced
validation logic with methods like
:meth:`~Pyjoyment.Validator.Validation.Pyjoyment_Validator_Validation.is_valid`.

.. literalinclude:: rendering/validation.py
    :language: python
    :caption: validation.py

Form elements generated with tag helpers from
:mod:`Pyjoyment.Plugin.TagHelpers` will automatically remember their previous
values and add the class ``field-with-error`` for fields that failed
validation to make styling with CSS easier.

.. code-block:: html

    <label class="field-with-error" for="user">
      Username (required, 1-20 characters, a-z/0-9)
    </label>
    <input class="field-with-error" type="text" name="user" value="SRI">

For a full list of available checks see also the checks of
:mod:`Pyjoyment.Validator`.

Adding form validation checks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Validation checks can be registered with
:meth:`~Pyjoyment.Validator.Pyjoyment_Validator.add_check` and return a
false value if they were successful. A true value may be used to pass along
additional information which can then be retrieved with
:meth:`~Pyjoyment.Validator.Validation.Pyjoyment_Validator_Validation.error`.

.. literalinclude:: rendering/range_check.py
    :language: python
    :caption: range_check.py

Cross-site request forgery
~~~~~~~~~~~~~~~~~~~~~~~~~~

CSRF is a very common attack on web applications that trick your logged in
users to submit forms they did not intend to send, with something as mundane
as a link. All you have to do, to protect your users from this, is to add an
additional hidden field to your forms with the helper ``csrf_field`` of
:mod:`Pyjoyment.Plugin.TagHelpers`, and validate it with
:meth:`~Pyjoyment.Validator.Validation.Pyjoyment_Validator_Validation.csrf_protect`.

.. literalinclude:: rendering/csrf.py
    :language: python
    :caption: csrf.py

For Ajax requests and the like, you can also generate a token directly with
the helper ``csrf_token`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`, and then
pass it along with the ``X-CSRF-Token`` request header.

The token is masked with a fresh random value on every request, so its value
changes each time even though it stays bound to the same session. This
protects against BREACH attacks, which could otherwise recover a static token
from compressed responses.

Advanced
--------

Less commonly used and more powerful features.

Template inheritance
~~~~~~~~~~~~~~~~~~~~

Inheritance takes the layout concept above one step further, the helpers
``content`` and ``extends`` of :mod:`Pyjoyment.Plugin.DefaultHelpers` allow
you to build skeleton templates with named blocks that child templates can
override.

.. literalinclude:: rendering/inheritance.py
    :language: python
    :caption: inheritance.py

This chain could go on and on to allow a very high level of template reuse.

Custom responses
~~~~~~~~~~~~~~~~

Most response content, static as well as dynamic, gets served through
:mod:`Pyjo.Asset.File` and :mod:`Pyjo.Asset.Memory` objects. For somewhat
static content, like cached JSON data or temporary files, you can create your
own and use the helper ``reply.asset`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers` to serve them while allowing content
negotiation to be performed with ``Range``, ``If-Modified-Since`` and
``If-None-Match`` headers.

.. literalinclude:: rendering/leak_asset.py
    :language: python
    :caption: leak_asset.py

For even more control you can also just skip the helper and use
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.rendered` to tell the
renderer when you're done generating a response.

.. literalinclude:: rendering/leak_rendered.py
    :language: python
    :caption: leak_rendered.py

Helper plugins
~~~~~~~~~~~~~~

Some helpers might be useful enough for you to share them between multiple
applications, plugins make that very simple.

.. literalinclude:: rendering/debug_helper_plugin/Pyjoyment/Plugin/DebugHelper.py
    :language: python
    :caption: Pyjoyment/Plugin/DebugHelper.py

The ``register`` method will be called when you load the plugin. And to add
your helper to the application, you can use
:meth:`~Pyjoyment.Pyjoyment_App.helper`.

.. literalinclude:: rendering/debug_plugin.py
    :language: python
    :caption: debug_plugin.py

A skeleton for a full distribution of a plugin can be automatically
generated.

.. code-block:: console

    $ pyjo generate plugin DebugHelper

And if you have a `PyPI <https://pypi.org>`_ account, you are only a few
commands away from releasing it to PyPI.

.. code-block:: console

    $ cd Pyjoyment-Plugin-DebugHelper
    $ uv run python -m Pyjo.Prove -l -r t
    $ uv build
    $ uv publish

Bundling assets with plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Assets such as templates and static files can be easily bundled with your
plugins, even if you plan to release them to PyPI.

.. code-block:: console

    $ pyjo generate plugin AlertAssets
    $ mkdir Pyjoyment-Plugin-AlertAssets/Pyjoyment/Plugin/AlertAssets
    $ cd Pyjoyment-Plugin-AlertAssets/Pyjoyment/Plugin/AlertAssets
    $ mkdir public
    $ echo 'alert("Hello World!");' > public/alertassets.js
    $ mkdir templates
    $ echo '%= javascript("/alertassets.js")' > templates/alertassets.html.ep

Just give them reasonably unique names, ideally based on the name of your
plugin, and append their respective directories to the list of search paths
when ``register`` is called.

.. literalinclude:: rendering/alert_assets/Pyjoyment/Plugin/AlertAssets.py
    :language: python
    :caption: Pyjoyment/Plugin/AlertAssets.py

The wheel of the distribution has only the module of the plugin, so the
directory goes to ``only-include`` in ``pyproject.toml`` too.

.. code-block:: toml

    [tool.hatch.build.targets.wheel]
    only-include = ["Pyjoyment/Plugin/AlertAssets.py", "Pyjoyment/Plugin/AlertAssets"]

Both will work just like normal ``templates`` and ``public`` directories once
you've installed and loaded the plugin, with slightly lower precedence.

.. literalinclude:: rendering/alert_me.py
    :language: python
    :caption: alert_me.py

And it works just the same for assets bundled in the ``__DATA__`` section of
your plugin.

.. literalinclude:: rendering/alert_assets_data/Pyjoyment/Plugin/AlertAssets.py
    :language: python
    :caption: Pyjoyment/Plugin/AlertAssets.py

Post-processing dynamic content
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While post-processing tasks are generally very easy with the hook
``after_dispatch`` of :meth:`~Pyjoyment.Pyjoyment_App.hook`, for content
generated by the renderer it is a lot more efficient to use the hook
``after_render``, which gets the content as a file object of bytes.

.. literalinclude:: rendering/compressed.py
    :language: python
    :caption: compressed.py

If you want to compress all dynamically generated content you can also
activate :attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.compress`.

Streaming
~~~~~~~~~

You don't have to render all content at once, the method
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.write` can also be used to
stream a series of smaller chunks of bytes.

.. literalinclude:: rendering/streaming.py
    :language: python
    :caption: streaming.py

The drain callback will be executed whenever the entire previous chunk of
data has actually been written.

.. code-block:: text

    HTTP/1.1 200 OK
    Date: Sat, 13 Sep 2014 16:48:29 GMT
    Content-Length: 12
    Server: Pyjoyment (Python)

    Hello World!

Instead of providing a ``Content-Length`` header you can also call
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.finish` and close the
connection manually once you are done.

.. literalinclude:: rendering/streaming_finish.py
    :language: python
    :caption: streaming_finish.py

While this is rather inefficient, as it prevents keep-alive, it is sometimes
necessary for EventSource and similar applications.

.. code-block:: text

    HTTP/1.1 200 OK
    Date: Sat, 13 Sep 2014 16:48:29 GMT
    Connection: close
    Server: Pyjoyment (Python)

    Hello World!

Chunked transfer encoding
~~~~~~~~~~~~~~~~~~~~~~~~~

For very dynamic content you might not know the response content length in
advance, that's where the chunked transfer encoding and
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.write_chunk` come in
handy. A common use would be to send the ``head`` section of an HTML document
to the browser in advance and speed up preloading of referenced images and
stylesheets.

.. literalinclude:: rendering/chunked.py
    :language: python
    :caption: chunked.py

The optional drain callback ensures that all previous chunks have been
written before processing continues. To end the stream you can call
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.finish` or write an empty
chunk of data.

.. code-block:: text

    HTTP/1.1 200 OK
    Date: Sat, 13 Sep 2014 16:48:29 GMT
    Transfer-Encoding: chunked
    Server: Pyjoyment (Python)

    29
    <html><head><title>Example</title></head>
    1b
    <body>Example</body></html>
    0

Especially in combination with long inactivity timeouts this can be very
useful for Comet (long polling). Due to limitations in some web servers this
might not work perfectly in all deployment environments.

Encoding
~~~~~~~~

Templates stored in files are expected to be ``UTF-8`` by default, but that
can be easily changed with
:attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.encoding`.

.. code-block:: python

    app.renderer.encoding = 'koi8-r'

All templates from the ``__DATA__`` section are characters of the Python
script, which is ``UTF-8`` unless it declares another encoding.

.. literalinclude:: rendering/heart.py
    :language: python
    :caption: heart.py

Base64 encoded DATA files
~~~~~~~~~~~~~~~~~~~~~~~~~

Base64 encoded static files such as images can be easily stored in the
``__DATA__`` section of your application, similar to templates.

.. literalinclude:: rendering/favicon.py
    :language: python
    :caption: favicon.py

Inflating DATA templates
~~~~~~~~~~~~~~~~~~~~~~~~

Templates stored in files get preferred over files from the ``__DATA__``
section, this allows you to include a default set of templates in your
application that the user can later customize. The command
:mod:`Pyjoyment.Command.Author.inflate` will write all templates and static
files from the ``__DATA__`` section into actual files in the ``templates``
and ``public`` directories.

.. code-block:: console

    $ ./myapp.py inflate

Customizing the template syntax
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can easily change the whole template syntax by loading
:mod:`Pyjoyment.Plugin.EPRenderer` with a custom configuration.

.. literalinclude:: rendering/mustache.py
    :language: python
    :caption: mustache.py

:mod:`Pyjo.Template` contains the whole list of available options.

Adding your favorite template system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maybe you would prefer a different template system than ``ep``, which is
provided by :mod:`Pyjoyment.Plugin.EPRenderer`, and there is not already a
plugin on PyPI for your favorite one. All you have to do, is to add a new
``handler`` with :meth:`~Pyjoyment.Renderer.Pyjoyment_Renderer.add_handler`
when ``register`` is called.

.. literalinclude:: rendering/my_renderer/Pyjoyment/Plugin/MyRenderer.py
    :language: python
    :caption: Pyjoyment/Plugin/MyRenderer.py

An ``inline`` template, if provided by the user, will be passed along with
the options. You can use
:meth:`~Pyjoyment.Renderer.Pyjoyment_Renderer.template_path` to search the
``templates`` directories of the application, and
:meth:`~Pyjoyment.Renderer.Pyjoyment_Renderer.get_data_template` to search
the ``__DATA__`` sections.

.. literalinclude:: rendering/mine.py
    :language: python
    :caption: mine.py

Adding a handler to generate binary data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default the renderer assumes that every ``handler`` generates characters
that need to be automatically encoded, but this can be easily disabled if
you're generating bytes instead.

.. literalinclude:: rendering/pickled.py
    :language: python
    :caption: pickled.py

The hook ``before_render`` of :meth:`~Pyjoyment.Pyjoyment_App.hook` can be
used to make stash values like ``pickle`` special, so that they no longer
require a ``handler`` value to be set explicitly.

.. code-block:: python

    # Explicit "handler" value
    c.render(pickle={'i': '♥ pyjoyment'}, handler='pickle')

    # Implicit "handler" value (with "before_render" hook)
    c.render(pickle={'i': '♥ pyjoyment'})

More
----

You can continue with :doc:`index` now or take a look at the `Mojolicious
wiki <https://github.com/mojolicious/mojo/wiki>`_, which contains a lot more
documentation and examples by many different authors.

Ported from `Mojolicious::Guides::Rendering
<https://github.com/mojolicious/mojo/blob/v9.53/lib/Mojolicious/Guides/Rendering.pod>`_
of Mojolicious 9.53.
