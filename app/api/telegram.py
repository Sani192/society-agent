#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import heapq
from typing import cast
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
import requests  # type: ignore[import-untyped]

from app.api.contracts import (
    ErrorResponse,
    TelegramWebhookPayload,
    WebhookStatusResponse,
)

from app.channels.core.handler import handle_inbound_message
from app.channels.core.audit_events import (
    NormalizedAuditEvent,
    persist_audit_events,
)
from app.channels.core.types import InboundMessage
from app.channels.core.webhook_runtime import (
    WebhookRuntimeStrategy,
    build_exception_event,
    build_processing_completed_event,
    claim_idempotency_key,
    hash_payload,
    mark_envelope_status,
    persist_inbound_envelope,
)
from app.channels.telegram.adapter import (
    parse_webhook_events,
    parse_webhook_payload,
    to_normalized_audit_events,
)
from app.channels.telegram.client import get_telegram_client
from app.config import settings
from app.db.session import SessionLocal
from app.utils.channel_audit_service import AuditTransport
from app.utils.logger import logger
from app.utils.operational_metrics import increment_counter

router = APIRouter()

MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_SECONDS = 2
MAX_RETRY_BACKOFF_SECONDS = 60
_RETRY_QUEUE: list[tuple[float, str, dict, int]] = []


class _TelegramRuntimeStrategy(WebhookRuntimeStrategy):
    channel = "telegram"

    def get_message_id(self, message: InboundMessage) -> str | None:
        value = message.metadata.get("message_id")
        return str(value) if value is not None else None

    def get_update_id(self, message: InboundMessage) -> str | None:
        value = message.metadata.get("update_id")
        return str(value) if value is not None else None

    def get_chat_id_or_phone(self, message: InboundMessage) -> str | None:
        chat_id = message.metadata.get("chat_id")
        if chat_id is not None:
            return str(chat_id)
        return str(message.sender_id)

    def get_external_user_id(self, message: InboundMessage) -> str | None:
        return str(message.sender_id)

    def get_idempotency_key(self, *, message_id: str | None, update_id: str | None) -> str | None:
        if update_id:
            return f"update:{update_id}"
        if message_id:
            return f"message:{message_id}"
        return None


_RUNTIME_STRATEGY = _TelegramRuntimeStrategy()


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
    return hash_payload(raw_body)


def _persist_inbound_envelope(*, payload_hash: str, payload: dict) -> str:
    return persist_inbound_envelope(
        channel="telegram",
        payload_hash=payload_hash,
        payload=payload,
        session_factory=SessionLocal,
    )


def _claim_idempotency_key(*, channel: str, message_id: str | None, update_id: str | None) -> bool:
    message = InboundMessage(
        channel=channel,
        sender_id="system",
        display_name="system",
        text="",
        metadata={"message_id": message_id, "update_id": update_id},
    )
    return claim_idempotency_key(
        strategy=_RUNTIME_STRATEGY,
        message=message,
        session_factory=SessionLocal,
    )


def _mark_envelope_status(*, envelope_id: str, status: str) -> None:
    mark_envelope_status(envelope_id=envelope_id, status=status, session_factory=SessionLocal)


def _build_processing_completed_event(*, trace_id: str, correlation_id: str | None, message, status: str = "completed") -> NormalizedAuditEvent:
    return build_processing_completed_event(
        strategy=_RUNTIME_STRATEGY,
        trace_id=trace_id,
        correlation_id=correlation_id,
        message=message,
        status=status,
    )


