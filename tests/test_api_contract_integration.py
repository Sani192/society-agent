from __future__ import annotations

import asyncio
import hashlib
import hmac

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.contracts import TelegramWebhookPayload, WhatsAppWebhookPayload
from app.api.health import health_check
from app.api.telegram import telegram_webhook_event
from app.api.whatsapp import whatsapp_webhook_event, whatsapp_webhook_verify


class StubRequest:
    def __init__(self, payload: dict, raw: bytes | None = None, signature: str | None = None):
        self._payload = payload
        self._raw = raw if raw is not None else b"{}"
        self.headers = {}
        if signature is not None:
            self.headers["X-Hub-Signature-256"] = signature

    async def body(self):
        return self._raw

    async def json(self):
        return self._payload


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_health_contract_success():
    response = health_check()
    assert response["status"] == "ok"
    assert response["message"]


def test_whatsapp_verify_success_validation_and_auth(monkeypatch):
    monkeypatch.setattr("app.api.whatsapp.settings.WHATSAPP_ENABLED", True)
    monkeypatch.setattr("app.api.whatsapp.settings.WHATSAPP_VERIFY_TOKEN", "verify-token")

    with pytest.raises(ValidationError):
        WhatsAppWebhookPayload.model_validate({"entry": "not-a-list"})

    with pytest.raises(HTTPException) as forbidden:
        whatsapp_webhook_verify(
            hub_mode="subscribe",
            hub_challenge="abc",
            hub_verify_token="wrong",
        )
    assert forbidden.value.status_code == 403

    success = whatsapp_webhook_verify(
        hub_mode="subscribe",
        hub_challenge="abc",
        hub_verify_token="verify-token",
    )
    assert success.body == b"abc"


def test_whatsapp_webhook_event_success_auth_and_retry(monkeypatch):
    monkeypatch.setattr("app.api.whatsapp.settings.WHATSAPP_ENABLED", True)
    monkeypatch.setattr("app.api.whatsapp.settings.WHATSAPP_APP_SECRET", "secret")
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [])

    body = b'{"object":"whatsapp_business_account","entry":[]}'
    payload = WhatsAppWebhookPayload.model_validate({"object": "whatsapp_business_account", "entry": []})

    first = asyncio.run(
        whatsapp_webhook_event(
            StubRequest(payload.model_dump(), raw=body, signature=_sign(body, "secret")),
        )
    )
    second = asyncio.run(
        whatsapp_webhook_event(
            StubRequest(payload.model_dump(), raw=body, signature=_sign(body, "secret")),
        )
    )
    assert first == {"status": "ignored"}
    assert second == {"status": "ignored"}

    with pytest.raises(HTTPException) as auth_error:
        asyncio.run(
            whatsapp_webhook_event(
                StubRequest(payload.model_dump(), raw=body, signature="sha256=bad"),
            )
        )
    assert auth_error.value.status_code == 401


def test_telegram_webhook_success_validation_auth_and_retry(monkeypatch):
    sent: list[tuple[str, str]] = []

    class StubClient:
        def send_text_message(self, chat_id: str, text: str):
            sent.append((chat_id, text))

    payload_data = {
        "update_id": 1001,
        "message": {
            "message_id": 55,
            "date": 1737000000,
            "text": "help",
            "chat": {"id": 123456, "type": "private"},
            "from": {"id": 999, "first_name": "Jane", "last_name": "Doe", "username": "janed"},
        },
    }

    with pytest.raises(ValidationError):
        TelegramWebhookPayload.model_validate({"message": {}})

    monkeypatch.setattr("app.api.telegram.settings.TELEGRAM_ENABLED", True)
    monkeypatch.setattr("app.api.telegram.settings.TELEGRAM_WEBHOOK_SECRET", "secret")
    monkeypatch.setattr("app.api.telegram.get_telegram_client", lambda: StubClient())
    monkeypatch.setattr("app.api.telegram.handle_inbound_message", lambda message: "reply")

    payload = TelegramWebhookPayload.model_validate(payload_data)
    request = StubRequest(payload.model_dump(), raw=b"{}")

    with pytest.raises(HTTPException) as forbidden:
        asyncio.run(telegram_webhook_event(request, None))
    assert forbidden.value.status_code == 403

    first = asyncio.run(telegram_webhook_event(request, "secret"))
    second = asyncio.run(telegram_webhook_event(request, "secret"))
    assert first == {"status": "ok"}
    assert second == {"status": "ok"}
    assert sent == [("123456", "reply"), ("123456", "reply")]
