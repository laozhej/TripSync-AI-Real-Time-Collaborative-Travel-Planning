# TripSync AI — Real-Time Collaborative Travel Planning

Independent educational prototype, broader project title “Airbnb Real-Time AI Trip Planning & Collaboration Platform.” No Airbnb affiliation, account access or integration is implied. Source: [PRD](Document/Project%20Document.docx), v1.0 September 2026, especially §§4,8–15.

**Current status: Phases 1–4 implementation/evidence tasks are complete.** The shared board, local grounded Concierge, chat/presence, voting, exact budgets, conflicts, dashboard/recommendations, analytics and Admin ingestion have acceptance evidence. [Phase 4 evidence](docs/PHASE_4_EVIDENCE.md) records security/recovery/setup checks, final tests and measured limitations: strict maximum sync missed, cold inference falls back, and rendered-AI P95/50-planner capacity are unestablished. Frontend design checks remain in [frontend evidence](docs/FRONTEND_UI_EVIDENCE.md).

**Selected track: Track A (full-stack). Selected stack: Python — FastAPI native WebSockets, PostgreSQL, SQLAlchemy async/asyncpg, Pytest; React JavaScript client.** Exactly one application backend; Concierge/recommendations are local Python modules. The PRD permits hosted or local inference. The user selected local open-source inference: Qwen2.5 1.5B through a portable Ollama runtime; this is an implementation choice, not a PRD mandate. Concierge business logic belongs to the single Python application backend. Alternatives and trade-offs are in [decisions](docs/DECISIONS.md).

New trips follow the Indian baseline: **Bengaluru, INR (₹) and IST**. Prices and destination metadata are fictional project-authored samples. Existing trips retain their original currency. See [India localization evidence](docs/INDIA_LOCALIZATION_EVIDENCE.md).

## Intended scope

The final build includes a shared day-by-day activity/lodging board, invites and trip roles, Drafting/Voting/Locked lifecycle, version-checked edits, chat/typing/reactions, presence/reconnect, Leader moderation, exact budgets and contested votes. The Concierge filters authored metadata before ranking and RAG generation, cites sources, flags schedule/budget conflicts and handles no-match/model outages safely. Dashboard/history/preferences, hybrid content+collaborative recommendations, session analytics and Admin dataset upload complete the three epics (§6).

Private/local use by one operator, one engineer, four-week baseline. No booking, payments, live travel APIs, native app, public hosting/CDN or multi-tenant infrastructure. At least one fully authored destination covers all constraint types. Required functionality is not excluded as an “MVP.” The first vertical slice is only the first milestone.

## Start here

1. Read [requirements](docs/PROJECT_REQUIREMENTS.md) and [provisional decisions](docs/DECISIONS.md).
2. Follow the [four-week plan](docs/IMPLEMENTATION_PLAN.md) and [25-task backlog](docs/TASKS.md).
3. First implementation slice: **authentication → create Trip Room → second participant joins → basic server-authoritative board synchronization**. Prerequisites: stack setup/locks, identity/membership/item migrations, one destination and shared socket/HTTP policy.
4. Follow the [setup/run/test commands](docs/ENVIRONMENT_SETUP.md), including local-model startup and migrations through `0011_phase3`. Actual exercised versions/results are in [Phase 2 evidence](docs/PHASE_2_EVIDENCE.md); final clean-setup/submission results are in Phase 4 evidence.
5. During implementation use Pytest/HTTP/socket/browser tests from feature creation, then collect actual evidence using the [demo/submission path](docs/DEMO_AND_SUBMISSION.md). See the recorded checks and limitations in the implementation evidence.

Weeks: 1 foundation + thin slice; 2 board and Concierge; 3 voting/personalization/analytics/Admin; 4 hardening/measurements/demo. High risks are Week 3 breadth, local model P95 <3 s, synchronization timing, batched durability and synthetic recommendation evaluation. Reduce dataset/model complexity before correctness, security, tests or documentation. See the decision log for voting eligibility/ties, room locking, Leader absence, money/time defaults and crash-loss limits needing review.

## FAQ

### Are the displayed prices real, and how do I report an inconsistency?

