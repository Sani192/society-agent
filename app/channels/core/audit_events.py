#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalization and persistence helpers for channel webhook audit events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import traceback
from typing import Any, Literal

from app.channels.core.audit_security import (
    dump_json,
    encrypt_for_audit_store,
    hash_event_record,
    redact_text,
    sanitize_payload,
)
from app.config import settings
from app.db.models import ChannelMessageEvent
from app.db.session import SessionLocal
from app.utils.logger import logger

ChannelName = Literal["whatsapp", "telegram"]
Direction = Literal["inbound", "outbound", "status", "system"]
EventKind = Literal[
    "webhook_received",
    "message_parsed",
    "reply_generated",
    "send_attempt",
    "send_result",
    "delivery_status",
    "processing_completed",
    "exception",
]


@dataclass(slots=True)
class NormalizedAuditEvent:
    channel: ChannelName
    direction: Direction
    event_type: EventKind
    provider_message_id: str | None = None
    provider_update_id: str | None = None
    chat_id_or_phone: str | None = None
    external_user_id: str | None = None
    message_text_raw: str | None = None
    payload_json: dict[str, Any] | None = None
    provider_error_code: str | None = None
    provider_error_message: str | None = None
    occurred_at: datetime | None = None

    def to_db_model(self) -> ChannelMessageEvent:
        pii_mode = settings.AUDIT_PII_CAPTURE_MODE

        sanitized_payload = sanitize_payload(self.payload_json)
        redacted_text = redact_text(self.message_text_raw)

        encrypted_text = None
        encrypted_payload = None
        if pii_mode == "encrypted_raw":
            encrypted_text = encrypt_for_audit_store(self.message_text_raw)
            encrypted_payload = encrypt_for_audit_store(dump_json(self.payload_json))

        if pii_mode == "none":
            stored_text = None
            stored_payload = None
        else:
            stored_text = redacted_text
            stored_payload = sanitized_payload

        return ChannelMessageEvent(
            channel=self.channel,
            direction=self.direction,
            event_type=self.event_type,
            provider_message_id=self.provider_message_id,
            provider_update_id=self.provider_update_id,
            chat_id_or_phone=self.chat_id_or_phone,
            external_user_id=self.external_user_id,
            message_text_raw=stored_text,
            message_text_raw_encrypted=encrypted_text,
            message_text_redacted=redacted_text,
            payload_json=stored_payload,
            payload_json_encrypted=encrypted_payload,
            provider_error_code=self.provider_error_code,
            provider_error_message=redact_text(self.provider_error_message),
            occurred_at=self.occurred_at or datetime.now(timezone.utc),
        )


def persist_audit_events(events: list[NormalizedAuditEvent]) -> int:
    if not events:
        return 0

    db = SessionLocal()
    try:
        previous_by_channel: dict[str, str | None] = {}
        for event in events:
            if event.channel not in previous_by_channel:
                previous = (
                    db.query(ChannelMessageEvent)
                    .filter(ChannelMessageEvent.channel == event.channel)
                    .order_by(ChannelMessageEvent.created_at.desc())
                    .first()
                )
                previous_by_channel[event.channel] = previous.event_hash if previous else None

            db_event = event.to_db_model()
            prev_hash = previous_by_channel[event.channel]
            event_payload = {
                "channel": db_event.channel,
                "direction": db_event.direction,
                "event_type": db_event.event_type,
                "provider_message_id": db_event.provider_message_id,
                "provider_update_id": db_event.provider_update_id,
                "chat_id_or_phone": db_event.chat_id_or_phone,
                "external_user_id": db_event.external_user_id,
                "message_text_redacted": db_event.message_text_redacted,
                "payload_json": db_event.payload_json,
                "provider_error_code": db_event.provider_error_code,
                "provider_error_message": db_event.provider_error_message,
                "occurred_at": db_event.occurred_at.isoformat() if db_event.occurred_at else None,
            }
            db_event.prev_event_hash = prev_hash
            db_event.event_hash = hash_event_record(prev_hash=prev_hash, payload=event_payload)
            previous_by_channel[event.channel] = db_event.event_hash
            db.add(db_event)

        db.commit()
        logger.info("Persisted channel audit events", extra={"count": len(events), "pii_mode": settings.AUDIT_PII_CAPTURE_MODE})
        return len(events)
    except Exception:
        db.rollback()
        logger.exception("Failed to persist channel audit events", extra={"count": len(events)})
        return 0
    finally:
        db.close()


def summarize_exception_stack(exc: Exception, *, max_frames: int = 8) -> list[str]:
    tb_exception = traceback.TracebackException.from_exception(exc)
    frames = list(tb_exception.stack)[-max_frames:]
    return [f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in frames]
