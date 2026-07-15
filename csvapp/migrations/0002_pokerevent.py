from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("csvapp", "0001_initial"),  # adjust this to match your latest migration
    ]

    operations = [
        migrations.CreateModel(
            name="PokerEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("event_date", models.DateTimeField()),
                ("location", models.CharField(blank=True, max_length=300)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["event_date"],
            },
        ),
    ]
