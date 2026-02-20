import asyncio

from app.api.whatsapp import whatsapp_webhook_event
from app.channels.core.types import InboundMessage
from app.whatsapp.finance_action_session import get_finance_action_session
from app.whatsapp.join_session import JoinSessionState, get_join_session, save_join_session


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


def test_whatsapp_webhook_event_sends_dashboard_buttons_for_menu(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
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
    assert len(button_attempts) == 1
    assert button_attempts[0]["header_text"] == "Society Control Panel"
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::my-account", "ui::finance", "ui::menu:more"]


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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_counts])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.handle_inbound_message", lambda message: f"✅ handled:{message.text}")

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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_counts])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.handle_inbound_message", lambda message: f"handled:{message.text}")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert text_attempts[-1] == (
        "919999000014",
        "❌ Specify counts. Example: veg 2 jain 1 kid 1",
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
        text="ui::menu:more",
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
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::society", "ui::reports", "ui::administration"]


def test_whatsapp_webhook_event_menu_more_for_member_shows_main_menu(monkeypatch):
    button_attempts = []

    class StubWhatsAppClient:
        def send_button_message(self, **kwargs):
            button_attempts.append(kwargs)
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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp.ensure_committee_member", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("no")))

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    button_ids = [button["reply"]["id"] for button in button_attempts[0]["buttons"]]
    assert button_ids == ["ui::society", "ui::reports", "menu"]


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


def test_whatsapp_webhook_event_ui_approve_user_sends_pending_user_selection(monkeypatch):
    list_attempts = []

    class StubWhatsAppClient:
        def send_list_message(self, **kwargs):
            list_attempts.append(kwargs)
            return {"messages": [{"id": "wamid.approval.user"}]}

        def send_text_message(self, to_phone: str, body: str):
            raise AssertionError("text fallback should not be sent")

    pending_user = type("PendingUser", (), {"request_code": "REQ-009", "flat_number": "A-303"})()
    inbound = InboundMessage(
        channel="whatsapp",
        sender_id="919999000071",
        display_name="Jane",
        text="ui::approve-user",
        metadata={"message_id": "wamid.approval.user", "canonical_sender_id": "919999000071"},
    )

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.api.whatsapp.get_latest_event",
        lambda db: type("Event", (), {"id": "evt-1", "society_id": "soc-1"})(),
    )
    monkeypatch.setattr(
        "app.api.whatsapp.AdminOnboardingQueryService.list_pending_users",
        lambda db, society_id: [pending_user],
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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.api.whatsapp._is_committee_member", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "app.api.whatsapp.get_latest_event",
        lambda db: type("Event", (), {"id": "evt-1", "society_id": "soc-1"})(),
    )
    monkeypatch.setattr(
        "app.api.whatsapp.PaymentRequestService.list_requests",
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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())

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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound_code, inbound_flat])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr(
        "app.api.whatsapp.JoinCodeService.get_society_by_join_code",
        lambda db, join_code: object() if join_code == "ABC123" else None,
    )

    def fake_handle_inbound_message(message):
        assert message.text == "join ABC123 A-101"
        return "✅ done"

    monkeypatch.setattr("app.api.whatsapp.handle_inbound_message", fake_handle_inbound_message)

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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())

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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_amount])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.handle_inbound_message", lambda message: f"handled:{message.text}")

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

    monkeypatch.setattr("app.api.whatsapp._ensure_channel_enabled", lambda: None)
    monkeypatch.setattr("app.api.whatsapp._verify_signature", lambda raw, sig: None)
    monkeypatch.setattr("app.api.whatsapp.parse_webhook_payload", lambda payload: [inbound_trigger, inbound_payload])
    monkeypatch.setattr("app.api.whatsapp.get_whatsapp_client", lambda: StubWhatsAppClient())
    monkeypatch.setattr("app.api.whatsapp.handle_inbound_message", lambda message: f"handled:{message.text}")

    response = asyncio.run(whatsapp_webhook_event(StubRequest({"entry": []})))

    assert response == {"status": "ok"}
    assert "Expected next reply: amount followed by reason." in text_attempts[0][1]
    assert text_attempts[-1] == ("919999000012", "handled:refund 200 guest absent")
    assert get_finance_action_session("919999000012") is None
