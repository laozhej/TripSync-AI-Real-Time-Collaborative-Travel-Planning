# REST specification

Implemented API v1, PRD §7.3. Base `/api/v1`; JSON UTF-8, unknown fields rejected. Authentication derives actor from JWT `sub`; a body `userId` is rejected, never trusted. Membership/capabilities are read server-side. The running `/openapi.json` and `/docs` expose actual request/response schemas. See [security](SECURITY.md) and [socket schemas](WEBSOCKET_PROTOCOL.md).

## Common rules

Bearer access JWT for authenticated HTTP. Same-origin refresh and WebSocket access cookies are described in SECURITY. Member routes return 404 for an inaccessible trip; role-forbidden commands generally return 403, with domain-specific 409 conflicts. Admin routes require account Admin. Room commands carry bounded UUID `correlationId` in JSON; no general X-Correlation-ID middleware is implemented. UUID `Idempotency-Key` is required for create/join/ask; same actor/key/body returns the saved result and mismatched body returns 409. The provisional 24-hour create/join replay policy does not yet have automated deletion. Other room commands carry `commandId` and expected versions, using the same services as sockets.

Catalog pagination uses limit 1–100, default 25, and an opaque cursor tied to dataset and proximity filters. Chat uses a positive room-sequence before cursor and returns up to 50 messages. Dashboard, dataset, conflict and vote lists are currently unpaginated. Dates are ISO dates and times carry offsets. Money uses integer minor units except the decimal-string compatibility fields below. All HTTP bodies are limited to 2 MiB. Text renders as escaped React text.

Errors use FastAPI's `detail` field. Authentication and unavailable-resource errors commonly return a string. Domain failures return a code object, for example `{"detail":{"code":"FORBIDDEN"}}`. Request validation returns HTTP 422 with a list of validation errors.

Expected statuses include 401 for invalid authentication, 403 for capability/origin failure, 404 for unavailable objects, 409 for state/version conflicts, 413 for oversized bodies, 422 for invalid data, 429 for authentication throttling, and 503 for unavailable persistence. Safe model fallback and empty constraints return HTTP 200 with an explicit answer status.

## Route inventory

| Method and route (under base) | Access | Request → response |
|---|---|---|
| POST `/auth/register` | Public, rate limited | email,password,displayName → 201 user; no role field |
| POST `/auth/login` | Public, rate limited | email,password → 200 accessToken,expiresIn,user; sets cookies |
| POST `/auth/refresh` | Refresh cookie + origin/CSRF | no body → rotated cookies + accessToken |
| POST `/auth/logout` | Auth/refresh session | no body → 204, revoke session family, clear cookies |
| GET `/me/dashboard` | Auth | joined trip history/rejoin, declared diets and derived categories/per-currency observed ranges |
| POST `/trips` | Any Auth | mandatory example below → 201 trip |
| GET `/trips/{id}` | Member | → trip settings, role, member summaries and current versions |
| POST `/trips/{id}/constraints` | Self or connected Leader | versioned self preferences or group category ceilings |
| POST `/trips/{id}/finalize` | Connected Leader | command IDs and expectedStateVersion; requires resolved conflicts/votes and Locked items |
| POST `/trips/{id}/invites` | Leader | `{role,maxUses,expiresAt}` → 201 inviteId,inviteCode,role,expiresAt,maxUses; code shown once |
| DELETE `/trips/{id}/invites/{inviteId}` | Leader | → 204 revoked |
| POST `/trips/join` | Auth | `{inviteCode}` → 200 tripId,role; repeated member join idempotent |
| POST `/trips/{id}/moderation` | Connected Leader | command IDs, expectedStateVersion, action mute/unmute/remove/lockRoom/unlockRoom/transfer and optional targetUserId |
| GET `/trips/{id}/planning` | Member | → full actor-authorized snapshot including members/board/budgets/chat/votes/conflicts |
| POST `/trips/{id}/items` | Planner canPin/Leader | `{commandId,correlationId,venueId or personalActivity,dayIndex,startTime,endTime,attendeeIds?,splitMode?,weights?}` → 201 command acknowledgement |
| POST `/trips/{id}/items/split` | Planner canPin/Leader | versioned attendee/even-or-weighted split edit; common command IDs |
| POST `/trips/{id}/votes` | Leader | `{commandId,correlationId,expectedVersions:{itemUUID:version},durationSeconds?}` → 200 durable vote/affectedItems/budgetSummary |
| POST `/trips/{id}/votes/cast` | Eligible Planner/Leader | `{commandId,correlationId,voteId,choiceVenueId,expectedBallotVersion}` → 200 durable vote; server actor |
| GET `/trips/{id}/votes/{voteId}` | Member | → vote with counts/deadline/status/result |
| GET `/trips/{id}/budgets` | Member | → currency,item allocations,committed/proposed totals and version |
| GET `/trips/{id}/conflicts` | Member | → `{items:[{status,data,opened_seq,resolved_seq}]}` conflict history |
| GET `/trips/{id}/chat` | Member | before cursor → chat with reactions; committed only |
| POST `/trips/{id}/chat` | Unmuted member | `{body}` → 201 durable message; socket equivalent preferred |
| GET `/destinations` | Auth | → active destination names, currencies and timezones |
| GET `/destinations/{destination}/venues` | Auth | near/radiusKm/limit/cursor/tripId → mandatory catalog response |
| GET `/trips/{id}/ai/sources/{citation}` | Member | canonical citation → authored source from the trip's immutable version |
| POST `/trips/{id}/ai/ask` | Member | constrained request below → 200 answer/status/sources |
| GET `/trips/{id}/recommendations` | Member | → top five exploratory items,modelVersion,hybridReady,generatedAt,interactionWatermark |
| POST `/trips/{id}/recommendations/train` | Admin with membership | off-loop training and atomic artifact promotion |
| POST `/trips/{id}/interactions` | Member | `{venueId,kind:"view"|"like",eventId}` → 201; pin/lock server-derived |
| GET `/trips/{id}/analytics` | Member | → sessionId,throughSeq,duration/peak/AI/conflict metrics,finalBudgets |
| POST `/admin/datasets` | Admin | UTF-8 JSON body ≤2 MiB → 201 staging datasetId/version or 422 bounded field paths |
| POST `/admin/datasets/{datasetId}/activate` | Admin | no body → 200 datasetId/status; atomic staging activation |
| GET `/admin/datasets` | Admin | → versions,validation status |
| GET `/health/live`, `/health/ready`, `/health/gateway` | Private host probe | → status; ready 503 if DB/schema/actors unhealthy; no credentials |

