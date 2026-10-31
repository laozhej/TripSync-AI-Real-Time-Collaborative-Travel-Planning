# Four-week implementation roadmap

Planning baseline for one engineer, PRD §11. Focused full-time effort is assumed; completion is not guaranteed. Documentation is delivered before scaffolding by user instruction (deviation from §13.2). [TASKS](TASKS.md) is the ordered executable backlog; [traceability](TRACEABILITY_MATRIX.md) preserves every required feature. Independent tasks mean work can be interleaved by the same engineer, not parallel staffing.

## First working vertical slice

Exactly: **authentication → create Trip Room → second participant joins → basic server-authoritative board synchronization**. Prerequisites: selected stack/track, resolved dependency installation, DB migrations for identity/trips/membership/items/events, one valid destination, shared HTTP/socket authorization and a two-browser fixture. Deliver one pin and snapshot path before widening scope. It does not establish final submission completeness: chat, lifecycle, votes, budgets, grounded AI, personalization, analytics and all evidence remain required.

## Week 1 — Foundation (TASK-001–007)

Objective: reproducible environment plus first end-to-end slice. Prerequisites: read PRD and these docs; confirm safe defaults affecting identity/capacity. Frontend: register/login, create room/invite/join and minimal list canvas. Backend: FastAPI structure, JWT/refresh/session policy, four-role enforcement, venue catalog, trip/membership service and one pin/snapshot command. DB: M001–M004 minimal events/snapshots, unique membership/role constraints. Integration: PostgreSQL async driver and native sockets; model runtime smoke test can be interleaved independently before AI coding.

Planned files: `backend/app/{auth,api,rooms,realtime,persistence}/`, `backend/alembic/`, `frontend/src/{auth,trips,board}/`, `data/destinations/lisbon.json`, `backend/tests/integration/`. These are future paths. Tests/security: AUTH-01, SEC-01/02, DATA-01, ROOM-01, BOARD-01 from feature creation; verify Viewer pin rejected and actor identity ignored from body. Acceptance: clean DB migration, two users authenticate, creator Leader issues invite, second member receives snapshot and both observe a basic server-accepted pin. DoD: TASK-001–007 accepted, commands documented from actual runs, test output saved, no secret committed.

Risk: environment/auth setup consumes the week; reduce visual styling/seed count, retain coverage. Recovery: reset only disposable test DB, preserve source data; migration rollback/restore before destructive changes. Failed thin slice blocks later broadening. No production deployment dependency.

## Week 2 — Board & Concierge (TASK-008–013)

Objective: lifecycle-correct collaboration and one grounded request. Prerequisites: Week 1 slice, events/snapshot protocol, seeded constraints. Frontend: day/time canvas pin/move/remove/lock, stale-write notices, presence/quality/reconnect, chat/typing/reactions, Concierge form/result with citations. Backend: full state machine, CAS, deterministic Leader absence/moderation, batch commits/recovery, hard filters/scoring/retrieval and one actual model call. DB: complete chat/reactions/event persistence and venue search index; model connection through async HTTP only.

Files: `backend/app/{board,concierge,rooms,realtime}/`, `frontend/src/{board,chat,concierge}/`, tests `BOARD-*`, `CHAT-01`, `SYNC-01`, `AI-01..07`, `OPS-01`. Security: origin/token expiry, room-sensitive revalidation, injection/fallback/citation allowlist. Acceptance: simultaneous version-4 moves yield one v5 and explicit loser conflict; reconnect returns current lifecycle/budgets; ≥20 suggestion cases pass hard filters; one real grounded answer demonstrated with valid citations; no-candidate/model-outage paths work. DoD includes tests and documentation updates, not a claim performance targets already passed.

Risk: RAG latency/hardware and recovery semantics. Keep top-5 source context and simple lexical retrieval; choose smaller model only after smoke test. Recovery: retain last committed room/dataset, new epoch resync on crash; bad generation uses deterministic valid-only fallback. Do not replace final real-generation evidence with stub output.

## Week 3 — Voting & Personalization (TASK-014–020)

