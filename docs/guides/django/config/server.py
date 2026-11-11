import os


# A WSGI application blocks, so it runs on the reactor of Poll, which is chosen before Pyjoyment is imported
os.environ.setdefault('PYJO_REACTOR', 'Pyjo.Reactor.Poll')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from Pyjoyment.Lite import *  # noqa: E402

from django.conf import settings  # noqa: E402
from django.core.signals import request_finished, request_started  # noqa: E402
from django.db import connection  # noqa: E402


# The static files of collectstatic, served before the routes, with the hashed names of ManifestStaticFilesStorage
# cached for a year
app.static.paths = [str(settings.STATIC_ROOT.parent)]
app.static.immutable = r'^static/.+\.[0-9a-f]{12}\.[^/.]+$'
app.static.cache_control = 'public, max-age=60'


# The database, in a request of Django, whose handlers close a connection that the database has dropped
def database(c):
    request_started.send(sender=__name__)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    finally:
        request_finished.send(sender=__name__)


# /livez and /readyz, and the /healthz of the project, which stays its own
plugin('Health', checks={'database': database}, healthz=None)

# The access log of gunicorn, without the probes
plugin('AccessLog')

# The project, which gets every request that the routes before do not match
plugin('Mount', {'/': 'config.wsgi:application'})

if __name__ == '__main__':
    app.start()
