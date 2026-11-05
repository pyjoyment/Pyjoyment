---
name: porting
description: Port a module of Mojolicious to Pyjoyment, or follow a newer release of Mojolicious, in the framework itself, with the procedure of the tests first, the docstrings of the POD, the markers of what differs from Mojolicious, and the translations of Perl into Python. Use when changing a ported module of Pyjo or Pyjoyment or its ported tests.
---

# Porting from Mojolicious

The target is **Mojolicious 9**. A module is ported from a release of it, the
newest one when the port starts, and its documentation names that release
("Ported from ... of Mojolicious 9.49"); the first ports are from 9.49. The
changes of newer releases are followed in the issue that tracks upstream, and a
change is ported to the modules it touches, whose documentation then names the
newer release. A fix that cannot wait for a release, as a security one, is
ported before it, and the module names the release that will have it. An edit
of a module that ports nothing from upstream leaves its release as it is.

Some modules have no counterpart in Mojolicious: `Pyjo.Test` (inspired by
Perl's `Test::More`), `Pyjo.Prove` (inspired by Perl's `prove`),
`Pyjo.String.*`, `Pyjo.GetOpt` (inspired by `Getopt::Long::Parser`, the engine
of `getopt` of `Pyjo.Util`, where Perl has references to variables as the
targets of the options), `Pyjo.IOLoop.Datagram` (inspired by `dgram` of Node.js),
`Pyjo.Iterator` (a lazy iterator of the elements of an iterable or of an
asynchronous iterable, for `for` and `async for` alike, inspired by the
iterator helpers of JavaScript, with the methods of `Pyjo.Collection`),
`Pyjo.Steps` (the steps of a coroutine that awaits requests, programs and
sleeps, which `run` drives blocking and `run_p` non-blocking, so that the code
of a library is written once for a script and for an action of a server,
where Mojolicious has a blocking and a non-blocking method of each operation;
no event loop runs the coroutine, so it awaits nothing else, not a promise,
whose `__await__` yields what only an event loop knows, and the driver raises
that `TypeError` instead of throwing it into the coroutine, where the `except`
of the errors of a connection would hide it),
`Pyjo.App` (inspired by `Mojo` of Mojolicious 6, the base class of
`Mojolicious` until Mojolicious 7, as `Pyjo_App` is of `Pyjoyment_App`),
`Pyjo.HelloWorld` (an application of pure Pyjo, where `Mojo::HelloWorld` is
one of Mojolicious, which `Pyjoyment.HelloWorld` ports), `Pyjo.App.WSGI` (the
application of Pyjo that runs a WSGI application, inspired by
`Mojolicious::Plugin::MountPSGI` of CPAN, the reverse of `Pyjo.Server.WSGI`),
`Pyjo.App.ASGI` (the application of Pyjo that runs an ASGI application, the
reverse of `Pyjo.Server.ASGI`), `Pyjo.App.FastCGI` (the application of Pyjo
that runs a FastCGI application, as PHP on php-fpm, through a connection to
it, the reverse of `Pyjo.Server.FastCGI`), `Pyjo.App.CGI` (the application of
Pyjo that runs a CGI program in a process of its own for each request, the
reverse of `Pyjo.Server.CGI`, inspired by `Mojolicious::Plugin::CGI` of CPAN,
whose base class has the response of CGI that `Pyjo.App.FastCGI` shares),
`Pyjo.App.Lambda` (the application of Pyjo that runs an event function of AWS
Lambda in a process of its own, through the Runtime API of Lambda, which it
serves, the reverse of `Pyjo.Server.Lambda`, whose runtime client runs a
handler of Python there),
`Pyjo.IOLoop.ChildProcess` (a program in a process of its own, with its
standard input, output and error as `Pyjo.IOLoop.Stream` objects, inspired by
`child_process` of Node.js, whose standard input is a stream that closes when
a write fails, as a stream handles an error of a write only when it reads, as
Mojo does, so that a pipe that is only written would be watched for ever after
the program closes it, and a reactor of poll reports its hang-up when it
watches for nothing),
`Pyjo.IOLoop.Stdio` (the standard input and output of the process as one
stream, inspired by `process.stdin` and `process.stdout` of Node.js),
`Pyjo.IOLoop.Messages` (a stream of messages on a stream of bytes, with the
framings of the transport stdio of MCP, of LSP and of Native Messaging),
`Pyjo.Server.Stdio` and `Pyjoyment.Command.stdio` (the server and the command
of a protocol on the standard input and output, which the application gives
with a subscriber of the event `stream` of the server, inspired by
`Pyjo.Server.Daemon` and its command),
`Pyjo.Server.Lambda`
and `Pyjoyment.Command.lambda` (the server and the command of the event
functions of AWS Lambda, inspired by `Pyjo.Server.WSGI` and its command, and
the client of the Runtime API of Lambda, `python -m Pyjo.Server.Lambda`,
which runs any handler, with `http.client` outside of the event loop, as a
handler that runs an event loop of its own, as Mangum, cannot run in one),
`Pyjoyment.Command.Author.generate.lambda_zip` (the ZIP files of an event
function of AWS Lambda on a custom runtime, with a layer of the Python of
python-build-standalone, which uv installs, inspired by `generate dockerfile`),
`Pyjoyment.Command.Author.generate.kubernetes` (the manifests of Kubernetes
for Kustomize, a base and the overlays `dev`, on the image of uv with the
application in a ConfigMap, and `prod`, on the image of `generate dockerfile`,
inspired by `generate dockerfile`),
`Pyjo.Server.FastCGI` and `Pyjoyment.Command.fastcgi` (FastCGI on the
connections of the listen locations `fcgi://` and `fcgi+unix://` of
`Pyjo.Server.Daemon`, written from the specification of FastCGI 1.0, and the
command of a web server that starts the application with its listen socket
as the file descriptor 0, inspired by `Pyjo.Server.CGI` and its command),
`Pyjo.Server.Prethread` and `Pyjoyment.Command.prethread` (the server of
`Pyjo.Server.Prefork` with threads for the worker processes, each a copy of
the server with the event loop of its thread and the duplicates of the listen
sockets of the manager, or the sockets themselves on Windows, where `accept` of
a duplicate can block when another one accepts the connection, as Thrall is Starlight with threads, and its command,
a subclass of the one of `prefork`),
`Pyjoyment.Plugin.AllowedHosts` (the validation of `Host` and `Origin`
against DNS rebinding, which the transport of MCP over HTTP requires of a
server on localhost, as the middleware of the MCP SDK and the hosts of
Django have it, in a hook of `before_dispatch` or the helper `allowed_hosts`
of `under`, as a condition of a route that fails lets the next route match),
`Pyjoyment.Plugin.Health` (the liveness and the readiness of containers and
orchestrators, with the endpoints of Kubernetes, in a hook of `around_dispatch`,
as a hook of `before_dispatch`, as the one of `AllowedHosts`, would reject the
`Host` of the address of a pod, and the readiness of a server that stops
gracefully from `is_stopping` of `Pyjo.IOLoop.singleton`, the event loop of
the thread that serves the request, as the hook `before_server_start` comes
once, in the manager, and a worker of `Pyjo.Server.Prethread` has the loop of
its thread),
`Pyjoyment.Plugin.PyRenderer` (the renderer of template strings, inspired by
`Mojolicious::Plugin::EPLRenderer`), `Pyjoyment.Plugin.TOMLConfig` (inspired
by `Mojolicious::Plugin::NotYAMLConfig`, for the format of configuration of
the standard library), `Pyjo.TOML` (the dumper of TOML, which the standard library only reads),
`Pyjoyment.Plugin.INIConfig` (inspired by `Mojolicious::Plugin::NotYAMLConfig`, for the INI
of `~/.aws/config`, `php.ini` and others), `Pyjo.INI` (the INI of those files, whose
tests compare it with the parser of botocore),
`Pyjo.JSON.Schema` (JSON Schema 2020-12 from the type hints of Python and
from a builder inspired by zod, and its validation, written from the
specification, whose tests compare the schemas with the ones of pydantic and
of zod, and run the official test suite of JSON Schema on the validation),
`Pyjo.JSON.RPC` (JSON-RPC 2.0, its server and its client, without a
transport, written from the specification, whose first consumer is the
distribution of MCP, and whose `to_action` makes an action of a route of
Pyjoyment, which takes the controller from the route, as `Pyjo` does not import
`Pyjoyment`, and whose `serve` serves a stream of messages in both directions),
`Pyjo.URL.Template` (the URI Templates of RFC 6570, written from the RFC,
whose tests are its examples, with their expansion and the match of a URI,
which the RFC leaves to the implementations, from both ends of the URI, so
that a URI of a client takes a time linear in its length, and one expression
takes what the others leave, whose first consumer is the distribution of MCP,
with the templates of its resources),
`Pyjo.Test.pytest_plugin` (the plugin of pytest, which runs the test scripts
as `Pyjo.Prove` does and the functions of `Pyjo.Test` in the tests of pytest),
`Pyjo.YAML` (the subset of YAML of `CPAN::Meta::YAML`,
which `Mojolicious::Plugin::NotYAMLConfig` reads, written anew, as the license
of the Perl module is that of Perl 5, with its regular expressions) and the
helpers in `Pyjo.Util` that turn statements into expressions. These extras follow their inspiration where it
helps, without porting it, and their tests are written for them rather than
ported.