Room locking/mute/remove/transfer use the shared moderation command. Move/remove/lock/unlock are native WebSocket commands (`trip.board.move/remove/lock/unlock`), not additional REST routes. Conflict resolution occurs by a successful item/budget edit or vote application; there is no “mark resolved” bypass. Responses carry command/version identifiers for reconciliation.

Invites select viewer/planner roles; transfer atomically swaps Leader/Planner. Explicit readmission of removed members and a generic account/profile edit endpoint remain unimplemented extensions. Member constraints contain dietaryTags, categoryCeilingsMinor and optional totalCeilingMinor; weights are per item. Missing required fields return 422. List filters never bypass membership checks.

## Mandatory examples and mappings

Routes remain unchanged from PRD §§7.3.1–3. Public monetary major-unit values are decimal strings to avoid binary floating-point; submit totalBudget as a string such as "1200.00". JSON numbers are rejected. All other money uses `...Minor` integers. This type adaptation is deliberate.

```http
POST /api/v1/trips
Authorization: Bearer <access-token>
Idempotency-Key: <uuid>
Content-Type: application/json

{"destination":"Lisbon, Portugal","startDate":"2026-11-10","endDate":"2026-11-14","totalBudget":"1200.00","currency":"EUR","maxParticipants":8}
```

201: `{"tripId":"tr_1","inviteCode":"<random-code>","status":"drafting","leaderUserId":"u_1","createdAt":"2026-10-29T06:00:00Z"}`. Destination must have an active dataset. Creator becomes Leader; first successful nonleader join starts a live session. Capacity 2..50 provisional; dates inclusive in destination timezone.

```http
GET /api/v1/destinations/Lisbon%2C%20Portugal/venues?near=38.7139,-9.1394&radiusKm=2
Authorization: Bearer <access-token>
```

200: `{"destination":"Lisbon, Portugal","venues":[{"venueId":"v_1","name":"Synthetic Riverside Kitchen","category":"food","pricePerPerson":"22.00","dietaryTags":["vegetarian"],"hours":{"weekly":[{"days":[1,2,3,4,5,6,7],"open":"11:00","close":"22:00","closeDayOffset":0}],"exceptions":[]},"coordinates":{"lat":38.7139,"lng":-9.1394},"sourceId":"venue:v_1@1"}],"nextCursor":null}`. `near` is lat,lng, range-checked; radius default 2, provisional maximum 20 km; radius without near is 422. Catalog browsing does not guarantee Concierge constraint validity.

