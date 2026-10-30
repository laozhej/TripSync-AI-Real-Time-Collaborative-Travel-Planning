# TripSync AI — Master Implementation To-Do List

**Status:** Implementation Backlog & Milestone Tracking  
**Architecture Track:** Track A (FastAPI + Native WebSockets + PostgreSQL + SQLAlchemy async/asyncpg + Pytest + React)  
**Primary References:** [TASKS.md](TASKS.md) | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) | [ARCHITECTURE.md](ARCHITECTURE.md) | [DECISIONS.md](DECISIONS.md)

---

## Progress Overview

| Phase | Focus | Tasks | Priority | Status |
|---|---|---|---|---|
| **Phase 1 (Week 1)** | Foundation & First Thin Slice | TASK-001 – TASK-007 | P0 | Complete for first-slice acceptance; see [evidence](PHASE_1_EVIDENCE.md) |
| **Phase 2 (Week 2)** | Board State Machine, Presence & AI Concierge | TASK-008 – TASK-013 | P0 / P1 | Pending |
| **Phase 3 (Week 3)** | Exact Budgets, Contested Voting & Personalization | TASK-014 – TASK-020 | P0 / P1 | Pending |
| **Phase 4 (Week 4)** | Hardening, Performance Benchmarking & Evidence | TASK-021 – TASK-025 | P0 | Pending |

---

## Phase 1: Foundation & First Vertical Slice (Week 1)
> **Milestone Objective:** A working vertical slice: **Authentication → Create Trip Room → Second Participant Joins → Server-Authoritative Board Synchronization**.

- [x] **TASK-001: Baseline Decisions & Source Traceability**
  - **Priority:** P0 | **Week:** W1 | **Depends on:** None
  - **Requirements:** REQ-001, REQ-033
  - **Planned Files:** `docs/DECISIONS.md`, `docs/PROJECT_REQUIREMENTS.md`, `docs/TRACEABILITY_MATRIX.md`
  - **Acceptance:** Finalize Track A Python stack baseline; verify and cross-link all PRD requirements (§§4, 8, 11, 14); ensure documentation precedes scaffolding.
  - **Verification:** `EV-DOC`

- [x] **TASK-002: Project Scaffolding & Environment Locks**
  - **Priority:** P0 | **Week:** W1 | **Depends on:** TASK-001
  - **Requirements:** REQ-001, REQ-028, REQ-032
  - **Planned Files:** `backend/`, `frontend/`, `backend/alembic/`, `backend/requirements.lock`, `.env.example`, `.gitignore`
  - **Acceptance:** Initialize FastAPI backend layout with Uvicorn; scaffold React/Vite frontend; configure Alembic and apply migrations M001–M004; implement `/health/live` and `/health/ready` endpoints; ensure zero hardcoded secrets.
  - **Verification:** `OPS-01`, `EV-DOC`

- [x] **TASK-003: Authentication, Session Management & RBAC Policies**
  - **Priority:** P0 | **Week:** W1 | **Depends on:** TASK-002
  - **Requirements:** REQ-002, REQ-003, REQ-029
  - **Planned Files:** `backend/app/auth/`, `backend/app/api/auth.py`, `frontend/src/auth/`
  - **Acceptance:** Argon2id password hashing; 15-minute access JWT and 7-day HttpOnly refresh token rotation (`POST /api/v1/auth/refresh`); HttpOnly cookie handshake for WebSockets (`/ws`); 4-role permission enforcement (Viewer, Planner, Leader, Admin) across both HTTP and sockets.
  - **Verification:** `AUTH-01`, `SEC-01`, `SEC-02`

- [x] **TASK-004: Authored Destination & Venue Catalog Ingestion**
  - **Priority:** P0 | **Week:** W1 | **Depends on:** TASK-002, TASK-003
  - **Requirements:** REQ-011, REQ-025
  - **Planned Files:** `data/destinations/lisbon.json`, `backend/app/datasets/`
  - **Acceptance:** Author synthetic Lisbon dataset covering all constraint types (all 4 dietary tags, price tiers, hours with overnight offsets, transit edges, dated weather); implement schema validator and PostgreSQL `tsvector`/GIN full-text search index.
  - **Verification:** `DATA-01`, `DATA-02`

