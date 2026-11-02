FAQ
===

Frequently Asked Questions.

This document contains answers for the most frequently asked questions about
:mod:`Pyjoyment`.

Questions
---------

We hope these answers are to your satisfaction.

How does Pyjoyment compare to other Python web frameworks?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The short answer is "it doesn't", because we interpret the term "web
framework" much more literally than others. With the emergence of the
real-time web and new technologies such as WebSockets, we are facing new
challenges that go way beyond what commonly used modules like
:mod:`urllib.request` were designed for. Because of this, :mod:`Pyjoyment`
contains a whole new HTTP client/server stack called :mod:`Pyjo`, the port
of Mojo of Mojolicious, which was heavily inspired by the original LWPng
effort and carefully designed with these new requirements in mind. So while
some of the higher abstraction layers might look similar to other web
frameworks, it is more of a web toolkit and can even be used as the
foundation for more advanced web frameworks.

Why doesn't Pyjoyment have any dependencies?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We are optimizing :mod:`Pyjoyment` for user-friendliness and development
speed, without compromises. The rules of :doc:`contributing` allow no
dependencies at run time, in favor of a faster and more painless installation
process. Where Mojolicious uses optional CPAN modules such as Cpanel::JSON::XS,
EV, IO::Socket::SSL and Net::DNS::Native to provide advanced functionality,
the standard library of Python has :mod:`json`, :mod:`asyncio`, :mod:`ssl`
and :func:`socket.getaddrinfo` in a thread. And a reactor on another event loop, as uvloop, can come from another
distribution, in the namespace ``Pyjo.Reactor``.

Why reinvent wheels?
~~~~~~~~~~~~~~~~~~~~

Because we can make them rounder. Components specifically designed for
user-friendliness and development speed are not easy to come by. We are
strong believers of the Perl mantra "There is more than one way to do it",
even where the Zen of Python prefers one obvious way, and our quest is to
develop the best possible solutions for these two criteria.

.. Left out from Mojolicious: "What about backwards compatibility?", as Pyjoyment has no policy of deprecations yet

Why not split up Pyjoyment into many smaller distributions?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Because there are no advantages, it drastically increases maintenance costs
and installation times without giving us anything in return. A distribution
of its own is for what extends :mod:`Pyjoyment`, as a reactor in the
namespace ``Pyjo.Reactor`` or a plugin in the namespace ``Pyjoyment.Plugin``.

Where can I discuss my patches for Pyjoyment?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We'd love to discuss your contributions to :mod:`Pyjoyment` on the `GitHub
issue tracker <https://github.com/pyjoyment/Pyjoyment/issues>`_.

Which versions of Python are supported by Pyjoyment?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First of all, you need to be aware that according to :pep:`602`, each
release series of Python receives bug fixes for two years, and security fixes
only for three more. :mod:`Pyjoyment` supports Python 3.12 and newer, and is
tested on each of these release series, as well as on the free-threaded build
of the newest one. PyPy is supported on a best-effort basis.

How well is Windows supported by Pyjoyment?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Windows is not officially supported by :mod:`Pyjoyment`, even though we try
to keep the distribution installable. There may be serious security and/or
reliability issues. Some of the more advanced features, such as
:meth:`subprocesses <Pyjo.IOLoop.Pyjo_IOLoop.subprocess>`,
:meth:`child processes <Pyjo.IOLoop.Pyjo_IOLoop.spawn>` and the
:mod:`Hot <Pyjo.Server.Hot>` web server, will also require the use of the
`Windows Subsystem for Linux <https://learn.microsoft.com/windows/wsl/>`_.
The port to Windows is followed in `its issue
<https://github.com/pyjoyment/Pyjoyment/issues/253>`_.

.. Left out from Mojolicious: "Is Perl's taint mode supported by Mojolicious?", as Python has no taint mode

Do I need to clean my environment before testing Pyjoyment?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:mod:`Pyjoyment` uses many environment variables both internally and
externally, notably (but not exclusively) those starting with the prefix
``PYJO_*``, as well as ``PORT`` and ``AWS_LAMBDA_RUNTIME_API``. The test suite
expects a clean environment; testing with a non-standard environment is
unsupported and is unlikely to succeed. Therefore when running the tests of
:mod:`Pyjoyment`, we highly recommend using an environment which does not set
these variables.

.. _faq-file-extension:

