"""
Katalogdagi BARCHA kitoblarni o'chiradi (masalan, toza import qilishdan oldin).

    python manage.py delete_all_books                  # faqat hisobot, hech narsa o'chmaydi
    python manage.py delete_all_books --apply          # zaxira -> tasdiq -> o'chirish

Kitob bilan birga uning nusxalari, ijaralari va jarimalari, navbatlar,
so'rovlar, sharhlar, sevimlilar, ro'yxat bandlari va o'qish tarixi ham ketadi.
A'zolar, foydalanuvchilar, xodim rollari, sozlamalar va audit jurnali qoladi.

Xavfsizlik:
  * bayroqsiz ishga tushirish hech narsani o'zgartirmaydi;
  * o'chirishdan oldin baza zaxiralanadi (`var/backups/books/`) — zaxira
    chiqmasa hech narsa o'chirilmaydi;
  * kitob qo'lida bo'lgan o'quvchi bo'lsa, alohida ruxsat bayrog'i kerak;
  * sonni o'z ichiga olgan tasdiq so'zi qo'lda yoziladi;
  * baza o'zgarishi bitta tranzaksiyada: xato bo'lsa hammasi joyida qoladi.
"""
import gzip
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from audit.models import ActionLog
from audit.services import log_action
from book_app.models import (
    Author,
    Book,
    Contributor,
    CourseReserveItem,
    ExternalRecord,
    Genre,
    Item,
    Publisher,
    Rental,
    Series,
    Subject,
)
from circulation.models import Fine, RentalRequest, Reservation
from circulation.services import recalc_patron_counters
from engagement.models import Favorite, Review, ShelfItem
from reading.models import ReadingHistory, ReadingProgress
from user_app.models import Patron

FILE_FIELDS = ('cover_image', 'electronic_version', 'audio_version')
BATCH = 500

#: (nom, model) — kitob bilan birga o'chadigan yozuvlar
LINKED = (
    ("Nusxalar", Item),
    ("Ijaralar (tarix bilan)", Rental),
    ("Jarimalar", Fine),
    ("Navbatlar", Reservation),
    ("Ijara so'rovlari", RentalRequest),
    ("Sharhlar", Review),
    ("Sevimlilar", Favorite),
    ("Ro'yxatlardagi kitoblar", ShelfItem),
    ("Fan adabiyoti bandlari", CourseReserveItem),
    ("O'qish jarayoni", ReadingProgress),
    ("O'qish tarixi", ReadingHistory),
    ("Tashqi bazaga bog'lanishlar", ExternalRecord),
)
REFERENCES = (("Mualliflar", Author), ("Nashriyotlar", Publisher),
              ("Turkumlar", Series), ("Mavzular", Subject))


def backup_database() -> Path:
    """`pg_dump` bilan zaxira. `deploy.sh` eski zaxiralarni tozalaganda tegmaydigan papkaga."""
    if connection.vendor != 'postgresql':
        raise CommandError("Zaxira faqat PostgreSQL uchun — o'chirish bekor qilindi.")
    if not shutil.which('pg_dump'):
        raise CommandError("pg_dump topilmadi — zaxirasiz o'chirilmaydi.")
    db = connection.settings_dict
    folder = Path(settings.BASE_DIR) / 'var' / 'backups' / 'books'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{timezone.localtime():%Y%m%d-%H%M%S}-ochirishdan-oldin.sql.gz"
    command = ['pg_dump', '--clean', '--if-exists', '-h', db.get('HOST') or '127.0.0.1',
               '-p', str(db.get('PORT') or 5432), '-U', db['USER'], db['NAME']]
    environment = {**os.environ, 'PGPASSWORD': db.get('PASSWORD') or ''}
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=environment) as process:
        with gzip.open(target, 'wb') as archive:
            shutil.copyfileobj(process.stdout, archive)
        error = process.stderr.read().decode(errors='replace')
    if process.returncode != 0:
        target.unlink(missing_ok=True)
        raise CommandError(f"Zaxira olinmadi, hech narsa o'chirilmadi:\n{error.strip()[:600]}")
    return target


