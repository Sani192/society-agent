#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Bot API payload adapter."""

from __future__ import annotations

from typing import Any

from app.channels.core.types import InboundMessage
from app.utils.logger import logger


def _build_display_name(user: dict[str, Any]) -> str:
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()
    username = (user.get("username") or "").strip()

    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    if full_name:
        return full_name
    if username:
        return f"@{username}"
    return str(user.get("id") or "unknown")


def parse_webhook_payload(payload: dict[str, Any]) -> list[InboundMessage]:
    logger.info("Parsing Telegram webhook payload")
    message = (payload or {}).get("message") or {}

    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    sender = message.get("from") or {}

    chat_id = chat.get("id")
    sender_id = sender.get("id")

    if not text or chat_id is None or sender_id is None:
        logger.info(
            "Skipping unsupported Telegram update",
            extra={"update_id": payload.get("update_id")},
        )
        return []

    inbound = InboundMessage(
        channel="telegram",
        sender_id=str(sender_id),
        display_name=_build_display_name(sender),
        text=text,
        metadata={
            "update_id": payload.get("update_id"),
            "chat_id": str(chat_id),
            "message_id": message.get("message_id"),
            "username": sender.get("username"),
            "canonical_sender_id": str(sender_id),
            "external_user_id": str(sender_id),
        },
    )

    logger.info(
        "Parsed Telegram inbound message",
        extra={"sender_id": inbound.sender_id, "chat_id": inbound.metadata.get("chat_id")},
    )
    return [inbound]
