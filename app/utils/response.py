#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:27:21 2026

@author: anonymous
"""

# app/utils/response.py

from app.i18n.catalog import translate


def success(message: str):
    return f"✅ {message}"


def warning(message: str):
    return f"⚠️ {message}"


def error(message: str):
    return f"❌ {message}"


def error_envelope(message: str):
    return {
        "status": "error",
        "message": message
    }


def safe_error_message(*, lang: str | None = None):
    """Return a localized generic error message safe for end-user responses."""
    return translate("common.unexpected_error", lang)


def safe_error_envelope(*, lang: str | None = None):
    """Return a standardized safe error envelope with localized generic text."""
    return error_envelope(safe_error_message(lang=lang))


def info(message: str):
    return f"ℹ️ {message}"
