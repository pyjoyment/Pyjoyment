import Pyjo.Exception
import Pyjo.String.Unicode
import Pyjo.URL
import Pyjo.URL.Template

from Pyjo.Test import *


# Not in Mojolicious: the URI Templates of RFC 6570, with the examples of its section 3.2 and the variables they have

VARIABLES = {
    'count': ['one', 'two', 'three'],
    'dom': ['example', 'com'],
    'dub': 'me/too',
    'hello': 'Hello World!',
    'half': '50%',
    'var': 'value',
    'who': 'fred',
    'base': 'http://example.com/home/',
    'path': '/foo/bar',
    'list': ['red', 'green', 'blue'],
    'keys': {'semi': ';', 'dot': '.', 'comma': ','},
    'v': '6',
    'x': '1024',
    'y': '768',
    'empty': '',
    'empty_keys': {},
    'undef': None,
}


def expand(template, variables=VARIABLES):
    return str(Pyjo.URL.Template.new(template).expand(variables))


def match(template, uri):
    return Pyjo.URL.Template.new(template).match(uri)


def failure(cb):
    # The message of the exception that the callback raises, or None
    try:
        cb()
    except Pyjo.Exception.object as e:
        return e.message
    return None


with subtest('Variable expansion'):
    is_ok(expand('{count}'), 'one,two,three', 'right expansion')
    is_ok(expand('{count*}'), 'one,two,three', 'right expansion')
    is_ok(expand('{/count}'), '/one,two,three', 'right expansion')
    is_ok(expand('{/count*}'), '/one/two/three', 'right expansion')
    is_ok(expand('{;count}'), ';count=one,two,three', 'right expansion')
    is_ok(expand('{;count*}'), ';count=one;count=two;count=three', 'right expansion')
    is_ok(expand('{?count}'), '?count=one,two,three', 'right expansion')
    is_ok(expand('{?count*}'), '?count=one&count=two&count=three', 'right expansion')
    is_ok(expand('{&count*}'), '&count=one&count=two&count=three', 'right expansion')

with subtest('Simple string expansion'):
    is_ok(expand('{var}'), 'value', 'right expansion')
    is_ok(expand('{hello}'), 'Hello%20World%21', 'right expansion')
    is_ok(expand('{half}'), '50%25', 'right expansion')
    is_ok(expand('O{empty}X'), 'OX', 'right expansion')
    is_ok(expand('O{undef}X'), 'OX', 'right expansion')
    is_ok(expand('{x,y}'), '1024,768', 'right expansion')
    is_ok(expand('{x,hello,y}'), '1024,Hello%20World%21,768', 'right expansion')
    is_ok(expand('?{x,empty}'), '?1024,', 'right expansion')
    is_ok(expand('?{x,undef}'), '?1024', 'right expansion')
    is_ok(expand('?{undef,y}'), '?768', 'right expansion')
    is_ok(expand('{var:3}'), 'val', 'right expansion')
    is_ok(expand('{var:30}'), 'value', 'right expansion')
    is_ok(expand('{list}'), 'red,green,blue', 'right expansion')
    is_ok(expand('{list*}'), 'red,green,blue', 'right expansion')
    is_ok(expand('{keys}'), 'semi,%3B,dot,.,comma,%2C', 'right expansion')
    is_ok(expand('{keys*}'), 'semi=%3B,dot=.,comma=%2C', 'right expansion')

with subtest('Reserved expansion'):
    is_ok(expand('{+var}'), 'value', 'right expansion')
    is_ok(expand('{+hello}'), 'Hello%20World!', 'right expansion')
    is_ok(expand('{+half}'), '50%25', 'right expansion')
    is_ok(expand('{base}index'), 'http%3A%2F%2Fexample.com%2Fhome%2Findex', 'right expansion')
    is_ok(expand('{+base}index'), 'http://example.com/home/index', 'right expansion')
    is_ok(expand('O{+empty}X'), 'OX', 'right expansion')
    is_ok(expand('O{+undef}X'), 'OX', 'right expansion')
    is_ok(expand('{+path}/here'), '/foo/bar/here', 'right expansion')
    is_ok(expand('here?ref={+path}'), 'here?ref=/foo/bar', 'right expansion')
    is_ok(expand('up{+path}{var}/here'), 'up/foo/barvalue/here', 'right expansion')
    is_ok(expand('{+x,hello,y}'), '1024,Hello%20World!,768', 'right expansion')
    is_ok(expand('{+path,x}/here'), '/foo/bar,1024/here', 'right expansion')
    is_ok(expand('{+path:6}/here'), '/foo/b/here', 'right expansion')
    is_ok(expand('{+list}'), 'red,green,blue', 'right expansion')
    is_ok(expand('{+list*}'), 'red,green,blue', 'right expansion')
    is_ok(expand('{+keys}'), 'semi,;,dot,.,comma,,', 'right expansion')
    is_ok(expand('{+keys*}'), 'semi=;,dot=.,comma=,', 'right expansion')

