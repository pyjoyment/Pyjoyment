"""
Pyjo.App.Lambda - AWS Lambda event function
===========================================
::

    from Pyjo.App.Lambda import Lambda

    app = Lambda(function='myfunction.handler')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.App.Lambda

    app = Pyjo.App.Lambda.new(function='myfunction.handler')

    # Another runtime, with the events of a REST API
    app = Pyjo.App.Lambda.new(command=['node', 'runtime.js'], payload='1.0')

    # Mount it in an application of Pyjoyment
    import Pyjoyment

    pyjoyment = Pyjoyment.new()
    pyjoyment.plugin('Mount', {'/function': app})

:mod:`Pyjo.App.Lambda` is an application of :mod:`Pyjo` that runs an event
function of `AWS Lambda <https://aws.amazon.com/lambda/>`_, so that a server
of :mod:`Pyjo` serves it, a route of :mod:`Pyjoyment` embeds it, as
:mod:`Pyjoyment.Plugin.Mount` does, and :mod:`Pyjo.Test.Pyjo` tests it, as
API Gateway, a Function URL or an Application Load Balancer runs it on AWS.

The function runs in a process of its own, as an execution environment of
Lambda does, which :mod:`Pyjo.IOLoop.ChildProcess` starts on the first
request and keeps for the next ones, which it gets one after another. Each
event loop has a process of its own, and the child of a fork, as a worker of
:mod:`Pyjo.Server.Prefork`, leaves the processes of its parent to it and
starts its own. The process gets its invocations from the `Runtime API
<https://docs.aws.amazon.com/lambda/latest/dg/runtimes-api.html>`_ of
``AWS_LAMBDA_RUNTIME_API``, which a :mod:`Pyjo.Server.Daemon` on a port of
the loopback serves on the same event loop, so that a handler of Python runs
with the runtime client of :mod:`Pyjo.Server.Lambda`, also one that runs an
event loop of its own, and a function of another runtime with its own runtime
client, without the event loop waiting for it. The graceful stop of the event
loop, as the one of ``TERM`` of a server, ends the process once it has
answered the invocations of the requests in progress, as its request for the
next invocation would keep the event loop running.

The request is the event of the payload format of :attr:`payload`, as
:mod:`Pyjo.Server.Lambda` takes it, and the path that a route embeds the
application under is the stage of API Gateway, in front of the path, which
:mod:`Pyjo.Server.Lambda` takes for the base path of the URL. A body that is
not text, JSON, XML, JavaScript or YAML in UTF-8 is in Base64. The response is
the one of the payload format, with its ``statusCode``, its headers, its
cookies and its body, which can be in Base64, and in the format ``2.0`` a
value without ``statusCode`` is a response ``200`` of the value as JSON, as API
Gateway takes it.

A streaming response of the runtime client, as the one of
:mod:`Pyjo.Server.Lambda` with the invoke mode ``RESPONSE_STREAM``, is
written as it comes, as a Function URL with the invoke mode
``RESPONSE_STREAM`` writes it: the status and the headers of its prelude, in
the content type ``application/vnd.awslambda.http-integration-response``,
before 8 null bytes, or ``200`` and the content type of the response, and its
body in chunks. The timeout of the function goes on until its end, and an
error in its trailers, or the timeout, in the middle of it closes the
connection, as the response cannot change anymore. ::

    # The streaming responses of an application on Pyjo.Server.Lambda
    app = Pyjo.App.Lambda.new(function='myapp.handler', env={'PYJO_LAMBDA_INVOKE_MODE': 'RESPONSE_STREAM'})

An error of the function or of its initialization, a response that is not
valid, a process that ends before its response, and an invocation that takes
longer than :attr:`timeout`, whose process is killed, as Lambda does, are a
response ``502``, logged, and the next request starts a new process. The
output of the process is logged, as Lambda sends it to CloudWatch. The event
loop does not watch pipes on Windows, so the response is ``502`` there.

Attributes
----------

:mod:`Pyjo.App.Lambda` inherits all attributes from :mod:`Pyjo.App` and
implements the following new ones.

See also
--------

:mod:`Pyjoyment`, :mod:`Pyjoyment.Plugin.Mount`, :mod:`Pyjo.Server.Lambda`,
:mod:`Pyjo.App.CGI`, https://mojolicious.org.

It has no counterpart in Mojolicious; it is the reverse of
:mod:`Pyjo.Server.Lambda`.

Classes
-------
"""

import Pyjo.App
import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Server.Daemon
import Pyjo.Transaction
import Pyjo.Transaction.HTTP

