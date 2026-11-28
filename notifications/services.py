from django.utils.text import Truncator

from .models import Notification


def notify(user, title, message='', type=Notification.Type.GENERAL, link=''):
    """Foydalanuvchiga bildirishnoma yuboradi."""
    if user is None:
        return None
    # Kitob nomi 500 belgigacha — maydonga sig'masa amalning o'zi yiqilmasin
    field = Notification._meta.get_field
    return Notification.objects.create(
        user=user, type=type, link=link,
        title=Truncator(title).chars(field('title').max_length),
        message=Truncator(message).chars(field('message').max_length))


def unread_count(user):
    if user is None or not getattr(user, 'is_authenticated', False):
        return 0
    return Notification.objects.filter(user=user, is_read=False).count()
