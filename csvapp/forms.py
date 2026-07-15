from django import forms
from django.utils import timezone

from .models import GameScore, PokerEvent, Announcement, HighHand, HAND_TYPE_CHOICES, _CARD_CHOICES


MONTH_CHOICES = [
    (1, "January"), (2, "February"), (3, "March"),
    (4, "April"), (5, "May"), (6, "June"),
    (7, "July"), (8, "August"), (9, "September"),
    (10, "October"), (11, "November"), (12, "December"),
]


class UploadGameForm(forms.Form):
    month = forms.ChoiceField(choices=MONTH_CHOICES, label="Tournament Month")
    year = forms.IntegerField(
        min_value=2020,
        max_value=2100,
        initial=timezone.now().year,
        label="Year",
    )
    csv_file = forms.FileField(
        label="Monthly Tournament CSV",
        help_text="Export from your poker software — must include Nickname, Points, and Hits columns.",
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Notes (optional)")
    overwrite = forms.BooleanField(
        required=False,
        label="Overwrite existing data for this month/year",
    )


class UploadOverallForm(forms.Form):
    year = forms.IntegerField(
        min_value=2020,
        max_value=2100,
        initial=timezone.now().year,
        label="Season Year",
    )
    csv_file = forms.FileField(
        label="Overall / Year-to-Date CSV",
        help_text="Must include Name, Games Played, EOY Pool, and Knockouts columns.",
    )
    overwrite = forms.BooleanField(
        required=False,
        label="Replace existing overall stats for this year",
    )


class PokerEventForm(forms.ModelForm):
    event_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M"],
        label="Start Time",
        help_text="Arizona time (MST — UTC-7, no daylight saving)",
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M"],
        label="End Time",
        help_text="Arizona time. Leave blank to default to 4 hours after start.",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        from zoneinfo import ZoneInfo
        super().__init__(*args, **kwargs)
        az = ZoneInfo("America/Phoenix")
        if self.instance and self.instance.pk:
            if self.instance.event_date:
                self.initial["event_date"] = self.instance.event_date.astimezone(az).strftime("%Y-%m-%dT%H:%M")
            if self.instance.end_time:
                self.initial["end_time"] = self.instance.end_time.astimezone(az).strftime("%Y-%m-%dT%H:%M")

    def _localize_az(self, dt):
        from zoneinfo import ZoneInfo
        return dt.replace(tzinfo=None).replace(tzinfo=ZoneInfo("America/Phoenix"))

    def clean_event_date(self):
        return self._localize_az(self.cleaned_data["event_date"])

    def clean_end_time(self):
        dt = self.cleaned_data.get("end_time")
        if dt:
            return self._localize_az(dt)
        return None

    class Meta:
        model = PokerEvent
        fields = ["title", "event_date", "end_time", "location", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. March Monthly Tournament"}),
            "location": forms.TextInput(attrs={"placeholder": "e.g. John's House, 123 Main St"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Buy-in details, special rules, notes..."}),
        }


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "body", "is_pinned", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. April Tournament Date Change"}),
            "body": forms.Textarea(attrs={
                "rows": 6,
                "placeholder": "Write your announcement here. Line breaks are preserved.",
            }),
        }
        labels = {
            "is_pinned": "Pin to top of announcements page & leaderboard strip",
            "is_active": "Publish (visible to all members)",
        }


class GameScoreEditForm(forms.ModelForm):
    class Meta:
        model = GameScore
        fields = ["rank", "score", "knockouts"]
        widgets = {
            "rank": forms.NumberInput(attrs={"min": 1}),
            "score": forms.NumberInput(attrs={"step": "0.01", "min": 0}),
            "knockouts": forms.NumberInput(attrs={"min": 0}),
        }


class HighHandForm(forms.ModelForm):
    card1 = forms.ChoiceField(choices=_CARD_CHOICES, label="Card 1")
    card2 = forms.ChoiceField(choices=_CARD_CHOICES, label="Card 2")
    card3 = forms.ChoiceField(choices=_CARD_CHOICES, label="Card 3")
    card4 = forms.ChoiceField(choices=_CARD_CHOICES, label="Card 4")
    card5 = forms.ChoiceField(choices=_CARD_CHOICES, label="Card 5")

    class Meta:
        model = HighHand
        fields = ["year", "player_name", "hand_type", "card1", "card2", "card3", "card4", "card5", "notes"]
        widgets = {
            "year": forms.NumberInput(attrs={"placeholder": "e.g. 2026"}),
            "player_name": forms.TextInput(attrs={"placeholder": "e.g. Mike"}),
            "notes": forms.TextInput(attrs={"placeholder": "e.g. Dealt at March tournament (optional)"}),
        }
        labels = {
            "player_name": "Player Name",
            "hand_type": "Hand Type",
            "notes": "Notes (optional)",
        }
