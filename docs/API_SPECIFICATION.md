# REST specification

API v1 design, PRD §7.3. Only the first-slice routes described in the implementation notes below exist; all others remain planned. Base `/api/v1`; JSON UTF-8, unknown fields rejected. Authentication derives actor from JWT `sub`; a body `userId` is rejected, never trusted. Membership/capabilities are read server-side. See [security](SECURITY.md) and [socket schemas](WEBSOCKET_PROTOCOL.md).

## Common rules

Bearer access JWT for authenticated HTTP. Same-origin refresh and WebSocket access cookies described in SECURITY. All member routes return 404 for an inaccessible trip; 403 for a forbidden capability within a visible trip. Admin routes require account Admin. `X-Correlation-ID` is accepted only as bounded UUID or replaced; response returns it. Mutations accept UUID `Idempotency-Key` (required for create/join/ask); same actor/key/body returns saved result; mismatched body 409. Retain committed keys for 24 h, provisional. Room commands also carry `commandId` and expected versions, using the same service as sockets.

Lists: `limit` 1..100 default 25, opaque `cursor`; response `{items:[],nextCursor:null}`; venues retain `{destination,venues:[],nextCursor}`. Cursors use stable `(createdAt,id)` or `(score,id)` plus filter/model version; invalid/expired cursor 422. ISO dates and offset-bearing datetimes; integer minor-unit amounts except mandatory-example compatibility fields noted below. Max normal body 64 KiB; text length limits apply after Unicode normalization. No raw HTML accepted.

Error shape:

```json
{"error":{"code":"STALE_VERSION","message":"Item changed; reconcile before retrying","fields":[],"current":{"itemId":"it_1","positionVersion":5},"correlationId":"<uuid>"}}
```

400 malformed JSON, 401 missing/expired JWT, 403 capability/origin failure, 404 unavailable resource, 409 stale/state/duplicate vote conflict, 413 too large, 422 schema/domain validation, 429 throttled, 503 DB/model unavailable when no safe response is possible. Constraint-empty and model fallback normally return 200 with explicit status, not fabricated success. 500 includes no trace or secret.

## Route inventory

| Method and route (under base) | Access | Request → response |
|---|---|---|
| POST `/auth/register` | Public, rate limited | email,password,displayName → 201 user; no role field |
| POST `/auth/login` | Public, rate limited | email,password → 200 accessToken,expiresIn,user; sets cookies |
| POST `/auth/refresh` | Refresh cookie + origin/CSRF | no body → rotated cookies + accessToken |
| POST `/auth/logout` | Auth/refresh session | no body → 204, revoke session family, clear cookies |
| GET/PATCH `/me` | Auth | read or `{displayName,preferences}` → user; preferences validates dietary tags and ceilings |
| GET `/me/trips` | Auth | status/history filters → paged joined trips with membership role and canRejoin |
| GET `/me/preferences` | Auth | → declared and derived profile, sampleCount, asOf |
| POST `/trips` | Any Auth | mandatory example below → 201 trip |
| GET `/trips/{id}` | Member | → trip settings, role, member summaries and current versions |
| PATCH `/trips/{id}` | Leader | `{expectedStateVersion,settings?,status?,totalBudget?,categoryCeilingsMinor?}` → trip; finalization validates unresolved work |
| POST `/trips/{id}/invites` | Leader | `{role,maxUses,expiresAt}` → 201 inviteCode,inviteUrl; code shown once |
| DELETE `/trips/{id}/invites/{inviteId}` | Leader | → 204 revoked |
| POST `/trips/join` | Auth | `{inviteCode}` → 200 tripId,role; repeated member join idempotent |
| GET `/trips/{id}/members` | Member | → paged membership list |
| PATCH `/trips/{id}/members/{memberId}` | Leader or self constraints only | `{expectedStateVersion,role?,canPin?,muted?,status?,constraints?}` → membership; self cannot set role/status; Leader may explicitly restore removed membership subject to capacity |
| DELETE `/trips/{id}/members/{memberId}` | Leader, or self leave | → 204; Leader must transfer first; removal revokes sockets |
| POST `/trips/{id}/leadership` | Leader | `{nextLeaderUserId,expectedStateVersion}` → 200 new Leader; atomic swap |
| GET `/trips/{id}/board` | Member | → full snapshot as in socket protocol |
| POST `/trips/{id}/items` | Planner canPin/Leader | `{venueId,dayIndex,startTime,endTime,attendeeIds,splitMode,weights?}` → 201 item,roomSeq,durable=false |
| PATCH `/trips/{id}/items/{itemId}` | Planner canPin/Leader | `{expectedPositionVersion,dayIndex?,startTime?,endTime?,attendeeIds?,weights?}` → applied item,seq,durability |
| DELETE `/trips/{id}/items/{itemId}` | Planner canPin/Leader, Drafting | body `{expectedPositionVersion}` → 200 tombstone,seq,durability |
| POST `/trips/{id}/items/{itemId}/lock` | Leader | `{expectedPositionVersion}` → 200 Locked item,durable=true |
| POST `/trips/{id}/items/{itemId}/unlock` | Leader | `{expectedPositionVersion,reason}` → 200 Drafting item,durable=true |
| POST `/trips/{id}/votes` | Leader | `{itemIds,expectedVersions,closesAt?}` → 201 vote,eligibleCount,options |
| PUT `/trips/{id}/votes/{voteId}/ballot` | Eligible Planner/Leader | `{choiceVenueId,expectedBallotVersion}` → 200 ballot; server actor |
| GET `/trips/{id}/votes/{voteId}` | Member | → vote with counts/deadline/status/result |
| GET `/trips/{id}/budgets` | Member | → currency,item allocations,committed/proposed totals and version |
| GET `/trips/{id}/conflicts` | Member | status filter → paged conflict records |
| GET `/trips/{id}/chat` | Member | before cursor → chat with reactions; committed only |
| POST `/trips/{id}/chat` | Unmuted member | `{body}` → 201 durable message; socket equivalent preferred |
| GET `/destinations/{destination}/venues` | Auth | near/radius/category/cursor → mandatory catalog response |
| GET `/destinations/{destination}/venues/{venueId}` | Auth | datasetVersion query → full authored venue with citation ID |
| POST `/trips/{id}/ai/ask` | Member | constrained request below → 200 answer/status/sources |
| GET `/trips/{id}/recommendations` | Member | `limit` max 20 → ranked venues/destinations,modelVersion,asOf |
| POST `/trips/{id}/interactions` | Member | `{venueId,kind:"view"|"like",liked?}` → 201; pin/lock/co_travel server-derived |
| GET `/trips/{id}/analytics` | Member | sessionId optional → metrics,asOfSeq,finalBudget |
| POST `/admin/datasets` | Admin | multipart file JSON/YAML → 201 validation summary/staging datasetId or 422 all bounded errors |
| POST `/admin/datasets/{datasetId}/activate` | Admin | `{expectedVersion}` → 200 active version; atomic |
| GET `/admin/datasets` | Admin | → versions,validation status |
| GET `/health/live`, `/health/ready`, `/health/gateway` | Private host probe | → status; ready 503 if DB/schema/actors unhealthy; no credentials |

