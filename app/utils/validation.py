from __future__ import annotations

import re
import uuid
from typing import Any


_SAFE_TEXT_RE = re.compile(r"[^\w\s,.:;@#&()\-+/]", re.UNICODE)
_STRICT_UUID_FIELDS = {
    "event_id",
    "flat_id",
    "member_id",
    "request_id",
    "committee_member_id",
    "society_id",
}


class ValidationError(Exception):
    """Raised when external input fails security validation."""


def validate_uuid(value, *, field_name: str, allow_none: bool = False) -> uuid.UUID | None:
    if value is None:
        if allow_none:
            return None
        raise ValidationError(f"Invalid {field_name}")
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field_name}") from exc


def validate_uuid_if_candidate(value: Any, *, field_name: str):
    """Validate UUID-like inputs while preserving legacy non-UUID identifiers."""
    if field_name in _STRICT_UUID_FIELDS:
        return validate_uuid(value, field_name=field_name)

    if isinstance(value, uuid.UUID):
        return validate_uuid(value, field_name=field_name)

    text = str(value).strip() if value is not None else ""
    if len(text) in {32, 36}:
        return validate_uuid(text, field_name=field_name)
    return value


def sanitize_command_text(value: str | None, *, max_length: int = 512) -> str:
    normalized = (value or "").strip()
    if len(normalized) > max_length:
        normalized = normalized[:max_length]
    return _SAFE_TEXT_RE.sub("", normalized)
