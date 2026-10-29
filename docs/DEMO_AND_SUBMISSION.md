# Demo and final submission

Planning template, PRD §§12–15. Every application checkbox is pending. Documentation-only delivery is not the final working-project submission.

## Repeatable demonstration

Prerequisites after implementation: verified setup, one fully validated destination, test Leader/Planner/Viewer and separate Admin account, a second browser/session, local model warm and cold profiles recorded, clean isolated trip and enabled safe event capture. Use synthetic data/accounts and no actual payments.

1. Register/login; Leader creates room with budget/dates/capacity and invites Planner and Viewer. Show trip-scoped roles and Admin upload authorization.
2. Two sessions join and receive identical full snapshot. Both pin/move day-by-day activity/lodging items; record server/client versions and timing.
3. Issue simultaneous moves with identical expected version: show winner and explicit stale-write notice; clients converge. Drop/reconnect one session; show snapshot, same identity/chat context and Leader absence behavior.
4. Chat/type/react; mute Planner briefly and prove rejected chat. Demonstrate remove/room lock/transfer/lock override with dedicated fixture if main flow would be disrupted.
5. Ask constrained dinner question; show filter inputs/valid candidates, real model-backed grounded response and canonical citations. Show no-valid-candidate and separately disclosed model outage fallback; no unsupported walking/weather claims.
6. Pin a shared-attendee schedule overlap or budget breach; show notification and resolve by edit/vote. Record ≥95% timing test separately from single demonstration.
7. Open timed contested-slot vote (also exercise system auto-open fixture), cast/change ballots, wait deadline, show deterministic result and winner/budgets applied to all clients.
8. Show manually expected even/weighted cents and running totals. Finalize only after resolving active conflicts/votes. Show history/preferences/rejoin, hybrid rail and fresh interaction changing recommendations without redeploy.
9. Admin stages valid dataset and activates; invalid dataset rejects with field errors. Existing trip retains dataset version. Show session analytics matching saved manual ledger, including final per-person budget.
10. Present automated test output, security rejections for all roles and measured distributions/limitations. Run a clean setup reproduction and write retrospective.

## Final evidence packing list

- [ ] Incremental Git history and source matching actual docs/schema/contracts (not one final bulk commit).
- [ ] Verified README setup/run/test path for chosen Track A/Python stack.
- [ ] Architecture, ER diagram, REST/socket examples and explicit implemented-versus-proposed status.
- [ ] Seed/sample destination coverage, provenance and valid/invalid fixtures.
- [ ] Actual board/constraints/budget/RBAC tests with raw output; integration and security/failure cases.
- [ ] Multi-session concurrent edit/reconnect recording or script output, stale notice and full snapshot.
- [ ] Real grounded Concierge generation/citations plus no-match and unavailable-model behavior.
- [ ] Conflict detected/resolved, timed election opened/cast/resolved/applied, exact budget demo.
- [ ] Dashboard/preferences/history, Admin ingestion, hybrid refresh and Precision@5 report.
- [ ] One manually reconciled analytics session ledger and final budget.
- [ ] Real sync/API/AI/fan-out/join/conflict measurements with hardware/network/clock/client counts and failures.
- [ ] Retrospective and explicit limitations/deviations; secrets scan of repository/history/evidence.

## Evidence templates (empty by design)

| Evidence ID | Requirement/test | Command or scenario | Environment/commit | Actual result | Artifact |
|---|---|---|---|---|---|
| EV-BOARD | REQ-005/006/008; BOARD-02/SYNC-01 | pending implementation | pending | NOT RUN | pending |
| EV-AI | REQ-012–017/021; AI-01..07 | pending implementation | pending | NOT RUN | pending |
| EV-VOTE | REQ-018–020; BUD/VOTE/CONFLICT | pending implementation | pending | NOT RUN | pending |
| EV-SEC | REQ-002/003/009/025/029 | pending implementation | pending | NOT RUN | pending |
| EV-REC | REQ-022/023; REC-01..05 | pending implementation | pending | NOT RUN | pending |
| EV-ANA | REQ-024; ANA-01 | pending implementation | pending | NOT RUN | pending |
| EV-PERF | REQ-030; PERF-01..03 | pending implementation | pending | NOT MEASURED | pending |
| EV-OPS | REQ-027/028; OPS-01..02 | pending implementation | pending | NOT RUN | pending |
| EV-DOC | REQ-001/026/031/032/033 | clean setup/demo/docs review | pending | implementation review pending | pending |

Measurement record: date, commit, stack/model/dataset versions, CPU/RAM/GPU/OS, network, clock calibration/uncertainty, warmup, client/room counts, seed, sample count, successes/timeouts/errors, P50/P95/max, target, pass/fail with explanation, raw sample path. Leave actuals pending until run; no example “passing” numeric results.

Manual session ledger columns: eventId,sessionId,roomSeq,serverTime,actor,event,connection first/last,questionId,conflict fingerprint/state,item allocations,committedSeq. Independent reviewer computes duration/peak/questions/flags/resolutions/final cents and compares exactly.

Retrospective template: what actually shipped; missed/changed requirements with PRD references and reason; evidence limitations; largest engineering failure and recovery; model/data constraints; next steps if more time; first-time setup issues. Evaluation rubric (§15.2): real-time 25%, AI/logistics 30%, dashboard/recommendations/analytics 10%, architecture/modeling/API 15%, security/tests/performance 15%, docs 5%. These are weights, not earned scores.
