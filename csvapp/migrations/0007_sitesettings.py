from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('csvapp', '0006_eventrsvp'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(
                    choices=[('default', 'Default (Dark Poker)'), ('glass', 'Glass (Modern)')],
                    default='default',
                    max_length=20,
                )),
            ],
            options={
                'verbose_name': 'Site Settings',
                'verbose_name_plural': 'Site Settings',
            },
        ),
    ]
