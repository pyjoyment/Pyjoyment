---
name: plugins
description: Write a plugin of Pyjoyment and a distribution of its own, as pyjo generate plugin makes it. Use for a class of Pyjoyment.Plugin whose register adds helpers, nested helpers, hooks, routes and a configuration to an application, for the namespace packages of Pyjoyment.Plugin and Pyjo.Reactor that a distribution adds a module to, and for its test, build and publication.
---

# Plugins and distributions

A plugin is a class of `Pyjoyment.Plugin` whose `register(app, conf)` adds
to an application what an application can add to itself: helpers, hooks,
routes, templates and static files. `app.plugin('Greeting', {...})` loads
`Pyjoyment.Plugin.Greeting` and calls `register` with the configuration. A
plugin that needs a library is a distribution of its own, which adds its
module to the namespace `Pyjoyment.Plugin` without an `__init__.py`, as
`pyjo generate plugin Greeting` makes it.

## A distribution of a plugin

```python
# Pyjoyment/Plugin/Greeting.py
"""
Pyjoyment.Plugin.Greeting - Greetings for Pyjoyment
===================================================
::

    # Pyjoyment.Lite
    plugin('Greeting', {'greeting': 'Hi'})

:mod:`Pyjoyment.Plugin.Greeting` adds the helper ``greet``.
"""

import Pyjoyment.Plugin


__version__ = '0.1.0'


class Pyjoyment_Plugin_Greeting(Pyjoyment.Plugin.object):
    def register(self, app, conf):
        greeting = conf.get('greeting', 'Hello')

        # A helper, which the controllers and the templates call
        app.helper('greet', lambda c, name: f'{greeting} {name}!')

        # A nested helper, which c.greeting.word() calls
        app.helper('greeting.word', lambda c: greeting)

        # A hook of each response
        app.hook('after_dispatch', lambda c: c.res.headers.header('X-Greeting', greeting))

        # A route of the plugin
        app.routes.get('/greeting').to(cb=lambda c: c.render(text=c.greet('plugin')))


object = Pyjoyment_Plugin_Greeting
Greeting = Pyjoyment_Plugin_Greeting
```

```python
# t/basic.py
import Pyjo.Test.Pyjo

from Pyjo.Test import *
from Pyjoyment.Lite import *


plugin('Greeting', {'greeting': 'Hi'})


@get('/')
def index(c):
    c.render(text=f'{c.greet("World")} {c.greeting.word()}')


t = Pyjo.Test.Pyjo.new()
t.get_ok('/').status_is(200).content_is('Hi World! Hi').header_is('X-Greeting', 'Hi')
t.get_ok('/greeting').status_is(200).content_is('Hi plugin!')

done_testing()
```

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "Pyjoyment-Plugin-Greeting"
dynamic = ["version"]
requires-python = ">=3.12"
dependencies = ["Pyjoyment"]

[tool.hatch.version]
path = "Pyjoyment/Plugin/Greeting.py"

# Only the module, without the __init__.py of the packages, which are the ones of Pyjoyment
[tool.hatch.build.targets.wheel]
only-include = ["Pyjoyment/Plugin/Greeting.py"]
```

- `register` runs once, at the start of the application; a value that the
  requests share, as a client of a service, is made there.
- `app.plugin('Greeting')` is `Pyjoyment.Plugin.Greeting`, and a dotted name,
  as `app.plugin('MyApp.Plugin.Greeting')`, a plugin of an application that
  is not a distribution.
- A hook gets the controller, `after_dispatch(c)`, or the next callback of
  the chain first, `around_dispatch(next, c)`, which it calls.
- The types of the helpers of a plugin, for type checkers and editors, are a
  class of its own, `class Helpers:` with `greet = Pyjoyment.Controller.Helper(greet)`
  for each function of a helper and `greeting: GreetingHelpers` for a prefix,
  which the base class of the controllers of an application inherits, as
  `Pyjoyment.Plugin.DefaultHelpers.Helpers` does for the default helpers.
- A reactor on another event loop is a distribution of the namespace
  `Pyjo.Reactor` in the same way, which `PYJO_REACTOR` selects.

## Commands

```sh
pyjo generate plugin Greeting              # the project Pyjoyment-Plugin-Greeting
uv run pyjo-prove -l -r t                  # its tests, with the module of the checkout
uv build                                   # the wheel and the sdist in dist/
uv publish                                 # to PyPI
```

## Mistakes

- An `__init__.py` in `Pyjoyment/` or `Pyjoyment/Plugin/` of a distribution
  replaces the package of Pyjoyment: the wheel has only the module.
- A helper is registered once, in `register`, not in a request; a name that
  another plugin registers too is replaced by the last one.
- A blocking call in a hook blocks the event loop for every request: the work
  that can move to `register` runs once there.
- A plugin without `object = ...` at the end of its module is not found by its
  short name.

## Documentation

- Pyjoyment.Plugin: https://pyjoyment.readthedocs.io/en/latest/api/Pyjoyment_Plugin.html
- Rendering, helper plugins: https://pyjoyment.readthedocs.io/en/latest/guides/rendering.html
- Distributions: https://pyjoyment.readthedocs.io/en/latest/distributions.html
