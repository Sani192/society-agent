#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:07:09 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import PendingUser, Flat
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class OnboardingStatusReport:

    @staticmethod
    @log_service_call(logger, "OnboardingStatusReport.generate")
    def generate(db: Session, society_id):
        context = build_log_context(society_id=society_id)
        records = (
            db.query(
                PendingUser.request_code,
                PendingUser.user_identifier,
                Flat.flat_number,
                PendingUser.status,
                PendingUser.created_at
            )
            .join(Flat, Flat.id == PendingUser.flat_id)
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
                format_timestamp(created),
                user
            ]
            for req, user, flat, status, created in records
        ]

        return {
            "headers": [
                "Request Code",
                "User Identifier",
                "Flat",
                "Status",
                "Created At",
                "Created By"
            ],
            "rows": rows
        }
