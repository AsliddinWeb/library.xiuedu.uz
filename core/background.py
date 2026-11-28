"""
Panelning o'zidan boshlanadigan uzoq ishlar (HEMIS yuklash, kitob importi).

Broker yo'q: uzoq ish **alohida jarayonda** (`manage.py <buyruq>`) yuradi va
holati `audit.JobRun` yozuvida turadi. Web worker ichidagi oqimga ishonib
bo'lmaydi — worker qayta ishga tushsa ish jimgina yo'qoladi. Xizmat qayta
ishga tushsa jarayon baribir to'xtashi mumkin, shuning uchun har bir ish
qayta boshlansa zarar qilmasligi shart.
"""
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, connection, transaction
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
    fields = ['status', 'message', 'finished_at', 'duration_ms']
    try:
        with transaction.atomic():
            record.save(update_fields=[*fields, 'stats'])
    except DatabaseError:
        # Hisoblagichlarni saqlab bo'lmasa ham ish «bajarilmoqda»da qotib qolmasin
        logger.exception("Ish natijasini to'liq saqlab bo'lmadi: %s", record.name)
        record.save(update_fields=fields)


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


def close_stale(name, after=STALE_AFTER):
    """Uzilib qolgan (belgi bermay qo'ygan) yozuvlarni yopadi."""
    limit = timezone.now() - after
    for record in JobRun.objects.filter(name=name, status=JobRun.Status.RUNNING):
        beat = record.stats.get('beat')
        seen = datetime.fromisoformat(beat) if beat else record.started_at
        if seen < limit:
            finish(record, JobRun.Status.FAILED,
                   "Jarayon to'xtab qoldi (server qayta ishga tushgan bo'lishi mumkin). "
                   "Qayta boshlang — bajarilgan qismi saqlangan.")


def is_running(name, after=STALE_AFTER):
    close_stale(name, after)
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


def log_file() -> Path:
    return Path(settings.BASE_DIR) / 'var' / 'background.log'


def spawn(name, command, *args, env=None, stale_after=STALE_AFTER, **initial):
    """`manage.py <command> --run-id N` ni alohida jarayonda boshlaydi.

    Shu nomdagi ish yurayotgan bo'lsa `None`. Maxfiy qiymatlar argument bilan
    emas, `env` orqali beriladi (argumentlar `ps` da ko'rinadi).
    """
    if is_running(name, stale_after):
        return None
    record = JobRun.objects.create(name=name, status=JobRun.Status.RUNNING, stats=initial)
    command_line = [sys.executable, str(Path(settings.BASE_DIR) / 'manage.py'), command,
                    '--run-id', str(record.pk), *args]
    try:
        log = log_file()
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('ab') as output:
            process = subprocess.Popen(
                command_line, cwd=settings.BASE_DIR, env={**os.environ, **(env or {})},
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
    except OSError as exc:
        logger.exception("Jarayonni boshlab bo'lmadi: %s", command)
        finish(record, JobRun.Status.FAILED, f"Jarayonni boshlab bo'lmadi: {exc}")
        return record
    # Tugagan jarayon «zombi» bo'lib qolmasin
    threading.Thread(target=process.wait, daemon=True).start()
    return record
