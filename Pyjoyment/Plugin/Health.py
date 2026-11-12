"""
Pyjoyment.Plugin.Health - Liveness and readiness plugin
=======================================================
::

    # Pyjoyment
    app.plugin('Health')

    # Pyjoyment.Lite
    plugin('Health')

    # The checks of readiness, of a function, a coroutine function or one that returns a promise
    app.plugin('Health', checks={'db': lambda c: db.ping(), 'queue': queue_ready_p}, timeout=2)

    # A check that another plugin adds
    app.health.check('cache', lambda c: cache.connected)

:mod:`Pyjoyment.Plugin.Health` answers the probes of containers and
orchestrators, as the liveness, readiness and startup probes of Kubernetes,
the probes of Cloud Run, the health checks of load balancers and the
``HEALTHCHECK`` of Docker, with the endpoints of Kubernetes itself.

``GET /livez``
    Liveness: ``200 OK`` with ``ok`` while the server answers, as a server
    whose event loop is blocked does not answer. It has no checks of the
    application, as an orchestrator restarts a container whose liveness
    fails, and a database that is down does not get up with it.

``GET /healthz``
    The same as ``/livez``, under the name of the probes of Docker and of
    load balancers.

``GET /readyz``
    Readiness: ``200 OK`` with ``ok`` once the checks of the application
    pass, and ``503 Service Unavailable`` with the list of the checks while
    one of them fails, so that an orchestrator or a load balancer sends the
    requests to another instance. The check ``shutdown`` fails from the
    moment that the server stops gracefully, also during its
    :attr:`~Pyjo.Server.Daemon.Pyjo_Server_Daemon.shutdown_delay`, as
    :attr:`Pyjo.IOLoop.Pyjo_IOLoop.is_stopping` of the event loop of the
    thread, :data:`Pyjo.IOLoop.singleton`, which is the one of every server of
    Pyjoyment, and its workers, tells: a client whose connection is kept alive
    gets ``503`` with its last response.

The checks run at the same time, and a check passes unless it raises an
exception, returns ``False``, or returns a promise, a coroutine or another
awaitable that is rejected, is fulfilled with ``False``, or does not settle
within its timeout. A check that returns a value has run to its end before its
timeout starts, so the timeout does not bound it: it blocks the event loop
while it runs, as any code that blocks does, and the timeouts of its own
client bound it, as ``connect_timeout`` of a database, and a library that
refuses a running loop of :mod:`asyncio`, as the ORM of Django, runs in
:func:`Pyjo.IOLoop.blocking`. The reason of a failure goes to the log, as the
``warn`` message ``Health check "db" failed: ...``, not to the response,
which withholds it.

A query of ``verbose`` lists the checks on success too, ``exclude`` leaves a
check out, as many times as there are checks to leave out, and a check of its
own is under the name of the endpoint, as ``/readyz/db``, as Kubernetes has
them. ::

    $ curl 'http://127.0.0.1:3000/readyz?verbose'
    [+]shutdown ok
    [+]db ok
    readyz check passed

    $ curl 'http://127.0.0.1:3000/readyz?exclude=db'
    ok

    $ curl -i 'http://127.0.0.1:3000/readyz/db'
    HTTP/1.1 503 Service Unavailable
    ...
    [-]db failed: reason withheld
    readyz check failed

The endpoints are answered in a hook of ``around_dispatch``, before the hooks
of ``before_dispatch``, the static files and the routes, so that a probe is
cheap, is not logged but on the level ``trace``, and is answered also where a
hook rejects it, as :mod:`Pyjoyment.Plugin.AllowedHosts` would reject the
``Host`` of the address of a pod, which a probe of Kubernetes sends. A hook of
``around_dispatch`` that the application registers before the plugin wraps
the probes too. So an endpoint takes the path from the routes of the
application, and from an application that :mod:`Pyjoyment.Plugin.Mount`
mounts: one with a ``/healthz`` of its own, which its monitors request, keeps
it with ``healthz=None``.

A server whose workers serve one connection at a time, as ``prefork -c 1``
for an application that blocks, keeps a probe in the backlog while every
worker is busy, so that a liveness probe of HTTP restarts a container that is
only busy. Its liveness probe connects to the port, as ``tcpSocket`` of
Kubernetes, which the kernel accepts into the backlog, as
:mod:`Pyjoyment.Command.Author.generate.kubernetes` makes it with
``--liveness-probe``, and ``/readyz`` stays its readiness probe.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Options
-------

:mod:`Pyjoyment.Plugin.Health` supports the following options.

``checks`` ::

    app.plugin('Health', checks={'db': lambda c: db.ping()})

    The checks of readiness, the names and the functions that take the
    controller of the probe, defaults to none.

``healthz`` ::

    app.plugin('Health', healthz='/health')
    app.plugin('Health', healthz=None)

    The path of the alias of liveness, defaults to ``/healthz``, ``None``
    leaves it out.

``livez`` ::

    app.plugin('Health', livez='/-/live')

    The path of liveness, defaults to ``/livez``, ``None`` leaves it out.

``readyz`` ::

    app.plugin('Health', readyz='/-/ready')

    The path of readiness, defaults to ``/readyz``, ``None`` leaves it out.

``timeout`` ::

    app.plugin('Health', timeout=0.5)

    The time in seconds that a check of a promise, a coroutine or another
    awaitable may take, defaults to ``1``, the timeout of a probe of
    Kubernetes.

Helpers
-------

:mod:`Pyjoyment.Plugin.Health` implements the following helpers.

``health.check`` ::

    app.health.check('db', lambda c: db.ping())
    app.health.check('search', search_ready_p, timeout=5)

    Add a check of readiness, with a timeout of its own, or replace the
    check of the name, as a plugin that connects to a service does.

``health.path`` ::

    path = c.health.path('livez')

    The path of an endpoint, ``livez``, ``readyz`` or ``healthz``, or
    ``None`` for one that is left out, as
    :mod:`Pyjoyment.Command.Author.generate.dockerfile` takes it for the
    ``HEALTHCHECK`` of the image.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious.

Classes
-------
"""

