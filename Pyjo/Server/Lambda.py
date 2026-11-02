"""
Pyjo.Server.Lambda - AWS Lambda server
======================================
::

    from Pyjo.Server.Lambda import Lambda

    server = Lambda()


    @server.unsubscribe('request').on('request')
    def request(server, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()


    handler = server.to_lambda_app()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Server.Lambda

    server = Pyjo.Server.Lambda.new()


    @server.unsubscribe('request').on('request')
    def request(server, tx):
        # Request
        method = tx.req.method
        path = tx.req.url.path

        # Response
        tx.res.code = 200
        tx.res.headers.content_type = 'text/plain'
        tx.res.body = f'{method} request for {path}!'.encode()

        # Resume transaction
        tx.resume()


    handler = server.to_lambda_app()

:mod:`Pyjo.Server.Lambda` allows :mod:`Pyjoyment` applications to run as
event functions of `AWS Lambda <https://aws.amazon.com/lambda/>`_, whose
handler gets the event of an HTTP request and returns its response, with the
payload formats of API Gateway, of Function URLs and of Application Load
Balancers:

* the format 2.0 of HTTP APIs and Function URLs, whose ``cookies`` are the
  ``Cookie`` header of the request and the ``Set-Cookie`` headers of the
  response, and whose stage, other than ``$default``, is the base path of the
  URL;
* the format 1.0 of REST APIs, whose stage is the base path of the URL, and
  whose decoded parameters of the query are encoded again;
* the events of Application Load Balancers, whose parameters of the query are
  as they were sent, with the headers of multiple values when the target
  group has them, and only the last value of a header otherwise.

The event and the context of the invocation are ``lambda.event`` and
``lambda.context`` of :attr:`~Pyjo.Message.Request.Pyjo_Message_Request.env`
of the request. A body that the event has in Base64 is decoded, and the body
of a response is Base64 too, unless its content type is text, JSON, XML,
JavaScript or YAML that is UTF-8. The handler is synchronous, so the event
loop of :mod:`Pyjo.IOLoop` runs until the response is complete, which can
come later and in chunks, whose framing is left out, as the response of an
event function is the whole body. ::

    # The handler "myapp.handler" of an event function
    handler = Pyjo.Server.Lambda.new(app=app).to_lambda_app()

With the invoke mode ``RESPONSE_STREAM`` of
:attr:`~Pyjo.Server.Lambda.Pyjo_Server_Lambda.invoke_mode`, which
follows the one of the Function URL or the response transfer mode of the
REST API of API Gateway, the handler returns an iterator of the body as it is
written instead, which the runtime client below streams: the status and the
headers as JSON, 8 null bytes, and the chunks of the body as they come, with
the content type ``application/vnd.awslambda.http-integration-response`` of
the iterator. The events of Application Load Balancers, which have no
streaming, get the whole response. ::

    # PYJO_LAMBDA_INVOKE_MODE=RESPONSE_STREAM in the environment of the function
    handler = Pyjo.Server.Lambda.new(app=app).to_lambda_app()

Events
------

:mod:`Pyjo.Server.Lambda` inherits all events from :mod:`Pyjo.Server`.

Attributes
----------

:mod:`Pyjo.Server.Lambda` inherits all attributes from :mod:`Pyjo.Server` and
implements :attr:`~Pyjo.Server.Lambda.Pyjo_Server_Lambda.invoke_mode`.

Runtime client
--------------
::

    Usage: python -m Pyjo.Server.Lambda [OPTIONS] [HANDLER]

      python -m Pyjo.Server.Lambda myapp.handler
      AWS_LAMBDA_RUNTIME_API=127.0.0.1:9001 python -m Pyjo.Server.Lambda myapp.handler

    Options:
      -h, --help   Show this message

The client of the `Runtime API
<https://docs.aws.amazon.com/lambda/latest/dg/runtimes-api.html>`_ of AWS
Lambda, which runs the handler of an event function, ``module.function`` or
the one of ``_HANDLER``, as a custom runtime does: it gets the next
invocation from the API of ``AWS_LAMBDA_RUNTIME_API``, calls the handler with
its event and a context, and posts the value that the handler returns as
JSON, or its exception, one invocation after another. An iterator of bytes
that the handler returns is a streaming response, chunked as it is iterated,
of the ``content_type`` of the iterator or ``application/octet-stream``, with
an exception in the middle of it in the trailers of the error, as the Runtime
API takes it, and an exception before its first chunk as the error of the
invocation. An exception of the
import of the handler is an error of the initialization, which ends the
client. The handler can be any handler of an event function, also one of
another framework, which runs an event loop of its own, as the client runs
outside of the event loop of :mod:`Pyjo.IOLoop`, and the directory of the
handler, ``LAMBDA_TASK_ROOT`` or the current one, is the first one of
:data:`sys.path`. ::

    #!/bin/sh
    # The bootstrap of a custom runtime, as provided.al2023
    exec python3 -m Pyjo.Server.Lambda

The context has the attributes and the method of the context of the Python
runtime of Lambda: ``aws_request_id``, ``invoked_function_arn``,
``function_name``, ``function_version``, ``memory_limit_in_mb``,
``log_group_name``, ``log_stream_name``, ``identity``, ``client_context``
and ``get_remaining_time_in_millis()``, from the headers of the invocation
and the variables of the environment that Lambda sets.

See also
--------

:mod:`Pyjoyment.Command.lambda`, :mod:`Pyjo.Server.WSGI`, :mod:`Pyjoyment`,
https://mojolicious.org.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.Parameters
import Pyjo.Server
import Pyjo.Transaction

from Pyjo.Server.WSGI import _IO  # pyright: ignore[reportPrivateUsage]
from Pyjo.Util import b64_encode, die, extract_usage, getopt, url_escape

import base64
import http.client
import importlib
import json
import os
import re
import sys
import time
import traceback
import wsgiref.util

from collections.abc import Callable, Iterator, Sequence
from typing import Any, NoReturn, Self, cast


type Event = dict[str, Any]
type Response = dict[str, Any]
type Handler = Callable[[Event, Any], Response | Iterator[bytes]]

# The content types of a body that is text, which goes as it is, where other bodies go in Base64
_RE_TEXT = re.compile(r'(?:text/|application/(?:[\w.-]+\+)?(?:json|xml|javascript|yaml)\b)', re.I)


class Pyjo_Server_Lambda(Pyjo.Server.object):
    """
    :mod:`Pyjo.Server.Lambda` inherits all attributes and methods from
    :mod:`Pyjo.Server` and implements the following new ones.
    """

    def __init__(self, *, invoke_mode: str | None = None, **kwargs: Any) -> None:
        """::

            server = Pyjo.Server.Lambda.new()
            server = Pyjo.Server.Lambda.new(invoke_mode='RESPONSE_STREAM')

        Construct a new :mod:`Pyjo.Server.Lambda` object.
        """
        super().__init__(**kwargs)
        self._invoke_mode = invoke_mode

    @property
    def invoke_mode(self) -> str:
        """::

            mode = server.invoke_mode
            server.invoke_mode = 'RESPONSE_STREAM'

        The mode of the invocations, as the ``InvokeMode`` of the Function
        URL, or the response transfer mode of API Gateway, of the function,
        which the function does not learn from its invocations: ``BUFFERED``
        or ``RESPONSE_STREAM``, defaults to the value of the
        ``PYJO_LAMBDA_INVOKE_MODE`` environment variable or ``BUFFERED``.
        """
        if self._invoke_mode is None:
            self._invoke_mode = os.environ.get('PYJO_LAMBDA_INVOKE_MODE') or 'BUFFERED'
        return self._invoke_mode

    @invoke_mode.setter
    def invoke_mode(self, value: str) -> None:
        self._invoke_mode = value

    # reportIncompatibleMethodOverride "Method "run" overrides class "Pyjo_Server" in an incompatible manner": run takes
    # the event and the context, as the run of Pyjo.Server.WSGI takes the environment
    def run(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, event: Event, context: Any = None
    ) -> Response | Iterator[bytes]:
        """::

            response = server.run(event, context)

        Run the event of an HTTP request and return its response, or the
        iterator of a streaming response with the invoke mode
        ``RESPONSE_STREAM``.
        """
        request = _Request(event)
        env = request.environ()
        env['lambda.event'] = event
        env['lambda.context'] = context

        tx = self.build_tx()
        req = tx.req.parse(env)
        tx.remote_address = request.remote_address
        if request.body:
            req.parse(request.body)

        # The response, which the application can give later
        resumed: list[bool] = []

        def resume(tx: Pyjo.Transaction.object) -> None:
            resumed.append(True)

        tx.on('resume', resume)
        self.emit('request', tx)
        while not resumed:
            Pyjo.IOLoop.one_tick()

        # The body, which can come later and in chunks, without their framing
        res = tx.res.fix_headers()
        body = _IO(tx, tx.is_empty, res.content.is_chunked)

        # The headers without the hop-by-hop ones, as the body is without its framing
        headers = [(name, value) for name, value in res.headers.to_list() if not wsgiref.util.is_hop_by_hop(name)]
        code = res.code or 404

        # The body as it is written, after the status and the headers, where the events of an Application Load Balancer
        # have no streaming
        if self.invoke_mode == 'RESPONSE_STREAM' and not request.alb:
            return _Stream(request.headers({'statusCode': code}, headers), body)

        # The whole body
        try:
            content = b''.join(body)
        finally:
            body.close()
        response = request.headers({'statusCode': code}, headers)
        if request.alb:
            response['statusDescription'] = f'{code} {res.message or res.default_message(code)}'

        # Text as it is, other content in Base64
        content_type = res.headers.content_type or ''
        if not content or _RE_TEXT.match(content_type) and _is_utf8(content):
            response['body'] = content.decode()
            response['isBase64Encoded'] = False
        else:
            response['body'] = b64_encode(content, '')
            response['isBase64Encoded'] = True
        return response

    def run_runtime(self) -> None:
        """::

            server.run_runtime()

        Run the application for the invocations of the Runtime API of
        ``AWS_LAMBDA_RUNTIME_API``, one after another, as the runtime client
        does with a handler, until the process ends, so that the script of
        the application is the runtime of a custom runtime itself.
        """
        if not (api := os.environ.get('AWS_LAMBDA_RUNTIME_API')):
            raise Pyjo.Exception.new('AWS_LAMBDA_RUNTIME_API is not set')

        # Preload application
        self.app.server(self)
        runtime = _Runtime(api)
        try:
            runtime.loop(self.run)
        finally:
            runtime.connection.close()

    def to_lambda_app(self) -> Handler:
        """::

            handler = server.to_lambda_app()

        Turn :mod:`Pyjoyment` application into the handler of an event
        function of AWS Lambda.
        """
        # Preload application and wrap it
        self.app.server(self)

        def handler(event: Event, context: Any) -> Response | Iterator[bytes]:
            return self.run(event, context)

        return handler


# The streaming response of an HTTP integration of Function URLs and API Gateway: the status and the headers as JSON, 8
# null bytes and the body as it is written
class _Stream(Iterator[bytes]):
    content_type = 'application/vnd.awslambda.http-integration-response'

    def __init__(self, response: Response, body: _IO) -> None:
        self._prelude: bytes | None = json.dumps(response, separators=(',', ':')).encode() + b'\x00' * 8
        self._body = body

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> bytes:
        if (prelude := self._prelude) is not None:
            self._prelude = None
            return prelude
        return next(self._body)

    def close(self) -> None:
        self._body.close()


# The request of an event, in one of its payload formats
class _Request:
    def __init__(self, event: Event) -> None:
        self.event = event
        context: dict[str, Any] = event.get('requestContext') or {}
        self.alb = 'elb' in context
        self.v2 = event.get('version') == '2.0'
        self.pairs: list[tuple[str, str]]

        # The body, which can be in Base64
        body: str | None = event.get('body')
        if body is None:
            self.body = b''
        elif event.get('isBase64Encoded'):
            self.body = base64.b64decode(body)
        else:
            self.body = body.encode()

        # The format 2.0, of HTTP APIs and Function URLs
        if self.v2:
            http: dict[str, Any] = context.get('http') or {}
            self.method: str = http.get('method') or 'GET'
            self.path: str = event.get('rawPath') or '/'
            self.query: str = event.get('rawQueryString') or ''
            self.pairs = _pairs(event.get('headers'))
            if cookies := event.get('cookies'):
                self.pairs.append(('cookie', '; '.join(cookies)))
            self.remote_address: str | None = http.get('sourceIp')
            self.protocol: str | None = http.get('protocol')
            self.https = True

            # A stage other than the default one in front of the path
            stage = context.get('stage')
            prefix = f'/{stage}'
            within = stage and stage != '$default' and (self.path == prefix or self.path.startswith(f'{prefix}/'))
            self.base = prefix if within else None
            return

        # The format 1.0, of REST APIs, and Application Load Balancers
        self.method = event.get('httpMethod') or 'GET'
        self.path = event.get('path') or '/'
        multi = event.get('multiValueHeaders')
        self.pairs = _pairs(multi if multi is not None else event.get('headers'))
        pairs = _pairs(event.get('multiValueQueryStringParameters') or event.get('queryStringParameters'))

        # The parameters of an Application Load Balancer as they were sent, and the decoded ones of a REST API
        if self.alb:
            self.query = '&'.join(f'{name}={value}' for name, value in pairs)
        else:
            query = Pyjo.Parameters.new()
            for name, value in pairs:
                query.append(name, value)
            self.query = query.to_str()
        identity: dict[str, Any] = context.get('identity') or {}
        self.remote_address = identity.get('sourceIp')
        self.protocol = context.get('protocol')
        self.https = any(name.lower() == 'x-forwarded-proto' and value == 'https' for name, value in self.pairs)

        # The stage of a REST API in front of the path
        path: str = context.get('path') or ''
        self.base = path[: -len(self.path)] or None if path != self.path and path.endswith(self.path) else None

    def environ(self) -> dict[str, Any]:
        # The CGI environment that Pyjo.Message.Request parses, with a path whose bytes beyond ASCII are
        # percent-encoded, as the path is escaped
        env: dict[str, Any] = {
            'REQUEST_METHOD': self.method,
            'PATH_INFO': url_escape(self.path.encode(), rb'\x80-\xff').decode('ascii'),
            'QUERY_STRING': self.query,
            'SERVER_PROTOCOL': self.protocol or 'HTTP/1.1',
        }
        if self.base is not None:
            env['SCRIPT_NAME'] = self.base
        if self.https:
            env['HTTPS'] = 'on'
        for name, value in self.pairs:
            key = 'HTTP_' + name.upper().replace('-', '_')

            # The body is whole, without the chunked framing
            if key == 'HTTP_TRANSFER_ENCODING':
                continue
            env[key] = f'{env[key]}{"; " if key == "HTTP_COOKIE" else ", "}{value}' if key in env else value
        if self.body:
            env['CONTENT_LENGTH'] = str(len(self.body))
        return env

    def headers(self, response: Response, pairs: list[tuple[str, str]]) -> Response:
        # The format 2.0 with its cookies, and its other headers of multiple values with commas
        if self.v2:
            headers: dict[str, str] = {}
            cookies: list[str] = []
            for name, value in pairs:
                if (name := name.lower()) == 'set-cookie':
                    cookies.append(value)
                else:
                    headers[name] = f'{headers[name]},{value}' if name in headers else value
            response['headers'] = headers
            if cookies:
                response['cookies'] = cookies

        # The headers of multiple values of the event, or the last value of each header
        elif 'multiValueHeaders' in self.event:
            multi: dict[str, list[str]] = {}
            for name, value in pairs:
                multi.setdefault(name, []).append(value)
            response['multiValueHeaders'] = multi
        else:
            response['headers'] = dict(pairs)
        return response


def main(argv: Sequence[str] | None = None) -> NoReturn:
    """::

        main(['myapp.handler'])

    The command line interface of the runtime client: parse the options and
    run the handler for the invocations of the Runtime API.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    opts = getopt(args, {'h|help': None})
    name = args[0] if args else os.environ.get('_HANDLER')
    if not opts or opts.help or not name:
        # The usage without its last newline, as SystemExit writes the message with one
        die(extract_usage(__file__, section='Runtime client').rstrip('\n'))
    if not (api := os.environ.get('AWS_LAMBDA_RUNTIME_API')):
        die('AWS_LAMBDA_RUNTIME_API is not set')
    runtime = _Runtime(api)
    try:
        runtime.run(name)
    finally:
        runtime.connection.close()
    sys.exit(0)


