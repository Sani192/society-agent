#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:45:47 2026

@author: anonymous
"""

# app/modules/onboarding/onboarding_service.py

import logging
from sqlalchemy.orm import Session

from app.db.models import PendingUser, Flat, UserFlatMapping, AuditLog
from app.modules.users.user_flat_service import UserFlatService
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class OnboardingService:

    @staticmethod
    @log_service_call(logger, "OnboardingService.start_onboarding")
    def start_onboarding(
        db: Session,
        *,
        society,
        user_identifier,
        flat_number
    ):
        context = build_log_context(society_id=society.id)
        logger.info(
            "Starting onboarding | user=%s flat_number=%s context=%s",
            user_identifier,
            flat_number,
            context
        )
        onboarding = (society.config_json or {}).get("onboarding")
        if not onboarding:
            raise Exception("Onboarding is not enabled for this society.")
        
        # 1️ BLOCK: already approved user
        existing_mapping = (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society.id,
                UserFlatMapping.user_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if existing_mapping:
            raise Exception("You are already registered with this society.")
        logger.info("No existing active mapping found | context=%s", context)
        
        # 2 Validate flat
        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == flat_number,
                Flat.society_id == society.id,
                Flat.is_active.is_(True)
            )
            .first()
        )

        if not flat:
            raise Exception("Invalid flat number.")
        logger.info("Validated flat for onboarding | flat_id=%s context=%s", flat.id, context)

        approval_required = onboarding.get("approval_required", True)
        
        # 3 Auto-approve
        if not approval_required:
            UserFlatService.assign_user_to_flat(
                db=db,
                society_id=society.id,
                flat_id=flat.id,
                user_identifier=user_identifier,
                performed_by=None
            )
            db.add(AuditLog(
                society_id=society.id,
                entity_type="onboarding",
                entity_id=flat.id,
                action="AUTO_APPROVE_ONBOARDING",
                reason=f"Auto-approved onboarding for {user_identifier}",
                performed_by=None
            ))
            db.commit()
            logger.info("Auto-approved onboarding | context=%s", context)
            return "APPROVED"


        # 4 Check if user already has a pending request
        existing = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society.id,
                PendingUser.user_identifier == user_identifier,
                PendingUser.status == "pending"
            )
            .first()
        )

        if existing:
            logger.info(
                "Existing pending onboarding request found | request_code=%s context=%s",
                existing.request_code,
                context
            )
            return existing.request_code

        # 5 Generate next human-friendly request code
        count = (
            db.query(PendingUser)
            .filter(PendingUser.society_id == society.id)
            .count()
        )

        request_code = f"REQ-{count + 1:03d}"
        logger.info("Generated onboarding request code | request_code=%s context=%s", request_code, context)

        # 6 Create pending request
        pending = PendingUser(
            society_id=society.id,
            request_code=request_code,
            user_identifier=user_identifier,
            flat_number=flat_number
        )

        db.add(pending)
        db.flush()
        logger.info("Created pending onboarding request | id=%s context=%s", pending.id, context)
        db.add(AuditLog(
            society_id=society.id,
            entity_type="onboarding",
            entity_id=pending.id,
            action="REQUEST_ONBOARDING",
            reason=f"Join request {request_code} for flat {flat_number}",
            performed_by=None
        ))
        db.commit()
        logger.info("Committed onboarding request | request_code=%s context=%s", request_code, context)

        return request_code
