"""
Pyjoyment.Plugin.CORS - Cross-Origin Resource Sharing plugin
============================================================
::

    # Pyjoyment
    app.plugin('CORS')

    # Pyjoyment.Lite
    plugin('CORS')

    # The pages of two sites, with their cookies, for the API only
    app.plugin(
        'CORS',
        origins=['https://app.example.com', 'https://admin.example.com'],
        credentials=True,
        paths=['/api'],
        max_age=600,
    )

:mod:`Pyjoyment.Plugin.CORS` lets the pages of other sites read the
responses of the application, with the protocol of
`CORS <https://fetch.spec.whatwg.org/#http-cors-protocol>`_ of Fetch. It
answers a preflight request, an ``OPTIONS`` request with
``Access-Control-Request-Method`` that a browser sends before a request that
a page of another site could not send without CORS, with
``204 No Content`` before the routes, and adds
``Access-Control-Allow-Origin`` to the responses, of the actions and the
static files alike, for a request with an ``Origin`` header of one of its
origins. A response that has ``Access-Control-Allow-Origin`` already, as one
that an action sets, is kept.

A request of an origin that is not one of the origins gets no headers of
CORS, so that the browser does not give the response to the page, and its
preflight request is answered without them too, so that it reaches no
action. CORS protects what a page of another site may read, not what it may
request: a form of another site can still post to the application, which
the CSRF protection of the forms is for.

With :mod:`Pyjoyment.Plugin.AllowedHosts`, which rejects a request of an
origin that is not one of its own with ``403 Forbidden``, the origins of
CORS are among its origins too.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Options
-------

:mod:`Pyjoyment.Plugin.CORS` supports the following options.

``credentials`` ::

    app.plugin('CORS', origins=['https://app.example.com'], credentials=True)

    Let the pages send their cookies and the authentication of HTTP with the
    requests, with ``Access-Control-Allow-Credentials: true``, defaults to
    ``False``. It needs the origins of their own, as a browser does not take
    ``*`` with credentials, and a page of any site that the user visits
    would read the responses for the user otherwise.

``expose`` ::

    app.plugin('CORS', expose=['Server-Timing', 'X-Request-Id'])

    The headers of the responses, other than the ones that every page may
    read, as ``Content-Type``, that a page may read, with
    ``Access-Control-Expose-Headers``, defaults to none.

``headers`` ::

    app.plugin('CORS', headers=['Authorization', 'Content-Type'])

    The headers that the requests of the pages may have, with
    ``Access-Control-Allow-Headers``, defaults to ``None``, the ones that a
    preflight request asks for in ``Access-Control-Request-Headers``.

``max_age`` ::

    app.plugin('CORS', max_age=600)

    How long a browser keeps the answer of a preflight request, in seconds,
    with ``Access-Control-Max-Age``, defaults to ``None``, for which a
    browser keeps it for 5 seconds. Chromium keeps it for 2 hours at most.

``methods`` ::

    app.plugin('CORS', methods=['GET', 'POST'])

    The methods that the requests of the pages may have, with
    ``Access-Control-Allow-Methods``, defaults to ``GET``, ``HEAD``,
    ``POST``, ``PUT``, ``PATCH`` and ``DELETE``.

``origins`` ::

    app.plugin('CORS', origins=['https://app.example.com', 'http://localhost:5173'])
    app.plugin('CORS', origins=[re.compile(r'^https://pr-\\d+\\.example\\.com$')])
    app.plugin('CORS', origins=lambda c, origin: origin.endswith('.example.com'))

    The origins of the pages that may read the responses, defaults to
    ``*``, every origin, without credentials. An origin is a scheme, a host
    and a port, as ``Origin`` has it, compared without its case, a regular
    expression searches it, and a function takes the controller and the
    origin, and returns true for an origin that may.

``paths`` ::

    app.plugin('CORS', paths=['/api', re.compile(r'^/v\\d+/')])

    The paths of the requests that CORS is for, defaults to ``None``, every
    path. A path is the one of a request and its subpaths, as ``/api`` of
    ``/api`` and ``/api/users``, and a regular expression searches the path
    of a request.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious.

Classes
-------
"""

import Pyjo.Exception
import Pyjoyment.Plugin

import re

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import Pyjoyment
    import Pyjoyment.Controller

