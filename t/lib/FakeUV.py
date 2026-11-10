import json
import os
import subprocess
import sys


# A uv for generate lambda-zip, which logs its arguments in the file of FAKE_UV_LOG, fails for the command of
# FAKE_UV_FAIL, makes what the generator takes from it, a Python of python-build-standalone and the packages of the
# dependencies, with Pyjoyment unless FAKE_UV_NO_PYJOYMENT is set, and compiles with the Python of the test, without
# the network
def command():
    return [sys.executable, os.path.abspath(__file__)]


def calls(log):
    with open(log) as file:
        return [json.loads(line) for line in file]


def _spew(*parts, content='pass\n'):
    path = os.path.join(*parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as file:
        file.write(content)


# The files of a distribution, with its metadata and the RECORD of all of them
def _distribution(target, name, version, files):
    metadata = f'{name.replace("-", "_").lower()}-{version}.dist-info'
    for file in files:
        _spew(target, *file.split('/'))
    _spew(target, metadata, 'METADATA', content=f'Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\nAbout\n')
    record = [*files, f'{metadata}/METADATA', f'{metadata}/RECORD']
    _spew(target, metadata, 'RECORD', content=''.join(f'{file},,\n' for file in record))


def _main(args):
    with open(os.environ['FAKE_UV_LOG'], 'a') as log:
        log.write(json.dumps(args) + '\n')
    if args[0] == os.environ.get('FAKE_UV_FAIL'):
        return 2

    # The Python of the layer, in its directory; the one of the machine is only logged
    if args[:2] == ['python', 'install'] and '--install-dir' in args:
        # The directory of the full version, and the link of the minor version, which comes first in the order of names
        version = args[-1].split('-')[1]
        full = args[-1].replace(
            version, version.removesuffix('t') + '.0' + ('+freethreaded' if version[-1] == 't' else '')
        )
        install = args[args.index('--install-dir') + 1]
        home = os.path.join(install, full)
        name = 'python' + version
        _spew(home, 'bin', name, content='ELF')
        try:
            os.symlink(full, os.path.join(install, args[-1]))
            os.symlink(name, os.path.join(home, 'bin', 'python3'))
        except OSError:
            pass
        for path in (
            'os.py',
            'idlelib/__init__.py',
            'site-packages/pip/__init__.py',
            'config-3-linux/Makefile',
            'lib-dynload/_json.so',
            'lib-dynload/_tkinter.so',
        ):
            _spew(home, 'lib', name, *path.split('/'))

        # The variables of the build with the directory of the installation, and a set of strings in the bytecode
        _spew(home, 'lib', name, '_sysconfigdata__linux.py', content=f'build_time_vars = {{"prefix": {home!r}}}\n')
        strings = ', '.join(repr(c) for c in 'abcdefghijklmnop')
        _spew(home, 'lib', name, 'webbrowser.py', content=f'def f(x):\n    return x in {{{strings}}}\n')
        _spew(home, 'include', 'Python.h')
    elif args[0] == 'export':
        _spew(args[args.index('-o') + 1], content='foo\n')
    elif args[:2] == ['pip', 'install']:
        target = args[args.index('--target') + 1]
        _spew(target, 'foo', '__init__.py')
        if not os.environ.get('FAKE_UV_NO_PYJOYMENT'):
            _distribution(target, 'Pyjoyment', '0.0.2', ['Pyjo/__init__.py', 'Pyjoyment/__init__.py', 'bin/foo'])
        # Another distribution of the namespace Pyjo
        _distribution(target, 'Pyjo-Foo', '0.1.0', ['Pyjo/Foo/__init__.py'])
        _spew(target, 'bin', 'foo')
        _spew(target, '.lock')
    elif args[0] == 'run':
        return subprocess.run([sys.executable, *args[args.index('--') + 2 :]]).returncode
    return 0


if __name__ == '__main__':
    if 'FAKE_UV_LOG' in os.environ:
        sys.exit(_main([arg for arg in sys.argv[1:] if arg != '--quiet']))

    from Pyjo.Test import plan

    plan(skip_all='helper module, not a test')
