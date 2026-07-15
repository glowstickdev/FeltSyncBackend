from django.conf import settings


def league(request):
    return {
        'league_name': getattr(settings, 'LEAGUE_NAME', 'My Poker League'),
    }
