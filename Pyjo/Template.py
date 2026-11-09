r"""
Pyjo.Template - Python-ish templates
====================================
::

    from Pyjo.Template import Template

    # Use Python modules
    mt = Template()
    print(mt.render('''
    % import time
    <div>
      % now = time.gmtime(0)
      Time: <%= time.strftime('%H:%M:%S', now) %>
    </div>
    '''))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Template

    # Use Python modules
    mt = Pyjo.Template.new()
    print(mt.render('''
    % import time
    <div>
      % now = time.gmtime(0)
      Time: <%= time.strftime('%H:%M:%S', now) %>
    </div>
    '''))

    # Render with arguments
    print(mt.render('''
    % numbers, title = args
    <div>
      <h1><%= title %></h1>
      % for i in numbers {
        Test <%= i %>
      % }
    </div>
    ''', range(1, 14), 'Hello World!'))

    # Render with named variables
    print(Pyjo.Template.new(vars=True).render('''
    <div>
      <h1><%= title %></h1>
      %= 5 + 5
    </div>
    ''', {'title': 'Hello World!'}))

:mod:`Pyjo.Template` is a minimalistic, fast, and very Python-ish template
engine, designed specifically for all those small tasks that come up during
big projects. Like preprocessing a configuration file, generating text from
heredocs and stuff like that.

Syntax
------

::

    <% Python code %>
    <%= Python expression, replaced with result %>
    <%== Python expression, replaced with XML escaped result %>
    <%# Comment, useful for debugging %>
    <%% Replaced with "<%", useful for generating templates %>
    % Python code line, treated as "<% line =%>" (explained later)
    %= Python expression line, treated as "<%= line %>"
    %== Python expression line, treated as "<%== line %>"
    %# Comment line, useful for debugging
    %% Replaced with "%", useful for generating templates

Escaping behavior can be reversed with the :attr:`~Pyjo_Template.auto_escape`
attribute. ::

    <%= Python expression, replaced with XML escaped result %>
    <%== Python expression, replaced with result %>

The default is for text that is not markup, as a configuration file or the
source of a program, where an escaped value would be wrong. A template of HTML
or XML sets :attr:`~Pyjo_Template.auto_escape`, as the renderer ``ep`` of
:mod:`Pyjoyment.Plugin.EPRenderer` does: without it, a value from a request, a
database or any other input of the application is inserted as markup, which
is a hole for cross-site scripting.

Markup, an object with the method ``__html__``, as :mod:`Pyjo.String.HTML`,
is always excluded from automatic escaping, and a value is rendered as an
interpolation of :mod:`Pyjo.String.Template`: ``None`` is nothing, a template
is markup, and a list is rendered item by item. ::

    % from Pyjo.String.HTML import html
    <%= html('<div>excluded!</div>') %>

The indentation of the template does not matter: a code line that ends with
``:`` opens a block, which ``end`` closes, and a line that starts with
``elif``, ``else``, ``except``, ``finally`` or ``case`` closes the block
before it and opens the next one. ``end`` closes the whole ``match`` after its
last ``case``. Braces can open and close a block too, which makes
one-liners easy: ``{`` at the end of a line that starts with a keyword of a
block opens it, and ``}`` at the start of a line closes it, as in ``} else
{``. Any other brace is the one of Python, so a ``dict`` or a ``set`` that
starts at the end of such a line is put in parentheses. ::

    % for name in ['Baerbel', 'Wolfgang']:
      % if name.startswith('B'):
    <b><%= name %></b>
      % else:
    <i><%= name %></i>
      % end
    % end
    <% for i in range(3) { %><%= i %><% } %>

Whitespace characters around tags can be trimmed by adding an additional equal
sign to the end of a tag. ::

    <% for i in range(1, 4) { %>
      <%= 'Trim all whitespace characters around this expression' =%>
    <% } %>

Newline characters can be escaped with a backslash. ::

    This is <%= 1 + 1 %> a\
    single line

And a backslash in front of a newline character can be escaped with another
backslash. ::

    This will <%= 1 + 1 %> result\\
    in multiple\\
    lines

A newline character gets appended automatically to every template, unless the
last character is a backslash. And empty lines at the end of a template are
ignored. ::

    There is <%= 1 + 1 %> no newline at the end here\

You can capture whole template blocks for reuse later with the ``begin`` and
``end`` keywords. Just be aware that both keywords are part of the surrounding
tag and not actual Python code, so there can only be whitespace after
``begin`` and before ``end``. ::

    <% block = begin %>
      <% name = args[0] =%>
      Hello <%= name %>.
    <% end %>
    <%= block('Baerbel') %>
    <%= block('Wolfgang') %>

Python lines can also be indented freely. ::

    % block = begin
      % name = args[0]
      Hello <%= name %>.
    % end
    %= block('Baerbel')
    %= block('Wolfgang')

:mod:`Pyjo.Template` templates get compiled to a Python function, that means
you can access arguments simply via ``args``. ::

    % foo, bar = args
    % x = args[0]
    test 123 <%= foo %>

The compilation of templates to Python code can make debugging a bit tricky,
but :mod:`Pyjo.Template` will return :mod:`Pyjo.Exception` objects that
stringify to error messages with context. ::

    name 'xx' is not defined at template line 4.
    Context:
      1: <html>
      2: </head>
      3: <body>
      4: % i = 2; xx
      5: %= i * 2
      6: </body>
    Traceback (most recent call first):
      File "template", line 4, in "_template"
      File "path/to/Pyjo/Template.py", line 123, in "process"
      File "path/to/myapp.py", line 123, in "<module>"

Debugging
---------

You can set the ``PYJO_TEMPLATE_DEBUG`` environment variable to get some
advanced diagnostics information printed to ``STDERR``. ::

    PYJO_TEMPLATE_DEBUG=1

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojo::Template <https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojo/Template.pm>`_
of Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.File
import Pyjo.String.HTML
import Pyjo.String.Template

from Pyjo.String.Unicode import split

import builtins
import inspect
import keyword
import os
import re
import sys
import traceback
import types

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Self, cast


type Anything = builtins.object

DEBUG = bool(os.environ.get('PYJO_TEMPLATE_DEBUG'))

# The keywords that open a block with a brace, and those that continue the block before
BLOCK_KEYWORDS = {
    'async',
    'class',
    'case',
    'def',
    'elif',
    'else',
    'except',
    'finally',
    'for',
    'if',
    'match',
    'try',
    'while',
    'with',
}
CONTINUE_KEYWORDS = {'case', 'elif', 'else', 'except', 'finally'}

RE_KEYWORD = re.compile(r'\s*(?:\}\s*)?([A-Za-z_]\w*)')
RE_STRING_PREFIX = re.compile(r'(?<![\w])([rRbBfFtTuU]{1,2})\Z')

_SANDBOXES: dict[str, types.ModuleType] = {}


class Pyjo_Template(Pyjo.Base.object):
    """
    :mod:`Pyjo.Template` inherits all methods from :mod:`Pyjo.Base` and
    implements the following new ones.
    """

    def __init__(
        self,
        *,
        append: str = '',
        auto_escape: bool | None = None,
        capture_end: str = 'end',
        capture_start: str = 'begin',
        code: str = '',
        comment_mark: str = '#',
        compiled: Callable[..., Any] | None = None,
        encoding: str | None = 'UTF-8',
        escape: Callable[[Any], str] | None = None,
        escape_mark: str = '=',
        expression_mark: str = '=',
        line_start: str = '%',
        name: str | None = None,
        namespace: str = 'Pyjo.Template.Sandbox',
        prepend: str = '',
        replace_mark: str = '%',
        tag_end: str = '%>',
        tag_start: str = '<%',
        tree: list[list[str]] | None = None,
        trim_mark: str = '=',
        unparsed: str = '',
        vars: bool | None = None,
    ) -> None:
        """::

            mt = Pyjo.Template.new()
            mt = Pyjo.Template.new(auto_escape=True)

        Construct a new :mod:`Pyjo.Template` object.
        """
        self.auto_escape = auto_escape
        """::

            boolean = mt.auto_escape
            mt.auto_escape = boolean

        Activate automatic escaping. A template of HTML or XML
        sets it, so that a value is not inserted as markup. ::

            # "&lt;html&gt;"
            Pyjo.Template.new(auto_escape=True).render("<%= '<html>' %>")
        """

        self.append = append
        """::

            code = mt.append
            mt.append = 'print("Processed template")'

        Append Python code to compiled template, as lines of their own.
        """

        self.capture_end = capture_end
        """::

            end = mt.capture_end
            mt.capture_end = 'end'

        Keyword indicating the end of a capture block, defaults to ``end``. ::

            <% block = begin %>
              Some data!
            <% end %>
        """

        self.capture_start = capture_start
        """::

            start = mt.capture_start
            mt.capture_start = 'begin'

        Keyword indicating the start of a capture block, defaults to
        ``begin``. ::

            <% block = begin %>
              Some data!
            <% end %>
        """

        self.code = code
        """::

            code = mt.code
            mt.code = code

        Python code for template if available.
        """

        self.comment_mark = comment_mark
        """::

            mark = mt.comment_mark
            mt.comment_mark = '#'

        Character indicating the start of a comment, defaults to ``#``. ::

            <%# This is a comment %>
        """

        self.compiled = compiled
        """::

            compiled = mt.compiled
            mt.compiled = compiled

        Compiled template code if available.
        """

        self.encoding = encoding
        """::

            encoding = mt.encoding
            mt.encoding = 'UTF-8'

        Encoding used for template files, defaults to ``UTF-8``.
        """

        # Unlike Mojolicious: the values are escaped as the interpolations of a template, as markup is what has
        # __html__, not every Mojo::ByteStream
        self.escape: Callable[[Any], str] = escape or Pyjo.String.Template.escape
        """::

            cb = mt.escape
            mt.escape = lambda value: ...

        A callback used to escape the results of escaped expressions, defaults
        to :func:`Pyjo.String.Template.escape`. ::

            mt.escape = lambda value: str(value)[::-1]
        """

        self.escape_mark = escape_mark
        """::

            mark = mt.escape_mark
            mt.escape_mark = '='

        Character indicating the start of an escaped expression, defaults to
        ``=``. ::

            <%== foo %>
        """

        self.expression_mark = expression_mark
        """::

            mark = mt.expression_mark
            mt.expression_mark = '='

        Character indicating the start of an expression, defaults to ``=``. ::

            <%= foo %>
        """

        self.line_start = line_start
        """::

            start = mt.line_start
            mt.line_start = '%'

        Character indicating the start of a code line, defaults to ``%``. ::

            % foo = 23
        """

        self._name = name

        # Unlike Mojolicious: a namespace is a module, which Python has as Perl has a package
        self.namespace = namespace
        """::

            namespace = mt.namespace
            mt.namespace = 'main'

        Namespace used to compile templates, defaults to
        ``Pyjo.Template.Sandbox``: the module of the name, if it is loaded, or
        a module of its own. Note that namespaces should only be shared very
        carefully between templates, since the globals of the module will not
        be cleared automatically.
        """

        self.prepend = prepend
        """::

            code = mt.prepend
            mt.prepend = 'this = args[0]'

        Prepend Python code to compiled template, as lines of their own.
        """

        self.replace_mark = replace_mark
        """::

            mark = mt.replace_mark
            mt.replace_mark = '%'

        Character used for escaping the start of a tag or line, defaults to
        ``%``. ::

            <%% foo = 23 %>
        """

        self.tag_start = tag_start
        """::

            start = mt.tag_start
            mt.tag_start = '<%'

        Characters indicating the start of a tag, defaults to ``<%``. ::

            <% foo = 23 %>
        """

        self.tag_end = tag_end
        """::

            end = mt.tag_end
            mt.tag_end = '%>'

        Characters indicating the end of a tag, defaults to ``%>``. ::

            <%= foo %>
        """

        self.tree: list[list[str]] = tree if tree is not None else []
        """::

            tree = mt.tree
            mt.tree = [['text', 'foo'], ['line']]

        Template in parsed form if available. Note that this structure should
        only be used very carefully since it is very dynamic.
        """

        self.trim_mark = trim_mark
        """::

            mark = mt.trim_mark
            mt.trim_mark = '-'

        Character activating automatic whitespace trimming, defaults to
        ``=``. ::

            <%= foo =%>
        """

        self.unparsed = unparsed
        """::

            unparsed = mt.unparsed
            mt.unparsed = '<%= 1 + 1 %>'

        Raw unparsed template if available.
        """

        self.vars = vars
        """::

            boolean = mt.vars
            mt.vars = boolean

        Instead of a list of values, use a dict with named variables to pass
        data to templates. ::

            # "works!"
            Pyjo.Template.new(vars=True).render('<%= test %>!', {'test': 'works'})
        """

        # Not in Mojolicious: the template lines of the lines of the compiled code, and its code objects, which find
        # the frames of the template in a traceback
        self._body: list[int] = []
        self._lines: list[int] = []
        self._codes: set[types.CodeType] = set()
        self._projection: list[str] = []

    @property
    def name(self) -> str:
        """::

            name = mt.name
            mt.name = 'foo.ep'

        Name of template currently being processed, defaults to ``template``.
        """
        if self._name is None:
            self._name = 'template'
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def parse(self, template: str) -> Self:
        """::

            mt = mt.parse('<%= 1 + 1 %>')

        Parse template into :attr:`tree`.
        """

        # Clean start
        tree: list[list[str]] = []
        self.unparsed = template
        self.tree = tree
        self.compiled = None

        tag = self.tag_start
        replace = self.replace_mark
        expr = self.expression_mark
        escp = self.escape_mark
        cpen = self.capture_end
        cmnt = self.comment_mark
        cpst = self.capture_start
        trim = self.trim_mark
        end = self.tag_end
        start = self.line_start

        q = re.escape
        line_re = re.compile(rf'^(\s*){q(start)}(?:({q(replace)})|({q(cmnt)})|({q(expr)}))?(.*)$')
        token_re = re.compile(
            '('
            # Replace
            rf'{q(tag)}(?:{q(replace)}|{q(cmnt)})'
            # Expression
            rf'|{q(tag + expr)}(?:{q(escp)})?(?:\s*{q(cpen)}(?!\w))?'
            # Code
            rf'|{q(tag)}(?:\s*{q(cpen)}(?!\w))?'
            # End
            rf'|(?:(?<!\w){q(cpst)}\s*)?(?:{q(trim)})?{q(end)}'
            ')'
        )
        cpen_re = re.compile(rf'^{q(tag)}(?:{q(expr)})?(?:{q(escp)})?\s*{q(cpen)}(.*)$')
        end_re = re.compile(rf'^(?:({q(cpst)})\s*)?({q(trim)})?{q(end)}$')

        # Split lines
        op = 'text'
        trimming: str | None = None
        capture = False
        for line in split('\n', template):
            line = line or ''

            # Turn Python line into mixed line
            if op == 'text' and (m := line_re.match(line)):
                # Escaped start
                if m[2]:
                    line = f'{m[1]}{start}{m[5]}'

                # Comment
                elif m[3]:
                    line = f'{tag}{m[3]} {trim}{end}'

                # Expression or code
                else:
                    line = f'{m[1]}{tag}{m[4]}{m[5]} {end}' if m[4] else f'{tag}{m[5]} {trim}{end}'

            # Escaped line ending
            if line.endswith('\\\\'):
                line = line[:-2] + '\\\n'
            elif line.endswith('\\'):
                line = line[:-1]
            else:
                line += '\n'

            # Mixed line
            for token in split(token_re, line):
                token = token or ''

                # Capture end
                if m := cpen_re.match(token):
                    token, capture = f'{tag}{m[1]}', True

                # End
                if op != 'text' and (m := end_re.match(token)):
                    # Capture start
                    if m[1]:
                        tree.insert(len(tree) - 1, ['cpst'])

                    # Trim left side
                    if (trimming := m[2]) and len(tree) > 1:
                        _trim(tree)

                    # Hint at end
                    op = 'text'
                    tree.append([op, ''])

                # Code
                elif token == tag:
                    op = 'code'

                # Expression
                elif token == f'{tag}{expr}':
                    op = 'expr'

                # Expression that needs to be escaped
                elif token == f'{tag}{expr}{escp}':
                    op = 'escp'

                # Comment
                elif token == f'{tag}{cmnt}':
                    op = 'cmnt'

                # Text (comments are just ignored)
                elif op != 'cmnt':
                    # Replace
                    if token == f'{tag}{replace}':
                        token = tag

                    # Trim right side (convert whitespace to line noise)
                    if trimming and (m := re.match(r'\s+', token)):
                        tree.append(['code', m[0]])
                        token = token[m.end() :]
                        trimming = None

                    # Token (with optional capture end)
                    if capture:
                        tree.append(['cpen'])
                    tree.append([op, token])
                    capture = False

            # Optimize successive text lines separated by a newline
            if (
                (_at(tree, -4) and tree[-4][0] != 'line')
                or (not _at(tree, -3) or tree[-3][0] != 'text' or not tree[-3][1].endswith('\n'))
                or ((_at(tree, -2) or [''])[0] != 'line' or tree[-1][0] != 'text')
            ):
                tree.append(['line'])
                continue
            tree[-3][1] += tree.pop()[1]

        return self

    def process(self, *args: Anything) -> Any:
        """::

            output = mt.process()
            output = mt.process(*args)
            output = mt.process({'foo': 'bar'})

        Process previously parsed template and return the result, or a
        :mod:`Pyjo.Exception` object if rendering failed. ::

            # Parse and process
            print(Pyjo.Template.new().parse('Hello <%= args[0] %>').process('Bender'))

            # Reuse template (for much better performance)
            mt = Pyjo.Template.new()
            print(mt.render('Hello <%= args[0] %>!', 'Bender'))
            print(mt.process('Fry'))
            print(mt.process('Leela'))
        """

        # Use a local stack trace for compile exceptions
        compiled = self.compiled
        if compiled is None:
            try:
                compiled = self._compile()._eval(args)
            except _CompileError as e:
                exception = Pyjo.Exception.new(e.message).inspect(self.unparsed, '\n'.join(self._projection))
                exception.trace().verbose = True
                return exception
            self.compiled = compiled

        # Unlike Mojolicious: the result is markup, as a template renders its own markup
        try:
            return Pyjo.String.HTML.new(compiled(*args))

        # An exception of Pyjoyment passes through, as Mojo passes on an object
        except Pyjo.Exception.object as e:
            return e

        # Use a real stack trace for normal exceptions
        except Exception as e:
            exception = Pyjo.Exception.new(e)
            caller = inspect.currentframe()
            exception.frames = self._frames(e) + traceback.extract_stack(caller and caller.f_back)[::-1]
            del caller
            exception.inspect(self.unparsed, '\n'.join(self._projection)).verbose = True
            return exception

    def render(self, template: str, *args: Anything) -> Any:
        """::

            output = mt.render('<%= 1 + 1 %>')
            output = mt.render('<%= args[0] + args[1] %>', *args)
            output = mt.render('<%= foo %>', {'foo': 'bar'})

        Render template and return the result, or a :mod:`Pyjo.Exception`
        object if rendering failed. ::

            # Longer version
            output = mt.parse('<%= 1 + 1 %>').process()

            # Render with arguments
            print(Pyjo.Template.new().render('<%= args[0] %>', 'bar'))

            # Render with named variables
            print(Pyjo.Template.new(vars=True).render('<%= foo %>', {'foo': 'bar'}))
        """
        return self.parse(template).process(*args)

    def render_file(self, path: Anything, *args: Anything) -> Any:
        """::

            output = mt.render_file('/tmp/foo.ep')
            output = mt.render_file('/tmp/foo.ep', *args)
            output = mt.render_file('/tmp/bar.ep', {'foo': 'bar'})

        Same as :meth:`render`, but renders a template file.
        """
        if self._name is None:
            self.name = str(path)
        file = Pyjo.File.path(path)
        if (encoding := self.encoding) is None:
            template = file.slurp().decode('latin-1')
        elif (template := file.slurp(encoding)) is None:
            raise Pyjo.Exception.new(f'Template "{path}" has invalid encoding')

        return self.render(template, *args)

    # Unlike Mojolicious: Python needs the indentation of its blocks, so the code is not line for line the template,
    # and the template lines of the code are kept for the tracebacks
    def _compile(self) -> Self:
        compiler = _Compiler(self.auto_escape)
        try:
            compiler.compile(self.tree)
        finally:
            self._projection = compiler.projection
        self._body = [line for _, line in compiler.out]
        self.code = '\n'.join(text for text, _ in compiler.out)
        self.tree = []
        return self

    def _eval(self, args: tuple[Anything, ...]) -> Callable[..., Any]:
        name = self._filename()

        # Variables
        variables: list[str] = []
        if self.vars and len(args) and isinstance(args[0], dict):
            keys = cast(dict[Anything, Anything], args[0]).keys()
            names = [k for k in keys if isinstance(k, str) and k.isidentifier() and not keyword.iskeyword(k)]
            if len(names):
                variables = [f'{k} = args[0].get({k!r})' for k in names] + ['args = args[1:]']

        # Wrap lines, the code of prepend and append as lines of their own, and the output as a list, which the markup
        # of Pyjo.String.HTML does not turn into markup as a string would
        head = [
            'def _wrap(_escape, _str, _html):',
            '    def _template(*args):',
            '        _O = []',
            *(f'        {line}' for line in [*self.prepend.split('\n'), *variables] if line.strip()),
        ]
        tail = [
            *(f'        {line}' for line in self.append.split('\n') if line.strip()),
            "        return ''.join(_O)",
            '    return _template',
        ]
        body = self.code.split('\n') if len(self._body) else []
        self._lines = [1] * len(head) + self._body + [max(self._body, default=1) + 1] * len(tail)
        code = '\n'.join([*head, *body, *tail])

        if DEBUG:
            sys.stderr.write(f'-- Code for {name}\n{code}\n\n')

        try:
            compiled = compile(code, name, 'exec')
        except SyntaxError as e:
            raise _CompileError(f'{e.msg} at {name} line {self._line(e.lineno)}.\n') from None
        namespace: dict[str, Any] = {}
        exec(compiled, _sandbox(self.namespace), namespace)
        self._codes = set(_code_objects(compiled))
        return namespace['_wrap'](self.escape, Pyjo.String.Template.raw, Pyjo.String.HTML.new)

    def _filename(self) -> str:
        return self.name.replace('"', '')

    def _frames(self, e: BaseException) -> list[traceback.FrameSummary]:
        frames: list[traceback.FrameSummary] = []
        lines = _split(self.unparsed)
        for frame, lineno in traceback.walk_tb(e.__traceback__):
            code = frame.f_code
            if code in self._codes:
                num = self._line(lineno)
                line = lines[num - 1] if 0 < num <= len(lines) else ''
                frames.append(traceback.FrameSummary(self._filename(), num, code.co_name, lookup_line=False, line=line))
            else:
                frames.append(traceback.FrameSummary(code.co_filename, lineno, code.co_name))
        return frames[::-1]

    def _line(self, lineno: int | None) -> int:
        if lineno is None or not len(self._lines):
            return 1
        return self._lines[min(max(lineno, 1), len(self._lines)) - 1]


# A block of the compiled code: a capture of begin and end, or a block of Python
@dataclass
class _Block:
    keyword: str
    line: int
    head: tuple[str, str] | None = None
    count: int = 0


class _CompileError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# A logical line of Python code, as the template has it
@dataclass
class _Logical:
    text: str
    start: int
    brace_open: int = -1
    brace_close: int = -1
    colon: bool = False


class _Compiler:
    def __init__(self, escape: bool | None) -> None:
        self.escape = escape
        self.out: list[tuple[str, int]] = []
        self.projection: list[str] = []
        self.blocks: list[_Block] = []
        self.depth = 2
        self.line = 1
        self.closed = False

        # Code lines of the template that are not compiled yet, as lines with their numbers
        self.buffer: list[tuple[int, str]] = []

        # An expression of several lines
        self.expr: list[tuple[int, str]] | None = None
        self.expr_op = ''

        # The statement that continues after the end of a capture
        self.continuation: tuple[str, str] | None = None
        self.captures = 0

    def compile(self, tree: list[list[str]]) -> None:
        capture = multi = False
        i = 0
        while (i := i + 1) <= len(tree) and (following := _at(tree, i)) is not None:
            op, value = (tree[i - 1] + [''])[:2]
            if op == 'line':
                self.line += 1
                if len(self.buffer):
                    self.buffer.append((self.line, ''))
                if self.expr is not None:
                    self.expr.append((self.line, ''))
                continue
            newline = value.endswith('\n')
            if newline:
                value = value[:-1]

            # Capture start before a token that is not code or an expression
            if capture and op not in ('code', 'expr', 'escp', 'cpst'):
                self.begin('code', '')
                capture = False

            # Text (quote and fix line ending), and the code before it unless it is the hint at the end of a tag
            if op == 'text':
                if value or newline:
                    self.flush()
                self.text(value, newline)

            # Multi-line expression
            elif multi and op in ('code', 'expr', 'escp'):
                assert self.expr is not None
                self._project(value)
                self.expr[-1] = (self.expr[-1][0], self.expr[-1][1] + value)

            # Code
            elif op == 'code':
                self._project(value)
                if capture:
                    self.begin('code', value)
                    capture = False
                elif self.continuation is not None:
                    kind, head = self.continuation
                    self.continuation = None
                    if following[0] == 'cpst':
                        self.continuation = (kind, head + value)
                    elif kind == 'code':
                        self.code(head + value)
                    else:
                        self.expression(kind, [(self.line, head + value)])
                else:
                    self.code(value)

            # Capture end
            elif op == 'cpen':
                self.flush()
                self.end()

            # Expression
            if op in ('expr', 'escp') and not multi:
                self.flush()
                self._project(value)
                escaped = op == 'escp' and not self.escape or op == 'expr' and self.escape
                kind = 'escp' if escaped else 'expr'
                if capture:
                    self.begin(kind, value)
                    capture = False
                else:
                    self.expr, self.expr_op = [(self.line, value)], kind
            if op in ('expr', 'escp', 'code') and self.expr is not None:
                # Multi-line
                multi = following[0] != 'text'
                if not multi:
                    self.expression(self.expr_op, self.expr)
                    self.expr = None

            # Capture start
            if op == 'cpst':
                capture = True

        self.flush()
        if len(self.blocks):
            block = self.blocks[-1]
            what = 'begin' if block.keyword == 'begin' else f'block "{block.keyword}"'
            raise _CompileError(f'Missing end of {what} from line {block.line} at template line {self.line}.\n')

    def begin(self, kind: str, value: str) -> None:
        if self.continuation is not None:
            kind, head = self.continuation
            self.continuation = None
        else:
            head = self.flush(final=False)
        self.captures += 1
        name = f'_begin{self.captures}'
        self.emit(f'def {name}(*args):')
        self.open(_Block('begin', self.line, head=(kind, head + value + name)))
        self.emit('_O = []')

    def close(self) -> _Block:
        block = self.blocks.pop()
        if not block.count:
            self.emit('pass', self.depth)
        self.depth -= 1
        return block

    def code(self, value: str) -> None:
        if not value.strip():
            return
        if not len(self.buffer):
            self.buffer.append((self.line, ''))
        first, *rest = value.split('\n')
        num, text = self.buffer[-1]
        self.buffer[-1] = (num, text + first)
        self.buffer.extend((self.line, line) for line in rest)

    def emit(self, text: str, depth: int | None = None, line: int | None = None) -> None:
        self.out.append(
            (' ' * 4 * (self.depth if depth is None else depth) + text, self.line if line is None else line)
        )
        if len(self.blocks):
            self.blocks[-1].count += 1
        self.closed = False

    def end(self) -> None:
        if not len(self.blocks):
            raise _CompileError(f'Unexpected end at template line {self.line}.\n')
        if self.blocks[-1].keyword == 'begin':
            self.emit("return _html(''.join(_O))")
        block = self.close()
        if block.keyword == 'begin':
            self.continuation = block.head
        elif block.keyword == 'case' and len(self.blocks) and self.blocks[-1].keyword == 'match':
            self.close()

    def expression(self, kind: str, parts: list[tuple[int, str]]) -> None:
        call = '_escape' if kind == 'escp' else '_str'
        (first_line, first), *rest = parts
        if not len(rest):
            self.emit(f'_O.append({call}({first.strip()}))', line=first_line)
            return
        self.emit(f'_O.append({call}(({first}', line=first_line)
        for num, part in rest:
            self.out.append((part, num))
        self.out.append((')))', rest[-1][0]))

    def flush(self, final: bool = True) -> str:
        if not len(self.buffer):
            return ''
        logicals, tail = _scan('\n'.join(text for _, text in self.buffer), final)
        starts = [num for num, _ in self.buffer]
        self.buffer = []
        for logical in logicals:
            self.statement(logical, starts)
        return tail

    def open(self, block: _Block) -> None:
        self.blocks.append(block)
        self.depth += 1

    def statement(self, logical: _Logical, starts: list[int]) -> None:
        text, line = logical.text, starts[logical.start]

        # Brace that opens a block
        brace = logical.brace_open >= 0
        if brace:
            text = text[: logical.brace_open].rstrip() + ':' + text[logical.brace_open + 1 :]

        # Brace that closes a block
        if logical.brace_close >= 0:
            if not len(self.blocks) or self.blocks[-1].keyword == 'begin':
                raise _CompileError(f'Unexpected "}}" at template line {line}.\n')
            self.close()
            self.closed = True
            text = text[logical.brace_close + 1 :]
            if not text.strip() or text.lstrip().startswith('#'):
                return

        # Keyword that continues the block before
        word = m[1] if (m := RE_KEYWORD.match(text)) else ''
        if word in CONTINUE_KEYWORDS and not self.closed and len(self.blocks) and self.blocks[-1].keyword != 'begin':
            if not (word == 'case' and self.blocks[-1].keyword == 'match'):
                self.close()

        first, *rest = text.lstrip().split('\n')
        self.emit(first if len(rest) else first.rstrip(), line=line)
        for i, continued in enumerate(rest, 1):
            self.out.append((continued, starts[logical.start + i]))
        if brace or logical.colon:
            self.open(_Block(word, line))

    def text(self, value: str, newline: bool) -> None:
        pieces = value.split('\n')
        if newline:
            pieces[-1] += '\n'
        pieces = [p + '\n' for p in pieces[:-1]] + [pieces[-1]]
        if len(pieces) == 1:
            if pieces[0]:
                self.emit(f'_O.append({pieces[0]!r})')
                self._project(f'_O.append({pieces[0]!r})')
            return
        self.emit(f'_O.append({pieces[0]!r}')
        self._project(f'_O.append({pieces[0]!r}')
        for piece in pieces[1:-1]:
            self.line += 1
            self.out.append((repr(piece), self.line))
            self._project(repr(piece))
        self.line += 1
        self.out.append((f'{pieces[-1]!r})', self.line))
        self._project(f'{pieces[-1]!r})')

    def _project(self, fragment: str) -> None:
        while len(self.projection) < self.line:
            self.projection.append('')
        self.projection[self.line - 1] += fragment


def _at(tree: list[list[str]], i: int) -> list[str] | None:
    return tree[i] if -len(tree) <= i < len(tree) else None


def _code_objects(code: types.CodeType) -> Iterator[types.CodeType]:
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from _code_objects(const)


def _sandbox(name: str) -> dict[str, Any]:
    if (module := sys.modules.get(name)) is None and (module := _SANDBOXES.get(name)) is None:
        module = _SANDBOXES[name] = types.ModuleType(name)

        # No spec, as the module has no source that linecache could read, which warns of a spec without a loader
        del module.__spec__
    return module.__dict__


# Logical lines of Python code, the brace and the colon that open a block, the brace that closes one, and the end of
# the code that is not a complete logical line yet
def _scan(code: str, final: bool) -> tuple[list[_Logical], str]:
    logicals: list[_Logical] = []
    i = start = line = first_line = 0
    n = len(code)
    depth = 0
    brace = close = last = -1
    first = -1

    def finish(end: int) -> None:
        nonlocal start, depth, brace, close, last, first, first_line
        text = code[start:end]
        if text.strip():
            lead = len(text) - len(text.lstrip())
            begin = start + lead
            logicals.append(
                _Logical(
                    text[lead:],
                    first_line + text.count('\n', 0, lead),
                    brace - begin if brace >= 0 and depth == 1 else -1,
                    close - begin if close >= 0 else -1,
                    depth == 0 and last >= 0 and code[last] == ':',
                )
            )
        start = end + 1
        depth = 0
        brace = close = last = first = -1
        first_line = line + 1

    while i < n:
        c = code[i]
        if c == '#':
            while i < n and code[i] != '\n':
                i += 1
            continue
        if c == '\\' and i + 1 < n and code[i + 1] == '\n':
            i += 2
            line += 1
            continue
        if c in '"\'':
            m = RE_STRING_PREFIX.search(code, start, i)
            end = _skip_string(code, i, m[1] if m else '')
            if end < 0:
                break
            line += code.count('\n', i, end)
            i = end
            last = i - 1
            if first < 0:
                first = i
            continue
        if c == '\n':
            if depth == 0 or (depth == 1 and brace >= 0 and last == brace and _block_keyword(code[start:i])):
                finish(i)
            line += 1
            i += 1
            continue
        if c in ' \t\r\f':
            i += 1
            continue
        if c in '([{':
            if c == '{' and depth == 0:
                brace = i
            depth += 1
        elif c in ')]}':
            if depth == 0 and c == '}' and first < 0 and close < 0:
                close = i
                i += 1
                continue
            depth = max(depth - 1, 0)
            if depth == 0:
                brace = -1
        last = i
        if first < 0:
            first = i
        i += 1

    if final and start < n:
        if not (depth == 1 and brace >= 0 and last == brace and _block_keyword(code[start:n])):
            brace = -1
        finish(n)
    return logicals, code[start:] if start < n else ''


def _block_keyword(text: str) -> bool:
    return bool(m := RE_KEYWORD.match(text)) and m[1] in BLOCK_KEYWORDS


# The end of a string literal, or -1 for a string that is not terminated
def _skip_string(code: str, i: int, prefix: str) -> int:
    quote = code[i : i + 3] if code[i : i + 3] in ('"""', "'''") else code[i]
    formatted = any(p in prefix.lower() for p in 'ft')
    i += len(quote)
    n = len(code)
    while i < n:
        if code.startswith(quote, i):
            return i + len(quote)
        c = code[i]
        if c == '\\':
            i += 2
            continue
        if c == '\n' and len(quote) == 1:
            return -1
        if formatted and c == '{':
            if code.startswith('{{', i):
                i += 2
                continue
            if (i := _skip_field(code, i + 1)) < 0:
                return -1
            continue
        i += 1
    return -1


# The end of a replacement field of an f-string or a t-string
def _skip_field(code: str, i: int) -> int:
    depth = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in '"\'':
            m = RE_STRING_PREFIX.search(code, 0, i)
            if (i := _skip_string(code, i, m[1] if m else '')) < 0:
                return -1
            continue
        if c in '([{':
            depth += 1
        elif c in ')]}':
            if depth == 0 and c == '}':
                return i + 1
            depth -= 1
        i += 1
    return -1


def _split(source: str) -> list[str]:
    lines = source.split('\n')
    while len(lines) and lines[-1] == '':
        lines.pop()
    return lines


def _trim(tree: list[list[str]]) -> None:

    # Skip captures
    i = -3 if tree[-2][0] in ('cpst', 'cpen') else -2

    # Only trim text
    if (node := _at(tree, i)) is None or node[0] != 'text':
        return

    # Convert whitespace text to line noise
    if m := re.search(r'\s+\Z', node[1]):
        node[1] = node[1][: m.start()]
        tree.insert(len(tree) + i, ['code', m[0]])


new = Pyjo_Template.new
object = Pyjo_Template
Template = Pyjo_Template
