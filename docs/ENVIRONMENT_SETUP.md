# Environment setup

TripSync AI is an independent, local educational prototype using Python 3.13, FastAPI native WebSockets, PostgreSQL, SQLAlchemy/asyncpg and a React JavaScript client. Run **one Uvicorn worker**: room authority is process-local. Phase 1–3 feature acceptance is recorded in the corresponding evidence documents; Phase 4 commands/results and limitations are in PHASE_4_EVIDENCE.md.

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
.\.venv\Scripts\python.exe -m app.cli import-dataset data\destinations\bengaluru.json
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

The key command creates a random signing key only when it is blank; it retains an existing key. Import the sample destination once into an empty database. Subsequent dataset versions use Admin staging/activation rather than re-importing the initial version. To grant an existing registered account Admin privileges, an operator can separately run `python -m app.cli create-admin` with the same `PYTHONPATH`; account registration itself cannot grant Admin.

In a second PowerShell window:

```powershell
cd D:\projects\Airbnb\frontend # or the frontend directory in your checkout
npm ci
npm run dev -- --host 127.0.0.1
```

Open the local address printed by Vite. Use two separate browser profiles or private windows to test independent accounts. Create a room in one, share its invitation code privately with the other, and add a sample place. The sample data is fictional. Access tokens remain in memory; the browser restores/rotates a valid refresh session and offers dashboard rejoin. A revoked/expired refresh session returns to sign-in.

## Verification and current limits

With the API running, `/api/v1/health/live`, `/api/v1/health/ready` and `/api/v1/health/gateway` report liveness, database/schema/room readiness and room-service availability. A failed room persistence batch makes readiness unavailable. These are basic probes; actor-loop freshness and complete operational monitoring are future work.

From the root, run unit tests with:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'backend')
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Database integration tests are skipped unless `TEST_DATABASE_URL` is set to a disposable, migrated database containing the sample dataset. For a clean database verification, `python backend\tests\clean_setup.py` uses `.env` to create a randomly named temporary database, applies migrations, imports the sample and runs the backend suite, then drops that database. It requires CREATEDB permission and never drops the configured database. Browser verification is the opt-in `backend\tests\browser_phase1.py` against running local API/Vite servers; the current script uses Windows Chrome. See [evidence](PHASE_1_EVIDENCE.md) for exact outcomes and warnings.

Secrets belong only in environment variables or the ignored `.env`. `COOKIE_SECURE=false` is for local loopback HTTP; use HTTPS/WSS and secure cookies for private network testing. The JWT key also encrypts retained idempotent results: rotation invalidates access tokens and makes old encrypted responses unreadable. No public hosting is configured. Timed voting, recommendations, dashboard, analytics and Admin ingestion are implemented; evidence distinguishes functional checks from performance gates.

Chat uses Alembic revision `0009_chat`; apply `upgrade head` when updating an existing local database. For an isolated browser smoke run, `\.venv\Scripts\python.exe backend\tests\browser_clean_setup.py` creates and drops a disposable database and starts temporary local servers; it requires PostgreSQL CREATEDB permission, available ports 8000/5173, Node and Windows Chrome. It does not migrate the configured database. See [evidence](PHASE_1_EVIDENCE.md) for actual results and limitations.

## Phase 2 local model and run path

The user selected local open-source inference. This checkout uses Qwen2.5 1.5B through a portable Ollama runtime on loopback. Ollama is the selected implementation, not a requirement named by the PRD. Runtime/weights/logs are ignored under `.local/`. The runtime and model are already present on the implementation machine; `.\scripts\start-local-model.ps1` starts or preloads them without changing the system PATH.

