from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.payments.refund_service import RefundService
from tests.utils import QueryMock


def test_process_refund_creates_refund(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id="flat-1")
    payment = SimpleNamespace(paid_amount=500, status="paid")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(first_result=payment),
        QueryMock(all_result=[])
    ]

    monkeypatch.setattr(
        "app.modules.payments.refund_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    refund = RefundService.process_refund(
        db=db,
        event_id="event-1",
        flat_id="flat-1",
        amount=200,
        performed_by="member-1",
        reason="Food quality issue"
    )

    assert refund.amount == 200
    assert payment.status == "refunded"
    db.commit.assert_called_once()


def test_process_refund_rejects_zero_amount():
    with pytest.raises(Exception, match="Refund amount must be greater than zero"):
        RefundService.process_refund(
            db=MagicMock(),
            event_id="event-1",
            flat_id="flat-1",
            amount=0,
            performed_by="member-1",
            reason="Invalid"
        )
