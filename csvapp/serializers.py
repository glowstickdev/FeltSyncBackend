import calendar
from rest_framework import serializers
from .models import (
    Player, GameScore, MonthlyGame,
    PokerEvent, EventRSVP, Announcement, HighHand,
)


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['id', 'name']


class GameScoreSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)

    class Meta:
        model = GameScore
        fields = ['id', 'player', 'score', 'rank', 'knockouts']


class MonthlyResultSerializer(serializers.ModelSerializer):
    # related_name on GameScore FK to MonthlyGame is 'scores'
    scores = GameScoreSerializer(many=True, read_only=True, source='scores')
    month_name = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyGame
        fields = ['year', 'month', 'month_name', 'scores', 'uploaded_at', 'notes']

    def get_month_name(self, obj):
        return calendar.month_name[obj.month]


class PokerEventSerializer(serializers.ModelSerializer):
    rsvp_counts = serializers.SerializerMethodField()
    my_rsvp = serializers.SerializerMethodField()

    class Meta:
        model = PokerEvent
        fields = [
            'id', 'title', 'event_date', 'end_time',
            'location', 'description', 'rsvp_counts', 'my_rsvp', 'created_at',
        ]

    def get_rsvp_counts(self, obj):
        # related_name on EventRSVP FK to PokerEvent is 'rsvps'
        qs = obj.rsvps.all()
        return {
            'yes':   qs.filter(response='yes').count(),
            'maybe': qs.filter(response='maybe').count(),
            'no':    qs.filter(response='no').count(),
        }

    def get_my_rsvp(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        rsvp = obj.rsvps.filter(user_identifier=request.user.email).first()
        return rsvp.response if rsvp else None


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'is_pinned', 'created_at']


class HighHandSerializer(serializers.ModelSerializer):
    cards = serializers.SerializerMethodField()

    class Meta:
        model = HighHand
        fields = ['year', 'player_name', 'hand_type', 'cards', 'notes']

    def get_cards(self, obj):
        return [obj.card1, obj.card2, obj.card3, obj.card4, obj.card5]


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    player = PlayerSerializer()
    top5_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    games_played = serializers.IntegerField()
    total_knockouts = serializers.IntegerField()
    april_knockouts = serializers.IntegerField()
    monthly_scores = serializers.ListField(child=serializers.FloatField(allow_null=True))
    top5_scores = serializers.ListField(child=serializers.FloatField())
    eoy_pool = serializers.DecimalField(max_digits=10, decimal_places=2)


class PlayerSeasonSummarySerializer(serializers.Serializer):
    year = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    top5_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    games_played = serializers.IntegerField()
    total_knockouts = serializers.IntegerField()


class PushTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(choices=['ios', 'android'])


class HeadToHeadSerializer(serializers.Serializer):
    player1 = PlayerSerializer()
    player2 = PlayerSerializer()
    shared_tournaments = serializers.IntegerField()
    player1_wins = serializers.IntegerField()
    player2_wins = serializers.IntegerField()
    ties = serializers.IntegerField()
    player1_avg_score = serializers.CharField()
    player2_avg_score = serializers.CharField()
    player1_avg_rank = serializers.CharField()
    player2_avg_rank = serializers.CharField()
    player1_total_ko = serializers.IntegerField()
    player2_total_ko = serializers.IntegerField()
