"""Umumiy shablon konteksti (flaglar, interfeys qiyofasi)."""
from .flags import all_flags


def feature_flags(request):
    """`{{ flags.<nom> }}` — funksiya flaglari shablonda."""
    return {'flags': all_flags()}


def permissions(request):
    """`{{ perms_flags }}` — foydalanuvchining ruxsat kodlari to'plami.

    Lazy: shablon ishlatmasa, hech qanday so'rov bajarilmaydi.
    Shablonda: `{% if "circ.checkout" in perms_flags %}`.
    """
    from django.utils.functional import SimpleLazyObject

    from user_app.permissions import user_permissions

    return {'perms_flags': SimpleLazyObject(lambda: user_permissions(getattr(request, 'user', None)))}
