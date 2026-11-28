"""
Universitet kitoblar bazasidan import.

    python manage.py import_arm --compare          # faqat solishtirish
    python manage.py import_arm --files            # kitoblar, muqovalar va PDF

Uzilib qolsa shu buyruqni qayta ishga tushiring: yuklangan kitoblar o'tkazib
yuboriladi, qolgani davom etadi. Paneldagi tugma ham shu buyruqni chaqiradi.
"""
from django.core.management.base import BaseCommand, CommandError

from audit.models import JobRun
from book_app import arm_import
from core import background


class Command(BaseCommand):
    help = "Universitet bazasidan kitoblarni import qiladi (uzilsa — qayta ishga tushiring)."

    def add_arguments(self, parser):
        parser.add_argument('--compare', action='store_true', help="Hech narsa yozmaydi")
        parser.add_argument('--no-covers', action='store_true', help="Muqovalarsiz")
        parser.add_argument('--files', action='store_true', help="PDF'larni ham ko'chiradi")
        parser.add_argument('--run-id', type=int, help="(panel) tayyor holat yozuvi")

    def handle(self, *args, **options):
        if options['run_id']:
            record = JobRun.objects.get(pk=options['run_id'], name=arm_import.JOB_NAME)
        else:
            if background.is_running(arm_import.JOB_NAME, arm_import.STALE_AFTER):
                raise CommandError("Import allaqachon ishlayapti (saytda holatiga qarang).")
            record = JobRun.objects.create(
                name=arm_import.JOB_NAME, status=JobRun.Status.RUNNING,
                stats={'dry': int(options['compare'])})
        arm_import.execute(record, options['compare'], not options['no_covers'],
                           options['files'], echo=self._echo)
        record.refresh_from_db()
        if record.status != JobRun.Status.SUCCESS:
            raise CommandError(record.message)
        self.stdout.write(self.style.SUCCESS(record.message))

    def _echo(self, stats):
        if 'done' not in stats:
            self.stdout.write("Tayyorlanmoqda...")
        else:
            self.stdout.write(
                f"ko'rildi {stats['done']} / {stats.get('total', '?')} | "
                f"yangi {stats.get('new', 0)} | avval yuklangan {stats.get('same', 0)} | "
                f"PDF {stats.get('files', 0)} | xato {stats.get('failed', 0)}")
        self.stdout.flush()
