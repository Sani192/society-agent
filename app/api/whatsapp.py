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

from app.channels.whatsapp.adapter import parse_webhook_payload
from app.channels.whatsapp.client import get_whatsapp_client
from app.config import settings
from app.utils.logger import logger
from app.whatsapp.handler import handle_message

router = APIRouter()


def _verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not settings.WHATSAPP_APP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp app secret not configured",
        )
    if not signature_header:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )


@router.get("/whatsapp")
def whatsapp_webhook_verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
):
    if not settings.WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp verify token not configured",
        )
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    _verify_signature(raw_body, signature)

    payload = await request.json()
    inbound_messages = parse_webhook_payload(payload)
    if not inbound_messages:
        logger.info("WhatsApp webhook received with no inbound messages")
        return {"status": "ignored"}

    client = get_whatsapp_client()
    for message in inbound_messages:
        reply_text = handle_message(
            phone_number=message.sender_phone,
            message=message.text,
        )
        client.send_text_message(message.sender_phone, reply_text)
    return {"status": "ok"}
