from __future__ import annotations

from datetime import datetime, timezone

from app.channels.core.audit_events import NormalizedAuditEvent


def build_webhook_received_event(*, payload_hash: str, payload: dict) -> NormalizedAuditEvent:
    return NormalizedAuditEvent(
        channel="whatsapp",
        direction="system",
        event_type="webhook_received",
        payload_json={
            "payload_hash": payload_hash,
            "selected": {
                "object": payload.get("object"),
                "entry_count": len(payload.get("entry") or []),
                "entry_ids": [entry.get("id") for entry in (payload.get("entry") or []) if isinstance(entry, dict)],
            },
        },
        occurred_at=datetime.now(timezone.utc),
    )
