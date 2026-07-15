from django.urls import path
from . import api_views

urlpatterns = [
    path('auth/login/', api_views.EmailLoginView.as_view()),
    path('auth/register/', api_views.RegisterView.as_view()),
    path('auth/account/', api_views.DeleteAccountView.as_view()),
    path('auth/apple/', api_views.AppleAuthView.as_view()),
    path('auth/google/', api_views.GoogleAuthView.as_view()),
    path('auth/refresh/', api_views.ThrottledTokenRefreshView.as_view()),
    path('config/', api_views.AppConfigView.as_view()),
    path('seasons/', api_views.SeasonsView.as_view()),
    path('seasons/<int:year>/leaderboard/', api_views.SeasonLeaderboardView.as_view()),
    path('results/<int:year>/<int:month>/', api_views.MonthlyResultView.as_view()),
    path('players/', api_views.PlayerListView.as_view()),
    path('players/compare/', api_views.HeadToHeadView.as_view()),  # must be before <int:pk>
    path('players/<int:pk>/', api_views.PlayerDetailView.as_view()),
    path('players/<int:pk>/games/', api_views.PlayerGamesView.as_view()),
    path('events/', api_views.EventListView.as_view()),
    path('events/<int:pk>/', api_views.EventDetailView.as_view()),
    path('events/<int:pk>/rsvp/', api_views.EventRSVPView.as_view()),
    path('events/<int:pk>/rsvps/', api_views.EventRSVPListView.as_view()),
    path('announcements/', api_views.AnnouncementListView.as_view()),
    path('admin/settings/', api_views.AdminSettingsView.as_view()),
    path('admin/push/', api_views.AdminPushView.as_view()),
    path('notifications/register-token/', api_views.RegisterPushTokenView.as_view()),
    path('notifications/unregister-token/', api_views.UnregisterPushTokenView.as_view()),
]
