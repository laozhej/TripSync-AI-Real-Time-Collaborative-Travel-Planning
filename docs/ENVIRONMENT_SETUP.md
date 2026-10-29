# Environment setup

**Planning only:** commands below are provisional until scaffolding and lockfiles exist. They have not been run against an application. PRD §§8–10,12. Do not run nonexistent CLI commands and interpret failures as application defects. The only current deliverables are documentation and the source PRD.

## Selected stack and official checks (2026-10-29)

| Dependency | Proposed baseline | Official source and verification limit |
|---|---|---|
| Python | 3.13.x | Local interpreter reports 3.13.1; project package compatibility still needs smoke test |
| FastAPI | Stable 0.x; exact patch to lock at TASK-002 | [Release notes](https://fastapi.tiangolo.com/release-notes/) show recent breaking changes; use current compatible release and record resolved version, not an untested guessed lock |
| React | 19.3 line | [Official versions](https://react.dev/versions) lists 19.3; client compatibility not tested |
| PostgreSQL | 18.x current supported minor | [Version policy](https://www.postgresql.org/support/versioning/) confirms support; pin exact image digest when scaffolded |
| SQLAlchemy | 2.0.55 maintenance baseline | [Release notice](https://www.sqlalchemy.org/blog/2026/10/16/sqlalchemy-2.0.55-released/) and [async API](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html); newer 2.1 line exists, avoid migration churn for baseline |
| asyncpg | 0.32.0 candidate | [Driver releases](https://github.com/MagicStack/asyncpg/releases) and [support docs](https://magicstack.github.io/asyncpg/current/) verify native asyncio/PostgreSQL support; Python/OS wheel install still pending |
| Vite / Node | Current compatible Vite stable; Node 22.12+ baseline | [Vite guide](https://vite.dev/guide/) defines runtime requirements; lock frontend toolchain after install smoke test |
| Pytest | Current supported stable, exact patch pending | [Official guide](https://docs.pytest.org/en/stable/); add pytest-asyncio, HTTPX and WebSocket client matching backend dependencies |
| Ollama | Local current stable, exact runtime/tag/digest pending | [Chat API](https://docs.ollama.com/api/chat), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [llama3.2 catalog](https://ollama.com/library/llama3.2); local schema support verified in docs, not runtime |

Pydantic v2, Uvicorn, Alembic, HTTPX, PyJWT, pwdlib Argon2, safe YAML parser and scikit-learn are planned libraries; exact compatible versions must be resolved/pinned at scaffold. Do not claim install-tested versions. React client uses JavaScript for simplicity; Python remains the sole application backend. No Motor/PyMongo needed: selected database is PostgreSQL. SQLAlchemy uses `postgresql+asyncpg://...`, shared async engine/pool, separate AsyncSession per task. [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) explicitly cautions against sharing an AsyncSession concurrently.

FastAPI [WebSocket dependencies](https://fastapi.tiangolo.com/advanced/websockets/) support handshake policy injection. Browser cookie transport plus JWT validation is application code to implement, not automatic token verification supplied by the framework. The [security tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) demonstrates JWT/password components, not the complete refresh/revocation protocol in this plan.

## Prerequisites and planned startup

Install Python, Node/npm, PostgreSQL (or Docker Compose), Git and Ollama. Allocate model disk/RAM after checking selected weights; no universal hardware minimum or 3 s guarantee is asserted. All JS/CSS/fonts/images served locally; no CDN dependency. Start DB before migrations/import; start Ollama before real-generation smoke test; fallback can run while model is down.

After a later implementation creates these paths/scripts, PowerShell workflow from repository root is intended to be:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
Copy-Item .env.example .env
# Fill local secrets and credentials in .env before continuing.
$env:PYTHONPATH=(Join-Path (Get-Location) 'backend')
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m app.cli create-admin
.\.venv\Scripts\python.exe -m app.cli import-dataset data/destinations/lisbon.json
ollama pull llama3.2:3b
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

The block makes `app.cli` importable through backend on PYTHONPATH; an editable package is a future alternative. Startup must load root `.env` explicitly via application settings, including for CLI/migrations; shell assignment is not implied by creating the file. This must be verified during scaffolding. Start frontend in a second terminal: `npm --prefix frontend ci`, then `npm --prefix frontend run dev -- --host 127.0.0.1`; future Vite proxy routes `/api` and `/ws` to backend, preserving same-origin cookies. Open frontend URL printed by Vite. For private packaged mode build frontend and serve through backend.

Planned verification: `.\.venv\Scripts\python.exe -m pytest backend/tests`; `npm --prefix frontend test -- --run`; `npm --prefix frontend run build`; future `python -m app.cli demo-session` and `python -m app.cli train-recommendations`. Each script is pending; README must be updated with verified commands once implemented. No package installation is requested now.

## Environment reference

| Name | Meaning/default proposal | Secret? |
|---|---|---|
| APP_ENV | local/private/test | No |
| DATABASE_URL | postgresql+asyncpg connection URL; no real credential in examples | Yes |
| JWT_SIGNING_KEY / JWT_ISSUER / JWT_AUDIENCE | random local key and exact configured issuer/audience | Key yes |
| ACCESS_TOKEN_MINUTES | 15, hard max 60 | No |
| REFRESH_TOKEN_DAYS | 7 | No |
| COOKIE_SECURE | false loopback HTTP, true private HTTPS | No |
| ALLOWED_ORIGINS | exact frontend origins, no wildcard credentials | No |
| CSRF_SECRET | independent random secret | Yes |
| MODEL_BASE_URL | http://127.0.0.1:11434, operator-configured only | No |
| MODEL_NAME / MODEL_TIMEOUT_MS | provisional llama3.2:3b / 2500 | No |
| ROOM_FLUSH_MS / ROOM_MAX_PARTICIPANTS | 100 / 50 design defaults | No |
| DATA_DIR / MODEL_ARTIFACT_DIR | local nonpublic directories | No |
| LOG_LEVEL | INFO, safe structured summaries | No |

## Troubleshooting

DB refused: check process/port/URL and readiness, not token changes. Alembic mismatch: backup then apply known revisions, never auto-drop tables. Missing asyncpg wheel: verify Python/driver matrix before changing stack. Cookie/socket 401: inspect origin/path/Secure and expiry without logging token; refresh then reconnect. Multiple workers produce divergent room authority: stop and restart exactly one worker. Slow/absent model: inspect runtime/model load, return disclosed grounded fallback and report cold/warm timing separately. Missing transit/weather citation: fix authored data or omit claim; never call a live travel API to fill the gap.
