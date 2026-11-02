import Pyjo.App.Lambda

from Pyjo.File import curfile
from Pyjoyment.Lite import *


# The WSGI application of hello_wsgi.py, the ASGI application of hello_asgi.py and the event function of AWS Lambda of
# hello_lambda.py, next to this script, on one server, next to the routes of this application
plugin('Mount', {'/wsgi': 'hello_wsgi:app'})
plugin('Mount', {'/asgi': 'hello_asgi:app'})
plugin('Mount', {'/lambda': Pyjo.App.Lambda.new(function='hello_lambda.handler', task_root=curfile().dirname())})

get('/', {'text': 'I ♥ Pyjoyment!'})

app.start()
