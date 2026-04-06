#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Security helpers for service-layer authorization checks."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import CommitteeMember
from app.permissions.guard import is_action_allowed


def require_committee_action(
    db: Session,
    *,
    society_id,
    performed_by,
    action: str,
) -> None:
    if performed_by is None:
        raise Exception("Authentication required for this action")

    committee_member = (
        db.query(CommitteeMember)
        .filter(
            CommitteeMember.id == performed_by,
            CommitteeMember.society_id == society_id,
            CommitteeMember.is_active.is_(True),
        )
        .first()
    )
    if committee_member is None:
        raise Exception("Performer is not an active committee member for this society")

    role = (getattr(committee_member, "role", "") or "").strip().lower()
    if not role:
        raise Exception("Committee member role is not configured")
    if not is_action_allowed(role, action):
        raise Exception("Insufficient role permissions for this action")


def require_committee_roles(
    db: Session,
    *,
    society_id,
    performed_by,
    allowed_roles: set[str],
) -> None:
    if performed_by is None:
        raise Exception("Authentication required for this action")

    committee_member = (
        db.query(CommitteeMember)
        .filter(
            CommitteeMember.id == performed_by,
            CommitteeMember.society_id == society_id,
            CommitteeMember.is_active.is_(True),
        )
        .first()
    )
    if committee_member is None:
        raise Exception("Performer is not an active committee member for this society")

    role = (getattr(committee_member, "role", "") or "").strip().lower()
    if not role:
        raise Exception("Committee member role is not configured")
    if role not in allowed_roles:
        raise Exception("Insufficient role permissions for this action")
