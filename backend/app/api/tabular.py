"""Shared plumbing for the admin data tables: literal search patterns, sort
ordering and CSV export (spreadsheet-safe, capped, and itself audited)."""
from __future__ import annotations

import csv
import enum
import io
import json
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from fastapi import Request, Response

from app.core.timeutil import hotel_today
from app.models import AdminUser
from app.services import audit

EXPORT_MAX_ROWS = 10_000


def like_pattern(text: str, *, prefix: bool = False) -> str:
    """LIKE pattern for a user's search text with %, _ and \\ taken literally.
    prefix=True means "starts with" instead of "contains"."""
    body = text.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return body + "%" if prefix else "%" + body + "%"


def ordered(stmt, column, order: str, tiebreak):
    """Sort by a column in either direction, with a stable tiebreak."""
    return stmt.order_by(column.asc() if order == "asc" else column.desc(), tiebreak.desc())


def csv_cell(value: Any) -> str:
    """One CSV value. Text starting with =, +, -, @, tab or CR is prefixed with
    ' so spreadsheet apps show it instead of running it as a formula."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, enum.Enum):
        value = value.value
    if isinstance(value, datetime):
        text = value.isoformat(sep=" ", timespec="seconds")
    elif isinstance(value, date):
        text = value.isoformat()
    elif isinstance(value, dict | list):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_response(name: str, header: list[str], rows: Iterable[Iterable[Any]]) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for row in rows:
        w.writerow([csv_cell(v) for v in row])
    filename = f"{name}-{hotel_today().isoformat()}.csv"
    # BOM so Excel opens the UTF-8 file with the right encoding
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def record_export(request: Request, actor: AdminUser, resource: str, rows: int, filters: dict[str, Any]) -> None:
    """Exports carry personal data out of the system, so each one is audited."""
    audit.record_now(action=f"{resource}.export", actor=actor, resource_type=resource, request=request,
                     details={"rows": rows, "filters": {k: str(v) for k, v in filters.items() if v not in (None, "")}})
