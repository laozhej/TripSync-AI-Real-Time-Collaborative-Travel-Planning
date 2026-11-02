# Side quest's

Recorded: 2026-11-02.

Status: ideas captured for later discussion only. This file does not authorize implementation, change project policy, or mark any feature complete. No application changes are part of this request.

## SQ-001 — Choose a trip destination

User idea: choose a location other than Bengaluru when creating a trip.

- Proposed experience: select a city from destinations with an active, validated dataset; keep Bengaluru as the default Indian baseline.
- Supporting work to consider: expose available destinations to the creation form and send the selected destination instead of the fixed Bengaluru value.
- Add a second destination dataset to demonstrate the complete flow. Goa was an example in discussion, not a confirmed destination choice.
- Use the existing Admin upload, validation, staging and activation capabilities rather than treating the admin panel as a new feature.
- Each new room should use its selected destination's dataset, currency and timezone. Preserve existing trip values and immutable dataset versions.
- Source context: PRD §§5.1, 6.3, 14.1; REQ-004, REQ-011, REQ-025; TASK-020 covers the existing Admin dataset feature.

## SQ-002 — Change an existing trip's destination

User interest: changing the location of a trip. Whether this means an existing room or only choosing a city at creation remains to be clarified.

- Possible future feature: allow a destination change inside an existing room.
- Open decisions: permissions, confirmation, and what happens to existing itinerary items, votes, budgets, dates and dataset references.
- Creating a separate room for the other destination was suggested as the simpler approach; it is not an approved product rule.
- Do not silently move existing items to another dataset or convert/relabel monetary values.
- Source context: PRD §§5.1, 6.1–6.2; existing dataset-pinning and budget invariants apply.

## SQ-003 — Build an itinerary of our own choice

User idea: create a personally chosen itinerary rather than relying only on AI suggestions.

- Existing baseline: the collaborative board supports choosing dataset-backed places and arranging itinerary items. AI suggestions are not the only planning path.
- Potential extension: add a custom place or personal activity missing from the dataset, such as visiting a friend.
- Open question: does the user want manual selection of available venues, unrestricted custom entries, or both? Custom-entry support was not verified during this discussion.
- Before any future implementation, decide the fields, permissions, validation, cost handling, schedule-conflict behavior and collaboration rules for custom entries.
- User-supplied information must remain distinguishable from validated dataset facts. Missing prices, hours, dietary information or coordinates must not be invented or treated as verified by the Concierge.
- Source context: PRD §§5.2, 5.3, 6.1–6.2; REQ-005 and REQ-017. Custom entries need separate design review against existing grounding rules.

## Implementation boundary

All ideas above are deferred. No phase acceptance, task checkbox, API contract, schema or application behavior changes are claimed by this note. Review the relevant requirements, decisions and traceability before implementing an idea in a later authorized task.
