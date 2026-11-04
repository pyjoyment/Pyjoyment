import Pyjo.IOLoop
import Pyjo.Reactor.Asyncio
import Pyjo.Server.ASGI

from Pyjo.Test import *

import asyncio
import importlib
import os
import sys


# Pyjo.Server.ASGI needs a reactor that runs in the loop of the ASGI server, which Pyjo.Reactor.Poll, with a loop of its
# own, does not
if not isinstance(Pyjo.IOLoop.singleton.reactor, Pyjo.Reactor.Asyncio.object):
    plan(skip_all='needs Pyjo.Reactor.Asyncio, which runs in the loop of the ASGI server')

# The ASGI server of the tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
ASGIClient = importlib.import_module('ASGIClient')

asgi = Pyjo.Server.ASGI.new()
asgi.unsubscribe('request')


@asgi.on('request')
def request(asgi, tx):
    def respond(loop):
        tx.res.code = 200
        tx.res.body = str(tx.req.url.path).encode()
        tx.resume()

    Pyjo.IOLoop.timer(float(tx.req.param('wait') or 0), respond)


app = asgi.to_asgi_app()

with subtest('Concurrent requests with asyncio.gather'):

    async def main():
        order = []

        async def get(path, wait):
            sent = await ASGIClient.call(app, *ASGIClient.http('GET', path, f'wait={wait}'.encode()))
            order.append(ASGIClient.response(sent)[2])

        await asyncio.gather(get('/slow', 0.2), get('/fast', 0.01))
        return order

    is_deeply_ok(asyncio.run(main()), [b'/fast', b'/slow'], 'timers of Pyjoyment run in the loop of asyncio')

with subtest('Messages through asyncio.Queue'):

    async def main():
        incoming, outgoing = asyncio.Queue(), asyncio.Queue()
        scope, messages = ASGIClient.http('POST', '/queue', body=b'Hello', headers=[(b'content-length', b'5')])
        task = asyncio.create_task(app(scope, incoming.get, outgoing.put))
        for message in messages:
            await incoming.put(message)
        await task
        sent = []
        while not outgoing.empty():
            sent.append(outgoing.get_nowait())
        return ASGIClient.response(sent)

    status, headers, body = asyncio.run(main())
    is_ok(status, 200, 'right status')
    is_ok(body, b'/queue', 'right content')

with subtest('Timeout of asyncio.wait_for'):

    async def main():
        try:
            await asyncio.wait_for(ASGIClient.call(app, *ASGIClient.http('GET', '/', b'wait=5')), 0.1)
        except TimeoutError:
            return 'timeout'

    is_ok(asyncio.run(main()), 'timeout', 'cancelled while waiting for the response')

done_testing()
