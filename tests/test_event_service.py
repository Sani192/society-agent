from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models import AuditLog, Event, WorkflowState
from app.modules.events.service import EventService
from tests.utils import QueryMock


def test_create_event_creates_workflow_and_audit():
    db = MagicMock()

    event = EventService.create_event(
        db=db,
        society_id="soc-1",
        name="Ganesh Chaturthi Dinner",
        event_date=datetime(2026, 9, 14, 19, 0),
        food_types=["veg", "jain"],
        charge_per_person=300,
        payment_deadline=datetime(2026, 9, 10, 23, 59),
        created_by="member-1"
    )

    assert event.status == "DRAFT"
    db.flush.assert_called_once()
    db.commit.assert_called_once()

    added_types = [type(call.args[0]) for call in db.add.call_args_list]
    assert Event in added_types
    assert WorkflowState in added_types
    assert AuditLog in added_types


@pytest.mark.parametrize(
    "method_name, expected_status, expected_state, expected_next",
    [
        ("activate_event", "ACTIVE", "ACTIVE", ["PAYMENT_LOCKED"]),
        ("lock_passes", "PAYMENT_LOCKED", "PAYMENT_LOCKED", ["EVENT_DAY"]),
        ("start_event_day", "EVENT_DAY", "EVENT_DAY", ["CLOSE_EVENT"]),
        ("close_event", "CLOSED", "CLOSED", [])
    ]
)
def test_event_lifecycle_transitions(
    monkeypatch,
    method_name,
    expected_status,
    expected_state,
    expected_next
):
    event = SimpleNamespace(society_id="soc-1", status=None)
    workflow = SimpleNamespace(current_state=None, allowed_next_states=None)
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=workflow)
    ]

    monkeypatch.setattr(
        "app.modules.events.service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    getattr(EventService, method_name)(
        db=db,
        event_id="event-1",
        performed_by="member-1"
    )

    assert event.status == expected_status
    assert workflow.current_state == expected_state
    assert workflow.allowed_next_states == expected_next
    db.commit.assert_called_once()


def test_event_lifecycle_requires_override(monkeypatch):
    event = SimpleNamespace(society_id="soc-1", status=None)
    workflow = SimpleNamespace(current_state=None, allowed_next_states=None)
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=workflow)
    ]

    monkeypatch.setattr(
        "app.modules.events.service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=False, message="Blocked")
    )

    with pytest.raises(Exception, match="Blocked"):
        EventService.activate_event(
            db=db,
            event_id="event-1",
            performed_by="member-1"
        )
