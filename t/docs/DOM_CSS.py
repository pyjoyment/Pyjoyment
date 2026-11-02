from Pyjo.Test import *


with subtest('Synopsis'):
    import Pyjo.DOM.HTML

    from Pyjo.DOM.CSS import CSS

    tree = (
        Pyjo.DOM.HTML.new().parse('<html><head><title>Test</title></head><body><h1>A</h1><h2>B</h2></body></html>').tree
    )

    # Select elements from DOM tree
    css = CSS(tree=tree)
    elements = css.select('h1, h2, h3')
    is_deeply_ok([e[1] for e in elements], ['h1', 'h2'], 'elements')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.DOM.CSS

    # Select elements from DOM tree
    css = Pyjo.DOM.CSS.new(tree=tree)
    elements = css.select('h1, h2, h3')
    is_deeply_ok([e[1] for e in elements], ['h1', 'h2'], 'elements')

with subtest('*'):
    all = css.select('*')
    isa_ok(all, list, 'all')

with subtest('E'):
    title = css.select('title')
    isa_ok(title, list, 'title')

with subtest('E[foo]'):
    links = css.select('a[href]')
    isa_ok(links, list, 'links')

with subtest('E[foo="bar"]'):
    case_sensitive = css.select('input[type="hidden"]')
    isa_ok(case_sensitive, list, 'case_sensitive')
    case_sensitive = css.select('input[type=hidden]')
    isa_ok(case_sensitive, list, 'case_sensitive')

with subtest('E[foo="bar" i]'):
    case_insensitive = css.select('input[type="hidden" i]')
    isa_ok(case_insensitive, list, 'case_insensitive')
    case_insensitive = css.select('input[type=hidden i]')
    isa_ok(case_insensitive, list, 'case_insensitive')
    case_insensitive = css.select('input[class~="foo" i]')
    isa_ok(case_insensitive, list, 'case_insensitive')

with subtest('E[foo="bar" s]'):
    case_sensitive = css.select('input[type="hidden" s]')
    isa_ok(case_sensitive, list, 'case_sensitive')

with subtest('E[foo~="bar"]'):
    foo = css.select('input[class~="foo"]')
    isa_ok(foo, list, 'foo')
    foo = css.select('input[class~=foo]')
    isa_ok(foo, list, 'foo')

with subtest('E[foo^="bar"]'):
    begins_with = css.select('input[name^="f"]')
    isa_ok(begins_with, list, 'begins_with')
    begins_with = css.select('input[name^=f]')
    isa_ok(begins_with, list, 'begins_with')

with subtest('E[foo$="bar"]'):
    ends_with = css.select('input[name$="o"]')
    isa_ok(ends_with, list, 'ends_with')
    ends_with = css.select('input[name$=o]')
    isa_ok(ends_with, list, 'ends_with')

with subtest('E[foo*="bar"]'):
    contains = css.select('input[name*="fo"]')
    isa_ok(contains, list, 'contains')
    contains = css.select('input[name*=fo]')
    isa_ok(contains, list, 'contains')

with subtest('E[foo|="en"]'):
    english = css.select('link[hreflang|=en]')
    isa_ok(english, list, 'english')

with subtest('E:root'):
    root = css.select(':root')
    isa_ok(root, list, 'root')

with subtest('E:nth-child(n)'):
    third = css.select('div:nth-child(3)')
    isa_ok(third, list, 'third')
    odd = css.select('div:nth-child(odd)')
    isa_ok(odd, list, 'odd')
    even = css.select('div:nth-child(even)')
    isa_ok(even, list, 'even')
    top3 = css.select('div:nth-child(-n+3)')
    isa_ok(top3, list, 'top3')

with subtest('E:nth-last-child(n)'):
    third = css.select('div:nth-last-child(3)')
    isa_ok(third, list, 'third')
    odd = css.select('div:nth-last-child(odd)')
    isa_ok(odd, list, 'odd')
    even = css.select('div:nth-last-child(even)')
    isa_ok(even, list, 'even')
    bottom3 = css.select('div:nth-last-child(-n+3)')
    isa_ok(bottom3, list, 'bottom3')

with subtest('E:nth-of-type(n)'):
    third = css.select('div:nth-of-type(3)')
    isa_ok(third, list, 'third')
    odd = css.select('div:nth-of-type(odd)')
    isa_ok(odd, list, 'odd')
    even = css.select('div:nth-of-type(even)')
    isa_ok(even, list, 'even')
    top3 = css.select('div:nth-of-type(-n+3)')
    isa_ok(top3, list, 'top3')

with subtest('E:nth-last-of-type(n)'):
    third = css.select('div:nth-last-of-type(3)')
    isa_ok(third, list, 'third')
    odd = css.select('div:nth-last-of-type(odd)')
    isa_ok(odd, list, 'odd')
    even = css.select('div:nth-last-of-type(even)')
    isa_ok(even, list, 'even')
    bottom3 = css.select('div:nth-last-of-type(-n+3)')
    isa_ok(bottom3, list, 'bottom3')

