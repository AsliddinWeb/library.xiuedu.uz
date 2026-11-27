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
# HTTPS. Standart holatda YOQILGAN — production sayt sertifikat bilan ishlashi kerak.
#
# MUHIM: sertifikat hali o'rnatilmagan bo'lsa (nginx faqat 80-portni tinglaydi),
# bu sozlama saytni ISHLAMAY QO'YADI: Django har so'rovni https'ga yo'naltiradi,
# brauzer esa 443-portga ulana olmaydi. Shunday holatda vaqtincha:
#
#     echo "USE_HTTPS=0" >> .env && sudo systemctl restart library
#
# va imkon qadar tezroq sertifikat o'rnating:
#
#     sudo certbot --nginx -d library.xiuedu.uz
#
# Sertifikat o'rnatilgach `USE_HTTPS` satrini .env dan olib tashlang.
USE_HTTPS = os.getenv('USE_HTTPS', '1').strip().lower() not in ('0', 'false', 'no', 'off')

SECURE_SSL_REDIRECT = USE_HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000 if USE_HTTPS else 0  # 1 yil
SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_HTTPS
SECURE_HSTS_PRELOAD = USE_HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Raqamli kitoblar (ebook/audio) himoyasi — nginx internal location orqali
# beriladi. nginx: location /protected-media/ { internal; alias /.../media/; }
USE_X_ACCEL_REDIRECT = True
X_ACCEL_LOCATION = '/protected-media'

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
