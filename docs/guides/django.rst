Django
======

Serving a project of Django with the servers of Pyjoyment.

This document describes how a project of Django, as it is, runs on the
servers of :mod:`Pyjoyment` in the place of gunicorn or uvicorn: its ``WSGI``
or its ``ASGI`` application mounted on ``/`` of an application of
:mod:`Pyjoyment.Lite` with :mod:`Pyjoyment.Plugin.Mount`, with the static
files, the probes and the access log of :mod:`Pyjoyment` around it.
:doc:`gunicorn` translates the options of gunicorn into the ones of
:mod:`Pyjoyment.Command.prefork`.

The project
-----------

The project of this guide has the layout of ``django-admin startproject``,
with a model of notes in SQLite and a ``/healthz`` of its own, and one file
more, ``config/server.py`` next to ``config/wsgi.py``, the script of the
servers of :mod:`Pyjoyment`.

.. literalinclude:: django/config/server.py
    :language: python
    :caption: config/server.py

.. literalinclude:: django/config/settings.py
    :language: python
    :caption: config/settings.py

The script is a module of the project, run from the directory of
``manage.py``, as ``manage.py`` imports the packages of the project from
there, and it starts the server under ``if __name__ == '__main__'``, so that
a test can import it.

.. code-block:: sh

    $ python manage.py migrate
    $ python manage.py collectstatic
    $ python -m config.server prefork -w 8 -c 1 -r 1

The event loop
--------------

A ``WSGI`` application blocks, and runs in the event loop of its worker,
which waits for it. :mod:`Pyjo.App.WSGI` calls it with
:func:`Pyjo.IOLoop.blocking`, so that it sees no running loop of
:mod:`asyncio` while it runs, as on a ``WSGI`` server, where Django would
refuse its database otherwise, as every query would raise
``SynchronousOnlyOperation: You cannot call this from an async context - use
a thread or sync_to_async.``, and a blocking request of :mod:`Pyjo.UserAgent`
would raise too. The code of Django that runs outside the application, as the
check of the database of the probes, is blocking code too, which
:func:`Pyjo.IOLoop.blocking` runs.

The project runs on :mod:`Pyjo.Reactor.Asyncio`, the default reactor, next to
what needs :mod:`asyncio`, as an ``ASGI`` application mounted on another
path, and on :mod:`Pyjo.Reactor.Poll` as well, which ``PYJO_REACTOR``
selects, except that an ``async def`` view, which Django runs in a thread
with an event loop of its own, awaits the promises of :mod:`Pyjo.UserAgent`
only with the reactor of :mod:`asyncio`.

What passes through
-------------------

The request comes to Django as a server of ``WSGI`` gives it:

* ``SCRIPT_NAME`` is empty on ``/``, so the URLs that Django builds need no
  ``FORCE_SCRIPT_NAME``;
* the headers are the ``HTTP_`` variables of the environment, as
  ``X-Forwarded-Proto`` is ``HTTP_X_FORWARDED_PROTO``, which
  ``SECURE_PROXY_SSL_HEADER`` reads;
* ``REMOTE_ADDR`` is the address of the connection, and with ``-p``, the
  reverse proxy support of the servers, the address of ``X-Forwarded-For``,
  with the scheme of ``X-Forwarded-Proto`` as ``wsgi.url_scheme``, so that
  ``request.is_secure()`` is true without ``SECURE_PROXY_SSL_HEADER``.

Django sets ``TZ`` of the process to its ``TIME_ZONE`` when it loads its
settings, ``America/Chicago`` unless the project sets another one, so the
time of the log and of the access log of :mod:`Pyjoyment` is in it too, as of
the rest of the process; ``tz`` of :mod:`Pyjoyment.Plugin.AccessLog` gives
the access log another one.

Static files
------------

:mod:`Pyjoyment.Static` serves the files of ``collectstatic`` before the
routes, in the place of whitenoise, whose middleware leaves ``MIDDLEWARE``:
the parent of ``STATIC_ROOT`` is the directory of the static files, which
has the files of ``/`` too, as ``robots.txt``, and the hashed names of
``ManifestStaticFilesStorage`` are cached for a year, as :doc:`mounting`
describes it. The directory of ``WHITENOISE_ROOT``, of the files of ``/`` as
``favicon.ico``, is another directory of ``app.static.paths``, and
``app.static.extra = {}`` leaves out the favicon and the images of
:mod:`Pyjoyment` for a project that has its own.

With ``DEBUG`` and before ``collectstatic``, ``staticfiles_urlpatterns()`` of
Django serves the static files of the apps, as ``config/urls.py`` does, after
the files that :mod:`Pyjoyment` has, as ``python -m config.server daemon``
of a checkout has none.

