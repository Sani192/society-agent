#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.utils.logger import logger


def handle_telegram_text(*, sender_id: str, text: str, display_name: str | None = None) -> str:
    logger.info(
        "Processing Telegram inbound text",
        extra={"sender_id": sender_id, "display_name": display_name or sender_id},
    )
    inbound_message = InboundMessage(
        channel="telegram",
        sender_id=sender_id,
        display_name=display_name or sender_id,
        text=text,
        metadata={},
    )
    return handle_inbound_message(inbound_message)
