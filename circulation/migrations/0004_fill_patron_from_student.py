"""
P1-B data-migratsiyasi: mavjud ijara/so'rov/navbat/jarima yozuvlariga `patron` biriktiriladi.

Eski yozuvlarda qarz oluvchi `StudentProfile` edi. Har bir yozuv uchun
`student.user.patron` topiladi va `patron` maydoniga yoziladi. `student` maydoni
o'chirilmaydi — P3 (`Loan`ga ko'chish) gacha ikki yozuvli davr davom etadi.

A'zoligi yo'q (kamdan-kam) foydalanuvchi uchun yozuv `patron=None` bo'lib qoladi:
hisobotlar `borrower_name` orqali baribir to'g'ri ko'rsatadi.
"""
from django.db import migrations


def fill(apps, schema_editor):
    Patron = apps.get_model('user_app', 'Patron')
    models_to_fix = [
        (apps.get_model('book_app', 'Rental'), 'ijara'),
        (apps.get_model('circulation', 'RentalRequest'), "so'rov"),
        (apps.get_model('circulation', 'Reservation'), 'navbat'),
        (apps.get_model('circulation', 'Fine'), 'jarima'),
    ]

    # user_id -> patron_id xaritasi (har yozuv uchun alohida so'rov qilmaslik uchun)
    patron_by_user = dict(
        Patron.objects.exclude(user__isnull=True).values_list('user_id', 'id')
    )

    for model, label in models_to_fix:
        updated = []
        for row in model.objects.filter(patron__isnull=True,
                                        student__isnull=False).select_related('student'):
            patron_id = patron_by_user.get(row.student.user_id)
            if patron_id:
                row.patron_id = patron_id
                updated.append(row)
        if updated:
            model.objects.bulk_update(updated, ['patron'])
        print(f"  {label}: {len(updated)} ta yozuvga a'zo biriktirildi")


class Migration(migrations.Migration):

    dependencies = [
        ('circulation', '0003_remove_rentalrequest_uniq_pending_request_per_student_book_and_more'),
        ('book_app', '0018_rental_patron_alter_rental_student_and_more'),
        ('user_app', '0014_seed_patrons_and_permissions'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