```http
POST /api/v1/trips/tr_1/ai/ask
Authorization: Bearer <access-token>
Idempotency-Key: <uuid>
Content-Type: application/json

{"question":"Suggest dinner near our tour under EUR25/person","anchorItemId":"it_1","category":"food","startTime":"2026-11-10T18:00:00+00:00","endTime":"2026-11-10T19:00:00+00:00","attendeeIds":["u_1","u_2"],"ceilingMinor":2500}
```

200 example, illustrative rather than a test result:

```json
{"questionId":"q_1","status":"grounded","answer":"Synthetic Riverside Kitchen costs EUR22.00 per person and has the required vegetarian tag.","suggestedVenueId":"v_1","sourceEvents":["venue:v_1@1"],"generatedAt":"2026-10-29T06:10:00Z","roomSeq":12,"datasetVersion":1}
```

The original request `userId` is intentionally removed. Missing category, slot or configured category ceiling returns `status:needs_clarification` plus required fields; natural language cannot relax server constraints. `sourceEvents` carries canonical metadata citations, not room events. No six-minute walking claim without cited transit data. A successful reply broadcasts `trip.ai.suggestion` once; clients correlate question ID. A changed trip version before return triggers revalidation/retry once, then `status:stale_context` without suggestions.

## Additional command contracts

All writes below derive the actor from authentication; IDs in examples are UUID placeholders. New domain errors use `{"detail":{"code":"..."}}`, HTTP 409 for stale versions/ballots/closed votes, 403 for capability failure and 404 for unavailable trip/object. Validation errors use FastAPI 422; Admin ingestion returns a bounded human-readable field-path string. No client actor IDs are accepted.

| Route | Live behavior |
|---|---|
| GET `/me/dashboard` | Member trip history, active rejoin, declared diets, observed per-currency price range and favored categories; no currency mixing |
| GET `/trips/{id}/planning` | Same full snapshot as the socket subscription, including votes, conflicts and exact budgets |
| POST `/trips/{id}/items/split` | commandId,correlationId,itemId,expectedPositionVersion,attendeeIds,splitMode,weights; durable versioned Drafting edit |
| POST `/trips/{id}/recommendations/train` | Admin account **with trip membership**; off-loop train and atomic active artifact promotion |
| POST `/trips/{id}/finalize` | commandId,correlationId,expectedStateVersion; connected Leader, no unresolved work, all active items Locked; returns durable session.ended |

Vote opening example: `{"commandId":"<uuid>","correlationId":"<uuid>","expectedVersions":{"<itemUUID1>":1,"<itemUUID2>":1},"durationSeconds":60}`. Ballot example: `{"commandId":"<uuid>","correlationId":"<uuid>","voteId":"<uuid>","choiceVenueId":"<uuid>","expectedBallotVersion":0}`. A successful ballot changes its version to 1; an intentional change supplies 1; repeating a committed command returns status duplicate.

Weighted split example: `{"commandId":"<uuid>","correlationId":"<uuid>","itemId":"<uuid>","expectedPositionVersion":1,"attendeeIds":["<userUUID1>","<userUUID2>"],"splitMode":"weighted","weights":{"<userUUID1>":1,"<userUUID2>":2}}`. Even split accepts no explicit weights. Pin accepts the same optional weighted configuration, while omitted attendees with even mode freeze all currently active memberships.

Catalog's optional `tripId=<uuid>` retrieves that member trip's pinned version; without it the mandatory destination/near/radius example continues to return the active version. Existing PRD mandatory create/catalog/ask examples and compatibility fields are preserved. Final analytics expose proposed and Locked totals separately; finalized sessions require them to agree. Running duration is explicitly as-of-query; finalized duration is exact ended_at minus started_at. A missing historical boundary is labeled unknown.
## Phase 4 transport limits

