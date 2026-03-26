#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:07:09 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import PendingUser, Flat, MemberIdentity
from app.i18n.catalog import translate
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class OnboardingStatusReport:

    @staticmethod
    @log_service_call(logger, "OnboardingStatusReport.generate")
    def generate(db: Session, society_id, *, lang: str | None = None):
        context = build_log_context(society_id=society_id)
        records = (
            db.query(
                PendingUser.request_code,
                MemberIdentity.normalized_identifier,
                Flat.flat_number,
                PendingUser.status,
                PendingUser.created_at
            )
            .join(Flat, Flat.id == PendingUser.flat_id)
            .join(MemberIdentity, MemberIdentity.id == PendingUser.member_identity_id)
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
            "header_keys": ["request_code", "user_identifier", "flat", "status", "created_at", "created_by"],
            "headers": [
                translate("report_exports.labels.headers.request_code", lang),
                translate("report_exports.labels.headers.user_identifier", lang),
                translate("report_exports.labels.headers.flat", lang),
                translate("report_exports.labels.headers.status", lang),
                translate("report_exports.labels.headers.created_at", lang),
                translate("report_exports.labels.headers.created_by", lang),
            ],
            "rows": rows
        }
