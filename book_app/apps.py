from django.apps import AppConfig


class BookAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'book_app'
    verbose_name = "Kitoblar"

    def ready(self):
        from . import signals  # noqa: F401  (qidiruv indeksi signallari)
