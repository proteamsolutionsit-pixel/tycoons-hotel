"""Password hashing and admin session tokens."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.timeutil import utcnow

ALGORITHM = "HS256"
SESSION_COOKIE = "tyc_admin"
CSRF_COOKIE = "tyc_csrf"
CSRF_HEADER = "X-CSRF-Token"

# bcrypt only looks at the first 72 bytes; refuse longer input rather than
# silently truncating it.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("ascii"))
    except ValueError:
        return False


# A real hash to compare against when the email is unknown, so a login for a
# missing account takes as long as one with a wrong password.
DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(rounds=12)).decode("ascii")


def password_problems(password: str) -> list[str]:
    problems = []
    if len(password) < 12:
        problems.append("at least 12 characters")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        problems.append("at most 72 bytes")
    if not any(c.islower() for c in password):
        problems.append("a lowercase letter")
    if not any(c.isupper() for c in password):
        problems.append("an uppercase letter")
    if not any(c.isdigit() for c in password):
        problems.append("a number")
    return problems


def create_session_token(user_id: int, token_version: int) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_expire_minutes)).timestamp()),
        "typ": "admin",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_session_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM],
                             options={"require": ["exp", "sub", "ver"]})
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == "admin" else None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
