Examples
========

Foundation
----------

Web scraping
~~~~~~~~~~~~

The user agent requests the HTML specification, and the lazy chain of
``iterate`` of its DOM prints the rows of the table of the named character
references one by one:

    .. include:: ../examples/ua/entities.py
       :code: python


URL manipulation
~~~~~~~~~~~~~~~~

    .. include:: ../examples/pyjo/url.py
       :code: python


Non-blocking TCP client/server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    .. include:: ../examples/pyjo/ioloop.py
       :code: python


Standalone HTTP server serving embedded template file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    .. include:: ../examples/servers/http_server.py
       :code: python


Requests on a timer
~~~~~~~~~~~~~~~~~~~

The user agent requests the server every second, in the same event loop, without
blocking it:

    .. include:: ../examples/ua/user_agent.py
       :code: python


A request on a loopback
~~~~~~~~~~~~~~~~~~~~~~~

A blocking request of the user agent to the server, in the same event loop:

    .. include:: ../examples/ua/loopback.py
       :code: python


Composition
-----------

Quick start
~~~~~~~~~~~

A whole web application of ``Pyjoyment.Lite``:

    .. include:: ../examples/pyjoyment/hello.py
       :code: python


JSON-RPC
~~~~~~~~

A calculator with Bootstrap, which is a client of the server of JSON-RPC of the
same application, whose methods validate their parameters with the schema of
their type hints, and shows the request and the response of each call:

    .. include:: ../examples/pyjoyment/json_rpc.py
       :code: python


Applications of other frameworks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A WSGI application, an ASGI application and an event function of AWS
Lambda, each in a file of its own, under the paths of an application of
``Pyjoyment.Lite``, on one server:

    .. include:: ../examples/mount/compose.py
       :code: python

A WSGI application, in a file of its own, under a path of an application of
``Pyjoyment.Lite``:

    .. include:: ../examples/mount/mount_wsgi.py
       :code: python

The WSGI application, which also runs on its own, on the WSGI server of the
standard library:

    .. include:: ../examples/mount/hello_wsgi.py
       :code: python

An application of Pyjoyment as the WSGI application, in the same file:

    .. include:: ../examples/mount/mount_wsgi_inception.py
       :code: python

An ASGI application, in a file of its own, under a path of an application of
``Pyjoyment.Lite``, whose events stream at the pace of the client:

    .. include:: ../examples/mount/mount_asgi.py
       :code: python

The ASGI application, which also runs on its own, on an ASGI server:

    .. include:: ../examples/mount/hello_asgi.py
       :code: python

An application of Pyjoyment as the ASGI application, in the same file:

    .. include:: ../examples/mount/mount_asgi_inception.py
       :code: python

A server of the MCP SDK, whose transport of Streamable HTTP is an ASGI
application, under a path of an application of ``Pyjoyment.Lite``:

    .. include:: ../examples/mount/mount_mcp.py
       :code: python

PHP on php-fpm, a FastCGI application, under a path of an application of
``Pyjoyment.Lite``, with the scripts of its directory and the pool of
php-fpm:

    .. include:: ../examples/mount/mount_fastcgi_php.py
       :code: python

    .. include:: ../examples/mount/php/index.php
       :code: php

    .. include:: ../examples/mount/php/phpinfo.php
       :code: php

    .. include:: ../examples/mount/php/php-fpm.conf
       :code: ini

A CGI program of Python in the directory ``cgi-bin``, under a path of an
application of ``Pyjoyment.Lite``, a process for each request:

    .. include:: ../examples/mount/mount_cgi.py
       :code: python

    .. include:: ../examples/mount/cgi-bin/hello.py
       :code: python

PHP on php-cgi, with the scripts of the same directory as for php-fpm, a
process of php-cgi for each request:

    .. include:: ../examples/mount/mount_cgi_php.py
       :code: python

An event function of AWS Lambda, in a file of its own, under a path of an
application of ``Pyjoyment.Lite``, in a process of its own, which gets the
requests one after another, as Lambda runs it:

    .. include:: ../examples/mount/mount_lambda.py
       :code: python

The event function, whose stage is the path it is mounted under:

    .. include:: ../examples/mount/hello_lambda.py
       :code: python

Starlette on Mangum as the event function, which runs an event loop of its own
in its process:

    .. include:: ../examples/mount/mount_lambda_mangum.py
       :code: python

    .. include:: ../examples/mount/hello_mangum.py
       :code: python

An application of Pyjoyment on :mod:`Pyjo.Server.Lambda` as the event function,
in the same file, which its process imports:

    .. include:: ../examples/mount/mount_lambda_inception.py
       :code: python


Both sides of the interface
---------------------------

Servers
~~~~~~~

``Pyjo.HelloWorld`` natively, on the web server of Pyjoyment:

    .. include:: ../examples/servers/hello_world.py
       :code: python

On `uvicorn <https://www.uvicorn.org/>`_, an ASGI server:

    .. include:: ../examples/servers/hello_world_uvicorn.py
       :code: python

On `Werkzeug <https://werkzeug.palletsprojects.com/>`_, a WSGI server:

    .. include:: ../examples/servers/hello_world_werkzeug.py
       :code: python


Deployment
----------

AWS Lambda
~~~~~~~~~~

As an event function of `AWS Lambda <https://aws.amazon.com/lambda/>`_:

    .. include:: ../examples/servers/hello_world_lambda.py
       :code: python

On a custom runtime of AWS Lambda, as ``provided.al2023``, its ``bootstrap``
runs it with the runtime client of Pyjoyment:

    .. include:: ../examples/servers/bootstrap
       :code: sh


Integration
-----------

WebSocket
~~~~~~~~~

A page of the application opens a WebSocket to it and sends it a URL, which
the application requests with its user agent, without blocking the other
connections, and sends back the title of the page:

    .. include:: ../examples/pyjoyment/title.py
       :code: python


Amazon S3
~~~~~~~~~

A bucket of Amazon S3 as a website, with `aiobotocore
<https://github.com/aio-libs/aiobotocore>`_, the asynchronous AWS SDK, whose
requests the actions await in the event loop of the server: the content of an
object, as it comes, ``index.html`` of a folder, or the list of its folders
and objects:

    .. include:: ../examples/aws/s3.py
       :code: python
