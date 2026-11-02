"""
Pyjoyment.Command - Command base class
======================================
::

    # Lowercase command name, in the module Pyjoyment.Command.mycommand
    from Pyjoyment.Command import Command

    from Pyjo.Util import extract_usage


    class Pyjoyment_Command_mycommand(Command):
        # Short description
        description = 'My first Pyjoyment command'

        # Usage message from the synopsis of the docstring of the module
        usage = extract_usage()

        def run(self, *args):
            # Magic here! :)
            ...


    object = Pyjoyment_Command_mycommand

    # Or import the module, as in Google Python Style Guide

    # Lowercase command name, in the module Pyjoyment.Command.mycommand
    import Pyjoyment.Command

    from Pyjo.Util import extract_usage


    class Pyjoyment_Command_mycommand(Pyjoyment.Command.object):
        # Short description
        description = 'My first Pyjoyment command'

        # Usage message from the synopsis of the docstring of the module
        usage = extract_usage()

        def run(self, *args):
            # Magic here! :)
            ...


    object = Pyjoyment_Command_mycommand

    # The synopsis in the docstring of the module
    \"\"\"
    Pyjoyment.Command.mycommand - My command
    ========================================
    ::

        Usage: APPLICATION mycommand [OPTIONS]

        Options:
          -s, --something   Does something
    \"\"\"

:mod:`Pyjoyment.Command` is an abstract base class for :mod:`Pyjoyment`
commands.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command.pm>`_
of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Base
import Pyjo.File
import Pyjo.Loader
import Pyjo.Server
import Pyjo.Template
import Pyjo.Util

import os
import sys
import weakref

from pkgutil import extend_path
from typing import TYPE_CHECKING, Any, Self


if TYPE_CHECKING:
    import Pyjoyment


class Pyjoyment_Command(Pyjo.Base.object):
    """
    :mod:`Pyjoyment.Command` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    description: str = 'No description'
    """::

        description = command.description
        command.description = 'Foo'

    Short description of command, used for the command list.
    """

    quiet: bool | None = None
    """::

        boolean = command.quiet
        command.quiet = boolean

    Limited command output.
    """

    usage: str = 'Usage: APPLICATION\n'
    """::

        usage = command.usage
        command.usage = 'Foo'

    Usage information for command, used for the help screen.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._app: weakref.ref[Pyjoyment.object] | None = None
        self._app_ref: Pyjoyment.object | None = None
        self.template: dict[str, Any] = {'vars': True}
        """::

            template = command.template
            command.template = {'vars': True}

        Attribute values passed to :mod:`Pyjo.Template` objects used to
        render templates with :meth:`render_data`, defaults to activating
        ``vars``.
        """
        for name, value in kwargs.items():
            setattr(self, name, value)

    @property
    def app(self) -> 'Pyjoyment.object':
        """::

            app = command.app
            command.app = Pyjoyment.new()

        Application for command, defaults to a :mod:`Pyjoyment.HelloWorld`
        object. Note that this attribute is weakened. ::

            # Introspect
            for path in command.app.renderer.paths:
                print(f'Template path: {path}')
        """
        if self._app is not None:
            if (app := self._app()) is None:
                raise ReferenceError('weakly-referenced object no longer exists')
            return app
        if self._app_ref is None:
            self._app_ref = Pyjo.Server.new().build_app('Pyjoyment.HelloWorld')  # pyright: ignore[reportAttributeAccessIssue]
        return self._app_ref  # pyright: ignore[reportReturnType]

    @app.setter
    def app(self, value: 'Pyjoyment.object') -> None:
        self._app = weakref.ref(value)

    def chmod_file(self, path: str | os.PathLike[str], mode: int) -> Self:
        """::

            command = command.chmod_file('/home/sri/foo.txt', 0o644)

        Change mode of a file.
        """
        Pyjo.File.path(path).chmod(mode)
        return self._loud(f'  [chmod] {path} {mode:o}')

    def chmod_rel_file(self, path: str, mode: int) -> Self:
        """::

            command = command.chmod_rel_file('foo/foo.txt', 0o644)

        Portably change mode of a file relative to the current working
        directory.
        """
        return self.chmod_file(self.rel_file(path), mode)

    def create_dir(self, path: str | os.PathLike[str]) -> Self:
        """::

            command = command.create_dir('/home/sri/foo/bar')

        Create a directory if it does not exist already.
        """
        if os.path.isdir(path):
            return self._loud(f'  [exist] {path}')
        Pyjo.File.path(path).make_path()
        return self._loud(f'  [mkdir] {path}')

    def create_rel_dir(self, path: str) -> Self:
        """::

            command = command.create_rel_dir('foo/bar/baz')

        Portably create a directory relative to the current working directory
        if it does not exist already.
        """
        return self.create_dir(self.rel_file(path))

    def extract_usage(self) -> str:
        """::

            usage = command.extract_usage()

        Extract usage message from the synopsis of the docstring of the file
        this method was called from with :func:`Pyjo.Util.extract_usage`.
        """
        return Pyjo.Util.extract_usage(sys._getframe(1).f_code.co_filename)  # pyright: ignore[reportPrivateUsage]

    def help(self, *args: str) -> None:
        """::

            command.help()

        Print usage information for command.
        """
        print(self.usage, end='')

    def rel_file(self, path: str) -> Pyjo.File.object:
        """::

            path = command.rel_file('foo/bar.txt')

        Return a :mod:`Pyjo.File` object relative to the current working
        directory.
        """
        return Pyjo.File.path().child(*path.split('/'))

    def render_data(self, name: str, *args: Any) -> str:
        """::

            data = command.render_data('foo_bar')
            data = command.render_data('foo_bar', *args)
            data = command.render_data('foo_bar', {'foo': 'bar'})

        Render a template from the ``DATA`` section of the module of the
        command with :mod:`Pyjo.Loader` and :mod:`Pyjo.Template`. The template
        can be configured with :attr:`template`.
        """
        template = Pyjo.Template.new(**self.template)
        template.name = f'template {name} from DATA section'
        output = template.render(str(Pyjo.Loader.data_section(type(self), name)), *args)
        if isinstance(output, Exception):
            raise output
        return str(output)

    def render_to_file(self, data: str, path: str | os.PathLike[str], *args: Any) -> Self:
        """::

            command = command.render_to_file('foo_bar', '/home/sri/foo.txt')
            command = command.render_to_file('foo_bar', '/home/sri/foo.txt', *args)
            command = command.render_to_file('foo_bar', '/home/sri/foo.txt', {'foo': 'bar'})

        Render a template with :meth:`render_data` to a file if it does not
        exist already, and create the directory if necessary.
        """
        return self.write_file(path, self.render_data(data, *args))

    def render_to_rel_file(self, data: str, path: str, *args: Any) -> Self:
        """::

            command = command.render_to_rel_file('foo_bar', 'foo/bar.txt')
            command = command.render_to_rel_file('foo_bar', 'foo/bar.txt', *args)
            command = command.render_to_rel_file('foo_bar', 'foo/bar.txt', {'foo': 'bar'})

        Portably render a template with :meth:`render_data` to a file relative
        to the current working directory if it does not exist already, and
        create the directory if necessary.
        """
        return self.render_to_file(data, self.rel_file(path), *args)

    def run(self, *args: str) -> Any:
        """::

            command.run()
            command.run(*sys.argv[1:])

        Run command. Meant to be overloaded in a subclass.
        """
        raise NotImplementedError('Method "run" not implemented by subclass')

    def write_file(self, path: str | os.PathLike[str], data: str | bytes) -> Self:
        """::

            command = command.write_file('/home/sri/foo.txt', 'Hello World!')

        Write text to a file if it does not exist already, and create the
        directory if necessary.
        """
        if os.path.isfile(path):
            return self._loud(f'  [exist] {path}')
        self.create_dir(Pyjo.File.path(path).dirname())
        Pyjo.File.path(path).spew(data)
        return self._loud(f'  [write] {path}')

    def write_rel_file(self, path: str, data: str | bytes) -> Self:
        """::

            command = command.write_rel_file('foo/bar.txt', 'Hello World!')

        Portably write text to a file relative to the current working
        directory if it does not exist already, and create the directory if
        necessary.
        """
        return self.write_file(self.rel_file(path), data)

    def _loud(self, msg: str) -> Self:
        if not self.quiet:
            # Unlike Mojolicious: flushed, as the standard output of a pipe, as the log of CI or of tee, is buffered in
            # blocks, so a command that runs long would show its progress at its end only
            print(msg, flush=True)
        return self


# Not in Mojolicious: a namespace that other distributions can add commands to
__path__ = extend_path(__path__, __name__)

new = Pyjoyment_Command.new
object = Pyjoyment_Command
Command = Pyjoyment_Command
