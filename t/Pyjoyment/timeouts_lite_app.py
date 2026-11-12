import os


os.environ['PYJO_MODE'] = 'development'

# A short inactivity timeout of the server, which a route makes longer
os.environ['PYJO_INACTIVITY_TIMEOUT'] = '0.3'

import Pyjo.IOLoop
import Pyjo.Promise
import Pyjo.Test.Pyjo

from Pyjo.Test import *
from Pyjoyment.Lite import app, get, group, under


# Not in Mojolicious: the timeouts of a route, the inactivity timeout of its connection and the most time to the end of
# its response, of the values inactivity_timeout and request_timeout of the stash, set before its first action


# A reactor whose run_coroutine cannot cancel a coroutine returns None, and leaves an action running after its timeout
async def probe():
    pass


cancels = Pyjo.IOLoop.singleton.reactor.run_coroutine(probe(), lambda value: None, lambda e: None) is not None

app.log.level = 'fatal'

events = []


def cancelled(expected, name):
    return is_deeply_ok(events, expected, name) if cancels else skip('the reactor cannot cancel a coroutine')


async def silent(c):
    try:
        await Pyjo.Promise.timer(float(c.param('wait') or 0.6))
        c.render(text='answered')
    finally:
        events.append('ended')


get('/short', silent)
get('/long', {'inactivity_timeout': 2}, silent)
get('/deadline', {'request_timeout': 0.2}, silent)


@get('/helper')
async def helper(c):
    c.request_timeout(0.2)
    await silent(c)


@get('/callback', {'request_timeout': 0.2})
def callback(c):
    Pyjo.IOLoop.timer(1, lambda loop: c.render(text='late'))


@get('/stream', {'request_timeout': 0.2, 'inactivity_timeout': 2})
async def stream(c):
    c.write_chunk(b'started')
    try:
        await Pyjo.Promise.timer(1)
    finally:
        events.append('stream ended')


with group():
    under({'inactivity_timeout': 2, 'request_timeout': 1})
    get('/group', silent)


def settle():
    # The events of the server after the end of a response or of its connection
    Pyjo.Promise.timer(0.1).wait()


t = Pyjo.Test.Pyjo.new()
t.ua.inactivity_timeout = 10

with subtest('Inactivity timeout of the server'):
    events.clear()
    tx = t.ua.get('/short')
    settle()
    is_ok(tx.error, {'message': 'Premature connection close'}, 'closed by the server')
    cancelled(['ended'], 'action cancelled')

with subtest('Inactivity timeout of a route'):
    events.clear()
    t.get_ok('/long').status_is(200).content_is('answered')

with subtest('Request timeout of a route'):
    events.clear()
    with app.log.capture('info') as logs:
        t.get_ok('/deadline?wait=5').status_is(504).content_is('')
        settle()
    cancelled(['ended'], 'action cancelled')
    like_ok(str(logs), r'Request timeout of 0\.2 seconds', 'logged')

    with app.log.capture('info') as logs:
        t.get_ok('/deadline?wait=0.05').status_is(200).content_is('answered')
        Pyjo.Promise.timer(0.3).wait()
    unlike_ok(str(logs), r'Request timeout', 'answered before the time, which does not pass later')

with subtest('Request timeout of the helper'):
    events.clear()
    t.get_ok('/helper?wait=5').status_is(504)
    settle()
    cancelled(['ended'], 'action cancelled')

with subtest('Request timeout of an action with a callback'):
    t.get_ok('/callback').status_is(504).content_is('')
    Pyjo.Promise.timer(1).wait()

with subtest('Request timeout of a response that has started'):
    events.clear()
    tx = t.ua.get('/stream')
    settle()
    is_ok(tx.res.code, 200, 'started')
    is_ok(tx.res.body, b'started', 'first chunk')
    ok(not tx.res.content.is_finished, 'connection closed without the last chunk')
    cancelled(['stream ended'], 'action cancelled')

with subtest('Timeouts of a group'):
    events.clear()
    t.get_ok('/group').status_is(200).content_is('answered')
    t.get_ok('/group?wait=5').status_is(504)
    settle()
    cancelled(['ended', 'ended'], 'answered, then cancelled')

t.close()

done_testing()