- [x] **TASK-005: Trip Creation, Invites & Membership Management**
  - **Priority:** P0 | **Week:** W1 | **Depends on:** TASK-003, TASK-004
  - **Requirements:** REQ-004, REQ-026
  - **Planned Files:** `backend/app/api/trips.py`, `frontend/src/trips/`
  - **Acceptance:** Trip creation assigns creator as Leader; cryptographically secure invite tokens with expiration and max-uses; second authenticated user redeems invite and joins room; enforce room capacity limits (2–50).
  - **Verification:** `ROOM-01`

- [x] **TASK-006: Server-Authoritative Room Actor & Atomic Snapshot Slice**
  - **Priority:** P0 | **Week:** W1 | **Depends on:** TASK-005
  - **Requirements:** REQ-005, REQ-008, REQ-027
  - **Planned Files:** `backend/app/rooms/`, `backend/app/realtime/`, `frontend/src/board/`
  - **Acceptance:** In-memory per-room actor manages command sequencing; native WebSocket connection delivers full snapshot within 2 s; two concurrent sessions observe server-accepted pins; server is sole state authority.
  - **Verification:** `BOARD-01`, `SYNC-01`

- [x] **TASK-007: Record First Slice Tests & Setup Evidence**
  - **Priority:** P0 | **Week:** W1 | **Depends on:** TASK-006
  - **Requirements:** REQ-031, REQ-032
  - **Planned Files:** `backend/tests/integration/`, `README.md`
  - **Acceptance:** Integration tests verify complete sequence: Auth → Create Room → Second User Joins → Sync Pin; document verified commands in `README.md` without exposing credentials.
  - **Verification:** `E2E-01`, `EV-DOC`

---

## Phase 2: Board State Machine, Presence & AI Concierge (Week 2)
> **Milestone Objective:** Lifecycle-correct collaborative canvas, optimistic concurrency control (CAS), presence, and grounded RAG suggestions.

- [ ] **TASK-008: Full Board Lifecycle, CAS Concurrency & Stale Rejection**
  - **Priority:** P0 | **Week:** W2 | **Depends on:** TASK-007
  - **Requirements:** REQ-005, REQ-006
  - **Planned Files:** `backend/app/board/`, `frontend/src/board/`
  - **Acceptance:** Implement day/time grid with pin, move, remove, and item lock; enforce `positionVersion` compare-and-reject (first server arrival increments version; stale arrival returns explicit conflict notice; no explicit DB row locks); lifecycle transitions `Drafting` → `Voting` → `Locked`.
  - **Verification:** `BOARD-01`, `BOARD-02`

- [ ] **TASK-009: Presence, Connection Quality, Reconnection & Leader Moderation**
  - **Priority:** P0 | **Week:** W2 | **Depends on:** TASK-008
  - **Requirements:** REQ-008, REQ-009, REQ-010
  - **Planned Files:** `backend/app/rooms/`, `frontend/src/board/`
  - **Acceptance:** Real-time presence updates (`trip.presence.update`); handle client drops with seamless token refresh and snapshot reconnect; detect Leader disconnect and freeze restricted actions; support Leader mute, member remove, room lock/unlock, and atomic leadership transfer.
  - **Verification:** `SYNC-01`, `ROOM-01`, `SEC-02`

- [ ] **TASK-010: Durable Chat, Typing Indicators & Emoji Reactions**
  - **Priority:** P1 | **Week:** W2 | **Depends on:** TASK-003, TASK-006
  - **Requirements:** REQ-007
  - **Planned Files:** `backend/app/realtime/`, `frontend/src/chat/`
  - **Acceptance:** Persisted chat history in `chat_messages`; optimistic emoji reactions with idempotent upsert/remove; 3-second auto-expiring typing indicator; muted members rejected from posting chat.
  - **Verification:** `CHAT-01`