Probes
------

:mod:`Pyjoyment.Plugin.Health` answers ``/livez`` and ``/readyz``, which
Kubernetes requests, before the routes, so ``healthz=None`` leaves the
``/healthz`` of the project to it, which its monitors may request with other
expectations. Django does not see the probes, so ``ALLOWED_HOSTS`` does not
reject the address of the pod, which the kubelet sends as ``Host``, and which
a view of Django answers with ``400 Bad Request``: ``/readyz`` is the
readiness probe without a ``Host`` header of its own.

With ``-c 1``, a probe of HTTP is a connection as any other, which waits in
the backlog while every worker is busy, so a liveness probe of HTTP restarts
the pod in a slow spell of a busy application. A liveness probe on
``tcpSocket``, which the kernel accepts into the backlog, does not.

.. code-block:: yaml

    readinessProbe:
      httpGet:
        path: /readyz
        port: http
    livenessProbe:
      tcpSocket:
        port: http

Outside a request of Django, nothing closes a connection of Django to the
database that the database has dropped, as after its restart, so a check
that keeps using it fails every probe until the worker restarts. The check
of ``config/server.py`` is framed as a request of Django, whose handlers of
``request_started`` and ``request_finished`` close a connection that is
broken or older than ``CONN_MAX_AGE``, as for a view, so that the next probe
connects again.

The timeout of a check of :mod:`Pyjoyment.Plugin.Health` is the one of a
check that returns a promise or a coroutine. A check that blocks runs to its
end first, so the timeouts of its driver bound it, as ``connect_timeout`` in
the ``OPTIONS`` of the database.

Access log
----------

:mod:`Pyjoyment.Plugin.AccessLog` writes a line of each response to the
standard output, in the combined format of the access log of gunicorn,
without the probes, as :doc:`cookbook` describes it. Behind a gateway that
gives the address of the client in a header of its own, ``client`` takes it,
as ``plugin('AccessLog', client='X-Envoy-External-Address')``, as the first
address of ``X-Forwarded-For`` is whatever the client wrote there.

Requests to other services
--------------------------

:mod:`Pyjo.UserAgent` is the HTTP client of a view, in the place of
``requests`` or ``httpx``. In a view of ``WSGI``, a blocking request runs
an event loop of its own, while the worker waits for it as for a query of the
database, so a request to the application itself needs another worker that is
free.

.. literalinclude:: ../../examples/servers/django_wsgi.py
    :language: python
    :caption: django_wsgi.py

ASGI
----

The ``ASGI`` application of the project runs on the default reactor, of
:mod:`asyncio`, with the same script, which mounts it in the place of the
``WSGI`` one.

.. code-block:: python

    plugin('Mount', {'/': 'config.asgi:application'})

Its ``async def`` views run in the event loop, where they await anything of
:mod:`asyncio` and the promises of :mod:`Pyjo.UserAgent`, while the event
loop serves the other requests. Its synchronous views and middleware run in a
thread, which ``sync_to_async`` of Django gives them, one thread for all of
them, and so do the queries of its async ORM, as
``await Note.objects.acount()``, as the backends of databases of Django are
synchronous.
A project of synchronous views and queries serves one request at a time in
each worker, and runs better on ``WSGI``.

.. literalinclude:: ../../examples/servers/django_asgi.py
    :language: python
    :caption: django_asgi.py

The ``ASGI`` application of Django has no lifespan, which
:mod:`Pyjo.App.ASGI` notes in the log on ``debug`` and serves it without.

Tests
-----

The tests of the project, which ``manage.py test`` runs, test the static
files, the probes and the routes of :mod:`Pyjoyment` in front of it too, with
:mod:`Pyjo.Test.Pyjo` of the application of ``config/server.py`` in a
``TestCase`` of Django, as :mod:`Pyjo.Test` describes the tests of
:mod:`unittest`.

.. literalinclude:: django/notes/tests.py
    :language: python
    :caption: notes/tests.py

A request of the test reaches the ``WSGIHandler`` of Django, as one of a
server does, which sends ``request_started`` and ``request_finished``, and so
does the check of the database. Their handler ``close_old_connections``
closes a connection that is not in the autocommit of the settings, as the one
of the transaction of a ``TestCase``, so a query of the view and of the check
fails after it. The test client of Django detaches the handler for its own
requests, and the test detaches it for its class. The test database of SQLite
in memory, the default, hides it, as Django does not close its connection,
and one of PostgreSQL, or of SQLite in a file, shows it.

More
----

The page of :doc:`/examples` has both examples, which request the API of
GitHub, or the one of ``GITHUB_API_URL``.

You can continue with :doc:`index` now.
