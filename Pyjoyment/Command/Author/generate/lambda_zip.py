"""
Pyjoyment.Command.Author.generate.lambda_zip - Lambda ZIP generator command
===========================================================================
::

    Usage: APPLICATION generate lambda-zip [OPTIONS]

      ./myapp.py generate lambda-zip
      python -m MyApp generate lambda-zip
      python -m MyApp generate lambda-zip --arch arm64
      python -m MyApp generate lambda-zip --python 3.15t
      python -m MyApp generate lambda-zip --no-layer
      python -m MyApp generate lambda-zip --runtime python3.14
      python -m MyApp generate lambda-zip --function-only
      python -m MyApp generate lambda-zip --function-only --layer-package Pyjo-AWS
      python -m MyApp generate lambda-zip --compress public
      python -m MyApp generate lambda-zip --compress public --compress-encoding br --compress-encoding gzip

    Options:
      -a, --arch <name>                Architecture of the function, "arm64" or
                                       "x86_64", defaults to "x86_64"
      -c, --compress <path>            Write the variants of gzip, and of brotli
                                       and zstd if the machine has them, of the
                                       static files of a directory in the
                                       function, can be repeated
      -C, --compress-pattern <glob>    Name of the files that --compress
                                       compresses, can be repeated, defaults to
                                       the formats of text
      -e, --compress-encoding <name>   Encoding of the variants that --compress
                                       writes, "br", "zstd" or "gzip", can be
                                       repeated, defaults to the ones that the
                                       machine has
          --function-only              Only the ZIP of the function, for layers
                                       of Python and Pyjoyment that are published
                                       already
      -h, --help                       Show this summary of available options
      -l, --layer-package <name>       Distribution of the dependencies that the
                                       layer of Pyjoyment has too, as "Pyjo-AWS",
                                       can be repeated
          --no-layer                   Put Python and Pyjoyment into the ZIP of
                                       the function, without layers
      -p, --python <version>           Version of Python, as "3.14" or "3.15t"
                                       for the free-threaded build, defaults to
                                       the version that runs the generator
      -r, --runtime <name>             Runtime of the function, "provided.al2023"
                                       or one of Python, as "python3.14",
                                       defaults to "provided.al2023"

:mod:`Pyjoyment.Command.Author.generate.lambda_zip` generates the ZIP files
of an event function of AWS Lambda on a custom runtime, as
``provided.al2023``, in ``dist``: ``function.zip``, with the application, its
dependencies and the ``bootstrap`` that runs it, ``python.zip``, a layer with
Python, which Lambda extracts in ``/opt``, so that the function runs on any
Python, as the free-threaded build or a version that the runtimes of Python of
Lambda do not have yet, and ``pyjoyment.zip``, a layer with Pyjoyment.

The ``bootstrap`` runs the script of the application, or its package, which
is the runtime of the function itself, as :mod:`Pyjoyment.Command.lambda`
detects, with the runtime client of :mod:`Pyjo.Server.Lambda`. A function
whose Function URL streams its responses has
``PYJO_LAMBDA_INVOKE_MODE=RESPONSE_STREAM`` in its environment, as
:attr:`Pyjo.Server.Lambda.Pyjo_Server_Lambda.invoke_mode` says.

The files are made with uv, which has to be on ``PATH``. Python is the build
of python-build-standalone that uv installs, for Linux with glibc and the
architecture of ``--arch``: the interpreter and its standard library,
without IDLE, Tkinter, turtledemo, ensurepip and pip, which a function does
not use. The dependencies are the ones of ``pyproject.toml``, which
:mod:`Pyjoyment.Command.Author.generate.pyproject` generates, locked with
``uv.lock`` if there is one, or the ones of the inline metadata of PEP 723 of
a :mod:`Pyjoyment.Lite` script that has it and no ``pyproject.toml``, locked
with its ``.lock`` file if there is one, with the wheels of Amazon Linux 2023,
``manylinux_2_34``. Without either, the generator fails with the commands that
add them, before it runs uv. The application is the files of the current directory,
without hidden ones, ``__pycache__`` and ``dist``, and a file of it that starts
with ``#!``, as the wrapper of ``AWS_LAMBDA_EXEC_WRAPPER``, is executable.

Python cannot write its bytecode in ``/var/task`` and ``/opt``, which are
read-only, so the generator compiles it with the Python of the same version
that uv installs for the machine that it runs on, which installs the
dependencies too, without a link in the directory of the executables of uv,
with the
invalidation mode ``unchecked-hash``, which Python uses without checking the
source. The files of the same input are the same, as the times in the ZIP are
fixed, so that a deployment that compares their hashes, as the one of
OpenTofu, changes only what has changed. They are written anew each time.

The layer of Pyjoyment has the distribution Pyjoyment that the dependencies
install, the files that its ``RECORD`` names, with the packages ``Pyjo`` and
``Pyjoyment``, and the distributions of ``--layer-package``, as ``Pyjo-AWS``,
with their bytecode, in ``python/lib/python3.X/site-packages``, which the
Python of ``python.zip`` and the runtime client of the runtime of Python of
Lambda of the same version both put in their path, the runtime client unless
``PYTHONPATH`` is set, so that one layer serves the functions of both, and a
function can take a layer of Pyjoyment that is published already in its place.
A wrapper of ``AWS_LAMBDA_EXEC_WRAPPER`` runs in the place of that runtime
client, so its function names the directory in ``PYTHONPATH``. Another
distribution of the namespace ``Pyjo``, as ``Pyjo-MCP``, stays in the
function, where the package ``Pyjo`` of the layer finds it, as
:func:`pkgutil.extend_path` keeps the namespace open, but a distribution that
the layer has too is the one of the layer.

With ``--runtime`` of a runtime of Python of Lambda, as ``python3.14``, the
function runs on the Python of Lambda, of the version of the runtime, without
``python.zip`` and without ``bootstrap``, with the handler of the application,
as ``app.handler`` for a script ``app.py`` that ends with
``handler = app.start()``.

With ``--no-layer``, Python and Pyjoyment are in ``function.zip``, Python in
the directory ``python``, and the function needs no layer, at the cost of a
larger ZIP for each deployment.

With ``--compress``, the function has the precompressed variants of the
static files of a directory of the application, as ``public``, which
:mod:`Pyjoyment.Static` serves to the clients that take them: ``.gz`` of
:mod:`gzip`, and ``.zst`` of ``compression.zstd`` of Python 3.14 or of the
command ``zstd``, and ``.br`` of the command ``brotli``, if the machine has
them, without a variant that is not smaller than its file. It compresses the
files of
:attr:`~Pyjoyment.Command.Author.generate.dockerfile.Pyjoyment_Command_Author_generate_dockerfile.compress_patterns`
of ``generate dockerfile``, the formats of text, or the names of
``--compress-pattern``, and leaves out the files smaller than
:attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.min_compress_size` of the
renderer.
With ``--compress-encoding``, it writes the variants of those encodings only,
as ``br`` and ``gzip`` for a function behind CloudFront, which forwards no
other encoding of ``Accept-Encoding`` to the origin, and fails when the
machine has no compressor of one of them.

With ``--function-only``, the generator writes ``function.zip`` alone, for the
layers of Python and of Pyjoyment that are published already, as the public
ones of `Pyjoyment-Lambda-Layers
<https://github.com/pyjoyment/Pyjoyment-Lambda-Layers>`_, which the same
generator builds, so that the ``bootstrap`` finds the Python of the layer in
``/opt/python/bin``. The function leaves out Pyjoyment and the distributions
of ``--layer-package``, as ``Pyjo-AWS``, which the public layer of Pyjoyment
has, as with its own layer, and the generator tells their versions of its
dependencies, which the layer of Pyjoyment is to have. On a runtime of Python,
the function takes the layer of Pyjoyment alone, of the same version of
Python.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.File
import Pyjoyment.Command
import Pyjoyment.Command.Author.generate.dockerfile

from Pyjo.Util import extract_usage, getopt

import fnmatch
import gzip
import importlib
import importlib.metadata
import importlib.util
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import zipfile

from collections.abc import Callable
from typing import Any


# The architectures of Lambda and the machines of Linux
_MACHINES = {'arm64': 'aarch64', 'x86_64': 'x86_64'}

# The parts of the standard library that a function does not use
_UNUSED = ('ensurepip', 'idlelib', 'site-packages', 'tkinter', 'turtledemo')

# The requirements that uv exports, for uv pip install
_FORMAT = ('--format', 'requirements.txt', '-o')

# The bytecode of the modules of a directory, with their paths on Lambda, which compileall would join with the
# separator of the machine, a backslash on Windows. Python, as 3.13, 3.15 and the free-threaded build, marshals a
# module otherwise after some modules that its process has compiled before, so the modules are compiled in chunks of
# the same files in the same order, each by a new interpreter, and not by a pool of processes, which gives a process
# the chunks in the order that it is free, so that the same files give the same bytecode on every machine. The
# free-threaded build marshals a module otherwise at random after a collection of the garbage too, which an
# interpreter of the chunks does not make
_COMPILE = r"""
import concurrent.futures, os, subprocess, sys
root, prefix = sys.argv[1:]
files = [os.path.join(d, f) for d, _, names in sorted(os.walk(root)) for f in sorted(names) if f.endswith('.py')]
lines = [f + '\t' + f'{prefix}/' + os.path.relpath(f, root).replace(os.sep, '/') for f in files]
chunks = [lines[i : i + 64] for i in range(0, len(lines), 64)]
code = '''
import gc, py_compile, sys
gc.disable()
mode = py_compile.PycInvalidationMode.UNCHECKED_HASH
pairs = [line.split('\\t') for line in sys.stdin.read().splitlines()]
sys.exit(not all([py_compile.compile(f, None, d, False, -1, mode, 1) for f, d in pairs]))
'''
def compile(chunk):
    return subprocess.run([sys.executable, '-c', code], input='\n'.join(chunk), text=True).returncode == 0
