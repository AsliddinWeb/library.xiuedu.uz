"""
Qidiruv indeksini avtomatik yangilab turish.

Kitob saqlanganda, muallif yoki mavzu biriktirilganda `search_text` va
`search_vector` qayta hisoblanadi — kutubxonachi hech narsa qilmaydi.

Rekursiya yo'q: indeks `queryset.update()` bilan yoziladi, ya'ni `post_save`
qayta chaqirilmaydi.
"""
import logging

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import Book, Contributor
from .search import update_search_text

logger = logging.getLogger('search')


def _reindex(book):
    try:
        update_search_text(book)
    except Exception:  # indeks xatosi saqlashni buzmasligi kerak
        logger.exception("Qidiruv indeksini yangilab bo'lmadi: book=%s", getattr(book, 'pk', None))


@receiver(post_save, sender=Book)
def book_saved(sender, instance, raw=False, **kwargs):
    if raw:            # fixture yuklanmoqda
        return
    _reindex(instance)


@receiver([post_save, post_delete], sender=Contributor)
def contributor_changed(sender, instance, **kwargs):
    if instance.book_id:
        _reindex(instance.book)


@receiver(m2m_changed, sender=Book.subjects.through)
def subjects_changed(sender, instance, action, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear') and isinstance(instance, Book):
        _reindex(instance)
