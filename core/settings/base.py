"""
Base settings for core project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from django.contrib.messages import constants as message_constants
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

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

    # Third party
    'django_htmx',

    # Global APPS
    'oauth',

    # Local APPS
    'user_app',
    'dashboard_app',
    'book_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
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

# Autentifikatsiya yo'naltirishlari
LOGIN_URL = '/auth/student-login/'
LOGIN_REDIRECT_URL = '/dashboard/'

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


# ---------------------------------------------------------------------------
# Unfold admin — custom sidebar va counter (badge)lar
# ---------------------------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": "XIU Library",
    "SITE_HEADER": "XIU Library",
    "SITE_SUBHEADER": "Elektron kutubxona boshqaruvi",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,

    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Boshqaruv"),
                "separator": False,
                "items": [
                    {
                        "title": _("Bosh sahifa"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": _("Kutubxona"),
                "separator": True,
                "items": [
                    {
                        "title": _("Kitoblar"),
                        "icon": "menu_book",
                        "link": reverse_lazy("admin:book_app_book_changelist"),
                        "badge": "core.unfold_badges.book_count",
                    },
                    {
                        "title": _("Kataloglar"),
                        "icon": "category",
                        "link": reverse_lazy("admin:book_app_genre_changelist"),
                        "badge": "core.unfold_badges.genre_count",
                    },
                    {
                        "title": _("Mualliflar"),
                        "icon": "edit_note",
                        "link": reverse_lazy("admin:book_app_author_changelist"),
                        "badge": "core.unfold_badges.author_count",
                    },
                    {
                        "title": _("Nusxalar"),
                        "icon": "library_books",
                        "link": reverse_lazy("admin:book_app_copy_changelist"),
                        "badge": "core.unfold_badges.available_copies",
                    },
                    {
                        "title": _("Ijaralar"),
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:book_app_rental_changelist"),
                        "badge": "core.unfold_badges.active_rentals",
                    },
                ],
            },
            {
                "title": _("Foydalanuvchilar"),
                "separator": True,
                "items": [
                    {
                        "title": _("Foydalanuvchilar"),
                        "icon": "group",
                        "link": reverse_lazy("admin:user_app_user_changelist"),
                        "badge": "core.unfold_badges.user_count",
                    },
                    {
                        "title": _("Talabalar"),
                        "icon": "school",
                        "link": reverse_lazy("admin:user_app_studentprofile_changelist"),
                        "badge": "core.unfold_badges.student_count",
                    },
                    {
                        "title": _("Hodimlar"),
                        "icon": "badge",
                        "link": reverse_lazy("admin:user_app_employeprofile_changelist"),
                        "badge": "core.unfold_badges.employee_count",
                    },
                    {
                        "title": _("Rollar"),
                        "icon": "shield_person",
                        "link": reverse_lazy("admin:user_app_role_changelist"),
                    },
                    {
                        "title": _("Guruhlar"),
                        "icon": "groups",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
        ],
    },
}
