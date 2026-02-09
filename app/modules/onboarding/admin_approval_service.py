#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:46:44 2026

@author: anonymous
"""

# app/modules/onboarding/admin_approval_service.py

import logging
from sqlalchemy.orm import Session

from app.db.models import PendingUser, Flat, AuditLog
from app.modules.users.user_flat_service import UserFlatService
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class AdminApprovalService:

    @staticmethod
    @log_service_call(logger, "AdminApprovalService.approve_user")
    def approve_user(db: Session, *, society_id, request_code, performed_by):
        context = build_log_context(society_id=society_id, performed_by=performed_by)
        logger.info("Approving onboarding request | request_code=%s context=%s", request_code, context)
        pending = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society_id,
                PendingUser.request_code == request_code,
                PendingUser.status == "pending"
            )
            .first()
        )

        if not pending or pending.status != "pending":
            raise Exception("Invalid pending request.")
        logger.info("Loaded pending onboarding request | id=%s context=%s", pending.id, context)

        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == pending.flat_number,
                Flat.society_id == pending.society_id
            )
            .first()
        )

        if not flat:
            raise Exception("Flat not found.")
        logger.info("Validated flat for approval | flat_id=%s context=%s", flat.id, context)

        UserFlatService.assign_user_to_flat(
            db=db,
            society_id=pending.society_id,
            flat_id=flat.id,
            user_identifier=pending.user_identifier,
            performed_by=performed_by
        )
        logger.info("Assigned user to flat for approval | context=%s", context)

        pending.status = "approved"
        db.add(AuditLog(
            society_id=pending.society_id,
            entity_type="onboarding",
            entity_id=pending.id,
            action="APPROVE_ONBOARDING",
            reason=f"Approved {pending.request_code}",
            performed_by=performed_by
        ))
        db.commit()
        logger.info("Committed onboarding approval | request_code=%s context=%s", pending.request_code, context)
        return pending
