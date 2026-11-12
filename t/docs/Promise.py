import Pyjo.DOM

from Pyjo.Test import *

import asyncio
import contextlib
import gc
import io
import os
import random
import subprocess
import sys
import types


# The documentation describes the default reactor, before Pyjo.IOLoop is loaded
os.environ.pop('PYJO_REACTOR', None)


# A user agent that answers without the network
class FakeUA:
    def get(self, url, cb):
        tx = types.SimpleNamespace(
            error=None,
            req=types.SimpleNamespace(url=url),
            res=types.SimpleNamespace(code=200, dom=lambda: Pyjo.DOM.new(f'<title>{url}</title>')),
        )
        Pyjo.IOLoop.timer(0.01 if 'mojolicious' in url else 0.02, lambda loop: cb(self, tx))


def warn(msg):
    print(f'warn: {msg}')


with subtest('Synopsis'):
    from Pyjo.Promise import Promise

    # Wrap continuation-passing style APIs with promises
    ua = FakeUA()

    def get_p(url):
        promise = Promise()

        def cb(ua, tx):
            err = tx.error
            if not err or err.get('code'):
                promise.resolve(tx)
            else:
                promise.reject(err['message'])

        ua.get(url, cb)
        return promise

    promise = get_p('https://mojolicious.org')
    isa_ok(promise, Promise, 'get_p')
    results = []
    promise.then(lambda tx: results.append(tx.res.code)).wait()
    is_deeply_ok(results, [200], 'resolved')

    # Or import the module, as in Google Python Style Guide

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        import Pyjo.Promise

        # Wrap continuation-passing style APIs with promises
        ua = FakeUA()

        def get_p(url):
            promise = Pyjo.Promise.new()

            def cb(ua, tx):
                err = tx.error
                if not err or err.get('code'):
                    promise.resolve(tx)
                else:
                    promise.reject(err['message'])

            ua.get(url, cb)
            return promise

        # Perform non-blocking operations sequentially
        def mojo_cb(mojo):
            print(mojo.res.code)
            return get_p('https://metacpan.org')

        get_p('https://mojolicious.org').then(mojo_cb).then(lambda cpan: print(cpan.res.code)).catch(
            lambda err: warn(f'Something went wrong: {err}')
        ).wait()

        # Synchronize non-blocking operations (all)
        mojo = get_p('https://mojolicious.org')
        cpan = get_p('https://metacpan.org')
        Pyjo.Promise.all(mojo, cpan).then(lambda mojo, cpan: print(mojo[0].res.code, cpan[0].res.code)).catch(
            lambda err: warn(f'Something went wrong: {err}')
        ).wait()

        # Synchronize non-blocking operations (race)
        mojo = get_p('https://mojolicious.org')
        cpan = get_p('https://metacpan.org')
        Pyjo.Promise.race(mojo, cpan).then(lambda tx: print(tx.req.url, 'won!')).catch(
            lambda err: warn(f'Something went wrong: {err}')
        ).wait()

        # Await a promise in a coroutine
        @Pyjo.Promise.coroutine
        async def code(url):
            tx = await get_p(url)
            return tx.res.code

        code('https://mojolicious.org').then(print).wait()
    is_ok(output.getvalue(), '200\n200\n200 200\nhttps://mojolicious.org won!\n200\n', 'synopsis')

with subtest('Values'):
    promise = Pyjo.Promise.resolve('a', 'b')
    got = []
    promise.then(lambda *values: Pyjo.Promise.resolve(*values)).then(lambda *values: got.extend(values)).wait()
    is_deeply_ok(got, ['a', 'b'], 'several values passed on')

with subtest('Coroutines'):

    async def main():
        title = (await get_p('https://mojolicious.org')).res.dom().at('title').text
        return title

    is_ok(asyncio.run(main()), 'https://mojolicious.org', 'awaited in asyncio')

with subtest('Debugging'):
    env = dict(os.environ, PYJO_PROMISE_DEBUG='1')
    code = 'import gc, Pyjo.Promise; Pyjo.Promise.reject("Oops"); gc.collect()'
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    like_ok(result.stderr, r'Unhandled rejected promise: Oops', 'warning')
    like_ok(result.stderr, r'-- Destroyed promise', 'diagnostics')

with subtest('ioloop'):
    promise = Pyjo.Promise.new()
    loop = promise.ioloop
    is_ok(loop, Pyjo.IOLoop.singleton, 'default')
    loop = Pyjo.IOLoop.new()
    promise.ioloop = loop
    is_ok(promise.ioloop, loop, 'set')

