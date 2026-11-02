"""
Pyjo.GetOpt - Command line options
==================================
::

    from Pyjo.GetOpt import GetOpt

    getopt = GetOpt()

    # The value goes to the result
    getopt.option('m|mode=s')

    opts = getopt.parse(['-m', 'production', 'myapp.py'])
    if not opts:
        raise SystemExit('Usage: ...')
    print(opts.mode)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GetOpt

    getopt = Pyjo.GetOpt.new()

    # The value goes to the result
    getopt.option('m|mode=s')

    # The values go to a list
    listen = []
    getopt.option('l|listen=s', listen)

    # A callback gets the value
    @getopt.on('i|inactivity-timeout=i')
    def timeout(name, value):
        print(f'{name}: {value}')

    opts = getopt.parse(['-m', 'production', '-l', 'http://*:8080', 'myapp.py'])
    if not opts:
        raise SystemExit('Usage: ...')
    print(opts.mode)

:mod:`Pyjo.GetOpt` extracts options from a list of command line arguments,
the way `Getopt::Long <https://metacpan.org/pod/Getopt::Long>`_ of Perl does
with the configuration that :func:`Pyjo.Util.getopt` gives it, as the
commands of Mojolicious do. It is the engine of :func:`Pyjo.Util.getopt`,
with decorators for the callbacks of the options.

An option is ``-name`` or ``--name``, with its value after it or after ``=``,
as ``--mode production``, ``--mode=production`` or ``-m production``. The
names are case sensitive and are not abbreviated, and the options of a
single letter are not bundled. The arguments that are not options stay in the
list, in their order, and ``--`` ends the options.

An unknown option, an option without its value and a value of a wrong type are
errors: their messages go to ``sys.stderr``, as warnings, the parsing goes on,
and the result is false.

Options
-------

The specification of an option is its names, separated by ``|``, and what it
takes. ::

    # A flag, True
    getopt.option('v|verbose')

    # A flag that --no-color and --nocolor negate, False
    getopt.option('color!')

    # A counter, which each -v increments
    getopt.option('v|verbose+')

    # A string, an integer or a float
    getopt.option('m|mode=s')
    getopt.option('b|backlog=i')
    getopt.option('r|ratio=f')

    # An optional value, which is "" or 0 without it
    getopt.option('p|proxy:s')

    # A list of values in the result
    getopt.option('H|header=s@')

    # A dict of the keys and the values of --define key=value in the result
    getopt.option('D|define=s%')

Next to what Getopt::Long has, an option can have a default, a type, which
converts its value, and the values that it accepts, as the arguments of
argparse. ::

    getopt.option('M|method=s', default='GET')
    getopt.option('home=s', type=Pyjo.File.path)
    getopt.option('m|mode=s', choices=['development', 'production'])

The name of an option in the result, and the name that a callback gets, is
its first name that is longer than one letter, or its only name, with ``_``
for ``-``: ``inactivity_timeout`` for ``i|inactivity-timeout=i``.

Environment
-----------

With ``env_prefix``, an option that is not given has the value of the
environment variable of the prefix and its name in upper case, as
``PYJO_INACTIVITY_TIMEOUT`` for ``i|inactivity-timeout=i``, which is
converted and checked as a value of the command line, before the default,
the way Cobra and Viper of Go have it. An option of one letter has none, and
an empty variable is not set. A flag is false as ``0``, ``false``, ``no`` or
``off``, a counter is the number, and an option of a list or a dict takes
values separated by commas, as ``PYJO_LISTEN=http://*:80,https://*:443``. ::

    # PYJO_WORKERS=12 python myapp.py prefork
    getopt = Pyjo.GetOpt.new(env_prefix='PYJO_').option('w|workers=i', default=4)

The other way around, the target :func:`env` sets an environment variable to
the value of an option, as a script of Mojolicious binds an option to
``$ENV{...}``, for the code that reads the variable later, as the
application its mode. ::

    # python myapp.py --mode production sets PYJO_MODE
    getopt = Pyjo.GetOpt.new().option('m|mode=s', Pyjo.GetOpt.env('PYJO_MODE'))

Usage
-----

The usage of a command, which :func:`Pyjo.Util.extract_usage` reads from its
documentation, lists its options in a block after a line ``Options:``, an
option with a short name as ``-h, --help`` or ``-V``, and one with a long name
only as ``    --home <path>``, aligned with the long names of the others, and
its description after them, in a column of its own. :func:`format_usage` lays
out these blocks, so that a new option or a longer one needs no alignment by
hand. ::

    Options:
      -h, --help          Show this summary of available options
          --home <path>   Path to home directory of your application, defaults to
                          the value of PYJO_HOME or auto-detection

See also
--------

:func:`Pyjo.Util.getopt`, https://mojolicious.org.

Inspired by `Getopt::Long::Parser <https://metacpan.org/pod/Getopt::Long>`_,
the object interface of Getopt::Long, which ``getopt`` of Mojo::Util
configures.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception

from Pyjo.Util import warn

import os
import re
import sys
import textwrap

from collections.abc import Callable, Sequence
from typing import Any, Self, cast, overload


type Callback = Callable[[str, Any], Any]
type Target = list[Any] | dict[Any, Any] | Callback | None

_RE_FLOAT = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_RE_INT = re.compile(r'[-+]?\d+')

# The default width of the lines of a usage, as the usages of Mojolicious have it
WIDTH = 77

# A line of options and a line of an option of a usage, with its label and its description
_RE_USAGE_OPTIONS = re.compile(r'^Options\b[^:]*:$')
_RE_USAGE_OPTION = re.compile(r'^  ((?:-\w(?:, --[\w-]+)?|    --[\w-]+)(?: \[?<[^>]+>\]?)?)(?: {2,}(\S.*))?$')


class Pyjo_GetOpt(Pyjo.Base.object):
    """
    :mod:`Pyjo.GetOpt` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(
        self, *, pass_through: bool = False, require_order: bool = False, env_prefix: str | None = None
    ) -> None:
        """::

            getopt = Pyjo.GetOpt.new()
            getopt = Pyjo.GetOpt.new(pass_through=True)
            getopt = Pyjo.GetOpt.new(require_order=True)
            getopt = Pyjo.GetOpt.new(env_prefix='PYJO_')

        Construct a new :mod:`Pyjo.GetOpt` object. With ``pass_through``,
        unknown options and ``--`` stay in the list of arguments, without a
        warning. With ``require_order``, the options end at the first argument
        that is not one, and what follows it stays in the list of arguments,
        options too, as the arguments of a command that the program runs. With
        ``env_prefix``, an option that is not given has the value of the
        environment variable of its name, see `Environment`_.
        """
        self.env_prefix = env_prefix
        self.pass_through = pass_through
        self.require_order = require_order
        self._names: dict[str, _Option] = {}
        self._negations: set[str] = set()
        self._options: list[_Option] = []

    @overload
    def on[F: Callback](
        self,
        spec: str,
        cb: None = None,
        *,
        type: Callable[[Any], Any] | None = None,
        choices: Sequence[Any] | None = None,
    ) -> Callable[[F], F]: ...

    @overload
    def on[F: Callback](
        self, spec: str, cb: F, *, type: Callable[[Any], Any] | None = None, choices: Sequence[Any] | None = None
    ) -> F: ...

    def on(
        self,
        spec: str,
        cb: Callback | None = None,
        *,
        type: Callable[[Any], Any] | None = None,
        choices: Sequence[Any] | None = None,
    ) -> Any:
        """::

            cb = getopt.on('b|backlog=i', lambda name, value: ...)

            @getopt.on('b|backlog=i')
            def backlog(name, value): ...

        Add an option whose callback gets its name and its value, or a tuple
        of the key and the value of a hash, as a decorator without the
        callback. ``type`` and ``choices`` are those of :meth:`option`.
        """
        if cb is None:

            def decorator(cb: Callback) -> Callback:
                return self.on(spec, cb, type=type, choices=choices)

            return decorator
        self.option(spec, cb, type=type, choices=choices)
        return cb

    def option(
        self,
        spec: str,
        target: Target = None,
        *,
        default: Any = None,
        type: Callable[[Any], Any] | None = None,
        choices: Sequence[Any] | None = None,
    ) -> Self:
        """::

            getopt = getopt.option('m|mode=s')
            getopt = getopt.option('l|listen=s', [])
            getopt = getopt.option('D|define=s%', {})
            getopt = getopt.option('b|backlog=i', lambda name, value: ...)
            getopt = getopt.option('M|method=s', default='GET')
            getopt = getopt.option('home=s', type=Pyjo.File.path)
            getopt = getopt.option('m|mode=s', choices=['development', 'production'])

        Add an option, whose value goes to the result, to a list, to a dict or
        to a callback. ``default`` is the value in the result of an option
        that is not given. ``type`` converts a value, after the type of the
        specification, and a :class:`ValueError`, a :class:`TypeError` or a
        :class:`LookupError` of it makes the value invalid, as a value that is
        not in ``choices``.
        """
        if not (m := re.fullmatch(r'([\w?-]+(?:\|[\w?-]+)*)(?:(!)|(\+)|([=:])([sif])([@%])?)?', spec)):
            raise Pyjo.Exception.new(f'Error in option spec: "{spec}"')
        # A target that is not one, as a default given in its place, fails here, as in Getopt::Long, and not when the option
        # is given
        if not _is_target(target):
            raise Pyjo.Exception.new(f'Invalid option linkage for "{spec}"')
        names = m[1].split('|')
        name = next((name for name in names if len(name) > 1), names[0]).replace('-', '_')
        kind = 'negatable' if m[2] else 'increment' if m[3] else 'value' if m[4] else 'flag'
        option = _Option(name, kind, m[5] or '', m[4] == ':', m[6] or '', target, default, type, choices)
        self._options.append(option)
        for name in names:
            self._names[name] = option
            if kind == 'negatable':
                self._names[f'no{name}'] = self._names[f'no-{name}'] = option
                self._negations.update((f'no{name}', f'no-{name}'))
        return self

    def parse(self, args: list[str] | None = None) -> 'Pyjo_GetOpt_Result':
        """::

            opts = getopt.parse()
            opts = getopt.parse(['--mode', 'production', 'myapp.py'])

        Extract the options from the list of arguments, which defaults to the
        ones of ``sys.argv``, and remove them from it. The result has the
        values of the options without a target, and is false after an error.
        """
        argv = sys.argv if args is None else args
        start = 1 if args is None else 0
        rest, keep = argv[start:], list[str]()
        values: dict[str, Any] = {
            o.name: [] if o.multi == '@' else {} if o.multi == '%' else None for o in self._options if o.target is None
        }
        seen: set[str] = set()
        success = True

        i = 0
        while i < len(rest):
            arg = rest[i]
            i += 1

            # The end of the options
            if arg == '--':
                keep.extend(rest[i - 1 :] if self.pass_through else rest[i:])
                break

            # An argument, after which the options end with require_order
            if not arg.startswith('-') or arg == '-':
                if self.require_order:
                    keep.extend(rest[i - 1 :])
                    break
                keep.append(arg)
                continue

            # An unknown option
            given, _, value = arg.lstrip('-').partition('=')
            value = value if '=' in arg else None
            if (option := self._names.get(given)) is None:
                if self.pass_through:
                    keep.append(arg)
                else:
                    warn(f'Unknown option: {given}')
                    success = False
                continue

            # A flag
            if option.kind != 'value':
                if value is not None:
                    warn(f'Option {given} does not take an argument')
                    success = False
                    continue
                seen.add(option.name)
                if option.kind == 'increment':
                    _store(option, values, (values.get(option.name) or 0) + 1)
                else:
                    _store(option, values, given not in self._negations)
                continue

            # A value after the option, which an optional one takes only when it is not an option
            if value is None and i < len(rest) and (not option.optional or _is_value(option.type, rest[i])):
                value = rest[i]
                i += 1
            if value is None:
                if not option.optional:
                    warn(f'Option {given} requires an argument')
                    success = False
                    continue
                value = ''

            # The key of a hash
            key = None
            if option.multi == '%':
                key, equals, value = value.partition('=')
                if not equals and not option.optional:
                    warn(f'Option {given}, key "{key}", requires a value')
                    success = False
                    continue

            # The type of the value
            if (converted := self._convert(option, given, value)) is _INVALID:
                success = False
                continue
            seen.add(option.name)
            _store(option, values, converted if key is None else (key, converted))

        # Not in Getopt::Long: the options that are not given, from the environment variables of their names
        if self.env_prefix is not None:
            for option in self._options:
                if option.name in seen or len(option.name) < 2:
                    continue
                name = f'{self.env_prefix}{option.name.upper()}'
                if not (value := os.environ.get(name)):
                    continue
                if self._environ(option, name, value, values):
                    seen.add(option.name)
                else:
                    success = False

        # The defaults of the options that are not given
        for option in self._options:
            if option.target is None and option.default is not None and option.name not in seen:
                default = option.default
                values[option.name] = (
                    list(default) if option.multi == '@' else dict(default) if option.multi == '%' else default
                )

        argv[start:] = keep
        return Pyjo_GetOpt_Result(values, success)

    def _environ(self, option: '_Option', name: str, value: str, values: dict[str, Any]) -> bool:
        # A flag, which is false as 0, false, no and off
        if option.kind in ('flag', 'negatable'):
            _store(option, values, value.lower() not in ('0', 'false', 'no', 'off'))
            return True

        # A counter, which is the number
        if option.kind == 'increment':
            if not _RE_INT.fullmatch(value):
                warn(f'Value "{value}" invalid for option {name} (integer number expected)')
                return False
            _store(option, values, int(value))
            return True

        # The values of a list or a dict, separated by commas, as PYJO_LISTEN has them
        target: Any = option.target
        mapping = option.multi == '%' or isinstance(target, dict)
        several = mapping or option.multi == '@' or isinstance(target, list)
        converted: list[Any] = []
        for item in value.split(',') if several else [value]:
            key = None
            if mapping:
                key, equals, item = item.partition('=')
                if not equals and not option.optional:
                    warn(f'Option {name}, key "{key}", requires a value')
                    return False
            if (result := self._convert(option, name, item)) is _INVALID:
                return False
            converted.append(result if key is None else (key, result))
        for result in converted:
            _store(option, values, result)
        return True

    def _convert(self, option: '_Option', given: str, value: str) -> Any:
        if option.optional and value == '' and option.type != 's':
            value = '0'
        if option.type == 'i' and not _RE_INT.fullmatch(value):
            warn(f'Value "{value}" invalid for option {given} (integer number expected)')
            return _INVALID
        if option.type == 'f' and not _RE_FLOAT.fullmatch(value):
            warn(f'Value "{value}" invalid for option {given} (real number expected)')
            return _INVALID
        converted: Any = int(value) if option.type == 'i' else float(value) if option.type == 'f' else value

        # Not in Getopt::Long: the type and the choices of argparse
        if option.convert is not None:
            try:
                converted = option.convert(converted)
            except (LookupError, TypeError, ValueError) as e:
                warn(f'Value "{value}" invalid for option {given} ({str(e).strip(chr(39))})')
                return _INVALID
        if option.choices is not None and converted not in option.choices:
            warn(f'Value "{value}" invalid for option {given} (choose from {", ".join(map(str, option.choices))})')
            return _INVALID
        return converted


