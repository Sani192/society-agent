#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Bot API client."""

from __future__ import annotations

from dataclasses import dataclass

import requests  # type: ignore[import-untyped]

from app.channels.telegram.constants import (
    DEFAULT_TELEGRAM_API_BASE_URL,
    TELEGRAM_REQUEST_TIMEOUT_SECONDS,
    TELEGRAM_SEND_MESSAGE_METHOD,
)
from app.config import settings
from app.utils.channel_audit_service import AuditTransport
from app.utils.channel_response_parser import parse_provider_error
from app.utils.logger import logger


@dataclass(frozen=True)
class TelegramClient:
    bot_token: str
    api_base_url: str = DEFAULT_TELEGRAM_API_BASE_URL
    audit_transport: AuditTransport | None = None

    def send_text_message(
        self,
        chat_id: str,
        text: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        url = f"{self.api_base_url}/bot{self.bot_token}/{TELEGRAM_SEND_MESSAGE_METHOD}"
        payload = {"chat_id": chat_id, "text": text}
        headers = {"Content-Type": "application/json"}
        audit = self.audit_transport or AuditTransport(channel="telegram")

        audit.log_send_attempt(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=str(chat_id),
            outbound_payload_metadata={"method": TELEGRAM_SEND_MESSAGE_METHOD, "text_length": len(text)},
        )

        logger.info("Sending Telegram message", extra={"chat_id": chat_id, "url": url})
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=TELEGRAM_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            response_payload = response.json() if response.content else {}
            parsed_error = parse_provider_error(
                channel="telegram",
                response_payload=response_payload,
                response_status_code=response.status_code,
            )
            provider_message_id = None
            if isinstance(response_payload.get("result"), dict):
                result = response_payload.get("result") or {}
                message_id = result.get("message_id")
                provider_message_id = str(message_id) if message_id is not None else None
            success = response_payload.get("ok") is not False
            audit.log_send_result(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=str(chat_id),
                status_code=response.status_code,
                provider_message_id=provider_message_id,
                response_payload_snapshot=response_payload,
                success=success,
                provider_error_code=parsed_error.get("provider_error_code"),
                provider_error_message=parsed_error.get("provider_error_message"),
            )
            logger.info(
                "Received Telegram API response",
                extra={"status_code": response.status_code, "chat_id": chat_id},
            )
            return response_payload
        except requests.RequestException as exc:
            audit.log_exception(
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=str(chat_id),
                exc=exc,
                outbound_payload_metadata=payload,
            )
            logger.exception("Failed sending Telegram message", extra={"chat_id": chat_id})
            raise


def get_telegram_client() -> TelegramClient:
    logger.info("Preparing Telegram client")
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    api_base_url = getattr(settings, "TELEGRAM_API_BASE_URL", DEFAULT_TELEGRAM_API_BASE_URL)
    if not bot_token:
        logger.error("Telegram bot token is not configured")
        raise ValueError("Telegram bot token is not configured")

    return TelegramClient(
        bot_token=bot_token,
        api_base_url=api_base_url,
        audit_transport=AuditTransport(channel="telegram"),
    )
