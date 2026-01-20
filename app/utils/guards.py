#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 07:28:42 2026

@author: anonymous
"""

# app/utils/guards.py

from app.config import settings


def normalize_phone(phone: str) -> str:
    return phone.replace("+", "").strip()


def ensure_admin(phone_number: str):
    normalized = normalize_phone(phone_number)
    whitelist = [normalize_phone(p) for p in settings.ADMIN_PHONE_WHITELIST]

    if normalized not in whitelist:
        raise Exception("You are not allowed to perform this action")


def ensure_reason(reason: str):
    if not reason or len(reason.strip()) < 5:
        raise Exception("Override reason must be at least 5 characters")
