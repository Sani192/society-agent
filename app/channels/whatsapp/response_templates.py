#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 09 10:12:34 2026

@author: anonymous
"""

# app/whatsapp/response_templates.py

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from functools import partial
from typing import Optional, Protocol

from app.i18n.catalog import translate
from app.utils.response import error, info, success, warning

DEFAULT_DATETIME_FORMAT = "%d %b %Y %H:%M"
class Translator(Protocol):
    def __call__(self, key: str, **params: object) -> str: ...



def _resolve_translator(*, lang: str | None = None, translator: Translator | None = None) -> Translator:
    if translator is not None:
        return translator
    return partial(translate, lang=lang)


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


def format_datetime(value, fmt: str = DEFAULT_DATETIME_FORMAT, *, lang: str | None = None, translator: Translator | None = None) -> str:
    translate_text = _resolve_translator(lang=lang, translator=translator)
    if value is None:
        return translate_text("response_templates.not_available")
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


def success_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None, *, lang: str | None = None, translator: Translator | None = None) -> str:
    _resolve_translator(lang=lang, translator=translator)
    return success(_compose_message(body, heading, emoji))


def warning_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None, *, lang: str | None = None, translator: Translator | None = None) -> str:
    _resolve_translator(lang=lang, translator=translator)
    return warning(_compose_message(body, heading, emoji))


def error_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None, *, lang: str | None = None, translator: Translator | None = None) -> str:
    _resolve_translator(lang=lang, translator=translator)
    return error(_compose_message(body, heading, emoji))


def info_response(body: str, heading: Optional[str] = None, emoji: Optional[str] = None, *, lang: str | None = None, translator: Translator | None = None) -> str:
    _resolve_translator(lang=lang, translator=translator)
    return info(_compose_message(body, heading, emoji))


def format_report_options_response(options: list[dict], *, lang: str | None = None, translator: Translator | None = None) -> str:
    translate_text = _resolve_translator(lang=lang, translator=translator)
    lines = [
        format_heading(
            translate_text("response_templates.exportable_report_options_heading"),
            "📚",
        ),
        translate_text("response_templates.report_options_intro"),
    ]

    if not options:
        lines.append(translate_text("response_templates.no_exportable_reports"))
        return join_lines(lines)

    for option in options:
        lines.extend(
            [
                "",
                f"*{translate_text('response_templates.category')}*: {option['category']}",
                f"*{translate_text('response_templates.report_key')}*: {option['report_key']}",
                f"*{translate_text('response_templates.label')}*: {option['label']}",
                f"*{translate_text('response_templates.formats')}*: {', '.join(option['supported_formats'])}",
                f"*{translate_text('response_templates.example')}*: {option['example_command']}",
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
    translator: Translator | None = None,
) -> tuple[str, InvalidInputContract]:
    translate_text = _resolve_translator(lang=lang, translator=translator)
    default_ctas = [
        {"id": "menu", "label": translate_text("response_templates.main_menu")},
        {"id": "help", "label": translate_text("response_templates.help")},
    ]
    label_keys = {
        "menu": "response_templates.main_menu",
        "help": "response_templates.help",
        "report options": "response_templates.report_options",
    }
    action_rows = tuple(
        {
            "id": action["id"],
            "label": action.get("label") or translate_text(label_keys.get(action["id"], "response_templates.help")),
        }
        for action in (ctas or default_ctas)
    )
    command_hints = ", ".join(action["id"] for action in action_rows)
    if channel == "whatsapp":
        text = info_response(
            translate_text(
                "response_templates.invalid_option",
                reason=reason,
                command_hints=command_hints,
            ),
            lang=lang,
            translator=translator,
        )
    else:
        text = info_response(
            translate_text(
                "response_templates.invalid_command",
                reason=reason,
                command_hints=command_hints,
            ),
            lang=lang,
            translator=translator,
        )
    return text, InvalidInputContract(reason=reason, ctas=action_rows)
