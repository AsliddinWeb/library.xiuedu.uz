"""
Sarlavhani alohida indekslash va FTS vektoriga vazn berish.

0024 da `search_title` maydoni qo'shildi. Shu migratsiya uni to'ldiradi va
vektorni qayta quradi: sarlavha — "A" vazni, qolgan matn — "D". Natijada
sarlavhada mos kelgan kitob natijalar boshida turadi.

0023 kabi, bu yerda ham faqat `fold()` import qilinadi va model tarixiy
holatdan olinadi — kelajakdagi sxema o'zgarishi migratsiyani buzmasligi uchun.
"""
from django.contrib.postgres.search import SearchVector
from django.db import migrations

BATCH = 500


def rebuild(apps, schema_editor):
    from book_app.translit import fold

    Book = apps.get_model('book_app', 'Book')

    bucket, updated = [], 0
    for book in Book.objects.only('id', 'title', 'subtitle',
                                  'parallel_title').iterator(chunk_size=BATCH):
        book.search_title = fold(" ".join(
            str(p) for p in (book.title, book.subtitle, book.parallel_title) if p))[:1000]
        bucket.append(book)
        if len(bucket) >= BATCH:
            Book.objects.bulk_update(bucket, ['search_title'])
            updated += len(bucket)
            bucket = []

    if bucket:
        Book.objects.bulk_update(bucket, ['search_title'])
        updated += len(bucket)

    if schema_editor.connection.vendor == 'postgresql':
        Book.objects.update(
            search_vector=(SearchVector('search_title', config='simple', weight='A') +
                           SearchVector('search_text', config='simple', weight='D')))

    print(f"  {updated} ta yozuvda sarlavha indeksi qurildi")


class Migration(migrations.Migration):

    dependencies = [
        ('book_app', '0024_add_search_title'),
    ]

    operations = [
        migrations.RunPython(rebuild, migrations.RunPython.noop),
    ]
