#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 21:31:38 2026

@author: anonymous
"""

# app/whatsapp/parser.py

import re
from datetime import datetime

from app.utils.logger import logger


EVENT_DATETIME_FORMAT = "%Y-%m-%d %H:%M"


def parse_amount(message: str):
    logger.info("Parsing amount from WhatsApp message")
    match = re.search(r"\b(\d+)\b", message)
    amount = int(match.group(1)) if match else None
    logger.info("Parsed amount", extra={"amount": amount})
    return amount


def parse_pass_counts(message: str):
    logger.info("Parsing pass counts from WhatsApp message")
    counts = {"veg": 0, "jain": 0, "kids": 0}

    for key in counts.keys():
        match = re.search(rf"{key}\s+(\d+)", message)
        if match:
            counts[key] = int(match.group(1))

    logger.info("Parsed pass counts", extra={"counts": counts})
    return counts


def parse_reason(message: str):
    logger.info("Parsing refund reason from WhatsApp message")
    match = re.search(r"reason\s+(.*)", message)
    reason = match.group(1).strip() if match else None
    logger.info("Parsed reason", extra={"has_reason": bool(reason)})
    return reason


def parse_target_flat(message: str):
    logger.info("Parsing target flat from WhatsApp message")
    match = re.search(r"\bfor\s+([A-Za-z0-9-]+)\b", message, re.IGNORECASE)
    if not match:
        match = re.search(r"\bflat\s+([A-Za-z0-9-]+)\b", message, re.IGNORECASE)
    flat = match.group(1).strip() if match else None
    logger.info("Parsed target flat", extra={"flat": flat})
    return flat


def parse_target_phone(message: str):
    logger.info("Parsing target phone from WhatsApp message")
    match = re.search(r"\bphone\s+(\+?\d{10,15})\b", message, re.IGNORECASE)
    phone = match.group(1).strip() if match else None
    logger.info("Parsed target phone", extra={"phone": phone})
    return phone


def parse_event_creation(message: str):
    logger.info("Parsing event creation command")
    example = (
        "add event Name | 2026-12-31 19:00 | food: veg,jain | adult:300 | "
        "child:150 | deadline:2026-12-30 18:00"
    )
    if not message.lower().startswith("add event"):
        logger.info("Event creation command format invalid: missing prefix")
        return None, f"Invalid format. Example: {example}"

    parts = [part.strip() for part in message.split("|")]
    if len(parts) < 5:
        logger.info("Event creation command missing fields")
        return None, f"Missing fields. Example: {example}"
    if len(parts) > 6:
        logger.info("Event creation command has extra fields")
        return None, f"Too many fields. Example: {example}"

    name = parts[0][len("add event"):].strip()
    if not name:
        logger.info("Event creation command missing event name")
        return None, f"Event name is required. Example: {example}"

    try:
        event_date = datetime.strptime(parts[1], EVENT_DATETIME_FORMAT)
    except ValueError:
        logger.info("Event creation command invalid event date")
        return None, f"Invalid event date. Use {EVENT_DATETIME_FORMAT}. Example: {example}"

    food_part = parts[2].lower()
    if not food_part.startswith("food:"):
        logger.info("Event creation command missing food section")
        return None, f"Food types missing. Example: {example}"
    food_types = [
        item.strip()
        for item in food_part.split("food:", 1)[1].split(",")
        if item.strip()
    ]
    if not food_types:
        logger.info("Event creation command has empty food types")
        return None, f"Food types missing. Example: {example}"

    adult_part = parts[3].lower()
    if not adult_part.startswith("adult:"):
        logger.info("Event creation command missing adult charge")
        return None, f"Adult charge missing. Example: {example}"
    try:
        charge_per_adult = int(adult_part.split("adult:", 1)[1].strip())
    except ValueError:
        logger.info("Event creation command non numeric adult charge")
        return None, f"Adult charge must be numeric. Example: {example}"

    child_part = parts[4].lower()
    if not child_part.startswith("child:"):
        logger.info("Event creation command missing child charge")
        return None, f"Child charge missing. Example: {example}"
    try:
        charge_per_child = int(child_part.split("child:", 1)[1].strip())
    except ValueError:
        logger.info("Event creation command non numeric child charge")
        return None, f"Child charge must be numeric. Example: {example}"

    payment_deadline = None
    if len(parts) == 6:
        deadline_part = parts[5].lower()
        if not deadline_part.startswith("deadline:"):
            logger.info("Event creation command invalid deadline format")
            return None, f"Deadline format invalid. Example: {example}"
        try:
            payment_deadline = datetime.strptime(
                deadline_part.split("deadline:", 1)[1].strip(),
                EVENT_DATETIME_FORMAT
            )
        except ValueError:
            logger.info("Event creation command invalid deadline date")
            return None, f"Invalid deadline. Use {EVENT_DATETIME_FORMAT}. Example: {example}"

    event_payload = {
        "name": name,
        "event_date": event_date,
        "food_types": food_types,
        "charge_per_adult": charge_per_adult,
        "charge_per_child": charge_per_child,
        "payment_deadline": payment_deadline
    }
    logger.info("Event creation command parsed successfully")
    return event_payload, None


def parse_report_export(message: str):
    """Parse export command into a normalized payload or a validation message."""
    logger.info("Parsing report export command")
    usage = "Use: export financial event-summary pdf"
    tokens = (message or "").strip().lower().split()

    if not tokens or tokens[0] != "export":
        return usage

    if len(tokens) < 4:
        return usage

    category = tokens[1]
    if category not in {"financial", "admin", "governance"}:
        return "Category must be one of: financial, admin, governance. " + usage

    report = tokens[2]
    report_format = tokens[3]
    if report_format not in {"csv", "excel", "pdf"}:
        return "Format must be one of: csv, excel, pdf. " + usage

    filters = {}
    remaining_tokens = tokens[4:]
    index = 0
    while index < len(remaining_tokens):
        token = remaining_tokens[index]

        if token.startswith("event_id=") or token.startswith("event-id="):
            event_id = token.split("=", 1)[1].strip()
            if not event_id:
                return "event_id cannot be empty. " + usage
            filters["event_id"] = event_id
            index += 1
            continue

        if token.startswith("event_id:") or token.startswith("event-id:"):
            event_id = token.split(":", 1)[1].strip()
            if not event_id:
                return "event_id cannot be empty. " + usage
            filters["event_id"] = event_id
            index += 1
            continue

        if token in {"event_id", "event-id", "eventid"}:
            if index + 1 >= len(remaining_tokens):
                return "event_id value is missing. " + usage
            filters["event_id"] = remaining_tokens[index + 1]
            index += 2
            continue

        if (
            index == 0
            and len(remaining_tokens) == 1
            and "=" not in token
            and ":" not in token
        ):
            filters["event_id"] = token
            index += 1
            continue

        return f"Unsupported filter token: {token}. " + usage

    return {
        "category": category,
        "report": report,
        "format": report_format,
        "filters": filters,
        "event_id": filters.get("event_id"),
    }
