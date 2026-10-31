# Decisions and unresolved rules

Status: design baseline established 2026-10-29; partial implementation exists. See PHASE_1_EVIDENCE.md for actual results. Source [PRD](../Document/Project%20Document.docx) §§4,6–10,13–15. Selected track/stack decisions are finalized for this documentation; domain defaults below remain provisional pending implementation review.

| ID | Decision, alternatives and consequence | Status/source |
|---|---|---|
| ADR-001 | Track A: React client. Track B saves UI work but adds harness/generator evidence and retains backend depth. | Selected; §4.3 (the §2 reference to 4.4 is a PRD typo) |
| ADR-002 | Python/FastAPI native WebSockets + PostgreSQL + SQLAlchemy async/asyncpg + Pytest. Java has reactive/blocking integration overhead; MERN shares JavaScript but adds Python-free model tooling effort and requires MongoDB. One modular backend fits solo delivery. | Selected; §§8,9.3 |
| ADR-003 | Account Admin privilege separate from per-trip Viewer/Planner/Leader. Do not trust JWT role claims alone after membership changes. | Provisional; global role examples in §7.2 conflict with §5 room assignment |
| ADR-004 | Compare-and-reject `positionVersion`; first valid server arrival wins that version. Never auto-retry stale intent. Explicit conflict includes current item. This supersedes §6.1 LWW wording per request and §§7.2,9.4. | Selected resolution of contradiction |
| ADR-005 | One application worker owns all in-memory room actors. Each room processes commands in arrival order; DB conditional updates check durable base version, without SELECT FOR UPDATE. Multiple rooms remain independent. | Selected; §9.4; multi-process deferred |
| ADR-006 | 100 ms batch flush default, memory-applied updates explicitly volatile until commit event; lock/vote/moderation/chat require durable commit before final success. No claim that all acknowledgements survive crash. | Provisional; §9.4 does not specify durability |
| ADR-007 | Viewer reads/chats/asks but cannot vote; Planner/Leader vote. Leader can restrict a Planner to vote-only via `canPin=false`; membership role remains Planner. | Provisional; §5.1's pin-versus-only-vote setting otherwise ambiguous |
| ADR-008 | Votes: fixed eligible membership snapshot, one changeable vote/person before deadline, no quorum, abstention is no vote, tie by stable ascending candidate ID, zero votes cancels to Drafting. Removed voters' ballots invalidated; new joins cannot vote in existing round. | Provisional; §6.2 omits election details |
| ADR-009 | Default vote 60 s; server receipt at deadline is late; eligible identity snapshot excludes Viewers. System auto-opens once for ≥2 drafting candidates in identical day/time slot with shared attendees; partial overlaps notify only. | Provisional; §6.2 |
| ADR-010 | Leader disconnect after last socket: visible immediately, freeze finalize/override/open-vote/settings until reconnect; no automatic promotion. Existing timed votes still resolve by server authority. Explicit transfer only to active Planner and durable atomic role swap. | Provisional choice of allowed §6.1 behavior |
| ADR-011 | Room lock rejects new joins and board/vote commands except Leader unlock/moderation; existing chat/read/ask work. Existing vote timer resolves to preserve its contract. Finalized trip is read-only including chat. | Provisional; room lock meaning absent |
| ADR-012 | One currency EUR, 2 decimals per trip, no conversion. Public `totalBudget` decimal string, internal minor-unit integers. Categories lodging/food/activity/transit. | Provisional; §§6.2,7.3 omit precision/categories |
| ADR-013 | Explicit attending members per item, default active members at pin; attendees frozen until versioned edit. Nonnegative integer weights, positive sum; stable user-ID remainder ordering after largest fractional remainders. | Provisional; split details unspecified |
| ADR-014 | Hard category ceiling = requester's category ceiling or group category default; optional request ceiling can tighten only. Attendee diets union; unknown required metadata excludes candidate. Total and personal budgets flagged separately. | Provisional precedence; §6.2 vs §5.3 |
| ADR-015 | Destination IANA timezone; UTC persisted intervals with offset-bearing input; reject ambiguous/nonexistent local times unless explicit valid offset. Hours expand by date; overnight close has day offset. Buffer extends requested start backward, default 30 min. | Provisional; §6.2 direction unspecified |
| ADR-016 | Haversine distance; no anchor disables radius and assigns constant proximity 1 (weights unchanged); stable ID tiebreak. Rating divided by 5; price headroom divided by ceiling. | Provisional normalization; §6.2 |
| ADR-017 | PostgreSQL full-text retrieval with deterministic matching/ranking remains selected. The PRD permits any hosted API or local open-source model for grounded generation. Ollama is not a PRD requirement. The user subsequently selected local open-source inference; the implemented provider is portable Ollama 0.40.13 with Qwen2.5 1.5B, validated in Phase 2. Model output requires application validation regardless of provider. | Revised 2026-10-31 per user; §§4.2,8.1,15 |
| ADR-018 | Canonical citation `venue:<id>@<datasetVersion>`; `sourceEvents` retained compatibility name. Walking minutes require an authored transit record, never proximity inference. | Selected correction of inconsistent §7.3.3 identifiers/example |
| ADR-019 | Recommendation item-neighbor CF + content cosine, equal blend; batch train within app CLI, reload atomic model version and immediately rerank fresh user history. | Provisional simple hybrid; §6.3 |
| ADR-020 | Minimum dataset size recommendation 12 venues/lodgings, 4 transit edges, 3 dated weather entries; only coverage, not these counts, required. Reduce counts/complexity before correctness/testing/docs. | Recommendation; §14.1 |
| ADR-021 | Documentation first overrides scaffold-now wording; application code begins only on subsequent user request. | Required user instruction; §13.2 deviation |

