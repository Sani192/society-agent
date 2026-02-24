from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.users.channel_identity_service import resolve_committee_member_by_identity
from app.utils.guards import ensure_committee_member


@pytest.mark.parametrize(
    ("channel_type", "external_user_id", "username"),
    [
        ("whatsapp", "919999000000", None),
        ("telegram", "123456", "janed"),
    ],
)
def test_resolve_member_by_identity_for_whatsapp_and_telegram(channel_type, external_user_id, username):
    member = SimpleNamespace(id="member-1", is_active=True)
    identity_row = SimpleNamespace(committee_member=member)

    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.first.return_value = identity_row

    db = MagicMock()
    db.query.return_value = query

    resolved = resolve_committee_member_by_identity(
        db=db,
        channel_type=channel_type,
        sender_id=external_user_id,
        username=username,
    )

    assert resolved is member
    assert db.query.call_count == 1


def test_resolve_member_by_identity_does_not_fallback_to_committee_phone_lookup():
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.first.return_value = None

    db = MagicMock()
    db.query.return_value = query

    resolved = resolve_committee_member_by_identity(
        db=db,
        channel_type="whatsapp",
        sender_id="919999000001",
        username=None,
    )

    assert resolved is None
    assert db.query.call_count == 1


def test_resolve_member_by_identity_skips_username_lookup_when_missing():
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.first.return_value = None

    db = MagicMock()
    db.query.return_value = query

    resolved = resolve_committee_member_by_identity(
        db=db,
        channel_type="telegram",
        sender_id="12345",
        username=None,
    )

    assert resolved is None
    assert db.query.call_count == 1


def test_ensure_committee_member_uses_identity_resolution_without_phone_fallback(monkeypatch):
    member = SimpleNamespace(id="member-1", is_active=True)
    captured = {}

    def _resolve(**kwargs):
        captured.update(kwargs)
        return member

    monkeypatch.setattr("app.utils.guards.resolve_committee_member_by_identity", _resolve)

    resolved = ensure_committee_member(
        "919999000000",
        MagicMock(),
        channel_type="telegram",
        external_user_id="123456",
        username="janed",
    )

    assert resolved is member
    assert "phone_number" not in captured
    assert captured["sender_id"] == "123456"
