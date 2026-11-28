"""
HEMIS'dan talaba va xodimlarni yuklash (paneldagi tugma shu buyruqni chaqiradi).

Token `HEMIS_RUN_TOKEN` yoki `HEMIS_API_TOKEN` muhit o'zgaruvchisidan olinadi —
buyruq satriga yozilmaydi.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from audit.models import JobRun
from user_app.hemis import sync


class Command(BaseCommand):
    help = "HEMIS'dan talaba va xodimlarni yuklaydi."

    def add_arguments(self, parser):
        parser.add_argument('--kinds', default='students,employees')
        parser.add_argument('--run-id', type=int, help="(panel) tayyor holat yozuvi")

    def handle(self, *args, **options):
        kinds = [kind for kind in options['kinds'].split(',') if kind in sync.SOURCES]
        if not kinds:
            raise CommandError("--kinds: students va/yoki employees")
        token = os.environ.pop(sync.TOKEN_ENV, '') or settings.HEMIS_API_TOKEN
        if options['run_id']:
            record = JobRun.objects.get(pk=options['run_id'], name=sync.JOB_NAME)
        else:
            if sync.is_running():
                raise CommandError("Yuklash allaqachon ishlayapti.")
            record = JobRun.objects.create(name=sync.JOB_NAME, status=JobRun.Status.RUNNING)
        sync.execute(record, token, kinds)
        record.refresh_from_db()
        if record.status != JobRun.Status.SUCCESS:
            raise CommandError(record.message)
        self.stdout.write(self.style.SUCCESS(record.message))
