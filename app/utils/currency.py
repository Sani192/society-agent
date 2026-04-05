#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from app.config import settings


def get_currency_symbol() -> str:
    return str(getattr(settings, "CURRENCY", "₹") or "₹")


def get_currency_code() -> str:
    return str(getattr(settings, "CURRENCY_CODE", "INR") or "INR")


def get_currency_label() -> str:
    code = get_currency_code().strip()
    symbol = get_currency_symbol().strip()
    if code and symbol:
        return f"{code} ({symbol})"
    return code or symbol


def format_currency(amount) -> str:
    symbol = get_currency_symbol()
    if amount is None:
        amount_value = 0
    else:
        amount_value = amount

    try:
        numeric = float(amount_value)
    except (TypeError, ValueError):
        return f"{symbol}{amount_value}"

    if numeric.is_integer():
        return f"{symbol}{int(numeric):,}"
    return f"{symbol}{numeric:,.2f}"
