from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.committee.committee_member_service import CommitteeMemberService

ACTOR_ID = "00000000-0000-0000-0000-0000000000aa"
MEMBER_ID = "00000000-0000-0000-0000-0000000000ab"


class _Query:
    def __init__(self, *, first_result=None, count_result=None, all_result=None):
        self._first_result = first_result
        self._count_result = count_result
        self._all_result = all_result

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._first_result

    def count(self):
        return self._count_result

    def all(self):
        return self._all_result


def test_list_members_only_active():
    db = MagicMock()
    members = [SimpleNamespace(id="m1")]
    db.query.return_value = _Query(all_result=members)

    result = CommitteeMemberService.list_members(db=db, society_id="soc")

    assert result == members


def test_add_member_forbidden_non_chairman():
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="secretary", is_active=True)),
    ]

    with pytest.raises(PermissionError):
        CommitteeMemberService.add_member(
            db=db,
            society_id="soc",
            name="N",
            phone_number="+91 99999 00000",
            role="treasurer",
            performed_by=ACTOR_ID,
        )


def test_add_member_duplicate_active_same_society():
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
        _Query(first_result=SimpleNamespace(is_active=True)),
    ]

    with pytest.raises(ValueError):
        CommitteeMemberService.add_member(
            db=db,
            society_id="soc",
            name="N",
            phone_number="+91 99999 00000",
            role="treasurer",
            performed_by=ACTOR_ID,
        )


def test_add_member_success_creates_active_member():
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
        _Query(first_result=None),
        _Query(first_result=None),
    ]

    result = CommitteeMemberService.add_member(
        db=db,
        society_id="soc",
        name="New Member",
        phone_number="+91 99999 00002",
        role="committee_member",
        performed_by=ACTOR_ID,
    )

    assert result.is_active is True
    assert result.role == "committee_member"
    assert result.name == "New Member"



def test_add_member_invalid_role_rejected():
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
    ]

    with pytest.raises(ValueError, match="Invalid role"):
        CommitteeMemberService.add_member(
            db=db,
            society_id="soc",
            name="N",
            phone_number="+91 99999 00000",
            role="invalid-role",
            performed_by=ACTOR_ID,
        )


def test_add_member_reactivate_inactive():
    inactive = SimpleNamespace(id="m2", is_active=False, society_id="soc")
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
        _Query(first_result=inactive),
        _Query(first_result=inactive),
    ]

    result = CommitteeMemberService.add_member(
        db=db,
        society_id="soc",
        name="Reactivated",
        phone_number="+91 99999 00000",
        role="secretary",
        performed_by=ACTOR_ID,
    )

    assert result is inactive
    assert inactive.is_active is True
    assert inactive.role == "secretary"


def test_remove_member_last_chairman_guard():
    target = SimpleNamespace(id="m3", role="chairman", is_active=True, name="C")
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
        _Query(first_result=target),
        _Query(count_result=1),
    ]

    with pytest.raises(ValueError):
        CommitteeMemberService.remove_member(
            db=db,
            society_id="soc",
            member_id=MEMBER_ID,
            performed_by=ACTOR_ID,
        )


def test_remove_member_soft_deactivation_success():
    target = SimpleNamespace(id="m5", role="secretary", is_active=True, name="Sec")
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
        _Query(first_result=target),
    ]

    result = CommitteeMemberService.remove_member(
        db=db,
        society_id="soc",
        member_id=MEMBER_ID,
        performed_by=ACTOR_ID,
    )

    assert result is target
    assert target.is_active is False


def test_change_role_success():
    target = SimpleNamespace(id="m4", role="secretary", is_active=True, name="S")
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
        _Query(first_result=target),
    ]

    result = CommitteeMemberService.change_role(
        db=db,
        society_id="soc",
        member_id=MEMBER_ID,
        role="treasurer",
        performed_by=ACTOR_ID,
    )

    assert result is target
    assert target.role == "treasurer"


def test_change_role_last_chairman_guard():
    target = SimpleNamespace(id="m6", role="chairman", is_active=True, name="Chair")
    db = MagicMock()
    db.query.side_effect = [
        _Query(first_result=SimpleNamespace(role="chairman", is_active=True)),
        _Query(first_result=target),
        _Query(count_result=1),
    ]

    with pytest.raises(ValueError, match="Cannot remove last active chairman"):
        CommitteeMemberService.change_role(
            db=db,
            society_id="soc",
            member_id=MEMBER_ID,
            role="secretary",
            performed_by=ACTOR_ID,
        )
