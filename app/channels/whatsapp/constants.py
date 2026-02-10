#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized constants for WhatsApp channel integration."""

from __future__ import annotations

from dataclasses import dataclass

# Environment variable keys
WHATSAPP_VERIFY_TOKEN_ENV_KEY = "WHATSAPP_VERIFY_TOKEN"
WHATSAPP_APP_SECRET_ENV_KEY = "WHATSAPP_APP_SECRET"
WHATSAPP_ACCESS_TOKEN_ENV_KEY = "WHATSAPP_ACCESS_TOKEN"
WHATSAPP_PHONE_NUMBER_ID_ENV_KEY = "WHATSAPP_PHONE_NUMBER_ID"
WHATSAPP_API_VERSION_ENV_KEY = "WHATSAPP_API_VERSION"
WHATSAPP_GRAPH_BASE_URL_ENV_KEY = "WHATSAPP_GRAPH_BASE_URL"

# API defaults
DEFAULT_WHATSAPP_API_VERSION = "v22.0"
DEFAULT_WHATSAPP_GRAPH_BASE_URL = "https://graph.facebook.com"
WHATSAPP_REQUEST_TIMEOUT_SECONDS = 10

# API constants
WHATSAPP_MESSAGING_PRODUCT = "whatsapp"
WHATSAPP_MESSAGES_PATH = "messages"
WHATSAPP_MEDIA_PATH = "media"
WHATSAPP_SIGNATURE_HEADER = "X-Hub-Signature-256"
WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE = "subscribe"


@dataclass(frozen=True)
class WhatsAppEnvConfig:
    """Configuration metadata for a WhatsApp setting loaded from environment."""

    attr_name: str
    env_key: str
    default: str | None = None


WHATSAPP_ENV_CONFIGS: tuple[WhatsAppEnvConfig, ...] = (
    WhatsAppEnvConfig(
        attr_name="WHATSAPP_VERIFY_TOKEN",
        env_key=WHATSAPP_VERIFY_TOKEN_ENV_KEY,
    ),
    WhatsAppEnvConfig(
        attr_name="WHATSAPP_APP_SECRET",
        env_key=WHATSAPP_APP_SECRET_ENV_KEY,
    ),
    WhatsAppEnvConfig(
        attr_name="WHATSAPP_ACCESS_TOKEN",
        env_key=WHATSAPP_ACCESS_TOKEN_ENV_KEY,
    ),
    WhatsAppEnvConfig(
        attr_name="WHATSAPP_PHONE_NUMBER_ID",
        env_key=WHATSAPP_PHONE_NUMBER_ID_ENV_KEY,
    ),
    WhatsAppEnvConfig(
        attr_name="WHATSAPP_API_VERSION",
        env_key=WHATSAPP_API_VERSION_ENV_KEY,
        default=DEFAULT_WHATSAPP_API_VERSION,
    ),
    WhatsAppEnvConfig(
        attr_name="WHATSAPP_GRAPH_BASE_URL",
        env_key=WHATSAPP_GRAPH_BASE_URL_ENV_KEY,
        default=DEFAULT_WHATSAPP_GRAPH_BASE_URL,
    ),
)