- [ ] **TASK-011: Batch Persistence, Room Epochs & Crash Recovery**
  - **Priority:** P0 | **Week:** W2 | **Depends on:** TASK-008
  - **Requirements:** REQ-027, REQ-028
  - **Planned Files:** `backend/app/persistence/`, `backend/app/rooms/`
  - **Acceptance:** 100 ms batched DB flush; explicit volatile vs. committed sequence acknowledgements (`trip.command.ack` and `trip.persistence.committed`); DB failure freezes mutations; server crash restarts with durable state, issues new `roomEpoch`, and prompts full client snapshot resync.
  - **Verification:** `OPS-01`, `SYNC-01`

- [ ] **TASK-012: Deterministic Hard Filter Matcher & Candidate Ranking**
  - **Priority:** P0 | **Week:** W2 | **Depends on:** TASK-004, TASK-008
  - **Requirements:** REQ-012, REQ-013, REQ-014, REQ-015, REQ-016
  - **Planned Files:** `backend/app/concierge/constraints.py`, `backend/tests/unit/`
  - **Acceptance:** Implement 4 strict pre-filters:
    1. Category price ceiling per person;
    2. Attendee dietary constraint union (every attendee tag must be satisfied);
    3. Operating hours matching with 30-min buffer and timezone conversion;
    4. Anchored Haversine radius (default 2 km).
    Rank valid candidates using `0.4*Proximity + 0.3*Rating + 0.3*BudgetHeadroom`. 100% valid results across ≥20 boundary test cases.
  - **Verification:** `AI-01`, `AI-07`

- [ ] **TASK-013: Grounded Ollama RAG, Source Citations & Safe Fallback**
  - **Priority:** P0 | **Week:** W2 | **Depends on:** TASK-003, TASK-012
  - **Requirements:** REQ-017, REQ-021
  - **Planned Files:** `backend/app/concierge/`, `frontend/src/concierge/`
  - **Acceptance:** Asynchronous HTTP call to local Ollama (`POST /api/chat`, e.g., `llama3.2:3b`) with JSON schema enforcement; validate candidate IDs and reason codes against source allowlist; render facts deterministically with canonical citations (`venue:<id>@<version>`); deterministic grounded fallback on model timeout (>2.5 s), schema error, or zero valid candidates.
  - **Verification:** `AI-02` through `AI-06`

---

## Phase 3: Exact Budgets, Contested Voting & Personalization (Week 3)
> **Milestone Objective:** Exact integer cents split engine, contested elections, synthetic recommendation engine, dashboard, and Admin dataset ingestion.

- [ ] **TASK-014: Exact Budget Math & Running Allocations**
  - **Priority:** P0 | **Week:** W3 | **Depends on:** TASK-008
  - **Requirements:** REQ-020
  - **Planned Files:** `backend/app/budget/`, `frontend/src/budget/`
  - **Acceptance:** Integer minor-unit calculations (`bigint`, EUR cents); even split with remainder cents assigned by stable ascending user IDs; weighted split with descending fractional remainder distribution; separate committed (Locked) from proposed totals; slot reservation for open voting candidates.
  - **Verification:** `BUD-01`, `BUD-02`, `BUD-03`

- [ ] **TASK-015: Idempotent Schedule Overlap & Budget Breach Conflict Detection**
  - **Priority:** P0 | **Week:** W3 | **Depends on:** TASK-011, TASK-014
  - **Requirements:** REQ-018
  - **Planned Files:** `backend/app/concierge/conflicts.py`, `frontend/src/board/`
  - **Acceptance:** Conflict detector identifying half-open time overlaps for shared attendees and total/category budget breaches; assign unique conflict fingerprints; notify clients within 1 s in ≥95% of cases; auto-resolve when underlying items are edited or removed.
  - **Verification:** `CONFLICT-01`

- [ ] **TASK-016: Timed Contested-Slot Voting & Durable Resolution**
  - **Priority:** P0 | **Week:** W3 | **Depends on:** TASK-009, TASK-014, TASK-015
  - **Requirements:** REQ-019
  - **Planned Files:** `backend/app/voting/`, `frontend/src/votes/`
  - **Acceptance:** Open timed election (Leader manual or system auto-open for identical contested slots); eligible voter snapshot; changeable ballots before deadline (default 60 s); deterministic tiebreak by ascending venue ID; atomic winner application (`Locked`), loser archiving (`Drafting` archive), and budget recomputation.
  - **Verification:** `VOTE-01` through `VOTE-04`

