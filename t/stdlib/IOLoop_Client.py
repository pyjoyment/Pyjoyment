import Pyjo.IOLoop
import Pyjo.IOLoop.Client

from Pyjo.Test import *

import importlib
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading


# The SOCKS5 proxy server of the tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
SocksServer = importlib.import_module('SocksServer')

CERTS = os.path.join(os.path.dirname(__file__), '..', 'certs')


def connect(**options):
    got = {'handle': None, 'err': None}
    client = Pyjo.IOLoop.Client.new()

    def connected(client, handle):
        got['handle'] = handle
        Pyjo.IOLoop.stop()

    def error(client, err):
        got['err'] = err
        Pyjo.IOLoop.stop()

    client.on('connect', connected)
    client.on('error', error)
    client.connect(**options)
    Pyjo.IOLoop.start()
    client.close()
    return got


# A server that sends a message with the port it sees the connection from, once for each connection
def serve(handler):
    listening = socket.create_server(('127.0.0.1', 0))

    def accept():
        while True:
            try:
                conn = listening.accept()[0]
            except OSError:
                return
            with conn:
                try:
                    handler(conn)
                except OSError:
                    pass

    threading.Thread(target=accept, daemon=True).start()
    return listening


def hello(conn):
    conn.sendall(f'hello {conn.getpeername()[1]}'.encode())


def receive(handle):
    handle.setblocking(True)
    handle.settimeout(10)
    with handle:
        return handle.recv(100).decode()


# A port that refuses a connection: a privileged one, which no test that runs at the same time takes, as it could take
# the port of a socket that is closed before the connection, and a socket bound without listening refuses nothing on
# macOS, where the connection times out
REFUSED = 1


with subtest('A server of the standard library'):
    listening = socket.create_server(('127.0.0.1', 0))
    port = listening.getsockname()[1]
    got = connect(port=port)
    isa_ok(got['handle'], socket.socket, 'connected')
    ok(not got['handle'].getblocking(), 'non-blocking')
    ok(got['handle'].getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY), 'TCP_NODELAY')
    listening.accept()[0].close()
    got['handle'].close()

    got = connect(address='localhost', port=port)
    isa_ok(got['handle'], socket.socket, 'by name, resolved in a thread')
    got['handle'].close()

    got = connect(port=port, source_address=('127.0.0.1', 0))
    is_ok(got['handle'].getsockname()[0], '127.0.0.1', 'from the source address')
    got['handle'].close()
    listening.close()

with subtest('Errors'):
    got = connect(port=REFUSED)
    isa_ok(got['err'], ConnectionRefusedError, 'refused')
    got = connect(address='name.invalid', port=80)
    like_ok(str(got['err']), r"^Can't resolve: ", 'unknown name')
    got = connect(port=REFUSED, socks_address='127.0.0.1')
    isa_ok(got['err'], ConnectionRefusedError, 'no SOCKS proxy')

with subtest('Blocking name resolution'):
    listening = socket.create_server(('127.0.0.1', 0))
    os.environ['PYJO_NO_NNR'] = '1'
    code = f"""
import Pyjo.IOLoop, Pyjo.IOLoop.Client
print(Pyjo.IOLoop.Client.object.can_nnr())
client = Pyjo.IOLoop.Client.new()
client.on('connect', lambda client, handle: print('connected') or Pyjo.IOLoop.stop())
client.connect(address='localhost', port={listening.getsockname()[1]})
Pyjo.IOLoop.start()
"""
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    del os.environ['PYJO_NO_NNR']
    is_ok(result.stdout, 'False\nconnected\n', 'PYJO_NO_NNR')
    listening.close()

