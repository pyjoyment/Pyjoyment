---
name: app
description: Build a full Pyjoyment application, a package with a class of the application, controllers as classes, a model, templates and static files in their directories, a configuration file and tests, as pyjo generate app makes it. Use for its structure, the routes of startup to controller#action, nested routes with under, helpers that give a model, plugins and configuration, and the growth of a script of Pyjoyment.Lite into it.
---

# A full application

A script of `Pyjoyment.Lite` grows into a package: a class of the
application, whose `startup` configures it and its routes, controllers as
classes whose methods are the actions, and the templates, the static files,
the configuration and the tests in directories next to the package.
`pyjo generate app MyApp` makes such a project:

```text
my_app/
  pyproject.toml
  my_app.yml                 the configuration of YAMLConfig
  MyApp/__init__.py          the class of the application
  MyApp/__main__.py          python -m MyApp, the commands
  MyApp/Controller/*.py      the controllers
  MyApp/Model/*.py           the model, plain Python
  templates/*/*.html.ep      a template for each controller and action
  templates/layouts/         the layouts
  public/                    the static files
  t/*.py                     the test scripts
```

## The application

```python
# MyApp/__init__.py
import Pyjoyment

from MyApp.Model.Notes import Notes


class MyApp(Pyjoyment.object):
    # Runs once, when the application starts
    def startup(self):
        config = self.plugin('YAMLConfig')
        self.secrets = config['secrets']

        # The model, which every controller reaches with the helper notes()
        notes = Notes()
        self.helper('notes', lambda c: notes)

        r = self.routes
        r.get('/').to('notes#index')
        r.get('/notes/<id:num>', 'note').to('notes#show')

        # The routes of the API, only for a request that the action check of the controller Auth lets in
        api = r.under('/api').to('auth#check')
        api.post('/notes').to('notes#create')


new = MyApp.new
object = MyApp
```

```python
# MyApp/__main__.py
import Pyjoyment.Commands


Pyjoyment.Commands.start_app('MyApp')
```

```python
# MyApp/Model/Notes.py
class Notes:
    def __init__(self):
        self.notes = {1: 'Buy milk'}

    def all(self):
        return self.notes

    def get(self, id):
        return self.notes.get(id)

    def add(self, text):
        id = max(self.notes, default=0) + 1
        self.notes[id] = text
        return id
```

```python
# MyApp/Controller/Notes.py
import Pyjoyment.Controller


class MyApp_Controller_Notes(Pyjoyment.Controller.object):
    # Renders templates/notes/index.html.ep, of the controller and the action
    def index(self):
        self.render(notes=self.notes().all())

    def show(self):
        id = int(self.param('id'))
        if (note := self.notes().get(id)) is None:
            return self.reply.not_found()
        self.render(id=id, note=note)

    def create(self):
        id = self.notes().add(self.req.json('/text'))
        self.res.headers.location = self.url_for('note', id=id).to_abs()
        self.render(json={'id': id}, status=201)


object = MyApp_Controller_Notes
```

```python
# MyApp/Controller/Auth.py
import Pyjoyment.Controller

from Pyjo.Util import secure_compare


class MyApp_Controller_Auth(Pyjoyment.Controller.object):
    # An action of under lets the routes after it run with a true value, and renders the response otherwise
    def check(self):
        if secure_compare(self.req.headers.header('X-Token') or '', self.config('token')):
            return True
        self.render(json={'error': 'unauthorized'}, status=401)
        return None


object = MyApp_Controller_Auth
```

```html
%# templates/notes/index.html.ep
% layout('default')
% title('Notes')
<ul>
  % for id, text in notes.items():
    <li><%= link_to(text, 'note', {'id': id}) %></li>
  % end
</ul>
```

```html
%# templates/notes/show.html.ep
% layout('default')
% title(note)
<p><%= note %></p>
```

```html
%# templates/layouts/default.html.ep
<!DOCTYPE html>
<html>
  <head><title><%= c.title() %></title></head>
  <body><%= content() %></body>
</html>
```

```yaml
# my_app.yml
secrets:
  - Change this secret
token: Change this token
```

