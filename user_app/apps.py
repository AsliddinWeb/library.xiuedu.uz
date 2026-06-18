# from django.apps import AppConfig
#
#
# class UserAppConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'user_app'

from django.apps import AppConfig


class YourAppNameConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_app'
    verbose_name = "Foydalanuvchilar"

    def ready(self):
        from . import signals  # noqa: F401  (signal'larni ro'yxatdan o'tkazadi)

