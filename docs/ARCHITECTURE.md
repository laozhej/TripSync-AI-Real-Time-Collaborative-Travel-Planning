# Architecture

Track A design and partial implementation; PRD §§7.1,9.3–9.4,10. The implemented first-slice boundaries and limitations are noted below. [Decisions](DECISIONS.md) distinguishes selected boundaries from provisional policies.

## Components

One FastAPI process with one Uvicorn worker owns API routes and native WebSocket connections. Room actors are keyed by trip ID, so no single-room assumption exists. PostgreSQL is the durable store; disk holds imported files, local assets, backups and versioned recommendation artifacts. A hosted API or local open-source model may supply inference, as permitted by PRD §8.1. The user selected local open-source inference; the current adapter calls Qwen2.5 1.5B through loopback Ollama HTTP. It does not create a second application backend. All matching, retrieval, prompt construction and validation live in Python modules.

```mermaid
flowchart LR
  UI[React browser: board/chat/dashboard/admin] -->|REST + JWT| API[FastAPI API]
  UI <-->|native WebSocket + JWT cookie| GW[Board gateway]
  API --> AUTH[Identity and membership policy]
  GW --> AUTH
  API --> ROOM[Per-room authoritative actor]
  GW --> ROOM
  ROOM --> BOARD[Board state machine]
  ROOM --> VOTE[Voting and exact budget engine]
  ROOM --> CHECK[Conflict detection]
  API --> AI[Constraint matcher + retrieval + RAG validation]
  AI --> MODEL[Local Qwen2.5 inference via Ollama HTTP]
  API --> REC[Content + collaborative recommendations]
  API --> INGEST[Dataset validation and indexing]
  ROOM --> FLUSH[Batch persistence and durable transitions]
  FLUSH --> DB[(PostgreSQL)]
  AI --> DB
  REC --> DB
  INGEST --> DB
  ROOM --> LOG[Analytics event ledger]
  LOG --> DB
```

## Module boundaries and planned files

| Module | Owns | Does not own | Proposed path |
|---|---|---|---|
| API | Pydantic request/response, HTTP errors, dependency injection | Business decisions | `backend/app/api/` |
| Auth/policy | JWT, sessions, membership capability evaluation | Board mutation | `backend/app/auth/` |
| Gateway | Socket auth, input limits, subscriptions, envelopes | Money or lifecycle rules | `backend/app/realtime/` |
| Room | Ordered commands, versions, in-memory aggregate and fan-out | Model calls | `backend/app/rooms/` |
| Board | Pure lifecycle transition/position validation | Socket I/O | `backend/app/board/` |
| Budget | Exact splits, ledger and ceiling evaluations | Model arithmetic | `backend/app/budget/` |
| Voting | Eligibility, deadlines, ballot/resolution and winner application | Permission bypass | `backend/app/voting/` |
| Constraints | Price/diet/hours/radius eligibility and score | Natural-language authority | `backend/app/concierge/constraints.py` |
| RAG | Retrieval, citation allowlist, model adapter, validated response | Inventing facts | `backend/app/concierge/` |
| Recommendations | Interaction features, content/CF training and serving | Hard Concierge filtering | `backend/app/recommendations/` |
| Analytics | Event definitions, idempotent projections and reconciliation | Client-reported truth | `backend/app/analytics/` |
| Ingestion | Admin staging, atomic activation, immutable dataset versions | Executing uploaded text | `backend/app/datasets/` |
| Persistence | SQLAlchemy repositories, migrations, unit of work | Alternate room authority | `backend/app/persistence/` |

These paths are plans, not files claimed as implemented. Both HTTP and socket commands invoke the same policy/domain functions. No Redis, message broker or vector database is necessary for one private process.

## Concurrency and state flow

```mermaid
sequenceDiagram
  participant A as Planner A
  participant R as Room actor
  participant D as PostgreSQL
  participant B as Planner B
  A->>R: move item expected positionVersion=4
  R->>R: authorize; compare; apply positionVersion=5
  R-->>A: ack applied, durable=false, roomSeq=31
  R-->>B: board.update version=5
  B->>R: move item expected positionVersion=4
  R-->>B: edit.conflict currentVersion=5 + authoritative item
  R->>D: 100 ms batch, conditional durable-base update + event ledger
  D-->>R: commit
  R-->>A: persistence.committed through roomSeq=31
```

