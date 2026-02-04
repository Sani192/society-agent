#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:31:38 2026

@author: anonymous
"""

# app/whatsapp/parser.py

import re


def parse_amount(message: str):
    match = re.search(r"\b(\d+)\b", message)
    return int(match.group(1)) if match else None


def parse_pass_counts(message: str):
    counts = {"veg": 0, "jain": 0, "kids": 0}

    for key in counts.keys():
        match = re.search(rf"{key}\s+(\d+)", message)
        if match:
            counts[key] = int(match.group(1))

    return counts


def parse_reason(message: str):
    match = re.search(r"reason\s+(.*)", message)
    return match.group(1).strip() if match else None


def parse_target_flat(message: str):
    match = re.search(r"\bfor\s+([A-Za-z0-9-]+)\b", message, re.IGNORECASE)
    if not match:
        match = re.search(r"\bflat\s+([A-Za-z0-9-]+)\b", message, re.IGNORECASE)
    return match.group(1).strip() if match else None


def parse_target_phone(message: str):
    match = re.search(r"\bphone\s+(\+?\d{10,15})\b", message, re.IGNORECASE)
    return match.group(1).strip() if match else None
