# Traceability matrix

Requirements trace with partial implementation and verification; current evidence and remaining gaps are documented below. Source [PRD](../Document/Project%20Document.docx); each requirement is defined in [requirements](PROJECT_REQUIREMENTS.md). Modules resolve to planned paths in [architecture](ARCHITECTURE.md); test IDs in [testing strategy](TESTING_STRATEGY.md); evidence IDs in [submission](DEMO_AND_SUBMISSION.md).

| Requirement | PRD sections | Module | Tasks | Planned tests | Submission evidence |
|---|---|---|---|---|---|
| REQ-001 | §§4,8,11,14 | Architecture/track | TASK-001, TASK-002, TASK-025 | EV-DOC; OPS-01; EV-DOC | EV-DOC; pending |
| REQ-002 | §§10.1 | Auth | TASK-003 | AUTH-01; SEC-01; SEC-02 | EV-SEC; pending |
| REQ-003 | §§3,10.1 | Auth/policy | TASK-003, TASK-021 | AUTH-01; SEC-01; SEC-02; SEC-01..06; E2E-01 | EV-SEC; pending |
| REQ-004 | §§5.1,6.1 | Rooms | TASK-005 | ROOM-01 | EV-BOARD; pending |
| REQ-005 | §§2,6.1 | Board | TASK-006, TASK-008, TASK-016 | BOARD-01; SYNC-01; BOARD-02; VOTE-04 | EV-BOARD; Phase 2 item rules verified; live election integration pending TASK-016 |
| REQ-006 | §§6.1,7.2,9.4 | Board/CAS | TASK-008 | BOARD-01; BOARD-02 | EV-BOARD; pending |
| REQ-007 | §§6.1 | Chat | TASK-010 | CHAT-01 | EV-BOARD; pending |
| REQ-008 | §§6.1,10.3 | Gateway/snapshot | TASK-006, TASK-009 | BOARD-01; SYNC-01; SYNC-01; ROOM-01; SEC-02 | EV-BOARD; pending |
| REQ-009 | §§6.1 | Moderation | TASK-009 | SYNC-01; ROOM-01; SEC-02 | EV-SEC; pending |
| REQ-010 | §§6.1 | Room/presence | TASK-009 | SYNC-01; ROOM-01; SEC-02 | EV-BOARD; pending |
| REQ-011 | §§4.1,6.2,14.1 | Ingestion/retrieval | TASK-004, TASK-020 | DATA-01; DATA-02; DATA-01; DATA-02; DATA-03; SEC-04 | EV-AI; pending |
| REQ-012 | §§6.2 | Constraints/budget | TASK-012 | AI-01; AI-07 | EV-AI; pending |
| REQ-013 | §§6.2 | Constraints/diet | TASK-012 | AI-01; AI-07 | EV-AI; pending |
| REQ-014 | §§6.2 | Constraints/hours | TASK-012 | AI-01; AI-07 | EV-AI; pending |
| REQ-015 | §§6.2 | Constraints/geo | TASK-012 | AI-01; AI-07 | EV-AI; pending |
| REQ-016 | §§6.2 | Ranking | TASK-012 | AI-01; AI-07 | EV-AI; pending |
| REQ-017 | §§5.3,6.2,7.3 | RAG | TASK-013 | AI-02; AI-03; AI-04; AI-05; AI-06 | EV-AI; pending |
| REQ-018 | §§6.2 | Conflict detector | TASK-015 | CONFLICT-01 | EV-VOTE; pending |
| REQ-019 | §§5.3,6.2 | Voting | TASK-016 | VOTE-01; VOTE-02; VOTE-03; VOTE-04 | EV-VOTE; pending |
| REQ-020 | §§1.3,3,13 | Budget | TASK-014 | BUD-01; BUD-02; BUD-03 | EV-VOTE; pending |
| REQ-021 | §§14.2,15.1 + request | RAG fallback | TASK-013 | AI-02; AI-03; AI-04; AI-05; AI-06 | EV-AI; pending |
| REQ-022 | §§6.3 | Dashboard | TASK-018 | E2E-01; SEC-03 | EV-REC; pending |
| REQ-023 | §§6.3 | Recommendations | TASK-017 | REC-01; REC-02; REC-03; REC-04; REC-05 | EV-REC; pending |
| REQ-024 | §§6.3 | Analytics | TASK-019 | ANA-01 | EV-ANA; pending |
| REQ-025 | §§6.3,10.1 | Admin/ingestion | TASK-004, TASK-020 | DATA-01; DATA-02; DATA-01; DATA-02; DATA-03; SEC-04 | EV-SEC; pending |
| REQ-026 | §§7.3 + request | API/gateway | TASK-005, TASK-024 | ROOM-01; EV-DOC; E2E-01 | EV-DOC; pending |
| REQ-027 | §§9.4,10.3 | Persistence | TASK-006, TASK-011, TASK-023 | BOARD-01; SYNC-01; OPS-01; SYNC-01; OPS-01; OPS-02 | EV-OPS; pending |
| REQ-028 | §§10.3 | Operations | TASK-002, TASK-011, TASK-023 | OPS-01; EV-DOC; OPS-01; SYNC-01; OPS-01; OPS-02 | EV-OPS; pending |
| REQ-029 | §§10.1 | Security | TASK-003, TASK-021 | AUTH-01; SEC-01; SEC-02; SEC-01..06; E2E-01 | EV-SEC; pending |
| REQ-030 | §§1.3,10.2,14.1 | Performance | TASK-022 | PERF-01; PERF-02; PERF-03 | EV-PERF; pending |
| REQ-031 | §§11.2,12,15 | Testing | TASK-007, TASK-021, TASK-022, TASK-025 | E2E-01; EV-DOC; SEC-01..06; E2E-01; PERF-01; PERF-02; PERF-03; EV-DOC | EV-DOC; pending |
| REQ-032 | §§12,13 | Submission | TASK-002, TASK-007, TASK-024, TASK-025 | OPS-01; EV-DOC; E2E-01; EV-DOC; EV-DOC; E2E-01; EV-DOC | EV-DOC; pending |
| REQ-033 | §§4.3 | Track alternative | TASK-001 | EV-DOC | EV-DOC; pending |

