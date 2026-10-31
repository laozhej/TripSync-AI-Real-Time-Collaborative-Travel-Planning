# India localization evidence

Date: 2026-10-31. Explicit user instruction after Phase 2: make the project follow India. This supersedes the earlier provisional Lisbon/EUR default; the original source DOCX and historical acceptance logs remain intact.

## Implemented

- New UI-created trips: Bengaluru, India; INR; Asia/Kolkata. Default sample group budget ₹25,000.00. Interface language metadata is `en-IN`; monetary display uses Indian grouping.
- Costs and ceilings remain exact integer minor units: 100 paise = ₹1. Budget events and Concierge answers use the actual trip currency, including retained EUR rooms. There is no exchange-rate conversion or relabeling of existing data.
- Indian board cells, selected-time moves, drag/drop and Concierge inputs use IST (UTC+05:30). Network/storage timestamps remain UTC/offset-aware instants, with destination-local day indexes. Midnight IST correctly belongs to the previous UTC date.
- New immutable, project-authored `data/destinations/bengaluru.json`: six fictional venues, dietary coverage, over-budget and restrictive/overnight examples, lodging, radius boundaries and synthetic transit/weather. These are authored test facts, not real prices, verified establishments or forecasts.
- The configured development database received Bengaluru as an additional destination. Existing Lisbon versions/trips were retained. No schema or monetary rewrite was required.

## Verification

Commands run from the repository root:

```powershell
$env:RUN_LIVE_MODEL='1'
.\.venv\Scripts\python.exe backend/tests/clean_setup.py
npm run test:unit --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python.exe backend/tests/browser_clean_setup.py
```

Backend: **92 passed, 1 warning in 72.44 seconds**, using a newly created PostgreSQL database, migrations through `0010_concierge`, and imports of both Indian and legacy datasets. The database was removed. The new Indian integration test verifies INR creation, exact paise totals, IST input, socket budget currency, grounded currency rendering and pinned INR source resolution; model output is explicitly mocked in that test. The opt-in real-model backend acceptance remains separate and passed in this run.

Frontend: **8 tests passed**, including the IST-midnight conversion and trip-boundary test. Production Vite build succeeded with 27 modules. Two isolated Chrome sessions passed against the Indian dataset: IST selected moves and native drag/drop, INR category ceilings, actual grounded local-model generation and citation resolution, chat/reactions, token expiry/refresh, reconnect and Leader moderation/removal. One observed join-to-snapshot interval was 245.4 ms; this is not a performance benchmark. Temporary browser servers and database were removed.

Runtime/model/hardware versions and earlier crash/outage evidence are in [Phase 2 evidence](PHASE_2_EVIDENCE.md). No additional performance, legal-compliance or real-travel-data claim is made by this locale change. Later required Phase 3/4 work remains open.
