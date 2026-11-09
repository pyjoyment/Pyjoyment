"""
Invoke the emulator of the Runtime API of AWS Lambda with the event of a file,
until it answers, and check that the response is the welcome page, as a
response of an event function, or with --stream as a streaming response of an
HTTP integration: the status of its prelude, 8 null bytes and the page, as the
emulator gives the content type application/octet-stream to every stream.
Its exit status tells whether it is, and the test point is the one of
invoke_event of lib.sh.

Usage: python invoke.py [--stream] URL EVENT.json
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request


args = sys.argv[1:]
stream = args[:1] == ['--stream']
url, path = args[1:] if stream else args
name = os.path.basename(path)
with open(path, 'rb') as f:
    event = f.read()

body = content_type = None
for _ in range(60):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=event), timeout=30) as res:
            body, content_type = res.read(), res.headers.get('Content-Type')
        break
    except (urllib.error.URLError, ConnectionError):
        time.sleep(0.5)

welcome = 'Welcome to the Pyjoyment real-time web framework!'
if stream:
    prelude, delimiter, page = (body or b'').partition(b'\x00' * 8)
    try:
        status = json.loads(prelude).get('statusCode')
    except ValueError:
        status = None
    ok = delimiter and status == 200
    ok = ok and welcome in page.decode('utf-8', 'replace')
    response = (content_type, body[:200] if body else body)
else:
    response = json.loads(body) if body else None
    ok = isinstance(response, dict) and response.get('statusCode') == 200 and not response.get('isBase64Encoded')
    ok = ok and welcome in response.get('body', '')
if not ok:
    print(f'invoke with {name}: {response}', file=sys.stderr)
    sys.exit(1)
