# Generated by Django 4.2.7 on 2023-12-25 09:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_userprofile_profile_pic'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='profile_pic',
            field=models.ImageField(blank=True, default='default.jpeg', null=True, upload_to='profile_pictures'),
        ),
    ]