All HTTP request bodies are limited to 2 MiB before parsing, including chunked input; overflow returns 413 with a generic detail. API responses include `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. The shareable local collection is `http/tripsync.http`; keep substituted tokens/invites in private client variables.


## Destination discovery

Authenticated `GET /api/v1/destinations` returns active destinations in name order, for example `{"destinations":[{"destination":"Goa, India","currency":"INR","timezone":"Asia/Kolkata"}]}`. Pass the selected destination and currency to the existing create-room endpoint. Creating a trip for another destination returns a new trip ID and invitation.

The existing `POST /api/v1/trips/{tripId}/items` also accepts personal activities. Its body uses the same exclusive `venueId` or `personalActivity` source fields as the [WebSocket pin command](WEBSOCKET_PROTOCOL.md#personal-activity-pins).


## Constraints, citations and money

Member preferences contain `dietaryTags`, `categoryCeilingsMinor` and optional `totalCeilingMinor`. A constraints update supplies either group category ceilings, or the acting member's targetUserId and constraints. Group changes require the connected Leader. Categories are food, activity, lodging and transit. Diets are vegetarian, vegan, halal and gluten-free.

The effective category ceiling comes from requester preferences or the group default. A request ceiling can tighten that value. It cannot provide a missing default. Empty attendees use all active memberships. All attendee diets must match. The full buffered slot must fit hours and an anchored venue must satisfy the radius. Personal activities cannot supply a location anchor.

Ask statuses are `grounded`, `grounded_fallback`, `no_valid_candidate`, `needs_clarification` and `stale_context`. A grounded fallback still selects a valid authored venue and carries its citation. No-match/clarification/stale responses have null venue and empty source events. A committed answer is broadcast as `trip.ai.suggestion`.

Bengaluru and Goa use INR and Asia/Kolkata. Legacy Lisbon uses EUR and Europe/Lisbon. Creation requires the chosen active dataset's currency. The original Lisbon examples above preserve PRD §§7.3.1–3. Prefix IDs in those historical examples stand for real UUIDs. Use the UUID-based examples below for request structure.

## Complete request examples

The following examples cover every registered REST operation. They are illustrative request bodies, with UUIDs to replace using actual returned resource IDs. Supply a fresh commandId/correlationId for each mutation. Supply a fresh Idempotency-Key UUID for create, join and ask. Replays reuse the original IDs and body. Authenticated requests use an Authorization Bearer header. Refresh/logout use the same-origin cookies and CSRF header described in SECURITY.md. Paths and query types come from the generated OpenAPI artifact.

### POST /api/v1/auth/register

```http
POST /api/v1/auth/register
Content-Type: application/json

{"email": "reviewer@example.invalid", "password": "sample-only-change-me", "displayName": "Reviewer"}
```

### POST /api/v1/auth/login

```http
POST /api/v1/auth/login
Content-Type: application/json

{"email": "reviewer@example.invalid", "password": "sample-only-change-me"}
```

### POST /api/v1/auth/refresh

```http
POST /api/v1/auth/refresh

```

### POST /api/v1/auth/logout

```http
POST /api/v1/auth/logout

```

### GET /api/v1/destinations

```http
GET /api/v1/destinations

```

### GET /api/v1/destinations/{destination}/venues

Supported query parameters are `near`, `radiusKm`, `limit`, `cursor`, `tripId`.

```http
GET /api/v1/destinations/{destination}/venues

```

### POST /api/v1/trips

```http
POST /api/v1/trips
Content-Type: application/json

{"destination": "Bengaluru, India", "startDate": "2026-11-10", "endDate": "2026-11-14", "totalBudget": "25000.00", "currency": "INR", "maxParticipants": 8}
```

### POST /api/v1/trips/join

```http
POST /api/v1/trips/join
Content-Type: application/json

{"inviteCode": "replace-with-issued-invitation-code"}
```

### GET /api/v1/trips/{trip_id}

```http
GET /api/v1/trips/{trip_id}

```

### POST /api/v1/trips/{trip_id}/invites

```http
POST /api/v1/trips/{trip_id}/invites
Content-Type: application/json

{"role": "planner", "maxUses": 1, "expiresAt": "2026-12-01T00:00:00Z"}
```

### DELETE /api/v1/trips/{trip_id}/invites/{invite_id}

```http
DELETE /api/v1/trips/{trip_id}/invites/{invite_id}

```

### POST /api/v1/trips/{trip_id}/constraints

```http
POST /api/v1/trips/{trip_id}/constraints
Content-Type: application/json

