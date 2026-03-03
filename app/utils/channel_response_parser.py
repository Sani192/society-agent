#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for parsing provider API error responses."""

from __future__ import annotations

from json import JSONDecodeError
from typing import Any


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_provider_error(
    *,
    channel: str,
    response_payload: dict[str, Any] | None = None,
    response_status_code: int | None = None,
) -> dict[str, Any]:
    """Extract normalized provider error fields from known channel response formats."""
    payload = _safe_dict(response_payload)

    if channel == "whatsapp":
        # Meta Graph API error schema: {"error": {...}}
        error_obj = _safe_dict(payload.get("error"))
        message = error_obj.get("message")
        code = error_obj.get("code")
        subcode = error_obj.get("error_subcode")
        error_type = error_obj.get("type")
        if code is not None and subcode is not None:
            provider_error_code = f"{code}:{subcode}"
        elif code is not None:
            provider_error_code = str(code)
        else:
            provider_error_code = None
        if provider_error_code and error_type:
            provider_error_code = f"{error_type}:{provider_error_code}"
        elif error_type:
            provider_error_code = str(error_type)
        return {
            "provider_error_code": provider_error_code,
            "provider_error_message": str(message) if message else None,
            "http_status": response_status_code,
        }

    if channel == "telegram":
        # Telegram Bot API error schema: {"ok": false, "error_code": ..., "description": "..."}
        if payload.get("ok") is False or payload.get("error_code") is not None:
            return {
                "provider_error_code": (
                    str(payload.get("error_code")) if payload.get("error_code") is not None else None
                ),
                "provider_error_message": (
                    str(payload.get("description")) if payload.get("description") else None
                ),
                "http_status": response_status_code,
            }

    return {
        "provider_error_code": None,
        "provider_error_message": None,
        "http_status": response_status_code,
    }


def parse_provider_error_from_exception(*, channel: str, exc: Exception) -> dict[str, Any]:
    """Try to read an HTTP response payload from an exception and parse provider error fields."""
    response = getattr(exc, "response", None)
    payload: dict[str, Any] = {}
    status_code: int | None = None

    if response is not None:
        status_code = getattr(response, "status_code", None)
        try:
            payload = response.json() if getattr(response, "content", None) else {}
        except (AttributeError, ValueError, JSONDecodeError):
            payload = {}

    parsed = parse_provider_error(
        channel=channel,
        response_payload=payload,
        response_status_code=status_code,
    )
    if not parsed.get("provider_error_message"):
        parsed["provider_error_message"] = str(exc)
    return parsed
