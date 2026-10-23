"""File uploads: CVs (private) and admin images (public under /media).

The stored name is always random - the uploader never chooses it - and the
type is checked against the file's leading bytes, not just its extension or
the client-supplied Content-Type.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import AppError

_CHUNK = 64 * 1024

# extension -> (content type, accepted magic-byte prefixes)
CV_TYPES = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".doc": ("application/msword", (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (b"PK\x03\x04",)),
}
IMAGE_TYPES = {
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".webp": ("image/webp", (b"RIFF",)),
}


@dataclass
class StoredFile:
    relative_path: str
    original_name: str
    content_type: str
    size: int


def private_dir() -> Path:
    return get_settings().storage_dir / "private"


def public_dir() -> Path:
    return get_settings().storage_dir / "public"


def _safe_original_name(name: str | None) -> str:
    name = Path(name or "file").name
    return "".join(c for c in name if c.isprintable() and c not in '<>:"/\\|?*')[:200] or "file"


async def _store(upload: UploadFile, *, allowed: dict, max_bytes: int, dest_root: Path, subdir: str,
                 label: str) -> StoredFile:
    original = _safe_original_name(upload.filename)
    ext = Path(original).suffix.lower()
    if ext not in allowed:
        raise AppError(f"Please upload a {label} file ({', '.join(sorted(allowed))}).", code="invalid_file_type",
                       details=[{"field": "file", "message": "Unsupported file type"}])
    content_type, magics = allowed[ext]

    head = await upload.read(16)
    if not any(head.startswith(m) for m in magics) or (ext == ".webp" and head[8:12] != b"WEBP"):
        raise AppError(f"That file doesn't look like a valid {ext} file.", code="invalid_file_content",
                       details=[{"field": "file", "message": "File content does not match its type"}])

    folder = dest_root / subdir
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = secrets.token_hex(16) + ext
    target = folder / stored_name
    size = len(head)
    try:
        with target.open("wb") as fh:
            fh.write(head)
            while chunk := await upload.read(_CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(f"The file is too large (max {max_bytes // (1024 * 1024)} MB).",
                                   code="file_too_large", status_code=413,
                                   details=[{"field": "file", "message": "File is too large"}])
                fh.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return StoredFile(relative_path=f"{subdir}/{stored_name}", original_name=original,
                      content_type=content_type, size=size)


async def store_cv(upload: UploadFile) -> StoredFile:
    return await _store(upload, allowed=CV_TYPES, max_bytes=get_settings().max_cv_bytes,
                        dest_root=private_dir(), subdir="cv", label="PDF or Word")


async def store_image(upload: UploadFile) -> tuple[StoredFile, str]:
    stored = await _store(upload, allowed=IMAGE_TYPES, max_bytes=get_settings().max_image_bytes,
                          dest_root=public_dir(), subdir="images", label="JPG, PNG or WebP")
    return stored, f"{get_settings().media_url_prefix}/{stored.relative_path}"


def resolve_private(relative_path: str) -> Path | None:
    """Resolve a stored CV path, refusing anything that escapes the private dir."""
    base = private_dir().resolve()
    candidate = (base / relative_path).resolve()
    if base not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def delete_private(relative_path: str | None) -> None:
    if relative_path and (p := resolve_private(relative_path)):
        p.unlink(missing_ok=True)
