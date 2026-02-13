from unittest.mock import MagicMock

from app.channels.core.handler import handle_inbound_message
from app.channels.core.types import InboundMessage


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


def test_handler_passes_inbound_message_to_committee_handler_for_exports():
    db = MagicMock()
    captured = {}

    message = InboundMessage(
        channel="whatsapp",
        sender_id="999",
        display_name="Jane",
        text="report export --category financial --report event-summary --format pdf",
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
        intent_detector=lambda text: "EXPORT_REPORT",
        onboarding_intent_handler=lambda **kwargs: None,
        committee_intent_handler=committee_handler,
        public_intent_handler=lambda **kwargs: None,
    )

    assert response == "ok"
    assert captured["inbound_message"].metadata["canonical_sender_id"] == "919898989898"
