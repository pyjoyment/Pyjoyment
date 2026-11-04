import Pyjo
import Pyjoyment

import os
import sys
import tomllib


# python -m Pyjo for the one-liners of the guides, whose remote services an application in the process of the one-liner
# answers, as the tests do not use the network: the user agent of the functions requests its own server, with the host
# of the remote service as the Host header
with open(os.path.join(os.path.dirname(__file__), '..', '..', 'pyproject.toml'), 'rb') as f:
    PROJECT = tomllib.load(f)['project']

EXAMPLE = """<!doctype html><html lang=en><head><meta charset=utf-8><title>Example Domain</title></head><body>
<p>This domain is for use in documentation examples without needing permission.</p></body></html>
"""

# The signature of a PNG file, whose CRLF and LF a write in text mode on Windows would change
PNG = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'

MOJOLICIOUS = '<html><head><title>Mojolicious - Perl real-time web framework</title></head><body></body></html>'

mock = Pyjoyment.new()
mock.log.level = 'fatal'


@mock.routes.any('/*rest', {'rest': ''})
def remote(c):
    host, path = c.req.headers.host, c.req.url.path.to_str()
    if host == 'example.com' and path == '/':
        return c.render(data=EXAMPLE.encode(), format='html')
    if host == 'mojolicious.org' and path == '/':
        return c.render(data=MOJOLICIOUS.encode(), format='html')
    if host == 'mojolicious.org' and path == '/mojo/logo-white.png':
        return c.render(data=PNG, format='png')
    if host == 'pypi.org' and path == '/pypi/Pyjoyment/json':
        info = {
            'name': PROJECT['name'],
            'requires_python': PROJECT['requires-python'],
            'project_urls': dict(sorted(PROJECT['urls'].items())),
        }
        return c.render(json={'info': info})
    if host == 'httpbin.org' and path == '/post':
        return c.render(json={'json': c.req.json()})
    c.render(text='Not Found', status=404)


def prepare(ua, tx):
    url = tx.req.url
    if url.is_abs:
        tx.req.headers.host = url.host
        url.scheme = url.host = url.port = None


def setup():
    ua = Pyjo._ua()
    ua.server.app = mock
    ua.on('prepare', prepare)


def main(argv):
    # Not imported by sitecustomize, before python -m Pyjo runs it
    import Pyjo.__main__

    setup()
    Pyjo.__main__.main(argv)


# A one-liner with its code, and without it a helper module, which the harness runs as every file of t
if __name__ == '__main__':
    if sys.argv[1:]:
        main(sys.argv[1:])
    else:
        from Pyjo.Test import plan

        plan(skip_all='helper module, not a test')