{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedStateVersion": 0, "categoryCeilingsMinor": {"food": 50000}}
```

### POST /api/v1/trips/{trip_id}/ai/ask

```http
POST /api/v1/trips/{trip_id}/ai/ask
Content-Type: application/json

{"question": "Suggest vegetarian lunch", "category": "food", "startTime": "2026-11-10T12:00:00+05:30", "endTime": "2026-11-10T13:00:00+05:30", "attendeeIds": [], "ceilingMinor": 50000}
```

### GET /api/v1/trips/{trip_id}/ai/sources/{citation}

```http
GET /api/v1/trips/{trip_id}/ai/sources/{citation}

```

### POST /api/v1/trips/{trip_id}/items

```http
POST /api/v1/trips/{trip_id}/items
Content-Type: application/json

{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "dayIndex": 0, "startTime": "2026-11-10T12:00:00+05:30", "endTime": "2026-11-10T13:00:00+05:30", "venueId": "22222222-2222-4222-8222-222222222222", "attendeeIds": [], "splitMode": "even"}
```

### GET /api/v1/trips/{trip_id}/chat

Supported query parameters are `before`.

```http
GET /api/v1/trips/{trip_id}/chat

```

### POST /api/v1/trips/{trip_id}/chat

```http
POST /api/v1/trips/{trip_id}/chat
Content-Type: application/json

{"body": "Meet at noon."}
```

### POST /api/v1/trips/{trip_id}/moderation

```http
POST /api/v1/trips/{trip_id}/moderation
Content-Type: application/json

{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedStateVersion": 0, "action": "lockRoom"}
```

### POST /api/v1/trips/{trip_id}/votes

```http
POST /api/v1/trips/{trip_id}/votes
Content-Type: application/json

{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedVersions": {"22222222-2222-4222-8222-222222222222": 1, "33333333-3333-4333-8333-333333333333": 1}, "durationSeconds": 60}
```

### POST /api/v1/trips/{trip_id}/votes/cast

```http
POST /api/v1/trips/{trip_id}/votes/cast
Content-Type: application/json

{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "voteId": "11111111-1111-4111-8111-111111111111", "choiceVenueId": "22222222-2222-4222-8222-222222222222", "expectedBallotVersion": 0}
```

### POST /api/v1/trips/{trip_id}/items/split

```http
POST /api/v1/trips/{trip_id}/items/split
Content-Type: application/json

{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "itemId": "22222222-2222-4222-8222-222222222222", "expectedPositionVersion": 1, "attendeeIds": ["11111111-1111-4111-8111-111111111111", "33333333-3333-4333-8333-333333333333"], "splitMode": "weighted", "weights": {"11111111-1111-4111-8111-111111111111": 1, "33333333-3333-4333-8333-333333333333": 2}}
```

### GET /api/v1/trips/{trip_id}/planning

```http
GET /api/v1/trips/{trip_id}/planning

```

### GET /api/v1/me/dashboard

```http
GET /api/v1/me/dashboard

```

### GET /api/v1/trips/{trip_id}/budgets

```http
GET /api/v1/trips/{trip_id}/budgets

```

### GET /api/v1/trips/{trip_id}/conflicts

```http
GET /api/v1/trips/{trip_id}/conflicts

```

### GET /api/v1/trips/{trip_id}/votes/{vote_id}

```http
GET /api/v1/trips/{trip_id}/votes/{vote_id}

```

### GET /api/v1/trips/{trip_id}/recommendations

```http
GET /api/v1/trips/{trip_id}/recommendations

```

### POST /api/v1/trips/{trip_id}/interactions

```http
POST /api/v1/trips/{trip_id}/interactions
Content-Type: application/json

{"venueId": "22222222-2222-4222-8222-222222222222", "kind": "like", "eventId": "11111111-1111-4111-8111-111111111111"}
```

### POST /api/v1/trips/{trip_id}/recommendations/train

```http
POST /api/v1/trips/{trip_id}/recommendations/train

```

### POST /api/v1/trips/{trip_id}/finalize

```http
POST /api/v1/trips/{trip_id}/finalize
Content-Type: application/json

{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedStateVersion": 0}
```

### GET /api/v1/trips/{trip_id}/analytics

```http
GET /api/v1/trips/{trip_id}/analytics

```

### POST /api/v1/admin/datasets

Send the complete JSON from [Goa sample](../data/destinations/goa.json) as the body. The upload uses the Dataset schema in DATASET_GUIDE.md.

### GET /api/v1/admin/datasets

```http
GET /api/v1/admin/datasets

```

### POST /api/v1/admin/datasets/{dataset_id}/activate

```http
POST /api/v1/admin/datasets/{dataset_id}/activate

```

### GET /api/v1/health/live

```http
GET /api/v1/health/live

```

### GET /api/v1/health/ready

```http
GET /api/v1/health/ready

```

### GET /api/v1/health/gateway

```http
GET /api/v1/health/gateway

```

Personal pin alternative, with the same common command and slot fields.

```json
{"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "dayIndex": 0, "startTime": "2026-11-10T12:00:00+05:30", "endTime": "2026-11-10T13:00:00+05:30", "personalActivity": {"name": "Visit a friend", "pricePerPersonMinor": 0}}
```
