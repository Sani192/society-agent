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
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    list_valid_categories,
    list_valid_report_keys_for_category,
)


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
    """Parse modern report export command into a normalized payload or validation error."""
    logger.info("Parsing report export command")
    usage = (
        "Use: report export --category financial --report event-summary --format pdf"
    )
    tokens = (message or "").strip().lower().split()
    formats = {"csv", "excel", "pdf"}
    export_registry = build_whatsapp_report_registry(
        financial_handler=lambda **_kwargs: None,
        admin_handler=lambda **_kwargs: None,
        governance_handler=lambda **_kwargs: None,
    )
    categories = set(list_valid_categories(registry=export_registry))

    if len(tokens) < 2 or tokens[0] != "report" or tokens[1] != "export":
        return usage

    option_tokens = tokens[2:]
    if not option_tokens:
        return usage

    category = None
    report = None
    report_format = None
    filters = {}

    index = 0
    while index < len(option_tokens):
        token = option_tokens[index]
        if not token.startswith("--"):
            return f"Unsupported token: {token}. {usage}"

        key, value = token, None
        if "=" in token:
            key, value = token.split("=", 1)

        if value is None:
            if index + 1 >= len(option_tokens):
                return f"Value missing for {key}. {usage}"
            value = option_tokens[index + 1]
            index += 1

        if key == "--category":
            category = value
        elif key == "--report":
            report = value
        elif key == "--format":
            report_format = value
        elif key in {"--event-id", "--event_id"}:
            if not value:
                return f"event_id cannot be empty. {usage}"
            filters["event_id"] = value
        else:
            return f"Unsupported option: {key}. {usage}"

        index += 1

    if not category or not report or not report_format:
        return usage

    if category not in categories:
        accepted_categories = ", ".join(sorted(categories))
        return (
            f"Invalid category: {category}. "
            f"Accepted values: {accepted_categories}. "
            f"Example: {usage.removeprefix('Use: ')}"
        )

    if report_format not in formats:
        accepted_formats = ", ".join(sorted(formats))
        return (
            f"Invalid format: {report_format}. "
            f"Accepted values: {accepted_formats}. "
            f"Example: {usage.removeprefix('Use: ')}"
        )

    valid_reports = list_valid_report_keys_for_category(
        registry=export_registry,
        category=category,
    )
    if report not in valid_reports:
        accepted_reports = ", ".join(valid_reports) if valid_reports else "none"
        return (
            f"Invalid report: {report} for category {category}. "
            f"Accepted values: {accepted_reports}. "
            "Try: report options. "
            f"Example: {usage.removeprefix('Use: ')}"
        )

    return {
        "category": category,
        "report": report,
        "format": report_format,
        "filters": filters,
        "event_id": filters.get("event_id"),
    }
