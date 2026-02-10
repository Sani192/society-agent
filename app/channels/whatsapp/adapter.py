#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WhatsApp Cloud API payload adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.utils.logger import logger


@dataclass(frozen=True)
class InboundMessage:
    sender_phone: str
    text: str
    message_id: str | None = None


def _iter_messages(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    logger.info("Iterating WhatsApp webhook payload entries")
    for entry in payload.get("entry", []) or []:
        logger.info("Processing webhook entry", extra={"entry_id": entry.get("id")})
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for message in value.get("messages", []) or []:
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
        messages.append(
            InboundMessage(
                sender_phone=sender,
                text=text,
                message_id=message.get("id"),
            )
        )
    logger.info("Parsed inbound WhatsApp messages", extra={"count": len(messages)})
    return messages
