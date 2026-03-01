#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Bot API payload adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.channels.core.audit_events import NormalizedAuditEvent
from app.channels.core.types import InboundMessage
from app.utils.logger import logger


def _build_display_name(user: dict[str, Any]) -> str:
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()
    username = (user.get("username") or "").strip()

    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    if full_name:
        return full_name
    if username:
        return f"@{username}"
    return str(user.get("id") or "unknown")


def _extract_message_text(message: dict[str, Any]) -> tuple[str | None, str]:
    text = (message.get("text") or "").strip()
    if text:
        if text.startswith("/"):
            return text, "command"
        return text, "text"
    caption = (message.get("caption") or "").strip()
    if caption:
        return caption, "caption"
    return None, "non_text"


def parse_webhook_payload(payload: dict[str, Any]) -> list[InboundMessage]:
    logger.info("Parsing Telegram webhook payload")
    parsed = parse_webhook_events(payload)
    inbound: list[InboundMessage] = []
    for event in parsed:
        if event.get("kind") != "inbound":
            continue
        inbound.append(
            InboundMessage(
                channel="telegram",
                sender_id=event["sender_id"],
                display_name=event["display_name"],
                text=event["text"],
                metadata=event["metadata"],
            )
        )
    return inbound


def parse_webhook_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    update_id = payload.get("update_id")
    events: list[dict[str, Any]] = []

    message = payload.get("message")
    if isinstance(message, dict):
        events.append(_parse_message_variant(payload, message, variant="message"))

    edited_message = payload.get("edited_message")
    if isinstance(edited_message, dict):
        events.append(_parse_message_variant(payload, edited_message, variant="edited_message"))

    callback_query = payload.get("callback_query")
    if isinstance(callback_query, dict):
        events.append(_parse_callback_query(payload, callback_query))

    if not events:
        events.append(
            {
                "kind": "ignored",
                "reason": "unsupported_update_variant",
                "update_id": update_id,
                "raw": payload,
                "occurred_at": datetime.now(timezone.utc),
            }
        )

    return events


def _parse_message_variant(payload: dict[str, Any], message: dict[str, Any], *, variant: str) -> dict[str, Any]:
    text, content_type = _extract_message_text(message)
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    sender_id = sender.get("id")
    chat_id = chat.get("id")

    if text and sender_id is not None and chat_id is not None:
        return {
            "kind": "inbound",
            "variant": variant,
            "text": text,
            "sender_id": str(sender_id),
            "display_name": _build_display_name(sender),
            "chat_id": str(chat_id),
            "message_id": message.get("message_id"),
            "update_id": payload.get("update_id"),
            "content_type": content_type,
            "occurred_at": datetime.now(timezone.utc),
            "metadata": {
                "update_id": payload.get("update_id"),
                "chat_id": str(chat_id),
                "message_id": message.get("message_id"),
                "username": sender.get("username"),
                "canonical_sender_id": str(sender_id),
                "external_user_id": str(sender_id),
                "variant": variant,
                "content_type": content_type,
            },
            "raw": message,
        }

    return {
        "kind": "ignored",
        "reason": "unsupported_message_payload",
        "variant": variant,
        "update_id": payload.get("update_id"),
        "message_id": message.get("message_id"),
        "content_type": content_type,
        "raw": message,
        "occurred_at": datetime.now(timezone.utc),
    }


def _parse_callback_query(payload: dict[str, Any], callback_query: dict[str, Any]) -> dict[str, Any]:
    data = (callback_query.get("data") or "").strip()
    sender = callback_query.get("from") or {}
    sender_id = sender.get("id")
    message = callback_query.get("message") or {}
    chat_id = ((message.get("chat") or {}).get("id"))

    if data and sender_id is not None:
        effective_chat = str(chat_id) if chat_id is not None else str(sender_id)
        return {
            "kind": "inbound",
            "variant": "callback_query",
            "text": data,
            "sender_id": str(sender_id),
            "display_name": _build_display_name(sender),
            "chat_id": effective_chat,
            "message_id": message.get("message_id"),
            "update_id": payload.get("update_id"),
            "content_type": "callback_query",
            "occurred_at": datetime.now(timezone.utc),
            "metadata": {
                "update_id": payload.get("update_id"),
                "chat_id": effective_chat,
                "message_id": message.get("message_id"),
                "username": sender.get("username"),
                "canonical_sender_id": str(sender_id),
                "external_user_id": str(sender_id),
                "variant": "callback_query",
                "content_type": "callback_query",
                "callback_query_id": callback_query.get("id"),
            },
            "raw": callback_query,
        }

    return {
        "kind": "ignored",
        "reason": "unsupported_callback_query",
        "variant": "callback_query",
        "update_id": payload.get("update_id"),
        "raw": callback_query,
        "occurred_at": datetime.now(timezone.utc),
    }


def to_normalized_audit_events(events: list[dict[str, Any]]) -> list[NormalizedAuditEvent]:
    normalized: list[NormalizedAuditEvent] = []
    for event in events:
        if event.get("kind") == "inbound":
            normalized.append(
                NormalizedAuditEvent(
                    channel="telegram",
                    direction="inbound",
                    event_type="message_parsed",
                    provider_message_id=(str(event.get("message_id")) if event.get("message_id") is not None else None),
                    provider_update_id=(str(event.get("update_id")) if event.get("update_id") is not None else None),
                    chat_id_or_phone=event.get("chat_id"),
                    external_user_id=event.get("sender_id"),
                    message_text_raw=event.get("text"),
                    payload_json={
                        "kind": "inbound",
                        "variant": event.get("variant"),
                        "content_type": event.get("content_type"),
                        "metadata": event.get("metadata"),
                        "raw": event.get("raw"),
                    },
                    occurred_at=event.get("occurred_at"),
                )
            )
        else:
            normalized.append(
                NormalizedAuditEvent(
                    channel="telegram",
                    direction="system",
                    event_type="message_parsed",
                    provider_message_id=(str(event.get("message_id")) if event.get("message_id") is not None else None),
                    provider_update_id=(str(event.get("update_id")) if event.get("update_id") is not None else None),
                    payload_json={
                        "kind": "ignored",
                        "reason": event.get("reason", "unsupported_payload"),
                        "variant": event.get("variant"),
                        "content_type": event.get("content_type"),
                        "raw": event.get("raw"),
                    },
                    occurred_at=event.get("occurred_at"),
                )
            )
    return normalized
