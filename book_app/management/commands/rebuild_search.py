"""
Qidiruv indeksini qayta qurish.

Har bir kitob uchun `search_text` (kirill/lotin birlashtirilgan matn) va
`search_vector` (PostgreSQL FTS) qayta hisoblanadi.

    python manage.py rebuild_search

Qachon kerak:
  · v3 ga o'tgandan keyin bir marta (mavjud 2000+ yozuv uchun);
  · transliteratsiya qoidalari o'zgarsa;
  · ko'p yozuv to'g'ridan-to'g'ri SQL bilan o'zgartirilsa.

Oddiy ishda indeks o'z-o'zidan yangilanadi (kitob saqlanganda).
"""
import time

from django.core.management.base import BaseCommand

from book_app.search import rebuild_all


class Command(BaseCommand):
    help = "Katalog qidiruv indeksini (search_text + search_vector) qayta quradi."

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=500)

    def handle(self, *args, **options):
        started = time.monotonic()
        self.stdout.write("Qidiruv indeksi qayta qurilmoqda...")

        count = rebuild_all(batch_size=options['batch_size'], stdout=self.stdout)
        elapsed = time.monotonic() - started

        self.stdout.write(self.style.SUCCESS(
            f"\nTayyor: {count} ta yozuv indekslandi ({elapsed:.1f} s)."
        ))
