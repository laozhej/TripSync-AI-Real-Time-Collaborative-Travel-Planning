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

## Security verification catalog

SEC-01 forged/expired/wrong-audience JWT, refresh reuse, logout socket closure and origin/CSRF; SEC-02 complete HTTP and socket role matrix including Admin without membership; SEC-03 cross-trip ID substitution and removed users; SEC-04 stored-XSS/SQL injection, malformed/oversized input and upload attacks; SEC-05 prompt injection/citation escape; SEC-06 secret scan and safe logging. Each rejection must leave state unchanged. No passed security assessment is claimed.

The first-slice role and session checks are documented in [phase 1 evidence](PHASE_1_EVIDENCE.md). They do not replace the later complete security assessment. Socket token/membership validity is polled at up to five-second intervals while idle; explicit logout and detected refresh reuse close tracked sockets. Full moderation, input and prompt-injection tests remain later work.

## Phase 2 security checks — 2026-10-31

The shared room services re-read current membership/session and role on sensitive changes. Admin does not bypass trip membership or Leader permissions. Removal closes every tracked membership tab and rejects both new and cached invite redemption. Tests cover Planner/Viewer/Admin rejection, foreign-trip message/source/attendee/anchor IDs, mute enforcement, stale settings, atomic transfer, revoked sessions, invalid text and context removal during generation. Browser token refresh is exercised with a test-only short first token and refresh failure returns to sign-in. Operational logs use a field whitelist; local inference receives only bounded eligible source context, never credentials or full chat history. Model IDs/reason fields and source versions are validated independently of schema generation, with React text rendering and no arbitrary source URLs.

These are actual Phase 2 checks, not the final SEC-01..06 audit. Full later-feature upload/recommendation/voting security and global limits remain TASK-021 and related features. See [evidence](PHASE_2_EVIDENCE.md).

## Phase 4 transport hardening — 2026-11-02

`app/transport.py` caps every HTTP body at 2 MiB before JSON parsing or route execution, including chunked bodies and misleading Content-Length. It adds no-store, nosniff and no-referrer response headers. Dataset validation retains its own limit. Oversized WebSocket text closes 1009; binary input closes 1003 rather than raising an unhandled text-frame exception. Existing 40-commands/second socket limit and bounded subscriber queues remain in force. These process-local controls do not constitute a public-internet deployment profile or comprehensive global HTTP request throttling.

`test_phase4_security.py` consolidates later-feature member/outsider-Admin reads, mutation denials, body identity/foreign venue rejection, malformed JSON/envelopes, binary/oversized sockets and bad origins. Existing auth/moderation/Concierge/Phase 3 tests cover valid-object role restrictions, revocation/expiry/removal, refresh reuse, upload validation, prompt/citation boundaries and atomic failures. `test_transport_limits.py` proves exact-limit acceptance and streamed overflow rejection before route execution. Final commands, scan scope and limitations are recorded in PHASE_4_EVIDENCE.md.

## Reload session restoration — 2026-11-02 follow-up

The React entry point now restores authentication on startup through the existing HttpOnly refresh-cookie/CSRF endpoint before presenting the sign-in form. Previously refresh ran only after a request with an existing in-memory access token returned 401; reload erased that token and never started restoration. Startup and ordinary 401 retry share one in-flight refresh promise and restore the server-returned user. Access tokens remain in memory; none are persisted to localStorage/sessionStorage. A loading status prevents a login-form flash while restoration is pending. Logged-out and revoked/expired sessions still require sign-in. This changes no backend token/session/reuse policy. Real Chrome regression evidence is recorded in FRONTEND_UI_EVIDENCE.md.