with concurrent.futures.ThreadPoolExecutor(os.cpu_count()) as pool:
    sys.exit(not all(pool.map(compile, chunks)))
"""


class Pyjoyment_Command_Author_generate_lambda_zip(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.Author.generate.lambda_zip` inherits all
    attributes and methods from :mod:`Pyjoyment.Command` and implements the
    following new ones.
    """

    description = 'Generate ZIP files of AWS Lambda'
    """::

        description = lambda_zip.description
        lambda_zip.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = lambda_zip.usage
        lambda_zip.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> None:
        """::

            lambda_zip.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        opts = getopt(
            arguments,
            {
                'a|arch=s': None,
                'c|compress=s@': None,
                'C|compress-pattern=s@': None,
                'e|compress-encoding=s@': None,
                'function-only': None,
                'l|layer-package=s@': None,
                'no-layer': None,
                'p|python=s': None,
                'r|runtime=s': None,
            },
        )
        if not opts:
            raise Pyjo.Exception.new(self.usage)
        if opts.function_only and opts.no_layer:
            raise Pyjo.Exception.new('Options --function-only and --no-layer exclude each other')
        if opts.layer_package and opts.no_layer:
            raise Pyjo.Exception.new('Options --layer-package and --no-layer exclude each other')

        arch: str = opts.arch or 'x86_64'
        if (machine := _MACHINES.get(arch)) is None:
            raise Pyjo.Exception.new(f'Unknown architecture: {arch}')
        runtime: str = opts.runtime or 'provided.al2023'
        version: str = opts.python or f'{sys.version_info.major}.{sys.version_info.minor}'
        if managed := re.fullmatch(r'python(3\.\d+)', runtime):
            if opts.python and opts.python != managed[1]:
                raise Pyjo.Exception.new(f'Option --python is not for the runtime {runtime}')
            version = managed[1]
        elif runtime != 'provided.al2023':
            raise Pyjo.Exception.new(f'Unknown runtime: {runtime}')
        if not re.fullmatch(r'3\.\d+(?:\.\d+)?t?', version):
            raise Pyjo.Exception.new(f'Unknown version of Python: {version}')
        layer = not opts.no_layer
        only = bool(opts.function_only)
        compress: list[str] = opts.compress or []
        patterns: list[str] = opts.compress_pattern or list(
            Pyjoyment.Command.Author.generate.dockerfile.object.compress_patterns
        )
        if opts.compress_pattern and not compress:
            raise Pyjo.Exception.new('Option --compress-pattern needs --compress')
        encodings: list[str] = opts.compress_encoding or []
        if encodings and not compress:
            raise Pyjo.Exception.new('Option --compress-encoding needs --compress')
        if unknown := [e for e in encodings if e not in _TOOLS]:
            raise Pyjo.Exception.new(f'Unknown encoding: {unknown[0]}')
        # The compressors of the encodings of the option, which fail before the build without them, or all that the
        # machine has
        compressors = _compressors() if compress else []
        if missing := [e for e in encodings if e not in [c[0] for c in compressors]]:
            raise Pyjo.Exception.new(f'No compressor of the encoding {missing[0]}: {_TOOLS[missing[0]]} not found')
        if encodings:
            compressors = [c for c in compressors if c[0] in encodings]

        # The script of Pyjoyment.Lite or the package of the application, and the dependencies of pyproject.toml, or of
        # the inline metadata of PEP 723 of a script without it, as generate dockerfile has them
        exe = os.environ.get('PYJO_EXE')
        script = Pyjo.File.path(exe).to_rel(self.app.home).to_str() if exe else None
        cmd = [script] if script else ['-m', type(self.app).__module__]
        project = self.rel_file('pyproject.toml').is_file
        if not project and not (exe and _metadata(Pyjo.File.path(exe))):
            raise Pyjo.Exception.new(_no_dependencies(script))

        # The Python of the machine that compiles the bytecode and gives the tags of the wheels, of the same version,
        # with the GIL unless the version is the free-threaded one, which uv does not take otherwise
        local = version if version.endswith('t') else f'{version}+gil'

        with Pyjo.File.tempdir() as tmp:
            # Python, the interpreter and its standard library, in the directory of its full version, which the variables
            # of its build name, and not the link of its minor version, or the Python of the runtime of Lambda
            python = tmp.child('layer', 'python')
            prefix = '/opt/python' if layer else '/var/task/python'
            if managed:
                interpreter = f'python{version}'
            elif only:
                # The interpreter of a layer that is published already, of the minor version
                interpreter = re.sub(r'^(3\.\d+)(?:\.\d+)?', r'python\1', version)
            else:
                install = tmp.child('install')
                self._uv(
                    'python', 'install', '--no-bin', '--install-dir', install, f'cpython-{version}-linux-{machine}-gnu'
                )
                home = next(p for p in sorted(os.listdir(install)) if re.match(r'cpython-\d+\.\d+\.\d+', p))
                # The layer, which Lambda extracts in /opt, with Python in its directory python
                interpreter = _python(install.child(home), python, prefix)

            # The dependencies, without the scripts of their packages, which run the Python of the machine, and the lock
            # of uv
            function = tmp.child('function').make_path()
            requirements = 'pyproject.toml'
            if project and self.rel_file('uv.lock').is_file:
                requirements = tmp.child('requirements.txt').to_str()
                self._uv('export', '--frozen', '--no-dev', '--no-emit-project', '--no-hashes', *_FORMAT, requirements)
            elif not project:
                frozen = ['--frozen'] if self.rel_file(f'{script}.lock').is_file else []
                requirements = tmp.child('requirements.txt').to_str()
                self._uv('export', '--script', script or '', *frozen, '--no-hashes', *_FORMAT, requirements)
            platform = f'{machine}-manylinux_2_34'
            deps = tmp.child('deps')
            # The Python of the machine, which uv pip install does not download, as uv run does, and which uv prefers
            # to one of the system, so the bytecode is the same on every machine
            self._uv('python', 'install', '--no-bin', version)
            self._uv(
                'pip', 'install', '--target', deps, '--python', local, '--python-platform', platform, '-r', requirements
            )
            # Pyjoyment, in the site-packages of the layer, which the runtimes of Python and the Python of the layer
            # put in their path
            pyjoyment = tmp.child('pyjoyment')
            site = pyjoyment.child('python', 'lib', interpreter, 'site-packages')
            if layer:
                distributions = _distributions(deps)
                site.make_path()
                layered: list[str] = ['Pyjoyment', *(opts.layer_package or [])]
                for name in layered:
                    if (distribution := distributions.get(_normalize(name))) is None:
                        raise Pyjo.Exception.new(f'{name} is not among the dependencies')
                    # The version of the distribution, which a layer that is published already is to have, before
                    # its metadata goes to the layer
                    if only:
                        self._loud(f'  [layer] {distribution.name} {distribution.version} for Python {interpreter[6:]}')
                    _move(deps, site, distribution)
            if deps.is_dir:
                top = os.fspath(deps)
                shutil.copytree(
                    deps, function, dirs_exist_ok=True, ignore=lambda dir, _: ['.lock', 'bin'] if dir == top else []
                )

            # The application, with its scripts executable, and the bootstrap that runs it
            executables = {'bootstrap', f'python/bin/{interpreter}'}
            for file in Pyjo.File.path().list_tree().each():
                name = file.to_rel(Pyjo.File.path()).to_str().replace(os.sep, '/')
                if name.split('/')[0] != 'dist' and '__pycache__' not in name.split('/'):
                    destination = function.child(*name.split('/'))
                    destination.dirname().make_path()
                    shutil.copyfile(file.to_str(), destination.to_str())
                    with open(file, 'rb') as source:
                        if source.read(2) == b'#!':
                            executables.add(name)
            # The variants of the static files, which Pyjoyment.Static serves
            if compress:
                encodings = _compress(function, compress, patterns, self.app.renderer.min_compress_size, compressors)
                self._loud(f'  [compress] {", ".join(compress)} ({", ".join(encodings)})')
            if not managed:
                executable = f'{prefix}/bin/{interpreter}' if layer else f'"$LAMBDA_TASK_ROOT/python/bin/{interpreter}"'
                function.child('bootstrap').spew(
                    self.render_data('bootstrap', {'cmd': shlex.join(cmd), 'python': executable})
                )

            # The bytecode, as /var/task and /opt are read-only
            if not managed and not only:
                self._compile(local, python, prefix)
            if layer and not only:
                self._compile(local, site, f'/opt/python/lib/{interpreter}/site-packages')
            self._compile(local, function, '/var/task')

            # The ZIP files, without the layers of an earlier build that this one does not write
            dist = self.rel_file('dist')
            self.create_dir(dist)
            for name in ('python.zip', 'pyjoyment.zip'):
                dist.child(name).remove()
            if layer and not managed and not only:
                _zip(python.dirname(), dist.child('python.zip'), {f'python/bin/{interpreter}'})
                self._loud(f'  [write] {dist.child("python.zip")}')
            elif not managed and not layer:
                shutil.copytree(python, function.child('python'))
            if layer and not only:
                _zip(pyjoyment, dist.child('pyjoyment.zip'), set())
                self._loud(f'  [write] {dist.child("pyjoyment.zip")}')
            _zip(function, dist.child('function.zip'), executables)
            self._loud(f'  [write] {dist.child("function.zip")}')

    # The bytecode of a set of strings, as in "x in {'a', 'b'}", has the order of their hashes, which a fixed seed keeps
    def _compile(self, local: str, dir: Pyjo.File.object, prefix: str) -> None:
        env = {**os.environ, 'PYTHONHASHSEED': '0'}
        self._uv('run', '--no-project', '--python', local, '--', 'python', '-c', _COMPILE, dir, prefix, env=env)

    def _uv(self, *args: str | Pyjo.File.object, env: dict[str, str] | None = None) -> None:
        command = [*_uv(), '--quiet', *map(str, args)]
        if (code := subprocess.run(command, env=env).returncode) != 0:
            raise Pyjo.Exception.new(f'Command "uv {" ".join(map(str, args[:2]))}" failed with exit status {code}')