with subtest('Fragment expansion'):
    is_ok(expand('{#var}'), '#value', 'right expansion')
    is_ok(expand('{#hello}'), '#Hello%20World!', 'right expansion')
    is_ok(expand('{#half}'), '#50%25', 'right expansion')
    is_ok(expand('foo{#empty}'), 'foo#', 'right expansion')
    is_ok(expand('foo{#undef}'), 'foo', 'right expansion')
    is_ok(expand('{#x,hello,y}'), '#1024,Hello%20World!,768', 'right expansion')
    is_ok(expand('{#path,x}/here'), '#/foo/bar,1024/here', 'right expansion')
    is_ok(expand('{#path:6}/here'), '#/foo/b/here', 'right expansion')
    is_ok(expand('{#list}'), '#red,green,blue', 'right expansion')
    is_ok(expand('{#list*}'), '#red,green,blue', 'right expansion')
    is_ok(expand('{#keys}'), '#semi,;,dot,.,comma,,', 'right expansion')
    is_ok(expand('{#keys*}'), '#semi=;,dot=.,comma=,', 'right expansion')

with subtest('Label expansion with dot-prefix'):
    is_ok(expand('{.who}'), '.fred', 'right expansion')
    is_ok(expand('{.who,who}'), '.fred.fred', 'right expansion')
    is_ok(expand('{.half,who}'), '.50%25.fred', 'right expansion')
    is_ok(expand('www{.dom*}'), 'www.example.com', 'right expansion')
    is_ok(expand('X{.var}'), 'X.value', 'right expansion')
    is_ok(expand('X{.empty}'), 'X.', 'right expansion')
    is_ok(expand('X{.undef}'), 'X', 'right expansion')
    is_ok(expand('X{.var:3}'), 'X.val', 'right expansion')
    is_ok(expand('X{.list}'), 'X.red,green,blue', 'right expansion')
    is_ok(expand('X{.list*}'), 'X.red.green.blue', 'right expansion')
    is_ok(expand('X{.keys}'), 'X.semi,%3B,dot,.,comma,%2C', 'right expansion')
    is_ok(expand('X{.keys*}'), 'X.semi=%3B.dot=..comma=%2C', 'right expansion')
    is_ok(expand('X{.empty_keys}'), 'X', 'right expansion')
    is_ok(expand('X{.empty_keys*}'), 'X', 'right expansion')

with subtest('Path segment expansion'):
    is_ok(expand('{/who}'), '/fred', 'right expansion')
    is_ok(expand('{/who,who}'), '/fred/fred', 'right expansion')
    is_ok(expand('{/half,who}'), '/50%25/fred', 'right expansion')
    is_ok(expand('{/who,dub}'), '/fred/me%2Ftoo', 'right expansion')
    is_ok(expand('{/var}'), '/value', 'right expansion')
    is_ok(expand('{/var,empty}'), '/value/', 'right expansion')
    is_ok(expand('{/var,undef}'), '/value', 'right expansion')
    is_ok(expand('{/var,x}/here'), '/value/1024/here', 'right expansion')
    is_ok(expand('{/var:1,var}'), '/v/value', 'right expansion')
    is_ok(expand('{/list}'), '/red,green,blue', 'right expansion')
    is_ok(expand('{/list*}'), '/red/green/blue', 'right expansion')
    is_ok(expand('{/list*,path:4}'), '/red/green/blue/%2Ffoo', 'right expansion')
    is_ok(expand('{/keys}'), '/semi,%3B,dot,.,comma,%2C', 'right expansion')
    is_ok(expand('{/keys*}'), '/semi=%3B/dot=./comma=%2C', 'right expansion')

