#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:07:08 2026

@author: anonymous
"""

# app/whatsapp/router.py

from app.whatsapp.intents import INTENTS


def detect_intent(message: str):
    msg = message.lower()

    for intent, keyword in INTENTS.items():
        if keyword in msg:
            return intent

    return None
