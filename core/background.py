"""
Panelning o'zidan boshlanadigan uzoq ishlar (HEMIS yuklash, kitob importi).

Broker yo'q: ish web jarayonining fon oqimida yuradi va holati `audit.JobRun`
yozuvida turadi. Server qayta ishga tushsa oqim uziladi — shuning uchun
har bir ish qayta boshlansa zarar qilmasligi shart.
"""
import logging
import threading
from datetime import datetime, timedelta

from django.db import connection
from django.utils import timezone

from audit.models import JobRun

logger = logging.getLogger('jobs')

#: Shuncha vaqt belgi bermagan «bajarilmoqda» yozuvi uzilgan hisoblanadi
STALE_AFTER = timedelta(minutes=10)


def finish(record, status, message):
    record.status = status
    record.message = message[:300]
    record.finished_at = timezone.now()
    record.duration_ms = int((record.finished_at - record.started_at).total_seconds() * 1000)
    record.save(update_fields=['status', 'message', 'stats', 'finished_at', 'duration_ms'])


def reporter(record):
    """Oraliq hisoblagichlarni saqlaydigan funksiya.

    Xodim «To'xtatish»ni bosgan bo'lsa `True` qaytaradi.
    """
    def progress(stats):
        saved = JobRun.objects.filter(pk=record.pk).values_list('stats', flat=True).first() or {}
        stop = bool(saved.get('stop'))
        record.stats = {**stats, 'beat': timezone.now().isoformat(), **({'stop': True} if stop else {})}
        record.save(update_fields=['stats'])
        return stop
    return progress


def close_stale(name):
    """Server qayta ishga tushganda uzilib qolgan yozuvlarni yopadi."""
    limit = timezone.now() - STALE_AFTER
    for record in JobRun.objects.filter(name=name, status=JobRun.Status.RUNNING):
        beat = record.stats.get('beat')
        seen = datetime.fromisoformat(beat) if beat else record.started_at
        if seen < limit:
            finish(record, JobRun.Status.FAILED,
                   "Uzilib qoldi (server qayta ishga tushgan bo'lishi mumkin). Qayta boshlang.")


def is_running(name):
    close_stale(name)
    return JobRun.objects.filter(name=name, status=JobRun.Status.RUNNING).exists()


def request_stop(name):
    stopped = False
    for record in JobRun.objects.filter(name=name, status=JobRun.Status.RUNNING):
        record.stats = {**record.stats, 'stop': True}
        record.save(update_fields=['stats'])
        stopped = True
    return stopped


def in_thread(target, *args):
    """`target`ni alohida oqimda bajaradi; oqimning baza ulanishi yopiladi."""
    def wrapper():
        try:
            target(*args)
        except Exception:
            logger.exception("Fon ishi xato bilan tugadi")
        finally:
            connection.close()

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread


def start(name, execute, *args, **initial):
    """`execute(record, *args)`ni fonda boshlaydi. Boshqasi ishlayotgan bo'lsa `None`."""
    if is_running(name):
        return None
    record = JobRun.objects.create(name=name, status=JobRun.Status.RUNNING, stats=initial)
    in_thread(lambda pk: execute(JobRun.objects.get(pk=pk), *args), record.pk)
    return record
