"""
Foydalanuvchilar bilan bog'liq davriy vazifalar.

HEMIS tokeni serverda sozlangan bo'lsagina ro'yxat har kuni yangilanadi.
Tokensiz o'rnatishda administrator uni panelning o'zidan
(«A'zolar → HEMIS'dan yuklash») qo'lda ishga tushiradi.
"""
from django.conf import settings

from audit.models import JobRun
from core.jobs import job

from .hemis import sync


@job('hemis_sync', "HEMIS'dan talaba va xodimlarni yangilaydi", schedule='daily',
     when=lambda: bool(settings.HEMIS_API_TOKEN))
def hemis_sync():
    record = JobRun.objects.filter(name=sync.JOB_NAME, status=JobRun.Status.RUNNING).first()
    # Jarayon belgisi panelda ko'rinadi va uzoq yuklash «uzilgan» deb yopilmaydi
    progress = sync.reporter(record) if record else (lambda stats: None)
    return sync.run(settings.HEMIS_API_TOKEN, progress=progress)
