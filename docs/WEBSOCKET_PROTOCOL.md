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
| `trip.board.split` | itemId,expectedPositionVersion,attendeeIds,splitMode,weights | Drafting, canPin/Leader |
| `trip.board.remove` | itemId,expectedPositionVersion | Drafting, canPin/Leader |
| `trip.board.lock` / `trip.board.unlock` | itemId,expectedPositionVersion,reason for unlock | Leader; explicit override unlock |
| `trip.vote.start` | expectedVersions,durationSeconds? | Leader; uses HTTP vote service |
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

## Implemented first-slice subset — 2026-10-30

The gateway now supports authenticated snapshot subscription and `trip.board.pin`, broadcasting `trip.board.update`, `trip.command.ack`, `trip.persistence.committed`, and persistence degradation. The first-slice snapshot contains items, even-split budgets, members, trip status, stable planning-session ID, epoch and sequences. Chat, votes, conflicts and other later-feature fields are not yet implemented. The browser reconnects with backoff and refreshes on HTTP 401; the full browser expiry/failure matrix remains pending. Logout and refresh-token reuse close tracked session sockets; idle expiry/membership revalidation is polled at up to five-second intervals. Command rate limiting currently caps 40 frames in a rolling second, rather than the proposed sustained/burst token bucket. Full protocol and security acceptance remain pending. See [evidence](PHASE_1_EVIDENCE.md).

The client now reconnects a dropped socket with backoff and requests an initial snapshot on the new connection; a forced-close browser test recovered the saved pin. HTTP requests attempt refresh after 401; browser expiry/refresh failure paths and full reconnect semantics are not yet verified. See [evidence](PHASE_1_EVIDENCE.md).

## Implemented board commands — 2026-10-31

The live socket gateway accepts `trip.board.move`, `trip.board.remove`, `trip.board.lock`, and `trip.board.unlock` using the command fields above. Moves/removals are volatile until the existing batch watermark advances; version-conditional database updates freeze the room if the durable base does not match. Lock/unlock flush prior pending changes and commit the transition before broadcasting success; unlock requires a reason. A stale position produces `trip.board.edit.conflict` with the authoritative item. The client reconciles board updates and presents basic move/remove/lock controls. The day/time selector is UTC and is not yet a full day/time grid. These commands do not implement voting, presence, moderation, or the entire TASK-008 acceptance.

## Chat implementation — 2026-10-31

Authenticated room members can send durable text chat using `trip.chat.send`; `trip.chat.message` advances the room sequence only after the message and event commit. A reconnect snapshot includes the latest 100 messages and their reactions, with a cursor when older history exists. `GET /api/v1/trips/{tripId}/chat?before=<roomSeq>` retrieves up to 50 earlier committed messages. `POST /api/v1/trips/{tripId}/chat` accepts `{body}` and an optional UUID `Idempotency-Key`; it uses the same room authorization and persistence path. The currently implemented cursor is a sequence number, not the opaque cursor proposed above. Muted members and finalized trips cannot send or react. Messages are rendered as text by React.

`trip.chat.typing` accepts `{isTyping:boolean}` and emits ephemeral `trip.chat.typing.update`; true indicators expire after three seconds, and the server throttles true updates to one per second per user. `trip.chat.react` accepts common command IDs plus `messageId`, `emoji`, and `active`; the current allowlist is 👍, ❤️, 😂 and 🎉. Reactions are durable and unique per message/user/emoji. The client shows an optimistic reaction pending the committed update. This is a partial TASK-010 implementation; complete role/isolation and failure coverage remains to be demonstrated.

## Presence and connection measurement — 2026-10-31

The room tracks sockets by authenticated user and publishes ephemeral `trip.presence.update` notifications with active member summaries, distinct-user counts, connected Planners and Leader connection status. Additional tabs use `updated`; first/last identity connection uses joined/left. Snapshots include connectedUsers and leaderConnected. The browser updates its member list and online indicators. Disconnect cleanup is shielded from cancellation while completing the database-backed presence update. Ping/pong echoes the nonce and client timestamp and adds server timestamps; the browser sends a ping every 10 seconds, displays round-trip time and reconnects when no pong is received for 30 seconds. These are connection indicators, not performance acceptance evidence. Leader moderation/transfer remain pending.

