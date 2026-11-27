"""
Fondni to'ldirish: nusxasi yo'q kitoblarga nusxa yaratadi.

Nima uchun kerak: v1/v2 da kitoblar katalogga kiritilgan, lekin **jismoniy
nusxalar yuritilmagan**. v3 da ijara aynan nusxaga (Item) beriladi, shuning
uchun har bir qog'oz kitobga kamida bitta nusxa kerak.

    # avval ko'rib chiqish (hech narsa yozilmaydi)
    python manage.py seed_items --dry-run

    # har kitobga 1 ta nusxa
    python manage.py seed_items

    # har kitobga 3 ta, "Darslik" turi bilan
    python manage.py seed_items --per-book 3 --item-type DARSLIK

Idempotent: nusxasi bor kitob chetlab o'tiladi, shuning uchun qayta ishga
tushirish xavfsiz. Keyin kutubxonachi panelda haqiqiy sonini to'g'rilaydi.
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from django.utils.timezone import now

from book_app.models import Book, Item
from holdings.models import ItemType, Library, ShelfLocation

BATCH = 500


class Command(BaseCommand):
    help = "Nusxasi yo'q kitoblarga nusxa (Item) yaratadi — shtrix-kod avtomatik."

    def add_arguments(self, parser):
        parser.add_argument('--per-book', type=int, default=1,
                            help="Har kitobga nechta nusxa (default: 1)")
        parser.add_argument('--modes', default='PHYSICAL,BOTH',
                            help="Qaysi turdagi yozuvlarga (default: PHYSICAL,BOTH; "
                                 "hammasi uchun: ALL)")
        parser.add_argument('--item-type', dest='item_type',
                            help="Nusxa turi kodi (default: birinchi faol tur)")
        parser.add_argument('--library', help="Filial kodi (default: birinchi faol filial)")
        parser.add_argument('--shelf', help="Javon kodi (ixtiyoriy)")
        parser.add_argument('--dry-run', action='store_true',
                            help="Faqat hisobot — baza o'zgarmaydi")

    def handle(self, *args, **options):
        per_book = max(1, options['per_book'])
        dry_run = options['dry_run']

        # --- Ma'lumotnomalar ---
        library = (Library.objects.filter(code=options['library']).first()
                   if options['library'] else Library.default())
        if library is None:
            raise CommandError("Filial topilmadi. Avval /panel/holdings/ da filial yarating.")

        item_type = (ItemType.objects.filter(code=options['item_type']).first()
                     if options['item_type'] else ItemType.default())
        if item_type is None:
            raise CommandError("Nusxa turi topilmadi. Avval /panel/holdings/ da tur yarating.")

        shelf = None
        if options['shelf']:
            shelf = ShelfLocation.objects.filter(code=options['shelf'], library=library).first()
            if shelf is None:
                raise CommandError(f"'{options['shelf']}' javoni '{library.code}' filialida yo'q.")

        # --- Qaysi kitoblar ---
        books = Book.objects.annotate(existing=Count('item')).filter(existing=0)
        modes = options['modes'].upper()
        if modes != 'ALL':
            books = books.filter(reading_mode__in=[m.strip() for m in modes.split(',') if m.strip()])
        books = books.only('id', 'title', 'udc', 'author_sign').order_by('id')

        total_books = books.count()
        if not total_books:
            self.stdout.write(self.style.SUCCESS(
                "Nusxasi yo'q kitob topilmadi — fond allaqachon to'liq."))
            return

        self.stdout.write(
            f"Kitoblar:   {total_books} ta (nusxasi yo'q, rejim: {modes})\n"
            f"Nusxa:      har biriga {per_book} ta -> jami {total_books * per_book} ta\n"
            f"Filial:     {library.name}\n"
            f"Turi:       {item_type.name}\n"
            f"Javon:      {shelf.code if shelf else '—'}"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n--dry-run: hech narsa yozilmadi."))
            return

        # --- Shtrix-kod hisoblagichi (bitta so'rov bilan) ---
        last = (Item.objects.filter(barcode__startswith='XIU')
                .order_by('-barcode').values_list('barcode', flat=True).first())
        counter = 0
        if last:
            match = re.search(r'(\d+)$', last)
            counter = int(match.group(1)) if match else 0

        today = now().date()
        created_total = 0
        touched_books = []

        with transaction.atomic():
            batch = []
            for book in books.iterator(chunk_size=BATCH):
                call_number = " ".join(p for p in (book.udc, book.author_sign) if p).strip()
                for index in range(per_book):
                    counter += 1
                    batch.append(Item(
                        book_id=book.pk,
                        barcode=f"XIU{counter:09d}",
                        inventory_number=f"INV-{index + 1}",
                        item_type=item_type,
                        library=library,
                        shelf_location=shelf,
                        call_number=call_number,
                        status=Item.Status.AVAILABLE,
                        is_available=True,
                        acquired_on=today,
                        acquisition_source=Item.Source.OTHER,
                    ))
                touched_books.append(book.pk)

                if len(batch) >= BATCH:
                    Item.objects.bulk_create(batch)
                    created_total += len(batch)
                    batch = []
                    self.stdout.write(f"  ... {created_total} ta nusxa", ending='\r')

            if batch:
                Item.objects.bulk_create(batch)
                created_total += len(batch)

            # Kitob ko'rsatkichlari (bitta UPDATE bilan)
            Book.objects.filter(pk__in=touched_books).update(
                items_count=per_book, available_count=per_book)

        # --- Audit izi ---
        from audit.models import ActionLog
        from audit.services import log_action
        log_action(ActionLog.Action.ITEM_CREATE,
                   note=f"seed_items: {created_total} ta nusxa, {len(touched_books)} ta kitob")

        self.stdout.write(self.style.SUCCESS(
            f"\nTayyor: {created_total} ta nusxa yaratildi ({len(touched_books)} ta kitobga).\n"
            f"Shtrix-kodlar: XIU{counter - created_total + 1:09d} … XIU{counter:09d}"
        ))
