import Pyjo.Promise

from Pyjoyment.Lite import *


# Non-blocking with async and await
@get('/headers')
async def headers(c):
    url = c.param('url') or 'https://github.com/pyjoyment/Pyjoyment'
    tx = await c.ua().get_p(url)
    c.render(json=tx.result.dom().find('h1, h2, h3').map('text').to_list())


# Non-blocking with a callback
@get('/title')
def title(c):
    c.ua().get('https://github.com/mojolicious/mojo', lambda ua, tx: c.render(text=tx.result.dom().at('title').text))


# Concurrent non-blocking
@get('/titles')
def titles(c):
    mojo = c.ua().get_p('https://github.com/mojolicious/mojo')
    pyjo = c.ua().get_p('https://github.com/pyjoyment/Pyjoyment')
    Pyjo.Promise.all(mojo, pyjo).then(
        lambda mojo, pyjo: c.render(
            json={
                'mojo': mojo[0].result.dom().at('title').text,
                'pyjo': pyjo[0].result.dom().at('title').text,
            }
        )
    ).wait()


app.start()
