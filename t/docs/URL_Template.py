import Pyjo.Exception
import Pyjo.String.Unicode
import Pyjo.URL

from Pyjo.Test import *

import contextlib
import io


with subtest('Synopsis'):
    from Pyjo.URL.Template import Template

    template = Template('https://api.github.com/repos/{owner}/{repo}/issues{?state,labels}')
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        print(template.expand(owner='pyjoyment', repo='Pyjoyment', state='open'))
        print(template.match('https://api.github.com/repos/pyjoyment/Pyjoyment/issues?state=open'))
    is_ok(
        stdout.getvalue(),
        'https://api.github.com/repos/pyjoyment/Pyjoyment/issues?state=open\n'
        "{'owner': 'pyjoyment', 'repo': 'Pyjoyment', 'state': 'open'}\n",
        'printed',
    )

    # Or import the module, as in Google Python Style Guide

    import Pyjo.URL.Template

    template = Pyjo.URL.Template.new('file:///project/{+path}')
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        print(template.expand({'path': 'src/main.py'}))
        print(template.match('file:///project/src/main.py')['path'])
    is_ok(stdout.getvalue(), 'file:///project/src/main.py\nsrc/main.py\n', 'printed')

with subtest('Description'):
    # "/search?q=Hello%20World%21&lang=en"
    is_ok(
        Pyjo.URL.Template.new('/search{?q,lang}').expand(q='Hello World!', lang='en'),
        '/search?q=Hello%20World%21&lang=en',
        'expand',
    )

    # {'owner': 'pyjoyment', 'path': 'src/main.py'}
    is_deeply_ok(
        Pyjo.URL.Template.new('repo://{owner}/blob/{+path}').match('repo://pyjoyment/blob/src/main.py'),
        {'owner': 'pyjoyment', 'path': 'src/main.py'},
        'match',
    )

with subtest('new'):
    tpl = Pyjo.URL.Template.new('/search{?q,lang}')
    is_ok(tpl.template, '/search{?q,lang}', 'template')
    try:
        Pyjo.URL.Template.new('/search{?q')
    except Pyjo.Exception.object as e:
        is_ok(e.message, 'Unmatched brace in URI template: /search{?q', 'not valid')
    else:
        fail_ok('not valid')

with subtest('template'):
    template = tpl.template
    is_ok(template, '/search{?q,lang}', 'template')

with subtest('__str__'):
    string = str(tpl)
    is_ok(string, '/search{?q,lang}', 'string')

with subtest('variables'):
    names = tpl.variables
    is_deeply_ok(names, ['q', 'lang'], 'names')

    # ['owner', 'repo', 'state']
    is_deeply_ok(
        Pyjo.URL.Template.new('/repos/{owner}/{repo}/issues{?state}').variables, ['owner', 'repo', 'state'], 'names'
    )

with subtest('expand'):
    url = tpl.expand(q='Hello World!')
    is_ok(url, '/search?q=Hello%20World%21', 'url')
    isa_ok(url, Pyjo.String.Unicode.object, 'string')
    url = tpl.expand({'q': 'Hello World!', 'lang': 'en'})
    is_ok(url, '/search?q=Hello%20World%21&lang=en', 'url')

    # "/repos/pyjoyment/Pyjoyment/issues?labels=bug,docs"
    template = Pyjo.URL.Template.new('/repos/{owner}/{repo}/issues{?labels}')
    is_ok(
        template.expand(owner='pyjoyment', repo='Pyjoyment', labels=['bug', 'docs']),
        '/repos/pyjoyment/Pyjoyment/issues?labels=bug,docs',
        'list',
    )

with subtest('match'):
    variables = tpl.match('/search?q=Hello%20World%21')
    is_deeply_ok(variables, {'q': 'Hello World!'}, 'variables')
    is_deeply_ok(tpl.match(Pyjo.URL.new('/search?lang=en')), {'lang': 'en'}, 'Pyjo.URL')
    is_ok(tpl.match('/other'), None, 'no match')

    # {'q': 'Hello World!'}
    is_deeply_ok(
        Pyjo.URL.Template.new('/search{?q,lang}').match('/search?q=Hello%20World%21'), {'q': 'Hello World!'}, 'match'
    )

    # {'path': ['src', 'main.py']}
    is_deeply_ok(
        Pyjo.URL.Template.new('file:///project{/path*}').match('file:///project/src/main.py'),
        {'path': ['src', 'main.py']},
        'match',
    )

done_testing()
