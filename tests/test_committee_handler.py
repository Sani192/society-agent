from types import SimpleNamespace
from unittest.mock import MagicMock

from app.whatsapp.handlers.committee_handler import handle_committee_intent
from app.whatsapp.committee_action_session import clear_committee_action_session
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
        "app.whatsapp.handlers.committee_handler.ExpenseService.add_expense",
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
        "app.whatsapp.handlers.committee_handler.PendingPaymentReport.get_pending_flats",
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
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.list_requests",
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
        "app.whatsapp.handlers.committee_handler.RefundRequestService.list_requests",
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
        "app.whatsapp.handlers.committee_handler.EventParticipationReport.generate",
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
        "app.whatsapp.handlers.committee_handler.ExpenseService.add_expense",
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
        "app.whatsapp.handlers.committee_handler.ContributionService.add_contribution",
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
        "app.whatsapp.handlers.committee_handler.ContributionRefundService.process_refund",
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
        "app.whatsapp.handlers.committee_handler.AdminApprovalService.approve_user",
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
        SimpleNamespace(
            request_code="REQ-001",
            flat_number="A-101",
            created_at=SimpleNamespace(strftime=lambda fmt: "01 Jan 2026 10:00"),
        )
    ]

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.AdminOnboardingQueryService.list_pending_users",
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
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.get_request_by_code",
        lambda **kwargs: request,
    )

    called = {}

    def fake_approve_request(**kwargs):
        called["approved"] = kwargs["request"].request_code

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.approve_request",
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
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.get_request_by_code",
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
        "app.whatsapp.handlers.committee_handler.PaymentRequestService.get_request_by_code",
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
        "app.whatsapp.handlers.committee_handler.RefundRequestService.get_request_by_code",
        lambda **kwargs: request,
    )

    called = {}

    def fake_approve_refund(**kwargs):
        called["approved"] = kwargs["request"].request_code

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.RefundRequestService.approve_request",
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
        "app.whatsapp.handlers.committee_handler.ContributionRefundService.process_refund",
        fake_process_refund,
    )

    response = handle_committee_intent(
        db=MagicMock(),
        intent="REFUND_SPONSOR",
        message="refund sponsor SP-001 500 reason extra",
        event=event,
        member=member,
    )

    assert (
        response
        == "❌ Refund exceeds contribution amount. Remaining refundable amount: ₹0"
    )




def test_committee_refund_sponsor_prompts_override_when_required(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1", role="chairman")

    def fake_process_refund(**kwargs):
        raise Exception("Action 'REFUND_CONTRIBUTION' requires override in state 'CLOSED'")

    monkeypatch.setattr(
        "app.whatsapp.handlers.committee_handler.ContributionRefundService.process_refund",
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
        "app.whatsapp.handlers.committee_handler.ContributionRefundService.process_refund",
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
        "app.whatsapp.handlers.committee_handler.RefundRequestService.get_request_by_code",
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
    assert "Choose a report to export" in response
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
        "app.whatsapp.handlers.committee_handler.EventService.create_event",
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