One actor processes commands serially in memory, including while a significant commit is pending. This is not a database row lock. A batch can coalesce item v4→v7 into a conditional update from durable v4 to v7 while retaining accepted command ledger entries. A failed CAS indicates unexpected writer or state corruption: freeze that room, reload durable aggregate and force resync. Never overwrite a mismatched durable base. Continuous drag positions remain client previews; send final drop commands, not every pixel.

Each accepted mutation advances `roomSeq`; item mutation advances `positionVersion`, including lifecycle and attendee/cost edits. A new `roomEpoch` on process recovery distinguishes a restored sequence from a previously observed volatile future. Unique `(tripId, commandId)` records enable deduplication of committed commands; volatile commands may disappear in a crash and must not be silently replayed after a new epoch.

## Persistence and recovery

Default batch 100 ms is provisional. Memory acknowledgement is explicitly `applied, durable=false`; it can be lost until the commit watermark. Pin/move/remove use this path. Significant transitions—lock, vote open/cast/resolve, transfer, settings, membership and moderation—flush all earlier room changes in the same transaction before durable acknowledgement and broadcast. Chat/reactions also commit before success. Reads/snapshots include `committedSeq`, so clients can distinguish visible state from durable state. Analytics logs accepted domain events transactionally with persisted state, excluding ephemeral typing/pings.

On DB outage: mark readiness false, freeze mutations for affected rooms, announce persistence degradation, and retain bounded pending data. Read-only memory snapshots identify volatility. On uncertain transaction outcome, query by command ID before retrying. If recovery cannot prove state, reload committed snapshot/event ledger, advance epoch and notify clients of rollback. The nominal crash window is one flush interval plus DB delay, not a guaranteed 100 ms bound. Never acknowledge volatile events as durable.

On startup hydrate snapshots/rows and persisted active votes before readiness; resolve expired votes once by unique resolution key. Store deadline in UTC; a restart cannot extend the election. Reconstruct chat and aggregates from durable records. On clean shutdown stop accepting writes, drain/flush, close sockets with reconnect advice; enforce timeout and log uncommitted watermark. See [operations](DEPLOYMENT_AND_OPERATIONS.md).

## Background work and deployment

Managed lifespan tasks own flush scheduling, vote deadlines, presence expiry and conflict evaluation. Avoid untracked request background tasks for critical recovery work. Overlap/budget checks run after each accepted change; bounded per-room queue plus version checks discard obsolete results. Small pure checks run inline; costly model I/O uses an async HTTP client; CPU-bound training/index rebuild uses an executor and atomic artifact swap. Never share an AsyncSession across concurrent tasks.

One private host serves bundled React assets, API and gateway; PostgreSQL binds loopback/private network. A local model, if selected, also binds privately; a hosted provider uses its authenticated API. Use TLS/WSS when testing across machines. Gateway health measures actor loop freshness and queue status; readiness additionally checks DB/schema. Metrics: command queue depth, rejected stale versions, mutation latency, flush lag, socket lag/disconnects, model latency/fallback and constraint violations. Correlation IDs appear in safe structured logs. Capacity is configurable up to the 50-planner design target; actual performance remains unmeasured (§§10.2,14.1).

## Implementation status — 2026-10-30

The first slice uses a single pooled async engine, room actors, native WebSockets and basic liveness, schema readiness and gateway probes. Later architecture on this page remains planned. See [evidence](PHASE_1_EVIDENCE.md).

The first-slice room actor is wired to membership authorization, batched persistence and WebSocket snapshots; later lifecycle and recovery drills remain pending. See [evidence](PHASE_1_EVIDENCE.md).

The first pin/snapshot actor now maintains in-memory authoritative items and batches pending pins to PostgreSQL, with volatile applied acknowledgements, committed watermark, freeze on batch failure and a new epoch on reload. Membership joining and Leader invite changes persist pending pins and the significant change in the same transaction under the room actor lock; full recovery drills and later-feature snapshot state remain outstanding. See [evidence](PHASE_1_EVIDENCE.md).

## Phase 2 implementation boundaries — 2026-10-31

