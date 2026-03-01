#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WhatsApp webhook HTTP handlers and orchestration."""

import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel

from app.api.contracts import ErrorResponse, WebhookStatusResponse, WhatsAppWebhookPayload
from app.channels.core.handler import handle_inbound_message
from app.channels.core.audit_events import NormalizedAuditEvent, persist_audit_events
from app.channels.whatsapp.adapter import (
    parse_webhook_events,
    parse_webhook_payload,
    to_normalized_audit_events,
)
from app.channels.whatsapp.client import get_whatsapp_client
from app.channels.whatsapp.constants import (
    WHATSAPP_SIGNATURE_HEADER,
    WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE,
)
from app.channels.whatsapp.report_flow import handle_report_flow
from app.channels.whatsapp.session_flows import handle_session_flow
from app.channels.whatsapp.ui_router import (
    WHATSAPP_LIST_MAX_ROWS,
    _button_row,
    _try_handle_ui_message,
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
    _ensure_channel_enabled()
    logger.info("Received compatibility WhatsApp command webhook")
    reply_text = handle_message(phone_number=payload.phone_number, message=payload.message)
    return {"reply": reply_text}


def _ensure_channel_enabled() -> None:
    if not settings.WHATSAPP_ENABLED:
        logger.info("WhatsApp channel is disabled")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp channel is disabled",
        )


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



def _hash_payload(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _build_webhook_received_event(*, payload_hash: str, payload: dict) -> NormalizedAuditEvent:
    selected_fields = {
        "object": payload.get("object"),
        "entry_count": len(payload.get("entry") or []),
        "entry_ids": [entry.get("id") for entry in (payload.get("entry") or []) if isinstance(entry, dict)],
    }
    return NormalizedAuditEvent(
        channel="whatsapp",
        direction="system",
        event_type="webhook_received",
        payload_json={"payload_hash": payload_hash, "selected": selected_fields},
        occurred_at=datetime.now(timezone.utc),
    )


def _build_reports_list_sections(
    options: list[dict],
    *,
    page_index: int = 0,
    page_size: int = WHATSAPP_LIST_MAX_ROWS,
    include_more_row: bool = False,
) -> list[dict]:
    from app.channels.whatsapp.report_flow import _build_reports_list_sections as _impl

    return _impl(
        options,
        page_index=page_index,
        page_size=page_size,
        include_more_row=include_more_row,
    )

@router.get(
    "/whatsapp",
    responses={403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def whatsapp_webhook_verify(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    _ensure_channel_enabled()
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


@router.post(
    "/whatsapp",
    response_model=WebhookStatusResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "object": {"type": "string"},
                            "entry": {"type": "array", "items": {"type": "object"}},
                        },
                        "additionalProperties": True,
                    }
                }
            },
        }
    },
)
async def whatsapp_webhook_event(request: Request) -> dict[str, str]:
    _ensure_channel_enabled()
    logger.info("Received WhatsApp webhook event")
    if hasattr(request, "body"):
        raw_body = await request.body()
    else:
        payload_for_body = await request.json()
        raw_body = json.dumps(payload_for_body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = request.headers.get(WHATSAPP_SIGNATURE_HEADER)
    _verify_signature(raw_body, signature)

    payload_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    payload = WhatsAppWebhookPayload.model_validate(payload_data)
    payload_dict = payload.model_dump(exclude_none=True)

    payload_hash = _hash_payload(raw_body)
    parsed_events = parse_webhook_events(payload_dict)
    normalized_events = [_build_webhook_received_event(payload_hash=payload_hash, payload=payload_dict)]
    normalized_events.extend(to_normalized_audit_events(parsed_events))
    persist_audit_events(normalized_events)

    inbound_messages = parse_webhook_payload(payload_dict)
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
        if _try_handle_ui_message(client=client, message=message):
            logger.info(
                "WhatsApp premium UI response sent",
                extra={"sender_id": message.sender_id, "message_id": message.metadata.get("message_id")},
            )
            continue

        if handle_session_flow(client=client, message=message):
            continue

        if handle_report_flow(client=client, message=message):
            continue

        reply_text = handle_inbound_message(message)
        try:
            if reply_text.startswith("ℹ️ Invalid option."):
                send_response = client.send_button_message(
                    to_phone=message.sender_id,
                    header_text="Invalid option",
                    body_text=reply_text,
                    buttons=[_button_row("menu", "Main Menu")],
                )
            else:
                send_response = client.send_text_message(message.sender_id, reply_text)
            logger.info(
                "WhatsApp text reply sent",
                extra={
                    "sender_id": message.sender_id,
                    "message_id": message.metadata.get("message_id"),
                    "response_keys": sorted(send_response.keys()),
                },
            )
        except Exception:
            logger.exception(
                "Failed to send WhatsApp text reply",
                extra={
                    "sender_id": message.sender_id,
                    "message_id": message.metadata.get("message_id"),
                },
            )

    logger.info("WhatsApp webhook processing completed")
    return {"status": "ok"}
