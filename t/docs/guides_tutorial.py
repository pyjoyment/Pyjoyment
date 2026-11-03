import Pyjo.File
import Pyjo.Test.Pyjo

from Pyjo.Test import *

import os
import re
import shutil
import subprocess
import sys
import tempfile


# The examples of docs/guides/tutorial.rst, which includes them
EXAMPLES = Pyjo.File.curfile().dirname().dirname().sibling('docs', 'guides', 'tutorial')


def tutorial(name, home=None):
    return Pyjo.Test.Pyjo.new(Pyjo.File.path(home or EXAMPLES).child(f'{name}.py'))


def command(name, *args, home=None):
    script = Pyjo.File.path(home or EXAMPLES).child(f'{name}.py').to_str()
    env = {**os.environ, 'PYTHONPATH': os.getcwd()}
    env.pop('PYJO_EXE', None)
    env.pop('PYJO_HOME', None)
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, env=env, timeout=60)


def copy(name):
    # The example in a directory of its own, with the files that it reads next to it
    tmp = tempfile.mkdtemp()
    shutil.copy(EXAMPLES.child(f'{name}.py').to_str(), tmp)
    return tmp


with subtest('Hello World'):
    t = tutorial('hello_world')
    t.get_ok('/').status_is(200).content_is('Hello World!')

with subtest('Commands'):
    is_ok(command('hello_world', 'get', '/').stdout, 'Hello World!', 'get')

with subtest('Routes'):
    t = tutorial('routes')
    t.get_ok('/foo').status_is(200).content_is('Hello World!')

with subtest('GET/POST parameters'):
    t = tutorial('parameters')
    t.get_ok('/foo?user=sri').status_is(200).content_is('Hello sri.')

with subtest('Stash and templates'):
    t = tutorial('stash')
    t.get_ok('/foo').status_is(200).content_is('The magic numbers are 23 and 24.\n')

with subtest('HTTP'):
    t = tutorial('request_response')
    t.get_ok('/agent', {'User-Agent': 'Bender'}).status_is(200).content_is('Request by Bender reached 127.0.0.1.')
    t.post_ok('/echo', 'test').status_is(200).header_is('X-Bender', 'Bite my shiny metal ass!').content_is('test')
    result = command('request_response', 'get', '-v', '-M', 'POST', '-c', 'test', '/echo')
    like_ok(result.stderr, re.compile(r'^X-Bender: Bite my shiny metal ass!$', re.M), 'header from the command line')
    like_ok(result.stdout, re.compile(r'test$'), 'body from the command line')

with subtest('JSON'):
    t = tutorial('json_reverse')
    t.put_ok('/reverse', json={'message': 'Hello Pyjo!'}).status_is(200).json_is({'message': '!ojyP olleH'})
    result = command('json_reverse', 'get', '-M', 'PUT', '-c', '{"message":"Hello Pyjo!"}', '/reverse')
    is_ok(result.stdout, '{"message":"!ojyP olleH"}', 'from the command line')

with subtest('Built-in exception and not_found pages'):
    t = tutorial('exception_pages')
    t.get_ok('/missing').status_is(404)
    t.get_ok('/dies').status_is(500).text_like('#error', re.compile(r'Intentional error'))
    like_ok(command('exception_pages', 'get', '/dies', '#error').stdout, re.compile(r'Intentional error'), 'selector')

with subtest('Route names'):
    t = tutorial('route_names')
    t.get_ok('/').status_is(200).content_is('<a href="/hello">Hello</a>.\n<a href="/">Reload</a>.\n')
    t.get_ok('/hello').status_is(200).content_is('Hello World!\n')

with subtest('Layouts'):
    t = tutorial('layouts')
    t.get_ok('/with_layout').status_is(200).text_is('title', 'Green').text_like('body', re.compile(r'Hello World!'))

with subtest('Blocks'):
    t = tutorial('blocks')
    t.get_ok('/with_block').status_is(200)
    t.content_like(re.compile(r'Try <a href="https://mojolicious.org">Mojolicious</a>\.'))
    t.content_like(re.compile(r'Try <a href="https://pyjoyment.readthedocs.io">Pyjoyment</a>\.'))

with subtest('Helpers'):
    t = tutorial('helpers')
    t.get_ok('/secret', {'User-Agent': 'Bender'}).status_is(200).content_is('We know who you are Bender (127.0.0.1).\n')

