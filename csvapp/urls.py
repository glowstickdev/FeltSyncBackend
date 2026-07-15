from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("upload/", views.upload, name="upload"),
    path("upload/overall/", views.upload_overall, name="upload_overall"),
    path("results/<int:year>/<int:month>/", views.monthly_results, name="monthly_results"),
    path("results/<int:year>/<int:month>/delete/", views.delete_game, name="delete_game"),
    path("scores/<int:pk>/edit/", views.edit_score, name="edit_score"),
    path("leaderboard/<int:year>/", views.leaderboard, name="leaderboard"),
    path("leaderboard/<int:year>/chart/", views.season_chart, name="season_chart"),
    # Player profiles & comparison
    path("player/<int:pk>/", views.player_profile, name="player_profile"),
    path("compare/", views.head_to_head, name="head_to_head"),
    # High Hand
    path("highhand/<int:year>/edit/", views.highhand_edit, name="highhand_edit"),
    # Announcements
    path("announcements/", views.announcements, name="announcements"),
    path("announcements/new/", views.announcement_create, name="announcement_create"),
    path("announcements/<int:pk>/edit/", views.announcement_edit, name="announcement_edit"),
    path("announcements/<int:pk>/delete/", views.announcement_delete, name="announcement_delete"),
    # Events
    path("events/", views.events, name="events"),
    path("events/create/", views.event_create, name="event_create"),
    path("events/<int:pk>/edit/", views.event_edit, name="event_edit"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("events/<int:pk>/ics/", views.event_ics, name="event_ics"),
    path("events/<int:pk>/rsvp/", views.rsvp_event, name="rsvp_event"),
    path("events/<int:pk>/rsvps/", views.event_rsvp_list, name="event_rsvp_list"),
    # Site settings (admin)
    path("settings/", views.site_settings, name="site_settings"),
]