with subtest('Path-style parameter expansion'):
    is_ok(expand('{;who}'), ';who=fred', 'right expansion')
    is_ok(expand('{;half}'), ';half=50%25', 'right expansion')
    is_ok(expand('{;empty}'), ';empty', 'right expansion')
    is_ok(expand('{;v,empty,who}'), ';v=6;empty;who=fred', 'right expansion')
    is_ok(expand('{;v,bar,who}'), ';v=6;who=fred', 'right expansion')
    is_ok(expand('{;x,y}'), ';x=1024;y=768', 'right expansion')
    is_ok(expand('{;x,y,empty}'), ';x=1024;y=768;empty', 'right expansion')
    is_ok(expand('{;x,y,undef}'), ';x=1024;y=768', 'right expansion')
    is_ok(expand('{;hello:5}'), ';hello=Hello', 'right expansion')
    is_ok(expand('{;list}'), ';list=red,green,blue', 'right expansion')
    is_ok(expand('{;list*}'), ';list=red;list=green;list=blue', 'right expansion')
    is_ok(expand('{;keys}'), ';keys=semi,%3B,dot,.,comma,%2C', 'right expansion')
    is_ok(expand('{;keys*}'), ';semi=%3B;dot=.;comma=%2C', 'right expansion')

with subtest('Form-style query expansion'):
    is_ok(expand('{?who}'), '?who=fred', 'right expansion')
    is_ok(expand('{?half}'), '?half=50%25', 'right expansion')
    is_ok(expand('{?x,y}'), '?x=1024&y=768', 'right expansion')
    is_ok(expand('{?x,y,empty}'), '?x=1024&y=768&empty=', 'right expansion')
    is_ok(expand('{?x,y,undef}'), '?x=1024&y=768', 'right expansion')
    is_ok(expand('{?var:3}'), '?var=val', 'right expansion')
    is_ok(expand('{?list}'), '?list=red,green,blue', 'right expansion')
    is_ok(expand('{?list*}'), '?list=red&list=green&list=blue', 'right expansion')
    is_ok(expand('{?keys}'), '?keys=semi,%3B,dot,.,comma,%2C', 'right expansion')
    is_ok(expand('{?keys*}'), '?semi=%3B&dot=.&comma=%2C', 'right expansion')

with subtest('Form-style query continuation'):
    is_ok(expand('{&who}'), '&who=fred', 'right expansion')
    is_ok(expand('{&half}'), '&half=50%25', 'right expansion')
    is_ok(expand('?fixed=yes{&x}'), '?fixed=yes&x=1024', 'right expansion')
    is_ok(expand('{&x,y,empty}'), '&x=1024&y=768&empty=', 'right expansion')
    is_ok(expand('{&var:3}'), '&var=val', 'right expansion')
    is_ok(expand('{&list}'), '&list=red,green,blue', 'right expansion')
    is_ok(expand('{&list*}'), '&list=red&list=green&list=blue', 'right expansion')
    is_ok(expand('{&keys}'), '&keys=semi,%3B,dot,.,comma,%2C', 'right expansion')
    is_ok(expand('{&keys*}'), '&semi=%3B&dot=.&comma=%2C', 'right expansion')

with subtest('Literals and values'):
    is_ok(expand('/a b/{var}', {}), '/a%20b/', 'literal encoded')
    is_ok(expand('/a%20b/{var}', {}), '/a%20b/', 'percent-encoded triplet of a literal')
    is_ok(expand('{var}', {'var': 'Zoë'}), 'Zo%C3%AB', 'UTF-8')
    is_ok(expand('{+var}', {'var': '%41%zz'}), '%41%25zz', 'percent-encoded triplet of a reserved expansion')
    is_ok(expand('{x}/{y}', {'x': 1024, 'y': True}), '1024/true', 'number and boolean')
    is_ok(expand('{list}', {'list': ('a', 'b')}), 'a,b', 'tuple')
    is_ok(expand('{?q}', {'q': []}), '', 'empty list undefined')
    isa_ok(Pyjo.URL.Template.new('/{var}').expand(var='x'), Pyjo.String.Unicode.object, 'string')
    is_ok(str(Pyjo.URL.Template.new('/{var}{?q}').expand({'var': 'x'}, q='y')), '/x?q=y', 'dict and keyword arguments')

with subtest('Variables'):
    is_deeply_ok(Pyjo.URL.Template.new('/{a}/{b,a}{?c*}').variables, ['a', 'b', 'c'], 'names once')
    is_deeply_ok(Pyjo.URL.Template.new('/static').variables, [], 'no variables')
    is_ok(str(Pyjo.URL.Template.new('/{a}')), '/{a}', 'template')