Documentation review must also check the role matrix, canonical money/citation fields, lifecycle transitions, timer semantics, volatile/committed acknowledgements and snapshot versions across all primary files. REQ-033 is conditional on a future Track B selection; selection/equivalence review is current evidence, not a claim that its harness exists.

## Implementation status — 2026-10-30

A preliminary FastAPI shell and two health failure tests now exist. They do not meet TASK-002 acceptance: clean installation, migrations, authenticated DB access, and complete health checks remain unverified. See [implementation evidence](PHASE_1_EVIDENCE.md). TASK-003 is partially started and TASK-004–007 remain unimplemented; the table above remains a design trace, not evidence of delivered features.


2026-10-30 update: PostgreSQL migrations, the dataset import and a narrow HTTP authentication/create/join path have been exercised on a disposable local database. The broader phase, especially WebSockets, frontend and complete security acceptance, remains pending; see [evidence](PHASE_1_EVIDENCE.md).

REQ-005/008/027 have an initial pin/snapshot implementation with two-browser and targeted database-backed evidence, but the complete snapshot, role matrix and recovery acceptance remain pending. See [phase 1 evidence](PHASE_1_EVIDENCE.md).

REQ-004/026 now have preliminary Leader invitation issuance/revocation and capacity rejection evidence; TASK-005 remains unchecked because all acceptance and dependency checks have not been demonstrated. See [phase 1 evidence](PHASE_1_EVIDENCE.md).

First-slice tests and their actual results are in [phase 1 evidence](PHASE_1_EVIDENCE.md). REQ-002–005, REQ-008, REQ-026, REQ-027 and REQ-029 have implemented first-slice coverage; rows that also span later tasks or submission evidence remain partial. No final epic or target achievement is implied.

2026-10-31: REQ-005 and REQ-006 have an isolated board-rule implementation with unit tests. It is not wired to the live application or persistence and does not meet TASK-008 acceptance; see [evidence](PHASE_1_EVIDENCE.md).

2026-10-31: REQ-005/006 now have live socket move/remove and Leader lock/unlock paths, version checks and database-backed tests; a complete grid, full lifecycle and acceptance remain pending. See [evidence](PHASE_1_EVIDENCE.md).

2026-10-31: REQ-007 has durable chat, history, typing and reaction implementation with database and two-browser evidence; TASK-010 remains open pending the additional security and failure coverage listed in [evidence](PHASE_1_EVIDENCE.md).

2026-10-31: REQ-012–016 now have a standalone deterministic matcher with 25 boundary/ranking tests. Authorized trip-context resolution, HTTP/client integration and full TASK-012 acceptance remain pending; see [Concierge implementation note](AI_TRAVEL_CONCIERGE.md).

The [2026-10-31 PRD alignment review](PRD_ALIGNMENT_REVIEW.md) distinguishes original requirements, explicit user overrides, implementation choices and unfinished coverage. REQ-017/021 require grounded model integration and safe failure handling; they do not require Ollama. Existing task completion states remain unchanged.

2026-10-31: REQ-008/010 now have distinct-user socket presence, Leader connectivity snapshots and targeted database/browser evidence. Full disconnect/moderation/recovery acceptance remains pending; see [evidence](PHASE_1_EVIDENCE.md).

## Phase 2 checkpoint acceptance — 2026-10-31

[Phase 2 evidence](PHASE_2_EVIDENCE.md) records accepted TASK-008–013: CAS/day grid/lifecycle rules (REQ-005/006), presence/moderation/refresh (REQ-008–010), durable chat (REQ-007), recovery/logging (REQ-027/028), authorized filtering/ranking (REQ-012–016), actual local generation/citations and safe fallback (REQ-017/021). Final submission evidence in the original table remains pending where it spans later tasks. REQ-005 explicitly also traces TASK-016 for live Voting orchestration; tested item state projections do not claim working elections. REQ-019/020/022–025 and later logistics, security/performance/demo requirements remain in final scope.

