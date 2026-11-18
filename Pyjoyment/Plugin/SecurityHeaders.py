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

``max_report_size`` ::

    app.plugin('SecurityHeaders', reports='/csp-reports', max_report_size=16384)

    Largest body of a request to the route of ``reports``, in bytes, defaults
    to ``65536``, 64 KiB. A larger one gets ``413 Request Entity Too
    Large``.

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

``reports`` ::

    app.plugin('SecurityHeaders', reports='/csp-reports', csp_report_only={'default-src': ["'self'"]})

    The path of a route, named ``csp_reports``, that takes the reports of
    the violations of the policies, defaults to ``None``. The policies of
    ``csp`` and ``csp_report_only`` of a dict without ``report-uri`` or
    ``report-to`` get both, ``report-uri`` for the browsers without the
    Reporting API, and the responses ``Reporting-Endpoints``, as
    ``csp="/csp-reports"``, which a browser takes from a page of HTTPS only,
    with the prefix of an application that is mounted. The route takes the
    reports of both, as ``application/csp-report`` and
    ``application/reports+json``, logs each violation with ``warn``, emits
    the hook ``csp_report``, and answers ``204 No Content``.

    The route is public and takes the reports of any client, so a report is
    what a client says, not what a browser has seen: its values are cut in
    the log, and an application that stores the reports limits how many.

``resource_policy`` ::

    app.plugin('SecurityHeaders', resource_policy='same-site')

    ``Cross-Origin-Resource-Policy``, defaults to ``None``, as a resource of
    the application that other sites load, as an image of a CDN, would be
    blocked.

Hooks
-----

:mod:`Pyjoyment.Plugin.SecurityHeaders` emits the following hooks.

``csp_report`` ::

    @app.hook('csp_report')
    def csp_report(c, report):
        c.app.log.info(f'{report["effectiveDirective"]} blocked {report["blockedURL"]}')

    Emitted for each violation of a request to the route of ``reports``,
    with the controller and the violation, as the body of a report of the
    Reporting API has it, with ``documentURL``, ``blockedURL``,
    ``effectiveDirective``, ``disposition`` and the others, also for a
    report of ``report-uri``, whose fields it renames.

Helpers
-------

:mod:`Pyjoyment.Plugin.SecurityHeaders` implements the following helpers.

``csp_nonce`` ::

    nonce = c.csp_nonce()

    %= javascript(begin
      hljs.highlightAll();
    %= end)
    <script nonce="<%= csp_nonce() %>">hljs.highlightAll();</script>

    The nonce of the response, 128 random bits, made when it is first used,
    which the hook adds to the directives ``default-src``, ``script-src``,
    ``script-src-elem``, ``style-src`` and ``style-src-elem`` that the
    policies of ``csp`` and ``csp_report_only`` have, so that the scripts and
    the styles of the response with that nonce run, and the ones that an
    attacker would inject do not. The helpers ``javascript`` and
    ``stylesheet`` of :mod:`Pyjoyment.Plugin.TagHelpers` give it to their
    inline scripts and styles, as the bundled templates use them. A script of
    a URL needs no nonce with a source as ``'self'``; with
    ``'strict-dynamic'``, it gets one with ``javascript('/app.js',
    nonce=c.csp_nonce())``. A nonce has no effect on the ``style``
    attributes, which a policy of the styles blocks.

    A response whose policy has the nonce gets ``Cache-Control: private``,
    unless it has a ``Cache-Control`` already, as a shared cache, as a CDN,
    would give the same nonce to every client, which would no longer be a
    secret. A page that a CDN keeps is better without inline scripts and
    styles, with a policy of their sources alone.

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

import base64
import re
import secrets

