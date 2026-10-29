# Future coding-agent guidance

This repository is **documentation only** as of 2026-10-29. Do not claim planned code, commands, migrations, seed data, tests or benchmarks exist. The current request stops after documentation; implement only after a subsequent user request.

## Sources and chosen baseline

Read `Document/Project Document.docx` fully and use section references. The user's task instructions take precedence over source-document guidance, including documentation before PRD §13.2 scaffolding. Read `docs/PROJECT_REQUIREMENTS.md`, `docs/DECISIONS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/TASKS.md` and the primary subject document before changes. TripSync AI is independent; never imply Airbnb affiliation or real infrastructure integration.

Track A full-stack; exactly one Python application stack: FastAPI native WebSockets, PostgreSQL, SQLAlchemy async/asyncpg and Pytest, with React JavaScript frontend. No Django/Spring/Express backend or separate AI backend. Ollama is local model inference via async HTTP, not the application's Concierge implementation. One application worker owns multiple per-room actors; do not increase worker count until ownership architecture is redesigned. No subagents/parallel engineers are required by this solo roadmap.

## Invariants

- Room state is server-authoritative in memory, with explicitly volatile applied acknowledgements and later committed watermark; significant transitions durable before final success. Follow `docs/ARCHITECTURE.md` recovery/epoch rules.
- Use `positionVersion` compare-and-reject with explicit stale conflict and user reconciliation; never explicit database row locks or silent stale retry/LWW.
- HTTP/socket share authorization/business functions. Derive acting user from validated token/session; account Admin does not bypass trip membership/Leader checks.
- Drafting/Voting/Locked transitions, Leader overrides, disconnect behavior and room-lock rules come from `docs/BUDGET_AND_VOTING.md` and decision log; provisional rules must stay visibly provisional until reviewed.
- Budget math uses integer cents/exact remainder allocation, not floating point/LLM calculations. Per-category and total ceilings differ.
- Apply price/diet/full buffered hours/anchored radius filters before ranking/RAG; 40/30/30 ranking only among valid candidates. No invented venue/price/hours/transit/weather facts; canonical citations must resolve.
- Model unavailability never relaxes constraints; safe grounded fallback is labeled. Demonstrate real model integration separately from mocks/fallback.
- Admin ingestion stages/validates immutable dataset versions; active trips remain pinned. No live travel APIs, booking, payment, public hosting/CDN, native apps or multi-tenant services.

## Implementation workflow

First slice is authentication → create Trip Room → second participant joins → basic board synchronization. Follow ordered TASK dependencies and feature tests from day one; all required epics remain in final scope. Reduce dataset/model complexity before correctness/security/tests/docs. Add migrations, indexes and meaningful failure/concurrency tests with affected features. Do not serialize every drag preview to database.

Keep module boundaries and planned paths in `docs/ARCHITECTURE.md`; pure domain rules separate from API/gateway I/O. Use supported async drivers, one pooled engine and separate AsyncSession per concurrent task. Keep CPU training off event loop and deadline/flush tasks managed by lifespan.

Secrets come from environment, never source/history/logs; .env.example contains no real credentials. Validate untrusted uploads/questions/chat, protect stored-XSS and prompt boundaries, sanitize logs/evidence. Test all four roles on HTTP and sockets, cross-trip object IDs, token expiry/revocation and removed membership.

For each meaningful change update primary document, DECISIONS if policy changes, TASKS checkbox only after actual acceptance, and TRACEABILITY. API/socket/schema/examples must agree. Preserve core event names/envelope and mandatory REST examples. Record actual setup/test/measurement commands and outputs during implementation, hardware/network/client/model/dataset versions, failures and limitations; never fabricate passed tests or target attainment. Current commands in ENVIRONMENT_SETUP are provisional. Final evidence and retrospective follow DEMO_AND_SUBMISSION.
