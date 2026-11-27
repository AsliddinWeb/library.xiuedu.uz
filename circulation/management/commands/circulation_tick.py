"""
ESKI BUYRUQ — orqaga moslik uchun saqlangan.

Yangi yo'l:  python manage.py run_jobs --schedule daily
Bu buyruq endi shunchaki sirkulyatsiya vazifalarini chaqiradi.
"""
from django.core.management.base import BaseCommand

from core.jobs import run_job

JOBS = ('due_soon_notices', 'fines_accrual', 'reservation_expiry')


class Command(BaseCommand):
    help = "(Eskirgan) Sirkulyatsiya davriy vazifalari — `run_jobs` ni ishlatish tavsiya etiladi."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "Eslatma: `circulation_tick` eskirgan. Yangi buyruq: "
            "python manage.py run_jobs --schedule daily"
        ))
        for name in JOBS:
            run = run_job(name)
            style = self.style.SUCCESS if run.status == run.Status.SUCCESS else self.style.ERROR
            self.stdout.write(style(f"{run.name}: {run.message or run.status}"))
