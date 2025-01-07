from .base import *

DEBUG = False

ALLOWED_HOSTS = ['library.xiuedu.uz', 'www.library.xiuedu.uz', '83.222.6.82', 'localhost']
CSRF_TRUSTED_ORIGINS = ["https://library.xiuedu.uz", "https://www.library.xiuedu.uz"]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
