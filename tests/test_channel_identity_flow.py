from unittest.mock import MagicMock

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.handlers.shared.public import handle_public_intent
from app.whatsapp.committee_action_session import (
    CommitteeActionSessionState,
    clear_committee_action_session,
    save_committee_action_session,
)
from app.whatsapp.export_session import (
    ExportSessionState,
    clear_export_session,
    save_export_session,
)


def test_telegram_link_member_flow_short_circuits(monkeypatch):
    db = MagicMock()

    monkeypatch.setattr(
        "app.channels.core.handler.link_member_by_code",
        lambda **kwargs: object(),
    )

    message = InboundMessage(
        channel="telegram",
        sender_id="999",
        display_name="Jane",
        text="link member ABC123",
        metadata={"username": "janed"},
    )

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(
            Exception("unauthorized")
        ),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: "LINK_MEMBER",
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "✅ Telegram account linked successfully."


def test_telegram_verify_phone_flow_short_circuits(monkeypatch):
    db = MagicMock()

    monkeypatch.setattr(
        "app.channels.core.handler.link_member_by_phone",
        lambda **kwargs: object(),
    )

    message = InboundMessage(
        channel="telegram",
        sender_id="999",
        display_name="Jane",
        text="verify phone 9999000011",
        metadata={"username": "janed"},
    )

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(
            Exception("unauthorized")
        ),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: "VERIFY_PHONE",
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "✅ Phone verified. Telegram account linked."


def test_handler_uses_canonical_sender_for_public_and_onboarding():
    db = MagicMock()
    captured = {}

    message = InboundMessage(
        channel="telegram",
        sender_id="999",
        display_name="Jane",
        text="join status",
        metadata={"canonical_sender_id": "919898989898"},
    )

    def onboarding_handler(**kwargs):
        captured["onboarding_phone"] = kwargs["phone_number"]
        return None

    def public_handler(**kwargs):
        captured["public_phone"] = kwargs["phone_number"]
        return "ok"

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(
            Exception("unauthorized")
        ),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: "JOIN_STATUS",
        onboarding_intent_handler=onboarding_handler,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=public_handler,
    )

    assert response == "ok"
    assert captured["onboarding_phone"] == "919898989898"
    assert captured["public_phone"] == "919898989898"


def test_handler_passes_inbound_message_to_committee_handler_for_report_options():
    db = MagicMock()
    captured = {}

    message = InboundMessage(
        channel="whatsapp",
        sender_id="999",
        display_name="Jane",
        text="report options",
        metadata={"canonical_sender_id": "919898989898"},
    )

    def committee_handler(**kwargs):
        captured["inbound_message"] = kwargs["inbound_message"]
        return "ok"

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: object(),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: "REPORT_OPTIONS",
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=committee_handler,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "ok"
    assert captured["inbound_message"].metadata["canonical_sender_id"] == "919898989898"


def test_whatsapp_unsupported_intent_falls_back_to_reports_menu_hint():
    db = MagicMock()
    message = InboundMessage(
        channel="whatsapp",
        sender_id="919999000000",
        display_name="Jane",
        text="totally unsupported",
        metadata={"canonical_sender_id": "919999000000"},
    )

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(
            Exception("unauthorized")
        ),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: "UNKNOWN_INTENT",
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "ℹ️ Invalid option. That command is not available here. Use: menu, help."


def test_whatsapp_no_intent_falls_back_to_menu_hint():
    db = MagicMock()
    message = InboundMessage(
        channel="whatsapp",
        sender_id="919999000001",
        display_name="John",
        text="what is this",
        metadata={"canonical_sender_id": "919999000001"},
    )

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(
            Exception("unauthorized")
        ),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: None,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "ℹ️ Invalid option. Try a listed menu command. Use: menu, help."


def test_whatsapp_pending_committee_action_maps_free_text_to_pending_intent():
    db = MagicMock()
    message = InboundMessage(
        channel="whatsapp",
        sender_id="919999000002",
        display_name="John",
        text="Water cans",
        metadata={"canonical_sender_id": "919999000002"},
    )

    save_committee_action_session(
        "member-1:919999000002",
        CommitteeActionSessionState(action="ADD_EXPENSE", step="reason"),
    )

    captured = {}

    def committee_handler(**kwargs):
        captured["intent"] = kwargs["intent"]
        return "ok"

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: type("M", (), {"id": "member-1"})(),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: None,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=committee_handler,
        public_intent_handler=lambda **kwargs: None,
    )

    clear_committee_action_session("member-1:919999000002")
    assert response == "ok"
    assert captured["intent"] == "COMMITTEE_PENDING_ACTION"


