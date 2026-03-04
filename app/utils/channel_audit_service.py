#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transport-level channel audit logging for outbound provider calls."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from app.channels.core.audit_events import (
    ChannelName,
    EventKind,
    NormalizedAuditEvent,
    persist_audit_events,
    summarize_exception_stack,
)
from app.channels.core.audit_security import sanitize_payload
from app.db.models import ChannelDeadLetter
from app.db.session import SessionLocal
from app.utils.channel_response_parser import parse_provider_error_from_exception
from app.utils.logger import logger


class AuditTransport:
    def __init__(self, *, channel: str):
        if channel not in {"whatsapp", "telegram"}:
            raise ValueError(f"Unsupported channel for AuditTransport: {channel}")
        self.channel = cast(ChannelName, channel)

    def _persist_event(self, event: NormalizedAuditEvent) -> None:
        persist_audit_events([event])

    def persist_dead_letter(
        self,
        *,
        trace_id: str | None,
        correlation_id: str | None,
        recipient: str,
        outbound_payload_metadata: dict[str, Any] | None,
        exc: Exception,
    ) -> None:
        if not trace_id:
            return

        db = SessionLocal()
        try:
            db.add(
                ChannelDeadLetter(
                    trace_id=trace_id,
                    correlation_id=correlation_id,
                    channel=self.channel,
                    recipient=recipient,
                    payload_json=sanitize_payload(outbound_payload_metadata or {}),
                    error_class=type(exc).__name__,
                    error_message=str(exc),
                    stack_summary=summarize_exception_stack(exc),
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to persist channel dead letter",
                extra={"channel": self.channel, "trace_id": trace_id, "recipient": recipient},
            )
        finally:
            db.close()

    def _build_event(self, *, event_type: EventKind, trace_id: str | None, correlation_id: str | None, recipient: str, payload_json: dict[str, Any] | None = None, http_status: int | None = None, provider_message_id: str | None = None, provider_error_code: str | None = None, provider_error_message: str | None = None) -> NormalizedAuditEvent:
        payload = sanitize_payload(payload_json or {})
        payload.update({"trace_id": trace_id, "correlation_id": correlation_id, "http_status": http_status})
        return NormalizedAuditEvent(
            channel=self.channel,
            direction="outbound",
            event_type=event_type,
            provider_message_id=provider_message_id,
            chat_id_or_phone=recipient,
            external_user_id=recipient,
            payload_json=payload,
            provider_error_code=provider_error_code,
            provider_error_message=provider_error_message,
            occurred_at=datetime.now(timezone.utc),
        )

    def log_send_attempt(
        self,
        *,
        trace_id: str | None,
        correlation_id: str | None,
        recipient: str,
        outbound_payload_metadata: dict[str, Any],
    ) -> None:
        self._persist_event(
            self._build_event(
                event_type="send_attempt",
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=recipient,
                payload_json={"outbound": outbound_payload_metadata},
            )
        )

    def log_send_result(
        self,
        *,
        trace_id: str | None,
        correlation_id: str | None,
        recipient: str,
        status_code: int | None,
        provider_message_id: str | None,
        response_payload_snapshot: dict[str, Any] | None,
        success: bool,
        provider_error_code: str | None = None,
        provider_error_message: str | None = None,
    ) -> None:
        self._persist_event(
            self._build_event(
                event_type="send_result",
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=recipient,
                payload_json={"success": success, "response": response_payload_snapshot or {}},
                http_status=status_code,
                provider_message_id=provider_message_id,
                provider_error_code=provider_error_code,
                provider_error_message=provider_error_message,
            )
        )

    def log_exception(
        self,
        *,
        trace_id: str | None,
        correlation_id: str | None,
        recipient: str,
        exc: Exception,
        outbound_payload_metadata: dict[str, Any] | None = None,
    ) -> None:
        parsed_error = parse_provider_error_from_exception(channel=self.channel, exc=exc)
        self._persist_event(
            self._build_event(
                event_type="exception",
                trace_id=trace_id,
                correlation_id=correlation_id,
                recipient=recipient,
                payload_json={"exception_type": type(exc).__name__},
                http_status=parsed_error.get("http_status"),
                provider_error_code=parsed_error.get("provider_error_code"),
                provider_error_message=parsed_error.get("provider_error_message"),
            )
        )
        self.persist_dead_letter(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=recipient,
            outbound_payload_metadata=outbound_payload_metadata or {"transport": "provider_send"},
            exc=exc,
        )
        self.log_send_result(
            trace_id=trace_id,
            correlation_id=correlation_id,
            recipient=recipient,
            status_code=parsed_error.get("http_status"),
            provider_message_id=None,
            response_payload_snapshot={},
            success=False,
            provider_error_code=parsed_error.get("provider_error_code"),
            provider_error_message=parsed_error.get("provider_error_message"),
        )