with subtest('Plugins'):
    t = tutorial('plugins')
    t.get_ok('/foo').status_is(200).json_is({'foo': 'bar'})

with subtest('Placeholders'):
    t = tutorial('placeholders')
    t.get_ok('/foo/test').status_is(200).content_is('Our :bar placeholder matched test')
    t.get_ok('/foo/test123').status_is(200).content_is('Our :bar placeholder matched test123')
    t.get_ok('/testsomething/foo').status_is(200).content_is('Our :bar placeholder matched test')
    t.get_ok('/test123something/foo').status_is(200).content_is('Our :bar placeholder matched test123')

with subtest('Relaxed Placeholders'):
    t = tutorial('relaxed_placeholders')
    t.get_ok('/hello/test').status_is(200).content_is('Your name is test.\n')
    t.get_ok('/hello/test.html').status_is(200).content_is('Your name is test.html.\n')

with subtest('Wildcard placeholders'):
    t = tutorial('wildcard_placeholders')
    t.get_ok('/hello/test').status_is(200).content_is('Your name is test.\n')
    t.get_ok('/hello/test123').status_is(200).content_is('Your name is test123.\n')
    t.get_ok('/hello/test.123/test/123').status_is(200).content_is('Your name is test.123/test/123.\n')

with subtest('HTTP methods'):
    t = tutorial('http_methods')
    t.get_ok('/hello').status_is(200).content_is('Hello World!')
    t.put_ok('/hello', 'four').status_is(200).content_is('You uploaded 4 bytes to /hello.')
    t.get_ok('/bye').status_is(200).content_is('Bye World!')
    t.post_ok('/bye').status_is(200).content_is('Bye World!')
    t.patch_ok('/bye').status_is(200).content_is('Bye World!')
    t.delete_ok('/bye').status_is(404)
    t.delete_ok('/whatever').status_is(200).content_is('You called /whatever with DELETE.')

with subtest('Optional placeholders'):
    t = tutorial('optional_placeholders')
    t.get_ok('/hello').status_is(200).content_is('My name is Sebastian and it is Monday.\n')
    t.get_ok('/hello/Sara').status_is(200).content_is('My name is Sara and it is Monday.\n')

with subtest('Restrictive placeholders'):
    t = tutorial('restrictive_placeholders')
    t.get_ok('/test').status_is(200).content_is('Our :foo placeholder matched test')
    t.get_ok('/123').status_is(200).content_is('Our :foo placeholder matched 123')
    t.get_ok('/other').status_is(404)

    t = tutorial('restrictive_regex')
    t.get_ok('/1').status_is(200).content_is('Our :bar placeholder matched 1')
    t.get_ok('/123').status_is(200).content_is('Our :bar placeholder matched 123')
    t.get_ok('/abc').status_is(404)
    like_ok(command('restrictive_regex', 'routes', '-v').stdout, re.compile(r'/:bar'), 'routes')

with subtest('Under'):
    t = tutorial('under_authentication')
    t.get_ok('/').status_is(200).content_is('You are not Bender, permission denied.\n')
    t.get_ok('/?name=Bender').status_is(200).content_is('Hi Bender.\n')

    t = tutorial('under_prefix')
    t.get_ok('/foo/bar').status_is(200).content_is('foo bar')
    t.get_ok('/foo/baz').status_is(200).content_is('foo baz')
    t.get_ok('/bar').status_is(200).content_is('whatever works\n')

    t = tutorial('under_group')
    t.get_ok('/welcome').status_is(200).content_is("You're not Bender.")
    t.get_ok('/welcome', {'X-Bender': 'Rodriguez'}).status_is(200).content_is('Hi Bender.')
    t.get_ok('/admin/dashboard', {'X-Bender': 'Rodriguez'}).status_is(200).content_is("You're not awesome enough.")
    t.get_ok('/admin/dashboard', {'X-Bender': 'Rodriguez', 'X-Awesome': '1'})
    t.status_is(200).content_is('Nothing to see here yet.')

