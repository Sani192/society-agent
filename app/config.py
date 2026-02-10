#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:26:10 2026

@author: anonymous
"""

# app/config.py

import os
from dotenv import load_dotenv

from app.channels.telegram.constants import TELEGRAM_ENV_CONFIGS
from app.channels.whatsapp.constants import WHATSAPP_ENV_CONFIGS

load_dotenv()


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    APP_ENV = os.getenv("APP_ENV", "local")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    CURRENCY = os.getenv("CURRENCY_SYMBOL", "₹")

    DEFAULT_SOCIETY_NAME = os.getenv("DEFAULT_SOCIETY_NAME")
    WHATSAPP_ENABLED = _env_flag("WHATSAPP_ENABLED", "true")
    TELEGRAM_ENABLED = _env_flag("TELEGRAM_ENABLED", "true")

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
