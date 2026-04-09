#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.db.models import AuditLog, CommitteeMember
from app.utils.guards import normalize_phone
from app.utils.identity import normalize_identifier
from app.utils.logger import logger
from app.utils.validation import validate_uuid_if_candidate

VALID_COMMITTEE_ROLES = {"chairman", "treasurer", "secretary", "committee_member"}


class CommitteeMemberService:
    @staticmethod
    def _normalize_phone(phone_number: str | None) -> str:
        normalized = normalize_phone(phone_number or "") or normalize_identifier(phone_number)
        if not normalized:
            raise ValueError("Invalid phone number")
        return normalized

    @staticmethod
    def _ensure_actor_authorized(*, db: Session, society_id, performed_by):
        performed_by = validate_uuid_if_candidate(performed_by, field_name="member_id")
        actor = (
            db.query(CommitteeMember)
            .filter(
                CommitteeMember.id == performed_by,
                CommitteeMember.society_id == society_id,
                CommitteeMember.is_active.is_(True),
            )
            .first()
        )
        if not actor:
            raise PermissionError("Only active chairman can perform this action.")

        if (actor.role or "").lower() != "chairman":
            raise PermissionError("Only chairman can perform this action.")

        return actor

    @staticmethod
    def _validate_role(role: str) -> str:
        normalized_role = (role or "").strip().lower()
        if normalized_role not in VALID_COMMITTEE_ROLES:
            raise ValueError(
                "Invalid role. Valid roles: chairman, treasurer, secretary, committee_member."
            )
        return normalized_role

    @staticmethod
    def _audit(db: Session, *, society_id, entity_id, action: str, reason: str, performed_by):
        db.add(
            AuditLog(
                society_id=society_id,
                entity_type="committee_member",
                entity_id=entity_id,
                action=action,
                reason=reason,
                performed_by=performed_by,
            )
        )

    @staticmethod
    def list_members(db: Session, society_id, include_inactive: bool = False):
        query = db.query(CommitteeMember).filter(CommitteeMember.society_id == society_id)
        if not include_inactive:
            query = query.filter(CommitteeMember.is_active.is_(True))
        return query.order_by(CommitteeMember.created_at.asc()).all()

    @staticmethod
    def add_member(db: Session, society_id, name, phone_number, role, performed_by):
        actor = CommitteeMemberService._ensure_actor_authorized(
            db=db,
            society_id=society_id,
            performed_by=performed_by,
        )
        normalized_phone = CommitteeMemberService._normalize_phone(phone_number)
        normalized_role = CommitteeMemberService._validate_role(role)
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise ValueError("Name is required")

        logger.info(
            "Committee member add requested | context=%s",
            {
                "society_id": str(society_id),
                "performed_by": str(performed_by),
                "actor_role": actor.role,
                "phone": normalized_phone,
                "role": normalized_role,
            },
        )

        existing_same_society = (
            db.query(CommitteeMember)
            .filter(
                CommitteeMember.society_id == society_id,
                CommitteeMember.phone_number == normalized_phone,
            )
            .first()
        )
        if existing_same_society and existing_same_society.is_active:
            raise ValueError("An active committee member already exists with this phone number.")

        existing_any_society = (
            db.query(CommitteeMember)
            .filter(CommitteeMember.phone_number == normalized_phone)
            .first()
        )
        if existing_any_society and existing_any_society.society_id != society_id:
            raise ValueError("Phone number is already assigned to another society.")

        if existing_same_society and not existing_same_society.is_active:
            member_row: Any = cast(Any, existing_same_society)
            member_row.name = cleaned_name
            member_row.role = normalized_role
            member_row.is_active = True
            CommitteeMemberService._audit(
                db,
                society_id=society_id,
                entity_id=existing_same_society.id,
                action="REACTIVATE_MEMBER",
                reason=f"Reactivated committee member {cleaned_name}",
                performed_by=performed_by,
            )
            logger.info(
                "Committee member reactivated | context=%s",
                {
                    "society_id": str(society_id),
                    "performed_by": str(performed_by),
                    "member_id": str(existing_same_society.id),
                },
            )
            return existing_same_society

        member = CommitteeMember(
            society_id=society_id,
            name=cleaned_name,
            phone_number=normalized_phone,
            role=normalized_role,
            is_active=True,
        )
        db.add(member)
        db.flush()
        CommitteeMemberService._audit(
            db,
            society_id=society_id,
            entity_id=member.id,
            action="ADD_MEMBER",
            reason=f"Added committee member {cleaned_name}",
            performed_by=performed_by,
        )
        logger.info(
            "Committee member added | context=%s",
            {
                "society_id": str(society_id),
                "performed_by": str(performed_by),
                "member_id": str(member.id),
            },
        )
        return member

    @staticmethod
    def remove_member(db: Session, society_id, member_id, performed_by):
        member_id = validate_uuid_if_candidate(member_id, field_name="member_id")
        CommitteeMemberService._ensure_actor_authorized(
            db=db,
            society_id=society_id,
            performed_by=performed_by,
        )

        target = (
            db.query(CommitteeMember)
            .filter(
                CommitteeMember.id == member_id,
                CommitteeMember.society_id == society_id,
            )
            .first()
        )
        if not target:
            raise ValueError("Committee member not found")
        if not target.is_active:
            return target

        if (target.role or "").lower() == "chairman":
            chairman_count = (
                db.query(CommitteeMember)
                .filter(
                    CommitteeMember.society_id == society_id,
                    CommitteeMember.is_active.is_(True),
                    CommitteeMember.role == "chairman",
                )
                .count()
            )
            if chairman_count <= 1:
                raise ValueError("Cannot remove last active chairman.")

        cast(Any, target).is_active = False
        CommitteeMemberService._audit(
            db,
            society_id=society_id,
            entity_id=target.id,
            action="REMOVE_MEMBER",
            reason=f"Removed committee member {target.name}",
            performed_by=performed_by,
        )
        logger.info(
            "Committee member removed | context=%s",
            {
                "society_id": str(society_id),
                "performed_by": str(performed_by),
                "member_id": str(target.id),
            },
        )
        return target

    @staticmethod
    def change_role(db: Session, society_id, member_id, role, performed_by):
        member_id = validate_uuid_if_candidate(member_id, field_name="member_id")
        CommitteeMemberService._ensure_actor_authorized(
            db=db,
            society_id=society_id,
            performed_by=performed_by,
        )

        target = (
            db.query(CommitteeMember)
            .filter(
                CommitteeMember.id == member_id,
                CommitteeMember.society_id == society_id,
            )
            .first()
        )
        if not target or not target.is_active:
            raise ValueError("Active committee member not found")

        next_role = CommitteeMemberService._validate_role(role)
        previous_role = (target.role or "").lower()
        if previous_role == "chairman" and next_role != "chairman":
            chairman_count = (
                db.query(CommitteeMember)
                .filter(
                    CommitteeMember.society_id == society_id,
                    CommitteeMember.is_active.is_(True),
                    CommitteeMember.role == "chairman",
                )
                .count()
            )
            if chairman_count <= 1:
                raise ValueError("Cannot remove last active chairman.")

        cast(Any, target).role = next_role
        CommitteeMemberService._audit(
            db,
            society_id=society_id,
            entity_id=target.id,
            action="CHANGE_MEMBER_ROLE",
            reason=f"Changed role from {previous_role or 'unknown'} to {next_role}",
            performed_by=performed_by,
        )
        logger.info(
            "Committee member role changed | context=%s",
            {
                "society_id": str(society_id),
                "performed_by": str(performed_by),
                "member_id": str(target.id),
                "new_role": next_role,
            },
        )
        return target
