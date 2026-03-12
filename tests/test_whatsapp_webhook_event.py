import asyncio
from unittest.mock import MagicMock

import pytest

from app.api.whatsapp.webhook import whatsapp_webhook_event
from app.channels.core.types import InboundMessage
from app.whatsapp.finance_action_session import clear_finance_action_session, get_finance_action_session
from app.whatsapp.join_session import JoinSessionState, get_join_session, save_join_session
from app.whatsapp.ui import build_committee_sections
from tests.utils import QueryMock

pytestmark = [pytest.mark.integration, pytest.mark.endpoint]

@pytest.fixture(autouse=True)
def _default_active_latest_event(monkeypatch):
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router.get_latest_event",
        lambda db: type("Event", (), {"society_id": 1, "status": "ACTIVE"})(),
    )



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
        text="unknown",
        metadata={"message_id": "wamid.1"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.channels.whatsapp.report_flow.detect_whatsapp_intent", lambda message: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: "reply")
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert sent_attempts == [("919999000000", "reply")]


def test_whatsapp_webhook_event_sends_dashboard_buttons_for_menu(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.1"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    class StubDB:
        def close(self):
            return None

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000001",
        display_name="Jane",
        text="menu",
        metadata={"message_id": "wamid.2", "canonical_sender_id": "919999000001"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: StubDB())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: type("Event", (), {"society_id": 1, "status": "ACTIVE"})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.resolve_flat", lambda *args, **kwargs: type("Flat", (), {"id": 1})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Society Control Panel"
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::my-account", "ui::finance", "ui::menu:more"]


def test_whatsapp_webhook_event_unknown_number_menu_prompts_to_join(monkeypatch):
    button_attempts = []
    text_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.1x"}]}

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.1y"}]}

    class StubDB:
        def close(self):
            return None

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000011",
        display_name="Unknown",
        text="menu",
        metadata={"message_id": "wamid.2x", "canonical_sender_id": "919999000011"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: StubDB())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: type("Event", (), {"society_id": 1, "status": "ACTIVE"})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_registered_member_for_sender", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.resolve_flat", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no flat")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_member_of_society", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("not member")))

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == []
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Registration Required"
    assert button_attempts[0]["body_text"] == "You are not registered yet. Tap below to join your society."
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::join-society"]
    assert "ui::my-account" not in button_ids
    assert "ui::finance" not in button_ids


def test_whatsapp_webhook_event_unknown_number_menu_prompts_to_join_without_latest_event(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.1n"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text should not be sent")

    class StubDB:
        def close(self):
            return None

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000015",
        display_name="Unknown",
        text="menu",
        metadata={"message_id": "wamid.2n", "canonical_sender_id": "919999000015"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: StubDB())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: None)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_registered_member_for_sender", lambda *args, **kwargs: False)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Registration Required"
    assert button_attempts[0]["body_text"] == "You are not registered yet. Tap below to join your society."
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::join-society"]
    assert "ui::my-account" not in button_ids
    assert "ui::finance" not in button_ids


def test_whatsapp_webhook_event_unknown_number_ui_section_prompts_to_join(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.1z"}]}

        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text should not be sent")

    class StubDB:
        def close(self):
            return None

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000012",
        display_name="Unknown",
        text="ui::finance",
        metadata={"message_id": "wamid.2z", "canonical_sender_id": "919999000012"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: StubDB())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: type("Event", (), {"society_id": 1, "status": "ACTIVE"})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_registered_member_for_sender", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.resolve_flat", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no flat")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_member_of_society", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("not member")))

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Registration Required"
    assert button_attempts[0]["body_text"] == "You are not registered yet. Tap below to join your society."
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::join-society"]


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

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == [(
        "919999000002",
        "Enter food counts.\nExample:\nveg 2 jain 1 kids 1",
    )]
    session = get_finance_action_session("919999000002")
    assert session is not None
    assert session.pending_action == "ADD_PASS_COUNTS"


