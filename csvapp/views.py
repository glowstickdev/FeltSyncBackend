from django.conf import settings as django_settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from .models import (
    Player, MonthlyGame, GameScore, OverallStats, PlayerOverallStat,
    PokerEvent, Announcement, HighHand, EventRSVP, SiteSettings,
)
from .forms import UploadGameForm, UploadOverallForm, PokerEventForm, AnnouncementForm, HighHandForm, GameScoreEditForm
from .csv_handler import (
    validate_and_parse_csv,
    validate_and_parse_overall_csv,
    CSVValidationError,
)


def home(request):
    latest_year = (
        MonthlyGame.objects.values_list("year", flat=True)
        .order_by("-year")
        .first()
    )
    current_year = latest_year or timezone.now().year
    return redirect("leaderboard", year=current_year)


# ─────────────────────────────────────────────
# MONTHLY TOURNAMENT UPLOAD
# ─────────────────────────────────────────────
@login_required
def upload(request):
    if request.method == "POST":
        form = UploadGameForm(request.POST, request.FILES)
        if form.is_valid():
            month = int(form.cleaned_data["month"])
            year = form.cleaned_data["year"]
            csv_file = form.cleaned_data["csv_file"]
            notes = form.cleaned_data["notes"]
            overwrite = form.cleaned_data["overwrite"]
            if MonthlyGame.objects.filter(month=month, year=year).exists() and not overwrite:
                messages.error(
                    request,
                    f"Data for that month/year already exists. Check 'Overwrite' to replace it.",
                )
                return render(request, "csvapp/upload.html", {
                    "form": UploadGameForm(),
                    "upload_overall_form": UploadOverallForm(),
                })
            try:
                parsed_rows, warnings = validate_and_parse_csv(csv_file)
            except CSVValidationError as e:
                for err in e.errors:
                    messages.error(request, err)
                return render(request, "csvapp/upload.html", {
                    "form": UploadGameForm(),
                    "upload_overall_form": UploadOverallForm(),
                })
            for w in warnings:
                messages.warning(request, w)
            with transaction.atomic():
                MonthlyGame.objects.filter(month=month, year=year).delete()
                csv_file.seek(0)
                game = MonthlyGame.objects.create(
                    month=month,
                    year=year,
                    uploaded_file=csv_file,
                    notes=notes,
                )
                for row in parsed_rows:
                    player, _ = Player.objects.get_or_create(
                        name__iexact=row["player_name"],
                        defaults={"name": row["player_name"]},
                    )
                    GameScore.objects.create(
                        game=game,
                        player=player,
                        score=row["score"],
                        rank=row["rank"],
                        knockouts=row.get("knockouts", 0),
                    )
            messages.success(
                request,
                f"✓ {game.get_month_display()} {year} uploaded — {len(parsed_rows)} players.",
            )
            return redirect("leaderboard", year=year)
    else:
        form = UploadGameForm()
    return render(request, "csvapp/upload.html", {
        "form": form,
        "upload_overall_form": UploadOverallForm(),
    })


@login_required
def upload_overall(request):
    if request.method == "POST":
        form = UploadOverallForm(request.POST, request.FILES)
        if form.is_valid():
            year = form.cleaned_data["year"]
            csv_file = form.cleaned_data["csv_file"]
            overwrite = form.cleaned_data["overwrite"]
            if OverallStats.objects.filter(year=year).exists() and not overwrite:
                messages.error(
                    request,
                    f"Overall stats for {year} already exist. Check 'Overwrite' to replace it.",
                )
                return render(request, "csvapp/upload.html", {
                    "form": UploadGameForm(),
                    "upload_overall_form": form,
                    "overall_active": True,
                })
            try:
                parsed_rows, warnings = validate_and_parse_overall_csv(csv_file)
            except CSVValidationError as e:
                for err in e.errors:
                    messages.error(request, err)
                return render(request, "csvapp/upload.html", {
                    "form": UploadGameForm(),
                    "upload_overall_form": form,
                    "overall_active": True,
                })
            for w in warnings:
                messages.warning(request, w)
            with transaction.atomic():
                OverallStats.objects.filter(year=year).delete()
                csv_file.seek(0)
                overall = OverallStats.objects.create(
                    year=year,
                    uploaded_file=csv_file,
                )
                for row in parsed_rows:
                    player, _ = Player.objects.get_or_create(
                        name__iexact=row["player_name"],
                        defaults={"name": row["player_name"]},
                    )
                    PlayerOverallStat.objects.create(
                        overall=overall,
                        player=player,
                        games_played=row["games_played"],
                        eoy_pool=row["eoy_pool"],
                        total_knockouts=row["total_knockouts"],
                    )
            messages.success(
                request,
                f"✓ Overall stats for {year} uploaded — {len(parsed_rows)} players.",
            )
            return redirect("leaderboard", year=year)
    else:
        form = UploadOverallForm()
    return render(request, "csvapp/upload.html", {
        "form": UploadGameForm(),
        "upload_overall_form": form,
        "overall_active": True,
    })


