Cookbook
========

Cooking with Pyjoyment.

This document contains many fun recipes for cooking with :mod:`Pyjoyment`.

Concepts
--------

Essentials every :mod:`Pyjoyment` developer should know.

Blocking and non-blocking operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A *blocking* operation is a function that blocks the execution of the calling
function until the function is finished.

.. code-block:: python

    def foo():
        result = blocking_function()
        ...

A *non-blocking* operation on the other hand lets the calling function
continue execution even though the function is not yet finished. Instead of
waiting, the calling function passes along a callback to be executed once the
function is finished, this is called continuation-passing style.

.. code-block:: python

    def foo():
        def done(result):
            ...

        non_blocking_function(done)
        ...

While :mod:`Pyjoyment` has been designed from the ground up for non-blocking
I/O and event loops, it is not possible to magically make Python code
non-blocking. You have to use specialized non-blocking code available through
modules like :mod:`Pyjo.IOLoop` and :mod:`Pyjo.UserAgent`, or the coroutines
of :mod:`asyncio`. You can wrap your blocking code in
:meth:`subprocesses <Pyjo.IOLoop.Pyjo_IOLoop.subprocess>` though to prevent
it from interfering with your non-blocking code, and run programs in
:meth:`child processes <Pyjo.IOLoop.Pyjo_IOLoop.spawn>`.

Event loops
~~~~~~~~~~~

An event loop is basically a loop that continually tests for external events
and executes the appropriate callbacks to handle them, it is often the main
loop in a program. Non-blocking tests for readability/writability of file
descriptors and timers are commonly used events for highly scalable network
servers, because they allow a single process to handle thousands of client
connections concurrently.

.. code-block:: python

    while True:
        readable = test_fds_for_readability()
        handle_readable_fds(readable)

        writable = test_fds_for_writability()
        handle_writable_fds(writable)

        expired = test_timers()
        handle_timers(expired)

In :mod:`Pyjoyment` this event loop is :mod:`Pyjo.IOLoop`, which runs on the
event loop of :mod:`asyncio`.

Reverse proxy
~~~~~~~~~~~~~

A reverse proxy architecture is a deployment technique used in many
production environments, where a *reverse proxy* server is put in front of
your application to act as the endpoint accessible by external clients. It
can provide a lot of benefits, like terminating SSL connections from the
outside, limiting the number of concurrent open sockets towards the
Pyjoyment application (or even using Unix sockets), balancing load across
multiple instances, or supporting several applications through the same
IP/port.

.. mermaid::

    flowchart LR
        client <--> proxy
        subgraph boundary [system boundary, e.g. same host]
            proxy[reverse proxy] <--> app[Pyjoyment application]
        end

This setup introduces some problems, though: the application will receive
requests from the reverse proxy instead of the original client; the
address/hostname where your application lives internally will be different
from the one visible from the outside; and if terminating SSL, the reverse
proxy exposes services via HTTPS while using HTTP towards the Pyjoyment
application.

As an example, compare a sample request from the client and what the
Pyjoyment application receives:

.. mermaid::

    %%{init: {'sequence': {'noteAlign': 'left'}}}%%
    sequenceDiagram
        participant client as client<br/>1.2.3.4
        participant proxy as reverse proxy<br/>api.example.com<br/>10.20.30.39
        participant app as Pyjoyment app<br/>10.20.30.40
        client ->> proxy: HTTPS
        Note over client,proxy: GET /foo/1 HTTP/1.1<br/>Host: api.example.com<br/>User-Agent: Firefox<br/>...
        proxy ->> app: HTTP
        Note over proxy,app: GET /foo/1 HTTP/1.1<br/>Host: 10.20.30.40<br/>User-Agent: ShinyProxy/1.2<br/>...

However, now the client address is no longer available (which might be
useful for analytics, or Geo-IP) and URLs generated via
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.url_for` will look like
this:

.. code-block:: text

   http://10.20.30.40/bar/2

instead of something meaningful for the client, like this:

.. code-block:: text

   https://api.example.com/bar/2

To solve these problems, you can configure your reverse proxy to send the
missing data (see `Nginx`_, `Apache/mod_proxy`_ and `Caddy`_) and tell your
application about it by setting the environment variable
``PYJO_REVERSE_PROXY``. In more complex situations, usually involving
multiple proxies or proxies that live outside your network, it can be
necessary to tell the application from which ip addresses to expect proxy
requests by setting ``PYJO_TRUSTED_PROXIES`` to a list of comma separated
addresses or CIDR networks. For even finer control, `Rewriting`_ includes
examples of how the changes could be implemented manually.

Hosts and origins
~~~~~~~~~~~~~~~~~

A server on ``localhost`` is not reachable from other machines, but it is
from the browser of its user, and so from every page that the browser has
open. A page of another site can request it, and with *DNS rebinding*, where
the attacker makes the name of its own site an address of ``127.0.0.1``, even
read the responses, as the browser takes the server for the site of the page.
Such a request has the name of the site of the attacker in its ``Host``
header, and the origin of its page, a scheme, a host and a port, in its
``Origin`` header, which a browser sends with a request of a page of another
site.

:mod:`Pyjoyment.Plugin.AllowedHosts` rejects a request whose ``Host`` is not
one of the hosts of the application, with ``421 Misdirected Request``, and a
request whose ``Origin`` is not one of its origins, with ``403 Forbidden``.
Without options, the hosts are those of ``localhost``, on any port, and the
origins are those of the hosts, which is what a server for development, or
of the Model Context Protocol on the machine of its user, needs.

.. code-block:: python

    plugin('AllowedHosts')

A deployment names its own hosts, a domain with its subdomains with a leading
dot, and the origins of the pages that request it, which replace the ones of
the hosts.

.. literalinclude:: cookbook/hosts.py
    :language: python
    :caption: myapp.py

Behind a `Reverse proxy`_, the host is the one of ``Host``, which the proxy
passes on, so it is the name that the clients use. To check only some routes,
as the endpoint of MCP of an application whose pages are public, the plugin
leaves out its hook, and the helper ``allowed_hosts`` checks the routes under
it, where it ends the dispatch of a request that is not allowed.

.. literalinclude:: cookbook/hosts_under.py
    :language: python
    :caption: myapp.py

.. _cookbook-deployment:

Deployment
----------

Getting :mod:`Pyjoyment` and :mod:`Pyjoyment.Lite` applications running on
different platforms. Note that many real-time web features are based on the
:mod:`Pyjo.IOLoop` event loop, and therefore require one of the built-in web
servers, or an ASGI server, to be able to use them to their full potential.

Built-in web server
~~~~~~~~~~~~~~~~~~~

:mod:`Pyjoyment` contains a very portable non-blocking I/O HTTP and WebSocket
server with :mod:`Pyjo.Server.Daemon`. It is usually used during development
and in the construction of more advanced web servers, but is solid and fast
enough for small to mid sized applications.

.. code-block:: console

    $ ./myapp.py daemon
    Web application available at http://127.0.0.1:3000

It is available to every application through the command
:mod:`Pyjoyment.Command.daemon`, which has many configuration options and is
known to work on every platform Python works on with its single-process
architecture.

.. code-block:: console

    $ ./myapp.py daemon -h
    ...List of available options...

Another huge advantage is that it supports TLS and WebSockets out of the box,
a development certificate for testing purposes is built right in, so it just
works, but you can specify all listen locations supported by
:attr:`Pyjo.Server.Daemon.Pyjo_Server_Daemon.listen`.

.. code-block:: console

    $ ./myapp.py daemon -l 'https://[::]:3000'
    Web application available at https://[::]:3000

To manage the web server with systemd, you can use a unit configuration file
like this.

.. code-block:: ini

    [Unit]
    Description=My Pyjoyment application
    After=network.target

    [Service]
    Type=simple
    User=sri
    ExecStart=/home/sri/myapp/myapp.py daemon -m production -l http://*:8080

    [Install]
    WantedBy=multi-user.target

Pre-forking
~~~~~~~~~~~

For bigger applications :mod:`Pyjoyment` contains the UNIX optimized
pre-forking web server :mod:`Pyjo.Server.Prefork`, which can take advantage
of multiple CPU cores and copy-on-write memory management to scale up to
thousands of concurrent client connections.

.. mermaid::

    treeView-beta
        Pyjo.Server.Prefork
            Pyjo.Server.Daemon [1]
            Pyjo.Server.Daemon [2]
            Pyjo.Server.Daemon [3]
            Pyjo.Server.Daemon [4]

It is based on :mod:`Pyjo.Server.Daemon` and available to every application
through the command :mod:`Pyjoyment.Command.prefork`.

.. code-block:: console

    $ ./myapp.py prefork
    Web application available at http://127.0.0.1:3000

Since all built-in web servers are based on the :mod:`Pyjo.IOLoop` event
loop, they scale best with non-blocking operations. But if your application
for some reason needs to perform many blocking operations, you can improve
performance by increasing the number of worker processes and decreasing the
number of concurrent connections each worker is allowed to handle (often as
low as ``1``).

.. code-block:: console

    $ ./myapp.py prefork -m production -w 10 -c 1
    Web application available at http://127.0.0.1:3000

:doc:`gunicorn` translates the options of gunicorn into the ones of the
pre-forking web server, and :doc:`django` serves a project of Django with it.

During startup your application is preloaded in the manager process, which
does not run an event loop, so you can use
:meth:`Pyjo.IOLoop.Pyjo_IOLoop.next_tick` to run code whenever a new worker
process has been forked and its event loop gets started.

.. literalinclude:: cookbook/worker.py
    :language: python
    :caption: myapp.py

And to manage the pre-forking web server with systemd, you can use a unit
configuration file like this.

.. code-block:: ini

    [Unit]
    Description=My Pyjoyment application
    After=network.target

    [Service]
    Type=simple
    User=sri
    ExecStart=/home/sri/myapp/myapp.py prefork -m production -l http://*:8080

    [Install]
    WantedBy=multi-user.target

Reload
~~~~~~

After reading the :doc:`tutorial`, you should already be familiar with
:mod:`Pyjo.Server.Reload`.

.. mermaid::

    treeView-beta
        Pyjo.Server.Reload
            Pyjo.Server.Daemon (or Pyjo.Server.Prefork)

It is basically a restarter that starts a new :mod:`Pyjo.Server.Daemon` web
server whenever a file in your project changes, and should therefore only be
used during development. To start applications with it you can use the
``pyjo-reload`` script, or the command ``reload`` of the application, which
takes the same options, and watches the package of an application too.

.. code-block:: console

    $ pyjo-reload ./myapp.py
    Web application available at http://127.0.0.1:3000

    $ ./myapp.py reload
    Web application available at http://127.0.0.1:3000

    $ python -m MyApp reload
    Web application available at http://127.0.0.1:3000

Any other server command can be used too, just put it after the application.

.. code-block:: console

    $ pyjo-reload ./myapp.py prefork -w 2

Additional commands that should run during development, like asset bundlers
in watch mode, can be started alongside the server. They run until
:mod:`Pyjo.Server.Reload` is stopped, and see the same ``PYJO_MODE`` as your
application.

.. code-block:: console

    $ pyjo-reload -x 'npx webpack --watch' ./myapp.py

Containers
~~~~~~~~~~

There are many ways to go cloud-native with :mod:`Pyjoyment`. To get you
started with containerizing your web applications we will explore one of them
in this recipe. First, you will need to declare the dependencies of your
application, for example in a ``pyproject.toml`` file. This should always
include at the very least :mod:`Pyjoyment` itself.

.. code-block:: toml

    [project]
    name = "myapp"
    version = "0.1.0"
    requires-python = ">=3.12"
    dependencies = ["Pyjoyment"]

The helper command :mod:`Pyjoyment.Command.Author.generate.pyproject` can
also generate a minimal ``pyproject.toml`` for you.

.. code-block:: console

    $ ./myapp.py generate pyproject
    ...

And then we are going to need a ``Dockerfile`` describing the container. A
very simple one will do for now.

.. code-block:: dockerfile

    FROM python:3.15
    COPY --from=ghcr.io/astral-sh/uv /uv /bin/uv
    WORKDIR /opt/myapp
    COPY . .
    RUN uv sync --no-dev
    EXPOSE 3000
    CMD [".venv/bin/python", "myapp.py", "prefork"]

It uses the `Python container <https://hub.docker.com/_/python>`_ from Docker
Hub, copies all the contents of your application directory into the
container, installs the dependencies with `uv <https://docs.astral.sh/uv/>`_,
and then starts the application on port ``3000`` with the pre-forking web
server. With :mod:`Pyjoyment.Command.Author.generate.dockerfile` there is also
a helper command to generate a ``Dockerfile`` for you, with a smaller image
and a server that stops gracefully in the time a container gets.

