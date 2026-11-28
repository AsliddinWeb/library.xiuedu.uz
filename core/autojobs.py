"""
Kunlik vazifalarni sayt ichidan ishga tushirish (cron'siz).

Serverda crontab ochiq bo'lmasa ham jarima, ogohlantirish va navbat ishlashi
kerak. Shuning uchun `AUTO_JOBS_HOUR` dan keyingi birinchi so'rov bugungi
vazifalarni fon oqimida ishga tushiradi.

Kafolatlar:
  * bugun muvaffaqiyatli bajarilgan vazifa qayta yurmaydi (cron yoki qo'lda
    `run_jobs` ishlatilgan bo'lsa ham);
  * bir vaqtda faqat bitta jarayon bajaradi — PostgreSQL advisory lock
    (gunicorn'da bir nechta worker bor);
  * xato bo'lsa kuniga `MAX_ATTEMPTS` martagacha qayta uriniladi;
  * foydalanuvchi so'rovi vazifa tugashini kutmaydi.

Soat chegarasi nega bor: vazifalar sanani UTC bo'yicha oladi, Toshkentda esa
05:00 gacha UTC sanasi hali kechagi kun bo'ladi.
"""
import logging
import threading
import time
from contextlib import contextmanager

from django.conf import settings
from django.db import connection
from django.utils import timezone

from .jobs import registry, run_job

logger = logging.getLogger('jobs')

#: Har bir jarayon bazaga shundan tez-tez qaramaydi (soniya)
CHECK_EVERY = 15 * 60
#: Bitta vazifaga bir kunda ko'pi bilan shuncha urinish
MAX_ATTEMPTS = 3
#: pg_advisory_lock kaliti ("XIU1")
LOCK_KEY = 0x58495531

_guard = threading.Lock()
_next_check = 0.0


@contextmanager
def exclusive(key=None):
    """Jarayonlararo qulf: boshqasi bajarayotgan bo'lsa `False` qaytaradi."""
    key = LOCK_KEY if key is None else key
    if connection.vendor != 'postgresql':
        yield True
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [key])
        locked = cursor.fetchone()[0]
    try:
        yield locked
    finally:
        if locked:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [key])


def due_jobs():
    """Bugun hali bajarilishi kerak bo'lgan kunlik vazifalar nomlari."""
    from audit.models import JobRun

    day_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    names = []
    for entry in registry('daily'):
        runs = JobRun.objects.filter(name=entry['name'], started_at__gte=day_start)
        if runs.filter(status=JobRun.Status.SUCCESS).exists():
            continue
        if runs.count() >= MAX_ATTEMPTS:
            continue
        names.append(entry['name'])
    return names


def run_due_jobs():
    """Navbati kelgan vazifalarni bajaradi va `JobRun` yozuvlarini qaytaradi."""
    with exclusive() as locked:
        if not locked:
            return []
        return [run_job(name) for name in due_jobs()]


def _worker():
    try:
        run_due_jobs()
    except Exception:
        logger.exception("Avtomatik vazifalar ishga tushmadi")
    finally:
        # Oqimning o'z baza ulanishi bor — yopilmasa osilib qoladi
        connection.close()


def maybe_start():
    """Vaqti kelgan bo'lsa fon oqimini boshlaydi va uni qaytaradi."""
    global _next_check
    if not settings.AUTO_JOBS or timezone.localtime().hour < settings.AUTO_JOBS_HOUR:
        return None
    with _guard:
        if time.monotonic() < _next_check:
            return None
        _next_check = time.monotonic() + CHECK_EVERY
    thread = threading.Thread(target=_worker, name='auto-jobs', daemon=True)
    thread.start()
    return thread


class AutoJobsMiddleware:
    """Javob tayyor bo'lgach vazifalarni (kerak bo'lsa) fonda boshlaydi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        maybe_start()
        return response