# An invocation of the Runtime API, as the context of the Python runtime of Lambda has it
class _Context:
    def __init__(self, headers: http.client.HTTPMessage) -> None:
        self.aws_request_id = headers.get('Lambda-Runtime-Aws-Request-Id', '')
        self.invoked_function_arn = headers.get('Lambda-Runtime-Invoked-Function-Arn', '')
        self.function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        self.function_version = os.environ.get('AWS_LAMBDA_FUNCTION_VERSION')
        self.memory_limit_in_mb = os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE')
        self.log_group_name = os.environ.get('AWS_LAMBDA_LOG_GROUP_NAME')
        self.log_stream_name = os.environ.get('AWS_LAMBDA_LOG_STREAM_NAME')
        self.identity = _json(headers.get('Lambda-Runtime-Cognito-Identity'))
        self.client_context = _json(headers.get('Lambda-Runtime-Client-Context'))
        deadline = headers.get('Lambda-Runtime-Deadline-Ms')
        self.deadline = int(deadline) if deadline and deadline.isdigit() else None

    def get_remaining_time_in_millis(self) -> int:
        if self.deadline is None:
            return 0
        return max(self.deadline - int(time.time() * 1000), 0)


# The client of the Runtime API, with a connection of its own, outside of the event loop
class _Runtime:
    PREFIX = '/2018-06-01/runtime'

    def __init__(self, api: str) -> None:
        self.connection = http.client.HTTPConnection(api)

    def run(self, name: str) -> None:
        try:
            handler = _handler(name)
        except Exception as e:
            self.post(f'{self.PREFIX}/init/error', _error(e, 'Runtime.ImportModuleError'), 'Runtime.ImportModuleError')
            raise SystemExit(1) from None
        self.loop(handler)

    # The invocations, one after another, for the handler
    def loop(self, handler: Callable[[Any, Any], Any]) -> None:
        while True:
            self.connection.request('GET', f'{self.PREFIX}/invocation/next')
            res = self.connection.getresponse()
            event = json.loads(res.read() or b'null')
            context = _Context(res.headers)
            if trace := res.headers.get('Lambda-Runtime-Trace-Id'):
                os.environ['_X_AMZN_TRACE_ID'] = trace
            else:
                os.environ.pop('_X_AMZN_TRACE_ID', None)
            path = f'{self.PREFIX}/invocation/{context.aws_request_id}'
            try:
                result = handler(event, context)
                if isinstance(result, Iterator):
                    self.stream(path, cast(Iterator[bytes], result))
                    continue
                body = json.dumps(result).encode()
            except Exception as e:
                self.post(f'{path}/error', _error(e), 'Unhandled')
                continue
            self.post(f'{path}/response', body)

    def post(self, path: str, body: bytes, error: str | None = None) -> None:
        headers = {'Content-Type': 'application/json'}
        if error is not None:
            headers['Lambda-Runtime-Function-Error-Type'] = error
        self.connection.request('POST', path, body, headers)
        self.connection.getresponse().read()

    # A streaming response, chunked as it is written, with an exception in the middle of it in the trailers, and the
    # connection closed after it, as the Runtime API asks
    def stream(self, path: str, body: Iterator[bytes]) -> None:
        try:
            # The first chunk before the request, so that an exception before the response is the error of the
            # invocation, which the Runtime API takes only before it
            try:
                chunk = next(body, b'')
            except Exception as e:
                self.post(f'{path}/error', _error(e), 'Unhandled')
                return

            connection = self.connection
            connection.putrequest('POST', f'{path}/response', skip_accept_encoding=True)
            connection.putheader('Content-Type', getattr(body, 'content_type', 'application/octet-stream'))
            connection.putheader('Lambda-Runtime-Function-Response-Mode', 'streaming')
            connection.putheader('Transfer-Encoding', 'chunked')
            connection.putheader('Trailer', 'Lambda-Runtime-Function-Error-Type, Lambda-Runtime-Function-Error-Body')
            connection.endheaders()
            trailers = b''
            try:
                while True:
                    if chunk:
                        connection.send(b'%x\x0d\x0a%s\x0d\x0a' % (len(chunk), chunk))
                    chunk = next(body)
            except StopIteration:
                pass
            except Exception as e:
                error = b64_encode(_error(e), '')
                trailers = (
                    f'Lambda-Runtime-Function-Error-Type: Unhandled\x0d\x0a'
                    f'Lambda-Runtime-Function-Error-Body: {error}\x0d\x0a'
                ).encode()
            connection.send(b'0\x0d\x0a' + trailers + b'\x0d\x0a')
            connection.getresponse().read()
            connection.close()
        finally:
            if close := getattr(body, 'close', None):
                close()


