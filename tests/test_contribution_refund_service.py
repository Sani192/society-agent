from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.contributions.contribution_refund_service import ContributionRefundService
from tests.utils import QueryMock


def test_contribution_refund_remaining_amount_not_negative():
    contribution = SimpleNamespace(id="contrib-1", amount=100, society_id="soc-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=contribution),
        QueryMock(scalar_result=150)
    ]

    with pytest.raises(Exception, match="Remaining refundable amount: ₹0"):
        ContributionRefundService.process_refund(
            db=db,
            event_id="event-1",
            contribution_code="SP-001",
            amount=10,
            reason="Over refund",
            performed_by="member-1"
        )