# The interpreter and its standard library, without what a function does not use, with the prefix of Python on Lambda in
# the variables of the build, where uv puts the directory that it installs in, and the name of the interpreter
def _python(home: Pyjo.File.object, python: Pyjo.File.object, prefix: str) -> str:
    bin = home.child('bin')
    names = sorted(os.listdir(bin))
    interpreter = next(n for n in names if re.fullmatch(r'python3\.\d+t?', n) and not os.path.islink(bin.child(n)))
    python.child('bin').make_path()
    shutil.copyfile(bin.child(interpreter).to_str(), python.child('bin', interpreter).to_str())
    library = python.child('lib', interpreter)
    shutil.copytree(home.child('lib', interpreter), library, symlinks=True)
    for name in os.listdir(library):
        if name in _UNUSED or name.startswith('config-'):
            shutil.rmtree(library.child(name))
        elif name.startswith('_sysconfigdata_') and name.endswith('.py'):
            # The directory in the literals of Python, with the backslashes of Windows escaped
            data = library.child(name)
            text = str(data.slurp('UTF-8')).replace(home.to_str().replace('\\', '\\\\'), prefix)
            data.spew(text.replace(home.to_str(), prefix), 'UTF-8')
    for name in os.listdir(library.child('lib-dynload')):
        if name.startswith('_tkinter'):
            os.remove(library.child('lib-dynload', name))
    return interpreter


