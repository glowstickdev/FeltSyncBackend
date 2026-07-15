"""
csvapp/api_views.py
Read-only REST API views. Scoring logic is self-contained here.

FK related_name corrections vs. setup doc defaults:
  MonthlyGame → GameScore:      related_name='scores'       (not gamescore_set)
  PokerEvent  → EventRSVP:      related_name='rsvps'        (not eventrsvp_set)
  OverallStats → PlayerOverallStat: related_name='player_stats' (not playeroverallstat_set)
"""

import calendar
import json
from decimal import Decimal
from datetime import datetime

import jwt
import requests as http_requests
from jwt.algorithms import RSAAlgorithm
from django.conf import settings as django_settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .throttles import (
    LoginRateThrottle,
    RegisterRateThrottle,
    SocialAuthRateThrottle,
    RefreshRateThrottle,
)

from .models import (
    Player, MonthlyGame, GameScore,
    OverallStats, PlayerOverallStat,
    PokerEvent, EventRSVP, Announcement, HighHand, AllowedEmail, PushToken, UserProfile,
)
from .push import send_expo_push
from .serializers import (
    PlayerSerializer,
    PokerEventSerializer,
    AnnouncementSerializer,
    HighHandSerializer,
    LeaderboardEntrySerializer,
    PlayerSeasonSummarySerializer,
    PushTokenSerializer,
)


# ─── Scoring helpers ──────────────────────────────────────────────────────────

def _player_season_total(scores_desc, year):
    top_n = django_settings.SCORING_TOP_N
    cutoff = django_settings.SCORING_TOP_N_FROM_YEAR
    relevant = scores_desc[:top_n] if year >= cutoff else scores_desc
    return sum(relevant, Decimal('0'))


def _build_standings(year):
    """
    Compute ranked standings for a season. Returns a list of dicts sorted
    by season total descending. Each dict contains all fields needed by
    LeaderboardEntrySerializer.
    """
    games = (
        MonthlyGame.objects
        .filter(year=year)
        .prefetch_related('scores__player')  # related_name='scores'
    )

    player_data = {}
    for game in games:
        for gs in game.scores.all():  # related_name='scores'
            pid = gs.player_id
            if pid not in player_data:
                player_data[pid] = {
                    'player': gs.player,
                    'scores': [],
                    'by_month': {},
                    'kos': 0,
                    'april_kos': 0,
                }
            player_data[pid]['scores'].append(gs.score)
            player_data[pid]['by_month'][game.month] = float(gs.score)
            player_data[pid]['kos'] += gs.knockouts
            if game.month >= django_settings.KNOCKOUT_START_MONTH:
                player_data[pid]['april_kos'] += gs.knockouts

    # EOY pool map.
    eoy_map = {}
    try:
        overall = OverallStats.objects.get(year=year)
        for pos in overall.player_stats.select_related('player'):  # related_name='player_stats'
            eoy_map[pos.player_id] = pos.eoy_pool
    except OverallStats.DoesNotExist:
        pass

    standings = []
    for pid, data in player_data.items():
        scores_desc = sorted(data['scores'], reverse=True)
        total = _player_season_total(scores_desc, year)
        top_n = django_settings.SCORING_TOP_N
        cutoff = django_settings.SCORING_TOP_N_FROM_YEAR
        top5_scores = [float(s) for s in (scores_desc[:top_n] if year >= cutoff else scores_desc)]
        monthly_scores = [data['by_month'].get(m, None) for m in range(1, 13)]

        standings.append({
            'player': data['player'],
            'top5_total': total,
            'games_played': len(data['scores']),
            'total_knockouts': data['kos'],
            'april_knockouts': data['april_kos'],
            'monthly_scores': monthly_scores,
            'top5_scores': top5_scores,
            'eoy_pool': eoy_map.get(pid, Decimal('0.00')),
        })

    standings.sort(key=lambda x: (-x['top5_total'], x['player'].name))

    # Assign ranks with tie-sharing (1, 1, 3, 4 format).
    ranked = []
    current_rank = 1
    for i, entry in enumerate(standings):
        if i > 0 and entry['top5_total'] == standings[i - 1]['top5_total']:
            entry['rank'] = ranked[-1]['rank']
        else:
            entry['rank'] = current_rank
        current_rank = i + 2
        ranked.append(entry)

    return ranked


# ─── Views ────────────────────────────────────────────────────────────────────

