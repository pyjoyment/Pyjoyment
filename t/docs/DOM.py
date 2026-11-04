from Pyjo.Test import *

import contextlib
import io


with subtest('Synopsis'):
    from Pyjo.DOM import DOM

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Parse
        dom = DOM('<div><p id="a">Test</p><p id="b">123</p></div>')

        # Find
        print(dom.at('#b').text)
        print(dom.find('p').map('text').join('\n'))
        print(dom.find('[id]').map('attr', 'id').join('\n'))
    is_ok(output.getvalue(), '123\nTest\n123\na\nb\n', 'output')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.DOM

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Parse
        dom = Pyjo.DOM.new('<div><p id="a">Test</p><p id="b">123</p></div>')

        # Find
        print(dom.at('#b').text)
        print(dom.find('p').map('text').join('\n'))
        print(dom.find('[id]').map('attr', 'id').join('\n'))

        # Iterate
        dom.find('p[id]').reverse().each(lambda e, num: print(e['id']))

        # Loop
        for e in dom.find('p[id]').each():
            print(e['id'], ':', e.text)

        # Modify
        dom.find('div p').last().append('<p id="c">456</p>')
        dom.at('#c').prepend(dom.new_tag('p', '789', id='d'))
        dom.find(':not(p)').map('strip')

        # Render
        print(dom)
    is_ok(
        output.getvalue(),
        '123\nTest\n123\na\nb\nb\na\na : Test\nb : 123\n'
        '<p id="a">Test</p><p id="b">123</p><p id="d">789</p><p id="c">456</p>\n',
        'output',
    )

with subtest('HTML and XML'):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # HTML semantics
        dom = Pyjo.DOM.new('<P ID="greeting">Hi!</P>')
        print(dom.at('p[id]').text)

        # XML semantics
        dom = Pyjo.DOM.new('<?xml version="1.0"?><P ID="greeting">Hi!</P>')
        print(dom.at('P[ID]').text)

        # Force HTML semantics
        dom = Pyjo.DOM.new().set(xml=False).parse('<P ID="greeting">Hi!</P>')
        print(dom.at('p[id]').text)

        # Force XML semantics
        dom = Pyjo.DOM.new().set(xml=True).parse('<P ID="greeting">Hi!</P>')
        print(dom.at('P[ID]').text)

        # Bytes of a page in windows-1250
        dom = Pyjo.DOM.new('<meta charset="windows-1250"><p>Zażółć gęślą jaźń</p>'.encode('windows-1250'))
        print(dom.at('p').text)
    is_ok(output.getvalue(), 'Hi!\nHi!\nHi!\nHi!\nZażółć gęślą jaźń\n', 'output')

with subtest('new'):
    dom = Pyjo.DOM.new()
    is_ok(dom, '', 'empty')
    dom = Pyjo.DOM.new('<foo bar="baz">I ♥ Pyjoyment!</foo>')
    is_ok(dom, '<foo bar="baz">I ♥ Pyjoyment!</foo>', 'parsed')

with subtest('__bool__'):
    boolean = bool(Pyjo.DOM.new())
    ok(boolean, 'always true')

with subtest('__contains__'):
    dom = Pyjo.DOM.new('<div id="test">Test</div>').at('div')
    boolean = 'id' in dom
    ok(boolean, 'has the attribute')

with subtest('__delitem__'):
    del dom['id']
    is_ok(dom, '<div>Test</div>', 'removed')

with subtest('__getitem__'):
    dom = Pyjo.DOM.new()

    # "test"
    is_ok(dom.parse('<div id="test">Test</div>').at('div')['id'], 'test', 'attribute')

    # "<!-- Test -->"
    is_ok(dom.parse('<!-- Test --><b>123</b>')[0], '<!-- Test -->', 'child node')

with subtest('__iter__'):
    nodes = []
    for node in dom:
        nodes.append(node.type)
    is_deeply_ok(nodes, ['comment', 'tag'], 'child nodes')

with subtest('__len__'):
    size = len(dom)
    is_ok(size, 2, 'child nodes')

with subtest('__setitem__'):
    dom.at('b')['id'] = 'test'
    is_ok(dom, '<!-- Test --><b id="test">123</b>', 'set')