Implemented code uses `app/realtime/rooms.py` for aggregate ownership, batching/unit-of-work and snapshots; `app/rooms/moderation.py` for durable moderation; `app/board/lifecycle.py` for pure item/vote lifecycle rules; and `app/concierge/{constraints,preferences,rag,service}.py` for authorized rule resolution, retrieval and generation. API transport lives in `app/api/concierge.py` and the native gateway; both invoke the same domain services. Planned persistence/voting package paths in the table are not claimed as existing services.

One pooled SQLAlchemy async engine supplies a separate connection/transaction to each concurrent operation. The current implementation uses SQLAlchemy Core AsyncConnection rather than sharing ORM AsyncSessions. Two bounded model calls per worker are permitted; when occupied, another eligible request uses a labeled grounded fallback. Model I/O runs outside the room lock. Context is captured under the room lock and revalidated before a durable answer is saved. In-flight identical questions share a ref-counted per-room lock; completed locks are removed. No user token, model free text or question is emitted to operational logs.

JSON logs whitelist event, trip/session IDs, roomEpoch, roomSeq, committedSeq, correlationId and UTC timestamp. Failed/uncertain commits freeze the room. Crash recovery reloads committed relational state and changes roomEpoch. The test-only recovery factory/file gate is not part of the production entry point. See [Phase 2 evidence](PHASE_2_EVIDENCE.md) for real process-kill, PostgreSQL-outage and lost-ack tests. Full backup restore, overdue elections and performance distributions remain later checks.

### Indian locale implementation

New UI trips select Bengaluru/INR/Asia-Kolkata. The display/input helper converts IST to offset-aware UTC instants and retains the destination-local dayIndex, including midnight crossing to the previous UTC day. Server validation continues to use IANA Asia/Kolkata. Actor budget events derive currency from the loaded trip; Concierge eligible choices carry the authorized trip currency to factual rendering. The schema accepts INR and legacy EUR, with trip creation requiring a matching dataset currency. No migration rewrites existing monetary values.

## Phase 3 boundaries (2026-11-01)

`app/budget/{engine,service}.py` owns pure exact splits and versioned split edits. `app/concierge/conflicts.py` owns pure fingerprints; `app/voting/service.py` persists elections/ballots/conflict transitions within the room transaction. `app/analytics/service.py` finalizes sessions. `app/recommendations/{engine,service,evaluate}.py` supplies content/CF training, serving and frozen evaluation. `app/api/phase3.py` is the HTTP adapter for these services plus dashboard/Admin operations. React components live under dashboard/votes/admin.

The managed 100-ms maintenance loop flushes rooms, checks deadlines and detects identical-slot contests. Significant services commit before advancing memory/publishing; PostgreSQL version predicates remain the unexpected-writer guard. Startup hydrates all open-vote rooms and resolves overdue rounds before readiness. If startup recovery fails, liveness stays available and readiness stays false until a successful restart. One worker remains mandatory. Conflict notifications use `trip.board.conflict` after commit and carry the committed state boundary; they do not allocate another room sequence.

Small versioned model artifacts live as checksummed JSONB in PostgreSQL, rather than a disk path. Training runs through `asyncio.to_thread`; promotion retires the previous active artifact and inserts the validated replacement atomically. Serving reads the active version on each request, so no redeploy/reload timer is needed. Fresh per-member history is reranked immediately and normalized scores are averaged for the current group.

## Phase 4 hardening and evidence boundaries

`app/transport.py` bounds HTTP input before parsing. Binary socket frames close explicitly; bounded subscriber queues disconnect slow readers without blocking healthy peers. No new application worker, backend service or schema migration is introduced. The model adapter now generates only one allowlisted source ID; complete filters and factual rendering stay in Python. See AI_TRAVEL_CONCIERGE.md for the internal prompt reduction and unchanged public contract.

Actual restore checks compare every public table's logical digest before application hydration, then verify new epochs and idempotent overdue-election recovery. Generated schema/index metadata and OpenAPI are in `evidence/contracts/`. The reference diagrams above explain the domain; these extracted contracts and Alembic revision 0011_phase3 are authoritative for the implemented physical fields. Load/client/model/browser measurements and scope limits are in PHASE_4_EVIDENCE.md.