```python
# t/notes.py
import Pyjo.Test.Pyjo

from Pyjo.Test import *


t = Pyjo.Test.Pyjo.new('MyApp')

with subtest('Pages'):
    t.get_ok('/').status_is(200).text_is('title', 'Notes').text_is('li a[href="/notes/1"]', 'Buy milk')
    t.get_ok('/notes/1').status_is(200).text_is('p', 'Buy milk')
    t.get_ok('/notes/9').status_is(404)

with subtest('API'):
    t.post_ok('/api/notes', json={'text': 'Bake bread'}).status_is(401)
    t.post_ok('/api/notes', {'X-Token': 'Change this token'}, json={'text': 'Bake bread'}).status_is(201)
    t.json_is({'id': 2}).header_like('Location', r'/notes/2$')
    t.get_ok('/notes/2').status_is(200).text_is('p', 'Bake bread')

done_testing()
```

- `r.get(...).to('notes#show')` dispatches to the method `show` of
  `MyApp.Controller.Notes`, whose class is the one that the module names
  `object`; an action without a method renders its template.
- A controller is a `Pyjoyment.Controller`: `self.param`, `self.render`,
  `self.req`, `self.res` and the helpers, as `self.notes()`, as `c.` of Lite.
- Type checkers and editors know the helpers of Pyjoyment, as `self.ua()` or
  `self.reply.not_found()`; a helper of the application is `Any` to them until
  a base class of its controllers declares it with the function of the
  helper, `notes = Pyjoyment.Controller.Helper(notes)`, which `startup`
  registers by its name.
- `self.plugin('YAMLConfig')` reads `my_app.yml`, and `my_app.production.yml`
  in the mode `production`; `TOMLConfig` and `JSONConfig` read the others.
- A name of a route is the string after its pattern, as `'note'`, which
  `url_for` and `link_to` take with the values of its placeholders.

## Commands

```sh
uvx --from Pyjoyment pyjo generate app MyApp  # a new project in my_app, which depends on Pyjoyment of PyPI
uv run python -m MyApp daemon                 # http://127.0.0.1:3000
uv run python -m MyApp routes                 # the routes, their names and controllers
uv run pyjo-prove -l -r t                     # the tests
python myapp.py inflate                       # a script of Lite: its templates of __DATA__ into templates/
```

## Mistakes

- A controller is found by its module, `MyApp/Controller/Notes.py` for
  `notes#...`; a missing one fails with `Controller "MyApp.Controller.Notes"
  does not exist`, and a missing method renders the template or nothing.
- A value of a template cannot have a name that `render` reserves, as `text`,
  `json`, `data`, `template`, `format` or `status`: `self.render(text=note)`
  renders the text itself, without the template.
- The helpers are registered in `startup`, not in a controller, and a value
  shared by the requests, as a model or a pool of connections, is made there.
- A model that blocks, as a database driver without asyncio, blocks every
  connection of the process: a library of asyncio awaited in `async def`
  actions, or the workers of `prefork`.
- `self.secrets` is set before the first session, from the configuration, not
  from the code that is committed.
- `print` in an action, a hook or a command goes to the standard output,
  which a pipe, as the one of a container or of CI, buffers in blocks, and has
  no time and no level: `c.log().info(...)` in an action, with the request
  id, and `self.app.log.info(...)` in a command or `startup`, write to the
  standard error at once, as JSON with `PYJO_LOG_FORMAT=json`. The standard
  output is for what a command gives as its result, as JSON for a program.

- A command of the application, a class of `Pyjoyment.Command` in
  `MyApp/Command/sync.py`, is found through
  `self.commands.namespaces.append('MyApp.Command')` of `startup`, or
  `app.commands.namespaces` of a script of Lite, whose package has another
  name than the script, as macOS takes `Sync/` and `sync.py` for one.
- The dict of `getopt` takes the target of an option, a list, a dict or a
  callback, not its default: `Pyjo.GetOpt.new().option('c|concurrency=i',
  default=4)` has one. `rel_file` of a command is relative to the current
  directory, as in Mojolicious; a file of the application is
  `self.app.home.child(...)`. `_loud` is private: a command reports with
  `self.app.log`.

## Documentation

- Growing: https://pyjoyment.readthedocs.io/en/latest/guides/growing.html
- Routing: https://pyjoyment.readthedocs.io/en/latest/guides/routing.html
- Pyjoyment: https://pyjoyment.readthedocs.io/en/latest/api/Pyjoyment.html
- Pyjoyment.Controller: https://pyjoyment.readthedocs.io/en/latest/api/Pyjoyment_Controller.html