with subtest('all_text'):
    # "foo\nbarbaz\n"
    is_ok(dom.parse('<div>foo\n<p>bar</p>baz\n</div>').at('div').all_text, 'foo\nbarbaz\n', 'all_text')

with subtest('ancestors'):
    dom = dom.parse('<div><p><b>Test</b></p></div>').at('b')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # List tag names of ancestor elements
        print(dom.ancestors().map('tag').join('\n'))
    is_ok(output.getvalue(), 'p\ndiv\n', 'output')

with subtest('append'):
    dom = Pyjo.DOM.new()

    # "<div><h1>Test</h1><h2>123</h2></div>"
    is_ok(
        dom.parse('<div><h1>Test</h1></div>').at('h1').append('<h2>123</h2>').root,
        '<div><h1>Test</h1><h2>123</h2></div>',
        'append',
    )

    # "<p>Test 123</p>"
    is_ok(dom.parse('<p>Test</p>').at('p').child_nodes.first().append(' 123').root, '<p>Test 123</p>', 'append')

with subtest('append_content'):
    # "<div><h1>Test123</h1></div>"
    is_ok(
        dom.parse('<div><h1>Test</h1></div>').at('h1').append_content('123').root,
        '<div><h1>Test123</h1></div>',
        'append_content',
    )

    # "<!-- Test 123 --><br>"
    is_ok(
        dom.parse('<!-- Test --><br>').child_nodes.first().append_content('123 ').root,
        '<!-- Test 123 --><br>',
        'append_content',
    )

    # "<p>Test<i>123</i></p>"
    is_ok(dom.parse('<p>Test</p>').at('p').append_content('<i>123</i>').root, '<p>Test<i>123</i></p>', 'append_content')

with subtest('at'):
    dom.parse('<svg xmlns:svg="http://www.w3.org/2000/svg"></svg>')

    # Find first element with "svg" namespace definition
    namespace = dom.at(r'[xmlns\:svg]')['xmlns:svg']
    is_ok(namespace, 'http://www.w3.org/2000/svg', 'namespace')

    # "<rect></rect>"
    is_ok(
        dom.parse('<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>').at(
            'svg|rect', svg='http://www.w3.org/2000/svg'
        ),
        '<rect></rect>',
        'at',
    )

with subtest('attr'):
    dom = Pyjo.DOM.new('<p id="a">Test</p>').at('p')

    # Remove an attribute
    del dom.attr()['id']
    is_ok(dom, '<p>Test</p>', 'removed')

    # Attribute without value
    dom.attr(selected=None)
    is_ok(dom, '<p selected>Test</p>', 'without value')

    dom = Pyjo.DOM.new('<p id="a">A</p><p>B</p><p id="c">C</p>')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # List id attributes
        print(dom.find('*').map('attr', 'id').compact().join('\n'))
    is_ok(output.getvalue(), 'a\nc\n', 'output')

with subtest('child_nodes'):
    # "<p><b>123</b></p>"
    is_ok(dom.parse('<p>Test<b>123</b></p>').at('p').child_nodes.first().remove(), '<p><b>123</b></p>', 'child_nodes')

    # "<!DOCTYPE html>"
    is_ok(dom.parse('<!DOCTYPE html><b>123</b>').child_nodes.first(), '<!DOCTYPE html>', 'child_nodes')

    # " Test "
    is_ok(dom.parse('<b>123</b><!-- Test -->').child_nodes.last().content, ' Test ', 'child_nodes')

with subtest('children'):
    dom = dom.parse('<div><p>Test</p></div>').at('div')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Show tag name of random child element
        print(dom.children().shuffle().first().tag)
    is_ok(output.getvalue(), 'p\n', 'output')

