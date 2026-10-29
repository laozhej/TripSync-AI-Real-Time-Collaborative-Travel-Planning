# Local deployment and operations

Proposed runbook, PRD §§4.1–4.2,9.4,10.3,14.1. No application is deployed. [Environment setup](ENVIRONMENT_SETUP.md) owns dependencies/commands; [architecture](ARCHITECTURE.md) owns durability semantics.

## Topology and startup

One private host, one FastAPI/Uvicorn application worker, local PostgreSQL and Ollama; static React build served locally. Multiple room actors share process but never state. Optional future Compose services `app`, `db`, `ollama` with named durable volumes, exact pinned images, DB readiness dependency and no public database/model ports. Compose is recommended, not a required deliverable or an existing file. No public hosting/CDN or external travel services.

Startup order: validate config/secrets → connect DB → verify migrations → hydrate room aggregates/active votes → resolve overdue votes idempotently → initialize retrieval/recommendation artifacts → mark gateway ready → serve frontend. Model unavailable degrades AI generator but need not block non-AI readiness; health exposes model status without a secret. Binding loopback is default; private LAN requires TLS/WSS, exact origins and Secure cookies. Do not add multiple workers without redesigning room ownership and cross-process fan-out.

## Health and observability

`/health/live` reports process alive; `/health/ready` checks DB/schema and recoverable room state, returns 503 during recovery; `/health/gateway` checks actor heartbeat/queue backlog/subscription service. Model health is separate so fallback isn't mistaken for a complete outage. No sensitive details on probes. Structured logs: timestamp, level, room/session correlationId, command/event IDs, actor pseudonym, status, queue/flush/model duration and source IDs; no raw JWT/chat/question/model response.

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

Restore into isolated test database, apply compatible schema version, compare event counts/checksums, recompute budgets/analytics for known session, then point stopped application at restored DB and start with new epochs. Preserve immutable dataset versions referenced by trips. OPS-01 tests crash/outage/expired vote recovery; OPS-02 tests restore and recomputation. No backup/restore test has occurred. Performance measurements must state if backup/model training was running concurrently.
