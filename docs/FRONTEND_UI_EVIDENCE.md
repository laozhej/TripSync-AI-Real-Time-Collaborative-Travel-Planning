# Phase 3 frontend improvement

## Inspection — 2026-11-01

Read the original DOCX in full, README, requirements, decisions, implementation plan, Phase 3 evidence, alignment review, architecture, budget/voting rules, REST/socket contracts and all frontend components. PRD §§6.1–6.3 and §11.1 define this work. This is an independent local educational prototype.

The existing React/Vite client has working server-authoritative board commands, drag/drop and selected-time moves, chat/reactions, Concierge, exact budget snapshots, elections, recommendations, dashboard and Admin ingestion. Most room features share one long sidebar. Resolved conflicts are hidden, vote options omit available board metadata, activation has no confirmation, and there is no theme control. Dataset controls currently use a successful Admin-only response as their visibility gate.

Preserve endpoint bodies, native socket envelopes, version checks, watermark/epoch reconciliation, role capabilities, dataset pinning and backend money calculations. Vote option history includes only IDs/names: historical prices/times must show unavailable when no matching board item exists. Recommendations can join the trip-pinned catalog for authored metadata; never infer prices or constraint validity. No backend application changes planned.

## Increment log

Inspection baseline: clean working tree on main; work branch `codex/phase3-frontend`. `npm --prefix frontend run test:unit`: 8 passed, no failures/skips. `npm --prefix frontend run build`: successful, 31 modules, JS 266.66 kB (81.93 kB gzip). Initial browser runner failed before tests with WinError 10048 on occupied fixed ports; no acceptance inferred.

## Design contract

Operate mode: itinerary first, contextual planning tools alongside, room status always visible. Forest green and teal actions, sage secondary surfaces, warm off-white canvas; dark surfaces with equivalent semantic contrast. Inter, served locally; compact readable labels, tabular money, clear lifecycle badges. Shared badges, section headings, theme control and confirmation dialog. Responsive grid scroll stays inside its region; keyboard users retain selected-time moves. Follow the user's explicit design/system requirements without introducing product scope.

Verification pending for all changed UI. Phase 4 backlog remains open.

### Increment 2 — tokens and primitives

Files: `frontend/src/style.css`, `frontend/src/ui/{Primitives.jsx,format.js}`, `frontend/public/fonts/{Inter.ttf,OFL.txt}`, `DESIGN.md`. Components: shared badges, headings, theme toggle, native confirmation dialog. Existing components retain their handlers and HTML controls. Build passed after token replacement (31 modules); rendered and keyboard verification remains pending. Browser runner gains optional isolated API/web ports with unchanged defaults; Vite proxy target is configurable for tests, with unchanged development default. No backend application behavior changed.

### Increment 3 — workspace and itinerary

Files: `main.jsx`, `board/BoardGrid.jsx`, `board/ModerationControls.jsx`. Added workspace anchors, role/member/status badges, theme control, live connection/committed-watermark status, distinct chat/traveler surfaces, day buttons, activity metadata and activity-focused grid scrolling. Native socket command bodies and authoritative replacement/stale conflict behavior are preserved. The explicit selected-time move remains available alongside drag/drop. Admin mount now uses the login response's existing `isAdmin`; backend checks are unchanged. Frontend tests 8/8, build (33 modules) and `git diff --check` passed. Browser verification of this increment pending.

The isolated-port baseline browser run completed successfully: Phase 3 two participants, weighted split, timed ballots/winner, analytics, model refresh, dashboard history/rejoin, dataset validation/activation and finalized controls; no page errors and 390px overflow passed. The screenshot was inspected. This run preceded the shell changes, so it does not verify them.

### Increment 4 — budgets, elections and conflicts

Files: `votes/PlanningPanel.jsx`, `votes/SplitEditor.jsx`. Separate budget/conflict/vote sections show backend totals, clear attendee/weight editing, selected ballot, timer, winner/cancellation and resolved conflict history. Existing API payloads and server rules are preserved. Errors request authoritative resync without silent retry. Historical vote slots not present on the board are explicitly unavailable; prices join only the pinned catalog. Analytics preserves unknown historical duration and shows per-person totals. Eight unit tests and production build passed; real-browser acceptance remains pending.