with subtest('content'):
    dom = Pyjo.DOM.new()

    # "<b>Test</b>"
    is_ok(dom.parse('<div><b>Test</b></div>').at('div').content, '<b>Test</b>', 'content')

    # "<div><h1>123</h1></div>"
    is_ok(dom.parse('<div><h1>Test</h1></div>').at('h1').set(content='123').root, '<div><h1>123</h1></div>', 'content')

    # "<p><i>123</i></p>"
    is_ok(dom.parse('<p>Test</p>').at('p').set(content='<i>123</i>').root, '<p><i>123</i></p>', 'content')

    # "<div><h1></h1></div>"
    is_ok(dom.parse('<div><h1>Test</h1></div>').at('h1').set(content='').root, '<div><h1></h1></div>', 'content')

    # " Test "
    is_ok(dom.parse('<!-- Test --><br>').child_nodes.first().content, ' Test ', 'content')

    # "<div><!-- 123 -->456</div>"
    is_ok(
        dom.parse('<div><!-- Test -->456</div>').at('div').child_nodes.first().set(content=' 123 ').root,
        '<div><!-- 123 -->456</div>',
        'content',
    )

with subtest('descendant_nodes'):
    # "<p><b>123</b></p>"
    is_ok(
        dom.parse('<p><!-- Test --><b>123<!-- 456 --></b></p>')
        .descendant_nodes.grep(lambda e: e.type == 'comment')
        .map('remove')
        .first(),
        '<p><b>123</b></p>',
        'descendant_nodes',
    )

    # "<p><b>test</b>test</p>"
    is_ok(
        dom.parse('<p><b>123</b>456</p>')
        .at('p')
        .descendant_nodes.grep(lambda e: e.type == 'text')
        .map('content', 'test')
        .first()
        .root,
        '<p><b>test</b>test</p>',
        'descendant_nodes',
    )

with subtest('find'):
    dom.parse(''.join(f'<div id="{i}"></div>' for i in range(24)) + '<h1>A</h1><h2>B</h2><div class="foo.bar"></div>')

    # Find a specific element and extract information
    id = dom.find('div')[23]['id']
    is_ok(id, '23', 'id')

    # Extract information from multiple elements
    headers = dom.find('h1, h2, h3').map('text').each()
    is_deeply_ok(headers, ['A', 'B'], 'headers')

    # Count all the different tags
    counts = dom.find('*').reduce(lambda a, b: a | {b.tag: a.get(b.tag, 0) + 1}, {})
    is_deeply_ok(counts, {'div': 25, 'h1': 1, 'h2': 1}, 'counts')

    # Find elements with a class that contains dots
    divs = dom.find(r'div.foo\.bar').each()
    is_ok(len(divs), 1, 'divs')

    # "<rect></rect>"
    is_ok(
        dom.parse('<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>')
        .find('svg|rect', svg='http://www.w3.org/2000/svg')
        .first(),
        '<rect></rect>',
        'find',
    )

with subtest('following'):
    dom = dom.parse('<p>A</p><b>B</b><i>C</i>').at('p')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # List tags of sibling elements after this node
        print(dom.following().map('tag').join('\n'))
    is_ok(output.getvalue(), 'b\ni\n', 'output')

with subtest('following_nodes'):
    # "C"
    is_ok(dom.parse('<p>A</p><!-- B -->C').at('p').following_nodes.last().content, 'C', 'following_nodes')

with subtest('iterate'):
    dom = dom.parse('<p>A</p><p>B <a href="/b">b</a></p><p>C</p>')
    iterator = dom.iterate('p ~ p')
    is_deeply_ok(iterator.map('text').to_list(), ['B ', 'C'], 'iterate')
    iterator = dom.parse('<svg xmlns="http://www.w3.org/2000/svg"><line /></svg>').iterate(
        'svg|line', svg='http://www.w3.org/2000/svg'
    )
    is_ok(iterator.first().tag, 'line', 'namespace')

    dom = dom.parse('<p>A</p><p>B <a href="/b">b</a></p><p>C</p>')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Print the text of each paragraph as soon as it is found
        dom.iterate('p').map('all_text').each(lambda text, num: print(text))
    is_ok(output.getvalue(), 'A\nB b\nC\n', 'printed')

    # Find no more elements after the first one with a link
    link = dom.iterate('p').first(lambda p: p.at('a[href]'))
    is_ok(link.all_text, 'B b', 'first with a link')

