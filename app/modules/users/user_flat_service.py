#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 10:54:04 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session

from app.db.models import UserFlatMapping, AuditLog, MemberIdentity
from app.utils.identity import normalize_identifier
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class UserFlatService:

    @staticmethod
    @log_service_call(logger, "UserFlatService.assign_user_to_flat")
    def assign_user_to_flat(
        db: Session,
        *,
        society_id,
        flat_id,
        member_identity_id,
        performed_by=None,
    ):
        context = build_log_context(society_id=society_id, performed_by=performed_by)
        identity = db.query(MemberIdentity).filter(MemberIdentity.id == member_identity_id).first()
        if not identity:
            raise Exception("Member identity not found")

        logger.info(
            "Assigning user to flat | flat_id=%s user=%s context=%s",
            flat_id,
            identity.normalized_identifier,
            context,
        )

        existing = (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.flat_id == flat_id,
                UserFlatMapping.member_identity_id == identity.id,
                UserFlatMapping.is_active.is_(True),
            )
            .first()
        )
        if existing:
            logger.info("User already mapped to flat | mapping_id=%s context=%s", existing.id, context)
            return existing

        mapping = UserFlatMapping(
            society_id=society_id,
            flat_id=flat_id,
            member_identity_id=identity.id,
        )
        db.add(mapping)
        db.flush()

        logger.info("Created user-flat mapping | mapping_id=%s context=%s", mapping.id, context)
        db.add(
            AuditLog(
                society_id=society_id,
                entity_type="user_flat_mapping",
                entity_id=mapping.id,
                action="ASSIGN_USER_FLAT",
                reason=f"Mapped {identity.normalized_identifier} to flat {flat_id}",
                performed_by=performed_by,
            )
        )
        logger.info("Captured user-flat audit log | context=%s", context)
        db.commit()
        logger.info("Committed user-flat assignment | context=%s", context)
        return mapping

    @staticmethod
    @log_service_call(logger, "UserFlatService.get_flats_for_user")
    def get_flats_for_user(
        db: Session,
        *,
        society_id,
        user_identifier,
    ):
        context = build_log_context(society_id=society_id)
        normalized_identifier = normalize_identifier(user_identifier) or user_identifier
        logger.info("Fetching flats for user | user=%s context=%s", normalized_identifier, context)
        return (
            db.query(UserFlatMapping)
            .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
            .filter(
                UserFlatMapping.society_id == society_id,
                MemberIdentity.normalized_identifier == normalized_identifier,
                UserFlatMapping.is_active.is_(True),
            )
            .all()
        )