.. code-block:: console

    $ ./myapp.py generate dockerfile
    ...

To build and deploy our container there are also many options available, here
we will simply use Docker.

.. code-block:: console

    $ docker build -t myapp_image .
    ...
    $ docker run -d -p 3000:3000 --name myapp_container myapp_image
    ...

And now your web application should be deployed as a container under
``http://127.0.0.1:3000``. With the ``PYJO_LOG_FORMAT`` environment variable
set to ``json``, as the option ``--log-format json`` of the commands sets it,
its log messages are lines of JSON, which the log collectors of platforms such
as Cloud Run and Kubernetes read with their levels and fields, see
:mod:`Pyjo.Log`.

.. code-block:: console

    $ docker run -d -p 3000:3000 -e PYJO_LOG_FORMAT=json --name myapp_container myapp_image
    ...

For Kubernetes, :mod:`Pyjoyment.Command.Author.generate.kubernetes` generates
the manifests of Kustomize, with an overlay ``prod`` that runs the image of
the ``Dockerfile``, and an overlay ``dev`` that runs the application without
an image of its own, on the image of uv, from a ConfigMap with the server
``daemon``, or with ``--host-path`` from the directory of the project, which a
local cluster, as the one of Docker Desktop or OrbStack, mounts, with
``pyjo-reload``. ``--server`` chooses another server, with its options after
``--``.

.. code-block:: console

    $ ./myapp.py generate kubernetes --image myapp_image
    ...
    $ kubectl apply -k kubernetes/dev
    ...
    $ kubectl apply -k kubernetes/prod
    ...

The overlay ``dev`` has a copy of the application in ``kubernetes/dev/files``,
which the generator writes anew each time, so it belongs in ``.gitignore``.

For more information and many more container deployment options we recommend
the `Docker <https://docs.docker.com/>`_ and `Kubernetes
<https://kubernetes.io/docs/>`_ documentation.

Health checks
~~~~~~~~~~~~~

Orchestrators and load balancers ask an application over HTTP whether it is
alive and whether it is ready for requests. :mod:`Pyjoyment.Plugin.Health`
answers them with the endpoints of Kubernetes: ``/livez`` while the server
answers, ``/healthz`` as its alias, and ``/readyz`` once the checks of the
application pass.

.. literalinclude:: cookbook/health.py
    :language: python
    :caption: myapp.py

The applications of :mod:`Pyjoyment.Command.Author.generate.app` and
:mod:`Pyjoyment.Command.Author.generate.lite_app` have the plugin already.

A check fails when it raises an exception or returns ``False``, and a
coroutine function or a promise is waited for, with a timeout, so a check can
ask a service that the application cannot work without, without blocking the
server.

.. code-block:: python

    async def search(c):
        tx = await c.ua().get_p('http://search.internal:9200/_cluster/health')
        return tx.res.is_success

    app.health.check('search', search, timeout=2)

Readiness lists the checks, which fail with ``503 Service Unavailable``, and
their reasons go to the log only.

.. code-block:: console

    $ curl -i http://127.0.0.1:3000/readyz
    HTTP/1.1 503 Service Unavailable
    ...
    [+]shutdown ok
    [-]uploads failed: reason withheld
    readyz check failed

Liveness has no checks of the application, as an orchestrator restarts a
container whose liveness fails, and a restart does not bring a database back.
In Kubernetes, the probes go to the port of the container, and the startup
probe gives the application time to start before liveness counts.

.. code-block:: yaml

    spec:
      terminationGracePeriodSeconds: 35
      containers:
        - name: myapp
          image: myapp_image
          env:
            - name: PYJO_SHUTDOWN_DELAY
              value: "5"
          ports:
            - containerPort: 3000
          startupProbe:
            httpGet:
              path: /livez
              port: 3000
            periodSeconds: 1
            failureThreshold: 30
          livenessProbe:
            httpGet:
              path: /livez
              port: 3000
          readinessProbe:
            httpGet:
              path: /readyz
              port: 3000

Until the startup probe passes, the kubelet runs neither the liveness nor the
readiness probe, and the pod gets requests only once readiness passes, which
waits for the checks of the application, as a database that is not up yet.
The server listens before it forks its workers, and a connection waits for a
worker in the backlog of the listen socket.

So does a probe: with workers that serve one connection at a time, as
``prefork -c 1`` for an application that blocks, a liveness probe of HTTP
waits behind the busy workers, and restarts a pod that is only busy. Its
liveness probe connects to the port, which the kernel accepts into the
backlog, as ``--liveness-probe`` of
:mod:`Pyjoyment.Command.Author.generate.kubernetes` makes it.

.. code-block:: yaml

    livenessProbe:
      tcpSocket:
        port: 3000

.. mermaid::

    sequenceDiagram
        participant K as kubelet
        participant M as prefork manager
        participant W as worker
        participant DB as database
        participant EP as EndpointSlice controller
        participant LB as kube-proxy, ingress, load balancer
        K->>M: starts the container
        Note over M: loads the application
        loop startupProbe, every second
            K-xM: GET /livez, connection refused
        end
        Note over M: before_server_start,<br/>listens on the port
        M->>W: forks the workers
        K->>W: GET /livez
        W-->>K: 200 ok
        Note over K: startup passed:<br/>liveness and readiness begin
        K->>W: GET /readyz
        W->>DB: check db
        DB--xW: connection refused
        W-->>K: 503, [-]db failed
        Note over EP: endpoint ready: false,<br/>no requests
        K->>W: GET /readyz
        W->>DB: check db
        DB-->>W: ok
        W-->>K: 200 ok
        K->>EP: pod Ready, through the API server
        EP->>LB: endpoint ready: true
        LB->>W: requests
        loop livenessProbe, every 10 seconds
            K->>W: GET /livez
            W-->>K: 200 ok
        end
        Note over K,W: liveness fails 3 times in a row:<br/>the kubelet restarts the container

Kubernetes sends ``TERM`` to a container that it stops at the same time as it
takes the pod out of the endpoints of its services, and kube-proxy, an ingress
controller or the load balancer of a cloud learn it a moment later. The server
keeps serving after ``TERM`` for
:attr:`~Pyjo.Server.Daemon.Pyjo_Server_Daemon.shutdown_delay`, the 5 seconds
of ``PYJO_SHUTDOWN_DELAY``, until they know, and then closes its listen
sockets, so a new connection that one of them still opens is refused.
``terminationGracePeriodSeconds`` has room for the delay and for the 25
seconds of :attr:`~Pyjo.Server.Prefork.Pyjo_Server_Prefork.graceful_timeout`.
A deployment that keeps the 30 seconds that Kubernetes gives by default
shortens the graceful timeout instead, as ``PYJO_GRACEFUL_TIMEOUT=20`` with
the delay of 5 seconds, which ``--grace-period 30`` of
:mod:`Pyjoyment.Command.Author.generate.kubernetes` sets.
From ``TERM`` on, readiness fails with the check ``shutdown``, so that a load
balancer that checks readiness, as one outside of the cluster, takes the
instance out of its rotation during the delay, and one that keeps its
connections alive sees it with its last response.

.. mermaid::

    sequenceDiagram
        participant API as API server
        participant EP as EndpointSlice controller
        participant LB as kube-proxy, ingress, load balancer
        participant K as kubelet
        participant M as prefork manager
        participant W as worker
        API->>EP: pod deleted
        API->>K: pod deleted
        K->>M: TERM
        M->>W: USR1
        par endpoints
            EP->>LB: endpoint ready: false, terminating: true
            Note over LB: learns it a moment later
        and shutdown_delay
            Note over M,W: shutdown_delay, 5 seconds
            LB->>W: requests until then
            W-->>LB: responses
            LB->>W: GET /readyz
            W-->>LB: 503, [-]shutdown failed
        end
        M->>W: TERM
        Note over M,W: close the listen sockets:<br/>a new connection is refused
        W-->>LB: the next response, Connection: close
        Note over W: the requests in progress finish
        W-->>M: exits, after after_server_stop
        M-->>K: exits with status 0
        Note over M,W: after shutdown_delay and graceful_timeout,<br/>30 seconds, the manager kills the workers
        Note over K,M: after<br/>terminationGracePeriodSeconds,<br/>35 seconds,<br/>the kubelet sends KILL

Cloud Run stops sending requests to an instance before it stops it, and needs
no such delay; its startup probe can wait for readiness, as it sends no
requests to an instance before it passes.

.. code-block:: yaml

    spec:
      template:
        spec:
          containers:
            - image: myapp_image
              startupProbe:
                httpGet:
                  path: /readyz
              livenessProbe:
                httpGet:
                  path: /livez

The ``Dockerfile`` of :mod:`Pyjoyment.Command.Author.generate.dockerfile` has a
``HEALTHCHECK`` that requests the liveness of an application with the plugin,
which ``docker ps`` shows, and which ``depends_on`` of Docker Compose waits
for.

.. code-block:: yaml

    services:
      myapp:
        build: .
      worker:
        build: ./worker
        depends_on:
          myapp:
            condition: service_healthy

Access log
~~~~~~~~~~

The log of the application has the messages of the application, and the
requests only on the level ``trace``, which a log of ``production`` leaves
out. :mod:`Pyjoyment.Plugin.AccessLog` writes the access log of a server of
production, one line for each response, also of the static files and of the
mounted applications, to the standard output, which a container collects, in
the combined format of Apache and nginx, which log analyzers read.

.. code-block:: python

    plugin('AccessLog')

.. code-block:: console

    $ curl http://127.0.0.1:3000/
    ...
    127.0.0.1 - - [06/Nov/2026:09:42:28 +0000] "GET / HTTP/1.1" 200 12 "-" "curl/8.7.1"

The probes of :mod:`Pyjoyment.Plugin.Health` are left out. Behind a reverse
proxy, the client is the one of ``X-Forwarded-For`` with the option ``-p`` of
the server, or of a header that the gateway sets, and a collector of logs, as
the one of Cloud Logging, takes lines of JSON, which ``PYJO_LOG_FORMAT=json``
makes the default, with the request in ``httpRequest``.

.. code-block:: python

    plugin('AccessLog', client='X-Envoy-External-Address', format='json')

Hot deployment
~~~~~~~~~~~~~~

:mod:`Pyjo.Server.Hot` is based on the :mod:`Pyjo.Server.Prefork` web
server, and adds some features especially optimized for high availability
non-containerized production environments. To start applications with it you
can use the ``pyjo-hot`` script, which listens on port ``8080``,
automatically daemonizes the server process and defaults to ``production``
mode for :mod:`Pyjoyment` and :mod:`Pyjoyment.Lite` applications.

