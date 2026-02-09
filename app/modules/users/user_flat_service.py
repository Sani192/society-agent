#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 10:54:04 2026

@author: anonymous
"""

# app/modules/users/user_flat_service.py

import logging
from sqlalchemy.orm import Session
from app.db.models import UserFlatMapping, AuditLog
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
        user_identifier,
        performed_by=None
    ):
        context = build_log_context(society_id=society_id, performed_by=performed_by)
        logger.info(
            "Assigning user to flat | flat_id=%s user=%s context=%s",
            flat_id,
            user_identifier,
            context
        )
        existing = (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.flat_id == flat_id,
                UserFlatMapping.user_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if existing:
            logger.info("User already mapped to flat | mapping_id=%s context=%s", existing.id, context)
            return existing

        mapping = UserFlatMapping(
            society_id=society_id,
            flat_id=flat_id,
            user_identifier=user_identifier
        )

        db.add(mapping)
        db.flush()
        logger.info("Created user-flat mapping | mapping_id=%s context=%s", mapping.id, context)
        db.add(AuditLog(
            society_id=society_id,
            entity_type="user_flat_mapping",
            entity_id=mapping.id,
            action="ASSIGN_USER_FLAT",
            reason=f"Mapped {user_identifier} to flat {flat_id}",
            performed_by=performed_by
        ))
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
        user_identifier
    ):
        context = build_log_context(society_id=society_id)
        logger.info("Fetching flats for user | user=%s context=%s", user_identifier, context)
        return (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.user_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .all()
        )