class Pyjo_GetOpt_Result:
    """
    The result of :meth:`~Pyjo_GetOpt.parse`, the values of the options as
    attributes, which is false after an error.
    """

    def __init__(self, values: dict[str, Any], success: bool) -> None:
        self.__dict__.update(values)
        self._success = success

    def __bool__(self) -> bool:
        return self._success

    # The values are attributes that the specifications of the options name
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f'{type(self).__name__!r} object has no attribute {name!r}', name=name, obj=self)

    def __repr__(self) -> str:
        values = ', '.join(f'{name}={value!r}' for name, value in vars(self).items() if not name.startswith('_'))
        return f'{type(self).__name__}({values})'


class _Option:
    def __init__(
        self,
        name: str,
        kind: str,
        type: str,
        optional: bool,
        multi: str,
        target: Target,
        default: Any,
        convert: Callable[[Any], Any] | None,
        choices: Sequence[Any] | None,
    ) -> None:
        self.choices = choices
        self.convert = convert
        self.default = default
        self.kind = kind
        self.multi = multi
        self.name = name
        self.optional = optional
        self.target = target
        self.type = type


# A value that is not valid, as None is one
_INVALID = Pyjo.Base.new()


def _is_value(type: str, arg: str) -> bool:
    if type == 's':
        return not arg.startswith('-') or arg == '-'
    return (_RE_FLOAT if type == 'f' else _RE_INT).fullmatch(arg) is not None


