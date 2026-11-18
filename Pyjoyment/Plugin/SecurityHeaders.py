"""
Pyjoyment.Plugin.SecurityHeaders - Security headers plugin
==========================================================
::

    # Pyjoyment
    app.plugin('SecurityHeaders')

    # Pyjoyment.Lite
    plugin('SecurityHeaders')

    # A policy of its own, tried out with the reports of the browser before it is enforced
    app.plugin(
        'SecurityHeaders',
        csp_report_only={'default-src': ["'self'"], 'img-src': ["'self'", 'data:']},
        permissions={'camera': [], 'geolocation': ['self'], 'microphone': []},
    )

    # Another policy for the responses of a route
    app.routes.get('/embed').to('embed#show', security_headers={'csp': {'frame-ancestors': ['https:']}})

:mod:`Pyjoyment.Plugin.SecurityHeaders` adds the headers that protect the
pages of an application in the browser to every response, of the actions,
the static files and the pages of errors alike: ``Strict-Transport-Security``,
``Content-Security-Policy``, ``Permissions-Policy``, ``X-Content-Type-Options``,
``Referrer-Policy`` and ``Cross-Origin-Opener-Policy``. A header that the
response has already, as one that an action sets, is kept.

Its defaults restrict nothing that a page usually needs:
``Content-Security-Policy`` keeps other sites from framing the pages and
from changing their base URL, without a policy of the scripts and the
styles, which the application gives with ``csp`` or tries out first with
``csp_report_only``.

``Strict-Transport-Security`` is sent with a response of a secure request
only, as :attr:`Pyjo.Message.Request.Pyjo_Message_Request.is_secure` says,
also of a request that a reverse proxy has received with HTTPS, and not for
``localhost`` and its subdomains, as a browser would then take every server
on the machine of a developer for one of HTTPS only, on any port. A browser
ignores it for an IP address.

The options of the policies take Python values, which the plugin turns into
the headers, or a string, which is the header as it is, and ``None`` or
``False`` leaves the header out.

See :mod:`Pyjoyment.Plugins` for a list of plugins that are available by
default.

Options
-------

:mod:`Pyjoyment.Plugin.SecurityHeaders` supports the following options.

``content_type_options`` ::

    app.plugin('SecurityHeaders', content_type_options=None)

    ``X-Content-Type-Options``, defaults to ``nosniff``, so that a browser
    takes the type of a response from ``Content-Type`` only.

``csp`` ::

    app.plugin('SecurityHeaders', csp={'default-src': ["'self'"], 'upgrade-insecure-requests': []})
    app.plugin('SecurityHeaders', csp="default-src 'self'")

    ``Content-Security-Policy``, the directives and their sources, defaults
    to ``{'base-uri': ["'self'"], 'frame-ancestors': ["'self'"],
    'object-src': ["'none'"]}``. A directive with no sources, as
    ``upgrade-insecure-requests``, has an empty list.

``csp_report_only`` ::

    app.plugin('SecurityHeaders', csp_report_only={'default-src': ["'self'"], 'report-uri': ['/csp-reports']})

    ``Content-Security-Policy-Report-Only``, a policy that the browser
    reports the violations of without enforcing it, as ``csp`` has it,
    defaults to ``None``. It goes with ``csp``, so that a stricter policy is
    tried out while the current one is enforced.

``embedder_policy`` ::

    app.plugin('SecurityHeaders', embedder_policy='require-corp')

    ``Cross-Origin-Embedder-Policy``, defaults to ``None``, as
    ``require-corp`` blocks the resources of other sites that do not allow
    it.

``hsts`` ::

    app.plugin('SecurityHeaders', hsts={'max_age': 300})
    app.plugin('SecurityHeaders', hsts={'max_age': 63072000, 'include_subdomains': True, 'preload': True})

    ``Strict-Transport-Security``, with ``max_age`` in seconds,
    ``include_subdomains`` and ``preload``, defaults to
    ``{'max_age': 31536000}``, a year. A browser keeps it for that long, so
    a site that starts to use it starts with a short one, and
    ``include_subdomains`` and ``preload`` come once every subdomain has
    HTTPS.

``opener_policy`` ::

    app.plugin('SecurityHeaders', opener_policy='same-origin-allow-popups')

    ``Cross-Origin-Opener-Policy``, defaults to ``same-origin``, so that a
    page of another site that opens one of the application, or that it
    opens, has no reference to its window.

``permissions`` ::

    app.plugin('SecurityHeaders', permissions={'camera': [], 'fullscreen': ['self'], 'geolocation': '*'})

    ``Permissions-Policy``, the features of the browser and the origins that
    may use them, defaults to ``{'camera': [], 'geolocation': [],
    'microphone': []}``. An empty list allows a feature to no one, ``self``
    to the origin of the page, ``*`` to every origin, and an origin, as
    ``https://example.com``, to that origin.

``referrer_policy`` ::

    app.plugin('SecurityHeaders', referrer_policy='no-referrer')

    ``Referrer-Policy``, defaults to ``strict-origin-when-cross-origin``, the
    origin alone for the requests to other sites, and nothing for a request
    from HTTPS to HTTP.

``resource_policy`` ::

    app.plugin('SecurityHeaders', resource_policy='same-site')

    ``Cross-Origin-Resource-Policy``, defaults to ``None``, as a resource of
    the application that other sites load, as an image of a CDN, would be
    blocked.

Stash
-----

``security_headers`` ::

    app.routes.get('/embed').to('embed#show', security_headers={'csp': {'frame-ancestors': ['https:']}})

    c.stash(security_headers={'permissions': None})

    Options of the response, which replace the ones of the plugin, as for a
    route whose pages other sites may frame.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious.

Classes
-------
"""