Room locking is PATCH settings `roomLocked`; mute/remove/transfer use routes above. Conflict resolution occurs by a successful item/budget edit or vote application and emits a resolved record; there is no “mark resolved” bypass. REST write responses include the same event identifiers as socket broadcasts so clients deduplicate.

Membership PATCH accepts only viewer/planner roles; Leader changes use the atomic leadership endpoint. Restoring `status:active` is a Leader-only readmission with an audit event, not automatic redemption of an old invite. Member constraints contain dietaryTags, categoryCeilingsMinor and optional totalCeilingMinor; weights are per item. Dates/times, UUIDs, enums, integer money and version fields follow the schema and dataset guides; missing required fields return 422. List filters never bypass membership checks.

## Mandatory examples and mappings

Routes remain unchanged from PRD §§7.3.1–3. Public monetary major-unit values are decimal strings to avoid binary floating-point; clients may submit the original integer 1200 exactly as 1200.00, but fractional JSON numbers are rejected in favor of strings. All other money uses `...Minor` integers. This type adaptation is deliberate.

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

200: `{"destination":"Lisbon, Portugal","venues":[{"venueId":"v_1","name":"Synthetic Riverside Kitchen","category":"food","pricePerPerson":"22.00","dietaryTags":["vegetarian"],"hours":{"open":"11:00","close":"22:00","closeDayOffset":0},"coordinates":{"lat":38.7139,"lng":-9.1394},"sourceId":"venue:v_1@1"}],"nextCursor":null}`. `near` is lat,lng, range-checked; radius default 2, provisional maximum 20 km; radius without near is 422. Catalog browsing does not guarantee Concierge constraint validity.

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

The original request `userId` is intentionally removed. Missing structured slot/attendee/category information that cannot be safely inferred returns `status:needs_clarification` plus required fields; natural language cannot relax server constraints. `sourceEvents` carries canonical metadata citations, not room events. No six-minute walking claim without cited transit data. A successful reply broadcasts `trip.ai.suggestion` once; clients correlate question ID. A changed trip version before return triggers revalidation/retry once, then `status:stale_context` without suggestions.

## Partial HTTP implementation — 2026-10-30

