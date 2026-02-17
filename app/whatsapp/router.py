#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.commands.router import detect_intent
from app.whatsapp.intents import WHATSAPP_INTENTS


def detect_whatsapp_intent(message: str):
    return detect_intent(message, intents=WHATSAPP_INTENTS)


__all__ = ["detect_whatsapp_intent"]
