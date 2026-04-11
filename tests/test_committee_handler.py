from datetime import datetime

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.handlers.shared.committee import handle_committee_intent
from app.utils.response import safe_error_message
from app.permissions.command_policy import get_intent_state_warning
from app.channels.whatsapp.committee_action_session import clear_committee_action_session
from tests.utils import QueryMock


def test_committee_add_expense_forbidden():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense water 1200",
        event=event,
        member=member,
    )
    assert response.startswith("⚠️")


def test_committee_add_expense_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="secretary")

    called = {}

    def fake_add_expense(**kwargs):
        called["added"] = True

    monkeypatch.setattr(
        "app.handlers.shared.committee.ExpenseService.add_expense",
        fake_add_expense,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense water 1200",
        event=event,
        member=member,
    )

    assert called["added"] is True
    assert "Expense added: ₹1,200" in response


def test_committee_add_expense_success_hindi(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="secretary")

    monkeypatch.setattr(
        "app.handlers.shared.committee.ExpenseService.add_expense",
        lambda **kwargs: None,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense water 1200",
        event=event,
        member=member,
        lang="hi",
    )

    assert "खर्च जोड़ा गया" in response


def test_committee_pending_payments_forbidden():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="secretary")
    response = handle_committee_intent(
        db=MagicMock(),
        intent="PENDING_PAYMENTS",
        message="pending payments",
        event=event,
        member=member,
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
        member=member,
    )
    assert response.startswith("⚠️")


def test_committee_pending_payments_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")

    monkeypatch.setattr(
        "app.handlers.shared.committee.PendingPaymentReport.get_pending_flats",
        lambda **kwargs: [{"flat": "A-101", "pending": 200}],
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PENDING_PAYMENTS",
        message="pending payments",
        event=event,
        member=member,
    )

    assert "A-101 – Pending ₹200" in response


