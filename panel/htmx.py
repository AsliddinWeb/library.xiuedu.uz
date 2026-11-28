"""Panel view'lari uchun umumiy HTMX yordamchilari."""
from django.shortcuts import render
from django_htmx.http import trigger_client_event


def toast(response, text, level='success'):
    """Javobga bildirishnoma qo'shadi (`static/js/ui.js` ko'rsatadi)."""
    trigger_client_event(response, 'toast', {'text': str(text), 'level': level})
    return response


def render_partial_or_page(request, page, partial, context):
    """HTMX so'roviga faqat bo'lak, oddiy so'rovga butun sahifa."""
    htmx = getattr(request, 'htmx', False)
    # Tarixdan tiklashda (back tugmasi) butun sahifa kerak
    if htmx and not getattr(htmx, 'history_restore_request', False):
        return render(request, partial, context)
    return render(request, page, context)
