import os


os.environ['PYJO_MODE'] = 'development'

# A short inactivity timeout of the server, which a heartbeat keeps a stream from
os.environ['PYJO_INACTIVITY_TIMEOUT'] = '0.3'

import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Test.Pyjo

from Pyjo.Test import *
from Pyjo.WebSocket import WS_PING
from Pyjoyment.Lite import app, get, websocket


# Not in Mojolicious: the heartbeat of a stream, the comments of Server-Sent Events or the pings of a WebSocket, of the
# helper heartbeat or of the value heartbeat of the stash of a route, set before its first action

app.log.level = 'fatal'


async def events(c):
    c.write_sse()
    await Pyjo.Promise.timer(0.5)
    c.write_sse({'text': 'done'})
    c.finish()


get('/events', {'heartbeat': 0.1}, events)
get('/silent', events)


@get('/helper')
async def helper(c):
    c.heartbeat(0.1)
    await events(c)


@get('/stopped')
async def stopped(c):
    c.heartbeat(0.05).heartbeat(None)
    c.write_sse()
    await Pyjo.Promise.timer(0.2)
    c.write_sse({'text': 'done'})
    c.finish()


@get('/plain', {'heartbeat': 0.05})
async def plain(c):
    await Pyjo.Promise.timer(0.2)
    c.render(text='plain')


@websocket('/ws', {'heartbeat': 0.1})
def ws(c):
    c.on('message', lambda c, msg: c.send(f'echo: {msg}'))


t = Pyjo.Test.Pyjo.new()
t.ua.inactivity_timeout = 10


def raw(path):
    # The bytes of a stream, with its comments, which the user agent leaves out of its events, until its end
    async def read():
        port = t.ua.server.url().port
        stream = await Pyjo.IOLoop.client_p(address='127.0.0.1', port=port)
        await stream.write_p(f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n'.encode())
        data = b''
        async for chunk in stream:
            data += chunk
        return data.decode()

    got = []
    Pyjo.Promise.new(read()).then(got.append).wait()
    return got[0]


with subtest('Comments of a stream of events'):
    data = raw('/events')
    like_ok(data, r'Content-Type: text/event-stream', 'stream')
    cmp_ok(data.count(': heartbeat\r\n\r\n'), '>=', 2, 'comments while it waits')
    like_ok(data, r'data: done\r\n\r\n', 'the event after them, beyond the inactivity timeout of the server')

with subtest('Without a heartbeat'):
    data = raw('/silent')
    unlike_ok(data, r'heartbeat', 'no comments')
    unlike_ok(data, r'data: done', 'closed by the inactivity timeout of the server')

with subtest('Heartbeat of the helper'):
    data = raw('/helper')
    cmp_ok(data.count(': heartbeat'), '>=', 2, 'comments')
    like_ok(data, r'data: done', 'event')

with subtest('Stopped'):
    data = raw('/stopped')
    unlike_ok(data, r'heartbeat', 'no comments')
    like_ok(data, r'data: done', 'event')

with subtest('Not a stream of events'):
    t.get_ok('/plain').status_is(200).content_is('plain')

with subtest('Pings of a WebSocket'):
    pings = []
    t.websocket_ok('/ws')
    t.tx.on('frame', lambda ws, frame: pings.append(frame) if frame[4] == WS_PING else None)
    Pyjo.Promise.timer(0.5).wait()
    t.send_ok('hi').message_ok().message_is('echo: hi').finish_ok()
    cmp_ok(len(pings), '>=', 2, 'pings while it waits, which keep it open beyond the inactivity timeout')

t.close()

done_testing()