with subtest('Invalid templates'):
    is_ok(failure(lambda: Pyjo.URL.Template.new('/{a')), 'Unmatched brace in URI template: /{a', 'unclosed')
    is_ok(failure(lambda: Pyjo.URL.Template.new('/a}')), 'Unmatched brace in URI template: /a}', 'unopened')
    is_ok(failure(lambda: Pyjo.URL.Template.new('/{}')), 'Invalid expression in URI template: {} of /{}', 'empty')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{=a}')), r'^Invalid expression', 'reserved operator')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{|a}')), r'^Invalid expression', 'reserved operator')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{a-b}')), r'^Invalid expression', 'invalid name')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{a.}')), r'^Invalid expression', 'dot at the end')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{a:0}')), r'^Invalid expression', 'prefix of zero')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{a:10000}')), r'^Invalid expression', 'prefix too long')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{a,,b}')), r'^Invalid expression', 'empty variable')
    like_ok(failure(lambda: Pyjo.URL.Template.new('/{a*:3}')), r'^Invalid expression', 'both modifiers')
    ok(Pyjo.URL.Template.new('/{a.b,c_d,%41}'), 'names with dots, underscores and triplets')
    is_ok(
        failure(lambda: expand('{list:1}')),
        'Prefix modifier of a variable with a list or a dict: list',
        'prefix of a list',
    )

with subtest('Matching simple strings'):
    is_deeply_ok(match('{var}', 'value'), {'var': 'value'}, 'right variables')
    is_deeply_ok(match('{hello}', 'Hello%20World%21'), {'hello': 'Hello World!'}, 'decoded')
    is_deeply_ok(match('{half}', '50%25'), {'half': '50%'}, 'right variables')
    is_deeply_ok(match('O{empty}X', 'OX'), {}, 'empty is undefined')
    is_deeply_ok(match('{x,y}', '1024,768'), {'x': '1024', 'y': '768'}, 'right variables')
    is_deeply_ok(match('?{x,undef}', '?1024'), {'x': '1024'}, 'fewer values')
    is_deeply_ok(match('{list}', 'red,green,blue'), {'list': 'red,green,blue'}, 'list as a string')
    is_deeply_ok(match('{var}', 'Zo%C3%AB'), {'var': 'Zoë'}, 'UTF-8')
    is_deeply_ok(match('{var}', '%E9'), {'var': 'é'}, 'not UTF-8')
    is_ok(match('{var}', 'a b'), None, 'not encoded')
    is_ok(match('{x,y}', '1,2,3'), None, 'more values')
    is_ok(match('/{var}', '/a/b'), None, 'value with a slash')

with subtest('Matching literals'):
    is_deeply_ok(match('/static', '/static'), {}, 'no variables')
    is_ok(match('/static', '/other'), None, 'other literal')
    is_ok(match('/static', '/static/'), None, 'more')
    is_deeply_ok(
        match('repo://{owner}/{repo}/raw', 'repo://pyjoyment/Pyjoyment/raw'),
        {'owner': 'pyjoyment', 'repo': 'Pyjoyment'},
        'right variables',
    )
    is_ok(match('repo://{owner}/{repo}/raw', 'repo://pyjoyment/Pyjoyment/raw/x'), None, 'more after the literal')
    is_ok(match('repo://{owner}/{repo}/raw', 'file://pyjoyment/Pyjoyment/raw'), None, 'other scheme')
    is_deeply_ok(match('docs://{name}.md', 'docs://a.b.md'), {'name': 'a.b'}, 'last expression to the end')
    is_deeply_ok(match('{a}.{b}.txt', 'x.y.z.txt'), {'a': 'x', 'b': 'y.z'}, 'first one to the first literal')
    is_deeply_ok(match('/a%20b/{var}', '/a%20b/x'), {'var': 'x'}, 'encoded literal')

