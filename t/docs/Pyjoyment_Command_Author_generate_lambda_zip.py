import Pyjo.File
import Pyjo.Home
import Pyjoyment
import Pyjoyment.Command.Author.generate.lambda_zip

from Pyjo.Test import *

import contextlib
import io
import os
import sys
import zipfile


sys.path.insert(0, Pyjo.File.curfile().dirname().sibling('lib').to_str())
import FakeUV  # noqa: E402  # pyright: ignore[reportMissingImports]


cwd = Pyjo.File.path()
exe = os.environ.pop('PYJO_EXE', None)
python = f'{sys.version_info.major}.{sys.version_info.minor}'
log = Pyjo.File.tempfile()
os.environ['FAKE_UV_LOG'] = log.to_str()
Pyjoyment.Command.Author.generate.lambda_zip._uv = FakeUV.command


def generate(dir, *args):
    log.spew('')
    os.chdir(dir)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            lambda_zip.run(*args)
    finally:
        os.chdir(cwd)
    return FakeUV.calls(log.to_str())


def read(path, name):
    with zipfile.ZipFile(path.to_str()) as archive:
        return archive.read(name).decode()


def names(path):
    with zipfile.ZipFile(path.to_str()) as archive:
        return archive.namelist()


with subtest('Synopsis'):
    application = Pyjoyment.new()
    lambda_zip = Pyjoyment.Command.Author.generate.lambda_zip.new(app=application)
    like_ok(
        lambda_zip.usage,
        r'^Usage: APPLICATION generate lambda-zip \[OPTIONS\]\n\n  \./myapp\.py generate lambda-zip\n',
        'usage',
    )
    like_ok(lambda_zip.usage, r'-a, --arch <name>', 'option of the architecture')
    like_ok(lambda_zip.usage, r'    --no-layer', 'option of the layer')
    like_ok(lambda_zip.usage, r'-p, --python <version>', 'option of Python')
    like_ok(lambda_zip.usage, r'-r, --runtime <name>', 'option of the runtime')

    # python -m MyApp generate lambda-zip
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    calls = generate(tmp)
    is_ok(calls[0][-1], f'cpython-{python}-linux-x86_64-gnu', 'Python of x86_64')
    like_ok(read(tmp.child('dist', 'function.zip'), 'bootstrap'), r'(?m)^exec \S+ -m Pyjoyment$', 'package')
    ok(f'python/bin/python{python}' in names(tmp.child('dist', 'python.zip')), 'layer')

    # python -m MyApp generate lambda-zip --arch arm64
    calls = generate(tmp, '--arch', 'arm64')
    is_ok(calls[0][-1], f'cpython-{python}-linux-aarch64-gnu', 'Python of arm64')

    # python -m MyApp generate lambda-zip --python 3.15t
    calls = generate(tmp, '--python', '3.15t')
    is_ok(calls[0][-1], 'cpython-3.15t-linux-x86_64-gnu', 'free-threaded Python')
    ok('python/bin/python3.15t' in names(tmp.child('dist', 'python.zip')), 'free-threaded interpreter')

    # python -m MyApp generate lambda-zip --no-layer
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    generate(tmp, '--no-layer')
    ok(f'python/bin/python{python}' in names(tmp.child('dist', 'function.zip')), 'Python in the function')
    ok('Pyjoyment/__init__.py' in names(tmp.child('dist', 'function.zip')), 'Pyjoyment in the function')
    ok(not os.path.exists(tmp.child('dist', 'python.zip')), 'no layer')

    # python -m MyApp generate lambda-zip --runtime python3.14
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    calls = generate(tmp, '--runtime', 'python3.14')
    ok(not os.path.exists(tmp.child('dist', 'python.zip')), 'Python of the runtime')
    ok('bootstrap' not in names(tmp.child('dist', 'function.zip')), 'handler of the application')
    pyjoyment = names(tmp.child('dist', 'pyjoyment.zip'))
    ok('python/lib/python3.14/site-packages/Pyjoyment/__init__.py' in pyjoyment, 'Pyjoyment of the runtime')

    # python -m MyApp generate lambda-zip --compress public
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    tmp.child('public').make_path().child('app.css').spew('body { color: #333 }\n' * 100)
    generate(tmp, '--compress', 'public')
    ok('public/app.css.gz' in names(tmp.child('dist', 'function.zip')), 'variants')

    # ./myapp.py generate lambda-zip
    tmp = Pyjo.File.tempdir()
    tmp.child('myapp.py').spew('')
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    application.home = Pyjo.Home.new(tmp.to_str())
    os.environ['PYJO_EXE'] = tmp.child('myapp.py').to_str()
    try:
        generate(tmp)
    finally:
        os.environ.pop('PYJO_EXE', None)
    like_ok(read(tmp.child('dist', 'function.zip'), 'bootstrap'), r'(?m)^exec \S+ myapp\.py$', 'script')

