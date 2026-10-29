# WebSocket protocol

Proposed native WebSockets, PRD §§6.1,7.3.4,9.3–9.4,10.1. Socket.IO is not used. URL `/ws/v1/trips/{tripId}`; one authenticated logical connection per room per browser tab. User/session identity comes from JWT, never socket payload user IDs. Browser handshake sends same access JWT through a short-lived HttpOnly cookie scoped `/ws`; scripted clients may send Authorization Bearer. Validate origin, token, session revocation and current membership before accepting. Reject expired credentials; refresh through HTTP then reconnect. Sensitive commands re-read current capability. Token expiry closes socket 1008; no URL token logging.

## Envelope and ordering

Keep required fields unchanged:

```json
{"event":"trip.board.update","tripId":"tr_1","payload":{"itemId":"it_1","dayIndex":0,"startTime":"2026-11-10T18:00:00Z","endTime":"2026-11-10T19:00:00Z","lifecycleStage":"drafting","positionVersion":5,"commandId":"<uuid>","roomSeq":31,"roomEpoch":"<uuid>","durable":false,"correlationId":"<uuid>"},"ts":1793253600000}
```

`ts` is server Unix milliseconds; `startTime/endTime` map to DB `starts_at/ends_at`. `dayIndex` zero-based destination-local date; mismatch with timestamps rejected. All durable aggregate events include eventId, roomSeq, roomEpoch and correlationId inside payload, proposed additions. Ephemeral presence/type/ping events have no aggregate sequence; never trigger a false sequence gap. `positionVersion` is per item, `stateVersion` for settings/membership, `roomSeq` orders accepted mutations and `committedSeq` marks persistence. TCP ordering applies only within a connection; reconnect/cross-client order is server sequence. Ignore duplicate eventId/roomSeq within epoch; gap or epoch change requests a full snapshot.

## Required server events

| Event | Payload (baseline fields retained; extensions explicit) |
|---|---|
| `trip.board.update` | itemId,dayIndex,startTime,endTime,lifecycleStage,positionVersion; add operation pin/move/remove/lock/unlock, full item or tombstone, budgetSummary and sequence metadata |
| `trip.board.conflict` | conflictType overlap/budgetBreach,itemIds,details; add conflictId,status open/resolved, detectedAt, basedOnSeq |
| `trip.presence.update` | participantId,action joined/left,participantCount; add connectedUsers,connectedPlanners,leaderConnected,quality. Leader-status refresh uses proposed action `updated` |
| `trip.chat.message` | messageId,userId,body,tsSeconds; add reactions,roomSeq,eventId. tsSeconds=floor(ts/1000) for compatibility |
| `trip.vote.open` | itemId,candidateVenueIds,closesAt; add voteId,optionItemIds,eligibleCount and eligibleUserIds restricted to members |
| `trip.vote.cast` | itemId,userId,choiceVenueId; add voteId,ballotVersion,counts. Actor ID assigned server-side |
| `trip.vote.resolved` | itemId,winningVenueId; add voteId,outcome resolved/cancelled,reason,winningItemId, affectedItems,budgetSummary. Null winner for zero-vote cancellation |
| `trip.ai.suggestion` | questionId,userId,answer,suggestedVenueId,sourceEvents; add status,datasetVersion,basedOnSeq; null venue on fallback/no match |
| `trip.sync.ping` / `trip.sync.pong` | clientSentAt,serverReceivedAt; pong adds serverSentAt,nonce. Client initiates ping with serverReceivedAt=null; server sets receive time |

## Proposed client commands and replies

Every mutating command includes UUID commandId and correlationId. At most 64 KiB JSON/frame; 20 commands/s/socket burst 40 (provisional); chat ≤2000 chars, question ≤4000, typing ≤1/s, emoji from documented allowlist. Bad payload → `trip.command.error`; repeated abuse close 1008, oversized close 1009. Slow client send queue >100 aggregate events → close 1013 with snapshot-on-rejoin, never silently drop board updates.

