"""
Tayyor ish o'rinlari: "Kataloglovchi" va "Abonement xodimi".

Administrator ruxsatlarni qo'lda yig'masdan, xodimga mos rolni tanlaydi. Shunday
nomli rol allaqachon bo'lsa, unga tegilmaydi.
"""
from django.db import migrations

ROLES = {
    "Kataloglovchi": (
        "Katalog va fondni yuritadi",
        ['catalog.view', 'catalog.edit', 'catalog.import', 'items.manage', 'reports.export'],
    ),
    "Abonement xodimi": (
        "Kitob beradi va qabul qiladi",
        ['catalog.view', 'circ.checkout', 'circ.checkin', 'circ.renew', 'circ.holds',
         'patrons.view', 'patrons.edit', 'billing.charge', 'billing.collect'],
    ),
}


def seed(apps, schema_editor):
    Role = apps.get_model('user_app', 'Role')
    for name, (description, permissions) in ROLES.items():
        Role.objects.get_or_create(
            name=name, defaults={'description': description, 'permissions': permissions})


class Migration(migrations.Migration):
    dependencies = [
        ('user_app', '0016_xodim_verbose_name'),
    ]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
