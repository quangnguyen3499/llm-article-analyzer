from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chatbot", "0002_delete_langchainpgcollection_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CareerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="My career profile", max_length=120)),
                ("source_name", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
    ]
