from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.reports.block_wise import BlockWiseReport
from app.modules.reports.event_summary import EventSummaryReport
from app.modules.reports.override_report import OverrideReport
from app.modules.reports.governance.audit_report import GovernanceAuditReport
from app.modules.reports.governance.audit_summary_service import AuditSummaryReport
from app.modules.reports.sponsor_wise import SponsorWiseReport
from tests.utils import QueryMock


def test_event_summary_report_balances():
    event = SimpleNamespace(id="event-1", name="Diwali")
    balance = SimpleNamespace(opening_balance=100)
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(get_result=event),
        QueryMock(scalar_result=300),
        QueryMock(scalar_result=50),
        QueryMock(scalar_result=80),
        QueryMock(scalar_result=10),
        QueryMock(first_result=balance)
    ]

    report = EventSummaryReport.generate(db=db, event_id="event-1")

    assert report["event"] == "Diwali"
    assert report["opening_balance"] == 100
    assert report["closing_balance"] == 360


def test_event_summary_report_requires_event():
    db = MagicMock()
    db.query.side_effect = [QueryMock(get_result=None)]

    with pytest.raises(Exception, match="Event not found"):
        EventSummaryReport.generate(db=db, event_id="missing")


def test_block_wise_report_grouping():
    event = SimpleNamespace(id="event-1")
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(get_result=event),
        QueryMock(all_result=[("A", 100), ("B", None)])
    ]

    report = BlockWiseReport.generate(db=db, event_id="event-1")

    assert report == {"A": 100, "B": 0}


def test_sponsor_wise_report_listing():
    event = SimpleNamespace(id="event-1")
    contribution = SimpleNamespace(
        source_name="Sponsor",
        contribution_type="cash",
        amount=500,
        notes="Gold sponsor"
    )
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(get_result=event),
        QueryMock(all_result=[contribution])
    ]

    report = SponsorWiseReport.generate(db=db, event_id="event-1")

    assert report == [
        {
            "source": "Sponsor",
            "type": "cash",
            "amount": 500,
            "notes": "Gold sponsor"
        }
    ]


def test_override_report_listing():
    event = SimpleNamespace(id="event-1")
    log = SimpleNamespace(
        action="OVERRIDE",
        reason="OVERRIDE: manual",
        performed_at="2026-01-10"
    )
    db = MagicMock()
    db.query.side_effect = [
        QueryMock(get_result=event),
        QueryMock(all_result=[log])
    ]

    report = OverrideReport.generate(db=db, event_id="event-1")

    assert report == [
        {
            "action": "OVERRIDE",
            "reason": "OVERRIDE: manual",
            "performed_at": "2026-01-10"
        }
    ]


def test_governance_audit_report_includes_system_and_committee_rows():
    db = MagicMock()
    query = QueryMock(
        all_result=[
            (
                datetime(2026, 1, 10, 9, 30),
                "ROLE_CHANGE",
                "Assigned moderator",
                "member-1",
                "Alex",
                "secretary",
            ),
            (
                datetime(2026, 1, 10, 8, 0),
                "POLICY_SYNC",
                None,
                None,
                None,
                None,
            ),
        ]
    )
    query.outerjoin = lambda *args, **kwargs: query
    db.query.side_effect = [query]

    report = GovernanceAuditReport.generate(db=db, society_id="soc-1")

    assert report["rows"] == [
        ["10 Jan 2026 09:30", "ROLE_CHANGE", "Assigned moderator", "Alex", "secretary"],
        ["10 Jan 2026 08:00", "POLICY_SYNC", "-", "System", "-"],
    ]


def test_audit_summary_report_scopes_refunds_by_society():
    overrides_query = QueryMock(scalar_result=3)

    class RefundQuery(QueryMock):
        def __init__(self):
            super().__init__(scalar_result=2)
            self.join_args = None
            self.filter_args = None

        def join(self, *args, **kwargs):
            self.join_args = args
            return self

        def filter(self, *args, **kwargs):
            self.filter_args = args
            return self

    refunds_query = RefundQuery()

    db = MagicMock()
    db.query.side_effect = [overrides_query, refunds_query]

    report = AuditSummaryReport.generate(db=db, society_id="soc-target")

    assert report["total_overrides"] == 3
    assert report["total_refunds"] == 2
    assert refunds_query.join_args is not None
    assert "refunds.event_id = events.id" in str(refunds_query.join_args[1])
    assert any(getattr(expr, "left", None) is not None and str(expr.left) == "events.society_id" and getattr(expr.right, "value", None) == "soc-target" for expr in refunds_query.filter_args)
    assert any(getattr(expr, "left", None) is not None and str(expr.left) == "refunds.status" and getattr(expr.right, "value", None) == "refunded" for expr in refunds_query.filter_args)


def test_audit_summary_report_refund_total_excludes_other_societies():
    class RefundQuery(QueryMock):
        def __init__(self, rows):
            super().__init__()
            self.rows = rows
            self.filter_args = ()

        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            self.filter_args = args
            return self

        def scalar(self):
            criteria = {}
            for expr in self.filter_args:
                if not hasattr(expr, "left") or not hasattr(expr, "right"):
                    continue
                left = str(expr.left)
                value = getattr(expr.right, "value", None)
                if left == "events.society_id":
                    criteria["society_id"] = value
                elif left == "refunds.status":
                    criteria["status"] = value

            return sum(
                1
                for row in self.rows
                if row["society_id"] == criteria.get("society_id")
                and row["status"] == criteria.get("status")
            )

    rows = [
        {"society_id": "soc-a", "status": "refunded"},
        {"society_id": "soc-b", "status": "refunded"},
        {"society_id": "soc-a", "status": "requested"},
    ]

    db = MagicMock()
    db.query.side_effect = [
        QueryMock(scalar_result=1),
        RefundQuery(rows),
    ]

    report = AuditSummaryReport.generate(db=db, society_id="soc-a")

    assert report["total_refunds"] == 1
    assert report["late_changes"] == 1
