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
