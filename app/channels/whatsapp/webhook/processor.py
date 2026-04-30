from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import requests

from app.channels.core.audit_events import persist_audit_events
from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.channels.core.webhook_runtime import WebhookRuntimeStrategy, build_exception_event, build_processing_completed_event, claim_idempotency_key, mark_envelope_status
from app.channels.whatsapp.client import WhatsAppRetryableError, get_whatsapp_client
from app.channels.whatsapp.report_flow import handle_report_flow
from app.channels.whatsapp.response_templates import INVALID_INPUT_METADATA_KEY
from app.channels.whatsapp.session_flows import handle_session_flow
from app.channels.whatsapp.ui_router import _button_row, _try_handle_ui_message
from app.db.session import SessionLocal
from app.utils.channel_audit_service import AuditTransport
from app.utils.operational_metrics import increment_counter
from app.utils.security_logging import log_security_event
from app.utils.logger import logger
from .retry import MAX_RETRY_ATTEMPTS, InMemoryRetryQueue, schedule_retry


@dataclass
class Processed:
    status: str = "processed"


@dataclass
class Queued:
    status: str = "queued"


@dataclass
class Ignored:
    status: str = "ignored"


@dataclass
class Failed:
    status: str = "failed"


class _WhatsAppRuntimeStrategy(WebhookRuntimeStrategy):
    channel = "whatsapp"
    def get_message_id(self, message: InboundMessage): return str(message.metadata.get("message_id")) if message.metadata.get("message_id") is not None else None
    def get_update_id(self, message: InboundMessage): return str(message.metadata.get("update_id")) if message.metadata.get("update_id") is not None else None
    def get_chat_id_or_phone(self, message: InboundMessage): return str(message.sender_id)
    def get_external_user_id(self, message: InboundMessage): return str(message.sender_id)
    def get_idempotency_key(self, *, message_id: str | None, update_id: str | None): return f"message:{message_id}" if message_id else (f"update:{update_id}" if update_id else None)


_RUNTIME = _WhatsAppRuntimeStrategy()
RETRY_QUEUE = InMemoryRetryQueue()


def process_envelope(*, envelope_id: str, payload_dict: dict, inbound_messages: list[InboundMessage], enforce_idempotency: bool = True, retry_attempt: int = 0):
    mark_envelope_status(envelope_id=envelope_id, status="processing", session_factory=SessionLocal)
    if not inbound_messages:
        mark_envelope_status(envelope_id=envelope_id, status="ignored", session_factory=SessionLocal)
        return Ignored()
    client = get_whatsapp_client()
    had_recoverable = False
    had_nonrecoverable = False
    for message in inbound_messages:
        trace_id = str(uuid4())
        correlation_id = str(message.metadata.get("message_id") or message.metadata.get("conversation_id") or message.metadata.get("timestamp") or "") or None
        if enforce_idempotency and not claim_idempotency_key(strategy=_RUNTIME, message=message, session_factory=SessionLocal):
            persist_audit_events([build_processing_completed_event(strategy=_RUNTIME, trace_id=trace_id, correlation_id=correlation_id, message=message, status="duplicate_skipped")])
            continue
        try:
            handled = _try_handle_ui_message(client=client, message=message) or handle_session_flow(client=client, message=message) or handle_report_flow(client=client, message=message)
            if not handled:
                reply = handle_inbound_message(message, trace_id=trace_id, correlation_id=correlation_id)
                invalid_contract = message.metadata.get(INVALID_INPUT_METADATA_KEY)
                if isinstance(invalid_contract, dict) and invalid_contract.get("response_type") == "invalid_input":
                    ctas = invalid_contract.get("ctas") or []
                    buttons = [_button_row(c.get("id", "menu"), c.get("label", "Main Menu")) for c in ctas[:3]] or [_button_row("menu", "Main Menu"), _button_row("help", "Help")]
                    client.send_button_message(to_phone=message.sender_id, header_text="Invalid command", body_text=reply, buttons=buttons, trace_id=trace_id, correlation_id=correlation_id)
                else:
                    client.send_text_message(to_phone=message.sender_id, body=reply, trace_id=trace_id, correlation_id=correlation_id)
            persist_audit_events([build_processing_completed_event(strategy=_RUNTIME, trace_id=trace_id, correlation_id=correlation_id, message=message)])
        except Exception as exc:
            recoverable = isinstance(exc, (WhatsAppRetryableError, requests.RequestException, TimeoutError, ConnectionError))
            if recoverable and retry_attempt < MAX_RETRY_ATTEMPTS:
                had_recoverable = True
                schedule_retry(RETRY_QUEUE, envelope_id=envelope_id, payload_dict=payload_dict, attempt=retry_attempt + 1)
            else:
                had_nonrecoverable = True
                increment_counter("whatsapp.webhook.failed_processing")
                log_security_event(logger, event="repeated_webhook_failures", actor_id=str(message.sender_id), action="process_whatsapp_envelope", resource_id=envelope_id, method="webhook", result="failed", reason_code=type(exc).__name__, trace_id=trace_id, retry_attempt=retry_attempt, max_retry_attempts=MAX_RETRY_ATTEMPTS)
                AuditTransport(channel="whatsapp").persist_dead_letter(trace_id=trace_id, correlation_id=correlation_id, recipient=str(message.sender_id), outbound_payload_metadata={"envelope_payload": payload_dict, "message_metadata": dict(message.metadata), "sender_id": message.sender_id}, exc=exc)
            persist_audit_events([build_exception_event(strategy=_RUNTIME, trace_id=trace_id, correlation_id=correlation_id, message=message, exc=exc)])
    if had_nonrecoverable:
        mark_envelope_status(envelope_id=envelope_id, status="failed", session_factory=SessionLocal)
        return Failed()
    if had_recoverable:
        mark_envelope_status(envelope_id=envelope_id, status="queued", session_factory=SessionLocal)
        return Queued()
    mark_envelope_status(envelope_id=envelope_id, status="processed", session_factory=SessionLocal)
    return Processed()
