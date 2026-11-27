"""
Mavjud katalog uchun qidiruv indeksini bir marta qurish.

v3 gacha `search_text` bo'sh edi. Bu migratsiya har bir kitob uchun uni
hisoblaydi (sarlavha + mualliflar + mavzular + nashriyot, kirill/lotin
birlashtirilgan) va PostgreSQL FTS vektorini to'ldiradi.

MUHIM: bu yerda `book_app.search` dan foydalanilmaydi. Migratsiya o'sha
paytdagi SXEMA bilan ishlashi kerak; jonli kod esa keyin o'zgaradi va
hali mavjud bo'lmagan ustunni so'rab qolishi mumkin (aynan shunday bo'lgan:
0024 da `search_title` qo'shilgach, bu migratsiya toza bazada yiqilgan edi).
Shuning uchun faqat o'zgarmas `fold()` yordamchisi import qilinadi va
model `apps.get_model` orqali olinadi.
"""
from django.contrib.postgres.search import SearchVector
from django.db import migrations

BATCH = 500


def build_index(apps, schema_editor):
    from book_app.translit import fold   # sof funksiya, sxemaga bog'liq emas

    Book = apps.get_model('book_app', 'Book')

    books = (Book.objects
             .select_related('publisher', 'series', 'category')
             .prefetch_related('authors', 'subjects'))

    bucket, updated = [], 0
    for book in books.iterator(chunk_size=BATCH):
        parts = [book.title, book.subtitle, book.parallel_title, book.isbn,
                 book.udc, book.bbk, book.faculty, book.department]
        parts += [author.full_name for author in book.authors.all()]
        parts += [subject.name for subject in book.subjects.all()]
        if book.publisher_id:
            parts.append(book.publisher.name)
        if book.series_id:
            parts.append(book.series.name)
        if book.category_id:
            parts.append(book.category.name)

        book.search_text = fold(" ".join(str(p) for p in parts if p))[:4000]
        bucket.append(book)

        if len(bucket) >= BATCH:
            Book.objects.bulk_update(bucket, ['search_text'])
            updated += len(bucket)
            bucket = []

    if bucket:
        Book.objects.bulk_update(bucket, ['search_text'])
        updated += len(bucket)

    if schema_editor.connection.vendor == 'postgresql':
        Book.objects.update(search_vector=SearchVector('search_text', config='simple'))

    print(f"  {updated} ta yozuv qidiruv uchun indekslandi")


class Migration(migrations.Migration):

    dependencies = [
        ('book_app', '0022_book_search_vector_alter_book_search_text_and_more'),
    ]

    operations = [
        migrations.RunPython(build_index, migrations.RunPython.noop),
    ]
