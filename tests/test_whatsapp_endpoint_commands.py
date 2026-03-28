from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.channels.core.handler as core_handler
import app.commands.router as commands_router
from app.channels.core.handler import handle_inbound_message
from app.channels.whatsapp.adapter import parse_webhook_payload
from app.channels.whatsapp.intents import WHATSAPP_INTENTS
from app.channels.whatsapp.ui.committee import (
    build_committee_food_collection_sections,
    build_committee_more_sections,
    build_committee_operations_more_sections,
    build_committee_operations_sections,
    build_committee_sections,
)
from app.channels.whatsapp.ui.dashboard import build_finance_sections, build_my_account_sections, build_society_sections
from app.channels.whatsapp.ui.finance import build_make_payment_sections, build_payments_sections
from app.channels.whatsapp.ui.participation import build_participation_sections
from app.channels.whatsapp.ui.reports import build_reports_sections

pytestmark = [pytest.mark.integration, pytest.mark.endpoint]


def _provider_payload(message: str, phone_number: str) -> dict:
    normalized_phone = phone_number.lstrip("+")
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "entry-1",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": normalized_phone, "profile": {"name": normalized_phone}}],
                    "messages": [{
                        "id": "wamid.test",
                        "from": normalized_phone,
                        "timestamp": "1700000000",
                        "text": {"body": message},
                        "type": "text",
                    }],
                },
            }],
        }],
    }


def _handle_provider_message(message: str, phone_number: str) -> str:
    inbound_messages = parse_webhook_payload(_provider_payload(message, phone_number))
    assert len(inbound_messages) == 1
    return handle_inbound_message(
        inbound_messages[0],
        session_factory=core_handler.SessionLocal,
        committee_member_resolver=core_handler.ensure_committee_member,
        latest_event_getter=core_handler.get_latest_event_for_society,
        intent_detector=commands_router.detect_intent,
        onboarding_intent_handler=core_handler.handle_onboarding_intent,
        committee_intent_handler=core_handler.handle_committee_intent,
        public_intent_handler=core_handler.handle_public_intent,
    )


def _setup_common_mocks(monkeypatch, member=None):
    def fake_session_local():
        return MagicMock()

    monkeypatch.setattr("app.channels.core.handler.SessionLocal", fake_session_local)
    monkeypatch.setattr(
        "app.channels.core.handler.get_latest_event_for_society",
        lambda db, society_id: SimpleNamespace(id="event-1", society_id="soc-1", status="ACTIVE")
    )
    monkeypatch.setattr("app.channels.core.handler.get_intent_state_warning", lambda **kwargs: None)

    if member is None:
        def fake_ensure_committee_member(phone_number, db, **kwargs):
            raise Exception("Not a committee member")

        monkeypatch.setattr(
            "app.channels.core.handler.ensure_committee_member",
            fake_ensure_committee_member
        )
    else:
        monkeypatch.setattr(
            "app.channels.core.handler.ensure_committee_member",
            lambda phone_number, db, **kwargs: member
        )


COMMITTEE_CASES = [
    ("ADD_EXPENSE", "expense water 1200"),
    ("PENDING_PAYMENTS", "pending payments"),
    ("PAYMENT_REQUESTS", "payment requests"),
    ("REFUND_REQUESTS", "refund requests"),
    ("PARTICIPATION_REPORT", "participation report"),
    ("REPORT_OPTIONS", "report options"),
    ("EXPORT_SELECTION", "export::report-1"),
    ("REMIND_FLAT", "remind A-101"),
    ("APPROVE", "approve user REQ-001"),
    ("APPROVE_PAYMENT", "approve payment PAY-001"),
    ("APPROVE_REFUND", "approve refund REF-001"),
    ("PENDING_USERS", "pending users"),
    ("GENERATE_FOOD_TOKENS", "generate food tokens"),
    ("OPEN_FOOD_COUNTER", "open food counter"),
    ("VERIFY_FOOD_TOKEN", "verify food token AB2K9M"),
    ("SCAN_FOOD_QR", "scan food qr AB2K9M"),
    ("SERVE_FOOD_FLAT", "serve flat A-101"),
    ("FLAT_PASS_STATUS", "flat passes A-101"),
    ("TOKEN_STATUS", "token status AB2K9M"),
    ("FOOD_DASHBOARD", "food dashboard"),
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
        "app.channels.core.handler.handle_onboarding_intent",
        fake_onboarding_handler
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_committee_intent",
        committee_spy
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_public_intent",
        public_spy
    )

    response = _handle_provider_message(message, "+919999000000")

    assert response == f"committee:{intent}"
    public_spy.assert_not_called()


