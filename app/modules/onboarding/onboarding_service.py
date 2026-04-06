#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:45:47 2026

@author: anonymous
"""

import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import PendingUser, Flat, UserFlatMapping, AuditLog
from app.modules.users.member_identity_service import MemberIdentityService
from app.modules.users.user_flat_service import UserFlatService
from app.utils.identity import normalize_identifier
from app.utils.logging_helpers import build_log_context, log_service_call
from app.utils.logging_helpers import mask_phone

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
        normalized_identifier = normalize_identifier(user_identifier) or user_identifier
        identity = MemberIdentityService.resolve_or_create(db, user_identifier=normalized_identifier)
        logger.info(
            "Starting onboarding | user=%s flat_number=%s context=%s",
            mask_phone(normalized_identifier),
            flat_number,
            context
        )
        onboarding = (society.config_json or {}).get("onboarding")
        if not onboarding:
            raise Exception("Onboarding is not enabled for this society.")

        existing_mapping = (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society.id,
                UserFlatMapping.member_identity_id == identity.id,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if existing_mapping:
            raise Exception("You are already registered with this society.")
        logger.info("No existing active mapping found | context=%s", context)

        flat_matches = (
            db.query(Flat)
            .filter(
                Flat.flat_number == flat_number,
                Flat.society_id == society.id,
                Flat.is_active.is_(True)
            )
            .all()
        )

        if not flat_matches:
            raise Exception("Invalid flat number.")
        if len(flat_matches) > 1:
            raise Exception("Flat data conflict detected. Please contact committee.")
        flat = flat_matches[0]
        logger.info("Validated flat for onboarding | flat_id=%s context=%s", flat.id, context)

        approval_required = onboarding.get("approval_required", True)

        if not approval_required:
            UserFlatService.assign_user_to_flat(
                db=db,
                society_id=society.id,
                flat_id=flat.id,
                member_identity_id=identity.id,
                performed_by=None
            )
            db.add(AuditLog(
                society_id=society.id,
                entity_type="onboarding",
                entity_id=flat.id,
                action="AUTO_APPROVE_ONBOARDING",
                reason=f"Auto-approved onboarding for {normalized_identifier}",
                performed_by=None
            ))
            db.commit()
            logger.info("Auto-approved onboarding | context=%s", context)
            return "APPROVED"

        existing = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society.id,
                PendingUser.member_identity_id == identity.id,
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

        count = (
            db.query(PendingUser)
            .filter(PendingUser.society_id == society.id)
            .count()
        )

        request_code = f"REQ-{count + 1:03d}"
        logger.info("Generated onboarding request code | request_code=%s context=%s", request_code, context)

        pending = PendingUser(
            society_id=society.id,
            request_code=request_code,
            member_identity_id=identity.id,
            flat_id=flat.id
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
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            logger.warning("Onboarding request conflict | context=%s error=%s", context, exc)
            raise Exception("An onboarding request already exists for this user.") from exc
        logger.info("Committed onboarding request | request_code=%s context=%s", request_code, context)

        return request_code
