---
name: templates
description: Write the templates of a Pyjoyment application. Use for ep templates of Embedded Python (tags, lines, blocks with end, escaping, the values of the stash as variables), layouts, partial templates, content blocks, helpers and tag helpers in templates, forms with CSRF protection and validation, templates of __DATA__ and templates/, and the template strings of PyRenderer.
---

# Templates

An `ep` template, of Embedded Python, is text with Python in its tags and
lines, which escapes what it prints. Its file is `templates/name.format.ep`,
as `templates/index.html.ep`, or a section of the `__DATA__` of a script of
`Pyjoyment.Lite`. The values of the stash are its variables, the controller is
`c`, and the helpers are its functions. Python 3.14 has the template strings
of `PyRenderer` too, written as functions of Python.

## Syntax

```text
<% Python code %>
<%= Python expression, replaced with its escaped result %>
<%== Python expression, replaced with its result as it is %>
<%# Comment %>
% Python code line
%= Python expression line, escaped
%== Python expression line, as it is
%# Comment line
```

A line that ends with `:` opens a block, which `% end` closes, as the
indentation of a template does not matter. `<%= ... =%>` trims the whitespace
around the tag, and a backslash at the end of a line joins the next one.

## Layouts, partials, blocks, forms

```python
"""
__DATA__

@@ index.html.ep
% layout('default')
% title('Shopping list')
% content_for('head', begin
  <meta name="description" content="A shopping list">
% end)
%= include('_items', items=items)
<p><%= link_to('Add an item', 'add') %></p>
<p><%= '<b>escaped</b>' %> <%== '<b>as it is</b>' %></p>

@@ _items.html.ep
% if items:
  <ul>
    % for item in items:
      <li><%= item %></li>
    % end
  </ul>
% else:
  <p>Nothing to buy.</p>
% end

@@ add.html.ep
% layout('default')
% title('Add an item')
%= form_for('save', begin
  %= csrf_field()
  %= text_field('item', placeholder='Bread')
  %= submit_button('Add')
% end)
% if (error := validation().error('item')):
  <p class="error">The item is <%= error[0] %>.</p>
% end

@@ layouts/default.html.ep
<!DOCTYPE html>
<html>
  <head>
    <title><%= c.title() %></title>
    %= content('head')
  </head>
  <body>
    <h1><%= c.title() %></h1>
    %= content()
  </body>
</html>
"""

from Pyjoyment.Lite import *


items = []


@get('/')
def index(c):
    c.render('index', items=items)


@get('/add', 'add')
def add(c):
    c.render('add')


# The form of the template "add" posts here, as form_for takes the method of the route named "save"
@post('/add', 'save')
def save(c):
    v = c.validation()
    if v.csrf_protect().has_error('csrf_token'):
        return c.render(text='Bad CSRF token', status=403)
    v.required('item', 'trim', 'not_empty').size(1, 30)
    if v.has_error():
        return c.render('add', status=400)
    items.append(v.param('item'))
    c.redirect_to('/')


app.start()
```

- `layout('name')` renders the template into `layouts/name.html.ep`, where
  `content()` is its output, and `content_for('head', begin ... % end)` adds
  to a named block that `content('head')` prints; `extends('name')` does the
  same for a template that a child overrides by its blocks.
- `include('_name', key=value)` renders a partial template with more values.
- A block of a template, `begin` and `% end)`, is a function that a helper
  takes as its last positional argument, as `form_for`, so the parenthesis
  closes after `end`.
- The tag helpers take the attributes as keyword arguments, and an attribute
  that is a keyword of Python, or has a dash, with `**`, as
  `text_field('q', **{'class': 'search', 'data-id': 1})`.
- `<%= %>` escapes what is not markup: a helper returns markup, and
  `Pyjo.String.HTML.html('<b>x</b>')` makes it.
- `Pyjo.Template` used directly, and the handler `epl`, do not escape
  `<%= %>`, as their default is for text that is not markup. A template of
  HTML that renders values from outside without the renderer `ep` takes
  `Pyjo.Template.new(auto_escape=True)`, or it is a hole for cross-site
  scripting.

## Template strings

```python
from Pyjo.String.Template import t
from Pyjoyment.Lite import *


# A template of PyRenderer is a function that returns a template string, which escapes what it interpolates, but markup
@template('hello.html')
def hello(c, name):
    link = c.link_to('Home', '/')
    return t('<p>Hello {name}! {link}</p>')


@get('/hello/:name')
def greet(c):
    c.render('hello', name=c.param('name'))


app.start()
```

- On Python 3.14 and newer, the function returns a t-string,
  `return t'<p>Hello {name}! {link}</p>'`; `t()` takes a string with the
  fields of `str.format` on every Python, with the variables of its caller,
  or keyword arguments.
- A template string is code, which a file of data cannot hold: its function
  is in the script, or in `templates/hello.html.py` as a function `render`.

## Mistakes

- A value of the stash hides a helper of the same name, as `title` or
  `include`, as Python has one namespace where Perl has sigils: call the
  helper of the controller, `c.title()`, or name the value otherwise. Pyjoyment
  says so in the message: `the value "include" of the stash hides the helper`.
- An empty field of a form is a value, as in Mojolicious 9: the filter
  `not_empty` of `v.required('item', 'trim', 'not_empty')` makes it missing.
- A name that is not in the stash is a `NameError` of the template:
  `stash('name')` gives `None` for a value that may be missing.
- A block without `% end` fails: `Missing end of block "if"`.
- A template is found by its name, format and handler: `c.render('add')`
  renders `add.html.ep`, and the format of the route, as `.json`, renders
  `add.json.ep`.
- A page of another template system, as Jinja, renders outside of the
  renderer, without its helpers, layouts and `__DATA__`.

## Documentation

- Rendering: https://pyjoyment.readthedocs.io/en/stable/guides/rendering.html
- Tag helpers: https://pyjoyment.readthedocs.io/en/stable/api/Pyjoyment_Plugin_TagHelpers.html
- Default helpers: https://pyjoyment.readthedocs.io/en/stable/api/Pyjoyment_Plugin_DefaultHelpers.html
- PyRenderer: https://pyjoyment.readthedocs.io/en/stable/api/Pyjoyment_Plugin_PyRenderer.html