import Pyjo.IOLoop
import Pyjo.Promise
import Pyjoyment.Plugin

import builtins
import concurrent.futures

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import Pyjoyment
    import Pyjoyment.Controller

type _Check = Callable[['Pyjoyment.Controller.object'], Any]

# The check of readiness of the server itself, which comes before the ones of the application
SHUTDOWN = 'shutdown'

# The result of a check that the query leaves out
EXCLUDED = builtins.object()


class Pyjoyment_Plugin_Health(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.Health` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> None:
        """::

            plugin.register(Pyjoyment.new())
            plugin.register(Pyjoyment.new(), {'checks': {'db': lambda c: True}})

        Register the hook and the helpers in :mod:`Pyjoyment` application.
        """
        conf = conf or {}
        default: float = conf.get('timeout', 1)
        given: dict[str, _Check] = conf.get('checks') or {}
        checks = {name: (cb, default) for name, cb in given.items()}
        paths: dict[str, str | None] = {
            endpoint: conf.get(endpoint, f'/{endpoint}') for endpoint in ('livez', 'readyz', 'healthz')
        }

        def check(c: 'Pyjoyment.Controller.object', name: str, cb: _Check, timeout: float | None = None) -> None:
            checks[name] = (cb, timeout if timeout is not None else default)

        def path(c: 'Pyjoyment.Controller.object', endpoint: str) -> str | None:
            return paths.get(endpoint)

        app.helper('health.check', check)
        app.helper('health.path', path)

        # The endpoints and the checks of their own, as Kubernetes has them
        live = {
            p: (endpoint, name)
            for endpoint in ('livez', 'healthz')
            if (prefix := paths[endpoint])
            for p, name in ((prefix, None), (f'{prefix}/ping', 'ping'))
        }
        ready = paths['readyz']

        def around_dispatch(next: Callable[[], Any], c: 'Pyjoyment.Controller.object') -> Any:
            req = c.req
            if req.method not in ('GET', 'HEAD'):
                return next()
            route = req.url.path.to_route()
            if (found := live.get(route)) is not None:
                return _live(c, *found)
            if ready and (route == ready or route.startswith(f'{ready}/')):
                name = route[len(ready) + 1 :] or None
                if name is None or name == SHUTDOWN or name in checks:
                    return _ready(c, name, checks)
            return next()

        app.hook('around_dispatch', around_dispatch)


def _live(c: 'Pyjoyment.Controller.object', endpoint: str, name: str | None) -> None:
    _render(c, endpoint, name, {'ping': None})


def _ready(c: 'Pyjoyment.Controller.object', name: str | None, checks: dict[str, tuple[_Check, float]]) -> None:
    # The checks of the probe in their order, which the query leaves out, each with the reason of its failure
    excluded = set(c.req.url.query.every_param('exclude')) if name is None else set[str]()
    results: dict[str, Any] = {n: None for n in ([SHUTDOWN, *checks] if name is None else [name])}
    promises: list[Pyjo.Promise.object] = []

    def failure(n: str) -> Callable[..., None]:
        def failed(*reason: Any) -> None:
            results[n] = reason[0] if reason and reason[0] is not None else 'rejected'

        return failed

    for n in results:
        if n in excluded:
            results[n] = EXCLUDED
        elif n == SHUTDOWN:
            results[n] = 'stopping gracefully' if Pyjo.IOLoop.singleton.is_stopping else None
        else:
            cb, timeout = checks[n]
            promises.append(_check_p(c, cb, timeout).catch(failure(n)))

    if not promises:
        return _render(c, 'readyz', name, results)

    # The response once every check has settled
    def render(*args: Any) -> None:
        _render(c, 'readyz', name, results)

    def exception(e: Any) -> None:
        c.helpers.reply.exception(e)

    c.render_later()
    Pyjo.Promise.all_settled(*promises).then(render).catch(exception)


def _check_p(c: 'Pyjoyment.Controller.object', cb: _Check, timeout: float) -> Pyjo.Promise.object:
    # A promise of its own, as a timeout attached to the promise of the check would reject a promise that the
    # application may share, as the one of its warm-up
    result = Pyjo.Promise.new()
    try:
        value = cb(c)
        if isinstance(value, Awaitable | concurrent.futures.Future) and not isinstance(value, Pyjo.Promise.object):
            value = Pyjo.Promise.new(value)
    except Exception as e:
        return result.reject(e)
    if not isinstance(value, Pyjo.Promise.object):
        return result.reject('returned False') if value is False else result.resolve()

    loop = result.ioloop
    timer = loop.timer(timeout, lambda loop: result.reject(f'timeout of {timeout:g} seconds'))

    def settled(*values: Any) -> None:
        loop.remove(timer)
        result.reject('returned False') if values and values[0] is False else result.resolve()

    def rejected(*reason: Any) -> None:
        loop.remove(timer)
        result.reject(*reason)

    value.then(settled, rejected)
    return result


def _render(c: 'Pyjoyment.Controller.object', endpoint: str, name: str | None, results: dict[str, Any]) -> None:
    # The failures with their reason in the log only, and the list of the checks on a failure or with "verbose"
    lines: list[str] = []
    failed = False
    for n, reason in results.items():
        if reason is EXCLUDED:
            lines.append(f'[+]{n} excluded: ok')
        elif reason is None:
            lines.append(f'[+]{n} ok')
        else:
            failed = True
            lines.append(f'[-]{n} failed: reason withheld')
            if n != SHUTDOWN:
                c.helpers.log().warn(f'Health check "{n}" failed: {reason}')

    if not failed and (name is not None or c.req.url.query.param('verbose') is None):
        c.render(text='ok', format='txt')
    else:
        lines.append(f'{endpoint} check {"failed" if failed else "passed"}')
        c.render(text='\n'.join(lines) + '\n', format='txt', status=503 if failed else 200)


new = Pyjoyment_Plugin_Health.new
object = Pyjoyment_Plugin_Health
Health = Pyjoyment_Plugin_Health