with subtest('Formats'):
    t = tutorial('formats')
    t.get_ok('/detection.html').status_is(200).content_type_like(re.compile(r'html')).text_is('title', 'Detected')
    t.get_ok('/detection.txt').status_is(200).content_type_like(re.compile(r'text/plain'))
    t.content_is('TXT was detected.\n')
    t.get_ok('/detection').status_is(404)

    t = tutorial('optional_formats')
    t.get_ok('/hello').status_is(200).content_is('hello world')
    t.get_ok('/hello.json').status_is(200).json_is({'hello': 'world'})
    t.get_ok('/hello.txt').status_is(200).content_is('hello world')

with subtest('Content negotiation'):
    t = tutorial('content_negotiation')
    t.get_ok('/hello', {'Accept': 'application/json'}).status_is(200).json_is({'hello': 'world'})
    t.get_ok('/hello', {'Accept': 'application/xml'}).status_is(200).content_is('<hello>world</hello>')
    t.get_ok('/hello.json').status_is(200).json_is({'hello': 'world'})
    t.get_ok('/hello.xml').status_is(200).content_is('<hello>world</hello>')
    t.get_ok('/hello?_format=json').status_is(200).json_is({'hello': 'world'})
    t.get_ok('/hello?_format=xml').status_is(200).content_is('<hello>world</hello>')
    t.get_ok('/hello').status_is(204).content_is('')

    # MIME type mappings
    t.app.types.type('rdf', 'application/rdf+xml')
    is_ok(t.app.types.type('rdf'), 'application/rdf+xml', 'type')

with subtest('Static files'):
    t = tutorial('static_files')
    t.get_ok('/something.js').status_is(200).content_is("alert('hello!');\n\n")
    t.get_ok('/test.txt').status_is(200).content_is('test 123\nlalala')
    result = command('static_files', 'get', '/something.js', '-v', '-H', 'Range: bytes=2-4')
    like_ok(result.stderr, re.compile(r'206 Partial Content'), 'range from the command line')
    like_ok(result.stdout, re.compile(r'ert$'), 'bytes of the range')

with subtest('External templates'):
    home = copy('external_templates')
    Pyjo.File.path(home, 'templates', 'foo').make_path().child('bar.html.ep').spew('Hello World!\n')
    t = tutorial('external_templates', home)
    t.get_ok('/external').status_is(200).content_is('Hello World!\n')
    shutil.rmtree(home)

with subtest('Home'):
    home = copy('home')
    Pyjo.File.path(home, 'cache').make_path().child('hello.txt').spew('Hello World!\n')
    t = tutorial('home', home)
    t.get_ok('/').status_is(200).content_is('Hello World!\n')
    result = command('home', 'eval', '-v', 'app.home', home=home)
    is_ok(result.stdout, f'{home}\n', 'eval')
    shutil.rmtree(home)

with subtest('Conditions'):
    t = tutorial('conditions')
    t.get_ok('/foo', {'User-Agent': 'Firefox'}).status_is(200)
    t.content_is('Congratulations, you are using a cool browser.')
    t.get_ok('/foo', {'User-Agent': 'Internet Explorer'}).status_is(200)
    t.content_is('Dude, you really need to upgrade to Firefox.')
    t.get_ok('/foo', {'User-Agent': 'Other'}).status_is(404)
    t.get_ok('/bar', {'Host': 'mojolicious.org'}).status_is(200).content_is('Hello Mojolicious.')
    t.get_ok('/bar').status_is(404)

with subtest('Sessions'):
    t = tutorial('sessions')
    t.get_ok('/counter').status_is(200).content_is('Counter: 1\n')
    t.get_ok('/counter').status_is(200).content_is('Counter: 2\n')

    # Custom secrets
    t.app.secrets = ['My secret passphrase here']
    t.get_ok('/counter').status_is(200).content_is('Counter: 1\n')

with subtest('File uploads'):
    t = tutorial('file_uploads')
    t.get_ok('/').status_is(200).element_exists('form[action="/upload"][enctype="multipart/form-data"]')
    t.element_exists('input[type="file"][name="example"]').element_exists('input[type="submit"][value="Upload"]')
    t.post_ok('/upload', form={'example': {'content': 'abc', 'filename': 'x.txt'}}).status_is(200)
    t.content_is('Thanks for uploading 3 byte file x.txt.')
    t.post_ok('/upload').status_is(302).header_like('Location', re.compile(r'/$'))

    # Increase limit to 1GiB
    t.app.max_request_size = 1073741824
    is_ok(t.app.max_request_size, 1073741824, 'limit')

    t.app.max_request_size = 10
    t.post_ok('/upload', form={'example': {'content': 'a' * 100, 'filename': 'x.txt'}}).status_is(200)
    t.content_is('File is too big.')

