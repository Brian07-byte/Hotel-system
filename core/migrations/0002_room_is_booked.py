# Generated by Django 5.1.2 on 2024-10-14 20:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='is_booked',
            field=models.BooleanField(default=False),
        ),
    ]
