#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Security helpers for protected channel audit storage."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

SENSITIVE_KEYS = {
    "password",
    "passcode",
    "token",
    "access_token",
    "authorization",
    "secret",
    "email",
    "phone",
    "phone_number",
    "chat_id",
    "sender_id",
    "message",
    "text",
}


class AuditCryptoError(Exception):
    pass


_CIPHERTEXT_V2_PREFIX = "v2:"


def _mask_text(value: str) -> str:
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    digits = sum(1 for c in value if c.isdigit())
    if "@" in value or digits >= 6:
        return "[REDACTED]"
    return value


def sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).strip().lower()
            if lowered in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = sanitize_payload(value)
        return redacted
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str):
        return redact_text(value=payload)
    return payload


def _encryption_key_bytes() -> bytes:
    key = settings.AUDIT_ENCRYPTION_KEY
    if not key:
        raise AuditCryptoError("AUDIT_ENCRYPTION_KEY is required when using encrypted_raw mode")
    return hashlib.sha256(key.encode("utf-8")).digest()


def _fernet_for_audit() -> Fernet:
    key = _encryption_key_bytes()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def _xor_keystream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < len(data):
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        output.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, output[: len(data)]))


def encrypt_for_audit_store(value: str | None) -> str | None:
    if value is None:
        return None
    token = _fernet_for_audit().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_CIPHERTEXT_V2_PREFIX}{token}"


def _decrypt_legacy_ciphertext(value: str) -> str:
    key = _encryption_key_bytes()
    blob = base64.urlsafe_b64decode(value.encode("utf-8"))
    nonce = blob[:16]
    signature = blob[16:48]
    ciphertext = blob[48:]
    expected = hmac.new(key, nonce + ciphertext, digestmod=hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise AuditCryptoError("Audit payload signature validation failed")
    plaintext = _xor_keystream(ciphertext, key, nonce)
    return plaintext.decode("utf-8")


def decrypt_from_audit_store(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith(_CIPHERTEXT_V2_PREFIX):
        token = value[len(_CIPHERTEXT_V2_PREFIX) :]
        try:
            return _fernet_for_audit().decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise AuditCryptoError("Audit payload decryption failed") from exc
    return _decrypt_legacy_ciphertext(value)


def dump_json(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def hash_event_record(*, prev_hash: str | None, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    material = f"{prev_hash or ''}|{canonical}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