from Pyjo.Server.Lambda import _RE_TEXT, _is_utf8  # pyright: ignore[reportPrivateUsage]
from Pyjo.Util import b64_encode

import base64
import json
import os
import re
import signal
import sys
import time
import uuid
import weakref
import wsgiref.util

from collections import deque
from typing import Any, cast


# The account, the region and the API of the identifiers of the events, which no AWS has
ACCOUNT = '123456789012'
REGION = 'us-east-1'
API = 'pyjo'

PREFIX = '/2018-06-01/runtime'

# The streaming response of an HTTP integration: the status and the headers as JSON, in the first 16 KB, before 8 null
# bytes and the body
INTEGRATION = 'application/vnd.awslambda.http-integration-response'
DELIMITER = b'\x00' * 8
MAX_PRELUDE = 16384


class Pyjo_App_Lambda(Pyjo.App.object):
    """
    :mod:`Pyjo.App.Lambda` inherits all methods from :mod:`Pyjo.App` and
    implements the following new ones.
    """

    def __init__(self, attrs: dict[str, Any] | None = None, /, **kwargs: Any) -> None:
        """::

            app = Pyjo.App.Lambda.new(function='myfunction.handler')

        Construct a new :mod:`Pyjo.App.Lambda` object.
        """
        self.command: list[str] | None = None
        """::

            command = app.command
            app.command = ['python', '-m', 'awslambdaric', 'myfunction.handler']
            app.command = ['./bootstrap']

        Program of the function, with its arguments, as the runtime client of
        another runtime or the ``bootstrap`` of a custom runtime, in
        :attr:`task_root`, or the runtime client of :mod:`Pyjo.Server.Lambda`
        with :attr:`function` and the interpreter of this process.
        """

        self.env: dict[str, str] = {}
        """::

            env = app.env
            app.env = {'TABLE_NAME': 'users'}

        Variables of the environment of the function, which are added to the
        ones of this process and of Lambda, and replace them.
        """

        self.function: str | None = None
        """::

            handler = app.function
            app.function = 'myfunction.handler'

        Handler of the function, ``module.function``, in ``_HANDLER``, which
        the runtime client of :mod:`Pyjo.Server.Lambda` runs without
        :attr:`command`.
        """

        self.function_name = 'pyjo'
        """::

            name = app.function_name
            app.function_name = 'myfunction'

        Name of the function, in ``AWS_LAMBDA_FUNCTION_NAME`` and in its ARN,
        defaults to ``pyjo``.
        """

        self.memory_size = 128
        """::

            size = app.memory_size
            app.memory_size = 512

        Memory of the function in megabytes, in
        ``AWS_LAMBDA_FUNCTION_MEMORY_SIZE``, defaults to ``128``.
        """

        self.multi_value_headers = False
        """::

            boolean = app.multi_value_headers
            app.multi_value_headers = True

        The headers and the parameters of the query of the events of an
        Application Load Balancer with multiple values, as a target group with
        them has them, false by default.
        """

        self.payload = '2.0'
        """::

            payload = app.payload
            app.payload = '1.0'
            app.payload = 'alb'

        Payload format of the events, ``2.0`` of HTTP APIs and Function URLs,
        the default, ``1.0`` of REST APIs, or ``alb`` of Application Load
        Balancers.
        """

        self.task_root: str | os.PathLike[str] | None = None
        """::

            root = app.task_root
            app.task_root = '/var/task'

        Directory of the function, in ``LAMBDA_TASK_ROOT``, which its process
        runs in, and which the runtime client of :mod:`Pyjo.Server.Lambda`
        imports the handler from, the current one by default.
        """

        self.timeout: float = 30
        """::

            timeout = app.timeout
            app.timeout = 3

        Maximum amount of time in seconds an invocation can take before its
        process is killed, defaults to ``30``, as an integration of API
        Gateway has it.
        """

        # The execution environments of each event loop, of the process that made them
        self._pid = os.getpid()
        self._environments: weakref.WeakKeyDictionary[Any, _Environment] = weakref.WeakKeyDictionary()
        _apps.add(self)

        super().__init__(attrs, **kwargs)

    def close(self) -> None:
        """::

            app.close()

        End the processes of the function, and close the connections and the
        servers of :attr:`ua`, as the end of a ``with`` block does.
        """
        if self._pid == os.getpid():
            for environment in list(self._environments.values()):
                environment.close()
            self._environments.clear()
        super().close()

    def handler(self, tx: Any) -> None:
        """::

            app.handler(Pyjo.Transaction.HTTP.new())
            app.handler(Pyjoyment.Controller.new())

        Invoke the function with the event of the request of the transaction,
        or of the controller of a route that embeds the application, and write
        its response.
        """
        if self.function is None and self.command is None:
            raise Pyjo.Exception.new('No Lambda function')
        if self.payload not in ('2.0', '1.0', 'alb'):
            raise Pyjo.Exception.new(f'Invalid Lambda payload format "{self.payload}"')
        c = None
        if not isinstance(tx, Pyjo.Transaction.object):
            c = tx
            tx = c.tx
            if not Pyjo.App._within(c):  # pyright: ignore[reportPrivateUsage]
                return c.helpers.reply.not_found()
            c.render_later()
        _Invocation(self, tx, c).start()

    def _environment(self) -> '_Environment':
        loop = Pyjo.IOLoop.singleton

        self._leave()
        environment = self._environments.get(loop)
        if environment is None or environment.ended:
            _register()
            self._environments[loop] = environment = _Environment(self)
        return environment

    # The child of a fork leaves the processes of its parent to it, and closes the copies of their servers, at the fork,
    # before its event loop reads the connections of the runtime clients of the parent, or of the processes that the
    # child starts later
    def _leave(self) -> None:
        if self._pid != (pid := os.getpid()):
            for environment in list(self._environments.values()):
                environment.leave()
            self._pid, self._environments = pid, weakref.WeakKeyDictionary()


