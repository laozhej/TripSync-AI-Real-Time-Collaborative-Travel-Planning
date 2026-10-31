# Phase 2 implementation and acceptance evidence

Date: 2026-10-31. TripSync AI is an independent local educational prototype. Source requirements: PRD §§6.1–6.2,7.3,9.4,10–12; backlog TASK-008–013. The Phase 1 log is chronological; this document owns current Phase 2 evidence. Phase 2 acceptance is recorded below; later project phases remain open.

## Delivered scope

| Task | Implementation and acceptance evidence |
|---|---|
| TASK-008 | Day/time grid with native drag/drop and an accessible selected-time alternative; pin/move/remove and durable Leader lock/unlock. Actual room commands released at a barrier from item version 4 produce one version-5 winner and one explicit stale conflict. Pure lifecycle primitives validate Drafting → Voting and resolution/cancellation; Voting items reject ordinary mutation. |
| TASK-009 | Distinct-user/multi-tab presence, current member/state versions, Leader absence with no promotion, ping/pong RTT, automatic socket reconnect and HTTP token refresh. Shared HTTP/socket moderation supports mute/unmute, removal, room lock/unlock and atomic transfer to a connected active Planner. Removal closes every membership tab and prevents fresh or cached invite rejoin. |
| TASK-010 | Durable chat/history, bounded sequence pagination, optimistic durable reaction upsert/remove, three-second typing expiry, mute/removal enforcement and text rendering. PostgreSQL tests exercise all membership roles including Admin accounts without bypass, foreign-trip message IDs, duplicate commands, pagination across new arrivals, and restart persistence. |
| TASK-011 | Default 100-ms batched volatile changes, separate committed watermarks, significant-transition transactions, freeze on failed/uncertain commit, recovery with new epochs, and whitelisted JSON operational logs. Actual server-process kills and a PostgreSQL connection outage are exercised by the recovery script. |
| TASK-012 | Authorized effective category ceiling, optional request tightening, active-attendee diet union, full buffered destination hours, anchored Haversine radius, valid-only lexical retrieval and normalized 40/30/30 ranking. Thirty matcher cases cover boundaries, overnight hours, summer offsets, ambiguous/nonexistent opening boundaries and deterministic ordering. |
| TASK-013 | Async local inference with a 2.5-second generation deadline, bounded response size, request-specific candidate schema, application ID/field validation, deterministic facts and resolvable canonical citations. API/client support clarification, no-match, model failure and changed-context results. Real-model integration is separate from mocked failure tests. |

Voting lifecycle **rules** are Phase 2 domain foundations. Timed elections, eligible-voter snapshots, ballots, automatic contest detection, and atomic election winner application with conflict/budget recomputation remain TASK-016 in Phase 3, after TASK-014/015. There is no public command that creates an unbacked Voting item. The pure lifecycle tests do not claim a live timed-election workflow. All later PRD epics remain mandatory.

## Reproducible checks and results

Run from the repository root, with `.env` configured privately for PostgreSQL and a role allowed to create disposable databases:

```powershell
.\scripts\start-local-model.ps1
$env:RUN_LIVE_MODEL='1'
.\.venv\Scripts\python.exe backend\tests\clean_setup.py
npm run test:unit --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python.exe backend\tests\browser_clean_setup.py
.\.venv\Scripts\python.exe backend\tests\recovery_phase2.py
```

The final backend run applied migrations through `0010_concierge`, imported the authored Lisbon dataset, and reported **91 passed, 1 warning in 75.92 seconds**. The database was removed. `RUN_LIVE_MODEL=1` includes an actual local-model HTTP/API/citation test that fails if generation falls back. Offline deterministic model tests are explicitly mocked. The recurring pytest-asyncio fixture-scope notice and Starlette TestClient deprecation are existing test-stack limitations, not silently suppressed failures.

The production build succeeded with Vite 7.3.7 (27 modules). The local-model start/warm-up script succeeded. The final two-session Chrome run passed grid drag/drop, real Concierge answers/citations, chat, expired-token refresh, forced reconnect, invitations, mute/unmute, room lock/unlock, leadership transfer, removal and revoked-session sign-in. Its one local join-to-snapshot observation was **355.9 ms**, not a performance benchmark. The browser factory uses an eight-second first access token to exercise refresh; production token issuance is unchanged. A dedicated worker runs the asynchronous database revocation helper outside Playwright's driver loop. Both temporary servers and the disposable browser database were removed.

The actual-process recovery script reported:

```text
PASS: actual process kills discard only volatile pins; durable board/chat/reactions/leadership/budgets/session restore with new epochs
PASS: PostgreSQL connection outage freezes the batch and mutations; restart restores committed watermark 5
Disposable recovery database removed
```

For reproducibility the recovery server is a **test-only factory** that pauses the normal flusher with a file gate. Opening the gate resumes the unchanged 100-ms production loop. The drill uses real PostgreSQL, terminates only its own server process, disables connections only to its randomly named disposable database, restores that flag, and drops the database. No production fault-control endpoint exists. A separate integration test injects failure after a successful commit, verifies frozen memory versus durable state, reloads a new epoch, and replays the command without applying it twice.

## Local model and environment

The user selected a local open-source model. Ollama is an implementation choice allowed by the PRD, not a PRD requirement. Portable runtime: **Ollama 0.40.13**. Model: **Qwen2.5 1.5B**, 986061892 bytes, digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`. Runtime archive SHA-256: `7afa38624fa62ee5d8293422d0ab084c1bb4603134c7f4dafce11a033b57cc19`, matched against the publisher's release metadata before extraction. Runtime, weights and local logs stay under ignored `.local/`; inference binds `127.0.0.1:11434` with cloud disabled in the launch helper.

Hardware: Windows host, Intel Core i7-10875H (8 cores), approximately 31.8 GiB RAM. Runtime detection reports NVIDIA GeForce RTX 2070 Super with 8 GiB VRAM and CUDA acceleration. The WMI AdapterRAM field reported 4 GiB and was not used as the authoritative GPU-memory reading. Test network is host loopback. Python 3.13.1; FastAPI 0.162.0; SQLAlchemy 2.0.55; asyncpg 0.32.0; Pytest 9.2.0; HTTPX 0.28.1; Playwright 1.64.1; websockets 17.3; Chrome 156.0.8078.79; Node v24.13.0; npm 9.9.4. Dataset: authored synthetic Lisbon, version 1.

After adapting the output schema to require one eligible selection, two actual adapter calls returned `status:grounded` with `venue:v_1@1` in 0.870 s and 0.448 s. One used a 60-second setup deadline, the other the normal 2.5-second deadline. These are individual local observations, not a P95 benchmark. Explicit model preload is test/demo setup and is not counted as generation latency. Cold loading or model failure may still return a labeled valid-only fallback.

## Failures fixed and limits

Seven frontend unit tests pass for UTC display dates mapped to destination-local trip dates, including summer/winter Lisbon, positive/negative/quarter-hour offsets, invalid slots and preserved duration at the half-open trip boundary. The board and room snapshot carry the IANA timezone. Additional backend checks cover cancelled per-question lock cleanup and database context-read failure before generation.

A final concurrent backend/browser validation attempt returned labeled generation fallbacks at the unchanged 2.5-second deadline and failed the strict live-model assertions. Those attempts are not passes. Running model acceptance sequentially after explicit preload produced the backend result above. Local contention and cold loading can still trigger fallback; no latency target or concurrent-model throughput is claimed.

Earlier runs exposed cancelled disconnect cleanup, stale room stateVersion after joining, a grid drop callback passing a day object, a model choosing an empty/insufficient selection, cold/setup fallback, a test helper nesting asyncio inside Playwright's loop, and the client retaining registration mode after session expiry. These failures were investigated and corrected; earlier failed runs are not counted as passes. Clean setup now saves sanitized failure diagnostics under ignored `.local/` and prints failed test names without dumping private configuration.

No sync/API/AI P95, 50-client capacity, or final project target is claimed. Week 4 load/security consolidation, backup/restore and final submission remain open. Date-specific hours exceptions are still rejected by ingestion; ambiguous authored opening boundaries fail closed. The current Concierge factual renderer answers from venue metadata and does not invent transit/weather prose. The authored transit/weather data remain stored for later required logistics integration. Exact weighted budgets, conflict detection, live contested elections, dashboard/recommendations, analytics and Admin upload remain Phase 3 work.

The configured **loopback development database** was also upgraded from `0008_venue_search` to `0010_concierge`. Counts of existing users, trips, itinerary items and datasets were checked before/after and preserved. PostgreSQL server version was 18.1. No signing secret, password or production/remote database was changed.

After disposable verification finished, the standard application entry point (`app.main:app`, one worker, port 8000) and Vite (loopback port 5173) were started against the configured development database. Independent HTTPX requests with environment proxies disabled returned HTTP 200 from `/api/v1/health/live`, `/api/v1/health/ready`, `/api/v1/health/gateway`, and the frontend root. Runtime logs and process IDs remain ignored under `.local/`.
