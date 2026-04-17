#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from uuid import uuid4


REQUEST_CODE_SUFFIX_LENGTH = 6
MAX_REQUEST_CODE_GENERATION_ATTEMPTS = 8


def _to_base36(value: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if value == 0:
        return "0"

    chars: list[str] = []
    while value:
        value, remainder = divmod(value, 36)
        chars.append(alphabet[remainder])
    return "".join(reversed(chars))


def generate_request_code(*, prefix: str, suffix_length: int = REQUEST_CODE_SUFFIX_LENGTH) -> str:
    encoded_uuid = _to_base36(uuid4().int)
    suffix = encoded_uuid[-suffix_length:].rjust(suffix_length, "0")
    return f"{prefix}-{suffix}"