`Pyjo.Util` is the port of `Mojo::Util` and of `Mojo::BaseUtil`, which
`Mojo::Util` exports again; the subtests of `t/mojo/base_util.t` are those
of `t/mojo/util.t`, so it has no test file of its own. Next to them,
`Pyjo.Util` has helpers of its own, for Python. A function of Mojo that waits
for a module that is not ported yet has a `# TODO:` comment in its place. A
function that works on characters in Mojo takes a `str`, and also `bytes`
where a ported module needs them, like `url_unescape`.

A module is ported anew from Mojolicious, not migrated from the existing
Python code. The existing Python module is a reference for how Perl idioms
were translated before, not a base to patch: it follows an older Mojo and
carries compromises that a fresh port does not need.

```sh
git clone https://github.com/mojolicious/mojo.git
git -C mojo checkout v9.49
```

For each module:

1. Port its tests from `t/mojo/*.t` first, keeping Mojo's test names and
   order, one assertion for one, without folding repeated ones into a loop
   or chaining the assertions of `Pyjo.Test`, so that the diff of a newer
   Mojolicious applies to them. Mojo's tests are the specification.
2. Port the module from `lib/Mojo/*.pm` until the tests pass.
3. Port its POD into the docstrings: the same sections in the same order
   (synopsis, description, events, attributes, methods, operators, see also)
   and Mojo's wording, with Python names and examples. The POD is the source of
   the Python documentation. Sphinx lists the classes after the module
   docstring, so "See also" ends the module docstring, before them. The
   synopsis of a module whose class it makes or subclasses starts with its
   first example in the form of Python, `from Pyjo.URL import URL` and
   `URL(...)`, which shows that both forms are correct. A test in `t/docs/`
   runs the examples.