class SeasonsView(APIView):
    def get(self, request):
        current_year = datetime.now().year
        years = list(
            MonthlyGame.objects
            .values_list('year', flat=True)
            .distinct()
            .order_by('-year')
        )
        if current_year not in years:
            years.insert(0, current_year)
        return Response({'years': years, 'current_year': current_year})


class SeasonLeaderboardView(APIView):
    def get(self, request, year):
        standings = _build_standings(year)
        ko_key = 'april_knockouts' if year >= django_settings.SCORING_TOP_N_FROM_YEAR else 'total_knockouts'
        ko_leaders = sorted(standings, key=lambda x: (-x[ko_key], x['player'].name))

        try:
            high_hand = HighHand.objects.get(year=year)
            high_hand_data = HighHandSerializer(high_hand).data
        except HighHand.DoesNotExist:
            high_hand_data = None

        pinned = (
            Announcement.objects
            .filter(is_active=True, is_pinned=True)
            .order_by('-created_at')[:3]
        )
        now = timezone.now()
        upcoming = (
            PokerEvent.objects
            .prefetch_related('rsvps')  # related_name='rsvps'
            .filter(event_date__gte=now)
            .order_by('event_date')[:3]
        )

        total_eoy_pool = Decimal('0.00')
        try:
            overall = OverallStats.objects.get(year=year)
            agg = overall.player_stats.aggregate(total=Sum('eoy_pool'))  # related_name='player_stats'
            total_eoy_pool = agg['total'] or Decimal('0.00')
        except OverallStats.DoesNotExist:
            pass

        return Response({
            'year': year,
            'standings': LeaderboardEntrySerializer(standings, many=True).data,
            'knockout_leaders': LeaderboardEntrySerializer(ko_leaders, many=True).data,
            'high_hand': high_hand_data,
            'pinned_announcements': AnnouncementSerializer(pinned, many=True).data,
            'upcoming_events': PokerEventSerializer(upcoming, many=True).data,
            'tournament_count': MonthlyGame.objects.filter(year=year).count(),
            'player_count': len(standings),
            'total_eoy_pool': str(total_eoy_pool),
        })


