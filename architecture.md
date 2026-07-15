# Architecture Overview

## System Purpose

The Private Poker League Manager is a self-hosted backend system designed to:

- Persist league data across multiple seasons
- Validate and import structured CSV data
- Calculate standings dynamically
- Provide a private web interface for league members

---

## High-Level Architecture

User
  ↓
Cloudflare Tunnel
  ↓
Reverse Proxy (Caddy/Nginx)
  ↓
Django Application
  ↓
PostgreSQL Database

---

## Components

### 1. Django Backend
Responsible for:
- Data models
- CSV import logic
- Validation rules
- Standings calculations
- Admin interface
- API endpoints (future)

---

### 2. PostgreSQL Database
Stores:
- Seasons
- Events
- Players
- Results
- Jackpot values

Persistent across deployments.

---

### 3. Reverse Proxy
Handles:
- HTTPS
- Secure routing
- Internal service forwarding

---

### 4. Cloudflare Zero Trust
Provides:
- Authentication
- Access control
- Private site exposure
- Email-based or SSO login

---

## Data Flow

1. Admin uploads CSV for an event.
2. Backend validates structure and data integrity.
3. Event is assigned to correct season.
4. Player results are stored.
5. Standings are recalculated dynamically when viewed.
6. Frontend displays aggregated standings.

---

## Design Philosophy

- Keep logic centralized in backend
- Avoid storing calculated totals permanently unless needed
- Preserve raw event data permanently
- Make seasons independent units
- Favor clarity over premature optimization
- deploy as docker-compose stack

---

## Future Expansion

- REST API for frontend decoupling
- Astro frontend
- Automated file watcher ingestion
- Notification system
