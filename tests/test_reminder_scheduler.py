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


def test_start_scheduler_registers_auto_close_with_config_timing(monkeypatch):
    config = SimpleNamespace(society_id="soc-1", run_hour=8, run_minute=30)
    db = MagicMock()
    db.query.return_value = QueryMock(all_result=[config])

    scheduler_mock = MagicMock()

    monkeypatch.setattr(reminder_scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(reminder_scheduler, "scheduler", scheduler_mock)

    reminder_scheduler.start_scheduler()

    add_job_calls = scheduler_mock.add_job.call_args_list
    assert len(add_job_calls) == 2

    payment_call = add_job_calls[0]
    auto_close_call = add_job_calls[1]

    assert payment_call.kwargs["hour"] == 8
    assert payment_call.kwargs["minute"] == 30
    assert payment_call.kwargs["args"] == ["soc-1"]

    assert auto_close_call.kwargs["hour"] == 8
    assert auto_close_call.kwargs["minute"] == 30
    assert auto_close_call.kwargs["args"] == ["soc-1"]
    assert auto_close_call.kwargs["id"] == "auto_close_soc-1"

    scheduler_mock.start.assert_called_once()
    db.close.assert_called_once()
