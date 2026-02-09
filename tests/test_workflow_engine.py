from types import SimpleNamespace
from unittest.mock import MagicMock

from app.workflows.engine import WorkflowEngine
from tests.utils import QueryMock


def test_check_action_denies_when_state_missing():
    db = MagicMock()
    db.query.return_value = QueryMock(first_result=None)

    result = WorkflowEngine.check_action(
        db=db,
        event_id="event-1",
        action="MARK_PAID"
    )

    assert result.allowed is False
    assert result.requires_override is False
    assert result.message == "Workflow state not initialized for event"


def test_check_action_allows_known_action():
    state_row = SimpleNamespace(current_state="ACTIVE")
    db = MagicMock()
    db.query.return_value = QueryMock(first_result=state_row)

    result = WorkflowEngine.check_action(
        db=db,
        event_id="event-1",
        action="MARK_PAID"
    )

    assert result.allowed is True
    assert result.requires_override is False
    assert result.message == "Action allowed"


def test_check_action_requires_override_for_disallowed_action():
    state_row = SimpleNamespace(current_state="ACTIVE")
    db = MagicMock()
    db.query.return_value = QueryMock(first_result=state_row)

    result = WorkflowEngine.check_action(
        db=db,
        event_id="event-1",
        action="CLOSE_EVENT"
    )

    assert result.allowed is False
    assert result.requires_override is True
    assert "requires override" in result.message


def test_check_action_closed_denies_without_performer():
    state_row = SimpleNamespace(current_state="CLOSED")
    db = MagicMock()
    db.query.return_value = QueryMock(first_result=state_row)

    result = WorkflowEngine.check_action(
        db=db,
        event_id="event-1",
        action="MARK_PAID",
        performed_by=None,
        override_reason="Reason"
    )

    assert result.allowed is False
    assert result.requires_override is False
    assert "performer required" in result.message


def test_check_action_closed_denies_without_reason():
    state_row = SimpleNamespace(current_state="CLOSED")
    member = SimpleNamespace(is_active=True, role="chairman")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=state_row),
        QueryMock(first_result=member),
    ]

    result = WorkflowEngine.check_action(
        db=db,
        event_id="event-1",
        action="MARK_PAID",
        performed_by="member-1",
        override_reason=None
    )

    assert result.allowed is False
    assert result.requires_override is False
    assert "reason required" in result.message


def test_check_action_closed_requires_override_when_valid():
    state_row = SimpleNamespace(current_state="CLOSED")
    member = SimpleNamespace(is_active=True, role="treasurer")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(first_result=state_row),
        QueryMock(first_result=member),
    ]

    result = WorkflowEngine.check_action(
        db=db,
        event_id="event-1",
        action="MARK_PAID",
        performed_by="member-1",
        override_reason="Urgent adjustment"
    )

    assert result.allowed is False
    assert result.requires_override is True


def test_apply_override_adds_audit_log():
    db = MagicMock()

    audit = WorkflowEngine.apply_override(
        db=db,
        society_id="soc-1",
        event_id="event-1",
        entity_type="payment",
        entity_id="flat-1",
        action="MARK_PAID",
        reason="Override",
        performed_by="member-1"
    )

    assert audit.action == "OVERRIDE_MARK_PAID"
    assert audit.entity_type == "payment"
    db.add.assert_called_once_with(audit)
