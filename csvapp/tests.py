from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .api_views import _build_standings
from .models import AllowedEmail, GameScore, MonthlyGame, Player, PokerEvent, UserProfile


# ─── Scoring ──────────────────────────────────────────────────────────────────

@override_settings(SCORING_TOP_N=5, SCORING_TOP_N_FROM_YEAR=2026, KNOCKOUT_START_MONTH=4)
class StandingsTests(TestCase):
    def add_scores(self, year, player, scores, knockouts=None):
        for i, score in enumerate(scores):
            month = i + 1
            game, _ = MonthlyGame.objects.get_or_create(
                year=year, month=month, defaults={'uploaded_file': f'test-{year}-{month}.csv'},
            )
            GameScore.objects.create(
                game=game, player=player, score=Decimal(score),
                knockouts=(knockouts or {}).get(month, 0),
            )

    def entry(self, standings, player):
        return next(e for e in standings if e['player'] == player)

    def test_top_five_scores_count_from_cutoff_year(self):
        p = Player.objects.create(name='Ace')
        self.add_scores(2026, p, [10, 50, 20, 40, 30, 60, 5])
        e = self.entry(_build_standings(2026), p)
        self.assertEqual(e['top5_total'], Decimal('200'))
        self.assertEqual(e['top5_scores'], [60.0, 50.0, 40.0, 30.0, 20.0])
        self.assertEqual(e['games_played'], 7)

    def test_all_scores_count_before_cutoff_year(self):
        p = Player.objects.create(name='Ace')
        self.add_scores(2025, p, [10, 50, 20, 40, 30, 60, 5])
        e = self.entry(_build_standings(2025), p)
        self.assertEqual(e['top5_total'], Decimal('215'))
        self.assertEqual(len(e['top5_scores']), 7)

    def test_tied_totals_share_rank_and_next_rank_skips(self):
        a, b, c, d = (Player.objects.create(name=n) for n in ('Alpha', 'Bravo', 'Charlie', 'Delta'))
        self.add_scores(2026, a, [100])
        self.add_scores(2026, b, [100])
        self.add_scores(2026, c, [80])
        self.add_scores(2026, d, [60])
        standings = _build_standings(2026)
        self.assertEqual([e['rank'] for e in standings], [1, 1, 3, 4])
        # Ties are listed alphabetically
        self.assertEqual([e['player'].name for e in standings[:2]], ['Alpha', 'Bravo'])

    def test_knockouts_split_by_start_month(self):
        p = Player.objects.create(name='Ace')
        self.add_scores(2026, p, [1, 1, 1, 1, 1], knockouts={1: 2, 3: 1, 4: 3, 5: 4})
        e = self.entry(_build_standings(2026), p)
        self.assertEqual(e['total_knockouts'], 10)
        self.assertEqual(e['april_knockouts'], 7)


# ─── Google sign-in ───────────────────────────────────────────────────────────

def _response(status_code, payload):
    resp = mock.Mock(status_code=status_code)
    resp.json.return_value = payload
    return resp


