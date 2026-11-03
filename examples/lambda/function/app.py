# /// script
# requires-python = ">=3.12"
# dependencies = ["Pyjoyment"]
#
# [tool.uv.sources]
# Pyjoyment = { path = "../../.." }
# ///
import Pyjo.App.FastCGI
import Pyjo.File
import Pyjo.INI
import Pyjo.IOLoop
import Pyjo.IOLoop.ChildProcess

from Pyjoyment.Lite import *

import os


@get('/')
def index(c):
    c.render(text='Hello Pyjoyment on AWS Lambda!')


# What the function gets of a request, after the load balancer and the event
@any('/echo')
def echo(c):
    req = c.req
    c.render(
        json={
            'method': req.method,
            'path': req.url.path.to_str(),
            'query': req.query_params.to_dict(),
            'body': req.text,
        }
    )


# PHP of a layer with php-fpm, as the one of Bref in the variable "layers", or of PHP_FPM, started with the execution
# environment, with phpinfo.php under /php
PHP_FPM = os.environ.get('PHP_FPM', '/opt/bin/php-fpm')

if os.path.exists(PHP_FPM):
    conf = Pyjo.File.tempfile(suffix='.conf').spew(
        Pyjo.INI.dump(
            {
                'global': {'error_log': '/dev/stderr', 'daemonize': False},
                'www': {
                    'listen': '/tmp/php-fpm.sock',
                    'pm': 'static',
                    'pm.max_children': 1,
                    'clear_env': False,
                    'catch_workers_output': True,
                    'decorate_workers_output': False,
                },
            }
        )
    )
    # In a group of its own, which the end of the interpreter kills, with its workers
    php_fpm = Pyjo.IOLoop.ChildProcess.new().spawn([PHP_FPM, '-n', '-y', conf.to_str(), '-F'], detached=True)
    ready = []

    # Its log in the one of the application, until it is ready, or ends
    @php_fpm.stderr.on('read')
    def log(stream, chunk):
        for line in chunk.decode(errors='replace').splitlines():
            app.log.info(f'php-fpm: {line}')
        if b'ready to handle connections' in chunk:
            ready.append(True)

    php_fpm.on('close', lambda child, code, signal: ready.append(False))
    while not ready:
        Pyjo.IOLoop.one_tick()

    if ready[0]:
        script = Pyjo.File.curfile().sibling('phpinfo.php').to_str()
        plugin('Mount', {'/php': Pyjo.App.FastCGI.new(url='fcgi+unix://%2Ftmp%2Fphp-fpm.sock', script=script)})
    else:
        app.log.error('php-fpm: not started')


# The handler "app.handler" of the event function, and the command of the arguments otherwise
handler = app.start()
