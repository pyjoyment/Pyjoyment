"""
Pyjoyment.Command.get - Get command
===================================
::

    Usage: APPLICATION get [OPTIONS] URL [SELECTOR|JSON-POINTER] [COMMANDS]

      ./myapp.py get /
      ./myapp.py get -H 'Accept: text/html' /hello.html 'head > title' text
      ./myapp.py get //sri:secr3t@/secrets.json /1/content
      pyjo get mojolicious.org
      pyjo get -v -r -o 25 -i 50 google.com
      pyjo get -v -H 'Host: mojolicious.org' -H 'Accept: */*' mojolicious.org
      pyjo get -u 'sri:s3cret' https://mojolicious.org
      pyjo get mojolicious.org > example.html
      pyjo get -M PUT mojolicious.org < example.html
      pyjo get -f 'q=Mojolicious' -f 'size=5' https://metacpan.org/search
      pyjo get -M POST -f 'upload=@example.html' mojolicious.org
      pyjo get mojolicious.org 'head > title' text
      pyjo get mojolicious.org .footer all
      pyjo get mojolicious.org a attr href
      pyjo get mojolicious.org '*' attr id
      pyjo get mojolicious.org 'h1, h2, h3' 3 text
      pyjo get https://pypi.org/pypi/Pyjoyment/json /info/version
      pyjo get -H 'Host: example.com' http+unix://%2Ftmp%2Fmyapp.sock/index.html

    Options:
      -C, --charset <charset>              Charset of HTML/XML content, defaults
                                           to auto-detection
      -c, --content <content>              Content to send with request
      -f, --form <name=value>              One or more form values and file
                                           uploads
      -H, --header <name:value>            One or more additional HTTP headers
      -h, --help                           Show this summary of available options
          --home <path>                    Path to home directory of your
                                           application, defaults to the value of
                                           PYJO_HOME or auto-detection
      -i, --inactivity-timeout <seconds>   Inactivity timeout, defaults to the
                                           value of PYJO_INACTIVITY_TIMEOUT or 40
      -k, --insecure                       Do not require a valid TLS certificate
                                           to access HTTPS sites
          --log-format <name>              Format of log messages, "text",
                                           "plain" without time and process, or
                                           "json", defaults to the value of
                                           PYJO_LOG_FORMAT or "text"
      -M, --method <method>                HTTP method to use, defaults to "GET"
      -m, --mode <name>                    Operating mode for your application,
                                           defaults to the value of PYJO_MODE or
                                           "development"
      -o, --connect-timeout <seconds>      Connect timeout, defaults to the value
                                           of PYJO_CONNECT_TIMEOUT or 10
      -r, --redirect                       Follow up to 10 redirects
      -S, --response-size <size>           Maximum response size in bytes,
                                           defaults to 2147483648 (2GiB)
      -u, --user <userinfo>                Alternate mechanism for specifying
                                           colon-separated username and password
      -v, --verbose                        Print request and response headers to
                                           STDERR

:mod:`Pyjoyment.Command.get` performs requests to remote hosts or local
applications.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::get
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/get.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Collection
import Pyjo.DOM
import Pyjo.Exception
import Pyjo.IOLoop
import Pyjo.JSON.Pointer
import Pyjo.Message
import Pyjo.URL
import Pyjo.UserAgent
import Pyjoyment.Command

from Pyjo.JSON import j, to_json
from Pyjo.Util import decode, extract_usage, getopt, warn

import re
import select
import sys
import weakref

from typing import Any, cast


class Pyjoyment_Command_get(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.get` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Perform HTTP request'
    """::

        description = get.description
        get.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = get.usage
        get.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> None:
        """::

            get.run(*sys.argv[1:])

        Run this command.
        """
        # Data from STDIN
        content = _stdin()

        ua: Any = Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton)
        arguments = list(args)
        form: dict[str, list[Any]] = {}
        headers: list[str] = []
        opts = getopt(
            arguments,
            {
                'C|charset=s': None,
                'c|content=s': None,
                'f|form=s': lambda name, value: _form(form, value),
                'H|header=s': headers,
                'i|inactivity-timeout=i': lambda name, value: setattr(ua, 'inactivity_timeout', value),
                'k|insecure': lambda name, value: setattr(ua, 'insecure', True),
                'M|method=s': None,
                'o|connect-timeout=i': lambda name, value: setattr(ua, 'connect_timeout', value),
                'r|redirect': None,
                'S|response-size=i': lambda name, value: setattr(ua, 'max_response_size', value),
                'u|user=s': None,
                'v|verbose': None,
            },
        )
        if not opts:
            raise Pyjo.Exception.new(self.usage)
        if opts.content is not None:
            content = opts.content
        method: str = opts.method or 'GET'
        redirect, verbose = opts.redirect, opts.verbose

        # Left out from Mojolicious: decoding the arguments, which Python has as characters already
        if not arguments:
            raise Pyjo.Exception.new(self.usage)
        url: Any = arguments.pop(0)
        selector = arguments.pop(0) if arguments else None

        # Parse header pairs
        pairs = {m[1]: m[2] for header in headers if (m := re.match(r'^\s*([^:]+)\s*:\s*(.*)$', header))}

        # Detect proxy for absolute URLs
        if not url.startswith('/'):
            ua.proxy.detect()
        else:
            ua.server.app = self.app
        if opts.user:
            url = Pyjo.URL.new(url).set(userinfo=opts.user)
        if redirect:
            ua.max_redirects = 10

        buffer = bytearray()

        @ua.on('start')
        def start(ua: Any, tx: Any) -> None:
            # Verbose
            tx = weakref.proxy(tx)
            if verbose:

                @tx.res.content.on('body')
                def body(content: Any) -> None:
                    warn(_header(tx.req), _header(tx.res))

            # Stream content (ignore redirects)
            @tx.res.content.unsubscribe('read').on('read')
            def read(content: Any, chunk: bytes) -> None:
                if redirect and tx.res.is_redirect:
                    return
                if selector is not None:
                    buffer.extend(chunk)
                else:
                    _write(chunk)

        # Switch to verbose for HEAD requests
        if method == 'HEAD':
            verbose = True
        if form:
            tx = ua.start(ua.build_tx(method, url, pairs, form=form))
        elif content is not None:
            tx = ua.start(ua.build_tx(method, url, pairs, content))
        else:
            tx = ua.start(ua.build_tx(method, url, pairs))
        res = tx.result

        # JSON Pointer
        if selector is None:
            return None
        if not selector or selector.startswith('/'):
            return _json(bytes(buffer), selector)

        # Selector
        charset = opts.charset or res.content.charset or res.default_charset
        return _select(bytes(buffer), selector, charset, *arguments)


