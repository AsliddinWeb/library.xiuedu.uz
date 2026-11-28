"""
Davriy vazifalar reyestri (job registry).

Vazifa — oddiy funksiya: `dict` qaytaradi (statistika) yoki `None`.
Har app o'z `jobs.py` faylida ro'yxatdan o'tkazadi:

    from core.jobs import job

    @job('fines_accrual', "Kechikish jarimalarini hisoblaydi", schedule='daily')
    def fines_accrual():
        ...
        return {'fines': 12}

Ishga tushirish:  python manage.py run_jobs            # barcha 'daily' vazifalar
                  python manage.py run_jobs fines_accrual
                  python manage.py run_jobs --list

Nega broker yo'q: bitta serverda ortiqcha xizmat kerak emas. Production'da
kunlik vazifalarni saytning o'zi ishga tushiradi (`core/autojobs.py`), cron
ixtiyoriy. Keyinchalik django-q2/Celery qo'shilsa, `run_job()` o'sha yerdan
chaqiriladi — vazifa kodiga tegilmaydi.

Vazifa qayta ishga tushsa zarar qilmasligi shart (takroriy xabar yoki yozuv
yaratmasin): xatodan keyin u qayta uriniladi.
"""
import logging
import time

from django.utils.module_loading import autodiscover_modules

logger = logging.getLogger('jobs')

SCHEDULES = ('daily', 'hourly', 'manual')

_REGISTRY: dict[str, dict] = {}
_discovered = False


def job(name, description='', schedule='daily'):
    """Vazifani reyestrga qo'shadigan dekorator."""
    if schedule not in SCHEDULES:
        raise ValueError(f"Noto'g'ri schedule: {schedule} (ruxsat: {SCHEDULES})")

    def decorator(func):
        if name in _REGISTRY:
            raise ValueError(f"'{name}' vazifasi allaqachon ro'yxatdan o'tgan")
        _REGISTRY[name] = {'name': name, 'func': func,
                           'description': description, 'schedule': schedule}
        return func

    return decorator


def discover():
    """Barcha app'lardagi `jobs` modullarini yuklaydi."""
    global _discovered
    if not _discovered:
        autodiscover_modules('jobs')
        _discovered = True


def registry(schedule=None):
    discover()
    items = sorted(_REGISTRY.values(), key=lambda j: j['name'])
    if schedule:
        items = [j for j in items if j['schedule'] == schedule]
    return items


def run_job(name, raise_errors=False):
    """Bitta vazifani bajaradi va `audit.JobRun` yozuvini qaytaradi."""
    from audit.models import JobRun

    discover()
    if name not in _REGISTRY:
        raise KeyError(f"'{name}' nomli vazifa yo'q. Mavjud: {', '.join(_REGISTRY)}")

    entry = _REGISTRY[name]
    run = JobRun.objects.create(name=name, status=JobRun.Status.RUNNING)
    started = time.monotonic()
    try:
        stats = entry['func']() or {}
        if not isinstance(stats, dict):
            stats = {'result': str(stats)}
        run.status = JobRun.Status.SUCCESS
        run.stats = stats
        run.message = ', '.join(f"{k}={v}" for k, v in stats.items())[:300]
    except Exception as exc:
        import traceback
        run.status = JobRun.Status.FAILED
        run.message = f"{type(exc).__name__}: {exc}"[:300]
        run.error = traceback.format_exc()
        logger.exception("Vazifa xato bilan tugadi: %s", name)
        if raise_errors:
            _finish(run, started)
            raise
    _finish(run, started)
    return run


def run_schedule(schedule='daily', raise_errors=False):
    """Berilgan jadvaldagi barcha vazifalarni ketma-ket bajaradi."""
    return [run_job(j['name'], raise_errors=raise_errors) for j in registry(schedule)]


def _finish(run, started):
    from django.utils.timezone import now
    run.finished_at = now()
    run.duration_ms = int((time.monotonic() - started) * 1000)
    run.save(update_fields=['status', 'stats', 'message', 'error', 'finished_at', 'duration_ms'])
