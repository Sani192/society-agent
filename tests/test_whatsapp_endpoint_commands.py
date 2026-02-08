from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.whatsapp import WhatsAppRequest, whatsapp_webhook


def _setup_common_mocks(monkeypatch, member=None):
    def fake_session_local():
        return MagicMock()

    monkeypatch.setattr("app.whatsapp.handler.SessionLocal", fake_session_local)
    monkeypatch.setattr(
        "app.whatsapp.handler.get_latest_event",
        lambda db: SimpleNamespace(id="event-1", society_id="soc-1")
    )

    if member is None:
        def fake_ensure_committee_member(phone_number, db):
            raise Exception("Not a committee member")

        monkeypatch.setattr(
            "app.whatsapp.handler.ensure_committee_member",
            fake_ensure_committee_member
        )
    else:
        monkeypatch.setattr(
            "app.whatsapp.handler.ensure_committee_member",
            lambda phone_number, db: member
        )


COMMITTEE_CASES = [
    ("ADD_EXPENSE", "expense water 1200"),
    ("PENDING_PAYMENTS", "pending payments"),
    ("PAYMENT_REQUESTS", "payment requests"),
    ("REFUND_REQUESTS", "refund requests"),
    ("PARTICIPATION_REPORT", "participation report"),
    ("REMIND_FLAT", "remind A-101"),
    ("APPROVE", "approve user REQ-001"),
    ("APPROVE_PAYMENT", "approve payment PAY-001"),
    ("APPROVE_REFUND", "approve refund REF-001"),
    ("PENDING_USERS", "pending users"),
]


@pytest.mark.parametrize("intent,message", COMMITTEE_CASES)
def test_whatsapp_endpoint_committee_commands(monkeypatch, intent, message):
    member = SimpleNamespace(id="member-1", role="chairman")
    _setup_common_mocks(monkeypatch, member=member)

    def fake_onboarding_handler(**kwargs):
        return None

    def fake_committee_handler(**kwargs):
        assert kwargs["intent"] == intent
        return f"committee:{intent}"

    committee_spy = MagicMock(side_effect=fake_committee_handler)
    public_spy = MagicMock(return_value="public")

    monkeypatch.setattr(
        "app.whatsapp.handler.handle_onboarding_intent",
        fake_onboarding_handler
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_committee_intent",
        committee_spy
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_public_intent",
        public_spy
    )

    response = whatsapp_webhook(
        WhatsAppRequest(phone_number="+919999000000", message=message)
    )

    assert response["reply"] == f"committee:{intent}"
    public_spy.assert_not_called()


PUBLIC_CASES = [
    ("ADD_PASS", "add pass veg 1"),
    ("PAY", "pay 500"),
    ("REFUND", "refund 200 reason guest absent"),
    ("MY_PASS", "my pass"),
    ("MY_PAYMENT", "my payment"),
    ("MY_PAYMENT_REQUESTS", "my payment requests"),
    ("MY_REFUND_REQUESTS", "my refund requests"),
    ("MY_PAYMENTS", "my payments"),
    ("MY_BALANCE", "my balance"),
    ("MY_STATUS", "my status"),
    ("SUMMARY", "summary"),
    ("BLOCK_REPORT", "block report"),
    ("HELP", "help"),
    ("COMMANDS", "commands"),
]


@pytest.mark.parametrize("intent,message", PUBLIC_CASES)
def test_whatsapp_endpoint_public_commands(monkeypatch, intent, message):
    _setup_common_mocks(monkeypatch, member=None)

    def fake_onboarding_handler(**kwargs):
        return None

    def fake_public_handler(**kwargs):
        assert kwargs["intent"] == intent
        return f"public:{intent}"

    committee_spy = MagicMock(return_value="committee")
    public_spy = MagicMock(side_effect=fake_public_handler)

    monkeypatch.setattr(
        "app.whatsapp.handler.handle_onboarding_intent",
        fake_onboarding_handler
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_committee_intent",
        committee_spy
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_public_intent",
        public_spy
    )

    response = whatsapp_webhook(
        WhatsAppRequest(phone_number="+919888000000", message=message)
    )

    assert response["reply"] == f"public:{intent}"
    committee_spy.assert_not_called()


ONBOARDING_CASES = [
    ("JOIN", "join ABC123 A-101"),
    ("JOIN_STATUS", "join status"),
]


@pytest.mark.parametrize("intent,message", ONBOARDING_CASES)
def test_whatsapp_endpoint_onboarding_commands(monkeypatch, intent, message):
    _setup_common_mocks(monkeypatch, member=None)

    def fake_onboarding_handler(**kwargs):
        assert kwargs["intent"] == intent
        return f"onboarding:{intent}"

    committee_spy = MagicMock(return_value="committee")
    public_spy = MagicMock(return_value="public")

    monkeypatch.setattr(
        "app.whatsapp.handler.handle_onboarding_intent",
        fake_onboarding_handler
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_committee_intent",
        committee_spy
    )
    monkeypatch.setattr(
        "app.whatsapp.handler.handle_public_intent",
        public_spy
    )

    response = whatsapp_webhook(
        WhatsAppRequest(phone_number="+919777000000", message=message)
    )

    assert response["reply"] == f"onboarding:{intent}"
    committee_spy.assert_not_called()
    public_spy.assert_not_called()