# Whether a value is a target of an option, as a bool, which leaves the type of the target as it is
def _is_target(target: Any) -> bool:
    return target is None or isinstance(target, (list, dict)) or callable(target)


def _store(option: _Option, values: dict[str, Any], value: Any) -> None:
    target = option.target
    if isinstance(target, list):
        cast(list[Any], target).append(value)
    elif isinstance(target, dict):
        key, value = cast(tuple[Any, Any], value)
        cast(dict[Any, Any], target)[key] = value
    elif target is not None:
        target(option.name, value)
    elif option.multi == '@':
        values[option.name].append(value)
    elif option.multi == '%':
        key, value = cast(tuple[Any, Any], value)
        values[option.name][key] = value
    else:
        values[option.name] = value


# Not in Getopt::Long: a target for an environment variable, as Perl binds an option to $ENV{...}
def env(name: str) -> Callable[[str, Any], None]:
    """::

        target = Pyjo.GetOpt.env('PYJO_MODE')

    A target of an option that sets the environment variable ``name`` to its
    value, ``1`` for a flag and ``0`` for a negated one, see `Environment`_. ::

        # --foreground sets PYJO_HOT_FOREGROUND to 1
        getopt.option('f|foreground', Pyjo.GetOpt.env('PYJO_HOT_FOREGROUND'))
    """

    def target(option: str, value: Any) -> None:
        os.environ[name] = '1' if value is True else '0' if value is False else str(value)

    return target


