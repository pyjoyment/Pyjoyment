---
name: django
description: Serve an existing Django project, or another WSGI or ASGI application of Python, with the servers of Pyjoyment in the place of gunicorn, uWSGI or uvicorn, as its application mounted on / of a script of Pyjoyment.Lite. Use for config/server.py, the reactor of Poll that the ORM of Django needs on WSGI, ASGI with async views, the options of gunicorn in prefork, the static files of collectstatic, the probes with a check of the database, the access log, and Pyjo.UserAgent in the views in the place of requests or httpx.
---

# Django on the servers of Pyjoyment

The project stays as it is. A script of `Pyjoyment.Lite` next to
`config/wsgi.py` mounts its application on `/`, and the static files, the
probes and the access log of Pyjoyment come before it.

```python
# config/server.py
import os


# A WSGI application blocks, so it runs on the reactor of Poll, which is chosen before Pyjoyment is imported
os.environ.setdefault('PYJO_REACTOR', 'Pyjo.Reactor.Poll')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from Pyjoyment.Lite import *  # noqa: E402

from django.conf import settings  # noqa: E402
from django.core.signals import request_finished, request_started  # noqa: E402
from django.db import connection  # noqa: E402


# The output of collectstatic, before the routes, in the place of whitenoise
app.static.paths = [str(settings.STATIC_ROOT.parent)]
app.static.immutable = r'^static/.+\.[0-9a-f]{12}\.[^/.]+$'


# The database in a request of Django, whose handlers close a connection that the database has dropped
def database(c):
    request_started.send(sender=__name__)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    finally:
        request_finished.send(sender=__name__)


plugin('Health', checks={'database': database}, healthz=None)
plugin('AccessLog')
plugin('Mount', {'/': 'config.wsgi:application'})

if __name__ == '__main__':
    app.start()
```

```sh
python manage.py collectstatic --noinput
python -m config.server prefork -w 8 -c 1 -r 1 -p -l 'http://*:8080'
```

## WSGI or ASGI

- WSGI runs on `Pyjo.Reactor.Poll`: with the reactor of asyncio, the default
  one, the loop of asyncio is running when Django is called, and every query
  raises `SynchronousOnlyOperation: You cannot call this from an async
  context`. `PYJO_REACTOR` is read when `Pyjo.IOLoop` is imported, by the first
  module of Pyjoyment, so the script sets it before its imports.
- ASGI, `config.asgi:application`, runs on the default reactor, without the
  line of `PYJO_REACTOR`, and the check of the database in the thread of
  Django: `checks={'database': sync_to_async(database)}` of
  `asgiref.sync`. Its `async def` views await asyncio and promises in the
  event loop; its synchronous views run in one thread of Django, and so do the
  queries of its async ORM, as `await Note.objects.acount()`, one at a time
  in each worker, so a project of synchronous views and queries stays on
  WSGI.
- The ASGI application of Django has no lifespan, which the log notes on
  `debug`.

## Requests to other services

`Pyjo.UserAgent` replaces `requests` and `httpx` in the views:

```python
import Pyjo.UserAgent

from django.http import JsonResponse


ua = Pyjo.UserAgent.new()


# WSGI on Poll: a blocking request, with an event loop of its own
def release(request):
    res = ua.get('https://api.github.com/repos/pyjoyment/Pyjoyment/releases/latest').result
    return JsonResponse({'release': res.json('/tag_name')})


# ASGI: awaited in the event loop, which serves the other requests meanwhile
async def release_async(request):
    res = (await ua.get_p('https://api.github.com/repos/pyjoyment/Pyjoyment/releases/latest')).result
    return JsonResponse({'release': res.json('/tag_name')})
```

A blocking request holds its worker, so a request to the application itself
needs another worker that is free.

## From gunicorn

| gunicorn                                        | `prefork`                                                        |
| ----------------------------------------------- | ---------------------------------------------------------------- |
| `--bind 0.0.0.0:8080`                           | `-l 'http://*:8080'`, `PYJO_LISTEN`, or `PORT`                   |
| `--workers 8`                                   | `-w 8`, `PYJO_WORKERS`                                           |
| sync workers                                    | `-c 1 -r 1`: one connection at a time, closed after its response |
| `--workers 1 --threads 8`                       | `prethread -w 8 -c 1 -r 1`                                       |
| `--timeout 30`                                  | `-H 30`: stopped gracefully, killed after `-G`                   |
| `--graceful-timeout`                            | `-G` (25)                                                        |
| `--keep-alive`                                  | `-k`                                                             |
| `--max-requests 1000 --max-requests-jitter 100` | `-a 1400`: less up to half at random, 1050 on average            |
| `--forwarded-allow-ips`                         | `-p` with the networks of the proxies                            |
| `--access-logfile -`                            | `plugin('AccessLog')`                                            |
| `--reload`                                      | `pyjo-reload`                                                    |
| `GUNICORN_CMD_ARGS`                             | `PYJO_` and the name of each option                              |

- `-c 1` without `-r 1` keeps an idle connection of a client or a proxy on
  the worker for the keep-alive timeout, while the others wait in the
  backlog.
- A shell in the `CMD` of a container runs the server with `exec`, so that it
  gets `TERM`.
- `-S` (`PYJO_SHUTDOWN_DELAY`) and `-G` go into `terminationGracePeriodSeconds`
  of Kubernetes, 30 by default: `-S 5 -G 20` with the default.
- The readiness probe is `/readyz`, which Django does not see, so
  `ALLOWED_HOSTS` does not reject the address of the pod that the kubelet
  sends as `Host`; the liveness probe with `-c 1` is `tcpSocket`, as an HTTP
  probe waits behind busy workers and restarts the pod.
- `WHITENOISE_ROOT` is another directory of `app.static.paths`, and
  `app.static.extra = {}` leaves out the favicon and the images of Pyjoyment;
  with `DEBUG`, `urlpatterns += staticfiles_urlpatterns()` serves the files of
  the apps before `collectstatic`.
- The client of the access log behind a gateway is its own header, as
  `plugin('AccessLog', client='X-Envoy-External-Address')`, not the first
  address of `X-Forwarded-For`, which the client writes.

## Mistakes

- `python config/server.py` puts `config/` first on `sys.path`, so
  `No module named 'config'`: `python -m config.server` from the directory of
  `manage.py`.
- `PYJO_REACTOR` set after an import of a module of Pyjoyment, as in a
  test, has no effect: the reactor of asyncio, and `SynchronousOnlyOperation`.
- `PYJO_REACTOR=Pyjo.Reactor.Poll` cannot run the ASGI application.
- `await ua.get_p(...)` in an `async def` view of WSGI fails with
  `Task got bad yield`, and a blocking `ua.get(...)` on asyncio with
  `Blocking request in a running event loop`.
- `Health` without `healthz=None` answers the `/healthz` of the project
  itself, before its routes.
- A check with `connection.cursor()` alone keeps a connection that the
  database has dropped, and fails every probe until the worker restarts.
- Django sets `TZ` of the process to `TIME_ZONE`, `America/Chicago` by
  default, which the time of the logs of Pyjoyment follows.

## Documentation

- Django: https://pyjoyment.readthedocs.io/en/stable/guides/django.html
- From gunicorn: https://pyjoyment.readthedocs.io/en/stable/guides/gunicorn.html
- Mounting: https://pyjoyment.readthedocs.io/en/stable/guides/mounting.html
