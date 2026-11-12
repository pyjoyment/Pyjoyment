import os


os.environ['PYJO_MODE'] = 'development'

import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Test.Pyjo

from Pyjo.Test import *
from Pyjoyment.Lite import app, get


# Not in Mojolicious: an action that is a coroutine function is cancelled where it waits when its connection closes
# before its response ends, with the request of the user agent that it waits for


# A reactor whose run_coroutine cannot cancel a coroutine returns None, and leaves such an action running to its end
async def probe():
    pass


if Pyjo.IOLoop.singleton.reactor.run_coroutine(probe(), lambda value: None, lambda e: None) is None:
    plan(skip_all='the reactor cannot cancel a coroutine')

app.log.level = 'fatal'

events = []


@get('/upstream')
async def upstream(c):
    try:
        await Pyjo.Promise.timer(5)
    finally:
        events.append('upstream cancelled')
    c.render(text='late')


@get('/redirect')
def redirect(c):
    c.redirect_to('/upstream')


@get('/slow')
async def slow(c):
    try:
        tx = await c.ua().get_p('/upstream')
        c.render(text=tx.result.text)
    finally:
        events.append('action ended')


@get('/rendered')
async def rendered(c):
    c.render(text='early')
    await Pyjo.Promise.timer(0.05)
    events.append('after the response')


@get('/events')
async def stream(c):
    c.res.headers.content_type = 'text/event-stream'
    c.write_sse({'text': 'first'})
    try:
        while True:
            await Pyjo.Promise.timer(5)
            c.write_sse({'text': 'next'})
    finally:
        events.append('stream cancelled')


def settle():
    # The events of the server after the client has closed its connection
    Pyjo.Promise.timer(0.1).wait()


t = Pyjo.Test.Pyjo.new()
t.ua.inactivity_timeout = 0.2

with subtest('Connection closed while the action waits'):
    events.clear()
    with app.log.capture('error') as logs:
        tx = t.ua.get('/slow')
        settle()
    is_ok(tx.error, {'message': 'Inactivity timeout'}, 'client gave up')
    is_deeply_ok(sorted(events), ['action ended', 'upstream cancelled'], 'action and its request cancelled')
    is_deeply_ok(list(logs), [], 'no exception')

with subtest('Not after the response'):
    events.clear()
    t.get_ok('/rendered').status_is(200).content_is('early')
    settle()
    is_deeply_ok(events, ['after the response'], 'the action goes on')

with subtest('A stream whose client has gone'):
    events.clear()
    tx = t.ua.get('/events')
    settle()
    is_ok(tx.res.code, 200, 'stream started')
    is_deeply_ok(events, ['stream cancelled'], 'cancelled')

with subtest('A request after a redirect'):
    events.clear()
    t.ua.max_redirects = 1
    promise = t.ua.get_p('/redirect')
    Pyjo.IOLoop.timer(0.05, lambda loop: promise.cancel())
    reason = []
    promise.catch(reason.append).wait()
    settle()
    t.ua.max_redirects = 0
    is_deeply_ok(reason, ['Request cancelled'], 'rejected')
    is_deeply_ok(events, ['upstream cancelled'], 'the request of the redirect closed')

t.close()

done_testing()