# ─────────────────────────────────────────────
# LEADERBOARD
# ─────────────────────────────────────────────
def leaderboard(request, year):
    available_years = (
        MonthlyGame.objects.values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )
    if not available_years:
        available_years = [timezone.now().year]

    games_this_year = MonthlyGame.objects.filter(year=year).order_by("month")

    try:
        overall_stats = OverallStats.objects.filter(year=year).latest()
        overall_map = {
            ps.player_id: ps
            for ps in PlayerOverallStat.objects.filter(overall=overall_stats).select_related("player")
        }
        total_eoy_pool = sum(ps.eoy_pool for ps in overall_map.values())
        last_overall_upload = overall_stats.uploaded_at
    except OverallStats.DoesNotExist:
        overall_map = {}
        total_eoy_pool = 0
        last_overall_upload = None

    last_monthly_upload = (
        MonthlyGame.objects.filter(year=year)
        .order_by("-uploaded_at")
        .values_list("uploaded_at", flat=True)
        .first()
    )

    try:
        last_event_update = PokerEvent.objects.order_by("-updated_at").values_list("updated_at", flat=True).first()
    except Exception:
        last_event_update = None

    try:
        last_announcement_update = Announcement.objects.filter(is_active=True).order_by("-updated_at").values_list("updated_at", flat=True).first()
    except Exception:
        last_announcement_update = None

    try:
        last_highhand_update = HighHand.objects.filter(year=year).values_list("updated_at", flat=True).first()
    except Exception:
        last_highhand_update = None

    last_updated = max(
        filter(None, [last_overall_upload, last_monthly_upload, last_event_update, last_announcement_update, last_highhand_update]),
        default=None,
    )

    tournament_count = games_this_year.count()
    players = Player.objects.filter(scores__game__year=year).distinct()

    leaderboard_data = []
    for player in players:
        all_scores_qs = (
            GameScore.objects.filter(player=player, game__year=year)
            .order_by("-score")
            .select_related("game")
        )
        all_scores = list(all_scores_qs)
        _top_n = django_settings.SCORING_TOP_N if year >= django_settings.SCORING_TOP_N_FROM_YEAR else len(all_scores)
        top5 = all_scores[:_top_n]
        top5_total = sum(gs.score for gs in top5)
        top5_values = [gs.score for gs in top5]
        individual_scores = [
            {"month": gs.game.get_month_display(), "score": gs.score}
            for gs in all_scores
        ]
        # Chronological scores for sparkline (ordered by month, not score)
        monthly_scores = [
            {"month": gs.game.month, "score": float(gs.score)}
            for gs in sorted(all_scores, key=lambda x: x.game.month)
        ]
        monthly_ko = sum(gs.knockouts for gs in all_scores)
        april_ko = sum(
            gs.knockouts for gs in all_scores
            if gs.game.month >= django_settings.KNOCKOUT_START_MONTH
        )
        ps = overall_map.get(player.id)
        games_played = ps.games_played if ps else len(all_scores)
        eoy_pool = ps.eoy_pool if ps else 0
        total_ko = ps.total_knockouts if ps else monthly_ko
        leaderboard_data.append({
            "player": player,
            "top5_scores": top5_values,
            "top5_total": round(top5_total, 2),
            "games_played": games_played,
            "individual_scores": individual_scores,
            "monthly_scores": monthly_scores,
            "eoy_pool": eoy_pool,
            "total_ko": total_ko,
            "april_kos": april_ko,
        })

    leaderboard_data.sort(key=lambda x: x["top5_total"], reverse=True)
    for i, entry in enumerate(leaderboard_data, start=1):
        entry["rank"] = i

    ko_sort_key = "april_kos" if year >= django_settings.SCORING_TOP_N_FROM_YEAR else "total_ko"
    knockout_leaders = sorted(leaderboard_data, key=lambda x: x[ko_sort_key], reverse=True)
    upcoming_events = PokerEvent.objects.filter(event_date__gte=timezone.now()).order_by("event_date")[:3]

    try:
        high_hand = HighHand.objects.get(year=year)
    except HighHand.DoesNotExist:
        high_hand = None

    pinned_announcements = Announcement.objects.filter(is_active=True, is_pinned=True)[:3]

    return render(request, "csvapp/leaderboard.html", {
        "leaderboard": leaderboard_data,
        "knockout_leaders": knockout_leaders,
        "year": year,
        "available_years": available_years,
        "games_this_year": games_this_year,
        "total_eoy_pool": total_eoy_pool,
        "tournament_count": tournament_count,
        "player_count": len(leaderboard_data),
        "last_updated": last_updated,
        "upcoming_events": upcoming_events,
        "high_hand": high_hand,
        "pinned_announcements": pinned_announcements,
    })


