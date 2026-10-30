"""Password and access-token primitives, independent of transport and persistence."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

_passwords = PasswordHash.recommended()


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Password must contain 12 to 128 characters")
    return _passwords.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _passwords.verify(password, password_hash)
    except (PwdlibError, ValueError, TypeError):
        return False


def issue_access_token(user_id: UUID, session_id: UUID, *, key: str, issuer: str, audience: str, minutes: int = 15) -> str:
    if len(key.encode("utf-8")) < 32 or not 1 <= minutes <= 60 or not issuer or not audience:
        raise ValueError("Invalid token configuration")
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "sid": str(session_id), "iss": issuer, "aud": audience,
                       "iat": now, "nbf": now, "exp": now + timedelta(minutes=minutes)}, key, algorithm="HS256")


def decode_access_token(token: str, *, key: str, issuer: str, audience: str) -> tuple[UUID, UUID]:
    payload = jwt.decode(token, key, algorithms=["HS256"], issuer=issuer, audience=audience,
                         options={"require": ["sub", "sid", "iss", "aud", "iat", "nbf", "exp"]})
    try:
        return UUID(payload["sub"]), UUID(payload["sid"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("Invalid identity") from exc