class Command(BaseCommand):
    help = "Barcha kitoblarni o'chiradi. Bayroqsiz — faqat nima o'chishini ko'rsatadi."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Haqiqatan o'chiradi")
        parser.add_argument('--with-active-loans', action='store_true',
                            help="O'quvchilar qo'lida kitob bo'lsa ham davom etadi")
        parser.add_argument('--delete-files', action='store_true',
                            help="Muqova, PDF va audio fayllarni ham diskdan o'chiradi")
        parser.add_argument('--delete-references', action='store_true',
                            help="Mualliflar, nashriyotlar, turkumlar va mavzularni ham o'chiradi")
        parser.add_argument('--delete-catalogs', action='store_true',
                            help="Kataloglarni ham o'chiradi")

    def handle(self, *args, **options):
        books = Book.objects.count()
        active = Rental.objects.filter(return_date__isnull=True).count()
        self._report(books, active, options)

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                "\nHech narsa o'chirilmadi. O'chirish uchun: --apply"))
            return
        extra = options['delete_references'] or options['delete_catalogs']
        if not books and not extra:
            self.stdout.write("O'chiradigan kitob yo'q.")
            return
        if active and not options['with_active_loans']:
            raise CommandError(
                f"{active} ta kitob hozir o'quvchilar qo'lida. Ular o'chsa kim nimani olgani "
                "yo'qoladi. Baribir davom etish uchun: --with-active-loans")

        backup = backup_database()
        self.stdout.write(self.style.SUCCESS(
            f"\nZaxira olindi: {backup} ({backup.stat().st_size / 1024:.0f} KB)"))

        phrase = f"OCHIRISH {books}"
        self.stdout.write(self.style.ERROR(
            f"\n{books} ta kitob butunlay o'chiriladi. Ortga qaytarish faqat zaxiradan."))
        try:
            answer = input(f"Davom etish uchun «{phrase}» deb yozing: ")
        except (EOFError, KeyboardInterrupt):
            answer = ''
        if answer.strip() != phrase:
            raise CommandError("Tasdiqlanmadi — hech narsa o'chirilmadi.")

        files = self._delete(options)
        removed = self._remove_files(files) if options['delete_files'] else 0

        log_action(ActionLog.Action.BIBLIO_DELETE,
                   note=f"Barcha kitoblar o'chirildi: {books} ta. Zaxira: {backup.name}")
        self.stdout.write(self.style.SUCCESS(f"\n{books} ta kitob o'chirildi."))
        if options['delete_files']:
            self.stdout.write(f"Diskdan o'chirilgan fayllar: {removed}")
        db = connection.settings_dict
        self.stdout.write(
            "\nOrtga qaytarish (zaxiradan keyingi BARCHA o'zgarishlar yo'qoladi; "
            "parol so'ralsa — .env dagi DB_PASSWORD):\n"
            f"  gunzip -c {backup} | psql -h {db.get('HOST') or '127.0.0.1'} "
            f"-U {db['USER']} {db['NAME']}"
            + ("\n  Diqqat: o'chirilgan fayllar zaxiradan qaytmaydi."
               if options['delete_files'] else ''))

    # ------------------------------------------------------------------

    def _report(self, books, active, options):
        self.stdout.write(f"Baza: {connection.settings_dict['NAME']}\n")
        self.stdout.write(f"O'chadi:\n  {'Kitoblar':<32}{books}")
        for label, model in LINKED:
            self.stdout.write(f"  {label:<32}{model.objects.count()}")
        unpaid = Fine.objects.filter(is_paid=False).aggregate(total=Sum('amount'))['total'] or 0
        for label, value in (("  shundan qo'lidagi kitoblar", active),
                             ("  to'lanmagan jarima (so'm)", f"{unpaid:.0f}")):
            self.stdout.write(f"  {label:<32}{value}")
        if options['delete_references']:
            for label, model in REFERENCES:
                self.stdout.write(f"  {label:<32}{model.objects.count()}")
        if options['delete_catalogs']:
            self.stdout.write(f"  {'Kataloglar':<32}{Genre.objects.count()}")
        if options['delete_files']:
            self.stdout.write(f"  {'Diskdagi fayllar':<32}{len(self._file_names())}")
        kept = ["a'zolar va foydalanuvchilar", "rollar", "sozlamalar", "audit jurnali"]
        if not options['delete_references']:
            kept.append("mualliflar, nashriyotlar, mavzular")
        if not options['delete_catalogs']:
            kept.append("kataloglar")
        if not options['delete_files']:
            kept.append("diskdagi fayllar")
        self.stdout.write(f"Qoladi: {', '.join(kept)}.")

    def _file_names(self):
        has_file = Q()
        for field in FILE_FIELDS:
            has_file |= Q(**{f'{field}__gt': ''})
        return {name for row in Book.objects.filter(has_file).values_list(*FILE_FIELDS)
                for name in row if name}

    @transaction.atomic
    def _delete(self, options):
        files = self._file_names()
        # Bog'lanishlar signalsiz o'chadi: har biri o'chayotgan kitobni qayta indekslamasin
        Contributor.objects.all()._raw_delete(connection.alias)
        ids = list(Book.objects.values_list('pk', flat=True))
        for start in range(0, len(ids), BATCH):
            Book.objects.filter(pk__in=ids[start:start + BATCH]).delete()
        if options['delete_references']:
            for _, model in REFERENCES:
                model.objects.all().delete()
        if options['delete_catalogs']:
            Genre.objects.all().delete()
        # A'zo kartasidagi «qo'lida», «kechikkan» va «qarz» ko'rsatkichlari
        stale = Patron.objects.filter(
            Q(active_loans_count__gt=0) | Q(overdue_count__gt=0) | ~Q(balance=0))
        for patron in stale:
            recalc_patron_counters(patron)
        return files

    def _remove_files(self, names):
        removed = 0
        for name in names:
            try:
                if default_storage.exists(name):
                    default_storage.delete(name)
                    removed += 1
            except OSError as exc:
                self.stderr.write(f"O'chirib bo'lmadi: {name} ({exc})")
        return removed
