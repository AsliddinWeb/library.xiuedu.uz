"""
O'quvchi rollaridan ruxsatlarni olib tashlaydi.

`Student`/`Employee` rollariga `catalog.view` yozilgan edi va u xodim paneliga
kirish uchun yetarli bo'lib qolgan. Endi o'quvchi rollari hech qanday ruxsat
bermaydi (kod ham ularni hisobga olmaydi — bu yozuvni tozalash).
"""
from django.db import migrations


def clear(apps, schema_editor):
    Role = apps.get_model('user_app', 'Role')
    Role.objects.filter(name__in=['Student', 'Employee']).update(permissions=[])


class Migration(migrations.Migration):
    dependencies = [
        ('user_app', '0014_seed_patrons_and_permissions'),
    ]
    operations = [migrations.RunPython(clear, migrations.RunPython.noop)]
