from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.modules.users.channel_identity_service import (
    _otp_hash,
    verify_phone_link_challenge,
)


class _QueryStub:
    def __init__(self, *, first_result=None):
        self._first_result = first_result

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._first_result


class _DBStub:
    def __init__(self, *, member, challenge, identity=None):
        self._member = member
        self._challenge = challenge
        self._identity = identity
        self.added = []
        self.commits = 0

    def query(self, model):
        model_name = model.__name__
        if model_name == "CommitteeMember":
            return _QueryStub(first_result=self._member)
        if model_name == "CommitteeMemberPhoneLinkChallenge":
            return _QueryStub(first_result=self._challenge)
        if model_name == "CommitteeMemberChannelIdentity":
            return _QueryStub(first_result=self._identity)
        raise AssertionError(f"unexpected model query: {model_name}")

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def _build_member():
    return SimpleNamespace(
        id=uuid4(),
        society_id=uuid4(),
        phone_number="9999000011",
        is_active=True,
    )


def _build_challenge(*, member, otp="112233", attempts_used=0, max_attempts=3):
    salt = "salt1234"
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        committee_member_id=member.id,
        channel_type="telegram",
        external_user_id="sender-1",
        phone_number=member.phone_number,
        otp_hash=_otp_hash(otp=otp, salt=salt),
        otp_salt=salt,
        created_at=now,
        expires_at=now + timedelta(minutes=5),
        attempts_used=attempts_used,
        max_attempts=max_attempts,
        verified_at=None,
        consumed_at=None,
        last_attempt_at=None,
    )


def test_verify_phone_link_challenge_locks_after_max_attempts():
    member = _build_member()
    challenge = _build_challenge(member=member, attempts_used=2, max_attempts=3)
    db = _DBStub(member=member, challenge=challenge, identity=None)

    result = verify_phone_link_challenge(
        db=db,
        channel_type="telegram",
        sender_id="sender-1",
        phone_number=member.phone_number,
        otp="000000",
        username="janed",
    )

    assert result["status"] == "invalid_otp"
    assert challenge.attempts_used == 3
    assert challenge.consumed_at is not None
    assert db.commits == 1


def test_verify_phone_link_challenge_rejects_replay_after_success():
    member = _build_member()
    challenge = _build_challenge(member=member, attempts_used=0, max_attempts=3)
    db = _DBStub(member=member, challenge=challenge, identity=None)

    first = verify_phone_link_challenge(
        db=db,
        channel_type="telegram",
        sender_id="sender-1",
        phone_number=member.phone_number,
        otp="112233",
        username="janed",
    )
    second = verify_phone_link_challenge(
        db=db,
        channel_type="telegram",
        sender_id="sender-1",
        phone_number=member.phone_number,
        otp="112233",
        username="janed",
    )

    assert first["status"] == "verified"
    assert second["status"] == "challenge_replayed"
