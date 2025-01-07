# Generated by Django 5.0.6 on 2024-12-26 08:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('user_app', '0009_remove_user_jshshir_remove_user_passport_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='Author',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=200, verbose_name='Ism Familiya')),
                ('bio', models.TextField(blank=True, null=True, verbose_name='Qisqacha tavsif')),
            ],
            options={
                'verbose_name': 'Muallif',
                'verbose_name_plural': 'Mualliflar',
            },
        ),
        migrations.CreateModel(
            name='Genre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Janr nomi')),
            ],
            options={
                'verbose_name': 'Janr',
                'verbose_name_plural': 'Janrlar',
            },
        ),
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Kitob nomi')),
                ('published_date', models.DateField(verbose_name='Chop etilgan sana')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Qisqacha tavsif')),
                ('audio_version', models.FileField(blank=True, null=True, upload_to='audio_books/', verbose_name='Audio versiyasi')),
                ('electronic_version', models.FileField(blank=True, null=True, upload_to='ebooks/', verbose_name='Elektron versiyasi')),
                ('page_count', models.PositiveIntegerField(blank=True, null=True, verbose_name='Sahifalar soni')),
                ('cover_image', models.ImageField(blank=True, null=True, upload_to='book_covers/', verbose_name='Muqova rasmi')),
                ('language', models.CharField(default="O'zbekcha", max_length=50, verbose_name='Til')),
                ('isbn', models.CharField(blank=True, max_length=13, null=True, verbose_name='ISBN')),
                ('authors', models.ManyToManyField(to='book_app.author', verbose_name='Mualliflar')),
                ('genres', models.ManyToManyField(to='book_app.genre', verbose_name='Janrlar')),
            ],
            options={
                'verbose_name': 'Kitob',
                'verbose_name_plural': 'Kitoblar',
            },
        ),
        migrations.CreateModel(
            name='Copy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inventory_number', models.CharField(max_length=50, verbose_name='Inventar raqami')),
                ('is_available', models.BooleanField(default=True, verbose_name='Mavjudmi')),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='book_app.book', verbose_name='Kitob')),
            ],
            options={
                'verbose_name': 'Nusxa',
                'verbose_name_plural': 'Nusxalar',
            },
        ),
        migrations.CreateModel(
            name='Rental',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('borrowed_date', models.DateField(verbose_name='Olgan sana')),
                ('return_date', models.DateField(blank=True, null=True, verbose_name='Qaytarish sanasi')),
                ('copy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='book_app.copy', verbose_name='Nusxa')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='user_app.studentprofile', verbose_name="O'quvchi")),
            ],
            options={
                'verbose_name': 'Ijara',
                'verbose_name_plural': 'Ijaralar',
            },
        ),
    ]