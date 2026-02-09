#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:26:10 2026

@author: anonymous
"""

# app/config.py

import os
from dotenv import load_dotenv

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

    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v20.0")
    WHATSAPP_GRAPH_BASE_URL = os.getenv(
        "WHATSAPP_GRAPH_BASE_URL", "https://graph.facebook.com"
    )


settings = Settings()
