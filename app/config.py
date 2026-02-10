#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:26:10 2026

@author: anonymous
"""

# app/config.py

import os
from dotenv import load_dotenv

from app.channels.whatsapp.constants import WHATSAPP_ENV_CONFIGS

load_dotenv()


class Settings:
    APP_ENV = os.getenv("APP_ENV", "local")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    CURRENCY = os.getenv("CURRENCY_SYMBOL", "₹")

    DEFAULT_SOCIETY_NAME = os.getenv("DEFAULT_SOCIETY_NAME")

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


settings = Settings()
