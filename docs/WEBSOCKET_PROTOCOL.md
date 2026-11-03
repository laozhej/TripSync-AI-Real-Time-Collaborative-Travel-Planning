# Implemented WebSocket protocol

Native WebSocket endpoint `/ws/v1/trips/{tripId}`, PRD §§6.1, 7.3.4, 9.3–9.4 and 10.1. Browser authentication uses the short-lived HttpOnly access cookie scoped to /ws. Scripted clients may supply Authorization Bearer. Both require an allowed Origin, valid token/session and active trip membership. The server revalidates on each command and every five seconds of idle receive time.

## Envelopes and durability

Client frames contain exactly `event` and `payload`. Server frames contain `event`, `tripId`, `payload` and integer Unix-millisecond `ts`.

```json
{"event":"trip.persistence.committed","tripId":"11111111-1111-4111-8111-111111111111","payload":{"roomEpoch":"22222222-2222-4222-8222-222222222222","committedSeq":4},"ts":1794290400000}
```

Command IDs and correlation IDs are UUIDs. Pin, move and remove can receive applied acknowledgements before durability. A later committed watermark covers those changes. Lock, unlock, split, votes, chat, moderation and constraints commit before final success. Reusing a command ID with a different body rejects. A committed duplicate returns the stored command result.

Item positionVersion rejects stale intent. stateVersion guards settings changes. roomSeq orders accepted mutations and committedSeq marks persistence. A new roomEpoch discards the old volatile future. Clients obtain a full snapshot after reconnect, epoch changes or sequence gaps. Presence, typing, ping and recommendation invalidations are ephemeral and do not advance roomSeq. Conflict notifications report the committed boundary without allocating a new one.

## Commands and examples

Examples below use illustrative UUIDs. Replace resource IDs with returned IDs and use a fresh commandId/correlationId for each distinct mutation. Times carry offsets. dayIndex is relative to the trip's destination-local start date. Unknown model fields reject.

### trip.board.pin

Planner with canPin or Leader.

```json
{"event": "trip.board.pin", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "dayIndex": 0, "startTime": "2026-11-10T12:00:00+05:30", "endTime": "2026-11-10T13:00:00+05:30", "venueId": "22222222-2222-4222-8222-222222222222", "attendeeIds": [], "splitMode": "even"}}
```

### trip.board.move

Drafting item, Planner with canPin or Leader.

```json
{"event": "trip.board.move", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "itemId": "22222222-2222-4222-8222-222222222222", "expectedPositionVersion": 1, "dayIndex": 0, "startTime": "2026-11-10T12:00:00+05:30", "endTime": "2026-11-10T13:00:00+05:30"}}
```

### trip.board.remove

Drafting item, Planner with canPin or Leader.

```json
{"event": "trip.board.remove", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "itemId": "22222222-2222-4222-8222-222222222222", "expectedPositionVersion": 1}}
```

### trip.board.lock

Connected Leader.

```json
{"event": "trip.board.lock", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "itemId": "22222222-2222-4222-8222-222222222222", "expectedPositionVersion": 1}}
```

### trip.board.unlock

Connected Leader.

```json
{"event": "trip.board.unlock", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "itemId": "22222222-2222-4222-8222-222222222222", "expectedPositionVersion": 1, "reason": "Revise the plan"}}
```

### trip.board.split

Drafting item, Planner with canPin or Leader.

```json
{"event": "trip.board.split", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "itemId": "22222222-2222-4222-8222-222222222222", "expectedPositionVersion": 1, "attendeeIds": ["11111111-1111-4111-8111-111111111111", "33333333-3333-4333-8333-333333333333"], "splitMode": "weighted", "weights": {"11111111-1111-4111-8111-111111111111": 1, "33333333-3333-4333-8333-333333333333": 2}}}
```

### trip.vote.start

Connected Leader.

```json
{"event": "trip.vote.start", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedVersions": {"22222222-2222-4222-8222-222222222222": 1, "33333333-3333-4333-8333-333333333333": 1}, "durationSeconds": 60}}
```

### trip.vote.open

Alias of trip.vote.start.

```json
{"event": "trip.vote.open", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedVersions": {"22222222-2222-4222-8222-222222222222": 1, "33333333-3333-4333-8333-333333333333": 1}, "durationSeconds": 60}}
```

### trip.vote.submit

Eligible Planner or Leader.

```json
{"event": "trip.vote.submit", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "voteId": "11111111-1111-4111-8111-111111111111", "choiceVenueId": "22222222-2222-4222-8222-222222222222", "expectedBallotVersion": 0}}
```

### trip.vote.cast

Alias of trip.vote.submit.

```json
{"event": "trip.vote.cast", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "voteId": "11111111-1111-4111-8111-111111111111", "choiceVenueId": "22222222-2222-4222-8222-222222222222", "expectedBallotVersion": 0}}
```

