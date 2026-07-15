"""
Theme CSS definitions. Each entry is injected into every HTML response by
ThemeMiddleware. The 'default' key is intentionally empty — the inline styles
in each template are the default. Only override themes need CSS here.
"""

_GLASS_CSS = """
/* ── Glass Theme ─────────────────────────────────────────────────────────── */
:root {
  --bg: #070b14;
  --card-bg: rgba(255,255,255,0.06);
  --border: rgba(255,255,255,0.12);
  --gold: #c9a84c;
  --gold-light: #e8c97a;
  --cream: #eef2ff;
  --red: #f87171;
  --green: #34d399;
  --green-light: #6ee7b7;
  --felt: rgba(255,255,255,0.04);
  --glass-blur: blur(14px);
  --glass-shadow: 0 8px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08);
}

/* Body background — deep navy with subtle colour orbs */
body {
  background: var(--bg) !important;
  background-image:
    radial-gradient(ellipse at 15% 40%, rgba(99,102,241,0.18) 0%, transparent 55%),
    radial-gradient(ellipse at 85% 15%, rgba(201,168,76,0.10) 0%, transparent 45%),
    radial-gradient(ellipse at 60% 85%, rgba(52,211,153,0.08) 0%, transparent 45%) !important;
}

/* ── Shared card / panel glass treatment ─────────────────────────────────── */
.stat-card,
.event-card,
.event-mini,
.form-card,
.ann-card,
.hh-card,
.ann-strip,
.jackpot-section,
.jackpot-banner,
.upload-box,
.profile-card,
.h2h-card,
.result-card,
.score-row,
.leaderboard-wrap,
.chart-wrap {
  background: var(--card-bg) !important;
  backdrop-filter: var(--glass-blur) !important;
  -webkit-backdrop-filter: var(--glass-blur) !important;
  border: 1px solid var(--border) !important;
  border-radius: 16px !important;
  box-shadow: var(--glass-shadow) !important;
}

.event-card:hover,
.stat-card:hover {
  border-color: rgba(201,168,76,0.45) !important;
  box-shadow: 0 12px 40px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.12) !important;
}

/* ── Navigation ──────────────────────────────────────────────────────────── */
.nav-bar {
  background: rgba(7,11,20,0.7) !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  border-bottom: 1px solid var(--border) !important;
  position: relative !important;
  z-index: 100 !important;
}
.nav-dropdown-menu { z-index: 1000 !important; }

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.btn-cal,
.btn-admin,
.btn-create,
.btn-rsvp,
.rsvp-btn {
  border-radius: 8px !important;
}

.btn-create {
  background: rgba(201,168,76,0.15) !important;
  backdrop-filter: blur(8px) !important;
  -webkit-backdrop-filter: blur(8px) !important;
  border-radius: 10px !important;
}

/* ── Header ──────────────────────────────────────────────────────────────── */
header {
  background: rgba(7,11,20,0.6) !important;
  backdrop-filter: blur(10px) !important;
  -webkit-backdrop-filter: blur(10px) !important;
}

/* ── Messages ────────────────────────────────────────────────────────────── */
.msg {
  backdrop-filter: blur(8px) !important;
  -webkit-backdrop-filter: blur(8px) !important;
  border-radius: 10px !important;
}

/* ── Tables ──────────────────────────────────────────────────────────────── */
table {
  border-radius: 12px !important;
  overflow: hidden !important;
}

/* ── Section titles ──────────────────────────────────────────────────────── */
.section-title {
  letter-spacing: 2px !important;
}

/* ── Leaderboard row hover ───────────────────────────────────────────────── */
tr:hover td {
  background: rgba(255,255,255,0.04) !important;
}

/* ── Year / nav pills ────────────────────────────────────────────────────── */
.year-picker a,
.nav-bar a {
  border-radius: 6px !important;
}

/* ── Footer ──────────────────────────────────────────────────────────────── */
footer {
  background: rgba(7,11,20,0.5) !important;
  backdrop-filter: blur(10px) !important;
  -webkit-backdrop-filter: blur(10px) !important;
}
"""

THEMES = {
    'default': '',
    'glass': _GLASS_CSS,
}
