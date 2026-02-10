#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:26:10 2026

@author: anonymous
"""

# app/config.py

import os
from dotenv import load_dotenv

from app.channels.whatsapp.constants import (
    DEFAULT_WHATSAPP_API_VERSION,
    DEFAULT_WHATSAPP_GRAPH_BASE_URL,
    WHATSAPP_ACCESS_TOKEN_ENV_KEY,
    WHATSAPP_API_VERSION_ENV_KEY,
    WHATSAPP_APP_SECRET_ENV_KEY,
    WHATSAPP_GRAPH_BASE_URL_ENV_KEY,
    WHATSAPP_PHONE_NUMBER_ID_ENV_KEY,
    WHATSAPP_VERIFY_TOKEN_ENV_KEY,
)

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

    WHATSAPP_VERIFY_TOKEN = os.getenv(WHATSAPP_VERIFY_TOKEN_ENV_KEY)
    WHATSAPP_APP_SECRET = os.getenv(WHATSAPP_APP_SECRET_ENV_KEY)
    WHATSAPP_ACCESS_TOKEN = os.getenv(WHATSAPP_ACCESS_TOKEN_ENV_KEY)
    WHATSAPP_PHONE_NUMBER_ID = os.getenv(WHATSAPP_PHONE_NUMBER_ID_ENV_KEY)
    WHATSAPP_API_VERSION = os.getenv(
        WHATSAPP_API_VERSION_ENV_KEY, DEFAULT_WHATSAPP_API_VERSION
    )
    WHATSAPP_GRAPH_BASE_URL = os.getenv(
        WHATSAPP_GRAPH_BASE_URL_ENV_KEY, DEFAULT_WHATSAPP_GRAPH_BASE_URL
    )


settings = Settings()
