"""Har so'rovda joriy foydalanuvchini audit kontekstiga qo'yadi."""
from .context import clear_context, set_context


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        set_context(
            actor=user if (user is not None and user.is_authenticated) else None,
            ip=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            path=request.get_full_path(),
        )
        try:
            return self.get_response(request)
        finally:
            clear_context()