# The encoding, the extension of its variants and the function that writes the variant of a file
type _Compressor = tuple[str, str, Callable[[str], Any]]

# The compressors of the encodings, for the message of one that the machine does not have
_TOOLS = {
    'br': 'command "brotli"',
    'zstd': 'module compression.zstd of Python 3.14 or command "zstd"',
    'gzip': 'module gzip',
}


# The variants of the static files of the directories of the application, of the formats of the patterns and of at
# least the size, with the compressors, without a variant that is not smaller than its file
def _compress(
    function: Pyjo.File.object, paths: list[str], patterns: list[str], size: int, compressors: list[_Compressor]
) -> list[str]:
    for path in paths:
        parts = [p for p in re.split(r'[\\/]', path) if p not in ('', '.')]
        if os.path.isabs(path) or '..' in parts or not function.child(*parts).is_dir:
            raise Pyjo.Exception.new(f'Directory not found in the application: {path}')
        for file in function.child(*parts).list_tree().each():
            name = file.to_str()
            if os.path.getsize(name) < size or not any(fnmatch.fnmatchcase(file.basename(), p) for p in patterns):
                continue
            for _, ext, compressor in compressors:
                compressor(name)
                if os.path.getsize(name + ext) >= os.path.getsize(name):
                    os.remove(name + ext)
    return [encoding for encoding, _, _ in compressors]