with subtest('matches'):
    # True
    ok(dom.parse('<p class="a">A</p>').at('p').matches('.a'), 'matches')
    ok(dom.parse('<p class="a">A</p>').at('p').matches('p[class]'), 'matches')

    # False
    ok(not dom.parse('<p class="a">A</p>').at('p').matches('.b'), 'does not match')
    ok(not dom.parse('<p class="a">A</p>').at('p').matches('p[id]'), 'does not match')

    # True
    ok(
        dom.parse('<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>')
        .at('svg')
        .matches('svg|svg', svg='http://www.w3.org/2000/svg'),
        'matches',
    )

with subtest('namespace'):
    # "http://www.w3.org/2000/svg"
    is_ok(
        Pyjo.DOM.new('<svg xmlns:svg="http://www.w3.org/2000/svg"><svg:circle>3.14</svg:circle></svg>')
        .at(r'svg\:circle')
        .namespace,
        'http://www.w3.org/2000/svg',
        'namespace',
    )

    dom = Pyjo.DOM.new(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:svg="http://www.w3.org/2000/svg"><svg:circle /><circle /></svg>'
    )

    # Find namespace for an element with namespace prefix
    namespace = dom.at(r'svg > svg\:circle').namespace
    is_ok(namespace, 'http://www.w3.org/2000/svg', 'namespace')

    # Find namespace for an element that may or may not have a namespace prefix
    namespace = dom.at('svg > circle').namespace
    is_ok(namespace, 'http://www.w3.org/2000/svg', 'namespace')

with subtest('new_tag'):
    tag = Pyjo.DOM.object.new_tag('div')
    is_ok(tag, '<div></div>', 'class')
    dom = Pyjo.DOM.new()
    tag = dom.new_tag('div')
    is_ok(tag, '<div></div>', 'object')

    # "<br>"
    is_ok(dom.new_tag('br'), '<br>', 'br')

    # "<div></div>"
    is_ok(dom.new_tag('div'), '<div></div>', 'div')

    # "<div hidden id="foo"></div>"
    is_ok(dom.new_tag('div', id='foo', hidden=None), '<div hidden id="foo"></div>', 'attributes')

    # "<div>test &amp; 123</div>"
    is_ok(dom.new_tag('div', 'test & 123'), '<div>test &amp; 123</div>', 'content')

    # "<div id="foo">test &amp; 123</div>"
    is_ok(dom.new_tag('div', 'test & 123', id='foo'), '<div id="foo">test &amp; 123</div>', 'content and attribute')

    # "<div data-bar="test" data-foo="1">test &amp; 123</div>"
    is_ok(
        dom.new_tag('div', 'test & 123', data={'foo': 1, 'Bar': 'test'}),
        '<div data-bar="test" data-foo="1">test &amp; 123</div>',
        'data',
    )

    # "<div id="foo">test & 123</div>"
    is_ok(dom.new_tag('div', lambda: 'test & 123', id='foo'), '<div id="foo">test & 123</div>', 'raw content')

    # "<div>Hello<b>Pyjo!</b></div>"
    is_ok(
        dom.parse('<div>Hello</div>').at('div').append_content(dom.new_tag('b', 'Pyjo!')).root,
        '<div>Hello<b>Pyjo!</b></div>',
        'append_content',
    )

with subtest('next'):
    # "<h2>123</h2>"
    is_ok(dom.parse('<div><h1>Test</h1><h2>123</h2></div>').at('h1').next, '<h2>123</h2>', 'next')

with subtest('next_node'):
    # "456"
    is_ok(dom.parse('<p><b>123</b><!-- Test -->456</p>').at('b').next_node.next_node, '456', 'next_node')

    # " Test "
    is_ok(dom.parse('<p><b>123</b><!-- Test -->456</p>').at('b').next_node.content, ' Test ', 'next_node')

with subtest('parent'):
    # "<b><i>Test</i></b>"
    is_ok(dom.parse('<p><b><i>Test</i></b></p>').at('i').parent, '<b><i>Test</i></b>', 'parent')

with subtest('parse'):
    # Parse XML
    dom = Pyjo.DOM.new().set(xml=True).parse('<foo>I ♥ Pyjoyment!</foo>')
    ok(dom.xml, 'XML')

