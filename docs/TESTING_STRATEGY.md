# Testing and measurement strategy

Test catalog and measurement plan, PRD §§6,10–15. Phase 1/2 tests have run; actual commands and results are in PHASE_1_EVIDENCE.md and PHASE_2_EVIDENCE.md. Later-phase tests and performance benchmarks remain pending. Tests start with each feature; Week 4 consolidates evidence. Use Pytest + asyncio fixtures, HTTPX and scripted native-WebSocket clients against real isolated PostgreSQL; React unit tests plus browser end-to-end two-session checks. SQLite cannot establish PostgreSQL CAS/transaction behavior.

## Test catalog

| Test ID | Planned assertion |
|---|---|
| AUTH-01 | Register/login/refresh/logout and current session identity; registration cannot set Admin |
| ROOM-01 | Create/invite/join/capacity, duplicate identity tabs, revoked/expired code, room lock, leadership transfer |
| BOARD-01 | Legal/illegal lifecycle transitions, Planner/Viewer restrictions, lock override reason |
| BOARD-02 | Barrier-start two expected-version moves: one accepts, one stale notification, all clients converge; repeated/random schedules |
| CHAT-01 | Durable history/reactions, typing expiry, mute enforcement, reconnect no lost committed chat |
| SYNC-01 | Atomic snapshot + subsequent events, midstream join, drop/reconnect, Leader absence, token expiry, multiple rooms and sequence gaps |
| AI-01..07 | ≥20 valid/invalid hard-filter requests, citations, injection, no-match, outage, changed context, score normalization |
| BUD-01..03 | Manual exact fixtures, sum properties, weights/attendees/currency validation, ceiling and reservation distinctions |
| VOTE-01..04 | Eligibility/duplicate tabs, deadline/ties/changes/zero votes, crash/idempotence, consistent winner/budget |
| CONFLICT-01 | Shared-attendee overlap/budget breach opens once, notification time, edits/votes resolve fingerprint |
| REC-01..05 | Held-out Precision@5, no-redeploy refresh, artifact rollback, cold start and access/version isolation |
| ANA-01 | Hand-written session ledger reproduces duration/peak/AI/conflict counts/final per-person budget exactly |
| DATA-01..03 | Valid staging/activation, invalid price/diet/coordinates/hours/unsafe file, immutable version/index readiness |
| SEC-01..06 | JWT/refresh/origin, all four roles HTTP+socket, cross-room access/removal, injection/limits, prompt boundary, secrets/logs |
| OPS-01..02 | Crash before/after commit, overdue vote once, DB outage/uncertain commit, backup restore reconciliation |
| PERF-01 | Board synchronization and server fan-out raw samples with convergence checks |
| PERF-02 | Non-AI API distribution, successes/failures and per-route P95 |
| PERF-03 | Actual model end-to-end warm/cold latency, timeout/fallback counts |
| E2E-01 | Complete required two-browser path plus dashboard/admin/recommendation evidence |

Unit tests cover pure domain functions with table-driven boundary cases. Integration tests exercise real transactions/version predicates and restart recovery. Model stubs establish deterministic error paths but do not prove real inference integration; real-model test recorded separately. HTTP collection includes auth/create/join/catalog/ask/forbidden/upload. Track A scripted clients still provide repeatable load evidence; if Track B later selected, collection/harness/generator replace all UI evidence (§4.3).

## Performance methodology and targets

| Dimension | Target | Measurement |
|---|---|---|
| Board synchronization | <100 ms normal local network | Mutation command dispatch to each client's identical aggregate applied/rendered; record max across clients and render convergence |
| Non-AI HTTP | P95 <200 ms | Request start to complete response, per-route and pooled distribution |
| AI | P95 <3 s | Ask dispatch to rendered grounded response, actual model calls; report fallback separately |
| Fan-out | <500 ms | Server receipt to last client delivery, 50 planners design capacity |
| Join snapshot | ≤2 s | Authenticated socket connection start through complete board/lifecycle/budgets application |
| Conflict detection | ≤1 s in ≥95% cases | Server conflicting mutation acceptance to client notification |
| Budget | 100% manual fixture agreement | Even/weighted and running totals, exact cents |
| Constraints | 100% over ≥20 requests | Every returned suggestion independently rechecked against active constraints |
| Recommendations | Precision@5 ≥0.6 | Frozen held-out self-generated set, no leakage |
| Analytics | Exact one-session reconciliation | Manual independent event ledger vs endpoint values |

