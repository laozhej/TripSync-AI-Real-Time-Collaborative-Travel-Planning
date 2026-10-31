# TripSync AI requirements

Status: requirements baseline with partial application implementation; actual coverage is recorded in TRACEABILITY_MATRIX.md and PHASE_1_EVIDENCE.md. Source: [original PRD](../Document/Project%20Document.docx), v1.0, September 2026. Section references below refer to that document. The user's documentation-first request takes precedence over PRD §13.2's immediate scaffolding guidance. TripSync AI is an independent educational prototype with no Airbnb affiliation or integration.

## Interpretation

**Required** means explicit PRD behavior or an explicit instruction in the documentation request. **Selected** means a design choice made for this plan. **Provisional** means a safe working rule needing review, not a claim about the PRD. Requirement completion depends on recorded acceptance evidence; the baseline does not imply that every requirement is implemented. [Decisions](DECISIONS.md) owns ambiguities; [traceability](TRACEABILITY_MATRIX.md) connects requirements to work and evidence.

## Requirement register

| ID | Required behavior | PRD |
|---|---|---|
| REQ-001 | Independent, private/local, solo four-week prototype; exactly one permitted stack; Track A default | §§4,8,11,14 |
| REQ-002 | Register/login, access JWT ≤1 hour, refresh, safe passwords and environment secrets | §10.1 |
| REQ-003 | Server-enforced Viewer, Planner, Leader, Admin permissions on HTTP and sockets | §§3,10.1 |
| REQ-004 | Create rooms with destination/dates/budget/capacity; invite link/code, join and assign membership | §§5.1,6.1 |
| REQ-005 | Day-by-day activity/lodging board, pin/move/remove and lifecycle Drafting → Voting → Locked | §§2,6.1 |
| REQ-006 | Deterministic concurrent edits, positionVersion checks, stale rejection and explicit reconciliation; no explicit row locks | §§6.1,7.2,9.4 |
| REQ-007 | Persisted chat history, typing and emoji reactions | §6.1 |
| REQ-008 | Presence, connection quality, reconnect identity and full board/lifecycle/budget snapshot within 2 s | §§6.1,10.3 |
| REQ-009 | Leader mute/remove, room lock, leadership transfer and item-lock override | §6.1 |
| REQ-010 | Deterministic, visible Leader-disconnected behavior | §6.1 |
| REQ-011 | Authored destination venue/lodging/transit/weather ingestion, validation and retrieval indexing | §§4.1,6.2,14.1 |
| REQ-012 | Hard category price ceiling filter before ranking/generation | §6.2 |
| REQ-013 | Every attending traveler's dietary constraints must be satisfied | §6.2 |
| REQ-014 | Full requested interval including configurable buffer must fit operating hours | §6.2 |
| REQ-015 | Anchored proximity hard filter, configurable default 2 km | §6.2 |
| REQ-016 | Valid-only ranking: proximity 40%, rating/popularity 30%, budget headroom 30% | §6.2 |
| REQ-017 | Grounded RAG answers cite metadata identifiers; invent no venue, price, hours, route or weather facts | §§5.3,6.2,7.3 |
| REQ-018 | Schedule-overlap and budget-breach detection, notifications and resolution tracking | §6.2 |
| REQ-019 | Timed contested-slot vote opened by Leader or system, cast/resolved and winner applied consistently | §§5.3,6.2 |
| REQ-020 | Exact even/weighted splits and running per-person totals | §§1.3,3,13 |
| REQ-021 | Safe no-valid-candidate handling; model outage must preserve hard constraints | §§14.2,15.1; request |
| REQ-022 | Dashboard history, derived preference profile and active-room rejoin | §6.3 |
| REQ-023 | Hybrid content + collaborative filtering from self-generated interactions; refresh without redeploy | §6.3 |
| REQ-024 | Session duration, peak planners, AI count, flagged/resolved conflicts and final budgets reconcile to event log | §6.3 |
| REQ-025 | Admin upload UI/API validates positive prices, dietary vocabulary, coordinates and hours | §§6.3,10.1 |
| REQ-026 | Preserve mandatory REST examples and event envelope/core event names; derive actor from authentication | §7.3; request |
| REQ-027 | Authoritative per-room memory with short batched/significant-transition persistence and documented recovery | §§9.4,10.3 |
| REQ-028 | Structured safe logs with room-session correlation; API and gateway health checks | §10.3 |
| REQ-029 | Input validation, stored-XSS protection, socket handshake authentication and sensitive-action revalidation | §10.1 |
| REQ-030 | Sync <100 ms; non-AI API P95 <200 ms; AI P95 <3 s; fan-out <500 ms; design for 50 and multiple rooms | §§1.3,10.2,14.1 |
| REQ-031 | Feature tests from the start; concurrency, budget, constraints and RBAC automated; honest measured evidence | §§11.2,12,15 |
| REQ-032 | Git history, reproducible setup, schema/API docs, seed data, walkthrough, test output and retrospective | §§12,13 |
| REQ-033 | Track B, if subsequently chosen, retains all backend work and adds HTTP collection, scripted clients, synthetic generator | §4.3 |