with subtest('Matching reserved and fragment expansions'):
    is_deeply_ok(match('{+path}/here', '/foo/bar/here'), {'path': '/foo/bar'}, 'right variables')
    is_deeply_ok(match('here?ref={+path}', 'here?ref=/foo/bar'), {'path': '/foo/bar'}, 'right variables')
    is_deeply_ok(match('{+base}index', 'http://example.com/home/index'), {'base': 'http://example.com/home/'}, 'right')
    is_deeply_ok(match('{+hello}', 'Hello%20World!'), {'hello': 'Hello World!'}, 'decoded')
    is_deeply_ok(match('file:///{+path}', 'file:///a/b/c.txt'), {'path': 'a/b/c.txt'}, 'right variables')
    is_deeply_ok(
        match('repo://{owner}/blob/{+path}{.ext}', 'repo://pyjoyment/blob/src/main.tar.gz'),
        {'owner': 'pyjoyment', 'path': 'src/main.tar', 'ext': 'gz'},
        'expressions on both sides',
    )
    is_deeply_ok(
        match('{+path}{.ext}', 'a.b/c'), {'path': 'a.b/c'}, 'label that is not one, of the expression in between'
    )
    is_deeply_ok(match('{+path}{?q}', '/a/b?q=x'), {'path': '/a/b', 'q': 'x'}, 'reserved and query')
    is_deeply_ok(match('{+path}{?q}', '/a/b'), {'path': '/a/b'}, 'no query')
    is_deeply_ok(match('{+path}/{name}', '/a/b/c'), {'path': '/a/b', 'name': 'c'}, 'last segment')
    is_deeply_ok(match('{+path}{/a,b}', '/x/1/2'), {'path': '/x', 'a': '1', 'b': '2'}, 'last segments')
    is_deeply_ok(match('{+path}{/a,b}', '/2'), {'a': '2'}, 'fewer segments')
    is_deeply_ok(match('{+path}{;x,y}', '/p;x=1;y=2'), {'path': '/p', 'x': '1', 'y': '2'}, 'last parameters')
    is_deeply_ok(match('{#var}', '#value'), {'var': 'value'}, 'fragment')
    is_deeply_ok(match('foo{#empty}', 'foo#'), {'empty': ''}, 'empty fragment')
    is_deeply_ok(match('foo{#undef}', 'foo'), {}, 'no fragment')
    is_deeply_ok(match('/page{#section}', '/page#a/b'), {'section': 'a/b'}, 'fragment with a slash')
    is_ok(match('/page{#section}', '/pagex'), None, 'no hash')

with subtest('Matching labels and path segments'):
    is_deeply_ok(match('{.who}', '.fred'), {'who': 'fred'}, 'right variables')
    is_deeply_ok(match('{.who,who}', '.fred.fred'), {'who': 'fred'}, 'right variables')
    is_deeply_ok(match('www{.dom*}', 'www.example.com'), {'dom': ['example', 'com']}, 'exploded list')
    is_deeply_ok(match('X{.empty}', 'X.'), {'empty': ''}, 'empty')
    is_deeply_ok(match('X{.undef}', 'X'), {}, 'undefined')
    is_deeply_ok(match('{/who}', '/fred'), {'who': 'fred'}, 'right variables')
    is_deeply_ok(match('{/who,dub}', '/fred/me%2Ftoo'), {'who': 'fred', 'dub': 'me/too'}, 'encoded slash')
    is_deeply_ok(match('{/var,x}/here', '/value/1024/here'), {'var': 'value', 'x': '1024'}, 'right variables')
    is_deeply_ok(match('{/list*}', '/red/green/blue'), {'list': ['red', 'green', 'blue']}, 'exploded list')
    is_deeply_ok(
        match('file:///project{/path*}', 'file:///project/src/main.py'), {'path': ['src', 'main.py']}, 'exploded'
    )
    is_deeply_ok(match('{/a}{/b}', '/x/y'), {'a': 'x', 'b': 'y'}, 'two segments')
    is_deeply_ok(match('{/a}{/b}', '/x'), {'a': 'x'}, 'one segment')

