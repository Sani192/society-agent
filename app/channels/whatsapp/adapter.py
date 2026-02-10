#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Cloud API payload adapter.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.channels.core.types import InboundMessage
from app.utils.logger import logger


def _iter_messages(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    logger.info("Iterating WhatsApp webhook payload entries")
    for entry in payload.get("entry", []) or []:
        logger.info("Processing webhook entry", extra={"entry_id": entry.get("id")})
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            contacts_by_wa_id = {
                contact.get("wa_id"): contact for contact in (value.get("contacts") or [])
            }
            for message in value.get("messages", []) or []:
                contact = contacts_by_wa_id.get(message.get("from")) or {}
                message["_profile_name"] = (contact.get("profile") or {}).get("name")
                logger.info(
                    "Yielding inbound WhatsApp message",
                    extra={"message_id": message.get("id")},
                )
                yield message


def parse_webhook_payload(payload: dict[str, Any]) -> list[InboundMessage]:
    logger.info("Parsing WhatsApp webhook payload")
    messages: list[InboundMessage] = []
    for message in _iter_messages(payload):
        sender = message.get("from")
        text = (message.get("text") or {}).get("body")
        if not sender or not text:
            logger.info(
                "Skipping malformed inbound message",
                extra={"message_id": message.get("id")},
            )
            continue

        profile_name = message.get("_profile_name")
        messages.append(
            InboundMessage(
                channel="whatsapp",
                sender_id=sender,
                display_name=profile_name or sender,
                text=text,
                metadata={"message_id": message.get("id")},
            )
        )
    logger.info("Parsed inbound WhatsApp messages", extra={"count": len(messages)})
    return messages
