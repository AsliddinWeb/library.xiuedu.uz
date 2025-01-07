# Generated by Django 5.0.6 on 2024-12-19 19:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_app', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='admin',
            options={'verbose_name': 'Admin', 'verbose_name_plural': 'Adminlar'},
        ),
        migrations.AlterModelOptions(
            name='employee',
            options={'verbose_name': 'Xodim', 'verbose_name_plural': 'Xodimlar'},
        ),
        migrations.AlterModelOptions(
            name='libraryadmin',
            options={'verbose_name': 'Kutubxona Admini', 'verbose_name_plural': 'Kutubxona Adminlari'},
        ),
        migrations.AlterModelOptions(
            name='role',
            options={'verbose_name': 'Rol', 'verbose_name_plural': 'Rollar'},
        ),
        migrations.AlterModelOptions(
            name='student',
            options={'verbose_name': 'Talaba', 'verbose_name_plural': 'Talabalar'},
        ),
        migrations.AlterModelOptions(
            name='user',
            options={'verbose_name': 'Foydalanuvchi', 'verbose_name_plural': 'Foydalanuvchilar'},
        ),
        migrations.AlterModelOptions(
            name='userrole',
            options={'verbose_name': 'Foydalanuvchi-Rol', 'verbose_name_plural': 'Foydalanuvchilar-Rollar'},
        ),
        migrations.AlterField(
            model_name='libraryadmin',
            name='bio',
            field=models.TextField(blank=True, null=True, verbose_name='Kutubxona admini haqida'),
        ),
    ]
