# Generated by Django 4.1.7 on 2023-03-20 20:40

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("top_albums", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="album",
            name="is_itunes_top",
            field=models.BooleanField(default=True),
        ),
    ]
