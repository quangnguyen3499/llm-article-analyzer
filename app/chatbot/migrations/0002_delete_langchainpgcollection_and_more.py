# Generated by Django 4.2.16 on 2025-02-02 23:13

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("chatbot", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="LangchainPgCollection",
        ),
        migrations.DeleteModel(
            name="LangchainPgEmbedding",
        ),
    ]
