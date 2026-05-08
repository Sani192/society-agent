import asyncio
import pytest
from fastapi import HTTPException

from app.channels.whatsapp.redaction import redact_whatsapp_payload
from app.api.whatsapp.webhook import whatsapp_webhook_event


class _StubReq:
    def __init__(self, body: bytes, content_length: str):
        self._body = body
        self.headers = {"content-length": content_length, "x-hub-signature-256": "sig"}
        self.client = type("C", (), {"host": "127.0.0.1"})()

    async def body(self):
        return self._body


def test_redaction_masks_phone_tokens_and_text():
    payload = {
        "from": "919876543210",
        "text": "hello there",
        "access_token": "EAABBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "nested": {"body": "free text", "note": "call me at +1 202-555-0100"},
    }
    redacted = redact_whatsapp_payload(payload)
    assert redacted["from"] == "[REDACTED_PHONE]"
    assert redacted["text"] == "[REDACTED_TEXT]"
    assert redacted["access_token"] == "[REDACTED_TOKEN]"
    assert redacted["nested"]["body"] == "[REDACTED_TEXT]"
    assert "202-555" not in redacted["nested"]["note"]


def test_whatsapp_webhook_rejects_oversized_payload(monkeypatch):
    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._enforce_webhook_rate_limit", lambda _request: None)

    req = _StubReq(body=b"{}", content_length="999999")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(whatsapp_webhook_event(req))
    assert exc_info.value.status_code == 413
