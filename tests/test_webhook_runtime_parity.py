import pytest

from app.api import telegram as telegram_api
import app.api.whatsapp.webhook as whatsapp_webhook_api
from app.channels.core.types import InboundMessage


@pytest.mark.parametrize(
    ("channel_module", "inbound_message", "payload_dict"),
    [
        (
            telegram_api,
            InboundMessage(
                channel="telegram",
                sender_id="user-1",
                display_name="User",
                text="hello",
                metadata={"chat_id": "chat-1", "message_id": 7, "update_id": 77},
            ),
            {"update_id": 77},
        ),
        (
            whatsapp_webhook_api,
            InboundMessage(
                channel="whatsapp",
                sender_id="919199199199",
                display_name="User",
                text="hello",
                metadata={"message_id": "wamid.7"},
            ),
            {"entry": [{}]},
        ),
    ],
)
def test_channel_runtime_duplicate_lifecycle_parity(monkeypatch, channel_module, inbound_message, payload_dict):
    statuses: list[str] = []
    terminal_statuses: list[str] = []
    business_calls = {"handle": 0, "send": 0}

    class _StubClient:
        def send_text_message(self, *args, **kwargs):
            business_calls["send"] += 1
            return {"ok": True}

    monkeypatch.setattr(channel_module, "parse_webhook_payload", lambda _payload: [inbound_message])
    monkeypatch.setattr(channel_module, "_mark_envelope_status", lambda **kwargs: statuses.append(kwargs["status"]))

    seen = {"called": False}

    def _claim(**_kwargs):
        if seen["called"]:
            return False
        seen["called"] = True
        return True

    monkeypatch.setattr(channel_module, "_claim_idempotency_key", _claim)

    def _persist(events):
        for event in events:
            if event.event_type == "processing_completed":
                terminal_statuses.append((event.payload_json or {}).get("status"))
        return len(events)

    monkeypatch.setattr(channel_module, "persist_audit_events", _persist)

    def _handle(*_args, **_kwargs):
        business_calls["handle"] += 1
        return "ok"

    monkeypatch.setattr(channel_module, "handle_inbound_message", _handle)

    if channel_module is telegram_api:
        monkeypatch.setattr(channel_module, "get_telegram_client", lambda: _StubClient())
        channel_module.process_telegram_envelope(envelope_id="env-1", payload_dict=payload_dict, enforce_idempotency=True)
        channel_module.process_telegram_envelope(envelope_id="env-2", payload_dict=payload_dict, enforce_idempotency=True)
    else:
        monkeypatch.setattr(channel_module, "get_whatsapp_client", lambda: _StubClient())
        monkeypatch.setattr(channel_module, "_try_handle_ui_message", lambda **_kwargs: False)
        monkeypatch.setattr(channel_module, "handle_session_flow", lambda **_kwargs: False)
        monkeypatch.setattr(channel_module, "handle_report_flow", lambda **_kwargs: False)
        channel_module.process_whatsapp_envelope(envelope_id="env-1", payload_dict=payload_dict, enforce_idempotency=True)
        channel_module.process_whatsapp_envelope(envelope_id="env-2", payload_dict=payload_dict, enforce_idempotency=True)

    assert business_calls == {"handle": 1, "send": 1}
    assert terminal_statuses == ["completed", "duplicate_skipped"]
    assert statuses == ["processing", "processed", "processing", "processed"]
