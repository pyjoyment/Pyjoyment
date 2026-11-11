import os

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'insecure')
DEBUG = os.environ.get('DJANGO_DEBUG') == '1'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = ['django.contrib.staticfiles', 'notes']
ROOT_URLCONF = 'config.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DATABASE', BASE_DIR / 'db.sqlite3'),
    },
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# The time zone of the process, which Django sets in TZ, so the logs of Pyjoyment have it too
TIME_ZONE = 'UTC'
USE_TZ = True

# The output of collectstatic, which Pyjoyment serves from the parent directory, with favicon.ico and robots.txt
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'public' / 'static'
