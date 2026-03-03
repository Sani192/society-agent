#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalization and persistence helpers for channel webhook audit events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import traceback
from typing import Any, Literal

from app.db.models import ChannelMessageEvent
from app.db.session import SessionLocal
from app.utils.logger import logger

ChannelName = Literal["whatsapp", "telegram"]
Direction = Literal["inbound", "status", "system"]
EventKind = Literal[
    "webhook_received",
    "message_parsed",
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
        return ChannelMessageEvent(
            channel=self.channel,
            direction=self.direction,
            event_type=self.event_type,
            provider_message_id=self.provider_message_id,
            provider_update_id=self.provider_update_id,
            chat_id_or_phone=self.chat_id_or_phone,
            external_user_id=self.external_user_id,
            message_text_raw=self.message_text_raw,
            message_text_redacted=self.message_text_raw,
            payload_json=self.payload_json,
            provider_error_code=self.provider_error_code,
            provider_error_message=self.provider_error_message,
            occurred_at=self.occurred_at or datetime.now(timezone.utc),
        )


def persist_audit_events(events: list[NormalizedAuditEvent]) -> int:
    if not events:
        return 0

    db = SessionLocal()
    try:
        db.add_all(event.to_db_model() for event in events)
        db.commit()
        logger.info("Persisted channel audit events", extra={"count": len(events)})
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
