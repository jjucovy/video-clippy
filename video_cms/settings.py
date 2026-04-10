"""
Django settings for video_cms project.
"""

import os
from pathlib import Path
from decouple import config, Csv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Render.com sets RENDER_EXTERNAL_HOSTNAME to the service's public hostname.
# Add it automatically so we never need to hard-code the random subdomain.
_render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_hostname and _render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_hostname)

# CSRF trusted origins — required by Django 4.0+ for any non-localhost HTTPS request.
# Without this the admin login (and any form POST) returns 403.
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())
if _render_hostname:
    _render_origin = f'https://{_render_hostname}'
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)

# Render terminates SSL at the edge and forwards requests over HTTP internally.
# This tells Django to trust the X-Forwarded-Proto header so it knows the
# original request was HTTPS (needed for CSRF, secure cookies, etc.).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'django_filters',
    'corsheaders',
    'django_q',

    # Local
    'archive',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'video_cms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'video_cms.wsgi.application'

# Database
_db_url = config('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
DATABASES = {
    'default': dj_database_url.parse(_db_url, conn_max_age=600)
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalisation
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

# CORS — allow the Astro frontend (and admin tools) to call the API
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https?://localhost(:\d+)?$',
    r'^https?://127\.0\.0\.1(:\d+)?$',
]
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
# In production set CORS_ALLOWED_ORIGINS in the environment; in dev allow all
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# Cloudflare Stream
CLOUDFLARE_ACCOUNT_ID = config('CLOUDFLARE_ACCOUNT_ID', default='')
CLOUDFLARE_API_TOKEN = config('CLOUDFLARE_API_TOKEN', default='')

# Cloudflare R2
R2_ACCOUNT_ID = config('R2_ACCOUNT_ID', default='')
R2_ACCESS_KEY_ID = config('R2_ACCESS_KEY_ID', default='')
R2_SECRET_ACCESS_KEY = config('R2_SECRET_ACCESS_KEY', default='')
R2_BUCKET_NAME = config('R2_BUCKET_NAME', default='')
R2_PUBLIC_URL = config('R2_PUBLIC_URL', default='')

# django-q2 cluster configuration
Q_CLUSTER = {
    'name': 'video_cms',
    'workers': 2,
    'recycle': 500,
    'timeout': 3600,       # 1-hour task timeout (must be < retry)
    'retry': 3700,         # retry after 1h 1m40s — must exceed timeout
    'compress': True,
    'save_limit': 250,
    'queue_limit': 50,
    'cpu_affinity': 1,
    'label': 'Django Q2',
    'orm': 'default',      # use the default DB as broker
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
