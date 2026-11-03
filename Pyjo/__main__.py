"""
Run a one-liner with the functions of :mod:`Pyjo`, as ``perl -Mojo -E`` does,
and print the value of an expression. ::

    $ python -m Pyjo 'g("mojolicious.org").dom().at("title").text'
"""

import Pyjo

import os
import sys


# Not in Mojolicious: perl -Mojo -E, as Python has no import on its command line that a one-liner can name
def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        sys.exit('usage: python -m Pyjo CODE [ARGS...]')
    code, sys.argv = args[0], ['-c', *args[1:]]

    # Silent one-liners
    os.environ.setdefault('PYJO_LOG_LEVEL', 'fatal')

    # sys for the arguments of an expression in sys.argv, as @ARGV of perl -E, which an import would make a statement
    namespace = {'__name__': '__main__', 'sys': sys, **{name: getattr(Pyjo, name) for name in Pyjo.__all__}}
    try:
        expression = compile(code, '<string>', 'eval')
    except SyntaxError:
        exec(compile(code, '<string>', 'exec'), namespace)
        return
    if (value := eval(expression, namespace)) is not None:
        # Bytes, as of j or a body, printed as Pyjo.String.Bytes prints them, where print would write their repr
        print(Pyjo.b(value) if isinstance(value, (bytes, bytearray)) else value)


if __name__ == '__main__':
    main()
