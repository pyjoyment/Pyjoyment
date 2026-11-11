from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponse
from django.urls import path
from notes import views


def healthz(request):
    return HttpResponse('ok')


urlpatterns = [
    path('', views.index),
    path('notes', views.notes),
    path('healthz', healthz),
]

# With DEBUG only, the static files of the apps before collectstatic, after the ones that Pyjoyment serves
urlpatterns += staticfiles_urlpatterns()