def test_whatsapp_webhook_event_add_pass_pending_action_accepts_count_only_reply(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.pass.1"}]}

    inbound_trigger = InboundMessage(
        channel="whatsapp",
        sender_id="919999000013",
        display_name="Jane",
        text="ui::participation:add-update-pass",
        metadata={"message_id": "wamid.pass.1"},
    )
    inbound_counts = InboundMessage(
        channel="whatsapp",
        sender_id="919999000013",
        display_name="Jane",
        text="veg 2 jain 1 kids 1",
        metadata={"message_id": "wamid.pass.2"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_counts])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: f"✅ handled:{message.text}")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts[-1] == (
        "919999000013",
        "✅ handled:add pass veg 2 jain 1 kids 1",
    )
    assert get_finance_action_session("919999000013") is None


def test_whatsapp_webhook_event_add_pass_pending_action_rejects_zero_counts(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.pass.3"}]}

    inbound_trigger = InboundMessage(
        channel="whatsapp",
        sender_id="919999000014",
        display_name="Jane",
        text="ui::participation:add-update-pass",
        metadata={"message_id": "wamid.pass.3"},
    )
    inbound_counts = InboundMessage(
        channel="whatsapp",
        sender_id="919999000014",
        display_name="Jane",
        text="hello there",
        metadata={"message_id": "wamid.pass.4"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_counts])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: f"handled:{message.text}")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts[-1] == (
        "919999000014",
        "❌ Specify counts. Example: veg 2 jain 1 kids 1",
    )
    session = get_finance_action_session("919999000014")
    assert session is not None
    assert session.pending_action == "ADD_PASS_COUNTS"


def test_whatsapp_webhook_event_menu_for_committee_includes_administration(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
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

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: object())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::administration", "ui::reports", "ui::menu:more"]


def test_whatsapp_webhook_event_menu_more_for_member_shows_all_sections_list(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.4a"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000004",
        display_name="Jane",
        text="ui::menu:more",
        metadata={"message_id": "wamid.4a", "canonical_sender_id": "919999000004"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: type("Event", (), {"society_id": 1, "status": "ACTIVE"})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.resolve_flat", lambda *args, **kwargs: type("Flat", (), {"id": 1})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    row_ids = [row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]]
    assert {"ui::my-account", "ui::finance", "ui::society", "ui::reports"}.issubset(set(row_ids))



def test_whatsapp_webhook_event_menu_without_active_event_shows_onboarding_buttons(monkeypatch):
    button_attempts = []
    text_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.menu.noevent.button"}]}

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.menu.noevent.text"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000031",
        display_name="Jane",
        text="menu",
        metadata={"message_id": "wamid.menu.noevent", "canonical_sender_id": "919999000031"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: None)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == []
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Society Control Panel"
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::my-account", "ui::finance", "ui::menu:more"]


def test_whatsapp_webhook_event_menu_more_without_active_event_shows_onboarding_sections(monkeypatch):
    list_attempts = []
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.menu.more.noevent.list"}]}

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.menu.more.noevent.text"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000032",
        display_name="Jane",
        text="ui::menu:more",
        metadata={"message_id": "wamid.menu.more.noevent", "canonical_sender_id": "919999000032"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: None)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == []
    assert len(list_attempts) == 1
    row_ids = [row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]]
    assert {"ui::my-account", "ui::finance", "ui::society", "ui::reports"}.issubset(set(row_ids))


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

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())

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

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: False)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))
    assert response == {"status": "ok"}

    rows = list_attempts[0]["sections"][0]["rows"]
    row_ids = {row["id"] for row in rows}
    assert {"summary", "block report", "report options"}.issubset(row_ids)
    assert "participation report" not in row_ids


def test_whatsapp_webhook_event_administration_operations_menu_respects_row_limit(monkeypatch):
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
        text="ui::administration:operations",
        metadata={"message_id": "wamid.7", "canonical_sender_id": "919999000007"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    total_rows = sum(len(section["rows"]) for section in list_attempts[0]["sections"])
    assert total_rows <= 10
    row_ids = {row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]}
    assert {"add event", "refund sponsor", "ui::administration:operations:more", "ui::administration"}.issubset(row_ids)



