# Demo and final submission

Submission guide, PRD §§12–15. The application and automated walkthroughs are implemented; actual evidence and missed targets are in [Phase 4 evidence](PHASE_4_EVIDENCE.md). The independent local prototype has no Airbnb affiliation. Measured sync misses and cold/model/render limitations remain explicit; a packed submission does not certify every KPI.

## Repeatable demonstration

For a first room-creation/join/pin check, start with the [two-browser walkthrough](TWO_BROWSER_WALKTHROUGH.md), then continue with the complete sequence below.

Prerequisites: verified setup, authored Bengaluru destination, synthetic Leader/Planner/Viewer and Admin accounts, a second browser/session, the local model running, and a clean isolated trip. Use only synthetic data/accounts and no actual payments. The reusable disposable-browser scripts are the recorded executable walkthrough; model-related scripts should run sequentially.

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

- [x] Incremental Git history and source matching actual docs/schema/contracts (not one final bulk commit).
- [x] Verified README setup/run/test path for chosen Track A/Python stack.
- [x] Architecture, ER diagram, REST/socket examples and explicit implemented-versus-proposed status.
- [x] Seed/sample destination coverage, provenance and valid/invalid fixtures.
- [x] Actual board/constraints/budget/RBAC tests with raw output; integration and security/failure cases.
- [x] Multi-session concurrent edit/reconnect recording or script output, stale notice and full snapshot.
- [x] Real grounded Concierge generation/citations plus no-match and unavailable-model behavior.
- [x] Conflict detected/resolved, timed election opened/cast/resolved/applied, exact budget demo.
- [x] Dashboard/preferences/history, Admin ingestion, hybrid refresh and Precision@5 report.
- [x] One manually reconciled analytics session ledger and final budget.
- [x] Real sync/API/AI/fan-out/join/conflict measurements with hardware/network/clock/client counts and failures.
- [x] Retrospective and explicit limitations/deviations; secrets scan of repository/history/evidence.

## Evidence index

| Evidence ID | Requirement/test | Command or scenario | Environment/commit | Actual result | Artifact |
|---|---|---|---|---|---|
| EV-BOARD | REQ-005/006/008; BOARD-02/SYNC-01 | scripted 20 races + Chrome drag/reconnect | Windows/local, Phase 4 source commits | converged; explicit stale rejections; strict sync maximum missed | evidence/performance; browser scripts; PHASE_4_EVIDENCE.md |
| EV-AI | REQ-012–017/021; AI-01..07 | actual local generation + rules/fallback tests | Qwen2.5 1.5B / Ollama 0.40.13 | 99/100 warm grounded; cold and 1 warm fallback; valid canonical sources | ai-samples.json; browser-concierge.txt |
| EV-VOTE | REQ-018–020; BUD/VOTE/CONFLICT | Phase 3 Chrome + restored overdue ballot | PostgreSQL 18.1 | winner applied; conflicts resolved; exact INR fixture restored | backend/tests/browser_phase3.py; operations/restore.json |
| EV-SEC | REQ-002/003/009/025/029 | complete backend suite, focused security and history scan | Phase 4 source | role/isolation/input cases exercised; scan scope bounded | tests/backend-clean.txt; security/secret-scan.json |
| EV-REC | REQ-022/023; REC-01..05 | frozen held-out evaluation + actual interaction refresh | seed 7312026 | Precision@5 1.00 on easy synthetic cohorts only | tests/recommendation-evaluation.json; Phase 3 evidence |
| EV-ANA | REQ-024; ANA-01 | independent session ledger / finalized weighted fixture | Phase 3/4 PostgreSQL | exact prior session reconciliation and restored 13333/26667 paise | PHASE_3_EVIDENCE.md; operations/restore.json |
| EV-PERF | REQ-030; PERF-01..03 | 10 sockets / 5 identities / 2 rooms; 1000 moves/reads; 101 final AI requests | same-host loopback | raw distributions retained; maximum sync target missed; render P95 unestablished | performance/*.json; PHASE_4_EVIDENCE.md |
| EV-OPS | REQ-027/028; OPS-01..02 | real process kill/outage, lost ack, pg_dump/restore | disposable databases | exact table digests; new epoch; overdue resolution once | operations/restore.json; recovery_phase2.py |
| EV-DOC | REQ-001/026/031/032 | fresh Python/npm install, extracted contracts and packaging | Track A / one FastAPI worker | automated local reproduction; no independent second-person setup claim | contracts/; submission-manifest.json; RETROSPECTIVE.md |

Measurement record: date, commit, stack/model/dataset versions, CPU/RAM/GPU/OS, network, clock calibration/uncertainty, warmup, client/room counts, seed, sample count, successes/timeouts/errors, P50/P95/max, target, pass/fail with explanation, raw sample path. Leave actuals pending until run; no example “passing” numeric results.

Manual session ledger columns: eventId,sessionId,roomSeq,serverTime,actor,event,connection first/last,questionId,conflict fingerprint/state,item allocations,committedSeq. Independent reviewer computes duration/peak/questions/flags/resolutions/final cents and compares exactly.

The written retrospective is [RETROSPECTIVE.md](RETROSPECTIVE.md). Evaluation rubric (§15.2): real-time 25%, AI/logistics 30%, dashboard/recommendations/analytics 10%, architecture/modeling/API 15%, security/tests/performance 15%, docs 5%. These are weights, not earned scores.

## Reproduce and package

Follow ENVIRONMENT_SETUP.md's Phase 4 block. Default browser verification demonstrates real Concierge/chat/reconnect/moderation; browser_frontend_ui.py demonstrates Viewer restrictions, stale reconciliation and overlap/budget resolution; browser_phase3.py demonstrates ballots/winner, weighted budget, dashboard/Admin/analytics. Their stdout is the executable walkthrough record; no continuous human-narrated video is claimed. The load harness independently demonstrates 20 concurrent-edit races and multi-room equality.

Run `python scripts/scan-submission.py` before `python scripts/package-submission.py`. The ZIP is `.local/tripsync-phase4-submission.zip`, intentionally ignored; `evidence/submission-manifest.json` records source/artifact checksums. The Git repository retains incremental history, while the ZIP excludes Git internals, credentials, ignored model/runtime files, DB archives and dependency/build directories. The manual HTTP collection requires private client variables and does not store working access/invite tokens.
