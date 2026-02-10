from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_

from app.db.models import (
    CommitteeMember,
    CommitteeMemberChannelIdentity,
    CommitteeMemberLinkCode,
)
import re


LINK_CODE_LENGTH = 6
LINK_CODE_TTL_MINUTES = 15


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return re.sub(r"\D", "", phone)


def _generate_code(length: int = LINK_CODE_LENGTH) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def resolve_committee_member_by_identity(
    *,
    db,
    channel_type: str,
    sender_id: str,
    phone_number: str | None = None,
    username: str | None = None,
):
    normalized_phone = _normalize_phone(phone_number or sender_id)

    identity = (
        db.query(CommitteeMemberChannelIdentity)
        .join(CommitteeMember, CommitteeMember.id == CommitteeMemberChannelIdentity.committee_member_id)
        .filter(
            CommitteeMember.is_active.is_(True),
            CommitteeMemberChannelIdentity.channel_type == channel_type,
            or_(
                CommitteeMemberChannelIdentity.external_user_id == str(sender_id),
                CommitteeMemberChannelIdentity.phone_number == normalized_phone,
                CommitteeMemberChannelIdentity.username == username,
            ),
        )
        .first()
    )
    if identity:
        return identity.committee_member

    if normalized_phone:
        legacy_member = (
            db.query(CommitteeMember)
            .filter(CommitteeMember.phone_number == normalized_phone, CommitteeMember.is_active.is_(True))
            .first()
        )
        if legacy_member:
            existing = (
                db.query(CommitteeMemberChannelIdentity)
                .filter(
                    CommitteeMemberChannelIdentity.committee_member_id == legacy_member.id,
                    CommitteeMemberChannelIdentity.channel_type == channel_type,
                    CommitteeMemberChannelIdentity.external_user_id == str(sender_id),
                )
                .first()
            )
            if not existing:
                db.add(
                    CommitteeMemberChannelIdentity(
                        committee_member_id=legacy_member.id,
                        channel_type=channel_type,
                        external_user_id=str(sender_id),
                        phone_number=normalized_phone,
                        username=username,
                        is_verified=True,
                    )
                )
                db.commit()
            return legacy_member

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
    phone_number: str | None = None,
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

    normalized_phone = _normalize_phone(phone_number)
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
            phone_number=normalized_phone,
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
    normalized_phone = _normalize_phone(phone_number)
    if not normalized_phone:
        return None

    member = (
        db.query(CommitteeMember)
        .filter(CommitteeMember.phone_number == normalized_phone, CommitteeMember.is_active.is_(True))
        .first()
    )
    if not member:
        return None

    existing = (
        db.query(CommitteeMemberChannelIdentity)
        .filter(
            CommitteeMemberChannelIdentity.committee_member_id == member.id,
            CommitteeMemberChannelIdentity.channel_type == channel_type,
            CommitteeMemberChannelIdentity.external_user_id == str(sender_id),
        )
        .first()
    )
    if not existing:
        db.add(
            CommitteeMemberChannelIdentity(
                committee_member_id=member.id,
                channel_type=channel_type,
                external_user_id=str(sender_id),
                phone_number=normalized_phone,
                username=username,
                is_verified=True,
            )
        )
        db.commit()
    return member