def test_whatsapp_webhook_event_administration_operations_more_menu_respects_row_limit(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.7b"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000017",
        display_name="Jane",
        text="ui::administration:operations:more",
        metadata={"message_id": "wamid.7b", "canonical_sender_id": "919999000017"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    total_rows = sum(len(section["rows"]) for section in list_attempts[0]["sections"])
    assert total_rows <= 10
    row_ids = {row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]}
    assert {"activate event", "close event", "remind", "ui::administration:food", "ui::administration:operations"}.issubset(row_ids)


def test_whatsapp_webhook_event_food_collection_menu(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.food"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000018",
        display_name="Jane",
        text="ui::administration:food",
        metadata={"message_id": "wamid.food", "canonical_sender_id": "919999000018"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    row_ids = {row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]}
    assert {"generate food tokens", "verify food token", "food dashboard", "ui::administration:operations:more"}.issubset(row_ids)



def test_whatsapp_webhook_event_committee_management_menu(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.8"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000081",
        display_name="Jane",
        text="ui::administration:committee",
        metadata={"message_id": "wamid.8", "canonical_sender_id": "919999000081"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    row_ids = {row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]}
    assert {"committee::view", "committee::add", "committee::remove", "committee::change-role"}.issubset(row_ids)


def test_whatsapp_webhook_event_administration_includes_committee_entry():
    sections = build_committee_sections()
    row_ids = {row["id"] for section in sections for row in section["rows"]}
    assert "ui::administration:committee" in row_ids

def test_whatsapp_webhook_event_ui_approve_user_sends_pending_user_selection(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.approval.user"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    pending_user = type("PendingUser", (), {"request_code": "REQ-009"})()
    flat = type("Flat", (), {"flat_number": "A-303"})()
    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000071",
        display_name="Jane",
        text="ui::approve-user",
        metadata={"message_id": "wamid.approval.user", "canonical_sender_id": "919999000071"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router.get_latest_event",
        lambda db: type("Event", (), {"id": "evt-1", "society_id": "soc-1"})(),
    )
    monkeypatch.setattr(
        "app.channels.whatsapp.approval_flow.AdminOnboardingQueryService.list_pending_users",
        lambda db, society_id: [(pending_user, flat)],
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    rows = list_attempts[0]["sections"][0]["rows"]
    assert rows[0]["id"] == "approve user REQ-009"
    assert rows[0]["description"] == "Flat A-303"


def test_whatsapp_webhook_event_ui_approve_payment_falls_back_to_template_when_list_send_fails(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise RuntimeError("list unsupported")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.approval.payment"}]}

    payment_request = type("PaymentRequest", (), {"request_code": "PAY-004", "amount": 1200})()
    flat = type("Flat", (), {"flat_number": "B-204"})()
    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000072",
        display_name="Jane",
        text="ui::approve-payment",
        metadata={"message_id": "wamid.approval.payment", "canonical_sender_id": "919999000072"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router.get_latest_event",
        lambda db: type("Event", (), {"id": "evt-1", "society_id": "soc-1"})(),
    )
    monkeypatch.setattr(
        "app.channels.whatsapp.approval_flow.PaymentRequestService.list_requests",
        lambda db, event_id, status: [(payment_request, flat)],
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == [("919999000072", "approve payment PAY-001")]


def test_whatsapp_webhook_event_ui_join_society_starts_conversation(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.join.1"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000008",
        display_name="Jane",
        text="ui::join-society",
        metadata={"message_id": "wamid.join.1"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == [("919999000008", "Please enter join code")]
    session = get_join_session("919999000008")
    assert session is not None
    assert session.pending_action == "JOIN"


def test_whatsapp_webhook_event_conversational_join_submits_on_flat(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.join.2"}]}

    save_join_session("919999000009", JoinSessionState(pending_action="JOIN"))

    inbound_code = InboundMessage(
        channel="whatsapp",
        sender_id="919999000009",
        display_name="Jane",
        text="ABC123",
        metadata={"message_id": "wamid.join.2", "canonical_sender_id": "919999000009"},
    )
    inbound_flat = InboundMessage(
        channel="whatsapp",
        sender_id="919999000009",
        display_name="Jane",
        text="A-101",
        metadata={"message_id": "wamid.join.3", "canonical_sender_id": "919999000009"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound_code, inbound_flat])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        "app.modules.onboarding.join_code_service.JoinCodeService.get_society_by_join_code",
        lambda db, join_code: object() if join_code == "ABC123" else None,
    )

    def fake_handle_inbound_message(message):
        assert message.text == "join ABC123 A-101"
        return "✅ done"

    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", fake_handle_inbound_message)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts == [
        ("919999000009", "Please enter flat number"),
        ("919999000009", "✅ done"),
    ]
    assert get_join_session("919999000009") is None


def test_whatsapp_webhook_event_ui_pay_custom_sets_pending_action(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.pay.1"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000010",
        display_name="Jane",
        text="ui::finance:pay-custom",
        metadata={"message_id": "wamid.pay.1"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert "Expected next reply: a number only." in text_attempts[0][1]
    assert "Type `cancel` to stop." in text_attempts[0][1]
    session = get_finance_action_session("919999000010")
    assert session is not None
    assert session.pending_action == "PAY_CUSTOM"


def test_whatsapp_webhook_event_pay_custom_numeric_reply_routes_to_pay(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.pay.2"}]}

    inbound_trigger = InboundMessage(
        channel="whatsapp",
        sender_id="919999000011",
        display_name="Jane",
        text="ui::finance:pay-custom",
        metadata={"message_id": "wamid.pay.2"},
    )
    inbound_amount = InboundMessage(
        channel="whatsapp",
        sender_id="919999000011",
        display_name="Jane",
        text="500",
        metadata={"message_id": "wamid.pay.3"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_amount])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: f"handled:{message.text}")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts[-1] == ("919999000011", "handled:pay 500")
    assert get_finance_action_session("919999000011") is None


def test_whatsapp_webhook_event_refund_pending_action_accepts_amount_and_reason_without_prefix(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.refund.1"}]}

    inbound_trigger = InboundMessage(
        channel="whatsapp",
        sender_id="919999000012",
        display_name="Jane",
        text="ui::request-refund",
        metadata={"message_id": "wamid.refund.1"},
    )
    inbound_payload = InboundMessage(
        channel="whatsapp",
        sender_id="919999000012",
        display_name="Jane",
        text="200 guest absent",
        metadata={"message_id": "wamid.refund.2"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_payload])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: f"handled:{message.text}")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert "Expected next reply: amount followed by reason." in text_attempts[0][1]
    assert text_attempts[-1] == ("919999000012", "handled:refund 200 guest absent")
    assert get_finance_action_session("919999000012") is None


def test_whatsapp_webhook_event_help_behaves_like_menu(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.help"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000015",
        display_name="Jane",
        text="help",
        metadata={"message_id": "wamid.help", "canonical_sender_id": "919999000015"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: type("Event", (), {"society_id": 1, "status": "ACTIVE"})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.resolve_flat", lambda *args, **kwargs: type("Flat", (), {"id": 1})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Society Control Panel"


def test_whatsapp_webhook_event_invalid_option_sends_main_menu_button(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.invalid"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("invalid option should use buttons")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000016",
        display_name="Jane",
        text="nonsense",
        metadata={"message_id": "wamid.invalid"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.channels.whatsapp.report_flow.detect_whatsapp_intent", lambda message: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: message.metadata.update({"response_contract": {"response_type": "invalid_input", "ctas": [{"id": "menu", "label": "Main Menu"}, {"id": "help", "label": "Help"}]}}) or "ℹ️ Invalid option. Try a listed menu command. Use: menu, help.")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Invalid command"
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["menu", "help"]


def test_whatsapp_webhook_event_report_options_opens_report_list_without_forcing_event_selection(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.report.events"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000017",
        display_name="Jane",
        text="report options",
        metadata={"message_id": "wamid.report.events", "canonical_sender_id": "919999000017"},
    )

    fake_member = type("M", (), {"id": "member-1", "role": "chairman", "society_id": "soc-1"})()

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: fake_member)
    monkeypatch.setattr(
        "app.channels.whatsapp.report_flow.list_exportable_report_options",
        lambda **kwargs: [{"category": "financial", "command_key": "financial:block-payments", "label": "Block Payments", "report_key": "block-payments"}],
    )
    closed_event = type("LE", (), {"id": "evt-x", "status": "CLOSED"})()
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: closed_event)

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    row_ids = [row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]]
    assert "export::financial:block-payments" in row_ids


def test_whatsapp_webhook_event_report_event_selection_opens_report_list(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.report.list"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000018",
        display_name="Jane",
        text="report-event::evt-1",
        metadata={"message_id": "wamid.report.list", "canonical_sender_id": "919999000018"},
    )

    fake_member = type("M", (), {"id": "member-2", "role": "chairman", "society_id": "soc-1"})()

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: fake_member)
    monkeypatch.setattr(
        "app.channels.whatsapp.report_flow.list_exportable_report_options",
        lambda **kwargs: [{"category": "financial", "command_key": "financial:block-payments", "label": "Block Payments"}],
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    row_ids = [row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]]
    assert "export::financial:block-payments" in row_ids


def test_whatsapp_webhook_event_export_requires_event_then_opens_event_selection(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.report.need-event"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000019",
        display_name="Jane",
        text="export::financial:block-payments",
        metadata={"message_id": "wamid.report.need-event", "canonical_sender_id": "919999000019"},
    )

    fake_member = type("M", (), {"id": "member-3", "role": "chairman", "society_id": "soc-1"})()
    fake_event = type("E", (), {"id": "evt-1", "name": "Ganesh Event", "event_date": __import__("datetime").datetime(2026, 9, 14, 19, 0), "status": "ACTIVE"})()
    fake_event_2 = type("E", (), {"id": "evt-2", "name": "Diwali Event", "event_date": __import__("datetime").datetime(2026, 10, 20, 20, 0), "status": "LOCKED"})()

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: fake_member)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._recent_report_events", lambda **kwargs: [fake_event, fake_event_2])

    from app.whatsapp.export_session import ExportSessionState, save_export_session
    save_export_session(
        "member-3:919999000019",
        ExportSessionState(options=[{"category": "financial", "report_key": "block-payments", "command_key": "financial:block-payments", "label": "Block Payments"}], event_id=None),
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    rows = list_attempts[0]["sections"][0]["rows"]
    assert rows[0]["id"].startswith("report-event::")




def test_whatsapp_webhook_event_export_requires_event_with_single_candidate_auto_selects(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("event selection list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.report.single-event"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000029",
        display_name="Jane",
        text="export::financial:block-payments",
        metadata={"message_id": "wamid.report.single-event", "canonical_sender_id": "919999000029"},
    )

    fake_member = type("M", (), {"id": "member-29", "role": "chairman", "society_id": "soc-1"})()
    fake_event = type("E", (), {"id": "evt-single", "name": "Annual Event", "event_date": __import__("datetime").datetime(2026, 9, 14, 19, 0), "status": "ACTIVE"})()

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: fake_member)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._recent_report_events", lambda **kwargs: [fake_event])
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: "✅ exported with auto event")

    from app.whatsapp.export_session import ExportSessionState, get_export_session, save_export_session
    save_export_session(
        "member-29:919999000029",
        ExportSessionState(options=[{"category": "financial", "report_key": "block-payments", "command_key": "financial:block-payments", "label": "Block Payments"}], event_id=None),
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts[-1] == ("919999000029", "✅ exported with auto event")
    session = get_export_session("member-29:919999000029")
    assert session is not None
    assert session.event_id == "evt-single"
def test_whatsapp_webhook_event_report_intent_requires_event_opens_event_selector(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.report.intent"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000020",
        display_name="Jane",
        text="summary",
        metadata={"message_id": "wamid.report.intent", "canonical_sender_id": "919999000020"},
    )

    fake_member = type("M", (), {"id": "member-4", "role": "chairman", "society_id": "soc-1"})()
    fake_event = type("E", (), {"id": "evt-2", "name": "Ganesh Event", "event_date": __import__("datetime").datetime(2026, 9, 14, 19, 0), "status": "ACTIVE"})()

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: fake_member)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: None)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._recent_report_events", lambda **kwargs: [fake_event])

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    rows = list_attempts[0]["sections"][0]["rows"]
    assert rows[0]["id"].startswith("report-event::")


def test_whatsapp_webhook_event_export_without_session_bootstraps(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.export.bootstrap"}]}

        def send_list_message(self, **kwargs):
            raise AssertionError("should not require list here")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000021",
        display_name="Jane",
        text="export::financial:ledger",
        metadata={"message_id": "wamid.export.bootstrap", "canonical_sender_id": "919999000021"},
    )

    fake_member = type("M", (), {"id": "member-5", "role": "chairman", "society_id": "soc-1"})()
    latest_event = type("E", (), {"id": "evt-3"})()

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: fake_member)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: latest_event)
    monkeypatch.setattr("app.channels.whatsapp.report_flow.list_exportable_report_options", lambda **kwargs: [{"category": "financial", "report_key": "ledger", "command_key": "financial:ledger", "label": "Ledger"}])
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: "✅ exported")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts[-1] == ("919999000021", "✅ exported")


def test_whatsapp_webhook_event_report_intent_uses_active_latest_event_without_selection(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("event selection list should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append((to_phone, body))
            return {"messages": [{"id": "wamid.report.active-latest"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000022",
        display_name="Jane",
        text="summary",
        metadata={"message_id": "wamid.report.active-latest", "canonical_sender_id": "919999000022"},
    )

    fake_member = type("M", (), {"id": "member-6", "role": "chairman", "society_id": "soc-1"})()
    active_event = type("E", (), {"id": "evt-active", "status": "ACTIVE"})()

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: fake_member)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: active_event)
    monkeypatch.setattr("app.api.whatsapp.webhook.handle_inbound_message", lambda message: "✅ summary with active event")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts[-1] == ("919999000022", "✅ summary with active event")


def test_whatsapp_webhook_event_ui_view_balance_requests_event_selection_when_multiple_events(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.finance.event-select"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text response should not be sent")

    class StubDB:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def distinct(self):
            return self

        def all(self):
            return [type("M", (), {"society_id": "soc-1"})()]

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def close(self):
            return None

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000101",
        display_name="Jane",
        text="ui::finance:view-balance",
        metadata={"message_id": "wamid.finance.balance", "canonical_sender_id": "919999000101"},
    )

    fake_events = [
        type("E", (), {"id": "evt-1", "name": "Ganesh", "event_date": __import__("datetime").datetime(2026, 9, 14, 19, 0), "status": "CLOSED"})(),
        type("E", (), {"id": "evt-2", "name": "Navratri", "event_date": __import__("datetime").datetime(2026, 8, 20, 18, 0), "status": "LOCKED"})(),
    ]

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: StubDB())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: None)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.resolve_flat", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not resolve flat before event select")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.UserQueryService.get_my_balance", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not load balance before event select")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.UserQueryService.get_my_payment_summary", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not load summary before event select")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router._recent_member_events", lambda **kwargs: fake_events)

    clear_finance_action_session("919999000101")
    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    rows = list_attempts[0]["sections"][0]["rows"]
    assert rows[0]["id"].startswith("finance-event::")
    session = get_finance_action_session("919999000101")
    assert session is not None
    assert session.pending_action == "VIEW_BALANCE"


def test_whatsapp_webhook_event_ui_make_payment_requests_event_selection_when_no_active_event(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.finance.makepay-select"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("no direct text fallback expected")

    class StubDB:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def distinct(self):
            return self

        def all(self):
            return [type("M", (), {"society_id": "soc-1"})()]

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def close(self):
            return None

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000102",
        display_name="Jane",
        text="ui::make-payment",
        metadata={"message_id": "wamid.finance.makepay", "canonical_sender_id": "919999000102"},
    )

    fake_events = [
        type("E", (), {"id": "evt-a", "name": "Past Event A", "event_date": __import__("datetime").datetime(2026, 7, 1, 19, 0), "status": "CLOSED"})(),
        type("E", (), {"id": "evt-b", "name": "Past Event B", "event_date": __import__("datetime").datetime(2026, 6, 1, 19, 0), "status": "LOCKED"})(),
    ]

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: StubDB())
    monkeypatch.setattr("app.channels.whatsapp.ui_router.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_registered_member_for_sender", lambda **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.get_latest_event", lambda db: None)
    monkeypatch.setattr("app.channels.whatsapp.ui_router.resolve_flat", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not resolve flat before event select")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router.UserQueryService.get_my_balance", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not compute balance before event select")))
    monkeypatch.setattr("app.channels.whatsapp.ui_router._recent_member_events", lambda **kwargs: fake_events)

    clear_finance_action_session("919999000102")
    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert len(list_attempts) == 1
    rows = list_attempts[0]["sections"][0]["rows"]
    assert rows[0]["id"].startswith("finance-event::")
    session = get_finance_action_session("919999000102")
    assert session is not None
    assert session.pending_action == "MAKE_PAYMENT"



def test_whatsapp_webhook_event_administration_menu_shows_manage_committee_for_authorized_user(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.admin.committee"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000083",
        display_name="Jane",
        text="ui::administration",
        metadata={"message_id": "wamid.admin.committee", "canonical_sender_id": "919999000083"},
    )

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman"})())

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    row_ids = {row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]}
    assert "ui::administration:committee" in row_ids


def test_whatsapp_webhook_event_committee_routes_trigger_expected_flows(monkeypatch):
    called = {}

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            return {"messages": [{"id": "wamid.committee.route"}]}

        def send_text_message(self, to_phone: str, body: str):
            return {"messages": [{"id": "wamid.committee.route.text"}]}

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    class StubDB:
        def query(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return []

        def close(self):
            return None

    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: StubDB())
    monkeypatch.setattr("app.channels.whatsapp.ui_router._get_committee_member", lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman", "society_id": "soc-1"})())

    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router._send_add_member_selection",
        lambda **kwargs: called.setdefault("add", True),
    )
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router._send_committee_member_selection",
        lambda **kwargs: called.setdefault("remove_or_change", kwargs["body_text"]),
    )
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router._handle_committee_view",
        lambda **kwargs: called.setdefault("view", True),
    )

    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [InboundMessage(channel="whatsapp", sender_id="919999000084", display_name="Jane", text="committee::add", metadata={"message_id": "wamid.add", "canonical_sender_id": "919999000084"})])
    asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [InboundMessage(channel="whatsapp", sender_id="919999000084", display_name="Jane", text="committee::remove", metadata={"message_id": "wamid.remove", "canonical_sender_id": "919999000084"})])
    asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [InboundMessage(channel="whatsapp", sender_id="919999000084", display_name="Jane", text="committee::view", metadata={"message_id": "wamid.view", "canonical_sender_id": "919999000084"})])
    asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert called["add"] is True
    assert called["remove_or_change"] == "Choose member to remove"
    assert called["view"] is True