| Command | Fields beyond common IDs | Authorization/result |
|---|---|---|
| `trip.board.pin` | venueId,dayIndex,startTime,endTime,attendeeIds,splitMode,weights? | Planner canPin/Leader; new Drafting item |
| `trip.board.move` | itemId,expectedPositionVersion,dayIndex,startTime,endTime | Drafting, canPin/Leader |
| `trip.board.edit` | itemId,expectedPositionVersion,attendeeIds?,splitMode?,weights? | Drafting, canPin/Leader |
| `trip.board.remove` | itemId,expectedPositionVersion | Drafting, canPin/Leader |
| `trip.board.lock` / `trip.board.unlock` | itemId,expectedPositionVersion,reason for unlock | Leader; explicit override unlock |
| `trip.vote.start` | itemIds,expectedVersions,closesAt? | Leader; uses HTTP vote service |
| `trip.vote.submit` | voteId,choiceVenueId,expectedBallotVersion | Eligible Planner/Leader; no request userId |
| `trip.chat.send` | body | Unmuted member |
| `trip.chat.typing` | isTyping bool | Unmuted member; expires after 3 s |
| `trip.chat.react` | messageId,emoji,active bool | Unmuted member; upsert/remove idempotent |
| `trip.moderation.command` | action mute/remove/lockRoom/unlockRoom/transfer, targetUserId?,expectedStateVersion | Leader; transfer requires active Planner |
| `trip.snapshot.request` | lastSeenSeq,lastEpoch | Member; full snapshot baseline |
| `trip.sync.ping` | clientSentAt,nonce | Member; pong |

`trip.command.ack` (proposed): `{commandId,status:applied|committed|duplicate,roomSeq,positionVersion?,durable,committedSeq}`. Final durability notification `trip.persistence.committed` advances committedSeq, covering earlier volatile ack. Significant commands send committed ack after transaction. Dedup same command/body returns original result; different body with same ID is COMMAND_ID_REUSE. `trip.command.error` contains code,fields,current?,commandId. No state mutation on rejection.

`trip.board.edit.conflict` (proposed) is separate from schedule/budget `trip.board.conflict`: `{commandId,itemId,expectedPositionVersion,currentPositionVersion,currentItem,roomSeq}`. Two moves from version 4: first accepted becomes 5; second explicitly rejected. Client replaces preview with currentItem, shows a conflict notice and lets user submit a fresh deliberate command. Do not auto-increment version or retry stale intent.

Other proposed events: `trip.chat.typing.update` `{userId,isTyping,expiresAt}`; `trip.chat.reaction.update` `{messageId,reactions}`; `trip.moderation.update` `{action,targetUserId?,stateVersion}`; `trip.persistence.degraded` `{committedSeq,reason}`; `trip.recommendations.updated` `{modelVersion,asOf}`. They are additions, not PRD-listed core events.

## Join, reconnect and snapshot

HTTP join redeems invite once; reconnect does not redeem again. Authenticate same user/session and validate active membership. Attach connection to existing identity; only first socket joins presence and last socket leaves. A 15 s provisional disconnect grace preserves session ID/chat context; Leader disconnected state is immediate when last socket drops. Membership count does not fluctuate with sockets; peak concurrency counts distinct connected Planner/Leader identities.

Snapshot event `trip.snapshot` (proposed) payload:

```json
{"roomEpoch":"<uuid>","roomSeq":31,"committedSeq":30,"stateVersion":3,"sessionId":"<uuid>","trip":{"status":"live","roomLocked":false},"items":[],"budgets":{"currency":"EUR","proposedMinor":0,"lockedMinor":0,"perPerson":[]},"votes":[],"conflicts":[],"members":[],"leaderConnected":true,"chat":{"items":[],"nextCursor":null},"serverTime":"2026-10-29T06:00:00Z"}
```

Actor captures snapshot and subscription at one sequence boundary: enqueue later events only after snapshot; client atomically replaces local aggregate then applies subsequent sequences. Older chat comes from paginated REST. No replay buffer required for baseline: every reconnect gets full snapshot within 2 s target (§6.1). Backoff 0.5/1/2/4/8 s plus jitter; reconnect automatically only with valid session. New epoch discards optimistic/uncommitted commands and announces potential rollback; user decides whether to reapply. Removed members are closed immediately and denied snapshot. Ping every 10 s; disconnect after 30 s without response, quality derived from RTT and missed pongs, never a claimed one-way measurement.
