"""
Pyjoyment.Command.Author.inflate - Inflate command
==================================================
::

    Usage: APPLICATION inflate [OPTIONS]

      ./myapp.py inflate

    Options:
      -h, --help                Show this summary of available options
          --home <path>         Path to home directory of your application,
                                defaults to the value of PYJO_HOME or
                                auto-detection
          --log-format <name>   Format of log messages, "text", "plain" without
                                time and process, or "json", defaults to the
                                value of PYJO_LOG_FORMAT or "text"
      -m, --mode <name>         Operating mode for your application, defaults to
                                the value of PYJO_MODE or "development"

:mod:`Pyjoyment.Command.Author.inflate` turns templates and static files
embedded in the ``DATA`` sections of your application into real files.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::Author::inflate
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/Author/inflate.pm>`_ of Mojolicious 9.49.

Classes
-------
"""

import Pyjoyment.Command

from Pyjo.Loader import data_section, file_is_binary
from Pyjo.Util import encode, extract_usage

import re

from typing import Any


class Pyjoyment_Command_Author_inflate(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.Author.inflate` inherits all attributes and methods
    from :mod:`Pyjoyment.Command` and implements the following new ones.
    """

    description = 'Inflate embedded files to real files'
    """::

        description = inflate.description
        inflate.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = inflate.usage
        inflate.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> None:
        """::

            inflate.run(*sys.argv[1:])

        Run this command.
        """
        # Find all embedded files
        all: dict[str, bytes] = {}
        app: Any = self.app
        for cls in [*app.renderer.classes, *app.static.classes]:
            files: Any = data_section(cls) or {}
            for name in files:
                data = data_section(cls, name)
                if not file_is_binary(cls, name):
                    data = encode('UTF-8', str(data))
                all[name] = data if isinstance(data, bytes) else b''

        # Turn them into real files
        for name in (name for name in all if re.search(r'\.\w+$', name)):
            prefix = 'templates' if re.search(r'\.\w+\.\w+$', name) else 'public'
            self.write_file(self.rel_file(f'{prefix}/{name}'), all[name])


new = Pyjoyment_Command_Author_inflate.new
object = Pyjoyment_Command_Author_inflate
