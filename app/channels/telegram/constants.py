#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized constants for Telegram channel integration."""

from __future__ import annotations

from dataclasses import dataclass

# Environment variable keys
TELEGRAM_BOT_TOKEN_ENV_KEY = "TELEGRAM_BOT_TOKEN"
TELEGRAM_API_BASE_URL_ENV_KEY = "TELEGRAM_API_BASE_URL"
TELEGRAM_WEBHOOK_SECRET_ENV_KEY = "TELEGRAM_WEBHOOK_SECRET"

# API defaults
DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
TELEGRAM_REQUEST_TIMEOUT_SECONDS = 10

# API constants
TELEGRAM_SEND_MESSAGE_METHOD = "sendMessage"


@dataclass(frozen=True)
class TelegramEnvConfig:
    """Configuration metadata for a Telegram setting loaded from environment."""

    attr_name: str
    env_key: str
    default: str | None = None


TELEGRAM_ENV_CONFIGS: tuple[TelegramEnvConfig, ...] = (
    TelegramEnvConfig(
        attr_name="TELEGRAM_BOT_TOKEN",
        env_key=TELEGRAM_BOT_TOKEN_ENV_KEY,
    ),
    TelegramEnvConfig(
        attr_name="TELEGRAM_API_BASE_URL",
        env_key=TELEGRAM_API_BASE_URL_ENV_KEY,
        default=DEFAULT_TELEGRAM_API_BASE_URL,
    ),
    TelegramEnvConfig(
        attr_name="TELEGRAM_WEBHOOK_SECRET",
        env_key=TELEGRAM_WEBHOOK_SECRET_ENV_KEY,
    ),
)
