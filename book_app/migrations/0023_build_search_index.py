"""
Mavjud katalog uchun qidiruv indeksini bir marta qurish.

v3 gacha `search_text` bo'sh edi. Bu migratsiya har bir kitob uchun uni
hisoblaydi (sarlavha + mualliflar + mavzular + nashriyot, kirill/lotin
birlashtirilgan) va PostgreSQL FTS vektorini to'ldiradi.

Keyinchalik indeks o'z-o'zidan yangilanadi (`book_app/signals.py`).
"""
from django.db import migrations


def build_index(apps, schema_editor):
    # Bu bir martalik indeks qurish — mantiqni takrorlamaslik uchun
    # servis funksiyasidan foydalanamiz (sxemaga ta'sir qilmaydi).
    from book_app.search import rebuild_all

    count = rebuild_all()
    print(f"  {count} ta yozuv qidiruv uchun indekslandi")


class Migration(migrations.Migration):

    dependencies = [
        ('book_app', '0022_book_search_vector_alter_book_search_text_and_more'),
    ]

    operations = [
        migrations.RunPython(build_index, migrations.RunPython.noop),
    ]
