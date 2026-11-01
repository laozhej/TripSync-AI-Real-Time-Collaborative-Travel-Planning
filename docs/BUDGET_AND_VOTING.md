# Exact budgets and contested voting

PRD §§1.3,3,5.3,6.1–6.2,7.2. No budget calculations below are measured application results; they are manual expected fixtures. [ADR-008–015](DECISIONS.md) are provisional domain rules, not PRD claims.

## Money and ceilings

INR for the Indian baseline, integer paise (`bigint`); legacy EUR rooms retain integer cents, no currency conversion or floating-point arithmetic. Parse major-unit decimal strings once at API boundary; >2 fractional digits rejected, not silently rounded. Positive venue price per person; item cost is snapshot price × attendee count. Lodging also uses per-person slot price in this prototype; nightly multi-room pricing is outside the dataset convention and must not be inferred. Transit prices follow authored per-person metadata. No payment occurs.

Per-category ceilings food/lodging/activity/transit constrain Concierge price-per-person. Total trip budget and each participant's total ceiling constrain cumulative allocations and generate budgetBreach alerts. Different ceilings are never conflated. Hard filtering never treats total budget as category budget without explicit configured category defaults. Attending members are explicit and versioned; membership changes do not silently reallocate existing costs.

Even split: for T cents and n attendees, q=T div n, r=T mod n; allocate q then one extra cent to first r ascending stable user IDs. Weighted split: nonnegative integer weights w_i, W=sum>0; base_i=(T*w_i) div W; remainder=T-sum(base). Give remaining cents to descending fractional remainder `(T*w_i) mod W`, ties ascending user ID. Zero-weight users receive zero; require total>0 and no negative weights. Sum allocations exactly T; allocations never negative. Use integer products with overflow checks at ingress (provisional maximum total 10^12 minor units).

| Manual fixture | Expected allocations |
|---|---|
| Even T=1000, users A/B/C | 334/333/333 |
| Even T=1, users A/B/C | 1/0/0 |
| Weighted T=1000, A:B:C=1:2:3 | 167/333/500 |
| Weighted T=1, A:B=1:1 | 1/0 |
| Weighted T=100, A:B=0:1 | 0/100 |
| Empty attendees, negative weight, all-zero weights, mixed currency | Reject with 422 |

Running totals sum allocations across active, nonremoved items. Expose Locked committed totals separately from proposed totals. Drafting alternatives in an open vote count as one slot reservation: per-person reservation is maximum allocation over its candidates, a conservative ceiling; Locked winner replaces reservation at resolution. This avoids summing mutually exclusive alternatives. Budget response identifies reservation method and per-item allocations so reviewers can reconcile. Drafting items outside a vote count normally; resulting advisory conflicts do not block pinning but must be resolved before finalization. All deltas are recomputed atomically on attendees/split edits and vote application.

## Item lifecycle

| From → to | Actor/trigger | Conditions |
|---|---|---|
| Drafting → Drafting | Planner canPin/Leader | pin/move/edit/remove, current version |
| Drafting → Voting | Leader or deterministic system | ≥2 candidates same slot, no existing open vote, versions match |
| Drafting → Locked | Leader | current version; no open vote involving item |
| Voting → Locked | System vote resolution | winning candidate, transaction applies winner |
| Voting → Drafting | System cancellation/losing options | zero votes cancels all; losing options return unpinned archive |
| Locked → Drafting | Leader override | explicit reason; advance version and notify |

Losing options are removed from active board and archived with vote history, so they do not continue charging budgets or triggering overlap. A Lock override requires unlock first; no hidden Planner edit bypass. Voting freezes location/attendees/cost options until resolution. The system can resolve a previously opened vote while Leader disconnected or room locked; new Leader-authorized actions remain frozen per ADR-010/011.

## Vote lifecycle and resolution

Open command contains option item IDs/versions and a common day/start/end/attendee set; venue IDs must be distinct to preserve PRD choiceVenueId mapping. Eligible voter snapshot includes active Planners/Leader at open, one identity regardless of sockets. Viewers excluded provisionally; `canPin=false` Planner may vote. Deadline server UTC, default now+60 s, provisional allowed range 10..300 s. Late boundary is `receivedAt >= closesAt`, including a command sent before deadline but arriving late.

