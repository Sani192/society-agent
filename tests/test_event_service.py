from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models import AuditLog, Event, WorkflowState
from app.modules.events.service import EventService
from tests.utils import QueryMock

EVENT_ID = "00000000-0000-0000-0000-0000000000e1"
MEMBER_ID = "00000000-0000-0000-0000-0000000000e2"


def test_create_event_creates_workflow_and_audit():
    db = MagicMock()

    event = EventService.create_event(
        db=db,
        society_id="soc-1",
        name="Ganesh Chaturthi Dinner",
        event_date=datetime(2026, 9, 14, 19, 0),
        food_types=["veg", "jain"],
        charge_per_adult=300,
        charge_per_child=150,
        payment_deadline=datetime(2026, 9, 10, 23, 59),
        created_by=MEMBER_ID
    )

    assert event.status == "DRAFT"
    db.flush.assert_called_once()
    db.commit.assert_called_once()

    added_types = [type(call.args[0]) for call in db.add.call_args_list]
    assert Event in added_types
    assert WorkflowState in added_types
    assert AuditLog in added_types


@pytest.mark.parametrize(
    "method_name, expected_status, expected_state, expected_next, override_reason",
    [
        ("activate_event", "ACTIVE", "ACTIVE", ["LOCKED"], None),
        ("lock_passes", "LOCKED", "LOCKED", ["EVENT_DAY"], None),
        ("start_event_day", "EVENT_DAY", "EVENT_DAY", ["CLOSE_EVENT"], None),
        ("close_event", "CLOSED", "CLOSED", [], "Closing after completion")
    ]
)
def test_event_lifecycle_transitions(
    monkeypatch,
    method_name,
    expected_status,
    expected_state,
    expected_next,
    override_reason
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

    kwargs = dict(
        db=db,
        event_id=EVENT_ID,
        performed_by=MEMBER_ID
    )
    if override_reason is not None:
        kwargs["override_reason"] = override_reason

    getattr(EventService, method_name)(**kwargs)

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
        lambda **kwargs: SimpleNamespace(
            allowed=False,
            requires_override=False,
            message="Blocked"
        )
    )

    with pytest.raises(Exception, match="Blocked"):
        EventService.activate_event(
            db=db,
            event_id=EVENT_ID,
            performed_by=MEMBER_ID
        )


def test_close_event_requires_reason_before_state_update():
    event = SimpleNamespace(society_id="soc-1", status="EVENT_DAY")
    workflow = SimpleNamespace(current_state="EVENT_DAY", allowed_next_states=["CLOSE_EVENT"])
    db = MagicMock()

    with pytest.raises(Exception, match="Close reason is required."):
        EventService.close_event(
            db=db,
            event_id=EVENT_ID,
            performed_by=MEMBER_ID,
            override_reason="   "
        )

    assert event.status == "EVENT_DAY"
    assert workflow.current_state == "EVENT_DAY"
    assert workflow.allowed_next_states == ["CLOSE_EVENT"]
    db.commit.assert_not_called()
    db.query.assert_not_called()


def test_close_event_success_with_reason_records_exact_audit_reason(monkeypatch):
    reason = "Closed after post-event reconciliation"
    event = SimpleNamespace(id=EVENT_ID, society_id="soc-1", status="EVENT_DAY")
    workflow = SimpleNamespace(current_state="EVENT_DAY", allowed_next_states=["CLOSE_EVENT"])
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=workflow)
    ]

    monkeypatch.setattr(
        "app.modules.events.service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    EventService.close_event(
        db=db,
        event_id=EVENT_ID,
        performed_by=MEMBER_ID,
        reason=reason,
        action="CLOSE_EVENT"
    )

    assert event.status == "CLOSED"
    assert workflow.current_state == "CLOSED"
    assert workflow.allowed_next_states == []
    db.commit.assert_called_once()

    audit_logs = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AuditLog) and call.args[0].action == "CLOSE_EVENT"
    ]
    assert len(audit_logs) == 1
    assert audit_logs[0].reason == reason
    assert str(audit_logs[0].performed_by) == MEMBER_ID


def test_close_event_from_system_source_still_creates_audit(monkeypatch):
    reason = "AUTO_CLOSE: event_date passed by 3 hours"
    event = SimpleNamespace(id=EVENT_ID, society_id="soc-1", status="EVENT_DAY")
    workflow = SimpleNamespace(current_state="EVENT_DAY", allowed_next_states=["CLOSE_EVENT"])
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=event),
        QueryMock(first_result=workflow)
    ]

    monkeypatch.setattr(
        "app.modules.events.service.WorkflowEngine.check_action",
        lambda **kwargs: SimpleNamespace(allowed=True)
    )

    EventService.close_event(
        db=db,
        event_id=EVENT_ID,
        performed_by=None,
        source="system:auto_close_job",
        reason=reason,
        action="AUTO_CLOSE_EVENT"
    )

    audit_logs = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], AuditLog)
    ]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "AUTO_CLOSE_EVENT"
    assert audit_logs[0].reason == "AUTO_CLOSE: event_date passed by 3 hours | source=system:auto_close_job"
    assert audit_logs[0].performed_by is None