For another Windows checkout, install the official portable runtime and model first. The verified runtime artifact was [Ollama v0.40.13](https://github.com/ollama/ollama/releases/tag/v0.40.13):

```powershell
New-Item -ItemType Directory -Force .local/ollama | Out-Null
curl.exe --location --fail --output .local/ollama-windows-amd64.zip https://github.com/ollama/ollama/releases/download/v0.40.13/ollama-windows-amd64.zip
$expectedHash='7AFA38624FA62EE5D8293422D0AB084C1BB4603134C7F4DAFCE11A033B57CC19'
if ((Get-FileHash .local/ollama-windows-amd64.zip -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Runtime checksum mismatch' }
Expand-Archive -LiteralPath .local/ollama-windows-amd64.zip -DestinationPath .local/ollama -Force
.\scripts\start-local-model.ps1 -PullModel
```

The archive hash was checked before executing it. Additional runtime and model disk space is required; actual versions, model digest and hardware are in [Phase 2 evidence](PHASE_2_EVIDENCE.md). For subsequent runs:

```powershell
.\scripts\start-local-model.ps1
$env:PYTHONPATH=(Join-Path (Get-Location) 'backend')
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
# In a second terminal:
npm run dev --prefix frontend -- --host 127.0.0.1
```

Open the Vite loopback address. Create/join a trip with two browser profiles. Pin a venue, use the grid/drop or selected-time move, and exercise chat and Leader room controls. For Concierge, expand Budget and dietary preferences, explicitly save a food ceiling such as INR500/person, declare each traveler's diets in that traveler's session, select a valid trip day/time (e.g. 12:00 IST for the synthetic kitchen), and ask. Click the canonical citation to view its pinned source. Missing configuration prompts clarification; unavailable/invalid generation is labeled fallback and never relaxes filters. Historical answers are labeled Earlier result after the room changes. Cold model loading is separate setup; application generation still has its 2.5-second deadline.

Phase 2 verification (all commands below were exercised):

```powershell
$env:RUN_LIVE_MODEL='1'
.\.venv\Scripts\python.exe backend\tests\clean_setup.py
npm run test:unit --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python.exe backend\tests\browser_clean_setup.py
.\.venv\Scripts\python.exe backend\tests\recovery_phase2.py
```

The clean setup and recovery/browser wrappers create and remove their own randomly named PostgreSQL databases. They require CREATEDB; the recovery drill also needs permission to terminate connections to its own database. Browser testing needs Chrome and free ports 8000/5173; recovery uses 8001. The browser test preloads the real local model and uses a test-only eight-second first JWT to verify refresh. `RUN_LIVE_MODEL=1` opts the backend suite into the actual-model acceptance test; leaving it unset skips that specific test and does not establish live-generation evidence. The standard production entry point imports no test factories or fault gates.

## Phase 3 update

Apply `python -m alembic -c backend/alembic.ini upgrade head` with PYTHONPATH=backend; current head is 0011_phase3. Keep one worker. No new dependency is required. Train the current destination model with `python -m app.cli train-recommendations --destination "Bengaluru, India"`. Training without interactions creates a disclosed cold-start artifact; use likes/pins from distinct test participants to provide actual CF evidence.

Verification commands: `.venv/Scripts/python backend/tests/clean_setup.py` (disposable PostgreSQL, both sample datasets, complete backend suite); `npm --prefix frontend run test:unit`; `npm --prefix frontend run build`; `.venv/Scripts/python backend/tests/browser_clean_setup.py backend/tests/browser_phase3.py`; and the evaluation command in RECOMMENDATION_ENGINE.md. The Phase 3 browser run does not require inference; the default existing browser script still verifies real Concierge separately after local-model preload. Test database and process cleanup is scoped to generated disposable resources. Sanitized failed-run diagnostics stay ignored in .local.

## Phase 4 verification

PostgreSQL client tools `pg_dump` and `pg_restore` must be on PATH for the now-required restore test. Install from the same PostgreSQL major version (verified 18.1). Stop your own Vite instances before reinstalling that checkout's node_modules: Windows locks loaded native Rollup/esbuild files. A clean npm install may instead use an isolated directory containing copies of package.json/package-lock.json. Do not stop unrelated processes or delete a running checkout's dependencies.

```powershell
.\scripts\start-local-model.ps1
$env:RUN_LIVE_MODEL='1'
.\.venv\Scripts\python.exe backend/tests/clean_setup.py
npm run test:unit --prefix frontend
npm run build --prefix frontend
# Choose unused loopback ports; these runners create disposable databases.
$env:BROWSER_API_PORT='8010'
$env:BROWSER_WEB_PORT='5180'
$env:BROWSER_TEST_TIMEOUT='600'
.\.venv\Scripts\python.exe backend/tests/browser_clean_setup.py backend/tests/phase4_measure.py
# Run model-related tests sequentially; measurement explicitly unloads the model.
.\.venv\Scripts\python.exe backend/tests/browser_clean_setup.py
.\.venv\Scripts\python.exe backend/tests/browser_clean_setup.py backend/tests/browser_phase3.py
.\.venv\Scripts\python.exe backend/tests/browser_clean_setup.py backend/tests/browser_frontend_ui.py
.\.venv\Scripts\python.exe backend/tests/recovery_phase2.py
.\.venv\Scripts\python.exe scripts/scan-submission.py
.\.venv\Scripts\python.exe scripts/package-submission.py
```

The measurement script records 1,000 moves and 1,000 HTTP reads across ten sockets/five identities/two rooms, 20 same-version races and 20 conflicts, then one explicitly unloaded cold request and 100 requests after a disclosed completed preload. It produces raw samples and nearest-rank summaries under evidence/performance. Browser render probes are separate. Results describe the exercised host/profile, not a 50-distinct-planner/LAN capacity certification. The package ZIP is ignored under `.local/tripsync-phase4-submission.zip`; its manifest contains only Git-visible source/evidence, excluding secrets and database dumps.