def _form(form: dict[str, list[Any]], value: str) -> None:
    if m := re.match(r'^(.+)=(@?)(.+)$', value, re.S):
        form.setdefault(m[1], []).append({'file': m[3]} if m[2] else m[3])


def _header(msg: Pyjo.Message.object) -> str:
    return msg.build_start_line().decode('latin-1') + msg.headers.to_str() + '\n\n'


def _json(buffer: bytes, pointer: str) -> None:
    if not (data := j(buffer)):
        return
    if (data := Pyjo.JSON.Pointer.new(data).get(pointer)) is None:
        return
    _say(to_json(cast(object, data)) if isinstance(data, (dict, list)) else data)


def _say(*values: Any) -> None:
    for value in values:
        if value is not None and (text := str(value)):
            print(text)


def _select(buffer: bytes, selector: str, charset: str | None, *args: str) -> None:
    arguments = list(args)

    # Keep a strong reference to the root
    text = (decode(charset, buffer) if charset else None) or buffer.decode('latin-1')
    dom = Pyjo.DOM.new(text)
    results: Any = dom.find(selector)

    while arguments:
        command = arguments.pop(0)

        # Number
        if re.fullmatch(r'\d+', command):
            index = int(command)
            results = Pyjo.Collection.c(*results[index : index + 1])
            continue

        # Text
        if command == 'text':
            return _say(*results.map('text').each())

        # All text
        if command == 'all':
            return _say(*results.map('all_text').each())

        # Attribute
        if command == 'attr':
            return _say(*results.map('attr', arguments[0] if arguments else '').each())

        # Unknown
        raise Pyjo.Exception.new(f'Unknown command "{command}".\n')

    _say(*results.each())


# Data from sys.stdin, unless it is a terminal or has nothing to read yet
def _stdin() -> str | None:
    try:
        if sys.stdin.isatty() or not select.select([sys.stdin], [], [], 0)[0]:
            return None
    except (AttributeError, OSError, ValueError):
        return None
    return sys.stdin.read()


# The bytes of the response, as Mojo prints them, after what sys.stdout has buffered
def _write(chunk: bytes) -> None:
    sys.stdout.flush()
    if (out := getattr(sys.stdout, 'buffer', None)) is not None:
        out.write(chunk)
        out.flush()
    else:
        sys.stdout.write(chunk.decode('latin-1'))


new = Pyjoyment_Command_get.new
object = Pyjoyment_Command_get