Prices, venue details, transit and weather in the sample datasets are fictional, project-authored demonstration data, not live quotes or booking offers; the current Bengaluru sample uses INR, while existing trips keep their original currency and dataset version. See the [current Indian sample](docs/DATASET_GUIDE.md#current-indian-sample) and [dataset version rules](docs/DATASET_GUIDE.md#phase-3-admin-ingestion).

If a displayed price, budget calculation or Concierge citation disagrees with its sample data, [open an issue using the issue form](https://github.com/ravadakaran/TripSync-AI-Real-Time-Collaborative-Travel-Planning/issues/new). Include the destination/currency, venue name or source ID, dataset version if known, page, steps, expected and actual amounts, and relevant attendee/split settings. For example: “In a new Bengaluru/INR trip, add Synthetic City Museum for one attendee with an even split: the catalog shows ₹200.00 but the itinerary shows ₹20,000.00.” This is an example report, not a known defect; add your own browser/version and sanitized screenshot, omitting credentials, invitation codes and personal data.

## Documentation index

| Document | Primary subject |
|---|---|
| [Requirements](docs/PROJECT_REQUIREMENTS.md) | REQ-001–033, roles, journeys, constraints |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Four-week gates, prerequisites, risks/recovery |
| [Architecture](docs/ARCHITECTURE.md) | Modules, diagrams, in-memory authority, persistence |
| [Database schema](docs/DATABASE_SCHEMA.md) | Entities/ER/indexes/migrations and document comparison |
| [REST API](docs/API_SPECIFICATION.md) | Routes/access/schema/errors and mandatory examples |
| [WebSocket protocol](docs/WEBSOCKET_PROTOCOL.md) | Required envelope/events, commands, versions/reconnect |
| [AI Concierge](docs/AI_TRAVEL_CONCIERGE.md) | Hard filters/scoring/retrieval/model/citations/fallback |
| [Budget and voting](docs/BUDGET_AND_VOTING.md) | Exact cents, lifecycle, election and winner application |
| [Recommendations](docs/RECOMMENDATION_ENGINE.md) | Content+CF, refresh and held-out Precision@5 |
| [Dataset guide](docs/DATASET_GUIDE.md) | Authored JSON/YAML, provenance, validation/coverage |
| [Testing](docs/TESTING_STRATEGY.md) | Planned assertions and measurement methodology |
| [Security](docs/SECURITY.md) | JWT/refresh, HTTP/socket RBAC, inputs/secrets/logs |
| [Environment](docs/ENVIRONMENT_SETUP.md) | Official references, prerequisites, provisional commands |
| [Deployment/operations](docs/DEPLOYMENT_AND_OPERATIONS.md) | Local topology, health, backup/recovery |
| [Tasks](docs/TASKS.md) | Ordered solo backlog with evidence-backed completion |
| [Phase 2 evidence](docs/PHASE_2_EVIDENCE.md) | Implemented Week 2 checkpoint, checks and limitations |
| [Decisions](docs/DECISIONS.md) | Chosen stack, provisional defaults, contradictions |
| [Traceability](docs/TRACEABILITY_MATRIX.md) | Requirements ↔ sections/modules/tasks/tests/evidence |
| [Demo/submission](docs/DEMO_AND_SUBMISSION.md) | Scenario, evidence templates, rubric/retrospective |

[CONTRIBUTING](CONTRIBUTING.md) defines incremental workflow; [AGENTS](AGENTS.md) guides later coding agents. Targets and actual outcomes are recorded in Phase 4 evidence: sync <100 ms, non-AI P95 <200 ms, AI P95 <3 s, fan-out <500 ms, snapshot within 2 s, conflict within 1 s in ≥95%, exact budgets/analytics, valid suggestions over ≥20 tests and Precision@5≥0.6. Design for 50 planners and multiple rooms; transparently reported 5–10-client tests are acceptable (§14.1).

## Run the current slice

Follow [environment setup](docs/ENVIRONMENT_SETUP.md) to install dependencies, configure a private `.env`, migrate a disposable PostgreSQL database and start the API and React client. The documented first-slice scenario covers two accounts, room creation and joining, a shared pin, and its committed watermark. [Implementation evidence](docs/PHASE_1_EVIDENCE.md) records the actual tests, limitations and remaining acceptance work.

The app is intended for local development. The historical first-slice evidence describes an earlier subset; use the Phase 3 evidence for the current feature boundary. Final security, performance, restore and submission results are recorded in Phase 4 evidence.

### Phase 3 implemented

Exact weighted budgets, durable conflicts/timed elections, dashboard/group recommendations, session analytics and Admin dataset staging/activation are available. [Phase 3 evidence](docs/PHASE_3_EVIDENCE.md) records actual database, browser, real-model and evaluation results. Current migration head: `0011_phase3`; retain one application worker. Use the Admin room button or `python -m app.cli train-recommendations --destination "Bengaluru, India"` to refresh a model after collecting likes/pins. Phase 4 hardening/evidence is complete, with measured misses and limitations recorded.

### Frontend workspace

The React/Vite room has itinerary/day navigation, budget/voting/conflict sections, Concierge, chat and traveler presence, with light/dark themes and locally bundled Inter. Admin accounts can stage immutable datasets and review an activation confirmation. Server-calculated money, role permissions, stale-version rejection and socket watermarks remain authoritative. See [design tokens](DESIGN.md) and [UI verification](docs/FRONTEND_UI_EVIDENCE.md).

The authenticated workspace now follows the user's supplied working HTML draft: persistent sidebar, compact top bar, trip overview and separate connected feature pages. Actual data replaces the draft's sample values; see the draft-alignment section in [frontend evidence](docs/FRONTEND_UI_EVIDENCE.md).

### Phase 4 implemented — 2026-11-02

Transport/security hardening, ten-socket/two-room measurements, actual PostgreSQL backup/restore, compact grounded model selection, clean dependency reproduction and submission tooling are complete. Final validation: **116 backend tests passed with real inference and PostgreSQL, 8 frontend tests passed, production build and Chrome walkthroughs passed**. See [Phase 4 evidence](docs/PHASE_4_EVIDENCE.md) and [retrospective](docs/RETROSPECTIVE.md).

Measured limitations remain: maximum socket sync 144 ms and one rendered move 133 ms exceed the strict 100-ms target. Warm real-model HTTP P95 is 1.60 s with 99/100 grounded responses; cold inference falls back. A single rendered AI observation was 3.20 s including automation overhead; rendered AI P95 and fifty-distinct-planner capacity are unestablished. These outcomes are recorded, not silently passed. Raw samples, generated contracts, test output and the local HTTP collection are under `evidence/` and `http/`.

Use ENVIRONMENT_SETUP.md's Phase 4 commands to reproduce checks. `python scripts/scan-submission.py` scans current/reachable-history signatures with explicit limits; `python scripts/package-submission.py` creates an ignored `.local/tripsync-phase4-submission.zip` and an evidence manifest. No credentials, dumps, dependency directories or model runtime are included.