type _Origins = str | Iterable[str | re.Pattern[str]] | Callable[['Pyjoyment.Controller.object', str], bool]
type _Paths = Iterable[str | re.Pattern[str]] | None

_METHODS = ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE')
_OPTIONS = {'credentials', 'expose', 'headers', 'max_age', 'methods', 'origins', 'paths'}


class Pyjoyment_Plugin_CORS(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.CORS` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> None:
        """::

            plugin.register(Pyjoyment.new())
            plugin.register(Pyjoyment.new(), {'origins': ['https://app.example.com']})

        Register the hooks in :mod:`Pyjoyment` application.
        """
        conf = conf or {}
        if unknown := sorted(set(conf) - _OPTIONS):
            raise Pyjo.Exception.new(f'Unknown option of CORS: {unknown[0]}')
        origins: _Origins = conf.get('origins', '*')
        credentials = bool(conf.get('credentials'))
        if credentials and origins == '*':
            raise Pyjo.Exception.new('Option credentials of CORS needs origins of its own')
        if not isinstance(origins, str) and not callable(origins):
            origins = list(origins)
        paths: _Paths = conf.get('paths')
        if paths is not None:
            paths = list(paths)
        methods = ', '.join(conf.get('methods') or _METHODS)
        headers: list[str] | None = conf.get('headers')
        expose = ', '.join(conf.get('expose') or [])
        max_age: int | None = conf.get('max_age')

        def allowed(c: 'Pyjoyment.Controller.object') -> str | None:
            # The value of Access-Control-Allow-Origin of the request, or None for one of another origin
            if paths is not None and not _path(c.req.url.path.to_str(), paths):
                return None
            if (origin := c.req.headers.origin) is None:
                return None
            if origins == '*':
                return '*'
            return origin if _origin(c, origins, origin) else None

        def before_dispatch(c: 'Pyjoyment.Controller.object') -> None:
            # A preflight request, which a route would not know, answered before the routes
            req = c.req
            if req.method != 'OPTIONS' or req.headers.access_control_request_method is None:
                return
            if paths is not None and not _path(req.url.path.to_str(), paths):
                return
            res_headers = c.res.headers
            if (origin := allowed(c)) is not None:
                res_headers.access_control_allow_origin = origin
                res_headers.access_control_allow_methods = methods
                if requested := req.headers.access_control_request_headers if headers is None else ', '.join(headers):
                    res_headers.access_control_allow_headers = requested
                if credentials:
                    res_headers.access_control_allow_credentials = 'true'
                if max_age is not None:
                    res_headers.access_control_max_age = max_age
            if origins != '*':
                res_headers.append('Vary', 'Origin')
            if headers is None:
                res_headers.append('Vary', 'Access-Control-Request-Headers')
            c.stash()['cors.preflight'] = True
            c.rendered(204)

        def after_dispatch(c: 'Pyjoyment.Controller.object') -> None:
            res_headers = c.res.headers
            if 'cors.preflight' in c.stash() or res_headers.access_control_allow_origin is not None:
                return
            if paths is not None and not _path(c.req.url.path.to_str(), paths):
                return
            # A cache keeps the responses of the origins apart
            if origins != '*':
                res_headers.append('Vary', 'Origin')
            if (origin := allowed(c)) is None:
                return
            res_headers.access_control_allow_origin = origin
            if credentials:
                res_headers.access_control_allow_credentials = 'true'
            if expose:
                res_headers.access_control_expose_headers = expose

        app.hook('before_dispatch', before_dispatch)
        app.hook('after_dispatch', after_dispatch)


def _origin(c: 'Pyjoyment.Controller.object', origins: _Origins, origin: str) -> bool:
    if callable(origins):
        return origins(c, origin)
    for allowed in origins:
        if isinstance(allowed, re.Pattern):
            if allowed.search(origin):
                return True
        elif allowed.lower() == origin.lower():
            return True
    return False


def _path(path: str, paths: Iterable[str | re.Pattern[str]]) -> bool:
    for allowed in paths:
        if isinstance(allowed, re.Pattern):
            if allowed.search(path):
                return True
            continue
        prefix = allowed.rstrip('/')
        if path == prefix or path.startswith(f'{prefix}/'):
            return True
    return False


new = Pyjoyment_Plugin_CORS.new
object = Pyjoyment_Plugin_CORS
CORS = Pyjoyment_Plugin_CORS
