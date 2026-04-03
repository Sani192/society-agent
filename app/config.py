#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:26:10 2026

@author: anonymous
"""

# app/config.py

import json
import os
from typing import Final
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


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _db_defaults_for_env(app_env: str) -> dict[str, int]:
    normalized = app_env.strip().lower()
    if normalized in {"production", "staging"}:
        return {
            "pool_size": 20,
            "max_overflow": 30,
            "pool_timeout": 30,
            "pool_recycle": 1800,
            "statement_timeout_ms": 30000,
        }
    if normalized in {"dev", "local"}:
        return {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 900,
            "statement_timeout_ms": 15000,
        }
    return {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1200,
        "statement_timeout_ms": 20000,
    }

class Settings:
    APP_ENV = os.getenv("APP_ENV", "local")
    APP_ENV_NORMALIZED: Final[str] = APP_ENV.strip().lower()
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

    REPORTS_API_AUTH_SECRET = os.getenv("REPORTS_API_AUTH_SECRET")

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

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ANNOUNCEMENT_QUEUE_DEFAULT = os.getenv("ANNOUNCEMENT_QUEUE_DEFAULT", "announcement-default")
    ANNOUNCEMENT_QUEUE_WHATSAPP = os.getenv("ANNOUNCEMENT_QUEUE_WHATSAPP", "announcement-whatsapp")
    ANNOUNCEMENT_JOB_TIMEOUT_SECONDS = _env_int("ANNOUNCEMENT_JOB_TIMEOUT_SECONDS", 120)
    ANNOUNCEMENT_RETRY_MAX = _env_int("ANNOUNCEMENT_RETRY_MAX", 3)
    ANNOUNCEMENT_RETRY_BASE_SECONDS = _env_int("ANNOUNCEMENT_RETRY_BASE_SECONDS", 2)
    ANNOUNCEMENT_WORKER_CONCURRENCY_WHATSAPP = _env_int("ANNOUNCEMENT_WORKER_CONCURRENCY_WHATSAPP", 2)
    ANNOUNCEMENT_WORKER_CONCURRENCY_DEFAULT = _env_int("ANNOUNCEMENT_WORKER_CONCURRENCY_DEFAULT", 1)
    ANNOUNCEMENT_DISPATCH_BACKEND = _env_choice("ANNOUNCEMENT_DISPATCH_BACKEND", "local", choices={"local", "rq"})

    _DB_DEFAULTS = _db_defaults_for_env(APP_ENV)
    DATABASE_URL = os.getenv("DATABASE_URL")
    READ_REPLICA_DATABASE_URL = os.getenv("READ_REPLICA_DATABASE_URL")
    DB_POOL_SIZE: int = _env_int("DB_POOL_SIZE", _DB_DEFAULTS["pool_size"])
    DB_MAX_OVERFLOW: int = _env_int("DB_MAX_OVERFLOW", _DB_DEFAULTS["max_overflow"])
    DB_POOL_TIMEOUT: int = _env_int("DB_POOL_TIMEOUT", _DB_DEFAULTS["pool_timeout"])
    DB_POOL_RECYCLE: int = _env_int("DB_POOL_RECYCLE", _DB_DEFAULTS["pool_recycle"])
    DB_STATEMENT_TIMEOUT_MS: int = _env_int(
        "DB_STATEMENT_TIMEOUT_MS",
        _DB_DEFAULTS["statement_timeout_ms"],
    )
    del _DB_DEFAULTS

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
