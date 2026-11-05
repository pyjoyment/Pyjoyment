import Pyjo.IOLoop
import Pyjo.Server.Daemon

from Pyjo.File import tempdir
from Pyjo.Test import *

import base64
import hashlib
import http.client
import os
import socket
import ssl
import struct
import sys
import threading

from unittest.mock import patch


# Clients of the standard library in a thread of their own, while the event loop of the daemon runs
def run(client):
    results = {}

    def thread():
        try:
            results['value'] = client()
        except Exception as e:
            results['error'] = e

    worker = threading.Thread(target=thread)
    worker.start()
    timer = Pyjo.IOLoop.recurring(0.05, lambda loop: worker.is_alive() or loop.stop())
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.remove(timer)
    worker.join()
    if 'error' in results:
        raise results['error']
    return results['value']


daemon = Pyjo.Server.Daemon.new(listen=['http://127.0.0.1'], silent=True)


@daemon.unsubscribe('request').on('request')
def request(daemon, tx):
    req = tx.req
    path = req.url.path.to_route()

    # WebSocket
    if tx.is_websocket:
        tx.res.code = 101
        return tx.resume()

    # Chunked content
    if path == '/chunked':
        tx.res.code = 200
        tx.res.content.write_chunk(b'Hello ').write_chunk(b'World!').write_chunk(b'')
        return tx.resume()

    # A chunk whose drain closes the connection, once it has been written, as the end of a response that cannot go on
    if path == '/close':
        tx.res.code = 200
        connection = tx.connection

        def drained(content, *args):
            if (stream := Pyjo.IOLoop.stream(connection)) is not None:
                stream.close_gracefully()

        tx.res.content.write_chunk(b'Hello', drained)
        return tx.resume()

    tx.res.code = 200
    tx.res.headers.content_type = 'text/plain'
    tx.res.body = f'{req.method} {path} {req.version} {len(req.body)}'.encode()
    tx.resume()


port = daemon.start().ports()[0]

with subtest('Keep-alive requests of http.client'):

    def client():
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        results = []
        for path in ('/one', '/two'):
            conn.request('GET', path)
            res = conn.getresponse()
            results.append((res.status, res.getheader('Server'), res.read()))
        conn.close()
        return results

    is_deeply_ok(
        run(client),
        [(200, 'Pyjoyment (Python)', b'GET /one 1.1 0'), (200, 'Pyjoyment (Python)', b'GET /two 1.1 0')],
        'two requests on one connection',
    )

with subtest('HTTP/1.0 request'):

    def client():
        with socket.create_connection(('127.0.0.1', port), timeout=10) as sock:
            sock.sendall(b'GET /old HTTP/1.0\r\n\r\n')
            response = b''
            while chunk := sock.recv(4096):
                response += chunk
        return response

    response = run(client)
    like_ok(response, rb'^HTTP/1\.1 200 OK\r\n', 'right status line')
    like_ok(response, rb'\r\n\r\nGET /old 1\.0 0$', 'right content, connection closed')

with subtest('POST request with a large body'):

    def client():
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request('POST', '/post', body=b'x' * 1000000)
        res = conn.getresponse()
        result = res.status, res.read()
        conn.close()
        return result

    is_deeply_ok(run(client), (200, b'POST /post 1.1 1000000'), 'whole body read')

with subtest('Chunked response'):

    def client():
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request('GET', '/chunked')
        res = conn.getresponse()
        result = res.getheader('Transfer-Encoding'), res.read()
        conn.close()
        return result

    is_deeply_ok(run(client), ('chunked', b'Hello World!'), 'decoded by http.client')

