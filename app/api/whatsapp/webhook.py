#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WhatsApp webhook HTTP handlers and orchestration."""

import hashlib
import hmac
import json
from typing import cast
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.contracts import ErrorResponse, WebhookStatusResponse, WhatsAppWebhookPayload
from app.channels.core.handler import handle_inbound_message
from app.channels.core.audit_events import (
    NormalizedAuditEvent,
    persist_audit_events,
    summarize_exception_stack,
)
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
from app.db.models import InboundWebhookEnvelope, WebhookIdempotencyKey
from app.db.session import SessionLocal
from app.utils.logger import logger
from app.channels.whatsapp.response_templates import INVALID_INPUT_METADATA_KEY

router = APIRouter()



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


def _hash_payload(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _persist_inbound_envelope(*, payload_hash: str, payload: dict) -> str:
    db = SessionLocal()
    try:
        envelope = InboundWebhookEnvelope(
            channel="whatsapp",
            payload_json=payload,
            payload_hash=payload_hash,
            status="queued",
        )
        db.add(envelope)
        db.commit()
        db.refresh(envelope)
        return str(envelope.id)
    except Exception:
        getattr(db, "rollback", lambda: None)()
        logger.warning("Failed to persist WhatsApp envelope; continuing without envelope persistence")
        return f"transient-{uuid4()}"
    finally:
        db.close()


def _mark_envelope_status(*, envelope_id: str, status: str) -> None:
    db = SessionLocal()
    try:
        db.query(InboundWebhookEnvelope).filter(InboundWebhookEnvelope.id == envelope_id).update(
            {
                InboundWebhookEnvelope.status: status,
                InboundWebhookEnvelope.processed_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        db.commit()
    except Exception:
        getattr(db, "rollback", lambda: None)()
    finally:
        db.close()


def _claim_idempotency_key(*, channel: str, message_id: str | None, update_id: str | None) -> bool:
    if message_id:
        key = f"message:{message_id}"
    elif update_id:
        key = f"update:{update_id}"
    else:
        return True

    db = SessionLocal()
    try:
        db.add(
            WebhookIdempotencyKey(
                channel=channel,
                provider_message_id=message_id,
                provider_update_id=update_id,
                idempotency_key=key,
            )
        )
        db.commit()
        return True
    except IntegrityError:
        getattr(db, "rollback", lambda: None)()
        return False
    except Exception:
        getattr(db, "rollback", lambda: None)()
        logger.warning("Idempotency store unavailable; proceeding without dedupe", extra={"channel": channel})
        return True
    finally:
        db.close()


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


def _build_processing_completed_event(*, trace_id: str, correlation_id: str | None, message, status: str = "completed") -> NormalizedAuditEvent:
    return NormalizedAuditEvent(
        channel="whatsapp",
        direction="system",
        event_type="processing_completed",
        provider_message_id=(str(message.metadata.get("message_id")) if message.metadata.get("message_id") is not None else None),
        chat_id_or_phone=str(message.sender_id),
        external_user_id=str(message.sender_id),
        payload_json={"trace_id": trace_id, "correlation_id": correlation_id, "status": status},
        occurred_at=datetime.now(timezone.utc),
    )


def _build_exception_event(*, trace_id: str, correlation_id: str | None, message, exc: Exception) -> NormalizedAuditEvent:
    return NormalizedAuditEvent(
        channel="whatsapp",
        direction="system",
        event_type="exception",
        provider_message_id=(str(message.metadata.get("message_id")) if message.metadata.get("message_id") is not None else None),
        chat_id_or_phone=str(message.sender_id),
        external_user_id=str(message.sender_id),
        provider_error_code=type(exc).__name__,
        provider_error_message=str(exc),
        payload_json={
            "trace_id": trace_id,
            "correlation_id": correlation_id,
            "exception_class": type(exc).__name__,
            "exception_message": str(exc),
            "stack_summary": summarize_exception_stack(exc),
        },
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp verify token not configured",
        )
    if (
        hub_mode == WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE
        and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN
    ):
        return Response(content=hub_challenge or "", media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def process_whatsapp_envelope(*, envelope_id: str, payload_dict: dict, enforce_idempotency: bool = True) -> None:
    inbound_messages = parse_webhook_payload(payload_dict)
    if not inbound_messages:
        logger.info("WhatsApp webhook received with no inbound messages")
        _mark_envelope_status(envelope_id=envelope_id, status="ignored")
        return

    client = get_whatsapp_client()
    for message in inbound_messages:
        trace_id = str(uuid4())
        correlation_id = (
            message.metadata.get("message_id")
            or message.metadata.get("conversation_id")
            or message.metadata.get("timestamp")
        )
        correlation_id_str = str(correlation_id) if correlation_id is not None else None
        terminal_event: NormalizedAuditEvent | None = None
        message.metadata["trace_id"] = trace_id
        if correlation_id is not None:
            message.metadata["correlation_id"] = correlation_id_str

        if enforce_idempotency and not _claim_idempotency_key(
            channel="whatsapp",
            message_id=(str(message.metadata.get("message_id")) if message.metadata.get("message_id") is not None else None),
            update_id=(str(message.metadata.get("update_id")) if message.metadata.get("update_id") is not None else None),
        ):
            persist_audit_events([
                _build_processing_completed_event(
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                    message=message,
                    status="duplicate_skipped",
                )
            ])
            continue

        try:
            handled = False
            if _try_handle_ui_message(client=client, message=message):
                handled = True
            elif handle_session_flow(client=client, message=message):
                handled = True
            elif handle_report_flow(client=client, message=message):
                handled = True

            if not handled:
                try:
                    reply_text = handle_inbound_message(
                        message,
                        trace_id=trace_id,
                        correlation_id=correlation_id_str,
                    )
                except TypeError:
                    reply_text = handle_inbound_message(message)
                invalid_contract = message.metadata.get(INVALID_INPUT_METADATA_KEY)
                if isinstance(invalid_contract, dict) and invalid_contract.get("response_type") == "invalid_input":
                    cta_rows = invalid_contract.get("ctas") or []
                    buttons = [_button_row(cta.get("id", "menu"), cta.get("label", "Main Menu")) for cta in cta_rows[:3]]
                    if not buttons:
                        buttons = [_button_row("menu", "Main Menu"), _button_row("help", "Help")]
                    try:
                        send_response = client.send_button_message(
                            to_phone=message.sender_id,
                            header_text="Invalid command",
                            body_text=reply_text,
                            buttons=buttons,
                            trace_id=trace_id,
                            correlation_id=correlation_id_str,
                        )
                    except TypeError:
                        send_response = client.send_button_message(
                            to_phone=message.sender_id,
                            header_text="Invalid command",
                            body_text=reply_text,
                            buttons=buttons,
                        )
                else:
                    try:
                        send_response = client.send_text_message(
                            message.sender_id,
                            reply_text,
                            trace_id=trace_id,
                            correlation_id=correlation_id_str,
                        )
                    except TypeError:
                        send_response = client.send_text_message(message.sender_id, reply_text)
                logger.info("WhatsApp text reply sent", extra={"response_keys": sorted(send_response.keys())})

            terminal_event = _build_processing_completed_event(
                trace_id=trace_id,
                correlation_id=correlation_id_str,
                message=message,
            )
        except Exception as exc:
            terminal_event = _build_exception_event(
                trace_id=trace_id,
                correlation_id=correlation_id_str,
                message=message,
                exc=exc,
            )
        finally:
            if terminal_event is None:
                terminal_event = _build_processing_completed_event(
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                    message=message,
                    status="unknown",
                )
            persist_audit_events([terminal_event])

    _mark_envelope_status(envelope_id=envelope_id, status="processed")


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
async def whatsapp_webhook_event(request: Request, background_tasks: BackgroundTasks = cast(BackgroundTasks, None)) -> dict[str, str]:
    _ensure_channel_enabled()
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

    if not parse_webhook_payload(payload_dict):
        logger.info("WhatsApp webhook received with no inbound messages")
        return {"status": "ignored"}

    envelope_id = _persist_inbound_envelope(payload_hash=payload_hash, payload=payload_dict)
    if background_tasks is not None:
        background_tasks.add_task(process_whatsapp_envelope, envelope_id=envelope_id, payload_dict=payload_dict, enforce_idempotency=True)
    else:
        process_whatsapp_envelope(envelope_id=envelope_id, payload_dict=payload_dict, enforce_idempotency=False)

    return {"status": "ok"}
