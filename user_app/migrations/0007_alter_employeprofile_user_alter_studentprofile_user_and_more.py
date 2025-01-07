# Generated by Django 5.0.6 on 2024-12-20 08:30

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_app', '0006_remove_user_current_role_alter_role_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employeprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='employe_profile', to=settings.AUTH_USER_MODEL, verbose_name='Foydalanuvchi'),
        ),
        migrations.AlterField(
            model_name='studentprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='student_profile', to=settings.AUTH_USER_MODEL, verbose_name='Foydalanuvchi'),
        ),
        migrations.AlterField(
            model_name='user',
            name='first_name',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Ismi'),
        ),
        migrations.AlterField(
            model_name='user',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Faol'),
        ),
        migrations.AlterField(
            model_name='user',
            name='is_staff',
            field=models.BooleanField(default=False, verbose_name='Hodim'),
        ),
        migrations.AlterField(
            model_name='user',
            name='second_name',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Familiyasi'),
        ),
        migrations.AlterField(
            model_name='user',
            name='third_name',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Sharifi'),
        ),
        migrations.AlterField(
            model_name='user',
            name='user_type',
            field=models.CharField(choices=[('STUDENT', 'Talaba'), ('EMPLOYE', 'Xodim')], default='STUDENT', max_length=10, verbose_name='Foydalanuvchi turi'),
        ),
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(max_length=150, unique=True, verbose_name='Foydalanuvchi nomi'),
        ),
    ]
