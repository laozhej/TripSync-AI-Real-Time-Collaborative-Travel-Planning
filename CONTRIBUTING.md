# Contributing

TripSync AI is a collaborative trip planner built as an educational project.

1. Follow the [local setup guide](docs/ENVIRONMENT_SETUP.md). Run `./scripts/setup-local.ps1` from the repository root in PowerShell after configuring PostgreSQL and `.env`.
2. Run the [backend checks](docs/ENVIRONMENT_SETUP.md#verification-and-current-limits). From `frontend`, run `npm run test:unit` and `npm run build`.
3. Open a pull request with the related issue or task, a summary of the change, and the checks you ran. Include screenshots for visible changes.

Use [Discussions](https://github.com/ravadakaran/TripSync-AI-Real-Time-Collaborative-Travel-Planning/discussions) for questions and [Issues](https://github.com/ravadakaran/TripSync-AI-Real-Time-Collaborative-Travel-Planning/issues) for bugs and feature requests.

The maintainer watches Issues, checks the queue daily at 7 p.m. IST, and aims to reply within 24 hours with a next step or a request for missing details.

Start with one TASK-ID from [the backlog](docs/TASKS.md), read its REQ IDs and original PRD sections, then inspect [decisions](docs/DECISIONS.md). Keep changes small enough to test and explain in one commit. Suggested branches `feature/task-008-board-cas`; commit messages `feat(board): reject stale moves (TASK-008, REQ-006)`. No extra engineer/reviewer is required; do a deliberate self-review before merging a working increment.

Use Python formatting/lint tools selected and pinned at scaffold; JavaScript React follows one consistent formatter. Domain functions remain transport independent. HTTP/socket share policy and services; do not duplicate budget/matching/lifecycle logic. SQL schema snake_case maps explicitly to camelCase contracts. No application framework outside selected Python stack. All dates, money, citations and version semantics follow primary docs.

For each feature: add meaningful unit/domain cases, real-DB integration for persistence, role-negative cases for both transports and browser/harness evidence where necessary. Run relevant checks first, then full required suite at milestone. Save actual outputs during implementation; never copy an expected number into a results table. Tests are part of feature completion, not deferred to Week 4. Update the owning document and traceability if contracts/decisions change; cross-link instead of duplicating rules.

Self-review checklist:

- [ ] REQ/TASK/PRD links explain the scope; no required behavior silently removed.
- [ ] Input versions/identity/capabilities validated on server; no body userId authorization.
- [ ] Money exact, diets/hours/budget/radius hard constraints preserved, citations resolvable.
- [ ] Persistence acknowledgement/recovery and vote timer failure paths handled.
- [ ] Relevant positive, boundary, concurrent and forbidden-action tests actually run.
- [ ] Secret scan and safe logging reviewed; .env/credentials/dumps/evidence sanitized.
- [ ] Primary docs/setup commands reflect actual build; unverified claims remain labeled.
- [ ] Incremental commit captures one working change, with known limitations recorded.

Before final submission reproduce setup from clean DB/environment using README alone, complete [demo checklist](docs/DEMO_AND_SUBMISSION.md) and compare artifacts against [traceability](docs/TRACEABILITY_MATRIX.md). Public deployment, payment/live API integration and broad refactors are not implied by contributing. Scope changes require explicit decision/rationale and updated affected docs; do not remove tests/docs to fit schedule (§14.2).
