"""
Base settings for core project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from django.contrib.messages import constants as message_constants

# loading env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key')

INSTALLED_APPS = [
    # Unfold admin
    'unfold',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Global APPS
    'oauth',

    # Local APPS
    'user_app',
    'dashboard_app',
    'book_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # Book processor
                'book_app.context_processors.book_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

LANGUAGE_CODE = 'uz'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = "user_app.User"

MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'

MESSAGE_TAGS = {
    message_constants.DEBUG: 'debug',
    message_constants.INFO: 'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'danger',
}

# OAuth settings
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
AUTHORIZE_URL = os.getenv('AUTHORIZE_URL')
ACCESS_TOKEN_URL = os.getenv('ACCESS_TOKEN_URL')
RESOURCE_OWNER_URL = os.getenv('RESOURCE_OWNER_URL')
EMPLOYE_AUTHORIZE_URL = os.getenv('EMPLOYE_AUTHORIZE_URL')
EMPLOYE_ACCESS_TOKEN_URL = os.getenv('EMPLOYE_ACCESS_TOKEN_URL')
EMPLOYE_RESOURCE_OWNER_URL = os.getenv('EMPLOYE_RESOURCE_OWNER_URL')