with subtest('preceding'):
    dom = Pyjo.DOM.new('<b>A</b><i>B</i><p>C</p>').at('p')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # List tags of sibling elements before this node
        print(dom.preceding().map('tag').join('\n'))
    is_ok(output.getvalue(), 'b\ni\n', 'output')

with subtest('preceding_nodes'):
    # "A"
    is_ok(dom.parse('A<!-- B --><p>C</p>').at('p').preceding_nodes.first().content, 'A', 'preceding_nodes')

with subtest('prepend'):
    # "<div><h1>Test</h1><h2>123</h2></div>"
    is_ok(
        dom.parse('<div><h2>123</h2></div>').at('h2').prepend('<h1>Test</h1>').root,
        '<div><h1>Test</h1><h2>123</h2></div>',
        'prepend',
    )

    # "<p>Test 123</p>"
    is_ok(dom.parse('<p>123</p>').at('p').child_nodes.first().prepend('Test ').root, '<p>Test 123</p>', 'prepend')

with subtest('prepend_content'):
    # "<div><h2>Test123</h2></div>"
    is_ok(
        dom.parse('<div><h2>123</h2></div>').at('h2').prepend_content('Test').root,
        '<div><h2>Test123</h2></div>',
        'prepend_content',
    )

    # "<!-- Test 123 --><br>"
    is_ok(
        dom.parse('<!-- 123 --><br>').child_nodes.first().prepend_content(' Test').root,
        '<!-- Test 123 --><br>',
        'prepend_content',
    )

    # "<p><i>123</i>Test</p>"
    is_ok(
        dom.parse('<p>Test</p>').at('p').prepend_content('<i>123</i>').root, '<p><i>123</i>Test</p>', 'prepend_content'
    )

with subtest('previous'):
    # "<h1>Test</h1>"
    is_ok(dom.parse('<div><h1>Test</h1><h2>123</h2></div>').at('h2').previous, '<h1>Test</h1>', 'previous')

with subtest('previous_node'):
    # "123"
    is_ok(dom.parse('<p>123<!-- Test --><b>456</b></p>').at('b').previous_node.previous_node, '123', 'previous_node')

    # " Test "
    is_ok(dom.parse('<p>123<!-- Test --><b>456</b></p>').at('b').previous_node.content, ' Test ', 'previous_node')

with subtest('remove'):
    # "<div></div>"
    is_ok(dom.parse('<div><h1>Test</h1></div>').at('h1').remove(), '<div></div>', 'remove')

    # "<p><b>456</b></p>"
    is_ok(dom.parse('<p>123<b>456</b></p>').at('p').child_nodes.first().remove().root, '<p><b>456</b></p>', 'remove')

with subtest('replace'):
    # "<div><h2>123</h2></div>"
    is_ok(dom.parse('<div><h1>Test</h1></div>').at('h1').replace('<h2>123</h2>'), '<div><h2>123</h2></div>', 'replace')

    # "<p><b>123</b></p>"
    is_ok(dom.parse('<p>Test</p>').at('p').child_nodes[0].replace('<b>123</b>').root, '<p><b>123</b></p>', 'replace')

with subtest('root'):
    root = dom.at('b').root
    is_ok(root.type, 'root', 'root')

with subtest('selector'):
    # "ul:nth-child(1) > li:nth-child(2)"
    is_ok(
        dom.parse('<ul><li>Test</li><li>123</li></ul>').find('li').last().selector,
        'ul:nth-child(1) > li:nth-child(2)',
        'selector',
    )

    # "p:nth-child(1) > b:nth-child(1) > i:nth-child(1)"
    is_ok(
        dom.parse('<p><b><i>Test</i></b></p>').at('i').selector,
        'p:nth-child(1) > b:nth-child(1) > i:nth-child(1)',
        'selector',
    )

with subtest('strip'):
    # "<div>Test</div>"
    is_ok(dom.parse('<div><h1>Test</h1></div>').at('h1').strip(), '<div>Test</div>', 'strip')

with subtest('tag'):
    dom = Pyjo.DOM.new('<div><p>A</p><b>B</b></div>').at('div')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # List tag names of child elements
        print(dom.children().map('tag').join('\n'))
    is_ok(output.getvalue(), 'p\nb\n', 'output')

