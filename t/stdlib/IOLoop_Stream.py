import Pyjo.IOLoop
import Pyjo.IOLoop.Stream
import Pyjo.IOLoop.TLS
import Pyjo.Reactor.Poll

from Pyjo.Test import *

import errno
import gc
import os
import socket
import ssl
import sys


with subtest('A pipe'):
    # select of Windows, which the reactors use there, watches sockets only
    if sys.platform == 'win32':
        skip('no pipes in the event loop on Windows', 1)
    else:
        r, w = os.pipe()
        reader = Pyjo.IOLoop.Stream.new(os.fdopen(r, 'rb', buffering=0))
        writer = Pyjo.IOLoop.Stream.new(os.fdopen(w, 'wb', buffering=0))
        got = []

        def read(stream, chunk):
            got.append(chunk)
            writer.close()

        reader.on('read', read)
        reader.on('close', lambda stream: Pyjo.IOLoop.stop())
        reader.start()
        writer.start()
        writer.write(b'through a pipe')
        Pyjo.IOLoop.start()
        is_deeply_ok(got, [b'through a pipe'], 'os.read and os.write')

with subtest('A closed peer'):
    a, b = socket.socketpair()
    stream = Pyjo.IOLoop.Stream.new(a)
    closed = []
    stream.on('close', lambda stream: closed.append(True) or Pyjo.IOLoop.stop())
    stream.start()
    b.close()
    Pyjo.IOLoop.start()
    is_deeply_ok(closed, [True], 'closed')
    is_ok(a.fileno(), -1, 'the socket is closed too')

with subtest('A connection that the peer aborted'):
    # As a read of Windows after a write to a peer that has closed the socket, WSAECONNABORTED
    class Aborted(socket.socket):
        def recv(self, *args):
            raise ConnectionAbortedError(errno.ECONNABORTED, 'Software caused connection abort')

    a, b = socket.socketpair()
    stream = Pyjo.IOLoop.Stream.new(Aborted(fileno=a.detach()))
    closed, errors = [], []
    stream.on('error', lambda stream, err: errors.append(err))
    stream.on('close', lambda stream: closed.append(True) or Pyjo.IOLoop.stop())
    stream.start()
    b.send(b'readable')
    Pyjo.IOLoop.timer(5, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()
    is_deeply_ok(closed, [True], 'closed')
    is_deeply_ok(errors, [], 'without an error')
    b.close()

with subtest('An error'):
    a, b = socket.socketpair()
    stream = Pyjo.IOLoop.Stream.new(a)
    errors = []
    stream.on('error', lambda stream, err: errors.append(err))
    stream.on('close', lambda stream: Pyjo.IOLoop.stop())
    stream.start()
    a.shutdown(socket.SHUT_RD)
    b.close()
    Pyjo.IOLoop.timer(1, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()
    ok(all(isinstance(e, OSError) for e in errors), 'errors are OSError')

with subtest('TLS'):
    certs = os.path.dirname(Pyjo.IOLoop.TLS.CERT)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(Pyjo.IOLoop.TLS.CERT, Pyjo.IOLoop.TLS.KEY)
    client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_context.load_verify_locations(os.path.join(certs, 'ca.crt'))
    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)
    server = context.wrap_socket(a, server_side=True, do_handshake_on_connect=False)
    client = client_context.wrap_socket(b, server_hostname='localhost', do_handshake_on_connect=False)
    for _ in range(100):
        done = 0
        for s in (server, client):
            try:
                s.do_handshake()
                done += 1
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                pass
        if done == 2:
            break
    ok(done == 2, 'verified with the CA of the tests, for localhost')
    got = []
    stream = Pyjo.IOLoop.Stream.new(server)
    stream.on('read', lambda stream, chunk: got.append(chunk) or Pyjo.IOLoop.stop())
    stream.start()
    other = Pyjo.IOLoop.Stream.new(client)
    other.start()
    other.write(b'secret')
    Pyjo.IOLoop.timer(5, lambda loop: Pyjo.IOLoop.stop())
    Pyjo.IOLoop.start()
    is_deeply_ok(got, [b'secret'], 'ssl.SSLSocket')
    stream.close()
    other.close()

with subtest('Context manager'):
    a, b = socket.socketpair()
    with Pyjo.IOLoop.Stream.new(a) as stream:
        is_ok(stream.handle, a, 'handle')
    is_ok(a.fileno(), -1, 'stream closed at the end of the block')
    b.close()

with subtest('Reactor that is gone'):
    a, b = socket.socketpair()
    reactor = Pyjo.Reactor.Poll.new()
    stream = Pyjo.IOLoop.Stream.new(a)
    stream.reactor = reactor
    del reactor
    gc.collect()
    stream.close()
    is_ok(a.fileno(), -1, 'handle closed')
    b.close()

done_testing()
