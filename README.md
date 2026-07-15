# Poker League App Backend

A self-hosted Django backend for managing a private poker league. Tracks season standings, monthly tournament results, knockouts, events, announcements, and end-of-year prize pools. Pairs with the PokerLeagueApp web and iOS mobile frontend. Android support is planned for a future release.

>**Heads up:** This was built as a personal pet project with the help of AI and was never intended for public use. That said, if you're running a private league with [The Tournament Director](https://www.thetournamentdirector.net/) and want to give your players a polished way to view standings and stats throughout the season, this might be exactly what you're looking for.

---

## Features

- Season leaderboard — year-to-date standings, top 5 scores per player (2026+)
- Monthly results — per-tournament import via CSV export from Tournament Director 3.7.2
- Knockout leaderboard — April-onwards KO tracking for the current season
- End-of-year prize pool — totals from overall stats upload
- High Hand of the Year — current holder with full card visualization
- Events — upcoming tournament calendar with ICS export
- Announcements — pinnable club news
- Multi-year history — season picker for historical standings
- REST API — mobile app backend at `/api/v1/`
- Two UI themes — default dark poker and glassmorphism

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.1, Python 3.12 |
| Database | PostgreSQL 15 |
| Web server | Gunicorn + WhiteNoise |
| Container | Docker Compose |
| API auth | JWT (SimpleJWT) via Google OAuth |
| Web auth | Cloudflare Access (optional) |

---

## Prerequisites

- Docker and Docker Compose
- A domain name (for HTTPS and mobile app access)
- A way to expose the app — Cloudflare Tunnel (recommended) or a reverse proxy (nginx, Caddy, etc.)

---

## Exposing Your App (pick one)

Before running the stack, decide how you'll make the app reachable from the internet. You'll need a public domain for HTTPS and mobile app access.

### Option A — Cloudflare Tunnel (recommended)

Cloudflare Tunnel creates an outbound-only connection from your server to Cloudflare's edge — no open ports, no public IP required.

