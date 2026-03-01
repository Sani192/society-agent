#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.contracts import (
    ErrorResponse,
    TelegramWebhookPayload,
    WebhookStatusResponse,
)

from app.channels.core.handler import handle_inbound_message
from app.channels.core.audit_events import NormalizedAuditEvent, persist_audit_events
from app.channels.telegram.adapter import (
    parse_webhook_events,
    parse_webhook_payload,
    to_normalized_audit_events,
)
from app.channels.telegram.client import get_telegram_client
from app.config import settings
from app.utils.logger import logger

router = APIRouter()


def _verify_webhook_secret(secret: str | None) -> None:
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
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
) -> WebhookStatusResponse:
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

    inbound_messages = parse_webhook_payload(payload_dict)
    if not inbound_messages:
        logger.info("Telegram webhook received with no inbound messages")
        return {"status": "ignored"}

    client = get_telegram_client()
    for message in inbound_messages:
        logger.info(
            "Processing inbound Telegram message",
            extra={
                "sender_id": message.sender_id,
                "chat_id": message.metadata.get("chat_id"),
                "message_id": message.metadata.get("message_id"),
            },
        )
        reply_text = handle_inbound_message(message)
        reply_chat_id = message.metadata.get("chat_id") or message.sender_id
        client.send_text_message(reply_chat_id, reply_text)

    logger.info("Telegram webhook processing completed")
    return {"status": "ok"}
