"""
PostgreSQL kengaytmalari (extensions).

- `pg_trgm`   — trigram qidiruv: xato yozilgan so'zni ham topadi
                ("algaritm" -> "Algoritmlar").
- `unaccent`  — diakritik belgilarni tashlab taqqoslash (o'/o, g'/g, ʼ).

Ikkisi ham P5 (OPAC qidiruvi) uchun poydevor, lekin migratsiya hozir qo'yiladi —
shunda dev va prod bazalari bir xil holatda bo'ladi.

SQLite'da (USE_SQLITE=1) bu migratsiya hech narsa qilmaydi.
"""
from django.db import migrations


def create_extensions(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS unaccent')


def drop_extensions(apps, schema_editor):
    # Ataylab hech narsa qilinmaydi: kengaytmani o'chirish boshqa jadvallardagi
    # indekslarni ham yo'q qilib yuborishi mumkin.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_extensions, drop_extensions),
    ]
