from types import SimpleNamespace
from unittest.mock import MagicMock

from app.whatsapp.handlers.public_handler import handle_public_intent
from tests.constants import COMMITTEE_PHONE, MEMBER_PHONE


def test_public_add_pass_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.resolve_flat",
        lambda *args, **kwargs: flat
    )

    called = {}

    def fake_add_or_update_pass(**kwargs):
        called["payload"] = kwargs

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.FoodPassService.add_or_update_pass",
        fake_add_or_update_pass
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="ADD_PASS",
        phone_number=COMMITTEE_PHONE,
        message="add pass veg 2 jain 1 kids 1",
        event=event,
        member=member
    )

    assert response.startswith("✅")
    assert called["payload"]["flat_id"] == flat.id


def test_public_add_pass_requires_event():
    response = handle_public_intent(
        db=MagicMock(),
        intent="ADD_PASS",
        phone_number=MEMBER_PHONE,
        message="add pass veg 2",
        event=None,
        member=None
    )
    assert response == "❌ No active event found. Please contact committee."


def test_public_pay_requires_amount():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    response = handle_public_intent(
        db=MagicMock(),
        intent="PAY",
        phone_number=MEMBER_PHONE,
        message="pay",
        event=event,
        member=None
    )
    assert response == "❌ Please specify amount. Example: pay 500"


def test_public_pay_request_for_member(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="PAY-001")
    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.PaymentRequestService.request_payment",
        lambda **kwargs: request
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="PAY",
        phone_number=MEMBER_PHONE,
        message="pay 500",
        event=event,
        member=None
    )

    assert "Request ID: *PAY-001*" in response


def test_public_pay_committee_approves_request(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="PAY-002")
    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.PaymentRequestService.find_matching_request",
        lambda **kwargs: request
    )

    called = {}

    def fake_approve_request(**kwargs):
        called["approved"] = True

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.PaymentRequestService.approve_request",
        fake_approve_request
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="PAY",
        phone_number=COMMITTEE_PHONE,
        message="pay 500",
        event=event,
        member=member
    )

    assert called["approved"] is True
    assert "Payment approved and recorded" in response


def test_public_pay_committee_records_payment(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.resolve_flat",
        lambda *args, **kwargs: flat
    )
    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.PaymentRequestService.find_matching_request",
        lambda **kwargs: None
    )

    called = {}

    def fake_record_payment(**kwargs):
        called["recorded"] = True

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.PaymentService.record_payment",
        fake_record_payment
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="PAY",
        phone_number=COMMITTEE_PHONE,
        message="pay 500",
        event=event,
        member=member
    )

    assert called["recorded"] is True
    assert response == "✅ 💰 Payment received: ₹500"


def test_public_refund_requires_reason():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    response = handle_public_intent(
        db=MagicMock(),
        intent="REFUND",
        phone_number=MEMBER_PHONE,
        message="refund 200",
        event=event,
        member=None
    )
    assert response == "❌ Example: refund 200 reason guest absent"


def test_public_refund_request_for_member(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="REF-001")
    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.RefundRequestService.request_refund",
        lambda **kwargs: request
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="REFUND",
        phone_number=MEMBER_PHONE,
        message="refund 200 reason guest absent",
        event=event,
        member=None
    )

    assert "Request ID: *REF-001*" in response


def test_public_refund_committee_approves_request(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="REF-002")
    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.RefundRequestService.find_matching_request",
        lambda **kwargs: request
    )

    called = {}

    def fake_approve_request(**kwargs):
        called["approved"] = True

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.RefundRequestService.approve_request",
        fake_approve_request
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="REFUND",
        phone_number=COMMITTEE_PHONE,
        message="refund 200 reason guest absent",
        event=event,
        member=member
    )

    assert called["approved"] is True
    assert "Refund approved and processed" in response


def test_public_my_pass_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    food_pass = SimpleNamespace(veg_count=1, jain_count=0, kids_count=1)

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.resolve_flat",
        lambda *args, **kwargs: flat
    )

    monkeypatch.setattr(
        "app.whatsapp.handlers.public_handler.UserQueryService.get_my_pass",
        lambda **kwargs: food_pass
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="MY_PASS",
        phone_number=MEMBER_PHONE,
        message="my pass",
        event=event,
        member=None
    )

    assert "Veg: 1" in response


def test_public_my_pass_requires_event():
    response = handle_public_intent(
        db=MagicMock(),
        intent="MY_PASS",
        phone_number=MEMBER_PHONE,
        message="my pass",
        event=None,
        member=None
    )
    assert response == "❌ No active event found. Please contact committee."


def test_public_help_and_commands():
    response = handle_public_intent(
        db=MagicMock(),
        intent="HELP",
        phone_number=MEMBER_PHONE,
        message="help",
        event=None,
        member=None
    )
    assert response.startswith("✅")

    commands = handle_public_intent(
        db=MagicMock(),
        intent="COMMANDS",
        phone_number=MEMBER_PHONE,
        message="commands",
        event=None,
        member=None
    )
    assert "Available Commands" in commands
