# Generated by Django 5.0.6 on 2024-12-19 19:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_app', '0003_alter_user_first_name_alter_user_second_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='current_role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='user_app.role', verbose_name='Hozirgi rol'),
        ),
    ]