with subtest('Description'):
    application = Pyjoyment.new()
    lambda_zip = Pyjoyment.Command.Author.generate.lambda_zip.new(app=application)
    tmp = Pyjo.File.tempdir()
    tmp.child('pyproject.toml').spew('[project]\nname = "my_app"\n')
    tmp.child('.hidden').spew('')
    tmp.child('MyApp').make_path().child('__init__.py').spew('pass\n')
    calls = generate(tmp)
    function = names(tmp.child('dist', 'function.zip'))
    ok('bootstrap' in function and 'MyApp/__init__.py' in function, 'application and bootstrap')
    ok('foo/__init__.py' in function, 'dependencies')
    ok('.hidden' not in function, 'no hidden files')
    like_ok(read(tmp.child('dist', 'function.zip'), 'bootstrap'), r'(?m)^exec /opt/python/bin/', 'Python of the layer')
    ok('Pyjoyment/__init__.py' not in function, 'Pyjoyment in its own layer')
    pyjoyment = names(tmp.child('dist', 'pyjoyment.zip'))
    site = f'python/lib/python{python}/site-packages'
    ok(f'{site}/Pyjo/__init__.py' in pyjoyment and f'{site}/Pyjoyment/__init__.py' in pyjoyment, 'layer of Pyjoyment')
    ok(any(name.startswith(f'{site}/Pyjoyment/__pycache__/') for name in pyjoyment), 'bytecode of Pyjoyment')
    layer = ' '.join(names(tmp.child('dist', 'python.zip')))
    unlike_ok(layer, r'idlelib|tkinter|site-packages', 'without what a function does not use')
    like_ok(layer, r'__pycache__/os\.', 'bytecode of the standard library')
    ok(any(name.startswith('MyApp/__pycache__/') for name in function), 'bytecode of the application')
    bytecode = next(name for name in function if name.startswith('MyApp/__pycache__/'))
    with zipfile.ZipFile(tmp.child('dist', 'function.zip').to_str()) as archive:
        # The flags of the header of the bytecode: based on a hash, without checking the source
        is_ok(int.from_bytes(archive.read(bytecode)[4:8], 'little'), 0b01, 'unchecked-hash')
    pip = next(call for call in calls if call[:2] == ['pip', 'install'])
    is_ok(pip[pip.index('--python-platform') + 1], 'x86_64-manylinux_2_34', 'Amazon Linux 2023')
    is_ok(pip[pip.index('-r') + 1], 'pyproject.toml', 'pyproject.toml')
    zips = tmp.child('dist', 'function.zip').slurp(), tmp.child('dist', 'python.zip').slurp()
    generate(tmp)
    ok(zips == (tmp.child('dist', 'function.zip').slurp(), tmp.child('dist', 'python.zip').slurp()), 'same files')

    tmp.child('uv.lock').spew('')
    calls = generate(tmp)
    export = next(call for call in calls if call[0] == 'export')
    ok('--frozen' in export, 'uv.lock')

    tmp = Pyjo.File.tempdir()
    tmp.child('myapp.py').spew('# /// script\n# dependencies = ["Pyjoyment"]\n# ///\n')
    tmp.child('myapp.py.lock').spew('')
    application.home = Pyjo.Home.new(tmp.to_str())
    os.environ['PYJO_EXE'] = tmp.child('myapp.py').to_str()
    try:
        calls = generate(tmp)
    finally:
        os.environ.pop('PYJO_EXE', None)
    export = next(call for call in calls if call[0] == 'export')
    is_ok(export[:3], ['export', '--script', 'myapp.py'], 'inline metadata')
    ok('--frozen' in export, 'lock of the script')

with subtest('Attributes'):
    lambda_zip = Pyjoyment.Command.Author.generate.lambda_zip.new()
    is_ok(lambda_zip.description, 'Generate ZIP files of AWS Lambda', 'description')
    like_ok(lambda_zip.usage, r'generate lambda-zip', 'usage')

if exe is not None:
    os.environ['PYJO_EXE'] = exe

done_testing()