# ─────────────────────────────────────────────
# MONTHLY RESULTS
# ─────────────────────────────────────────────
def monthly_results(request, month, year):
    game = get_object_or_404(MonthlyGame, month=month, year=year)
    scores = (
        GameScore.objects.filter(game=game)
        .select_related("player")
        .order_by("rank", "-score")
    )
    all_games = MonthlyGame.objects.filter(year=year).order_by("month")
    return render(request, "csvapp/monthly_results.html", {
        "game": game,
        "scores": scores,
        "all_games": all_games,
        "year": year,
    })


# ─────────────────────────────────────────────
# EDIT SCORE
# ─────────────────────────────────────────────
@login_required
def edit_score(request, pk):
    gs = get_object_or_404(GameScore.objects.select_related("game", "player"), pk=pk)
    if request.method == "POST":
        form = GameScoreEditForm(request.POST, instance=gs)
        if form.is_valid():
            form.save()
            messages.success(request, f"✓ {gs.player.name}'s score updated.")
            return redirect("monthly_results", month=gs.game.month, year=gs.game.year)
    else:
        form = GameScoreEditForm(instance=gs)
    return render(request, "csvapp/score_edit_form.html", {
        "form": form,
        "gs": gs,
    })


# ─────────────────────────────────────────────
# DELETE GAME
# ─────────────────────────────────────────────
@login_required
def delete_game(request, month, year):
    game = get_object_or_404(MonthlyGame, month=month, year=year)
    if request.method == "POST":
        game_str = str(game)
        game.delete()
        messages.success(request, f"Deleted all data for {game_str}.")
        return redirect("leaderboard", year=year)
    return render(request, "csvapp/confirm_delete.html", {"game": game})


# ─────────────────────────────────────────────
# HIGH HAND
# ─────────────────────────────────────────────
@login_required
def highhand_edit(request, year):
    """Create or update the High Hand record for the given year."""
    instance, _ = HighHand.objects.get_or_create(
        year=year,
        defaults={
            "player_name": "",
            "hand_type": "high_card",
            "card1": "As", "card2": "Ks", "card3": "Qs", "card4": "Js", "card5": "Ts",
        },
    )
    if request.method == "POST":
        form = HighHandForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"✓ High Hand updated for {year}.")
            return redirect("leaderboard", year=year)
    else:
        form = HighHandForm(instance=instance)
    return render(request, "csvapp/highhand_form.html", {
        "form": form,
        "year": year,
        "high_hand": instance,
    })


# ─────────────────────────────────────────────
# ANNOUNCEMENTS
# ─────────────────────────────────────────────
def announcements(request):
    active_announcements = Announcement.objects.filter(is_active=True)
    return render(request, "csvapp/announcements.html", {
        "announcements": active_announcements,
    })


@login_required
def announcement_create(request):
    if request.method == "POST":
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✓ Announcement published.")
            return redirect("announcements")
    else:
        form = AnnouncementForm(initial={"is_active": True})
    return render(request, "csvapp/announcement_form.html", {"form": form, "action": "New"})


@login_required
def announcement_edit(request, pk):
    ann = get_object_or_404(Announcement, pk=pk)
    if request.method == "POST":
        form = AnnouncementForm(request.POST, instance=ann)
        if form.is_valid():
            form.save()
            messages.success(request, "✓ Announcement updated.")
            return redirect("announcements")
    else:
        form = AnnouncementForm(instance=ann)
    return render(request, "csvapp/announcement_form.html", {"form": form, "action": "Edit", "announcement": ann})


@login_required
def announcement_delete(request, pk):
    ann = get_object_or_404(Announcement, pk=pk)
    if request.method == "POST":
        ann.delete()
        messages.success(request, "Announcement deleted.")
        return redirect("announcements")
    return render(request, "csvapp/announcement_confirm_delete.html", {"announcement": ann})


# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────
def events(request):
    from django.db.models import Count, Q
    upcoming = PokerEvent.objects.filter(event_date__gte=timezone.now()).order_by("event_date").annotate(
        yes_count=Count('rsvps', filter=Q(rsvps__response='yes')),
        maybe_count=Count('rsvps', filter=Q(rsvps__response='maybe')),
    )
    past = PokerEvent.objects.filter(event_date__lt=timezone.now()).order_by("-event_date")[:5]

    user_rsvp_yes = set()
    user_rsvp_maybe = set()
    user_rsvp_no = set()
    member = _is_member(request)
    if member:
        uid = _get_user_identifier(request)
        for rsvp in EventRSVP.objects.filter(event__in=upcoming, user_identifier=uid):
            if rsvp.response == 'yes':
                user_rsvp_yes.add(rsvp.event_id)
            elif rsvp.response == 'maybe':
                user_rsvp_maybe.add(rsvp.event_id)
            else:
                user_rsvp_no.add(rsvp.event_id)

    return render(request, "csvapp/events.html", {
        "upcoming": upcoming,
        "past": past,
        "is_member": member,
        "user_rsvp_yes": user_rsvp_yes,
        "user_rsvp_maybe": user_rsvp_maybe,
        "user_rsvp_no": user_rsvp_no,
    })


def _get_user_identifier(request):
    """Return a stable string identifier for the authenticated user."""
    cf_email = request.META.get('HTTP_CF_ACCESS_AUTHENTICATED_USER_EMAIL')
    if cf_email:
        return cf_email
    if request.user.email:
        return request.user.email
    return request.user.get_username()


def _is_member(request):
    """True if the user is authenticated via Cloudflare Access or Django."""
    return bool(request.META.get('HTTP_CF_ACCESS_AUTHENTICATED_USER_EMAIL')) or request.user.is_authenticated


def rsvp_event(request, pk):
    if request.method != "POST":
        return redirect("events")
    if not _is_member(request):
        messages.error(request, "You must be logged in to RSVP.")
        return redirect("events")
    event = get_object_or_404(PokerEvent, pk=pk)
    if event.event_date < timezone.now():
        messages.error(request, "Cannot RSVP to a past event.")
        return redirect("events")
    response = request.POST.get("response")
    if response not in ("yes", "maybe", "no"):
        messages.error(request, "Invalid RSVP response.")
        return redirect("events")
    uid = _get_user_identifier(request)
    EventRSVP.objects.update_or_create(
        event=event,
        user_identifier=uid,
        defaults={"response": response},
    )
    return redirect("events")


@login_required
def event_rsvp_list(request, pk):
    event = get_object_or_404(PokerEvent, pk=pk)
    rsvps = EventRSVP.objects.filter(event=event).order_by("response", "user_identifier")
    counts = {"yes": 0, "maybe": 0, "no": 0}
    for r in rsvps:
        counts[r.response] += 1
    return render(request, "csvapp/event_rsvp_list.html", {
        "event": event,
        "rsvps": rsvps,
        "counts": counts,
    })


@login_required
def event_create(request):
    if request.method == "POST":
        form = PokerEventForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✓ Event created.")
            return redirect("events")
    else:
        form = PokerEventForm()
    return render(request, "csvapp/event_form.html", {"form": form, "action": "Create"})


@login_required
def event_edit(request, pk):
    event = get_object_or_404(PokerEvent, pk=pk)
    if request.method == "POST":
        form = PokerEventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "✓ Event updated.")
            return redirect("events")
    else:
        form = PokerEventForm(instance=event)
    return render(request, "csvapp/event_form.html", {"form": form, "action": "Edit", "event": event})


@login_required
def event_delete(request, pk):
    event = get_object_or_404(PokerEvent, pk=pk)
    if request.method == "POST":
        event.delete()
        messages.success(request, "Event deleted.")
        return redirect("events")
    return render(request, "csvapp/event_confirm_delete.html", {"event": event})


