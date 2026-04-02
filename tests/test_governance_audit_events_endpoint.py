from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.auth import AuthenticatedPrincipal
from app.api.reports.governance import read_protected_audit_events
from app.db.models import AuditLog
from tests.utils import QueryMock

pytestmark = [pytest.mark.integration, pytest.mark.endpoint]


def test_read_protected_audit_events_creates_audit_log(db_session, monkeypatch):
    member = SimpleNamespace(id=uuid4(), society_id=uuid4(), role="chairman")

    monkeypatch.setattr(
        "app.api.reports.governance.authorize_committee_member_report",
        lambda **_: (member, None),
    )
    monkeypatch.setattr("app.api.reports.governance.settings.AUDIT_READ_ROLES", {"chairman"})

    db_session.query.return_value = QueryMock(all_result=[])

    response = read_protected_audit_events(
        channel="telegram",
        event_type="webhook_received",
        limit=10,
        db=db_session,
        principal=AuthenticatedPrincipal(committee_member_id=member.id),
    )

    assert response["count"] == 0

    audit_logs = [call.args[0] for call in db_session.add.call_args_list if isinstance(call.args[0], AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "VIEW_GOVERNANCE_AUDIT"
    assert audit_logs[0].reason == "format=json; channel=telegram; event_type=webhook_received; limit=10"
    assert audit_logs[0].performed_by == member.id
    assert audit_logs[0].society_id == member.society_id
