from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # ── Player ──
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),

        # ── MonthlyGame ──
        migrations.CreateModel(
            name='MonthlyGame',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.IntegerField(choices=[
                    (1,'January'),(2,'February'),(3,'March'),
                    (4,'April'),(5,'May'),(6,'June'),
                    (7,'July'),(8,'August'),(9,'September'),
                    (10,'October'),(11,'November'),(12,'December'),
                ])),
                ('year', models.IntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_file', models.FileField(upload_to='uploads/%Y/%m/')),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-year', '-month'],
                'unique_together': {('month', 'year')},
            },
        ),

        # ── GameScore ──
        migrations.CreateModel(
            name='GameScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.FloatField()),
                ('rank', models.IntegerField(blank=True, null=True)),
                ('knockouts', models.IntegerField(default=0)),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='csvapp.monthlygame')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='csvapp.player')),
            ],
            options={
                'ordering': ['-score'],
                'unique_together': {('game', 'player')},
            },
        ),

        # ── OverallStats ──
        migrations.CreateModel(
            name='OverallStats',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_file', models.FileField(upload_to='uploads/overall/%Y/')),
            ],
            options={
                'ordering': ['-year', '-uploaded_at'],
                'get_latest_by': 'uploaded_at',
            },
        ),

        # ── PlayerOverallStat ──
        migrations.CreateModel(
            name='PlayerOverallStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('games_played', models.IntegerField(default=0)),
                ('eoy_pool', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('total_knockouts', models.IntegerField(default=0)),
                ('overall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_stats', to='csvapp.overallstats')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='overall_stats', to='csvapp.player')),
            ],
            options={
                'unique_together': {('overall', 'player')},
            },
        ),
    ]