Where did my file extension go?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Standard route placeholders will not match the ``.`` character, however
:mod:`Pyjoyment` routes can take file extensions like ``.html``, remove the
leading ``.``, and store the result in the ``format`` stash value, when they
declare the possible values with a restrictive placeholder. This can be
useful for URL-based content negotiation, such as automatically rendering
different templates based on the file extension. See :ref:`the formats in
the routing guide <routing-formats>` for information on customizing format
detection, or consider using :ref:`relaxed placeholders
<routing-relaxed-placeholders>` to allow matching of the ``.`` character.

Can I configure Hot from the command line?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

No, you can't, :mod:`Hot <Pyjo.Server.Hot>` is a bit special in this regard.
Because when you initiate a zero downtime software upgrade (hot deployment),
you are only really sending a ``HUP`` signal to the already running server,
and no other information can be passed along. What you can do instead, is to
use a :mod:`Pyjoyment.Plugin.Config`, :mod:`Pyjoyment.Plugin.JSONConfig`,
:mod:`Pyjoyment.Plugin.YAMLConfig` or :mod:`Pyjoyment.Plugin.TOMLConfig`
configuration file.

.. code-block:: python
    :caption: myapp.conf

    {
        'hot': {
            'listen': ['http://*:8080'],
            'workers': 10,
        }
    }

Or if you don't actually need zero downtime software upgrades, just use
:mod:`Pyjoyment.Command.prefork` instead, which is otherwise almost identical
to Hot.

.. code-block:: console

    $ ./myapp.py prefork -m production -l http://*:8080 -w 10

What does the error "...certificate verify failed" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are many variations of this error, but most of them mean that TLS
certificate verification in :mod:`Pyjo.UserAgent` failed. This usually
happens for two reasons. The most common one is that the peer certificate is
simply invalid. If that's the case and you are certain that no MITM attack is
being attempted, you can use the attribute
:attr:`~Pyjo.UserAgent.Pyjo_UserAgent.insecure` or ``PYJO_INSECURE``
environment variable to disable certificate verification. And if that's not
the case you might be missing the certificate authorities of the system,
which :func:`ssl.create_default_context` loads from the default locations of
OpenSSL, and which the ``SSL_CERT_FILE`` and ``SSL_CERT_DIR`` environment
variables can point to.

What does the error "Maximum message size exceeded" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To protect your applications from excessively large requests and responses,
our HTTP parser has a cap after which it will automatically stop accepting
new data, and in most cases force the connection to be closed. The limit is
16MiB for requests, and 2GiB for responses by default. You can use the
attributes :attr:`~Pyjoyment.Pyjoyment_App.max_request_size` and
:attr:`~Pyjo.UserAgent.Pyjo_UserAgent.max_response_size` to change these
values.

What does the error "Maximum start-line size exceeded" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a very similar protection mechanism to the one described in the
previous answer, but a little more specific. It limits the maximum length of
the start-line for HTTP requests and responses. The limit is 64KiB by
default, you can use the attribute
:attr:`~Pyjo.Message.Pyjo_Message.max_line_size` or ``PYJO_MAX_LINE_SIZE``
environment variable to change this value.

What does the error "Maximum header size exceeded" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Almost the same as the previous answer, but this protection mechanism limits
the number and maximum length of HTTP request and response headers. The
limits are 100 headers with 64KiB each by default, you can use the attributes
:attr:`~Pyjo.Headers.Pyjo_Headers.max_lines` and
:attr:`~Pyjo.Headers.Pyjo_Headers.max_line_size` or the ``PYJO_MAX_LINES``
and ``PYJO_MAX_LINE_SIZE`` environment variables to change these values.

What does the error "Maximum buffer size exceeded" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This protection mechanism limits how much content the HTTP parser is allowed
to buffer when parsing chunked, compressed and multipart messages. The limit
is around 256KiB by default, you can use the attribute
:attr:`~Pyjo.Content.Pyjo_Content.max_buffer_size` or
``PYJO_MAX_BUFFER_SIZE`` environment variable to change this value.

What does "Your secret passphrase needs to be changed" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:mod:`Pyjoyment` uses secret passphrases for security features such as
signed cookies. It defaults to using
:attr:`~Pyjo.App.Pyjo_App.moniker`, which is not very secure, so we added
this log message as a reminder. You can change the passphrase with the
attribute :attr:`~Pyjoyment.Pyjoyment_App.secrets`. Since some plugins also
depend on it, you should try changing it as early as possible in your
application.

.. code-block:: python

    app.secrets = ['My very secret passphrase.']

