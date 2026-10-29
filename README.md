# TripSync AI — Real-Time Collaborative Travel Planning

Independent educational prototype, broader project title “Airbnb Real-Time AI Trip Planning & Collaboration Platform.” No Airbnb affiliation, account access or integration is implied. Source: [PRD](Document/Project%20Document.docx), v1.0 September 2026, especially §§4,8–15.

**Current status: documentation only. No application, seed dataset, migrations, automated application tests or performance results have been implemented.** The user explicitly requested documentation before code, overriding PRD §13.2's scaffold-first suggestion. Application work begins only on a subsequent request.

**Selected track: Track A (full-stack). Selected stack: Python — FastAPI native WebSockets, PostgreSQL, SQLAlchemy async/asyncpg, Pytest; React JavaScript client.** Exactly one application backend; Concierge/recommendations are local Python modules. A local Ollama runtime supplies model inference through HTTP, not a second application backend. Alternatives and trade-offs are in [decisions](docs/DECISIONS.md).

## Intended scope

The final build includes a shared day-by-day activity/lodging board, invites and trip roles, Drafting/Voting/Locked lifecycle, version-checked edits, chat/typing/reactions, presence/reconnect, Leader moderation, exact budgets and contested votes. The Concierge filters authored metadata before ranking and RAG generation, cites sources, flags schedule/budget conflicts and handles no-match/model outages safely. Dashboard/history/preferences, hybrid content+collaborative recommendations, session analytics and Admin dataset upload complete the three epics (§6).

Private/local use by one operator, one engineer, four-week baseline. No booking, payments, live travel APIs, native app, public hosting/CDN or multi-tenant infrastructure. At least one fully authored destination covers all constraint types. Required functionality is not excluded as an “MVP.” The first vertical slice is only the first milestone.

## Start here

1. Read [requirements](docs/PROJECT_REQUIREMENTS.md) and [provisional decisions](docs/DECISIONS.md).
2. Follow the [four-week plan](docs/IMPLEMENTATION_PLAN.md) and [25-task backlog](docs/TASKS.md).
3. First implementation slice: **authentication → create Trip Room → second participant joins → basic server-authoritative board synchronization**. Prerequisites: stack setup/locks, identity/membership/item migrations, one destination and shared socket/HTTP policy.
4. Setup/run/test commands are [documented provisionally](docs/ENVIRONMENT_SETUP.md); they cannot run until the application exists. Planned tools: Python 3.13, Node/Vite/React, PostgreSQL 18 and local Ollama. Exact package locks require installation verification.
5. During implementation use Pytest/HTTP/socket/browser tests from feature creation, then collect actual evidence using the [demo/submission path](docs/DEMO_AND_SUBMISSION.md). No passing results are asserted now.

Weeks: 1 foundation + thin slice; 2 board and Concierge; 3 voting/personalization/analytics/Admin; 4 hardening/measurements/demo. High risks are Week 3 breadth, local model P95 <3 s, synchronization timing, batched durability and synthetic recommendation evaluation. Reduce dataset/model complexity before correctness, security, tests or documentation. See the decision log for voting eligibility/ties, room locking, Leader absence, money/time defaults and crash-loss limits needing review.

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
| [Tasks](docs/TASKS.md) | Ordered, dependent, unchecked solo backlog |
| [Decisions](docs/DECISIONS.md) | Chosen stack, provisional defaults, contradictions |
| [Traceability](docs/TRACEABILITY_MATRIX.md) | Requirements ↔ sections/modules/tasks/tests/evidence |
| [Demo/submission](docs/DEMO_AND_SUBMISSION.md) | Scenario, evidence templates, rubric/retrospective |

[CONTRIBUTING](CONTRIBUTING.md) defines incremental workflow; [AGENTS](AGENTS.md) guides later coding agents. Targets remain unmeasured: sync <100 ms, non-AI P95 <200 ms, AI P95 <3 s, fan-out <500 ms, snapshot within 2 s, conflict within 1 s in ≥95%, exact budgets/analytics, valid suggestions over ≥20 tests and Precision@5≥0.6. Design for 50 planners and multiple rooms; transparently reported 5–10-client tests are acceptable (§14.1).