4. Name the source at the end of "See also", as a link to the file at the tag
   of the release (`https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Date.pm`),
   annotate the module and put it on pyright's strict list.
5. Check the module off in the porting inventory issue, which lists every
   module of the target Mojolicious with its Pyjoyment counterpart.

Code that has no counterpart in the Mojolicious module or in its test, such
as a method, a branch, an assertion or a form of an argument for Python
only, has a comment that starts with `# Not in Mojolicious:` and says what it
is for, so that the diff of a newer Mojolicious can be applied around it.
This lists them:

```sh
grep -rn "Not in Mojolicious" Pyjo t/Pyjo
```

It is a comment, not a part of the docstring: the documentation describes
the API as it is. Translations of Perl idioms, as listed below, are Mojo's
code and are not marked.

A method of Mojolicious that has another name in Pyjoyment than the
translations below give it, as `to_rfc3339` for Mojo's `to_datetime`, has a
comment that starts with `# Renamed from Mojolicious:` and names the Mojo
method, in the module and in its ported tests, where the diff of a newer
Mojolicious uses the old name.

A method or an assertion of Mojolicious that is left out on purpose has a
comment where it would be, in the order of the Mojo module or test, that
starts with `# Left out from Mojolicious:`, names what is left out and says
why, so that its absence is not taken for an omission.

Behaviour that differs from Mojolicious on purpose has a comment that starts
with `# Unlike Mojolicious:`, says what Mojo does, and why the port does
otherwise, so that a newer Mojolicious does not bring the old behaviour back.
Where the difference comes from a bug of Mojolicious, the bug also goes to
the issue that collects them.

A mistake that Python makes likely and Perl does not, as a helper without its
call (`c.ua.get_p` for `c.ua().get_p`), the response that an action returns as
a view of another framework, or a callback with other arguments than the ones
it gets, which Perl does not check, has a hint in its message that names the
fix, after the message of Mojolicious, which the tests of Mojolicious still
match. The hint goes where the error is raised or logged already, so that a
request that succeeds pays nothing: `_call_hint` of `Pyjo.Util` adds it to the
`TypeError` of the call of a callback itself, not of its body, and `_suggest`
names the attribute that a wrong name most likely meant, as `Did you mean
"req"?` for `c.request`. A method that only gives a hint, as `__getattr__` of
a promise, is defined under `if not TYPE_CHECKING:`, as type checkers would
take any attribute of the class for one. A mistake that is valid code, which
no error tells, is for the documentation and the guides of the coding agents.

These markers are for what stays. What waits for a module that is not ported
yet, as a method left out, a stand-in for a class of Mojolicious or a test
that runs without a command, has a comment that starts with `# TODO:` and
says what to do and when, so that the port of that module finds it:

```sh
grep -rn "TODO:" Pyjo Pyjoyment t
```

Mojo's tests and the behaviour of its code at the tag are the reference, not
its POD: the examples in the POD are not tested and can be wrong. Where they
disagree, run the Perl code from the clone (`perl -Imojo/lib -MMojo::URL -e ...`)
and port what it does.

A bug or a quirk of Mojolicious itself, found while porting, goes to the issue
that collects them, with a Perl command that reproduces it at the tag and what
the port does about it. Reporting it upstream is a decision of its own.

Moving a ported module to a newer release is the difference between the two
versions, applied to code, tests and docstrings alike:

```sh
git -C mojo diff v9.49 v9.50 -- lib/Mojo/URL.pm t/mojo/url.t
```

Perl and Python differ in a few places that a port must translate rather than copy, which [translations.md](translations.md) lists: read it before a port or a change of ported code.