# An invocation of the function for a request, and its response
class _Invocation:
    def __init__(self, app: Pyjo_App_Lambda, tx: Any, c: Any) -> None:
        self.app = app
        self.tx = tx
        self.c = c
        self.id = str(uuid.uuid4())
        self.done = False
        self.environment: _Environment | None = None
        self.event: dict[str, Any] = {}
        self.waiting: tuple[str, float] | None = None

        # A streaming response: the request of the runtime client that sends it, the prelude that comes before its body,
        # its status and its headers, which go with its first chunk, whether they have gone, with the body chunked, and
        # the chunks that wait to be written, after which the connection closes when it is closing
        self.api: str | None = None
        self.prelude: bytearray | None = None
        self.head: tuple[int, list[tuple[str, str]]] | None = None
        self.started = False
        self.chunked = False
        self.pending = 0
        self.closing = False

    def start(self) -> None:
        self.tx.on('finish', self._finish)
        self.event = _event(self.app, self.tx, self.c, self.id)

        # The connection of the client waits for the response without its inactivity timeout, which the timeout of the
        # function takes the place of
        if (connection := self.tx.connection) is not None and (stream := Pyjo.IOLoop.stream(connection)) is not None:
            self.waiting = (connection, stream.timeout)
            stream.timeout = 0

        self.app._environment().invoke(self)  # pyright: ignore[reportPrivateUsage]

    def fail(self, message: str) -> None:
        if self.done:
            return
        self.app.log.error(message)

        # A streaming response that has started cannot change, so the connection is closed once the chunks of it that
        # wait have been written
        if self.started:
            self.done = True
            self._waited()
            if self.pending:
                self.closing = True
            else:
                self._close()
            return
        self._write(502, [('Content-Type', 'text/plain')], b'Bad Gateway')

    # The response of the payload format, or a value as JSON of the format 2.0
    def respond(self, body: bytes) -> None:
        if self.done:
            return
        try:
            value = json.loads(body or b'null')
        except ValueError:
            return self.fail('Lambda function returned invalid JSON')
        if not isinstance(value, dict) or 'statusCode' not in value:
            if self.app.payload != '2.0':
                return self.fail('Lambda function returned no statusCode')
            text = value if isinstance(value, str) else json.dumps(value)
            return self._write(200, [('Content-Type', 'application/json')], text.encode())

        try:
            response = cast(dict[str, Any], value)
            code, headers = _status(response)
            content = response.get('body')
            if content is None:
                data = b''
            elif response.get('isBase64Encoded'):
                data = base64.b64decode(content)
            else:
                data = str(content).encode()
        except (AttributeError, TypeError, ValueError) as e:
            return self.fail(f'Lambda function returned an invalid response: {e}')
        self._write(code, headers, data)

    # The start of a streaming response, once the headers of its request have come: with the status and the headers of
    # the prelude of an HTTP integration, or of the content type of the request
    def stream(self, api: str | None, content_type: str) -> None:
        self.api = api
        if content_type.split(';')[0].strip().lower() == INTEGRATION:
            self.prelude = bytearray()
        else:
            self._start(200, [('Content-Type', content_type or 'application/octet-stream')])

    # A chunk of a streaming response, after its prelude
    def stream_chunk(self, chunk: bytes) -> None:
        if self.done:
            return
        if (prelude := self.prelude) is not None:
            prelude += chunk
            if (end := prelude.find(DELIMITER)) < 0:
                if len(prelude) > MAX_PRELUDE:
                    self.fail('Lambda function returned no prelude in the first 16 KB of its streaming response')
                return
            self.prelude = None
            try:
                value = json.loads(bytes(prelude[:end]))
                code, headers = _status(cast(dict[str, Any], value) if isinstance(value, dict) else {})
            except (AttributeError, KeyError, TypeError, ValueError) as e:
                return self.fail(f'Lambda function returned an invalid prelude: {e}')
            self._start(code, headers)
            chunk = bytes(prelude[end + len(DELIMITER) :])
        if not len(chunk):
            return

        # The next chunks of the runtime client once the chunk has been written to the client
        connection = self.api

        def drained(*args: Any) -> None:
            self.pending -= 1
            if self.closing and not self.pending:
                return self._close()
            if connection is not None and (stream := Pyjo.IOLoop.stream(connection)) is not None:
                stream.start()

        if connection is not None and (stream := Pyjo.IOLoop.stream(connection)) is not None:
            stream.stop()
        self._begin()
        self.pending += 1
        content = self.tx.res.content
        (content.write_chunk if self.chunked else content.write)(chunk, drained)
        self._rendered()

    # The end of a streaming response, with the error of its trailers
    def stream_end(self, error: str | None, body: str | None) -> None:
        if error is not None:
            message = _message(_json(base64.b64decode(body or ''))) if body else error
            return self.fail(f'Lambda function error: {message}')
        if self.done:
            return
        if self.prelude is not None:
            return self.fail('Lambda function returned no prelude in its streaming response')
        self.done = True
        self._waited()
        self._begin()
        content = self.tx.res.content
        (content.write_chunk if self.chunked else content.write)(b'')
        self._rendered()

    # The status and the headers of a streaming response, with its first chunk
    def _begin(self) -> None:
        if not self.started and (head := self.head) is not None:
            self.started = True
            self._headers(*head)

    # The connection of the client, once what has been written to it is
    def _close(self) -> None:
        if (connection := self.tx.connection) is not None and (stream := Pyjo.IOLoop.stream(connection)) is not None:
            stream.close_gracefully()

    # The client is gone, or has its response
    def _finish(self, *args: Any) -> None:
        if self.done:
            return
        self.done = True
        if (environment := self.environment) is not None:
            environment.cancel(self)

    def _headers(self, code: int, headers: list[tuple[str, str]]) -> None:
        res = self.tx.res
        res.code = code
        for name, value in headers:
            if not wsgiref.util.is_hop_by_hop(name) and name.lower() != 'content-length':
                res.headers.add(name, value)

    def _rendered(self) -> None:
        if (c := self.c) is not None:
            c.rendered()
        else:
            self.tx.resume()

    # The status and the headers of a streaming response, which go with its first chunk, as its body is chunked, or ends
    # with the connection of HTTP/1.0
    def _start(self, code: int, headers: list[tuple[str, str]]) -> None:
        self.head = (code, headers)
        self.chunked = self.tx.req.version == '1.1'
        if self.tx.is_empty:
            self.done = True
            self._waited()
            self._begin()
            self.tx.res.content.write(b'')
            self._rendered()

    # The inactivity timeout of the connection of the client again
    def _waited(self) -> None:
        if (waiting := self.waiting) is not None:
            self.waiting = None
            connection, timeout = waiting
            if (stream := Pyjo.IOLoop.stream(connection)) is not None:
                stream.timeout = timeout

    def _write(self, code: int, headers: list[tuple[str, str]], body: bytes) -> None:
        self.done = True
        self._waited()
        self._headers(code, headers)
        self.tx.res.body = body
        self._rendered()