def event_ics(request, pk):
    """Download .ics file for Apple Calendar, Google Calendar, and any calendar app.

    Times are emitted in UTC (Z suffix) rather than using a VTIMEZONE block.
    Google Calendar ignores inline VTIMEZONE definitions and only reliably
    handles UTC or its own timezone database — UTC is the safest common format.
    iOS Calendar handles UTC correctly too.
    """
    event = get_object_or_404(PokerEvent, pk=pk)

    import pytz
    from datetime import timedelta

    arizona_tz = pytz.timezone('America/Phoenix')
    utc_tz = pytz.utc

    if event.event_date.tzinfo is None:
        event_dt = arizona_tz.localize(event.event_date)
    else:
        event_dt = event.event_date.astimezone(arizona_tz)

    if event.end_time:
        if event.end_time.tzinfo is None:
            end_dt = arizona_tz.localize(event.end_time)
        else:
            end_dt = event.end_time.astimezone(arizona_tz)
    else:
        end_dt = event_dt + timedelta(hours=4)

    def fmt_utc(dt):
        return dt.astimezone(utc_tz).strftime("%Y%m%dT%H%M%SZ")

    description = event.description.replace("\n", "\\n").replace(",", "\\,") if event.description else ""
    location = event.location.replace(",", "\\,") if event.location else ""
    title = event.title.replace(",", "\\,")

    # Emit all times in UTC (Z suffix). Google Calendar and iOS both handle
    # UTC correctly. TZID-based approaches fail because Google Calendar
    # ignores the TZID parameter and treats the raw value as UTC anyway.
    # RFC 5545 requires CRLF line endings.
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{getattr(django_settings, 'LEAGUE_NAME', 'Poker League')}//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:poker-event-{event.pk}@pokerleague",
        f"DTSTAMP:{fmt_utc(timezone.now())}",
        f"DTSTART:{fmt_utc(event_dt)}",
        f"DTEND:{fmt_utc(end_dt)}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{location}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    ics_content = "\r\n".join(ics_lines) + "\r\n"

    response = HttpResponse(ics_content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="poker-event-{event.pk}.ics"'
    return response


# ─────────────────────────────────────────────
# SEASON CHART
# ─────────────────────────────────────────────
def season_chart(request, year):
    import json as _json

    games = MonthlyGame.objects.filter(year=year).order_by("month")
    if not games.exists():
        return redirect("leaderboard", year=year)

    month_list = [g.month for g in games]
    month_labels = [g.get_month_display() for g in games]

    players = Player.objects.filter(scores__game__year=year).distinct().order_by("name")

    score_map = {}
    for gs in GameScore.objects.filter(game__year=year).select_related("game"):
        score_map.setdefault(gs.player_id, {})[gs.game.month] = float(gs.score)

    player_datasets = []
    for player in players:
        player_months = score_map.get(player.id, {})
        player_datasets.append({
            "name": player.name,
            "data": [player_months.get(m) for m in month_list],
        })

    available_years = (
        MonthlyGame.objects.values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )

    return render(request, "csvapp/season_chart.html", {
        "year": year,
        "available_years": available_years,
        "month_labels_json": _json.dumps(month_labels),
        "player_datasets_json": _json.dumps(player_datasets),
        "games_this_year": games,
    })


# ─────────────────────────────────────────────
# HEAD-TO-HEAD COMPARISON
# ─────────────────────────────────────────────
def head_to_head(request):
    players = Player.objects.order_by("name")
    p1_id = request.GET.get("p1")
    p2_id = request.GET.get("p2")
    p1 = p2 = comparison = None

    if p1_id and p2_id and p1_id != p2_id:
        p1 = get_object_or_404(Player, pk=p1_id)
        p2 = get_object_or_404(Player, pk=p2_id)

        p1_game_ids = set(GameScore.objects.filter(player=p1).values_list("game_id", flat=True))
        p2_game_ids = set(GameScore.objects.filter(player=p2).values_list("game_id", flat=True))
        shared_game_ids = p1_game_ids & p2_game_ids

        if shared_game_ids:
            shared_games = MonthlyGame.objects.filter(pk__in=shared_game_ids).order_by("year", "month")
            p1_scores = {gs.game_id: gs for gs in GameScore.objects.filter(player=p1, game_id__in=shared_game_ids)}
            p2_scores = {gs.game_id: gs for gs in GameScore.objects.filter(player=p2, game_id__in=shared_game_ids)}

            rows = []
            p1_wins = p2_wins = ties = 0
            p1_score_sum = p2_score_sum = 0
            p1_rank_sum = p2_rank_sum = 0
            p1_ko_sum = p2_ko_sum = 0

            for game in shared_games:
                gs1 = p1_scores[game.pk]
                gs2 = p2_scores[game.pk]
                p1_score_sum += gs1.score
                p2_score_sum += gs2.score
                p1_rank_sum += gs1.rank
                p2_rank_sum += gs2.rank
                p1_ko_sum += gs1.knockouts
                p2_ko_sum += gs2.knockouts
                if gs1.rank < gs2.rank:
                    winner = "p1"
                    p1_wins += 1
                elif gs2.rank < gs1.rank:
                    winner = "p2"
                    p2_wins += 1
                else:
                    winner = "tie"
                    ties += 1
                rows.append({"game": game, "gs1": gs1, "gs2": gs2, "winner": winner})

            n = len(rows)
            comparison = {
                "rows": rows,
                "games_count": n,
                "p1_wins": p1_wins,
                "p2_wins": p2_wins,
                "ties": ties,
                "p1_avg_score": round(p1_score_sum / n, 2),
                "p2_avg_score": round(p2_score_sum / n, 2),
                "p1_avg_rank": round(p1_rank_sum / n, 1),
                "p2_avg_rank": round(p2_rank_sum / n, 1),
                "p1_total_ko": p1_ko_sum,
                "p2_total_ko": p2_ko_sum,
            }

    return render(request, "csvapp/head_to_head.html", {
        "players": players,
        "p1": p1,
        "p2": p2,
        "p1_id": p1_id,
        "p2_id": p2_id,
        "comparison": comparison,
    })


# ─────────────────────────────────────────────
# PLAYER PROFILE
# ─────────────────────────────────────────────
def player_profile(request, pk):
    player = get_object_or_404(Player, pk=pk)

    # All scores across all years, ordered chronologically
    all_scores = (
        GameScore.objects.filter(player=player)
        .select_related("game")
        .order_by("game__year", "game__month")
    )

    # Group scores by year
    from collections import defaultdict
    scores_by_year = defaultdict(list)
    for gs in all_scores:
        scores_by_year[gs.game.year].append(gs)

    # Build per-year summary
    top_n_cutoff = django_settings.SCORING_TOP_N_FROM_YEAR
    top_n = django_settings.SCORING_TOP_N
    year_summaries = []
    for year in sorted(scores_by_year.keys(), reverse=True):
        year_scores = scores_by_year[year]
        if year >= top_n_cutoff:
            sorted_scores = sorted(year_scores, key=lambda x: x.score, reverse=True)
            counting_scores = sorted_scores[:top_n]
            season_total = round(sum(gs.score for gs in counting_scores), 2)
            scoring_note = f"Top {top_n} scores"
        else:
            season_total = round(sum(gs.score for gs in year_scores), 2)
            scoring_note = "Total points"

        total_ko = sum(gs.knockouts for gs in year_scores)

        # Current season rank
        season_rank = None
        if year >= top_n_cutoff:
            all_players = Player.objects.filter(scores__game__year=year).distinct()
            player_totals = []
            for p in all_players:
                p_scores = sorted(
                    GameScore.objects.filter(player=p, game__year=year).values_list("score", flat=True),
                    reverse=True
                )
                player_totals.append((p.pk, round(sum(p_scores[:top_n]), 2)))
            player_totals.sort(key=lambda x: x[1], reverse=True)
            for i, (pid, _) in enumerate(player_totals, start=1):
                if pid == player.pk:
                    season_rank = i
                    break

        year_summaries.append({
            "year": year,
            "scores": year_scores,
            "season_total": season_total,
            "scoring_note": scoring_note,
            "total_ko": total_ko,
            "games_played": len(year_scores),
            "season_rank": season_rank,
        })

    # Lifetime totals
    lifetime_ko = sum(gs.knockouts for gs in all_scores)
    lifetime_games = all_scores.count()
    seasons_played = len(scores_by_year)

    return render(request, "csvapp/player_profile.html", {
        "player": player,
        "year_summaries": year_summaries,
        "lifetime_ko": lifetime_ko,
        "lifetime_games": lifetime_games,
        "seasons_played": seasons_played,
    })


# ─────────────────────────────────────────────
# SITE SETTINGS (admin)
# ─────────────────────────────────────────────
@login_required
def site_settings(request):
    settings_obj = SiteSettings.get()
    if request.method == "POST":
        theme = request.POST.get("theme")
        if theme in dict(SiteSettings.THEME_CHOICES):
            settings_obj.theme = theme
            settings_obj.save()
            messages.success(request, f"✓ Theme switched to {settings_obj.get_theme_display()}.")
        return redirect("site_settings")
    return render(request, "csvapp/site_settings.html", {
        "settings": settings_obj,
        "theme_choices": SiteSettings.THEME_CHOICES,
    })