@override_settings(GOOGLE_CLIENT_IDS=['our-client'])
class GoogleAuthTests(TestCase):
    url = '/api/v1/auth/google/'

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        AllowedEmail.objects.create(email='player@example.com')

    def post(self, tokeninfo, userinfo=None):
        def fake_get(url, **kwargs):
            if 'tokeninfo' in url:
                return _response(200, tokeninfo)
            return _response(200, userinfo or {'given_name': 'Pat'})
        with mock.patch('csvapp.api_views.http_requests.get', side_effect=fake_get):
            return self.client.post(self.url, {'access_token': 't'}, format='json')

    def test_accepts_token_from_our_client(self):
        resp = self.post({'aud': 'our-client', 'email': 'player@example.com', 'email_verified': 'true'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('refresh', resp.data)

    def test_rejects_token_from_another_app(self):
        resp = self.post({'aud': 'other-app', 'azp': 'other-app', 'email': 'player@example.com', 'email_verified': 'true'})
        self.assertEqual(resp.status_code, 401)

    def test_rejects_unverified_email(self):
        resp = self.post({'aud': 'our-client', 'email': 'player@example.com', 'email_verified': 'false'})
        self.assertEqual(resp.status_code, 401)

    def test_email_comes_from_tokeninfo_not_userinfo(self):
        resp = self.post(
            {'aud': 'our-client', 'email': 'stranger@example.com', 'email_verified': 'true'},
            userinfo={'email': 'player@example.com'},
        )
        self.assertEqual(resp.status_code, 202)

    @override_settings(GOOGLE_CLIENT_IDS=[])
    def test_refuses_when_client_ids_not_configured(self):
        resp = self.post({'aud': 'our-client', 'email': 'player@example.com', 'email_verified': 'true'})
        self.assertEqual(resp.status_code, 503)


# ─── Apple sign-in ────────────────────────────────────────────────────────────

class AppleAuthTests(TestCase):
    url = '/api/v1/auth/apple/'

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        AllowedEmail.objects.create(email='player@example.com')
        AllowedEmail.objects.create(email='admin@example.com')

    def post(self, claims, **extra):
        keys = _response(200, {'keys': [{'kid': 'k'}]})
        with mock.patch('csvapp.api_views.http_requests.get', return_value=keys), \
                mock.patch('csvapp.api_views.jwt.get_unverified_header', return_value={'kid': 'k'}), \
                mock.patch('csvapp.api_views.RSAAlgorithm.from_jwk'), \
                mock.patch('csvapp.api_views.jwt.decode', return_value=claims):
            return self.client.post(self.url, {'identity_token': 't', **extra}, format='json')

    def test_ignores_client_supplied_email(self):
        resp = self.post({'sub': 'apple-1'}, email='admin@example.com')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(User.objects.filter(username='admin@example.com').exists())

    def test_links_sub_and_matches_on_it_later(self):
        resp = self.post({'sub': 'apple-1', 'email': 'player@example.com'})
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(username='player@example.com')
        self.assertEqual(user.profile.apple_sub, 'apple-1')

        # Later tokens may omit the email claim
        resp = self.post({'sub': 'apple-1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['user']['email'], 'player@example.com')

    def test_rejects_email_already_linked_to_another_apple_id(self):
        user = User.objects.create(username='player@example.com', email='player@example.com')
        UserProfile.objects.filter(user=user).update(apple_sub='apple-1')
        resp = self.post({'sub': 'apple-2', 'email': 'player@example.com'})
        self.assertEqual(resp.status_code, 400)


# ─── Events ───────────────────────────────────────────────────────────────────

class EventApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create(username='staff@example.com', email='staff@example.com', is_staff=True)
        self.member = User.objects.create(username='member@example.com', email='member@example.com')

    def test_create_with_bad_date_returns_400(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post('/api/v1/events/', {'title': 'Game', 'event_date': 'not a date'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('event_date', resp.data)

    def test_create_requires_title_and_date(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post('/api/v1/events/', {'location': 'Somewhere'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_staff_can_create(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(
            '/api/v1/events/', {'title': 'Game', 'event_date': '2026-11-01T18:00:00-07:00'}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(PokerEvent.objects.filter(title='Game').exists())

    def test_non_staff_cannot_create_but_can_list(self):
        self.client.force_authenticate(self.member)
        resp = self.client.post(
            '/api/v1/events/', {'title': 'Game', 'event_date': '2026-11-01T18:00:00-07:00'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.client.get('/api/v1/events/').status_code, 200)

    def test_patch_with_bad_date_returns_400(self):
        event = PokerEvent.objects.create(title='Game', event_date='2026-11-01T18:00:00-07:00')
        self.client.force_authenticate(self.staff)
        resp = self.client.patch(f'/api/v1/events/{event.pk}/', {'event_date': 'nope'}, format='json')
        self.assertEqual(resp.status_code, 400)
