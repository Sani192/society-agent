from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.payments.refund_service import RefundService
from tests.utils import QueryMock

EVENT_ID = "00000000-0000-0000-0000-0000000000a2"
FLAT_ID = "00000000-0000-0000-0000-0000000000f2"
MEMBER_ID = "00000000-0000-0000-0000-0000000000b2"


def test_process_refund_creates_refund(monkeypatch):
    event = SimpleNamespace(society_id="soc-1")
    flat = SimpleNamespace(id=FLAT_ID, society_id="soc-1")
    committee_member = SimpleNamespace(id="member-1", society_id="soc-1", is_active=True, role="treasurer")
    payment = SimpleNamespace(paid_amount=500, status="paid")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=flat),
        QueryMock(first_result=committee_member),
        QueryMock(first_result=payment),
        QueryMock(all_result=[]),
        QueryMock(scalar_result=200),
    ]

    monkeypatch.setattr(
        "app.modules.payments.refund_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    refund = RefundService.process_refund(
        db=db,
        event_id=EVENT_ID,
        flat_id=FLAT_ID,
        amount=200,
        performed_by=MEMBER_ID,
        reason="Food quality issue"
    )

    assert refund.amount == 200
    assert payment.status == "refunded"
    db.commit.assert_called_once()


def test_process_refund_rejects_zero_amount():
    with pytest.raises(Exception, match="Refund amount must be greater than zero"):
        RefundService.process_refund(
            db=MagicMock(),
            event_id=EVENT_ID,
            flat_id=FLAT_ID,
            amount=0,
            performed_by=MEMBER_ID,
            reason="Invalid"
        )
