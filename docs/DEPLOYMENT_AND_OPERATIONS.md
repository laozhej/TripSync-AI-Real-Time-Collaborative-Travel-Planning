# Local deployment and operations

Local runbook, PRD §§4.1–4.2,9.4,10.3,14.1. The application runs privately on loopback; public deployment is out of scope. [Environment setup](ENVIRONMENT_SETUP.md) owns dependencies/commands; [architecture](ARCHITECTURE.md) owns durability semantics. Phase 4 verification and remaining limits are recorded in PHASE_4_EVIDENCE.md.

## Topology and startup

One private host, one FastAPI/Uvicorn application worker, local PostgreSQL and selected local Ollama/Qwen inference; React/Vite runs locally. Multiple room actors share the process but never state. Optional future Compose services could use named durable volumes, pinned images and DB readiness dependencies; no Compose file is claimed. No public hosting/CDN or external travel services.

Startup order: validate config/secrets → connect DB → verify migrations → hydrate room aggregates/active votes → resolve overdue votes idempotently → initialize retrieval/recommendation artifacts → mark gateway ready → serve frontend. Model unavailable degrades AI generator but need not block non-AI readiness; health exposes model status without a secret. Binding loopback is default; private LAN requires TLS/WSS, exact origins and Secure cookies. Do not add multiple workers without redesigning room ownership and cross-process fan-out.

## Health and observability

`/api/v1/health/live` reports process alive; `/api/v1/health/ready` checks DB/schema, startup recovery, a live maintenance task and frozen rooms; `/api/v1/health/gateway` checks the maintenance task and frozen rooms. Dedicated heartbeat-age/queue/model health probes remain extensions, not existing monitoring. Current structured room logs whitelist event, trip/session/epoch/sequence/committed watermark, correlationId and UTC time; richer per-operation timing is measured by the local harness rather than asserted as general production telemetry. No raw JWT/chat/question/model response is included in these logs.

Metrics include sync/apply/fan-out timing, active rooms, distinct connected users/planners, rejection counts, flush lag/committed watermark, model cold load and generation latency, fallback rate, no-valid-candidate counts, conflict detection delays and recommendation version. Local JSON/CSV measurements suffice; no hosted telemetry required. Provisional alerts: flush lag >1 s, unbounded queue growth, stalled vote timer, repeated model failures; record actual thresholds chosen during implementation.

## Failure procedures

| Failure | Behavior and recovery |
|---|---|
| Client drop | Preserve membership/session; first/last socket presence; full snapshot after JWT refresh/reconnect |
| Leader drop | Show disconnected immediately; freeze new Leader actions; keep existing vote deadlines |
| DB unavailable | Readiness false; freeze writes; announce degraded persistence; keep bounded memory; restore/query uncertain commits before proceeding |
| Crash before flush | Volatile acknowledged moves may be lost; reload committed rows/events, new roomEpoch, full resync and visible rollback notice |
| Vote deadline during outage | Do not fabricate winner; resolve from durable eligible ballots after recovery; deadline stays unchanged |
| Model timeout | Grounded deterministic valid-only fallback, label unavailable; other modules continue |
| Ingestion/index failure | Staged version never activated; keep previous active version; existing trips unchanged |
| Bad recommendation artifact | Retain previous model; invalidate affected cache and disclose degraded serving |
| Disk full | Reject new uploads/writes safely, freeze affected room, preserve existing DB; operator frees verified space |

Clean shutdown stops accepts, drains room commands, persists pending mutations and snapshots, closes connections with restart hint, then closes pools/runtime client. If timeout occurs log committed watermark and explicitly uncommitted range. Server-authored session.end distinguishes operator finalization from accidental process loss; restart must not double-count a planning session.

## Backup and restore

Before migration/major demo use PostgreSQL logical backup plus authored dataset files and model artifact manifest/checksums; store credentials separately. Retain e.g. 7 local daily backups provisionally, outside served files and Git. `pg_dump`/`pg_restore` command credentials must come through protected environment/service config, never command text committed to docs. Actual backup commands and local paths must be verified at implementation.

Restore into an isolated test database, compare logical table counts/checksums, recompute budgets/analytics for a known session, then point the stopped application at the restored DB and start with new epochs. Preserve immutable dataset versions referenced by trips. OPS-01 tests crash/outage/expired vote recovery; OPS-02 tests restore and recomputation. Phase 4 exercises actual backup restoration as detailed below. Performance measurements must state background backup/training activity.

## Phase 2 operations — 2026-10-31

The standard entry point remains `app.main:app` with one worker. Local model inference binds loopback and is started/preloaded separately with `scripts/start-local-model.ps1`. API readiness expects Alembic `0010_concierge`, a live room flush task and no frozen room. It does not certify performance or model availability; valid-only fallback covers model outages. Operational JSON logs whitelist room/session/correlation identifiers and watermarks for applied board events, committed batches/transitions, and Concierge requests/results/replays/rejections; message/question/token bodies and raw database exceptions are excluded from those logs.

Actual crash/outage and lost-ack checks are in [Phase 2 evidence](PHASE_2_EVIDENCE.md). Normal database loss freezes writes; reconnect/restart with durable state issues a new epoch and warns about volatile edits. Test-only factories are isolated under backend/tests and do not add operational fault endpoints. Backup restoration, overdue election resolution and final load/security consolidation are still required later.

## Verified Phase 4 restore procedure

Run `python backend/tests/clean_setup.py backend/tests/test_phase4_restore.py` from the root using the installed environment. The script requires PostgreSQL `pg_dump`/`pg_restore` on PATH, CREATEDB and permission to drop its own generated databases. The source must have the `tripsync_verify_` prefix; the restored database is newly generated as `tripsync_restore_<uuid>`. It never dumps/restores over the configured working database.

The test invokes custom-format pg_dump and pg_restore with `--no-owner`; passwords are passed in the child process environment rather than arguments. The archive stays under ignored `.local/` and is deleted in finally. Every public table is compared by sorted logical-row SHA256 and count before recovery. Application recovery then creates a new room epoch, resolves the saved overdue ballot once, locks the selected winner, and reproduces an independent INR 40,000-paise split as 13,333/26,667 paise. A repeated deadline tick produces no extra resolution. Only schema metadata and digests, not table contents/password hashes/refresh tokens, enter `evidence/operations/restore.json` and `evidence/contracts/`.

The original real process-kill/PostgreSQL outage drill remains `python backend/tests/recovery_phase2.py`: it proves durable board/chat/reactions/leadership/budgets survive while volatile edits may roll back, with readiness/write rejection after uncertain persistence. The lost-ack integration test separately commits then raises before acknowledgement and verifies durable recovery/deduplication. See PHASE_4_EVIDENCE.md for actual rerun results. Backup retention/scheduling and a production operator restore UI remain outside this local manual drill.
