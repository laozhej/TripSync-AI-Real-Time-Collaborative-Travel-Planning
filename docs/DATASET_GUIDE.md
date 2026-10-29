# Authored destination datasets

Proposed schema `schemaVersion:1`, PRD §§4.1,6.2–6.3,14.1. No actual seed dataset is claimed as delivered by this documentation task. Future seed is `data/destinations/lisbon.json`; examples below are synthetic design fixtures. One destination must cover every hard-filter type; more destinations are optional.

## Format and validation

JSON preferred; YAML accepted with safe loader only (no custom constructors), duplicate keys rejected, bounded aliases/depth. UTF-8 upload ≤2 MiB, ≤2000 entries, ≤20 KiB description, depth ≤12 provisional. Admin-authenticated upload stages and validates entire bundle; reject atomically with `{path,code,message}` errors, capped 100 errors. No partial active import. Checksums make repeat import idempotent. Activate new immutable version atomically and rebuild retrieval index before exposure; trips retain original version. Never execute uploaded code or retrieve arbitrary remote URLs.

```json
{
  "schemaVersion":1,
  "destination":"Lisbon, Portugal",
  "timezone":"Europe/Lisbon",
  "currency":"EUR",
  "provenance":{"kind":"synthetic","author":"project engineer","authoredAt":"2026-10-29","license":"project-authored","notice":"Demonstration data, not travel advice"},
  "venues":[{
    "sourceId":"v_1","name":"Synthetic Riverside Kitchen","category":"food",
    "pricePerPerson":"22.00","dietaryTags":["vegetarian","vegan"],
    "coordinates":{"lat":38.7139,"lng":-9.1394},"rating":4.0,
    "hours":{"weekly":[{"days":[1,2,3,4,5,6,7],"open":"11:00","close":"22:00","closeDayOffset":0}],"exceptions":[]},
    "description":"Authored example with plant-based options."
  }],
  "transit":[{"sourceId":"t_1","fromVenueId":"v_1","toVenueId":"v_2","mode":"walk","durationMinutes":12,"validFrom":"2026-11-10T00:00:00Z","validTo":"2026-11-15T00:00:00Z","synthetic":true}],
  "weather":[{"sourceId":"w_1","date":"2026-11-10","summary":"Synthetic light rain","temperatureC":16,"synthetic":true}]
}
```

Fragment illustrates schema; it needs a defined `v_2` before import because dangling transit references are rejected. Category vocabulary `food|lodging|activity|transit`. Dietary vocabulary `vegetarian|vegan|halal|gluten-free`; every tag required by an attendee must be explicitly present—vegan does not automatically imply vegetarian unless dataset includes both. Future vocabulary changes require versioned migration and fixtures.

Required venue fields are sourceId unique within version, name, category, positive exact price, supported currency, tags array (empty allowed), coordinates, hours and description; rating optional [0,5]. Latitude [-90,90], longitude [-180,180], finite only (NaN/infinity forbidden). Validate timezone against IANA, valid ISO dates and positive durations. Hours use weekdays ISO 1..7, HH:MM, closeDayOffset 0 or 1; expanded close must exceed open and duration ≤24 h. Overnight 22:00→02:00 requires offset 1. Empty weekly intervals mean closed, not always open. Exceptions replace hours on a local date; reject overlapping intervals and contradictory exceptions. Lodging uses explicitly authored availability interval/rate convention; no nightly pricing assumption.

Transit requires valid endpoints, positive duration, mode and validity interval. Weather is dated authored metadata, never a forecast obtained live. Both carry provenance and synthetic labels in responses; do not apply an expired weather/transit record to a new trip date. Canonical citation IDs are `venue:v_1@1`, `transit:t_1@1`, `weather:w_1@1`. Dataset version comes from ingestion, not trusted client claims.

## Minimum coverage checklist

- At least one fully worked destination with food, lodging and activity choices.
- At least one valid candidate for each of four dietary tags and one combined-diet match.
- One over-category-budget venue; one missing a required diet; restrictive/closed hours; overnight and buffered boundary cases.
- Anchor and near/just-outside-radius choices; distinct same-slot alternatives for voting.
- Transit edge supporting an explicit travel-duration claim; dated synthetic weather with clear provenance.
- Valid schema and invalid upload fixtures: zero/negative/malformed prices, unknown diet, lat 90.1/lng -180.1, invalid hours, duplicate IDs, dangling references, unsafe YAML, oversized payload and prompt-injection description.

Recommendation: ~12 venue/lodging options, 4 transit edges, 3 weather dates. Counts are adjustable; required coverage is not. Track B would additionally require automated location generation of coordinates/hours/prices with reproducible seed (§4.3); Track A can use a small authored dataset plus property-based boundary fixtures. DATA-01 validates valid/import/activation; DATA-02 invalid/boundary fixtures; DATA-03 version pinning/rollback/index readiness. No tests have run.
