import Pyjo.Exception
import Pyjo.String.HTML
import Pyjo.Template

from Pyjo.Test import *

import os
import re
import sys
import traceback
import types


class MyTemplateException:
    @staticmethod
    def exception():
        raise Exception('ohoh')


# A module that a template imports from
exporter = types.ModuleType('MyTemplateExporter')
exporter.foo = lambda: 'works!'
sys.modules['MyTemplateExporter'] = exporter

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')

with subtest('Empty template'):
    mt = Pyjo.Template.new()
    output = mt.render('')
    is_ok(output, '', 'empty string')

with subtest('Named template'):
    mt = Pyjo.Template.new()
    mt.name = 'foo/bar.ep'
    output = mt.render('% import inspect\n<%= inspect.currentframe().f_code.co_filename %>')
    is_ok(output, 'foo/bar.ep\n', 'template name')

with subtest('Consistent scalar context'):
    # Unlike Mojolicious: a list is rendered item by item, not as its length in the scalar context of Perl
    mt.prepend = 'foo = [3, 4]'
    output = mt.render('<%= foo %>:<%== foo %>')
    is_ok(output, '34:34\n', 'same context')

with subtest('Parentheses'):
    mt = Pyjo.Template.new()
    output = mt.render('<%= (1,2,3)[1] %><%== (1,2,3)[2] %>')
    is_ok(output, '23\n', 'no ambiguity')

with subtest('String'):
    mt = Pyjo.Template.new()
    output = mt.render('Just a <%= "test" %>')
    is_ok(output, 'Just a test\n', 'rendered string')

with subtest('Trim tag'):
    mt = Pyjo.Template.new()
    output = mt.render(" ♥    <%= 'test♥' =%> \n")
    is_ok(output, ' ♥test♥', 'tag trimmed')

with subtest('Trim expression'):
    mt = Pyjo.Template.new()
    output = mt.render("<%= '123' %><%= 'begin#test' =%>\n")
    is_ok(output, '123begin#test', 'expression trimmed')

with subtest('Trim expression (multiple lines)'):
    mt = Pyjo.Template.new()
    output = mt.render(" foo    \n    <%= 'test' =%>\n foo\n")
    is_ok(output, ' foo    \ntest foo\n', 'expression trimmed')

with subtest('Trim expression (at start of line)'):
    mt = Pyjo.Template.new()
    output = mt.render("    \n<%= 'test' =%>\n    ")
    is_ok(output, '    \ntest    \n', 'expression trimmed')

with subtest('Trim expression (multiple lines)'):
    mt = Pyjo.Template.new()
    output = mt.render(" bar\n foo\n    <%= 'test' =%>\n foo\n bar\n")
    is_ok(output, ' bar\n foo\ntest foo\n bar\n', 'expression trimmed')

with subtest('Trim expression (multiple empty lines)'):
    mt = Pyjo.Template.new()
    output = mt.render("    \n<%= 'test' =%>\n    ")
    is_ok(output, '    \ntest    \n', 'expression trimmed')

capture = 'def capture(cb, *args): return cb(*args)'

