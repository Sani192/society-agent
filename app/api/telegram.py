#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import cast
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from app.api.contracts import (
    ErrorResponse,
    TelegramWebhookPayload,
    WebhookStatusResponse,
)

from app.channels.core.handler import handle_inbound_message
from app.channels.core.audit_events import (
    NormalizedAuditEvent,
    persist_audit_events,
    summarize_exception_stack,
)
from app.channels.telegram.adapter import (
    parse_webhook_events,
    parse_webhook_payload,
    to_normalized_audit_events,
)
from app.channels.telegram.client import get_telegram_client
from app.config import settings
from app.db.models import InboundWebhookEnvelope, WebhookIdempotencyKey
from app.db.session import SessionLocal
from app.utils.logger import logger

router = APIRouter()


def _verify_webhook_secret(secret: str | None) -> None:
    expected_secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
    if not expected_secret:
        return
    if secret != expected_secret:
        logger.warning("Telegram webhook secret validation failed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


def _ensure_channel_enabled() -> None:
    if not settings.TELEGRAM_ENABLED:
        logger.info("Telegram channel is disabled")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram channel is disabled",
        )


def _hash_payload(raw_body: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw_body).hexdigest()


def _persist_inbound_envelope(*, payload_hash: str, payload: dict) -> str:
    db = SessionLocal()
    try:
        envelope = InboundWebhookEnvelope(
            channel="telegram",
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
        logger.warning("Failed to persist Telegram envelope; continuing without envelope persistence")
        return f"transient-{uuid4()}"
    finally:
        db.close()


def _claim_idempotency_key(*, channel: str, message_id: str | None, update_id: str | None) -> bool:
    if update_id:
        key = f"update:{update_id}"
    elif message_id:
        key = f"message:{message_id}"
    else:
        return True

    db = SessionLocal()
    try:
        db.add(
            WebhookIdempotencyKey(
                channel=channel,
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
        logger.warning("Idempotency store unavailable; proceeding without dedupe", extra={"channel": channel})
        return True
    finally:
        db.close()


def _mark_envelope_status(*, envelope_id: str, status: str) -> None:
    db = SessionLocal()
    try:
        db.query(InboundWebhookEnvelope).filter(InboundWebhookEnvelope.id == envelope_id).update(
            {
                InboundWebhookEnvelope.status: status,
                InboundWebhookEnvelope.processed_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        db.commit()
    except Exception:
        getattr(db, "rollback", lambda: None)()
    finally:
        db.close()


def _build_processing_completed_event(*, trace_id: str, correlation_id: str | None, message, status: str = "completed") -> NormalizedAuditEvent:
    return NormalizedAuditEvent(
        channel="telegram",
        direction="system",
        event_type="processing_completed",
        provider_message_id=(str(message.metadata.get("message_id")) if message.metadata.get("message_id") is not None else None),
        provider_update_id=(str(message.metadata.get("update_id")) if message.metadata.get("update_id") is not None else None),
        chat_id_or_phone=str(message.metadata.get("chat_id") or message.sender_id),
        external_user_id=str(message.sender_id),
        payload_json={"trace_id": trace_id, "correlation_id": correlation_id, "status": status},
        occurred_at=datetime.now(timezone.utc),
    )


def _build_exception_event(*, trace_id: str, correlation_id: str | None, message, exc: Exception) -> NormalizedAuditEvent:
    return NormalizedAuditEvent(
        channel="telegram",
        direction="system",
        event_type="exception",
        provider_message_id=(str(message.metadata.get("message_id")) if message.metadata.get("message_id") is not None else None),
        provider_update_id=(str(message.metadata.get("update_id")) if message.metadata.get("update_id") is not None else None),
        chat_id_or_phone=str(message.metadata.get("chat_id") or message.sender_id),
        external_user_id=str(message.sender_id),
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


def _build_webhook_received_event(*, payload_hash: str, payload: dict) -> NormalizedAuditEvent:
    selected_fields = {
        "update_id": payload.get("update_id"),
        "has_message": isinstance(payload.get("message"), dict),
        "has_edited_message": isinstance(payload.get("edited_message"), dict),
        "has_callback_query": isinstance(payload.get("callback_query"), dict),
    }
    return NormalizedAuditEvent(
        channel="telegram",
        direction="system",
        event_type="webhook_received",
        provider_update_id=(str(payload.get("update_id")) if payload.get("update_id") is not None else None),
        payload_json={"payload_hash": payload_hash, "selected": selected_fields},
        occurred_at=datetime.now(timezone.utc),
    )


def process_telegram_envelope(*, envelope_id: str, payload_dict: dict, enforce_idempotency: bool = True) -> None:
    inbound_messages = parse_webhook_payload(payload_dict)
    if not inbound_messages:
        logger.info("Telegram webhook received with no inbound messages")
        _mark_envelope_status(envelope_id=envelope_id, status="ignored")
        return

    client = get_telegram_client()
    for message in inbound_messages:
        trace_id = str(uuid4())
        correlation_id = message.metadata.get("update_id") or message.metadata.get("message_id")
        correlation_id_str = str(correlation_id) if correlation_id is not None else None
        terminal_event: NormalizedAuditEvent | None = None
        message.metadata["trace_id"] = trace_id
        if correlation_id is not None:
            message.metadata["correlation_id"] = correlation_id_str
        if enforce_idempotency and not _claim_idempotency_key(
            channel="telegram",
            message_id=(str(message.metadata.get("message_id")) if message.metadata.get("message_id") is not None else None),
            update_id=(str(message.metadata.get("update_id")) if message.metadata.get("update_id") is not None else None),
        ):
            logger.info("Skipping duplicate Telegram webhook message", extra={"correlation_id": correlation_id_str})
            persist_audit_events([
                _build_processing_completed_event(
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                    message=message,
                    status="duplicate_skipped",
                )
            ])
            continue
        try:
            try:
                reply_text = handle_inbound_message(
                    message,
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                )
            except TypeError:
                reply_text = handle_inbound_message(message)

            reply_chat_id = message.metadata.get("chat_id") or message.sender_id
            try:
                client.send_text_message(
                    reply_chat_id,
                    reply_text,
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                )
            except TypeError:
                client.send_text_message(reply_chat_id, reply_text)

            terminal_event = _build_processing_completed_event(
                trace_id=trace_id,
                correlation_id=correlation_id_str,
                message=message,
            )
        except Exception as exc:
            logger.exception("Telegram message processing failed")
            terminal_event = _build_exception_event(
                trace_id=trace_id,
                correlation_id=correlation_id_str,
                message=message,
                exc=exc,
            )
        finally:
            if terminal_event is None:
                terminal_event = _build_processing_completed_event(
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                    message=message,
                    status="unknown",
                )
            persist_audit_events([terminal_event])

    _mark_envelope_status(envelope_id=envelope_id, status="processed")


@router.post(
    "/telegram",
    response_model=WebhookStatusResponse,
    responses={403: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["update_id"],
                        "properties": {
                            "update_id": {"type": "integer"},
                        },
                        "additionalProperties": True,
                    }
                }
            },
        }
    },
)
async def telegram_webhook_event(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    background_tasks: BackgroundTasks = cast(BackgroundTasks, None),
) -> dict[str, str]:
    _ensure_channel_enabled()
    logger.info("Received Telegram webhook event")
    _verify_webhook_secret(x_telegram_bot_api_secret_token)

    payload_data = await request.json()
    if hasattr(request, "body"):
        raw_body = await request.body()
        if not raw_body:
            raw_body = json.dumps(payload_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    else:
        raw_body = json.dumps(payload_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload = TelegramWebhookPayload.model_validate(payload_data)
    payload_dict = payload.model_dump(exclude_none=True)

    parsed_events = parse_webhook_events(payload_dict)
    normalized_events = [_build_webhook_received_event(payload_hash=_hash_payload(raw_body), payload=payload_dict)]
    normalized_events.extend(to_normalized_audit_events(parsed_events))
    persist_audit_events(normalized_events)

    if not parse_webhook_payload(payload_dict):
        logger.info("Telegram webhook received with no inbound messages")
        return {"status": "ignored"}

    envelope_id = _persist_inbound_envelope(payload_hash=_hash_payload(raw_body), payload=payload_dict)
    if background_tasks is not None:
        background_tasks.add_task(process_telegram_envelope, envelope_id=envelope_id, payload_dict=payload_dict, enforce_idempotency=True)
    else:
        process_telegram_envelope(envelope_id=envelope_id, payload_dict=payload_dict, enforce_idempotency=False)

    logger.info("Telegram webhook accepted for asynchronous processing")
    return {"status": "ok"}
