#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import MemberIdentity

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
