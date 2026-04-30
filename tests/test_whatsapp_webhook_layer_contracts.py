import pytest
from fastapi import HTTPException

from app.channels.whatsapp.webhook import auth, limits, processor
from app.channels.core.types import InboundMessage

pytestmark = [pytest.mark.integration]


def test_auth_signature_fail(monkeypatch):
    monkeypatch.setattr(auth.settings, "WHATSAPP_APP_SECRET", "secret")
    with pytest.raises(HTTPException) as exc:
        auth.verify_signature(b"{}", "sha256=bad")
    assert exc.value.status_code == 401


def test_rate_limit_contract(monkeypatch):
    monkeypatch.setattr(limits.settings, "WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(limits.settings, "WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(limits, "increment_sliding_window", lambda **_: 2)
    with pytest.raises(HTTPException) as exc:
        limits.enforce_webhook_rate_limit(type("R", (), {"headers": {"x-forwarded-for": "1.1.1.1"}, "client": None})())
    assert exc.value.status_code == 429


def test_processor_duplicate_ignored(monkeypatch):
    inbound = InboundMessage(channel="whatsapp", sender_id="1", display_name="a", text="hello", metadata={"message_id": "m1"})
    monkeypatch.setattr(processor, "claim_idempotency_key", lambda **_: False)
    monkeypatch.setattr(processor, "persist_audit_events", lambda events: 1)
    marks = []
    monkeypatch.setattr(processor, "mark_envelope_status", lambda **kwargs: marks.append(kwargs["status"]))
    monkeypatch.setattr(processor, "get_whatsapp_client", lambda: object())
    result = processor.process_envelope(envelope_id="e1", payload_dict={}, inbound_messages=[inbound], enforce_idempotency=True)
    assert result.status == "processed"
    assert marks == ["processing", "processed"]
