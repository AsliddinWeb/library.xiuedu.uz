"""
Joriy so'rov konteksti (kim, qaysi IP) — model signallari va servislar
`log_action()` chaqirganda aktyorni qo'lda uzatmasligi uchun.

`contextvars` ishlatiladi: thread ham, async ham xavfsiz.
"""
import contextvars

_actor = contextvars.ContextVar('audit_actor', default=None)
_meta = contextvars.ContextVar('audit_meta', default=None)


def set_context(actor=None, ip=None, user_agent='', path=''):
    _actor.set(actor)
    _meta.set({'ip': ip, 'user_agent': user_agent[:300], 'path': path[:300]})


def clear_context():
    _actor.set(None)
    _meta.set(None)


def current_actor():
    return _actor.get()


def current_meta():
    return _meta.get() or {}
