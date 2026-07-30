import os
from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR.parent / 'frontend'

SECRET_KEY = config('SECRET_KEY', default='django-insecure-jumpstart-dev-2026')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    # daphne must come first so `manage.py runserver` serves ASGI (WebSockets)
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',
    # Local apps
    'accounts',
    'store',
    'chatbot',
    'agents',
    'tools',
    'rag',
    'services',
    'staff',
    'knowledge',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [FRONTEND_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='jumpstart_db'),
        'USER': config('DB_USER', default='jumpstart_user'),
        'PASSWORD': config('DB_PASSWORD', default='jumpstart2026'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'accounts.User'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [FRONTEND_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django Channels — in-memory for local dev
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS
CORS_ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
CORS_ALLOW_CREDENTIALS = True

# LLM — Ollama only (see report for why: Groq's daily token quota made
# iterative testing impractical, and larger local/Colab-hosted models gave
# more reliable instruction-following once tuned than the smallest local
# model did). OLLAMA_BASE_URL points at a local server or a tunnelled
# remote one (e.g. Colab + ngrok) depending on available hardware.
OLLAMA_MODEL = config('OLLAMA_MODEL', default='qwen2.5:14b-instruct-q4_K_M')
OLLAMA_BASE_URL = config('OLLAMA_BASE_URL', default='http://localhost:11434')

# Hugging Face Hub — optional token silences the "unauthenticated requests"
# warning and raises download rate limits. huggingface_hub reads it from the
# environment, so export it before any transformers/sentence-transformers import.
_hf_token = config('HF_TOKEN', default='')
if _hf_token:
    os.environ.setdefault('HF_TOKEN', _hf_token)

# Knowledge doc upload limit (20 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# Confidence thresholds
CONFIDENCE_HIGH = 0.80
CONFIDENCE_MEDIUM = 0.65
MAX_CLARIFICATION_ATTEMPTS = 2
MAX_TOOL_CALLS = 5
MAX_PLAN_STEPS = 5
MAX_REGENERATION_ATTEMPTS = 1

# When True, skips safety_check's LLM groundedness layer (Layer 2) entirely —
# the deterministic keyword pre-filter (Layer 1) still always runs. Cuts
# roughly one full LLM call (sometimes two, if it would have triggered a
# regeneration) off every turn that would have used it. Useful for faster
# manual evaluation iteration on a slow local/tunnelled model; leave False
# for real usage, since it removes a real (if secondary) safety layer.
SKIP_LLM_SAFETY_CHECK = config('SKIP_LLM_SAFETY_CHECK', default=False, cast=bool)

# Production hardening — activates when DEBUG=False in .env.
# The prototype runs locally over plain HTTP; a real deployment behind HTTPS
# gets secure cookies, SSL redirect, and HSTS automatically.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days; raise once stable
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_HTTPONLY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
