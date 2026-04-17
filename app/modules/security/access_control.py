#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Security helpers for service-layer authorization checks."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import CommitteeMember
from app.permissions.guard import is_action_allowed
from app.utils.security_logging import log_security_event
from app.utils.logger import get_logger

logger = get_logger(__name__)


def require_committee_action(
    db: Session,
    *,
    society_id,
    performed_by,
    action: str,
) -> None:
    if performed_by is None:
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=None,
            society_id=str(society_id) if society_id is not None else None,
            action=action,
            method="committee_action",
            result="denied",
            reason_code="AUTH_REQUIRED",
        )
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
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=str(performed_by),
            society_id=str(society_id) if society_id is not None else None,
            action=action,
            method="committee_action",
            result="denied",
            reason_code="MEMBER_NOT_ACTIVE",
        )
        raise Exception("Performer is not an active committee member for this society")

    role = (getattr(committee_member, "role", "") or "").strip().lower()
    if not role:
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=str(performed_by),
            society_id=str(society_id) if society_id is not None else None,
            action=action,
            method="committee_action",
            result="denied",
            reason_code="ROLE_MISSING",
        )
        raise Exception("Committee member role is not configured")
    if not is_action_allowed(role, action):
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=str(performed_by),
            society_id=str(society_id) if society_id is not None else None,
            action=action,
            method="committee_action",
            result="denied",
            reason_code="ROLE_NOT_ALLOWED",
            role=role,
        )
        raise Exception("Insufficient role permissions for this action")


def require_committee_roles(
    db: Session,
    *,
    society_id,
    performed_by,
    allowed_roles: set[str],
) -> None:
    if performed_by is None:
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=None,
            society_id=str(society_id) if society_id is not None else None,
            action="committee_role_check",
            method="committee_roles",
            result="denied",
            reason_code="AUTH_REQUIRED",
        )
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
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=str(performed_by),
            society_id=str(society_id) if society_id is not None else None,
            action="committee_role_check",
            method="committee_roles",
            result="denied",
            reason_code="MEMBER_NOT_ACTIVE",
        )
        raise Exception("Performer is not an active committee member for this society")

    role = (getattr(committee_member, "role", "") or "").strip().lower()
    if not role:
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=str(performed_by),
            society_id=str(society_id) if society_id is not None else None,
            action="committee_role_check",
            method="committee_roles",
            result="denied",
            reason_code="ROLE_MISSING",
        )
        raise Exception("Committee member role is not configured")
    if role not in allowed_roles:
        log_security_event(
            logger,
            event="unauthorized_access",
            actor_id=str(performed_by),
            society_id=str(society_id) if society_id is not None else None,
            action="committee_role_check",
            method="committee_roles",
            result="denied",
            reason_code="ROLE_NOT_ALLOWED",
            role=role,
            allowed_roles=sorted(allowed_roles),
        )
        raise Exception("Insufficient role permissions for this action")
