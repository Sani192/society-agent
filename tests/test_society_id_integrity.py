from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models import EventContribution
from app.modules.contributions.contribution_service import ContributionService
from app.modules.payments.payment_request_service import PaymentRequestService
from app.modules.payments.refund_request_service import RefundRequestService
from app.modules.reminders.reminder_service import ReminderService
from tests.utils import QueryMock

EVENT_ID = "00000000-0000-0000-0000-0000000000c1"
FLAT_ID = "00000000-0000-0000-0000-0000000000c2"


def test_payment_request_rejects_flat_from_other_society():
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=SimpleNamespace(id=EVENT_ID, society_id="soc-1")),
        QueryMock(first_result=SimpleNamespace(id=FLAT_ID, society_id="soc-2")),
    ]

    with pytest.raises(Exception, match="Flat does not belong to the event society"):
        PaymentRequestService.request_payment(
            db=db,
            event_id=EVENT_ID,
            flat_id=FLAT_ID,
            amount=100,
            payment_mode="upi",
            requested_by_mapping_id="mapping-1",
        )


def test_refund_request_rejects_flat_from_other_society():
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=SimpleNamespace(id=EVENT_ID, society_id="soc-1")),
        QueryMock(first_result=SimpleNamespace(id=FLAT_ID, society_id="soc-2")),
    ]

    with pytest.raises(Exception, match="Flat does not belong to the event society"):
        RefundRequestService.request_refund(
            db=db,
            event_id=EVENT_ID,
            flat_id=FLAT_ID,
            amount=100,
            reason="duplicate",
            requested_by_mapping_id="mapping-1",
        )


def test_contribution_persists_without_denormalized_society_id(monkeypatch):
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=SimpleNamespace(id="event-1", society_id="soc-1")),
        QueryMock(count_result=0),
    ]

    monkeypatch.setattr(
        "app.modules.contributions.contribution_service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True),
    )

    ContributionService.add_contribution(
        db=db,
        event_id="event-1",
        contribution_type="sponsor",
        source_name="ACME",
        amount=500,
        performed_by="member-1",
    )

    contribution = next(
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], EventContribution)
    )
    assert contribution.event_id == "event-1"
    assert not hasattr(contribution, "society_id")


def test_reminder_persists_without_denormalized_society_id():
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    db.execute.return_value = SimpleNamespace(rowcount=1)
    db.query.side_effect = [
        QueryMock(first_result=SimpleNamespace(id="event-1", society_id="soc-1")),
        QueryMock(all_result=[SimpleNamespace(flat_id="flat-1", expected_amount=400, paid_amount=100)]),
        QueryMock(first_result=None),
    ]

    generated = ReminderService.generate_pending_payment_reminders(
        db=db,
        event_id="event-1",
    )

    assert generated[0].event_id == "event-1"
    assert not hasattr(generated[0], "society_id")
