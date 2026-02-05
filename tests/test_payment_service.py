from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.payments.payment_service import PaymentService
from tests.utils import QueryMock


def test_record_payment_creates_payment(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    food_pass = SimpleNamespace(total_amount=300)
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(first_result=food_pass),
        QueryMock(first_result=None)
    ]

    monkeypatch.setattr(
        "app.modules.payments.payment_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    payment = PaymentService.record_payment(
        db=db,
        event_id="event-1",
        flat_id="flat-1",
        amount=300,
        payment_mode="upi",
        performed_by="member-1"
    )

    assert payment.paid_amount == 300
    assert payment.status == "paid"
    db.commit.assert_called_once()


def test_record_payment_rejects_zero_amount():
    with pytest.raises(Exception, match="Payment amount must be greater than zero"):
        PaymentService.record_payment(
            db=MagicMock(),
            event_id="event-1",
            flat_id="flat-1",
            amount=0,
            payment_mode="cash",
            performed_by="member-1"
        )