Objective: all three epics function end-to-end. Prerequisites: reliable item versions, server session ledger and valid metadata. Frontend: timed vote controls/tally, exact budget panel, conflict details/resolution, dashboard history/preferences/rejoin, recommendation rail, Admin upload and analytics. Backend: exact split engine, schedule/budget detector, durable election/application, synthetic interaction generation and simple content/CF hybrid, refresh/batch CLI, ledger projections and staged dataset activation. DB: M005–M006 with ballot uniqueness, conflict fingerprints, interaction/artifact indexes; immutable version activation.

Files: `backend/app/{budget,voting,recommendations,analytics,datasets}/`, `frontend/src/{votes,dashboard,admin}/`, `backend/tests/`, future model artifacts under ignored local data directory. Tests: BUD-01..03, VOTE-01..04, CONFLICT-01, REC-01..05, ANA-01, DATA-01..03 and permission matrix additions. Acceptance: exact manual budget fixtures agree 100%; one vote wins/applies everywhere; conflict opens/resolves; Admin invalid upload rejects clearly; interaction changes rail without redeploy; hybrid held-out evaluation and analytics reconciliation are runnable. Precision@5≥0.6 remains an evaluation gate; failure must be investigated and honestly reported, never tuned on test labels.

DoD: no required epic missing; draft demo works with real DB/model; feature tests pass with recorded output. Risks: broad Week 3 scope/synthetic evaluation leakage. Interleave dataset authoring and fixtures during earlier waits; reduce model complexity or dataset counts, not hybrid requirement. Recovery: transactionally cancel no-turnout votes, restart overdue ones once, keep prior dataset/artifact on invalid activation.

## Week 4 — Hardening & Evidence (TASK-021–025)

Objective: reproduce and report correctness/security/performance, update docs to actual build. Prerequisites: all required features present and feature tests already written. Frontend: verify multi-tab convergence, error/empty/reconnect states and responsive demo path. Backend/DB: integration/load fixtures, failure injection and restore, query index review, safe logs/health. No new framework/service integration planned.

Files: future `evidence/`, `backend/tests/load/`, HTTP collection, browser tests and updated docs. Run security matrix, complete test suite, 5–10 clients honestly reported plus multiple-room test, latency methodology in [testing](TESTING_STRATEGY.md), real model warm/cold measures, manual event-log reconciliation. Acceptance: required targets measured with raw samples/failures; no fake pass claims; demo includes stale edits/reconnect/AI/conflict/vote/roles; first-time setup reproduced on clean environment; retrospective lists actual omissions. DoD: final checklist in [submission](DEMO_AND_SUBMISSION.md), incremental Git history and sanitized evidence archive.

Risk: targets missed or required feature unfinished. Profile/reduce dataset/model work first; report missed target with raw evidence and limitation, never relabel required feature optional. Any scope deviation requires DECISIONS + requirements + traceability updates. Recovery: before demo back up known-good DB/artifacts; restore in isolated DB and test route; retain prior working revision and pin dependencies.

## Cross-week completion rules

Every task has a requirement link, acceptance check and test ID. Implement domain logic before transport duplication; HTTP/socket share services. Daily: read requirement → implement small vertical change → test positive/negative → update relevant primary doc → commit working increment and note done/blocked/next. No subagents or additional engineers assumed. P0 correctness/security and P1 required breadth both ship; P2 is optional tooling only, never a renamed required feature.

## Week 1 implementation status — 2026-10-30

TASK-001–007 first-slice acceptance is complete with the clean-database, integration and two-browser checks recorded in [evidence](PHASE_1_EVIDENCE.md). The current pin/snapshot slice does not implement the Week 2 lifecycle, presence/chat or Concierge, or later-phase functionality. The single join-to-snapshot timing is a local observation only, not a load-test result.

## Week 2 checkpoint status — 2026-10-31

TASK-008–013 meet the Week 2 checkpoint in PRD §11.1: live pin/move/lock, CAS conflicts, presence/moderation/reconnect, chat, tested hard matching and a real grounded constrained answer with citations. See PHASE_2_EVIDENCE.md for actual commands/results and boundary details. Pure Voting lifecycle rules are available for Week 3; contested elections, exact weighted budgets, conflict orchestration, recommendations/dashboard, analytics and Admin upload remain TASK-014–020. No final target attainment is implied.
