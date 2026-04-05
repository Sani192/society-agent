#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WhatsApp webhook HTTP handlers and orchestration."""

import hashlib
import hmac
import json
import heapq
from typing import NoReturn, cast
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response, status
import requests  # type: ignore[import-untyped]

from app.api.contracts import ErrorResponse, WebhookStatusResponse, WhatsAppWebhookPayload
from app.channels.core.handler import handle_inbound_message
from app.channels.core.audit_events import (
    NormalizedAuditEvent,
    persist_audit_events,
)
from app.channels.core.types import InboundMessage
from app.channels.core.webhook_runtime import (
    WebhookRuntimeStrategy,
    build_exception_event,
    build_processing_completed_event,
    claim_idempotency_key,
    hash_payload,
    mark_envelope_status,
    persist_inbound_envelope,
)
from app.channels.whatsapp.adapter import (
    parse_webhook_events,
    parse_webhook_payload,
    to_normalized_audit_events,
)
from app.channels.whatsapp.client import get_whatsapp_client
from app.channels.whatsapp.client import WhatsAppRetryableError
from app.channels.whatsapp.constants import (
    WHATSAPP_SIGNATURE_HEADER,
    WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE,
)
from app.channels.whatsapp.report_flow import handle_report_flow
from app.channels.whatsapp.config_validation import (
    validate_whatsapp_runtime_config,
    validate_whatsapp_verification_config,
)
from app.channels.whatsapp.session_flows import handle_session_flow
from app.channels.whatsapp.ui_router import (
    WHATSAPP_LIST_MAX_ROWS,
    _button_row,
    _try_handle_ui_message,
)
from app.config import settings
from app.utils.channel_audit_service import AuditTransport
from app.utils.logger import logger
from app.utils.operational_metrics import increment_counter
from app.channels.whatsapp.response_templates import INVALID_INPUT_METADATA_KEY

from app.db.session import SessionLocal

router = APIRouter()

MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_SECONDS = 2
MAX_RETRY_BACKOFF_SECONDS = 60
_RETRY_QUEUE: list[tuple[float, str, dict, int]] = []


class _WhatsAppRuntimeStrategy(WebhookRuntimeStrategy):
    channel = "whatsapp"

    def get_message_id(self, message: InboundMessage) -> str | None:
        value = message.metadata.get("message_id")
        return str(value) if value is not None else None

    def get_update_id(self, message: InboundMessage) -> str | None:
        value = message.metadata.get("update_id")
        return str(value) if value is not None else None

    def get_chat_id_or_phone(self, message: InboundMessage) -> str | None:
        return str(message.sender_id)

    def get_external_user_id(self, message: InboundMessage) -> str | None:
        return str(message.sender_id)

    def get_idempotency_key(self, *, message_id: str | None, update_id: str | None) -> str | None:
        if message_id:
            return f"message:{message_id}"
        if update_id:
            return f"update:{update_id}"
        return None


_RUNTIME_STRATEGY = _WhatsAppRuntimeStrategy()



def _ensure_channel_enabled() -> None:
    if not settings.WHATSAPP_ENABLED:
        logger.info("WhatsApp channel is disabled")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp channel is disabled",
        )
    validation = validate_whatsapp_runtime_config()
    if not validation.complete:
        _raise_config_unavailable(context="message processing", missing_fields=validation.missing_fields)


def _raise_config_unavailable(*, context: str, missing_fields: tuple[str, ...]) -> NoReturn:
    increment_counter("whatsapp.webhook.config_failure")
    logger.error(
        "WhatsApp configuration is incomplete",
        extra={
            "event": "whatsapp_config_validation_failure",
            "context": context,
            "missing_fields": list(missing_fields),
        },
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "WhatsApp channel configuration is incomplete for "
            f"{context}. Set: {', '.join(missing_fields)}"
        ),
    )


def _ensure_verification_config_ready() -> None:
    validation = validate_whatsapp_verification_config()
    if not validation.complete:
        _raise_config_unavailable(context="webhook verification", missing_fields=validation.missing_fields)


