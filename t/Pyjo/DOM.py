import Pyjo.DOM
import Pyjo.DOM.HTML

from Pyjo.DOM.HTML import tag_to_html
from Pyjo.Test import *

import re


with subtest('Empty'):
    is_ok(Pyjo.DOM.new(), '', 'right result')
    is_ok(Pyjo.DOM.new(''), '', 'right result')
    is_ok(Pyjo.DOM.new().parse(''), '', 'right result')
    is_ok(Pyjo.DOM.new().at('p'), None, 'no result')
    is_ok(Pyjo.DOM.new().append_content(''), '', 'right result')
    is_ok(Pyjo.DOM.new().all_text, '', 'right result')

with subtest('Simple (basics)'):
    dom = Pyjo.DOM.new('<div><div FOO="0" id="a">A</div><div id="b">B</div></div>')
    is_ok(dom.at('#b').text, 'B', 'right text')
    div = []
    div.extend(dom.find('div[id]').map('text').each())
    is_deeply_ok(div, ['A', 'B'], 'found all div elements with id')
    div = []
    dom.find('div[id]').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'B'], 'found all div elements with id')
    is_ok(dom.at('#a').attr('foo'), '0', 'right attribute')
    is_ok(dom.at('#a').attr()['foo'], '0', 'right attribute')
    is_ok(str(dom), '<div><div foo="0" id="a">A</div><div id="b">B</div></div>', 'right result')

with subtest('Tap into method chain'):
    dom = Pyjo.DOM.new().parse('<div id="a">A</div><div id="b">B</div>')
    is_deeply_ok(dom.find('[id]').map('attr', 'id').each(), ['a', 'b'], 'right result')
    is_ok(dom.tap(lambda e: e.at('#b').remove()), '<div id="a">A</div>', 'right result')

with subtest('Build tree from scratch'):
    is_ok(Pyjo.DOM.new().append_content('<p>').at('p').append_content('0').text, '0', 'right text')

with subtest('Simple nesting with healing (tree structure)'):
    dom = Pyjo.DOM.new("""\
<foo><bar a="b&lt;c">ju<baz a23>s<bazz />t</bar>works</foo>
""")
    is_ok(dom.tree[0], 'root', 'right type')
    is_ok(dom.tree[1][0], 'tag', 'right type')
    is_ok(dom.tree[1][1], 'foo', 'right tag')
    is_deeply_ok(dom.tree[1][2], {}, 'empty attributes')
    is_ok(dom.tree[1][3], dom.tree, 'right parent')
    is_ok(dom.tree[1][4][0], 'tag', 'right type')
    is_ok(dom.tree[1][4][1], 'bar', 'right tag')
    is_deeply_ok(dom.tree[1][4][2], {'a': 'b<c'}, 'right attributes')
    is_ok(dom.tree[1][4][3], dom.tree[1], 'right parent')
    is_ok(dom.tree[1][4][4][0], 'text', 'right type')
    is_ok(dom.tree[1][4][4][1], 'ju', 'right text')
    is_ok(dom.tree[1][4][4][2], dom.tree[1][4], 'right parent')
    is_ok(dom.tree[1][4][5][0], 'tag', 'right type')
    is_ok(dom.tree[1][4][5][1], 'baz', 'right tag')
    is_deeply_ok(dom.tree[1][4][5][2], {'a23': None}, 'right attributes')
    is_ok(dom.tree[1][4][5][3], dom.tree[1][4], 'right parent')
    is_ok(dom.tree[1][4][5][4][0], 'text', 'right type')
    is_ok(dom.tree[1][4][5][4][1], 's', 'right text')
    is_ok(dom.tree[1][4][5][4][2], dom.tree[1][4][5], 'right parent')
    is_ok(dom.tree[1][4][5][5][0], 'tag', 'right type')
    is_ok(dom.tree[1][4][5][5][1], 'bazz', 'right tag')
    is_deeply_ok(dom.tree[1][4][5][5][2], {}, 'empty attributes')
    is_ok(dom.tree[1][4][5][5][3], dom.tree[1][4][5], 'right parent')
    is_ok(dom.tree[1][4][5][6][0], 'text', 'right type')
    is_ok(dom.tree[1][4][5][6][1], 't', 'right text')
    is_ok(dom.tree[1][4][5][6][2], dom.tree[1][4][5], 'right parent')
    is_ok(dom.tree[1][5][0], 'text', 'right type')
    is_ok(dom.tree[1][5][1], 'works', 'right text')
    is_ok(dom.tree[1][5][2], dom.tree[1], 'right parent')
    is_ok(
        str(dom),
        """\
<foo><bar a="b&lt;c">ju<baz a23>s<bazz></bazz>t</baz></bar>works</foo>
""",
        'right result',
    )

with subtest('Select based on parent'):
    dom = Pyjo.DOM.new("""\
  <body>
    <div>test1</div>
    <div><div>test2</div></div>
  <body>
""")
    is_ok(dom.find('body > div')[0].text, 'test1', 'right text')
    is_ok(dom.find('body > div')[1].text, '', 'no content')
    is_ok(dom.find('body > div').get(2), None, 'no result')
    is_ok(dom.find('body > div').size, 2, 'right number of elements')
    is_ok(dom.find('body > div > div')[0].text, 'test2', 'right text')
    is_ok(dom.find('body > div > div').get(1), None, 'no result')
    is_ok(dom.find('body > div > div').size, 1, 'right number of elements')

with subtest('A bit of everything (basic navigation)'):
    dom = Pyjo.DOM.new().parse("""\
<!doctype foo>
<foo bar="ba&lt;z">
  test
  <simple class="working">easy</simple>
  <test foo="bar" id="test" />
  <!-- lala -->
  works well
  <![CDATA[ yada yada]]>
  <?boom lalalala ?>
  <a little bit broken>
  < very broken
  <br />
  more text
</foo>
""")
    ok(not dom.xml, 'XML mode not detected')
    is_ok(dom.tag, None, 'no tag')
    is_ok(dom.attr('foo'), None, 'no attribute')
    is_ok(dom.attr(foo='bar').attr('foo'), None, 'no attribute')
    is_ok(dom.tree[1][0], 'doctype', 'right type')
    is_ok(dom.tree[1][1], ' foo', 'right doctype')
    is_ok(
        str(dom),
        """\
<!DOCTYPE foo>
<foo bar="ba&lt;z">
  test
  <simple class="working">easy</simple>
  <test foo="bar" id="test"></test>
  <!-- lala -->
  works well
  <![CDATA[ yada yada]]>
  <?boom lalalala ?>
  <a bit broken little>
  &lt; very broken
  <br>
  more text
</a></foo>
""",
        'right result',
    )
    simple = dom.at('foo simple.working[class^="wor"]')
    is_ok(
        simple.parent.all_text,
        '\n  test\n  easy\n  \n  \n  works well\n   yada yada\n  \n  \n  < very broken\n  \n  more text\n',
        'right text',
    )
    is_ok(simple.tag, 'simple', 'right tag')
    is_ok(simple.attr('class'), 'working', 'right class attribute')
    is_ok(simple.text, 'easy', 'right text')
    is_ok(simple.parent.tag, 'foo', 'right parent tag')
    is_ok(simple.parent.attr()['bar'], 'ba<z', 'right parent attribute')
    is_ok(simple.parent.children()[1].tag, 'test', 'right sibling')
    is_ok(simple.to_str(), '<simple class="working">easy</simple>', 'stringified right')
    simple.parent.attr(bar='baz').attr({'this': 'works', 'too': 'yea'})
    is_ok(simple.parent.attr('bar'), 'baz', 'right parent attribute')
    is_ok(simple.parent.attr('this'), 'works', 'right parent attribute')
    is_ok(simple.parent.attr('too'), 'yea', 'right parent attribute')
    is_ok(dom.at('test#test').tag, 'test', 'right tag')
    is_ok(dom.at('[class$="ing"]').tag, 'simple', 'right tag')
    is_ok(dom.at('[class="working"]').tag, 'simple', 'right tag')
    is_ok(dom.at('[class$=ing]').tag, 'simple', 'right tag')
    is_ok(dom.at('[class=working][class]').tag, 'simple', 'right tag')
    is_ok(dom.at('foo > simple').next.tag, 'test', 'right tag')
    is_ok(dom.at('foo > simple').next.next.tag, 'a', 'right tag')
    is_ok(dom.at('foo > test').previous.tag, 'simple', 'right tag')
    is_ok(dom.next, None, 'no siblings')
    is_ok(dom.previous, None, 'no siblings')
    is_ok(dom.at('foo > a').next, None, 'no next sibling')
    is_ok(dom.at('foo > simple').previous, None, 'no previous sibling')
    is_deeply_ok(dom.at('simple').ancestors().map('tag').each(), ['foo'], 'right results')
    ok(not dom.at('simple').ancestors().first().xml, 'XML mode not active')

with subtest('Nodes'):
    dom = Pyjo.DOM.new('<!DOCTYPE before><p>test<![CDATA[123]]><!-- 456 --></p><?after?>')
    is_ok(dom.at('p').preceding_nodes.first().content, ' before', 'right content')
    is_ok(dom.at('p').preceding_nodes.size, 1, 'right number of nodes')
    is_ok(dom.at('p').child_nodes.last().preceding_nodes.first().content, 'test', 'right content')
    is_ok(dom.at('p').child_nodes.last().preceding_nodes.last().content, '123', 'right content')
    is_ok(dom.at('p').child_nodes.last().preceding_nodes.size, 2, 'right number of nodes')
    is_ok(dom.preceding_nodes.size, 0, 'no preceding nodes')
    is_ok(dom.at('p').following_nodes.first().content, 'after', 'right content')
    is_ok(dom.at('p').following_nodes.size, 1, 'right number of nodes')
    is_ok(dom.child_nodes.first().following_nodes.first().tag, 'p', 'right tag')
    is_ok(dom.child_nodes.first().following_nodes.last().content, 'after', 'right content')
    is_ok(dom.child_nodes.first().following_nodes.size, 2, 'right number of nodes')
    is_ok(dom.following_nodes.size, 0, 'no following nodes')
    is_ok(dom.at('p').previous_node.content, ' before', 'right content')
    is_ok(dom.at('p').previous_node.previous_node, None, 'no more siblings')
    is_ok(dom.at('p').next_node.content, 'after', 'right content')
    is_ok(dom.at('p').next_node.next_node, None, 'no more siblings')
    is_ok(dom.at('p').child_nodes.last().previous_node.previous_node.content, 'test', 'right content')
    is_ok(dom.at('p').child_nodes.first().next_node.next_node.content, ' 456 ', 'right content')
    is_ok(dom.descendant_nodes[0].type, 'doctype', 'right type')
    is_ok(dom.descendant_nodes[0].content, ' before', 'right content')
    is_ok(dom.descendant_nodes[0], '<!DOCTYPE before>', 'right content')
    is_ok(dom.descendant_nodes[1].tag, 'p', 'right tag')
    is_ok(dom.descendant_nodes[2].type, 'text', 'right type')
    is_ok(dom.descendant_nodes[2].content, 'test', 'right content')
    is_ok(dom.descendant_nodes[5].type, 'pi', 'right type')
    is_ok(dom.descendant_nodes[5].content, 'after', 'right content')
    is_ok(dom.at('p').descendant_nodes[0].type, 'text', 'right type')
    is_ok(dom.at('p').descendant_nodes[0].content, 'test', 'right type')
    is_ok(dom.at('p').descendant_nodes.last().type, 'comment', 'right type')
    is_ok(dom.at('p').descendant_nodes.last().content, ' 456 ', 'right type')
    is_ok(dom.child_nodes[1].child_nodes.first().parent.tag, 'p', 'right tag')
    is_ok(dom.child_nodes[1].child_nodes.first().content, 'test', 'right content')
    is_ok(dom.child_nodes[1].child_nodes.first(), 'test', 'right content')
    is_ok(dom.at('p').child_nodes.first().type, 'text', 'right type')
    is_ok(dom.at('p').child_nodes.first().remove().tag, 'p', 'right tag')
    is_ok(dom.at('p').child_nodes.first().type, 'cdata', 'right type')
    is_ok(dom.at('p').child_nodes.first().content, '123', 'right content')
    is_ok(dom.at('p').child_nodes[1].type, 'comment', 'right type')
    is_ok(dom.at('p').child_nodes[1].content, ' 456 ', 'right content')
    is_ok(dom[0].type, 'doctype', 'right type')
    is_ok(dom[0].content, ' before', 'right content')
    is_ok(dom.child_nodes[2].type, 'pi', 'right type')
    is_ok(dom.child_nodes[2].content, 'after', 'right content')
    is_ok(dom.child_nodes.first().set(content=' again').content, ' again', 'right content')
    is_ok(dom.child_nodes.grep(lambda e: e.type == 'pi').map('remove').first().type, 'root', 'right type')
    is_ok(str(dom), '<!DOCTYPE again><p><![CDATA[123]]><!-- 456 --></p>', 'right result')

with subtest('Modify nodes'):
    dom = Pyjo.DOM.new('<script>la<la>la</script>')
    is_ok(dom.at('script').type, 'tag', 'right type')
    is_ok(dom.at('script')[0].type, 'raw', 'right type')
    is_ok(dom.at('script')[0].content, 'la<la>la', 'right content')
    is_ok(str(dom), '<script>la<la>la</script>', 'right result')
    is_ok(dom.at('script').child_nodes.first().replace('a<b>c</b>1<b>d</b>').tag, 'script', 'right tag')
    is_ok(str(dom), '<script>a<b>c</b>1<b>d</b></script>', 'right result')
    is_ok(dom.at('b').child_nodes.first().append('e').content, 'c', 'right content')
    is_ok(dom.at('b').child_nodes.first().prepend('f').type, 'text', 'right type')
    is_ok(str(dom), '<script>a<b>fce</b>1<b>d</b></script>', 'right result')
    is_ok(dom.at('script').child_nodes.first().following().first().tag, 'b', 'right tag')
    is_ok(dom.at('script').child_nodes.first().next.content, 'fce', 'right content')
    is_ok(dom.at('script').child_nodes.first().previous, None, 'no siblings')
    is_ok(dom.at('script').child_nodes[2].previous.content, 'fce', 'right content')
    is_ok(dom.at('b').child_nodes[1].next, None, 'no siblings')
    is_ok(
        dom.at('script').child_nodes.first().wrap('<i>:)</i>').root,
        '<script><i>:)a</i><b>fce</b>1<b>d</b></script>',
        'right result',
    )
    is_ok(
        dom.at('i').child_nodes.first().wrap_content('<b></b>').root,
        '<script><i>:)a</i><b>fce</b>1<b>d</b></script>',
        'no changes',
    )
    is_ok(
        dom.at('i').child_nodes.first().wrap('<b></b>').root,
        '<script><i><b>:)</b>a</i><b>fce</b>1<b>d</b></script>',
        'right result',
    )
    is_ok(dom.at('b').child_nodes.first().ancestors().map('tag').join(','), 'b,i,script', 'right result')
    is_ok(dom.at('b').child_nodes.first().append_content('g').content, ':)g', 'right content')
    is_ok(dom.at('b').child_nodes.first().prepend_content('h').content, 'h:)g', 'right content')
    is_ok(str(dom), '<script><i><b>h:)g</b>a</i><b>fce</b>1<b>d</b></script>', 'right result')
    is_ok(dom.at('script > b:last-of-type').append('<!--y-->').following_nodes.first().content, 'y', 'right content')
    is_ok(dom.at('i').prepend('z').preceding_nodes.first().content, 'z', 'right content')
    is_ok(dom.at('i').following().last().text, 'd', 'right text')
    is_ok(dom.at('i').following().size, 2, 'right number of following elements')
    is_ok(dom.at('i').following('b:last-of-type').first().text, 'd', 'right text')
    is_ok(dom.at('i').following('b:last-of-type').size, 1, 'right number of following elements')
    is_ok(dom.following().size, 0, 'no following elements')
    is_ok(dom.at('script > b:last-of-type').preceding().first().tag, 'i', 'right tag')
    is_ok(dom.at('script > b:last-of-type').preceding().size, 2, 'right number of preceding elements')
    is_ok(dom.at('script > b:last-of-type').preceding('b').first().tag, 'b', 'right tag')
    is_ok(dom.at('script > b:last-of-type').preceding('b').size, 1, 'right number of preceding elements')
    is_ok(dom.preceding().size, 0, 'no preceding elements')
    is_ok(str(dom), '<script>z<i><b>h:)g</b>a</i><b>fce</b>1<b>d</b><!--y--></script>', 'right result')

with subtest('XML nodes'):
    dom = Pyjo.DOM.new().set(xml=True).parse('<b>test<image /></b>')
    ok(dom.at('b').child_nodes.first().xml, 'XML mode active')
    ok(dom.at('b').child_nodes.first().replace('<br>').child_nodes.first().xml, 'XML mode active')
    is_ok(str(dom), '<b><br /><image /></b>', 'right result')

with subtest('Treating nodes as elements'):
    dom = Pyjo.DOM.new('foo<b>bar</b>baz')
    is_ok(dom.child_nodes.first().child_nodes.size, 0, 'no nodes')
    is_ok(dom.child_nodes.first().descendant_nodes.size, 0, 'no nodes')
    is_ok(dom.child_nodes.first().children().size, 0, 'no children')
    is_ok(dom.child_nodes.first().strip().parent, 'foo<b>bar</b>baz', 'no changes')
    is_ok(dom.child_nodes.first().at('b'), None, 'no result')
    is_ok(dom.child_nodes.first().find('*').size, 0, 'no results')
    ok(not dom.child_nodes.first().matches('*'), 'no match')
    is_deeply_ok(dom.child_nodes.first().attr(), {}, 'no attributes')
    is_ok(dom.child_nodes.first().namespace, None, 'no namespace')
    is_ok(dom.child_nodes.first().tag, None, 'no tag')
    is_ok(dom.child_nodes.first().text, '', 'no text')
    is_ok(dom.child_nodes.first().all_text, '', 'no text')

with subtest('Class and ID'):
    dom = Pyjo.DOM.new('<div id="id" class="class">a</div>')
    is_ok(dom.at('div#id.class').text, 'a', 'right text')

with subtest('Deep nesting (parent combinator)'):
    dom = Pyjo.DOM.new("""\
<html>
  <head>
    <title>Foo</title>
  </head>
  <body>
    <div id="container">
      <div id="header">
        <div id="logo">Hello World</div>
        <div id="buttons">
          <p id="foo">Foo</p>
        </div>
      </div>
      <form>
        <div id="buttons">
          <p id="bar">Bar</p>
        </div>
      </form>
      <div id="content">More stuff</div>
    </div>
  </body>
</html>
""")
    p = dom.find('body > #container > div p[id]')
    is_ok(p[0].attr('id'), 'foo', 'right id attribute')
    is_ok(p.get(1), None, 'no second result')
    is_ok(p.size, 1, 'right number of elements')
    p = []
    div = []
    dom.find('div').each(lambda e, num: div.append(e.attr('id')))
    dom.find('p').each(lambda e, num: p.append(e.attr('id')))
    is_deeply_ok(p, ['foo', 'bar'], 'found all p elements')
    ids = ['container', 'header', 'logo', 'buttons', 'buttons', 'content']
    is_deeply_ok(div, ids, 'found all div elements')
    is_deeply_ok(dom.at('p').ancestors().map('tag').each(), ['div', 'div', 'div', 'body', 'html'], 'right results')
    is_deeply_ok(dom.at('html').ancestors().each(), [], 'no results')
    is_deeply_ok(dom.ancestors().each(), [], 'no results')

with subtest('Script tag'):
    dom = Pyjo.DOM.new("""\
<script charset="utf-8">alert('lalala');</script>
""")
    is_ok(dom.at('script').text, "alert('lalala');", 'right script content')

with subtest('Script tag with HTML comment containing nested script tags'):
    dom = Pyjo.DOM.new('<script> console.log("<!--"); </script>')
    is_ok(dom.at('script').text, ' console.log("<!--"); ', 'right script content')

    dom = Pyjo.DOM.new('<script> console.log("<!-- <script> -->"); </script>')
    is_ok(dom.at('script').text, ' console.log("<!-- <script> -->"); ', 'right script content')

    dom = Pyjo.DOM.new('<script> console.log("<!-- <script> </script>"); </script>')
    is_ok(dom.at('script').text, ' console.log("<!-- <script> </script>"); ', 'right script content')

    dom = Pyjo.DOM.new('<script> console.log("<!-- <script> </script> -->"); </script>')
    is_ok(dom.at('script').text, ' console.log("<!-- <script> </script> -->"); ', 'right script content')

with subtest('Script tag with HTML comment containing stray characters'):
    dom = Pyjo.DOM.new('<script>/* <!-- <foo --> */</script>')
    is_ok(dom.at('script').text, '/* <!-- <foo --> */', 'right script content')

    dom = Pyjo.DOM.new('<script>/* <!-- a-b --> */</script>')
    is_ok(dom.at('script').text, '/* <!-- a-b --> */', 'right script content')

