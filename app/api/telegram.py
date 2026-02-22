#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.contracts import (
    ErrorResponse,
    TelegramWebhookPayload,
    WebhookStatusResponse,
)

from app.channels.core.handler import handle_inbound_message
from app.channels.telegram.adapter import parse_webhook_payload
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

    payload = TelegramWebhookPayload.model_validate(await request.json())
    inbound_messages = parse_webhook_payload(payload.model_dump(exclude_none=True))
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
