---
name: mojolicious
description: Port an application, a script or a test of Mojolicious, Mojo or Test::Mojo from Perl to Pyjoyment, the port of Mojolicious to Python. Use for the translation of Mojolicious::Lite, of a full Mojolicious application and its controllers, of ep templates, of Mojo::UserAgent, Mojo::DOM, Mojo::IOLoop and Mojo::Promise code, and of tests of Test::Mojo, with the names and idioms that Pyjoyment gives them.
---

# Porting from Mojolicious

Pyjoyment is Mojolicious in Python, with the same classes, methods and
behaviour where Python allows: `Mojo::*` is `Pyjo.*`, `Mojolicious::*` is
`Pyjoyment.*`, `Test::Mojo` is `Pyjo.Test.Pyjo`, and `ojo` is `Pyjo`. A port
keeps the structure of the Perl code and translates its idioms.

## An application and its test

```perl
use Mojolicious::Lite -signatures;

helper greeting => sub ($c, $name) { "Hello $name!" };

get '/' => sub ($c) {
  $c->render(template => 'index', name => $c->param('name') // 'World');
};

get '/api/:id' => [id => qr/\d+/] => sub ($c) {
  $c->render(json => {id => $c->param('id')});
};

app->start;
__DATA__

@@ index.html.ep
% layout 'default';
<p><%= greeting $name %></p>
% for my $i (1 .. 3) {
  <i><%= $i %></i>
% }

@@ layouts/default.html.ep
<!DOCTYPE html>
<html><body><%= content %></body></html>
```

```python
# app.py
"""
__DATA__

@@ index.html.ep
% layout('default')
<p><%= greeting(name) %></p>
% for i in range(1, 4):
  <i><%= i %></i>
% end

@@ layouts/default.html.ep
<!DOCTYPE html>
<html><body><%= content() %></body></html>
"""

import re

from Pyjoyment.Lite import *


@helper('greeting')
def greeting(c, name):
    return f'Hello {name}!'


@get('/')
def index(c):
    c.render(template='index', name=c.param('name') or 'World')


@get('/api/:id', id=re.compile(r'\d+'))
def api(c):
    c.render(json={'id': c.param('id')})


app.start()
```

```perl
use Mojo::File qw(curfile);
use Test::More;
use Test::Mojo;

my $t = Test::Mojo->new(curfile->dirname->sibling('app.pl'));
$t->get_ok('/?name=Sara')->status_is(200)->text_is(p => 'Hello Sara!');
is $t->tx->res->dom->find('i')->size, 3, 'three items';
$t->get_ok('/api/23')->status_is(200)->json_is('/id' => 23);

done_testing;
```

```python
# t/app.py
import Pyjo.Test.Pyjo

from Pyjo.File import curfile
from Pyjo.Test import *


t = Pyjo.Test.Pyjo.new(curfile().dirname().sibling('app.py'))
t.get_ok('/?name=Sara').status_is(200).text_is('p', 'Hello Sara!')
is_ok(t.tx.res.dom().find('i').size, 3, 'three items')
t.get_ok('/api/23').status_is(200).json_is('/id', '23')

done_testing()
```

## Translations

