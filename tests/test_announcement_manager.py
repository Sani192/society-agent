from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.announcements.manager import AnnouncementManager


class _DummyThread:
    def __init__(self, target=None, kwargs=None, daemon=None):
        self.target = target
        self.kwargs = kwargs
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


def test_queue_society_announcement_returns_counts(monkeypatch):
    member = SimpleNamespace(id=uuid4(), society_id=uuid4())

    monkeypatch.setattr(
        "app.modules.announcements.manager.AnnouncementRecipientService.get_active_member_targets",
        lambda **kwargs: {
            "targets": [
                {
                    "member_identity_id": uuid4(),
                    "whatsapp_user_id": "919999000000",
                    "receiver_name": "Asha",
                    "event_name": None,
                }
            ],
            "total_candidates": 2,
            "queued_count": 1,
            "skipped_missing_whatsapp": 1,
            "duplicate_whatsapp_ids": 0,
        },
    )

    created = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        "app.modules.announcements.manager.AnnouncementService.create_announcement",
        lambda *args, **kwargs: created,
    )

    started = {"value": False}
    monkeypatch.setattr(
        "app.modules.announcements.manager.AnnouncementManager.trigger_delivery_async",
        lambda: started.__setitem__("value", True),
    )

    result = AnnouncementManager.queue(
        db=SimpleNamespace(),
        member=member,
        event=None,
        message_body="Dinner starts in 15 minutes",
        scope="society",
    )

    assert result.announcement_id == str(created.id)
    assert result.accepted_count == 1
    assert result.skipped_count == 1
    assert started["value"] is True


def test_queue_event_requires_active_event(monkeypatch):
    member = SimpleNamespace(id=uuid4(), society_id=uuid4())

    monkeypatch.setattr(
        "app.modules.announcements.manager.AnnouncementManager.resolve_current_event",
        lambda **kwargs: None,
    )

    with pytest.raises(ValueError, match="No active event found"):
        AnnouncementManager.queue(
            db=SimpleNamespace(),
            member=member,
            event=None,
            message_body="Aarti starting now",
            scope="event",
        )


def test_trigger_delivery_async_spawns_daemon_thread(monkeypatch):
    captured = {"thread": None}

    def _build_thread(*args, **kwargs):
        thread = _DummyThread(*args, **kwargs)
        captured["thread"] = thread
        return thread

    monkeypatch.setattr("app.modules.announcements.manager.threading.Thread", _build_thread)

    AnnouncementManager.trigger_delivery_async()

    thread = captured["thread"]
    assert thread is not None
    assert thread.daemon is True
    assert thread.started is True
    assert isinstance(thread.kwargs, dict)
