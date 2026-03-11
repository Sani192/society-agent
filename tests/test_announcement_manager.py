from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.announcements.manager import AnnouncementManager


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

    captured = {"announcement_id": None}
    monkeypatch.setattr(
        "app.modules.announcements.manager.AnnouncementManager.trigger_delivery_async",
        lambda *, announcement_id: captured.__setitem__("announcement_id", announcement_id),
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
    assert captured["announcement_id"] == str(created.id)


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


def test_trigger_delivery_async_enqueues_jobs(monkeypatch):
    captured = {"announcement_id": None}
    monkeypatch.setattr(
        "app.modules.announcements.manager.enqueue_announcement_delivery_tasks",
        lambda *, announcement_id: captured.__setitem__("announcement_id", announcement_id),
    )

    AnnouncementManager.trigger_delivery_async(announcement_id="ann-1")

    assert captured["announcement_id"] == "ann-1"