with subtest('HTML5 (unquoted values)'):
    dom = Pyjo.DOM.new('<div id = test foo ="bar" class=tset bar=/baz/ value baz=//>works</div>')
    is_ok(dom.at('#test').text, 'works', 'right text')
    is_ok(dom.at('div').text, 'works', 'right text')
    is_ok(dom.at('[foo=bar][foo="bar"]').text, 'works', 'right text')
    is_ok(dom.at('[foo="ba"]'), None, 'no result')
    is_ok(dom.at('[foo=bar]').text, 'works', 'right text')
    is_ok(dom.at('[foo=ba]'), None, 'no result')
    is_ok(dom.at('.tset').text, 'works', 'right text')
    is_ok(dom.at('[bar=/baz/]').text, 'works', 'right text')
    is_ok(dom.at('[baz=//]').text, 'works', 'right text')
    is_ok(dom.at('[value]').text, 'works', 'right text')
    is_ok(dom.at('[value=baz]'), None, 'no result')

with subtest('HTML1 (single quotes, uppercase tags and whitespace in attributes)'):
    dom = Pyjo.DOM.new("""<DIV id = 'test' foo ='bar' class= "tset">works</DIV>""")
    is_ok(dom.at('#test').text, 'works', 'right text')
    is_ok(dom.at('div').text, 'works', 'right text')
    is_ok(dom.at('[foo="bar"]').text, 'works', 'right text')
    is_ok(dom.at('[foo="ba"]'), None, 'no result')
    is_ok(dom.at('[foo=bar]').text, 'works', 'right text')
    is_ok(dom.at('[foo=ba]'), None, 'no result')
    is_ok(dom.at('.tset').text, 'works', 'right text')

with subtest('Already decoded Unicode snowman and quotes in selector'):
    dom = Pyjo.DOM.new('<div id="snow&apos;m&quot;an">☃</div>')
    is_ok(dom.at('[id="snow\'m\\"an"]').text, '☃', 'right text')
    is_ok(dom.at('[id="snow\'m\\22 an"]').text, '☃', 'right text')
    is_ok(dom.at('[id="snow\'m\\000022an"]').text, '☃', 'right text')
    is_ok(dom.at('[id="snow\'m\\22an"]'), None, 'no result')
    is_ok(dom.at('[id="snow\'m\\21 an"]'), None, 'no result')
    is_ok(dom.at('[id="snow\'m\\000021an"]'), None, 'no result')
    is_ok(dom.at('[id="snow\'m\\000021 an"]'), None, 'no result')
    is_ok(dom.at("[id='snow\\'m\"an']").text, '☃', 'right text')
    is_ok(dom.at("[id='snow\\27m\"an']").text, '☃', 'right text')

with subtest('Unicode and escaped selectors'):
    html = '<html><div id="☃x">Snowman</div><div class="x ♥">Heart</div></html>'
    dom = Pyjo.DOM.new(html)
    is_ok(dom.at('#\\\n\\002603x').text, 'Snowman', 'right text')
    is_ok(dom.at('#\\2603 x').text, 'Snowman', 'right text')
    is_ok(dom.at('#\\\n\\2603 x').text, 'Snowman', 'right text')
    is_ok(dom.at('[id="\\\n\\2603 x"]').text, 'Snowman', 'right text')
    is_ok(dom.at('[id="\\\n\\002603x"]').text, 'Snowman', 'right text')
    is_ok(dom.at('[id="\\\\2603 x"]').text, 'Snowman', 'right text')
    is_ok(dom.at('html #\\\n\\002603x').text, 'Snowman', 'right text')
    is_ok(dom.at('html #\\2603 x').text, 'Snowman', 'right text')
    is_ok(dom.at('html #\\\n\\2603 x').text, 'Snowman', 'right text')
    is_ok(dom.at('html [id="\\\n\\2603 x"]').text, 'Snowman', 'right text')
    is_ok(dom.at('html [id="\\\n\\002603x"]').text, 'Snowman', 'right text')
    is_ok(dom.at('html [id="\\\\2603 x"]').text, 'Snowman', 'right text')
    is_ok(dom.at('#☃x').text, 'Snowman', 'right text')
    is_ok(dom.at('div#☃x').text, 'Snowman', 'right text')
    is_ok(dom.at('html div#☃x').text, 'Snowman', 'right text')
    is_ok(dom.at('[id^="☃"]').text, 'Snowman', 'right text')
    is_ok(dom.at('div[id^="☃"]').text, 'Snowman', 'right text')
    is_ok(dom.at('html div[id^="☃"]').text, 'Snowman', 'right text')
    is_ok(dom.at('html > div[id^="☃"]').text, 'Snowman', 'right text')
    is_ok(dom.at('[id^=☃]').text, 'Snowman', 'right text')
    is_ok(dom.at('div[id^=☃]').text, 'Snowman', 'right text')
    is_ok(dom.at('html div[id^=☃]').text, 'Snowman', 'right text')
    is_ok(dom.at('html > div[id^=☃]').text, 'Snowman', 'right text')
    is_ok(dom.at('.\\\n\\002665').text, 'Heart', 'right text')
    is_ok(dom.at('.\\2665').text, 'Heart', 'right text')
    is_ok(dom.at('html .\\\n\\002665').text, 'Heart', 'right text')
    is_ok(dom.at('html .\\2665').text, 'Heart', 'right text')
    is_ok(dom.at('html [class$="\\\n\\002665"]').text, 'Heart', 'right text')
    is_ok(dom.at('html [class$="\\2665"]').text, 'Heart', 'right text')
    is_ok(dom.at('[class$="\\\n\\002665"]').text, 'Heart', 'right text')
    is_ok(dom.at('[class$="\\2665"]').text, 'Heart', 'right text')
    is_ok(dom.at('.x').text, 'Heart', 'right text')
    is_ok(dom.at('html .x').text, 'Heart', 'right text')
    is_ok(dom.at('.♥').text, 'Heart', 'right text')
    is_ok(dom.at('html .♥').text, 'Heart', 'right text')
    is_ok(dom.at('div.♥').text, 'Heart', 'right text')
    is_ok(dom.at('html div.♥').text, 'Heart', 'right text')
    is_ok(dom.at('[class$="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('div[class$="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('html div[class$="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('html > div[class$="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('[class$=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('div[class$=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('html div[class$=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('html > div[class$=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('[class~="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('div[class~="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('html div[class~="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('html > div[class~="♥"]').text, 'Heart', 'right text')
    is_ok(dom.at('[class~=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('div[class~=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('html div[class~=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('html > div[class~=♥]').text, 'Heart', 'right text')
    is_ok(dom.at('[class~="x"]').text, 'Heart', 'right text')
    is_ok(dom.at('div[class~="x"]').text, 'Heart', 'right text')
    is_ok(dom.at('html div[class~="x"]').text, 'Heart', 'right text')
    is_ok(dom.at('html > div[class~="x"]').text, 'Heart', 'right text')
    is_ok(dom.at('[class~=x]').text, 'Heart', 'right text')
    is_ok(dom.at('div[class~=x]').text, 'Heart', 'right text')
    is_ok(dom.at('html div[class~=x]').text, 'Heart', 'right text')
    is_ok(dom.at('html > div[class~=x]').text, 'Heart', 'right text')
    is_ok(dom.at('html'), html, 'right result')
    is_ok(dom.at('#☃x').parent, html, 'right result')
    is_ok(dom.at('#☃x').root, html, 'right result')
    is_ok(dom.children('html').first(), html, 'right result')
    is_ok(dom.to_str(), html, 'right result')
    is_ok(dom.content, html, 'right result')

with subtest('Looks remotely like HTML'):
    dom = Pyjo.DOM.new('<!DOCTYPE H "-/W/D HT 4/E">☃<title class=test>♥</title>☃')
    is_ok(dom.at('title').text, '♥', 'right text')
    is_ok(dom.at('*').text, '♥', 'right text')
    is_ok(dom.at('.test').text, '♥', 'right text')

with subtest('Replace elements'):
    dom = Pyjo.DOM.new('<div>foo<p>lalala</p>bar</div>')
    is_ok(dom.at('p').replace('<foo>bar</foo>'), '<div>foo<foo>bar</foo>bar</div>', 'right result')
    is_ok(str(dom), '<div>foo<foo>bar</foo>bar</div>', 'right result')
    dom.at('foo').replace(Pyjo.DOM.new('text'))
    is_ok(str(dom), '<div>footextbar</div>', 'right result')
    dom = Pyjo.DOM.new('<div>foo</div><div>bar</div>')
    dom.find('div').each(lambda e, num: e.replace('<p>test</p>'))
    is_ok(str(dom), '<p>test</p><p>test</p>', 'right result')
    dom = Pyjo.DOM.new('<div>foo<p>lalala</p>bar</div>')
    is_ok(dom.replace('♥'), '♥', 'right result')
    is_ok(str(dom), '♥', 'right result')
    dom.replace('<div>foo<p>lalala</p>bar</div>')
    is_ok(str(dom), '<div>foo<p>lalala</p>bar</div>', 'right result')
    is_ok(dom.at('p').replace(''), '<div>foobar</div>', 'right result')
    is_ok(str(dom), '<div>foobar</div>', 'right result')
    is_ok(dom.replace(''), '', 'no result')
    is_ok(str(dom), '', 'no result')
    dom.replace('<div>foo<p>lalala</p>bar</div>')
    is_ok(str(dom), '<div>foo<p>lalala</p>bar</div>', 'right result')
    dom.find('p').map('replace', '')
    is_ok(str(dom), '<div>foobar</div>', 'right result')
    dom = Pyjo.DOM.new('<div>♥</div>')
    dom.at('div').set(content='☃')
    is_ok(str(dom), '<div>☃</div>', 'right result')
    dom = Pyjo.DOM.new('<div>♥</div>')
    dom.at('div').set(content='\u2603')
    is_ok(dom.to_str(), '<div>☃</div>', 'right result')
    is_ok(dom.at('div').replace('<p>♥</p>').root, '<p>♥</p>', 'right result')
    is_ok(dom.to_str(), '<p>♥</p>', 'right result')
    is_ok(dom.replace('<b>whatever</b>').root, '<b>whatever</b>', 'right result')
    is_ok(dom.to_str(), '<b>whatever</b>', 'right result')
    dom.at('b').prepend('<p>foo</p>').append('<p>bar</p>')
    is_ok(str(dom), '<p>foo</p><b>whatever</b><p>bar</p>', 'right result')
    is_ok(dom.find('p').map('remove').first().root.at('b').text, 'whatever', 'right result')
    is_ok(str(dom), '<b>whatever</b>', 'right result')
    is_ok(dom.at('b').strip(), 'whatever', 'right result')
    is_ok(dom.strip(), 'whatever', 'right result')
    is_ok(dom.remove(), '', 'right result')
    dom.replace('A<div>B<p>C<b>D<i><u>E</u></i>F</b>G</p><div>H</div></div>I')
    is_ok(
        dom.find(':not(div):not(i):not(u)').map('strip').first().root,
        'A<div>BCD<i><u>E</u></i>FG<div>H</div></div>I',
        'right result',
    )
    is_ok(dom.at('i').to_str(), '<i><u>E</u></i>', 'right result')
    dom = Pyjo.DOM.new('<div><div>A</div><div>B</div>C</div>')
    is_ok(dom.at('div').at('div').text, 'A', 'right text')
    dom.at('div').find('div').map('strip')
    is_ok(str(dom), '<div>ABC</div>', 'right result')

with subtest('Replace element content'):
    dom = Pyjo.DOM.new('<div>foo<p>lalala</p>bar</div>')
    is_ok(dom.at('p').set(content='bar'), '<p>bar</p>', 'right result')
    is_ok(str(dom), '<div>foo<p>bar</p>bar</div>', 'right result')
    dom.at('p').set(content=Pyjo.DOM.new('text'))
    is_ok(str(dom), '<div>foo<p>text</p>bar</div>', 'right result')
    dom = Pyjo.DOM.new('<div>foo</div><div>bar</div>')
    dom.find('div').each(lambda e, num: e.set(content='<p>test</p>'))
    is_ok(str(dom), '<div><p>test</p></div><div><p>test</p></div>', 'right result')
    dom.find('p').each(lambda e, num: e.set(content=''))
    is_ok(str(dom), '<div><p></p></div><div><p></p></div>', 'right result')
    dom = Pyjo.DOM.new('<div><p id="☃" /></div>')
    dom.at('#☃').set(content='♥')
    is_ok(str(dom), '<div><p id="☃">♥</p></div>', 'right result')
    dom = Pyjo.DOM.new('<div>foo<p>lalala</p>bar</div>')
    dom.set(content='♥')
    is_ok(str(dom), '♥', 'right result')
    is_ok(dom.set(content='<div>foo<p>lalala</p>bar</div>'), '<div>foo<p>lalala</p>bar</div>', 'right result')
    is_ok(str(dom), '<div>foo<p>lalala</p>bar</div>', 'right result')
    is_ok(dom.set(content=''), '', 'no result')
    is_ok(str(dom), '', 'no result')
    dom.set(content='<div>foo<p>lalala</p>bar</div>')
    is_ok(str(dom), '<div>foo<p>lalala</p>bar</div>', 'right result')
    is_ok(dom.at('p').set(content=''), '<p></p>', 'right result')

with subtest('Mixed search and tree walk'):
    dom = Pyjo.DOM.new("""\
<table>
  <tr>
    <td>text1</td>
    <td>text2</td>
  </tr>
</table>
""")
    data = []
    for tr in dom.find('table tr').each():
        for td in tr.children():
            data.extend([td.tag, td.all_text])
    is_ok(data[0], 'td', 'right tag')
    is_ok(data[1], 'text1', 'right text')
    is_ok(data[2], 'td', 'right tag')
    is_ok(data[3], 'text2', 'right text')
    is_ok(len(data), 4, 'no tag')

with subtest('RSS'):
    dom = Pyjo.DOM.new("""\
<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
  <channel>
    <title>Test Blog</title>
    <link>http://blog.example.com</link>
    <description>lalala</description>
    <generator>Mojolicious</generator>
    <item>
      <pubDate>Mon, 12 Jul 2010 20:42:00</pubDate>
      <title>Works!</title>
      <link>http://blog.example.com/test</link>
      <guid>http://blog.example.com/test</guid>
      <description>
        <![CDATA[<p>trololololo>]]>
      </description>
      <my:extension foo:id="works">
        <![CDATA[
          [awesome]]
        ]]>
      </my:extension>
    </item>
  </channel>
</rss>
""")
    ok(dom.xml, 'XML mode detected')
    is_ok(dom.find('rss')[0].attr('version'), '2.0', 'right version')
    is_deeply_ok(dom.at('title').ancestors().map('tag').each(), ['channel', 'rss'], 'right results')
    is_ok(dom.at('extension').attr('foo:id'), 'works', 'right id')
    like_ok(dom.at('[foo\\:id]').text, r'\[awesome\]\]', 'right text')
    like_ok(dom.at('[foo\\:id="works"]').text, r'\[awesome\]\]', 'right text')
    is_ok(dom.find('description')[1].text, '\n        <p>trololololo>\n      ', 'right text')
    is_ok(dom.at('pubDate').text, 'Mon, 12 Jul 2010 20:42:00', 'right text')
    like_ok(dom.at('[foo\\:id*="ork"]').text, r'\[awesome\]\]', 'right text')
    like_ok(dom.at('[foo\\:id*="orks"]').text, r'\[awesome\]\]', 'right text')
    like_ok(dom.at('[foo\\:id*="work"]').text, r'\[awesome\]\]', 'right text')
    like_ok(dom.at('[foo\\:id*="or"]').text, r'\[awesome\]\]', 'right text')
    ok(dom.at('rss').xml, 'XML mode active')
    ok(dom.at('extension').parent.xml, 'XML mode active')
    ok(dom.at('extension').root.xml, 'XML mode active')
    ok(dom.children('rss').first().xml, 'XML mode active')
    ok(dom.at('title').ancestors().first().xml, 'XML mode active')

with subtest('Namespace'):
    dom = Pyjo.DOM.new("""\
<?xml version="1.0"?>
<bk:book xmlns='uri:default-ns'
         xmlns:bk='uri:book-ns'
         xmlns:isbn='uri:isbn-ns'>
  <bk:title>Programming Perl</bk:title>
  <comment>rocks!</comment>
  <nons xmlns=''>
    <section>Nothing</section>
  </nons>
  <meta xmlns='uri:meta-ns'>
    <isbn:number>978-0596000271</isbn:number>
  </meta>
</bk:book>
""")
    ok(dom.xml, 'XML mode detected')
    is_ok(dom.namespace, None, 'no namespace')
    is_ok(dom.at('book comment').namespace, 'uri:default-ns', 'right namespace')
    is_ok(dom.at('book comment').text, 'rocks!', 'right text')
    is_ok(dom.at('book nons section').namespace, '', 'no namespace')
    is_ok(dom.at('book nons section').text, 'Nothing', 'right text')
    is_ok(dom.at('book meta number').namespace, 'uri:isbn-ns', 'right namespace')
    is_ok(dom.at('book meta number').text, '978-0596000271', 'right text')
    is_ok(dom.children('bk\\:book').first()['xmlns'], 'uri:default-ns', 'right attribute')
    is_ok(dom.children('book').first()['xmlns'], 'uri:default-ns', 'right attribute')
    is_ok(dom.children('k\\:book').first(), None, 'no result')
    is_ok(dom.children('ook').first(), None, 'no result')
    is_ok(dom.at('k\\:book'), None, 'no result')
    is_ok(dom.at('ook'), None, 'no result')
    is_ok(dom.at('[xmlns\\:bk]')['xmlns:bk'], 'uri:book-ns', 'right attribute')
    is_ok(dom.at('[s\\:bk]'), None, 'no result')
    is_ok(dom.at('[k]'), None, 'no result')
    is_ok(dom.at('number').ancestors('meta').first()['xmlns'], 'uri:meta-ns', 'right attribute')
    ok(dom.at('nons').matches('book > nons'), 'element did match')
    ok(not dom.at('title').matches('book > nons > section'), 'element did not match')

with subtest('Dots'):
    dom = Pyjo.DOM.new("""\
<?xml version="1.0"?>
<foo xmlns:foo.bar="uri:first">
  <bar xmlns:fooxbar="uri:second">
    <foo.bar:baz>First</fooxbar:baz>
    <fooxbar:ya.da>Second</foo.bar:ya.da>
  </bar>
</foo>
""")
    is_ok(dom.at('foo bar baz').text, 'First\n    ', 'right text')
    is_ok(dom.at('baz').namespace, 'uri:first', 'right namespace')
    is_ok(dom.at('foo bar ya\\.da').text, 'Second\n  ', 'right text')
    is_ok(dom.at('ya\\.da').namespace, 'uri:second', 'right namespace')
    is_ok(dom.at('foo').namespace, None, 'no namespace')
    is_ok(dom.at('[xml\\.s]'), None, 'no result')
    is_ok(dom.at('b\\.z'), None, 'no result')

with subtest('Yadis'):
    dom = Pyjo.DOM.new("""\
<?xml version="1.0" encoding="UTF-8"?>
<XRDS xmlns="xri://$xrds">
  <XRD xmlns="xri://$xrd*($v*2.0)">
    <Service>
      <Type>http://o.r.g/sso/2.0</Type>
    </Service>
    <Service>
      <Type>http://o.r.g/sso/1.0</Type>
    </Service>
  </XRD>
</XRDS>
""")
    ok(dom.xml, 'XML mode detected')
    is_ok(dom.at('XRDS').namespace, 'xri://$xrds', 'right namespace')
    is_ok(dom.at('XRD').namespace, 'xri://$xrd*($v*2.0)', 'right namespace')
    s = dom.find('XRDS XRD Service')
    is_ok(s[0].at('Type').text, 'http://o.r.g/sso/2.0', 'right text')
    is_ok(s[0].namespace, 'xri://$xrd*($v*2.0)', 'right namespace')
    is_ok(s[1].at('Type').text, 'http://o.r.g/sso/1.0', 'right text')
    is_ok(s[1].namespace, 'xri://$xrd*($v*2.0)', 'right namespace')
    is_ok(s.get(2), None, 'no result')
    is_ok(s.size, 2, 'right number of elements')

with subtest('Yadis (roundtrip with namespace)'):
    yadis = """\
<?xml version="1.0" encoding="UTF-8"?>
<xrds:XRDS xmlns="xri://$xrd*($v*2.0)" xmlns:xrds="xri://$xrds">
  <XRD>
    <Service>
      <Type>http://o.r.g/sso/3.0</Type>
    </Service>
    <xrds:Service>
      <Type>http://o.r.g/sso/4.0</Type>
    </xrds:Service>
  </XRD>
  <XRD>
    <Service>
      <Type test="23">http://o.r.g/sso/2.0</Type>
    </Service>
    <Service>
      <Type Test="23" test="24">http://o.r.g/sso/1.0</Type>
    </Service>
  </XRD>
</xrds:XRDS>
"""
    dom = Pyjo.DOM.new(yadis)
    ok(dom.xml, 'XML mode detected')
    is_ok(dom.at('XRDS').namespace, 'xri://$xrds', 'right namespace')
    is_ok(dom.at('XRD').namespace, 'xri://$xrd*($v*2.0)', 'right namespace')
    s = dom.find('XRDS XRD Service')
    is_ok(s[0].at('Type').text, 'http://o.r.g/sso/3.0', 'right text')
    is_ok(s[0].namespace, 'xri://$xrd*($v*2.0)', 'right namespace')
    is_ok(s[1].at('Type').text, 'http://o.r.g/sso/4.0', 'right text')
    is_ok(s[1].namespace, 'xri://$xrds', 'right namespace')
    is_ok(s[2].at('Type').text, 'http://o.r.g/sso/2.0', 'right text')
    is_ok(s[2].namespace, 'xri://$xrd*($v*2.0)', 'right namespace')
    is_ok(s[3].at('Type').text, 'http://o.r.g/sso/1.0', 'right text')
    is_ok(s[3].namespace, 'xri://$xrd*($v*2.0)', 'right namespace')
    is_ok(s.get(4), None, 'no result')
    is_ok(s.size, 4, 'right number of elements')
    is_ok(dom.at('[Test="23"]').text, 'http://o.r.g/sso/1.0', 'right text')
    is_ok(dom.at('[test="23"]').text, 'http://o.r.g/sso/2.0', 'right text')
    is_ok(dom.find('xrds\\:Service > Type')[0].text, 'http://o.r.g/sso/4.0', 'right text')
    is_ok(dom.find('xrds\\:Service > Type').get(1), None, 'no result')
    is_ok(dom.find('xrds\\3AService > Type')[0].text, 'http://o.r.g/sso/4.0', 'right text')
    is_ok(dom.find('xrds\\3AService > Type').get(1), None, 'no result')
    is_ok(dom.find('xrds\\3A Service > Type')[0].text, 'http://o.r.g/sso/4.0', 'right text')
    is_ok(dom.find('xrds\\3A Service > Type').get(1), None, 'no result')
    is_ok(dom.find('xrds\\00003AService > Type')[0].text, 'http://o.r.g/sso/4.0', 'right text')
    is_ok(dom.find('xrds\\00003AService > Type').get(1), None, 'no result')
    is_ok(dom.find('xrds\\00003A Service > Type')[0].text, 'http://o.r.g/sso/4.0', 'right text')
    is_ok(dom.find('xrds\\00003A Service > Type').get(1), None, 'no result')
    is_ok(str(dom), yadis, 'successful roundtrip')

with subtest('Result and iterator order'):
    dom = Pyjo.DOM.new('<a><b>1</b></a><b>2</b><b>3</b>')
    numbers = []
    dom.find('b').each(lambda e, num: numbers.extend([num, e.text]))
    is_deeply_ok(numbers, [1, '1', 2, '2', 3, '3'], 'right order')

with subtest('Attributes on multiple lines'):
    dom = Pyjo.DOM.new("<div test=23 id='a' \n class='x' foo=bar />")
    is_ok(dom.at('div.x').attr('test'), '23', 'right attribute')
    is_ok(dom.at('[foo="bar"]').attr('class'), 'x', 'right attribute')
    is_ok(
        dom.at('div').attr(baz=None).root.to_str(),
        '<div baz class="x" foo="bar" id="a" test="23"></div>',
        'right result',
    )

with subtest('Markup characters in attribute values'):
    dom = Pyjo.DOM.new("""<div id="<a>" \n test='='>Test<div id='><' /></div>""")
    is_ok(dom.at('div[id="<a>"]').attr()['test'], '=', 'right attribute')
    is_ok(dom.at('[id="<a>"]').text, 'Test', 'right text')
    is_ok(dom.at('[id="><"]').attr()['id'], '><', 'right attribute')

with subtest('Empty attributes'):
    dom = Pyjo.DOM.new("""<div test="" test2='' />""")
    is_ok(dom.at('div').attr()['test'], '', 'empty attribute value')
    is_ok(dom.at('div').attr()['test2'], '', 'empty attribute value')
    is_ok(dom.at('[test]').tag, 'div', 'right tag')
    is_ok(dom.at('[test2]').tag, 'div', 'right tag')
    is_ok(dom.at('[test3]'), None, 'no result')
    is_ok(dom.at('[test=""]').tag, 'div', 'right tag')
    is_ok(dom.at('[test2=""]').tag, 'div', 'right tag')
    is_ok(dom.at('[test3=""]'), None, 'no result')

with subtest('Multi-line attribute'):
    dom = Pyjo.DOM.new('<div class="line1\nline2" />')
    is_ok(dom.at('div').attr()['class'], 'line1\nline2', 'multi-line attribute value')
    is_ok(dom.at('.line1').tag, 'div', 'right tag')
    is_ok(dom.at('.line2').tag, 'div', 'right tag')
    is_ok(dom.at('.line3'), None, 'no result')

with subtest('Entities in attributes'):
    dom = Pyjo.DOM.new('<a href="/?foo&lt=bar"></a>')
    is_ok(dom.at('a')['href'], '/?foo&lt=bar', 'right attribute value')
    dom = Pyjo.DOM.new('<a href="/?f&ltoo=bar"></a>')
    is_ok(dom.at('a')['href'], '/?f&ltoo=bar', 'right attribute value')
    dom = Pyjo.DOM.new('<a href="/?f&lt-oo=bar"></a>')
    is_ok(dom.at('a')['href'], '/?f<-oo=bar', 'right attribute value')
    dom = Pyjo.DOM.new('<a href="/?foo=&lt"></a>')
    is_ok(dom.at('a')['href'], '/?foo=<', 'right attribute value')
    dom = Pyjo.DOM.new('<a href="/?f&lt;oo=bar"></a>')
    is_ok(dom.at('a')['href'], '/?f<oo=bar', 'right attribute value')

with subtest('Whitespaces before closing bracket'):
    dom = Pyjo.DOM.new('<div >content</div>')
    ok(dom.at('div'), 'tag found')
    is_ok(dom.at('div').text, 'content', 'right text')
    is_ok(dom.at('div').content, 'content', 'right text')

with subtest('Class with hyphen'):
    dom = Pyjo.DOM.new('<div class="a">A</div><div class="a-1">A1</div>')
    div = []
    dom.find('.a').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A'], 'found first element only')
    div = []
    dom.find('.a-1').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A1'], 'found last element only')

with subtest('Defined but false text'):
    dom = Pyjo.DOM.new('<div><div id="a">A</div><div id="b">B</div></div><div id="0">0</div>')
    div = []
    dom.find('div[id]').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'B', '0'], 'found all div elements with id')

with subtest('Empty tags'):
    dom = Pyjo.DOM.new('<hr /><br/><br id="br"/><br />')
    is_ok(str(dom), '<hr><br><br id="br"><br>', 'right result')
    is_ok(dom.at('br').content, '', 'empty result')

with subtest('Inner XML'):
    dom = Pyjo.DOM.new('<a>xxx<x>x</x>xxx</a>')
    is_ok(dom.at('a').content, 'xxx<x>x</x>xxx', 'right result')
    is_ok(dom.content, '<a>xxx<x>x</x>xxx</a>', 'right result')

with subtest('Multiple selectors'):
    dom = Pyjo.DOM.new('<div id="a">A</div><div id="b">B</div><div id="c">C</div><p>D</p>')
    div = []
    dom.find('p, div').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'B', 'C', 'D'], 'found all elements')
    div = []
    dom.find('#a, #c').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'C'], 'found all div elements with the right ids')
    div = []
    dom.find('div#a, div#b').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'B'], 'found all div elements with the right ids')
    div = []
    dom.find('div[id="a"], div[id="c"]').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'C'], 'found all div elements with the right ids')
    dom = Pyjo.DOM.new('<div id="☃">A</div><div id="b">B</div><div id="♥x">C</div>')
    div = []
    dom.find('#☃, #♥x').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'C'], 'found all div elements with the right ids')
    div = []
    dom.find('div#☃, div#b').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'B'], 'found all div elements with the right ids')
    div = []
    dom.find('div[id="☃"], div[id="♥x"]').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'C'], 'found all div elements with the right ids')

