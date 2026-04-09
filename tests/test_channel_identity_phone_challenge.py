from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.modules.users.channel_identity_service import (
    _otp_hash,
    request_phone_link_challenge,
    verify_phone_link_challenge,
)


class _QueryStub:
    def __init__(self, *, first_result=None, all_result=None):
        self._first_result = first_result
        self._all_result = all_result or []
        self.joined_models = []

    def filter(self, *args, **kwargs):
        return self

    def join(self, model, *args, **kwargs):
        self.joined_models.append(model.__name__)
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._all_result

    def first(self):
        return self._first_result


class _DBStub:
    def __init__(self, *, member, challenge, identity=None):
        self._member = member
        self._challenge = challenge
        self._identity = identity
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.refreshes = 0
        self.queries = []

    def query(self, model):
        model_name = model.__name__
        query = None
        if model_name == "CommitteeMember":
            query = _QueryStub(first_result=self._member)
        elif model_name == "CommitteeMemberPhoneLinkChallenge":
            query = _QueryStub(first_result=self._challenge, all_result=[])
        elif model_name == "CommitteeMemberChannelIdentity":
            query = _QueryStub(first_result=self._identity)
        else:
            raise AssertionError(f"unexpected model query: {model_name}")
        self.queries.append((model_name, query))
        return query

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushes += 1

    def refresh(self, _obj):
        self.refreshes += 1

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
    challenge_query = [query for model_name, query in db.queries if model_name == "CommitteeMemberPhoneLinkChallenge"][0]
    assert "CommitteeMember" in challenge_query.joined_models


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


def test_request_phone_link_challenge_does_not_store_denormalized_phone():
    member = _build_member()
    db = _DBStub(member=member, challenge=None, identity=None)

    result = request_phone_link_challenge(
        db=db,
        channel_type="telegram",
        sender_id="sender-1",
        phone_number=member.phone_number,
        username="janed",
    )

    created_challenges = [obj for obj in db.added if obj.__class__.__name__ == "CommitteeMemberPhoneLinkChallenge"]
    assert result["status"] == "issued"
    assert result["delivery_status"] == "not_requested"
    assert len(created_challenges) == 1
    assert not hasattr(created_challenges[0], "phone_number")
    assert "otp" not in result

    audit_logs = [obj for obj in db.added if obj.__class__.__name__ == "AuditLog"]
    assert len(audit_logs) == 2
    for audit in audit_logs:
        metadata = dict(audit.metadata_json or {})
        assert "otp" not in metadata


def test_request_phone_link_challenge_delivers_otp_via_explicit_transport():
    member = _build_member()
    db = _DBStub(member=member, challenge=None, identity=None)
    transport_calls = []

    def _transport(**kwargs):
        transport_calls.append(kwargs)
        return {"status": "queued"}

    result = request_phone_link_challenge(
        db=db,
        channel_type="telegram",
        sender_id="sender-1",
        phone_number=member.phone_number,
        username="janed",
        otp_delivery_transport=_transport,
    )

    assert result["status"] == "issued"
    assert result["delivery_status"] == "queued"
    assert "challenge_id" in result
    assert len(transport_calls) == 1
    assert transport_calls[0]["phone_number"] == member.phone_number
    assert "otp" in transport_calls[0]
