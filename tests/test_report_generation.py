from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.reports.block_wise import BlockWiseReport
from app.modules.reports.event_summary import EventSummaryReport
from app.modules.reports.override_report import OverrideReport
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