.. code-block:: console

    $ pyjo-hot ./myapp.py

The script of a :mod:`Pyjoyment` application is ``MyApp/__main__.py``, which
``pyjo-hot`` starts from the directory of its project.

.. code-block:: console

    $ pyjo-hot ./MyApp/__main__.py

Many configuration settings can be tweaked right from within your application
with :meth:`Pyjo.App.Pyjo_App.config`, for a full list see
:mod:`Pyjo.Server.Hot`.

.. literalinclude:: cookbook/hot.py
    :language: python
    :caption: myapp.py

Or just add a ``hot`` section to your :mod:`Pyjoyment.Plugin.Config`,
:mod:`Pyjoyment.Plugin.JSONConfig`, :mod:`Pyjoyment.Plugin.YAMLConfig`,
:mod:`Pyjoyment.Plugin.TOMLConfig` or :mod:`Pyjoyment.Plugin.INIConfig`
configuration file.

.. code-block:: python
    :caption: myapp.conf

    {
        'hot': {
            'listen': ['https://*:443?cert=/etc/server.crt&key=/etc/server.key'],
            'workers': 10,
        }
    }

But one of its biggest advantages is the support for effortless zero downtime
software upgrades (hot deployment). That means you can upgrade
:mod:`Pyjoyment`, Python or even system libraries at runtime without ever
stopping the server or losing a single incoming connection, just by running
the command above again.

.. code-block:: console

    $ pyjo-hot ./myapp.py
    Starting hot deployment for Hot server 31841.

You might also want to enable proxy support if you're using
:mod:`Pyjo.Server.Hot` behind a reverse proxy. This allows :mod:`Pyjoyment`
to automatically pick up the ``X-Forwarded-For`` and ``X-Forwarded-Proto``
headers.

.. code-block:: python
    :caption: myapp.conf

    {'hot': {'proxy': True}}

To manage :mod:`Pyjo.Server.Hot` with systemd, you can use a unit
configuration file like this.

.. code-block:: ini

    [Unit]
    Description=My Pyjoyment application
    After=network.target

    [Service]
    Type=forking
    User=sri
    PIDFile=/home/sri/myapp/hot.pid
    ExecStart=/path/to/pyjo-hot /home/sri/myapp/myapp.py
    ExecReload=/path/to/pyjo-hot /home/sri/myapp/myapp.py
    KillMode=process

    [Install]
    WantedBy=multi-user.target

Zero downtime software upgrades
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:mod:`Pyjo.Server.Hot` makes zero downtime software upgrades (hot deployment)
very simple, as you can see above, but on modern operating systems that
support the ``SO_REUSEPORT`` socket option, there is also another method
available that works with all built-in web servers.

.. code-block:: console

    $ ./myapp.py prefork -P /tmp/first.pid -l 'http://*:8080?reuse=1'
    Web application available at http://127.0.0.1:8080

All you have to do, is to start a second web server listening to the same
port, and stop the first web server gracefully afterwards.

.. code-block:: console

    $ ./myapp.py prefork -P /tmp/second.pid -l 'http://*:8080?reuse=1'
    Web application available at http://127.0.0.1:8080
    $ kill -s TERM $(cat /tmp/first.pid)

Just remember that both web servers need to be started with the ``reuse``
parameter.

Nginx
~~~~~

One of the most popular setups these days is :mod:`Pyjo.Server.Hot` behind
an `Nginx <https://nginx.org>`__ reverse proxy, which even supports WebSockets
in newer versions.

.. code-block:: nginx

    upstream myapp {
      server 127.0.0.1:8080;
    }
    server {
      listen 80;
      server_name localhost;
      location / {
        proxy_pass http://myapp;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
      }
    }

Apache/mod_proxy
~~~~~~~~~~~~~~~~

Another good reverse proxy is `Apache <https://httpd.apache.org>`_ with
``mod_proxy``, the configuration looks quite similar to the Nginx one above.
And if you need WebSocket support, newer versions come with
``mod_proxy_wstunnel``.

.. code-block:: apache

    <VirtualHost *:80>
      ServerName localhost
      <Proxy *>
        Require all granted
      </Proxy>
      ProxyRequests Off
      ProxyPreserveHost On
      ProxyPass /echo ws://localhost:8080/echo
      ProxyPass / http://localhost:8080/ keepalive=On
      ProxyPassReverse / http://localhost:8080/
      RequestHeader set X-Forwarded-Proto "http"
    </VirtualHost>

Caddy
~~~~~

`Caddy <https://caddyserver.com>`__ is a reverse proxy that needs the least
configuration of them all: it gets a certificate for the domain of the site
on its own, passes WebSockets along, and sets the ``X-Forwarded-For`` and
``X-Forwarded-Proto`` headers by default.

.. code-block:: text
    :caption: Caddyfile

    example.com {
      reverse_proxy 127.0.0.1:8080
    }

Apache/CGI
~~~~~~~~~~

``CGI`` is supported out of the box and your :mod:`Pyjoyment` application
will automatically detect that it is executed as a ``CGI`` script. Its use in
production environments is discouraged though, because as a result of how
``CGI`` works, it is very slow and many web servers are making it
exceptionally hard to configure properly. Additionally, many real-time web
features, such as WebSockets, are not available.

.. code-block:: apache

    ScriptAlias / /home/sri/myapp/myapp.py/

Envoy
~~~~~

:mod:`Pyjoyment` applications can be deployed on cloud-native environments
that use `Envoy <https://www.envoyproxy.io>`_, such as with this reverse proxy
configuration similar to the Apache and Nginx ones above.

.. code-block:: yaml

    static_resources:
      listeners:
      - name: listener_0
        address:
          socket_address: { address: 0.0.0.0, port_value: 80 }
        filter_chains:
        - filters:
          - name: envoy.filters.network.http_connection_manager
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
              codec_type: auto
              stat_prefix: index_http
              route_config:
                name: local_route
                virtual_hosts:
                - name: service
                  domains: ["*"]
                  routes:
                  - match:
                      prefix: "/"
                    route:
                      cluster: local_service
              upgrade_configs:
              - upgrade_type: websocket
              http_filters:
              - name: envoy.filters.http.router
                typed_config:
      clusters:
      - name: local_service
        connect_timeout: 0.25s
        type: strict_dns
        lb_policy: round_robin
        load_assignment:
          cluster_name: local_service
          endpoints:
          - lb_endpoints:
            - endpoint:
                address:
                  socket_address: { address: pyjo, port_value: 8080 }

While this configuration works for simple applications, Envoy's typical use
case is for implementing proxies of applications as a "service mesh"
providing advanced filtering, load balancing, and observability features,
such as seen in `Istio
<https://istio.io/latest/docs/ops/deployment/architecture/>`_. For more
examples, visit the `Envoy documentation
<https://www.envoyproxy.io/docs/envoy/latest/start/start>`_.

.. _cookbook-long-requests:

Long requests
~~~~~~~~~~~~~

A request that waits for a model of language, for a tool of an agent or for
a long job can be silent for minutes before its first byte, and can stream
for minutes after it. Each layer in front of the application has timeouts of
its own, between two reads or for the whole response, and the shortest one
ends the request, with an error that the application never sees.

The application gives such a route timeouts of its own with the values
``inactivity_timeout``, ``request_timeout`` and ``heartbeat`` of its stash,
as :doc:`routing` describes: a longer inactivity timeout of the connection,
the most time to the end of the response, after which the request gets a
``504``, and a comment of Server-Sent Events or a ping of a WebSocket while
the stream waits, more often than the shortest idle timeout in front of it.
An action that is a coroutine function is cancelled when its connection
closes before its response ends, as when a proxy in front of it gives up,
with the requests of :mod:`Pyjo.UserAgent` that it waits for. A
``request_timeout`` below the timeout of the whole response of a layer in
front of the application ends the request with the ``504`` of the
application, which it logs, rather than with an error of that layer.

* nginx waits ``proxy_read_timeout`` between two reads from the
  application, 60 seconds by default, and buffers the response, which holds
  back a stream of events until ``proxy_buffering off`` or the header
  ``X-Accel-Buffering: no`` of the response; ingress-nginx of Kubernetes has
  them as the annotations ``nginx.ingress.kubernetes.io/proxy-read-timeout``
  and ``nginx.ingress.kubernetes.io/proxy-buffering``.

  .. code-block:: nginx

      location / {
        proxy_pass http://myapp;
        proxy_read_timeout 600s;
        proxy_buffering off;
      }

* Caddy passes a stream of ``text/event-stream`` on at once, and waits for
  the headers of the response as long as ``response_header_timeout`` of its
  ``transport http``.
* The Application Load Balancer of AWS closes a connection that is idle for
  its idle timeout, 60 seconds by default, which a heartbeat keeps from it,
  and CloudFront waits its origin response timeout for the first byte and
  between two reads, 30 seconds by default.
* The Application Load Balancer of Google Cloud waits the timeout of its
  backend service, 30 seconds by default, for the whole response of HTTP,
  also of a stream of events, which a heartbeat does not extend, and for a
  WebSocket that is idle.
* Cloud Run ends a request after the request timeout of the service, 5
  minutes by default, which ``gcloud run deploy --timeout`` changes, also
  for a stream of events and a WebSocket.
* Kubernetes has no timeouts of its own for the requests of a Service; the
  Ingress controller in front of it, or a route of the Gateway API, with
  ``timeouts.request`` and ``timeouts.backendRequest`` of an HTTPRoute, has
  them.
* Amazon API Gateway ends a request after the timeout of its integration,
  and passes a stream on only with the response transfer mode ``STREAM`` of
  a REST API, with the limits of its documentation.
* AWS Lambda ends an invocation after the timeout of the function, 3
  seconds by default and 15 minutes at most, and streams a response with
  ``PYJO_LAMBDA_INVOKE_MODE=RESPONSE_STREAM``, as :ref:`cookbook-aws-lambda`
  describes, whose ``request_timeout`` below the timeout of the function
  gives the client a ``504`` of the application.

FastCGI
~~~~~~~

`FastCGI <https://fastcgi-archives.github.io/FastCGI_Specification.html>`__
is the protocol of web servers that are not reverse proxies of HTTP, or are
configured as such, and all built-in web servers speak it on the listen
locations ``fcgi://`` and ``fcgi+unix://``, see :mod:`Pyjo.Server.FastCGI`.
The web server speaks HTTP to the clients, so WebSockets are not available.

.. code-block:: console

    $ ./myapp.py prefork -m production -l fcgi+unix://%2Ftmp%2Fmyapp.sock

The web server only has to send the requests to that socket, as nginx does
with this configuration.

.. code-block:: nginx

    server {
      listen 80;
      server_name localhost;
      location / {
        include fastcgi_params;
        fastcgi_pass unix:/tmp/myapp.sock;
        fastcgi_keep_conn on;
      }
    }

Some web servers, as Apache with ``mod_fcgid`` and lighttpd, start the
FastCGI application themselves, which the command
:mod:`Pyjoyment.Command.fastcgi` detects, so the script of the application
needs no command.

.. code-block:: apache

    <VirtualHost *:80>
      ServerName localhost
      ScriptAlias / /home/sri/myapp/myapp.py/
      <Directory /home/sri/myapp>
        SetHandler fcgid-script
        Options +ExecCGI
        Require all granted
      </Directory>
    </VirtualHost>

WSGI and ASGI
~~~~~~~~~~~~~

