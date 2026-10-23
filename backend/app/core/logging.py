"""Structured (JSON) logging with a redaction safety net: values of fields
whose names look sensitive are replaced before anything is written."""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}
_SENSITIVE_KEY = re.compile(r"pass|secret|token|signature|authorization|cookie|card|cvv|otp|api_key", re.I)
# Inline secrets inside free text, e.g. a URL with credentials or "key_secret=..."
_SENSITIVE_TEXT = re.compile(r"(?i)(mysql\+pymysql://[^:/\s]+:)[^@\s]+(@)|((?:secret|password|token)=)[^&\s]+")


def redact_text(text: str) -> str:
    return _SENSITIVE_TEXT.sub(lambda m: (m.group(1) + "***" + m.group(2)) if m.group(1) else (m.group(3) + "***"),
                               text)


def _redact(value, key: str = "", depth: int = 0):
    if key and _SENSITIVE_KEY.search(key):
        return "[redacted]"
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        return {k: _redact(v, str(k), depth + 1) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_redact(v, "", depth + 1) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_text(record.getMessage()),
        }
        for k, v in vars(record).items():
            if k not in _RESERVED and not k.startswith("_"):
                payload[k] = _redact(v, k)
        if record.exc_info:
            payload["exc"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


class _RedactingTextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output
                         else _RedactingTextFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # uvicorn's own access log duplicates our request log
    logging.getLogger("uvicorn.access").disabled = True