# The compressors of the encodings of Pyjoyment.Static, in its order: brotli of its command, zstd of the standard
# library of Python 3.14 or of its command, and gzip of the standard library, without the time of the file, as gzip -n,
# so that the same files give the same ZIP
def _compressors() -> list[_Compressor]:
    compressors: list[_Compressor] = []
    if brotli := shutil.which('brotli'):
        compressors.append(('br', '.br', lambda f: subprocess.run([brotli, '-k', '-f', '-q', '11', f], check=True)))
    # The module of Python 3.14, which pyright of Python 3.12 does not know, and which a build without libzstd lacks
    zstd: Any = None
    if importlib.util.find_spec('compression'):
        try:
            zstd = importlib.import_module('compression.zstd')
        except ImportError:
            pass
    if zstd is not None:
        compressors.append(
            (
                'zstd',
                '.zst',
                lambda f: Pyjo.File.path(f + '.zst').spew(zstd.compress(Pyjo.File.path(f).slurp(), level=19)),
            )
        )
    elif command := shutil.which('zstd'):
        compressors.append(
            ('zstd', '.zst', lambda f: subprocess.run([command, '-q', '-k', '-f', '-19', f], check=True))
        )
    compressors.append(
        ('gzip', '.gz', lambda f: Pyjo.File.path(f + '.gz').spew(gzip.compress(Pyjo.File.path(f).slurp(), 9, mtime=0)))
    )
    return compressors


