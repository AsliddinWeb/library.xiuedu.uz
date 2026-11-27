"""
P2 — 1-qadam: `Copy` modeli `Item`ga QAYTA NOMLANADI.

MUHIM: `makemigrations` avtomatik ravishda "Copy o'chirildi + Item yaratildi" deb
yozgan edi — bunday migratsiya fonddagi barcha nusxani (va ularga bog'langan
ijaralarni) YO'Q QILGAN bo'lardi. Shuning uchun fayl qo'lda `RenameModel`ga
almashtirildi: jadval nomi o'zgaradi (`book_app_copy` -> `book_app_item`),
ma'lumot joyida qoladi, FK va cheklovlar Postgres tomonidan avtomatik ko'chiriladi.

Qolgan barcha o'zgarish (yangi maydonlar, Publisher/Series/Subject/Contributor)
keyingi migratsiyalarda.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('book_app', '0018_rental_patron_alter_rental_student_and_more'),
    ]

    operations = [
        migrations.RenameModel(old_name='Copy', new_name='Item'),
    ]
