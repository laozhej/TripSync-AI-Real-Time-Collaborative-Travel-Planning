# TripSync AI interface

The user specified a premium travel workspace in forest green, teal, pale sage and warm off-white, with Inter and light/dark themes. This is an operating interface: the shared itinerary leads, contextual tools support it, and status comes from the server.

Tokens live in `frontend/src/style.css`: canvas, surface, surface-soft, ink, muted, line, accent, accent-ink, forest, warning and danger. Inter is bundled locally with its OFL licence. No CDN or imagery is needed for this planning surface.

Use 4/8/12/16/24/32px spacing, 12–16px content corners, 44px minimum primary controls, persistent visible focus, tabular numbers, wrapping content and internally scrollable tables. Semantic badges distinguish lifecycle, online state and conflicts with text as well as color. Confirmation uses a native modal dialog with keyboard dismissal and focus restoration. At narrow widths the context column follows the itinerary and navigation wraps. Reduced motion disables transitions.

Money, votes, conflicts and persistence remain backend-authoritative. Unavailable historical metadata is labeled; exploratory recommendations are never presented as constraint-checked Concierge results.

## User working-draft alignment

The user-provided `tripsync_phase3_working_draft.html` is the visual reference. The authenticated client uses a 238px persistent sidebar, a 72px top bar and compact individual workspace pages. Overview uses four server-fed summary cards, a 1.65/.85 itinerary/context layout, selectable day rows and member/attention panels. At <=700px the sidebar becomes a mobile drawer. Actual trip data replaces the draft's illustrative content; business semantics and exact totals are unchanged. SVG navigation icons share one stroke style. Muted text retains accessible contrast rather than copying low-contrast sample tokens.
