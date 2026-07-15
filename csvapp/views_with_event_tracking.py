from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from .models import Player, MonthlyGame, GameScore, OverallStats, PlayerOverallStat, PokerEvent
from .forms import UploadGameForm, UploadOverallForm, PokerEventForm
from .csv_handler import (
    validate_and_parse_csv,
    validate_and_parse_overall_csv,
    CSVValidationError,
)
def home(request):
    current_year = timezone.now().year
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
                    "form": form,
                    "upload_overall_form": UploadOverallForm(),
                })
            try:
                parsed_rows, warnings = validate_and_parse_csv(csv_file)
            except CSVValidationError as e:
                for err in e.errors:
                    messages.error(request, err)
                return render(request, "csvapp/upload.html", {
                    "form": form,
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
                        knockouts=row.get("knockouts", 0),
                    )
                scores = GameScore.objects.filter(game=game).order_by("-score")
                for rank, gs in enumerate(scores, start=1):
                    gs.rank = rank
                    gs.save(update_fields=["rank"])
            messages.success(
                request,
                f"✓ Uploaded {len(parsed_rows)} scores for {game}.",
            )
            return redirect("monthly_results", month=month, year=year)
    else:
        now = timezone.now()
        form = UploadGameForm(initial={"month": now.month, "year": now.year})
    return render(request, "csvapp/upload.html", {
        "form": form,
        "upload_overall_form": UploadOverallForm(),
    })
# ─────────────────────────────────────────────
# OVERALL / YTD UPLOAD
# ─────────────────────────────────────────────
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
                    f"Overall stats for {year} already exist. Check 'Overwrite' to replace.",
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
        MonthlyGame.objects.filter(year=year).order_by("-uploaded_at").values_list("uploaded_at", flat=True).first()
    )
    
    # Check for most recent event modification (if updated_at field exists)
    try:
        last_event_update = PokerEvent.objects.order_by("-updated_at").values_list("updated_at", flat=True).first()
    except:
        last_event_update = None
    
    # Use the most recent timestamp from any activity
    last_updated = max(filter(None, [last_overall_upload, last_monthly_upload, last_event_update]), default=None)
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
        top5 = all_scores[:5]
        top5_total = sum(gs.score for gs in top5)
        top5_values = [gs.score for gs in top5]
        individual_scores = [
            {"month": gs.game.get_month_display(), "score": gs.score}
            for gs in all_scores
        ]
        monthly_ko = sum(gs.knockouts for gs in all_scores)
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
            "eoy_pool": eoy_pool,
            "total_ko": total_ko,
        })
    leaderboard_data.sort(key=lambda x: x["top5_total"], reverse=True)
    for i, entry in enumerate(leaderboard_data, start=1):
        entry["rank"] = i

    # Create separate knockout leaders list sorted by total_ko
    knockout_leaders = sorted(leaderboard_data, key=lambda x: x["total_ko"], reverse=True)

    # Upcoming events for the sidebar/section on leaderboard
    upcoming_events = PokerEvent.objects.filter(event_date__gte=timezone.now()).order_by("event_date")[:3]

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
# EVENTS
# ─────────────────────────────────────────────
def events(request):
    upcoming = PokerEvent.objects.filter(event_date__gte=timezone.now()).order_by("event_date")
    past = PokerEvent.objects.filter(event_date__lt=timezone.now()).order_by("-event_date")[:5]
    return render(request, "csvapp/events.html", {
        "upcoming": upcoming,
        "past": past,
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
    """Download .ics file for Apple Calendar / any calendar app."""
    event = get_object_or_404(PokerEvent, pk=pk)
    # Format datetimes in UTC for ICS (RFC 5545)
    from datetime import timezone as dt_tz
    dt_start = event.event_date.astimezone(dt_tz.utc)
    # Default duration: 4 hours
    from datetime import timedelta
    dt_end = dt_start + timedelta(hours=4)
    def ics_dt(dt):
        return dt.strftime("%Y%m%dT%H%M%SZ")
    description = event.description.replace("\n", "\\n").replace(",", "\\,") if event.description else ""
    location = event.location.replace(",", "\\,") if event.location else ""
    title = event.title.replace(",", "\\,")
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Poker League//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{event.pk}@pokertucson.com
DTSTAMP:{ics_dt(timezone.now())}
DTSTART:{ics_dt(dt_start)}
DTEND:{ics_dt(dt_end)}
SUMMARY:{title}
DESCRIPTION:{description}
LOCATION:{location}
END:VEVENT
END:VCALENDAR"""
    response = HttpResponse(ics_content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="poker-event-{event.pk}.ics"'
    return response
