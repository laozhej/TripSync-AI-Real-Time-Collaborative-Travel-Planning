# Required deliverables readiness — 2026-11-03

PRD §12.1 deliverables are present in the repository. The current implementation includes the destination and personal-activity side quests. Performance target outcomes remain those measured in PHASE_4_EVIDENCE.md.

## Deliverable map

| Required deliverable | Submission artifact |
|---|---|
| Incremental Git repository | Git history includes foundation, feature, recovery, UI, performance and submission commits. The side quest source and documentation follow-up have separate commits. |
| Stack-specific README and setup | [README](../README.md), [setup](ENVIRONMENT_SETUP.md), dependency locks and .env.example. Current migration is 0012_personal_activities. |
| Architecture overview | [Architecture](ARCHITECTURE.md) describes actual room ownership, module paths, persistence and local deployment. |
| Full API reference | [REST reference](API_SPECIFICATION.md) covers all 37 registered operations. [Socket reference](WEBSOCKET_PROTOCOL.md) covers 17 client commands including aliases and 21 server events. Request examples were validated against application models. |
| Implemented database schema | [Schema](DATABASE_SCHEMA.md), Alembic migrations and [extracted columns/indexes](../evidence/contracts/schema.json). The ER view includes the personal activity source relationship. |
| Seed/sample data | [Bengaluru](../data/destinations/bengaluru.json), [Goa](../data/destinations/goa.json), [Lisbon](../data/destinations/lisbon.json), importer and Admin validation. |
| Automated test suite | backend/tests covers board lifecycle, concurrency, budget, constraints, permissions, recovery and integration. frontend/tests covers timezone/slot behavior. |
| Retrospective | [Retrospective](RETROSPECTIVE.md) covers scope, implementation, failures, limitations and next steps. |

## Current verification

Executed locally on Windows with Python 3.13.1, Node 24.13.0, Vite 7.3.7 and Chrome 156.0.8078.79. PostgreSQL tests use fresh disposable databases with migrations through 0012 and the checked-in destination files. Local inference uses the existing Qwen2.5 1.5B/Ollama setup documented in ENVIRONMENT_SETUP.md. These are correctness and reproducibility checks, with no new performance benchmark claims.

| Command | Observed result | Retained output |
|---|---|---|
| RUN_LIVE_MODEL=1 .venv/Scripts/python.exe -u backend/tests/clean_setup.py | 117 passed, no skips, 1 warning, 104.46 seconds | [Backend](../evidence/tests/submission-followup-backend.txt) |
| node --test in frontend | 8 passed | [Frontend](../evidence/tests/submission-followup-frontend.txt) |
| npm run build in frontend | Production build succeeded | [Frontend](../evidence/tests/submission-followup-frontend.txt) |
| browser_clean_setup.py browser_side_quests.py with ports 8017/5187 | Destination default/selection, two-client personal activity sync/move, separate room isolation and reload/rejoin passed | [Browser](../evidence/tests/submission-followup-browser.txt) |
| Input regression mutation check | Removing control-character validation caused the existing invalid-input test to fail. The original source was restored before final verification. | Recorded here |
| Restore test within the full backend run | Fresh database migrations, logical backup reconciliation and recovery passed | [Restore](../evidence/operations/submission-followup-restore.json) |

The browser test first failed because the destination control lacked a stable accessible label. Adding an explicit label resolved that failure. The earlier implementation run caught a readiness check pinned to migration 0011, which was updated to 0012. Both corrections are included in the passing verification above.

## Packaging and limitations

Run scripts/scan-submission.py followed by scripts/package-submission.py. The refreshed archive is .local/tripsync-phase4-submission.zip and evidence/submission-manifest.json records included files and SHA-256 hashes. The archive contains source, docs, tests, sample data and sanitized evidence. Git history is supplied by the repository itself. Private environment files, database dumps, model/runtime files and dependency/build directories are excluded by the existing packager.

The scan checks configured long secret values and selected credential signatures in current files and reachable history. Its scope and limitations are in evidence/security/secret-scan.json. Packaging is followed by verifying every manifest checksum against the archive and worktree.

The development database needs migration 0012 and the Goa import to expose the new destination. Verification uses disposable databases. Historical performance limits include a missed strict maximum sync target, cold-model fallback, and unestablished rendered-AI P95 and 50-distinct-planner capacity. The prior measured results remain in PHASE_4_EVIDENCE.md. Provisional business defaults remain labeled in DECISIONS.md.
