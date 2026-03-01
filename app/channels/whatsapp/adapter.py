#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Cloud API payload adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from app.channels.core.audit_events import NormalizedAuditEvent
from app.channels.core.types import InboundMessage
from app.utils.logger import logger


def _to_iso_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        epoch_seconds = int(value)
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _to_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _iter_changes(payload: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            yield entry, (change.get("value", {}) or {})


def parse_webhook_payload(payload: dict[str, Any]) -> list[InboundMessage]:
    logger.info("Parsing WhatsApp webhook payload")
    events = parse_webhook_events(payload)
    messages: list[InboundMessage] = []
    for event in events:
        if event["kind"] != "inbound":
            continue
        sender = event["sender_id"]
        text = event["text"]
        if not sender or not text:
            logger.info("Skipping malformed inbound message", extra={"message_id": event.get("message_id")})
            continue
        messages.append(
            InboundMessage(
                channel="whatsapp",
                sender_id=sender,
                display_name=event.get("display_name") or sender,
                text=text,
                metadata=event["metadata"],
            )
        )
    logger.info("Parsed inbound WhatsApp messages", extra={"count": len(messages)})
    return messages


def parse_webhook_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    logger.info("Parsing WhatsApp webhook events")
    parsed_events: list[dict[str, Any]] = []
    for entry, value in _iter_changes(payload):
        contacts_by_wa_id = {
            contact.get("wa_id"): contact for contact in (value.get("contacts") or []) if contact.get("wa_id")
        }

        for message in value.get("messages", []) or []:
            sender = message.get("from")
            profile_name = ((contacts_by_wa_id.get(sender) or {}).get("profile") or {}).get("name")
            text = (message.get("text") or {}).get("body")
            interactive_list_reply = ((message.get("interactive") or {}).get("list_reply") or {})
            interactive_button_reply = ((message.get("interactive") or {}).get("button_reply") or {})
            if not text:
                text = interactive_list_reply.get("id") or interactive_button_reply.get("id")

            parsed_events.append(
                {
                    "kind": "inbound" if (sender and text) else "ignored",
                    "reason": None if (sender and text) else "unsupported_message_payload",
                    "entry_id": entry.get("id"),
                    "sender_id": sender,
                    "display_name": profile_name,
                    "text": text,
                    "message_id": message.get("id"),
                    "timestamp": message.get("timestamp"),
                    "occurred_at": _to_datetime(message.get("timestamp")),
                    "metadata": {
                        "message_id": message.get("id"),
                        "canonical_sender_id": sender,
                        "phone_number": sender,
                        "interactive_list_reply_id": interactive_list_reply.get("id"),
                        "interactive_list_reply_title": interactive_list_reply.get("title"),
                        "interactive_button_reply_id": interactive_button_reply.get("id"),
                        "interactive_button_reply_title": interactive_button_reply.get("title"),
                        "timestamp": message.get("timestamp"),
                        "timestamp_iso": _to_iso_timestamp(message.get("timestamp")),
                    },
                    "raw": message,
                }
            )

        for status in value.get("statuses", []) or []:
            parsed_events.append(
                {
                    "kind": "status",
                    "status": status.get("status"),
                    "message_id": status.get("id"),
                    "recipient_id": status.get("recipient_id"),
                    "conversation": status.get("conversation"),
                    "pricing": status.get("pricing"),
                    "timestamp": status.get("timestamp"),
                    "errors": status.get("errors") or [],
                    "occurred_at": _to_datetime(status.get("timestamp")),
                    "raw": status,
                }
            )

        has_known_content = bool((value.get("messages") or []) or (value.get("statuses") or []))
        if not has_known_content:
            parsed_events.append(
                {
                    "kind": "ignored",
                    "reason": "unsupported_change_payload",
                    "entry_id": entry.get("id"),
                    "raw": value,
                    "occurred_at": datetime.now(timezone.utc),
                }
            )

    return parsed_events


def to_normalized_audit_events(events: list[dict[str, Any]]) -> list[NormalizedAuditEvent]:
    normalized: list[NormalizedAuditEvent] = []
    for event in events:
        kind = event.get("kind")
        if kind == "inbound":
            normalized.append(
                NormalizedAuditEvent(
                    channel="whatsapp",
                    direction="inbound",
                    event_type="message_parsed",
                    provider_message_id=event.get("message_id"),
                    chat_id_or_phone=event.get("sender_id"),
                    external_user_id=event.get("sender_id"),
                    message_text_raw=event.get("text"),
                    payload_json={
                        "kind": "inbound",
                        "entry_id": event.get("entry_id"),
                        "metadata": event.get("metadata"),
                        "raw": event.get("raw"),
                    },
                    occurred_at=event.get("occurred_at"),
                )
            )
        elif kind == "status":
            errors = event.get("errors") or []
            primary_error = errors[0] if errors else {}
            normalized.append(
                NormalizedAuditEvent(
                    channel="whatsapp",
                    direction="status",
                    event_type="delivery_status",
                    provider_message_id=event.get("message_id"),
                    chat_id_or_phone=event.get("recipient_id"),
                    external_user_id=event.get("recipient_id"),
                    payload_json={
                        "kind": "status",
                        "status": event.get("status"),
                        "conversation": event.get("conversation"),
                        "pricing": event.get("pricing"),
                        "errors": errors,
                        "raw": event.get("raw"),
                    },
                    provider_error_code=(str(primary_error.get("code")) if primary_error.get("code") is not None else None),
                    provider_error_message=primary_error.get("title") or primary_error.get("message"),
                    occurred_at=event.get("occurred_at"),
                )
            )
        else:
            normalized.append(
                NormalizedAuditEvent(
                    channel="whatsapp",
                    direction="system",
                    event_type="message_parsed",
                    payload_json={
                        "kind": "ignored",
                        "reason": event.get("reason", "unsupported_payload"),
                        "entry_id": event.get("entry_id"),
                        "raw": event.get("raw"),
                    },
                    occurred_at=event.get("occurred_at"),
                )
            )
    return normalized