## Indian localization follow-up

Explicit user requirement: INR/paise, Asia/Kolkata IST board and an authored Indian destination. Implementation: Bengaluru fixture, dataset/API currency validation, room-derived budget/event currency, Concierge currency rendering, frontend locale/time helpers. Verification: `test_india_integration.py`, India case in frontend `time.test.js`, and the Bengaluru two-browser real-model flow. Original Phase 2 evidence stays historical; current results are recorded in INDIA_LOCALIZATION_EVIDENCE.md.

### Phase 3 allocation increment (2026-11-01)

REQ-020 / TASK-014: `app/budget/engine.py`, `tests/test_budget.py`: 9 passed for manual even/weighted/remainder/zero-weight fixtures, conservation and vote reservations. This increment alone does not accept the entire Phase 3 UI/election workflow. Phase 3's final acceptance record is PHASE_3_EVIDENCE.md.

## Phase 3 acceptance — 2026-11-01

| Requirements / task | Implemented evidence |
|---|---|
| REQ-020 / TASK-014 | budget engine/service, test_budget and database/browser weighted splits; recovery fixture 2400 minor units = 800/1600 |
| REQ-018 / TASK-015 | pure overlap/ceiling rules, transactional conflicts/history and post-commit core conflict notifications; state correction resolves one incident |
| REQ-019 / TASK-016 | shared HTTP/socket election service, managed deadlines/recovery, eligibility/removal/stale ballots, tie/no-turnout and failed-commit tests; two Chrome clients share one locked winner |
| REQ-023 / TASK-017 | real interactions/content+item-neighbor CF, atomic artifacts/fresh-history rerank, failed-artifact retention; frozen 40-user evaluation Precision@5 1.00 with disclosed easy-cohort limits |
| REQ-022 / TASK-018 | dashboard history/rejoin, declared diets, per-currency observed price ranges and derived categories; Chrome active rejoin/finalized history |
| REQ-024 / TASK-019 | durable session/presence/conflict ledgers, exact finalized duration, peak=1/AI=1/conflicts=1→1 and final 800/1600 manual fixture |
| REQ-011/025 / TASK-020 | bounded Admin JSON validation/staging/activation, invalid field errors and immutable pinned catalog; PostgreSQL and browser checks |
| REQ-003/026/027/029/031/032 | role/trip boundaries, original core envelopes/events, significant transaction persistence, docs/schema/setup updates and actual commands/results |

See PHASE_3_EVIDENCE.md for the final 110-test backend run (including real inference), 8 frontend tests, production build, browser output, environment, failures and limitations. Requirement coverage here does not imply the remaining Phase 4 full security/performance/recovery/submission gates have passed.

## Phase 3 frontend follow-up

Presentation improvements for REQ-005–010, REQ-018–025 and REQ-027 are tracked in FRONTEND_UI_EVIDENCE.md. Existing Phase 3 acceptance remains historical. No Phase 4 acceptance checkbox changes follow from UI implementation alone.

Frontend follow-up implementation: `main.jsx`/BoardGrid (REQ-005–010/027), PlanningPanel/SplitEditor (REQ-018–020/023–024), Dashboard (REQ-022), DatasetAdmin (REQ-011/025) and ConciergePanel (REQ-017/021). Existing commands and actor/version semantics are preserved. Browser checks and disclosed limits are in FRONTEND_UI_EVIDENCE.md.

The user-supplied working draft subsequently established the actual sidebar/page layout. `workspace/TripOverview.jsx` and revised main/CSS preserve the existing contracts while supplying separate connected screens; new and adapted browser checks are recorded in FRONTEND_UI_EVIDENCE.md.
## Phase 4 additions (2026-11-02)

REQ-029/031: `app/transport.py`, `test_transport_limits.py`, `test_phase4_security.py` add pre-parser body bounds, clean frame rejection and later-feature identity/isolation consolidation. `test_room_actor.py` additionally exercises slow-subscriber eviction. REQ-027/028: `test_phase4_restore.py` adds actual logical backup/all-table digest restore and overdue-election recovery, independently checked exact INR weights. REQ-030: `phase4_measure.py` and instrumented `browser_phase1.py` collect real socket/HTTP/model and separate browser render samples. These paths are implementation coverage; final task acceptance and measured outcomes are recorded in PHASE_4_EVIDENCE.md.

TASK-021–025 accepted for delivered hardening/evidence artifacts: final 116 backend tests passed with real DB/model, 8 frontend tests/build and Chrome walkthroughs passed; clean installs, restore digests, extracted physical/OpenAPI contracts, limited history-secret scan and submission manifest/ZIP were produced. REQ-017/021 additionally uses compact allowlisted source-ID generation with unchanged filters/citations; optimized warm HTTP sample produced 99/100 grounded answers, P95 1.60 s. REQ-030 remains a measured partial performance result: strict maximum sync missed; cold generation falls back; full rendered-AI P95, exact one-way fan-out and 50-distinct-planner capacity are not established. No requirement is silently removed or marked KPI-passed by these task checkboxes.