def test_whatsapp_webhook_event_committee_flow_lists_include_back_and_menu_navigation():
    from app.channels.whatsapp.ui_router import _build_committee_role_sections, _with_navigation

    role_sections = _build_committee_role_sections(include_navigation=True)
    role_nav_rows = role_sections[-1]["rows"]
    assert [row["id"] for row in role_nav_rows] == ["ui::administration:committee", "menu"]

    member_sections = _with_navigation(
        sections=[{"title": "Members", "rows": [{"id": "committee-member::cm-1", "title": "Alice", "description": "919999000000 · Secretary"}]}],
        back_id="ui::administration:committee",
    )
    member_nav_rows = member_sections[-1]["rows"]
    assert [row["id"] for row in member_nav_rows] == ["ui::administration:committee", "menu"]

def test_whatsapp_webhook_event_verify_food_token_opens_picker(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.food.verify"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000019",
        display_name="Jane",
        text="verify food token",
        metadata={"message_id": "wamid.food.verify", "canonical_sender_id": "919999000019"},
    )

    db = type("DB", (), {"close": lambda self: None})()
    db.query = MagicMock(side_effect=[
        QueryMock(first_result=type("Event", (), {"id": "evt-1"})()),
        QueryMock(all_result=[type("Token", (), {"token_code": "AB2K9M", "food_type": "veg", "served_at": None})()]),
    ])

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: db)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router._get_committee_member",
        lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman", "society_id": "soc-1"})(),
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    row_ids = {row["id"] for section in list_attempts[0]["sections"] for row in section["rows"]}
    assert "food-verify-token::AB2K9M" in row_ids


