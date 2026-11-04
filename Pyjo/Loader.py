r"""
Pyjo.Loader - Load all kinds of things
======================================
::

    from Pyjo.Loader import data_section, find_modules, load_class
    from Pyjo.Util import warn

    # Find modules in a namespace
    for module in find_modules('Some.Namespace'):

        # Load them safely
        e = load_class(module)
        if isinstance(e, Exception):
            warn(f'Loading "{module}" failed: {e}')
            continue

        # And extract files from the DATA section
        print(data_section(module, 'some_file.txt'))

:mod:`Pyjo.Loader` is a class loader and plugin framework. Aside from finding
modules and loading classes, it allows multiple files to be stored in the
``DATA`` section of a module, which can then be accessed individually. The
section is the ``__DATA__`` variable of the module, or its docstring after a
line ``__DATA__``. ::

    # Foo.py

    __DATA__ = r'''
    @@ test.txt
    This is the first file.

    @@ test2.html (base64)
    VGhpcyBpcyB0aGUgc2Vjb25kIGZpbGUu

    @@ test
    This is the
    third file.
    '''

Each file has a header starting with ``@@``, followed by the file name and
optional instructions for decoding its content. Currently only the Base64
encoding is supported, which can be quite convenient for the storage of binary
data.

A class is named as a module of Python, with dots, and is loaded from
:data:`sys.path`. A function that takes a class takes the module, a class, or
the dotted name of a module or of a class in it.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Loader <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Loader.pm>`_
of Mojolicious 9.49.

Functions
---------
"""

import Pyjo.Exception
import Pyjo.File
import Pyjo.String.Unicode

from Pyjo.Util import b64_decode

import importlib
import importlib.util
import os
import re
import sys
import traceback

from importlib.machinery import ModuleSpec
from types import ModuleType


# A class: its module, a class in it, or the dotted name of either
type Class = ModuleType | type | str

_BIN: dict[str, dict[str, bool]] = {}
_CACHE: dict[str, dict[str, str | bytes]] = {}


def data_section(cls: Class | None, name: str | None = None) -> 'dict[str, str | bytes] | str | bytes | None':
    """::

        all = data_section('Foo.Bar')
        index = data_section('Foo.Bar', 'index.html')

    Extract embedded file from the ``DATA`` section of a module, all files
    will be cached once they have been accessed for the first time. A file
    encoded in Base64 is :class:`bytes`, any other a :class:`str`. ::

        # List embedded files
        for name in data_section('Foo.Bar'):
            print(name)
    """
    if not cls:
        return None
    return _all(cls).get(name) if name else _all(cls)


def file_is_binary(cls: Class, name: str) -> bool | None:
    """::

        boolean = file_is_binary('Foo.Bar', 'test.png')

    Check if embedded file from the ``DATA`` section of a module was Base64
    encoded.
    """
    return bool(_BIN.get(_key(cls) or '', {}).get(name)) if len(_all(cls)) else None


def find_modules(ns: str, *, recursive: bool = False) -> list[str]:
    """::

        modules = find_modules('MyApp.Namespace')
        modules = find_modules('MyApp.Namespace', recursive=True)

    Search for modules in a namespace, in the directories of
    :data:`sys.path`, without loading them. A package, a directory with an
    ``__init__.py``, is a module too.

    These options are currently available:

    recursive
        ::

            recursive=True

        Search namespace recursively.
    """
    parts = ns.split('.')
    dirs = [d for d in (Pyjo.File.new(p or '.', *parts) for p in sys.path) if d.is_dir]

    modules: set[str] = set()
    for dir in dirs:
        for file in dir.list_tree() if recursive else dir.list(dir=True):
            path = file.to_str()

            # Not in Mojolicious: a package is a module, as Foo.pm next to Foo/ is in Perl
            if os.path.isdir(path):
                if not os.path.isfile(path := os.path.join(path, '__init__.py')):
                    continue

            if not path.endswith('.py'):
                continue
            rel = Pyjo.File.new(path[:-3]).to_rel(dir).to_list()
            if rel[-1] == '__init__':
                rel.pop()
            if len(rel):
                modules.add('.'.join([ns, *rel]))

    return sorted(modules)


def find_packages(ns: str) -> list[str]:
    """::

        pkgs = find_packages('MyApp.Namespace')

    Search for packages in a namespace non-recursively: the modules in it that
    are loaded, as :data:`sys.modules` has them.
    """
    prefix = f'{ns}.'
    return sorted(n for n in list(sys.modules) if n.startswith(prefix) and '.' not in n[len(prefix) :])