### trip.chat.send

Unmuted member.

```json
{"event": "trip.chat.send", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "body": "Meet at noon."}}
```

### trip.chat.typing

Unmuted member.

```json
{"event": "trip.chat.typing", "payload": {"isTyping": true}}
```

### trip.chat.react

Unmuted member.

```json
{"event": "trip.chat.react", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "messageId": "22222222-2222-4222-8222-222222222222", "emoji": "👍", "active": true}}
```

### trip.moderation.command

Connected Leader.

```json
{"event": "trip.moderation.command", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedStateVersion": 0, "action": "lockRoom"}}
```

### trip.constraints.update

Connected Leader for group defaults, self for personal preferences.

```json
{"event": "trip.constraints.update", "payload": {"commandId": "11111111-1111-4111-8111-111111111111", "correlationId": "33333333-3333-4333-8333-333333333333", "expectedStateVersion": 0, "categoryCeilingsMinor": {"food": 50000}}}
```

### trip.sync.ping

Member.

```json
{"event": "trip.sync.ping", "payload": {"clientSentAt": 1794290400000, "nonce": "11111111-1111-4111-8111-111111111111"}}
```

### trip.snapshot.request

Member.

```json
{"event": "trip.snapshot.request", "payload": {}}
```

## Personal activity pins

Supply either venueId or `personalActivity`, whose shape is `{"name":"Visit a friend","pricePerPersonMinor":0}`. Both source fields together reject. Names trim whitespace and accept 1–120 characters. Cost is a nonnegative integer in the room currency's minor units, bounded by the existing item/room total limits. The same slot, attendee and split fields apply. Empty attendees freeze all currently active members at pin time.

Personal activities have `venueId: null` in updates and snapshots. They share move/remove/lock, budget and overlap behavior. Catalog venues remain eligible for venue ballots and Concierge anchors. Unlock requires a reason. All provisional voting, room-lock and Leader-disconnect policies are in BUDGET_AND_VOTING.md.

Moderation actions are mute, unmute, remove, lockRoom, unlockRoom and transfer. Participant actions require targetUserId. Constraints accept either group categoryCeilingsMinor or targetUserId plus self constraints. Emoji choices are 👍, ❤️, 😂 and 🎉.

## Server events and payload examples

These are illustrative payload excerpts showing the fields specific to each event. The envelope above wraps every event. Board and durable domain events also carry applicable eventId, commandId, correlationId, roomEpoch, roomSeq and durable fields. System-generated events may omit command IDs. Complete aggregate objects use the shapes described below.

