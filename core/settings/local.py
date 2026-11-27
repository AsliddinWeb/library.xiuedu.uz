from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# ---------------------------------------------------------------------------
# Ma'lumotlar bazasi
#
# v3'dan boshlab dev muhitda ham PostgreSQL ishlatiladi — to'liq matnli qidiruv
# (FTS), trigram va JSON imkoniyatlari SQLite'da yo'q, shuning uchun "dev'da
# ishladi, prod'da ishlamadi" holati bo'lmasligi kerak.
#
# Lokal Postgres'ni ko'tarish:   make db-up      (docker-compose.yml)
# Vaqtincha SQLite'ga qaytish:   USE_SQLITE=1 python manage.py ...
# ---------------------------------------------------------------------------
if os.getenv('USE_SQLITE') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'library_db'),
            'USER': os.getenv('DB_USER', 'library_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'library_pass'),
            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

STATICFILES_DIRS = [BASE_DIR / 'static']