class MonthlyResultView(APIView):
    def get(self, request, year, month):
        try:
            game = MonthlyGame.objects.prefetch_related(
                'scores__player'  # related_name='scores'
            ).get(year=year, month=month)
        except MonthlyGame.DoesNotExist:
            return Response(
                {'detail': 'No tournament found for this month.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        scores = sorted(
            game.scores.all(),  # related_name='scores'
            key=lambda gs: (gs.rank is None, gs.rank or 0, -gs.score)
        )
        return Response({
            'year': game.year,
            'month': game.month,
            'month_name': calendar.month_name[game.month],
            'scores': [
                {
                    'id': gs.id,
                    'player': PlayerSerializer(gs.player).data,
                    'score': str(gs.score),
                    'rank': gs.rank,
                    'knockouts': gs.knockouts,
                }
                for gs in scores
            ],
            'uploaded_at': game.uploaded_at.isoformat(),
            'notes': game.notes or '',
        })


class PlayerListView(APIView):
    def get(self, request):
        players = Player.objects.all().order_by('name')
        return Response(PlayerSerializer(players, many=True).data)


class PlayerDetailView(APIView):
    def get(self, request, pk):
        try:
            player = Player.objects.get(pk=pk)
        except Player.DoesNotExist:
            return Response({'detail': 'Player not found.'}, status=status.HTTP_404_NOT_FOUND)

        years = (
            GameScore.objects
            .filter(player=player)
            .values_list('game__year', flat=True)
            .distinct()
            .order_by('-game__year')
        )

        seasons = []
        lifetime_games = 0
        lifetime_knockouts = 0

        for year in years:
            gs_qs = GameScore.objects.filter(player=player, game__year=year).select_related('game')
            score_values = [gs.score for gs in gs_qs]
            scores_desc = sorted(score_values, reverse=True)
            total = _player_season_total(scores_desc, year)
            kos = sum(gs.knockouts for gs in gs_qs)
            games_played = len(score_values)

            lifetime_games += games_played
            lifetime_knockouts += kos

            standings = _build_standings(year)
            player_rank = next(
                (e['rank'] for e in standings if e['player'].id == player.id), None
            )

            seasons.append({
                'year': year,
                'rank': player_rank,
                'top5_total': total,
                'games_played': games_played,
                'total_knockouts': kos,
            })

        return Response({
            'player': PlayerSerializer(player).data,
            'seasons': PlayerSeasonSummarySerializer(seasons, many=True).data,
            'lifetime_games': lifetime_games,
            'lifetime_knockouts': lifetime_knockouts,
            'seasons_played': len(seasons),
        })


class PlayerGamesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            player = Player.objects.get(pk=pk)
        except Player.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        scores = (GameScore.objects
                  .filter(player=player)
                  .select_related('game')
                  .order_by('-game__year', '-game__month'))

        data = [
            {
                'year': gs.game.year,
                'month': gs.game.month,
                'month_name': calendar.month_name[gs.game.month],
                'score': str(gs.score),
                'rank': gs.rank,
                'knockouts': gs.knockouts,
                'notes': gs.game.notes or '',
            }
            for gs in scores
        ]
        return Response(data)


class HeadToHeadView(APIView):
    def get(self, request):
        p1_id = request.query_params.get('p1')
        p2_id = request.query_params.get('p2')

        if not p1_id or not p2_id:
            return Response(
                {'detail': 'Both p1 and p2 query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            p1 = Player.objects.get(pk=int(p1_id))
            p2 = Player.objects.get(pk=int(p2_id))
        except (Player.DoesNotExist, ValueError):
            return Response({'detail': 'One or both players not found.'}, status=status.HTTP_404_NOT_FOUND)

        p1_game_ids = set(GameScore.objects.filter(player=p1).values_list('game_id', flat=True))
        p2_game_ids = set(GameScore.objects.filter(player=p2).values_list('game_id', flat=True))
        shared_game_ids = p1_game_ids & p2_game_ids

        empty_response = {
            'player1': PlayerSerializer(p1).data,
            'player2': PlayerSerializer(p2).data,
            'shared_tournaments': 0,
            'player1_wins': 0, 'player2_wins': 0, 'ties': 0,
            'player1_avg_score': '0.00', 'player2_avg_score': '0.00',
            'player1_avg_rank': '—', 'player2_avg_rank': '—',
            'player1_total_ko': 0, 'player2_total_ko': 0,
        }
        if not shared_game_ids:
            return Response(empty_response)

        p1_scores = {gs.game_id: gs for gs in GameScore.objects.filter(player=p1, game_id__in=shared_game_ids)}
        p2_scores = {gs.game_id: gs for gs in GameScore.objects.filter(player=p2, game_id__in=shared_game_ids)}

        p1_wins = p2_wins = ties = 0
        p1_score_sum = p2_score_sum = Decimal('0')
        p1_ranks, p2_ranks = [], []
        p1_ko_total = p2_ko_total = 0

        for gid in shared_game_ids:
            gs1, gs2 = p1_scores[gid], p2_scores[gid]
            p1_score_sum += gs1.score
            p2_score_sum += gs2.score
            p1_ko_total += gs1.knockouts
            p2_ko_total += gs2.knockouts
            if gs1.rank is not None: p1_ranks.append(gs1.rank)
            if gs2.rank is not None: p2_ranks.append(gs2.rank)

            if gs1.rank is not None and gs2.rank is not None:
                if gs1.rank < gs2.rank: p1_wins += 1
                elif gs2.rank < gs1.rank: p2_wins += 1
                else: ties += 1
            else:
                if gs1.score > gs2.score: p1_wins += 1
                elif gs2.score > gs1.score: p2_wins += 1
                else: ties += 1

        n = len(shared_game_ids)
        return Response({
            'player1': PlayerSerializer(p1).data,
            'player2': PlayerSerializer(p2).data,
            'shared_tournaments': n,
            'player1_wins': p1_wins,
            'player2_wins': p2_wins,
            'ties': ties,
            'player1_avg_score': str(round(p1_score_sum / n, 2)),
            'player2_avg_score': str(round(p2_score_sum / n, 2)),
            'player1_avg_rank': str(round(sum(p1_ranks) / len(p1_ranks), 1)) if p1_ranks else '—',
            'player2_avg_rank': str(round(sum(p2_ranks) / len(p2_ranks), 1)) if p2_ranks else '—',
            'player1_total_ko': p1_ko_total,
            'player2_total_ko': p2_ko_total,
        })


class EventListView(APIView):
    def get(self, request):
        events = (
            PokerEvent.objects
            .prefetch_related('rsvps')  # related_name='rsvps'
            .order_by('event_date')
        )
        return Response(PokerEventSerializer(events, many=True, context={'request': request}).data)

    def post(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Staff only.'}, status=status.HTTP_403_FORBIDDEN)
        fields = ['title', 'event_date', 'end_time', 'location', 'description']
        data = {f: request.data[f] for f in fields if f in request.data}
        if 'title' not in data or 'event_date' not in data:
            return Response({'detail': 'title and event_date are required.'}, status=status.HTTP_400_BAD_REQUEST)
        event = PokerEvent.objects.create(**data)
        return Response(PokerEventSerializer(event).data, status=status.HTTP_201_CREATED)


class EventDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_event(self, pk):
        try:
            return PokerEvent.objects.prefetch_related('rsvps').get(pk=pk)
        except PokerEvent.DoesNotExist:
            return None

    def patch(self, request, pk):
        event = self._get_event(pk)
        if event is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        fields = ['title', 'event_date', 'end_time', 'location', 'description']
        for f in fields:
            if f in request.data:
                setattr(event, f, request.data[f])
        event.save()
        return Response(PokerEventSerializer(event).data)

    def delete(self, request, pk):
        event = self._get_event(pk)
        if event is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventRSVPView(APIView):
    """POST/DELETE /api/v1/events/{id}/rsvp/ — any authenticated user can RSVP."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            event = PokerEvent.objects.get(pk=pk)
        except PokerEvent.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if event.event_date < timezone.now():
            return Response({'detail': 'Cannot RSVP to a past event.'}, status=status.HTTP_400_BAD_REQUEST)
        response_val = request.data.get('response')
        if response_val not in ('yes', 'maybe', 'no'):
            return Response({'detail': 'response must be yes, maybe, or no.'}, status=status.HTTP_400_BAD_REQUEST)
        EventRSVP.objects.update_or_create(
            event=event,
            user_identifier=request.user.email,
            defaults={'response': response_val},
        )
        return Response({'response': response_val})

    def delete(self, request, pk):
        try:
            event = PokerEvent.objects.get(pk=pk)
        except PokerEvent.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        EventRSVP.objects.filter(
            event=event,
            user_identifier=request.user.email,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventRSVPListView(APIView):
    """GET /api/v1/events/{id}/rsvps/ — staff only, returns individual RSVPs with names."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, pk):
        try:
            event = PokerEvent.objects.get(pk=pk)
        except PokerEvent.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Build email→name map in one query
        rsvps = list(event.rsvps.all().order_by('user_identifier'))
        emails = [r.user_identifier for r in rsvps]
        user_map = {
            u.email: u.get_full_name()
            for u in User.objects.filter(email__in=emails)
        }

        return Response([
            {
                'id': r.id,
                'player_name': user_map.get(r.user_identifier, ''),
                'player_email': r.user_identifier,
                'response': r.response,
                'updated_at': r.updated_at.isoformat(),
            }
            for r in rsvps
        ])


class AnnouncementListView(APIView):
    def get(self, request):
        announcements = (
            Announcement.objects
            .filter(is_active=True)
            .order_by('-is_pinned', '-created_at')
        )
        return Response(AnnouncementSerializer(announcements, many=True).data)


class AppConfigView(APIView):
    """
    GET /api/v1/config/
    Returns league name and UI theme for initial app setup.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        theme = 'default'
        try:
            from .models import SiteSettings
            site = SiteSettings.objects.get(pk=1)
            theme = site.theme
        except Exception:
            pass

        return Response({
            'league_name': getattr(django_settings, 'LEAGUE_NAME', 'Poker League'),
            'theme': theme,
            'timezone': getattr(django_settings, 'LEAGUE_TIMEZONE', 'America/Phoenix'),
        })


class AdminSettingsView(APIView):
    """
    GET /api/v1/admin/settings/  — read current settings (staff only)
    PATCH /api/v1/admin/settings/ — update settings (staff only)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_site(self):
        from .models import SiteSettings
        site, _ = SiteSettings.objects.get_or_create(pk=1)
        return site

    def get(self, request):
        site = self._get_site()
        return Response({'theme': site.theme})

    def patch(self, request):
        site = self._get_site()
        if 'theme' in request.data:
            from .models import SiteSettings
            valid_themes = [t[0] for t in SiteSettings.THEME_CHOICES]
            if request.data['theme'] not in valid_themes:
                return Response({'detail': f'Invalid theme. Choose from: {valid_themes}'}, status=status.HTTP_400_BAD_REQUEST)
            site.theme = request.data['theme']
            site.save()
        return Response({'theme': site.theme})


class EmailLoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticate with email + password. Only emails in AllowedEmail can log in.
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password', '')

        if not email or not password:
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not AllowedEmail.objects.filter(email__iexact=email).exists():
            return Response({'detail': 'Email not in allowlist'}, status=status.HTTP_403_FORBIDDEN)

        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'email': user.email, 'is_staff': user.is_staff},
        })


class RegisterView(APIView):
    """
    POST /api/v1/auth/register/
    Self-registration. Creates a Django user but does NOT add to AllowedEmail.
    Account requires admin approval before login is possible.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError

        name = request.data.get('name', '').strip()
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password', '')

        errors = {}

        try:
            validate_email(email)
        except DjangoValidationError:
            errors['email'] = ['Enter a valid email address.']

        if len(password) < 8:
            errors['password'] = ['Password must be at least 8 characters.']

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=email).exists():
            return Response(
                {'email': ['A user with this email already exists.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User(username=email, email=email, first_name=name)
        user.set_password(password)
        user.save()

        return Response(
            {'message': 'Account created. A league admin will approve your access.'},
            status=status.HTTP_201_CREATED,
        )


class DeleteAccountView(APIView):
    """
    DELETE /api/v1/auth/account/
    Permanently delete the authenticated user's own account.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        EventRSVP.objects.filter(user_identifier=request.user.email).delete()
        AllowedEmail.objects.filter(email=request.user.email).delete()
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GoogleAuthView(APIView):
    """
    POST /api/v1/auth/google/
    Exchange a Google OAuth access token for a JWT pair.
    Only emails in AllowedEmail can authenticate.
    """
    permission_classes = [AllowAny]
    throttle_classes = [SocialAuthRateThrottle]

    def post(self, request):
        access_token = request.data.get('access_token')
        if not access_token:
            return Response({'detail': 'access_token required.'}, status=400)

        # Verify token + get user info from Google
        resp = http_requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=5,
        )
        if resp.status_code != 200:
            return Response({'detail': 'Invalid Google token.'}, status=401)

        userinfo = resp.json()
        email = userinfo.get('email', '').lower()

        first_name = userinfo.get('given_name', '')
        last_name = userinfo.get('family_name', '')

        # Check allowlist
        if not AllowedEmail.objects.filter(email__iexact=email).exists():
            # Save/update the user record so admins can review and approve
            user, _ = User.objects.get_or_create(
                username=email,
                defaults={'email': email, 'is_active': True},
            )
            update_fields = []
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                update_fields.append('first_name')
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                update_fields.append('last_name')
            if update_fields:
                user.save(update_fields=update_fields)
            return Response(
                {
                    'status': 'pending_approval',
                    'message': 'Your account is pending admin approval. You\'ll be able to sign in once approved.',
                },
                status=status.HTTP_202_ACCEPTED,
            )

        # Get or create Django user, always sync name from Google
        user, created = User.objects.get_or_create(
            username=email,
            defaults={'email': email, 'is_active': True},
        )
        if first_name or last_name:
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=['first_name', 'last_name'])

        # Issue JWT pair
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'email': email, 'is_staff': user.is_staff},
        })


