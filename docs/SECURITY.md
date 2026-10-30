# Security design

Security design and partially verified controls, PRD §10.1; verification evidence and limitations appear below. Private hosting limits exposure but does not remove authorization requirements. [API](API_SPECIFICATION.md) and [WebSocket](WEBSOCKET_PROTOCOL.md) share one policy module.

## Identity and tokens

Use Argon2id password hashing through pwdlib; passwords 12..128 characters, permit password managers and spaces; never log or truncate. Normalize email for uniqueness; generic failed-login response, rate-limit login/register by source/account and apply bounded cooldown. Registration never accepts role/Admin flags. Create Admin only through local authenticated operator CLI and document credentials outside Git.

Access JWT default 15 min, maximum 60 min. Verify signature with explicit algorithm allowlist, issuer, audience, exp, nbf, sub and session ID; reject algorithm confusion and unsigned tokens. Generate signing secret outside source; maintain key ID for rotation. Token identifies user/session, not authoritative current room role. Session revocation and current membership checked for room-sensitive actions. On logout/removal invalidate active socket access immediately through local registry; expiry closes remaining connection.

Opaque refresh tokens expire provisionally in 7 days, stored as hashes with family/version, rotate every use, revoke family on reuse. Refresh cookie HttpOnly, SameSite=Strict, Secure on HTTPS, path `/api/v1/auth`; enforce trusted Origin plus CSRF header/token for cookie-authenticated mutations. Access token returned to frontend memory for HTTP Bearer; never localStorage. Set same JWT in a separate HttpOnly `/ws` cookie for browser handshake because native browser WebSocket cannot set arbitrary Authorization headers. Restrict socket origins and validate cookie JWT before accept. Local HTTP loopback profile explicitly disables Secure cookies; private LAN uses HTTPS/WSS. Do not put tokens in URL query strings.

## Authorization and validation

Every trip/item/message/vote query verifies trip ownership through active membership before returning data. Viewers cannot edit/vote under provisional baseline; canPin=false Planners can vote but not move. Leader-only operations re-read membership and expected state version; Admin permits datasets, never arbitrary trip access. Invite codes use cryptographic randomness, hashed storage, expiry/max-uses/revocation and rate-limited redemption. Codes cannot contain a trusted user ID. Removed membership blocks old invite redemption; re-admission requires explicit Leader action (future member status edit).

Validate ID linkage, date ranges, supported currencies, safe integer money, finite coordinates, hours, enum vocabulary, attendee membership and expected versions. Reject unknown fields to expose attempted role/body userId injection. Bound pagination/frame/body/description sizes and per-user request rates. Dataset MIME/extension is advisory; parse actual content safely, stage outside served assets and reject unsafe YAML. Never accept uploaded file path or external URL as server filesystem destination.

Chat and source text are plain Unicode. React escapes text nodes; never `dangerouslySetInnerHTML`. No arbitrary Markdown HTML, script URLs, SVG uploads or remote content embedding. If links are later enabled, allow only safe schemes and escape labels. Server normalizes text and strips control characters while preserving ordinary user content; output escaping remains essential. SQLAlchemy bound parameters prevent SQL injection; never interpolate search/order expressions from user input. Apply CSP with self-hosted assets and exact allowed model/API connection origins.

## AI, secrets and logging

Questions/descriptions are untrusted prompt data. Only validated IDs/field references can enter rendered grounded output; model cannot call arbitrary tools, execute code or write board state. Limit context and model output; model runtime binds loopback. No personal information is necessary for inference; use pseudonymous attendee constraints. Recommendations use synthetic/test interaction data and have bounded retention under operator control.

`.env`, DB dumps, tokens, raw uploads and model caches are ignored; commit `.env.example` names with empty/safe placeholders only. Secret scans run on staged changes and full history before submission. If exposed, revoke/rotate immediately and remove from history as a separate deliberate recovery operation. Logs include event type, trip/session correlation, actor pseudonym, timing, outcome and source IDs; exclude password, token, invite code, email, full question/chat and raw model response. AI request/response logging (§10.3) means safe structured summaries/status/source IDs and hashes, not sensitive bodies.

## Planned security verification

SEC-01 forged/expired/wrong-audience JWT, refresh reuse, logout socket closure and origin/CSRF; SEC-02 complete HTTP and socket role matrix including Admin without membership; SEC-03 cross-trip ID substitution and removed users; SEC-04 stored-XSS/SQL injection, malformed/oversized input and upload attacks; SEC-05 prompt injection/citation escape; SEC-06 secret scan and safe logging. Each rejection must leave state unchanged. No passed security assessment is claimed.

The code now contains Argon2id password and signed access-token primitives. These are not an authentication service: session checks, rotation/reuse handling, rate limits, transport integration and the role matrix remain unimplemented and unverified. See [evidence](PHASE_1_EVIDENCE.md).

A pure shared role/capability policy has unit tests, but is not wired to HTTP or sockets. The phase 1 security acceptance remains unmet.

Trip detail reads now require active membership, and login/registration reject a supplied untrusted Origin. These are partial checks and do not establish socket authorization, removal closure, or the full security matrix.

First-slice tests now cover Viewer pin rejection via both transports and immediate socket closure after logout; other role combinations, token expiry timing, cross-trip object substitution and the complete matrix remain pending. See [evidence](PHASE_1_EVIDENCE.md).

The 2026-10-30 role tests also cover expired credentials and an Admin without trip membership on HTTP/socket, plus invite-management denial for Planner and outsider accounts. The complete role matrix, concurrent redemption and removed-membership cases remain pending.

The first-slice role and session checks are documented in [phase 1 evidence](PHASE_1_EVIDENCE.md). They do not replace the later complete security assessment. Socket token/membership validity is polled at up to five-second intervals while idle; explicit logout and detected refresh reuse close tracked sockets. Full moderation, input and prompt-injection tests remain later work.
