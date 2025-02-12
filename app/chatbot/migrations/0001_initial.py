# Generated by Django 4.2.7 on 2023-11-21 17:48

from django.db import migrations, models
import pgvector.django


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LangchainPgCollection",
            fields=[
                ("name", models.CharField(blank=True, null=True)),
                ("cmetadata", models.TextField(blank=True, null=True)),
                ("uuid", models.UUIDField(primary_key=True, serialize=False)),
            ],
            options={
                "db_table": "langchain_pg_collection",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="LangchainPgEmbedding",
            fields=[
                ("embedding", pgvector.django.VectorField(dimensions=1536)),
                ("document", models.CharField(blank=True, null=True)),
                ("cmetadata", models.TextField(blank=True, null=True)),
                ("custom_id", models.CharField(blank=True, null=True)),
                ("uuid", models.UUIDField(primary_key=True, serialize=False)),
            ],
            options={
                "db_table": "langchain_pg_embedding",
                "managed": False,
            },
        ),
    ]
