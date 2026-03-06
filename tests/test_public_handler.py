from types import SimpleNamespace
from unittest.mock import MagicMock

from app.whatsapp.handlers.public_handler import handle_public_intent
from tests.constants import COMMITTEE_PHONE, MEMBER_PHONE
from tests.utils import QueryMock


def test_public_add_pass_success(monkeypatch):
    event = SimpleNamespace(
        id="event-1",
        society_id="soc-1",
        charge_per_adult=200,
        charge_per_child=100
    )
    flat = SimpleNamespace(id="flat-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )

    called = {}

    def fake_add_or_update_pass(**kwargs):
        called["payload"] = kwargs

    monkeypatch.setattr(
        "app.handlers.shared.public.FoodPassService.add_or_update_pass",
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
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="PAY-001")
    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentRequestService.request_payment",
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
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="PAY-002")
    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentRequestService.find_matching_request",
        lambda **kwargs: request
    )

    called = {}

    def fake_approve_request(**kwargs):
        called["approved"] = True

    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentRequestService.approve_request",
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
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )
    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentRequestService.find_matching_request",
        lambda **kwargs: None
    )

    called = {}

    def fake_record_payment(**kwargs):
        called["recorded"] = True

    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentService.record_payment",
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
    assert response == "✅ Payment received: ₹500"


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
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="REF-001")
    monkeypatch.setattr(
        "app.handlers.shared.public.RefundRequestService.request_refund",
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


def test_public_refund_request_surfaces_error(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )

    def fake_request_refund(**kwargs):
        raise Exception("Invalid flat number.")

    monkeypatch.setattr(
        "app.handlers.shared.public.RefundRequestService.request_refund",
        fake_request_refund
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="REFUND",
        phone_number=MEMBER_PHONE,
        message="refund 200 reason guest absent",
        event=event,
        member=None
    )

    assert response == "❌ Invalid flat number."


def test_public_refund_committee_approves_request(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )

    request = SimpleNamespace(request_code="REF-002")
    monkeypatch.setattr(
        "app.handlers.shared.public.RefundRequestService.find_matching_request",
        lambda **kwargs: request
    )

    called = {}

    def fake_approve_request(**kwargs):
        called["approved"] = True

    monkeypatch.setattr(
        "app.handlers.shared.public.RefundRequestService.approve_request",
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


def test_public_refund_committee_surfaces_error(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )
    monkeypatch.setattr(
        "app.handlers.shared.public.RefundRequestService.find_matching_request",
        lambda **kwargs: None
    )

    def fake_process_refund(**kwargs):
        raise Exception("Refund amount exceeds paid amount")

    monkeypatch.setattr(
        "app.handlers.shared.public.RefundService.process_refund",
        fake_process_refund
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="REFUND",
        phone_number=COMMITTEE_PHONE,
        message="refund 200 reason guest absent",
        event=event,
        member=member
    )

    assert response == "❌ Refund amount exceeds paid amount"


def test_public_my_pass_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    food_pass = SimpleNamespace(veg_count=1, jain_count=0, kids_count=1)

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.UserQueryService.get_my_pass",
        lambda **kwargs: food_pass
    )
    monkeypatch.setattr(
        "app.handlers.shared.public.FoodCollectionService.member_pass_status",
        lambda **kwargs: {
            "total_passes": 2,
            "served": 1,
            "remaining": 1,
            "by_type": {"veg": {"total": 2, "served": 1, "remaining": 1}},
            "tokens": [],
        },
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
    assert "Served: 1" in response
    assert "Veg: served 1 / total 2 (remaining 1)" in response


def test_public_my_tokens_success(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: flat
    )
    monkeypatch.setattr(
        "app.handlers.shared.public.FoodCollectionService.member_pass_status",
        lambda **kwargs: {
            "total_passes": 2,
            "served": 1,
            "remaining": 1,
            "by_type": {"veg": {"total": 2, "served": 1, "remaining": 1}},
            "tokens": [
                {"token": "AB2K9M", "food_type": "veg", "served": False},
                {"token": "CD3N7P", "food_type": "jain", "served": True},
            ],
        },
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="MY_TOKENS",
        phone_number=MEMBER_PHONE,
        message="my tokens",
        event=event,
        member=None,
    )

    assert "AB2K9M" in response
    assert "Remaining: 1" in response
    assert "Veg: served 1 / total 2 (remaining 1)" in response


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


def test_public_my_payment_requests(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    request = SimpleNamespace(request_code="PAY-003", amount=250, status="requested")
    member_flat = SimpleNamespace(id="flat-1")
    request_flat = SimpleNamespace(flat_number="A-101")

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: member_flat
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentRequestService.list_requests",
        lambda **kwargs: [(request, request_flat)]
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="MY_PAYMENT_REQUESTS",
        phone_number=MEMBER_PHONE,
        message="my payment requests",
        event=event,
        member=None
    )

    assert "PAY-003" in response
    assert "A-101" in response


def test_public_my_refund_requests(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    request = SimpleNamespace(request_code="REF-003", amount=150, status="requested")
    member_flat = SimpleNamespace(id="flat-1")
    request_flat = SimpleNamespace(flat_number="B-101")

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: member_flat
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.RefundRequestService.list_requests",
        lambda **kwargs: [(request, request_flat)]
    )

    response = handle_public_intent(
        db=MagicMock(),
        intent="MY_REFUND_REQUESTS",
        phone_number=MEMBER_PHONE,
        message="my refund requests",
        event=event,
        member=None
    )

    assert "REF-003" in response
    assert "B-101" in response


def test_public_my_payments(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    request = SimpleNamespace(request_code="PAY-010", amount=400, status="approved")
    pending_request = SimpleNamespace(request_code="PAY-011", amount=300, status="requested")
    member_flat = SimpleNamespace(id="flat-1")
    request_flat = SimpleNamespace(flat_number="C-301")
    pending_flat = SimpleNamespace(flat_number="C-302")
    payment = SimpleNamespace(status="partial", paid_amount=200, expected_amount=500)

    db = MagicMock()
    db.query.return_value = QueryMock(first_result=payment)

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: member_flat
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.UserQueryService.get_my_payment_summary",
        lambda **kwargs: {"paid": 400, "refunded": 0, "net_paid": 400}
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.UserQueryService.get_my_balance",
        lambda **kwargs: {"expected": 500, "paid": 400, "balance": 100}
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentRequestService.list_requests",
        lambda **kwargs: [(request, request_flat), (pending_request, pending_flat)]
    )

    response = handle_public_intent(
        db=db,
        intent="MY_PAYMENTS",
        phone_number=MEMBER_PHONE,
        message="my payments",
        event=event,
        member=None
    )

    assert "PAY-010" in response
    assert "PAY-011" in response
    assert "C-301" in response
    assert "C-302" in response
    assert "Payment Summary" in response
    assert "Status: partial (₹200 of ₹500)" in response


def test_public_my_payments_no_requests(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member_flat = SimpleNamespace(id="flat-1")
    payment = SimpleNamespace(status="pending", paid_amount=0, expected_amount=800)

    db = MagicMock()
    db.query.return_value = QueryMock(first_result=payment)

    monkeypatch.setattr(
        "app.handlers.shared.public.resolve_flat",
        lambda *args, **kwargs: member_flat
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.UserQueryService.get_my_payment_summary",
        lambda **kwargs: {"paid": 0, "refunded": 0, "net_paid": 0}
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.UserQueryService.get_my_balance",
        lambda **kwargs: {"expected": 800, "paid": 0, "balance": 800}
    )

    monkeypatch.setattr(
        "app.handlers.shared.public.PaymentRequestService.list_requests",
        lambda **kwargs: []
    )

    response = handle_public_intent(
        db=db,
        intent="MY_PAYMENTS",
        phone_number=MEMBER_PHONE,
        message="my payments",
        event=event,
        member=None
    )

    assert "No payment requests found" in response
    assert "Status: pending (₹0 of ₹800)" in response


def test_public_help_and_commands():
    from app.commands.handlers.public_handler import handle_public_intent

    event = SimpleNamespace(id="event-1", society_id="soc-1")

    help_response = handle_public_intent(
        db=MagicMock(),
        intent="HELP",
        phone_number="919999000000",
        message="help",
        event=event,
        member=None,
    )

    assert "Society Control Panel" in help_response
    assert "Type *menu*." in help_response


def test_public_summary_formats_currency(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.handlers.shared.public.PublicEventSummaryReport.generate",
        lambda **kwargs: {
            "participants": 12,
            "income": 1200,
            "expenses": 300,
            "closing_balance": 900,
            "sponsors": ["Alpha"]
        }
    )

    db = MagicMock()

    response = handle_public_intent(
        db=db,
        intent="SUMMARY",
        phone_number=MEMBER_PHONE,
        message="summary",
        event=event,
        member=member
    )

    assert "📊 *Event Summary*" in response
    assert "Total Income: ₹1,200" in response
    assert "Sponsors: Alpha" in response


def test_public_block_report_formats_currency(monkeypatch):
    event = SimpleNamespace(id="event-1", society_id="soc-1")
    member = SimpleNamespace(id="member-1")

    monkeypatch.setattr(
        "app.handlers.shared.public.BlockContributionReport.generate",
        lambda **kwargs: {"Block A": 2500}
    )

    db = MagicMock()

    response = handle_public_intent(
        db=db,
        intent="BLOCK_REPORT",
        phone_number=MEMBER_PHONE,
        message="block report",
        event=event,
        member=member
    )

    assert "🏢 *Block Contribution Report*" in response
    assert "Block A: ₹2,500" in response



def test_public_actions_blocked_for_non_committee_when_event_not_active(db_session, seed_event):
    from app.commands.handlers.public_handler import handle_public_intent

    event = seed_event(status="DRAFT")

    response = handle_public_intent(
        db=db_session,
        intent="PAY",
        phone_number="+910000000000",
        message="pay 500",
        event=event,
        member=None,
    )

    assert response.startswith("❌")
    assert "available only when event is active" in response
