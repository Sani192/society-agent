#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 04 10:29:20 2026

@author: anonymous
"""

# app/whatsapp/handlers/common.py

from uuid import UUID

from app.db.models import Event, Flat, MemberIdentity, UserFlatMapping
from app.utils.guards import ensure_member_of_society, normalize_phone




def get_latest_event(db):
    """Backward-compatible global latest event resolver; prefer society-scoped resolver."""
    return db.query(Event).order_by(Event.created_at.desc()).first()


def get_latest_event_for_society(db, society_id):
    if not society_id:
        return None
    try:
        return (
            db.query(Event)
            .filter(Event.society_id == society_id)
            .order_by(Event.created_at.desc())
            .first()
        )
    except Exception:
        return None


def resolve_sender_society_id(db, sender_id):
    normalized_sender = normalize_phone(sender_id)
    if not normalized_sender:
        return None

    candidate_ids = {normalized_sender}
    if len(normalized_sender) > 10:
        candidate_ids.add(normalized_sender[-10:])

    try:
        mapping = (
            db.query(UserFlatMapping.society_id)
            .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
            .filter(
                MemberIdentity.normalized_identifier.in_(tuple(candidate_ids)),
                UserFlatMapping.is_active.is_(True),
            )
            .order_by(UserFlatMapping.created_at.desc())
            .first()
        )
        if not mapping:
            return None
        society_id = getattr(mapping, "society_id", None)
        if society_id is None:
            return None
        if isinstance(society_id, (str, int, bytes, UUID)):
            return society_id
        return None
    except Exception:
        return None


def resolve_flat(
    db,
    *,
    phone_number,
    society_id,
    flat_number=None
):
    if flat_number:
        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == flat_number,
                Flat.society_id == society_id
            )
            .first()
        )
        if not flat:
            raise Exception("Flat not found in society.")
        return flat

    mappings = ensure_member_of_society(phone_number, db, society_id)
    return db.query(Flat).get(mappings[0].flat_id)
