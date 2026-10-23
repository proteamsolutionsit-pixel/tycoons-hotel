"""Password hashing, password policy and opaque-token helpers.

Passwords: Argon2id (argon2-cffi, RFC 9106 low-memory profile). Hashes made by
the earlier bcrypt implementation still verify and are re-hashed to Argon2id on
the next successful sign-in (`needs_rehash`).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.profiles import RFC_9106_LOW_MEMORY

SESSION_COOKIE = "tyc_admin"
CSRF_COOKIE = "tyc_csrf"
CSRF_HEADER = "X-CSRF-Token"

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

_hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)  # Argon2id, t=3, m=64 MiB, p=4


def hash_password(password: str) -> str:
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password is too long")
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or len(password) > MAX_PASSWORD_LENGTH:
        return False
    if stored_hash.startswith("$2"):  # legacy bcrypt
        raw = password.encode("utf-8")
        if len(raw) > 72:
            return False
        try:
            return bcrypt.checkpw(raw, stored_hash.encode("ascii"))
        except ValueError:
            return False
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    if stored_hash.startswith("$2"):
        return True
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True


# A real hash to verify against when the account doesn't exist, so a failed
# login takes the same time whether or not the email is registered.
DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

# Most common passwords and patterns staff tend to pick. Short on purpose: the
# length + character-class rules already exclude the bulk of breach lists.
_COMMON = {
    "password", "passw0rd", "p@ssword", "p@ssw0rd", "welcome", "letmein", "qwerty", "admin", "administrator",
    "iloveyou", "monkey", "dragon", "sunshine", "princess", "football", "baseball", "master", "superman",
    "trustno1", "changeme", "tycoons", "tycoon", "hotel", "bengaluru", "bangalore", "india", "razorpay",
}


def password_problems(password: str, *, email: str | None = None, name: str | None = None) -> list[str]:
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"at most {MAX_PASSWORD_LENGTH} characters")
    if not any(c.islower() for c in password):
        problems.append("a lowercase letter")
    if not any(c.isupper() for c in password):
        problems.append("an uppercase letter")
    if not any(c.isdigit() for c in password):
        problems.append("a number")
    lowered = password.lower()
    simplified = "".join(c for c in lowered if c.isalpha())
    if any(w in lowered or w == simplified for w in _COMMON):
        problems.append("no common words such as 'password' or the hotel's name")
    personal = []
    if email:
        personal.append(email.split("@")[0].lower())
    if name:
        personal.extend(p.lower() for p in name.split() if len(p) >= 4)
    if any(p and len(p) >= 4 and p in lowered for p in personal):
        problems.append("nothing from your name or email address")
    if len(set(password)) < 6:
        problems.append("more variety (too many repeated characters)")
    return problems


def new_token() -> str:
    """256-bit random URL-safe token (session ids, CSRF, reset links)."""
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
