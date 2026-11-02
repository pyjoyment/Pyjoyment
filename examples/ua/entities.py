import Pyjo.UserAgent

from Pyjo.String.Unicode import u


# Extract named character references from HTML spec
tx = Pyjo.UserAgent.new().get('https://html.spec.whatwg.org')
for n in tx.res.dom().iterate('#named-character-references-table tbody > tr'):
    u(n.at('td > code').text + ' ' + n.children('td')[1].text).trim().say()
