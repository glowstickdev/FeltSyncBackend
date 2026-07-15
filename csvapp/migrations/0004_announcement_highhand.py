from django.db import migrations, models

_CARD_CHOICES = [
    (f"{r}{s}", f"{rl} of {sl}")
    for r, rl in [
        ('2','2'),('3','3'),('4','4'),('5','5'),('6','6'),
        ('7','7'),('8','8'),('9','9'),('T','10'),
        ('J','Jack'),('Q','Queen'),('K','King'),('A','Ace'),
    ]
    for s, sl in [
        ('s','Spades ♠'),('h','Hearts ♥'),('d','Diamonds ♦'),('c','Clubs ♣'),
    ]
]


class Migration(migrations.Migration):

    dependencies = [
        ('csvapp', '0003_alter_gamescore_options_alter_monthlygame_options_and_more'),
    ]

    operations = [
        # ── Announcement ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('is_pinned', models.BooleanField(default=False, help_text='Pinned announcements appear at the top')),
                ('is_active', models.BooleanField(default=True, help_text='Only active announcements are shown to members')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-is_pinned', '-created_at'],
                'get_latest_by': 'created_at',
            },
        ),

        # ── HighHand ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='HighHand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField(unique=True)),
                ('player_name', models.CharField(max_length=100)),
                ('hand_type', models.CharField(max_length=30, choices=[
                    ('royal_flush',     'Royal Flush'),
                    ('straight_flush',  'Straight Flush'),
                    ('four_of_a_kind',  'Four of a Kind'),
                    ('full_house',      'Full House'),
                    ('flush',           'Flush'),
                    ('straight',        'Straight'),
                    ('three_of_a_kind', 'Three of a Kind'),
                    ('two_pair',        'Two Pair'),
                    ('one_pair',        'One Pair'),
                    ('high_card',       'High Card'),
                ])),
                ('card1', models.CharField(max_length=2, choices=_CARD_CHOICES)),
                ('card2', models.CharField(max_length=2, choices=_CARD_CHOICES)),
                ('card3', models.CharField(max_length=2, choices=_CARD_CHOICES)),
                ('card4', models.CharField(max_length=2, choices=_CARD_CHOICES)),
                ('card5', models.CharField(max_length=2, choices=_CARD_CHOICES)),
                ('notes', models.CharField(blank=True, max_length=300, help_text="Optional context, e.g. 'Dealt at March tournament'")),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'High Hand of the Year',
                'verbose_name_plural': 'High Hands of the Year',
                'ordering': ['-year'],
            },
        ),
    ]
