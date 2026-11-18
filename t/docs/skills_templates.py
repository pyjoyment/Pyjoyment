import Pyjo.File
import Pyjo.Test.Pyjo
import Pyjoyment

from Pyjo.Test import *

import importlib
import os
import re
import sys


# The code of plugins/pyjoyment/skills/templates/SKILL.md, each application in a file of its own, as a coding agent
# writes it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
Skills = importlib.import_module('Skills')

code = Skills.blocks('templates')
is_ok(len(code), 2, 'two applications')

tmp = Pyjo.File.tempdir()


def load(n):
    file = tmp.child(f'app{n}.py').spew(code[n])
    t = Pyjo.Test.Pyjo.new(file)
    t.app.log.level = 'fatal'
    return t


with subtest('Layouts, partials, blocks, forms'):
    t = load(0)
    t.get_ok('/').status_is(200).text_is('title', 'Shopping list').text_is('h1', 'Shopping list')
    t.element_exists('head meta[name="description"]').text_is('p', 'Nothing to buy.')
    t.content_like(r'&lt;b&gt;escaped&lt;/b&gt; <b>as it is</b>')
    t.element_exists('a[href="/add"]')
    t.get_ok('/add').status_is(200).text_is('title', 'Add an item').element_exists('form[method="POST"][action="/add"]')
    token = t.tx.res.dom().at('input[name="csrf_token"]').attr('value')
    t.post_ok('/add', form={'item': 'Bread'}).status_is(403).content_is('Bad CSRF token')
    t.post_ok('/add', form={'item': '', 'csrf_token': token}).status_is(400).text_is('p.error', 'The item is required.')
    t.post_ok('/add', form={'item': 'Bread', 'csrf_token': token}).status_is(302).header_is('Location', '/')
    t.get_ok('/').status_is(200).text_is('li', 'Bread')

with subtest('Template strings'):
    t = load(1)
    t.get_ok('/hello/Joe').status_is(200).text_is('p', 'Hello Joe! ').text_is('p a[href="/"]', 'Home')
    t.get_ok('/hello/%3Cb%3E').status_is(200).content_is('<p>Hello &lt;b&gt;! <a href="/">Home</a></p>')

with subtest('Nonce'):
    # The forms of the inline scripts and styles of the skill, with the Content-Security-Policy of SecurityHeaders
    app = Pyjoyment.new()
    app.log.level = 'fatal'
    app.plugin('SecurityHeaders', csp={'script-src': ["'self'"], 'style-src': ["'self'"]})
    template = (
        '%= javascript(begin\n  hello();\n%= end)\n'
        '%= stylesheet(begin\n  p {color: red}\n%= end)\n'
        '<script nonce="<%= csp_nonce() %>">world();</script>\n'
    )
    app.routes.get('/', lambda c: c.render(inline=template))
    t = Pyjo.Test.Pyjo.new(app)
    t.get_ok('/').status_is(200)
    nonce = t.tx.res.dom().at('script').attr('nonce')
    ok(nonce, 'nonce')
    is_ok(len(t.tx.res.dom(f'script[nonce="{nonce}"], style[nonce="{nonce}"]')), 3, 'every inline script and style')
    t.header_like('Content-Security-Policy', rf"script-src 'self' 'nonce-{re.escape(nonce)}'")

done_testing()
