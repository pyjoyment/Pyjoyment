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

# The promises of the actions that have started, which the client closes its connection after, whatever time they take
started: dict[str, Pyjo.Promise.object] = {}


def when(name):
    promise = started[name] = Pyjo.Promise.new()
    return promise


def signal(name):
    if (promise := started.pop(name, None)) is not None:
        promise.resolve()


@get('/upstream')
async def upstream(c):
    signal('upstream')
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


@get('/wait')
async def wait(c):
    try:
        await Pyjo.Promise.timer(5)
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
    signal('stream')
    try:
        while True:
            await Pyjo.Promise.timer(5)
            c.write_sse({'text': 'next'})
    finally:
        events.append('stream cancelled')


def gone(path, name):
    # A request whose client goes away once the action has started
    client = t.ua.get_p(path)

    # Not a lambda, whose value would be the promise that cancel returns, which then would adopt its rejection
    def leave(*values):
        client.cancel()

    when(name).then(leave)
    reason = []
    client.catch(reason.append).wait()
    settle()
    return reason


def settle():
    # The events of the server after the client has closed its connection
    Pyjo.Promise.timer(0.1).wait()


t = Pyjo.Test.Pyjo.new()

with subtest('Connection closed while the action waits'):
    events.clear()
    with app.log.capture('error') as logs:
        reason = gone('/slow', 'upstream')
    is_deeply_ok(reason, ['Request cancelled'], 'client gone')
    is_deeply_ok(sorted(events), ['action ended', 'upstream cancelled'], 'action and its request cancelled')
    is_deeply_ok(list(logs), [], 'no exception')

with subtest('Inactivity timeout of the client'):
    events.clear()
    t.ua.inactivity_timeout = 0.5
    tx = t.ua.get('/wait')
    settle()
    t.ua.inactivity_timeout = 40
    is_ok(tx.error, {'message': 'Inactivity timeout'}, 'client gave up')
    is_deeply_ok(events, ['action ended'], 'action cancelled')

with subtest('Not after the response'):
    events.clear()
    t.get_ok('/rendered').status_is(200).content_is('early')
    settle()
    is_deeply_ok(events, ['after the response'], 'the action goes on')

with subtest('A stream whose client has gone'):
    events.clear()
    reason = gone('/events', 'stream')
    is_deeply_ok(reason, ['Request cancelled'], 'client gone')
    is_deeply_ok(events, ['stream cancelled'], 'cancelled')

with subtest('A request after a redirect'):
    events.clear()
    t.ua.max_redirects = 1
    reason = gone('/redirect', 'upstream')
    t.ua.max_redirects = 0
    is_deeply_ok(reason, ['Request cancelled'], 'rejected')
    is_deeply_ok(events, ['upstream cancelled'], 'the request of the redirect closed')

t.close()

done_testing()
