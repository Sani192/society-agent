#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transport-level channel audit logging for outbound provider calls."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.models import ChannelMessageEvent
from app.db.session import SessionLocal
from app.utils.channel_response_parser import parse_provider_error_from_exception
from app.utils.logger import logger


class AuditTransport:
    def __init__(self, *, channel: str):
        self.channel = channel

    def _persist_event(self, event: ChannelMessageEvent) -> None:
        db = SessionLocal()
        try:
            db.add(event)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to persist transport audit event",
                extra={"channel": self.channel, "event_type": event.event_type},
            )
        finally:
            db.close()

    def _build_event(self, *, event_type: str, trace_id: str | None, correlation_id: str | None, recipient: str, payload_json: dict[str, Any] | None = None, http_status: int | None = None, provider_message_id: str | None = None, provider_error_code: str | None = None, provider_error_message: str | None = None) -> ChannelMessageEvent:
        return ChannelMessageEvent(
            trace_id=trace_id,
            correlation_id=correlation_id,
            channel=self.channel,
            direction="outbound",
            event_type=event_type,
            provider_message_id=provider_message_id,
            chat_id_or_phone=recipient,
            external_user_id=recipient,
            payload_json=payload_json,
            http_status=http_status,
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

