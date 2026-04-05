from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, cast
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.channels.core.audit_events import ChannelName, NormalizedAuditEvent, summarize_exception_stack
from app.channels.core.types import InboundMessage
from app.db.models import InboundWebhookEnvelope, WebhookIdempotencyKey
from app.db.session import SessionLocal
from app.utils.logger import logger


class SessionLike(Protocol):
    def add(self, instance: object) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def refresh(self, instance: object) -> None:
        ...

    def query(self, *entities: object):
        ...

    def close(self) -> None:
        ...


class WebhookRuntimeStrategy(Protocol):
    channel: ChannelName

    def get_message_id(self, message: InboundMessage) -> str | None:
        ...

    def get_update_id(self, message: InboundMessage) -> str | None:
        ...

    def get_chat_id_or_phone(self, message: InboundMessage) -> str | None:
        ...

    def get_external_user_id(self, message: InboundMessage) -> str | None:
        ...

    def get_idempotency_key(self, *, message_id: str | None, update_id: str | None) -> str | None:
        ...


@dataclass(frozen=True, slots=True)
class DefaultWebhookRuntimeStrategy:
    channel: ChannelName

    def get_message_id(self, message: InboundMessage) -> str | None:
        value = message.metadata.get("message_id")
        return str(value) if value is not None else None

    def get_update_id(self, message: InboundMessage) -> str | None:
        value = message.metadata.get("update_id")
        return str(value) if value is not None else None

    def get_chat_id_or_phone(self, message: InboundMessage) -> str | None:
        chat_id = message.metadata.get("chat_id")
        return str(chat_id) if chat_id is not None else str(message.sender_id)

    def get_external_user_id(self, message: InboundMessage) -> str | None:
        external = message.metadata.get("external_user_id")
        if external is not None:
            return str(external)
        return str(message.sender_id)

    def get_idempotency_key(self, *, message_id: str | None, update_id: str | None) -> str | None:
        if message_id:
            return f"message:{message_id}"
        if update_id:
            return f"update:{update_id}"
        return None


def hash_payload(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def persist_inbound_envelope(
    *,
    channel: str,
    payload_hash: str,
    payload: dict,
    session_factory: Any = SessionLocal,
) -> str:
    db = cast(SessionLike, session_factory())
    try:
        envelope = InboundWebhookEnvelope(
            channel=channel,
            payload_json=payload,
            payload_hash=payload_hash,
            status="queued",
        )
        db.add(envelope)
        db.commit()
        db.refresh(envelope)
        return str(envelope.id)
    except Exception:
        getattr(db, "rollback", lambda: None)()
        logger.warning("Failed to persist inbound envelope; continuing without persistence", extra={"channel": channel})
        return f"transient-{uuid4()}"
    finally:
        db.close()


def mark_envelope_status(
    *,
    envelope_id: str,
    status: str,
    session_factory: Any = SessionLocal,
) -> None:
    if envelope_id.startswith("transient-"):
        return
    processed_at = datetime.now(timezone.utc) if status in {"processed", "failed", "ignored"} else None
    db = cast(SessionLike, session_factory())
    try:
        db.query(InboundWebhookEnvelope).filter(InboundWebhookEnvelope.id == envelope_id).update(
            {
                InboundWebhookEnvelope.status: status,
                InboundWebhookEnvelope.processed_at: processed_at,
            },
            synchronize_session=False,
        )
        db.commit()
    except Exception:
        getattr(db, "rollback", lambda: None)()
    finally:
        db.close()


def claim_idempotency_key(
    *,
    strategy: WebhookRuntimeStrategy,
    message: InboundMessage,
    session_factory: Any = SessionLocal,
) -> bool:
    message_id = strategy.get_message_id(message)
    update_id = strategy.get_update_id(message)
    key = strategy.get_idempotency_key(message_id=message_id, update_id=update_id)
    if not key:
        return True

    db = cast(SessionLike, session_factory())
    try:
        db.add(
            WebhookIdempotencyKey(
                channel=strategy.channel,
                provider_message_id=message_id,
                provider_update_id=update_id,
                idempotency_key=key,
            )
        )
        db.commit()
        return True
    except IntegrityError:
        getattr(db, "rollback", lambda: None)()
        return False
    except Exception:
        getattr(db, "rollback", lambda: None)()
        logger.warning(
            "Idempotency store unavailable; proceeding without dedupe",
            extra={"channel": strategy.channel},
        )
        return True
    finally:
        db.close()


def build_processing_completed_event(
    *,
    strategy: WebhookRuntimeStrategy,
    trace_id: str,
    correlation_id: str | None,
    message: InboundMessage,
    status: str = "completed",
) -> NormalizedAuditEvent:
    return NormalizedAuditEvent(
        channel=strategy.channel,
        direction="system",
        event_type="processing_completed",
        provider_message_id=strategy.get_message_id(message),
        provider_update_id=strategy.get_update_id(message),
        chat_id_or_phone=strategy.get_chat_id_or_phone(message),
        external_user_id=strategy.get_external_user_id(message),
        payload_json={"trace_id": trace_id, "correlation_id": correlation_id, "status": status},
        occurred_at=datetime.now(timezone.utc),
    )


def build_exception_event(
    *,
    strategy: WebhookRuntimeStrategy,
    trace_id: str,
    correlation_id: str | None,
    message: InboundMessage,
    exc: Exception,
) -> NormalizedAuditEvent:
    return NormalizedAuditEvent(
        channel=strategy.channel,
        direction="system",
        event_type="exception",
        provider_message_id=strategy.get_message_id(message),
        provider_update_id=strategy.get_update_id(message),
        chat_id_or_phone=strategy.get_chat_id_or_phone(message),
        external_user_id=strategy.get_external_user_id(message),
        provider_error_code=type(exc).__name__,
        provider_error_message=str(exc),
        payload_json={
            "trace_id": trace_id,
            "correlation_id": correlation_id,
            "exception_class": type(exc).__name__,
            "exception_message": str(exc),
            "stack_summary": summarize_exception_stack(exc),
        },
        occurred_at=datetime.now(timezone.utc),
    )
