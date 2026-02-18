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
from app.db.session import SessionLocal
from app.whatsapp.router import detect_whatsapp_intent
from app.modules.reports.common.whatsapp_report_registry import (
    build_whatsapp_report_registry,
    list_exportable_report_options,
)
from app.modules.reports.whatsapp_export_service import WhatsAppReportExportService
from app.modules.users.user_query_service import UserQueryService
from app.modules.onboarding.join_code_service import JoinCodeService
from app.commands.handlers.common import get_latest_event, resolve_flat
from app.whatsapp.response_templates import format_currency
from app.whatsapp.ui import (
    add_or_update_pass_prompt,
    build_committee_more_sections,
    build_committee_sections,
    build_finance_sections,
    build_main_dashboard_sections,
    build_make_payment_sections,
    build_my_account_sections,
    build_participation_sections,
    build_payments_sections,
    build_reports_sections,
    build_society_sections,
    format_financial_overview,
    payment_custom_amount_prompt,
    refund_request_prompt,
)
from app.utils.guards import ensure_committee_member
from app.utils.logger import logger
from app.whatsapp.export_session import (
    ExportSessionState,
    build_export_session_key,
    get_export_session,
    save_export_session,
)
from app.whatsapp.finance_action_session import (
    FinanceActionSessionState,
    build_finance_action_session_key,
    clear_finance_action_session,
    get_finance_action_session,
    save_finance_action_session,
)
from app.whatsapp.join_session import (
    JoinSessionState,
    build_join_session_key,
    clear_join_session,
    get_join_session,
    save_join_session,
)
from app.whatsapp.handler import handle_message

router = APIRouter()

WHATSAPP_LIST_MAX_ROWS = 10
WHATSAPP_MORE_REPORTS_ROW_ID = "export::more-reports"


def _report_page_option_limit(*, total_options: int, page_size: int = WHATSAPP_LIST_MAX_ROWS) -> int:
    if page_size <= 1:
        return 1
    return page_size - 1 if total_options > page_size else page_size


def _chunk_report_options(options: list[dict], page_size: int = WHATSAPP_LIST_MAX_ROWS) -> list[list[dict]]:
    if page_size <= 0:
        page_size = WHATSAPP_LIST_MAX_ROWS
    return [options[idx : idx + page_size] for idx in range(0, len(options), page_size)]


