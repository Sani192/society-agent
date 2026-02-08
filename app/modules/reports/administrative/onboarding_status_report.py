#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:07:09 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import PendingUser
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class OnboardingStatusReport:

    @staticmethod
    @log_service_call(logger, "OnboardingStatusReport.generate")
    def generate(db: Session, society_id):
        context = build_log_context(society_id=society_id)
        records = (
            db.query(
                PendingUser.request_code,
                PendingUser.user_identifier,
                PendingUser.flat_number,
                PendingUser.status,
                PendingUser.created_at
            )
            .filter(PendingUser.society_id == society_id)
            .all()
        )
        if not records:
            logger.info(
                "Workflow decision: no onboarding status records | context=%s",
                context
            )

        rows = [
            [
                req,
                user,
                flat,
                status,
                created.strftime("%d %b %Y")
            ]
            for req, user, flat, status, created in records
        ]

        return {
            "headers": [
                "Request Code",
                "User Identifier",
                "Flat",
                "Status",
                "Requested On"
            ],
            "rows": rows
        }