with subtest('Connection closed by the drain of its content'):
    errors = []
    reactor = Pyjo.IOLoop.singleton.reactor
    cb = reactor.on('error', lambda reactor, err: errors.append(str(err)))

    def client():
        with socket.create_connection(('127.0.0.1', port), timeout=10) as sock:
            sock.sendall(b'GET /close HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
            response = b''
            while chunk := sock.recv(4096):
                response += chunk
        return response

    response = run(client)
    reactor.unsubscribe('error', cb)
    like_ok(response, rb'\r\n\r\n5\r\nHello$', 'chunk written, connection closed')
    is_deeply_ok(errors, [], 'no error of the reactor')

with subtest('Concurrent connections'):

    def client():
        results = [None] * 5

        def one(i):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            conn.request('GET', f'/concurrent{i}')
            results[i] = conn.getresponse().read()
            conn.close()

        threads = [threading.Thread(target=one, args=(i,)) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results

    is_deeply_ok(run(client), [f'GET /concurrent{i} 1.1 0'.encode() for i in range(5)], 'all answered')

with subtest('WebSocket handshake of RFC 6455'):
    key = base64.b64encode(os.urandom(16)).decode()

    def client():
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request(
            'GET',
            '/ws',
            headers={
                'Upgrade': 'websocket',
                'Connection': 'Upgrade',
                'Sec-WebSocket-Key': key,
                'Sec-WebSocket-Version': '13',
            },
        )
        res = conn.getresponse()
        conn.close()
        return res.status, res.getheader('Upgrade'), res.getheader('Sec-WebSocket-Accept')

    accept = base64.b64encode(hashlib.sha1(f'{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11'.encode()).digest()).decode()
    is_deeply_ok(run(client), (101, 'websocket', accept), 'switching protocols')

if hasattr(socket, 'AF_UNIX'):
    with subtest('UNIX domain socket'):
        tmp = tempdir()
        path = tmp.child('test.sock').to_str()
        unix = Pyjo.Server.Daemon.new(listen=[f'http+unix://{path.replace("/", "%2F")}'], silent=True).start()
        unix.unsubscribe('request').on('request', request)

        def client():
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(10)
                sock.connect(path)
                sock.sendall(b'GET /unix HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
                response = b''
                while chunk := sock.recv(4096):
                    response += chunk
            return response

        like_ok(run(client), rb'\r\n\r\nGET /unix 1\.1 0$', 'right content')
        unix.stop()

with subtest('TLS of ssl'):
    certs = os.path.join(os.path.dirname(__file__), '..', '..', 'Pyjo', 'IOLoop', 'certs')
    tls = Pyjo.Server.Daemon.new(listen=['https://127.0.0.1?version=TLSv1_2'], silent=True).start()
    tls.unsubscribe('request').on('request', request)
    tls_port = tls.ports()[0]

    def client():
        context = ssl.create_default_context(cafile=os.path.join(certs, 'ca.crt'))
        conn = http.client.HTTPSConnection('127.0.0.1', tls_port, context=context, timeout=10)
        conn.request('GET', '/secure')
        res = conn.getresponse()
        version = conn.sock.version()
        result = version, res.read()
        conn.close()
        return result

    is_deeply_ok(run(client), ('TLSv1.2', b'GET /secure 1.1 0'), 'verified certificate, version of the location')
    tls.stop()

with subtest('Connection reset by the client after the request'):
    # The client resets the connection while the daemon is about to build the transaction of the request, so
    # getpeername fails
    read, reset = threading.Event(), threading.Event()
    build_tx = Pyjo.Server.Daemon.object._build_tx

    def wait_for_reset(self, id, c):
        read.set()
        reset.wait(5)
        return build_tx(self, id, c)

    def client():
        conn = socket.create_connection(('127.0.0.1', port))
        conn.sendall(b'GET /reset HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
        read.wait(5)
        conn.setsockopt(
            socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('HH' if sys.platform == 'win32' else 'ii', 1, 0)
        )
        conn.close()
        reset.set()

    errors = []
    error = Pyjo.IOLoop.singleton.reactor.on('error', lambda reactor, err: errors.append(repr(err)))
    with patch.object(Pyjo.Server.Daemon.object, '_build_tx', wait_for_reset):
        run(client)
    Pyjo.IOLoop.singleton.reactor.unsubscribe('error', error)
    ok(read.is_set(), 'request read')
    is_deeply_ok(errors, [], 'no error of the reactor')

with subtest('Context manager'):
    with (
        Pyjo.IOLoop.new() as loop,
        Pyjo.Server.Daemon.new(ioloop=loop, listen=['http://127.0.0.1'], silent=True) as daemon,
    ):
        port = daemon.start().ports()[0]
        socket.create_connection(('127.0.0.1', port)).close()
    throws_ok(
        lambda: socket.create_connection(('127.0.0.1', port)),
        ConnectionRefusedError,
        'listen socket closed at the end of the block',
    )

with subtest('close'):
    with Pyjo.IOLoop.new() as loop:
        daemon = Pyjo.Server.Daemon.new(ioloop=loop, listen=['http://127.0.0.1'], silent=True)
        port = daemon.start().ports()[0]
        socket.create_connection(('127.0.0.1', port)).close()
        daemon.close()
        throws_ok(lambda: socket.create_connection(('127.0.0.1', port)), ConnectionRefusedError, 'listen socket closed')

done_testing()
