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
