from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.reminders import reminder_scheduler
from tests.utils import QueryMock


def test_run_event_auto_close_job_closes_eligible_events(monkeypatch):
    now = datetime.now(timezone.utc)
    eligible = SimpleNamespace(
        id="event-1",
        society_id="soc-1",
        event_date=now - timedelta(hours=5),
        status="EVENT_DAY"
    )

    db = MagicMock()
    db.query.return_value = QueryMock(all_result=[eligible])

    close_calls = []

    monkeypatch.setattr(reminder_scheduler, "SessionLocal", lambda: db)

    def _close_event(**kwargs):
        close_calls.append(kwargs)

    monkeypatch.setattr(reminder_scheduler.EventService, "close_event", _close_event)

    reminder_scheduler.run_event_auto_close_job("soc-1", min_age_hours=2)

    assert len(close_calls) == 1
    close_call = close_calls[0]
    assert close_call["event_id"] == "event-1"
    assert close_call["performed_by"] is None
    assert close_call["source"] == reminder_scheduler.AUTO_CLOSE_SOURCE
    assert close_call["action"] == "AUTO_CLOSE_EVENT"
    assert close_call["reason"].startswith("AUTO_CLOSE: event_date passed by ")
    assert close_call["reason"].endswith(" hours")
    db.close.assert_called_once()


def test_run_event_auto_close_job_logs_failure_and_continues(monkeypatch):
    now = datetime.now(timezone.utc)
    first = SimpleNamespace(id="event-1", society_id="soc-1", event_date=now - timedelta(hours=4), status="EVENT_DAY")
    second = SimpleNamespace(id="event-2", society_id="soc-1", event_date=now - timedelta(hours=6), status="EVENT_DAY")

    db = MagicMock()
    db.query.return_value = QueryMock(all_result=[first, second])

    monkeypatch.setattr(reminder_scheduler, "SessionLocal", lambda: db)

    seen = []

    def _close_event(**kwargs):
        seen.append(kwargs["event_id"])
        if kwargs["event_id"] == "event-1":
            raise Exception("boom")

    monkeypatch.setattr(reminder_scheduler.EventService, "close_event", _close_event)

    exception_logger = MagicMock()
    monkeypatch.setattr(reminder_scheduler, "logger", SimpleNamespace(exception=exception_logger))

    reminder_scheduler.run_event_auto_close_job("soc-1", min_age_hours=2)

    assert seen == ["event-1", "event-2"]
    assert exception_logger.called
    db.close.assert_called_once()