with subtest('Multiple attributes'):
    dom = Pyjo.DOM.new("""\
<div foo="bar" bar="baz">A</div>
<div foo="bar">B</div>
<div foo="bar" bar="baz">C</div>
<div foo="baz" bar="baz">D</div>
""")
    div = []
    dom.find('div[foo="bar"][bar="baz"]').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'C'], 'found all div elements with the right atributes')
    div = []
    dom.find('div[foo^="b"][foo$="r"]').each(lambda e, num: div.append(e.text))
    is_deeply_ok(div, ['A', 'B', 'C'], 'found all div elements with the right atributes')
    is_ok(dom.at('[foo="bar"]').previous, None, 'no previous sibling')
    is_ok(dom.at('[foo="bar"]').next.text, 'B', 'right text')
    is_ok(dom.at('[foo="bar"]').next.previous.text, 'A', 'right text')
    is_ok(dom.at('[foo="bar"]').next.next.next.next, None, 'no next sibling')

with subtest('Pseudo-classes'):
    dom = Pyjo.DOM.new("""\
<form action="/foo">
    <input type="text" name="user" value="test" />
    <input type="checkbox" checked="checked" name="groovy">
    <select name="a">
        <option value="b">b</option>
        <optgroup label="c">
            <option value="d">d</option>
            <option selected="selected" value="e">E</option>
            <option value="f">f</option>
        </optgroup>
        <option value="g">g</option>
        <option selected value="h">H</option>
    </select>
    <input type="submit" value="Ok!" />
    <input type="checkbox" checked name="I">
    <p id="content">test 123</p>
    <p id="no_content"><? test ?><!-- 123 --></p>
</form>
""")
    is_ok(dom.find(':root')[0].tag, 'form', 'right tag')
    is_ok(dom.find('*:root')[0].tag, 'form', 'right tag')
    is_ok(dom.find('form:root')[0].tag, 'form', 'right tag')
    is_ok(dom.find(':root').get(1), None, 'no result')
    is_ok(dom.find(':checked')[0].attr()['name'], 'groovy', 'right name')
    is_ok(dom.find('option:checked')[0].attr()['value'], 'e', 'right value')
    is_ok(dom.find(':checked')[1].text, 'E', 'right text')
    is_ok(dom.find('*:checked')[1].text, 'E', 'right text')
    is_ok(dom.find(':checked')[2].text, 'H', 'right name')
    is_ok(dom.find(':checked')[3].attr()['name'], 'I', 'right name')
    is_ok(dom.find(':checked').get(4), None, 'no result')
    is_ok(dom.find('option[selected]')[0].attr()['value'], 'e', 'right value')
    is_ok(dom.find('option[selected]')[1].text, 'H', 'right text')
    is_ok(dom.find('option[selected]').get(2), None, 'no result')
    is_ok(dom.find(':checked[value="e"]')[0].text, 'E', 'right text')
    is_ok(dom.find('*:checked[value="e"]')[0].text, 'E', 'right text')
    is_ok(dom.find('option:checked[value="e"]')[0].text, 'E', 'right text')
    is_ok(dom.at('optgroup option:checked[value="e"]').text, 'E', 'right text')
    is_ok(dom.at('select option:checked[value="e"]').text, 'E', 'right text')
    is_ok(dom.at('select :checked[value="e"]').text, 'E', 'right text')
    is_ok(dom.at('optgroup > :checked[value="e"]').text, 'E', 'right text')
    is_ok(dom.at('select *:checked[value="e"]').text, 'E', 'right text')
    is_ok(dom.at('optgroup > *:checked[value="e"]').text, 'E', 'right text')
    is_ok(dom.find(':checked[value="e"]').get(1), None, 'no result')
    is_ok(dom.find(':empty')[0].attr()['name'], 'user', 'right name')
    is_ok(dom.find('input:empty')[0].attr()['name'], 'user', 'right name')
    is_ok(dom.at(':empty[type^="ch"]').attr()['name'], 'groovy', 'right name')
    is_ok(dom.at('p').attr()['id'], 'content', 'right attribute')
    is_ok(dom.at('p:empty').attr()['id'], 'no_content', 'right attribute')

