"""Encryption at rest for secrets entered in the admin (Razorpay key secret,
webhook secret). Fernet: AES-128-CBC + HMAC-SHA256, authenticated.

The key comes from SETTINGS_ENCRYPTION_KEY, or else from a key file generated
once under STORAGE_DIR/private. Either way it never lives in the database, so a
copied database alone does not reveal the secrets. Lose the key and the stored
secrets are unreadable: they then have to be entered again.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

log = logging.getLogger("app.secretbox")
_lock = threading.Lock()
_fernet: Fernet | None = None


class SecretUnavailable(Exception):
    """The stored value cannot be decrypted with the current key."""


def key_file() -> Path:
    return get_settings().storage_dir / "private" / "settings.key"


def _load_key() -> bytes:
    env_key = get_settings().settings_encryption_key.strip()
    if env_key:
        return env_key.encode()
    path = key_file()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # O_EXCL: two workers starting together cannot both write a key
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as fh:
                fh.write(Fernet.generate_key())
            log.warning("Generated a new settings encryption key", extra={"key_file": str(path)})
    return path.read_bytes().strip()


def _box() -> Fernet:
    global _fernet
    with _lock:
        if _fernet is None:
            _fernet = Fernet(_load_key())
        return _fernet


def encrypt(plain: str) -> str:
    return _box().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _box().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretUnavailable from exc


def reset_cache() -> None:
    """Tests: forget the loaded key."""
    global _fernet
    with _lock:
        _fernet = None