PUBLIC_CASES = [
    ("ADD_PASS", "add pass veg 1"),
    ("PAY", "pay 500"),
    ("REFUND", "refund 200 reason guest absent"),
    ("MY_PASS", "my pass"),
    ("MY_TOKENS", "my tokens"),
    ("MY_PAYMENT_REQUESTS", "my payment requests"),
    ("MY_REFUND_REQUESTS", "my refund requests"),
    ("MY_PAYMENTS", "my payments"),
    ("MY_BALANCE", "my balance"),
    ("MY_STATUS", "my status"),
    ("SUMMARY", "summary"),
    ("BLOCK_REPORT", "block report"),
    ("HELP", "help"),
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
        "app.channels.core.handler.handle_onboarding_intent",
        fake_onboarding_handler
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_committee_intent",
        committee_spy
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_public_intent",
        public_spy
    )

    response = _handle_provider_message(message, "+919888000000")

    assert response == f"public:{intent}"
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
        "app.channels.core.handler.handle_onboarding_intent",
        fake_onboarding_handler
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_committee_intent",
        committee_spy
    )
    monkeypatch.setattr(
        "app.channels.core.handler.handle_public_intent",
        public_spy
    )

    response = _handle_provider_message(message, "+919777000000")

    assert response == f"onboarding:{intent}"
    committee_spy.assert_not_called()
    public_spy.assert_not_called()


def test_whatsapp_ui_rows_cover_whatsapp_intents():
    intent_keywords = set(WHATSAPP_INTENTS.values())

    sections = []
    sections.extend(build_my_account_sections())
    sections.extend(build_society_sections())
    sections.extend(build_finance_sections(include_payment_actions=True))
    sections.extend(build_participation_sections(include_add_pass=True))
    sections.extend(build_payments_sections())
    sections.extend(build_make_payment_sections(outstanding_amount="500"))
    sections.extend(build_reports_sections(is_committee=True))
    sections.extend(build_committee_sections())
    sections.extend(build_committee_more_sections())
    sections.extend(build_committee_operations_more_sections())
    sections.extend(build_committee_food_collection_sections())

    row_ids = {
        row["id"]
        for section in sections
        for row in section["rows"]
    }

    expected_template_only = {"menu", "help", "pay", "join", "refund", "approve user", "approve payment", "approve refund", "add event", "activate event", "lock passes", "start event", "close event", "add sponsor", "refund sponsor", "expense", "remind", "announce event", "announce society", "committee members", "add committee member", "remove committee member", "change committee role"}
    template_helper_rows = {
        "ui::approve-user",
        "ui::approve-payment",
        "ui::approve-refund",
        "ui::join-society",
        "ui::make-payment",
        "ui::request-refund",
    }

    missing = sorted(
        keyword
        for keyword in intent_keywords
        if keyword not in row_ids and keyword not in expected_template_only
    )

    assert not missing
    assert template_helper_rows.issubset(row_ids)


def test_committee_operations_menu_contains_announce_actions():
    sections = build_committee_operations_sections()
    row_ids = {row["id"] for section in sections for row in section["rows"]}

    assert "announce event" in row_ids
    assert "announce society" in row_ids