`WSGI <https://peps.python.org/pep-3333/>`_ is an interface between Python
web frameworks and web servers, and `ASGI <https://asgi.readthedocs.io>`_ is
its asynchronous successor, with WebSockets. :mod:`Pyjoyment` applications
are ridiculously simple to deploy on their servers, with
:mod:`Pyjo.Server.WSGI` and :mod:`Pyjo.Server.ASGI`, but be aware that with
WSGI many real-time web features, such as WebSockets, are not available. The
script of the application ends with ``application = app.start()``, which
gives a server the application, when the ``PYJO_WSGI`` or ``PYJO_ASGI``
environment variable is set.

.. code-block:: console

    $ PYJO_WSGI=1 gunicorn myapp:application
    $ PYJO_ASGI=1 uvicorn myapp:application

The ``PYJO_REVERSE_PROXY`` environment variable can be used to enable proxy
support, this allows :mod:`Pyjoyment` to automatically pick up the
``X-Forwarded-For`` and ``X-Forwarded-Proto`` headers.

.. code-block:: console

    $ PYJO_REVERSE_PROXY=1 PYJO_WSGI=1 gunicorn myapp:application

If a server is unable to correctly detect the application home directory, you
can simply use the ``PYJO_HOME`` environment variable.

.. code-block:: console

    $ PYJO_HOME=/home/sri/myapp PYJO_WSGI=1 gunicorn myapp:application

There is no need for a separate file of the application for the server, just
point the server at your application script, it will automatically act like
one if it detects the presence of the ``PYJO_WSGI`` or ``PYJO_ASGI``
environment variable.

WSGI middleware
~~~~~~~~~~~~~~~

Wrapper scripts like ``myapp_wsgi.py`` are a great way to separate deployment
and application logic. :mod:`Pyjo.Server.WSGI` can be used directly to load
and customize applications in the wrapper script.

.. literalinclude:: cookbook/wsgi/myapp_wsgi.py
    :language: python
    :caption: myapp_wsgi.py

.. code-block:: console

    $ gunicorn myapp_wsgi:application

But you could even use middleware right in your application, which starts
the command :mod:`Pyjoyment.Command.wsgi` for it.

.. literalinclude:: cookbook/wsgi/welcome.py
    :language: python
    :caption: myapp.py

.. _cookbook-aws-lambda:

AWS Lambda
~~~~~~~~~~

An application runs as an event function of `AWS Lambda
<https://aws.amazon.com/lambda/>`_, whose handler answers the events of API
Gateway, Function URLs and Application Load Balancers, with
:mod:`Pyjo.Server.Lambda`. The script of the application ends with
``handler = app.start()``, which gives the runtime of Lambda its handler,
``myapp.handler``, as it detects the ``AWS_LAMBDA_RUNTIME_API`` environment
variable, which Lambda sets.

.. literalinclude:: cookbook/lambda/myapp.py
    :language: python
    :caption: myapp.py

On a custom runtime, as ``provided.al2023``, or in an image, the ``bootstrap``
of the function runs it with the runtime client of :mod:`Pyjo.Server.Lambda`,
which needs no other library, or runs the script itself, which is the runtime
when it is the main program, as :mod:`Pyjoyment.Command.lambda` detects.

.. code-block:: sh

    #!/bin/sh
    exec python3 -m Pyjo.Server.Lambda

.. code-block:: sh

    #!/bin/sh
    exec python3 "$LAMBDA_TASK_ROOT/myapp.py"

An image of the function, of any Python, has the same command, which
:mod:`Pyjoyment.Command.Author.generate.dockerfile` writes with
``--target lambda``.

.. code-block:: console

    $ ./myapp.py generate dockerfile --target lambda

A ZIP of the function for ``provided.al2023`` brings the Python of its
``bootstrap`` in a layer, of any version, also the free-threaded build, which
:mod:`Pyjoyment.Command.Author.generate.lambda_zip` writes with uv to ``dist``:
``python.zip``, the layer, ``pyjoyment.zip``, a layer with Pyjoyment, and
``function.zip``, the application with its other dependencies and the
``bootstrap`` that runs it with the Python of the layer.

.. code-block:: console

    $ ./myapp.py generate lambda-zip --arch arm64

With ``--runtime python3.14``, the function runs on the runtime of Python of
Lambda, with its handler, as ``myapp.handler``, and the same layer of
Pyjoyment, which the functions of the same Python share, so that a layer of
Pyjoyment that is published already serves in its place.

.. code-block:: console

    $ ./myapp.py generate lambda-zip --arch arm64 --runtime python3.14

`Pyjoyment-Lambda-Layers
<https://github.com/pyjoyment/Pyjoyment-Lambda-Layers>`_ publishes such
layers, built by the same generator, as public layers of the account
``959435416781`` in the commercial regions of AWS: of Python, as
``python3_14-arm64`` or ``python3_15t-x86_64``, of one version and one
architecture, for ``provided.al2023``, and of Pyjoyment, as
``pyjoyment-python3_14``, for both architectures, with the layer of Python or
on the runtime ``python3.14``. With ``--function-only``, the generator writes
``function.zip`` alone, for them, and tells the version of Pyjoyment of the
dependencies of the application, which the description of the layer of
Pyjoyment says too. The layer of Pyjoyment has `Pyjo-AWS
<https://github.com/pyjoyment/Pyjo-AWS>`_ too, which
``--layer-package Pyjo-AWS`` leaves out of the function of an application
that depends on it, as the layer gives it; another distribution of the
namespace ``Pyjo``, as ``Pyjo-MCP``, stays in the function.

.. code-block:: console

    $ ./myapp.py generate lambda-zip --arch arm64 --function-only
      [layer] Pyjoyment 0.1.0 for Python 3.14
      [write] /home/sri/myapp/dist/function.zip
    $ ./myapp.py generate lambda-zip --arch arm64 --function-only --layer-package Pyjo-AWS
      [layer] Pyjoyment 0.1.0 for Python 3.14
      [layer] Pyjo-AWS 0.1.0 for Python 3.14
      [write] /home/sri/myapp/dist/function.zip

A function takes a layer by the ARN of a version, as
``arn:aws:lambda:<region>:959435416781:layer:pyjoyment-python3_14:<version>``,
which the index of the layers of each release, ``layers.json``, gives as
``{layer: {region: arn}}``. The index of the latest release is always at the
same URL, which a one-liner reads with a JSON Pointer.

.. code-block:: console

    $ python -m Pyjo 'g("https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json").json("/pyjoyment-python3_14/eu-central-1")'

The directories `examples/lambda
<https://github.com/pyjoyment/Pyjoyment/tree/main/examples/lambda>`_ and
`examples/lambda_zip
<https://github.com/pyjoyment/Pyjoyment/tree/main/examples/lambda_zip>`_ of the
repository deploy such functions with OpenTofu.

The same function runs locally, mounted in an application with
:mod:`Pyjo.App.Lambda`, in a process of its own, which gets its invocations
through the Runtime API of Lambda, as on AWS, and with the path of the mount as
the stage of API Gateway.

.. literalinclude:: cookbook/lambda/gateway.py
    :language: python
    :caption: gateway.py

So it is tried live with the built-in web server, and tested with
:mod:`Pyjo.Test.Pyjo`, before it goes to AWS.

.. code-block:: console

    $ ./gateway.py daemon
    $ curl http://127.0.0.1:3000/myapp
    Hello Lambda at /myapp!

.. code-block:: python

    t = Pyjo.Test.Pyjo.new('gateway.py')
    t.get_ok('/myapp').status_is(200).content_is('Hello Lambda at /myapp!')

A Function URL with the invoke mode ``RESPONSE_STREAM``, or a REST API of API
Gateway with the response transfer mode ``STREAM``, streams the responses of
the function as they are written, as the tokens of a model or a long download
need. The runtime of Python of Lambda does not stream, so the runtime client of
:mod:`Pyjo.Server.Lambda` runs the function: with the ``bootstrap`` of a custom
runtime above, or on the runtime of Python with a wrapper that
``AWS_LAMBDA_EXEC_WRAPPER`` names, as ``/var/task/wrapper.py``. The function
does not learn the invoke mode from its invocations, so
``PYJO_LAMBDA_INVOKE_MODE=RESPONSE_STREAM`` tells it, the same as the one of the
Function URL. The runtime puts the layers in the path of Python only for its own
runtime client, so a function whose Pyjoyment is in a layer names its
site-packages for the wrapper, as
``PYTHONPATH=/opt/python/lib/python3.14/site-packages``.

.. literalinclude:: ../../examples/lambda_stream/function/wrapper.py
    :language: python
    :caption: wrapper.py

:mod:`Pyjo.App.Lambda` streams the function locally the same way, with
``PYJO_LAMBDA_INVOKE_MODE`` in its attribute ``env``, and the directory
`examples/lambda_stream
<https://github.com/pyjoyment/Pyjoyment/tree/main/examples/lambda_stream>`_ of the
repository deploys such a function with OpenTofu.

Standard input and output
~~~~~~~~~~~~~~~~~~~~~~~~~

An application serves a protocol on the standard input and output too, with
the command :mod:`Pyjoyment.Command.stdio`, as a local server of MCP or of
the Language Server Protocol that another program starts, or a protocol of
lines that inetd or systemd serves. The application gives the protocol with a
subscriber of the event ``stream`` of :mod:`Pyjo.Server.Stdio`, in the hook
``before_server_start``, so that it still serves its routes with the other
servers, and :mod:`Pyjo.IOLoop.Messages` turns the stream into messages, as
lines.

.. literalinclude:: cookbook/stdio/lines.py
    :language: python
    :caption: lines.py

The standard output belongs to the protocol, so what the application prints
goes to the standard error, with its log.

.. code-block:: console

    $ printf 'hello\nworld\n' | ./lines.py stdio
    Got hello
    Got world
    HELLO
    WORLD

The server ends once the standard input has ended and the rest of the output
is written, or on ``INT`` and ``TERM``, which end the standard input as its
end does. :meth:`~Pyjo.JSON.RPC.Pyjo_JSON_RPC.serve` of :mod:`Pyjo.JSON.RPC`
serves JSON-RPC on the messages, with one message on each line, as the
transport stdio of MCP has them, answers the requests at the same time, and
ends the stream once the requests in progress have their responses.

.. literalinclude:: cookbook/stdio/rpc.py
    :language: python
    :caption: rpc.py

.. code-block:: console

    $ echo '{"jsonrpc":"2.0","method":"divide","params":[7,2],"id":1}' | ./rpc.py stdio
    {"jsonrpc":"2.0","result":3.5,"id":1}

The client of such a server starts it as a child process with
:mod:`Pyjo.IOLoop.ChildProcess`, whose standard output and input are a stream
of messages, which ``serve`` makes a client of, and whose standard input it
closes to end the server.

.. literalinclude:: cookbook/stdio/client.py
    :language: python
    :caption: client.py

.. code-block:: console

    $ python client.py
    3.5

Rewriting
~~~~~~~~~

Sometimes you might have to deploy your application in a blackbox environment
where you can't just change the server configuration or behind a reverse
proxy that passes along additional information with ``X-Forwarded-*``
headers. In such cases you can use the hook ``before_dispatch`` of
:meth:`Pyjoyment.Pyjoyment_App.hook` to rewrite incoming requests.

.. code-block:: python

    # Change scheme if "X-Forwarded-HTTPS" header is set
    @app.hook('before_dispatch')
    def https(c):
        if c.req.headers.header('X-Forwarded-HTTPS'):
            c.req.url.base.scheme = 'https'

