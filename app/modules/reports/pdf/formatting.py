#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 07 12:00:00 2026

@author: anonymous
"""

from typing import Iterable

CURRENCY_TOKENS = (
    "amount",
    "paid",
    "pending",
    "expected",
    "balance",
    "income",
    "expense",
    "refund",
    "total",
    "cash",
)


def format_currency(value):
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    return f"₹ {value:,}"


def format_report_rows(headers: list, rows: Iterable[list]):
    currency_columns = [
        idx for idx, header in enumerate(headers)
        if any(token in header.lower() for token in CURRENCY_TOKENS)
    ]

    formatted = []
    for row in rows:
        new_row = list(row)
        for idx in currency_columns:
            if idx >= len(new_row):
                continue
            new_row[idx] = format_currency(new_row[idx])
        formatted.append(new_row)
    return formatted