| Event | Payload example |
|---|---|
| `trip.snapshot` | `{"roomEpoch":"11111111-1111-4111-8111-111111111111","roomSeq":0,"committedSeq":0,"items":[],"votes":[],"conflicts":[]}` |
| `trip.board.update` | `{"operation":"pin","itemId":"22222222-2222-4222-8222-222222222222","item":{"itemId":"22222222-2222-4222-8222-222222222222","venueId":null,"name":"Visit a friend","dayIndex":0,"startTime":"2026-11-10T12:00:00+05:30","endTime":"2026-11-10T13:00:00+05:30","lifecycleStage":"drafting","positionVersion":1,"pricePerPersonMinor":0,"attendeeIds":["11111111-1111-4111-8111-111111111111"],"splitMode":"even","weights":{"11111111-1111-4111-8111-111111111111":1}}}` |
| `trip.board.edit.conflict` | `{"commandId":"11111111-1111-4111-8111-111111111111","itemId":"22222222-2222-4222-8222-222222222222","expectedPositionVersion":1,"currentPositionVersion":2,"currentItem":{"itemId":"22222222-2222-4222-8222-222222222222","positionVersion":2},"roomSeq":2}` |
| `trip.board.conflict` | `{"fingerprint":"example-hash","conflictType":"overlap","itemIds":["11111111-1111-4111-8111-111111111111","22222222-2222-4222-8222-222222222222"],"details":{},"status":"open","roomSeq":2,"roomEpoch":"11111111-1111-4111-8111-111111111111","durable":true}` |
| `trip.presence.update` | `{"participantId":"11111111-1111-4111-8111-111111111111","action":"joined","participantCount":2,"connectedUsers":["11111111-1111-4111-8111-111111111111","22222222-2222-4222-8222-222222222222"],"connectedPlanners":2,"leaderConnected":true,"stateVersion":1,"members":[]}` |
| `trip.chat.message` | `{"messageId":"22222222-2222-4222-8222-222222222222","userId":"11111111-1111-4111-8111-111111111111","body":"Meet at noon.","tsSeconds":1794290400,"reactions":[]}` |
| `trip.chat.typing.update` | `{"userId":"11111111-1111-4111-8111-111111111111","isTyping":true,"expiresAt":"2026-11-10T06:00:03Z"}` |
| `trip.chat.reaction.update` | `{"messageId":"22222222-2222-4222-8222-222222222222","reactions":[{"emoji":"👍","userIds":["11111111-1111-4111-8111-111111111111"]}]}` |
| `trip.vote.open` | `{"itemId":"22222222-2222-4222-8222-222222222222","candidateVenueIds":["11111111-1111-4111-8111-111111111111","22222222-2222-4222-8222-222222222222"],"closesAt":"2026-11-10T06:01:00Z","voteId":"11111111-1111-4111-8111-111111111111","vote":{"status":"open"},"affectedItems":[]}` |
| `trip.vote.cast` | `{"itemId":"22222222-2222-4222-8222-222222222222","userId":"11111111-1111-4111-8111-111111111111","choiceVenueId":"22222222-2222-4222-8222-222222222222","voteId":"11111111-1111-4111-8111-111111111111","ballotVersion":1,"vote":{"status":"open"}}` |
| `trip.vote.resolved` | `{"itemId":"22222222-2222-4222-8222-222222222222","winningVenueId":null,"voteId":"11111111-1111-4111-8111-111111111111","vote":{"status":"cancelled"},"affectedItems":[],"activeItems":[],"archivedItems":[]}` |
| `trip.ai.suggestion` | `{"questionId":"11111111-1111-4111-8111-111111111111","userId":"11111111-1111-4111-8111-111111111111","answer":"No authored venue satisfies the constraints.","suggestedVenueId":null,"sourceEvents":[],"status":"no_valid_candidate","datasetVersion":1,"basedOnSeq":2}` |
| `trip.sync.pong` | `{"clientSentAt":1794290400000,"nonce":"11111111-1111-4111-8111-111111111111","serverReceivedAt":1794290400001,"serverSentAt":1794290400001}` |
| `trip.command.ack` | `{"commandId":"11111111-1111-4111-8111-111111111111","status":"applied","roomSeq":1,"positionVersion":1,"durable":false,"committedSeq":0}` |
| `trip.command.error` | `{"code":"FORBIDDEN","commandId":"11111111-1111-4111-8111-111111111111"}` |
| `trip.persistence.committed` | `{"committedSeq":1,"roomEpoch":"11111111-1111-4111-8111-111111111111"}` |
| `trip.persistence.degraded` | `{"committedSeq":0,"reason":"commit failed; reconnect after recovery"}` |
| `trip.moderation.update` | `{"action":"lockRoom","stateVersion":2}` |
| `trip.constraints.update` | `{"stateVersion":2}` |
| `trip.recommendations.updated` | `{}` |
| `session.ended` | `{"stateVersion":2,"finalBudget":{"currency":"INR","proposedMinor":0,"lockedMinor":0}}` |

The gateway sends vote/split service result payloads directly inside trip.command.ack. Other commands return the compact status acknowledgement shown above. Duplicate status and optional version fields depend on the command.

Board updates include operation and item. Pin/move/remove/lock/unlock additionally expose item fields at the payload top level. Split sends its item under item. budgetSummary contains currency, proposedMinor, lockedMinor, perPerson, itemAllocations, reservationMethod and reservations. Open votes reserve each attendee's maximum candidate allocation. Finalized sessions have equal proposed/locked totals.

Vote objects include voteId, optionIds, options (itemId, venueId, name), eligibleUserIds, status, closesAt and ballots (userId, choiceItemId, version), with result fields after resolution. Opening/resolution also carries affected items and budgetSummary. Clients refresh their snapshot after multi-item vote transitions.

Snapshots additionally contain connectedUsers, leaderConnected, stateVersion, sessionId, trip (status, roomLocked, categoryCeilingsMinor, timezone), preferences, lastSuggestion, budgets, chat and members. Chat contains up to 100 latest messages and a before cursor for older REST history. A member includes userId, displayName, role, canPin and muted.

## Reconnect, errors and limits

Subscription and snapshot are enqueued under the room lock before subsequent events. First/last sockets affect distinct-user presence. The last Leader socket disconnect immediately freezes connected-Leader actions. Membership and stable planning-session identity persist across reconnects. The browser refreshes HTTP credentials and reconnects with backoff.

A stale position emits trip.board.edit.conflict with the authoritative currentItem. The client displays reconciliation controls and requires a new deliberate edit. Other domain failures emit trip.command.error. Malformed payloads use INVALID_COMMAND.

Text frames are bounded to 65,536 UTF-8 bytes. Binary frames close 1003, oversized frames close 1009, and more than 40 frames in a rolling second closes 1008. Failed authorization also closes 1008. A subscriber queue is bounded to 100 entries and slow consumers disconnect for snapshot recovery. Typing true updates are limited to one per second and expire after three seconds. The client measures ping RTT for connection quality.

The two-second snapshot and sub-100-ms synchronization values are targets. Actual measurements and misses are in PHASE_4_EVIDENCE.md.