# ─── Push Notifications ───────────────────────────────────────────────────────

class RegisterPushTokenView(APIView):
    """
    POST /api/v1/notifications/register-token/
    Body: { "token": "ExponentPushToken[...]", "platform": "ios" | "android" }
    Upserts the token for the authenticated user.
    Returns 201 on create, 200 on update.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PushTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        _, created = PushToken.objects.update_or_create(
            token=data['token'],
            defaults={'user': request.user, 'platform': data['platform']},
        )
        return Response(
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class UnregisterPushTokenView(APIView):
    """
    DELETE /api/v1/notifications/unregister-token/
    Body: { "token": "ExponentPushToken[...]" }
    Deletes the token if it belongs to the authenticated user. Idempotent.
    Returns 204.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        token = request.data.get('token', '')
        PushToken.objects.filter(token=token, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminPushView(APIView):
    """
    POST /api/v1/admin/push/
    Staff only. Send an ad-hoc push to a targeted audience.
    Body: { title, body, audience, event_id?, interactive_rsvp? }
    audience: all | internal_testers | event_yes | event_maybe_or_none | event_no
    interactive_rsvp: true only valid with audience=event_maybe_or_none + event_id
    Returns: { sent, skipped_no_token, failed }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    _AUDIENCES = ('all', 'internal_testers', 'event_yes', 'event_maybe_or_none', 'event_no')

    def post(self, request):
        title = request.data.get('title', '').strip()
        body = request.data.get('body', '').strip()
        audience = request.data.get('audience', '')
        event_id = request.data.get('event_id')
        interactive_rsvp = bool(request.data.get('interactive_rsvp', False))

        if not title or not body:
            return Response({'detail': 'title and body are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if audience not in self._AUDIENCES:
            return Response(
                {'detail': f'audience must be one of: {", ".join(self._AUDIENCES)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if audience.startswith('event_') and not event_id:
            return Response({'detail': 'event_id is required for event_* audiences.'}, status=status.HTTP_400_BAD_REQUEST)
        if interactive_rsvp and (audience not in ('event_maybe_or_none', 'internal_testers') or not event_id):
            return Response(
                {'detail': 'interactive_rsvp requires audience=event_maybe_or_none or internal_testers, plus event_id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_qs = PushToken.objects.select_related('user')

        if audience == 'internal_testers':
            token_qs = token_qs.filter(user__profile__is_internal_tester=True)
        elif audience.startswith('event_'):
            try:
                event = PokerEvent.objects.get(pk=event_id)
            except PokerEvent.DoesNotExist:
                return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)

            if audience == 'event_yes':
                emails = set(EventRSVP.objects.filter(event=event, response='yes').values_list('user_identifier', flat=True))
                token_qs = token_qs.filter(user__email__in=emails)
            elif audience == 'event_maybe_or_none':
                exclude_emails = set(
                    EventRSVP.objects
                    .filter(event=event, response__in=['yes', 'no'])
                    .values_list('user_identifier', flat=True)
                )
                token_qs = token_qs.exclude(user__email__in=exclude_emails)
            elif audience == 'event_no':
                emails = set(EventRSVP.objects.filter(event=event, response='no').values_list('user_identifier', flat=True))
                token_qs = token_qs.filter(user__email__in=emails)

        tokens = list(token_qs.values_list('token', flat=True))

        push_data = {'type': 'rsvp_prompt', 'event_id': int(event_id)} if interactive_rsvp else None
        category = 'rsvp_prompt' if interactive_rsvp else None
        result = send_expo_push(tokens, title=title, body=body, data=push_data, category_id=category)
        return Response({
            'sent': result['sent'],
            'skipped_no_token': result['skipped'],
            'failed': result['failed'],
        })


APPLE_BUNDLE_ID = 'com.glowstickdev.feltsync'


class AppleAuthView(APIView):
    """
    POST /api/v1/auth/apple/
    Exchange an Apple identity token for a JWT pair.
    Only emails in AllowedEmail can authenticate; others are saved for admin review.
    """
    permission_classes = [AllowAny]
    throttle_classes = [SocialAuthRateThrottle]

    def post(self, request):
        identity_token = request.data.get('identity_token')
        client_email = request.data.get('email')

        if not identity_token:
            return Response({'detail': 'identity_token is required.'}, status=400)

        try:
            keys = http_requests.get('https://appleid.apple.com/auth/keys', timeout=5).json()['keys']
            kid = jwt.get_unverified_header(identity_token).get('kid')
            key = next((k for k in keys if k['kid'] == kid), None)
            if not key:
                raise ValueError('No matching key')
            public_key = RSAAlgorithm.from_jwk(json.dumps(key))
            claims = jwt.decode(identity_token, public_key, algorithms=['RS256'], audience=APPLE_BUNDLE_ID)
        except Exception:
            return Response({'detail': 'Invalid Apple identity token.'}, status=400)

        email = (claims.get('email') or client_email or '').lower().strip()
        if not email:
            return Response({'detail': 'Email unavailable. Sign out on your device and try again.'}, status=400)

        user, created = User.objects.get_or_create(
            username__iexact=email,
            defaults={'username': email, 'email': email},
        )

        name = (request.data.get('name') or '').strip()
        parts = name.split(' ', 1) if name else []
        given = parts[0] if parts else ''
        family = parts[1] if len(parts) > 1 else ''
        if given and (created or not user.first_name):
            user.first_name = given
            user.last_name = family
            user.save(update_fields=['first_name', 'last_name'])

        if not AllowedEmail.objects.filter(email__iexact=email).exists():
            return Response(
                {'status': 'pending_approval', 'message': 'Your account is pending admin approval.'},
                status=202,
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'email': user.email, 'is_staff': user.is_staff},
        })


class ThrottledTokenRefreshView(TokenRefreshView):
    """POST /api/v1/auth/refresh/ — rate-limited token refresh."""
    throttle_classes = [RefreshRateThrottle]
