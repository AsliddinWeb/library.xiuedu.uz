# Generated by Django 5.0.6 on 2024-12-20 08:00

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_app', '0004_user_current_role'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='employee',
            name='user',
        ),
        migrations.RemoveField(
            model_name='libraryadmin',
            name='user',
        ),
        migrations.RemoveField(
            model_name='student',
            name='user',
        ),
        migrations.AlterUniqueTogether(
            name='userrole',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='userrole',
            name='role',
        ),
        migrations.RemoveField(
            model_name='userrole',
            name='user',
        ),
        migrations.AlterModelOptions(
            name='role',
            options={},
        ),
        migrations.AlterModelOptions(
            name='user',
            options={},
        ),
        migrations.RemoveField(
            model_name='user',
            name='date_joined',
        ),
        migrations.RemoveField(
            model_name='user',
            name='last_name',
        ),
        migrations.AddField(
            model_name='user',
            name='user_type',
            field=models.CharField(choices=[('STUDENT', 'Student'), ('EMPLOYE', 'Employe')], default='STUDENT', max_length=10),
        ),
        migrations.AlterField(
            model_name='role',
            name='name',
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='is_staff',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(max_length=150, unique=True),
        ),
        migrations.CreateModel(
            name='Employe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('roles', models.ManyToManyField(blank=True, to='user_app.role')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='employe_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.DeleteModel(
            name='Admin',
        ),
        migrations.DeleteModel(
            name='Employee',
        ),
        migrations.DeleteModel(
            name='LibraryAdmin',
        ),
        migrations.DeleteModel(
            name='Student',
        ),
        migrations.DeleteModel(
            name='UserRole',
        ),
    ]
