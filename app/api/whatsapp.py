#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 06:32:11 2026

@author: anonymous
"""

# app/api/whatsapp.py

import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.channels.whatsapp.adapter import parse_webhook_payload
from app.channels.whatsapp.client import get_whatsapp_client
from app.channels.whatsapp.constants import (
    WHATSAPP_SIGNATURE_HEADER,
    WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE,
)
from app.config import settings
from app.utils.logger import logger
from app.whatsapp.handler import handle_message

router = APIRouter()


class WhatsAppRequest(BaseModel):
    phone_number: str
    message: str


def whatsapp_webhook(payload: WhatsAppRequest) -> dict[str, str]:
    """Compatibility command-style webhook used by tests and local callers."""
    logger.info("Received compatibility WhatsApp command webhook")
    reply_text = handle_message(phone_number=payload.phone_number, message=payload.message)
    return {"reply": reply_text}


def _verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    logger.info("Verifying WhatsApp webhook signature")
    if not settings.WHATSAPP_APP_SECRET:
        logger.error("WhatsApp app secret not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp app secret not configured",
        )
    if not signature_header:
        logger.warning("WhatsApp webhook signature header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature header",
        )
    expected_hash = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    expected_signature = f"sha256={expected_hash}"
    if not hmac.compare_digest(expected_signature, signature_header):
        logger.warning("Invalid WhatsApp webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    logger.info("WhatsApp webhook signature verification passed")


@router.get("/whatsapp")
def whatsapp_webhook_verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
):
    logger.info("Received WhatsApp webhook verification request")
    if not settings.WHATSAPP_VERIFY_TOKEN:
        logger.error("WhatsApp verify token not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp verify token not configured",
        )
    if (
        hub_mode == WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE
        and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN
    ):
        logger.info("WhatsApp webhook verification successful")
        return Response(content=hub_challenge or "", media_type="text/plain")

    logger.warning("WhatsApp webhook verification failed")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/whatsapp")
async def whatsapp_webhook_event(request: Request):
    logger.info("Received WhatsApp webhook event")
    raw_body = await request.body()
    signature = request.headers.get(WHATSAPP_SIGNATURE_HEADER)
    _verify_signature(raw_body, signature)

    payload = await request.json()
    inbound_messages = parse_webhook_payload(payload)
    if not inbound_messages:
        logger.info("WhatsApp webhook received with no inbound messages")
        return {"status": "ignored"}

    client = get_whatsapp_client()
    for message in inbound_messages:
        logger.info(
            "Processing inbound WhatsApp message",
            extra={
                "sender_id": message.sender_id,
                "channel": message.channel,
                "message_id": message.metadata.get("message_id"),
            },
        )
        reply_text = handle_inbound_message(message)
        client.send_text_message(message.sender_id, reply_text)

    logger.info("WhatsApp webhook processing completed")
    return {"status": "ok"}