with subtest('User agent'):
    t = tutorial('user_agent')

    # The first application of Pyjoyment.Lite in a process is the one of the servers of the user agents, as in Mojo
    t.app.ua.server.app = t.app
    t.app.routes.get('/page', lambda c: c.render(data=b'<h1>One</h1><p>x</p><h2>Two</h2><h3>Three</h3>'))
    t.get_ok('/headers?url=/page').status_is(200).json_is(['One', 'Two', 'Three'])

    if os.environ.get('TEST_ONLINE'):

        @subtest('Remote hosts', reruns=2, reruns_delay=10)
        def _():
            t.get_ok('/title').status_is(200).content_like(re.compile(r'Mojolicious'))
            t.get_ok('/titles').status_is(200).json_like('/mojo', re.compile(r'Mojolicious'))
            t.json_like('/pyjo', re.compile(r'Pyjoyment'))


with subtest('WebSockets'):
    t = tutorial('websockets')
    t.get_ok('/').status_is(200).content_like(re.compile(r"new WebSocket\('ws://127\.0\.0\.1:\d+/echo'\)"))
    t.websocket_ok('/echo').send_ok({'json': {'msg': 'I ♥ Pyjoyment!'}}).message_ok()
    t.json_message_is({'msg': 'echo: I ♥ Pyjoyment!'}).finish_ok()

with subtest('JSON-RPC'):
    t = tutorial('json_rpc')

    # The first application of Pyjoyment.Lite in a process is the one of the servers of the user agents, as in Mojo
    t.app.ua.server.app = t.app
    request = {'jsonrpc': '2.0', 'method': 'divide', 'params': [7, 2], 'id': 1}
    t.post_ok('/rpc', json=request).status_is(200).json_is({'jsonrpc': '2.0', 'result': 3.5, 'id': 1})
    t.get_ok('/divide/7/2').status_is(200).json_is({'result': 3.5})
    t.get_ok('/divide/1/0').status_is(400).json_is({'error': 'Division by zero', 'code': 1})
    t.get_ok('/divide/x/0').status_is(404)
    message = '{"jsonrpc":"2.0","method":"divide","params":[7,2],"id":1}'
    result = command('json_rpc', 'get', '-M', 'POST', '-c', message, '/rpc')
    is_ok(result.stdout, '{"jsonrpc":"2.0","result":3.5,"id":1}', 'server from the command line')
    result = command('json_rpc', 'get', '/divide/7/2')
    is_ok(result.stdout, '{"result":3.5}', 'client from the command line')

with subtest('Mode'):
    t = tutorial('mode')
    t.get_ok('/').status_is(200).content_is('Development!')
    os.environ['PYJO_MODE'] = 'production'
    t = tutorial('mode')
    t.get_ok('/').status_is(200).content_is('Something else!')
    del os.environ['PYJO_MODE']

with subtest('Testing'):
    home = tempfile.mkdtemp()
    Pyjo.File.path(home, 'myapp.py').spew(
        "from Pyjoyment.Lite import *\n\nget('/', {'text': 'Funky!'})\n\napp.start()\n"
    )
    Pyjo.File.path(home, 't').make_path().child('basic.py').spew("""\
from Pyjo.Test import *

import Pyjo.File
import Pyjo.Test.Pyjo

import re

# Portably point to "../myapp.py"
script = Pyjo.File.curfile().dirname().sibling('myapp.py')

t = Pyjo.Test.Pyjo.new(script)
t.get_ok('/').status_is(200).content_like(re.compile(r'Funky'))

done_testing()
""")
    result = subprocess.run(
        [sys.executable, '-m', 'Pyjo.Prove', '-l', '-v', 't/basic.py'],
        capture_output=True,
        text=True,
        cwd=home,
        env={**os.environ, 'PYTHONPATH': os.getcwd()},
        timeout=60,
    )
    like_ok(result.stdout, re.compile(r'Result: PASS'), 'prove')
    shutil.rmtree(home)

done_testing()
