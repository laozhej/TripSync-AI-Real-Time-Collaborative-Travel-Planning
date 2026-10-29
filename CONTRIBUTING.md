# Contributing

This is a solo educational build, currently documentation only. PRD §§11.2–13 require incremental working commits, reproducible setup and honest evidence. No remote repository or commit history is claimed as created by this documentation request.

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