import Pyjo.Exception
import Pyjoyment.Plugin

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import Pyjoyment
    import Pyjoyment.Controller

# The headers of the options, and their defaults
_HEADERS = {
    'content_type_options': 'X-Content-Type-Options',
    'csp': 'Content-Security-Policy',
    'csp_report_only': 'Content-Security-Policy-Report-Only',
    'embedder_policy': 'Cross-Origin-Embedder-Policy',
    'hsts': 'Strict-Transport-Security',
    'opener_policy': 'Cross-Origin-Opener-Policy',
    'permissions': 'Permissions-Policy',
    'referrer_policy': 'Referrer-Policy',
    'resource_policy': 'Cross-Origin-Resource-Policy',
}
_DEFAULTS: dict[str, Any] = {
    'content_type_options': 'nosniff',
    'csp': {'base-uri': ["'self'"], 'frame-ancestors': ["'self'"], 'object-src': ["'none'"]},
    'csp_report_only': None,
    'embedder_policy': None,
    'hsts': {'max_age': 31536000},
    'opener_policy': 'same-origin',
    'permissions': {'camera': [], 'geolocation': [], 'microphone': []},
    'referrer_policy': 'strict-origin-when-cross-origin',
    'resource_policy': None,
}


class Pyjoyment_Plugin_SecurityHeaders(Pyjoyment.Plugin.object):
    """
    :mod:`Pyjoyment.Plugin.SecurityHeaders` inherits all methods from
    :mod:`Pyjoyment.Plugin` and implements the following new ones.
    """

    def register(self, app: 'Pyjoyment.object', conf: dict[str, Any] | None = None) -> None:
        """::

            plugin.register(Pyjoyment.new())
            plugin.register(Pyjoyment.new(), {'hsts': {'max_age': 300}})

        Register the hook in :mod:`Pyjoyment` application.
        """
        options = {**_DEFAULTS, **_options(conf or {})}
        headers = _headers(options)

        def after_dispatch(c: 'Pyjoyment.Controller.object') -> None:
            # An unknown option of the stash is logged, as the response has been rendered already
            values = headers
            if own := c.stash().get('security_headers'):
                if unknown := sorted(set(own) - set(_HEADERS)):
                    c.helpers.log().error(f'Unknown option of SecurityHeaders: {unknown[0]}')
                values = _headers({**options, **{k: v for k, v in own.items() if k in _HEADERS}})
            res_headers = c.res.headers
            for name, value in values.items():
                if name == 'Strict-Transport-Security' and not _secure(c):
                    continue
                if res_headers.header(name) is None:
                    res_headers.header(name, value)

        app.hook('after_dispatch', after_dispatch)


def _csp(policy: dict[str, list[str]]) -> str:
    return '; '.join(' '.join([directive, *sources]) for directive, sources in policy.items())


def _headers(options: dict[str, Any]) -> dict[str, str]:
    # The values of the headers of the options, without the ones that are left out
    headers: dict[str, str] = {}
    for option, name in _HEADERS.items():
        if (value := options[option]) is None or value is False:
            continue
        if not isinstance(value, str):
            value = (
                _hsts(value) if option == 'hsts' else _permissions(value) if option == 'permissions' else _csp(value)
            )
        headers[name] = value
    return headers


def _hsts(hsts: dict[str, Any]) -> str:
    value = f'max-age={int(hsts.get("max_age", 31536000))}'
    if hsts.get('include_subdomains'):
        value += '; includeSubDomains'
    if hsts.get('preload'):
        value += '; preload'
    return value


def _options(conf: dict[str, Any]) -> dict[str, Any]:
    if unknown := sorted(set(conf) - set(_HEADERS)):
        raise Pyjo.Exception.new(f'Unknown option of SecurityHeaders: {unknown[0]}')
    return conf


def _permissions(policy: dict[str, list[str] | str]) -> str:
    # The allowlists of the structured fields of RFC 8941, as (self "https://example.com"), or * for every origin
    features: list[str] = []
    for feature, origins in policy.items():
        if isinstance(origins, str):
            origins = [origins]
        if origins == ['*']:
            features.append(f'{feature}=*')
            continue
        tokens = [o.strip("'") if o.strip("'") in ('self', 'src') else f'"{o}"' for o in origins]
        features.append(f'{feature}=({" ".join(tokens)})')
    return ', '.join(features)


def _secure(c: 'Pyjoyment.Controller.object') -> bool:
    # Not for localhost, whose servers on every port a browser would take for ones of HTTPS only
    req = c.req
    if not req.is_secure:
        return False
    host = (req.url.to_abs().host or '').lower()
    return host != 'localhost' and not host.endswith('.localhost')


new = Pyjoyment_Plugin_SecurityHeaders.new
object = Pyjoyment_Plugin_SecurityHeaders
SecurityHeaders = Pyjoyment_Plugin_SecurityHeaders
