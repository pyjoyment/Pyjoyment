---
name: scraping
description: Request web pages and APIs and extract data from them with Pyjo.UserAgent and Pyjo.DOM, ported from Mojo::UserAgent and Mojo::DOM. Use for web scraping with CSS selectors, JSON APIs with JSON Pointers, blocking requests in scripts, concurrent requests with promises, redirects, timeouts, headers, forms, cookies and proxies, HTML that is parsed or changed, and the one-liners of python -m Pyjo.
---

# Web scraping

`Pyjo.UserAgent` requests a URL and gives a transaction, `tx`, whose response
parses its HTML into `Pyjo.DOM`, which CSS selectors query, and its JSON,
which JSON Pointers query. A request without a callback blocks until the
response is there, as a script wants; `get_p` gives a promise, so many
requests run at the same time in the event loop.

## A page and an API

```python
# scrape.py
import Pyjo.URL
import Pyjo.UserAgent

import sys


url = sys.argv[1] if len(sys.argv) > 1 else 'https://pyjoyment.readthedocs.io/'

# Redirects followed, and limits of time, where the defaults wait longer
ua = Pyjo.UserAgent.new(max_redirects=5, connect_timeout=5, request_timeout=20)
ua.transactor.name = 'MyScraper/1.0'

# result raises an exception for an error of the connection, but not for a response of an error, as 404
tx = ua.get(url, {'Accept-Language': 'en'})
res = tx.result
if not res.is_success:
    sys.exit(f'{res.code} {res.message}')

dom = res.dom()
print(dom.at('title').text)

# The first links, absolute with the URL of the request, after the redirects
for href in dom.find('a[href]').map('attr', 'href').head(3):
    print(Pyjo.URL.new(href).to_abs(tx.req.url))

# The text of the items of a list, as one string
print(dom.find('ul.items li').map('all_text').join(', '))

# JSON, with a JSON Pointer into it
api = ua.get(Pyjo.URL.new('/api/items').to_abs(tx.req.url)).result
print(api.json('/items/0/name'))
```

- `dom.at(css)` is the first element or `None`, `dom.find(css)` a
  `Pyjo.Collection` of all, with `map`, `grep`, `first`, `head`, `join`,
  `each` and `size`; an element has `text` (its own), `all_text` (of its
  descendants too), `attr('href')`, `tag`, `children(css)`, `parent`.
- `dom.iterate(css)` is a lazy `Pyjo.Iterator` of the same elements, found as
  they are taken, so that the first one is processed before the last one is
  found, and `first` stops the search.
- `ua.get(url, headers, form={...})`, `ua.post(url, json={...})`, a body as
  bytes after the headers; `res.code`, `res.headers.content_type`, `res.text`,
  `res.json()`, `res.dom()`, `res.save_to(path)`.
- The user agent keeps the cookies of its responses, as a browser does, in
  `ua.cookie_jar`; `ua.proxy.detect()` takes the proxy of `HTTP_PROXY` and
  `HTTPS_PROXY`.

## Many pages at the same time

```python
# titles.py
import Pyjo.Promise
import Pyjo.UserAgent

import sys


urls = sys.argv[1:] or ['https://pyjoyment.readthedocs.io/', 'https://github.com/pyjoyment/Pyjoyment']
ua = Pyjo.UserAgent.new(max_redirects=5, request_timeout=20)


def title(tx):
    print(f'{tx.req.url}: {tx.result.dom().at("title").text}')


# Three requests at a time, each title as it comes, and the script waits for the last one
promise = Pyjo.Promise.map(lambda url: ua.get_p(url).then(title), *urls, concurrency=3)
promise.catch(lambda err: sys.exit(f'Failed: {err}')).wait()
```

- `wait()` runs the event loop until the promise settles, which a script
  does; an application awaits the promise in an `async def` action instead.

## HTML without a request

```python
# dom.py
import Pyjo.DOM


dom = Pyjo.DOM.new('<ul id="fruits"><li class="a">Apple</li><li>Banana</li></ul>')
print(dom.at('#fruits li.a').text)
print(dom.find('li').map('text').join(', '))

# Changed in place
dom.at('ul').append_content('<li>Cherry</li>')
dom.at('li.a').remove()
print(dom)
```

## One-liners

```sh
python -m Pyjo 'g("https://pyjoyment.readthedocs.io").dom().at("title").text'
python -m Pyjo 'g("https://api.github.com/repos/pyjoyment/Pyjoyment").json("/stargazers_count")'
python -m Pyjo 'x("<p>Hello <b>World</b></p>").at("b").text'
PYJO_MAX_REDIRECTS=0 python -m Pyjo 'g("http://github.com").code'
```

`from Pyjo import *` gives the same functions to a script: `g`, `p`, `w`
and the other methods of HTTP, `x` for the DOM, `j` for JSON.

## Mistakes

- `tx.result` raises for an error of the connection, as a refused one or a
  timeout, but gives the response of an error of HTTP: check
  `res.is_success` or `res.code`.
- The user agent follows no redirects by default: `max_redirects`.
- A blocking request inside an application, `c.ua().get(url)` in an action,
  stops the event loop: an action awaits `c.ua().get_p(url)`.
- `text` is the text of the element itself, without the text of its
  descendants, as `<p>Hello <b>World</b></p>` gives `Hello`: `all_text` takes
  it all.
- A URL of an attribute is relative to the page: `to_abs(tx.req.url)`.
- A script with the name of a module of the standard library, as
  `concurrent.py`, `json.py` or `email.py`, hides it from every module that
  imports it, as the directory of a script comes first in `sys.path`.
- A signature of a request, as Signature Version 4 of AWS or the HMAC of an
  API, is made in the event `start`, where the URL is absolute, but `Host` and
  `Content-Length` are not set yet: the signature sets `Host` itself and
  leaves out `Content-Length`. With requests at the same time, a subscriber
  signs its own transaction only, `if tx is mine`, and unsubscribes, as
  `once` takes the one that starts next.
- A request has no limit of its whole time, `request_timeout` is `0`, and 40
  seconds without data, `inactivity_timeout`: a batch of long requests sets
  both, so that one that hangs or trickles ends.
## Documentation

- Pyjo.UserAgent: https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_UserAgent.html
- Pyjo.DOM: https://pyjoyment.readthedocs.io/en/latest/api/Pyjo_DOM.html
- Pyjo, the one-liners: https://pyjoyment.readthedocs.io/en/latest/api/Pyjo.html
- Cookbook, user agent: https://pyjoyment.readthedocs.io/en/latest/guides/cookbook.html