with subtest('all, all_settled, any and race'):
    promises = [Pyjo.Promise.resolve(1), Pyjo.Promise.resolve(2)]
    got = []
    new = Pyjo.Promise.all(*promises)
    new.then(lambda *values: got.append(values))
    new = Pyjo.Promise.all_settled(*promises)
    new.then(lambda *values: got.append(values))
    new = Pyjo.Promise.any(*promises)
    new.then(lambda *values: got.append(values))
    new = Pyjo.Promise.race(*promises)
    new.then(lambda *values: got.append(values)).wait()
    is_deeply_ok(
        got,
        [
            ([1], [2]),
            ({'status': 'fulfilled', 'value': [1]}, {'status': 'fulfilled', 'value': [2]}),
            (1,),
            (1,),
        ],
        'results',
    )

with subtest('cancel'):
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        # Cancel a coroutine, whose finally blocks run
        async def main():
            try:
                await Pyjo.Promise.timer(5)
            finally:
                print('cancelled')

        promise = Pyjo.Promise.new(main())
        Pyjo.IOLoop.timer(0.01, lambda loop: promise.cancel())
        promise.catch(lambda err: print(type(err).__name__)).wait()
    is_ok(stdout.getvalue(), 'cancelled\nCancelledError\n', 'finally block and the cancellation of the reactor')
    ok(promise.cancel() is promise, 'settled, as it is')

    # Nothing to cancel
    promise = Pyjo.Promise.new()
    promise.cancel()
    promise.resolve('later')
    got = []
    promise.then(got.append)
    Pyjo.IOLoop.one_tick()
    is_deeply_ok(got, ['later'], 'still pending')

with subtest('catch'):
    got = []
    promise = Pyjo.Promise.reject('Oops')
    new = promise.catch(lambda *reason: ...)

    # Longer version
    new = promise.then(None, lambda *reason: ...)

    # Pass along the rejection reason
    def cb(*reason):
        warn(f'Something went wrong: {reason[0]}')
        return Pyjo.Promise.reject(*reason)

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        promise.catch(cb).catch(lambda *reason: got.append(reason))

        # Change the rejection reason
        promise.catch(lambda *reason: f'This is bad: {reason[0]}').then(lambda value: got.append(value)).wait()
    is_ok(output.getvalue(), 'warn: Something went wrong: Oops\n', 'warned')
    is_deeply_ok(sorted(got, key=str), [('Oops',), 'This is bad: Oops'], 'passed along and changed')

with subtest('clone'):
    promise = Pyjo.Promise.resolve('done')
    new = promise.clone()
    isnt_ok(new, promise, 'new promise')
    is_ok(new.ioloop, promise.ioloop, 'same loop')

