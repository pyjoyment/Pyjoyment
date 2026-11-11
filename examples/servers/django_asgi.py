import Pyjo.UserAgent

from Pyjoyment.Lite import *

import os

from django.conf import settings
from django.core.asgi import get_asgi_application
from django.http import HttpResponse, JsonResponse
from django.urls import path


# A project of Django in one file
settings.configure(ROOT_URLCONF=__name__, ALLOWED_HOSTS=['*'], SECRET_KEY='insecure', TIME_ZONE='UTC')

# The user agent of the views, in the place of httpx, and the API of GitHub, or the one of GITHUB_API_URL
ua = Pyjo.UserAgent.new()
api = os.environ.get('GITHUB_API_URL', 'https://api.github.com')


def index(request):
    return HttpResponse(f'Hello from Django at {request.path}!')


# A request awaited in the event loop of asyncio, which serves the other requests meanwhile
async def release(request):
    res = (await ua.get_p(f'{api}/repos/pyjoyment/Pyjoyment/releases/latest')).result
    return JsonResponse({'status': res.code, 'release': res.json('/tag_name')})


urlpatterns = [path('', index), path('release', release)]

# An ASGI application, on the reactor of asyncio, the default one
plugin('Mount', {'/': get_asgi_application()})

app.start()
