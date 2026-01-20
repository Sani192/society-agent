#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:07:08 2026

@author: anonymous
"""

# app/whatsapp/router.py

from app.whatsapp.intents import INTENTS


def detect_intent(message: str):
    msg = message.lower().strip()

    # 1️ Exact phrase match (highest priority)
    for intent, keyword in INTENTS.items():
        if msg == keyword:
            return intent

    # 2️ Starts-with match (safe for commands with args)
    for intent, keyword in INTENTS.items():
        if msg.startswith(keyword + " "):
            return intent

    # 3️ Word-boundary match (last resort)
    for intent, keyword in INTENTS.items():
        if f" {keyword} " in f" {msg} ":
            return intent

    return None