# An execution environment of the function: its process, and the Runtime API that it gets its invocations from, one
# after another
class _Environment:
    def __init__(self, app: Pyjo_App_Lambda) -> None:
        self.app = app
        self.closing = False
        self.current: _Invocation | None = None
        self.ended = False
        self.failed = False
        self.next: Any = None
        self.started = False
        self.queue: deque[_Invocation] = deque()
        self.timer: str | None = None

        api = _RuntimeAPI()
        api.environment = weakref.ref(self)
        api.log = app.log
        self.daemon = Pyjo.Server.Daemon.new(
            app=api, listen=['http://127.0.0.1'], silent=True, inactivity_timeout=0
        ).start()

        # The graceful stop of the event loop waits for the connections of the Runtime API too, as the one of the runtime
        # client that waits for its next invocation, so the environment ends once it has no invocation, also when it
        # starts while the event loop stops
        ref = weakref.ref(self)
        loop = self.daemon.ioloop
        self.stopping = loop.is_stopping

        def finish(loop: Any) -> None:
            if (environment := ref()) is not None:
                environment.stopping = True
                environment.dispatch()

        self.finished = loop.once('finish', finish)

        # The variables of Lambda, of the runtime client of Pyjo.Server.Lambda without a command, and of the attribute
        root: str = os.path.abspath(os.fspath(app.task_root)) if app.task_root is not None else os.getcwd()
        name = app.function_name
        env: dict[str, str] = {
            **os.environ,
            'AWS_LAMBDA_RUNTIME_API': f'127.0.0.1:{self.daemon.ports()[0]}',
            'AWS_LAMBDA_FUNCTION_NAME': name,
            'AWS_LAMBDA_FUNCTION_VERSION': '$LATEST',
            'AWS_LAMBDA_FUNCTION_MEMORY_SIZE': str(app.memory_size),
            'AWS_LAMBDA_LOG_GROUP_NAME': f'/aws/lambda/{name}',
            'AWS_LAMBDA_LOG_STREAM_NAME': f'{time.strftime("%Y/%m/%d", time.gmtime())}/[$LATEST]{uuid.uuid4().hex}',
            'LAMBDA_TASK_ROOT': root,
            '_HANDLER': app.function or '',
            'PYTHONUNBUFFERED': '1',
        }
        env.setdefault('AWS_REGION', REGION)
        command = app.command
        if command is None:
            command = [sys.executable, '-m', 'Pyjo.Server.Lambda']
            checkout = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(Pyjo.App.__file__))))
            env['PYTHONPATH'] = os.pathsep.join([checkout, *filter(None, [env.get('PYTHONPATH')])])
        env.update(app.env)

        self.child = child = Pyjo.IOLoop.spawn(command, cwd=root, detached=True, env=env)
        for stream, log in ((child.stdout, app.log.info), (child.stderr, app.log.warn)):
            if stream is not None:
                lines = _Lines(log)
                stream.on('read', lines.read)
                stream.on('close', lines.closed)

        def error(child: Any, err: Any) -> None:
            if (environment := ref()) is not None:
                environment.end(f'Lambda function failed: {err}', True)

        def close(child: Any, code: int | None, signal: int | None) -> None:
            if (environment := ref()) is not None:
                # A process that ends before it asks for an invocation fails the ones that wait for it too
                status = f'signal {signal}' if signal else f'status {code}'
                failed = environment.failed or not environment.started
                environment.end(f'Lambda function ended with {status}', failed)

        child.on('error', error)
        child.on('close', close)

    def cancel(self, invocation: _Invocation) -> None:
        if invocation in self.queue:
            self.queue.remove(invocation)

    def close(self) -> None:
        self.end('Lambda function closed', True)

    # The invocation for the runtime client that waits for it
    def dispatch(self) -> None:
        if self.stopping and self.current is None and not self.queue:
            return self._close_later()
        if self.current is not None or not self.queue or (tx := self.next) is None:
            return
        self.next = None
        self.current = invocation = self.queue.popleft()
        app = self.app
        deadline = int((time.time() + app.timeout) * 1000)
        res = tx.res
        res.code = 200
        headers = res.headers
        headers.content_type = 'application/json'
        headers.header('Lambda-Runtime-Aws-Request-Id', invocation.id)
        headers.header('Lambda-Runtime-Deadline-Ms', str(deadline))
        headers.header('Lambda-Runtime-Invoked-Function-Arn', _arn(app))
        headers.header('Lambda-Runtime-Trace-Id', f'Root=1-{int(time.time()):08x}-{uuid.uuid4().hex[:24]}')
        res.body = json.dumps(invocation.event).encode()
        tx.resume()

        ref = weakref.ref(self)

        def timeout(loop: Any) -> None:
            if (environment := ref()) is not None:
                environment.timer = None
                environment.timed_out()

        self.timer = Pyjo.IOLoop.timer(app.timeout, timeout)

    # The end of the process, of a failure or its own, which fails the invocation that it had, and the ones that wait
    # for it when the function failed, where they go to a new process otherwise
    def end(self, message: str, failed: bool) -> None:
        first = not self.ended
        self.ended = True
        self._stop()
        if (invocation := self.current) is not None:
            self.current = None
            invocation.fail(message)
        queue, self.queue = list(self.queue), deque()
        if first:
            self.daemon.ioloop.unsubscribe('finish', self.finished)
            self.child.kill(signal.SIGKILL)
            self.daemon.close()
        if failed:
            for invocation in queue:
                invocation.fail(message)
        elif queue:
            environment = self.app._environment()  # pyright: ignore[reportPrivateUsage]
            for invocation in queue:
                environment.invoke(invocation)

    def error(self, id: str, error: dict[str, Any]) -> None:
        if (invocation := self._take(id)) is not None:
            invocation.fail(f'Lambda function error: {_message(error)}')
        self.dispatch()

    def init_error(self, error: dict[str, Any]) -> None:
        self.failed = True
        self.app.log.error(f'Lambda function initialization error: {_message(error)}')

    def invoke(self, invocation: _Invocation) -> None:
        invocation.environment = self
        self.queue.append(invocation)
        self.dispatch()

    # The child of a fork leaves the process to its parent, and closes its copy of the server
    def leave(self) -> None:
        self.ended = True
        self._stop()
        self.daemon.ioloop.unsubscribe('finish', self.finished)
        self.daemon.close()

    def response(self, id: str, body: bytes) -> None:
        if (invocation := self._take(id)) is not None:
            invocation.respond(body)
        self.dispatch()

    # The start of the streaming response of the current invocation, which stays current until its end, as its timeout
    # goes on
    def streaming(self, id: str, api: str | None, content_type: str) -> _Invocation | None:
        if (invocation := self.current) is None or invocation.id != id:
            return None
        invocation.stream(api, content_type)
        return invocation

    def streamed(self, id: str, error: str | None, body: str | None) -> None:
        if (invocation := self._take(id)) is not None:
            invocation.stream_end(error, body)
        self.dispatch()

    def timed_out(self) -> None:
        app = self.app
        self.end(f'Lambda function timed out after {app.timeout} seconds', False)

    def wait(self, tx: Any) -> None:
        self.next = tx
        self.started = True
        ref = weakref.ref(self)

        def finish(tx: Any) -> None:
            if (environment := ref()) is not None and environment.next is tx:
                environment.next = None

        tx.on('finish', finish)
        self.dispatch()

    # The end of an environment without an invocation while the event loop stops, in the next cycle of the event loop,
    # as the request of the Runtime API that has made it so is still answered
    def _close_later(self) -> None:
        if self.ended or self.closing:
            return
        self.closing = True
        ref = weakref.ref(self)

        def close(loop: Any) -> None:
            if (environment := ref()) is not None:
                environment.closing = False
                if environment.current is None and not environment.queue:
                    environment.close()

        self.daemon.ioloop.timer(0, close)

    def _stop(self) -> None:
        if (timer := self.timer) is not None:
            self.timer = None
            Pyjo.IOLoop.remove(timer)

    def _take(self, id: str) -> _Invocation | None:
        if (invocation := self.current) is None or invocation.id != id:
            return None
        self._stop()
        self.current = None
        return invocation


