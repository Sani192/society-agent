import asyncio

import pytest

from app.api import telegram as telegram_api
from app.api.whatsapp import webhook as whatsapp_webhook_api
from app.channels.core.types import InboundMessage

pytestmark = [pytest.mark.integration, pytest.mark.endpoint]


class StubTelegramRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    async def json(self):
        return self._payload

    async def body(self):
        return b'{"update_id": 1}'


class StubWhatsAppRequest:
    def __init__(self, payload: dict):
        self._payload = payload
        self.headers = {"X-Hub-Signature-256": "sha256=test"}

    async def json(self):
        return self._payload

    async def body(self):
        return b'{"entry": []}'


def test_telegram_webhook_tracks_terminal_event_per_message_and_continues(monkeypatch):
    events = []
    sent = []

    class StubClient:
        def send_text_message(self, chat_id, text, **kwargs):
            sent.append((chat_id, text, kwargs.get("trace_id")))
            return {"ok": True}

    inbound_messages = [
        InboundMessage(
            channel="telegram",
            sender_id="u1",
            display_name="A",
            text="first",
            metadata={"chat_id": "c1", "message_id": 1, "update_id": 101},
        ),
        InboundMessage(
            channel="telegram",
            sender_id="u2",
            display_name="B",
            text="second",
            metadata={"chat_id": "c2", "message_id": 2, "update_id": 102},
        ),
    ]

    def fake_handle(message, **kwargs):
        if message.text == "first":
            raise RuntimeError("boom")
        return "ok"

    monkeypatch.setattr(telegram_api, "_ensure_channel_enabled", lambda: None)
    monkeypatch.setattr(telegram_api, "_verify_webhook_secret", lambda secret: None)
    monkeypatch.setattr(telegram_api, "parse_webhook_events", lambda payload: [])
    monkeypatch.setattr(telegram_api, "to_normalized_audit_events", lambda parsed: [])
    monkeypatch.setattr(telegram_api, "persist_audit_events", lambda batch: events.extend(batch) or len(batch))
    monkeypatch.setattr(telegram_api, "parse_webhook_payload", lambda payload: inbound_messages)
    monkeypatch.setattr(telegram_api, "_persist_inbound_envelope", lambda **_kwargs: "env-1")
    monkeypatch.setattr(telegram_api, "_mark_envelope_status", lambda **_kwargs: None)
    monkeypatch.setattr(telegram_api, "_claim_idempotency_key", lambda **_kwargs: True)
    monkeypatch.setattr(telegram_api, "handle_inbound_message", fake_handle)
    monkeypatch.setattr(telegram_api, "get_telegram_client", lambda: StubClient())

    response = asyncio.run(telegram_api.telegram_webhook_event(StubTelegramRequest({"update_id": 1})))

    assert response == {"status": "ok"}
    assert len(sent) == 1
    terminal_events = [event for event in events if event.event_type in {"processing_completed", "exception"}]
    assert len(terminal_events) == 2
    assert sum(1 for event in terminal_events if event.event_type == "exception") == 1
    assert sum(1 for event in terminal_events if event.event_type == "processing_completed") == 1


def test_whatsapp_webhook_tracks_terminal_event_per_message_and_continues(monkeypatch):
    events = []
    sent = []

    class StubClient:
        def send_text_message(self, to_phone, body, **kwargs):
            sent.append((to_phone, body, kwargs.get("trace_id")))
            return {"messages": [{"id": "wamid.1"}]}

    inbound_messages = [
        InboundMessage(
            channel="whatsapp",
            sender_id="9191",
            display_name="A",
            text="first",
            metadata={"message_id": "wamid.a"},
        ),
        InboundMessage(
            channel="whatsapp",
            sender_id="9292",
            display_name="B",
            text="second",
            metadata={"message_id": "wamid.b"},
        ),
    ]

    def fake_handle(message, **kwargs):
        if message.text == "first":
            raise RuntimeError("boom")
        return "ok"

    monkeypatch.setattr(whatsapp_webhook_api, "_ensure_channel_enabled", lambda: None)
    monkeypatch.setattr(whatsapp_webhook_api, "_verify_signature", lambda raw, sig: None)
    monkeypatch.setattr(whatsapp_webhook_api, "parse_webhook_events", lambda payload: [])
    monkeypatch.setattr(whatsapp_webhook_api, "to_normalized_audit_events", lambda parsed: [])
    monkeypatch.setattr(whatsapp_webhook_api, "persist_audit_events", lambda batch: events.extend(batch) or len(batch))
    monkeypatch.setattr(whatsapp_webhook_api, "parse_webhook_payload", lambda payload: inbound_messages)
    monkeypatch.setattr(whatsapp_webhook_api, "_persist_inbound_envelope", lambda **_kwargs: "env-1")
    monkeypatch.setattr(whatsapp_webhook_api, "_mark_envelope_status", lambda **_kwargs: None)
    monkeypatch.setattr(whatsapp_webhook_api, "_claim_idempotency_key", lambda **_kwargs: True)
    monkeypatch.setattr(whatsapp_webhook_api, "_try_handle_ui_message", lambda **kwargs: False)
    monkeypatch.setattr(whatsapp_webhook_api, "handle_session_flow", lambda **kwargs: False)
    monkeypatch.setattr(whatsapp_webhook_api, "handle_report_flow", lambda **kwargs: False)
    monkeypatch.setattr(whatsapp_webhook_api, "handle_inbound_message", fake_handle)
    monkeypatch.setattr(whatsapp_webhook_api, "get_whatsapp_client", lambda: StubClient())

    response = asyncio.run(whatsapp_webhook_api.whatsapp_webhook_event(StubWhatsAppRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(sent) == 1
    terminal_events = [event for event in events if event.event_type in {"processing_completed", "exception"}]
    assert len(terminal_events) == 2
    assert sum(1 for event in terminal_events if event.event_type == "exception") == 1
    assert sum(1 for event in terminal_events if event.event_type == "processing_completed") == 1


class StubBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))

    def run_all(self):
        for fn, args, kwargs in self.tasks:
            fn(*args, **kwargs)


