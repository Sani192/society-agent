from __future__ import annotations

import re
import uuid


_SAFE_TEXT_RE = re.compile(r"[^\w\s,.:;@#&()\-+/]", re.UNICODE)


def validate_uuid(value, *, field_name: str, allow_none: bool = False) -> uuid.UUID | None:
    if value is None:
        if allow_none:
            return None
        raise Exception(f"Invalid {field_name}")
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise Exception(f"Invalid {field_name}") from exc


def sanitize_command_text(value: str | None, *, max_length: int = 512) -> str:
    normalized = (value or "").strip()
    if len(normalized) > max_length:
        normalized = normalized[:max_length]
    return _SAFE_TEXT_RE.sub("", normalized)

