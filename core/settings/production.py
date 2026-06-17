from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# SECRET_KEY production'da majburiy — default ishlatilmasligi kerak
if not os.getenv('SECRET_KEY'):
    raise ImproperlyConfigured("SECRET_KEY muhit o'zgaruvchisi production'da o'rnatilishi shart.")
SECRET_KEY = os.getenv('SECRET_KEY')

# Ruxsat etilgan hostlar (vergul bilan ajratib env orqali berish mumkin)
ALLOWED_HOSTS = os.getenv(
    'ALLOWED_HOSTS',
    'library.xiuedu.uz,www.library.xiuedu.uz',
).split(',')

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

# Xavfsizlik sozlamalari (HTTPS orqasida ishlaydi)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000  # 1 yil
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Statik fayllar (collectstatic chiqishi — whitenoise xizmat qiladi)
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
