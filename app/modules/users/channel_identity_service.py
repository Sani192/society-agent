from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Callable

import re

from app.db.models import (
    AuditLog,
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    CommitteeMemberLinkCode,
    CommitteeMemberPhoneLinkChallenge,
)


LINK_CODE_LENGTH = 6
LINK_CODE_TTL_MINUTES = 15
PHONE_LINK_OTP_LENGTH = 6
PHONE_LINK_OTP_TTL_MINUTES = 5
PHONE_LINK_MAX_ATTEMPTS = 5


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return re.sub(r"\D", "", phone)


def _generate_code(length: int = LINK_CODE_LENGTH) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_otp(length: int = PHONE_LINK_OTP_LENGTH) -> str:
    alphabet = string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _otp_hash(*, otp: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{otp}".encode("utf-8")).hexdigest()


def _log_phone_link_audit(
    db,
    *,
    member: CommitteeMember | None,
    action: str,
    reason: str,
    metadata: dict | None = None,
):
    if not member:
        return

    db.add(
        AuditLog(
            society_id=member.society_id,
            entity_type="committee_member_channel_identity",
            entity_id=member.id,
            action=action,
            reason=reason[:255],
            metadata_json=metadata,
            performed_by=member.id,
        )
    )


def resolve_committee_member_by_identity(
    *,
    db,
    channel_type: str,
    sender_id: str,
    username: str | None = None,
):
    query = (
        db.query(CommitteeMemberChannelIdentity)
        .join(CommitteeMember, CommitteeMember.id == CommitteeMemberChannelIdentity.committee_member_id)
        .filter(
            CommitteeMember.is_active.is_(True),
            CommitteeMemberChannelIdentity.channel_type == channel_type,
            CommitteeMemberChannelIdentity.external_user_id == str(sender_id),
        )
    )

    identity = query.first()
    if identity:
        return identity.committee_member

    if username:
        username_identity = (
            db.query(CommitteeMemberChannelIdentity)
            .join(CommitteeMember, CommitteeMember.id == CommitteeMemberChannelIdentity.committee_member_id)
            .filter(
                CommitteeMember.is_active.is_(True),
                CommitteeMemberChannelIdentity.channel_type == channel_type,
                CommitteeMemberChannelIdentity.username == username,
            )
            .first()
        )
        if username_identity:
            return username_identity.committee_member

    return None


def create_member_link_code(*, db, member: CommitteeMember, ttl_minutes: int = LINK_CODE_TTL_MINUTES) -> CommitteeMemberLinkCode:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

    while True:
        code = _generate_code()
        exists = db.query(CommitteeMemberLinkCode).filter(CommitteeMemberLinkCode.code == code).first()
        if not exists:
            break

    link_code = CommitteeMemberLinkCode(
        committee_member_id=member.id,
        code=code,
        expires_at=expires_at,
    )
    db.add(link_code)
    db.commit()
    db.refresh(link_code)
    return link_code


def link_member_by_code(
    *,
    db,
    channel_type: str,
    sender_id: str,
    code: str,
    username: str | None = None,
):
    now = datetime.now(timezone.utc)
    link_code = (
        db.query(CommitteeMemberLinkCode)
        .join(CommitteeMember, CommitteeMember.id == CommitteeMemberLinkCode.committee_member_id)
        .filter(
            CommitteeMemberLinkCode.code == code.upper().strip(),
            CommitteeMemberLinkCode.consumed_at.is_(None),
            CommitteeMemberLinkCode.expires_at >= now,
            CommitteeMember.is_active.is_(True),
        )
        .first()
    )
    if not link_code:
        return None

    identity = (
        db.query(CommitteeMemberChannelIdentity)
        .filter(
            CommitteeMemberChannelIdentity.channel_type == channel_type,
            CommitteeMemberChannelIdentity.external_user_id == str(sender_id),
        )
        .first()
    )
    if not identity:
        identity = CommitteeMemberChannelIdentity(
            committee_member_id=link_code.committee_member_id,
            channel_type=channel_type,
            external_user_id=str(sender_id),
            username=username,
            is_verified=True,
        )
        db.add(identity)

    link_code.consumed_at = now
    db.commit()
    return link_code.committee_member


def link_member_by_phone(
    *,
    db,
    channel_type: str,
    sender_id: str,
    phone_number: str,
    username: str | None = None,
):
    # Deprecated: direct phone-based linking is no longer permitted.
    # Use request_phone_link_challenge + verify_phone_link_challenge instead.
    return None


def request_phone_link_challenge(
    *,
    db,
    channel_type: str,
    sender_id: str,
    phone_number: str,
    username: str | None = None,
    ttl_minutes: int = PHONE_LINK_OTP_TTL_MINUTES,
    max_attempts: int = PHONE_LINK_MAX_ATTEMPTS,
    otp_delivery_transport: Callable[..., bool | dict | None] | None = None,
):
    normalized_phone = _normalize_phone(phone_number)
    if not normalized_phone:
        return {"status": "invalid_phone"}

    member = (
        db.query(CommitteeMember)
        .filter(CommitteeMember.phone_number == normalized_phone, CommitteeMember.is_active.is_(True))
        .first()
    )
    if not member:
        return {"status": "member_not_found"}

    now = datetime.now(timezone.utc)
    otp = _generate_otp()
    salt = secrets.token_hex(16)

    active_challenges = (
        db.query(CommitteeMemberPhoneLinkChallenge)
        .filter(
            CommitteeMemberPhoneLinkChallenge.committee_member_id == member.id,
            CommitteeMemberPhoneLinkChallenge.channel_type == channel_type,
            CommitteeMemberPhoneLinkChallenge.external_user_id == str(sender_id),
            CommitteeMemberPhoneLinkChallenge.consumed_at.is_(None),
            CommitteeMemberPhoneLinkChallenge.expires_at >= now,
        )
        .all()
    )
    for active in active_challenges:
        active.consumed_at = now

    challenge = CommitteeMemberPhoneLinkChallenge(
        committee_member_id=member.id,
        channel_type=channel_type,
        external_user_id=str(sender_id),
        username=username,
        otp_hash=_otp_hash(otp=otp, salt=salt),
        otp_salt=salt,
        expires_at=now + timedelta(minutes=ttl_minutes),
        max_attempts=max_attempts,
    )
    db.add(challenge)
    db.flush()
    _log_phone_link_audit(
        db,
        member=member,
        action="LINK_CHALLENGE_REQUESTED",
        reason="channel_link_phone_challenge_requested",
        metadata={
            "channel_type": channel_type,
            "sender_id": str(sender_id),
            "challenge_id": str(challenge.id),
        },
    )
    db.commit()
    db.refresh(challenge)
    delivery_status = "not_requested"
    if otp_delivery_transport:
        delivery_result = otp_delivery_transport(
            member=member,
            phone_number=normalized_phone,
            otp=otp,
            challenge=challenge,
            channel_type=channel_type,
            sender_id=str(sender_id),
        )
        if isinstance(delivery_result, dict):
            delivery_status = str(delivery_result.get("status") or "unknown")
        elif isinstance(delivery_result, bool):
            delivery_status = "sent" if delivery_result else "failed"
        elif delivery_result is None:
            delivery_status = "unknown"
        else:
            delivery_status = str(delivery_result)

    _log_phone_link_audit(
        db,
        member=member,
        action="LINK_CHALLENGE_DELIVERY_ATTEMPTED",
        reason="channel_link_phone_challenge_delivery_attempted",
        metadata={
            "channel_type": channel_type,
            "sender_id": str(sender_id),
            "challenge_id": str(challenge.id),
            "delivery_status": delivery_status,
        },
    )
    db.commit()
    return {"status": "issued", "challenge_id": challenge.id, "delivery_status": delivery_status}


def verify_phone_link_challenge(
    *,
    db,
    channel_type: str,
    sender_id: str,
    phone_number: str,
    otp: str,
    username: str | None = None,
):
    normalized_phone = _normalize_phone(phone_number)
    if not normalized_phone or not otp:
        return {"status": "invalid_input"}

    member = (
        db.query(CommitteeMember)
        .filter(CommitteeMember.phone_number == normalized_phone, CommitteeMember.is_active.is_(True))
        .first()
    )
    if not member:
        return {"status": "member_not_found"}

    now = datetime.now(timezone.utc)
    challenge = (
        db.query(CommitteeMemberPhoneLinkChallenge)
        .join(CommitteeMember, CommitteeMember.id == CommitteeMemberPhoneLinkChallenge.committee_member_id)
        .filter(
            CommitteeMemberPhoneLinkChallenge.committee_member_id == member.id,
            CommitteeMemberPhoneLinkChallenge.channel_type == channel_type,
            CommitteeMemberPhoneLinkChallenge.external_user_id == str(sender_id),
            CommitteeMember.phone_number == normalized_phone,
            CommitteeMember.is_active.is_(True),
        )
        .order_by(CommitteeMemberPhoneLinkChallenge.created_at.desc())
        .first()
    )
    if not challenge:
        _log_phone_link_audit(
            db,
            member=member,
            action="LINK_CHALLENGE_FAILED",
            reason="challenge_missing",
            metadata={"channel_type": channel_type, "sender_id": str(sender_id)},
        )
        db.commit()
        return {"status": "challenge_missing"}

    if challenge.verified_at is not None or challenge.consumed_at is not None:
        _log_phone_link_audit(
            db,
            member=member,
            action="LINK_CHALLENGE_FAILED",
            reason="challenge_replayed",
            metadata={"challenge_id": str(challenge.id)},
        )
        db.commit()
        return {"status": "challenge_replayed"}

    if challenge.expires_at < now:
        challenge.consumed_at = now
        _log_phone_link_audit(
            db,
            member=member,
            action="LINK_CHALLENGE_FAILED",
            reason="challenge_expired",
            metadata={"challenge_id": str(challenge.id)},
        )
        db.commit()
        return {"status": "challenge_expired"}

    if challenge.attempts_used >= challenge.max_attempts:
        challenge.consumed_at = now
        _log_phone_link_audit(
            db,
            member=member,
            action="LINK_CHALLENGE_FAILED",
            reason="challenge_attempt_limit",
            metadata={"challenge_id": str(challenge.id)},
        )
        db.commit()
        return {"status": "challenge_attempt_limit"}

    if not secrets.compare_digest(challenge.otp_hash, _otp_hash(otp=otp.strip(), salt=challenge.otp_salt)):
        challenge.attempts_used = int(challenge.attempts_used or 0) + 1
        challenge.last_attempt_at = now
        if challenge.attempts_used >= challenge.max_attempts:
            challenge.consumed_at = now
        _log_phone_link_audit(
            db,
            member=member,
            action="LINK_CHALLENGE_FAILED",
            reason="challenge_invalid_otp",
            metadata={
                "challenge_id": str(challenge.id),
                "attempts_used": challenge.attempts_used,
                "max_attempts": challenge.max_attempts,
            },
        )
        db.commit()
        return {"status": "invalid_otp", "attempts_used": challenge.attempts_used, "max_attempts": challenge.max_attempts}

    identity = (
        db.query(CommitteeMemberChannelIdentity)
        .filter(
            CommitteeMemberChannelIdentity.channel_type == channel_type,
            CommitteeMemberChannelIdentity.external_user_id == str(sender_id),
        )
        .first()
    )
    if not identity:
        db.add(
            CommitteeMemberChannelIdentity(
                committee_member_id=member.id,
                channel_type=channel_type,
                external_user_id=str(sender_id),
                username=username,
                is_verified=True,
            )
        )

    challenge.verified_at = now
    challenge.consumed_at = now
    challenge.last_attempt_at = now
    _log_phone_link_audit(
        db,
        member=member,
        action="LINK_CHALLENGE_VERIFIED",
        reason="channel_link_phone_challenge_verified",
        metadata={"challenge_id": str(challenge.id), "channel_type": channel_type},
    )
    db.commit()
    return {"status": "verified", "member": member}
