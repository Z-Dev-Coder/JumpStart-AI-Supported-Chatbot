# JumpStart — Setup Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Node.js 18+
- (Optional) Groq API key from https://console.groq.com

---

## 1 — PostgreSQL Database Setup

Open **pgAdmin** or run **psql** as the postgres superuser:

```sql
-- Create database user
CREATE USER jumpstart_user WITH PASSWORD 'jumpstart2026';

-- Create database
CREATE DATABASE jumpstart_db OWNER jumpstart_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE jumpstart_db TO jumpstart_user;

-- Connect to the new database, then enable pgvector
\c jumpstart_db

CREATE EXTENSION IF NOT EXISTS vector;

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO jumpstart_user;
```

**Quick way (run in Command Prompt as Administrator):**
```
psql -U postgres -c "CREATE USER jumpstart_user WITH PASSWORD 'jumpstart2026';"
psql -U postgres -c "CREATE DATABASE jumpstart_db OWNER jumpstart_user;"
psql -U postgres -d jumpstart_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -U postgres -d jumpstart_db -c "GRANT ALL ON SCHEMA public TO jumpstart_user;"
```

---

## 2 — Backend Setup

```powershell
cd "d:\Software Engineering\HDSE\HDSE-CPL-Capstone Project - Application Development\JumpStart\backend"

# Activate virtual environment
.\venv\Scripts\activate

# Install dependencies (if not already done)
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Seed demo data
python manage.py seed_data

# Seed the AI knowledge base (approved policy docs + embeddings)
python manage.py seed_knowledge

# (Optional) Create a superuser for Django admin
python manage.py createsuperuser
```

---

## 3 — Frontend CSS Build

```powershell
cd "d:\Software Engineering\HDSE\HDSE-CPL-Capstone Project - Application Development\JumpStart\frontend"

# Install Node dependencies (if not already done)
npm install

# Build Tailwind CSS
npm run build:css
```

---

## 4 — Configure Groq API Key

Edit `backend/.env` and replace the placeholder:
```
GROQ_API_KEY=your-groq-api-key-here
```
Get a free key at: https://console.groq.com

---

## 5 — Start the Server

```powershell
cd "d:\Software Engineering\HDSE\HDSE-CPL-Capstone Project - Application Development\JumpStart\backend"
.\venv\Scripts\activate

# Development server (now serves WebSockets too, via daphne in INSTALLED_APPS)
python manage.py runserver

# OR explicitly with Daphne
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Visit: **http://localhost:8000**

---

## Demo Accounts (after seed_data)

| Role     | Username       | Password     |
|----------|----------------|--------------|
| Customer | customer_demo  | demo1234!    |
| Staff    | staff_demo     | demo1234!    |
| Admin    | admin_demo     | demo1234!    |

---

## Pages

| URL                    | Description                     |
|------------------------|---------------------------------|
| http://localhost:8000/ | Storefront home                 |
| http://localhost:8000/products/ | Products grid          |
| http://localhost:8000/account/ | Customer account        |
| http://localhost:8000/staff/   | Staff dashboard         |
| http://localhost:8000/admin-panel/ | Admin dashboard     |

---

## Production Checklist

The prototype runs locally over HTTP by design (capstone scope). For a real deployment:

1. **Set `DEBUG=False` in `backend/.env`** — this automatically enables HTTPS redirect,
   HSTS, and secure session/CSRF cookies (see the hardening block at the bottom of
   `config/settings.py`). Only do this behind an HTTPS reverse proxy — with
   `DEBUG=False` over plain HTTP the site will redirect to https:// and fail locally.
2. Set real values in `.env`: strong `SECRET_KEY` (already generated), production
   `ALLOWED_HOSTS`, a strong database password, and your own `GROQ_API_KEY`.
3. Switch `CHANNEL_LAYERS` to Redis (`channels_redis`) — the in-memory layer only
   works for a single process.
4. Serve static files properly: `python manage.py collectstatic` + WhiteNoise or a web
   server; the dev server only serves static/media when `DEBUG=True`.
5. Run daphne behind a reverse proxy (nginx/Caddy) that terminates TLS; WebSockets
   automatically use `wss://` on HTTPS pages.
6. Verify with `python manage.py check --deploy`.

Security guardrails already built in (per the implementation plan): role-based
permissions on every API, JWT + session auth kept in sync, agent restricted to
approved tools (no model-generated SQL), retrieval restricted to approved documents,
prompt-injection guard with canned response, input length limits, forbidden-promise
safety check with regeneration, sensitive actions require human approval, full agent
action audit trail, and automatic escalation to staff on any agent failure.

---

## Troubleshooting

**"password authentication failed for user jumpstart_user"**
→ Run the PostgreSQL setup commands in Step 1.

**"could not connect to server"**
→ Make sure PostgreSQL is running: `net start postgresql-x64-15` (adjust version)

**Chat WebSocket not connecting**
→ `runserver` now serves WebSockets (daphne is in INSTALLED_APPS). If it still fails, the chat panel automatically falls back to HTTP polling.

**Chat always says "Connecting you to a human agent"**
→ The knowledge base is empty. Run `python manage.py seed_knowledge`.

**Sentiment model slow on first load**
→ The HuggingFace model downloads on first use (~300MB). Subsequent loads use cache.

**"GROQ_API_KEY is not set"**
→ Edit `backend/.env` and add your key from https://console.groq.com
