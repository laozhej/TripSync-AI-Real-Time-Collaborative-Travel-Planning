# Phase 3 implementation evidence

Recorded 2026-11-01 for TASK-014–020, PRD §§3,6.2–6.3,7.2–7.3,11.1. TripSync AI is an independent educational prototype. The original DOCX remains source history; Indian locale, CAS and the selected Python/local-inference choices follow the user's instructions and decision log.

## Implemented behavior

- Exact even/weighted allocations, integer remainder ordering, proposed/Locked per-person totals, per-person maximum election reservations, versioned attendee/split edits and self total ceilings.
- Durable schedule/budget conflict incidents and resolution by state correction. Core `trip.board.conflict` notifications publish after commit; history and transition ledgers remain inspectable.
- Leader and system elections, fixed eligibility, versioned changeable ballots, removed-ballot invalidation, deadline rejection, stable ties, zero-turnout cancellation, archived losers and atomic winner application. Managed startup resolves persisted overdue votes before readiness; failed commits freeze writes.
- Real interaction endpoints plus server-derived pin/lock history, content/item-neighbor CF artifacts, atomic model promotion, immediate group-history reranking and same-sequence browser invalidation. Admin training works through API/UI or application CLI.
- Membership-scoped dashboard, history/rejoin, observed categories and per-currency price ranges, declared diets, exact session boundaries/presence/conflict ledgers and finalized budget reconciliation.
- Admin JSON validation/staging/activation, indexed immutable versions, pinned-trip catalog access, and read-only finalized UI.

Domain policies remain provisional where DECISIONS marks them provisional. No extra backend, database, cloud service, public hosting or live travel integration was added.

## Commands and results

Run from the repository root with the existing environment. `clean_setup.py` creates a random disposable PostgreSQL database, applies all migrations, imports Lisbon and Bengaluru, runs tests and removes only that generated database. It never drops the configured development database.

```powershell
$env:PYTHONPATH='backend'
./scripts/start-local-model.ps1
$env:RUN_LIVE_MODEL='1'
.venv/Scripts/python backend/tests/clean_setup.py backend/tests -vv -o faulthandler_timeout=20
npm --prefix frontend run test:unit
npm --prefix frontend run build
.venv/Scripts/python backend/tests/browser_clean_setup.py backend/tests/browser_phase3.py
.venv/Scripts/python -m app.recommendations.evaluate --output data/interactions/phase3-evaluation.json
```

The final full run after the weighted-pin recovery correction reported **110 passed, 1 warning in 86.03s**, including real local inference, with no skips. An earlier completed run before that correction passed 110 in 85.83s; the new independent 800/1600 reconciliation assertion exposed and now guards the correction. Frontend unit tests: **8 passed, 0 failed/skipped**. Vite production build: **31 modules**, successful, latest JS bundle 266.66 kB / 81.93 kB gzip. Python compileall and Git whitespace checks succeeded. These are build observations, not latency targets.

The final Phase 3 Chrome run reported:

```text
Phase 3 Chrome: two participants, weighted split, system vote/ballots/deadline/winner, analytics, hybrid refresh, dashboard rejoin/history, Admin invalid/valid staging/activation, finalization; no page errors; 390px overflow check passed
Disposable browser database removed
```

The browser uses two isolated Chrome contexts, actual PostgreSQL/API/native sockets and the real 60-second system deadline. It also saves a full-page screenshot under ignored `.local/phase3-browser.png`; it was visually inspected. The total-ceiling form, finalized read-only controls and Admin upload paths are exercised. No calibrated convergence timing or accessibility certification is claimed. Existing timing unit tests retain IST midnight and legacy timezone coverage.

## Exact manual reconciliation fixture

The database acceptance fixture uses two explicitly weighted attendees (1:2) and Lisbon venue v_2 at 1200 cents/person. The selected winner costs **2400 cents**, allocated **800/1600**, both proposed and Locked after finalization. One other candidate is archived, so it adds zero final cost. The one overlap incident opens once and resolves once. Only the Leader has a socket in this fixture (Planner ballots are HTTP), so peak distinct connected planners is **1**. One accepted clarification answer plus an identical idempotent retry counts as **1** Concierge answer. Exact duration equals persisted finalization end minus the second-member join start; reconnect does not reset that start. The test independently compares these hand expectations, relational boundaries, conflict transitions and final per-person output. Unknown starts in pre-Phase-3 historical trips are labeled rather than reconstructed.