## Phase 2 sequenced events and snapshots — 2026-10-31

`trip.moderation.command` is implemented for mute/unmute/remove/lockRoom/unlockRoom/transfer with common IDs, expectedStateVersion and optional targetUserId. The committed `trip.moderation.update` includes stateVersion, roomSeq/epoch, eventId/correlationId, durable=true, roomLocked, leaderUserId, leaderConnected, connectedUsers and current active members (including muted). Transfer swaps both membership roles and trips.leader_user_id in one transaction. Removed members are closed with 1008 and cannot replay an old invite join. No automatic promotion occurs on Leader disconnect.

Proposed addition `trip.constraints.update` is both the client command and its committed server event. The command includes common IDs, expectedStateVersion, and group categoryCeilingsMinor **or** self targetUserId/constraints. The event carries versions/identifiers and group ceilings, without broadcasting another user's private ceiling values. Clients request a fresh actor-authorized snapshot after this event. Group settings require a connected Leader; self dietary/category declarations do not confer a role.

`trip.ai.suggestion` is now a committed sequenced event. It contains the HTTP answer fields described in API_SPECIFICATION. Clients advance their aggregate sequence on AI/constraints/moderation events as well as board/chat/reactions. Ephemeral presence/typing/pong events do not advance roomSeq. Presence includes current stateVersion, including updates after an HTTP join, so the next deliberate settings action uses the latest observed version. A stale settings action still rejects explicitly and requests reconciliation.

Snapshots now include active member mute/role flags, own `preferences`, trip `categoryCeilingsMinor`, connectedUsers/leaderConnected, current chat/reactions/cursor and the latest committed suggestion, alongside lifecycle/budgets/watermarks. A snapshot or new epoch replaces the client's aggregate; it does not silently replay uncommitted commands. Timed election/ballot and conflict fields remain Phase 3 additions, not fabricated empty working services. Browser token expiry/revocation, multi-tab disconnect and actual crash tests are recorded in [Phase 2 evidence](PHASE_2_EVIDENCE.md).

## Phase 3 live additions

`trip.vote.start`/`trip.vote.open` commands accept expectedVersions keyed by item UUID and durationSeconds 10..300 (default 60). `trip.vote.submit`/`trip.vote.cast` accept voteId,choiceVenueId,expectedBallotVersion. Both invoke the same election services as REST. Common commandId/correlationId remain required. `trip.board.split` performs versioned attendee/even-or-weighted edits through the same service as HTTP.

Core `trip.vote.open`, `trip.vote.cast` and `trip.vote.resolved` retain their PRD fields and additionally carry a complete bounded vote object. Open/resolved carry budgetSummary and affectedItems; resolution also carries activeItems/archivedItems. The client requests a full snapshot to reconcile these multi-item transitions. Cast includes authenticated userId and incremented ballotVersion. No winner is published before commit.

`trip.board.conflict` is now emitted after its transaction commits: `{fingerprint,conflictType,itemIds,details,status,roomSeq,roomEpoch,durable:true}`. Open and resolved incidents carry the resulting committed boundary without consuming a new sequence; clients refetch the snapshot. Snapshots include persisted open/resolved history and current ballots. `session.ended` triggers a finalized snapshot. `trip.recommendations.updated` is an invalidation signal; it does not advance roomSeq. The browser separately increments its recommendation refresh token so a same-sequence model/interaction update still refetches the rail. The server-assigned envelope and all original core event names remain unchanged.
## Phase 4 transport rejection

Binary frames close with 1003; text frames over 65,536 UTF-8 bytes close with 1009. Malformed JSON or an invalid event/payload envelope emits `trip.command.error` / `INVALID_COMMAND`. The existing per-socket 40-command/second limit closes 1008. These checks do not change the core event names or server-authoritative version rules.