with subtest('SOCKS5'):
    target = serve(hello)
    port = target.getsockname()[1]
    proxy = SocksServer.new()
    got = connect(port=port, socks_address='127.0.0.1', socks_port=proxy.port)
    is_ok(receive(got['handle']), f'hello {proxy.last}', 'connected through the proxy')
    got = connect(address='localhost', port=port, socks_address='127.0.0.1', socks_port=proxy.port)
    is_ok(receive(got['handle']), f'hello {proxy.last}', 'the proxy resolves the name')

    got = connect(port=REFUSED, socks_address='127.0.0.1', socks_port=proxy.port)
    is_ok(got['err'], 'Connection refused', 'the proxy cannot connect')
    proxy.close()

    proxy = SocksServer.new('foo', 'bar')
    got = connect(port=port, socks_address='127.0.0.1', socks_port=proxy.port, socks_user='foo', socks_pass='bar')
    is_ok(receive(got['handle']), f'hello {proxy.last}', 'authenticated')
    got = connect(port=port, socks_address='127.0.0.1', socks_port=proxy.port, socks_user='foo', socks_pass='baz')
    is_ok(got['err'], 'Authentication failed with SOCKS5 proxy', 'wrong password')
    got = connect(port=port, socks_address='127.0.0.1', socks_port=proxy.port)
    is_ok(got['err'], 'No valid auth mechanisms', 'no user')
    proxy.close()
    target.close()

with subtest('TLS through SOCKS5'):
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(os.path.join(CERTS, 'server.crt'), os.path.join(CERTS, 'server.key'))

    def secure(conn):
        with context.wrap_socket(conn, server_side=True) as tls:
            tls.sendall(b'secure')

    target = serve(secure)
    proxy = SocksServer.new()
    got = connect(
        address='localhost',
        port=target.getsockname()[1],
        socks_address='127.0.0.1',
        socks_port=proxy.port,
        tls=True,
        tls_ca=os.path.join(CERTS, 'ca.crt'),
    )
    isa_ok(got['handle'], ssl.SSLSocket, 'TLS')
    is_ok(receive(got['handle']), 'secure', 'verified certificate of the target')
    proxy.close()
    target.close()

with subtest('SOCKS5 protocol errors'):
    # The greeting is read, as a socket closed with data unread resets the connection
    proxy = serve(lambda conn: conn.recv(3))
    got = connect(port=80, socks_address='127.0.0.1', socks_port=proxy.getsockname()[1])
    is_ok(got['err'], 'Socket closed by remote side', 'proxy closes the connection')
    proxy.close()

    def unsupported(conn):
        conn.recv(3)
        conn.sendall(b'\x05\x00')
        conn.recv(100)
        conn.sendall(b'\x05\x00\x00\x09')

    proxy = serve(unsupported)
    got = connect(port=80, socks_address='127.0.0.1', socks_port=proxy.getsockname()[1])
    is_ok(got['err'], 'Unsupported address type returned by socks server: 9', 'unsupported address type')
    proxy.close()

with subtest('SOCKS5 support disabled'):
    code = """
import Pyjo.IOLoop, Pyjo.IOLoop.Client
print(Pyjo.IOLoop.Client.object.can_socks())
client = Pyjo.IOLoop.Client.new()
client.on('error', lambda client, err: print(err) or Pyjo.IOLoop.stop())
client.connect(port=80, socks_address='127.0.0.1', socks_port={port})
Pyjo.IOLoop.start()
"""
    proxy = SocksServer.new()
    env = dict(os.environ, PYJO_NO_SOCKS='1')
    result = subprocess.run(
        [sys.executable, '-c', code.format(port=proxy.port)], capture_output=True, text=True, env=env
    )
    is_ok(result.stdout, 'False\nSOCKS support is disabled\n', 'PYJO_NO_SOCKS')
    proxy.close()

with subtest('UNIX domain socket'):
    if not hasattr(socket, 'AF_UNIX'):
        skip('no UNIX domain sockets', 1)
    else:
        with tempfile.TemporaryDirectory() as dir:
            path = os.path.join(dir, 'test.sock')
            listening = socket.socket(socket.AF_UNIX)
            listening.bind(path)
            listening.listen()
            got = connect(path=path)
            is_ok(got['handle'].family, socket.AF_UNIX, 'connected')
            got['handle'].close()
            listening.close()

with subtest('Context manager'):
    listening = socket.create_server(('127.0.0.1', 0))
    connected = []
    with Pyjo.IOLoop.Client.new() as client:
        client.on('connect', lambda client, handle: connected.append(handle))
        client.connect(address='127.0.0.1', port=listening.getsockname()[1])
    Pyjo.IOLoop.timer(0.2, lambda loop: loop.stop())
    Pyjo.IOLoop.start()
    is_ok(connected, [], 'connection closed at the end of the block')
    listening.close()

done_testing()