with subtest('lastly'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        promise = Pyjo.Promise.resolve('done')
        new = promise.lastly(lambda: ...)

        # Do something on fulfillment and rejection
        promise.lastly(lambda: print('We are done!')).wait()
    is_ok(output.getvalue(), 'We are done!\n', 'finally')
    is_ok(Pyjo.Promise.object.finally_, Pyjo.Promise.object.lastly, 'alias')

with subtest('map'):
    items = [1, 2, 3, 4]
    got = []
    new = Pyjo.Promise.map(lambda item: Pyjo.Promise.resolve(item * 2), *items)
    new.then(lambda *values: got.append(values))
    new = Pyjo.Promise.map(lambda item: Pyjo.Promise.resolve(item * 3), *items, concurrency=3)
    new.then(lambda *values: got.append(values)).wait()
    is_deeply_ok(got, [([2], [4], [6], [8]), ([3], [6], [9], [12])], 'mapped')

with subtest('new'):
    promise = Pyjo.Promise.new()
    promise = Pyjo.Promise.new(lambda resolve, reject: ...)
    isa_ok(promise, Pyjo.Promise.object, 'promise')

    # Wrap a continuation-passing style API
    def cb(resolve, reject):
        Pyjo.IOLoop.timer(0.01, lambda loop: resolve('Lucky!') if random.randint(0, 1) else reject('Unlucky!'))

    promise = Pyjo.Promise.new(cb)
    got = []
    promise.then(got.append, got.append).wait()
    ok(got[0] in ('Lucky!', 'Unlucky!'), 'lucky or not')

    # Wrap a coroutine
    async def lucky():
        await Pyjo.Promise.timer(0.01)
        return 'Lucky!'

    promise = Pyjo.Promise.new(lucky())
    got = []
    promise.then(got.append).wait()
    is_deeply_ok(got, ['Lucky!'], 'coroutine')

    # Wrap a future of asyncio
    async def wrap():
        import time

        future = asyncio.get_running_loop().run_in_executor(None, time.sleep, 0.01)
        promise = Pyjo.Promise.new(future)
        isa_ok(promise, Pyjo.Promise.object, 'promise of a future')
        return await promise

    is_ok(asyncio.run(wrap()), None, 'future')

    import concurrent.futures
    import time

    # Wrap a future of a pool of threads
    with concurrent.futures.ThreadPoolExecutor() as executor:
        promise = Pyjo.Promise.new(executor.submit(time.sleep, 0.01))
        promise.wait()
    got = []
    promise.then(lambda *values: got.append(values)).wait()
    is_deeply_ok(got, [()], 'future of concurrent.futures')

    # A promise of a timer that stops it
    promise = Pyjo.Promise.new(cancel=lambda: Pyjo.IOLoop.remove(id))
    id = Pyjo.IOLoop.timer(5, lambda loop: promise.resolve())
    promise.cancel()
    is_ok(Pyjo.IOLoop.singleton.reactor.remove(id), False, 'timer removed')
    is_ok(promise.cancel(), promise, 'once')

with subtest('reject and resolve'):
    got = []
    new = Pyjo.Promise.reject('a', 'b')
    new.catch(lambda *reason: got.append(reason))
    promise = Pyjo.Promise.new()
    promise = promise.reject('c')
    promise.catch(lambda *reason: got.append(reason))

    # Longer version
    promise = Pyjo.Promise.new().reject('d')
    promise.catch(lambda *reason: got.append(reason))

    new = Pyjo.Promise.resolve('e', 'f')
    new.then(lambda *value: got.append(value))
    promise = Pyjo.Promise.new()
    promise = promise.resolve('g')

    # Longer version
    promise = Pyjo.Promise.new().resolve('h')
    promise.then(lambda *value: got.append(value)).wait()
    is_deeply_ok(got, [('a', 'b'), ('c',), ('d',), ('e', 'f'), ('h',)], 'settled')

with subtest('then'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        promise = Pyjo.Promise.resolve(42)
        new = promise.then(lambda *value: ...)
        new = promise.then(lambda *value: ..., lambda *reason: ...)
        new = promise.then(None, lambda *reason: ...)

        # Pass along the fulfillment value or rejection reason
        def value_cb(*value):
            print(f'The result is {value[0]}')
            return Pyjo.Promise.resolve(*value)

        def reason_cb(*reason):
            warn(f'Something went wrong: {reason[0]}')
            return Pyjo.Promise.reject(*reason)

        promise.then(value_cb, reason_cb)

        # Change the fulfillment value or rejection reason
        promise.then(lambda *value: f'This is good: {value[0]}', lambda *reason: f'This is bad: {reason[0]}').then(
            print
        ).wait()
    is_ok(output.getvalue(), 'The result is 42\nThis is good: 42\n', 'then')

with subtest('timer and timeout'):
    got = []
    new = Pyjo.Promise.timer(0.01, 'Success!')
    new.then(got.append)
    promise = Pyjo.Promise.new()
    promise = promise.timer(0.01, 'Success!')
    promise = Pyjo.Promise.new().timer(0.01)

    # Wait 5 seconds between two steps
    promise = Pyjo.Promise.resolve()
    with contextlib.redirect_stdout(io.StringIO()) as output:
        promise.then(lambda *_: Pyjo.Promise.timer(0.01)).then(lambda *_: print('Five seconds later')).wait()
    is_ok(output.getvalue(), 'Five seconds later\n', 'delay between two steps')

    new = Pyjo.Promise.timeout(0.01, 'Timeout!')
    new.catch(got.append)
    promise = Pyjo.Promise.new()
    promise = promise.timeout(0.01, 'Timeout!')
    promise.catch(lambda *reason: None)
    promise = Pyjo.Promise.new().timeout(0.01)
    promise.catch(got.append)
    Pyjo.Promise.timer(0.05).wait()
    is_deeply_ok(sorted(got), ['Promise timeout', 'Success!', 'Timeout!'], 'timers')

with subtest('to_future'):
    future = Pyjo.Promise.timer(0.01, 'value').to_future()
    ok(hasattr(future, 'add_done_callback'), 'future')

    # Print the value when the future is done
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        future = Pyjo.Promise.timer(0.01, 'Done!').to_future()
        future.add_done_callback(lambda future: print(future.result()))
        Pyjo.Promise.timer(0.05).wait()
    is_ok(output.getvalue(), 'Done!\n', 'printed')

with subtest('wait'):
    promise = Pyjo.Promise.timer(0.01, 'waited')
    promise.wait()
    got = []
    promise.then(got.append).wait()
    is_deeply_ok(got, ['waited'], 'waited')

with subtest('coroutine'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        ua = FakeUA()
        ua.get_p = get_p

        @Pyjo.Promise.coroutine
        async def title(url):
            tx = await ua.get_p(url)
            return tx.res.dom().at('title').text

        title('https://mojolicious.org').then(print).wait()
    is_ok(output.getvalue(), 'https://mojolicious.org\n', 'title')

gc.collect()

done_testing()