| Mojolicious                                                  | Pyjoyment                                                          |
| ------------------------------------------------------------ | ------------------------------------------------------------------ |
| `get '/' => sub ($c) {...};`                                 | `@get('/')` over `def index(c): ...`                               |
| `get '/' => 'index';`, `get '/' => {text => 'Hi'};`          | `get('/', 'index')`, `get('/', {'text': 'Hi'})`                    |
| `[id => qr/\d+/]`, `[format => ['json']]`                    | `id=re.compile(r'\d+')`, `format=['json']`                         |
| `under sub ($c) {...};`, `group {...};`                      | `@under` over a function, `with group():`                          |
| `app->start;`, `__DATA__`                                    | `app.start()`, the docstring after a line `__DATA__`               |
| `$c->render(json => {...}, status => 201)`                   | `c.render(json={...}, status=201)`                                 |
| `$c->param('x') // 'default'`, `undef`                       | `c.param('x') or 'default'`, `None`                                |
| `$c->stash(foo => 1)`, `$c->session->{user}`                 | `c.stash(foo=1)`, `c.session('user')`                              |
| `$c->ua->get($url => {Accept => '*/*'} => form => {a => 1})` | `c.ua().get(url, {'Accept': '*/*'}, form={'a': 1})`                |
| `$c->on(message => sub ($c, $msg) {...})`                    | `@c.on('message')` over `def message(c, msg): ...`                 |
| `async sub ($c) { my $tx = await $c->ua->get_p($url) }`      | `async def action(c): tx = await c.ua().get_p(url)`                |
| `Mojo::IOLoop->timer(2 => sub ($loop) {...})`                | `Pyjo.IOLoop.timer(2, lambda loop: ...)`                           |
| `$promise->then(sub ($v) {...})->catch(...)->finally(...)`   | `promise.then(lambda v: ...).catch(...).lastly(...)`               |
| `$dom->find('a')->map(attr => 'href')->join("\n")`           | `dom.find('a').map('attr', 'href').join('\n')`                     |
| `use Mojo::Util qw(b64_encode sha1_sum);`, `b($s)->sha1_sum` | `from Pyjo.Util import b64_encode, sha1_sum`, `b(s).sha1_sum()`    |
| `path($file)->slurp`, `tempdir`                              | `Pyjo.File.path(file).slurp()`, `Pyjo.File.tempdir()`              |
| `die`, `Mojo::Exception->throw`, `->continue`, `$t->or`      | `raise`, `Pyjo.Exception.throw`, `.proceed()`, `t.otherwise`       |
| `is`, `is_deeply`, `like`                                    | `is_ok`, `is_deeply_ok`, `like_ok`                                 |
| `plugin 'NotYAMLConfig';`, `plugin 'Config';`                | `plugin('YAMLConfig')`, `plugin('Config')`, `plugin('TOMLConfig')` |
| `morbo`, `hypnotoad`, `mojo generate app`, `MOJO_MODE`       | `pyjo-reload`, `pyjo-hot`, `pyjo generate app`, `PYJO_MODE`        |

- A full application is a package: `package MyApp; use Mojo::Base
  'Mojolicious', -signatures;` is `class MyApp(Pyjoyment.object):` in
  `MyApp/__init__.py`, which ends with `object = MyApp`, and a controller
  `MyApp::Controller::Users` is a class in `MyApp/Controller/Users.py`, whose
  module names it `object`.
- A helper that takes a block, as `form_for login => (method => 'POST') =>
  begin`, is `%= form_for('login', begin` with `%= end, method='POST')`: the
  block is the last positional argument and the attributes follow it.
- An attribute of Mojo, and a method without arguments that describes the
  object, are attributes and properties: `$c->req->url->path` is
  `c.req.url.path`, and `$collection->size` is `collection.size`, not
  `size()`.
- `$_` of a callback is its first argument, and a callback returns one value,
  where Perl returns a list.

## Mistakes

- A value of the stash and a helper share one namespace in a template, where
  Perl has sigils: the layout calls `c.title()`, as `title` can be a value.
- `$c->param('x') // 'default'` keeps an empty string, `or` does not: `x if
  (x := c.param('x')) is not None else 'default'` where it matters.
- A placeholder is a string, as in Perl: `json_is('/id', '23')`, or convert it.
- `qr/.../` is `re.compile(r'...')`, with a raw string, and a global flag as
  `(?i)` only at the start of a pattern of Python.
- A string of Perl in single quotes keeps `\n` as two characters, a string of
  Python does not.

## Documentation

- Pyjoyment: https://pyjoyment.readthedocs.io/en/latest/
- The guides, ports of Mojolicious::Guides: https://pyjoyment.readthedocs.io/en/latest/guides/index.html