def test_telegram_duplicate_webhook_retry_executes_business_once(monkeypatch):
    calls = {"handle": 0, "send": 0}

    class StubClient:
        def send_text_message(self, *_args, **_kwargs):
            calls["send"] += 1
            return {"ok": True}

    inbound = InboundMessage(
        channel="telegram",
        sender_id="u1",
        display_name="A",
        text="hello",
        metadata={"chat_id": "c1", "message_id": 1, "update_id": 101},
    )
    seen = set()

    def fake_claim(**kwargs):
        key = (kwargs.get("channel"), kwargs.get("message_id"), kwargs.get("update_id"))
        if key in seen:
            return False
        seen.add(key)
        return True

    monkeypatch.setattr(telegram_api, "_ensure_channel_enabled", lambda: None)
    monkeypatch.setattr(telegram_api, "_verify_webhook_secret", lambda _secret: None)
    monkeypatch.setattr(telegram_api, "parse_webhook_events", lambda _payload: [])
    monkeypatch.setattr(telegram_api, "to_normalized_audit_events", lambda _parsed: [])
    monkeypatch.setattr(telegram_api, "persist_audit_events", lambda _batch: 1)
    monkeypatch.setattr(telegram_api, "parse_webhook_payload", lambda _payload: [inbound])
    monkeypatch.setattr(telegram_api, "get_telegram_client", lambda: StubClient())
    monkeypatch.setattr(telegram_api, "_persist_inbound_envelope", lambda **_kwargs: "env-1")
    monkeypatch.setattr(telegram_api, "_mark_envelope_status", lambda **_kwargs: None)
    monkeypatch.setattr(telegram_api, "_claim_idempotency_key", fake_claim)

    def _handle(*_args, **_kwargs):
        calls["handle"] += 1
        return "ok"

    monkeypatch.setattr(telegram_api, "handle_inbound_message", _handle)

    bg1 = StubBackgroundTasks()
    bg2 = StubBackgroundTasks()
    asyncio.run(telegram_api.telegram_webhook_event(StubTelegramRequest({"update_id": 1}), background_tasks=bg1))
    asyncio.run(telegram_api.telegram_webhook_event(StubTelegramRequest({"update_id": 1}), background_tasks=bg2))
    bg1.run_all()
    bg2.run_all()

    assert calls["handle"] == 1
    assert calls["send"] == 1


def test_whatsapp_duplicate_webhook_retry_executes_business_once(monkeypatch):
    calls = {"handle": 0, "send": 0}

    class StubClient:
        def send_text_message(self, *_args, **_kwargs):
            calls["send"] += 1
            return {"messages": [{"id": "wamid.1"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="9191",
        display_name="A",
        text="hello",
        metadata={"message_id": "wamid.a"},
    )
    seen = set()

    def fake_claim(**kwargs):
        key = (kwargs.get("channel"), kwargs.get("message_id"), kwargs.get("update_id"))
        if key in seen:
            return False
        seen.add(key)
        return True

    monkeypatch.setattr(whatsapp_webhook_api, "_ensure_channel_enabled", lambda: None)
    monkeypatch.setattr(whatsapp_webhook_api, "_verify_signature", lambda _raw, _sig: None)
    monkeypatch.setattr(whatsapp_webhook_api, "parse_webhook_events", lambda _payload: [])
    monkeypatch.setattr(whatsapp_webhook_api, "to_normalized_audit_events", lambda _parsed: [])
    monkeypatch.setattr(whatsapp_webhook_api, "persist_audit_events", lambda _batch: 1)
    monkeypatch.setattr(whatsapp_webhook_api, "parse_webhook_payload", lambda _payload: [inbound])
    monkeypatch.setattr(whatsapp_webhook_api, "_try_handle_ui_message", lambda **_kwargs: False)
    monkeypatch.setattr(whatsapp_webhook_api, "handle_session_flow", lambda **_kwargs: False)
    monkeypatch.setattr(whatsapp_webhook_api, "handle_report_flow", lambda **_kwargs: False)
    monkeypatch.setattr(whatsapp_webhook_api, "get_whatsapp_client", lambda: StubClient())
    monkeypatch.setattr(whatsapp_webhook_api, "_persist_inbound_envelope", lambda **_kwargs: "env-1")
    monkeypatch.setattr(whatsapp_webhook_api, "_mark_envelope_status", lambda **_kwargs: None)
    monkeypatch.setattr(whatsapp_webhook_api, "_claim_idempotency_key", fake_claim)

    def _handle(*_args, **_kwargs):
        calls["handle"] += 1
        return "ok"

    monkeypatch.setattr(whatsapp_webhook_api, "handle_inbound_message", _handle)

    bg1 = StubBackgroundTasks()
    bg2 = StubBackgroundTasks()
    asyncio.run(whatsapp_webhook_api.whatsapp_webhook_event(StubWhatsAppRequest({"entry": []}), background_tasks=bg1))
    asyncio.run(whatsapp_webhook_api.whatsapp_webhook_event(StubWhatsAppRequest({"entry": []}), background_tasks=bg2))
    bg1.run_all()
    bg2.run_all()

    assert calls["handle"] == 1
    assert calls["send"] == 1
