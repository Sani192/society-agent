#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import MemberIdentity
from app.utils.identity import normalize_identifier

SUPPORTED_LANGUAGE_CODES = {"en", "hi", "gu"}
DEFAULT_LANGUAGE = "en"


def normalize_language_code(language_code: str | None) -> str | None:
    normalized = (language_code or "").strip().lower()
    if normalized in SUPPORTED_LANGUAGE_CODES:
        return normalized
    return None


def get_effective_language(identity: MemberIdentity | None) -> str:
    preferred_language = getattr(identity, "preferred_language", None) if identity else None
    return normalize_language_code(preferred_language) or DEFAULT_LANGUAGE


def resolve_sender_language(
    db: Session,
    *,
    sender_id: str | None,
    channel: Literal["whatsapp", "telegram"] | str,
) -> str:
    if not sender_id:
        return DEFAULT_LANGUAGE

    normalized_sender = normalize_identifier(sender_id)
    sender_candidates = {sender_id, normalized_sender}
    if normalized_sender and len(normalized_sender) > 10:
        sender_candidates.add(normalized_sender[-10:])
    sender_candidates = {candidate for candidate in sender_candidates if candidate}
    if not sender_candidates:
        return DEFAULT_LANGUAGE

    filters = [
        MemberIdentity.normalized_identifier.in_(tuple(sender_candidates)),
        MemberIdentity.normalized_phone.in_(tuple(sender_candidates)),
    ]
    if channel == "whatsapp":
        filters.append(MemberIdentity.whatsapp_user_id.in_(tuple(sender_candidates)))
    elif channel == "telegram":
        filters.append(MemberIdentity.telegram_user_id.in_(tuple(sender_candidates)))

    query_filter = filters[0] | filters[1]
    if len(filters) > 2:
        query_filter = query_filter | filters[2]

    try:
        identity = db.query(MemberIdentity).filter(query_filter).first()
    except Exception:
        return DEFAULT_LANGUAGE
    return get_effective_language(identity)


def set_preferred_language(
    db: Session,
    *,
    identity: MemberIdentity,
    language_code: str,
) -> str:
    normalized_language = normalize_language_code(language_code)
    if not normalized_language:
        raise ValueError("Unsupported language selection")

    setattr(identity, "preferred_language", normalized_language)
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return normalized_language
