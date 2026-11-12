import Pyjo.IOLoop

from Pyjoyment.Lite import *

import os

from django.conf import settings
from django.core.signals import request_finished, request_started
from django.db import connection


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# The static files of collectstatic, served before the routes, with the hashed names of ManifestStaticFilesStorage
# cached for a year
app.static.paths = [str(settings.STATIC_ROOT.parent)]
app.static.immutable = r'^static/.+\.[0-9a-f]{12}\.[^/.]+$'
app.static.cache_control = 'public, max-age=60'


# The database, in a request of Django, whose handlers close a connection that the database has dropped
def database():
    request_started.send(sender=__name__)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    finally:
        request_finished.send(sender=__name__)


# /livez and /readyz, with the check of the database as blocking code, and the /healthz of the project, which stays its
# own
plugin('Health', checks={'database': lambda c: Pyjo.IOLoop.blocking(database)}, healthz=None)

# The access log of gunicorn, without the probes
plugin('AccessLog')

# The project, which gets every request that the routes before do not match
plugin('Mount', {'/': 'config.wsgi:application'})

if __name__ == '__main__':
    app.start()