PRD wording for snapshot/conflict uses “within”; ≤ boundaries adopted provisionally, strict `<` retained for latency targets as stated. Sync drift is not server-to-last-delivery fan-out: drift includes origin-to-server and client apply/render work, while fan-out starts at server receipt. Also report inter-client apply spread (`max(apply)-min(apply)`) as an additional metric; it cannot substitute for mutation-to-all delay.

Single-host harness uses common monotonic reference and records receipt/apply acknowledgements. Browsers on one host use calibrated performance time origins; real LAN clients require NTP/clock-offset estimation via repeated ping/pong, recorded offset and uncertainty. If clocks cannot support one-way claims, report server receipt-to-client ACK round trip as a conservative proxy, clearly labeled, and do not claim exact one-way pass. `ts` wall clock aids tracing, not a sufficient precision clock. Rendering evidence from browser instrumentation is separate from scripted receipt measurements.

Proposed reproducible run: 5–10 clients (acceptable §14.1), 2+ rooms, 2 min warmup then ≥1000 board mutations/HTTP samples and ≥100 real AI queries if hardware permits; disclose actual counts and any smaller run. Separate two-client simultaneous-item test from uniform load. Include idle/slow client, reconnect and model cold start. Report hardware CPU/RAM/GPU, OS, network/RTT, dependency/model/dataset versions, client count/room distribution, seed, sampling period and background tasks. Use nearest-rank empirical P95 and report n, P50/P95/max plus failure count. Never drop failed/time-out samples from availability reporting; latency quantiles label successful-only versus timeout-censored population.

AI cold/warm distributions separate; do not prewarm secretly or count fallback as successful model response. Verify final aggregate equality after load, not merely frame receipt. Fifty is design intent; a 10-client run does not establish capacity 50. All target results remain **NOT MEASURED**.

## Analytics event semantics

Provisional planning duration: first live session start (second distinct member joins) to explicit trip finalization/session end; reconnect grace does not create another session. Peak concurrency counts distinct connected Planner/Leader users, excludes Viewer/Admin-only and duplicate tabs. AI questions count accepted unique ask command IDs including fallback, exclude retries/dedup. Conflicts flagged counts new fingerprints; resolved counts first open→resolved transition. Final budget is Locked allocations at final committed sequence; advisory alternatives excluded. Persist session start/end and connection first/last transitions for exact reconstruction. ANA-01 independently computes all metrics from one manually verified ledger, including disconnect/duplicate request and a conflict reopening as a new incident.

## Evidence output

During implementation save raw test output, command/config versions and timestamps in `evidence/tests/`; performance CSV/JSON plus method in `evidence/performance/`; annotated recordings and manual ledger in `evidence/demo/`. These folders/results do not exist yet. Redact secrets, not failures. [Demo checklist](DEMO_AND_SUBMISSION.md) supplies templates. Documentation verification now checks file/link/ID consistency only; it is not application test evidence.

## Phase 3 actual verification

PHASE_3_EVIDENCE.md records 110 backend passes with real local inference, 8 frontend test passes, production build and two-browser Phase 3 output. Database tests exercise exact recovered 800/1600 weighted budgets, version/ballot/role/removed-member failures, overdue/no-turnout/tie behavior, failed commit rollback, manual analytics and artifact/dataset immutability. Presence and session boundaries are separate durable supporting ledgers rather than board-sequence events. Final analytics uses the exact persisted second-member join through finalization interval; a session lacking a historical observed start reports durationKnown=false. Frozen recommendation cohorts meet the precision gate on that fixture only. Phase 4 measurements/consolidation remain pending.
