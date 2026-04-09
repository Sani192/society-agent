from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.whatsapp.webhook as webhook_api
from app.config import settings


class StubRequest:
    def __init__(self, ip: str = "203.0.113.10"):
        self.headers = {"x-forwarded-for": ip}
        self.client = SimpleNamespace(host=ip)


def test_enforce_webhook_rate_limit_blocks_and_audits(monkeypatch):
    events = []
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 3)
    monkeypatch.setattr(webhook_api, "_increment_sliding_window", lambda **_kwargs: 4)
    monkeypatch.setattr(webhook_api, "persist_audit_events", lambda batch: events.extend(batch) or len(batch))

    with pytest.raises(HTTPException) as exc_info:
        webhook_api._enforce_webhook_rate_limit(StubRequest())

    assert exc_info.value.status_code == 429
    assert events
    event = events[-1]
    assert event.provider_error_code == "WHATSAPP_WEBHOOK_IP_RATE_LIMIT_EXCEEDED"
    assert event.payload_json["reason_code"] == "WHATSAPP_WEBHOOK_IP_RATE_LIMIT_EXCEEDED"
    assert event.payload_json["limit_scope"] == "ip"


def test_enforce_sender_spam_limit_blocks_and_audits(monkeypatch):
    events = []
    monkeypatch.setattr(settings, "WHATSAPP_SENDER_SPAM_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "WHATSAPP_SENDER_SPAM_MAX_MESSAGES", 2)
    monkeypatch.setattr(webhook_api, "_increment_sliding_window", lambda **_kwargs: 3)
    monkeypatch.setattr(webhook_api, "persist_audit_events", lambda batch: events.extend(batch) or len(batch))

    with pytest.raises(HTTPException) as exc_info:
        webhook_api._enforce_sender_spam_limit("9191919191")

    assert exc_info.value.status_code == 429
    assert events
    event = events[-1]
    assert event.provider_error_code == "WHATSAPP_SENDER_SPAM_RATE_LIMIT_EXCEEDED"
    assert event.payload_json["reason_code"] == "WHATSAPP_SENDER_SPAM_RATE_LIMIT_EXCEEDED"
    assert event.payload_json["limit_scope"] == "sender"


def test_enforce_webhook_rate_limit_fails_open_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_RATE_LIMIT_MAX_REQUESTS", 3)

    def _raise_backend_error(**_kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr(webhook_api, "_increment_sliding_window", _raise_backend_error)

    webhook_api._enforce_webhook_rate_limit(StubRequest())