# The lines of an output of the process, which are logged as they come
class _Lines:
    def __init__(self, log: Any) -> None:
        self.log = log
        self.buffer = bytearray()

    def closed(self, stream: Any) -> None:
        if len(self.buffer):
            self.line(bytes(self.buffer))
            self.buffer.clear()

    def line(self, line: bytes) -> None:
        self.log(f'Lambda function: {line.decode("utf-8", "replace").rstrip()}')

    def read(self, stream: Any, chunk: bytes) -> None:
        self.buffer += chunk
        while (end := self.buffer.find(b'\n')) >= 0:
            self.line(bytes(self.buffer[:end]))
            del self.buffer[: end + 1]


# The Runtime API of an execution environment, for its process
class _RuntimeAPI(Pyjo.App.object):
    environment: 'weakref.ref[_Environment] | None' = None

    # A streaming response goes to the invocation as it comes, once the headers of its request are there, and its body is
    # not kept
    def build_tx(self) -> Pyjo.Transaction.HTTP.object:
        tx = super().build_tx()
        req = weakref.ref(tx.req)
        ref = weakref.ref(tx)
        environment = self.environment

        def body(content: Any) -> None:
            if (r := req()) is None or (t := ref()) is None or not _is_streaming(r):
                return
            m = re.fullmatch(rf'{PREFIX}/invocation/([^/]+)/response', r.url.path.to_str())
            env = environment() if environment is not None else None
            if m is None or env is None or env.ended:
                return
            invocation = env.streaming(m.group(1), t.connection, r.headers.content_type or '')
            if invocation is None:
                return

            def read(content: Any, chunk: bytes) -> None:
                invocation.stream_chunk(bytes(chunk))

            content.unsubscribe('read').on('read', read)

        tx.req.content.on('body', body)
        return tx

    def handler(self, tx: Any) -> None:
        environment = self.environment() if self.environment is not None else None
        req = tx.req
        method, path = req.method, req.url.path.to_str()
        if environment is not None and not environment.ended:
            if method == 'GET' and path == f'{PREFIX}/invocation/next':
                return environment.wait(tx)
            if method == 'POST' and (m := re.fullmatch(rf'{PREFIX}/invocation/([^/]+)/(response|error)', path)):
                id, kind = m.group(1), m.group(2)
                _reply(tx, 202)
                if kind == 'response' and _is_streaming(req):
                    headers = req.headers
                    return environment.streamed(
                        id,
                        headers.header('Lambda-Runtime-Function-Error-Type'),
                        headers.header('Lambda-Runtime-Function-Error-Body'),
                    )
                if kind == 'response':
                    return environment.response(id, req.body)
                return environment.error(id, _json(req.body))
            if method == 'POST' and path == f'{PREFIX}/init/error':
                _reply(tx, 202)
                return environment.init_error(_json(req.body))
        _reply(tx, 404)