# The distributions of a directory by their normalized names
def _distributions(dir: Pyjo.File.object) -> dict[str, importlib.metadata.Distribution]:
    if not dir.is_dir:
        return {}
    return {_normalize(d.name): d for d in importlib.metadata.distributions(path=[dir.to_str()])}


# The files of a distribution, which its RECORD names, from a directory to another one, without its scripts, and the
# directories that it leaves empty, so that a distribution of the same namespace, as Pyjo, stays where it is
def _move(
    source: Pyjo.File.object, destination: Pyjo.File.object, distribution: importlib.metadata.Distribution
) -> None:
    for path in distribution.files or []:
        if path.is_absolute() or path.parts[0] in ('..', 'bin') or not (file := source.child(*path.parts)).is_file:
            continue
        destination.child(*path.parts).dirname().make_path()
        shutil.move(file.to_str(), destination.child(*path.parts).to_str())
    for dir, _, _ in sorted(os.walk(source), reverse=True):
        if dir != os.fspath(source) and not os.listdir(dir):
            os.rmdir(dir)


# The name of a distribution as PEP 503 normalizes it
def _normalize(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


# The error of an application without pyproject.toml, or of a script without it and without the inline
# metadata of PEP 723, with the commands that add them, instead of a build that fails without its dependencies
def _no_dependencies(script: str | None) -> str:
    if script is None:
        return 'No dependencies of the application: add a pyproject.toml with "generate pyproject"'
    add = f'uv add --script {shlex.quote(script)} Pyjoyment'
    return (
        f'No dependencies of the script {script}: add its inline metadata with "{add}", '
        'or a pyproject.toml with "generate pyproject"'
    )


# Whether the script has the inline metadata of PEP 723
def _metadata(path: Pyjo.File.object) -> bool:
    try:
        return re.search(r'(?m)^# /// script\r?$', str(path.slurp('UTF-8') or '')) is not None
    except OSError:
        return False


# The command of uv
def _uv() -> list[str]:
    if (uv := shutil.which('uv')) is None:
        raise Pyjo.Exception.new('Command "uv" not found')
    return [uv]


# A ZIP file of the directory, the same for the same files, with the modes of Lambda, which the files of Windows do not
# have, and without the symbolic links of Python, which the interpreter does not need
def _zip(dir: Pyjo.File.object, path: Pyjo.File.object, executables: set[str]) -> None:
    with zipfile.ZipFile(path.to_str(), 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in dir.list_tree(hidden=True).each():
            if os.path.islink(file):
                continue
            name = file.to_rel(dir).to_str().replace(os.sep, '/')
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | (0o755 if name in executables else 0o644)) << 16
            with open(file, 'rb') as source, archive.open(info, 'w') as destination:
                shutil.copyfileobj(source, destination)


new = Pyjoyment_Command_Author_generate_lambda_zip.new
object = Pyjoyment_Command_Author_generate_lambda_zip

__DATA__ = r"""
@@ bootstrap
#!/bin/sh
# The runtime of the event function: the application, with the runtime client of Pyjo.Server.Lambda
cd "$LAMBDA_TASK_ROOT" || exit 1
exec <%= python %> <%= cmd %>
"""