One ballot per voter per vote; changes permitted before deadline with expectedBallotVersion, stale update rejected. Abstention means no ballot; no quorum. Count only currently eligible/nonremoved voters from original snapshot; joins after open excluded. Removed user cannot vote and prior ballot is invalidated transactionally. A leadership transfer does not add the former Viewer to an existing election.

At deadline actor marks resolving, loads committed ballots, ranks by vote count then lexicographically ascending canonical venue ID. Any positive turnout resolves; zero turnout cancels to Drafting and emits reason. Winner transitions Locked in same transaction as tally/result, removal of losing active options, budget recomputation and conflict updates. Increment every affected item's positionVersion and roomSeq; broadcast complete affectedItems result only after commit. Duplicate timers/restarts cannot apply twice: unique resolution event per vote and conditional status=open update.

System opening is required (§6.2): on identical-slot contested candidates, auto-open once after second eligible item; idempotent slot key prevents duplicate elections. Partial overlaps merely notify. If the room is locked, defer new auto-open until unlock; show conflict. After crash, overdue persisted vote resolves once before readiness; never extend closesAt. A failed resolution commit leaves vote open/overdue and room writes frozen until recovery, never announces an uncommitted winner.

## Planned checks

BUD-01 manual even/weighted fixtures, zero/large totals and permutations; BUD-02 property sum/allocation/nonnegative checks and exact running totals; BUD-03 category versus group/personal ceiling and vote reservation. VOTE-01 eligibility and duplicate tabs; VOTE-02 boundary/changes/abstention/ties/no turnout; VOTE-03 crash and duplicate timer; VOTE-04 all clients apply identical winner/budget and permission-denied edits leave state untouched. Correctness target 100% agreement, results pending.

## Phase 2 implementation note — 2026-10-31

A standalone, tested board lifecycle rule module exists for move/remove/lock/unlock permissions and stale-version rejection. It is not connected to the room actor, API, database, or browser, and does not yet implement vote transitions or durable operations. The behavior above remains provisional and TASK-008 is not complete. See [test evidence](PHASE_1_EVIDENCE.md).

The live room now invokes the provisional move/remove/lock/unlock rules; a successful lock or unlock commits before broadcast. Voting transitions remain unimplemented and the full lifecycle acceptance remains open. See [evidence](PHASE_1_EVIDENCE.md).

## Phase 2 lifecycle acceptance — 2026-10-31

The live board implements Drafting pin/move/remove and durable Leader lock/unlock; `begin_voting` and `resolve_voting` implement the internal versioned lifecycle projections, validate common slots/attendees, freeze Voting edits, and distinguish cancellation from archived losers. They are not public commands and do not create elections on their own. TASK-016 must call and persist these primitives with eligible voters, deadlines, ballots, winner/conflict/budget application. No timed vote workflow is claimed in Phase 2. The exact-budget rules and all Phase 3 requirements above remain mandatory.

### Indian currency override (2026-10-31)

New Indian trips use INR. Integer minor units mean paise: INR350.00 = 35000 paise; a ₹25,000.00 group budget = 2500000 paise. Ceilings and totals keep exact integer math and remainder allocation; formatting uses en-IN grouping. Legacy EUR rooms retain euro cents. No implicit currency conversion or mixing is permitted. This supersedes the earlier provisional EUR-only choice.

## Phase 3 implementation — 2026-11-01

`app/budget/engine.py` implements integer largest-remainder allocations and per-person maximum vote reservations. The manual fixtures and conservation checks ran with `python -m pytest backend/tests/test_budget.py -q`: 9 passed. `app/concierge/conflicts.py` detects exact interval overlaps for shared attendees and separate total/personal budget breaches; immutable fingerprint history is persisted with room transactions. This supersedes the historical Phase 2 notes above; full Phase 3 acceptance is recorded separately in PHASE_3_EVIDENCE.md.