def _build_exception_event(*, trace_id: str, correlation_id: str | None, message, exc: Exception) -> NormalizedAuditEvent:
    return build_exception_event(
        strategy=_RUNTIME_STRATEGY,
        trace_id=trace_id,
        correlation_id=correlation_id,
        message=message,
        exc=exc,
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


def _is_recoverable_exception(exc: Exception) -> bool:
    return isinstance(exc, (requests.RequestException, TimeoutError, ConnectionError))


def _push_dead_letter(*, trace_id: str, correlation_id: str | None, message, payload_dict: dict, exc: Exception) -> None:
    AuditTransport(channel="telegram").persist_dead_letter(
        trace_id=trace_id,
        correlation_id=correlation_id,
        recipient=str(message.metadata.get("chat_id") or message.sender_id),
        outbound_payload_metadata={
            "envelope_payload": payload_dict,
            "message_metadata": dict(message.metadata),
            "sender_id": message.sender_id,
        },
        exc=exc,
    )


def _schedule_retry(*, envelope_id: str, payload_dict: dict, attempt: int) -> None:
    backoff_seconds = min(RETRY_BASE_SECONDS * (2 ** max(attempt - 1, 0)), MAX_RETRY_BACKOFF_SECONDS)
    run_after = datetime.now(timezone.utc).timestamp() + float(backoff_seconds)
    heapq.heappush(_RETRY_QUEUE, (run_after, envelope_id, payload_dict, attempt))
    increment_counter("telegram.webhook.retries_scheduled")


def process_telegram_retry_queue() -> int:
    processed = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    while _RETRY_QUEUE and _RETRY_QUEUE[0][0] <= now_ts:
        _, envelope_id, payload_dict, attempt = heapq.heappop(_RETRY_QUEUE)
        process_telegram_envelope(
            envelope_id=envelope_id,
            payload_dict=payload_dict,
            enforce_idempotency=False,
            retry_attempt=attempt,
        )
        processed += 1
    return processed


def process_telegram_envelope(*, envelope_id: str, payload_dict: dict, enforce_idempotency: bool = True, retry_attempt: int = 0) -> None:
    _mark_envelope_status(envelope_id=envelope_id, status="processing")
    inbound_messages = parse_webhook_payload(payload_dict)
    if not inbound_messages:
        logger.info("Telegram webhook received with no inbound messages")
        _mark_envelope_status(envelope_id=envelope_id, status="ignored")
        return

    client = get_telegram_client()
    had_nonrecoverable_failure = False
    had_recoverable_failure = False
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
            reply_text = handle_inbound_message(
                message,
                trace_id=trace_id,
                correlation_id=correlation_id_str,
            )

            reply_chat_id = message.metadata.get("chat_id") or message.sender_id
            client.send_text_message(
                chat_id=str(reply_chat_id),
                text=reply_text,
                trace_id=trace_id,
                correlation_id=correlation_id_str,
            )

            terminal_event = _build_processing_completed_event(
                trace_id=trace_id,
                correlation_id=correlation_id_str,
                message=message,
            )
        except Exception as exc:
            logger.exception("Telegram message processing failed")
            recoverable = _is_recoverable_exception(exc)
            if recoverable and retry_attempt < MAX_RETRY_ATTEMPTS:
                had_recoverable_failure = True
                _schedule_retry(
                    envelope_id=envelope_id,
                    payload_dict=payload_dict,
                    attempt=retry_attempt + 1,
                )
            else:
                had_nonrecoverable_failure = True
                increment_counter("telegram.webhook.failed_processing")
                _push_dead_letter(
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                    message=message,
                    payload_dict=payload_dict,
                    exc=exc,
                )
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

    if had_nonrecoverable_failure:
        _mark_envelope_status(envelope_id=envelope_id, status="failed")
    elif had_recoverable_failure:
        _mark_envelope_status(envelope_id=envelope_id, status="queued")
    else:
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
    request_headers = getattr(request, "headers", {}) or {}
    content_length = request_headers.get("content-length")
    max_body_bytes = max(
        1024,
        min(int(settings.TELEGRAM_WEBHOOK_MAX_BODY_BYTES), int(settings.PUBLIC_ENDPOINT_MAX_BODY_BYTES)),
    )
    if content_length and content_length.isdigit() and int(content_length) > max_body_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")

    payload_data = await request.json()
    if hasattr(request, "body"):
        raw_body = await request.body()
        if not raw_body:
            raw_body = json.dumps(payload_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    else:
        raw_body = json.dumps(payload_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(raw_body) > max_body_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")
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