def _normalize_report_page(page_index: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 0
    return page_index % total_pages


def _next_report_page(current_page: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 0
    return (current_page + 1) % total_pages




def _is_committee_member(*, db, sender_id: str, external_user_id: str) -> bool:
    try:
        ensure_committee_member(
            sender_id,
            db,
            channel_type="whatsapp",
            external_user_id=external_user_id,
        )
        return True
    except Exception:
        return False


def _send_dashboard_ui(*, client, sender_id: str, is_committee: bool) -> None:
    client.send_list_message(
        to_phone=sender_id,
        header_text="Society Control Panel",
        body_text="Select a section",
        button_text="Open",
        sections=build_main_dashboard_sections(is_committee=is_committee),
    )


def _try_handle_ui_message(*, client, message) -> bool:
    msg = message.text.strip().lower()

    if msg in {"menu", "ui::menu"}:
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            _send_dashboard_ui(
                client=client,
                sender_id=message.sender_id,
                is_committee=_is_committee_member(
                    db=db,
                    sender_id=canonical_sender,
                    external_user_id=message.sender_id,
                ),
            )
            return True
        finally:
            db.close()

    if msg == "ui::participation":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="Participation",
            body_text="Participation",
            button_text="Open",
            sections=build_participation_sections(),
        )
        return True

    if msg == "ui::participation:add-update-pass":
        client.send_text_message(message.sender_id, add_or_update_pass_prompt())
        return True

    if msg == "ui::payments":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="Your Financial Overview",
            body_text="Select an action",
            button_text="Open",
            sections=build_payments_sections(),
        )
        return True

    if msg == "ui::finance:view-balance":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            latest_event = get_latest_event(db)
            if not latest_event:
                client.send_text_message(message.sender_id, "No active event found.")
                return True
            flat = resolve_flat(db, phone_number=canonical_sender, society_id=latest_event.society_id)
            balance = UserQueryService.get_my_balance(db=db, event_id=latest_event.id, flat_id=flat.id)
            summary = UserQueryService.get_my_payment_summary(db=db, event_id=latest_event.id, flat_id=flat.id)
            client.send_text_message(
                message.sender_id,
                format_financial_overview(
                    expected=format_currency(balance["expected"]),
                    paid=format_currency(balance["paid"]),
                    refunded=format_currency(summary["refunded"]),
                    outstanding=format_currency(balance["balance"]),
                ),
            )
            return True
        except Exception:
            logger.exception("Failed to build financial overview")
            return False
        finally:
            db.close()

    if msg == "ui::make-payment":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            latest_event = get_latest_event(db)
            if not latest_event:
                client.send_text_message(message.sender_id, "No active event found.")
                return True
            flat = resolve_flat(db, phone_number=canonical_sender, society_id=latest_event.society_id)
            balance = UserQueryService.get_my_balance(db=db, event_id=latest_event.id, flat_id=flat.id)
            outstanding = max(balance["balance"], 0)
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Make Payment",
                body_text=f"Outstanding Amount: {format_currency(outstanding)}",
                button_text="Choose",
                sections=build_make_payment_sections(outstanding_amount=str(int(outstanding) if float(outstanding).is_integer() else outstanding)),
            )
            return True
        except Exception:
            logger.exception("Failed to build make payment menu")
            return False
        finally:
            db.close()

    if msg == "ui::finance:pay-custom":
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="PAY_CUSTOM"),
        )
        client.send_text_message(message.sender_id, payment_custom_amount_prompt())
        return True

    if msg == "ui::request-refund":
        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        save_finance_action_session(
            finance_session_key,
            FinanceActionSessionState(pending_action="REFUND_REQUEST"),
        )
        client.send_text_message(message.sender_id, refund_request_prompt())
        return True

    if msg == "ui::my-account":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="My Account",
            body_text="Select a section",
            button_text="Open",
            sections=build_my_account_sections(),
        )
        return True

    if msg == "ui::society":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="Society",
            body_text="Select a section",
            button_text="Open",
            sections=build_society_sections(),
        )
        return True

    if msg == "ui::join-society":
        session_key = build_join_session_key(sender_id=message.sender_id)
        save_join_session(
            session_key,
            JoinSessionState(pending_action="JOIN"),
        )
        client.send_text_message(message.sender_id, "Please enter join code")
        return True

    if msg == "ui::finance":
        client.send_list_message(
            to_phone=message.sender_id,
            header_text="Finance",
            body_text="Select a section",
            button_text="Open",
            sections=build_finance_sections(),
        )
        return True

    if msg == "ui::reports":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Reports",
                body_text="Select a report action",
                button_text="Open",
                sections=build_reports_sections(
                    is_committee=_is_committee_member(
                        db=db,
                        sender_id=canonical_sender,
                        external_user_id=message.sender_id,
                    )
                ),
            )
            return True
        finally:
            db.close()

    if msg == "ui::administration":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            if not _is_committee_member(db=db, sender_id=canonical_sender, external_user_id=message.sender_id):
                client.send_text_message(message.sender_id, "Access restricted.")
                return True
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Administration",
                body_text="Select a section",
                button_text="Open",
                sections=build_committee_sections(),
            )
            return True
        finally:
            db.close()

    if msg == "ui::administration:more":
        db = SessionLocal()
        try:
            canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
            if not _is_committee_member(db=db, sender_id=canonical_sender, external_user_id=message.sender_id):
                client.send_text_message(message.sender_id, "Access restricted.")
                return True
            client.send_list_message(
                to_phone=message.sender_id,
                header_text="Administration",
                body_text="More actions",
                button_text="Open",
                sections=build_committee_more_sections(),
            )
            return True
        finally:
            db.close()

    if msg == "ui::approve-user":
        client.send_text_message(message.sender_id, "approve user REQ-001")
        return True

    if msg == "ui::approve-payment":
        client.send_text_message(message.sender_id, "approve payment PAY-001")
        return True

    if msg == "ui::approve-refund":
        client.send_text_message(message.sender_id, "approve refund REF-001")
        return True

    return False

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


