# Environment setup

TripSync AI is an independent, local educational prototype. The implemented first slice uses Python 3.13, FastAPI native WebSockets, PostgreSQL, SQLAlchemy/asyncpg and a React JavaScript client. Run **one Uvicorn worker**: room authority is process-local. The remaining phase 1 acceptance gaps are recorded in [implementation evidence](PHASE_1_EVIDENCE.md); later features described in other documents remain planned.

## Prerequisites

Install Python 3.13, Node.js/npm, PostgreSQL and Git. Create an empty disposable PostgreSQL database and a role with permission to create its tables. The tested environment used Python 3.13.1, Node 24.13.0, npm 9.9.4 and PostgreSQL 18.1. Python dependency versions are in `backend/requirements.lock`, and npm versions are in `frontend/package-lock.json`.

## First-time setup (PowerShell)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
Copy-Item .env.example .env
notepad .env
```

Set `DATABASE_URL` in `.env` to the disposable database using `postgresql+asyncpg://`; URL-encode reserved characters in credentials. Keep this file private and never paste it or its contents into chat. Its example contains no credentials. The example permits the local frontend origin `http://127.0.0.1:5173`; if using a different local origin, update `ALLOWED_ORIGINS` accordingly.

Then run:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'backend')
.\.venv\Scripts\python.exe -m app.cli init-local-key
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m app.cli import-dataset data\destinations\lisbon.json
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

The key command creates a random signing key only when it is blank; it retains an existing key. Import the sample destination once into an empty database. Re-importing an existing destination intentionally fails until dataset version activation is implemented. To grant an existing registered account Admin privileges, an operator can separately run `python -m app.cli create-admin` with the same `PYTHONPATH`; account registration itself cannot grant Admin.

In a second PowerShell window:

```powershell
cd D:\projects\Airbnb\frontend # or the frontend directory in your checkout
npm ci
npm run dev -- --host 127.0.0.1
```

Open the local address printed by Vite. Use two separate browser profiles or private windows to test independent accounts. Create a room in one, share its invitation code privately with the other, and add a sample place. The sample data is fictional. Browser refresh currently loses the in-memory access token; sign in again. The full dashboard/rejoin experience remains planned.

## Verification and current limits

With the API running, `/api/v1/health/live`, `/api/v1/health/ready` and `/api/v1/health/gateway` report liveness, database/schema/room readiness and room-service availability. A failed room persistence batch makes readiness unavailable. These are basic probes; actor-loop freshness and complete operational monitoring are future work.

From the root, run unit tests with:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'backend')
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Database integration tests are skipped unless `TEST_DATABASE_URL` is set to a disposable, migrated database containing the sample dataset. For a clean database verification, `python backend\tests\clean_setup.py` uses `.env` to create a randomly named temporary database, applies migrations, imports the sample and runs the backend suite, then drops that database. It requires CREATEDB permission and never drops the configured database. Browser verification is the opt-in `backend\tests\browser_phase1.py` against running local API/Vite servers; the current script uses Windows Chrome. See [evidence](PHASE_1_EVIDENCE.md) for exact outcomes and warnings.

Secrets belong only in environment variables or the ignored `.env`. `COOKIE_SECURE=false` is for local loopback HTTP; use HTTPS/WSS and secure cookies for private network testing. The JWT key also encrypts retained idempotent results: rotation invalidates access tokens and makes old encrypted responses unreadable. No public hosting is configured. Ollama, Concierge, recommendations, voting and later features are not implemented.
