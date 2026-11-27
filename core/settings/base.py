"""
Base settings for core project.
"""
import os
from pathlib import Path

from django.contrib.messages import constants as message_constants
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# loading env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key')

INSTALLED_APPS = [
    # Unfold admin
    'unfold',
    'unfold.contrib.filters',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',   # FTS, trigram, JSON lookuplar

    # Third party
    'django_htmx',

    # Global APPS
    'oauth',

    # Local APPS
    'audit',
    'user_app',
    'dashboard_app',
    'book_app',
    'holdings',
    'circulation',
    'reading',
    'engagement',
    'notifications',
    'panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'audit.middleware.AuditContextMiddleware',
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
                # Bildirishnomalar (o'qilmaganlar soni)
                'notifications.context_processors.notifications',
                # Kutubxonachi sidebar statistikasi
                'dashboard_app.context_processors.librarian',
                # Funksiya flaglari ({{ flags.<nom> }})
                'core.context_processors.feature_flags',
                # Ruxsat flaglari ({{ perms_flags }})
                'core.context_processors.permissions',
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

# Loyiha darajasidagi statik fayllar (app.css, ui.js, vendor kutubxonalari).
# MUHIM: bu ro'yxat ilgari faqat `local.py` da edi — shu sababli production'da
# `collectstatic` ularni yig'masdan, saytda CSS/JS yo'q bo'lib qolardi.
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = "user_app.User"

# ---------------------------------------------------------------------------
# Funksiya flaglari — standart qiymatlar `core/flags.py`da, bu yerda loyiha
# bo'yicha ustun qiymat beriladi. Muhitdan: FLAG_<NOM>=1/0
# ---------------------------------------------------------------------------
FEATURE_FLAGS: dict[str, bool] = {}

# Autentifikatsiya yo'naltirishlari
LOGIN_URL = '/auth/student-login/'
LOGIN_REDIRECT_URL = '/dashboard/'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        # Loyiha modullari
        'oauth': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'circulation': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'audit': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'jobs': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

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
    "SHOW_BACK_BUTTON": True,

    # Brend ranglari (saytdagi navy bilan mos)
    "COLORS": {
        "primary": {
            "50": "238 242 249",
            "100": "215 224 239",
            "200": "176 194 221",
            "300": "129 156 196",
            "400": "84 116 166",
            "500": "55 87 137",
            "600": "42 68 112",
            "700": "32 51 90",
            "800": "22 36 63",
            "900": "14 26 48",
            "950": "7 15 32",
        },
    },

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
                        "link": reverse_lazy("admin:book_app_item_changelist"),
                        "badge": "core.unfold_badges.available_copies",
                    },
                    {
                        "title": _("Nashriyotlar"),
                        "icon": "domain",
                        "link": reverse_lazy("admin:book_app_publisher_changelist"),
                    },
                    {
                        "title": _("Mavzular"),
                        "icon": "sell",
                        "link": reverse_lazy("admin:book_app_subject_changelist"),
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
                "title": _("Fond tuzilmasi"),
                "separator": True,
                "items": [
                    {
                        "title": _("Filiallar"),
                        "icon": "account_balance",
                        "link": reverse_lazy("admin:holdings_library_changelist"),
                    },
                    {
                        "title": _("Nusxa turlari"),
                        "icon": "category",
                        "link": reverse_lazy("admin:holdings_itemtype_changelist"),
                    },
                    {
                        "title": _("Javonlar"),
                        "icon": "shelves",
                        "link": reverse_lazy("admin:holdings_shelflocation_changelist"),
                    },
                    {
                        "title": _("Nusxa jurnali"),
                        "icon": "history",
                        "link": reverse_lazy("admin:book_app_itemstatuslog_changelist"),
                    },
                ],
            },
            {
                "title": _("Ijara"),
                "separator": True,
                "items": [
                    {
                        "title": _("Ijara so'rovlari"),
                        "icon": "assignment",
                        "link": reverse_lazy("admin:circulation_rentalrequest_changelist"),
                        "badge": "core.unfold_badges.pending_requests",
                    },
                    {
                        "title": _("Navbatlar"),
                        "icon": "schedule",
                        "link": reverse_lazy("admin:circulation_reservation_changelist"),
                        "badge": "core.unfold_badges.waiting_reservations",
                    },
                    {
                        "title": _("Jarimalar"),
                        "icon": "payments",
                        "link": reverse_lazy("admin:circulation_fine_changelist"),
                        "badge": "core.unfold_badges.unpaid_fines",
                    },
                    {
                        "title": _("Sozlamalar"),
                        "icon": "settings",
                        "link": reverse_lazy("admin:circulation_librarysettings_changelist"),
                    },
                ],
            },
            {
                "title": _("Faollik"),
                "separator": True,
                "items": [
                    {
                        "title": _("Sharhlar"),
                        "icon": "rate_review",
                        "link": reverse_lazy("admin:engagement_review_changelist"),
                        "badge": "core.unfold_badges.pending_reviews",
                    },
                    {
                        "title": _("Sevimlilar"),
                        "icon": "favorite",
                        "link": reverse_lazy("admin:engagement_favorite_changelist"),
                    },
                    {
                        "title": _("O'qish jarayoni"),
                        "icon": "auto_stories",
                        "link": reverse_lazy("admin:reading_readingprogress_changelist"),
                    },
                    {
                        "title": _("O'qish tarixi"),
                        "icon": "history",
                        "link": reverse_lazy("admin:reading_readinghistory_changelist"),
                    },
                    {
                        "title": _("Bildirishnomalar"),
                        "icon": "notifications",
                        "link": reverse_lazy("admin:notifications_notification_changelist"),
                    },
                ],
            },
            {
                "title": _("A'zolik"),
                "separator": True,
                "items": [
                    {
                        "title": _("Kutubxona a'zolari"),
                        "icon": "card_membership",
                        "link": reverse_lazy("admin:user_app_patron_changelist"),
                        "badge": "core.unfold_badges.patron_count",
                    },
                    {
                        "title": _("A'zo toifalari"),
                        "icon": "groups_2",
                        "link": reverse_lazy("admin:user_app_patroncategory_changelist"),
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
