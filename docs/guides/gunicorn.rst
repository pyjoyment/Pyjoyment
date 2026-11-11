From gunicorn
=============

The options of gunicorn in the pre-forking server.

This document translates the options, the worker model and the habits of a
deployment of gunicorn into the ones of :mod:`Pyjoyment.Command.prefork`,
the command of :mod:`Pyjo.Server.Prefork`, for an application of
:mod:`Pyjoyment` or one of another framework that it mounts, as a project of
Django, which :doc:`django` serves.

Options
-------

Each option of :mod:`Pyjoyment.Command.prefork` that is not given has the
value of the environment variable of ``PYJO_`` and its name, as
``PYJO_WORKERS`` of ``-w``, so ``GUNICORN_CMD_ARGS`` is one variable for each
option.

.. list-table::
    :header-rows: 1

    * - gunicorn
      - Pyjoyment
    * - ``--bind 0.0.0.0:8080``
      - ``-l 'http://*:8080'``, ``PYJO_LISTEN``, or the port of ``PORT``
    * - ``--bind unix:/run/myapp.sock``
      - ``-l http+unix://%2Frun%2Fmyapp.sock``
    * - ``--certfile``, ``--keyfile``
      - ``-l 'https://*:443?cert=./server.crt&key=./server.key'``
    * - ``--workers``
      - ``-w``, ``PYJO_WORKERS``
    * - the sync workers, one request at a time
      - ``-c 1 -r 1``: one connection for each worker, without keep-alive
    * - ``--threads``
      - :mod:`Pyjoyment.Command.prethread`, whose workers are threads of one
        process, with ``-c 1 -r 1``
    * - ``--worker-class uvicorn.workers.UvicornWorker``
      - the ``ASGI`` application mounted, on the default reactor, of
        :mod:`asyncio`
    * - ``--timeout``
      - ``-H``, ``PYJO_HEARTBEAT_TIMEOUT``: a worker without a heartbeat for
        longer is stopped gracefully, and killed after the graceful timeout
    * - ``--graceful-timeout``
      - ``-G``, ``PYJO_GRACEFUL_TIMEOUT``
    * - none
      - ``-S``, ``PYJO_SHUTDOWN_DELAY``: the time to serve after ``TERM``,
        with a failing ``/readyz`` of :mod:`Pyjoyment.Plugin.Health`
    * - ``--keep-alive``
      - ``-k``, ``PYJO_KEEP_ALIVE_TIMEOUT``
    * - ``--max-requests``
      - ``-a``, ``PYJO_ACCEPTS``: connections, so requests with ``-r 1``
    * - ``--max-requests-jitter``
      - none: up to half of ``-a``, subtracted at random
    * - ``--backlog``
      - ``-b``, ``PYJO_BACKLOG``
    * - ``--forwarded-allow-ips``
      - ``-p``, ``PYJO_REVERSE_PROXY``, with the addresses or the networks of
        the proxies
    * - ``--access-logfile -``, ``--access-logformat``
      - ``plugin('AccessLog')`` and its ``format``
    * - ``--error-logfile``, ``--log-level``
      - ``app.log.path``, ``PYJO_LOG_LEVEL``
    * - ``--limit-request-line``, ``--limit-request-field_size``
      - ``PYJO_MAX_LINE_SIZE``
    * - ``--limit-request-fields``
      - ``PYJO_MAX_LINES``
    * - ``--pid``
      - ``-P``, ``PYJO_PID_FILE``
    * - ``--worker-tmp-dir``, ``--control-socket``
      - none: the heartbeats go through a pipe
    * - ``--preload``
      - always: the application is loaded before the workers are forked
    * - ``--reload``
      - ``pyjo-reload``
    * - ``--user``, ``--group``
      - none: the user of the container, as ``generate dockerfile -u`` sets
        it

Workers
-------

A worker of gunicorn of the default class serves one request at a time, and
closes the connection after it. ``-c 1`` alone serves one connection at a
time, but keeps it alive, so an idle connection of a client or a proxy holds
the worker for the keep-alive timeout, while the other connections wait in
the backlog. Without ``-c 1``, a slow request of an application that blocks
holds the other connections of its worker, while other workers are idle.
``-r 1`` closes the connection after each response, as gunicorn does, which
loses nothing behind a proxy, and avoids the race of a proxy that reuses a
connection that the server closes.

.. code-block:: sh

    $ python app.py prefork -w 8 -c 1 -r 1

An application that does not block, as one of :mod:`Pyjoyment` that awaits
its I/O, keeps the defaults, with many connections in each worker.

Restarts of workers
-------------------

``--max-requests-jitter`` adds a random number up to its value to
``--max-requests`` of each worker of gunicorn, so that the workers, which
share the load evenly, do not restart at the same moment. ``-a`` subtracts a
random number up to half of its value instead, so ``-a 1000`` replaces a
worker after 500 to 1000 connections, 750 on average, and
``--max-requests 1000 --max-requests-jitter 100``, 1050 on average, is
``-a 1400``, 700 to 1400. ``-s``, 2 by default, starts the new worker while
the old one finishes, forked from the manager, which has the application
loaded, so a restart costs little.

Containers
----------

The manager is the process that gets ``TERM``, so a shell in the command of
a container runs it with ``exec``, which makes it PID 1:

.. code-block:: dockerfile

    CMD ["sh", "-c", "exec python -m config.server prefork -w ${WORKERS:-4} -c 1 -r 1"]

Kubernetes kills a container ``terminationGracePeriodSeconds`` after
``TERM``, 30 seconds by default, so the shutdown delay and the graceful
timeout go into it: ``generate kubernetes`` sets it to their sum and 5
seconds more, and a deployment that keeps 30 seconds shortens the graceful
timeout, as ``PYJO_SHUTDOWN_DELAY=5`` with ``PYJO_GRACEFUL_TIMEOUT=20``.

``prefork`` writes only its pid file, ``prefork.pid`` in the temporary
directory, so a read-only root filesystem needs a writable ``TMPDIR``, as an
``emptyDir`` on ``/tmp``, or ``-P`` in another directory.

You can continue with :doc:`index` now.