# The error of an exception, as the Python runtime of Lambda posts it
def _error(e: Exception, type: str | None = None) -> bytes:
    stack = traceback.format_list(traceback.extract_tb(e.__traceback__))
    return json.dumps({'errorMessage': str(e), 'errorType': type or e.__class__.__name__, 'stackTrace': stack}).encode()


# The handler of a name "module.function", from the directory of the task first
def _handler(name: str) -> Callable[[Any, Any], Any]:
    module, _, function = name.rpartition('.')
    if not module:
        raise ValueError(f'Bad handler "{name}": not a module and a function')
    root = os.environ.get('LAMBDA_TASK_ROOT') or os.getcwd()
    if root not in sys.path:
        sys.path.insert(0, root)
    handler = getattr(importlib.import_module(module), function, None)
    if not callable(handler):
        raise AttributeError(f'Handler "{function}" missing on module "{module}"')
    return handler


def _json(value: str | None) -> Any:
    return json.loads(value) if value else None


def _is_utf8(body: bytes) -> bool:
    try:
        body.decode()
    except UnicodeDecodeError:
        return False
    return True


# The pairs of names and values of a dict of the event, whose values can be lists of values
def _pairs(values: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for name, value in cast(dict[str, Any], values or {}).items():
        for item in cast(list[Any], value) if isinstance(value, list) else [value]:
            pairs.append((name, str(item)))
    return pairs


new = Pyjo_Server_Lambda.new
object = Pyjo_Server_Lambda
Lambda = Pyjo_Server_Lambda

if __name__ == '__main__':
    main()
