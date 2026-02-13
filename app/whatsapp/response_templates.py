#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 09 10:12:34 2026

@author: anonymous
"""

# app/whatsapp/response_templates.py

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

from app.utils.response import success, warning, error, info

DEFAULT_DATETIME_FORMAT = "%d %b %Y %H:%M"


def format_heading(title: str, emoji: Optional[str] = None) -> str:
    cleaned = title.strip()
    if emoji:
        return f"{emoji} *{cleaned}*"
    return f"*{cleaned}*"


def format_currency(amount) -> str:
    if amount is None:
        amount_value = 0
    else:
        amount_value = amount

    try:
        numeric = float(amount_value)
    except (TypeError, ValueError):
        return f"₹{amount_value}"

    if numeric.is_integer():
        return f"₹{int(numeric):,}"
    return f"₹{numeric:,.2f}"


def format_datetime(value, fmt: str = DEFAULT_DATETIME_FORMAT) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (datetime, date)) or hasattr(value, "strftime"):
        return value.strftime(fmt)
    return str(value)


def join_lines(lines: Iterable[str]) -> str:
    return "\n".join([line for line in lines if line is not None])


def _compose_message(body: str, heading: Optional[str], emoji: Optional[str]) -> str:
    if heading:
        header = format_heading(heading, emoji)
        if body:
            return f"{header}\n{body}"
        return header
    return body


def success_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None) -> str:
    return success(_compose_message(body, heading, emoji))


def warning_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None) -> str:
    return warning(_compose_message(body, heading, emoji))


def error_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None) -> str:
    return error(_compose_message(body, heading, emoji))


def info_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None) -> str:
    return info(_compose_message(body, heading, emoji))


EXPORT_COMMAND_EXAMPLES = (
    "report export --category financial --report event-summary --format pdf",
    "report export --category admin --report onboarding-status --format csv",
    "report export --category governance --report audit --format excel",
)
