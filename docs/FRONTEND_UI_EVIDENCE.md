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

### Increment 5 — dashboard and recommendations

Files: `dashboard/Dashboard.jsx` (recommendation cards are in the preceding PlanningPanel increment). Trip history/rejoin, favored categories, declared diets and per-currency observed price ranges now have distinct presentation and honest empty/loading states. Recommendations join only the authorized trip-pinned catalog and explain exploratory/model status; a like success appears only after the existing interaction API confirms it. No client recommendation scoring or currency conversion. Eight unit tests and build passed; browser verification pending.

### Increment 6 — Admin lifecycle and activation

Files: `admin/DatasetAdmin.jsx`. Admin-only mount remains derived from authenticated account data, with server authorization intact. Upload limits/field diagnostics, dataset checksums and lifecycle badges, a native confirmation dialog before activation, pending controls and actual model-refresh results are visible. Activation still uses the same endpoint and keeps existing trips pinned. Eight unit tests and build passed. Confirmation and keyboard behavior require the upcoming browser checks.

### Increment 7 — Concierge presentation

Files: `board/ConciergePanel.jsx`, shared CSS. Added a navigable Concierge section, request busy state, result/status badges and authored-source presentation; request bodies, hard-filter/backend ownership and canonical source lookup remain unchanged. Existing stale-answer warning retained. Responsive/keyboard/browser verification follows.

### Browser verification follow-up

Both existing browser programs passed after presentation changes. Phase 1 exercised real Concierge/citations, native drag/drop, selected-time moves, chat/typing/reactions, expired-token refresh, reconnect, moderation/transfer/removal and session revocation. Its single local join-to-snapshot observation was 258.3 ms. Phase 3 exercised weighted splits, timed vote/winner, analytics, recommendations/model refresh, dashboard rejoin/history, invalid/valid staging, activation confirmation cancellation/Escape/focus restoration, finalization/read-only states and widths 390/768/1024. No page errors. Light/dark and mobile screenshots were inspected; captures were then adjusted to disable transitions for stable theme comparison.

An additional three-role browser case is being added for stale move rejection, overlap/budget correction, Viewer chat/read-only controls and no-turnout cancellation. Its first run passed the stale-move/overlap/Viewer paths but failed waiting for the personal budget conflict to clear after an immediate second preference save. This is under investigation, not accepted. Initial axe-core 4.11.0 checks reported zero WCAG A/AA violations for sign-in (18 rules passed) and empty dashboard (17). Full room/dialog/theme audits remain pending.

## Final verification commands

Windows / loopback, one worker per isolated test instance and a distinct disposable PostgreSQL database per run. Application/test dependencies remain the existing environment (Python 3.13.1, Playwright 1.64.1, Node 24.13.0, npm 9.9.4, React 19.3.1, Vite 7.3.7). Existing local Ollama/Qwen was started/preloaded using the existing helper; no provider/model substitution. Backend application code, migrations and API/socket contracts were not changed. Full backend suite and load/restore gates were not rerun for this presentation change; the 110-test Phase 3 result remains historical.

```powershell
npm --prefix frontend run test:unit
npm --prefix frontend run build
./scripts/start-local-model.ps1
$env:BROWSER_API_PORT='18001'
$env:BROWSER_WEB_PORT='15174'
.venv/Scripts/python backend/tests/browser_clean_setup.py
$env:BROWSER_API_PORT='18000'
$env:BROWSER_WEB_PORT='15173'
.venv/Scripts/python backend/tests/browser_clean_setup.py backend/tests/browser_phase3.py
$env:BROWSER_API_PORT='18002'
$env:BROWSER_WEB_PORT='15175'
.venv/Scripts/python backend/tests/browser_clean_setup.py backend/tests/browser_frontend_ui.py
```

Optional accessibility tooling is kept outside app dependencies. For these runs `npm pack axe-core@4.11.0 --silent --pack-destination .local` obtained the package; only its `package/axe.min.js` member was read with Python `tarfile.extractfile` into `.local/axe.min.js`. Set `$env:UI_AXE_PATH='D:/projects/Airbnb/.local/axe.min.js'` before the browser commands to reproduce the reported WCAG 2 A/AA + 2.1 AA scans. No app manifest/lockfile dependency was added. Browser test sources show the exact scenarios and capture paths.