# The ARN of the function
def _arn(app: Pyjo_App_Lambda) -> str:
    return f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:{app.function_name}'


# The body of the request, as it is in text, or in Base64
def _body(req: Any) -> tuple[str | None, bool]:
    body: bytes = req.body
    if not len(body):
        return None, False
    if _RE_TEXT.match(req.headers.content_type or '') and _is_utf8(body):
        return body.decode(), False
    return b64_encode(body, ''), True


# The event of the request in the payload format of the application
def _event(app: Pyjo_App_Lambda, tx: Any, c: Any, id: str) -> dict[str, Any]:
    req = tx.req
    url = req.url
    script, path = Pyjo.App._mount(tx, c)  # pyright: ignore[reportPrivateUsage]
    script = script.rstrip('/')
    full = script + path or '/'
    path = path or '/'
    stage = script.strip('/') or '$default'
    pairs = [(name, value) for name in req.headers.names() for value in req.headers.every_header(name)]
    body, encoded = _body(req)
    method = req.method
    address = tx.remote_address or '127.0.0.1'
    agent = req.headers.user_agent or ''
    host = req.headers.host or url.base.host or 'localhost'
    now = time.time()

    # The format 2.0 of HTTP APIs and Function URLs, with the path of the mount as its stage
    if app.payload == '2.0':
        headers: dict[str, str] = {}
        cookies: list[str] = []
        for name, value in pairs:
            if (name := name.lower()) == 'cookie':
                cookies += [cookie for cookie in value.split('; ') if cookie]
            else:
                headers[name] = f'{headers[name]},{value}' if name in headers else value
        query: dict[str, str] = {}
        for name, value in url.query.pairs:
            query[name] = f'{query[name]},{value}' if name in query else value
        event: dict[str, Any] = {
            'version': '2.0',
            'routeKey': '$default',
            'rawPath': full,
            'rawQueryString': url.query.to_str(),
            'headers': headers,
            'requestContext': {
                'accountId': ACCOUNT,
                'apiId': API,
                'domainName': host,
                'domainPrefix': host.split('.')[0],
                'http': {
                    'method': method,
                    'path': full,
                    'protocol': f'HTTP/{req.version}',
                    'sourceIp': address,
                    'userAgent': agent,
                },
                'requestId': id,
                'routeKey': '$default',
                'stage': stage,
                'time': time.strftime('%d/%b/%Y:%H:%M:%S +0000', time.gmtime(now)),
                'timeEpoch': int(now * 1000),
            },
            'isBase64Encoded': encoded,
        }
        if cookies:
            event['cookies'] = cookies
        if query:
            event['queryStringParameters'] = query
        if body is not None:
            event['body'] = body
        return event

    # The format 1.0 of REST APIs, with the path of the mount as its stage, in front of the path of the context
    if app.payload == '1.0':
        single: dict[str, str] = {}
        multi: dict[str, list[str]] = {}
        for name, value in pairs:
            single[name] = value
            multi.setdefault(name, []).append(value)
        params: dict[str, str] = {}
        multi_params: dict[str, list[str]] = {}
        for name, value in url.query.pairs:
            params[name] = value
            multi_params.setdefault(name, []).append(value)
        return {
            'version': '1.0',
            'resource': '/{proxy+}',
            'path': path,
            'httpMethod': method,
            'headers': single,
            'multiValueHeaders': multi,
            'queryStringParameters': params or None,
            'multiValueQueryStringParameters': multi_params or None,
            'pathParameters': {'proxy': path.lstrip('/')},
            'stageVariables': None,
            'requestContext': {
                'accountId': ACCOUNT,
                'apiId': API,
                'domainName': host,
                'httpMethod': method,
                'identity': {'sourceIp': address, 'userAgent': agent},
                'path': full,
                'protocol': f'HTTP/{req.version}',
                'requestId': id,
                'requestTimeEpoch': int(now * 1000),
                'resourcePath': '/{proxy+}',
                'stage': stage,
            },
            'body': body,
            'isBase64Encoded': encoded,
        }

    # The events of an Application Load Balancer, with the whole path and the parameters of the query as they were
    # sent, and the headers in lower case, of multiple values when the target group has them
    raw = [tuple(part.split('=', 1)) if '=' in part else (part, '') for part in url.query.to_str().split('&') if part]
    event = {
        'requestContext': {
            'elb': {
                'targetGroupArn': f'arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:targetgroup/{API}/0123456789abcdef'
            }
        },
        'httpMethod': method,
        'path': full,
        'body': body or '',
        'isBase64Encoded': encoded,
    }
    if app.multi_value_headers:
        multi_headers: dict[str, list[str]] = {}
        for name, value in pairs:
            multi_headers.setdefault(name.lower(), []).append(value)
        multi_query: dict[str, list[str]] = {}
        for name, value in raw:
            multi_query.setdefault(name, []).append(value)
        event['multiValueHeaders'] = multi_headers
        event['multiValueQueryStringParameters'] = multi_query
    else:
        event['headers'] = {name.lower(): value for name, value in pairs}
        event['queryStringParameters'] = dict(raw)
    return event