- [ ] **TASK-017: Synthetic Interaction Generator & Hybrid Recommendation Engine**
  - **Priority:** P1 | **Week:** W3 | **Depends on:** TASK-004, TASK-014
  - **Requirements:** REQ-023
  - **Planned Files:** `backend/app/recommendations/`, `data/interactions/`
  - **Acceptance:** Scripted generator creating realistic synthetic user interactions (view, like, pin, lock, co-travel); item-item CF + content cosine hybrid model; CLI batch training and atomic model promotion; zero-redeploy serving cache invalidation; evaluate on chronological held-out test split targeting Precision@5 ≥ 0.6.
  - **Verification:** `REC-01` through `REC-05`

- [ ] **TASK-018: User Dashboard, Preferences & Active Room Rejoin**
  - **Priority:** P1 | **Week:** W3 | **Depends on:** TASK-009, TASK-017
  - **Requirements:** REQ-022
  - **Planned Files:** `frontend/src/dashboard/`, `backend/app/api/me.py`
  - **Acceptance:** User dashboard displaying joined trip history, active room rejoin links, and derived/declared preference profile editor.
  - **Verification:** `E2E-01`, `SEC-03`

- [ ] **TASK-019: Session Analytics & Audit Ledger Reconciliation**
  - **Priority:** P0 | **Week:** W3 | **Depends on:** TASK-011, TASK-015, TASK-016
  - **Requirements:** REQ-024
  - **Planned Files:** `backend/app/analytics/`, `frontend/src/dashboard/`
  - **Acceptance:** Record planning session start/end, peak concurrency (distinct connected Planners/Leaders), AI question counts, flagged/resolved conflicts, and final budgets; reconcile metrics 100% against an independent manual audit ledger.
  - **Verification:** `ANA-01`

- [ ] **TASK-020: Admin Upload Portal, Staging & Atomic Dataset Activation**
  - **Priority:** P0 | **Week:** W3 | **Depends on:** TASK-003, TASK-004
  - **Requirements:** REQ-011, REQ-025
  - **Planned Files:** `frontend/src/admin/`, `backend/app/datasets/`
  - **Acceptance:** Admin-only upload portal (`POST /api/v1/admin/datasets`) with schema validation; bounded error reporting; atomic activation of immutable versions; active trips remain pinned to their initial dataset version.
  - **Verification:** `DATA-01`, `DATA-02`, `DATA-03`, `SEC-04`

---

## Phase 4: Hardening, Performance Benchmarking & Evidence (Week 4)
> **Milestone Objective:** End-to-end integration, performance profiling, failure recovery validation, repeatable demo, and submission evidence packaging.

- [ ] **TASK-021: End-to-End Test Suite & Security Consolidation**
  - **Priority:** P0 | **Week:** W4 | **Depends on:** TASK-013, TASK-016, TASK-018, TASK-019, TASK-020
  - **Requirements:** REQ-003, REQ-029, REQ-031
  - **Planned Files:** `backend/tests/`, `frontend/tests/`, `http/`
  - **Acceptance:** Complete security verification matrix (token expiry, refresh reuse, 4 roles across HTTP/WS, cross-tenant isolation, stored XSS, SQL injection, prompt injection defense, secret leak scanning).
  - **Verification:** `SEC-01` through `SEC-06`, `E2E-01`

- [ ] **TASK-022: Performance Benchmarking & Real Model Measurements**
  - **Priority:** P0 | **Week:** W4 | **Depends on:** TASK-011, TASK-021
  - **Requirements:** REQ-030, REQ-031
  - **Planned Files:** `backend/tests/load/`, `evidence/performance/`
  - **Acceptance:** Execute load tests with 5–10 concurrent clients and multiple rooms; record raw empirical distributions (P50, P95, max) for:
    - Board sync drift (<100 ms)
    - Non-AI HTTP P95 (<200 ms)
    - Real Ollama RAG P95 (<3 s)
    - Server fan-out (<500 ms)
    - Join snapshot (≤2 s)
    - Conflict detection (≤1 s in ≥95% cases).
  - **Verification:** `PERF-01`, `PERF-02`, `PERF-03`

