"""
Davriy vazifalarni ishga tushiradi (cron uchun yagona kirish nuqtasi).

    python manage.py run_jobs                 # barcha 'daily' vazifalar
    python manage.py run_jobs fines_accrual   # faqat bittasi
    python manage.py run_jobs --schedule hourly
    python manage.py run_jobs --list

Cron:
    0 1 * * *   <venv>/bin/python manage.py run_jobs --schedule daily
    5 * * * *   <venv>/bin/python manage.py run_jobs --schedule hourly
"""
from django.core.management.base import BaseCommand, CommandError

from core.jobs import registry, run_job, run_schedule


class Command(BaseCommand):
    help = "Rejalashtirilgan vazifalarni bajaradi va natijani jurnalga yozadi."

    def add_arguments(self, parser):
        parser.add_argument('names', nargs='*', help="Aniq vazifa nomlari")
        parser.add_argument('--schedule', default='daily', choices=['daily', 'hourly', 'manual'])
        parser.add_argument('--list', action='store_true', help="Vazifalar ro'yxatini ko'rsatadi")
        parser.add_argument('--raise-errors', action='store_true', help="Xatoni yashirmaydi")

    def handle(self, *args, **options):
        if options['list']:
            for entry in registry():
                self.stdout.write(f"  {entry['name']:<24} [{entry['schedule']:<6}] {entry['description']}")
            return

        names = options['names']
        try:
            runs = ([run_job(n, raise_errors=options['raise_errors']) for n in names]
                    if names else run_schedule(options['schedule'],
                                               raise_errors=options['raise_errors']))
        except KeyError as exc:
            raise CommandError(str(exc)) from exc

        if not runs:
            self.stdout.write(self.style.WARNING("Bajariladigan vazifa topilmadi."))
            return

        failed = 0
        for run in runs:
            if run.status == run.Status.SUCCESS:
                self.stdout.write(self.style.SUCCESS(
                    f"✓ {run.name} ({run.duration_ms} ms) {run.message}"))
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f"✗ {run.name}: {run.message}"))

        if failed:
            raise CommandError(f"{failed} ta vazifa xato bilan tugadi.")