with subtest('text'):
    dom = Pyjo.DOM.new()

    # "bar"
    is_ok(dom.parse('<div>foo<p>bar</p>baz</div>').at('p').text, 'bar', 'text')

    # "foo\nbaz\n"
    is_ok(dom.parse('<div>foo\n<p>bar</p>baz\n</div>').at('div').text, 'foo\nbaz\n', 'text')

with subtest('to_str'):
    # "<b>Test</b>"
    is_ok(dom.parse('<div><b>Test</b></div>').at('div b').to_str(), '<b>Test</b>', 'to_str')

with subtest('tree'):
    tree = dom.tree
    dom.tree = ['root']
    is_ok(dom, '', 'empty tree')
    dom.tree = tree

with subtest('type'):
    # "cdata"
    is_ok(dom.parse('<![CDATA[Test]]>').child_nodes.first().type, 'cdata', 'type')

    # "comment"
    is_ok(dom.parse('<!-- Test -->').child_nodes.first().type, 'comment', 'type')

    # "doctype"
    is_ok(dom.parse('<!DOCTYPE html>').child_nodes.first().type, 'doctype', 'type')

    # "pi"
    is_ok(dom.parse('<?xml version="1.0"?>').child_nodes.first().type, 'pi', 'type')
    dom = Pyjo.DOM.new()

    # "raw"
    is_ok(dom.parse('<script>Test</script>').at('script').child_nodes.first().type, 'raw', 'type')

    # "root"
    is_ok(dom.parse('<p>Test</p>').type, 'root', 'type')

    # "tag"
    is_ok(dom.parse('<p>Test</p>').at('p').type, 'tag', 'type')

    # "text"
    is_ok(dom.parse('<p>Test</p>').at('p').child_nodes.first().type, 'text', 'type')

with subtest('val'):
    dom = Pyjo.DOM.new()

    # "a"
    is_ok(dom.parse('<input name=test value=a>').at('input').val, 'a', 'val')

    # "b"
    is_ok(dom.parse('<textarea>b</textarea>').at('textarea').val, 'b', 'val')

    # "c"
    is_ok(dom.parse('<option value="c">Test</option>').at('option').val, 'c', 'val')

    # "d"
    is_ok(dom.parse('<select><option selected>d</option></select>').at('select').val, 'd', 'val')

    # "e"
    is_ok(dom.parse('<select multiple><option selected>e</option></select>').at('select').val[0], 'e', 'val')

    # "on"
    is_ok(dom.parse('<input name=test type=checkbox>').at('input').val, 'on', 'val')

with subtest('wrap'):
    # "<p>123<b>Test</b></p>"
    is_ok(dom.parse('<b>Test</b>').at('b').wrap('<p>123</p>').root, '<p>123<b>Test</b></p>', 'wrap')

    # "<div><p><b>Test</b></p>123</div>"
    is_ok(
        dom.parse('<b>Test</b>').at('b').wrap('<div><p></p>123</div>').root, '<div><p><b>Test</b></p>123</div>', 'wrap'
    )

    # "<p><b>Test</b></p><p>123</p>"
    is_ok(dom.parse('<b>Test</b>').at('b').wrap('<p></p><p>123</p>').root, '<p><b>Test</b></p><p>123</p>', 'wrap')

    # "<p><b>Test</b></p>"
    is_ok(dom.parse('<p>Test</p>').at('p').child_nodes.first().wrap('<b>').root, '<p><b>Test</b></p>', 'wrap')

with subtest('wrap_content'):
    # "<p><b>123Test</b></p><p></p>"
    is_ok(
        dom.parse('<p>Test<p>').at('p').wrap_content('<b>123</b>').root, '<p><b>123Test</b></p><p></p>', 'wrap_content'
    )

    # "<p><b>Test</b></p><p>123</p>"
    is_ok(dom.parse('<b>Test</b>').wrap_content('<p></p><p>123</p>'), '<p><b>Test</b></p><p>123</p>', 'wrap_content')

with subtest('xml'):
    boolean = dom.xml
    none_ok(boolean, 'auto-detection')
    dom.xml = True
    ok(dom.xml, 'XML')

done_testing()
