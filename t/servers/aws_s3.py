import Pyjo.IOLoop
import Pyjo.Reactor.Asyncio
import Pyjo.Server.Daemon
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.File import curfile
from Pyjo.Test import *
from Pyjo.Util import xml_escape

import importlib.util
import os
import sys


# The asynchronous AWS SDK of the example, of the dependency group "servers": uv run --only-group servers python -m
# Pyjo.Prove t/servers
if not importlib.util.find_spec('aiobotocore'):
    plan(skip_all='needs the dependency group "servers", without aiobotocore')

# aiobotocore runs on the event loop of asyncio, which Pyjo.Reactor.Poll does not run
if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
    plan(skip_all='needs Pyjo.Reactor.Asyncio, as aiobotocore runs on asyncio')

EXAMPLE = curfile().dirname().dirname().sibling('examples', 'aws', 's3.py')

# The objects of the bucket, in the place of S3, as a test does not request remote hosts
OBJECTS = {
    'big.bin': ('application/octet-stream', os.urandom(1024 * 1024)),
    'docs/a b.txt': ('text/plain', b'A file with a space'),
    'docs/empty.txt': ('text/plain', b''),
    'docs/sub/x.txt': ('text/plain', b'X'),
    'folder/': ('application/x-directory', b''),
    'site/index.html': ('text/html', b'<p>The index</p>'),
    'site/page.html': ('text/html', b'<p>A page</p>'),
}

# The part of the API of S3 that the example uses, ListObjectsV2 and GetObject, with the addressing of a path
s3 = Pyjoyment.new()


@s3.routes.get('/:bucket')
def list_objects(c):
    prefix = c.param('prefix') or ''
    delimiter = c.param('delimiter') or ''
    entries = {}
    for key in sorted(OBJECTS):
        if not key.startswith(prefix):
            continue
        rest = key.removeprefix(prefix)
        if delimiter and delimiter in rest:
            entries[prefix + rest.split(delimiter)[0] + delimiter] = 'prefix'
        else:
            entries[key] = 'key'
    start = int(c.param('continuation-token') or 0)
    end = start + int(c.param('max-keys') or 1000)
    page = list(entries.items())[start:end]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">')
    xml.append(f'<Name>{c.param("bucket")}</Name><Prefix>{xml_escape(prefix)}</Prefix><KeyCount>{len(page)}</KeyCount>')
    xml.append(f'<IsTruncated>{"true" if end < len(entries) else "false"}</IsTruncated>')
    if end < len(entries):
        xml.append(f'<NextContinuationToken>{end}</NextContinuationToken>')
    for key, kind in page:
        if kind == 'prefix':
            xml.append(f'<CommonPrefixes><Prefix>{xml_escape(key)}</Prefix></CommonPrefixes>')
        else:
            xml.append(f'<Contents><Key>{xml_escape(key)}</Key><Size>{len(OBJECTS[key][1])}</Size></Contents>')
    xml.append('</ListBucketResult>')
    c.render(data=''.join(xml).encode(), format='xml')


@s3.routes.get('/:bucket/*key')
def get_object(c):
    if (key := c.param('key')) not in OBJECTS:
        xml = '<?xml version="1.0" encoding="UTF-8"?><Error><Code>NoSuchKey</Code></Error>'
        return c.render(data=xml.encode(), format='xml', status=404)
    type, content = OBJECTS[key]
    c.res.headers.etag = '"etag"'
    c.res.headers.last_modified = 'Fri, 30 Oct 2026 12:00:00 GMT'
    c.res.headers.content_type = type
    c.render(data=content)


with Pyjo.Server.Daemon.new(app=s3, listen=['http://127.0.0.1'], silent=True) as daemon:
    # The credentials of the SDK, without the files of the AWS CLI
    os.environ.update(
        {
            'AWS_ACCESS_KEY_ID': 'test',
            'AWS_SECRET_ACCESS_KEY': 'test',
            'AWS_CONFIG_FILE': os.devnull,
            'AWS_SHARED_CREDENTIALS_FILE': os.devnull,
        }
    )
    for name in ('AWS_ENDPOINT_URL', 'AWS_PROFILE', 'AWS_REGION', 'S3_BUCKET'):
        os.environ.pop(name, None)

    # The options of the example before its command, which it takes from sys.argv, where it leaves the command
    sys.argv[1:] = ['--bucket', 'bucket', '--endpoint-url', f'http://127.0.0.1:{daemon.start().ports()[0]}']
    sys.argv += ['--region', 'us-east-1', 'daemon', '-l', 'http://*:8080']
    t = Pyjo.Test.Pyjo.new(EXAMPLE)
    is_deeply_ok(sys.argv[1:], ['daemon', '-l', 'http://*:8080'], 'command left')
    is_ok(os.environ['S3_BUCKET'], 'bucket', 'bucket')
    is_ok(os.environ['AWS_REGION'], 'us-east-1', 'region')

    with subtest('Folders'):
        t.get_ok('/').status_is(200).text_is('h1', '/').element_count_is('li', 4)
        t.element_exists('a[href="/big.bin"]').element_exists('a[href="/docs/"]').element_exists('a[href="/folder/"]')
        t.element_exists('a[href="/site/"]').element_exists_not('a[href="../"]')
        t.get_ok('/docs/').status_is(200).text_is('h1', '/docs/').element_exists('a[href="../"]')
        t.text_is('a[href="/docs/a%20b.txt"]', 'a b.txt').text_is('a[href="/docs/sub/"]', 'sub/')
        t.get_ok('/folder/').status_is(200).element_count_is('li', 1)
        t.get_ok('/missing/').status_is(404)

    with subtest('Objects'):
        t.get_ok('/docs/a%20b.txt').status_is(200).content_type_is('text/plain').content_is('A file with a space')
        t.header_is('ETag', '"etag"').header_is('Last-Modified', 'Fri, 30 Oct 2026 12:00:00 GMT')
        t.get_ok('/docs/empty.txt').status_is(200).header_is('Content-Length', '0').content_is('')
        t.get_ok('/big.bin').status_is(200).header_is('Content-Length', str(1024 * 1024))
        ok(t.tx.res.body == OBJECTS['big.bin'][1], 'right content')
        t.head_ok('/docs/sub/x.txt').status_is(200).header_is('Content-Length', '1').content_is('')
        t.get_ok('/missing').status_is(404)

    with subtest('Index'):
        t.get_ok('/site/').status_is(200).content_type_is('text/html').content_is('<p>The index</p>')
        t.get_ok('/site/page.html').status_is(200).content_is('<p>A page</p>')

    with subtest('Folder without its slash'):
        t.get_ok('/site').status_is(302).header_is('Location', '/site/')
        t.get_ok('/docs/sub').status_is(302).header_is('Location', '/docs/sub/')

    # The client of S3 closes its connections as when the server stops
    t.app.server_stopped(daemon).wait()

done_testing()