What does "Nothing has been rendered, expecting delayed response" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:mod:`Pyjoyment` has been designed from the ground up for non-blocking I/O
and event loops. So when a new request comes in and no response is generated
right away, it will assume that this was intentional and return control to
the web server, which can then handle other requests while waiting for events
such as timers to finally generate a response.

What does "Action returned a str, which is not a response" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An action generates its response with the methods of the controller, such as
:meth:`~Pyjoyment.Controller.Pyjoyment_Controller.render`, and what it returns
is not the response, as it is for a view of other Python web frameworks. When
an action returns a string, bytes, a dict, a list or a tuple and nothing has
been rendered, not even a template named after its route, :mod:`Pyjoyment`
reports it instead of waiting for a delayed response.

.. code-block:: python

    @get('/')
    def hello(c):
        c.render(text='Hello World!')

    @get('/data')
    def data(c):
        c.render(json={'hello': 'world'})

What does "Helper "log" has no attribute "debug"" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A helper is called, also one without arguments, which returns an object, such
as ``log`` of :mod:`Pyjoyment.Plugin.DefaultHelpers` the logger of the
request, and ``ua`` the user agent of the application. Without the call, the
attribute is taken from the helper itself.

.. code-block:: python

    @get('/')
    def hello(c):
        c.log().debug('Hello!')
        c.render(text='Hello World!')

What does "Inactivity timeout" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To protect your applications from denial-of-service attacks, all connections
have an inactivity timeout which limits how long a connection may be inactive
before being closed automatically. It defaults to ``40`` seconds for the user
agent and ``30`` seconds for all built-in web servers, and can be changed
with the attributes
:attr:`~Pyjo.UserAgent.Pyjo_UserAgent.inactivity_timeout` and
:attr:`~Pyjo.Server.Daemon.Pyjo_Server_Daemon.inactivity_timeout` or the
``PYJO_INACTIVITY_TIMEOUT`` environment variable. In :mod:`Pyjoyment`
applications you can also use the helper ``inactivity_timeout`` of
:mod:`Pyjoyment.Plugin.DefaultHelpers` to change it on demand for each
connection individually. This timeout always applies, so you might have to
tweak it for applications that take a long time to process a request.

What does "Premature connection close" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This error message is often related to the one above, and means that the web
server closed the connection before the user agent could receive the whole
response or that the user agent got destroyed, which forces all connections
to be closed immediately.

.. code-block:: python

    # The variable ua goes out of scope and gets destroyed too early
    @Pyjo.IOLoop.timer(5)
    def visit(loop):
        ua = Pyjo.UserAgent.new()
        ua.get('https://pyjoyment.readthedocs.io', lambda ua, tx: print(tx.result.dom.at('title').text))

What does "Worker 31842 has no heartbeat (50 seconds), restarting" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As long as they are accepting new connections, worker processes of all
built-in pre-forking web servers, and the worker threads of
:mod:`Pyjo.Server.Prethread`, send heartbeat messages to the manager process
at regular intervals, to signal that they are still responsive. A blocking
operation such as an infinite loop in your application can prevent this, and
will force the affected worker to be restarted after a timeout. This timeout
defaults to ``50`` seconds and can be extended with the attribute
:attr:`~Pyjo.Server.Prefork.Pyjo_Server_Prefork.heartbeat_timeout` if your
application requires it.

What does "Transaction already destroyed" mean?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This error message usually appears after waiting for the results of a
non-blocking operation for longer periods of time, because the underlying
connection has been closed in the meantime and the value of the attribute
:attr:`~Pyjoyment.Controller.Pyjoyment_Controller.tx` is no longer
available. While there might not be a way to prevent the connection from
getting closed, you can try to avoid this error message by keeping a
reference to the transaction object that is not weak.

.. code-block:: python

    # Keep a strong reference to the transaction object
    tx = c.render_later().tx


    def visited(res):
        c.render(text='Visited pyjoyment.readthedocs.io')


    def failed(err):
        tx
        c.reply.exception(err)


    c.ua().get_p('https://pyjoyment.readthedocs.io').then(visited).catch(failed)

.. Left out from Mojolicious: "What does "Illegal character in prototype" mean?", as Python has no prototypes and
   its function signatures need no feature

More
----

You can continue with :doc:`index` now or take a look at the `Mojolicious
wiki <https://github.com/mojolicious/mojo/wiki>`_, which contains a lot more
documentation and examples by many different authors.

Ported from `Mojolicious::Guides::FAQ
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Guides/FAQ.pod>`_
of Mojolicious 9.49.
