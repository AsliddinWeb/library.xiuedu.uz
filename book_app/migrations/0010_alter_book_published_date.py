# Generated by Django 5.0.6 on 2025-01-24 06:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book_app', '0009_alter_book_published_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='book',
            name='published_date',
            field=models.CharField(blank=True, default='2020', max_length=255, null=True, verbose_name='Chop etilgan sana'),
        ),
    ]