def test_whatsapp_numeric_intent_not_treated_as_export_without_active_session():
    db = MagicMock()
    captured = {}

    message = InboundMessage(
        channel="whatsapp",
        sender_id="919999111111",
        display_name="John",
        text="2",
        metadata={"canonical_sender_id": "919999111111"},
    )

    def fake_detector(text, **kwargs):
        captured["allow_numeric"] = kwargs.get("allow_numeric_export_selection")
        return None

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(Exception("unauthorized")),
        latest_event_getter=lambda db: None,
        intent_detector=fake_detector,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "ℹ️ Invalid option. Try a listed menu command. Use: menu, help."
    assert captured["allow_numeric"] is False


def test_whatsapp_numeric_intent_treated_as_export_with_active_session_for_sender():
    db = MagicMock()
    captured = {}

    message = InboundMessage(
        channel="whatsapp",
        sender_id="919999111112",
        display_name="John",
        text="2",
        metadata={"canonical_sender_id": "919999111112"},
    )

    save_export_session(
        "member-1:919999111112",
        ExportSessionState(options=[{"category": "financial", "report_key": "event-summary", "label": "Event Summary", "supported_formats": ["pdf"], "example_command": "export 1", "command_key": "financial:event-summary"}]),
    )

    def fake_detector(text, **kwargs):
        captured["allow_numeric"] = kwargs.get("allow_numeric_export_selection")
        return "EXPORT_SELECTION"

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: type("M", (), {"id": "member-1"})(),
        latest_event_getter=lambda db: type("E", (), {"status": "ACTIVE"})(),
        intent_detector=fake_detector,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: "ok",
        public_intent_handler=lambda **kwargs: None,
    )

    clear_export_session("member-1:919999111112")
    assert response == "ok"
    assert captured["allow_numeric"] is True


def test_whatsapp_legacy_reports_alias_returns_migration_hint():
    db = MagicMock()
    message = InboundMessage(
        channel="whatsapp",
        sender_id="919999000010",
        display_name="John",
        text="reports",
        metadata={"canonical_sender_id": "919999000010"},
    )

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(Exception("unauthorized")),
        latest_event_getter=lambda db: None,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "ℹ️ `reports` is no longer supported. Send `report options` to view exportable reports."


def test_whatsapp_legacy_report_export_returns_migration_hint():
    db = MagicMock()
    message = InboundMessage(
        channel="whatsapp",
        sender_id="919999000011",
        display_name="John",
        text="report export --category financial --report ledger --format pdf",
        metadata={"canonical_sender_id": "919999000011"},
    )

    response = handle_inbound_message(
        message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(Exception("unauthorized")),
        latest_event_getter=lambda db: None,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "ℹ️ `report export ...` is no longer supported. Send `report options`, then reply with `export <number>` or tap an `export::<key>` option."


def test_invalid_command_contract_is_consistent_for_whatsapp_and_telegram():
    db = MagicMock()

    whatsapp_message = InboundMessage(
        channel="whatsapp",
        sender_id="919999000111",
        display_name="WA User",
        text="???",
        metadata={},
    )
    telegram_message = InboundMessage(
        channel="telegram",
        sender_id="tg-111",
        display_name="TG User",
        text="???",
        metadata={},
    )

    wa_response = handle_inbound_message(
        whatsapp_message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(Exception("unauthorized")),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: None,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )
    tg_response = handle_inbound_message(
        telegram_message,
        session_factory=lambda: db,
        committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(Exception("unauthorized")),
        latest_event_getter=lambda db: None,
        intent_detector=lambda text: None,
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=lambda **kwargs: None,
        public_intent_handler=lambda **kwargs: None,
    )

    assert wa_response.startswith("ℹ️ Invalid option.")
    assert tg_response.startswith("ℹ️ Invalid command.")
    for message in (whatsapp_message, telegram_message):
        contract = message.metadata["response_contract"]
        assert contract["response_type"] == "invalid_input"
        assert contract["severity"] == "info"
        assert [cta["id"] for cta in contract["ctas"][:2]] == ["menu", "help"]


def test_telegram_menu_and_help_return_command_specific_responses():
    db = MagicMock()

    def _run(text: str) -> str:
        message = InboundMessage(
            channel="telegram",
            sender_id="tg-user",
            display_name="TG",
            text=text,
            metadata={},
        )
        return handle_inbound_message(
            message,
            session_factory=lambda: db,
            committee_member_resolver=lambda *args, **kwargs: (_ for _ in ()).throw(Exception("unauthorized")),
            latest_event_getter=lambda db: None,
            intent_detector=lambda _text: "MENU" if text == "menu" else "HELP",
            onboarding_intent_handler=lambda **kwargs: None,
            committee_intent_handler=lambda **kwargs: None,
            public_intent_handler=handle_public_intent,
        )

    menu_response = _run("menu")
    help_response = _run("help")

    assert menu_response.startswith("✅")
    assert "Main menu:" in menu_response
    assert help_response.startswith("✅")
    assert "Society Control Panel" in help_response
    assert "Type *menu*." in help_response
    assert menu_response != help_response