with subtest('More pseudo-classes'):
    dom = Pyjo.DOM.new("""\
<ul>
    <li>A</li>
    <li>B</li>
    <li>C</li>
    <li>D</li>
    <li>E</li>
    <li>F</li>
    <li>G</li>
    <li>H</li>
</ul>
""")
    li = []
    dom.find('li:nth-child(odd)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'C', 'E', 'G'], 'found all odd li elements')
    li = []
    dom.find('li:NTH-CHILD(ODD)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'C', 'E', 'G'], 'found all odd li elements')
    li = []
    dom.find('li:nth-last-child(odd)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['B', 'D', 'F', 'H'], 'found all odd li elements')
    is_ok(dom.find(':nth-child(odd)')[0].tag, 'ul', 'right tag')
    is_ok(dom.find(':nth-child(odd)')[1].text, 'A', 'right text')
    is_ok(dom.find(':nth-child(1)')[0].tag, 'ul', 'right tag')
    is_ok(dom.find(':nth-child(1)')[1].text, 'A', 'right text')
    is_ok(dom.find(':nth-last-child(odd)')[0].tag, 'ul', 'right tag')
    is_ok(dom.find(':nth-last-child(odd)').last().text, 'H', 'right text')
    is_ok(dom.find(':nth-last-child(1)')[0].tag, 'ul', 'right tag')
    is_ok(dom.find(':nth-last-child(1)')[1].text, 'H', 'right text')
    li = []
    dom.find('li:nth-child(2n+1)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'C', 'E', 'G'], 'found all odd li elements')
    li = []
    dom.find('li:nth-child(2n + 1)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'C', 'E', 'G'], 'found all odd li elements')
    li = []
    dom.find('li:nth-last-child(2n+1)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['B', 'D', 'F', 'H'], 'found all odd li elements')
    li = []
    dom.find('li:nth-child(even)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['B', 'D', 'F', 'H'], 'found all even li elements')
    li = []
    dom.find('li:NTH-CHILD(EVEN)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['B', 'D', 'F', 'H'], 'found all even li elements')
    li = []
    dom.find('li:nth-last-child( even )').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'C', 'E', 'G'], 'found all even li elements')
    li = []
    dom.find('li:nth-child(2n+2)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['B', 'D', 'F', 'H'], 'found all even li elements')
    li = []
    dom.find('li:nTh-chILd(2N+2)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['B', 'D', 'F', 'H'], 'found all even li elements')
    li = []
    dom.find('li:nth-child( 2n + 2 )').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['B', 'D', 'F', 'H'], 'found all even li elements')
    li = []
    dom.find('li:nth-last-child(2n+2)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'C', 'E', 'G'], 'found all even li elements')
    li = []
    dom.find('li:nth-child(4n+1)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'E'], 'found the right li elements')
    li = []
    dom.find('li:nth-last-child(4n+1)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['D', 'H'], 'found the right li elements')
    li = []
    dom.find('li:nth-child(4n+4)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['D', 'H'], 'found the right li elements')
    li = []
    dom.find('li:nth-last-child(4n+4)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'E'], 'found the right li elements')
    li = []
    dom.find('li:nth-child(4n)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['D', 'H'], 'found the right li elements')
    li = []
    dom.find('li:nth-child( 4n )').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['D', 'H'], 'found the right li elements')
    li = []
    dom.find('li:nth-last-child(4n)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'E'], 'found the right li elements')
    li = []
    dom.find('li:nth-child(5n-2)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['C', 'H'], 'found the right li elements')
    li = []
    dom.find('li:nth-child( 5n - 2 )').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['C', 'H'], 'found the right li elements')
    li = []
    dom.find('li:nth-last-child(5n-2)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'F'], 'found the right li elements')
    li = []
    dom.find('li:nth-child(-n+3)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C'], 'found first three li elements')
    li = []
    dom.find('li:nth-child( -n + 3 )').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C'], 'found first three li elements')
    li = []
    dom.find('li:nth-last-child(-n+3)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['F', 'G', 'H'], 'found last three li elements')
    li = []
    dom.find('li:nth-child(-1n+3)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C'], 'found first three li elements')
    li = []
    dom.find('li:nth-last-child(-1n+3)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['F', 'G', 'H'], 'found first three li elements')
    li = []
    dom.find('li:nth-child(3n)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['C', 'F'], 'found every third li elements')
    li = []
    dom.find('li:nth-last-child(3n)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['C', 'F'], 'found every third li elements')
    li = []
    dom.find('li:NTH-LAST-CHILD(3N)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['C', 'F'], 'found every third li elements')
    li = []
    dom.find('li:Nth-Last-Child(3N)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['C', 'F'], 'found every third li elements')
    li = []
    dom.find('li:nth-child( 3 )').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['C'], 'found third li element')
    li = []
    dom.find('li:nth-last-child( +3 )').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['F'], 'found third last li element')
    li = []
    dom.find('li:nth-child(1n+0)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:nth-child(1n-0)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:nth-child(n+0)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:nth-child(n)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:nth-child(n+0)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:NTH-CHILD(N+0)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:Nth-Child(N+0)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:nth-child(n)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 'found all li elements')
    li = []
    dom.find('li:nth-child(0n+1)').each(lambda e, num: li.append(e.text))
    is_deeply_ok(li, ['A'], 'found first li element')
    is_ok(dom.find('li:nth-child(0n+0)').size, 0, 'no results')
    is_ok(dom.find('li:nth-child(0)').size, 0, 'no results')
    is_ok(dom.find('li:nth-child()').size, 0, 'no results')
    is_ok(dom.find('li:nth-child(whatever)').size, 0, 'no results')
    is_ok(dom.find('li:whatever(whatever)').size, 0, 'no results')

with subtest('Even more pseudo-classes'):
    dom = Pyjo.DOM.new("""\
<ul>
    <li>A</li>
    <p>B</p>
    <li class="test ♥">C</li>
    <p>D</p>
    <li>E</li>
    <li>F</li>
    <p>G</p>
    <li>H</li>
    <li>I</li>
</ul>
<div>
    <div class="☃">J</div>
</div>
<div>
    <a href="http://mojolicious.org">Mojo!</a>
    <div class="☃">K</div>
    <a href="http://mojolicious.org">Mojolicious!</a>
</div>
""")
    e = []
    dom.find('ul :nth-child(odd)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'C', 'E', 'G', 'I'], 'found all odd elements')
    e = []
    dom.find('li:nth-of-type(odd)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'E', 'H'], 'found all odd li elements')
    e = []
    dom.find('ul li:not(:first-child, :last-child)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['C', 'E', 'F', 'H'], 'found all li elements but first/last')
    e = []
    dom.find('ul li:is(:first-child, :last-child)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'I'], 'found first/last li elements')
    e = []
    dom.find('li:nth-last-of-type( odd )').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['C', 'F', 'I'], 'found all odd li elements (counting from end)')
    e = []
    dom.find('p:nth-of-type(odd)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['B', 'G'], 'found all odd p elements')
    e = []
    dom.find('p:nth-last-of-type(odd)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['B', 'G'], 'found all odd p elements (counting from end)')
    e = []
    dom.find('ul :nth-child(1)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A'], 'found first child')
    e = []
    dom.find('ul :first-child').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A'], 'found first child')
    e = []
    dom.find('p:nth-of-type(1)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['B'], 'found first child')
    e = []
    dom.find('p:first-of-type').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['B'], 'found first child')
    e = []
    dom.find('li:nth-of-type(1)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A'], 'found first child')
    e = []
    dom.find('li:first-of-type').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A'], 'found first child')
    e = []
    dom.find('ul :nth-last-child(-n+1)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['I'], 'found last child')
    e = []
    dom.find('ul :last-child').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['I'], 'found last child')
    e = []
    dom.find('p:nth-last-of-type(-n+1)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['G'], 'found last child')
    e = []
    dom.find('p:last-of-type').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['G'], 'found last child')
    e = []
    dom.find('li:nth-last-of-type(-n+1)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['I'], 'found last child')
    e = []
    dom.find('li:last-of-type').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['I'], 'found last child')
    e = []
    dom.find('ul :nth-child(-n+3):not(li)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['B'], 'found first p element')
    e = []
    dom.find('ul :nth-child(-n+3):NOT(li)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['B'], 'found first p element')
    e = []
    dom.find('ul :nth-child(-n+3):not(:first-child)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['B', 'C'], 'found second and third element')
    e = []
    dom.find('ul :nth-child(-n+3):not(.♥)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'B'], 'found first and second element')
    e = []
    dom.find('ul :nth-child(-n+3):not([class$="♥"])').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'B'], 'found first and second element')
    e = []
    dom.find('ul :nth-child(-n+3):not(li[class$="♥"])').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'B'], 'found first and second element')
    e = []
    dom.find('ul :nth-child(-n+3):not([class$="♥"][class^="test"])').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'B'], 'found first and second element')
    e = []
    dom.find('ul :nth-child(-n+3):not(*[class$="♥"])').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['A', 'B'], 'found first and second element')
    e = []
    dom.find('ul :nth-child(-n+3):not(:nth-child(-n+2))').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['C'], 'found third element')
    e = []
    dom.find('ul :nth-child(-n+3):not(:nth-child(1)):not(:nth-child(2))').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['C'], 'found third element')
    e = []
    dom.find(':only-child').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['J'], 'found only child')
    e = []
    dom.find('div :only-of-type').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['J', 'K'], 'found only child')
    e = []
    dom.find('div:only-child').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['J'], 'found only child')
    e = []
    dom.find('div div:only-of-type').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['J', 'K'], 'found only child')
    e = []
    dom.find('div :nth-child(-n+2)').each(lambda n, num: e.append(n.text))
    is_deeply_ok(e, ['J', 'Mojo!', 'K'], 'found first two children of each div')

with subtest('Links'):
    dom = Pyjo.DOM.new("""\
<a>A</a>
<a href=/>B</a>
<link rel=C>
<link href=/ rel=D>
<area alt=E>
<area href=/ alt=F>
<div href=borked>very borked</div>
""")
    is_ok(dom.find(':any-link').map(lambda e: e.tag).join(','), 'a,link,area', 'right tags')
    is_ok(dom.find(':link').map(lambda e: e.tag).join(','), 'a,link,area', 'right tags')
    is_ok(dom.find(':visited').map(lambda e: e.tag).join(','), 'a,link,area', 'right tags')
    is_ok(dom.at('a:link').text, 'B', 'right result')
    is_ok(dom.at('a:any-link').text, 'B', 'right result')
    is_ok(dom.at('a:visited').text, 'B', 'right result')
    is_ok(dom.at('link:any-link')['rel'], 'D', 'right result')
    is_ok(dom.at('link:link')['rel'], 'D', 'right result')
    is_ok(dom.at('link:visited')['rel'], 'D', 'right result')
    is_ok(dom.at('area:link')['alt'], 'F', 'right result')
    is_ok(dom.at('area:any-link')['alt'], 'F', 'right result')
    is_ok(dom.at('area:visited')['alt'], 'F', 'right result')

with subtest('Sibling combinator'):
    dom = Pyjo.DOM.new("""\
<ul>
    <li>A</li>
    <p>B</p>
    <li>C</li>
</ul>
<h1>D</h1>
<p id="♥">E</p>
<p id="☃">F<b>H</b></p>
<div>G</div>
""")
    is_ok(dom.at('li ~ p').text, 'B', 'right text')
    is_ok(dom.at('li + p').text, 'B', 'right text')
    is_ok(dom.at('h1 ~ p ~ p').text, 'F', 'right text')
    is_ok(dom.at('h1 + p ~ p').text, 'F', 'right text')
    is_ok(dom.at('h1 ~ p + p').text, 'F', 'right text')
    is_ok(dom.at('h1 + p + p').text, 'F', 'right text')
    is_ok(dom.at('h1  +  p+p').text, 'F', 'right text')
    is_ok(dom.at('ul > li ~ li').text, 'C', 'right text')
    is_ok(dom.at('ul li ~ li').text, 'C', 'right text')
    is_ok(dom.at('ul>li~li').text, 'C', 'right text')
    is_ok(dom.at('ul li li'), None, 'no result')
    is_ok(dom.at('ul ~ li ~ li'), None, 'no result')
    is_ok(dom.at('ul + li ~ li'), None, 'no result')
    is_ok(dom.at('ul > li + li'), None, 'no result')
    is_ok(dom.at('h1 ~ div').text, 'G', 'right text')
    is_ok(dom.at('h1 + div'), None, 'no result')
    is_ok(dom.at('p + div').text, 'G', 'right text')
    is_ok(dom.at('ul + h1 + p + p + div').text, 'G', 'right text')
    is_ok(dom.at('ul + h1 ~ p + div').text, 'G', 'right text')
    is_ok(dom.at('h1 ~ #♥').text, 'E', 'right text')
    is_ok(dom.at('h1 + #♥').text, 'E', 'right text')
    is_ok(dom.at('#♥~#☃').text, 'F', 'right text')
    is_ok(dom.at('#♥+#☃').text, 'F', 'right text')
    is_ok(dom.at('#♥+#☃>b').text, 'H', 'right text')
    is_ok(dom.at('#♥ > #☃'), None, 'no result')
    is_ok(dom.at('#♥ #☃'), None, 'no result')
    is_ok(dom.at('#♥ + #☃ + :nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ ~ #☃ + :nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ + #☃ ~ :nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ ~ #☃ ~ :nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ + :nth-last-child(2)').text, 'F', 'right text')
    is_ok(dom.at('#♥ ~ :nth-last-child(2)').text, 'F', 'right text')
    is_ok(dom.at('#♥ + #☃ + *:nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ ~ #☃ + *:nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ + #☃ ~ *:nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ ~ #☃ ~ *:nth-last-child(1)').text, 'G', 'right text')
    is_ok(dom.at('#♥ + *:nth-last-child(2)').text, 'F', 'right text')
    is_ok(dom.at('#♥ ~ *:nth-last-child(2)').text, 'F', 'right text')
    ok(dom.at('#♥').matches('h1 + p'), 'match')
    ok(not dom.at('#☃').matches('h1 + p'), 'no match')
    ok(not dom.at('h1').matches('h1 + p'), 'no match')
    ok(dom.at('#☃').matches('h1 ~ p'), 'match')
    ok(dom.at('#♥').matches('h1 ~ p'), 'match')
    ok(not dom.at('div').matches('h1 ~ p'), 'no match')
    ok(not dom.matches('h1 + p'), 'no match')

with subtest('Whitespace as descendant combinator'):
    dom = Pyjo.DOM.new('<ul> <li>Ax1</li> </ul>')
    is_ok(dom.at('ul li').text, 'Ax1', 'space combinator')
    is_ok(dom.at('ul\tli').text, 'Ax1', 'tab combinator')
    is_ok(dom.at('ul \tli').text, 'Ax1', 'space + tab combinator')
    is_ok(dom.at('ul\t li').text, 'Ax1', 'tab + space combinator')
    is_ok(dom.at('ul\t\tli').text, 'Ax1', 'multiple tab combinator')
    is_ok(dom.at('ul\nli').text, 'Ax1', 'newline combinator')
    is_ok(dom.at('ul\rli').text, 'Ax1', 'carriage return combinator')
    is_ok(dom.at('ul\fli').text, 'Ax1', 'form feed combinator')

    multi = Pyjo.DOM.new('<ul><li>A</li><li>B</li></ul>')
    is_deeply_ok(multi.find('ul\tli').map('text').to_list(), ['A', 'B'], 'find with tab combinator')

    child = Pyjo.DOM.new('<ul><li>Ax1</li></ul>')
    is_ok(child.at('ul\t>\tli').text, 'Ax1', 'tabs around child combinator')
    is_ok(child.at('ul\n>\nli').text, 'Ax1', 'newlines around child combinator')

with subtest('Scoped selectors'):
    dom = Pyjo.DOM.new("""\
<p>Zero</p>
<div>
  <p>One</p>
  <p>Two</p>
  <p><a href="#">Link</a></p>
</div>
<div>
  <p>Three</p>
  <p>Four</p>
  <i>Six</i>
</div>
<p>Five</p>
""")
    is_ok(dom.at('div p').at(':scope').text, 'One', 'right text')
    is_ok(dom.at('div').at(':scope p').text, 'One', 'right text')
    is_ok(dom.at('div').at(':scope > p').text, 'One', 'right text')
    is_ok(dom.at('div').at('> p').text, 'One', 'right text')
    is_ok(dom.at('div p').at('+ p').text, 'Two', 'right text')
    is_ok(dom.at('div p').at('~ p').text, 'Two', 'right text')
    is_ok(dom.at('div p').at('~ p a').text, 'Link', 'right text')
    is_ok(dom.at('div').at(':scope a').text, 'Link', 'right text')
    is_ok(dom.at('div').at(':scope > a'), None, 'no result')
    is_ok(dom.at('div').at(':scope > p > a').text, 'Link', 'right text')
    is_ok(dom.find('div').last().at(':scope p').text, 'Three', 'right text')
    is_ok(dom.find('div').last().at(':scope > p').text, 'Three', 'right text')
    is_ok(dom.find('div').last().at('> p').text, 'Three', 'right text')
    is_ok(dom.at('div p').at(':scope + p').text, 'Two', 'right text')
    is_ok(dom.at('div').at(':scope > p:nth-child(2), p a').text, 'Two', 'right text')
    is_ok(dom.at('div').at('p, :scope > p:nth-child(2)').text, 'One', 'right text')
    is_ok(dom.at('div').at('p:not(:scope > *)').text, 'Zero', 'right text')
    is_ok(dom.at('div p:nth-child(2)').at('*:is(:scope)').text, 'Two', 'right text')
    is_ok(dom.at('div').at('div p, ~ p').text, 'Five', 'right text')
    is_ok(dom.at('> p').text, 'Zero', 'right text')
    is_ok(dom.at(':scope'), None, 'no result')
    is_ok(dom.at(':scope p').text, 'Zero', 'right text')
    is_ok(dom.at(':scope div p').text, 'One', 'right text')
    is_ok(dom.at(':scope p a').text, 'Link', 'right text')
    is_ok(dom.at('> p').at('p ~ :scope'), None, 'no result')
    is_ok(dom.at('> p:last-child').at('p ~ :scope').text, 'Five', 'righ text')
    is_ok(dom.at('p:has(+ i)').text, 'Four', 'right text')
    is_ok(dom.at('p:has(:scope ~ i)').text, 'Three', 'right text')
    is_ok(dom.at('div:has(i) p').text, 'Three', 'right text')
    is_ok(dom.at('div:has(> i) p').text, 'Three', 'right text')
    is_ok(dom.find('div:not(:has(i)) > p').last().all_text, 'Link', 'right text')
    is_ok(dom.find('div:has(:not(p)) > p').last().all_text, 'Four', 'right text')

with subtest('Text matching'):
    dom = Pyjo.DOM.new("""\
<p>Zero</p>
<div>
  <p>One&lt;Two&gt;</p>
  <div>Two<!-- Three -->Four</div>
  <p>Five Six<a href="#">Seven</a>Eight</p>
</div>
""")
    is_ok(dom.at(':text(ero)').text, 'Zero', 'right text')
    is_ok(dom.at(':text(Zero)').text, 'Zero', 'right text')
    is_ok(dom.at('p:text(Zero)').text, 'Zero', 'right text')
    is_ok(dom.at('div:text(Zero)'), None, 'no result')
    is_ok(dom.at('p:text(w)').text, 'One<Two>', 'right text')
    is_ok(dom.at(':text(<Two>)').text, 'One<Two>', 'right text')
    is_ok(dom.at(':text(Sev)').text, 'Seven', 'right text')
    is_ok(dom.at(':text(/^Seven$/)').text, 'Seven', 'right text')
    is_ok(dom.at('p a:text(even)').text, 'Seven', 'right text')
    is_ok(dom.at(':text(v) :text(e)').text, 'Seven', 'right text')
    is_ok(dom.at(':text(eight)').all_text, 'Five SixSevenEight', 'right text')
    is_ok(dom.at(':text(/Ei.ht/)').all_text, 'Five SixSevenEight', 'right text')
    is_ok(dom.at(':text(/(?i:ei.ht)/)').all_text, 'Five SixSevenEight', 'right text')
    is_ok(dom.at(':text(v) :text(x)'), None, 'no result')
    is_ok(dom.at('div:text(x)'), None, 'no result')
    is_ok(dom.at(':text(three)'), None, 'no result')
    is_ok(dom.at(':text(/three/)'), None, 'no result')
    is_ok(dom.at(':text(/zero/)'), None, 'no result')
    is_ok(dom.at(':text(/zero/)'), None, 'no result')

with subtest('Adding nodes'):
    dom = Pyjo.DOM.new("""\
<ul>
    <li>A</li>
    <p>B</p>
    <li>C</li>
</ul>
<div>D</div>
""")
    dom.at('li').append('<p>A1</p>23')
    is_ok(
        str(dom),
        """\
<ul>
    <li>A</li><p>A1</p>23
    <p>B</p>
    <li>C</li>
</ul>
<div>D</div>
""",
        'right result',
    )
    dom.at('li').prepend('24').prepend('<div>A-1</div>25')
    is_ok(
        str(dom),
        """\
<ul>
    24<div>A-1</div>25<li>A</li><p>A1</p>23
    <p>B</p>
    <li>C</li>
</ul>
<div>D</div>
""",
        'right result',
    )
    is_ok(dom.at('div').text, 'A-1', 'right text')
    is_ok(dom.at('iv'), None, 'no result')
    is_ok(dom.prepend('l').prepend('alal').prepend('a').type, 'root', 'right type')
    is_ok(
        str(dom),
        """\
<ul>
    24<div>A-1</div>25<li>A</li><p>A1</p>23
    <p>B</p>
    <li>C</li>
</ul>
<div>D</div>
""",
        'no changes',
    )
    is_ok(dom.append('lalala').type, 'root', 'right type')
    is_ok(
        str(dom),
        """\
<ul>
    24<div>A-1</div>25<li>A</li><p>A1</p>23
    <p>B</p>
    <li>C</li>
</ul>
<div>D</div>
""",
        'no changes',
    )
    dom.find('div').each(lambda e, num: e.append('works'))
    is_ok(
        str(dom),
        """\
<ul>
    24<div>A-1</div>works25<li>A</li><p>A1</p>23
    <p>B</p>
    <li>C</li>
</ul>
<div>D</div>works
""",
        'right result',
    )
    dom.at('li').prepend_content('A3<p>A2</p>').prepend_content('A4')
    is_ok(dom.at('li').text, 'A4A3A', 'right text')
    is_ok(
        str(dom),
        """\
<ul>
    24<div>A-1</div>works25<li>A4A3<p>A2</p>A</li><p>A1</p>23
    <p>B</p>
    <li>C</li>
</ul>
<div>D</div>works
""",
        'right result',
    )
    dom.find('li')[1].append_content('<p>C2</p>C3').append_content(' C4').append_content('C5')
    is_ok(dom.find('li')[1].text, 'CC3 C4C5', 'right text')
    is_ok(
        str(dom),
        """\
<ul>
    24<div>A-1</div>works25<li>A4A3<p>A2</p>A</li><p>A1</p>23
    <p>B</p>
    <li>C<p>C2</p>C3 C4C5</li>
</ul>
<div>D</div>works
""",
        'right result',
    )

with subtest('Optional "head" and "body" tags'):
    dom = Pyjo.DOM.new("""\
<html>
  <head>
    <title>foo</title>
  <body>bar
""")
    is_ok(dom.at('html > head > title').text, 'foo', 'right text')
    is_ok(dom.at('html > body').text, 'bar\n', 'right text')

with subtest('Optional "li" tag'):
    dom = Pyjo.DOM.new("""\
<ul>
  <li>
    <ol>
      <li>F
      <li>G
    </ol>
  <li>A</li>
  <LI>B
  <li>C</li>
  <li>D
  <li>E
</ul>
""")
    is_ok(dom.find('ul > li > ol > li')[0].text, 'F\n      ', 'right text')
    is_ok(dom.find('ul > li > ol > li')[1].text, 'G\n    ', 'right text')
    is_ok(dom.find('ul > li')[1].text, 'A', 'right text')
    is_ok(dom.find('ul > li')[2].text, 'B\n  ', 'right text')
    is_ok(dom.find('ul > li')[3].text, 'C', 'right text')
    is_ok(dom.find('ul > li')[4].text, 'D\n  ', 'right text')
    is_ok(dom.find('ul > li')[5].text, 'E\n', 'right text')

with subtest('Optional "p" tag'):
    dom = Pyjo.DOM.new("""\
<div>
  <p>A</p>
  <P>B
  <p>C</p>
  <p>D<div>X</div>
  <p>E<img src="foo.png">
  <p>F<br>G
  <p>H
</div>
""")
    is_ok(dom.find('div > p')[0].text, 'A', 'right text')
    is_ok(dom.find('div > p')[1].text, 'B\n  ', 'right text')
    is_ok(dom.find('div > p')[2].text, 'C', 'right text')
    is_ok(dom.find('div > p')[3].text, 'D', 'right text')
    is_ok(dom.find('div > p')[4].text, 'E\n  ', 'right text')
    is_ok(dom.find('div > p')[5].text, 'FG\n  ', 'right text')
    is_ok(dom.find('div > p')[6].text, 'H\n', 'right text')
    is_ok(dom.find('div > p > p').get(0), None, 'no results')
    is_ok(dom.at('div > p > img').attr()['src'], 'foo.png', 'right attribute')
    is_ok(dom.at('div > div').text, 'X', 'right text')

with subtest('Optional "dt" and "dd" tags'):
    dom = Pyjo.DOM.new("""\
<dl>
  <dt>A</dt>
  <DD>B
  <dt>C</dt>
  <dd>D
  <dt>E
  <dd>F
</dl>
""")
    is_ok(dom.find('dl > dt')[0].text, 'A', 'right text')
    is_ok(dom.find('dl > dd')[0].text, 'B\n  ', 'right text')
    is_ok(dom.find('dl > dt')[1].text, 'C', 'right text')
    is_ok(dom.find('dl > dd')[1].text, 'D\n  ', 'right text')
    is_ok(dom.find('dl > dt')[2].text, 'E\n  ', 'right text')
    is_ok(dom.find('dl > dd')[2].text, 'F\n', 'right text')

with subtest('Optional "rp" and "rt" tags'):
    dom = Pyjo.DOM.new("""\
<ruby>
  <rp>A</rp>
  <RT>B
  <rp>C</rp>
  <rt>D
  <rp>E
  <rt>F
</ruby>
""")
    is_ok(dom.find('ruby > rp')[0].text, 'A', 'right text')
    is_ok(dom.find('ruby > rt')[0].text, 'B\n  ', 'right text')
    is_ok(dom.find('ruby > rp')[1].text, 'C', 'right text')
    is_ok(dom.find('ruby > rt')[1].text, 'D\n  ', 'right text')
    is_ok(dom.find('ruby > rp')[2].text, 'E\n  ', 'right text')
    is_ok(dom.find('ruby > rt')[2].text, 'F\n', 'right text')

with subtest('Optional "optgroup" and "option" tags'):
    dom = Pyjo.DOM.new("""\
<div>
  <optgroup>A
    <option id="foo">B
    <option>C</option>
    <option>D
  <OPTGROUP>E
    <option>F
  <optgroup>G
    <option>H
</div>
""")
    is_ok(dom.find('div > optgroup')[0].text, 'A\n    \n    ', 'right text')
    is_ok(dom.find('div > optgroup > #foo')[0].text, 'B\n    ', 'right text')
    is_ok(dom.find('div > optgroup > option')[1].text, 'C', 'right text')
    is_ok(dom.find('div > optgroup > option')[2].text, 'D\n  ', 'right text')
    is_ok(dom.find('div > optgroup')[1].text, 'E\n    ', 'right text')
    is_ok(dom.find('div > optgroup > option')[3].text, 'F\n  ', 'right text')
    is_ok(dom.find('div > optgroup')[2].text, 'G\n    ', 'right text')
    is_ok(dom.find('div > optgroup > option')[4].text, 'H\n', 'right text')

with subtest('Optional "colgroup" tag'):
    dom = Pyjo.DOM.new("""\
<table>
  <col id=morefail>
  <col id=fail>
  <colgroup>
    <col id=foo>
    <col class=foo>
  <colgroup>
    <col id=bar>
</table>
""")
    is_ok(dom.find('table > col')[0].attr()['id'], 'morefail', 'right attribute')
    is_ok(dom.find('table > col')[1].attr()['id'], 'fail', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[0].attr()['id'], 'foo', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[1].attr()['class'], 'foo', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[2].attr()['id'], 'bar', 'right attribute')

with subtest('Optional "thead", "tbody", "tfoot", "tr", "th" and "td" tags'):
    dom = Pyjo.DOM.new("""\
<table>
  <thead>
    <tr>
      <th>A</th>
      <th>D
  <tfoot>
    <tr>
      <td>C
  <tbody>
    <tr>
      <td>B
</table>
""")
    is_ok(dom.at('table > thead > tr > th').text, 'A', 'right text')
    is_ok(dom.find('table > thead > tr > th')[1].text, 'D\n  ', 'right text')
    is_ok(dom.at('table > tbody > tr > td').text, 'B\n', 'right text')
    is_ok(dom.at('table > tfoot > tr > td').text, 'C\n  ', 'right text')

with subtest('Optional "colgroup", "thead", "tbody", "tr", "th" and "td" tags'):
    dom = Pyjo.DOM.new("""\
<table>
  <col id=morefail>
  <col id=fail>
  <colgroup>
    <col id=foo />
    <col class=foo>
  <colgroup>
    <col id=bar>
  </colgroup>
  <thead>
    <tr>
      <th>A</th>
      <th>D
  <tbody>
    <tr>
      <td>B
  <tbody>
    <tr>
      <td>E
</table>
""")
    is_ok(dom.find('table > col')[0].attr()['id'], 'morefail', 'right attribute')
    is_ok(dom.find('table > col')[1].attr()['id'], 'fail', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[0].attr()['id'], 'foo', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[1].attr()['class'], 'foo', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[2].attr()['id'], 'bar', 'right attribute')
    is_ok(dom.at('table > thead > tr > th').text, 'A', 'right text')
    is_ok(dom.find('table > thead > tr > th')[1].text, 'D\n  ', 'right text')
    is_ok(dom.at('table > tbody > tr > td').text, 'B\n  ', 'right text')
    is_ok(dom.find('table > tbody > tr > td').map('text').join('\n'), 'B\n  \nE\n', 'right text')

with subtest('Optional "colgroup", "tbody", "tr", "th" and "td" tags'):
    dom = Pyjo.DOM.new("""\
<table>
  <colgroup>
    <col id=foo />
    <col class=foo>
  <colgroup>
    <col id=bar>
  </colgroup>
  <tbody>
    <tr>
      <td>B
</table>
""")
    is_ok(dom.find('table > colgroup > col')[0].attr()['id'], 'foo', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[1].attr()['class'], 'foo', 'right attribute')
    is_ok(dom.find('table > colgroup > col')[2].attr()['id'], 'bar', 'right attribute')
    is_ok(dom.at('table > tbody > tr > td').text, 'B\n', 'right text')

with subtest('Optional "tr" and "td" tags'):
    dom = Pyjo.DOM.new("""\
<table>
    <tr>
      <td>A
      <td>B</td>
    <tr>
      <td>C
    </tr>
    <tr>
      <td>D
</table>
""")
    is_ok(dom.find('table > tr > td')[0].text, 'A\n      ', 'right text')
    is_ok(dom.find('table > tr > td')[1].text, 'B', 'right text')
    is_ok(dom.find('table > tr > td')[2].text, 'C\n    ', 'right text')
    is_ok(dom.find('table > tr > td')[3].text, 'D\n', 'right text')

with subtest('Real world table'):
    dom = Pyjo.DOM.new("""\
<html>
  <head>
    <title>Real World!</title>
  <body>
    <p>Just a test
    <table class=RealWorld>
      <thead>
        <tr>
          <th class=one>One
          <th class=two>Two
          <th class=three>Three
          <th class=four>Four
      <tbody>
        <tr>
          <td class=alpha>Alpha
          <td class=beta>Beta
          <td class=gamma><a href="#gamma">Gamma</a>
          <td class=delta>Delta
        <tr>
          <td class=alpha>Alpha Two
          <td class=beta>Beta Two
          <td class=gamma><a href="#gamma-two">Gamma Two</a>
          <td class=delta>Delta Two
    </table>
""")
    is_ok(dom.find('html > head > title')[0].text, 'Real World!', 'right text')
    is_ok(dom.find('html > body > p')[0].text, 'Just a test\n    ', 'right text')
    is_ok(dom.find('p')[0].text, 'Just a test\n    ', 'right text')
    is_ok(dom.find('thead > tr > .three')[0].text, 'Three\n          ', 'right text')
    is_ok(dom.find('thead > tr > .four')[0].text, 'Four\n      ', 'right text')
    is_ok(dom.find('tbody > tr > .beta')[0].text, 'Beta\n          ', 'right text')
    is_ok(dom.find('tbody > tr > .gamma')[0].text, '\n          ', 'no text')
    is_ok(dom.find('tbody > tr > .gamma > a')[0].text, 'Gamma', 'right text')
    is_ok(dom.find('tbody > tr > .alpha')[1].text, 'Alpha Two\n          ', 'right text')
    is_ok(dom.find('tbody > tr > .gamma > a')[1].text, 'Gamma Two', 'right text')
    following = dom.find('tr > td:nth-child(1)').map('following', ':nth-child(even)').flatten().map('all_text').each()
    elements = ['Beta\n          ', 'Delta\n        ', 'Beta Two\n          ', 'Delta Two\n    ']
    is_deeply_ok(following, elements, 'right results')

with subtest('Real world list'):
    dom = Pyjo.DOM.new("""\
<html>
  <head>
    <title>Real World!</title>
  <body>
    <ul>
      <li>
        Test
        <br>
        123
        <p>

      <li>
        Test
        <br>
        321
        <p>
      <li>
        Test
        3
        2
        1
        <p>
    </ul>
""")
    is_ok(dom.find('html > head > title')[0].text, 'Real World!', 'right text')
    is_ok(dom.find('body > ul > li')[0].text, '\n        Test\n        \n        123\n        ', 'right text')
    is_ok(dom.find('body > ul > li > p')[0].text, '\n\n      ', 'no text')
    is_ok(dom.find('body > ul > li')[1].text, '\n        Test\n        \n        321\n        ', 'right text')
    is_ok(dom.find('body > ul > li > p')[1].text, '\n      ', 'no text')
    is_ok(
        dom.find('body > ul > li')[1].all_text, '\n        Test\n        \n        321\n        \n      ', 'right text'
    )
    is_ok(dom.find('body > ul > li > p')[1].all_text, '\n      ', 'no text')
    is_ok(dom.find('body > ul > li')[2].text, '\n        Test\n        3\n        2\n        1\n        ', 'right text')
    is_ok(dom.find('body > ul > li > p')[2].text, '\n    ', 'no text')
    is_ok(dom.find('body > ul > li')[2].all_text, '\n        Test\n        3\n        2\n        1\n        \n    ')
    is_ok(dom.find('body > ul > li > p')[2].all_text, '\n    ', 'no text')

with subtest('Advanced whitespace trimming (punctuation)'):
    dom = Pyjo.DOM.new("""\
<html>
  <head>
    <title>Real World!</title>
  <body>
    <div>foo <strong>bar</strong>.</div>
    <div>foo<strong>, bar</strong>baz<strong>; yada</strong>.</div>
    <div>foo<strong>: bar</strong>baz<strong>? yada</strong>!</div>
""")
    is_ok(dom.find('html > head > title')[0].text, 'Real World!', 'right text')
    is_ok(dom.find('body > div')[0].all_text, 'foo bar.', 'right text')
    is_ok(dom.find('body > div')[1].all_text, 'foo, barbaz; yada.', 'right text')
    is_ok(dom.find('body > div')[1].text, 'foobaz.', 'right text')
    is_ok(dom.find('body > div')[2].all_text, 'foo: barbaz? yada!', 'right text')
    is_ok(dom.find('body > div')[2].text, 'foobaz!', 'right text')

with subtest('Real world JavaScript and CSS'):
    dom = Pyjo.DOM.new("""\
<html>
  <head>
    <style test=works>#style { foo: style('<test>'); }</style>
    <script>
      if (a < b) {
        alert('<123>');
      }
    </script>
  <body>Foo!</body>
""")
    is_ok(dom.find('html > body')[0].text, 'Foo!', 'right text')
    is_ok(dom.find('html > head > style')[0].text, "#style { foo: style('<test>'); }", 'right text')
    is_ok(
        dom.find('html > head > script')[0].text,
        "\n      if (a < b) {\n        alert('<123>');\n      }\n    ",
        'right text',
    )

with subtest('More real world JavaScript'):
    dom = Pyjo.DOM.new("""\
<!DOCTYPE html>
<html>
  <head>
    <title>Foo</title>
    <script src="/js/one.js"></script>
    <script src="/js/two.js"></script>
    <script src="/js/three.js"></script>
  </head>
  <body>Bar</body>
</html>
""")
    is_ok(dom.at('title').text, 'Foo', 'right text')
    is_ok(dom.find('html > head > script')[0].attr('src'), '/js/one.js', 'right attribute')
    is_ok(dom.find('html > head > script')[1].attr('src'), '/js/two.js', 'right attribute')
    is_ok(dom.find('html > head > script')[2].attr('src'), '/js/three.js', 'right attribute')
    is_ok(dom.find('html > head > script')[2].text, '', 'no text')
    is_ok(dom.at('html > body').text, 'Bar', 'right text')

with subtest('Even more real world JavaScript'):
    dom = Pyjo.DOM.new("""\
<!DOCTYPE html>
<html>
  <head>
    <title>Foo</title>
    <script src="/js/one.js"></script>
    <script src="/js/two.js"></script>
    <script src="/js/three.js">
  </head>
  <body>Bar</body>
</html>
""")
    is_ok(dom.at('title').text, 'Foo', 'right text')
    is_ok(dom.find('html > head > script')[0].attr('src'), '/js/one.js', 'right attribute')
    is_ok(dom.find('html > head > script')[1].attr('src'), '/js/two.js', 'right attribute')
    is_ok(dom.find('html > head > script')[2].attr('src'), '/js/three.js', 'right attribute')
    is_ok(dom.find('html > head > script')[2].text, '\n  </head>\n  <body>Bar</body>\n</html>\n', 'raw content to EOF')

with subtest('Inline DTD'):
    dom = Pyjo.DOM.new("""\
<?xml version="1.0"?>
<!-- This is a Test! -->
  <!DOCTYPE root [
    <!ELEMENT root (#PCDATA)>
    <!ATTLIST root att CDATA #REQUIRED>
  ]>
<root att="test">
  <![CDATA[<hello>world</hello>]]>
</root>
""")
    ok(dom.xml, 'XML mode detected')
    is_ok(dom.at('root').attr('att'), 'test', 'right attribute')
    is_ok(
        dom.tree[5][1],
        ' root [\n    <!ELEMENT root (#PCDATA)>\n    <!ATTLIST root att CDATA #REQUIRED>\n  ]',
        'right doctype',
    )
    is_ok(dom.at('root').text, '\n  <hello>world</hello>\n', 'right text')
    dom = Pyjo.DOM.new("""\
<!doctype book
  SYSTEM "usr.dtd"
  [
    <!ENTITY test "yeah">
  ]>
<foo />
""")
    is_ok(
        dom.tree[1][1],
        ' book\n  SYSTEM "usr.dtd"\n  [\n    <!ENTITY test "yeah"',
        'right doctype (ends at first ">" in HTML)',
    )
    is_ok(dom.tree[2][1], '\n  ]>\n', 'right text')
    ok(not dom.xml, 'XML mode not detected')
    is_ok(dom.at('foo'), '<foo></foo>', 'right element')
    dom = Pyjo.DOM.new("""\
<?xml version="1.0" encoding = 'utf-8'?>
  <!DOCTYPE foo [
    <!ELEMENT foo ANY>
    <!ATTLIST foo xml:lang CDATA #IMPLIED>
    <!ENTITY % e SYSTEM "myentities.ent">
    %myentities;
  ]  >
<foo xml:lang="de">Check!</fOo>
""")
    ok(dom.xml, 'XML mode detected')
    is_ok(
        dom.tree[3][1],
        ' foo [\n    <!ELEMENT foo ANY>\n    <!ATTLIST foo xml:lang CDATA #IMPLIED>\n'
        '    <!ENTITY % e SYSTEM "myentities.ent">\n    %myentities;\n  ]  ',
        'right doctype',
    )
    is_ok(dom.at('foo').attr()['xml:lang'], 'de', 'right attribute')
    is_ok(dom.at('foo').text, 'Check!\n', 'right text')
    dom = (
        Pyjo.DOM.new()
        .set(xml=True)
        .parse("""\
<!DOCTYPE TESTSUITE PUBLIC "my.dtd" 'mhhh' [
    <!ELEMENT foo ANY>
    <!ATTLIST foo bar ENTITY 'true'>
    <!ENTITY system_entities SYSTEM 'systems.xml'>
    <!ENTITY leertaste '&#32;'>
    <!-- This is a comment -->
    <!NOTATION hmmm SYSTEM "hmmm">
  ]   >
<?check for-nothing?>
<foo bar='false'>&leertaste;!!!</foo>
""")
    )
    is_ok(
        dom.tree[1][1],
        " TESTSUITE PUBLIC \"my.dtd\" 'mhhh' [\n    <!ELEMENT foo ANY>\n    <!ATTLIST foo bar ENTITY 'true'>\n"
        "    <!ENTITY system_entities SYSTEM 'systems.xml'>\n    <!ENTITY leertaste '&#32;'>\n"
        '    <!-- This is a comment -->\n    <!NOTATION hmmm SYSTEM "hmmm">\n  ]   ',
        'right doctype',
    )
    is_ok(dom.at('foo').attr('bar'), 'false', 'right attribute')

with subtest('Broken "font" block and useless end tags'):
    dom = Pyjo.DOM.new("""\
<html>
  <head><title>Test</title></head>
  <body>
    <table>
      <tr><td><font>test</td></font></tr>
      </tr>
    </table>
  </body>
</html>
""")
    is_ok(dom.at('html > head > title').text, 'Test', 'right text')
    is_ok(dom.at('html body table tr td > font').text, 'test', 'right text')

with subtest('Different broken "font" block'):
    dom = Pyjo.DOM.new("""\
<html>
  <head><title>Test</title></head>
  <body>
    <font>
    <table>
      <tr>
        <td>test1<br></td></font>
        <td>test2<br>
    </table>
  </body>
</html>
""")
    is_ok(dom.at('html > head > title').text, 'Test', 'right text')
    is_ok(dom.find('html > body > font > table > tr > td')[0].text, 'test1', 'right text')
    is_ok(dom.find('html > body > font > table > tr > td')[1].text, 'test2\n    ', 'right text')

with subtest('Broken "font" and "div" blocks'):
    dom = Pyjo.DOM.new("""\
<html>
  <head><title>Test</title></head>
  <body>
    <font>
    <div>test1<br>
      <div>test2<br></font>
    </div>
  </body>
</html>
""")
    is_ok(dom.at('html head title').text, 'Test', 'right text')
    is_ok(dom.at('html body font > div').text, 'test1\n      \n  ', 'right text')
    is_ok(dom.at('html body font > div > div').text, 'test2\n    ', 'right text')

with subtest('Broken "div" blocks'):
    dom = Pyjo.DOM.new("""\
<html>
<head><title>Test</title></head>
<body>
  <div>
  <table>
    <tr><td><div>test</td></div></tr>
    </div>
  </table>
</body>
</html>
""")
    is_ok(dom.at('html head title').text, 'Test', 'right text')
    is_ok(dom.at('html body div table tr td > div').text, 'test', 'right text')

with subtest('And another broken "font" block'):
    dom = Pyjo.DOM.new("""\
<html>
  <head><title>Test</title></head>
  <body>
    <table>
      <tr>
        <td><font><br>te<br>st<br>1</td></font>
        <td>x1<td><img>tes<br>t2</td>
        <td>x2<td><font>t<br>est3</font></td>
      </tr>
    </table>
  </body>
</html>
""")
    is_ok(dom.at('html > head > title').text, 'Test', 'right text')
    is_ok(dom.find('html body table tr > td > font')[0].text, 'test1', 'right text')
    is_ok(dom.find('html body table tr > td')[1].text, 'x1', 'right text')
    is_ok(dom.find('html body table tr > td')[2].text, 'test2', 'right text')
    is_ok(dom.find('html body table tr > td')[3].text, 'x2', 'right text')
    is_ok(dom.find('html body table tr > td').get(5), None, 'no result')
    is_ok(dom.find('html body table tr > td').size, 5, 'right number of elements')
    is_ok(dom.find('html body table tr > td > font')[1].text, 'test3', 'right text')
    is_ok(dom.find('html body table tr > td > font').get(2), None, 'no result')
    is_ok(dom.find('html body table tr > td > font').size, 2, 'right number of elements')
    is_ok(
        dom,
        """\
<html>
  <head><title>Test</title></head>
  <body>
    <table>
      <tr>
        <td><font><br>te<br>st<br>1</font></td>
        <td>x1</td><td><img>tes<br>t2</td>
        <td>x2</td><td><font>t<br>est3</font></td>
      </tr>
    </table>
  </body>
</html>
""",
        'right result',
    )

with subtest('A collection of wonderful screwups'):
    dom = Pyjo.DOM.new("""\
<!DOCTYPE html>
<html lang="en">
  <head><title>Wonderful Screwups</title></head>
  <body id="screw-up">
    <div>
      <div class="ewww">
        <a href="/test" target='_blank'><img src="/test.png"></a>
        <a href='/real bad' screwup: http://localhost/bad' target='_blank'>
          <img src="/test2.png">
      </div>
      </mt:If>
    </div>
    <b>>la<>la<<>>la<</b>
  </body>
</html>
""")
    is_ok(dom.at('#screw-up > b').text, '>la<>la<<>>la<', 'right text')
    is_ok(dom.at('#screw-up .ewww > a > img').attr('src'), '/test.png', 'right attribute')
    is_ok(dom.find('#screw-up .ewww > a > img')[1].attr('src'), '/test2.png', 'right attribute')
    is_ok(dom.find('#screw-up .ewww > a > img').get(2), None, 'no result')
    is_ok(dom.find('#screw-up .ewww > a > img').size, 2, 'right number of elements')

with subtest('Broken "br" tag'):
    dom = Pyjo.DOM.new('<br< abc abc abc abc abc abc abc abc<p>Test</p>')
    is_ok(dom.at('p').text, 'Test', 'right text')

with subtest('Modifying an XML document'):
    dom = Pyjo.DOM.new("""\
<?xml version='1.0' encoding='UTF-8'?>
<XMLTest />
""")
    ok(dom.xml, 'XML mode detected')
    dom.at('XMLTest').set(content='<Element />')
    element = dom.at('Element')
    is_ok(element.tag, 'Element', 'right tag')
    ok(element.xml, 'XML mode active')
    element = dom.at('XMLTest').children()[0]
    is_ok(element.tag, 'Element', 'right child')
    is_ok(element.parent.tag, 'XMLTest', 'right parent')
    ok(element.root.xml, 'XML mode active')
    dom.replace('<XMLTest2 /><XMLTest3 just="works" />')
    ok(dom.xml, 'XML mode active')
    dom.at('XMLTest2')['foo'] = None
    is_ok(dom, '<XMLTest2 foo="foo" /><XMLTest3 just="works" />', 'right result')

with subtest('Ensure HTML semantics'):
    ok(not Pyjo.DOM.new().set(xml=None).parse('<?xml version="1.0"?>').xml, 'XML mode not detected')
    dom = Pyjo.DOM.new().set(xml=False).parse('<?xml version="1.0"?><br><div>Test</div>')
    is_ok(dom.at('div:root').text, 'Test', 'right text')

with subtest('Ensure XML semantics'):
    ok(Pyjo.DOM.new().set(xml=True).parse('<foo />').xml, 'XML mode active')
    dom = Pyjo.DOM.new("""\
<?xml version='1.0' encoding='UTF-8'?>
<script>
  <table>
    <td>
      <tr><thead>foo<thead></tr>
    </td>
    <td>
      <tr><thead>bar<thead></tr>
    </td>
  </table>
</script>
""")
    is_ok(dom.find('table > td > tr > thead')[0].text, 'foo', 'right text')
    is_ok(dom.find('script > table > td > tr > thead')[1].text, 'bar', 'right text')
    is_ok(dom.find('table > td > tr > thead').get(2), None, 'no result')
    is_ok(dom.find('table > td > tr > thead').size, 2, 'right number of elements')

with subtest('Ensure XML semantics again'):
    dom = (
        Pyjo.DOM.new()
        .set(xml=True)
        .parse("""\
<table>
  <td>
    <tr><thead>foo<thead></tr>
  </td>
  <td>
    <tr><thead>bar<thead></tr>
  </td>
</table>
""")
    )
    is_ok(dom.find('table > td > tr > thead')[0].text, 'foo', 'right text')
    is_ok(dom.find('table > td > tr > thead')[1].text, 'bar', 'right text')
    is_ok(dom.find('table > td > tr > thead').get(2), None, 'no result')
    is_ok(dom.find('table > td > tr > thead').size, 2, 'right number of elements')

with subtest('Nested tables'):
    dom = Pyjo.DOM.new("""\
<table id="foo">
  <tr>
    <td>
      <table id="bar">
        <tr>
          <td>baz</td>
        </tr>
      </table>
    </td>
  </tr>
</table>
""")
    is_ok(dom.find('#foo > tr > td > #bar > tr >td')[0].text, 'baz', 'right text')
    is_ok(dom.find('table > tr > td > table > tr >td')[0].text, 'baz', 'right text')

with subtest('Nested find'):
    dom = Pyjo.DOM.new().parse("""\
<c>
  <a>foo</a>
  <b>
    <a>bar</a>
    <c>
      <a>baz</a>
      <d>
        <a>yada</a>
      </d>
    </c>
  </b>
</c>
""")
    results = []
    dom.find('b').each(lambda e, num: e.find('a').each(lambda e, num: results.append(e.text)))
    is_deeply_ok(results, ['bar', 'baz', 'yada'], 'right results')
    results = []
    dom.find('a').each(lambda e, num: results.append(e.text))
    is_deeply_ok(results, ['foo', 'bar', 'baz', 'yada'], 'right results')
    results = []
    dom.find('b').each(lambda e, num: e.find('c a').each(lambda e, num: results.append(e.text)))
    is_deeply_ok(results, ['baz', 'yada'], 'right results')
    is_ok(dom.at('b').at('a').text, 'bar', 'right text')
    is_ok(dom.at('c > b > a').text, 'bar', 'right text')
    is_ok(dom.at('b').at('c > b > a'), None, 'no result')

with subtest('Direct hash access to attributes in XML mode'):
    dom = (
        Pyjo.DOM.new()
        .set(xml=True)
        .parse("""\
<a id="one">
  <B class="two" test>
    foo
    <c id="three">bar</c>
    <c ID="four">baz</c>
  </B>
</a>
""")
    )
    ok(dom.xml, 'XML mode active')
    is_ok(dom.at('a')['id'], 'one', 'right attribute')
    is_deeply_ok(sorted(dom.at('a').attr()), ['id'], 'right attributes')
    is_ok(dom.at('a').at('B').text, '\n    foo\n    \n    \n  ', 'right text')
    is_ok(dom.at('B')['class'], 'two', 'right attribute')
    is_deeply_ok(sorted(dom.at('a B').attr()), ['class', 'test'], 'right attributes')
    is_ok(dom.find('a B c')[0].text, 'bar', 'right text')
    is_ok(dom.find('a B c')[0]['id'], 'three', 'right attribute')
    is_deeply_ok(sorted(dom.find('a B c')[0].attr()), ['id'], 'right attributes')
    is_ok(dom.find('a B c')[1].text, 'baz', 'right text')
    is_ok(dom.find('a B c')[1]['ID'], 'four', 'right attribute')
    is_deeply_ok(sorted(dom.find('a B c')[1].attr()), ['ID'], 'right attributes')
    is_ok(dom.find('a B c').get(2), None, 'no result')
    is_ok(dom.find('a B c').size, 2, 'right number of elements')
    results = []
    dom.find('a B c').each(lambda e, num: results.append(e.text))
    is_deeply_ok(results, ['bar', 'baz'], 'right results')
    is_ok(dom.find('a B c').join('\n'), '<c id="three">bar</c>\n<c ID="four">baz</c>', 'right result')
    is_deeply_ok(list(dom.attr()), [], 'root has no attributes')
    is_ok(dom.find('#nothing').join(), '', 'no result')

with subtest('Direct hash access to attributes in HTML mode'):
    dom = Pyjo.DOM.new("""\
<a id="one">
  <B class="two" test>
    foo
    <c id="three">bar</c>
    <c ID="four">baz</c>
  </B>
</a>
""")
    ok(not dom.xml, 'XML mode not active')
    is_ok(dom.at('a')['id'], 'one', 'right attribute')
    is_deeply_ok(sorted(dom.at('a').attr()), ['id'], 'right attributes')
    is_ok(dom.at('a').at('b').text, '\n    foo\n    \n    \n  ', 'right text')
    is_ok(dom.at('b')['class'], 'two', 'right attribute')
    is_deeply_ok(sorted(dom.at('a b').attr()), ['class', 'test'], 'right attributes')
    is_ok(dom.find('a b c')[0].text, 'bar', 'right text')
    is_ok(dom.find('a b c')[0]['id'], 'three', 'right attribute')
    is_deeply_ok(sorted(dom.find('a b c')[0].attr()), ['id'], 'right attributes')
    is_ok(dom.find('a b c')[1].text, 'baz', 'right text')
    is_ok(dom.find('a b c')[1]['id'], 'four', 'right attribute')
    is_deeply_ok(sorted(dom.find('a b c')[1].attr()), ['id'], 'right attributes')
    is_ok(dom.find('a b c').get(2), None, 'no result')
    is_ok(dom.find('a b c').size, 2, 'right number of elements')
    results = []
    dom.find('a b c').each(lambda e, num: results.append(e.text))
    is_deeply_ok(results, ['bar', 'baz'], 'right results')
    is_ok(dom.find('a b c').join('\n'), '<c id="three">bar</c>\n<c id="four">baz</c>', 'right result')
    is_deeply_ok(list(dom.attr()), [], 'root has no attributes')
    is_ok(dom.find('#nothing').join(), '', 'no result')

with subtest('Append and prepend content'):
    dom = Pyjo.DOM.new('<a><b>Test<c /></b></a>')
    dom.at('b').append_content('<d />')
    is_ok(dom.children()[0].tag, 'a', 'right tag')
    is_ok(dom.all_text, 'Test', 'right text')
    is_ok(dom.at('c').parent.tag, 'b', 'right tag')
    is_ok(dom.at('d').parent.tag, 'b', 'right tag')
    dom.at('b').prepend_content('<e>Mojo</e>')
    is_ok(dom.at('e').parent.tag, 'b', 'right tag')
    is_ok(dom.all_text, 'MojoTest', 'right text')

with subtest('Wrap elements'):
    dom = Pyjo.DOM.new('<a>Test</a>')
    is_ok(str(dom), '<a>Test</a>', 'right result')
    is_ok(dom.wrap('<b></b>').type, 'root', 'right type')
    is_ok(str(dom), '<a>Test</a>', 'no changes')
    is_ok(dom.at('a').wrap('<b></b>').type, 'tag', 'right type')
    is_ok(str(dom), '<b><a>Test</a></b>', 'right result')
    is_ok(dom.at('b').strip().at('a').wrap('A').tag, 'a', 'right tag')
    is_ok(str(dom), '<a>Test</a>', 'right result')
    is_ok(dom.at('a').wrap('<b></b>').tag, 'a', 'right tag')
    is_ok(str(dom), '<b><a>Test</a></b>', 'right result')
    is_ok(dom.at('a').wrap('C<c><d>D</d><e>E</e></c>F').parent.tag, 'd', 'right tag')
    is_ok(str(dom), '<b>C<c><d>D<a>Test</a></d><e>E</e></c>F</b>', 'right result')

with subtest('Wrap content'):
    dom = Pyjo.DOM.new('<a>Test</a>')
    is_ok(dom.at('a').wrap_content('A').tag, 'a', 'right tag')
    is_ok(str(dom), '<a>Test</a>', 'right result')
    is_ok(dom.wrap_content('<b></b>').type, 'root', 'right type')
    is_ok(str(dom), '<b><a>Test</a></b>', 'right result')
    is_ok(dom.at('b').strip().at('a').set(tag='e:a').wrap_content('1<b c="d"></b>').tag, 'e:a', 'right tag')
    is_ok(str(dom), '<e:a>1<b c="d">Test</b></e:a>', 'right result')
    is_ok(dom.at('a').wrap_content('C<c><d>D</d><e>E</e></c>F').parent.type, 'root', 'right type')
    is_ok(str(dom), '<e:a>C<c><d>D1<b c="d">Test</b></d><e>E</e></c>F</e:a>', 'right result')

with subtest('Broken "div" in "td"'):
    dom = Pyjo.DOM.new("""\
<table>
  <tr>
    <td><div id="A"></td>
    <td><div id="B"></td>
  </tr>
</table>
""")
    is_ok(dom.find('table tr td')[0].at('div')['id'], 'A', 'right attribute')
    is_ok(dom.find('table tr td')[1].at('div')['id'], 'B', 'right attribute')
    is_ok(dom.find('table tr td').get(2), None, 'no result')
    is_ok(dom.find('table tr td').size, 2, 'right number of elements')
    is_ok(
        str(dom),
        """\
<table>
  <tr>
    <td><div id="A"></div></td>
    <td><div id="B"></div></td>
  </tr>
</table>
""",
        'right result',
    )

with subtest('Form values'):
    dom = Pyjo.DOM.new("""\
<form action="/foo">
  <p>Test</p>
  <input type="text" name="a" value="A" />
  <input type="checkbox" name="q">
  <input type="checkbox" checked name="b" value="B">
  <input type="radio" name="r">
  <input type="radio" checked name="c" value="C">
  <input name="s">
  <input type="checkbox" name="t" value="">
  <input type=text name="u">
  <select multiple name="f">
    <option value="F">G</option>
    <optgroup>
      <option>H</option>
      <option selected>I</option>
      <option selected disabled>V</option>
    </optgroup>
    <option value="J" selected>K</option>
    <optgroup disabled>
      <option selected>I2</option>
    </optgroup>
  </select>
  <select name="n"><option>N</option></select>
  <select multiple name="q"><option>Q</option></select>
  <select name="y" disabled>
    <option selected>Y</option>
  </select>
  <select name="d">
    <option selected>R</option>
    <option selected>D</option>
  </select>
  <textarea name="m">M</textarea>
  <button name="o" value="O">No!</button>
  <input type="submit" name="p" value="P" />
</form>
""")
    is_ok(dom.at('p').val, None, 'no value')
    is_ok(dom.at('input').val, 'A', 'right value')
    is_ok(dom.at('input:checked').val, 'B', 'right value')
    is_ok(dom.at('input:checked[type=radio]').val, 'C', 'right value')
    is_deeply_ok(dom.at('select').val, ['I', 'J'], 'right values')
    is_ok(dom.at('select option').val, 'F', 'right value')
    is_ok(dom.at('select optgroup option:not([selected])').val, 'H', 'right value')
    is_ok(dom.find('select')[1].at('option').val, 'N', 'right value')
    is_ok(dom.find('select')[1].val, None, 'no value')
    is_ok(dom.find('select')[2].val, None, 'no value')
    is_ok(dom.find('select')[2].at('option').val, 'Q', 'right value')
    is_ok(dom.at('select[disabled]').val, 'Y', 'right value')
    is_ok(dom.find('select').last().val, 'D', 'right value')
    is_ok(dom.find('select').last().at('option').val, 'R', 'right value')
    is_ok(dom.at('textarea').val, 'M', 'right value')
    is_ok(dom.at('button').val, 'O', 'right value')
    is_ok(dom.at('form').find('input').last().val, 'P', 'right value')
    is_ok(dom.at('input[name=q]').val, 'on', 'right value')
    is_ok(dom.at('input[name=r]').val, 'on', 'right value')
    is_ok(dom.at('input[name=s]').val, None, 'no value')
    is_ok(dom.at('input[name=t]').val, '', 'right value')
    is_ok(dom.at('input[name=u]').val, None, 'no value')

with subtest('PoCo example with whitespace-sensitive text'):
    dom = Pyjo.DOM.new("""\
<?xml version="1.0" encoding="UTF-8"?>
<response>
  <entry>
    <id>1286823</id>
    <displayName>Homer Simpson</displayName>
    <addresses>
      <type>home</type>
      <formatted><![CDATA[742 Evergreen Terrace
Springfield, VT 12345 USA]]></formatted>
    </addresses>
  </entry>
  <entry>
    <id>1286822</id>
    <displayName>Marge Simpson</displayName>
    <addresses>
      <type>home</type>
      <formatted>742 Evergreen Terrace
Springfield, VT 12345 USA</formatted>
    </addresses>
  </entry>
</response>
""")
    is_ok(dom.find('entry')[0].at('displayName').text, 'Homer Simpson', 'right text')
    is_ok(dom.find('entry')[0].at('id').text, '1286823', 'right text')
    is_ok(dom.find('entry')[0].at('addresses').children('type')[0].text, 'home', 'right text')
    is_ok(
        dom.find('entry')[0].at('addresses formatted').text,
        '742 Evergreen Terrace\nSpringfield, VT 12345 USA',
        'right text',
    )
    is_ok(dom.find('entry')[1].at('displayName').text, 'Marge Simpson', 'right text')
    is_ok(dom.find('entry')[1].at('id').text, '1286822', 'right text')
    is_ok(dom.find('entry')[1].at('addresses').children('type')[0].text, 'home', 'right text')
    is_ok(
        dom.find('entry')[1].at('addresses formatted').text,
        '742 Evergreen Terrace\nSpringfield, VT 12345 USA',
        'right text',
    )
    is_ok(dom.find('entry').get(2), None, 'no result')
    is_ok(dom.find('entry').size, 2, 'right number of elements')

with subtest('Find attribute with hyphen in name and value'):
    dom = Pyjo.DOM.new("""\
<html>
  <head><meta http-equiv="content-type" content="text/html"></head>
</html>
""")
    is_ok(dom.find('[http-equiv]')[0]['content'], 'text/html', 'right attribute')
    is_ok(dom.find('[http-equiv]').get(1), None, 'no result')
    is_ok(dom.find('[http-equiv="content-type"]')[0]['content'], 'text/html', 'right attribute')
    is_ok(dom.find('[http-equiv="content-type"]').get(1), None, 'no result')
    is_ok(dom.find('[http-equiv^="content-"]')[0]['content'], 'text/html', 'right attribute')
    is_ok(dom.find('[http-equiv^="content-"]').get(1), None, 'no result')
    is_ok(dom.find('head > [http-equiv$="-type"]')[0]['content'], 'text/html', 'right attribute')
    is_ok(dom.find('head > [http-equiv$="-type"]').get(1), None, 'no result')

with subtest('Find "0" attribute value'):
    dom = Pyjo.DOM.new("""\
<a accesskey="0">Zero</a>
<a accesskey="1">O&gTn&gte</a>
""")
    is_ok(dom.find('a[accesskey]')[0].text, 'Zero', 'right text')
    is_ok(dom.find('a[accesskey]')[1].text, 'O&gTn>e', 'right text')
    is_ok(dom.find('a[accesskey]').get(2), None, 'no result')
    is_ok(dom.find('a[accesskey=0]')[0].text, 'Zero', 'right text')
    is_ok(dom.find('a[accesskey=0]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey^=0]')[0].text, 'Zero', 'right text')
    is_ok(dom.find('a[accesskey^=0]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey$=0]')[0].text, 'Zero', 'right text')
    is_ok(dom.find('a[accesskey$=0]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey~=0]')[0].text, 'Zero', 'right text')
    is_ok(dom.find('a[accesskey~=0]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey*=0]')[0].text, 'Zero', 'right text')
    is_ok(dom.find('a[accesskey*=0]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey|=0]')[0].text, 'Zero', 'right text')
    is_ok(dom.find('a[accesskey|=0]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey=1]')[0].text, 'O&gTn>e', 'right text')
    is_ok(dom.find('a[accesskey=1]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey^=1]')[0].text, 'O&gTn>e', 'right text')
    is_ok(dom.find('a[accesskey^=1]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey$=1]')[0].text, 'O&gTn>e', 'right text')
    is_ok(dom.find('a[accesskey$=1]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey~=1]')[0].text, 'O&gTn>e', 'right text')
    is_ok(dom.find('a[accesskey~=1]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey*=1]')[0].text, 'O&gTn>e', 'right text')
    is_ok(dom.find('a[accesskey*=1]').get(1), None, 'no result')
    is_ok(dom.find('a[accesskey|=1]')[0].text, 'O&gTn>e', 'right text')
    is_ok(dom.find('a[accesskey|=1]').get(1), None, 'no result')
    is_ok(dom.at('a[accesskey*="."]'), None, 'no result')

with subtest('Empty attribute value'):
    dom = Pyjo.DOM.new("""\
<foo bar=>
  test
</foo>
<bar>after</bar>
""")
    is_ok(dom.tree[0], 'root', 'right type')
    is_ok(dom.tree[1][0], 'tag', 'right type')
    is_ok(dom.tree[1][1], 'foo', 'right tag')
    is_deeply_ok(dom.tree[1][2], {'bar': ''}, 'right attributes')
    is_ok(dom.tree[1][4][0], 'text', 'right type')
    is_ok(dom.tree[1][4][1], '\n  test\n', 'right text')
    is_ok(dom.tree[3][0], 'tag', 'right type')
    is_ok(dom.tree[3][1], 'bar', 'right tag')
    is_ok(dom.tree[3][4][0], 'text', 'right type')
    is_ok(dom.tree[3][4][1], 'after', 'right text')
    is_ok(
        str(dom),
        """\
<foo bar="">
  test
</foo>
<bar>after</bar>
""",
        'right result',
    )

with subtest('Case-insensitive attribute values'):
    dom = Pyjo.DOM.new("""\
<p class="foo">A</p>
<p class="foo bAr">B</p>
<p class="FOO">C</p>
<p class="foo-bar">D</p>
""")
    is_ok(dom.find('.foo').map('text').join(','), 'A,B', 'right result')
    is_ok(dom.find('.FOO').map('text').join(','), 'C', 'right result')
    is_ok(dom.find('[class=foo]').map('text').join(','), 'A', 'right result')
    is_ok(dom.find('[class=foo s]').map('text').join(','), 'A', 'right result')
    is_ok(dom.find('[class=foo S]').map('text').join(','), 'A', 'right result')
    is_ok(dom.find('[class=foo i]').map('text').join(','), 'A,C', 'right result')
    is_ok(dom.find('[class="foo" i]').map('text').join(','), 'A,C', 'right result')
    is_ok(dom.find('[class="foo" I]').map('text').join(','), 'A,C', 'right result')
    is_ok(dom.find('[class="foo bar"]').size, 0, 'no results')
    is_ok(dom.find('[class="foo bar s"]').size, 0, 'no results')
    is_ok(dom.find('[class="foo bar S"]').size, 0, 'no results')
    is_ok(dom.find('[class="foo bar" i]').map('text').join(','), 'B', 'right result')
    is_ok(dom.find('[class~=foo]').map('text').join(','), 'A,B', 'right result')
    is_ok(dom.find('[class~=foo s]').map('text').join(','), 'A,B', 'right result')
    is_ok(dom.find('[class~=foo i]').map('text').join(','), 'A,B,C', 'right result')
    is_ok(dom.find('[class*=f]').map('text').join(','), 'A,B,D', 'right result')
    is_ok(dom.find('[class*=f s]').map('text').join(','), 'A,B,D', 'right result')
    is_ok(dom.find('[class*=f i]').map('text').join(','), 'A,B,C,D', 'right result')
    is_ok(dom.find('[class^=F]').map('text').join(','), 'C', 'right result')
    is_ok(dom.find('[class^=F S]').map('text').join(','), 'C', 'right result')
    is_ok(dom.find('[class^=F i]').map('text').join(','), 'A,B,C,D', 'right result')
    is_ok(dom.find('[class^=F I]').map('text').join(','), 'A,B,C,D', 'right result')
    is_ok(dom.find('[class$=O]').map('text').join(','), 'C', 'right result')
    is_ok(dom.find('[class$=O i]').map('text').join(','), 'A,C', 'right result')
    is_ok(dom.find('[class|=foo]').map('text').join(','), 'A,D', 'right result')
    is_ok(dom.find('[class|=foo i]').map('text').join(','), 'A,C,D', 'right result')

with subtest('Nested description lists'):
    dom = Pyjo.DOM.new("""\
<dl>
  <dt>A</dt>
  <DD>
    <dl>
      <dt>B
      <dd>C
    </dl>
  </dd>
</dl>
""")
    is_ok(dom.find('dl > dd > dl > dt')[0].text, 'B\n      ', 'right text')
    is_ok(dom.find('dl > dd > dl > dd')[0].text, 'C\n    ', 'right text')
    is_ok(dom.find('dl > dt')[0].text, 'A', 'right text')

with subtest('Nested lists'):
    dom = Pyjo.DOM.new("""\
<div>
  <ul>
    <li>
      A
      <ul>
        <li>B</li>
        C
      </ul>
    </li>
  </ul>
</div>
""")
    is_ok(dom.find('div > ul > li')[0].text, '\n      A\n      \n    ', 'right text')
    is_ok(dom.find('div > ul > li').get(1), None, 'no result')
    is_ok(dom.find('div > ul li')[0].text, '\n      A\n      \n    ', 'right text')
    is_ok(dom.find('div > ul li')[1].text, 'B', 'right text')
    is_ok(dom.find('div > ul li').get(2), None, 'no result')
    is_ok(dom.find('div > ul ul')[0].text, '\n        \n        C\n      ', 'right text')
    is_ok(dom.find('div > ul ul').get(1), None, 'no result')

with subtest('Unusual order'):
    dom = Pyjo.DOM.new('<a href="http://example.com" id="foo" class="bar">Ok!</a>')
    is_ok(dom.at('a:not([href$=foo])[href^=h]').text, 'Ok!', 'right text')
    is_ok(dom.at('a:not([href$=example.com])[href^=h]'), None, 'no result')
    is_ok(dom.at('a[href^=h]#foo.bar').text, 'Ok!', 'right text')
    is_ok(dom.at('a[href^=h]#foo.baz'), None, 'no result')
    is_ok(dom.at('a[href^=h]#foo:not(b)').text, 'Ok!', 'right text')
    is_ok(dom.at('a[href^=h]#foo:not(a)'), None, 'no result')
    is_ok(dom.at('[href^=h].bar:not(b)[href$=m]#foo').text, 'Ok!', 'right text')
    is_ok(dom.at('[href^=h].bar:not(b)[href$=m]#bar'), None, 'no result')
    is_ok(dom.at(':not(b)#foo#foo').text, 'Ok!', 'right text')
    is_ok(dom.at(':not(b)#foo#bar'), None, 'no result')
    is_ok(dom.at(':not([href^=h]#foo#bar)').text, 'Ok!', 'right text')
    is_ok(dom.at(':not([href^=h]#foo#foo)'), None, 'no result')

with subtest('Slash between attributes'):
    dom = Pyjo.DOM.new('<input /type=checkbox / value="/a/" checked/><br/>')
    is_deeply_ok(dom.at('input').attr(), {'type': 'checkbox', 'value': '/a/', 'checked': None}, 'right attributes')
    is_ok(str(dom), '<input checked type="checkbox" value="/a/"><br>', 'right result')

with subtest('Dot and hash in class and id attributes'):
    dom = Pyjo.DOM.new('<p class="a#b.c">A</p><p id="a#b.c">B</p>')
    is_ok(dom.at('p.a\\#b\\.c').text, 'A', 'right text')
    is_ok(dom.at(':not(p.a\\#b\\.c)').text, 'B', 'right text')
    is_ok(dom.at('p#a\\#b\\.c').text, 'B', 'right text')
    is_ok(dom.at(':not(p#a\\#b\\.c)').text, 'A', 'right text')

with subtest('Extra whitespace'):
    dom = Pyjo.DOM.new('< span>a< /span><b >b</b><span >c</ span>')
    is_ok(dom.at('b').text, 'b', 'right text')
    is_ok(dom.at('b + span').text, 'c', 'right text')
    is_ok(str(dom), '&lt; span&gt;a&lt; /span&gt;<b>b</b><span>c</span>', 'right result')

with subtest('Selectors with leading and trailing whitespace'):
    dom = Pyjo.DOM.new('<div id=foo><b>works</b></div>')
    is_ok(dom.at(' div   b ').text, 'works', 'right text')
    is_ok(dom.at('  :not(  #foo  )  ').text, 'works', 'right text')

with subtest('"0"'):
    dom = Pyjo.DOM.new('0')
    is_ok(str(dom), '0', 'right result')
    dom.append_content('☃')
    is_ok(str(dom), '0☃', 'right result')
    is_ok(dom.parse('<!DOCTYPE 0>'), '<!DOCTYPE 0>', 'successful roundtrip')
    is_ok(dom.parse('<!--0-->'), '<!--0-->', 'successful roundtrip')
    is_ok(dom.parse('<![CDATA[0]]>'), '<![CDATA[0]]>', 'successful roundtrip')
    is_ok(dom.parse('<?0?>'), '<?0?>', 'successful roundtrip')

with subtest('Not self-closing'):
    dom = Pyjo.DOM.new('<div />< div ><pre />test</div >123')
    is_ok(dom.at('div > pre').text, 'test', 'right text')
    is_ok(str(dom), '<div>&lt; div &gt;<pre>test</pre></div>123', 'right result')
    dom = Pyjo.DOM.new('<p /><svg><circle /><circle /></svg>')
    is_ok(dom.find('p > svg > circle').size, 2, 'two circles')
    is_ok(str(dom), '<p><svg><circle></circle><circle></circle></svg></p>', 'right result')

with subtest('Auto-close tag'):
    dom = Pyjo.DOM.new('<p><div />')
    is_ok(str(dom), '<p></p><div></div>', 'right result')

with subtest('No auto-close in scope'):
    dom = Pyjo.DOM.new('<p><svg><div /></svg>')
    is_ok(str(dom), '<p><svg><div></div></svg></p>', 'with SVG')
    dom = Pyjo.DOM.new('<p><math><div /></math>')
    is_ok(str(dom), '<p><math><div></div></math></p>', 'with MathML')

with subtest('Auto-close scope'):
    dom = Pyjo.DOM.new('<p><svg></p>')
    is_ok(str(dom), '<p><svg></svg></p>', 'closing tag')
    dom = Pyjo.DOM.new('<p><math>')
    is_ok(str(dom), '<p><math></math></p>', 'close eof')

with subtest('"image"'):
    dom = Pyjo.DOM.new('<image src="foo.png">test')
    is_ok(dom.at('img')['src'], 'foo.png', 'right attribute')
    is_ok(str(dom), '<img src="foo.png">test', 'right result')

with subtest('"title"'):
    dom = Pyjo.DOM.new('<title> <p>test&lt;</title>')
    is_ok(dom.at('title').text, ' <p>test<', 'right text')
    is_ok(str(dom), '<title> &lt;p&gt;test&lt;</title>', 'right result')

    dom = Pyjo.DOM.new('<title>&lt;/title&gt;&lt;img src=x onerror=alert(1)&gt;</title>')
    is_ok(dom.at('title').text, '</title><img src=x onerror=alert(1)>', 'right text')
    is_ok(str(dom), '<title>&lt;/title&gt;&lt;img src=x onerror=alert(1)&gt;</title>', 'end tag stays escaped')

with subtest('"textarea"'):
    dom = Pyjo.DOM.new('<textarea id="a"> <p>test&lt;</textarea>')
    is_ok(dom.at('textarea#a').text, ' <p>test<', 'right text')
    is_ok(str(dom), '<textarea id="a"> &lt;p&gt;test&lt;</textarea>', 'right result')

    dom = Pyjo.DOM.new('<textarea>&lt;/textarea&gt;&lt;script&gt;alert(1)&lt;/script&gt;</textarea>')
    is_ok(dom.at('textarea').text, '</textarea><script>alert(1)</script>', 'right text')
    is_ok(
        str(dom), '<textarea>&lt;/textarea&gt;&lt;script&gt;alert(1)&lt;/script&gt;</textarea>', 'end tag stays escaped'
    )

with subtest('CDATA, processing instructions and DOCTYPE end at the first ">" in HTML'):
    dom = Pyjo.DOM.new('<![CDATA[><img src=x onerror=alert(1)>]]>')
    is_ok(dom.child_nodes[0].type, 'cdata', 'right type')
    is_ok(dom.child_nodes[0].content, '', 'no content')
    is_ok(dom.at('img')['onerror'], 'alert(1)', 'right attribute')
    is_ok(dom.child_nodes[2].content, ']]>', 'right text')
    dom.find('img').each(lambda e, num: e.remove())
    is_ok(str(dom), '<![CDATA[]]>]]&gt;', 'right result')

    dom = Pyjo.DOM.new('<?><img src=x onerror=alert(1)>?>')
    is_ok(dom.child_nodes[0].type, 'pi', 'right type')
    is_ok(dom.at('img')['onerror'], 'alert(1)', 'right attribute')
    dom.find('img').each(lambda e, num: e.remove())
    is_ok(str(dom), '<??>?&gt;', 'right result')

    dom = Pyjo.DOM.new('<!DOCTYPE html [><img src=x onerror=alert(1)>]>')
    is_ok(dom.child_nodes[0].type, 'doctype', 'right type')
    is_ok(dom.child_nodes[0].content, ' html [', 'right content')
    is_ok(dom.at('img')['onerror'], 'alert(1)', 'right attribute')
    dom.find('img').each(lambda e, num: e.remove())
    is_ok(str(dom), '<!DOCTYPE html [>]&gt;', 'right result')

    dom = Pyjo.DOM.new('<p><![CDATA[1 < 2]]><?php echo 1?></p>')
    is_ok(dom.at('p').child_nodes[0].content, '1 < 2', 'right content')
    is_ok(dom.at('p').child_nodes[1].content, 'php echo 1', 'right content')
    is_ok(str(dom), '<p><![CDATA[1 < 2]]><?php echo 1?></p>', 'successful roundtrip')

    dom = Pyjo.DOM.new('<svg><script><![CDATA[ if (a > b) {} ]]></script></svg>')
    is_ok(dom.at('script').child_nodes.first().type, 'cdata', 'right type')
    is_ok(dom.at('script').child_nodes.first().content, ' if (a > b) {} ', 'right content')
    is_ok(str(dom), '<svg><script><![CDATA[ if (a > b) {} ]]></script></svg>', 'successful roundtrip')

    dom = Pyjo.DOM.new('<svg><foreignObject><![CDATA[><img src=x onerror=alert(1)>]]></foreignObject></svg>')
    is_ok(dom.at('foreignobject img')['onerror'], 'alert(1)', 'right attribute')

    dom = Pyjo.DOM.new().set(xml=True).parse('<root><![CDATA[><img src=x onerror=alert(1)>]]></root>')
    ok(not dom.at('img'), 'no img element in XML mode')
    is_ok(dom.at('root').text, '><img src=x onerror=alert(1)>', 'right text')

with subtest('"style" and "script" in foreign content'):
    dom = Pyjo.DOM.new('<svg><style><img src=x onerror=alert(1)></style></svg>')
    is_ok(dom.at('svg > style > img')['onerror'], 'alert(1)', 'right attribute')
    dom.find('img').each(lambda e, num: e.remove())
    is_ok(str(dom), '<svg><style></style></svg>', 'right result')

    dom = Pyjo.DOM.new('<math><script><img src=x onerror=alert(1)></script></math>')
    is_ok(dom.at('math > script > img')['onerror'], 'alert(1)', 'right attribute')

    dom = Pyjo.DOM.new('<svg><title><img src=x onerror=alert(1)></title></svg>')
    is_ok(dom.at('svg > title > img')['onerror'], 'alert(1)', 'right attribute')

    dom = Pyjo.DOM.new('<svg><foreignObject><style><b>test</b></style></foreignObject></svg>')
    ok(not dom.at('b'), 'no b element')
    is_ok(dom.at('style').text, '<b>test</b>', 'right text')

    dom = Pyjo.DOM.new('<math><mi><style><b>test</b></style></mi></math>')
    ok(not dom.at('b'), 'no b element')

    dom = Pyjo.DOM.new('<math><annotation-xml><style><b>test</b></style></annotation-xml></math>')
    ok(dom.at('b'), 'b element')
    dom = Pyjo.DOM.new('<math><annotation-xml encoding="text/html"><style><b>test</b></style></annotation-xml></math>')
    ok(not dom.at('b'), 'no b element')

with subtest('Raw text end tags'):
    dom = Pyjo.DOM.new('<style></style/><img src=x onerror=alert(1)></style>')
    is_ok(dom.at('style').text, '', 'no text')
    is_ok(dom.at('img')['onerror'], 'alert(1)', 'right attribute')
    dom.find('img').each(lambda e, num: e.remove())
    is_ok(str(dom), '<style></style>', 'right result')

    dom = Pyjo.DOM.new('<script>1</script/><img src=x onerror=alert(1)></script>')
    is_ok(dom.at('script').text, '1', 'right text')
    is_ok(dom.at('img')['onerror'], 'alert(1)', 'right attribute')

    dom = Pyjo.DOM.new('<style>a</style foo="bar">b')
    is_ok(dom.at('style').text, 'a', 'right text')
    is_ok(str(dom), '<style>a</style>b', 'right result')

    dom = Pyjo.DOM.new('<title>a</title/>b')
    is_ok(dom.at('title').text, 'a', 'right text')
    is_ok(str(dom), '<title>a</title>b', 'right result')

    dom = Pyjo.DOM.new('<div><p>a</p/>b</div>')
    is_ok(str(dom), '<div><p>a</p>b</div>', 'right result')

with subtest('Raw text moved out of "style" and "script"'):
    dom = Pyjo.DOM.new('<p><style><img src=x onerror=alert(1)></style></p>')
    dom.find(':not(p)').each(lambda e, num: e.strip())
    is_ok(str(dom), '<p>&lt;img src=x onerror=alert(1)&gt;</p>', 'right result')
    is_ok(dom.at('p').child_nodes.first().type, 'text', 'right type')

    dom = Pyjo.DOM.new('<div><script><b>test</b></script></div>')
    dom.at('div').append_content(dom.at('script').child_nodes.first())
    is_ok(str(dom), '<div><script><b>test</b></script>&lt;b&gt;test&lt;/b&gt;</div>', 'right result')

    dom = Pyjo.DOM.new('<script></script>')
    dom.at('script').append_content(Pyjo.DOM.new('<style>a < b</style>').at('style').child_nodes.first())
    is_ok(str(dom), '<script>a < b</script>', 'raw text stays raw')

    is_ok(tag_to_html('div', lambda: '<b>test</b>'), '<div><b>test</b></div>', 'raw content')
    dom = Pyjo.DOM.new('<p></p>')
    dom.at('p').append_content(dom.new_tag('div', lambda: '<b>test</b>'))
    is_ok(str(dom), '<p><div><b>test</b></div></p>', 'raw content')

with subtest('Only a leading XML declaration enables XML mode'):
    dom = Pyjo.DOM.new('<p>x</p><?php echo "xml"?><SCRIPT>alert(1)</SCRIPT>')
    ok(not dom.xml, 'XML mode not detected')
    is_ok(dom.find('script').size, 1, 'one script element')

    dom = Pyjo.DOM.new('<?xml-stylesheet href="test.xsl"?><SCRIPT>alert(1)</SCRIPT>')
    ok(not dom.xml, 'XML mode not detected')
    is_ok(dom.find('script').size, 1, 'one script element')

    dom = Pyjo.DOM.new('<p>x</p><?xml version="1.0"?><SCRIPT>alert(1)</SCRIPT>')
    ok(not dom.xml, 'XML mode not detected')
    is_ok(dom.find('script').size, 1, 'one script element')

    ok(Pyjo.DOM.new('<?xml version="1.0"?><Foo/>').xml, 'XML mode detected')
    ok(Pyjo.DOM.new('\n  <?xml version="1.0"?><Foo/>').xml, 'XML mode detected')
    ok(Pyjo.DOM.new('﻿<?xml version="1.0"?><Foo/>').xml, 'XML mode detected')
    ok(Pyjo.DOM.new('<?xml?><Foo/>').xml, 'XML mode detected')
    ok(not Pyjo.DOM.new().set(xml=False).parse('<?xml version="1.0"?><Foo/>').xml, 'XML mode not detected')

with subtest('Comments'):
    dom = Pyjo.DOM.new("""\
<!-- HTML5 -->
<!-- bad idea -- HTML5 -->
""")
    is_ok(dom.tree[1][1], ' HTML5 ', 'right comment')
    is_ok(dom.tree[3][1], ' bad idea -- HTML5 ', 'right comment')

with subtest('Comment is not terminated by "-- >"'):
    dom = Pyjo.DOM.new('<!-- a > -- > b <blink>c</blink> -->')
    is_ok(dom.at('blink'), None, 'blink element is inside comment')
    is_ok(dom.tree[1][1], ' a > -- > b <blink>c</blink> ', 'right comment')

with subtest('Abrupt and bang-terminated comments'):
    dom = Pyjo.DOM.new('<!DOCTYPE html>\n<!--> <p>OK</p> <!-- -->')
    is_ok(dom.at('p').text, 'OK', 'abrupt empty comment closure')

    dom = Pyjo.DOM.new('<!DOCTYPE html>\n<!---> <p>OK</p> <!-- -->')
    is_ok(dom.at('p').text, 'OK', 'dash-terminated empty comment')

    dom = Pyjo.DOM.new('<!DOCTYPE html>\n<!-- --!> <p>OK</p> <!-- -->')
    is_ok(dom.at('p').text, 'OK', 'bang-terminated comment')

with subtest('Huge number of attributes'):
    dom = Pyjo.DOM.new('<div ' + ('a=b ' * 32768) + '>Test</div>')
    is_ok(dom.at('div[a=b]').text, 'Test', 'right text')

with subtest('Huge number of nested tags'):
    huge = ('<a>' * 100) + 'works' + ('</a>' * 100)
    dom = Pyjo.DOM.new(huge)
    is_ok(dom.all_text, 'works', 'right text')
    is_ok(str(dom), huge, 'right result')

with subtest('Namespace'):
    dom = (
        Pyjo.DOM.new()
        .set(xml=True)
        .parse("""\
<tag xmlns:myns="coolns">
  <this>foo</this>
  <myns:this>bar</myns:this>
</tag>
""")
    )
    ns = {'cool': 'coolns'}
    is_deeply_ok(dom.find('cool|this', **ns).map('text'), ['bar'], 'right result')
    is_deeply_ok(dom.find('cool|*', **ns).map('text'), ['bar'], 'right result')
    is_deeply_ok(dom.find('|this', **ns).map('text'), ['foo'], 'right result')
    is_deeply_ok(dom.find('*|this', **ns).map('text'), ['foo', 'bar'], 'right result')
    ok(not dom.at('foo|*'), 'no result')

with subtest('Namespace declaration on the same tag'):
    dom = Pyjo.DOM.new().set(xml=True).parse('<x:tag xmlns:x="ns" foo="bar" />')
    is_ok(dom.at('ns|tag', ns='ns')['foo'], 'bar', 'right result')

with subtest('Explicit no namespace'):
    dom = Pyjo.DOM.new().set(xml=True).parse('<foo xmlns=""><bar /></foo>')
    ok(dom.at('|bar'), 'result')

with subtest('Nested namespaces'):
    dom = (
        Pyjo.DOM.new()
        .set(xml=True)
        .parse("""\
<foo xmlns="ns:foo">
  <tag val="1" />
  <bar xmlns="ns:bar">
    <tag val="2" />
    <baz />
    <yada hreflang="en-US">YADA</yada>
  </bar>
</foo>
""")
    )
    ns = {'foons': 'ns:foo', 'barns': 'ns:bar'}
    ok(dom.at('foons|foo', **ns), 'result')
    ok(dom.at('foons|foo:not(barns|*)', **ns), 'result')
    ok(dom.at('foo:not(|foo)', **ns), 'result')
    ok(dom.at('foons|foo:root', **ns), 'result')
    ok(dom.at('foo:is(:root, foons|*)', **ns), 'result')
    ok(not dom.at('foons|foo:not(:root)', **ns), 'no result')
    is_ok(dom.at('foons|tag', **ns)['val'], '1', 'right value')
    is_ok(dom.at('foons|tag:empty', **ns)['val'], '1', 'right value')
    ok(dom.at('foons|tag[val="1"]', **ns), 'result')
    ok(dom.at('foons|tag[val="1"]:empty', **ns), 'result')
    ok(dom.at('foo > foons|tag[val="1"]', **ns), 'result')
    ok(dom.at('foons|foo > foons|tag[val="1"]', **ns), 'result')
    ok(dom.at('foo foons|tag[val="1"]', **ns), 'result')
    ok(dom.at('foons|foo foons|tag[val="1"]', **ns), 'result')
    ok(dom.at('barns|bar', **ns), 'result')
    ok(dom.at('barns|bar:not(foons|*)', **ns), 'result')
    ok(dom.at('bar:not(|bar)', **ns), 'result')
    ok(dom.at('bar:is(barns|*)', **ns), 'result')
    ok(not dom.at('barns|bar:root', **ns), 'no result')
    ok(dom.at('barns|bar:not(:root)', **ns), 'result')
    ok(dom.at('bar:is(barns|*, :not(:root))', **ns), 'result')
    ok(dom.at('foons|foo barns|bar', **ns), 'result')
    is_ok(dom.at('barns|tag', **ns)['val'], '2', 'right value')
    is_ok(dom.at('barns|tag:empty', **ns)['val'], '2', 'right value')
    ok(dom.at('barns|tag[val="2"]', **ns), 'result')
    ok(dom.at('barns|tag[val="2"]:empty', **ns), 'result')
    ok(dom.at('bar > barns|tag[val="2"]', **ns), 'result')
    ok(dom.at('barns|bar > barns|tag[val="2"]', **ns), 'result')
    ok(dom.at('bar barns|tag[val="2"]', **ns), 'result')
    ok(dom.at('barns|bar barns|tag[val="2"]', **ns), 'result')
    ok(dom.at('foons|foo barns|bar baz', **ns), 'result')
    ok(dom.at('foons|foo barns|bar barns|baz', **ns), 'result')
    ok(dom.at('foons|foo barns|bar barns|tag[val="2"] + baz', **ns), 'result')
    ok(dom.at('foons|foo barns|bar barns|tag[val="2"] + barns|baz', **ns), 'result')
    ok(dom.at('foons|foo barns|bar barns|tag[val="2"] ~ baz', **ns), 'result')
    ok(dom.at('foons|foo barns|bar barns|tag[val="2"] ~ barns|baz', **ns), 'result')
    ok(not dom.at('foons|bar', **ns), 'no result')
    ok(not dom.at('foons|baz', **ns), 'no result')
    ok(dom.at('baz').matches('barns|*', **ns), 'match')
    is_ok(dom.at('barns|bar [hreflang|=en]', **ns).text, 'YADA', 'right text')
    is_ok(dom.at('barns|bar [hreflang|=en-US]', **ns).text, 'YADA', 'right text')
    ok(not dom.at('barns|bar [hreflang|=en-US-yada]', **ns), 'no result')
    ok(not dom.at('barns|bar [hreflang|=e]', **ns), 'no result')

with subtest('No more content'):
    dom = Pyjo.DOM.new("""\
  <body>
    <select>
      <option>A
      <option>B
    </select>
    <textarea>C</textarea>
  </body>
""")
    is_ok(dom.find('body > select > option')[0].text, 'A\n      ', 'right text')
    is_ok(dom.find('body > select > option')[1].text, 'B\n    ', 'right text')
    is_ok(dom.at('body > textarea').text, 'C', 'right text')

    dom = Pyjo.DOM.new("""\
  <body>
    <select>
      <optgroup>
        <option>A
        <option>B
    </select>
    <textarea>C</textarea>
  </body>
""")
    is_ok(dom.find('body > select > optgroup > option')[0].text, 'A\n        ', 'right text')
    is_ok(dom.find('body > select > optgroup > option')[1].text, 'B\n    ', 'right text')
    is_ok(dom.at('body > textarea').text, 'C', 'right text')

    dom = Pyjo.DOM.new("""\
  <body>
    <ul>
      <li>A
      <li>B
    </ul>
    <textarea>C</textarea>
  </body>
""")
    is_ok(dom.find('body > ul > li')[0].text, 'A\n      ', 'right text')
    is_ok(dom.find('body > ul > li')[1].text, 'B\n    ', 'right text')
    is_ok(dom.at('body > textarea').text, 'C', 'right text')

    dom = Pyjo.DOM.new("""\
  <body>
    <dl>
      <dd>A
      <dd>B
    </dl>
    <textarea>C</textarea>
  </body>
""")
    is_ok(dom.find('body > dl > dd')[0].text, 'A\n      ', 'right text')
    is_ok(dom.find('body > dl > dd')[1].text, 'B\n    ', 'right text')
    is_ok(dom.at('body > textarea').text, 'C', 'right text')

    dom = Pyjo.DOM.new("""\
  <body>
    <ruby>
      <rp>A
      <rt>B
    </ruby>
    <textarea>C</textarea>
  </body>
""")
    is_ok(dom.at('body > ruby > rp').text, 'A\n      ', 'right text')
    is_ok(dom.at('body > ruby > rt').text, 'B\n    ', 'right text')
    is_ok(dom.at('body > textarea').text, 'C', 'right text')

    dom = Pyjo.DOM.new("""\
  <body>
    <ruby>
      <rt>A
      <rp>B
    </ruby>
    <textarea>C</textarea>
  </body>
""")
    is_ok(dom.at('body > ruby > rt').text, 'A\n      ', 'right text')
    is_ok(dom.at('body > ruby > rp').text, 'B\n    ', 'right text')
    is_ok(dom.at('body > textarea').text, 'C', 'right text')

with subtest('Exclude "<script>" and "<style>" from text extraction in HTML documents'):
    dom = Pyjo.DOM.new("""\
  <html>
    <head>
      <title>Hello</title>
      <script>123</script>
      <style>456</style>
    </head>
    <body>
      <script>123</script>
      <div>Mojo!</div>
      <style>456</style>
    </body>
  <html>
""")
    like_ok(dom.at('html').all_text, (r'Hello.*Mojo!', 's'), 'title and div')
    unlike_ok(dom.at('html').all_text, r'123', 'no script')
    unlike_ok(dom.at('html').all_text, r'456', 'no style')
    like_ok(dom.at('script').text, r'123', 'script text')
    like_ok(dom.at('style').text, r'456', 'style text')

    dom = Pyjo.DOM.new("""\
  <?xml version="1.0" encoding="UTF-8"?>
  <foo>
    <title>Hello</title>
    <script>123</script>
    <style>456</style>
   </foo>
""")
    like_ok(dom.at('foo').all_text, (r'Hello.*123.*456', 's'), 'everything')
    like_ok(dom.at('script').text, r'123', 'script text')
    like_ok(dom.at('style').text, r'456', 'style text')

with subtest('Reusing fragments'):
    fragment = Pyjo.DOM.new('<a><b>C</b></a>')
    dom = Pyjo.DOM.new('<div></div>')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom.at('div').append(fragment)
    dom.at('div').append(fragment)
    is_ok(dom, '<div></div><a><b>C</b></a><a><b>C</b></a>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom = Pyjo.DOM.new('<div></div>')
    dom.at('div').append_content(fragment)
    dom.at('div').append_content(fragment)
    is_ok(dom, '<div><a><b>C</b></a><a><b>C</b></a></div>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom = Pyjo.DOM.new('<div></div>')
    dom.at('div').set(content=fragment)
    dom.at('div a').set(content=fragment)
    is_ok(dom, '<div><a><a><b>C</b></a></a></div>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom = Pyjo.DOM.new('<div></div>')
    dom.at('div').prepend(fragment)
    dom.at('div').prepend(fragment)
    is_ok(dom, '<a><b>C</b></a><a><b>C</b></a><div></div>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom = Pyjo.DOM.new('<div></div>')
    dom.at('div').prepend_content(fragment)
    dom.at('div').prepend_content(fragment)
    is_ok(dom, '<div><a><b>C</b></a><a><b>C</b></a></div>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom = Pyjo.DOM.new('<div></div>')
    dom.at('div').replace(fragment)
    dom.at('b').replace(fragment)
    is_ok(dom, '<a><a><b>C</b></a></a>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom = Pyjo.DOM.new('<div></div>')
    dom.at('div').wrap(fragment)
    dom.at('b').wrap(fragment)
    is_ok(dom, '<a><a><b>C<b>C<div></div></b></b></a></a>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')
    dom = Pyjo.DOM.new('<div></div>')
    dom.at('div').wrap_content(fragment)
    dom.at('b').wrap_content(fragment)
    is_ok(dom, '<div><a><b><a><b>CC</b></a></b></a></div>', 'right result')
    is_ok(fragment, '<a><b>C</b></a>', 'right result')

with subtest('Generate tags'):
    is_ok(Pyjo.DOM.object.new_tag('br').to_str(), '<br>', 'right result')
    is_ok(Pyjo.DOM.object.new_tag('div').to_str(), '<div></div>', 'right result')
    is_ok(Pyjo.DOM.object.new_tag('div', id='foo', hidden=None).to_str(), '<div hidden id="foo"></div>', 'right result')
    is_ok(Pyjo.DOM.object.new_tag('div', 'safe & content'), '<div>safe &amp; content</div>', 'right result')
    is_ok(
        Pyjo.DOM.object.new_tag('div', 'safe & content', id='foo'),
        '<div id="foo">safe &amp; content</div>',
        'right result',
    )
    is_ok(
        Pyjo.DOM.object.new_tag('div', 'safe & content', id='foo', data={'foo': 0, 'Bar': 'test'}),
        '<div data-bar="test" data-foo="0" id="foo">safe &amp; content</div>',
        'right result',
    )
    is_ok(Pyjo.DOM.object.new_tag('div', lambda: 'unsafe & content'), '<div>unsafe & content</div>', 'right result')
    is_ok(
        Pyjo.DOM.object.new_tag('div', lambda: 'unsafe & content', id='foo'),
        '<div id="foo">unsafe & content</div>',
        'right result',
    )
    is_ok(Pyjo.DOM.new().new_tag('foo', hidden=None), '<foo hidden></foo>', 'right result')
    is_ok(Pyjo.DOM.new().set(xml=True).new_tag('foo', hidden=None), '<foo hidden="hidden" />', 'right result')
    dom = Pyjo.DOM.new('<div>Test</div>')
    br = dom.new_tag('br')
    dom.at('div').append_content(br).append_content(br)
    is_ok(dom, '<div>Test<br><br></div>', 'right result')
    is_ok(tag_to_html('div', 'bar', id='foo'), '<div id="foo">bar</div>', 'right result')

with subtest('Generate selector'):
    dom = Pyjo.DOM.new("""\
<html>
  <head>
    <title>Test</title>
  </head>
  <body>
    <p id="a">A</p>
    <p id="b">B</p>
    <p id="c">C</p>
    <p id="d">D</p>
  </body>
<html>
""")
    is_ok(dom.selector, None, 'not a tag')
    is_ok(dom.at('#a').child_nodes.first().selector, None, 'not a tag')
    is_ok(dom.at('#a').selector, 'html:nth-child(1) > body:nth-child(2) > p:nth-child(1)', 'right selector')
    is_ok(dom.at(dom.at('#a').selector).text, 'A', 'right text')
    is_ok(dom.at('#b').selector, 'html:nth-child(1) > body:nth-child(2) > p:nth-child(2)', 'right selector')
    is_ok(dom.at(dom.at('#b').selector).text, 'B', 'right text')
    is_ok(dom.at('#c').selector, 'html:nth-child(1) > body:nth-child(2) > p:nth-child(3)', 'right selector')
    is_ok(dom.at(dom.at('#c').selector).text, 'C', 'right text')
    is_ok(dom.at('#d').selector, 'html:nth-child(1) > body:nth-child(2) > p:nth-child(4)', 'right selector')
    is_ok(dom.at(dom.at('#d').selector).text, 'D', 'right text')
    is_ok(dom.at('title').selector, 'html:nth-child(1) > head:nth-child(1) > title:nth-child(1)', 'right selector')
    is_ok(dom.at(dom.at('title').selector).text, 'Test', 'right text')
    is_ok(dom.at('html').selector, 'html:nth-child(1)', 'right selector')

with subtest('Reusing partial DOM trees'):
    dom = Pyjo.DOM.new().parse('<div><b>Test</b></div>')
    is_ok(dom.at('div').prepend(dom.at('b')).root, '<b>Test</b><div><b>Test</b></div>', 'right result')

with subtest('Real world table with optional elements'):
    dom = Pyjo.DOM.new().parse("""\
<!DOCTYPE html>
<html lang="en">
  <body>
    <table class="table table-striped">
      <thead>
        <tr>
          <th>key</th>
          <th>secret</th>
          <th>expires</th>
          <th>action</th>
      </thead>
      <tbody>
        <tr id="api_key_4">
          <td class="key">PERCIVALKEY01</td>
          <td class="secret">PERCIVALSECRET01</td>
          <td class="expiration">2020-06-18 11:12:03 +0000</td>
        <tr id="api_key_5">
          <td class="key">PERCIVALKEY02</td>
          <td class="secret">PERCIVALSECRET02</td>
          <td class="expiration">never</td>
      </tbody>
    </table>
  </body>
</html>
""")
    is_ok(dom.at('thead tr th').text, 'key', 'right text')
    is_ok(dom.at('#api_key_4 .key').text, 'PERCIVALKEY01', 'right text')
    is_ok(dom.at('#api_key_4 .secret').text, 'PERCIVALSECRET01', 'right text')
    is_ok(dom.at('#api_key_4 .expiration').text, '2020-06-18 11:12:03 +0000', 'right text')
    is_ok(dom.at('#api_key_5 .expiration').text, 'never', 'right text')

with subtest('Root pseudo-class'):
    dom = Pyjo.DOM.new('<html><head></head><body><div><div>x</div></div></body></html>')
    is_ok(dom.find('body > :first-child > :first-child').first().text, 'x', 'right text')
    is_ok(dom.at(':scope:first-child'), None, 'no result')

with subtest('Runaway "<"'):
    dom = Pyjo.DOM.new("""\
    <table>
      <tr>
        <td>
          <div class="test" data-id="123" data-score="3">works</div>
          TEST 123<br />
          Test  12-34-5 test  >= 75% and < 85%  test<br />
          Test  12-34-5  -test foo >= 5% and < 30% test<br />
          Test  12-23-4 n/a >=13% and = 1% and < 5% test tset<br />
          Test  12-34-5  test >= 1% and < 5%   foo, bar, baz<br />
          Test foo, bar, baz  123-456-78  test < 1%  foo, bar, baz yada, foo, bar and baz, yada
        </td>
      </tr>
    </table>
""")
    is_ok(dom.at('.test').text, 'works', 'right text')

with subtest('Unclosed comments, CDATA sections, processing instructions and RCDATA elements'):
    dom = Pyjo.DOM.new('<p><!-- a <p><!-- b <![CDATA[ c <? d <![CDATA[ e <? f')
    is_ok(dom.find('p').size, 2, 'right number of elements')
    is_ok(dom.all_text, '<!-- a <!-- b <![CDATA[ c <? d <![CDATA[ e <? f', 'right text')

    dom = Pyjo.DOM.new('<div><textarea>a<p><textarea>b</div><p><!--c-->')
    is_deeply_ok(dom.find('textarea').map('text').to_list(), ['a', 'b'], 'right text')
    is_ok(dom.find('p').size, 2, 'right number of elements')

with subtest('Stray "=" after tag name'):
    dom = Pyjo.DOM.new('<div ="x"><img ="foo" src="bar"></div =y><p ="">a</p>')
    is_ok(dom.at('img').attr('src'), 'bar', 'right attribute')
    is_ok(dom.at('div').children().size, 1, 'right number of children')
    is_ok(dom.at('p').text, 'a', 'right text')
    is_ok(str(dom), '<div "x"><img "foo" src="bar"></div><p "">a</p>', 'right result')

with subtest('Runaway "<" in what looks like an attribute value'):
    dom = Pyjo.DOM.new('<a&amp;=<b x="1">test</b>')
    is_ok(dom.at('b').text, 'test', 'right text')
    is_ok(str(dom), '&lt;a&amp;=<b x="1">test</b>', 'right result')

with subtest('"<" followed by space is not a tag opener'):
    dom = Pyjo.DOM.new('if a < script then="<!--"> </script> <p>FAIL</p>-->')
    is_deeply_ok(dom.find('script, p').map('to_string').to_list(), [], 'fragment contains no tags, just a comment')

    dom = Pyjo.DOM.new('a < b')
    is_ok(str(dom), 'a &lt; b', 'right result')
    is_deeply_ok(dom.find('*').to_list(), [], 'no elements')

    dom = Pyjo.DOM.new('a < b <p>ok</p>')
    is_deeply_ok(dom.find('*').map('tag').to_list(), ['p'], 'only one element')
    is_ok(dom.at('p').text, 'ok', 'right text')

with subtest('XML name characters'):
    dom = Pyjo.DOM.new().set(xml=True).parse('<Foo><1a>foo</1a></Foo>')
    is_ok(dom.at('Foo').text, '<1a>foo</1a>', 'right text')
    is_ok(str(dom), '<Foo>&lt;1a&gt;foo&lt;/1a&gt;</Foo>', 'right result')

    dom = Pyjo.DOM.new().set(xml=True).parse('<Foo><.a>foo</.a></Foo>')
    is_ok(dom.at('Foo').text, '<.a>foo</.a>', 'right text')
    is_ok(str(dom), '<Foo>&lt;.a&gt;foo&lt;/.a&gt;</Foo>', 'right result')

    dom = Pyjo.DOM.new().set(xml=True).parse('<Foo><.>foo</.></Foo>')
    is_ok(dom.at('Foo').text, '<.>foo</.>', 'right text')
    is_ok(str(dom), '<Foo>&lt;.&gt;foo&lt;/.&gt;</Foo>', 'right result')

    dom = Pyjo.DOM.new().set(xml=True).parse('<Foo><-a>foo</-a></Foo>')
    is_ok(dom.at('Foo').text, '<-a>foo</-a>', 'right text')
    is_ok(str(dom), '<Foo>&lt;-a&gt;foo&lt;/-a&gt;</Foo>', 'right result')

    dom = Pyjo.DOM.new().set(xml=True).parse('<Foo><a1>foo</a1></Foo>')
    is_ok(dom.at('Foo a1').text, 'foo', 'right text')
    is_ok(str(dom), '<Foo><a1>foo</a1></Foo>', 'right result')

    dom = Pyjo.DOM.new().set(xml=True).parse('<Foo><a .b -c 1>foo</a></Foo>')
    is_ok(dom.at('Foo').text, '<a .b -c 1>foo', 'right text')
    is_ok(str(dom), '<Foo>&lt;a .b -c 1&gt;foo</Foo>', 'right result')

    dom = Pyjo.DOM.new().set(xml=True).parse('<😄 😄="😄">foo</😄>')
    is_ok(dom.at('😄').text, 'foo', 'right text')
    is_ok(str(dom), '<😄 😄="😄">foo</😄>', 'right result')

    dom = Pyjo.DOM.new().set(xml=True).parse('<こんにちは こんにちは="こんにちは">foo</こんにちは>')
    is_ok(dom.at('こんにちは').text, 'foo', 'right text')
    is_ok(str(dom), '<こんにちは こんにちは="こんにちは">foo</こんにちは>', 'right result')

with subtest('Script end tags'):
    dom = Pyjo.DOM.new("""\
    <!DOCTYPE html>
    <h1>Welcome to HTML</h1>
    <script>
        console.log('< /script> is safe');
        /* <div>XXX this is not a div element</div> */
    </script>
""")
    like_ok(dom.at('script').text, (r'console\.log.+< \/script>.+this is not a div element', 's'), 'right text')

    dom = Pyjo.DOM.new("""\
    <!DOCTYPE html>
    <h1>Welcome to HTML</h1>
    <script>
        console.log('this is a script element and should be executed');
    // </script asdf> <p>
        console.log('this is not a script');
        // <span data-wtf="</script>">:-)</span>
""")
    like_ok(dom.at('script').text, (r'console\.log.+executed.+\/\/', 's'), 'right text')
    like_ok(dom.at('p').text, (r'console\.log.+this is not a script', 's'), 'right text')
    is_ok(dom.at('span').text, ':-)', 'right text')

    dom = Pyjo.DOM.new("""\
    <!DOCTYPE html>
    <h1>Welcome to HTML</h1>
    <div>
      <script> console.log('</scriptxyz is safe'); </script>
    </div>
""")
    like_ok(dom.at('script').text, (r'console\.log.+scriptxyz is safe', 's'), 'right text')
    like_ok(dom.at('div').text, (r'^\s+$', 's'), 'right text')

with subtest('Descendant combinator chain with non-matching selector'):
    dom = Pyjo.DOM.new('<div> ' * 100 + '</div> ' * 100)
    is_deeply_ok(
        dom.find('#gobbledygook * * * *').map(lambda e: e.to_str()).to_list(),
        [],
        'non-existent elements have no descendants',
    )
    is_ok(dom.at('#gobbledygook * * * *'), None, 'no match')

    is_deeply_ok(
        dom.find('* * * * #gobbledygook').map(lambda e: e.to_str()).to_list(),
        [],
        'non-existent elements have no ancestors',
    )
    is_ok(dom.at('* * * * #gobbledygook'), None, 'no match')

    exists = Pyjo.DOM.new('<div id="x"><a><b><c><d>ok</d></c></b></a></div>')
    is_ok(exists.at('#x * * * *').text, 'ok', 'matching id still resolves descendants')

with subtest('First match without combinators'):
    dom = Pyjo.DOM.new('<div><p id="a">A</p><span><b class="x">B</b></span></div><p class="x">C</p>')
    is_ok(dom.at('b, p').text, 'A', 'first match in document order')
    is_ok(dom.at('.x').text, 'B', 'nested match comes first')
    is_ok(dom.at('span').at('b.x, p').text, 'B', 'only matches inside the element')
    is_ok(dom.at('div').at('p.x'), None, 'no match inside the element')
    is_ok(dom.at('i'), None, 'no match')

with subtest('Unknown CSS selector'):
    dom = Pyjo.DOM.new('<html><head></head><body><div><div>x</div></div></body></html>')
    throws_ok(lambda: dom.at('div['), re.compile(r'Unknown CSS selector: div\['), 'right error')
    throws_ok(lambda: dom.find('p['), re.compile(r'Unknown CSS selector: p\['), 'right error')

# Not in Mojolicious: the matches one by one, which are the ones of find, from a scope too
with subtest('Lazy selection'):
    dom = Pyjo.DOM.new(
        '<div id="x"><a>1</a><b id="b"><c>2</c><a>3</a><c>4</c></b><c>5</c></div>'
        '<section><p>6</p><b><p>7</p></b><p class="x">8</p></section>'
    )
    selectors = [
        '*',
        'a',
        'c',
        'b c',
        'b > c',
        'a ~ b c',
        'a + b c',
        'a ~ c',
        'c + a',
        'c ~ c',
        'div c',
        'div > c',
        ':scope c',
        ':scope > c',
        ':scope ~ c',
        'c:not(:first-child)',
        'b:has(> c)',
        'p:is(.x, :first-child)',
        'section p',
        'section > b > p',
        ':root',
        'div, section p',
        'b ~ *',
    ]
    for scope in (dom, dom.at('#x'), dom.at('#b'), dom.at('section')):
        for css in selectors:
            found = [str(e) for e in scope.find(css)]
            is_deeply_ok([str(e) for e in scope.iterate(css)], found, f'{css} from {scope.tag or "root"}')

    dom = Pyjo.DOM.new('<p class="x">1</p><p>2</p><p>3</p>')
    elements = iter(dom.iterate('p.x'))
    is_ok(next(elements).text, '1', 'first element')
    dom.find('p')[2].attr(**{'class': 'x'})
    is_deeply_ok([e.text for e in elements], ['3'], 'the rest matched as they are taken')
    is_deeply_ok([e.text for e in dom.iterate('p.x')], ['1', '3'], 'matched anew for each iteration')

done_testing()