Registration, login, refresh, logout, initial catalog browse, trip creation and invite redemption have preliminary implementations and database-backed tests. Other routes and WebSockets above remain planned. Creation currently issues a Planner invite and encrypts the idempotent response because it includes the one-time invite code; the key is derived from the locally configured JWT secret. Rotating that secret makes saved responses unreadable, and retention cleanup currently occurs on reuse of the same idempotency key. Room capacity/concurrency and the full role/security matrix still require verification. See [evidence](PHASE_1_EVIDENCE.md).

`GET /trips/{tripId}` now returns a preliminary member-only trip detail and active member list. It has a database-backed check for access before and after joining. Error bodies and remaining documented fields have not yet been aligned to the full API contract.

Preliminary WebSocket and HTTP pin endpoints now call the same actor service. The current HTTP pin payload additionally requires `commandId` and `correlationId` and supports even splits only; snapshot and error bodies do not yet satisfy the complete planned contract. See [evidence](PHASE_1_EVIDENCE.md).

Leader invite creation and revocation now have preliminary implementations and tests, including capacity and permission rejection. The initial create-trip invite can be redeemed; the UI can create and revoke a later single-use Planner or Viewer invite. Invite creation does not yet implement the documented idempotency-key behavior or invite URL. See [evidence](PHASE_1_EVIDENCE.md).

## Implemented chat subset — 2026-10-31

`GET /api/v1/trips/{tripId}/chat` returns up to 50 committed messages with reactions; `before` is a positive room-sequence cursor and `nextCursor` is the next older boundary or null. `POST /api/v1/trips/{tripId}/chat` accepts `{body}` and optional UUID `Idempotency-Key`, returning the committed message. Both require current trip membership; posting reuses the room service and checks mute and trip status. The current numeric cursor and route-specific HTTP errors differ from the proposed common API conventions above.

## Phase 2 implemented contracts — 2026-10-31

In addition to the original routes and examples, these routes are implemented. Intended inventory entries above that are not mentioned in implementation notes remain planned.

| Route | Implemented behavior |
|---|---|
| POST `/trips/{tripId}/moderation` | Common `commandId`, `correlationId`, `expectedStateVersion`; action `mute`, `unmute`, `remove`, `lockRoom`, `unlockRoom`, or `transfer`; participant actions require `targetUserId`. Same service as `trip.moderation.command`. |
| POST `/trips/{tripId}/constraints` | Common IDs/version plus either group `categoryCeilingsMinor` (Leader) or `targetUserId` and `constraints` (self only). Same service as `trip.constraints.update`. |
| POST `/trips/{tripId}/ai/ask` | The mandatory example fields above are supported; UUID `Idempotency-Key` is required. Optional `radiusKm` (default 2) and `bufferMinutes` (default 30). No body userId accepted. |
| GET `/trips/{tripId}/ai/sources/{citation}` | Resolve `venue:<sourceId>@<version>` only from that trip's pinned dataset. Current membership/session required; unknown or mismatched version returns 404. |

Member constraints are `{dietaryTags:[],categoryCeilingsMinor:{}}`. Category vocabulary is food/activity/lodging/transit; positive ceilings are integer EUR cents. Group defaults and requester ceilings are stored independently of `totalBudget`. A request `ceilingMinor` can tighten the configured effective ceiling; it cannot supply a missing configured default or widen the effective ceiling. An empty attendee list uses all active members; unknown/duplicate attendee IDs reject. Dietary requirements are the union for those attendees. A missing category/slot/configured ceiling returns `needs_clarification` with requiredFields.

Ask responses preserve questionId/userId/answer/suggestedVenueId/sourceEvents and add status, datasetVersion, basedOnSeq, generatedAt, eventId, roomEpoch, roomSeq and durable. `grounded` means actual validated model output; `grounded_fallback` is labeled and uses only valid authored candidates. `no_valid_candidate`, `needs_clarification` and `stale_context` contain null suggestedVenueId and empty citations. Committed responses are idempotent and broadcast once as `trip.ai.suggestion`; requesters removed during generation cannot receive the result. A changing room is re-evaluated once, then returns stale_context.

The current HTTP errors retain FastAPI `detail` (string or `{code,...}`), rather than claiming the proposed common error envelope above is complete. Stale settings return 409 with currentStateVersion; stale board moves use the separate socket edit-conflict event. Actual checks are in [Phase 2 evidence](PHASE_2_EVIDENCE.md).

### India baseline update

Create-room currency accepts INR or legacy EUR, and must match the selected active dataset. The new default example is destination `Bengaluru, India`, currency `INR`, totalBudget `25000.00`; GET trip returns timezone `Asia/Kolkata`. A noon IST slot is `2026-11-10T12:00:00+05:30` (the same instant as `2026-11-10T06:30:00Z`). Budget minor units in Indian rooms are paise. Earlier mandatory PRD examples and legacy EUR fixtures remain documented as historical examples.
