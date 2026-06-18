from .models import Notification


def notify(user, title, message='', type=Notification.Type.GENERAL, link=''):
    """Foydalanuvchiga bildirishnoma yuboradi."""
    if user is None:
        return None
    return Notification.objects.create(
        user=user, type=type, title=title, message=message, link=link)


def unread_count(user):
    if user is None or not getattr(user, 'is_authenticated', False):
        return 0
    return Notification.objects.filter(user=user, is_read=False).count()