def test_whatsapp_webhook_event_token_status_picker_includes_served_tokens(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.food.status"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000021",
        display_name="Jane",
        text="token status",
        metadata={"message_id": "wamid.food.status", "canonical_sender_id": "919999000021"},
    )

    db = type("DB", (), {"close": lambda self: None})()
    db.query = MagicMock(side_effect=[
        QueryMock(first_result=type("Event", (), {"id": "evt-1"})()),
        QueryMock(all_result=[
            type("Token", (), {"token_code": "PEND1", "food_type": "veg", "served_at": None})(),
            type("Token", (), {"token_code": "SERV1", "food_type": "veg", "served_at": object()})(),
        ]),
    ])

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: db)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router._get_committee_member",
        lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman", "society_id": "soc-1"})(),
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    rows = [row for section in list_attempts[0]["sections"] for row in section["rows"] if row["id"].startswith("food-token-status::")]
    row_map = {row["id"]: row["description"] for row in rows}
    assert row_map["food-token-status::PEND1"] == "Veg | Pending"
    assert row_map["food-token-status::SERV1"] == "Veg | Served"


def test_whatsapp_webhook_event_verify_food_token_selection_serves(monkeypatch):
    text_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            raise AssertionError("list message should not be sent")

        def send_text_message(self, to_phone: str, body: str):
            text_attempts.append(body)
            return {"messages": [{"id": "wamid.food.serve"}]}

    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000020",
        display_name="Jane",
        text="food-verify-token::AB2K9M",
        metadata={"message_id": "wamid.food.serve", "canonical_sender_id": "919999000020"},
    )

    db = type("DB", (), {"close": lambda self: None})()
    db.query = MagicMock(side_effect=[
        QueryMock(first_result=type("Event", (), {"id": "evt-1"})()),
    ])

    monkeypatch.setattr("app.api.whatsapp.webhook._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp.webhook._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.webhook.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.webhook.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.webhook.SessionLocal", lambda: db)
    monkeypatch.setattr("app.channels.whatsapp.ui_router._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.channels.whatsapp.ui_router._get_committee_member",
        lambda *args, **kwargs: type("Member", (), {"id": "m-1", "role": "chairman", "society_id": "soc-1"})(),
    )
    monkeypatch.setattr(
        "app.modules.events.food_collection_service.FoodCollectionService.verify_and_serve_token",
        lambda **kwargs: type("Served", (), {"token_code": "AB2K9M", "food_type": "veg"})(),
    )

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert any("Served token AB2K9M" in msg for msg in text_attempts)