from typing import TYPE_CHECKING, Any, cast


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
# The directives of the scripts and the styles, and the default one of both, which the nonce goes into
_NONCE_DIRECTIVES = ('default-src', 'script-src', 'script-src-elem', 'style-src', 'style-src-elem')
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

        Register the hook and the helper in :mod:`Pyjoyment` application.
        """
        conf = _options(conf or {})
        path: str | None = conf.pop('reports', None)
        max_size: int = conf.pop('max_report_size', 65536)
        options = {**_DEFAULTS, **conf}
        headers = _headers(options)

        def after_dispatch(c: 'Pyjoyment.Controller.object') -> None:
            # An unknown option of the stash is logged, as the response has been rendered already
            values, nonced = headers, False
            stash = c.stash()
            own: dict[str, Any] = stash.get('security_headers') or {}
            if own or 'security_headers.nonce' in stash or path is not None:
                if unknown := sorted(set(own) - set(_HEADERS)):
                    c.helpers.log().error(f'Unknown option of SecurityHeaders: {unknown[0]}')
                # The endpoint of the reports with the prefix of an application that is mounted
                url = str(c.url_for('csp_reports')) if path is not None else None
                current = _reports({**options, **{k: v for k, v in own.items() if k in _HEADERS}}, url)
                current, nonced = _nonce(current, stash.get('security_headers.nonce'))
                values = _headers(current, url)

            res_headers = c.res.headers
            for name, value in values.items():
                if name == 'Strict-Transport-Security' and not _secure(c):
                    continue
                if res_headers.header(name) is None:
                    res_headers.header(name, value)

            # A shared cache, as a CDN, would give the nonce of the response to every client
            if nonced and res_headers.cache_control is None:
                res_headers.cache_control = 'private'

        app.helper('csp_nonce', _csp_nonce)
        app.hook('after_dispatch', after_dispatch)

        # The reports of the violations of the policies, of report-uri and of report-to
        if path is not None:

            def csp_reports(c: 'Pyjoyment.Controller.object') -> None:
                req = c.req
                if req.body_size > max_size:
                    c.render(text='Report too large', status=413)
                    return
                if (reports := _violations(req.json())) is None:
                    c.render(text='Invalid report', status=400)
                    return
                log = c.helpers.log()
                for report in reports:
                    log.warn(_summary(report))
                    app.plugins.emit_hook('csp_report', c, report)
                c.rendered(204)

            app.routes.post(path, csp_reports, 'csp_reports')


def _csp_nonce(c: 'Pyjoyment.Controller.object') -> str:
    # A nonce of 128 random bits for each response, made when a template or an action first needs it
    stash = c.stash()
    if (nonce := stash.get('security_headers.nonce')) is None:
        nonce = stash['security_headers.nonce'] = base64.b64encode(secrets.token_bytes(16)).decode()
    return nonce


def _csp(policy: dict[str, list[str]]) -> str:
    return '; '.join(' '.join([directive, *sources]) for directive, sources in policy.items())


def _headers(options: dict[str, Any], reports: str | None = None) -> dict[str, str]:
    # The values of the headers of the options, without the ones that are left out, and the endpoint of the reports
    headers: dict[str, str] = {'Reporting-Endpoints': f'csp="{reports}"'} if reports is not None else {}
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


def _nonce(options: dict[str, Any], nonce: str | None) -> tuple[dict[str, Any], bool]:
    # The nonce in the directives of the scripts and the styles that a policy of a dict has, as a policy without them
    # restricts neither, and whether a policy has it, for the Cache-Control of the response
    if nonce is None:
        return options, False
    options = dict(options)
    nonced = False
    for option in ('csp', 'csp_report_only'):
        if isinstance(policy := options[option], dict):
            options[option] = {
                d: [*sources, f"'nonce-{nonce}'"] if d in _NONCE_DIRECTIVES else sources
                for d, sources in cast(dict[str, list[str]], policy).items()
            }
            nonced = nonced or any(d in _NONCE_DIRECTIVES for d in cast(dict[str, list[str]], policy))
    return options, nonced


def _options(conf: dict[str, Any]) -> dict[str, Any]:
    if unknown := sorted(set(conf) - set(_HEADERS) - {'max_report_size', 'reports'}):
        raise Pyjo.Exception.new(f'Unknown option of SecurityHeaders: {unknown[0]}')
    return dict(conf)


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


def _reports(options: dict[str, Any], path: str | None) -> dict[str, Any]:
    # The endpoint of the reports in the policies of a dict that name none, with report-uri for the browsers that do
    # not have report-to
    if path is None:
        return options
    options = dict(options)
    for option in ('csp', 'csp_report_only'):
        if not isinstance(policy := options[option], dict):
            continue
        directives = cast(dict[str, list[str]], policy)
        if not {'report-uri', 'report-to'} & set(directives):
            options[option] = {**directives, 'report-uri': [path], 'report-to': ['csp']}
    return options


# The fields of a report of report-uri, as the body of a report of report-to names them
_FIELDS = {
    'blocked-uri': 'blockedURL',
    'column-number': 'columnNumber',
    'disposition': 'disposition',
    'document-uri': 'documentURL',
    'effective-directive': 'effectiveDirective',
    'line-number': 'lineNumber',
    'original-policy': 'originalPolicy',
    'referrer': 'referrer',
    'script-sample': 'sample',
    'source-file': 'sourceFile',
    'status-code': 'statusCode',
}


def _summary(report: dict[str, Any]) -> str:
    # One line of the log, without the control characters and the length that a client could forge it with
    def field(name: str) -> str:
        return re.sub(r'[\x00-\x1f\x7f]', '?', str(report.get(name) or '-'))[:200]

    disposition = ' (report only)' if report.get('disposition') == 'report' else ''
    return (
        f'CSP violation of {field("effectiveDirective")}: {field("blockedURL")} in {field("documentURL")}{disposition}'
    )


def _violations(data: Any) -> list[dict[str, Any]] | None:
    # The violations of a report of report-to, a list of reports of the Reporting API, or of report-uri, an object of
    # csp-report, as the bodies of the former
    if isinstance(data, list):
        reports = cast(list[Any], data)
        if not all(isinstance(r, dict) for r in reports):
            return None
        return [
            cast(dict[str, Any], r['body'])
            for r in cast(list[dict[str, Any]], reports)
            if r.get('type') == 'csp-violation' and isinstance(r.get('body'), dict)
        ]
    if isinstance(data, dict) and isinstance(report := cast(dict[str, Any], data).get('csp-report'), dict):
        legacy = cast(dict[str, Any], report)
        violation = {_FIELDS[k]: v for k, v in legacy.items() if k in _FIELDS}
        violation.setdefault('effectiveDirective', legacy.get('violated-directive'))
        return [violation]
    return None


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
