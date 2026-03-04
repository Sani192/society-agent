#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:26:10 2026

@author: anonymous
"""

# app/config.py

import json
import os
from dotenv import load_dotenv

from app.channels.telegram.constants import TELEGRAM_ENV_CONFIGS
from app.channels.whatsapp.constants import WHATSAPP_ENV_CONFIGS

load_dotenv()


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_json_dict(name: str, default: dict[str, int]) -> dict[str, int]:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return default
    if not isinstance(parsed, dict):
        return default
    normalized: dict[str, int] = {}
    for key, value in parsed.items():
        try:
            normalized[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return normalized or default


def _env_choice(name: str, default: str, *, choices: set[str]) -> str:
    candidate = os.getenv(name, default).strip().lower()
    if candidate in choices:
        return candidate
    return default

class Settings:
    APP_ENV = os.getenv("APP_ENV", "local")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    CURRENCY = os.getenv("CURRENCY_SYMBOL", "₹")

    DEFAULT_SOCIETY_NAME = os.getenv("DEFAULT_SOCIETY_NAME")
    WHATSAPP_ENABLED = _env_flag("WHATSAPP_ENABLED", "true")
    TELEGRAM_ENABLED = _env_flag("TELEGRAM_ENABLED", "true")

    AUDIT_RETENTION_DAYS_BY_EVENT = _env_json_dict(
        "AUDIT_RETENTION_DAYS_BY_EVENT",
        default={
            "webhook_received": 30,
            "message_parsed": 30,
            "reply_generated": 30,
            "send_attempt": 90,
            "send_result": 90,
            "delivery_status": 90,
            "processing_completed": 30,
            "exception": 365,
        },
    )
    AUDIT_PII_CAPTURE_MODE = _env_choice(
        "AUDIT_PII_CAPTURE_MODE",
        "redacted",
        choices={"none", "redacted", "encrypted_raw"},
    )
    AUDIT_ENCRYPTION_KEY = os.getenv("AUDIT_ENCRYPTION_KEY")
    AUDIT_KMS_KEY_ID = os.getenv("AUDIT_KMS_KEY_ID")
    AUDIT_READ_ROLES = {
        role.strip().lower()
        for role in os.getenv("AUDIT_READ_ROLES", "chairman,governance,admin").split(",")
        if role.strip()
    }

    # Declared explicitly for static type-checkers; values are populated from env.
    WHATSAPP_VERIFY_TOKEN: str | None
    WHATSAPP_APP_SECRET: str | None
    WHATSAPP_ACCESS_TOKEN: str | None
    WHATSAPP_PHONE_NUMBER_ID: str | None
    WHATSAPP_API_VERSION: str
    WHATSAPP_GRAPH_BASE_URL: str

    ADMIN_PHONE_WHITELIST = [
        phone.strip()
        for phone in os.getenv("ADMIN_PHONE_WHITELIST", "").split(",")
        if phone.strip()
    ]

    _WHATSAPP_SETTINGS = {
        config.attr_name: os.getenv(config.env_key, config.default)
        for config in WHATSAPP_ENV_CONFIGS
    }
    locals().update(_WHATSAPP_SETTINGS)
    del _WHATSAPP_SETTINGS

    _TELEGRAM_SETTINGS = {
        config.attr_name: os.getenv(config.env_key, config.default)
        for config in TELEGRAM_ENV_CONFIGS
    }
    locals().update(_TELEGRAM_SETTINGS)
    del _TELEGRAM_SETTINGS



settings = Settings()
