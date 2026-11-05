import Pyjo.IOLoop
import Pyjo.Reactor.Asyncio
import Pyjo.UserAgent

from Pyjo.Test import *

import asyncio
import gzip
import http.server
import json
import os
import socket
import ssl
import struct
import sys
import threading

from http.cookies import SimpleCookie
from unittest.mock import patch
from urllib.parse import urlsplit


# A server of http.server in a thread of its own, as the other end of the user agent
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = self.path
        if path == '/chunked':
            self.send_response(200)
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
            for chunk in (b'Hello ', b'World!', b''):
                self.wfile.write(f'{len(chunk):x}\r\n'.encode() + chunk + b'\r\n')
            return
        if path == '/gzip':
            body = gzip.compress(b'Hello gzip!')
            self.send_response(200)
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/target?from=redirect')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if path == '/cookie':
            cookie = SimpleCookie()
            cookie['session'] = 'abc'
            cookie['session']['path'] = '/'
            self.send_response(200)
            self.send_header('Set-Cookie', cookie['session'].OutputString())
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self._answer()

    def do_POST(self):
        self._answer()

    def _answer(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = json.dumps(
            {
                'method': self.command,
                'path': self.path,
                'body': self.rfile.read(length).decode(),
                'cookie': self.headers.get('Cookie'),
                'port': self.client_address[1],
            }
        ).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(context=None):
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    if context is not None:
        server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


server = serve()
url = f'http://127.0.0.1:{server.server_address[1]}'
ua = Pyjo.UserAgent.new()

with subtest('Keep-alive with http.server'):
    tx = ua.get(f'{url}/one')
    is_ok(tx.res.json()['path'], '/one', 'right path')
    port = tx.res.json()['port']
    tx = ua.get(f'{url}/two')
    ok(tx.kept_alive, 'kept alive')
    is_ok(tx.res.json()['port'], port, 'same connection')

with subtest('Chunked response'):
    tx = ua.get(f'{url}/chunked')
    is_ok(tx.res.headers.content_length, '12', 'the length of the content in place of the chunks')
    is_ok(tx.res.body, b'Hello World!', 'right content')

with subtest('Compressed response of gzip'):
    tx = ua.get(f'{url}/gzip')
    is_ok(tx.res.body, b'Hello gzip!', 'decompressed')

with subtest('Redirect'):
    ua.max_redirects = 1
    tx = ua.get(f'{url}/redirect')
    ua.max_redirects = 0
    is_ok(tx.res.json()['path'], '/target?from=redirect', 'followed')
    is_ok(tx.previous.res.code, 302, 'right status of the redirect')

with subtest('Cookie of http.cookies'):
    ua.get(f'{url}/cookie')
    tx = ua.get(f'{url}/after')
    is_ok(tx.res.json()['cookie'], 'session=abc', 'sent back')

with subtest('Form and JSON'):
    tx = ua.post(f'{url}/form', form={'a': ['b', 'c']})
    is_ok(tx.res.json()['body'], 'a=b&a=c', 'form')
    tx = ua.post(f'{url}/json', json={'a': [1, 2]})
    is_deeply_ok(json.loads(tx.res.json()['body']), {'a': [1, 2]}, 'JSON')

with subtest('URL of urllib.parse'):
    tx = ua.get(urlsplit(f'{url}/split?x=1'))
    is_ok(tx.res.json()['path'], '/split?x=1', 'right path')

with subtest('Non-blocking with the event loop'):
    results = []

    def cb(ua, tx):
        results.append(tx.res.json()['path'])
        Pyjo.IOLoop.stop()

    ua.get(f'{url}/nb', cb)
    Pyjo.IOLoop.start()
    is_deeply_ok(results, ['/nb'], 'right path')

with subtest('A callback as a keyword argument'):
    results = []

    def cb(ua, tx):
        results.append(tx.res.json()['body'])
        Pyjo.IOLoop.stop()

    ua.post(f'{url}/form', form={'a': 'b'}, cb=cb)
    Pyjo.IOLoop.start()
    is_deeply_ok(results, ['a=b'], 'non-blocking')
    throws_ok(lambda: ua.get(f'{url}/nb', cb, cb=cb), TypeError, 'not twice')

    def handshake(ua, tx):
        results.append(tx.is_websocket)
        Pyjo.IOLoop.stop()

    isa_ok(ua.websocket(f'{url}/ws', cb=handshake), str, 'id of the WebSocket connection')
    Pyjo.IOLoop.start()
    is_deeply_ok(results, ['a=b', False], 'no WebSocket with http.server')
    throws_ok(lambda: ua.websocket(f'{url}/ws', handshake, cb=handshake), TypeError, 'not twice')

    @ua.websocket(f'{url}/ws')
    def ws(ua, tx):
        Pyjo.IOLoop.stop()

    isa_ok(ws, str, 'the decorated name is the id of the connection')
    Pyjo.IOLoop.start()

with subtest('Blocking request in a running event loop of asyncio'):
    # The asyncio reactor, whatever PYJO_REACTOR says, as the event loop of asyncio runs the requests
    reactor = Pyjo.IOLoop.singleton.reactor
    Pyjo.IOLoop.singleton.reactor = Pyjo.Reactor.Asyncio.new()

    async def blocking():
        ioloop = Pyjo.IOLoop.new(reactor=Pyjo.Reactor.Asyncio.new())
        with Pyjo.UserAgent.new(ioloop=ioloop) as ua:
            running = ioloop.is_running
            try:
                ua.get(f'{url}/blocking')
            except RuntimeError as e:
                return running, str(e)

    # A SelectorEventLoop, as the ProactorEventLoop that asyncio.run makes on Windows cannot watch handles
    running, error = asyncio.run(blocking(), loop_factory=asyncio.SelectorEventLoop)
    ok(running, 'the event loop of the user agent runs')
    like_ok(error, r'^Blocking request in a running event loop, await a promise of a request', 'right error')

    async def awaited():
        with Pyjo.UserAgent.new() as ua:
            return await ua.get_p(f'{url}/awaited')

    tx = asyncio.run(awaited(), loop_factory=asyncio.SelectorEventLoop)
    is_ok(tx.res.json()['path'], '/awaited', 'awaited request')
    Pyjo.IOLoop.singleton.reactor = reactor

with subtest('TLS of ssl'):
    certs = os.path.join(os.path.dirname(__file__), '..', 'certs')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(os.path.join(certs, 'server.crt'), os.path.join(certs, 'server.key'))
    tls = serve(context)
    ua = Pyjo.UserAgent.new(ca=os.path.join(certs, 'ca.crt'))
    tx = ua.get(f'https://127.0.0.1:{tls.server_address[1]}/secure')
    ok(not tx.error, 'verified')
    is_ok(tx.res.json()['path'], '/secure', 'right path')
    ua = Pyjo.UserAgent.new()
    tx = ua.get(f'https://127.0.0.1:{tls.server_address[1]}/secure')
    like_ok(tx.error['message'], r'certificate verify failed', 'not verified without the CA')
    tls.shutdown()
    tls.server_close()

server.shutdown()
server.server_close()

with subtest('Connection reset by the server before the request'):
    # The server resets the connection while the user agent is about to send the request, as a server of TLS 1.3 that
    # rejects the certificate of the client after the handshake of the client, so getpeername fails
    listener = socket.create_server(('127.0.0.1', 0))
    connected, reset = threading.Event(), threading.Event()

    def server_thread():
        conn, _ = listener.accept()
        connected.wait(5)
        conn.setsockopt(
            socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('HH' if sys.platform == 'win32' else 'ii', 1, 0)
        )
        conn.close()
        reset.set()

    thread = threading.Thread(target=server_thread)
    thread.start()
    process = Pyjo.UserAgent.object._process

    def wait_for_reset(self, id):
        connected.set()
        reset.wait(5)
        process(self, id)

    ua = Pyjo.UserAgent.new()
    errors = []
    ua.ioloop.reactor.on('error', lambda reactor, err: errors.append(repr(err)))
    with patch.object(Pyjo.UserAgent.object, '_process', wait_for_reset):
        tx = ua.get(f'http://127.0.0.1:{listener.getsockname()[1]}/')
    thread.join()
    listener.close()
    ok(tx.error, 'error of the transaction')
    is_deeply_ok(errors, [], 'no error of the reactor')
    ua.close()

with subtest('Context manager'):
    with Pyjo.UserAgent.new() as ua:
        port = ua.server.url().port
        socket.create_connection(('127.0.0.1', port)).close()
    throws_ok(lambda: socket.create_connection(('127.0.0.1', port)), ConnectionRefusedError, 'server closed at the end')

with subtest('close'):
    ua = Pyjo.UserAgent.new()
    port = ua.server.url().port
    socket.create_connection(('127.0.0.1', port)).close()
    ua.close()
    throws_ok(lambda: socket.create_connection(('127.0.0.1', port)), ConnectionRefusedError, 'server closed')

done_testing()