# Not in Getopt::Long: the layout of the options of a usage, which Pod::Usage leaves to the author of the POD
def format_usage(usage: str, width: int = WIDTH) -> str:
    """::

        usage = Pyjo.GetOpt.format_usage(usage)
        usage = Pyjo.GetOpt.format_usage(usage, width=79)

    Lay out the blocks of options of a usage message, see `Usage`_: the
    descriptions in a column three spaces after the longest option of the
    block, wrapped to the width of the lines, ``77`` by default, and the rest
    of the message as it is. ::

        # The usage of a command, laid out
        print(Pyjo.GetOpt.format_usage(extract_usage()))
    """
    lines = usage.split('\n')
    result: list[str] = []
    block: list[list[str]] = []

    def flush() -> None:
        if not block:
            return
        labels = [entry[0] for entry in block]
        column = 2 + max(len(label) for label in labels) + 3
        for label, *description in block:
            wrapped = textwrap.wrap(
                ' '.join(description), max(width - column, 1), break_long_words=False, break_on_hyphens=False
            )
            result.append(f'  {label:<{column - 2}}{wrapped[0]}'.rstrip() if wrapped else f'  {label}')
            result.extend(' ' * column + line for line in wrapped[1:])
        block.clear()

    in_block = False
    for line in lines:
        if in_block and line.strip():
            if m := _RE_USAGE_OPTION.match(line):
                block.append([m[1].rstrip(), *([m[2]] if m[2] else [])])
                continue
            if block and line.startswith('   '):
                block[-1].append(line.strip())
                continue
        if in_block:
            flush()
        in_block = _RE_USAGE_OPTIONS.match(line) is not None
        result.append(line)
    flush()
    return '\n'.join(result)


new = Pyjo_GetOpt.new
object = Pyjo_GetOpt
GetOpt = Pyjo_GetOpt
