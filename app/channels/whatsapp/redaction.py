from __future__ import annotations

import re
from typing import Any

_PHONE_PATTERN = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_TOKEN_PATTERN = re.compile(r"(?i)(bearer\s+)?[A-Za-z0-9_\-]{20,}")
_TEXT_KEYS = {"text", "body", "caption", "title", "description", "name"}
_SECRET_KEYS = {"token", "authorization", "auth", "password", "secret", "access_token"}


def _is_phone_like(value: str) -> bool:
    digits = "".join(ch for ch in value if ch.isdigit())
    return len(digits) >= 10


def redact_whatsapp_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            key_lower = str(key).strip().lower()
            if key_lower in _SECRET_KEYS:
                redacted[key] = "[REDACTED_TOKEN]"
            elif key_lower in _TEXT_KEYS and isinstance(value, str):
                redacted[key] = "[REDACTED_TEXT]"
            else:
                redacted[key] = redact_whatsapp_payload(value)
        return redacted
    if isinstance(payload, list):
        return [redact_whatsapp_payload(item) for item in payload]
    if isinstance(payload, str):
        if _is_phone_like(payload):
            return "[REDACTED_PHONE]"
        masked = _PHONE_PATTERN.sub("[REDACTED_PHONE]", payload)
        return _TOKEN_PATTERN.sub("[REDACTED_TOKEN]", masked)
    return payload
