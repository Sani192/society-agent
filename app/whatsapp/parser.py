#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:31:38 2026

@author: anonymous
"""

# app/whatsapp/parser.py

import re
from datetime import datetime


EVENT_DATETIME_FORMAT = "%Y-%m-%d %H:%M"


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


def parse_event_creation(message: str):
    example = (
        "add event Name | 2026-12-31 19:00 | food: veg,jain | adult:300 | "
        "child:150 | deadline:2026-12-30 18:00"
    )
    if not message.lower().startswith("add event"):
        return None, f"Invalid format. Example: {example}"

    parts = [part.strip() for part in message.split("|")]
    if len(parts) < 5:
        return None, f"Missing fields. Example: {example}"
    if len(parts) > 6:
        return None, f"Too many fields. Example: {example}"

    name = parts[0][len("add event"):].strip()
    if not name:
        return None, f"Event name is required. Example: {example}"

    try:
        event_date = datetime.strptime(parts[1], EVENT_DATETIME_FORMAT)
    except ValueError:
        return None, f"Invalid event date. Use {EVENT_DATETIME_FORMAT}. Example: {example}"

    food_part = parts[2].lower()
    if not food_part.startswith("food:"):
        return None, f"Food types missing. Example: {example}"
    food_types = [
        item.strip()
        for item in food_part.split("food:", 1)[1].split(",")
        if item.strip()
    ]
    if not food_types:
        return None, f"Food types missing. Example: {example}"

    adult_part = parts[3].lower()
    if not adult_part.startswith("adult:"):
        return None, f"Adult charge missing. Example: {example}"
    try:
        charge_per_adult = int(adult_part.split("adult:", 1)[1].strip())
    except ValueError:
        return None, f"Adult charge must be numeric. Example: {example}"

    child_part = parts[4].lower()
    if not child_part.startswith("child:"):
        return None, f"Child charge missing. Example: {example}"
    try:
        charge_per_child = int(child_part.split("child:", 1)[1].strip())
    except ValueError:
        return None, f"Child charge must be numeric. Example: {example}"

    payment_deadline = None
    if len(parts) == 6:
        deadline_part = parts[5].lower()
        if not deadline_part.startswith("deadline:"):
            return None, f"Deadline format invalid. Example: {example}"
        try:
            payment_deadline = datetime.strptime(
                deadline_part.split("deadline:", 1)[1].strip(),
                EVENT_DATETIME_FORMAT
            )
        except ValueError:
            return None, f"Invalid deadline. Use {EVENT_DATETIME_FORMAT}. Example: {example}"

    return {
        "name": name,
        "event_date": event_date,
        "food_types": food_types,
        "charge_per_adult": charge_per_adult,
        "charge_per_child": charge_per_child,
        "payment_deadline": payment_deadline
    }, None
