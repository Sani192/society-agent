from types import SimpleNamespace
from unittest.mock import MagicMock

from app.whatsapp.handlers.committee_handler import handle_committee_intent
from tests.constants import COMMITTEE_PHONE
from tests.utils import QueryMock


def test_committee_add_expense_forbidden():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense water 1200",
        event=event,
        member=member
    )
    assert response.startswith("⚠️")


def test_committee_add_expense_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="secretary")

    called = {}

    def fake_add_expense(**kwargs):
        called["added"] = True

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.ExpenseService.add_expense",
        fake_add_expense
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense water 1200",
        event=event,
        member=member
    )

    assert called["added"] is True
    assert "Expense added: ₹1,200" in response


def test_committee_pending_payments_forbidden():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="secretary")
    response = handle_committee_intent(
        db=MagicMock(),
        intent="PENDING_PAYMENTS",
        message="pending payments",
        event=event,
        member=member
    )
    assert response.startswith("⚠️")


def test_committee_pending_users_forbidden():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    response = handle_committee_intent(
        db=MagicMock(),
        intent="PENDING_USERS",
        message="pending users",
        event=event,
        member=member
    )
    assert response.startswith("⚠️")


def test_committee_pending_payments_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.PendingPaymentReport.get_pending_flats",
        lambda **kwargs: [{"flat": "A-101", "pending": 200}]
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PENDING_PAYMENTS",
        message="pending payments",
        event=event,
        member=member
    )

    assert "A-101 – Pending ₹200" in response


def test_committee_payment_requests(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(
        request_code="PAY-001",
        amount=500,
        requested_by="+919999000000",
        status="requested"
    )
    flat = SimpleNamespace(flat_number="A-101")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.list_requests",
        lambda **kwargs: [(request, flat)]
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PAYMENT_REQUESTS",
        message="payment requests",
        event=event,
        member=member
    )

    assert "PAY-001" in response
    assert "A-101" in response


def test_committee_refund_requests(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(
        request_code="REF-001",
        amount=300,
        requested_by="+919999000000",
        status="requested"
    )
    flat = SimpleNamespace(flat_number="B-201")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.RefundRequestService.list_requests",
        lambda **kwargs: [(request, flat)]
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_REQUESTS",
        message="refund requests",
        event=event,
        member=member
    )

    assert "REF-001" in response
    assert "B-201" in response


def test_committee_participation_report(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")
    member = SimpleNamespace(id="member-1", role="chairman")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.EventParticipationReport.generate",
        lambda **kwargs: {"participating": ["A-101"], "not_participating": ["A-102"]}
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PARTICIPATION_REPORT",
        message="participation report",
        event=event,
        member=member
    )

    assert "A-101" in response
    assert "A-102" in response


def test_committee_remind_flat_requires_number():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    response = handle_committee_intent(
        db=MagicMock(),
        intent="REMIND_FLAT",
        message="remind",
        event=event,
        member=member
    )
    assert response == "❌ Example: remind A-101"


def test_committee_remind_flat_success():
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")
    member = SimpleNamespace(id="member-1", role="treasurer")
    flat = SimpleNamespace(id="flat-1", flat_number="A-101")
    food_pass = SimpleNamespace(total_amount=1000, is_participating=True)

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=flat),
        QueryMock(first_result=food_pass),
        QueryMock(scalar_result=200),
        QueryMock(scalar_result=50)
    ]

    response = handle_committee_intent(
        db=db,
        intent="REMIND_FLAT",
        message="remind A-101",
        event=event,
        member=member
    )

    assert "pending amount" in response
    assert "₹750" in response


def test_committee_remind_flat_not_found():
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")
    member = SimpleNamespace(id="member-1", role="treasurer")

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=None)
    ]

    response = handle_committee_intent(
        db=db,
        intent="REMIND_FLAT",
        message="remind A-999",
        event=event,
        member=member
    )

    assert response == "❌ Flat not found."


def test_committee_remind_flat_not_joined():
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")
    member = SimpleNamespace(id="member-1", role="treasurer")
    flat = SimpleNamespace(id="flat-1", flat_number="A-101")

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=flat),
        QueryMock(first_result=None)
    ]

    response = handle_committee_intent(
        db=db,
        intent="REMIND_FLAT",
        message="remind A-101",
        event=event,
        member=member
    )

    assert response == "❌ Flat has not joined the event."


def test_committee_approve_user(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    called = {}

    def fake_approve_user(**kwargs):
        called["approved"] = True

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.AdminApprovalService.approve_user",
        fake_approve_user
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE",
        message="Approve User req-001",
        event=event,
        member=member
    )

    assert called["approved"] is True
    assert "REQ-001" in response


def test_committee_approve_user_forbidden():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE",
        message="Approve User req-001",
        event=event,
        member=member
    )

    assert response.startswith("⚠️")


def test_committee_pending_users(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")
    pending = [
        SimpleNamespace(
            request_code="REQ-001",
            flat_number="A-101",
            created_at=SimpleNamespace(strftime=lambda fmt: "01 Jan 2026 10:00")
        )
    ]

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.AdminOnboardingQueryService.list_pending_users",
        lambda **kwargs: pending
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PENDING_USERS",
        message="pending users",
        event=event,
        member=member
    )

    assert "REQ-001" in response


def test_committee_approve_payment(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="PAY-001", status="requested")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.get_request_by_code",
        lambda **kwargs: request
    )

    called = {}

    def fake_approve_request(**kwargs):
        called["approved"] = kwargs["request"].request_code

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.approve_request",
        fake_approve_request
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_PAYMENT",
        message="Approve Payment pay-001",
        event=event,
        member=member
    )

    assert called["approved"] == "PAY-001"
    assert response == "✅ Payment approved (PAY-001)"


def test_committee_approve_payment_not_found(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.get_request_by_code",
        lambda **kwargs: None
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_PAYMENT",
        message="Approve Payment pay-999",
        event=event,
        member=member
    )

    assert response == "❌ Payment request not found."


def test_committee_approve_payment_already_processed(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="PAY-002", status="approved")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.get_request_by_code",
        lambda **kwargs: request
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_PAYMENT",
        message="Approve Payment pay-002",
        event=event,
        member=member
    )

    assert response == "⚠️ Payment request already processed."


def test_committee_approve_refund(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="REF-001", status="requested")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.RefundRequestService.get_request_by_code",
        lambda **kwargs: request
    )

    called = {}

    def fake_approve_refund(**kwargs):
        called["approved"] = kwargs["request"].request_code

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.RefundRequestService.approve_request",
        fake_approve_refund
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_REFUND",
        message="Approve Refund ref-001",
        event=event,
        member=member
    )

    assert called["approved"] == "REF-001"
    assert response == "✅ Refund approved (REF-001)"


def test_committee_refund_sponsor_surfaces_error(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    def fake_process_refund(**kwargs):
        raise Exception("Refund exceeds contribution amount. Remaining refundable amount: ₹0")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.ContributionRefundService.process_refund",
        fake_process_refund
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_SPONSOR",
        message="refund sponsor SP-001 500 reason extra",
        event=event,
        member=member
    )

    assert response == "❌ Refund exceeds contribution amount. Remaining refundable amount: ₹0"


def test_committee_approve_refund_already_processed(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="REF-002", status="approved")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.RefundRequestService.get_request_by_code",
        lambda **kwargs: request
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_REFUND",
        message="Approve Refund ref-002",
        event=event,
        member=member
    )

    assert response == "⚠️ Refund request already processed."