def _verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    logger.info("Verifying WhatsApp webhook signature")
    app_secret = settings.WHATSAPP_APP_SECRET
    if not app_secret:
        _raise_config_unavailable(
            context="signature verification",
            missing_fields=("WHATSAPP_APP_SECRET",),
        )
    if not signature_header:
        logger.warning("WhatsApp webhook signature header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature header",
        )
    expected_hash = hmac.new(
        app_secret.encode("utf-8"),
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
    return hash_payload(raw_body)


def _persist_inbound_envelope(*, payload_hash: str, payload: dict) -> str:
    return persist_inbound_envelope(
        channel="whatsapp",
        payload_hash=payload_hash,
        payload=payload,
        session_factory=SessionLocal,
    )


def _mark_envelope_status(*, envelope_id: str, status: str) -> None:
    mark_envelope_status(envelope_id=envelope_id, status=status, session_factory=SessionLocal)


def _claim_idempotency_key(*, channel: str, message_id: str | None, update_id: str | None) -> bool:
    message = InboundMessage(
        channel=channel,
        sender_id="system",
        display_name="system",
        text="",
        metadata={"message_id": message_id, "update_id": update_id},
    )
    return claim_idempotency_key(
        strategy=_RUNTIME_STRATEGY,
        message=message,
        session_factory=SessionLocal,
    )


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
    return build_processing_completed_event(
        strategy=_RUNTIME_STRATEGY,
        trace_id=trace_id,
        correlation_id=correlation_id,
        message=message,
        status=status,
    )


def _build_exception_event(*, trace_id: str, correlation_id: str | None, message, exc: Exception) -> NormalizedAuditEvent:
    return build_exception_event(
        strategy=_RUNTIME_STRATEGY,
        trace_id=trace_id,
        correlation_id=correlation_id,
        message=message,
        exc=exc,
    )


def _is_recoverable_exception(exc: Exception) -> bool:
    return isinstance(exc, (WhatsAppRetryableError, requests.RequestException, TimeoutError, ConnectionError))


def _push_dead_letter(*, trace_id: str, correlation_id: str | None, message, payload_dict: dict, exc: Exception) -> None:
    AuditTransport(channel="whatsapp").persist_dead_letter(
        trace_id=trace_id,
        correlation_id=correlation_id,
        recipient=str(message.sender_id),
        outbound_payload_metadata={
            "envelope_payload": payload_dict,
            "message_metadata": dict(message.metadata),
            "sender_id": message.sender_id,
        },
        exc=exc,
    )


def _schedule_retry(*, envelope_id: str, payload_dict: dict, attempt: int) -> None:
    backoff_seconds = min(RETRY_BASE_SECONDS * (2 ** max(attempt - 1, 0)), MAX_RETRY_BACKOFF_SECONDS)
    run_after = datetime.now(timezone.utc).timestamp() + float(backoff_seconds)
    heapq.heappush(_RETRY_QUEUE, (run_after, envelope_id, payload_dict, attempt))
    increment_counter("whatsapp.webhook.retries_scheduled")


def process_whatsapp_retry_queue() -> int:
    processed = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    while _RETRY_QUEUE and _RETRY_QUEUE[0][0] <= now_ts:
        _, envelope_id, payload_dict, attempt = heapq.heappop(_RETRY_QUEUE)
        process_whatsapp_envelope(
            envelope_id=envelope_id,
            payload_dict=payload_dict,
            enforce_idempotency=False,
            retry_attempt=attempt,
        )
        processed += 1
    return processed


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
    _ensure_verification_config_ready()
    if (
        hub_mode == WHATSAPP_WEBHOOK_VERIFY_MODE_SUBSCRIBE
        and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN
    ):
        return Response(content=hub_challenge or "", media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def process_whatsapp_envelope(*, envelope_id: str, payload_dict: dict, enforce_idempotency: bool = True, retry_attempt: int = 0) -> None:
    _mark_envelope_status(envelope_id=envelope_id, status="processing")
    inbound_messages = parse_webhook_payload(payload_dict)
    if not inbound_messages:
        logger.info("WhatsApp webhook received with no inbound messages")
        _mark_envelope_status(envelope_id=envelope_id, status="ignored")
        return

    client = get_whatsapp_client()
    had_nonrecoverable_failure = False
    had_recoverable_failure = False
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
                reply_text = handle_inbound_message(
                    message,
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                )
                invalid_contract = message.metadata.get(INVALID_INPUT_METADATA_KEY)
                if isinstance(invalid_contract, dict) and invalid_contract.get("response_type") == "invalid_input":
                    cta_rows = invalid_contract.get("ctas") or []
                    buttons = [_button_row(cta.get("id", "menu"), cta.get("label", "Main Menu")) for cta in cta_rows[:3]]
                    if not buttons:
                        buttons = [_button_row("menu", "Main Menu"), _button_row("help", "Help")]
                    send_response = client.send_button_message(
                        to_phone=message.sender_id,
                        header_text="Invalid command",
                        body_text=reply_text,
                        buttons=buttons,
                        trace_id=trace_id,
                        correlation_id=correlation_id_str,
                    )
                else:
                    send_response = client.send_text_message(
                        to_phone=message.sender_id,
                        body=reply_text,
                        trace_id=trace_id,
                        correlation_id=correlation_id_str,
                    )
                logger.info("WhatsApp text reply sent", extra={"response_keys": sorted(send_response.keys())})

            terminal_event = _build_processing_completed_event(
                trace_id=trace_id,
                correlation_id=correlation_id_str,
                message=message,
            )
        except Exception as exc:
            recoverable = _is_recoverable_exception(exc)
            if recoverable and retry_attempt < MAX_RETRY_ATTEMPTS:
                had_recoverable_failure = True
                _schedule_retry(
                    envelope_id=envelope_id,
                    payload_dict=payload_dict,
                    attempt=retry_attempt + 1,
                )
            else:
                had_nonrecoverable_failure = True
                increment_counter("whatsapp.webhook.failed_processing")
                _push_dead_letter(
                    trace_id=trace_id,
                    correlation_id=correlation_id_str,
                    message=message,
                    payload_dict=payload_dict,
                    exc=exc,
                )
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

    if had_nonrecoverable_failure:
        _mark_envelope_status(envelope_id=envelope_id, status="failed")
    elif had_recoverable_failure:
        _mark_envelope_status(envelope_id=envelope_id, status="queued")
    else:
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
