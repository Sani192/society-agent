from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.modules.announcements import delivery_worker


class DummyClient:
    def __init__(self):
        self.sent_text = []
        self.sent_template = []

    def send_text_message(self, to_phone, body):
        self.sent_text.append((to_phone, body))

    def send_template_message(self, **kwargs):
        self.sent_template.append(kwargs)


def _delivery(*, metadata_json, message_text="Announcement", rendered_payload=None):
    member_identity = SimpleNamespace(metadata_json=metadata_json)
    announcement = SimpleNamespace(message_text=message_text, type="announcement")
    return SimpleNamespace(
        status="pending",
        channel="whatsapp",
        recipient_id="919999000000",
        announcement=announcement,
        member_identity=member_identity,
        rendered_payload=rendered_payload,
    )


def _general_payload():
    return {
        "template_name": "society_announcement_general",
        "body_parameters": ["Resident", "Announcement"],
    }


def test_send_delivery_uses_template_inside_policy_window(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(delivery_worker, "get_whatsapp_client", lambda: client)

    delivery = _delivery(
        metadata_json={
            "channel_state": {
                "whatsapp": {
                    "opt_in": True,
                    "last_inbound_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                }
            }
        },
        rendered_payload=_general_payload(),
    )

    outcome, reason = delivery_worker._send_delivery(delivery)

    assert outcome == "sent_template"
    assert reason is None
    assert client.sent_text == []
    assert len(client.sent_template) == 1
    assert client.sent_template[0]["template_name"] == "society_announcement_general"


def test_send_delivery_routes_to_template_outside_window(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(delivery_worker, "get_whatsapp_client", lambda: client)

    delivery = _delivery(
        metadata_json={
            "channel_state": {
                "whatsapp": {
                    "opt_in": True,
                    "last_inbound_at": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(),
                }
            }
        },
        rendered_payload=_general_payload(),
    )

    outcome, reason = delivery_worker._send_delivery(delivery)

    assert outcome == "sent_template"
    assert reason is None
    assert client.sent_text == []
    assert len(client.sent_template) == 1
    assert client.sent_template[0]["template_name"] == "society_announcement_general"


def test_send_delivery_fails_when_rendered_payload_missing(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(delivery_worker, "get_whatsapp_client", lambda: client)

    delivery = _delivery(
        metadata_json={
            "channel_state": {
                "whatsapp": {
                    "opt_in": True,
                    "last_inbound_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                }
            }
        }
    )

    outcome, reason = delivery_worker._send_delivery(delivery)

    assert outcome == "failed_template_required"
    assert reason is not None
    assert client.sent_text == []
    assert client.sent_template == []


def test_send_delivery_raises_on_empty_placeholders(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(delivery_worker, "get_whatsapp_client", lambda: client)

    delivery = _delivery(
        metadata_json={"channel_state": {"whatsapp": {"opt_in": True}}},
        rendered_payload={"template_name": "society_announcement_general", "body_parameters": ["Resident", ""]},
    )

    with pytest.raises(ValueError, match="empty template placeholders"):
        delivery_worker._send_delivery(delivery)


def test_send_delivery_skips_when_no_opt_in(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(delivery_worker, "get_whatsapp_client", lambda: client)

    delivery = _delivery(
        metadata_json={
            "channel_state": {
                "whatsapp": {
                    "last_inbound_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        }
    )

    outcome, reason = delivery_worker._send_delivery(delivery)

    assert outcome == "skipped_no_opt_in"
    assert reason is not None
    assert client.sent_text == []
    assert client.sent_template == []


def test_guard_whatsapp_announcement_requires_template():
    from app.modules.announcements.service import AnnouncementService

    with pytest.raises(ValueError, match="must use template"):
        AnnouncementService.guard_whatsapp_announcement_delivery(
            channel="whatsapp",
            announcement_type="announcement",
            uses_template_path=False,
        )


def test_guard_non_announcement_allows_non_template():
    from app.modules.announcements.service import AnnouncementService

    AnnouncementService.guard_whatsapp_announcement_delivery(
        channel="whatsapp",
        announcement_type="reminder",
        uses_template_path=False,
    )
