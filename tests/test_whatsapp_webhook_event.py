import asyncio

from app.api.whatsapp import whatsapp_webhook_event
from app.channels.core.types import InboundMessage


class StubRequest:
    def __init__(self, payload: dict):
        self._payload = payload
        self.headers = {"X-Hub-Signature-256": "sha256=test"}

    async def body(self):
        return b'{"entry": []}'

    async def json(self):
        return self._payload


def test_whatsapp_webhook_event_handles_send_text_errors(monkeypatch):
    sent_attempts = []

    class StubWhatsAppClient:
        def send_text_message(self, to_phone: str, body: str):
            sent_attempts.append((to_phone, body))
            raise RuntimeError("send failed")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000000",
        display_name="Jane",
        text="help",
        metadata={"message_id": "wamid.1"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.detect_intent", lambda message: "HELP")
    monkeypatch.setattr("app.api.whatsapp.handle_inbound_message", lambda message: "reply")
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert sent_attempts == [("919999000000", "reply")]