Other cases cover all manual allocation fixtures, conservation, zero/invalid weights, category versus personal/group ceilings, stale split/ballot conflicts, Viewer/Admin isolation, cross-trip access, removed ballots, late receipt, tie/no-turnout rules, duplicate timers, overdue recovery, failed election commit rollback, fresh-history CF serving, rejected artifact retention and active-trip dataset pinning across activation. Socket command adapters invoke the same authorized services as HTTP; the Chrome run verifies real ballot fan-out and common winner state.

## Recommendation evaluation

See [frozen output](../data/interactions/phase3-evaluation.json) and `app/recommendations/evaluate.py`. Seed 7312026; 40 authored fictional feature items; 40 synthetic users; 120 chronological training, 80 validation and 200 test positives. Fixture SHA-256 `7944cec86d95b498a02d133b086da0e5b00144eff7056fb15f8dd81cd190b077`. Fixed equal blend; training receives no held-out labels. Validation positives are already observed and excluded from final recommendations. All other eligible unseen items are ranked; denominator is always five.

| Model | Macro Precision@5 |
|---|---:|
| Hybrid | 1.00 |
| Content | 1.00 |
| Collaborative | 0.915 |
| Popularity | 0.11 |

The ≥0.6 gate passes on this deliberately simple single-category-cohort fixture. Content is equally strong; no hybrid improvement or real-traveler generalization is claimed. The evaluation catalog is separate from the unchanged six-place application sample. Real application interactions and actual hybrid serving are demonstrated independently in PostgreSQL tests and the browser.

## Environment and local update

Windows 11 build 26300, Intel Core i7-10875H (8 cores/16 logical processors), 34,164,142,080 bytes physical RAM; loopback network; one application worker. Python 3.13.1; FastAPI 0.162.0; SQLAlchemy 2.0.55; asyncpg 0.32.0; Pytest 9.2.0; HTTPX 0.28.1; Playwright 1.64.1. Node 24.13.0, npm 9.9.4, React/react-dom 19.3.1, Vite 7.3.7. Dependencies were not changed.

Ollama 0.40.13 and Qwen2.5 1.5B (986061892 bytes), digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`. The local runtime/weights were already installed; the launch helper started and preloaded them. No model download or provider substitution occurred.

Bengaluru JSON SHA-256 `99e9adb075ab9a0938f6dbaa6424f89690143c1dcfe76484b45af48fb59194c8`; Lisbon `f52f4dddd18e7c3a4423e715803d91a3362f97db5d93e94224b8d1fdaa49c2f2`. The configured loopback database was upgraded from 0010_concierge to 0011_phase3. Before/after counts stayed users=1, trips=3, itinerary_items=2, datasets=2; no legacy money or dataset conversion occurred. Application/Vite helpers were restarted on 127.0.0.1:8000/5173; independent HTTPX requests (environment proxies disabled) returned 200 for live/ready/gateway and the frontend root. Local process IDs/logs remain ignored.

## Failures and limits

An explicit live-model run initially failed because Ollama was stopped; that run had 109 backend passes and one real-model connection failure. After the existing local runtime was started/preloaded, all 110 passed. Earlier runs also exposed startup recovery blocking liveness, missing same-sequence rail invalidation, weighted-pin batch inserts hardcoding weight 1, old-version catalog access after activation, and test cleanup/fixture errors. Those failures were corrected and are not counted as passes. Frontend edits during a browser wait initially caused Vite reloads and loss of the intentionally in-memory access token; the accepted run held frontend sources fixed. Validation diagnostics are bounded and logs redact environment credentials/JWTs; no credentials are included here.

Known limits: provisional election/business defaults; synthetic-only recommendation evaluation; historical pre-Phase-3 session duration may be unknown; one-worker room ownership; volatile move acknowledgements until committed watermark; local model cold loading/contention can still trigger the unchanged grounded fallback. No sync/API/AI P95, load/capacity, 50-planner attainment, complete security matrix, backup/restore or final submission is claimed. TASK-021–025 remain Phase 4 work.
