from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


class SiteSettings(models.Model):
    THEME_DEFAULT = 'default'
    THEME_GLASS = 'glass'
    THEME_CHOICES = [
        (THEME_DEFAULT, 'Default (Dark Poker)'),
        (THEME_GLASS, 'Glass (Modern)'),
    ]
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default=THEME_DEFAULT)

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Site Settings (theme: {self.theme})'


class Player(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class MonthlyGame(models.Model):
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
    ]
    
    month = models.IntegerField(choices=MONTH_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.IntegerField()
    uploaded_file = models.FileField(upload_to='monthly_games/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('month', 'year')
        ordering = ['year', 'month']
        get_latest_by = 'uploaded_at'

    def __str__(self):
        return f"{self.get_month_display()} {self.year}"


class GameScore(models.Model):
    game = models.ForeignKey(MonthlyGame, on_delete=models.CASCADE, related_name='scores')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='scores')
    score = models.DecimalField(max_digits=10, decimal_places=2)
    rank = models.IntegerField(null=True, blank=True)
    knockouts = models.IntegerField(default=0)

    class Meta:
        ordering = ['rank', '-score']
        unique_together = ('game', 'player')

    def __str__(self):
        return f"{self.player.name} - {self.game} - {self.score}"


class OverallStats(models.Model):
    year = models.IntegerField(unique=True)
    uploaded_file = models.FileField(upload_to='overall_stats/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year']
        verbose_name_plural = 'Overall Stats'
        get_latest_by = 'uploaded_at'

    def __str__(self):
        return f"Overall Stats {self.year}"


class PlayerOverallStat(models.Model):
    overall = models.ForeignKey(OverallStats, on_delete=models.CASCADE, related_name='player_stats')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='overall_stats')
    games_played = models.IntegerField(default=0)
    eoy_pool = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_knockouts = models.IntegerField(default=0)

    class Meta:
        unique_together = ('overall', 'player')
        ordering = ['-eoy_pool']

    def __str__(self):
        return f"{self.player.name} - {self.overall.year}"


class PokerEvent(models.Model):
    title = models.CharField(max_length=200)
    event_date = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ['event_date']
        get_latest_by = 'updated_at'

    def __str__(self):
        return f"{self.title} - {self.event_date.strftime('%b %d, %Y')}"


# ── Announcements ──────────────────────────────────────────────────────────────

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_pinned = models.BooleanField(default=False, help_text="Pinned announcements appear at the top")
    is_active = models.BooleanField(default=True, help_text="Only active announcements are shown to members")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        get_latest_by = 'created_at'

    def __str__(self):
        return self.title


# ── Event RSVPs ────────────────────────────────────────────────────────────────

class EventRSVP(models.Model):
    RESPONSE_CHOICES = [
        ('yes', 'Yes'),
        ('maybe', 'Maybe'),
        ('no', 'No'),
    ]
    event = models.ForeignKey(PokerEvent, on_delete=models.CASCADE, related_name='rsvps')
    user_identifier = models.CharField(max_length=254)
    response = models.CharField(max_length=5, choices=RESPONSE_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('event', 'user_identifier')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user_identifier} → {self.event} ({self.response})"


# ── High Hand of the Year ──────────────────────────────────────────────────────

CARD_RANK_CHOICES = [
    ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6'),
    ('7', '7'), ('8', '8'), ('9', '9'), ('T', '10'),
    ('J', 'Jack'), ('Q', 'Queen'), ('K', 'King'), ('A', 'Ace'),
]

CARD_SUIT_CHOICES = [
    ('s', 'Spades ♠'),
    ('h', 'Hearts ♥'),
    ('d', 'Diamonds ♦'),
    ('c', 'Clubs ♣'),
]

HAND_TYPE_CHOICES = [
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
]

_CARD_CHOICES = [
    (f"{r}{s}", f"{rl} of {sl}")
    for r, rl in CARD_RANK_CHOICES
    for s, sl in CARD_SUIT_CHOICES
]


class HighHand(models.Model):
    """Tracks the current High Hand of the Year holder."""
    year        = models.IntegerField(unique=True)
    player_name = models.CharField(max_length=100)
    hand_type   = models.CharField(max_length=30, choices=HAND_TYPE_CHOICES)
    # Five cards stored as rank+suit strings, e.g. "As", "Kh", "Qd", "Jc", "Ts"
    card1 = models.CharField(max_length=2, choices=_CARD_CHOICES)
    card2 = models.CharField(max_length=2, choices=_CARD_CHOICES)
    card3 = models.CharField(max_length=2, choices=_CARD_CHOICES)
    card4 = models.CharField(max_length=2, choices=_CARD_CHOICES)
    card5 = models.CharField(max_length=2, choices=_CARD_CHOICES)
    notes = models.CharField(
        max_length=300, blank=True,
        help_text="Optional context, e.g. 'Dealt at March tournament'"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year']
        verbose_name = 'High Hand of the Year'
        verbose_name_plural = 'High Hands of the Year'

    def __str__(self):
        return f"{self.year} High Hand — {self.player_name} ({self.get_hand_type_display()})"

    @property
    def cards(self):
        return [self.card1, self.card2, self.card3, self.card4, self.card5]


class AllowedEmail(models.Model):
    email = models.EmailField(unique=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['email']

    def __str__(self):
        return self.email


# ── Push Notifications ────────────────────────────────────────────────────────

class PushToken(models.Model):
    PLATFORM_CHOICES = [('ios', 'iOS'), ('android', 'Android')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.platform}"


class UserProfile(models.Model):
    """Extends the built-in User with push-notification targeting flags."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    is_internal_tester = models.BooleanField(
        default=False,
        help_text='Receives push notifications sent to the internal-tester audience.',
    )

    def __str__(self):
        return f"Profile({self.user})"


class EventPushLog(models.Model):
    """Idempotency record — prevents double-sending scheduled event pushes."""
    KIND_HEADCOUNT = 'headcount_nudge'
    KIND_DAY_OF = 'day_of'
    KIND_CHOICES = [
        (KIND_HEADCOUNT, 'Headcount Nudge'),
        (KIND_DAY_OF, 'Day-of Reminder'),
    ]
    event = models.ForeignKey(PokerEvent, on_delete=models.CASCADE, related_name='push_logs')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    sent_date = models.DateField()

    class Meta:
        unique_together = ('event', 'kind', 'sent_date')

    def __str__(self):
        return f"{self.event} — {self.kind} ({self.sent_date})"


# ── Auto-create UserProfile whenever a User is saved ─────────────────────────

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_profile(sender, instance, created, **kwargs):
    UserProfile.objects.get_or_create(user=instance)


# ── Announcement push signal ──────────────────────────────────────────────────

@receiver(post_save, sender=Announcement)
def push_new_announcement(sender, instance, created, **kwargs):
    if not created:
        return
    from .push import send_expo_push
    tokens = list(PushToken.objects.values_list('token', flat=True))
    if tokens:
        send_expo_push(
            tokens,
            title='FeltSync',
            body=instance.title,
            data={'kind': 'announcement', 'announcementId': instance.id},
        )
