#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 09 10:12:34 2026

@author: anonymous
"""

# app/whatsapp/response_templates.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

from app.i18n.catalog import translate
from app.utils.response import error, info, success, warning

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


def format_report_options_response(options: list[dict], *, lang: str | None = None) -> str:
    lines = [
        format_heading(
            translate("response_templates.exportable_report_options_heading", lang),
            "📚",
        )
    ]

    if not options:
        lines.append(translate("response_templates.no_exportable_reports", lang))
        return join_lines(lines)

    for option in options:
        lines.extend(
            [
                "",
                f"*{translate('response_templates.category', lang)}*: {option['category']}",
                f"*{translate('response_templates.report_key', lang)}*: {option['report_key']}",
                f"*{translate('response_templates.label', lang)}*: {option['label']}",
                f"*{translate('response_templates.formats', lang)}*: {', '.join(option['supported_formats'])}",
                f"*{translate('response_templates.example', lang)}*: {option['example_command']}",
            ]
        )

    return join_lines(lines)


EXPORT_COMMAND_EXAMPLES = (
    "report options",
    "export::financial:ledger",
    "export 1",
)


INVALID_INPUT_METADATA_KEY = "response_contract"


@dataclass(frozen=True)
class InvalidInputContract:
    reason: str
    ctas: tuple[dict[str, str], ...]
    response_type: str = "invalid_input"
    severity: str = "info"


def build_invalid_command_response(
    *,
    channel: str,
    reason: str,
    ctas: list[dict[str, str]] | None = None,
    lang: str | None = None,
) -> tuple[str, InvalidInputContract]:
    action_rows = tuple(
        ctas
        or [
            {"id": "menu", "label": translate("response_templates.main_menu", lang)},
            {"id": "help", "label": translate("response_templates.help", lang)},
        ]
    )
    command_hints = ", ".join(action["id"] for action in action_rows)
    if channel == "whatsapp":
        text = info_response(
            translate(
                "response_templates.invalid_option",
                lang,
                reason=reason,
                command_hints=command_hints,
            )
        )
    else:
        text = info_response(
            translate(
                "response_templates.invalid_command",
                lang,
                reason=reason,
                command_hints=command_hints,
            )
        )
    return text, InvalidInputContract(reason=reason, ctas=action_rows)
