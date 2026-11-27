"""
Audit yozish API'si.

Oddiy foydalanish (aktyor va IP avtomatik olinadi):
    from audit.services import log_action
    log_action(ActionLog.Action.CHECKOUT, obj=loan, note="skaner orqali")

O'zgarishlarni avtomatik taqqoslash:
    before = snapshot(item)
    ...
    log_change(ActionLog.Action.ITEM_EDIT, item, before)
"""
import logging

from .context import current_actor, current_meta
from .models import ActionLog

logger = logging.getLogger('audit')

# Hech qachon audit yozuviga tushmaydigan maydonlar
SENSITIVE_FIELDS = {'password', 'secret', 'token', 'search_vector'}


def _is_auto_timestamp(field):
    """`auto_now` / `auto_now_add` maydonlari — har saqlashda o'zgaradi, audit uchun shovqin."""
    return getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False)


def snapshot(instance, fields=None):
    """Model nusxasining maydon qiymatlarini lug'at sifatida oladi (taqqoslash uchun).

    `updated_at` kabi avtomatik vaqt maydonlari va maxfiy maydonlar tashlab ketiladi:
    aks holda har tahrirlashda "updated_at o'zgardi" deb yozilib, jurnal shovqinga aylanadi.
    """
    if instance is None:
        return {}

    if fields:
        selected = [instance._meta.get_field(name) for name in fields]
    else:
        selected = list(instance._meta.concrete_fields)

    data = {}
    for field in selected:
        if field.name in SENSITIVE_FIELDS or _is_auto_timestamp(field):
            continue
        try:
            value = (getattr(instance, f'{field.name}_id', None) if field.is_relation
                     else getattr(instance, field.name))
        except Exception:
            continue
        data[field.name] = _plain(value)
    return data


def diff(before: dict, after: dict) -> dict:
    """{maydon: [eski, yangi]} — faqat o'zgarganlar."""
    changed = {}
    for key, new_value in after.items():
        old_value = before.get(key)
        if old_value != new_value:
            changed[key] = [old_value, new_value]
    return changed


def log_action(action, obj=None, changes=None, note='', actor=None, object_repr=None):
    """Audit yozuvini yaratadi. Xato bo'lsa ham asosiy oqimni buzmaydi."""
    try:
        actor = actor if actor is not None else current_actor()
        meta = current_meta()
        return ActionLog.objects.create(
            actor=actor if (actor is not None and getattr(actor, 'pk', None)) else None,
            actor_label=_actor_label(actor),
            action=action,
            object_type=obj._meta.label if obj is not None else '',
            object_id=str(getattr(obj, 'pk', '') or ''),
            object_repr=(object_repr or (str(obj) if obj is not None else ''))[:300],
            changes=changes or {},
            note=note[:300],
            ip=meta.get('ip'),
            user_agent=meta.get('user_agent', ''),
            path=meta.get('path', ''),
        )
    except Exception:  # audit hech qachon so'rovni yiqitmasligi kerak
        logger.exception("Audit yozuvini saqlash muvaffaqiyatsiz: %s", action)
        return None


def log_change(action, obj, before: dict, note='', actor=None):
    """`before` snapshot bilan taqqoslab, faqat o'zgargan maydonlarni yozadi."""
    changed = diff(before, snapshot(obj))
    if not changed and before:
        return None
    return log_action(action, obj=obj, changes=changed, note=note, actor=actor)


def _actor_label(actor):
    if actor is None:
        return 'tizim'
    name = getattr(actor, 'get_full_name', lambda: '')() or getattr(actor, 'username', '')
    return str(name)[:150]


def _plain(value):
    """JSON'ga yozib bo'ladigan oddiy qiymatga aylantiradi."""
    from datetime import date, datetime, time
    from decimal import Decimal
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)