## Roles and journeys

Selected scope model: account `isAdmin` grants dataset management; membership role is Viewer/Planner/Leader per trip. All registered accounts may create a trip and become its Leader. Admin does not bypass trip membership or automatically become Leader. This interprets the global `users.role` reference in §7.2; see ADR-003.

| Operation | Viewer | Planner | Leader | Admin account |
|---|---|---|---|---|
| Read member room/history/chat; subscribe; ping | Yes | Yes | Yes | Only with membership |
| Chat/react/type; ask Concierge | Yes | Yes | Yes | Uses membership role |
| Pin/move/remove drafting item | No | Yes | Yes | Uses membership role |
| Vote | No (provisional) | Yes | Yes | Uses membership role |
| Open vote, finalize, override, settings, moderate, transfer | No | No | Yes | Uses membership role |
| Upload/activate datasets | No | No | No unless Admin | Yes |

Leader: authenticate → create → invite/assign → review board/conflicts → vote → lock/finalize. Participant: authenticate → redeem invite → snapshot → collaborate → disconnect/rejoin. Concierge is an internal service actor; it receives no user token capable of changing permissions. System votes use the same voting domain service as Leader commands.

## Business invariants

One active Leader per trip; capacity counts distinct active memberships, not sockets. Removed users cannot rejoin with a formerly valid invite. Items reference one immutable dataset version. Server controls all versions and deadlines. Locked or Voting items cannot be moved by Planners. Only validated candidates reach generation. Budgets use integer minor units; votes and their result application are atomic durable transitions. Multiple browser tabs represent one voting identity.

The initial slice omits later features only temporarily: authentication → create Trip Room → second participant joins → basic server-authoritative board synchronization. Every requirement above remains in the final submission.

## Constraints, dependencies and gaps

No booking, payment, live travel integration, native app, public hosting, CDN asset requirement or multi-tenant infrastructure (§4.2). Minimum one destination covers all dietary tags, over-budget and restrictive-hour examples (§14.1). Model runtime/weights and local hardware are external dependencies; no latency claim is yet supported. Full-time solo effort is the PRD baseline, not a completion guarantee.

Open rules: LWW versus CAS; global roles versus membership; Viewer voting; quorum/ties/abstentions/vote changes; room lock; Leader absence; category and personal ceilings; attendees and weights; currency/remainders; timezone/DST/overnight hours/buffer direction; missing metadata; acknowledged-event durability; source identifier mismatch and unsupported walking claim in §7.3.3. [DECISIONS.md](DECISIONS.md) records each rule and its provisional resolution. No PRD-required functionality is intentionally removed.

## India baseline — user instruction, 2026-10-31

The user requested an Indian project. New UI-created trips use Bengaluru, India, INR and Asia/Kolkata (IST, UTC+05:30). Monetary calculations remain integer paise (100 paise per rupee); display uses Indian currency grouping. The English interface uses Indian conventions. The project-authored Bengaluru dataset is fictional and covers the existing dietary, hours, radius, budget, lodging, transit and weather test shapes; it makes no claims about real establishments, fares or forecasts. Existing Lisbon/EUR trips and historical acceptance evidence are preserved, without currency conversion or relabeling. UTC remains the wire/storage timestamp convention; Indian board inputs/display use IST. These user instructions override the earlier provisional EUR/destination baseline. Other required phases and security/architecture invariants remain unchanged.
