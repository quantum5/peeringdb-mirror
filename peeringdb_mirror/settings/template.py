from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-6)a5p^78%y9fvd)1r5troa=chey4tusp5!8t)pnda^&52)k3r('

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = []

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# PeeringDB configuration
PEERINGDB_API = 'https://www.peeringdb.com/api'
PEERINGDB_API_KEY = None
