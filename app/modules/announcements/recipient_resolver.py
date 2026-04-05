#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Resolve provider recipient identifiers from member identity + channel."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import MemberIdentity


CHANNEL_RECIPIENT_FIELDS: dict[str, str] = {
    "whatsapp": "whatsapp_user_id",
    "telegram": "telegram_user_id",
}


def resolve_provider_recipient_id(*, db: Session, member_identity_id: UUID | str, channel: str) -> str:
    channel_key = str(channel or "").strip().lower()
    recipient_field = CHANNEL_RECIPIENT_FIELDS.get(channel_key)
    if not recipient_field:
        raise ValueError(f"Unsupported channel: {channel}")

    member_identity = (
        db.query(MemberIdentity)
        .filter(MemberIdentity.id == member_identity_id)
        .one_or_none()
    )
    if member_identity is None:
        raise ValueError(f"Member identity not found: {member_identity_id}")

    recipient_id = str(getattr(member_identity, recipient_field, "") or "").strip()
    if not recipient_id:
        raise ValueError(
            f"Missing provider recipient identifier for member_identity_id={member_identity_id} channel={channel_key}"
        )

    return recipient_id
