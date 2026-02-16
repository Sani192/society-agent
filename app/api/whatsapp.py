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
from app.channels.whatsapp.adapter import parse_webhook_payload
from app.channels.whatsapp.client import get_whatsapp_client
from app.channels.whatsapp.constants import (
    WHATSAPP_SIGNATURE_HEADER,
    WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE,
)
from app.config import settings
from app.db.session import SessionLocal
from app.commands.router import detect_intent
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    list_exportable_report_options,
)
from app.modules.reports.whatsapp_export_service import WhatsAppReportExportService
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.whatsapp.export_session import ExportSessionState, build_export_session_key, save_export_session
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


def _build_reports_list_sections(options: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for option in options:
        grouped.setdefault(option["category"], []).append(option)

    sections: list[dict] = []
    max_total_rows = 10
    used_rows = 0

    for category in sorted(grouped):
        entries = grouped[category]
        if used_rows >= max_total_rows:
            break

        rows = []
        for option in entries:
            if used_rows >= max_total_rows:
                break
            rows.append(
                {
                    "id": f"export::{option['command_key']}",
                    "title": option["label"][:24],
                    "description": f"Category: {category.title()} · PDF",
                }
            )
            used_rows += 1

        if rows:
            sections.append({"title": category.title(), "rows": rows})
    return sections[:10]


@router.get("/whatsapp")
def whatsapp_webhook_verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
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


@router.post("/whatsapp")
async def whatsapp_webhook_event(request: Request):
    _ensure_channel_enabled()
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
        intent = detect_intent(message.text)
        if intent in {"REPORTS", "REPORT_OPTIONS"}:
            db = SessionLocal()
            try:
                canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
                member = ensure_committee_member(
                    canonical_sender,
                    db,
                    channel_type="whatsapp",
                    external_user_id=message.sender_id,
                )
                report_options = list_exportable_report_options(
                    registry=build_whatsapp_report_registry(
                        handlers_by_code=WhatsAppReportExportService.handlers_by_report_code(),
                    ),
                    role=member.role,
                )

                save_export_session(
                    build_export_session_key(member_id=str(member.id), sender_id=canonical_sender),
                    ExportSessionState(options=report_options),
                )

                sections = _build_reports_list_sections(report_options)
                if sections:
                    client.send_list_message(
                        to_phone=message.sender_id,
                        header_text="Reports",
                        body_text=(
                            "Pick a report category and tap a report. "
                            "I will instantly generate the PDF and send it here."
                        ),
                        button_text="Choose Report",
                        sections=sections,
                        footer_text="Tip: You can also type reports anytime.",
                    )
                    continue
            except Exception:
                logger.exception("Failed to send reports interactive list")
            finally:
                db.close()

        reply_text = handle_inbound_message(message)
        client.send_text_message(message.sender_id, reply_text)

    logger.info("WhatsApp webhook processing completed")
    return {"status": "ok"}