Since reverse proxies generally don't pass along information about path
prefixes your application might be deployed under, rewriting the base path of
incoming requests is also quite common. This allows
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.url_for` for example, to
generate portable URLs based on the current environment.

.. code-block:: python

    # Move first part and slash from path to base path in production mode
    if app.mode == 'production':

        @app.hook('before_dispatch')
        def prefix(c):
            base, path = c.req.url.base.path, c.req.url.path
            base.trailing_slash, path.leading_slash = True, False
            base.parts.append(path.parts.pop(0))

:mod:`Pyjo.URL` objects are very easy to manipulate, just make sure that the
URL (``foo/bar?baz=yada``), which represents the routing destination, is
always relative to the base URL (``http://example.com/myapp/``), which
represents the deployment location of your application.

Deployment specific plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deployment specific 3rd party plugins, such as one that would switch the user
and group of the server, ``SetUserGroup``, do not need to be included in your
application code. They can also be loaded later on via the reserved
``plugins`` value for :mod:`Pyjoyment` applications that are using any one of
the built-in configuration plugins :mod:`Pyjoyment.Plugin.Config`,
:mod:`Pyjoyment.Plugin.JSONConfig`, :mod:`Pyjoyment.Plugin.YAMLConfig`,
:mod:`Pyjoyment.Plugin.TOMLConfig` or :mod:`Pyjoyment.Plugin.INIConfig`.

.. code-block:: python
    :caption: myapp.conf

    {
        'plugins': [
            {'SetUserGroup': {'user': 'sri', 'group': 'staff'}},
        ]
    }

Application embedding
~~~~~~~~~~~~~~~~~~~~~

From time to time you might want to reuse parts of :mod:`Pyjoyment`
applications like configuration files, database connection or helpers for
other scripts, with this little :mod:`Pyjo.Server` based mock server you can
just embed them.

.. code-block:: python

    import Pyjo.Server

    # Load application with mock server
    server = Pyjo.Server.new()
    app = server.load_app('./myapp.py')

    # Access fully initialized application
    print(*app.static.paths, sep='\n')
    print(app.config('secret_identity'))
    print(app.dumper({'just': 'a helper test'}))
    print(app.build_controller().render_to_string(template='foo'))

The plugin :mod:`Pyjoyment.Plugin.Mount` uses this functionality to allow you
to combine multiple applications into one and deploy them together.

.. code-block:: python

    from Pyjoyment.Lite import *

    app.config(hot={'listen': ['http://*:80']})

    plugin('Mount', {'test1.example.com': '/home/sri/myapp1.py'})
    plugin('Mount', {'test2.example.com': '/home/sri/myapp2.py'})

    app.start()

Web server embedding
~~~~~~~~~~~~~~~~~~~~

You can also use :meth:`Pyjo.IOLoop.Pyjo_IOLoop.one_tick` to embed the
built-in web server :mod:`Pyjo.Server.Daemon` into alien environments like
foreign event loops that for some reason can't just be integrated with a new
reactor backend.

.. code-block:: python

    import Pyjo.IOLoop
    import Pyjo.Server.Daemon

    from Pyjoyment.Lite import *

    # Normal action
    get('/', {'text': 'Hello World!'})

    # Connect application with web server and start accepting connections
    daemon = Pyjo.Server.Daemon.new(app=app, listen=['http://*:8080'])
    daemon.start()

    # Call "one_tick" repeatedly from the alien environment
    while True:
        Pyjo.IOLoop.one_tick()

.. _cookbook-real-time-web:

Real-time web
-------------

The real-time web is a collection of technologies that include Comet (long
polling), EventSource and WebSockets, which allow content to be pushed to
consumers with long-lived connections as soon as it is generated, instead of
relying on the more traditional pull model. All built-in web servers use
non-blocking I/O and are based on the :mod:`Pyjo.IOLoop` event loop, which
provides many very powerful features that allow real-time web applications to
scale up to thousands of concurrent client connections.

Backend web services
~~~~~~~~~~~~~~~~~~~~

Since :mod:`Pyjo.UserAgent` is also based on the :mod:`Pyjo.IOLoop` event
loop, it won't block the built-in web servers when used non-blocking, even for
high latency backend web services.

.. literalinclude:: cookbook/backend.py
    :language: python
    :caption: myapp.py

The callback passed to :meth:`Pyjo.UserAgent.Pyjo_UserAgent.get` will be
executed once the request to the backend web service has been finished, this
is called continuation-passing style.

Synchronizing non-blocking operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multiple non-blocking operations, such as concurrent requests, can be easily
synchronized with promises and :meth:`Pyjo.Promise.Pyjo_Promise.all`. You
create :mod:`Pyjo.Promise` objects manually or use methods like ``get_p`` of
:mod:`Pyjo.UserAgent` that create them for you.

.. literalinclude:: cookbook/synchronizing.py
    :language: python
    :caption: myapp.py

To create promises manually you just wrap your continuation-passing style APIs
in functions that return promises. Here's an example for how ``get_p`` of
:mod:`Pyjo.UserAgent` works internally.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.UserAgent

    # Wrap a user agent method with a promise
    ua = Pyjo.UserAgent.new()


    def get_p(*args):
        promise = Pyjo.Promise.new()

        def done(ua, tx):
            err = tx.error
            if not err or err.get('code'):
                promise.resolve(tx)
            promise.reject(err['message'] if err else None)

        ua.get(*args, done)
        return promise


    # Use our new promise generating function
    get_p('https://pyjoyment.readthedocs.io').then(lambda tx: print(tx.result.dom().at('title').text)).wait()

Promises have three states, they start out as ``pending`` and you call
:meth:`Pyjo.Promise.Pyjo_Promise.resolve` to transition them to
``fulfilled``, or :meth:`Pyjo.Promise.Pyjo_Promise.reject` to transition
them to ``rejected``.

async/await
~~~~~~~~~~~

And Python has the ``async`` and ``await`` keywords built right in, which
make using promises even easier, and make the use of closures with promises
completely optional.

The ``async`` keyword is placed before the ``def`` keyword, and with the
decorator :func:`Pyjo.Promise.coroutine` means that this function always
returns a promise. Returned values that are not :mod:`Pyjo.Promise` objects
will be wrapped in a resolved promise automatically. And if an exception gets
raised in the function it will result in a rejected promise.

.. code-block:: python

    import Pyjo.Promise


    @Pyjo.Promise.coroutine
    async def hello_p():
        return 'Hello Pyjo!'


    hello_p().then(print).wait()

The ``await`` keyword on the other hand makes Python wait for the promise to
be settled. It then returns the fulfillment values or raises an exception with
the rejection reason. While waiting, the event loop is free to perform other
tasks however, so no resources are wasted.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.URL
    import Pyjo.UserAgent

    ua = Pyjo.UserAgent.new()


    # Search GitHub non-blocking for multiple terms sequentially
    @Pyjo.Promise.coroutine
    async def search_github_p(terms):
        github = Pyjo.URL.new('https://api.github.com/search/repositories')
        urls = [github.clone().set(query={'q': term}) for term in terms]

        for url in urls:
            tx = await ua.get_p(url)
            print(tx.result.json('/items/0/full_name'))


    search_github_p(['pyjoyment', 'mojolicious']).wait()

The loop above performs all requests sequentially, awaiting a result before
sending the next request. But you can also perform those requests
concurrently instead, by using methods like
:meth:`Pyjo.Promise.Pyjo_Promise.all` to combine multiple promises before
awaiting the results.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.URL
    import Pyjo.UserAgent

    ua = Pyjo.UserAgent.new()


    # Search GitHub non-blocking for multiple terms concurrently
    @Pyjo.Promise.coroutine
    async def search_github_p(terms):
        github = Pyjo.URL.new('https://api.github.com/search/repositories')
        urls = [github.clone().set(query={'q': term}) for term in terms]

        promises = [ua.get_p(url) for url in urls]
        results = await Pyjo.Promise.all(*promises)
        for result in results:
            print(result[0].result.json('/items/0/full_name'))


    search_github_p(['pyjoyment', 'mojolicious']).wait()

All of this also means that you can use normal Python exception handling
again.

.. code-block:: python

    import Pyjo.Promise

    from Pyjo.Util import warn


    # Catch a non-blocking exception
    @Pyjo.Promise.coroutine
    async def hello_p():
        try:
            await Pyjo.Promise.reject('This is an exception')
        except Exception as err:
            warn(f'Error: {err}')


    hello_p().wait()

And it works just the same in :mod:`Pyjoyment` and :mod:`Pyjoyment.Lite`
applications. Just declare your actions with the ``async`` keyword and use
``await`` to wait for promises to be ``fulfilled`` or ``rejected``.

.. literalinclude:: cookbook/titles.py
    :language: python
    :caption: myapp.py

Promises returned by actions will automatically get the default
:mod:`Pyjoyment` exception handler attached. Making it much harder to ever
miss a non-blocking exception again, even if you forgot to handle it yourself.

An action that is a coroutine function is cancelled where it waits when its
connection closes before its response ends, as when the client goes away or
the inactivity timeout of the connection passes. It gets the exception of the
cancellation of the reactor, :class:`asyncio.CancelledError` of the default
one, which ``except Exception`` does not catch, so that its ``finally``
blocks run, and the request of :mod:`Pyjo.UserAgent` that it waits for closes
its connection, so that a request to a slow service, as a model of language,
whose answer nobody reads anymore, stops too. An action that has rendered its
response goes on to its end.

Timers
~~~~~~

Timers, another primary feature of the event loop, are created with
:meth:`Pyjo.IOLoop.Pyjo_IOLoop.timer` and can, for example, be used to delay
rendering of a response, and unlike :func:`time.sleep`, won't block any other
requests that might be processed concurrently.

.. literalinclude:: cookbook/delayed.py
    :language: python
    :caption: myapp.py

Recurring timers created with :meth:`Pyjo.IOLoop.Pyjo_IOLoop.recurring` are
slightly more powerful, but need to be stopped manually, or they would just
keep getting emitted.

.. literalinclude:: cookbook/counter.py
    :language: python
    :caption: myapp.py

Timers are not tied to a specific request or connection, and can even be
created at startup time.

.. literalinclude:: cookbook/background.py
    :language: python
    :caption: myapp.py

Just remember that all these non-blocking operations are processed
cooperatively, so your callbacks shouldn't block for too long.

Subprocesses
~~~~~~~~~~~~

You can also use subprocesses, created with
:meth:`Pyjo.IOLoop.Pyjo_IOLoop.subprocess`, to perform computationally
expensive operations without blocking the event loop.

.. literalinclude:: cookbook/blocking.py
    :language: python
    :caption: myapp.py

The callback passed to :meth:`Pyjo.IOLoop.Subprocess.Pyjo_IOLoop_Subprocess.run_p`
will be executed in a child process, without blocking the event loop of the
parent process. The results of the callback will then be shared between both
processes, and the promise fulfilled or rejected in the parent process.

Child processes
~~~~~~~~~~~~~~~

A program, as a command line tool, runs in a child process too, with
:meth:`Pyjo.IOLoop.Pyjo_IOLoop.spawn`, which gives a
:mod:`Pyjo.IOLoop.ChildProcess` object, as ``child_process`` of Node.js does.
Its standard input, output and error are streams of the event loop, so that
the program gets the body of the request and the client gets its output as it
comes, without blocking the event loop.

.. literalinclude:: cookbook/sort.py
    :language: python
    :caption: myapp.py

.. code-block:: sh

    $ curl --data-binary $'b\na\n' http://localhost:3000/sort
    a
    b

The event ``spawn`` comes once the program runs, ``close`` once it has
exited and its output has ended, with its exit code, and ``error`` if it
cannot run. ``stop`` and ``start`` of the stream of its output pause and
resume reading it, as for a slow client, and
:meth:`~Pyjo.IOLoop.ChildProcess.Pyjo_IOLoop_ChildProcess.kill` ends it early,
with the programs that it starts when it runs ``detached``, in a process group
of its own.

:meth:`~Pyjo.IOLoop.ChildProcess.Pyjo_IOLoop_ChildProcess.run_p` gives its exit
code, its output and its error at once, as a promise, which a coroutine awaits.

.. code-block:: python

    @get('/system')
    async def system(c):
        code, out, err = await Pyjo.IOLoop.ChildProcess.new().run_p(['uname', '-s'])
        c.render(text=out.strip().decode())

Exceptions in non-blocking operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since timers and other non-blocking operations are running solely in the
event loop, outside of the application, exceptions that get raised in
callbacks can't get caught and handled automatically. But you can handle them
manually by subscribing to the event ``error`` of :mod:`Pyjo.Reactor` or
catching them inside the callback.

.. literalinclude:: cookbook/errors.py
    :language: python
    :caption: myapp.py

A default subscriber that turns all errors into warnings will usually be added
by :mod:`Pyjo.IOLoop` as a fallback.

.. code-block:: python

    Pyjo.IOLoop.singleton.reactor.unsubscribe('error')

During development or for applications where crashing is simply preferable,
you can also make every exception that gets raised in a callback fatal by
removing all of its subscribers.

WebSocket web service
~~~~~~~~~~~~~~~~~~~~~

The WebSocket protocol offers full bi-directional low-latency communication
channels between clients and servers. Receive messages just by subscribing to
events such as ``message`` of :mod:`Pyjo.Transaction.WebSocket` with
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.on` and return them with
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.send`.

.. literalinclude:: cookbook/echo.py
    :language: python
    :caption: myapp.py

The event ``finish`` of :mod:`Pyjo.Transaction.WebSocket` will be emitted
right after the WebSocket connection has been closed.

.. code-block:: python

    c.tx.with_compression()

You can activate ``permessage-deflate`` compression with
:meth:`Pyjo.Transaction.WebSocket.Pyjo_Transaction_WebSocket.with_compression`,
this can result in much better performance, but also increases memory usage by
up to 300KiB per connection.

.. code-block:: python

    proto = c.tx.with_protocols('v2.proto', 'v1.proto')

You can also use
:meth:`Pyjo.Transaction.WebSocket.Pyjo_Transaction_WebSocket.with_protocols`
to negotiate a subprotocol.

Server-Sent Events web service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Server-Sent Events (SSE) is a special form of long polling where you can use
:meth:`Pyjoyment.Controller.Pyjoyment_Controller.write_sse` to directly send
DOM events from servers to clients. It is uni-directional, that means you will
have to use Ajax requests for sending data from clients to servers, the
advantage however is low infrastructure requirements, since it reuses the HTTP
protocol for transport.

.. literalinclude:: cookbook/livelog.py
    :language: python
    :caption: myapp.py

The event ``message`` of :mod:`Pyjo.Log` will be emitted for every new log
message and the event ``finish`` of :mod:`Pyjo.Transaction` right after the
transaction has been finished.

Streaming multipart uploads
~~~~~~~~~~~~~~~~~~~~~~~~~~~

:mod:`Pyjoyment` contains a very sophisticated event system based on
:mod:`Pyjo.EventEmitter`, with ready-to-use events on almost all layers, and
which can be combined to solve some of the hardest problems in web
development.

.. literalinclude:: cookbook/upload.py
    :language: python
    :caption: myapp.py

More event loops
~~~~~~~~~~~~~~~~

Internally, the :mod:`Pyjo.IOLoop` event loop can use multiple reactor
backends, :mod:`Pyjo.Reactor.Asyncio`, the default one, runs on the event loop
of :mod:`asyncio`. Which in turn allows the coroutines of :mod:`asyncio` and
the libraries built on it to just work.

.. literalinclude:: cookbook/sleepy.py
    :language: python
    :caption: myapp.py

.. _cookbook-user-agent:

User agent
----------

When we say :mod:`Pyjoyment` is a web framework we actually mean it, with
:mod:`Pyjo.UserAgent` there's a full featured HTTP and WebSocket user agent
built right in.

REST web services
~~~~~~~~~~~~~~~~~

Requests can be performed very comfortably with methods like
:meth:`Pyjo.UserAgent.Pyjo_UserAgent.get`, and always result in a
:mod:`Pyjo.Transaction.HTTP` object, which has many useful attributes and
methods. You can check for connection errors with
:attr:`Pyjo.Transaction.Pyjo_Transaction.result`, or access HTTP request and
response information directly through
:attr:`Pyjo.Transaction.Pyjo_Transaction.req` and
:attr:`Pyjo.Transaction.Pyjo_Transaction.res`.

.. code-block:: python

    import Pyjo.UserAgent

    # Request a resource and make sure there were no connection errors
    ua = Pyjo.UserAgent.new()
    tx = ua.get('https://pyjoyment.readthedocs.io/en/latest/api/Pyjo.html', {'Accept': 'text/plain'})
    res = tx.result

    # Decide what to do with its representation
    if res.is_success:
        print(res.text)
    elif res.is_error:
        print(res.message)
    elif res.code == 301:
        print(res.headers.location)
    else:
        print('Whatever...')

While methods like
:attr:`Pyjo.Message.Response.Pyjo_Message_Response.is_success` and
:attr:`Pyjo.Message.Response.Pyjo_Message_Response.is_error` serve as
building blocks for more sophisticated REST clients.

Web scraping
~~~~~~~~~~~~

Scraping information from websites has never been this much fun before. The
built-in HTML/XML parser :mod:`Pyjo.DOM` is accessible through
:meth:`Pyjo.Message.Pyjo_Message.dom` and supports all CSS selectors that make
sense for a standalone parser, it can be a very powerful tool especially for
testing web application.

.. code-block:: python

    import Pyjo.UserAgent

    # Fetch website
    ua = Pyjo.UserAgent.new()
    res = ua.get('https://pyjoyment.readthedocs.io').result

    # Extract title
    print('Title:', res.dom().at('head > title').text)

    # Extract headings
    res.dom('h1, h2, h3').each(lambda dom, i: print('Heading:', dom.all_text))

    # Visit all nodes recursively to extract more than just text
    for n in res.dom().descendant_nodes:
        # Text or CDATA node
        if n.type == 'text' or n.type == 'cdata':
            print(n.content, end='')

        # Also include alternate text for images
        if n.type == 'tag' and n.tag == 'img':
            print(n['alt'] or '', end='')

For a full list of available CSS selectors see :mod:`Pyjo.DOM.CSS`.

JSON web services
~~~~~~~~~~~~~~~~~

Most web services these days are based on the JSON data-interchange format.
That's why :mod:`Pyjoyment` comes with :mod:`Pyjo.JSON` built right in, which
is accessible through :meth:`Pyjo.Message.Pyjo_Message.json`.

.. code-block:: python

    import Pyjo.URL
    import Pyjo.UserAgent

    # Fresh user agent
    ua = Pyjo.UserAgent.new()

    # Search GitHub for "pyjoyment" and list recently updated repositories
    url = Pyjo.URL.new('https://api.github.com/search/repositories')
    url.query = {'q': 'pyjoyment', 'sort': 'updated'}
    for item in ua.get(url).result.json('/items'):
        print(f"{item['full_name']} ({item['owner']['login']})")

Basic authentication
~~~~~~~~~~~~~~~~~~~~

You can just add username and password to the URL, an ``Authorization``
header will be automatically generated.

.. code-block:: python

    import Pyjo.UserAgent

    ua = Pyjo.UserAgent.new()
    print(ua.get('https://sri:secret@example.com/hideout').result.text)

If you're using :mod:`Pyjo.URL` to build the URL, be aware that the userinfo
part will not be included if the object is stringified. You'll have to pass
the object itself to :mod:`Pyjo.UserAgent` or use
:meth:`Pyjo.URL.Pyjo_URL.to_unsafe_str`.

.. code-block:: python

    import Pyjo.URL
    import Pyjo.UserAgent

    ua = Pyjo.UserAgent.new()
    url = Pyjo.URL.new('https://example.com/hideout').set(userinfo='sri:secret')
    print(ua.get(url).result.text)

Decorating follow-up requests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:mod:`Pyjo.UserAgent` can automatically follow redirects, the event ``start``
of :mod:`Pyjo.UserAgent` allows you direct access to each transaction right
after they have been initialized and before a connection gets associated with
them.

.. code-block:: python

    import Pyjo.UserAgent

    # User agent following up to 10 redirects
    ua = Pyjo.UserAgent.new(max_redirects=10)


    # Add a witty header to every request
    @ua.on('start')
    def start(ua, tx):
        tx.req.headers.header('X-Bender', 'Bite my shiny metal ass!')
        print('Request:', tx.req.url.clone().to_abs())


    # Request that will most likely get redirected
    print('Title:', ua.get('google.com').result.dom().at('head > title').text)

This even works for proxy ``CONNECT`` requests.

Content generators
~~~~~~~~~~~~~~~~~~

Content generators can be registered with
:meth:`Pyjo.UserAgent.Transactor.Pyjo_UserAgent_Transactor.add_generator` to
generate the same type of content repeatedly for multiple requests.

.. code-block:: python

    import Pyjo.Asset.File
    import Pyjo.UserAgent

    # Add "stream" generator
    ua = Pyjo.UserAgent.new()


    def stream(transactor, tx, path):
        tx.req.content.asset = Pyjo.Asset.File.new(path=path)


    ua.transactor.add_generator('stream', stream)

    # Send multiple files streaming via PUT and POST
    ua.put('http://example.com/upload', stream='/home/sri/pyjo.png')
    ua.post('http://example.com/upload', stream='/home/sri/minion.png')

The ``json``, ``form`` and ``multipart`` content generators are always
available.

.. code-block:: python

    import Pyjo.UserAgent

    # Send "application/json" content via PATCH
    ua = Pyjo.UserAgent.new()
    tx = ua.patch('http://api.example.com', json={'foo': 'bar'})

    # Send query parameters via GET
    tx2 = ua.get('search.example.com', form={'q': 'test'})

    # Send "application/x-www-form-urlencoded" content via POST
    tx3 = ua.post('http://search.example.com', form={'q': 'test'})

    # Send "multipart/form-data" content via PUT
    tx4 = ua.put('upload.example.com', form={'test': {'content': 'Hello World!'}})

    # Send custom multipart content via PUT
    tx5 = ua.put('api.example.com', multipart=['Hello', 'World!'])

For more information about available content generators see also
:meth:`Pyjo.UserAgent.Transactor.Pyjo_UserAgent_Transactor.tx`.

Large file downloads
~~~~~~~~~~~~~~~~~~~~

When downloading large files with :mod:`Pyjo.UserAgent` you don't have to
worry about memory usage at all, because it will automatically stream
everything above 250KiB into a temporary file, which can then be moved into a
permanent file with :meth:`Pyjo.Message.Pyjo_Message.save_to`.

.. code-block:: python

    import Pyjo.UserAgent

    # Fetch the latest Pyjoyment tarball
    ua = Pyjo.UserAgent.new(max_redirects=5)
    tx = ua.get('https://github.com/pyjoyment/Pyjoyment/tarball/main')
    tx.result.save_to('pyjoyment.tar.gz')

With :meth:`Pyjo.File.Pyjo_File.download` you can also stream file downloads
directly into the target file. This allows for interrupted downloads to be
resumed at a later time.

.. code-block:: python

    import Pyjo.File

    # Download the latest Pyjoyment tarball directly into a file
    Pyjo.File.path('/home/sri/pyjoyment.tar.gz').download('https://github.com/pyjoyment/Pyjoyment/tarball/main')

To protect you from excessively large files there is also a limit of 2GiB by
default, which you can tweak with the attribute
:attr:`Pyjo.UserAgent.Pyjo_UserAgent.max_response_size`.

.. code-block:: python

    # Increase limit to 10GiB
    ua.max_response_size = 10737418240

Large file upload
~~~~~~~~~~~~~~~~~

Uploading a large file is even easier.

.. code-block:: python

    import Pyjo.UserAgent

    # Upload file via POST and "multipart/form-data"
    ua = Pyjo.UserAgent.new()
    ua.post('example.com/upload', form={'image': {'file': '/home/sri/hello.png'}})

And once again you don't have to worry about memory usage, all data will be
streamed directly from the file.

Streaming response
~~~~~~~~~~~~~~~~~~

Receiving a streaming response can be really tricky in most HTTP clients, but
:mod:`Pyjo.UserAgent` makes it actually easy.

.. code-block:: python

    import Pyjo.UserAgent

    # Accept responses of indefinite size
    ua = Pyjo.UserAgent.new(max_response_size=0)

    # Build a normal transaction
    tx = ua.build_tx('GET', 'http://example.com')

    # Replace "read" events to disable default content parser
    tx.res.content.unsubscribe('read').on('read', lambda content, data: print(f'Streaming: {data}'))

    # Process transaction
    tx = ua.start(tx)

The event ``read`` of :mod:`Pyjo.Content` will be emitted for every chunk of
data that is received, even chunked transfer encoding and gzip content
encoding will be handled transparently if necessary.

Streaming request
~~~~~~~~~~~~~~~~~

Sending a streaming request is almost just as easy.

.. code-block:: python

    import Pyjo.UserAgent

    # Build a normal transaction
    ua = Pyjo.UserAgent.new()
    tx = ua.build_tx('POST', 'http://example.com')

    # Prepare body
    body = b'Hello World!'
    tx.req.headers.content_length = len(body)


    # Start writing directly with a drain callback
    def drain(content, offset=None):
        global body
        chunk, body = body[:1], body[1:]
        content.write(chunk, drain if len(body) else None)


    drain(tx.req.content)

    # Process transaction
    tx = ua.start(tx)

The drain callback passed to :meth:`Pyjo.Content.Pyjo_Content.write` will be
executed whenever the entire previous chunk of data has actually been
written.

Non-blocking
~~~~~~~~~~~~

:mod:`Pyjo.UserAgent` has been designed from the ground up to be
non-blocking, the whole blocking API is just a simple convenience wrapper.
Especially for high latency tasks like web crawling this can be extremely
useful, because you can keep many concurrent connections active at the same
time.

.. code-block:: python

    import Pyjo.IOLoop
    import Pyjo.UserAgent

    # Concurrent non-blocking requests
    ua = Pyjo.UserAgent.new()
    ua.get('https://github.com/pyjoyment/Pyjoyment', lambda ua, pyjo: print(pyjo.result.dom().at('title').text))
    ua.get('https://github.com/mojolicious/mojo', lambda ua, mojo: print(mojo.result.dom().at('title').text))

    # Start event loop if necessary
    if not Pyjo.IOLoop.is_running():
        Pyjo.IOLoop.start()

But don't try to open too many connections to one server at the same time, it
might get overwhelmed. Better use a queue to process requests in smaller
batches.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.UserAgent

    urls = [
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_DOM.html',
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo.html',
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_File.html',
        'https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_URL.html',
    ]

    # User agent with a custom name, following up to 5 redirects
    ua = Pyjo.UserAgent.new(max_redirects=5)
    ua.transactor.name = 'MyParallelCrawler 1.0'

    # Use a promise to keep the event loop running until we are done
    promise = Pyjo.Promise.new()
    count = 0


    def fetch():
        global count

        # Stop if there are no more URLs
        if not urls:
            return
        url = urls.pop(0)

        # Fetch the next title
        def title(ua, tx):
            global count
            print(f'{url}: {tx.result.dom().at("title").text}')

            # Next request
            fetch()
            count -= 1
            if count == 0:
                promise.resolve()

        ua.get(url, title)
        count += 1


    # Process two requests at a time
    for _ in range(2):
        fetch()
    promise.wait()

It is also strongly recommended to respect every sites ``robots.txt`` file as
well as terms of service, and to wait a little before reopening connections to
the same host, or the operators might be forced to block your access.

Long requests of the user agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A service that answers slowly, as the API of a model of language, which can
be silent for minutes before its first byte, gets a user agent of its own,
whose :attr:`~Pyjo.UserAgent.Pyjo_UserAgent.inactivity_timeout` waits that
long, and whose :attr:`~Pyjo.UserAgent.Pyjo_UserAgent.request_timeout`
bounds each of its requests. A request with a time of its own races with
:meth:`Pyjo.Promise.Pyjo_Promise.timeout`, and
:meth:`Pyjo.Promise.Pyjo_Promise.cancel` closes its connection when the time
passes first, as nothing awaits its response anymore, and does nothing when
the request has ended.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.UserAgent

    # A user agent of its own for a slow service
    llm = Pyjo.UserAgent.new(inactivity_timeout=300, request_timeout=600)


    # One request with a time of its own
    async def complete(prompt):
        promise = llm.post_p('https://api.example.com/v1/complete', json={'prompt': prompt})
        try:
            tx = await Pyjo.Promise.race(promise, Pyjo.Promise.timeout(120, 'Too slow'))
        finally:
            promise.cancel()
        return tx.result.json()

An action of :mod:`Pyjoyment` that awaits such a request is cancelled when
its client goes away, with the request, as :ref:`cookbook-long-requests`
describes.

Concurrent blocking requests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You might have seen :meth:`Pyjo.Promise.Pyjo_Promise.wait` already in some
examples above. It is used to make non-blocking operations portable, allowing
them to work inside an already running event loop or start one on demand.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.UserAgent

    # Synchronize non-blocking requests with promises
    ua = Pyjo.UserAgent.new()
    pyjo_promise = ua.get_p('https://github.com/pyjoyment/Pyjoyment')
    mojo_promise = ua.get_p('https://github.com/mojolicious/mojo')


    @Pyjo.Promise.all(pyjo_promise, mojo_promise).then
    def titles(pyjo, mojo):
        print(pyjo[0].result.dom().at('title').text)
        print(mojo[0].result.dom().at('title').text)


    titles.wait()

WebSockets
~~~~~~~~~~

WebSockets are not just for the server-side, you can use ``websocket_p`` of
:mod:`Pyjo.UserAgent` to open new connections, which are always
non-blocking. The WebSocket handshake uses HTTP, and is a normal ``GET``
request with a few additional headers. It can even contain cookies, and is
followed by a ``101`` response from the server, notifying our user agent that
the connection has been established and it can start using the bi-directional
WebSocket protocol.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.UserAgent

    from Pyjo.Util import warn

    # Open WebSocket to echo service
    ua = Pyjo.UserAgent.new()


    @ua.websocket_p('wss://ws.postman-echo.com/raw').then
    def echo(tx):
        # Prepare a followup promise so we can wait for messages
        promise = Pyjo.Promise.new()

        # Wait for WebSocket to be closed
        @tx.on('finish')
        def finish(tx, code, reason):
            print(f'WebSocket closed with status {code}.')
            promise.resolve()

        # Close WebSocket after receiving one message
        @tx.on('message')
        def message(tx, msg):
            print(f'WebSocket message: {msg}')
            tx.finish()

        # Send a message to the server
        tx.send('Hi!')

        # Insert a new promise into the promise chain
        return promise


    # Handle failed WebSocket handshakes and other exceptions
    echo.catch(lambda err: warn(f'WebSocket error: {err}')).wait()

UNIX domain sockets
~~~~~~~~~~~~~~~~~~~

Not just TCP/IP sockets are supported, but also UNIX domain sockets, which can
have significant security and performance benefits when used for
inter-process communication. Instead of ``http://`` and ``ws://`` you can use
the ``http+unix://`` and ``ws+unix://`` schemes, and pass along a percent
encoded path (``/`` becomes ``%2F``) instead of a hostname.

.. code-block:: python

    import Pyjo.Promise
    import Pyjo.UserAgent

    from Pyjo.Util import warn

    # GET request via UNIX domain socket "/tmp/foo.sock"
    ua = Pyjo.UserAgent.new()
    print(ua.get('http+unix://%2Ftmp%2Ffoo.sock/index.html').result.text)

    # GET request with HOST header via UNIX domain socket "/tmp/bar.sock"
    tx = ua.get('http+unix://%2Ftmp%2Fbar.sock', {'Host': 'example.com'})
    print(tx.result.text)


    # WebSocket connection via UNIX domain socket "/tmp/baz.sock"
    @ua.websocket_p('ws+unix://%2Ftmp%2Fbaz.sock/echo').then
    def echo(tx):
        promise = Pyjo.Promise.new()
        tx.on('finish', lambda tx, *args: promise.resolve())

        @tx.on('message')
        def message(tx, msg):
            print(f'WebSocket message: {msg}')
            tx.finish()

        tx.send('Hi!')

        return promise


    echo.catch(lambda err: warn(f'WebSocket error: {err}')).wait()

You can set the ``Host`` header manually to pass along a hostname.

Command line
~~~~~~~~~~~~

Don't you hate checking huge HTML files from the command line? Thanks to the
command :mod:`Pyjoyment.Command.get` that is about to change. You can just
pick the parts that actually matter with the CSS selectors from
:mod:`Pyjo.DOM` and JSON Pointers from :mod:`Pyjo.JSON.Pointer`.

.. code-block:: console

    $ pyjo get https://mojolicious.org 'head > title'

How about a list of all id attributes?

.. code-block:: console

    $ pyjo get https://mojolicious.org '*' attr id

Or the text content of all heading tags?

.. code-block:: console

    $ pyjo get https://mojolicious.org 'h1, h2, h3' text

Maybe just the text of the third heading?

.. code-block:: console

    $ pyjo get https://mojolicious.org 'h1, h2, h3' 3 text

You can also extract all text from nested child elements.

.. code-block:: console

    $ pyjo get https://mojolicious.org '#mojobar' all

The request can be customized as well.

.. code-block:: console

    $ pyjo get -M POST -H 'X-Bender: Bite my shiny metal ass!' http://google.com

Store response data by redirecting ``STDOUT``.

.. code-block:: console

    $ pyjo get mojolicious.org > example.html

Pass request data by redirecting ``STDIN``.

.. code-block:: console

    $ pyjo get -M PUT mojolicious.org < example.html

Or use the output of another program.

.. code-block:: console

    $ echo 'Hello World' | pyjo get -M PUT https://mojolicious.org

Submit forms as ``application/x-www-form-urlencoded`` content.

.. code-block:: console

    $ pyjo get -M POST -f 'q=Pyjoyment' -f 'size=5' https://metacpan.org/search

And upload files as ``multipart/form-data`` content.

.. code-block:: console

    $ pyjo get -M POST -f 'upload=@example.html' mojolicious.org

You can follow redirects and view the headers for all messages.

.. code-block:: console

    $ pyjo get -r -v http://google.com 'head > title'

Extract just the information you really need from JSON data structures.

.. code-block:: console

    $ pyjo get https://pypi.org/pypi/Pyjoyment/json /info/version

This can be an invaluable tool for testing your applications.

.. code-block:: console

    $ ./myapp.py get /welcome 'head > title'

One-liners
~~~~~~~~~~

For quick hacks and especially testing, :mod:`Pyjo` one-liners are also a
great choice.

.. code-block:: console

    $ python -m Pyjo 'g("mojolicious.org").dom().at("title").text'

More of them, for JSON APIs, files of JSON and YAML and the manifests of
Kubernetes, are in :doc:`oneliners`.

Applications
------------

Fun :mod:`Pyjoyment` application hacks for all occasions.

Basic authentication
~~~~~~~~~~~~~~~~~~~~

Basic authentication data will be automatically extracted from the
``Authorization`` header.

.. literalinclude:: cookbook/basic_auth.py
    :language: python
    :caption: myapp.py

This can be combined with TLS for a secure authentication mechanism.

.. code-block:: console

    $ ./myapp.py daemon -l 'https://*:3000?cert=./server.crt&key=./server.key'

Adding a configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Adding a configuration file to your application is as easy as adding a file to
its home directory and loading the plugin :mod:`Pyjoyment.Plugin.Config`. The
default name is based on the value of :attr:`Pyjo.App.Pyjo_App.moniker`
(``myapp``), appended with a ``.conf`` extension (``myapp.conf``).

.. code-block:: console

    $ mkdir myapp
    $ cd myapp
    $ touch myapp.py
    $ chmod 744 myapp.py
    $ echo "{'name': 'my Pyjoyment application'}" > myapp.conf

Configuration files themselves are just Python code whose last expression is
a dict with configuration settings of your choice. All those settings are then
available through the method :meth:`Pyjo.App.Pyjo_App.config` and the
helper ``config`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`.

.. literalinclude:: cookbook/config/myapp.py
    :language: python
    :caption: myapp.py

Alternatively you can also use configuration files in the JSON format with
:mod:`Pyjoyment.Plugin.JSONConfig`, in YAML with
:mod:`Pyjoyment.Plugin.YAMLConfig`, in TOML with
:mod:`Pyjoyment.Plugin.TOMLConfig` or in INI with
:mod:`Pyjoyment.Plugin.INIConfig`.

Adding a plugin to your application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To organize your code better and to prevent helpers from cluttering your
application, you can use application specific plugins.

.. code-block:: console

    $ mkdir -p MyApp/Plugin
    $ touch MyApp/Plugin/MyHelpers.py

They work just like normal plugins and are also subclasses of
:mod:`Pyjoyment.Plugin`. Nested helpers with a prefix based on the plugin name
are an easy way to avoid conflicts.

.. literalinclude:: cookbook/plugin/MyApp/Plugin/MyHelpers.py
    :language: python
    :caption: MyApp/Plugin/MyHelpers.py

You can have as many application specific plugins as you like, the only
difference to normal plugins is that you load them using their full name.
The directory of the script is the first one of ``sys.path``, so the package
``MyApp`` next to it is found.

.. literalinclude:: cookbook/plugin/myapp.py
    :language: python
    :caption: myapp.py

Of course these plugins can contain more than just helpers, take a look at
:mod:`Pyjoyment.Plugins` for a few ideas.

Adding commands to Pyjoyment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By now you've probably used many of the built-in commands described in
:mod:`Pyjoyment.Commands`, but did you know that you can just add new ones and
that they will be picked up automatically by the command line interface if
they are placed in a directory from ``sys.path``? The namespace
``Pyjoyment.Command`` takes in the modules of every
``Pyjoyment/Command`` directory there.

.. literalinclude:: cookbook/commands/Pyjoyment/Command/spy.py
    :language: python
    :caption: Pyjoyment/Command/spy.py

Command line arguments are passed right through and there are many useful
attributes and methods in :mod:`Pyjoyment.Command` that you can use or
overload.

.. code-block:: console

    $ pyjo spy secrets
    pyjoyment-hello_world

    $ python -m MyApp spy secrets
    my_app

And to make your commands application specific, just add a custom namespace to
:attr:`Pyjoyment.Commands.Pyjoyment_Commands.namespaces` and use a module
like ``MyApp.Command.spy`` instead of ``Pyjoyment.Command.spy``.

.. literalinclude:: cookbook/commands/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

The options ``-h``/``--help``, ``--home`` and ``-m``/``--mode`` are handled
automatically by :mod:`Pyjoyment.Commands` and are shared by all commands.

.. code-block:: console

    $ python -m MyApp spy -m production mode
    production

For a full list of shared options see :mod:`Pyjoyment.Commands`.

Running code against your application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ever thought about running a quick one-liner against your :mod:`Pyjoyment`
application to test something? Thanks to the command
:mod:`Pyjoyment.Command.eval` you can do just that, the application object
itself can be accessed via ``app``.

.. code-block:: console

    $ pyjo generate lite-app myapp.py
    $ ./myapp.py eval 'print(*app.static.paths, sep="\n")'
    $ ./myapp.py eval 'print(*sorted(app.renderer.helpers), sep="\n")'

The ``verbose`` options will automatically print the return value or returned
data structure to ``sys.stdout``.

.. code-block:: console

    $ ./myapp.py eval -v 'app.static.paths[0]'
    $ ./myapp.py eval -V 'app.static.paths'

Making your application installable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ever thought about releasing your :mod:`Pyjoyment` application to PyPI? It's
actually much easier than you might think.

.. code-block:: console

    $ pyjo generate app MyApp
    $ cd my_app
    $ mv public templates my_app.yml MyApp/

The trick is to move the ``public`` and ``templates`` directories, and the
configuration file, into the package, so they can get automatically installed
with the modules. A configuration file with secrets can also stay out of the
package, where the ``PYJO_CONFIG`` environment variable points at it, so that
the secrets are not published. Additionally author commands from the
``Pyjoyment.Command.Author`` namespace are not usually wanted by an installed
application so they can be excluded.

.. literalinclude:: cookbook/installable/MyApp/__init__.py
    :language: python
    :caption: MyApp/__init__.py

Finally there is just one small change to be made to ``pyproject.toml``. It
gets a build system, which builds the package ``MyApp`` with its files into a
wheel, and the version that every distribution on PyPI needs.

.. literalinclude:: cookbook/installable/pyproject.toml
    :language: toml
    :caption: pyproject.toml

That's really everything, now you can package your application like any other
Python project, and ``python -m MyApp`` starts it once it is installed.

.. code-block:: console

    $ python -m Pyjo.Prove -l -r t
    $ uv build

And if you have a PyPI account (which can be requested at https://pypi.org)
even upload it.

.. code-block:: console

    $ uv publish

Proxy
~~~~~

While every :mod:`Pyjoyment` application has the built-in user agent, the
helper ``ua`` of :mod:`Pyjoyment.Plugin.DefaultHelpers`, for you to perform
requests to backend web services, this is not always the most efficient
solution. The specialized proxy helpers ``proxy.get_p`` and ``proxy.start_p``
of :mod:`Pyjoyment.Plugin.DefaultHelpers` can stream response content
straight to the client, as soon as a new chunk of data is received from the
backend web service. Additionally they will take care of removing hop-by-hop
headers and protect you automatically from backpressure issues. Which can
happen in situations where the connection to the backend web service is
faster than the connection to the client and data forwarding needs to be
throttled. And the best of all, everything happens non-blocking, that means
your web server can process other requests concurrently while waiting for
I/O.

.. literalinclude:: cookbook/proxy.py
    :language: python
    :caption: myapp.py

All proxy helpers return a :mod:`Pyjo.Promise` object, which should be used to
handle connection errors to backend web services gracefully. And if you ever
need to forward all headers from the client to the backend web service, make
sure to use :meth:`Pyjo.Headers.Pyjo_Headers.dehop` to remove all hop-by-hop
headers.

.. code-block:: python

    # Clone and modify request headers
    headers = c.req.headers.clone().dehop()
    headers.accept = 'application/json'
    tx = c.ua().build_tx('PUT', 'https://mojolicious.org', headers.to_dict())

JSONP
~~~~~

A page of another site reads the JSON of your application with CORS, which a
new API should use: the header ``Access-Control-Allow-Origin`` names the
origins that may read the response, and the recipe `Hosts and origins`_ says
how to check them.

.. code-block:: python

    @get('/headlines')
    def headlines(c):
        c.res.headers.access_control_allow_origin = 'https://example.com'
        c.render(json=HEADLINES)

Some clients cannot use CORS, as a widget on the pages of others that has to
work with old browsers, or a page opened from ``file://``. They load the data
with an element ``script``, and the response of JSONP is JavaScript that calls
a function of the page, whose name comes with the request. :mod:`Pyjoyment`
has no helper for it, as it takes a few lines, and each of them makes it safe.

.. literalinclude:: cookbook/jsonp.py
    :language: python
    :caption: myapp.py

.. code-block:: console

    $ ./myapp.py get '/headlines?callback=show'
    /**/show({"headlines":["Pyjoyment released","Hello World!"]});

* The name of the callback is put into the code of the response, so it is
  checked against the names of JavaScript, with dots for the members of an
  object, as ``App.show``. Anything else, as ``alert(1)//``, would be code that
  the page runs.
* The type ``application/javascript`` and ``X-Content-Type-Options: nosniff``
  keep the browser from taking the response for something else.
* The comment ``/**/`` in front of the callback keeps a response from starting
  with bytes that a plugin of a browser takes for another format, as the old
  attack of Rosetta Flash did.
* Any site can read a response of JSONP, with the cookies of its user too. So
  it serves only public data, or data that a token in the URL of the request
  allows, never the data of a session.

JSON inline
~~~~~~~~~~~

The data of a page do not need a request of their own, when the page that
renders them carries them, as the first state of an application of JavaScript
or the configuration of a widget. An element ``script`` of the type
``application/json``, which the browser does not run, holds them, and
``JSON.parse`` reads its text.

.. literalinclude:: cookbook/json_inline.py
    :language: python
    :caption: myapp.py

The JSON goes into the template with ``<%==``, as the escaping of HTML of
``<%=`` would break its quotes. :func:`Pyjo.JSON.to_json` escapes ``/`` and
``<`` in its strings, so that neither ``</script>`` nor ``<!--<script>`` in
the data can end the element or keep it from ending, and ``JSON.parse`` gets
them back as they were. A page with the data of its user is not for a cache
that other users share.

JSON inline is for the data of the page that renders them, JSONP for a page of
another site that cannot use CORS, and CORS or a request of the same origin for
everything else.

Hello World
~~~~~~~~~~~

If every byte matters this is the smallest ``Hello World`` application you can
write with :mod:`Pyjoyment.Lite`.

.. literalinclude:: cookbook/hello.py
    :language: python
    :caption: myapp.py

It works because all routes without a pattern default to ``/`` and automatic
rendering kicks in even if no actual code gets executed by the router. The
renderer just picks up the ``text`` value from the stash and generates a
response.

Hello World one-liners
~~~~~~~~~~~~~~~~~~~~~~

The ``Hello World`` example above can get even a little bit shorter in a
:mod:`Pyjo` one-liner.

.. code-block:: console

    $ python -m Pyjo 'a({"text": "Hello World!"}).start()' daemon

And you can use all the commands from :mod:`Pyjoyment.Commands`.

.. code-block:: console

    $ python -m Pyjo 'a({"text": "Hello World!"}).start()' get -v /

More
----

You can continue with :doc:`index` now or take a look at the `Mojolicious
wiki <https://github.com/mojolicious/mojo/wiki>`_, which contains a lot more
documentation and examples by many different authors.

Ported from `Mojolicious::Guides::Cookbook
<https://github.com/mojolicious/mojo/blob/v9.53/lib/Mojolicious/Guides/Cookbook.pod>`_
of Mojolicious 9.53.