with subtest('Matching parameters'):
    is_deeply_ok(match('{;who}', ';who=fred'), {'who': 'fred'}, 'right variables')
    is_deeply_ok(match('{;empty}', ';empty'), {'empty': ''}, 'empty')
    is_deeply_ok(match('{;v,empty,who}', ';v=6;empty;who=fred'), {'v': '6', 'empty': '', 'who': 'fred'}, 'right')
    is_deeply_ok(match('{;list*}', ';list=red;list=green'), {'list': ['red', 'green']}, 'exploded list')
    is_deeply_ok(match('{;keys*}', ';semi=%3B;dot=.'), {'keys': {'semi': ';', 'dot': '.'}}, 'exploded dict')
    is_deeply_ok(match('{?x,y}', '?x=1024&y=768'), {'x': '1024', 'y': '768'}, 'right variables')
    is_deeply_ok(match('{?x,y}', '?y=768&x=1024'), {'x': '1024', 'y': '768'}, 'any order')
    is_deeply_ok(match('{?x,y,empty}', '?x=1024&y=768&empty='), {'x': '1024', 'y': '768', 'empty': ''}, 'empty')
    is_deeply_ok(match('/search{?q,lang}', '/search'), {}, 'no query')
    is_deeply_ok(match('/search{?q,lang}', '/search?'), {}, 'empty query')
    is_deeply_ok(match('{?list}', '?list=red,green,blue'), {'list': 'red,green,blue'}, 'list as a string')
    is_deeply_ok(match('{?list*}', '?list=red&list=green'), {'list': ['red', 'green']}, 'exploded list')
    is_deeply_ok(match('{?keys*}', '?semi=%3B&dot=.'), {'keys': {'semi': ';', 'dot': '.'}}, 'exploded dict')
    is_deeply_ok(match('?fixed=yes{&x}', '?fixed=yes&x=1024'), {'x': '1024'}, 'continuation')
    is_deeply_ok(match('{?q}{&x}', '?q=a&x=1'), {'q': 'a', 'x': '1'}, 'query and continuation')
    is_ok(match('{?x}', '?y=1'), None, 'unknown name')
    is_ok(match('{?x}', '?x=1&y=2'), None, 'more parameters')
    is_ok(match('{?x}', 'x=1'), None, 'no question mark')

with subtest('Matching a URL'):
    url = Pyjo.URL.new('https://api.github.com/repos/pyjoyment/Pyjoyment/issues?state=open')
    is_deeply_ok(
        match('https://api.github.com/repos/{owner}/{repo}/issues{?state,labels}', url),
        {'owner': 'pyjoyment', 'repo': 'Pyjoyment', 'state': 'open'},
        'Pyjo.URL object',
    )

with subtest('Round trips'):
    for template, variables in (
        ('repo://{owner}/{repo}/blob/{+path}', {'owner': 'pyjoyment', 'repo': 'Pyjoyment', 'path': 'a/b c/d.py'}),
        ('/search{?q,lang}', {'q': 'Hello World!', 'lang': 'pl'}),
        ('file:///project{/path*}', {'path': ['src', 'zażółć.py']}),
        ('{/a,b}{?c}', {'a': '1', 'b': '2', 'c': '3'}),
    ):
        tpl = Pyjo.URL.Template.new(template)
        is_deeply_ok(tpl.match(tpl.expand(variables)), variables, f'round trip of {template}')

with subtest('Ambiguous templates'):
    is_ok(
        failure(lambda: match('{+a}/{+b}', '/x/y')),
        'More than one expression of a reserved or exploded value: {+a}/{+b}',
        'two reserved expansions',
    )
    like_ok(failure(lambda: match('{/a*}{/b*}', '/x/y')), r'^More than one expression', 'two explode modifiers')
    is_ok(
        failure(lambda: match('{a}{b}', 'xy')),
        'Expressions without a literal between them: {a}{b}',
        'adjacent expressions',
    )
    is_ok(
        failure(lambda: match('{+path}{name}', 'xy')),
        'Expressions without a literal between them: {+path}{name}',
        'adjacent to the reserved expansion',
    )
    is_deeply_ok(match('{a}{.b}', 'x.y'), {'a': 'x', 'b': 'y'}, 'first character of the operator between them')
    is_ok(str(Pyjo.URL.Template.new('{a}{b}').expand(a='x', b='y')), 'xy', 'expansion of an ambiguous template')

with subtest('Long URIs'):
    # The time is linear in the length of the URI, as of a client that sends one that does not match
    tpl = Pyjo.URL.Template.new('{a}.{b}-{c}/{+d}/{e}.txt')
    is_ok(tpl.match('.' * 100000 + 'x'), None, 'no match')
    is_ok(tpl.match('a.' * 50000), None, 'no match')
    is_deeply_ok(
        tpl.match('a.b-c/' + 'd/' * 50000 + 'e.txt'),
        {'a': 'a', 'b': 'b', 'c': 'c', 'd': '/'.join(['d'] * 50000), 'e': 'e'},
        'long match',
    )

done_testing()
