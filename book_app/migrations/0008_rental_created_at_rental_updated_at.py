# Generated by Django 5.0.6 on 2025-01-06 11:37

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book_app', '0007_alter_rental_borrowed_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='rental',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='Kitob yaratilgan sana'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='rental',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Kitob yangilangan sana'),
        ),
    ]
