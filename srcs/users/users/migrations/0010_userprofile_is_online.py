# Generated by Django 4.2.8 on 2024-01-18 15:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_alter_userprofile_profile_pic'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_online',
            field=models.BooleanField(default=False),
        ),
    ]
