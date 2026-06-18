from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def dropdown(request):
    """Topbar qo'ng'irog'i uchun so'nggi bildirishnomalar (HTMX)."""
    items = Notification.objects.filter(user=request.user)[:8]
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, 'notifications/partials/_dropdown.html',
                  {'items': items, 'unread': unread})


@login_required
def notification_list(request):
    items = Notification.objects.filter(user=request.user)
    return render(request, 'notifications/list.html', {'items': items})


@login_required
def mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=['is_read'])
    return redirect(n.link or 'notifications:list')


@require_POST
@login_required
def read_all(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    items = Notification.objects.filter(user=request.user)[:8]
    return render(request, 'notifications/partials/_dropdown.html',
                  {'items': items, 'unread': 0})
