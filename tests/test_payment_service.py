from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.payments.payment_service import PaymentService
from tests.utils import QueryMock

EVENT_ID = "00000000-0000-0000-0000-0000000000a1"
FLAT_ID = "00000000-0000-0000-0000-0000000000f1"
MEMBER_ID = "00000000-0000-0000-0000-0000000000b1"


def test_record_payment_creates_payment(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id=FLAT_ID, society_id="soc-1")
    committee_member = SimpleNamespace(id="member-1", society_id="soc-1", is_active=True, role="treasurer")
    food_pass = SimpleNamespace(total_amount=300)
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(first_result=committee_member),
        QueryMock(first_result=food_pass),
        QueryMock(first_result=None)
    ]

    monkeypatch.setattr(
        "app.modules.payments.payment_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    payment = PaymentService.record_payment(
        db=db,
        event_id=EVENT_ID,
        flat_id=FLAT_ID,
        amount=300,
        payment_mode="upi",
        performed_by=MEMBER_ID
    )

    assert payment.paid_amount == 300
    assert payment.status == "paid"
    db.commit.assert_called_once()


def test_record_payment_rejects_zero_amount():
    with pytest.raises(Exception, match="Payment amount must be greater than zero"):
        PaymentService.record_payment(
            db=MagicMock(),
            event_id=EVENT_ID,
            flat_id=FLAT_ID,
            amount=0,
            payment_mode="cash",
            performed_by=MEMBER_ID
        )


def test_record_payment_rejects_flat_from_different_society(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id=FLAT_ID, society_id="soc-2")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
    ]

    monkeypatch.setattr(
        "app.modules.payments.payment_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    with pytest.raises(Exception, match="Flat does not belong to the event society"):
        PaymentService.record_payment(
            db=db,
            event_id=EVENT_ID,
            flat_id=FLAT_ID,
            amount=300,
            payment_mode="upi",
            performed_by=MEMBER_ID
        )