with subtest('Trim expression tags'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render('    <%= capture(begin =%><html><% end) =%>    ')
    is_ok(output, '<html>', 'expression tags trimmed')

with subtest('Trim expression tags (relaxed expression end)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render('    <%= capture(begin =%><html><%= end) =%>    ')
    is_ok(output, '<html>', 'expression tags trimmed')

with subtest('Trim expression tags (relaxed escaped expression end)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render('    <%= capture(begin =%><html><%== end) =%>    ')
    is_ok(output, '<html>', 'expression tags trimmed')

with subtest('Trim expression tags (trim reset)'):
    mt = Pyjo.Template.new()
    output = mt.render('    <%= "one" =%><%= "two" %>  three')
    is_ok(output, 'onetwo  three\n', 'expression tags trimmed')

with subtest('Nothing to trim'):
    mt = Pyjo.Template.new()
    output = mt.render('<% =%>')
    is_ok(output, '', 'nothing trimmed')

with subtest('Replace tag'):
    mt = Pyjo.Template.new()
    output = mt.render('<%% 1 + 1 %>')
    is_ok(output, '<% 1 + 1 %>\n', 'tag has been replaced')

with subtest('Replace expression tag'):
    mt = Pyjo.Template.new()
    output = mt.render('<%%= 1 + 1 %>')
    is_ok(output, '<%= 1 + 1 %>\n', 'expression tag has been replaced')

with subtest('Replace expression tag (alternative)'):
    mt = Pyjo.Template.new()
    output = mt.render(' lalala <%%= 1 + 1 %> 1234 ')
    is_ok(output, ' lalala <%= 1 + 1 %> 1234 \n', 'expression tag has been replaced')

with subtest('Replace expression tag (another alternative)'):
    mt = Pyjo.Template.new()
    output = mt.render("""lalala <%%= 1 +
 1 %> 12
34
""")
    is_ok(output, 'lalala <%= 1 +\n 1 %> 12\n34\n', 'expression tag has been replaced')

with subtest('Replace comment tag'):
    mt = Pyjo.Template.new()
    output = mt.render('<%%# 1 + 1 %>')
    is_ok(output, '<%# 1 + 1 %>\n', 'comment tag has been replaced')

with subtest('Replace line'):
    mt = Pyjo.Template.new()
    output = mt.render('%% my $foo = 23;')
    is_ok(output, '% my $foo = 23;\n', 'line has been replaced')

with subtest('Replace expression line'):
    mt = Pyjo.Template.new()
    output = mt.render('  %%= 1 + 1')
    is_ok(output, '  %= 1 + 1\n', 'expression line has been replaced')

with subtest('Replace expression line (alternative)'):
    mt = Pyjo.Template.new()
    output = mt.render('%%= 1 + 1')
    is_ok(output, '%= 1 + 1\n', 'expression line has been replaced')

with subtest('Replace comment line'):
    mt = Pyjo.Template.new()
    output = mt.render('  %%# 1 + 1')
    is_ok(output, '  %# 1 + 1\n', 'comment line has been replaced')

with subtest('Replace mixed'):
    mt = Pyjo.Template.new()
    output = mt.render("""%% my $num = <%= 20 + 3%>;
The number is <%%= <%= '$' %>num %>.
""")
    is_ok(output, '% my $num = 23;\nThe number is <%= $num %>.\n', 'mixed lines have been replaced')

with subtest('Helper starting with "end"'):
    mt = Pyjo.Template.new(prepend="endpoint = 'works!'")
    output = mt.render("""% endpoint
%= endpoint
%== endpoint
<% endpoint %><%= endpoint %><%== endpoint =%>
""")
    is_ok(output, 'works!\nworks!\nworks!works!', 'helper worked')

with subtest('Helper ending with "begin"'):
    mt = Pyjo.Template.new(prepend="funbegin = 'works too!'")
    output = mt.render(r"""% funbegin
%= funbegin
%== funbegin
<% funbegin %><%= funbegin %><%== funbegin =%>\
""")
    is_ok(output, 'works too!\nworks too!\nworks too!works too!', 'helper worked')

with subtest('Catched exception'):
    mt = Pyjo.Template.new()
    output = mt.render("""% try {
%   raise Exception({'foo': 'bar'})
% } except Exception as e {
%   error = e
% }
%= error.args[0]['foo']
""")
    is_ok(output, 'bar\n', 'exception passed through')


# Dummy exception object
class MyException(Exception):
    def __init__(self, error):
        super().__init__(error)
        self.error = error


with subtest('Catched exception object'):
    mt = Pyjo.Template.new()
    output = mt.render(
        """% MyException = args[0]
% try {
%   raise MyException('works!')
% } except Exception as e {
%   error = e
% }
%= error.error
""",
        MyException,
    )
    is_ok(output, 'works!\n', 'exception object passed through')

with subtest('Recursive block'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block = None
<% block = begin =%>
% i = args[0]
<html>
<%= block(i - 1) if i else '' %>
<% end =%>
<%= block(2) %>
""")
    is_ok(output, '<html>\n<html>\n<html>\n\n\n\n\n', 'recursive block')

with subtest('Recursive block (python lines)'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block = None
% block = begin
% i = args[0]
<html>
%= block(i - 1) if i else ''
% end
%= block(2)
""")
    is_ok(output, '<html>\n<html>\n<html>\n\n\n\n\n', 'recursive block')

with subtest('Recursive block (indented python lines)'):
    mt = Pyjo.Template.new()
    output = mt.render("""  % block = None
  % block = begin
    % i = args[0]
<html>
    <%= block(i - 1) if i else '' =%>
  % end
  %= block(2)
""")
    is_ok(output, '  <html>\n<html>\n<html>\n\n', 'recursive block')

with subtest('Expression block (less whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""<% block =begin=%>
<html>
<%end=%>
<%= block() %>
""")
    is_ok(output, '<html>\n\n', 'expression block')

with subtest('Expression block (python lines and less whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block =begin
<html>
%end
<%= block() %>
""")
    is_ok(output, '<html>\n\n', 'expression block')

with subtest('Expression block (indented python lines and less whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""    % block =begin
<html>
    %end
<%= block() %>
""")
    is_ok(output, '<html>\n\n', 'expression block')

with subtest('Escaped expression block (passed through with extra whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""<% block =  begin %>
<html>
<% end  %>
<%== block() %>
""")
    is_ok(output, '\n\n<html>\n\n', 'escaped expression block')

with subtest('Escaped expression block (passed through with python lines and extra whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block =  begin
<html>
<% end  %>
<%== block() %>
""")
    is_ok(output, '\n<html>\n\n', 'escaped expression block')

with subtest('Escaped expression block (passed through with indented python lines and extra whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render(""" % block =  begin
<html>
   % end
<%== block() %>
""")
    is_ok(output, '<html>\n\n', 'escaped expression block')

with subtest('Capture lines (passed through with extra whitespace)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""<% result = capture(begin                  %>
<html>
<%                        end) %>
%== result
""")
    is_ok(output, '\n\n<html>\n\n', 'captured lines')

with subtest('Capture tags (passed through)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""<% result = capture(begin %><html><% end) %><%== result %>
""")
    is_ok(output, '<html>\n', 'capture tags')

with subtest('Capture tags (passed through alternative)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""<% result = capture(begin %><html><% end) %><%== result %>
""")
    is_ok(output, '<html>\n', 'capture tags')

with subtest('Capture tags with appended code (passed through)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""<% result = (capture(begin %><html><% end)) %><%== result %>
""")
    is_ok(output, '<html>\n', 'capture tags with appended code')

with subtest('Capture tags with appended code (passed through alternative)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""<% result = ( capture( begin %><html><% end ) ) %><%= result %>
""")
    is_ok(output, '<html>\n', 'capture tags with appended code')

with subtest('Nested capture tags (passed through)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""<% result = capture(
  begin %><%= capture(begin %><html><% end)
  %><% end) %><%== result %>
""")
    is_ok(output, '<html>\n', 'nested capture tags')

with subtest('Nested capture tags (passed through alternative)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""<% result = capture(begin =%>
    <%== capture(begin =%>
        <html>
    <% end) =%>
<% end) =%>
<%= result =%>
""")
    is_ok(output, '        <html>\n', 'nested capture tags')

with subtest('Advanced capturing (extra whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""<% block =  begin  =%>
<% name = args[0] =%>
Hello <%= name %>.
<%  end  =%>
<%= block('Baerbel') =%>
<%= block('Wolfgang') =%>
""")
    is_ok(output, 'Hello Baerbel.\nHello Wolfgang.\n', 'advanced capturing')

with subtest('Advanced capturing (python lines extra whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block =  begin
<% name = args[0] =%>
Hello <%= name %>.
%  end
<%= block('Baerbel') %>
<%= block('Wolfgang') %>
""")
    is_ok(output, 'Hello Baerbel.\n\nHello Wolfgang.\n\n', 'advanced capturing')

with subtest('Advanced capturing (indented python lines extra whitespace)'):
    mt = Pyjo.Template.new()
    output = mt.render("""    % block =  begin
<% name = args[0] =%>
Hello <%= name %>.
    %  end
<%= block('Baerbel') %>
<%= block('Wolfgang') %>
""")
    is_ok(output, 'Hello Baerbel.\n\nHello Wolfgang.\n\n', 'advanced capturing')

with subtest('Advanced capturing with tags'):
    mt = Pyjo.Template.new()
    output = mt.render("""<% block = begin =%>
    <% name = args[0] =%>
    Hello <%= name %>.
<% end =%>
<%= block('Sebastian') %>
<%= block('Sara') %>
""")
    is_ok(output, '    Hello Sebastian.\n\n    Hello Sara.\n\n', 'advanced capturing with tags')

with subtest('Advanced capturing with tags (python lines)'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block = begin
    <% name = args[0] =%>
    Hello <%= name %>.
% end
%= block('Sebastian')
%= block('Sara')
""")
    is_ok(output, '    Hello Sebastian.\n\n    Hello Sara.\n\n', 'advanced capturing with tags')

with subtest('Advanced capturing with tags (indented python lines)'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block = begin
    % name = args[0]
    Hello <%= name %>.
% end
    %= block('Sebastian')
%= block('Sara')
""")
    is_ok(output, '        Hello Sebastian.\n\n    Hello Sara.\n\n', 'advanced capturing with tags')

with subtest('Advanced capturing with tags (alternative)'):
    mt = Pyjo.Template.new()
    output = mt.render("""<% block = begin =%>
    <% name = args[0] =%>
    Hello <%= name %>.
<% end =%>
<%= block('Sebastian') %>
<%= block('Sara') %>
""")
    is_ok(output, '    Hello Sebastian.\n\n    Hello Sara.\n\n', 'advanced capturing with tags')

with subtest('Advanced capturing with tags (python lines and alternative)'):
    mt = Pyjo.Template.new()
    output = mt.render("""% block = begin
    <% name = args[0] =%>
    Hello <%= name %>.
% end
%= block('Sebastian')
%= block('Sara')
""")
    is_ok(output, '    Hello Sebastian.\n\n    Hello Sara.\n\n', 'advanced capturing with tags')

with subtest('Advanced capturing with tags (indented python lines and alternative)'):
    mt = Pyjo.Template.new()
    output = mt.render(""" % block = begin
    % name = args[0]
    Hello <%= name %>.
 % end
%= block('Sebastian')
%= block('Sara')
""")
    is_ok(output, '    Hello Sebastian.\n\n    Hello Sara.\n\n', 'advanced capturing with tags')

with subtest('More advanced capturing with tags (alternative)'):
    mt = Pyjo.Template.new()
    output = mt.render("""<% block1 = (
begin =%>
    <% name = args[0] =%>
    Hello <%= name %>.
<% end) =%>
<% block2 = (
begin =%>
    <% name = args[0] =%>
    Bye <%= name %>.
<% end) =%>
<%= block1('Sebastian') %>
<%= block2('Sara') %>
""")
    is_ok(output, '    Hello Sebastian.\n\n    Bye Sara.\n\n', 'advanced capturing with tags')

with subtest('Block loop'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""% i = iter(range(2, 5))
<% for _ in range(3) { %><%= capture(begin %>
    <%= next(i) %>
<% end) %><% } %>
""")
    is_ok(output, '\n    2\n\n    3\n\n    4\n\n', 'block loop')

with subtest('Block loop (python lines)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""% i = iter(range(2, 5))
% for _ in range(3) {
%= capture(begin
    <%= next(i) =%>
% end)
% }
""")
    is_ok(output, '\n2\n3\n4', 'block loop')

with subtest('Block loop (indented python lines)'):
    mt = Pyjo.Template.new(prepend=capture)
    output = mt.render("""  % i = iter(range(2, 5))
  % for _ in range(3) {
 %= capture(begin
    %= next(i)
   % end)
  % }
""")
    is_ok(output, ' \n    2\n \n    3\n \n    4\n', 'block loop')

with subtest('End and begin in the same python line'):
    concat = 'def concat(a, b): return a() + b()'
    mt = Pyjo.Template.new(prepend=concat)
    output = mt.render("""  %= concat(begin
    1
  % end, begin
    2
  % end)
""")
    is_ok(output, '  \n    1\n    2\n', 'end, begin')

with subtest('Strict'):
    output = Pyjo.Template.new().render('% foo += 1')
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    like_ok(output.message, r"local variable 'foo'", 'right message')

with subtest('Importing into a template'):
    mt = Pyjo.Template.new()
    output = mt.render("""% from MyTemplateExporter import foo
%= __name__
%= foo()
""")
    is_ok(output, 'Pyjo.Template.Sandbox\nworks!\n', 'right result')
    output = mt.render("""% from MyTemplateExporter import foo
%= __name__
%= foo()
""")
    is_ok(output, 'Pyjo.Template.Sandbox\nworks!\n', 'right result')

with subtest('Unusable error message (stack trace required)'):
    mt = Pyjo.Template.new()
    output = mt.render("""test
123
% raise Exception('x\\n')
test
""")
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    is_ok(output.message, 'x\n', 'right message')
    is_ok(output.lines_before[0][0], 1, 'right number')
    is_ok(output.lines_before[0][1], 'test', 'right line')
    is_ok(output.lines_before[1][0], 2, 'right number')
    is_ok(output.lines_before[1][1], '123', 'right line')
    ok(output.lines_before[1][2], 'contains code')
    is_ok(output.line[0], 3, 'right number')
    is_ok(output.line[1], "% raise Exception('x\\n')", 'right line')
    ok(output.line[2], 'contains code')
    like_ok(str(output), r'^x', 'right result')

with subtest('Compile time exception'):
    mt = Pyjo.Template.new()
    output = mt.render("""test
123
% if True {
%= 1 + 1
test
""")
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    like_ok(output.message, r'Missing end of block', 'right message')
    is_ok(output.lines_before[0][0], 1, 'right number')
    is_ok(output.lines_before[0][1], 'test', 'right line')
    is_ok(output.lines_before[1][0], 2, 'right number')
    is_ok(output.lines_before[1][1], '123', 'right line')
    is_ok(output.lines_before[2][0], 3, 'right number')
    is_ok(output.lines_before[2][1], '% if True {', 'right line')
    is_ok(output.lines_before[3][0], 4, 'right number')
    is_ok(output.lines_before[3][1], '%= 1 + 1', 'right line')
    is_ok(output.line[0], 5, 'right number')
    is_ok(output.line[1], 'test', 'right line')
    like_ok(str(output), r'Missing end of block', 'right result')
    like_ok(output.frames[0].filename, r'Template\.py$', 'right file')

with subtest('Exception in module'):
    mt = Pyjo.Template.new(prepend='from __main__ import MyTemplateException')
    output = mt.render("""test
123
%= MyTemplateException.exception()
%= 1 + 1
test
""")
    # The lines of this file around the line that raises the exception
    with open(__file__, encoding='UTF-8') as f:
        lines = f.read().split('\n')
    num = lines.index("        raise Exception('ohoh')") + 1
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    like_ok(output.message, r'ohoh', 'right message')
    is_ok(output.lines_before[0][0], num - 5, 'right number')
    is_ok(output.lines_before[0][1], lines[num - 6], 'right line')
    is_ok(output.lines_before[1][0], num - 4, 'right number')
    is_ok(output.lines_before[1][1], lines[num - 5], 'right line')
    is_ok(output.lines_before[2][0], num - 3, 'right number')
    is_ok(output.lines_before[2][1], lines[num - 4], 'right line')
    is_ok(output.lines_before[3][0], num - 2, 'right number')
    is_ok(output.lines_before[3][1], lines[num - 3], 'right line')
    is_ok(output.lines_before[4][0], num - 1, 'right number')
    is_ok(output.lines_before[4][1], lines[num - 2], 'right line')
    is_ok(output.line[0], num, 'right number')
    is_ok(output.line[1], "        raise Exception('ohoh')", 'right line')
    is_ok(output.lines_after[0][0], num + 1, 'right number')
    is_ok(output.lines_after[0][1], lines[num], 'right line')
    is_ok(output.lines_after[1][0], num + 2, 'right number')
    is_ok(output.lines_after[1][1], lines[num + 1], 'right line')
    like_ok(str(output), r'ohoh', 'right result')

with subtest('Exception in template'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""test
123\
456
 %# This dies
% raise Exception('oops!')
%= 1 + 1
test
""")
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    like_ok(output.message, r'oops!', 'right message')
    is_ok(output.lines_before[0][0], 1, 'right number')
    is_ok(output.lines_before[0][1], 'test', 'right line')
    is_ok(output.lines_before[1][0], 2, 'right number')
    is_ok(output.lines_before[1][1], '123\\', 'right line')
    is_ok(output.lines_before[2][0], 3, 'right number')
    is_ok(output.lines_before[2][1], '456', 'right line')
    is_ok(output.lines_before[3][0], 4, 'right number')
    is_ok(output.lines_before[3][1], ' %# This dies', 'right line')
    is_ok(output.line[0], 5, 'right number')
    is_ok(output.line[1], "% raise Exception('oops!')", 'right line')
    is_ok(output.lines_after[0][0], 6, 'right number')
    is_ok(output.lines_after[0][1], '%= 1 + 1', 'right line')
    is_ok(output.lines_after[1][0], 7, 'right number')
    is_ok(output.lines_after[1][1], 'test', 'right line')
    output.frames = [
        traceback.FrameSummary('template', 5, 'Sandbox.sub', lookup_line=False),
        traceback.FrameSummary('template.py', 673, 'main.sub', lookup_line=False),
    ]
    is_ok(
        str(output),
        """oops! at template line 5.
Context:
  1: test
  2: 123\\
  3: 456
  4:  %# This dies
  5: % raise Exception('oops!')
  6: %= 1 + 1
  7: test
Traceback (most recent call first):
  File "template", line 5, in "Sandbox.sub"
  File "template.py", line 673, in "main.sub"
""",
        'right result',
    )

with subtest('Exception in template (empty python lines)'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""test\\
123
%
% raise Exception('oops!')
%
  %
%
%= 1 + 1
test
""")
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    like_ok(output.message, r'oops!', 'right message')
    is_ok(output.lines_before[0][0], 1, 'right number')
    is_ok(output.lines_before[0][1], 'test\\\\', 'right line')
    ok(output.lines_before[0][2], 'contains code')
    is_ok(output.lines_before[1][0], 2, 'right number')
    is_ok(output.lines_before[1][1], '123', 'right line')
    ok(output.lines_before[1][2], 'contains code')
    is_ok(output.lines_before[2][0], 3, 'right number')
    is_ok(output.lines_before[2][1], '%', 'right line')
    is_ok(output.lines_before[2][2], ' ', 'right code')
    is_ok(output.line[0], 4, 'right number')
    is_ok(output.line[1], "% raise Exception('oops!')", 'right line')
    is_ok(output.lines_after[0][0], 5, 'right number')
    is_ok(output.lines_after[0][1], '%', 'right line')
    is_ok(output.lines_after[0][2], ' ', 'right code')
    is_ok(output.lines_after[1][0], 6, 'right number')
    is_ok(output.lines_after[1][1], '  %', 'right line')
    is_ok(output.lines_after[1][2], ' ', 'right code')
    is_ok(output.lines_after[2][0], 7, 'right number')
    is_ok(output.lines_after[2][1], '%', 'right line')
    is_ok(output.lines_after[2][2], ' ', 'right code')
    like_ok(str(output), r'oops! at template line 4', 'right result')

with subtest('Exception in nested template'):
    mt = Pyjo.Template.new(prepend='import Pyjo.Template')
    mt.tag_start = '[$-'
    mt.tag_end = '-$]'
    mt.line_start = '$-'
    output = mt.render("""test
$- mt = Pyjo.Template.new()
[$- output = mt.render('''%= bar
''') -$]
$-= output
""")
    like_ok(
        output,
        re.compile(r"test\n\nname 'bar' is not defined at template line 1\.", re.S),
        'exception in nested template',
    )

with subtest('Control structures'):
    mt = Pyjo.Template.new()
    output = mt.render("""% if 23 > 22 {
foo
% }
% else {
bar
% }
% if 23 > 22 {
bar
% }
% else {
foo
% }
""")
    is_ok(output, 'foo\nbar\n', 'control structure')

with subtest('Mixed tags'):
    mt = Pyjo.Template.new()
    output = mt.render(
        """<html foo="bar">
<%= args[0] + 1 %> test <%= 2 + 2 %> lala <%# comment lalala %>
%# This is a comment!
% i = 2
%= i * 2
</html>
""",
        2,
    )
    is_ok(output, '<html foo="bar">\n3 test 4 lala \n4\n</html>\n', 'all tags')
    like_ok(mt.code, r'lala', 'right code')
    unlike_ok(mt.code, r' comment lalala ', 'right code')
    ok(callable(mt.compiled), 'code compiled')

with subtest('Arguments'):
    mt = Pyjo.Template.new()
    output = mt.render(
        """% msg = args[0]
<html><% hash = args[1] %>
%= msg + ' ' + hash['foo']
</html>
""",
        'test',
        {'foo': 'bar'},
    )
    is_ok(output, '<html>\ntest bar\n</html>\n', 'arguments')
    is_ok(mt.process('tset', {'foo': 'baz'}), '<html>\ntset baz\n</html>\n', 'arguments again')
    is_ok(mt.process('tset', {'foo': 'yada'}), '<html>\ntset yada\n</html>\n', 'arguments again')

with subtest('Variables'):
    mt = Pyjo.Template.new()
    mt.vars = True
    output = mt.render('<%= foo %><%= bar %>', {'foo': 'works', 'bar': '!'})
    is_ok(output, 'works!\n', 'variables')

with subtest('No variables'):
    mt = Pyjo.Template.new()
    mt.vars = True
    output = mt.render('works too!')
    is_ok(output, 'works too!\n', 'no variables')

with subtest('Bad variables'):
    mt = Pyjo.Template.new()
    mt.vars = True
    output = mt.render('bad variables!', {'not good': 23})
    is_ok(output, 'bad variables!\n', 'bad variables')

with subtest('Ugly multiline loop'):
    mt = Pyjo.Template.new()
    output = mt.render("""% nums = ''
<html><% for i in range(1, 5) {
    nums += str(i)
} %><%= nums%></html>
""")
    is_ok(output, '<html>1234</html>\n', 'ugly multiline loop')

with subtest('Clean multiline loop'):
    mt = Pyjo.Template.new()
    output = mt.render("""<html>
%  for i in range(1, 5) {
%=    i
%  }
</html>
""")
    is_ok(output, '<html>\n1\n2\n3\n4\n</html>\n', 'clean multiline loop')

with subtest('Escaped line ending'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""<html>\
%= '2' * 4
</html>\\\\
""")
    is_ok(output, '<html>2222\n</html>\\\\\\\n', 'escaped line ending')

with subtest('XML escape'):
    mt = Pyjo.Template.new()
    output = mt.render("""<html><%== '<html>' %>
%== '&lt;'
</html>
""")
    is_ok(output, '<html>&lt;html&gt;\n&amp;lt;\n</html>\n', 'XML escape')

with subtest('XML auto escape'):
    mt = Pyjo.Template.new()
    mt.auto_escape = True
    output = mt.render("""<html><%= '<html>' %>
%= 'begin#&lt;'
%== 'begin#&lt;'
</html>
""")
    is_ok(
        output,
        """<html>&lt;html&gt;
begin#&amp;lt;
begin#&lt;
</html>
""",
        'XML auto escape',
    )

with subtest('Complicated XML auto escape'):
    mt = Pyjo.Template.new()
    mt.auto_escape = True
    output = mt.render(
        """% import json
%= json.dumps(args[0], indent=2) + '\\n'
""",
        {'foo': 23},
    )
    is_ok(
        output,
        """{
  &quot;foo&quot;: 23
}

""",
        'complicated XML auto escape',
    )

with subtest('Complicated XML auto escape'):
    mt = Pyjo.Template.new()
    mt.auto_escape = True
    output = mt.render("""<html><%= ['<html>' for _ in range(3)] %></html>
""")
    is_ok(
        output,
        """<html>&lt;html&gt;&lt;html&gt;&lt;html&gt;</html>
""",
        'complicated XML auto escape',
    )

with subtest('Prepending code'):
    mt = Pyjo.Template.new()
    mt.prepend = "foo = args[0]; bar = 'something\\nelse'"
    output = mt.render(
        """<%= foo %>
%= bar
% bar = 23
%= bar
""",
        23,
    )
    is_ok(output, '23\nsomething\nelse\n23\n', 'prepending code')
    mt = Pyjo.Template.new()
    mt.prepend = 'global foo\nfoo = lambda: 23'
    output = mt.render('<%= foo() %>')
    is_ok(output, '23\n', 'right result')
    output = mt.render('%= foo()')
    is_ok(output, '23\n', 'right result')

with subtest('Appending code'):
    mt = Pyjo.Template.new()
    mt.append = "_O = 'FOO!'"
    output = mt.render('23')
    is_ok(output, 'FOO!', 'appending code')

with subtest('Multiline comment'):
    mt = Pyjo.Template.new()
    output = mt.render("""<html><%# this is
a
comment %>this not
%  for i in range(1, 5) {
%=    i
%  }
</html>
""")
    is_ok(output, '<html>this not\n1\n2\n3\n4\n</html>\n', 'multiline comment')

with subtest('Commented out tags'):
    mt = Pyjo.Template.new()
    output = mt.render("""<html>
 %# <%= 23 %>test<%= 24 %>
</html>
""")
    is_ok(output, '<html>\n</html>\n', 'commented out tags')

with subtest('One-liner'):
    mt = Pyjo.Template.new()
    output = mt.render('<html><%= 3 * 3 %></html>\\')
    is_ok(output, '<html>9</html>', 'one-liner')

with subtest('Different line start'):
    mt = Pyjo.Template.new()
    mt.line_start = '$'
    output = mt.render(r"""<html>\
$= '2' * 4
</html>\\\\
""")
    is_ok(output, '<html>2222\n</html>\\\\\\\n', 'different line start')

with subtest('Inline comments'):
    mt = Pyjo.Template.new()
    output = mt.render("""% if 1 { # test
works!
% }   # tset
great!
""")
    is_ok(output, 'works!\ngreat!\n', 'comments did not affect the result')

with subtest('Inline comment on last line'):
    mt = Pyjo.Template.new()
    output = mt.render("""% if 1 {
works!
% }   # tset
""")
    is_ok(output, 'works!\n', 'comment did not affect the result')

with subtest('Multiline expression'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""<html><%= '2'
* 4 %>\
</html>\
""")
    is_ok(output, '<html>2222</html>', 'multiline expression')

with subtest('Different multiline expression'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""<%= '2' *
  4
%>\
""")
    is_ok(output, '2222', 'multiline expression')

with subtest('Yet another multiline expression'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""<%= 'hello' +
    ' world' %>\
""")
    is_ok(output, 'hello world', 'multiline expression')

with subtest('And another multiline expression'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""<%= 'hello' +

    ' world' %>\
""")
    is_ok(output, 'hello world', 'multiline expression')

with subtest('And another multiline expression'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""<%= 'hello' +

 ' wo' +

    'rld'
%>\
""")
    is_ok(output, 'hello world', 'multiline expression')

with subtest('Escaped multiline expression'):
    mt = Pyjo.Template.new()
    output = mt.render("""<%==
'hello '
+'world'
%>
""")
    is_ok(output, 'hello world\n', 'escaped multiline expression')

with subtest('Empty statement'):
    mt = Pyjo.Template.new()
    output = mt.render('test\n\n123\n\n<% %>456\n789')
    is_ok(output, 'test\n\n123\n\n456\n789\n', 'empty statement')

with subtest('No newline'):
    mt = Pyjo.Template.new()
    output = mt.render('test')
    is_ok(output, 'test\n', 'just one newline')

with subtest('Multiple newlines at the end'):
    mt = Pyjo.Template.new()
    output = mt.render('test\n\n\n\n')
    is_ok(output, 'test\n', 'just one newline')

with subtest('Escaped newline at the end'):
    mt = Pyjo.Template.new()
    output = mt.render('test\\\n')
    is_ok(output, 'test', 'no newline')

with subtest('Multiple escaped newlines at the end'):
    mt = Pyjo.Template.new()
    output = mt.render('test\\\n\n\n\n')
    is_ok(output, 'test', 'no newline')

with subtest('Optimize successive text lines ending with newlines'):
    mt = Pyjo.Template.new()
    mt.parse(r"""test
123
456\
789\\
987
654
321
""")
    is_ok(mt.tree[0][1], 'test\n123\n456', 'optimized text lines')
    output = mt.process()
    is_deeply_ok(mt.tree, [], 'has been consumed')
    is_ok(output, 'test\n123\n456789\\\n987\n654\n321\n', 'just text')

with subtest('Scoped scalar'):
    mt = Pyjo.Template.new()
    output = mt.render("""% foo = 'bar'
<%= foo %>
""")
    is_ok(output, 'bar\n', 'scoped scalar')

with subtest('Different tags and line start'):
    mt = Pyjo.Template.new()
    mt.tag_start = '[$-'
    mt.tag_end = '-$]'
    mt.line_start = '$-'
    output = mt.render(
        """$- msg = args[0]
<html>[$- hash = args[1] -$]
$-= msg + ' ' + hash['foo']
</html>
""",
        'test',
        {'foo': 'bar'},
    )
    is_ok(output, '<html>\ntest bar\n</html>\n', 'different tags and line start')

with subtest('Different expression and comment marks'):
    mt = Pyjo.Template.new()
    mt.comment_mark = '@@@'
    mt.expression_mark = '---'
    output = mt.render(
        """% msg = args[0]
<html><% hash = args[1] %><%@@@ comment lalala %>
%--- msg + ' ' + hash['foo']
</html>
""",
        'test',
        {'foo': 'bar'},
    )
    is_ok(
        output,
        """<html>
test bar
</html>
""",
        'different expression and comment mark',
    )

with subtest('File'):
    mt = Pyjo.Template.new()
    file = os.path.join(TEMPLATES, 'test.ep')
    output = mt.render_file(file, 3)
    like_ok(output, re.compile(r'23\nHello World!'), 'file')

with subtest('Exception in file'):
    mt = Pyjo.Template.new()
    file = os.path.join(TEMPLATES, 'exception.ep')
    output = mt.render_file(file)
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    # Unlike Mojolicious: the message of Python has no location, which the string of the exception adds
    like_ok(str(output), r'exception\.ep line 2', 'message contains filename')
    is_ok(output.lines_before[0][0], 1, 'right number')
    is_ok(output.lines_before[0][1], 'test', 'right line')
    is_ok(output.line[0], 2, 'right number')
    is_ok(output.line[1], '% raise Exception()', 'right line')
    is_ok(output.lines_after[0][0], 3, 'right number')
    is_ok(output.lines_after[0][1], '123', 'right line')
    like_ok(str(output), r'exception\.ep line 2', 'right result')

with subtest('Exception in file (different name)'):
    mt = Pyjo.Template.new()
    mt.name = '"foo.ep" from DATA section'
    output = mt.render_file(file)
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    # Unlike Mojolicious: the message of Python has no location, which the string of the exception adds
    like_ok(str(output), r'foo\.ep from DATA section line 2', 'message contains filename')
    is_ok(output.lines_before[0][0], 1, 'right number')
    is_ok(output.lines_before[0][1], 'test', 'right line')
    is_ok(output.line[0], 2, 'right number')
    is_ok(output.line[1], '% raise Exception()', 'right line')
    is_ok(output.lines_after[0][0], 3, 'right number')
    is_ok(output.lines_after[0][1], '123', 'right line')
    like_ok(str(output), r'foo\.ep from DATA section line 2', 'right result')

with subtest('Exception with UTF-8 context'):
    mt = Pyjo.Template.new()
    file = os.path.join(TEMPLATES, 'utf8_exception.ep')
    output = mt.render_file(file)
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    is_ok(output.lines_before[0][1], '☃', 'right line')
    is_ok(output.line[1], "% raise Exception('♥')", 'right line')
    is_ok(output.lines_after[0][1], '☃', 'right line')

with subtest('Exception in first line with bad message'):
    mt = Pyjo.Template.new()
    output = mt.render('<% raise Exception("Test at template line 99\\n") %>')
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    is_ok(output.message, 'Test at template line 99\n', 'right message')
    is_ok(len(output.lines_before), 0, 'no lines before')
    is_ok(output.line[0], 1, 'right number')
    is_ok(output.line[1], '<% raise Exception("Test at template line 99\\n") %>', 'right line')
    is_ok(len(output.lines_after), 0, 'no lines after')

with subtest('Different encodings'):
    mt = Pyjo.Template.new(encoding='shift_jis')
    file = os.path.join(TEMPLATES, 'utf8_exception.ep')
    throws_ok(lambda: mt.render_file(file), Pyjo.Exception.object, re.compile('invalid encoding'))

with subtest('Custom escape function'):
    mt = Pyjo.Template.new(escape=lambda value: '+' + value)
    is_ok(mt.render('<%== "hi" =%>'), '+hi', 'right escaped string')


# Not in Mojolicious: blocks the way of Python
with subtest('Blocks with a colon'):
    mt = Pyjo.Template.new()
    output = mt.render("""% for i in range(3):
%   if i == 0:
zero
%   elif i == 1:
one
%   else:
many
%   end
% end
""")
    is_ok(output, 'zero\none\nmany\n', 'blocks')
    output = mt.render("""<% for i in range(3): %><%= i %><% end %>
""")
    is_ok(output, '012\n', 'blocks in tags')

# Not in Mojolicious: the end of a nested block does not continue it
with subtest('Branch after a nested block'):
    mt = Pyjo.Template.new(vars=True)
    template = """% if x:
%   for item in items:
<%= item %>
%   end
% else:
nothing
% end
"""
    is_ok(mt.render(template, {'x': True, 'items': [1, 2]}), '1\n2\n', 'first branch with a loop')
    is_ok(mt.render(template, {'x': False, 'items': [1, 2]}), 'nothing\n', 'else of the outer block')
    template = """% if x:
%   if y:
A
%   end
% elif z:
B
% else:
C
% end
"""
    is_ok(mt.render(template, {'x': True, 'y': False, 'z': True}), '', 'inner block without its branch')
    is_ok(mt.render(template, {'x': False, 'y': False, 'z': True}), 'B\n', 'elif of the outer block')
    is_ok(mt.render(template, {'x': False, 'y': False, 'z': False}), 'C\n', 'else of the outer block')
    output = mt.render("""% for i in []:
%   for j in [1]:
<%= j %>
%   end
% else:
empty
% end
""")
    is_ok(output, 'empty\n', 'else of the outer loop')
    output = mt.render("""% for i in [1] {
%   if i {
yes
%   }
%   else {
no
%   }
% } else {
empty
% }
""")
    is_ok(output, 'yes\nempty\n', 'else after a closing brace continues its block')

# Not in Mojolicious: a block without statements
with subtest('Empty blocks'):
    mt = Pyjo.Template.new()
    output = mt.render("""% for i in range(3):
% end
% if True {
% }
done
""")
    is_ok(output, 'done\n', 'empty blocks')

# Not in Mojolicious: match and case
with subtest('Match and case'):
    mt = Pyjo.Template.new()
    output = mt.render("""% for value in (1, 'a', None):
%   match value:
%   case int():
int
%   case str():
str
%   case _:
other
%   end
% end
""")
    is_ok(output, 'int\nstr\nother\n', 'one end for the match')
    output = mt.render("""% match 2 {
% case 1 {
one
% }
% case 2 {
two
% }
% }
""")
    is_ok(output, 'two\n', 'braces')

# Not in Mojolicious: try, except, else and finally
with subtest('Try'):
    mt = Pyjo.Template.new()
    output = mt.render("""% for value in ('x', None):
% try:
%   if value: raise ValueError(value)
% except ValueError as e:
caught <%= e %>
% else:
not raised
% finally:
finally
% end
% end
""")
    is_ok(output, 'caught x\nfinally\nnot raised\nfinally\n', 'try')

# Not in Mojolicious: while
with subtest('While'):
    mt = Pyjo.Template.new()
    output = mt.render(r"""% i = 0
% while i < 3 {
<%= i %>\
%   i += 1
% }
""")
    is_ok(output, '012', 'while')

# Not in Mojolicious: the braces of Python are not blocks
with subtest('Braces of Python'):
    mt = Pyjo.Template.new()
    output = mt.render("""% d = {
%   'a': 1,
% }
<%= d['a'] %> <%= {'b': 2}['b'] %>
% if d == {'a': 1} {
dict
% }
% if {x for x in d} == {'a'}: # set
set
% end
<%= f'{d["a"]}' %> <%= f"{ {'c': 3}['c'] }" %> <%= '{' %>
""")
    is_ok(output, '1 2\ndict\nset\n1 3 {\n', 'braces')

# Not in Mojolicious: code of several lines in a tag
with subtest('Code of several lines'):
    mt = Pyjo.Template.new()
    output = mt.render("""<%
total = 0
for i in range(4) {
        total += i
}
text = '''a
  b'''
%><%= total %> <%= text %>
""")
    is_ok(output, '6 a\n  b\n', 'code of several lines')
    output = mt.render("""% total = sum([
%   1,
%   2,
% ])
<%= total %>
""")
    is_ok(output, '3\n', 'lines that continue')

# Not in Mojolicious: errors of the blocks
with subtest('Unexpected end'):
    mt = Pyjo.Template.new()
    output = mt.render('test\n% end\n')
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    like_ok(output.message, r'^Unexpected end at template line 2\.', 'right message')
    is_ok(output.line[0], 2, 'right number')
    output = mt.render('test\n% }\n')
    like_ok(output.message, r'^Unexpected "}" at template line 2\.', 'right message')
    output = mt.render('% block = begin\n% }\n% end\n')
    like_ok(output.message, r'^Unexpected "}" at template line 2\.', 'brace that closes a capture')
    output = mt.render('<% block = begin %>\ntest\n')
    like_ok(output.message, r'^Missing end of begin from line 1 at template line 2\.', 'capture without end')

# Not in Mojolicious: a syntax error of Python
with subtest('Syntax error'):
    mt = Pyjo.Template.new()
    output = mt.render('test\n% x = (1,\n%= 2\n')
    isa_ok(output, Pyjo.Exception.object, 'right exception')
    like_ok(output.message, r'was never closed at template line 2\.', 'right message')
    is_ok(output.line[0], 2, 'right number')
    is_ok(output.line[1], '% x = (1,', 'right line')

# Not in Mojolicious: the values are rendered as the interpolations of Pyjo.String.Template
with subtest('Values'):
    from Pyjo.String.HTML import html
    from Pyjo.String.Template import t

    mt = Pyjo.Template.new(auto_escape=True)
    output = mt.render(
        '<%= args[0] %>|<%= args[1] %>|<%= args[2] %>|<%= args[3] %>|<%== args[3] %>',
        html('<b>'),
        None,
        t('<i>{x}</i>', x='<s>'),
        ['<a>', html('<b>')],
    )
    is_ok(output, '<b>||<i>&lt;s&gt;</i>|&lt;a&gt;<b>|<a><b>\n', 'markup, None, template and list')
    isa_ok(output, Pyjo.String.HTML.object, 'markup')
    output = mt.render('<% block = begin %><b><% end %><%= block() %>')
    is_ok(output, '<b>\n', 'capture is markup')

# Not in Mojolicious: t-strings of Python 3.14 in a template
with subtest('Template strings'):
    if sys.version_info < (3, 14):
        skip('t-strings need Python 3.14', 1)
    else:
        mt = Pyjo.Template.new()
        output = mt.render("""% x = '<s>'
<%= t'<b>{x}</b>' %>
""")
        is_ok(output, '<b>&lt;s&gt;</b>\n', 't-string')

# Not in Mojolicious: a module as the namespace, and its globals shared between templates
with subtest('Namespace'):
    mt = Pyjo.Template.new(namespace='MyTemplateExporter')
    is_ok(mt.render('<%= foo() %>'), 'works!\n', 'module')
    mt = Pyjo.Template.new()
    mt.render('% global shared\n% shared = 23')
    is_ok(Pyjo.Template.new().render('<%= shared %>'), '23\n', 'shared globals')

# Not in Mojolicious: names of variables that Python does not have
with subtest('Variables with names of Python'):
    mt = Pyjo.Template.new(vars=True)
    is_ok(mt.render('<%= foo %>', {'foo': 1, 'class': 2, 3: 4}), '1\n', 'only the names of Python')

done_testing()