def load_class(cls: str) -> 'Pyjo.Exception.object | bool | None':
    """::

        e = load_class('Foo.Bar')

    Load a class and catch exceptions, returns a false value if loading was
    successful, a true value if the class was not found, or a
    :mod:`Pyjo.Exception` object if loading failed. A directory without an
    ``__init__.py`` (a namespace package) is not a class. The context of the
    exception is the line of the module that failed to load, and the exception
    of Python is its ``__cause__``. ::

        # Handle exceptions
        if e := load_class('Foo.Bar'):
            raise Exception(f'Exception: {e}' if isinstance(e, Exception) else 'Not found!')
    """
    # Invalid class name
    if not re.fullmatch(r'\w(?:[\w.]*\w)?', cls or ''):
        return True
    # Left out from Mojolicious: the deprecated package separator "'", which Python has never had

    # Load if not already loaded
    module = sys.modules.get(cls)
    try:
        spec = module.__spec__ if module is not None else _find_spec(cls)
    except ModuleNotFoundError as e:
        # Does not exist
        if e.name is not None and (cls == e.name or cls.startswith(f'{e.name}.')):
            return True
        return _exception(e, None)
    except Exception as e:
        return _exception(e, None)
    if module is not None and spec is None:
        return None

    # Does not exist, or a namespace package
    if spec is None or spec.origin is None:
        return True

    try:
        importlib.import_module(cls)
    except Exception as e:
        # Real error
        return _exception(e, spec.origin)
    return None


def load_classes(ns: str) -> list[str]:
    """::

        classes = load_classes('Foo.Bar')

    Load all classes in a namespace recursively.
    """
    classes: list[str] = []
    for module in find_modules(ns, recursive=True):
        if not (e := load_class(module)):
            classes.append(module)
        if isinstance(e, Exception):
            raise e

    return classes


def _all(cls: Class) -> dict[str, str | bytes]:
    if (module := _module(cls)) is None:
        return {}
    name = module.__name__
    if name in _CACHE:
        return _CACHE[name]

    # Not in Mojolicious: the __DATA__ variable of a module, or its docstring after a line __DATA__
    data = getattr(module, '__DATA__', None)
    if not isinstance(data, str):
        doc = module.__doc__
        if not isinstance(doc, str) or not re.search(r'^__DATA__\r?$', doc, re.M):
            return {}
        data = doc

    # Ignore everything before __DATA__
    data = re.sub(r'\A.*\n__DATA__\r?\n', '\n', data, count=1, flags=re.S)

    # Ignore everything after __END__
    data = re.sub(r'\n__END__\r?\n.*\Z', '\n', data, count=1, flags=re.S)

    # Split files
    files = Pyjo.String.Unicode.split(re.compile(r'^@@\s*(.+?)\s*\r?\n', re.M), data)[1:]

    # Find data
    all: dict[str, str | bytes] = {}
    _CACHE[name] = all
    while len(files):
        file, content = files[0] or '', files[1] if len(files) > 1 else None
        del files[:2]
        content = content or ''
        if (base := re.sub(r'\s*\(\s*base64\s*\)$', '', file)) != file:
            _BIN.setdefault(name, {})[base] = True
            all[base] = b64_decode(content)
        else:
            all[file] = content

    return all


# The exception of a module that failed to load, with the context of the line of the module
def _exception(e: Exception, origin: str | None) -> Pyjo.Exception.object:
    err = Pyjo.Exception.new(e)
    err.__cause__ = e

    # Unlike Mojolicious: croak reports the line of the caller, Python the line of the raise, so the frames of the
    # module come first, or the location of a syntax error, which is not in a frame
    if isinstance(e, SyntaxError) and e.filename is not None and e.lineno is not None:
        err.frames.insert(0, traceback.FrameSummary(e.filename, e.lineno, '<module>', lookup_line=False, line=e.text))
    elif origin is not None:
        for i, frame in enumerate(err.frames):
            if frame.filename == origin and frame.name == '<module>':
                del err.frames[:i]
                break

    return err.inspect()


# The module of a class, or the longest prefix of a dotted name that is loaded
# Not in Mojolicious: the finders of importlib keep the files of a directory until its time of modification changes,
# which may not show a module written right after they looked, where require of Perl looks at the files each time, so a
# module that is not found is looked for again without them
def _find_spec(cls: str) -> ModuleSpec | None:
    try:
        if (spec := importlib.util.find_spec(cls)) is not None:
            return spec
    except ModuleNotFoundError:
        pass
    importlib.invalidate_caches()
    return importlib.util.find_spec(cls)


def _module(cls: Class) -> ModuleType | None:
    if isinstance(cls, ModuleType):
        return cls
    name = cls.__module__ if isinstance(cls, type) else cls
    parts = name.split('.')
    for i in range(len(parts), 0, -1):
        if (module := sys.modules.get('.'.join(parts[:i]))) is not None:
            return module
    return None


# The name of the module of a class, the key of the cache
def _key(cls: Class) -> str | None:
    return module.__name__ if (module := _module(cls)) is not None else None


# Not in Mojolicious: the class of a dotted name, which a Perl package is, for the modules of Pyjoyment that load
# plugins and controllers by name: the class that a module names its object, or an attribute of the longest prefix of
# the name that is a module
def _class(name: str) -> type | None:  # pyright: ignore[reportUnusedFunction]
    if (module := sys.modules.get(name)) is not None:
        found: object = getattr(module, 'object', None)
        return found if isinstance(found, type) else None
    parts = name.split('.')
    for i in range(len(parts) - 1, 0, -1):
        try:
            found = importlib.import_module('.'.join(parts[:i]))
        except ImportError:
            continue
        try:
            for attr in parts[i:]:
                found = getattr(found, attr)
        except AttributeError:
            return None
        return found if isinstance(found, type) else None
    return None
