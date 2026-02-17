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
    monkeypatch.setattr("app.api.whatsapp.detect_whatsapp_intent", lambda message: "HELP")
    monkeypatch.setattr("app.api.whatsapp.handle_inbound_message", lambda message: "reply")
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert sent_attempts == [("919999000000", "reply")]


def test_whatsapp_webhook_event_sends_dashboard_list_for_menu(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.1"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000001",
        display_name="Jane",
        text="menu",
        metadata={"message_id": "wamid.2", "canonical_sender_id": "919999000001"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    assert list_attempts[0]["header_text"] == "Society Control Panel"
    sections = list_attempts[0]["sections"]
    assert len(sections) == 1
    assert sections[0]["title"] == "Sections"
    assert len(sections[0]["rows"]) <= 10
    assert any(row["id"] == "ui::reports" for row in sections[0]["rows"])


def test_whatsapp_webhook_event_prompts_for_add_pass_from_ui(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.3"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000002",
        display_name="Jane",
        text="ui::participation:add-update-pass",
        metadata={"message_id": "wamid.3"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == [(
        "919999000002",
        "Enter food counts.\nExample:\nveg 2 jain 1 kids 1",
    )]


def test_whatsapp_webhook_event_menu_for_committee_includes_administration(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.4"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000003",
        display_name="Jane",
        text="menu",
        metadata={"message_id": "wamid.4", "canonical_sender_id": "919999000003"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp.ensure_committee_member", lambda *args, **kwargs: object())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    rows = list_attempts[0]["sections"][0]["rows"]
    assert any(row["id"] == "ui::administration" for row in rows)
    assert len(rows) <= 10


def test_whatsapp_webhook_event_administration_menu_respects_row_limit(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.5"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000005",
        display_name="Jane",
        text="ui::administration",
        metadata={"message_id": "wamid.5", "canonical_sender_id": "919999000005"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp._is_committee_member", lambda *args, **kwargs: True)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    total_rows = sum(len(section["rows"]) for section in list_attempts[0]["sections"])
    assert total_rows <= 10


def test_whatsapp_webhook_event_reports_menu_committee_gated_rows(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.6"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000006",
        display_name="Jane",
        text="ui::reports",
        metadata={"message_id": "wamid.6", "canonical_sender_id": "919999000006"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp._is_committee_member", lambda *args, **kwargs: False)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))
    assert response == {"status": "ok"}

    rows = list_attempts[0]["sections"][0]["rows"]
    row_ids = {row["id"] for row in rows}
    assert {"summary", "block report", "report options"}.issubset(row_ids)
    assert "participation report" not in row_ids


def test_whatsapp_webhook_event_administration_more_menu_respects_row_limit(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.7"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000007",
        display_name="Jane",
        text="ui::administration:more",
        metadata={"message_id": "wamid.7", "canonical_sender_id": "919999000007"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp._is_committee_member", lambda *args, **kwargs: True)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    total_rows = sum(len(section["rows"]) for section in list_attempts[0]["sections"])
    assert total_rows <= 10
    row_ids = {row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]}
    assert {"ui::approve-user", "ui::approve-payment", "ui::approve-refund"}.issubset(row_ids)
