"""
Pyjoyment.Command.eval - Eval command
=====================================
::

    Usage: APPLICATION eval [OPTIONS] CODE

      ./myapp.py eval 'print(app.ua.get("/").result.body)'
      ./myapp.py eval 'print(*sorted(app.renderer.helpers), sep="\\n")'
      ./myapp.py eval -v 'app.home'
      ./myapp.py eval -V 'app.renderer.paths'

    Options:
      -h, --help                Show this summary of available options
          --home <path>         Path to home directory of your application,
                                defaults to the value of PYJO_HOME or
                                auto-detection
          --log-format <name>   Format of log messages, "text", "plain" without
                                time and process, or "json", defaults to the
                                value of PYJO_LOG_FORMAT or "text"
      -m, --mode <name>         Operating mode for your application, defaults to
                                the value of PYJO_MODE or "development"
      -v, --verbose             Print return value to sys.stdout
      -V                        Print returned data structure to sys.stdout

:mod:`Pyjoyment.Command.eval` runs code against applications. The code
is Python, with the application as ``app``, and its result is the value of its
last expression. If the result is a promise (then-able), it will wait until
the promise is fulfilled or rejected and the result is returned.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::eval
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/eval.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.Promise
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

import ast

from typing import Any


class Pyjoyment_Command_eval(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.eval` inherits all attributes and methods from
    :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Run code against application'
    """::

        description = eval.description
        eval.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = eval.usage
        eval.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> Any:
        """::

            eval.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        if not (opts := getopt(arguments, {'v|verbose': None, 'V': None})):
            raise Pyjo.Exception.new(self.usage)
        code = arguments.pop(0) if arguments else ''

        # Run code against application
        app = self.app
        # Unlike Mojolicious: Python code, whose value is the one of its last expression, as the value of Perl code is
        # the one of its last statement
        result = _eval(code, {'__name__': '__main__', 'app': app})

        # Handle promises
        values: list[Any] = []
        errors: list[Any] = []
        Pyjo.Promise.resolve(result).then(values.append, errors.append).wait()
        if errors:
            raise errors[0] if isinstance(errors[0], BaseException) else Pyjo.Exception.new(str(errors[0]))
        result = values[0] if values else None
        if result is None or not (opts.verbose or opts.V):
            return result
        if opts.V:
            print(app.dumper(result), end='')
        else:
            print(result)
        return None


def _eval(code: str, namespace: dict[str, Any]) -> Any:
    tree = ast.parse(code, '-e')
    last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    exec(compile(tree, '-e', 'exec'), namespace)
    if not isinstance(last, ast.Expr):
        return None
    return eval(compile(ast.Expression(last.value), '-e', 'eval'), namespace)


new = Pyjoyment_Command_eval.new
object = Pyjoyment_Command_eval
