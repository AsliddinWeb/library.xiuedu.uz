from .services import unread_count


def notifications(request):
    return {'unread_notifications': unread_count(getattr(request, 'user', None))}