def _is_streaming(req: Any) -> bool:
    return req.method == 'POST' and req.headers.header('Lambda-Runtime-Function-Response-Mode') == 'streaming'


# The status and the headers of a response, or of the prelude of a streaming one, where the headers of multiple values
# take the place of the ones of the same name of one value
def _status(response: dict[str, Any]) -> tuple[int, list[tuple[str, str]]]:
    code = int(response.get('statusCode', 200))
    multi = cast(dict[str, list[Any]], response.get('multiValueHeaders') or {})
    single = cast(dict[str, Any], response.get('headers') or {})
    names = {str(name).lower() for name in multi}
    headers = [(str(name), str(item)) for name, item in single.items() if str(name).lower() not in names]
    headers += [(str(name), str(item)) for name, items in multi.items() for item in items]
    headers += [('Set-Cookie', str(cookie)) for cookie in cast(list[Any], response.get('cookies') or [])]
    return code, headers


def _json(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body or b'{}')
    except ValueError:
        return {}
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


# The message of an error of the function, with its type
def _message(error: dict[str, Any]) -> str:
    kind, message = error.get('errorType'), error.get('errorMessage')
    return f'{kind}: {message}' if kind else str(message)


def _reply(tx: Any, code: int) -> None:
    res = tx.res
    res.code = code
    res.headers.content_type = 'application/json'
    res.body = b'{"status":"OK"}' if code < 400 else b'{"errorMessage":"Not Found"}'
    tx.resume()


# The applications whose execution environments the child of a fork leaves, at the fork. The handler is registered with the
# first environment, after the one of the reactor, which os.register_at_fork calls first, so that the reactor has moved
# to a loop of its own, as a loop of epoll shares its state with the parent
_apps: 'weakref.WeakSet[Pyjo_App_Lambda]' = weakref.WeakSet()
_registered = False


def _register() -> None:
    global _registered
    if not _registered and hasattr(os, 'register_at_fork'):
        _registered = True
        os.register_at_fork(after_in_child=_after_fork_in_child)


def _after_fork_in_child() -> None:
    for app in list(_apps):
        try:
            app._leave()  # pyright: ignore[reportPrivateUsage]
        except Exception:
            pass


new = Pyjo_App_Lambda.new
object = Pyjo_App_Lambda
Lambda = Pyjo_App_Lambda