def test_committee_payment_requests(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(
        request_code="PAY-001",
        amount=500,
        requested_by="+919999000000",
        status="requested",
    )
    flat = SimpleNamespace(flat_number="A-101")

    monkeypatch.setattr(
        "app.handlers.shared.committee.PaymentRequestService.list_requests",
        lambda **kwargs: [(request, flat)],
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PAYMENT_REQUESTS",
        message="payment requests",
        event=event,
        member=member,
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
        status="requested",
    )
    flat = SimpleNamespace(flat_number="B-201")

    monkeypatch.setattr(
        "app.handlers.shared.committee.RefundRequestService.list_requests",
        lambda **kwargs: [(request, flat)],
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_REQUESTS",
        message="refund requests",
        event=event,
        member=member,
    )

    assert "REF-001" in response
    assert "B-201" in response


def test_committee_participation_report(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")
    member = SimpleNamespace(id="member-1", role="chairman")

    monkeypatch.setattr(
        "app.handlers.shared.committee.EventParticipationReport.generate",
        lambda **kwargs: {"participating": ["A-101"], "not_participating": ["A-102"]},
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PARTICIPATION_REPORT",
        message="participation report",
        event=event,
        member=member,
    )

    assert "A-101" in response
    assert "A-102" in response


def test_committee_remind_flat_requires_number():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    inbound = SimpleNamespace(sender_id="sender-remind-1", metadata={})
    response = handle_committee_intent(
        db=MagicMock(),
        intent="REMIND_FLAT",
        message="remind",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    clear_committee_action_session("member-1:sender-remind-1")
    assert "Please share flat number. Example: A-101" in response
    assert "Type `cancel` to stop." in response


def test_committee_add_expense_guided_flow(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-g1", role="secretary")
    inbound = SimpleNamespace(sender_id="sender-g1", metadata={})

    called = {}

    def fake_add_expense(**kwargs):
        called["description"] = kwargs["description"]
        called["amount"] = kwargs["amount"]

    monkeypatch.setattr(
        "app.handlers.shared.committee.ExpenseService.add_expense",
        fake_add_expense,
    )

    step1 = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    assert "Please share expense reason/category." in step1
    assert "Type `cancel` to stop." in step1

    step2 = handle_committee_intent(
        db=MagicMock(),
        intent="COMMITTEE_PENDING_ACTION",
        message="Water cans",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    assert "Please share expense amount. Example: 1200" in step2
    assert "Type `cancel` to stop." in step2

    step3 = handle_committee_intent(
        db=MagicMock(),
        intent="COMMITTEE_PENDING_ACTION",
        message="1200",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    clear_committee_action_session("member-g1:sender-g1")
    assert called["description"] == "Water cans"
    assert called["amount"] == 1200
    assert "Expense added: ₹1,200" in step3


def test_committee_add_sponsor_guided_flow(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-g2", role="chairman")
    inbound = SimpleNamespace(sender_id="sender-g2", metadata={})

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    called = {}

    def fake_add_contribution(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "app.handlers.shared.committee.ContributionService.add_contribution",
        fake_add_contribution,
    )

    step1 = handle_committee_intent(
        db=db,
        intent="ADD_SPONSOR",
        message="add sponsor",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    assert "Sponsor type? Reply: monetary or in-kind" in step1
    assert "Type `cancel` to stop." in step1

    handle_committee_intent(
        db=db,
        intent="COMMITTEE_PENDING_ACTION",
        message="monetary",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=db,
        intent="COMMITTEE_PENDING_ACTION",
        message="ABC Corp",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    step4 = handle_committee_intent(
        db=db,
        intent="COMMITTEE_PENDING_ACTION",
        message="5000",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    clear_committee_action_session("member-g2:sender-g2")
    assert called["contribution_type"] == "sponsor"
    assert called["amount"] == 5000
    assert step4 == "✅ 🤝 *Sponsor added*\nSponsor added successfully."


def test_committee_refund_sponsor_guided_flow(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-g3", role="chairman")
    inbound = SimpleNamespace(sender_id="sender-g3", metadata={})

    called = {}

    def fake_process_refund(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "app.handlers.shared.committee.ContributionRefundService.process_refund",
        fake_process_refund,
    )

    step1 = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_SPONSOR",
        message="refund sponsor",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    assert "Please share contribution code. Example: SP-001" in step1
    assert "Type `cancel` to stop." in step1

    handle_committee_intent(
        db=MagicMock(),
        intent="COMMITTEE_PENDING_ACTION",
        message="sp-001",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=MagicMock(),
        intent="COMMITTEE_PENDING_ACTION",
        message="500",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    step4 = handle_committee_intent(
        db=MagicMock(),
        intent="COMMITTEE_PENDING_ACTION",
        message="duplicate charge",
        event=event,
        member=member,
        inbound_message=inbound,
    )
    clear_committee_action_session("member-g3:sender-g3")
    assert called["contribution_code"] == "SP-001"
    assert called["amount"] == 500
    assert called["reason"] == "duplicate charge"
    assert step4 == "✅ ↩️ *Refund processed*\nSponsor refund processed (SP-001)."


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
        QueryMock(scalar_result=50),
    ]

    response = handle_committee_intent(
        db=db, intent="REMIND_FLAT", message="remind A-101", event=event, member=member
    )

    assert "pending amount" in response
    assert "₹750" in response


def test_committee_remind_flat_not_found():
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")
    member = SimpleNamespace(id="member-1", role="treasurer")

    db = MagicMock()
    db.query.side_effect = [QueryMock(first_result=None)]

    response = handle_committee_intent(
        db=db, intent="REMIND_FLAT", message="remind A-999", event=event, member=member
    )

    assert response == "❌ Flat not found."


def test_committee_remind_flat_not_joined():
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Diwali")
    member = SimpleNamespace(id="member-1", role="treasurer")
    flat = SimpleNamespace(id="flat-1", flat_number="A-101")

    db = MagicMock()
    db.query.side_effect = [QueryMock(first_result=flat), QueryMock(first_result=None)]

    response = handle_committee_intent(
        db=db, intent="REMIND_FLAT", message="remind A-101", event=event, member=member
    )

    assert response == "❌ Flat has not joined the event."


def test_committee_approve_user(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    called = {}

    def fake_approve_user(**kwargs):
        called["approved"] = True

    monkeypatch.setattr(
        "app.handlers.shared.committee.AdminApprovalService.approve_user",
        fake_approve_user,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE",
        message="Approve User req-001",
        event=event,
        member=member,
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
        member=member,
    )

    assert response.startswith("⚠️")


def test_committee_pending_users(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")
    pending = [
        (
            SimpleNamespace(
                request_code="REQ-001",
                created_at=SimpleNamespace(strftime=lambda fmt: "01 Jan 2026 10:00"),
            ),
            SimpleNamespace(flat_number="A-101"),
        )
    ]

    monkeypatch.setattr(
        "app.handlers.shared.committee.AdminOnboardingQueryService.list_pending_users",
        lambda **kwargs: pending,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="PENDING_USERS",
        message="pending users",
        event=event,
        member=member,
    )

    assert "REQ-001" in response


def test_committee_approve_payment(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="PAY-001", status="requested")

    monkeypatch.setattr(
        "app.handlers.shared.committee.PaymentRequestService.get_request_by_code",
        lambda **kwargs: request,
    )

    called = {}

    def fake_approve_request(**kwargs):
        called["approved"] = kwargs["request"].request_code

    monkeypatch.setattr(
        "app.handlers.shared.committee.PaymentRequestService.approve_request",
        fake_approve_request,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_PAYMENT",
        message="Approve Payment pay-001",
        event=event,
        member=member,
    )

    assert called["approved"] == "PAY-001"
    assert response == "✅ Payment approved (PAY-001)"


def test_committee_approve_payment_not_found(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")

    monkeypatch.setattr(
        "app.handlers.shared.committee.PaymentRequestService.get_request_by_code",
        lambda **kwargs: None,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_PAYMENT",
        message="Approve Payment pay-999",
        event=event,
        member=member,
    )

    assert response == "❌ Payment request not found."


def test_committee_approve_payment_already_processed(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="PAY-002", status="approved")

    monkeypatch.setattr(
        "app.handlers.shared.committee.PaymentRequestService.get_request_by_code",
        lambda **kwargs: request,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_PAYMENT",
        message="Approve Payment pay-002",
        event=event,
        member=member,
    )

    assert response == "⚠️ Payment request already processed."


def test_committee_approve_refund(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="REF-001", status="requested")

    monkeypatch.setattr(
        "app.handlers.shared.committee.RefundRequestService.get_request_by_code",
        lambda **kwargs: request,
    )

    called = {}

    def fake_approve_refund(**kwargs):
        called["approved"] = kwargs["request"].request_code

    monkeypatch.setattr(
        "app.handlers.shared.committee.RefundRequestService.approve_request",
        fake_approve_refund,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_REFUND",
        message="Approve Refund ref-001",
        event=event,
        member=member,
    )

    assert called["approved"] == "REF-001"
    assert response == "✅ Refund approved (REF-001)"


def test_committee_refund_sponsor_surfaces_error(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    def fake_process_refund(**kwargs):
        raise Exception(
            "Refund exceeds contribution amount. Remaining refundable amount: ₹0"
        )

    monkeypatch.setattr(
        "app.handlers.shared.committee.ContributionRefundService.process_refund",
        fake_process_refund,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_SPONSOR",
        message="refund sponsor SP-001 500 reason extra",
        event=event,
        member=member,
    )

    assert response == f"❌ {safe_error_message()}"




def test_committee_refund_sponsor_prompts_override_when_required(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    def fake_process_refund(**kwargs):
        raise Exception("Action 'REFUND_CONTRIBUTION' requires override in state 'CLOSED'")

    monkeypatch.setattr(
        "app.handlers.shared.committee.ContributionRefundService.process_refund",
        fake_process_refund,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_SPONSOR",
        message="refund sponsor SP-001 500 reason extra",
        event=event,
        member=member,
    )

    assert "override reason" in response.lower()


def test_committee_refund_sponsor_direct_passes_override_reason(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    called = {}

    def fake_process_refund(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "app.handlers.shared.committee.ContributionRefundService.process_refund",
        fake_process_refund,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_SPONSOR",
        message="refund sponsor SP-001 500 reason extra charge override audit approved",
        event=event,
        member=member,
    )

    assert called["override_reason"] == "audit approved"
    assert response == "✅ ↩️ *Refund processed*\nSponsor refund processed (SP-001)."


def test_committee_approve_refund_already_processed(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")
    request = SimpleNamespace(request_code="REF-002", status="approved")

    monkeypatch.setattr(
        "app.handlers.shared.committee.RefundRequestService.get_request_by_code",
        lambda **kwargs: request,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="APPROVE_REFUND",
        message="Approve Refund ref-002",
        event=event,
        member=member,
    )

    assert response == "⚠️ Refund request already processed."


def test_committee_export_selection_requires_active_session():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(
        id="member-1", name="Chairman Rao", role="chairman", society_id="soc-1", phone_number="919999000000"
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="EXPORT_SELECTION",
        message="export 1",
        event=event,
        member=member,
    )

    assert response == "ℹ️ No active export session. Send `report options` first."


def test_committee_report_options_success():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(
        id="member-1", name="Chairman Rao", role="chairman", society_id="soc-1", phone_number="919999000000"
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REPORT_OPTIONS",
        message="report options",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert "Choose report event + report" in response
    assert "report export --category" not in response
    assert "export <number>" in response
    assert "🗂️ *Financial*" in response
    assert "🗂️ *Admin*" in response
    assert "🗂️ *Governance*" in response
    assert "↪ Reply: export" in response
    assert "report export --category" not in response


def test_committee_report_options_filtered_by_role():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(
        id="member-1", role="secretary", society_id="soc-1", phone_number="919999000000"
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REPORT_OPTIONS",
        message="report options",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert "Member Directory" in response
    assert "Onboarding Status" in response
    assert "Ledger" in response
    assert "Event Financial Summary" not in response


def test_committee_add_event_starts_guided_setup_on_exact_command():
    member = SimpleNamespace(id="member-guided-1", role="secretary", society_id="soc-1")

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="add event",
        event=None,
        member=member,
        inbound_message=SimpleNamespace(sender_id="999", metadata={}),
    )

    assert "Event setup (guided)" in response
    assert "What is the event name?" in response


def test_committee_add_event_uses_wizard_when_fields_missing(monkeypatch):
    member = SimpleNamespace(id="member-guided-2", role="secretary", society_id="soc-1")

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="add event Holi | 2026-03-10 19:00",
        event=None,
        member=member,
        inbound_message=SimpleNamespace(sender_id="998", metadata={}),
    )

    assert "Event setup (guided)" in response
    assert "What is the event name?" in response


def test_committee_add_event_wizard_completes_and_creates_event(monkeypatch):
    member = SimpleNamespace(id="member-guided-3", role="secretary", society_id="soc-1")
    inbound = SimpleNamespace(sender_id="997", metadata={})

    created = {}

    def fake_create_event(**kwargs):
        created.update(kwargs)
        return SimpleNamespace(
            name=kwargs["name"],
            event_date=kwargs["event_date"],
            food_types=kwargs["food_types"],
            charge_per_adult=kwargs["charge_per_adult"],
            charge_per_child=kwargs["charge_per_child"],
            payment_deadline=kwargs["payment_deadline"],
        )

    monkeypatch.setattr(
        "app.handlers.shared.committee.EventService.create_event",
        fake_create_event,
    )

    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="add event",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="Summer Fest",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="2026-05-01 19:30",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="veg,jain",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="350",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="150",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="skip",
        event=None,
        member=member,
        inbound_message=inbound,
    )

    assert "Event created" in response
    assert created["name"] == "Summer Fest"
    assert created["food_types"] == ["veg", "jain"]
    assert created["charge_per_adult"] == 350
    assert created["charge_per_child"] == 150
    assert created["payment_deadline"] is None


def test_committee_add_event_wizard_reprompts_on_invalid_date():
    member = SimpleNamespace(id="member-guided-4", role="secretary", society_id="soc-1")
    inbound = SimpleNamespace(sender_id="996", metadata={})

    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="add event",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="Monsoon Meet",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EVENT",
        message="tomorrow evening",
        event=None,
        member=member,
        inbound_message=inbound,
    )

    assert response.startswith("❌")
    assert "YYYY-MM-DD HH:MM" in response


@pytest.mark.parametrize(
    "intent,message,patch_path,roles",
    [
        (
            "ADD_EXPENSE",
            "expense water 1200 override closed correction",
            "app.handlers.shared.committee.ExpenseService.add_expense",
            ["chairman", "secretary", "treasurer", "committee_member"],
        ),
        (
            "ADD_SPONSOR",
            "add sponsor ABC Corp 5000 override closed correction",
            "app.handlers.shared.committee.ContributionService.add_contribution",
            ["chairman", "secretary", "treasurer", "committee_member"],
        ),
        (
            "REFUND_SPONSOR",
            "refund sponsor SP-001 500 reason duplicate charge override closed correction",
            "app.handlers.shared.committee.ContributionRefundService.process_refund",
            ["chairman", "secretary", "treasurer", "committee_member"],
        ),
    ],
)
def test_closed_override_allows_all_committee_roles(monkeypatch, intent, message, patch_path, roles):
    event = SimpleNamespace(id="event-1", society_id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.committee._event_state_for_intent",
        lambda **kwargs: "CLOSED",
    )

    called = {}

    def fake_call(**kwargs):
        called[kwargs["performed_by"]] = kwargs

    monkeypatch.setattr(patch_path, fake_call)

    for role in roles:
        member = SimpleNamespace(id=f"member-{role}", role=role)
        response = handle_committee_intent(
            db=MagicMock(),
            intent=intent,
            message=message,
            event=event,
            member=member,
        )

        assert response.startswith("✅")
        assert called[f"member-{role}"]["override_reason"] == "closed correction"


def test_closed_override_still_blocks_missing_reason(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="treasurer")

    monkeypatch.setattr(
        "app.handlers.shared.committee._event_state_for_intent",
        lambda **kwargs: "CLOSED",
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense water 1200",
        event=event,
        member=member,
    )

    assert response.startswith("⚠️")




def test_committee_member_can_announce_event(monkeypatch):
    member = SimpleNamespace(id="member-1", role="committee_member", society_id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.committee.AnnouncementManager.queue",
        lambda **kwargs: SimpleNamespace(
            accepted_count=2,
            skipped_count=0,
            announcement_id="ann-cm-1",
        ),
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ANNOUNCE_EVENT",
        message="announce event Welcome all",
        event=SimpleNamespace(id="event-1", society_id="soc-1"),
        member=member,
    )

    assert response.startswith("✅")
    assert "Accepted: 2" in response


def test_committee_member_cannot_add_expense_without_override():
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="committee_member")

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_EXPENSE",
        message="expense water 1200",
        event=event,
        member=member,
    )

    assert response.startswith("⚠️")

def test_committee_announce_event_requires_committee_role():
    member = SimpleNamespace(id="member-1", role="member", society_id="soc-1")

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ANNOUNCE_EVENT",
        message="announce event Dinner starts at 8pm",
        event=None,
        member=member,
    )

    assert response.startswith("⚠️")


def test_committee_announce_event_prompts_for_body_when_missing():
    member = SimpleNamespace(id="member-1", role="secretary", society_id="soc-1")
    inbound = SimpleNamespace(sender_id="sender-ann-1", metadata={})

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ANNOUNCE_EVENT",
        message="announce event   ",
        event=None,
        member=member,
        inbound_message=inbound,
    )

    clear_committee_action_session("member-1:sender-ann-1")
    assert response.startswith("ℹ️")
    assert "Please type the event announcement text" in response


def test_committee_announce_society_rejects_over_limit_body():
    member = SimpleNamespace(id="member-1", role="chairman", society_id="soc-1")
    long_body = "x" * 4097

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ANNOUNCE_SOCIETY",
        message=f"announce society {long_body}",
        event=None,
        member=member,
    )

    assert response.startswith("❌")
    assert "too long" in response


def test_committee_announce_event_acknowledges_queued_count(monkeypatch):
    member = SimpleNamespace(id="member-1", role="treasurer", society_id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.committee.AnnouncementManager.queue",
        lambda **kwargs: SimpleNamespace(
            accepted_count=27,
            skipped_count=3,
            announcement_id="ann-123",
        ),
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ANNOUNCE_EVENT",
        message="announce event Dinner starts at 8pm",
        event=SimpleNamespace(id="event-1", society_id="soc-1"),
        member=member,
    )

    assert response.startswith("✅")
    assert "Accepted: 27" in response
    assert "Skipped: 3" in response
    assert "Announcement ID: ann-123" in response


def test_committee_announce_event_pending_flow_rejects_empty_then_accepts(monkeypatch):
    member = SimpleNamespace(id="member-1", role="chairman", society_id="soc-1")
    inbound = SimpleNamespace(sender_id="sender-ann-2", metadata={})

    monkeypatch.setattr(
        "app.handlers.shared.committee.AnnouncementManager.queue",
        lambda **kwargs: SimpleNamespace(
            accepted_count=9,
            skipped_count=1,
            announcement_id="ann-999",
        ),
    )

    step1 = handle_committee_intent(
        db=MagicMock(),
        intent="ANNOUNCE_EVENT",
        message="announce event",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    assert "Please type the event announcement text" in step1

    step2 = handle_committee_intent(
        db=MagicMock(),
        intent="COMMITTEE_PENDING_ACTION",
        message="   ",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    assert step2.startswith("❌")
    assert "cannot be empty" in step2

    step3 = handle_committee_intent(
        db=MagicMock(),
        intent="COMMITTEE_PENDING_ACTION",
        message="Please arrive by 8pm",
        event=None,
        member=member,
        inbound_message=inbound,
    )
    clear_committee_action_session("member-1:sender-ann-2")
    assert step3.startswith("✅")
    assert "Accepted: 9" in step3
    assert "Skipped: 1" in step3
    assert "Announcement ID: ann-999" in step3


def test_committee_announce_event_returns_error_when_no_active_event(monkeypatch):
    member = SimpleNamespace(id="member-1", role="chairman", society_id="soc-1")

    def raise_no_event(**kwargs):
        raise ValueError("No active event found. Please contact committee.")

    monkeypatch.setattr(
        "app.handlers.shared.committee.AnnouncementManager.queue",
        raise_no_event,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ANNOUNCE_EVENT",
        message="announce event Starts at 8pm",
        event=None,
        member=member,
    )

    assert response == f"❌ {safe_error_message()}"


def test_committee_list_members(monkeypatch):
    member = SimpleNamespace(id="member-l1", role="chairman", society_id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.committee.CommitteeMemberService.list_members",
        lambda **kwargs: [
            SimpleNamespace(
                id="cm-1",
                name="Alice",
                role="chairman",
                phone_number="919999900000",
                is_active=True,
            )
        ],
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="LIST_COMMITTEE_MEMBERS",
        message="committee members",
        event=None,
        member=member,
    )

    assert "Alice" in response
    assert "cm-1" in response


def test_committee_add_member_permission_warning(monkeypatch):
    member = SimpleNamespace(id="member-l2", role="secretary", society_id="soc-1")

    def _raise(**kwargs):
        raise PermissionError("Only chairman can perform this action.")

    monkeypatch.setattr(
        "app.handlers.shared.committee.CommitteeMemberService.add_member",
        _raise,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="ADD_COMMITTEE_MEMBER",
        message="add committee member Bob|+919999000001|treasurer",
        event=None,
        member=member,
    )

    assert response.startswith("⚠️")


def test_committee_change_role_success(monkeypatch):
    member = SimpleNamespace(id="member-l3", role="chairman", society_id="soc-1")

    monkeypatch.setattr(
        "app.handlers.shared.committee.CommitteeMemberService.change_role",
        lambda **kwargs: SimpleNamespace(name="Carl", role="secretary"),
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="CHANGE_COMMITTEE_ROLE",
        message="change committee role cm-2 secretary",
        event=None,
        member=member,
    )

    assert "Carl" in response
    assert "secretary" in response

def test_committee_generate_food_tokens(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Holi")
    member = SimpleNamespace(id="member-1", role="secretary")

    callback_calls = {}

    def fake_generate_tokens_for_event(**kwargs):
        callback_calls["notify_callback"] = kwargs.get("notify_callback")
        return [SimpleNamespace(token_code="AA22BB"), SimpleNamespace(token_code="CC33DD")]

    monkeypatch.setattr(
        "app.handlers.shared.committee.FoodCollectionService.generate_tokens_for_event",
        fake_generate_tokens_for_event,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="GENERATE_FOOD_TOKENS",
        message="generate food tokens",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert "Generated 2 food tokens" in response
    assert callable(callback_calls["notify_callback"])


def test_committee_generate_food_tokens_invokes_notification_callback(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Holi")
    member = SimpleNamespace(id="member-1", role="secretary")

    callback_calls = {}

    def fake_generate_tokens_for_event(**kwargs):
        notify_callback = kwargs["notify_callback"]
        callback_calls["callback_present"] = callable(notify_callback)
        generated_tokens = [SimpleNamespace(flat_id="flat-1"), SimpleNamespace(flat_id="flat-1")]
        notify_callback(event=event, generated_tokens=generated_tokens)
        return generated_tokens

    monkeypatch.setattr(
        "app.handlers.shared.committee.FoodCollectionService.generate_tokens_for_event",
        fake_generate_tokens_for_event,
    )

    def fake_notify_generated_food_tokens(**kwargs):
        callback_calls["event_name"] = kwargs["event"].name
        callback_calls["token_count"] = len(kwargs["generated_tokens"])
        callback_calls["performed_by"] = kwargs["performed_by"]

    monkeypatch.setattr(
        "app.handlers.shared.committee._notify_generated_food_tokens",
        fake_notify_generated_food_tokens,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="GENERATE_FOOD_TOKENS",
        message="generate food tokens",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert callback_calls["callback_present"] is True
    assert callback_calls["event_name"] == "Holi"
    assert callback_calls["token_count"] == 2
    assert callback_calls["performed_by"] == "member-1"


def test_committee_open_food_counter_broadcasts_event_announcement(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Holi")
    member = SimpleNamespace(id="member-1", role="chairman", society_id="soc-1")
    queue_calls = {}

    monkeypatch.setattr(
        "app.handlers.shared.committee.FoodCollectionService.open_food_counter",
        lambda **kwargs: SimpleNamespace(closes_at=None),
    )

    def fake_queue(**kwargs):
        queue_calls.update(kwargs)
        return SimpleNamespace(announcement_id="ann-1", accepted_count=10, skipped_count=2)

    monkeypatch.setattr("app.handlers.shared.committee.AnnouncementManager.queue", fake_queue)

    response = handle_committee_intent(
        db=MagicMock(),
        intent="OPEN_FOOD_COUNTER",
        message="open food counter 60",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert "Food counter is now open" in response
    assert queue_calls["scope"] == "event"
    assert queue_calls["event"] is event
    assert queue_calls["member"] is member
    assert "Holi: food counter is now open." in queue_calls["message_body"]
    assert "Please keep your token/QR ready" in queue_calls["message_body"]
    assert "Counter closes at" not in queue_calls["message_body"]


def test_committee_open_food_counter_broadcast_includes_close_time(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Holi")
    member = SimpleNamespace(id="member-1", role="chairman", society_id="soc-1")
    queue_calls = {}

    monkeypatch.setattr(
        "app.handlers.shared.committee.FoodCollectionService.open_food_counter",
        lambda **kwargs: SimpleNamespace(closes_at=datetime(2026, 3, 14, 20, 30)),
    )

    def fake_queue(**kwargs):
        queue_calls.update(kwargs)
        return SimpleNamespace(announcement_id="ann-1", accepted_count=10, skipped_count=2)

    monkeypatch.setattr("app.handlers.shared.committee.AnnouncementManager.queue", fake_queue)

    response = handle_committee_intent(
        db=MagicMock(),
        intent="OPEN_FOOD_COUNTER",
        message="open food counter 60",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert "Counter closes at" in queue_calls["message_body"]


def test_committee_verify_food_token(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Holi")
    member = SimpleNamespace(id="member-1", role="chairman")

    monkeypatch.setattr(
        "app.handlers.shared.committee.FoodCollectionService.verify_and_serve_token",
        lambda **kwargs: SimpleNamespace(token_code="AB2K9M", food_type="veg"),
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="VERIFY_FOOD_TOKEN",
        message="verify food token AB2K9M",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert "Served token AB2K9M" in response


def test_committee_food_dashboard(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1", name="Holi")
    member = SimpleNamespace(id="member-1", role="chairman")

    monkeypatch.setattr(
        "app.handlers.shared.committee.FoodCollectionService.dashboard",
        lambda **kwargs: {
            "total_plates": 10,
            "served_plates": 4,
            "remaining_plates": 6,
            "by_type": {"veg": {"total": 6, "served": 3, "remaining": 3}},
            "recent_served": [
                {
                    "token": "AB2K9M",
                    "flat_id": "flat-1",
                    "flat_number": "A-101",
                    "food_type": "veg",
                    "served_at": datetime(2026, 1, 1, 19, 0),
                }
            ],
        },
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="FOOD_DASHBOARD",
        message="food dashboard",
        event=event,
        member=member,
    )

    assert response.startswith("✅")
    assert "Total: 10" in response
    assert "AB2K9M | A-101 | veg" in response


def test_food_committee_intents_blocked_outside_allowed_state():
    warning = get_intent_state_warning(
        intent="OPEN_FOOD_COUNTER",
        event_state="LOCKED",
        is_committee=True,
    )

    assert warning == "This command is available only when event state is: EVENT_DAY."


def test_food_committee_intents_allowed_in_event_day_state():
    warning = get_intent_state_warning(
        intent="FOOD_DASHBOARD",
        event_state="EVENT_DAY",
        is_committee=True,
    )

    assert warning is None