def _build_reports_list_sections(
    options: list[dict],
    *,
    page_index: int = 0,
    page_size: int = WHATSAPP_LIST_MAX_ROWS,
    include_more_row: bool = False,
) -> list[dict]:
    effective_page_size = _report_page_option_limit(total_options=len(options), page_size=page_size) if include_more_row else page_size
    option_pages = _chunk_report_options(options, page_size=effective_page_size)
    if not option_pages:
        return []

    normalized_page = _normalize_report_page(page_index=page_index, total_pages=len(option_pages))
    page_options = option_pages[normalized_page]

    grouped: dict[str, list[dict]] = {}
    for option in page_options:
        grouped.setdefault(option["category"], []).append(option)

    sections: list[dict] = []
    for category in sorted(grouped):
        rows = [
            {
                "id": f"export::{option['command_key']}",
                "title": option["label"][:24],
                "description": f"Category: {category.title()} · PDF",
            }
            for option in grouped[category]
        ]
        if rows:
            sections.append({"title": category.title(), "rows": rows})

    if include_more_row:
        sections.append(
            {
                "title": "More",
                "rows": [
                    {
                        "id": WHATSAPP_MORE_REPORTS_ROW_ID,
                        "title": "More reports",
                        "description": "Show the next page of reports",
                    }
                ],
            }
        )
    return sections


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
        if _try_handle_ui_message(client=client, message=message):
            logger.info(
                "WhatsApp premium UI response sent",
                extra={"sender_id": message.sender_id, "message_id": message.metadata.get("message_id")},
            )
            continue

        join_session_key = build_join_session_key(sender_id=message.sender_id)
        join_session = get_join_session(join_session_key)
        if join_session and join_session.pending_action == "JOIN":
            user_text = message.text.strip()
            db = SessionLocal()
            try:
                if not join_session.join_code:
                    society = JoinCodeService.get_society_by_join_code(db, user_text)
                    if not society:
                        client.send_text_message(message.sender_id, "❌ Invalid join code.")
                        continue
                    save_join_session(
                        join_session_key,
                        JoinSessionState(pending_action="JOIN", join_code=user_text),
                    )
                    client.send_text_message(message.sender_id, "Please enter flat number")
                    continue

                canonical_sender = message.metadata.get("canonical_sender_id") or message.sender_id
                synthetic_command = f"join {join_session.join_code} {user_text}"
                reply_text = handle_inbound_message(
                    InboundMessage(
                        channel=message.channel,
                        sender_id=message.sender_id,
                        display_name=message.display_name,
                        text=synthetic_command,
                        metadata={**message.metadata, "canonical_sender_id": canonical_sender},
                    )
                )
                clear_join_session(join_session_key)
                send_response = client.send_text_message(message.sender_id, reply_text)
                logger.info(
                    "WhatsApp text reply sent from conversational join flow",
                    extra={
                        "sender_id": message.sender_id,
                        "message_id": message.metadata.get("message_id"),
                        "response_keys": sorted(send_response.keys()),
                    },
                )
                continue
            finally:
                db.close()

        finance_session_key = build_finance_action_session_key(sender_id=message.sender_id)
        finance_session = get_finance_action_session(finance_session_key)
        normalized_text = (message.text or "").strip().lower()

        if finance_session and normalized_text == "cancel":
            clear_finance_action_session(finance_session_key)
            send_response = client.send_text_message(message.sender_id, "Cancelled. You can use menu to start again.")
            logger.info(
                "WhatsApp finance pending action cancelled",
                extra={
                    "sender_id": message.sender_id,
                    "message_id": message.metadata.get("message_id"),
                    "response_keys": sorted(send_response.keys()),
                },
            )
            continue

        if finance_session and finance_session.pending_action == "PAY_CUSTOM" and normalized_text.isdigit():
            synthetic_command = f"pay {normalized_text}"
            inbound = InboundMessage(
                channel=message.channel,
                sender_id=message.sender_id,
                display_name=message.display_name,
                text=synthetic_command,
                metadata=message.metadata,
            )
            reply_text = handle_inbound_message(inbound)
            clear_finance_action_session(finance_session_key)
            send_response = client.send_text_message(message.sender_id, reply_text)
            logger.info(
                "WhatsApp finance pay-custom conversational reply sent",
                extra={
                    "sender_id": message.sender_id,
                    "message_id": message.metadata.get("message_id"),
                    "response_keys": sorted(send_response.keys()),
                },
            )
            continue

        if finance_session and finance_session.pending_action == "REFUND_REQUEST" and normalized_text:
            synthetic_command = f"refund {message.text.strip()}"
            inbound = InboundMessage(
                channel=message.channel,
                sender_id=message.sender_id,
                display_name=message.display_name,
                text=synthetic_command,
                metadata=message.metadata,
            )
            reply_text = handle_inbound_message(inbound)
            clear_finance_action_session(finance_session_key)
            send_response = client.send_text_message(message.sender_id, reply_text)
            logger.info(
                "WhatsApp finance refund conversational reply sent",
                extra={
                    "sender_id": message.sender_id,
                    "message_id": message.metadata.get("message_id"),
                    "response_keys": sorted(send_response.keys()),
                },
            )
            continue

        intent = detect_whatsapp_intent(message.text)
        requested_more_reports = message.text.strip().lower() == WHATSAPP_MORE_REPORTS_ROW_ID
        if intent == "REPORT_OPTIONS" or requested_more_reports:
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

                session_key = build_export_session_key(
                    member_id=str(member.id),
                    sender_id=canonical_sender,
                )
                session = get_export_session(session_key)
                requested_next_page = requested_more_reports
                current_page = session.current_page if session else 0
                include_more_row = len(report_options) > WHATSAPP_LIST_MAX_ROWS
                option_pages = _chunk_report_options(
                    report_options,
                    page_size=_report_page_option_limit(
                        total_options=len(report_options),
                        page_size=WHATSAPP_LIST_MAX_ROWS,
                    )
                    if include_more_row
                    else WHATSAPP_LIST_MAX_ROWS,
                )

                if requested_next_page and option_pages:
                    current_page = _next_report_page(current_page=current_page, total_pages=len(option_pages))
                else:
                    current_page = _normalize_report_page(
                        page_index=current_page,
                        total_pages=len(option_pages),
                    )

                save_export_session(
                    session_key,
                    ExportSessionState(options=report_options, current_page=current_page),
                )

                sections = _build_reports_list_sections(
                    report_options,
                    page_index=current_page,
                    include_more_row=include_more_row,
                )
                if sections:
                    list_response = client.send_list_message(
                        to_phone=message.sender_id,
                        header_text="Reports",
                        body_text=(
                            "Pick a report category and tap a report. "
                            "I will instantly generate the PDF and send it here."
                        ),
                        button_text="Choose Report",
                        sections=sections,
                        footer_text="Tip: You can also type report options anytime.",
                    )
                    logger.info(
                        "WhatsApp reports interactive list sent",
                        extra={
                            "sender_id": message.sender_id,
                            "message_id": message.metadata.get("message_id"),
                            "response_keys": sorted(list_response.keys()),
                            "page_index": current_page,
                        },
                    )
                    continue
            except Exception:
                logger.exception("Failed to send reports interactive list")
            finally:
                db.close()

        reply_text = handle_inbound_message(message)
        try:
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
