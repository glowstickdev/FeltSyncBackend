from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('csvapp', '0005_add_event_end_time'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventRSVP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_identifier', models.CharField(max_length=254)),
                ('response', models.CharField(choices=[('yes', 'Yes'), ('maybe', 'Maybe'), ('no', 'No')], max_length=5)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rsvps', to='csvapp.pokerevent')),
            ],
            options={
                'ordering': ['-updated_at'],
                'unique_together': {('event', 'user_identifier')},
            },
        ),
    ]