Final unit/build run: **8 passed, zero failures/skips; production build successful, 33 modules, JS 282.98 kB / 86.30 kB gzip, CSS 14.58 kB / 3.87 kB gzip**. Inter is locally bundled (876,576 bytes) with OFL; source is Google Fonts' official `ofl/inter/Inter[opsz,wght].ttf`. No remote font/CDN runtime requests.

Both the complete Phase 3 program and the new three-role program passed after pending-state improvements. The latter verifies explicit stale move reconciliation, Viewer disabled board/vote/split controls with allowed chat, overlap resolution, personal budget conflict correction, actual 60-second no-turnout cancellation, keyboard skip-link focus, theme persistence, and widths 390/768/1024/1440. Existing Phase 1 also passed (280.8 ms observed join-to-snapshot in that run). No calibrated latency/capacity claim follows. All generated test databases were removed by their existing runner.

Axe reported no WCAG A/AA violations across sign-in, dashboard, active room, Viewer voting, activation dialog, finalized mobile and light/dark states. Its incomplete checks identified the grid's generic labeled container and contrast at clipped/overlapping scroll content. The container now has explicit `role=region`; final targeted re-verification follows below. Contrast token calculations for body/muted/action text on their used surfaces were independently checked: all ten light/dark pairs >=4.5:1 (minimum 5.37:1); raw ratios are in ignored `.local/ui-contrast.json`. Clipped-grid/dialog contrast results require visual review, not a fabricated automated pass or accessibility certification.

The mechanical design detector ran once on changed frontend targets. Its only two warnings concerned using Inter; that font is retained because it was explicitly requested. No policy/business ADR changed. TASK-021–025 remain open.

### Increments 8–10 — final checks and limits

Final semantic grid fix verified by rerunning the existing Phase 1 browser flow with axe enabled: zero WCAG A/AA violations in light and dark rooms (27/28 rules passed). The generic-label incomplete finding is gone; only contrast checks on clipped/overlapping content remain incomplete. Screenshots of the actual dark room, mobile view, open conflict, Viewer vote, cancelled vote and dashboard were inspected. Keyboard skip link, native confirmation focus/Escape/restore and alternative move controls have actual browser assertions. Token contrast calculations and visual review cover the reported clipped-text cases at the tested states; no screen-reader certification is claimed.

Latest Phase 1 output: `Two browser sessions: grid drag/drop, real Concierge/citations, chat, expired-token refresh, reconnect, moderation and revoked-session sign-in succeeded; join to snapshot 256.0 ms`. Latest Phase 3 output: the full two-participant weighted-split/vote/winner/analytics/model/dashboard/Admin/finalization flow passed, no page errors and mobile overflow passed. Latest added regression output: `Frontend UI Chrome: Viewer restrictions/chat; stale move reconciliation; overlap and personal budget conflict resolution; real no-turnout cancellation; keyboard skip link; light/dark accessibility and responsive widths passed; no page errors`. All disposable databases removed.

Final changed UI safeguards include disconnected-socket refresh guards, explicit stale ballot/split/closed-vote/finalization error copy, a backend-supplied group ceiling, disabled Concierge fields while requests are pending, and an explicit named scroll region. The initial budget-test failure came from editing while the first request was still pending; the test now waits for completion, and the UI disables those fields during a request. The corrected full scenario passed twice. No backend domain fix was necessary.

Code review checked server-owned versions/amounts, React text escaping, authenticated Admin gating, membership restrictions, interaction tracking, immutable catalog joins, authoritative refresh, deadline ownership and no fabricated historical vote metadata. No backend application changes or dependency additions. The remaining limitation is that historical vote options contain only IDs/names: removed options show schedule unavailable and source prices only when present in the pinned catalog. Phase 4 full security/load/backup/restore/submission gates remain open; this UI work does not accept them.

Artifacts (ignored, synthetic disposable test data): `.local/ui-final-room-{light,dark,mobile}.png`, `ui-room-{390,768,1024}.png`, `ui-conflict-open.png`, `ui-vote-open-viewer.png`, `ui-vote-cancelled.png`, `ui-dashboard-dark.png`, `ui-audit/*.json`, `ui-detector.json`, `ui-contrast.json`. Increment commits are retained on `codex/phase3-frontend`.
