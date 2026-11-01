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
