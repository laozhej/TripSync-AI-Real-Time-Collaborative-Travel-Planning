"""Authentication routes. Session revocation is checked for every HTTP request."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import deque
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import jwt

from app.auth.tokens import decode_access_token, hash_password, issue_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
_attempts: dict[str, deque] = {}
_dummy_hash = hash_password("dummy password used for unknown accounts")


def throttle(request: Request, email: str):
    """Bound login/register attempts per source and account in this one-worker process."""
    now = time.monotonic()
    source = request.client.host if request.client else "unknown"
    keys = ("source:" + digest(source), "account:" + digest(email))
    if len(_attempts) >= 10000:
        for key in list(_attempts):
            if not _attempts[key] or _attempts[key][-1] <= now - 60:
                del _attempts[key]
        if len(_attempts) >= 10000 and any(key not in _attempts for key in keys):
            raise HTTPException(429, "Too many attempts")
    for key in keys:
        events = _attempts.setdefault(key, deque())
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= 10:
            raise HTTPException(429, "Too many attempts")
    for key in keys:
        _attempts[key].append(now)


def check_optional_origin(request: Request):
    origin = request.headers.get("origin")
    allowed = {v.strip() for v in os.getenv("ALLOWED_ORIGINS", "").split(",") if v.strip()}
    if origin is not None and origin not in allowed:
        raise HTTPException(403, "Invalid origin")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Login(Strict):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, email):
        email = email.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("invalid email")
        return email


class Register(Login):
    display_name: str = Field(alias="displayName", min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def name_valid(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("invalid display name")
        return value


def auth_config():
    key = os.getenv("JWT_SIGNING_KEY", "")
    issuer = os.getenv("JWT_ISSUER", "")
    audience = os.getenv("JWT_AUDIENCE", "")
    if len(key.encode()) < 32 or not issuer or not audience:
        raise HTTPException(503, "Authentication is not configured")
    return dict(key=key, issuer=issuer, audience=audience)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_check(request: Request):
    allowed = {v.strip() for v in os.getenv("ALLOWED_ORIGINS", "").split(",") if v.strip()}
    origin = request.headers.get("origin")
    csrf_cookie = request.cookies.get("tripsync_csrf", "")
    csrf_header = request.headers.get("x-csrf-token", "")
    if origin not in allowed or not csrf_cookie or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(403, "Invalid origin or CSRF token")


def set_cookies(response, refresh, csrf, access):
    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie("tripsync_refresh", refresh, httponly=True, secure=secure, samesite="strict", path="/api/v1/auth", max_age=7*86400)
    response.set_cookie("tripsync_csrf", csrf, httponly=False, secure=secure, samesite="strict", path="/", max_age=7*86400)
    response.set_cookie("tripsync_ws", access, httponly=True, secure=secure, samesite="strict", path="/ws", max_age=900)


async def close_session_sockets(app, session_id):
    for socket in tuple(app.state.socket_sessions.get(session_id, ())):
        try:
            await socket.close(code=1008)
        except Exception:
            # The peer may already have disconnected before the registry is pruned.
            pass


def access_response(user_id, session_id, user):
    access = issue_access_token(user_id, session_id, **auth_config())
    return access, {"accessToken": access, "expiresIn": 900, "user": user}


@router.post("/register", status_code=201)
async def register(body: Register, request: Request):
    check_optional_origin(request)
    throttle(request, body.email)
    hashed = await asyncio.to_thread(hash_password, body.password)
    uid = uuid4()
    try:
        async with request.app.state.engine.begin() as conn:
            await conn.execute(text("INSERT INTO users (id,normalized_email,password_hash,display_name) VALUES (:id,:email,:password,:name)"),
                               dict(id=uid, email=body.email, password=hashed, name=body.display_name))
    except IntegrityError:
        raise HTTPException(409, "Account already exists") from None
    return {"userId": str(uid), "displayName": body.display_name}


@router.post("/login")
async def login(body: Login, request: Request, response: Response):
    check_optional_origin(request)
    auth_config()
    throttle(request, body.email)
    async with request.app.state.engine.connect() as conn:
        row = (await conn.execute(text("SELECT id,password_hash,display_name,is_admin FROM users WHERE normalized_email=:email"), {"email": body.email})).mappings().first()
    valid = await asyncio.to_thread(verify_password, body.password, row["password_hash"] if row else _dummy_hash)
    if row is None or not valid:
        raise HTTPException(401, "Invalid email or password")
    uid, sid, family = row["id"], uuid4(), uuid4()
    refresh, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(days=7)
    async with request.app.state.engine.begin() as conn:
        await conn.execute(text("INSERT INTO auth_sessions (id,user_id,refresh_hash,family_id,expires_at) VALUES (:id,:uid,:hash,:family,:expiry)"),
                           dict(id=sid, uid=uid, hash=digest(refresh), family=family, expiry=expiry))
        await conn.execute(text("INSERT INTO refresh_tokens (token_hash,session_id,expires_at) VALUES (:hash,:sid,:expiry)"),
                           dict(hash=digest(refresh), sid=sid, expiry=expiry))
    user = {"userId": str(uid), "displayName": row["display_name"], "isAdmin": row["is_admin"]}
    access, result = access_response(uid, sid, user)
    set_cookies(response, refresh, csrf, access)
    return result


async def authenticated(request: Request, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        uid, sid = decode_access_token(authorization[7:], **auth_config())
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(401, "Invalid access token") from None
    async with request.app.state.engine.connect() as conn:
        row = (await conn.execute(text("""SELECT u.id,u.display_name,u.is_admin FROM users u
            JOIN auth_sessions s ON s.user_id=u.id WHERE u.id=:uid AND s.id=:sid
            AND s.revoked_at IS NULL AND s.expires_at > now()"""), dict(uid=uid, sid=sid))).mappings().first()
    if not row:
        raise HTTPException(401, "Session expired or revoked")
    return dict(user_id=uid, session_id=sid, is_admin=row["is_admin"], display_name=row["display_name"])


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    csrf_check(request)
    auth_config()
    old = request.cookies.get("tripsync_refresh", "")
    if not old or len(old) > 256:
        raise HTTPException(401, "Invalid refresh token")
    new, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    rejected = False
    revoked = False
    row = None
    async with request.app.state.engine.begin() as conn:
        row = (await conn.execute(text("""SELECT t.session_id,t.used_at,t.expires_at,s.user_id,s.family_id,s.revoked_at,
            s.expires_at AS session_expires,u.display_name,u.is_admin FROM refresh_tokens t
            JOIN auth_sessions s ON s.id=t.session_id JOIN users u ON u.id=s.user_id WHERE t.token_hash=:hash"""), {"hash": digest(old)})).mappings().first()
        if not row:
            rejected = True
        elif row["used_at"] is not None:
            await conn.execute(text("UPDATE auth_sessions SET revoked_at=:now WHERE family_id=:family AND revoked_at IS NULL"), dict(now=now, family=row["family_id"]))
            rejected = True
            revoked = True
        elif row["revoked_at"] is not None or row["expires_at"] <= now or row["session_expires"] <= now:
            rejected = True
        else:
            result = await conn.execute(text("UPDATE refresh_tokens SET used_at=:now WHERE token_hash=:hash AND used_at IS NULL RETURNING token_hash"), dict(now=now, hash=digest(old)))
            if not result.first():
                await conn.execute(text("UPDATE auth_sessions SET revoked_at=:now WHERE family_id=:family AND revoked_at IS NULL"), dict(now=now, family=row["family_id"]))
                rejected = True
                revoked = True
            else:
                await conn.execute(text("INSERT INTO refresh_tokens (token_hash,session_id,expires_at) VALUES (:hash,:sid,:expiry)"),
                                   dict(hash=digest(new), sid=row["session_id"], expiry=row["session_expires"]))
                await conn.execute(text("UPDATE auth_sessions SET refresh_hash=:hash WHERE id=:sid"), dict(hash=digest(new), sid=row["session_id"]))
    if rejected:
        if revoked:
            await close_session_sockets(request.app, row['session_id'])
        raise HTTPException(401, "Invalid refresh token")
    user = {"userId": str(row["user_id"]), "displayName": row["display_name"], "isAdmin": row["is_admin"]}
    access, result = access_response(row["user_id"], row["session_id"], user)
    set_cookies(response, new, csrf, access)
    return result


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, actor=Depends(authenticated)):
    csrf_check(request)
    async with request.app.state.engine.begin() as conn:
        await conn.execute(text("UPDATE auth_sessions SET revoked_at=now() WHERE id=:id AND revoked_at IS NULL"), {"id": actor["session_id"]})
    await close_session_sockets(request.app, actor['session_id'])
    for key, path in (("tripsync_refresh", "/api/v1/auth"), ("tripsync_csrf", "/"), ("tripsync_ws", "/ws")):
        response.delete_cookie(key, path=path)
    response.status_code = 204
    return response