1. Install `cloudflared` on your host.
2. Run `cloudflared tunnel login` and `cloudflared tunnel create <your-tunnel-name>` (pick any name that's memorable to you, e.g. `my-poker-league`).
3. Configure the tunnel to forward to `http://localhost:80`.
4. Point your domain's DNS to the tunnel.

The web UI can additionally be protected with **Cloudflare Access** (Zero Trust → Access → Applications) to require Google login before any page loads. This is separate from the mobile app's JWT auth.

### Option B — Reverse proxy (nginx, Caddy, etc.)

Point your reverse proxy at port 80 on the host and handle TLS termination as normal.

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/glowstickdev/PokerLeagueAppBackend.git
cd PokerLeagueAppBackend
cp .env.example .env
```

Edit `.env` and fill in every value. At minimum:
- `DJANGO_SECRET_KEY` — generate one with the command in `.env.example`
- `POSTGRES_PASSWORD` — any strong password
- `DJANGO_ALLOWED_HOSTS` — your domain
- `CSRF_TRUSTED_ORIGINS` — `https://yourdomain.com`
- `LEAGUE_NAME` — your league's display name
- `LEAGUE_TIMEZONE` — IANA timezone string (e.g. `America/Chicago`)

### 2. Start the stack

```bash
docker compose up -d
```

The container automatically runs `collectstatic`, `makemigrations`, and `migrate` on startup. No manual migration step needed.

### 3. Create a superuser

```bash
docker exec -it app-web python manage.py createsuperuser
```

### 4. Add allowed users (mobile app access)

Log in to the Django admin at `https://yourdomain.com/admin/` and add entries to **Allowed Emails**. Every user who should be able to log in to the mobile app needs an entry here.

### 5. Connect the mobile app

At first launch, the PokerLeagueApp will prompt for a backend URL. Enter `https://yourdomain.com`.

---

## Google OAuth Setup (for mobile app login)

The mobile app authenticates users via Google Sign-In. The backend validates the Google token and issues a JWT. No Google credentials are stored on the backend — only the resulting Django user record.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google+ API** (or People API).
3. Under **APIs & Services → Credentials**, create an **OAuth 2.0 Client ID**:
   - For mobile app authentication: the client ID is configured in the mobile app, not the backend.
   - Authorized JavaScript origins: add `https://yourdomain.com`
4. The backend's `/api/v1/auth/google/` endpoint accepts a Google access token and returns a JWT pair.

User access is controlled by the **AllowedEmail** list in Django admin — a valid Google account is not enough on its own.

---

## AllowedEmail Allowlist

This is the app-level access gate. Even if a user has a valid Google account, they cannot log in to the mobile app unless their email appears in the AllowedEmail table.

To add a user: Django admin → **Allowed Emails** → Add.

---

## Importing Tournament Data

Monthly results and overall stats are imported via CSV files exported from **Tournament Director v3.7.2**.

| Page | URL |
|---|---|
| Monthly results upload | `/upload/` |
| Overall/EOY stats upload | `/upload/overall/` |

The upload interface validates file structure before committing. An existing month can be overwritten by uploading a replacement file.

---

## Environment Variable Reference

| Variable | Description | Example |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key — keep private, change on first deploy | `django-insecure-...` |
| `DJANGO_DEBUG` | Debug mode — set to `0` in production | `0` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames | `yourdomain.com,localhost` |
| `POSTGRES_DB` | PostgreSQL database name | `pokerdb` |
| `POSTGRES_USER` | PostgreSQL username | `pokerapp` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `strongpassword` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins for CSRF | `https://yourdomain.com` |
| `LEAGUE_NAME` | League display name, shown in all web UI | `My Poker League` |
| `LEAGUE_TIMEZONE` | IANA timezone for your league | `America/Chicago` |
| `GUNICORN_WORKERS` | Gunicorn worker processes (default: 2) | `2` |
| `GUNICORN_THREADS` | Gunicorn threads per worker (default: 4) | `4` |

---

## Admin Panel Overview

Access at `/admin/`. Requires a Django staff or superuser account.

| Section | What you can do |
|---|---|
| Players | View all registered players |
| Monthly Games | View uploaded tournament files |
| Game Scores | View and edit individual scores |
| Overall Stats | View uploaded season-total files |
| Poker Events | Create, edit, delete events; view RSVPs |
| Announcements | Create and pin announcements |
| High Hands | Set the current High Hand of the Year holder |
| Allowed Emails | Manage mobile app access |
| Site Settings | Switch UI theme (default / glass) |

---

## API Overview

All API endpoints are under `/api/v1/`. Most require a JWT Bearer token in the `Authorization` header. Tokens are obtained via the Google OAuth flow.

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/auth/google/` | POST | Public | Exchange Google token for JWT |
| `/auth/refresh/` | POST | Public | Refresh JWT access token |
| `/config/` | GET | Public | League name, theme, timezone |
| `/seasons/` | GET | Authenticated | List available seasons |
| `/seasons/{year}/leaderboard/` | GET | Authenticated | Full leaderboard, standings, KO leaders |
| `/results/{year}/{month}/` | GET | Authenticated | Single tournament results |
| `/players/` | GET | Authenticated | All players |
| `/players/{id}/` | GET | Authenticated | Player detail and season history |
| `/players/{id}/games/` | GET | Authenticated | All game scores for a player |
| `/players/compare/` | GET | Authenticated | Head-to-head comparison |
| `/events/` | GET | Authenticated | Upcoming and past events |
| `/events/` | POST | Staff | Create event |
| `/events/{id}/` | PATCH | Staff | Update event |
| `/events/{id}/` | DELETE | Staff | Delete event |
| `/events/{id}/rsvp/` | POST | Authenticated | Submit RSVP (yes/maybe/no) |
| `/events/{id}/rsvps/` | GET | Staff | List all RSVPs for an event |
| `/announcements/` | GET | Authenticated | Active announcements |
| `/admin/settings/` | GET/PATCH | Staff | Read or update site settings |

---

## Project Structure

```
poker-tool/
├── config/               # Django settings and WSGI
├── csvapp/               # Main application
│   ├── models.py         # Player, MonthlyGame, GameScore, OverallStats, etc.
│   ├── views.py          # Web UI views
│   ├── api_views.py      # REST API views
│   ├── api_urls.py       # API URL routing
│   ├── serializers.py    # DRF serializers
│   ├── csv_handler.py    # CSV validation and parsing
│   ├── context_processors.py  # Injects league_name into all templates
│   ├── templates/        # Django HTML templates
│   └── migrations/       # Database migrations
├── .env.example          # Environment variable template
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── scoring-rules.md      # Scoring logic documentation
```

---

## Scoring Rules

- **2026 onward** — each player's top 5 tournament scores count toward their season total
- **Pre-2026** — sum of all tournament scores
- **Knockout leaders (2026+)** — ranked by April-onwards knockouts only (`april_knockouts` field)
- See [scoring-rules.md](scoring-rules.md) for full details

---

## Rebuilding After Config Changes

```bash
docker compose build --no-cache && docker compose up -d
```
