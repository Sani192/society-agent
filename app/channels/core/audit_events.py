#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalization and persistence helpers for channel webhook audit events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import traceback
from typing import Any, Literal, cast

from app.channels.core.audit_security import (
    dump_json,
    encrypt_for_audit_store,
    hash_event_record,
    redact_text,
    sanitize_payload,
)
from app.config import settings
from app.db.models import (
    ChannelMessageEvent,
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    MemberIdentity,
    UserFlatMapping,
)
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
    society_id: str | None = None
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
            society_id=self.society_id,
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
                previous_hash = cast(str | None, previous.event_hash) if previous else None
                previous_by_channel[event.channel] = previous_hash

            db_event = event.to_db_model()
            if db_event.society_id is None:
                db_event.society_id = _resolve_society_id_for_event(
                    db,
                    external_user_id=db_event.external_user_id,
                    chat_id_or_phone=db_event.chat_id_or_phone,
                )
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
            computed_event_hash = hash_event_record(prev_hash=prev_hash, payload=event_payload)
            setattr(db_event, "prev_event_hash", prev_hash)
            setattr(db_event, "event_hash", computed_event_hash)
            previous_by_channel[event.channel] = computed_event_hash
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


def _resolve_society_id_for_event(db, *, external_user_id: str | None, chat_id_or_phone: str | None):
    lookup_values = [value for value in {external_user_id, chat_id_or_phone} if value]
    if not lookup_values:
        return None

    committee_society = (
        db.query(CommitteeMember.society_id)
        .filter(CommitteeMember.phone_number.in_(lookup_values))
        .first()
    )
    if committee_society:
        return committee_society[0]

    committee_channel_society = (
        db.query(CommitteeMember.society_id)
        .join(CommitteeMemberChannelIdentity, CommitteeMemberChannelIdentity.committee_member_id == CommitteeMember.id)
        .filter(CommitteeMemberChannelIdentity.external_user_id.in_(lookup_values))
        .first()
    )
    if committee_channel_society:
        return committee_channel_society[0]

    member_identity = (
        db.query(UserFlatMapping.society_id)
        .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
        .filter(
            UserFlatMapping.is_active.is_(True),
            (
                MemberIdentity.normalized_identifier.in_(lookup_values)
                | MemberIdentity.normalized_phone.in_(lookup_values)
                | MemberIdentity.whatsapp_user_id.in_(lookup_values)
                | MemberIdentity.telegram_user_id.in_(lookup_values)
            ),
        )
        .first()
    )
    if member_identity:
        return member_identity[0]
    return None


def summarize_exception_stack(exc: Exception, *, max_frames: int = 8) -> list[str]:
    tb_exception = traceback.TracebackException.from_exception(exc)
    frames = list(tb_exception.stack)[-max_frames:]
    return [f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in frames]
