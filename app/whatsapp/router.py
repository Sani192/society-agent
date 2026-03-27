#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.commands.router import detect_intent
from app.whatsapp.intents import WHATSAPP_INTENTS


def detect_whatsapp_intent(
    message: str,
    *,
    language: str | None = None,
    allow_numeric_export_selection: bool = True,
):
    return detect_intent(
        message,
        intents=WHATSAPP_INTENTS,
        language=language,
        allow_numeric_export_selection=allow_numeric_export_selection,
    )


__all__ = ["detect_whatsapp_intent"]
