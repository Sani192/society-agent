from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.contributions.contribution_refund_service import ContributionRefundService
from tests.utils import QueryMock


def _build_db(*, contribution=None, refunded_total=0):
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=contribution),
        QueryMock(scalar_result=refunded_total),
    ]
    return db


def test_contribution_refund_remaining_amount_not_negative():
    contribution = SimpleNamespace(id="contrib-1", amount=100, society_id="soc-1")
    db = _build_db(contribution=contribution, refunded_total=150)

    with pytest.raises(Exception, match="Remaining refundable amount: ₹0"):
        ContributionRefundService.process_refund(
            db=db,
            event_id="event-1",
            contribution_code="SP-001",
            amount=10,
            reason="Over refund",
            performed_by="member-1",
        )


def test_contribution_refund_denies_when_workflow_blocks(monkeypatch):
    contribution = SimpleNamespace(id="contrib-1", amount=500, society_id="soc-1")
    db = _build_db(contribution=contribution, refunded_total=100)

    monkeypatch.setattr(
        "app.modules.contributions.contribution_refund_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(
            allowed=False,
            requires_override=False,
            message="Action not allowed in current state",
        ),
    )

    with pytest.raises(Exception, match="Action not allowed in current state"):
        ContributionRefundService.process_refund(
            db=db,
            event_id="event-1",
            contribution_code="SP-001",
            amount=50,
            reason="Duplicate",
            performed_by="member-1",
        )


def test_contribution_refund_requires_override_reason(monkeypatch):
    contribution = SimpleNamespace(id="contrib-1", amount=500, society_id="soc-1")
    db = _build_db(contribution=contribution, refunded_total=100)

    monkeypatch.setattr(
        "app.modules.contributions.contribution_refund_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(
            allowed=False,
            requires_override=True,
            message="Action 'REFUND_CONTRIBUTION' requires override in state 'CLOSED'",
        ),
    )

    with pytest.raises(Exception, match="requires override"):
        ContributionRefundService.process_refund(
            db=db,
            event_id="event-1",
            contribution_code="SP-001",
            amount=50,
            reason="Duplicate",
            performed_by="member-1",
        )


def test_contribution_refund_applies_override_and_audit(monkeypatch):
    contribution = SimpleNamespace(id="contrib-1", amount=500, society_id="soc-1")
    db = _build_db(contribution=contribution, refunded_total=100)

    monkeypatch.setattr(
        "app.modules.contributions.contribution_refund_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(
            allowed=False,
            requires_override=True,
            message="Action 'REFUND_CONTRIBUTION' requires override in state 'CLOSED'",
        ),
    )

    override_calls = {}

    def fake_apply_override(**kwargs):
        override_calls.update(kwargs)

    monkeypatch.setattr(
        "app.modules.contributions.contribution_refund_service.WorkflowEngine.apply_override",
        fake_apply_override,
    )

    ContributionRefundService.process_refund(
        db=db,
        event_id="event-1",
        contribution_code="SP-001",
        amount=50,
        reason="Duplicate",
        performed_by="member-1",
        override_reason="Chairman approval",
    )

    assert override_calls["action"] == "REFUND_CONTRIBUTION"
    assert override_calls["reason"] == "Chairman approval"
    db.commit.assert_called_once()
