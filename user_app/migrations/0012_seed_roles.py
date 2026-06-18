from django.db import migrations

ROLES = [
    ('Student', 'Talaba'),
    ('Employee', 'Xodim'),
    ('LibraryAdmin', 'Kutubxonachi'),
    ('Admin', 'Administrator'),
]


def seed(apps, schema_editor):
    Role = apps.get_model('user_app', 'Role')
    for name, desc in ROLES:
        Role.objects.get_or_create(name=name, defaults={'description': desc})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('user_app', '0011_alter_role_options_employeprofile_created_at_and_more'),
    ]
    operations = [migrations.RunPython(seed, noop)]
