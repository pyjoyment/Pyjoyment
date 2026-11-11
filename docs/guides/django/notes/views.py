from notes.models import Note

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt


def index(request):
    return HttpResponse(f'{Note.objects.count()} notes, {request.scheme} from {request.META["REMOTE_ADDR"]}')


@csrf_exempt
def notes(request):
    if request.method == 'POST':
        Note.objects.create(text=request.POST['text'])
    return JsonResponse({'notes': list(Note.objects.values_list('text', flat=True))})
