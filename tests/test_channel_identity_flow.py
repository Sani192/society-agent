from unittest.mock import MagicMock

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage
from app.whatsapp.committee_action_session import (
    CommitteeActionSessionState,
    clear_committee_action_session,
    save_committee_action_session,
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

    assert response == "ℹ️ Command not supported. Please use *commands* to view available commands."


def test_whatsapp_no_intent_falls_back_to_commands_hint():
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

    assert response == "ℹ️ Command not supported. Please use *commands* to view available commands."


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
