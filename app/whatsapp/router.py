#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:07:08 2026

@author: anonymous
"""

# app/whatsapp/router.py

from app.utils.logger import logger
from app.whatsapp.intents import INTENTS


def detect_intent(message: str):
    msg = message.lower().strip()
    logger.info("Detecting WhatsApp intent", extra={"message_text": msg})

    # 1️ Exact phrase match (highest priority)
    for intent, keyword in INTENTS.items():
        if msg == keyword:
            logger.info("Intent detected by exact match", extra={"intent": intent})
            return intent

    # 2️ Starts-with match (safe for commands with args)
    for intent, keyword in INTENTS.items():
        if msg.startswith(keyword + " "):
            logger.info("Intent detected by startswith", extra={"intent": intent})
            return intent

    # 3️ Word-boundary match (last resort)
    for intent, keyword in INTENTS.items():
        if f" {keyword} " in f" {msg} ":
            logger.info("Intent detected by word-boundary", extra={"intent": intent})
            return intent

    logger.info("No WhatsApp intent detected")
    return None
