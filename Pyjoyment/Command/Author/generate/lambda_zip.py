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

    Options:
      -a, --arch <name>        Architecture of the function, "arm64" or "x86_64",
                               defaults to "x86_64"
      -h, --help               Show this summary of available options
          --no-layer           Put Python and Pyjoyment into the ZIP of the
                               function, without layers
      -p, --python <version>   Version of Python, as "3.14" or "3.15t" for the
                               free-threaded build, defaults to the version that
                               runs the generator
      -r, --runtime <name>     Runtime of the function, "provided.al2023" or one
                               of Python, as "python3.14", defaults to
                               "provided.al2023"

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
``manylinux_2_34``. The application is the files of the current directory,
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

The layer of Pyjoyment has the packages ``Pyjo`` and ``Pyjoyment`` that the
dependencies install, with their bytecode, in
``python/lib/python3.X/site-packages``, which the Python of ``python.zip`` and
the runtime client of the runtime of Python of Lambda of the same version both
put in their path, the runtime client unless ``PYTHONPATH`` is set, so that one
layer serves the functions of both, and a function can take a layer of
Pyjoyment that is published already in its place. A wrapper of
``AWS_LAMBDA_EXEC_WRAPPER`` runs in the place of that runtime client, so its
function names the directory in ``PYTHONPATH``.

With ``--runtime`` of a runtime of Python of Lambda, as ``python3.14``, the
function runs on the Python of Lambda, of the version of the runtime, without
``python.zip`` and without ``bootstrap``, with the handler of the application,
as ``app.handler`` for a script ``app.py`` that ends with
``handler = app.start()``.

With ``--no-layer``, Python and Pyjoyment are in ``function.zip``, Python in
the directory ``python``, and the function needs no layer, at the cost of a
larger ZIP for each deployment.

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

from Pyjo.Util import extract_usage, getopt

import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import zipfile


# The architectures of Lambda and the machines of Linux
_MACHINES = {'arm64': 'aarch64', 'x86_64': 'x86_64'}

# The parts of the standard library that a function does not use
_UNUSED = ('ensurepip', 'idlelib', 'site-packages', 'tkinter', 'turtledemo')

# The packages of Pyjoyment and its metadata, which go to a layer of their own
_PYJOYMENT = r'Pyjo|Pyjoyment|(?i:pyjoyment-[^-]+\.dist-info)'

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
        if not (
            opts := getopt(arguments, {'a|arch=s': None, 'no-layer': None, 'p|python=s': None, 'r|runtime=s': None})
        ):
            raise Pyjo.Exception.new(self.usage)

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

        # The script of Pyjoyment.Lite or the package of the application, and the dependencies of the inline metadata of
        # PEP 723 of the script, if it has them and there is no pyproject.toml, as generate dockerfile has them
        exe = os.environ.get('PYJO_EXE')
        script = Pyjo.File.path(exe).to_rel(self.app.home).to_str() if exe else None
        cmd = [script] if script else ['-m', type(self.app).__module__]
        project = os.path.isfile(self.rel_file('pyproject.toml')) or not exe or not _metadata(Pyjo.File.path(exe))

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
            if project and os.path.isfile(self.rel_file('uv.lock')):
                requirements = tmp.child('requirements.txt').to_str()
                self._uv('export', '--frozen', '--no-dev', '--no-emit-project', '--no-hashes', *_FORMAT, requirements)
            elif not project:
                frozen = ['--frozen'] if os.path.isfile(self.rel_file(f'{script}.lock')) else []
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
                names = sorted(os.listdir(deps)) if os.path.isdir(deps) else []
                if 'Pyjoyment' not in names:
                    raise Pyjo.Exception.new('Pyjoyment is not among the dependencies')
                site.make_path()
                for name in filter(lambda n: re.fullmatch(_PYJOYMENT, n), names):
                    shutil.move(deps.child(name).to_str(), site.child(name).to_str())
            if os.path.isdir(deps):
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
            if not managed:
                executable = f'{prefix}/bin/{interpreter}' if layer else f'"$LAMBDA_TASK_ROOT/python/bin/{interpreter}"'
                function.child('bootstrap').spew(
                    self.render_data('bootstrap', {'cmd': shlex.join(cmd), 'python': executable})
                )

            # The bytecode, as /var/task and /opt are read-only
            if not managed:
                self._compile(local, python, prefix)
            if layer:
                self._compile(local, site, f'/opt/python/lib/{interpreter}/site-packages')
            self._compile(local, function, '/var/task')

            # The ZIP files, without the layers of an earlier build that this one does not write
            dist = self.rel_file('dist')
            self.create_dir(dist)
            for name in ('python.zip', 'pyjoyment.zip'):
                dist.child(name).remove()
            if layer and not managed:
                _zip(python.dirname(), dist.child('python.zip'), {f'python/bin/{interpreter}'})
                self._loud(f'  [write] {dist.child("python.zip")}')
            elif not managed:
                shutil.copytree(python, function.child('python'))
            if layer:
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
