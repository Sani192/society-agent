#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Bot API client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.channels.telegram.constants import (
    DEFAULT_TELEGRAM_API_BASE_URL,
    TELEGRAM_REQUEST_TIMEOUT_SECONDS,
    TELEGRAM_SEND_MESSAGE_METHOD,
)
from app.config import settings
from app.utils.logger import logger


@dataclass(frozen=True)
class TelegramClient:
    bot_token: str
    api_base_url: str = DEFAULT_TELEGRAM_API_BASE_URL

    def send_text_message(self, chat_id: str, text: str) -> dict:
        url = f"{self.api_base_url}/bot{self.bot_token}/{TELEGRAM_SEND_MESSAGE_METHOD}"
        payload = {"chat_id": chat_id, "text": text}
        headers = {"Content-Type": "application/json"}

        logger.info("Sending Telegram message", extra={"chat_id": chat_id, "url": url})
        try:
            req = Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(req, timeout=TELEGRAM_REQUEST_TIMEOUT_SECONDS) as response:
                response_body = response.read().decode("utf-8")
                logger.info(
                    "Received Telegram API response",
                    extra={"status_code": response.status, "chat_id": chat_id},
                )
                return json.loads(response_body) if response_body else {}
        except (HTTPError, URLError, TimeoutError):
            logger.exception("Failed sending Telegram message", extra={"chat_id": chat_id})
            raise


def get_telegram_client() -> TelegramClient:
    logger.info("Preparing Telegram client")
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("Telegram bot token is not configured")
        raise ValueError("Telegram bot token is not configured")

    return TelegramClient(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        api_base_url=settings.TELEGRAM_API_BASE_URL,
    )