## Decisions to revisit before coding affected modules

Review ADR-007–016 with stakeholder before behavior is treated as final; safe defaults permit planning but do not assert PRD specificity. The selected local model tag/digest and smoke-test results are recorded in PHASE_2_EVIDENCE.md; the 3 s P95 target is especially risky. Review whether crash loss of volatile moves is acceptable; durable-every-move logging is an alternative with measurable latency cost. Any stronger guarantee must change protocol, persistence and tests together.

No booking/live integration or required-feature deferral is proposed. Plain SQL retrieval instead of embeddings is a deliberately small RAG implementation, not removal of retrieval. Asyncpg avoids obsolete Motor guidance because PostgreSQL is selected; no MongoDB driver is installed. Versions and official references are maintained in [environment setup](ENVIRONMENT_SETUP.md).

## 2026-10-30 implementation note

Preliminary create/join idempotency responses are encrypted at rest using a domain-separated key derived from the local JWT signing secret, so replay can return the original one-time invite without storing it as plaintext. Changing that secret makes retained responses unavailable. This is an implementation choice, not a change to the provisional 24-hour replay policy; automated expiration cleanup remains to be implemented.

## PRD alignment revision — 2026-10-31

Per the user's instruction to build around the original project document, ADR-017 no longer mandates Ollama. PRD §§4.2/8.1 allow a hosted API or local open-source model. Provider selection is pending; the application must still implement deterministic filtering, grounded generation, citation validation and a real-model demonstration. See [alignment review](PRD_ALIGNMENT_REVIEW.md) for remaining scope and explicit user overrides. No acceptance checkbox changes result from this revision.

## Phase 2 decision follow-up — 2026-10-31

The user explicitly selected **local open-source inference** after the PRD alignment review. Ollama 0.40.13 with Qwen2.5 1.5B is now the concrete implementation choice for ADR-017, rather than a requirement attributed to the original document. The approximately 986-MB Apache-licensed model was chosen to keep local generation small enough for the observed hardware; the exact digest, real results and cold/fallback limitations are in [Phase 2 evidence](PHASE_2_EVIDENCE.md). Request-specific structured output requires one eligible candidate and allowlisted fields; no-match is decided before generation and factual prose is rendered by the application.

The Phase 2/3 boundary follows PRD §11.1: Week 2 provides pin/move/lock lifecycle rules and a working grounded request; Week 3 provides contested elections, ballots/timers and winner/conflict/budget orchestration. Pure Voting lifecycle projections exist and are tested; no live timed election is claimed yet. This preserves the final required feature and ordered TASK-014/015/016 dependencies.

No other provisional domain default is silently finalized. Room absence freezes restricted Leader actions; transfer requires a connected active Planner. Group defaults and self category/diet preferences are versioned separately from total-budget accounting. User overrides of CAS and the selected Python stack remain authoritative.