- [ ] **TASK-023: Disaster Recovery, Database Outages & Backup/Restore Drills**
  - **Priority:** P0 | **Week:** W4 | **Depends on:** TASK-011, TASK-021
  - **Requirements:** REQ-027, REQ-028
  - **Planned Files:** `evidence/operations/`, `docs/DEPLOYMENT_AND_OPERATIONS.md`
  - **Acceptance:** Verify system recovery across failure modes: crash before batch commit, crash during election, database connectivity loss, and PostgreSQL logical backup/restore with budget and analytics reconciliation.
  - **Verification:** `OPS-01`, `OPS-02`

- [ ] **TASK-024: Repeatable Demonstration Script Execution**
  - **Priority:** P0 | **Week:** W4 | **Depends on:** TASK-022, TASK-023
  - **Requirements:** REQ-026, REQ-032
  - **Planned Files:** `README.md`, `evidence/demo/`
  - **Acceptance:** Execute the full 10-step demonstration workflow from `DEMO_AND_SUBMISSION.md` (concurrent edits, stale write rejection, reconnect, chat, grounded AI, conflict resolution, vote, exact split, dataset update) from a clean environment.
  - **Verification:** `E2E-01`, `EV-DOC`

- [ ] **TASK-025: Final Submission Package, Retrospective & Documentation Review**
  - **Priority:** P0 | **Week:** W4 | **Depends on:** TASK-024
  - **Requirements:** REQ-001, REQ-031, REQ-032
  - **Planned Files:** `docs/DEMO_AND_SUBMISSION.md`, `evidence/`
  - **Acceptance:** Populate all evidence templates; verify clean Git commit history; document honest retrospective and limitations; ensure complete consistency between code, schemas, and API documentation.
  - **Verification:** `EV-DOC`

---

## Verification & Test Catalog Reference

| Test Suite | Focus Area | Covering Tasks |
|---|---|---|
| `AUTH-01` | Register, login, token refresh, logout, password hashing | TASK-003 |
| `ROOM-01` | Trip creation, invite lifecycle, capacity bounds, room lock | TASK-005, TASK-009 |
| `BOARD-01..02` | Board lifecycle, CAS version rejection, concurrent convergence | TASK-006, TASK-008 |
| `CHAT-01` | Durable chat, typing indicator expiration, mute enforcement | TASK-010 |
| `SYNC-01` | Snapshot delivery, reconnect, sequence gap handling, epoch recovery | TASK-006, TASK-009, TASK-011 |
| `AI-01..07` | 4 hard filters, scoring, Ollama RAG, source citations, fallback | TASK-012, TASK-013 |
| `BUD-01..03` | Integer cents math, even/weighted split remainders, reservations | TASK-014 |
| `VOTE-01..04` | Ballot submission, tiebreaking, deadline resolution, crash recovery | TASK-016 |
| `CONFLICT-01` | Schedule overlap and budget breach detection and resolution | TASK-015 |
| `REC-01..05` | Hybrid recommendation training, cold start, Precision@5 ≥ 0.6 | TASK-017 |
| `ANA-01` | Independent session ledger audit and metric reconciliation | TASK-019 |
| `DATA-01..03` | Dataset schema validation, boundary fixtures, atomic activation | TASK-004, TASK-020 |
| `SEC-01..06` | Authentication security, 4-role matrix, cross-tenant isolation, injections | TASK-003, TASK-021 |
| `OPS-01..02` | Crash recovery, overdue election handling, backup and restore | TASK-011, TASK-023 |
| `PERF-01..03` | Real latency benchmarks, fan-out, sync drift, model inference time | TASK-022 |
| `E2E-01` | Two-browser end-to-end collaboration demonstration | TASK-007, TASK-021, TASK-024 |
| `EV-DOC` | Source traceability, reproducible setup, documentation consistency | TASK-001, TASK-002, TASK-024, TASK-025 |
