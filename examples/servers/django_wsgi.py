import os


# A WSGI application blocks, so it runs on the reactor of Poll, which is chosen before Pyjoyment is imported
os.environ.setdefault('PYJO_REACTOR', 'Pyjo.Reactor.Poll')

import Pyjo.UserAgent  # noqa: E402

from Pyjoyment.Lite import *  # noqa: E402

from django.conf import settings  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402
from django.http import HttpResponse, JsonResponse  # noqa: E402
from django.urls import path  # noqa: E402


# A project of Django in one file
settings.configure(ROOT_URLCONF=__name__, ALLOWED_HOSTS=['*'], SECRET_KEY='insecure', TIME_ZONE='UTC')

# The user agent of the views, in the place of requests, and the API of GitHub, or the one of GITHUB_API_URL
ua = Pyjo.UserAgent.new()
api = os.environ.get('GITHUB_API_URL', 'https://api.github.com')


def index(request):
    return HttpResponse(f'Hello from Django at {request.path}!')


# A blocking request, which runs an event loop of its own, while the worker waits for it as for a query of the ORM
def release(request):
    res = ua.get(f'{api}/repos/pyjoyment/Pyjoyment/releases/latest').result
    return JsonResponse({'status': res.code, 'release': res.json('/tag_name')})


urlpatterns = [path('', index), path('release', release)]

plugin('Mount', {'/': get_wsgi_application()})

app.start()
