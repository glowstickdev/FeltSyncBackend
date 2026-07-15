from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Player, MonthlyGame, GameScore, PokerEvent, Announcement, HighHand, AllowedEmail, UserProfile


# ─── User admin with approval workflow ───────────────────────────────────────

class ApprovalStatusFilter(admin.SimpleListFilter):
    title = 'approval status'
    parameter_name = 'approved'

    def lookups(self, request, model_admin):
        return [('yes', 'Approved'), ('no', 'Pending')]

    def queryset(self, request, queryset):
        approved_emails = AllowedEmail.objects.values_list('email', flat=True)
        if self.value() == 'yes':
            return queryset.filter(email__in=approved_emails)
        if self.value() == 'no':
            return queryset.exclude(email__in=approved_emails)
        return queryset


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    verbose_name_plural = 'Push Notification Settings'


class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_approved', 'is_internal_tester_display')
    list_filter = UserAdmin.list_filter + (ApprovalStatusFilter, 'profile__is_internal_tester')
    inlines = [UserProfileInline]
    actions = ['approve_users']

    @admin.display(boolean=True, description='Approved')
    def is_approved(self, obj):
        return AllowedEmail.objects.filter(email=obj.email).exists()

    @admin.display(boolean=True, description='Internal Tester')
    def is_internal_tester_display(self, obj):
        try:
            return obj.profile.is_internal_tester
        except UserProfile.DoesNotExist:
            return False

    @admin.action(description='Approve selected users')
    def approve_users(self, request, queryset):
        approved = 0
        already = 0
        for user in queryset:
            _, created = AllowedEmail.objects.get_or_create(email=user.email)
            if created:
                approved += 1
            else:
                already += 1
        parts = []
        if approved:
            parts.append(f'{approved} user{"s" if approved != 1 else ""} approved.')
        if already:
            parts.append(f'{already} already approved.')
        self.message_user(request, ' '.join(parts))


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


class GameScoreInline(admin.TabularInline):
    model = GameScore
    extra = 0
    readonly_fields = ("rank",)


@admin.register(MonthlyGame)
class MonthlyGameAdmin(admin.ModelAdmin):
    list_display = ("__str__", "month", "year", "uploaded_at")
    list_filter = ("year", "month")
    inlines = [GameScoreInline]


@admin.register(GameScore)
class GameScoreAdmin(admin.ModelAdmin):
    list_display = ("player", "game", "score", "rank")
    list_filter = ("game__year", "game__month")
    search_fields = ("player__name",)


@admin.register(PokerEvent)
class PokerEventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_date", "location", "created_at")
    list_filter = ("event_date",)
    search_fields = ("title", "location", "description")
    ordering = ("event_date",)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_pinned", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "is_pinned")
    list_editable = ("is_pinned", "is_active")
    search_fields = ("title", "body")
    ordering = ("-is_pinned", "-created_at")
    fieldsets = (
        (None, {
            "fields": ("title", "body"),
        }),
        ("Visibility", {
            "fields": ("is_active", "is_pinned"),
            "description": (
                "Pinned announcements appear first and are shown as a strip "
                "on the leaderboard. Inactive announcements are hidden from members."
            ),
        }),
    )


@admin.register(AllowedEmail)
class AllowedEmailAdmin(admin.ModelAdmin):
    list_display = ("email", "added_at")
    search_fields = ("email",)


@admin.register(HighHand)
class HighHandAdmin(admin.ModelAdmin):
    list_display = ("year", "player_name", "hand_type", "updated_at")
    list_filter = ("year", "hand_type")
    search_fields = ("player_name",)
    fieldsets = (
        ("Season & Player", {
            "fields": ("year", "player_name"),
        }),
        ("Hand", {
            "fields": ("hand_type", "card1", "card2", "card3", "card4", "card5"),
            "description": (
                "Enter each card as rank + suit. "
                "Ranks: 2–9, T (ten), J, Q, K, A. "
                "Suits: s (spades ♠), h (hearts ♥), d (diamonds ♦), c (clubs ♣). "
                "Examples: As = Ace of Spades · Kh = King of Hearts · Td = Ten of Diamonds"
            ),
        }),
        ("Notes", {
            "fields": ("notes",),
        }),
    )