with subtest('E:first-child'):
    first = css.select('div p:first-child')
    isa_ok(first, list, 'first')

with subtest('E:last-child'):
    last = css.select('div p:last-child')
    isa_ok(last, list, 'last')

with subtest('E:first-of-type'):
    first = css.select('div p:first-of-type')
    isa_ok(first, list, 'first')

with subtest('E:last-of-type'):
    last = css.select('div p:last-of-type')
    isa_ok(last, list, 'last')

with subtest('E:only-child'):
    lonely = css.select('div p:only-child')
    isa_ok(lonely, list, 'lonely')

with subtest('E:only-of-type'):
    lonely = css.select('div p:only-of-type')
    isa_ok(lonely, list, 'lonely')

with subtest('E:empty'):
    empty = css.select(':empty')
    isa_ok(empty, list, 'empty')


with subtest('E:link'):
    links = css.select(':any-link')
    isa_ok(links, list, 'links')
    links = css.select(':link')
    isa_ok(links, list, 'links')
    links = css.select(':visited')
    isa_ok(links, list, 'links')


with subtest('E:scope'):
    scoped = css.select('a:not(:scope > a)')
    isa_ok(scoped, list, 'scoped')
    scoped = css.select('div :scope p')
    isa_ok(scoped, list, 'scoped')
    scoped = css.select('~ p')
    isa_ok(scoped, list, 'scoped')

with subtest('E:checked'):
    input = css.select(':checked')
    isa_ok(input, list, 'input')

with subtest('E.warning'):
    warning = css.select('div.warning')
    isa_ok(warning, list, 'warning')

with subtest('E#myid'):
    foo = css.select('div#foo')
    isa_ok(foo, list, 'foo')

with subtest('E:not(s1, s2)'):
    others = css.select('div p:not(:first-child, :last-child)')
    isa_ok(others, list, 'others')

with subtest('E:is(s1, s2)'):
    headers = css.select(':is(section, article, aside, nav) h1')
    isa_ok(headers, list, 'headers')

with subtest('E:has(rs1, rs2)'):
    link = css.select('a:has(> img)')
    isa_ok(link, list, 'link')

with subtest('E:text(string_or_regex)'):
    # Substring match
    login = css.select(':text(Log in)')
    isa_ok(login, list, 'login')
    # Regex match
    login = css.select(':text(/Log ?in/)')
    isa_ok(login, list, 'login')
    # Regex match (case-insensitive)
    login = css.select(':text(/(?i:Log ?in)/)')
    isa_ok(login, list, 'login')

with subtest('A|E'):
    elem = css.select('lq|elem', lq='http://example.com/q-markup')
    isa_ok(elem, list, 'elem')
    div = css.select('|div')
    isa_ok(div, list, 'div')

with subtest('E F'):
    headlines = css.select('div h1')
    isa_ok(headlines, list, 'headlines')

with subtest('E > F'):
    headlines = css.select('html > body > div > h1')
    isa_ok(headlines, list, 'headlines')

with subtest('E + F'):
    second = css.select('h1 + h2')
    isa_ok(second, list, 'second')

with subtest('E ~ F'):
    second = css.select('h1 ~ h2')
    isa_ok(second, list, 'second')

with subtest('E, F, G'):
    headlines = css.select('h1, h2, h3')
    isa_ok(headlines, list, 'headlines')

with subtest('E[foo=bar][bar=baz]'):
    links = css.select('a[foo^=b][foo$=ar]')
    isa_ok(links, list, 'links')

with subtest('tree'):
    tree = css.tree
    css.tree = ['root']
    is_deeply_ok(css.tree, ['root'], 'tree')
    css.tree = tree

with subtest('matches'):
    boolean = Pyjo.DOM.CSS.new(tree=css.select_one('title')).matches('head > title')
    ok(boolean, 'matches')
    boolean = css.matches('svg|line', svg='http://www.w3.org/2000/svg')
    none_ok(boolean, 'root is not an element')

with subtest('select'):
    results = css.select('head > title')
    is_ok(results[0][1], 'title', 'results')
    results = css.select('svg|line', svg='http://www.w3.org/2000/svg')
    is_deeply_ok(results, [], 'no results')

with subtest('select_iter'):
    results = css.select_iter('head > title')
    is_ok(next(results)[1], 'title', 'results')
    results = css.select_iter('svg|line', svg='http://www.w3.org/2000/svg')
    is_deeply_ok(list(results), [], 'no results')

with subtest('select_one'):
    result = css.select_one('head > title')
    is_ok(result[1], 'title', 'result')
    result = css.select_one('svg|line', svg='http://www.w3.org/2000/svg')
    none_ok(result, 'no result')

done_testing()
