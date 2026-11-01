# pyright: reportUnnecessaryTypeIgnoreComment=true

import Pyjo.Log
import Pyjo.String.HTML
import Pyjo.Test.Pyjo
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent
import Pyjoyment
import Pyjoyment.Controller
import Pyjoyment.Plugin.DefaultHelpers
import Pyjoyment.Plugin.TagHelpers
import Pyjoyment.Routes.Route

from Pyjo.Test import *
from Pyjoyment.Lite import *

import functools
import inspect
import re

from typing import TYPE_CHECKING, Any, assert_type, cast


# Not in Mojolicious: the types of the helpers for type checkers, as Perl has none, which pyright checks in this file
# in strict mode, with the errors of the calls that are wrong


class Users:
    def __init__(self, names: list[str]) -> None:
        self.names = names

    def count(self) -> int:
        return len(self.names)


def users(c: Pyjoyment.Controller.object) -> Users:
    return Users(['sri', 'tom'])


class Controller(Pyjoyment.Controller.object):
    users = Pyjoyment.Controller.Helper(users)


class Unregistered(Pyjoyment.Controller.object):
    unregistered = Pyjoyment.Controller.Helper(users)


helper('users', users)
app.controller_class = Controller


@get('/users')
def index(c: Controller) -> None:
    c.render(text=str(c.users().count()))


# The function of each helper that a class of the types of a plugin declares, with the prefixes of nested helpers
def declared(cls: type, prefix: str = '') -> dict[str, Any]:
    found: dict[str, Any] = {}
    for name, value in vars(cls).items():
        if isinstance(value, Pyjoyment.Controller.Helper):
            found[prefix + name] = value.cb
    for name, nested in inspect.get_annotations(cls).items():
        found.update(declared(nested, f'{prefix}{name}.'))
    return found


# The helpers that a plugin registers
def registered(plugin: Any) -> dict[str, Any]:
    other = Pyjoyment.new()
    other.renderer.helpers.clear()
    plugin.new().register(other)
    return dict(other.renderer.helpers)


# What tells the same function, as a closure or a partial function is made again for each declaration
def key(cb: Any) -> Any:
    if isinstance(cb, functools.partial):
        partial = cast('functools.partial[Any]', cb)
        return key(partial.func), partial.args, partial.keywords
    if inspect.isfunction(cb):
        return cb.__code__, [cell.cell_contents for cell in cb.__closure__ or ()]
    return cb


t = Pyjo.Test.Pyjo.new()

with subtest('Types of the default helpers'):
    for plugin, helpers in (
        (Pyjoyment.Plugin.DefaultHelpers, Pyjoyment.Plugin.DefaultHelpers.Helpers),
        (Pyjoyment.Plugin.TagHelpers, Pyjoyment.Plugin.TagHelpers.Helpers),
    ):
        types, functions = declared(helpers), registered(plugin)
        is_deeply_ok(sorted(types), sorted(functions), f'{plugin.__name__}: types of all helpers')
        is_deeply_ok(
            [name for name in functions if name in types and key(types[name]) != key(functions[name])],
            [],
            f'{plugin.__name__}: types of the functions of the helpers',
        )

with subtest('Types of the helpers of a controller'):
    tx = Pyjo.Transaction.HTTP.new()
    c = Controller.new(app=app, tx=tx)
    assert_type(c.ua(), Pyjo.UserAgent.object)
    is_ok(c.ua(), app.ua, 'right user agent')
    assert_type(c.log(), Pyjo.Log.object)
    assert_type(c.text_field('name'), Pyjo.String.HTML.object)
    is_ok(str(c.text_field('name')), '<input name="name" type="text">', 'right field')
    assert_type(c.timing.elapsed('none'), float | None)
    is_ok(c.timing.elapsed('none'), None, 'nested helper')
    assert_type(c.helpers.timing.elapsed('none'), float | None)
    assert_type(c.helpers.dumper([]), str)

    # A helper without a type
    base = Pyjoyment.Controller.new(app=app, tx=tx)
    assert_type(base.users(), Any)
    is_ok(base.users().count(), 2, 'helper without a type')
    assert_type(c.helpers.users(), Any)

    # The attribute of the controller, not the helper of the same name
    assert_type(c.app, Pyjoyment.object)

with subtest('Types of the helpers of an application'):
    assert_type(app.dumper([]), str)
    is_ok(app.dumper([]), '[]\n', 'helper of the application')

    # The attribute of the application, not the helper of the same name
    assert_type(app.ua, Pyjo.UserAgent.object)

with subtest('Types of the helpers of an application, declared by the application'):
    t.get_ok('/users').status_is(200).content_is('2')
    tx = Pyjo.Transaction.HTTP.new()
    c = Controller.new(app=app, tx=tx)
    assert_type(c.users(), Users)
    is_ok(c.users().count(), 2, 'helper of the application')

    # The helper of the renderer, which an application or a plugin can replace
    def nobody(c: Pyjoyment.Controller.object) -> Users:
        return Users([])

    helper('users', nobody)
    is_ok(c.users().count(), 0, 'replaced helper')
    helper('users', users)

    # Not an action
    ok(not callable(Controller.users), 'not callable on the class')

with subtest('Type of a helper that is not registered'):
    c = Unregistered.new(app=app)
    line = inspect.currentframe().f_lineno + 2  # pyright: ignore[reportOptionalMemberAccess]
    try:
        c.unregistered()
    except AttributeError as e:
        like_ok(
            str(e), rf'Can\'t locate object method "unregistered" .* at {re.escape(__file__)} line {line}\.', 'caller'
        )

with subtest('Types of the functions of Pyjoyment.Lite'):
    route = get('/types')
    assert_type(route, Pyjoyment.Routes.Route.object)
    is_ok(route.to_str(), '/types', 'right route')

# The calls that are wrong, which only pyright checks
if TYPE_CHECKING:
    tx = Pyjo.Transaction.HTTP.new()
    c = Controller.new(app=app, tx=tx)

    # A helper without the call
    c.ua.get_p('/')  # pyright: ignore[reportFunctionMemberAccess]

    # The arguments of a helper
    c.ua(1)  # pyright: ignore[reportCallIssue]
    c.timing.elapsed(1)  # pyright: ignore[reportArgumentType]
    c.users('sri')  # pyright: ignore[reportCallIssue]
    app.dumper(nothing=True)  # pyright: ignore[reportCallIssue]

    # A nested helper that is not declared
    c.timing.unknown()  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

done_testing()
