#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:05:44 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import UserFlatMapping, Flat, MemberIdentity
from app.i18n.catalog import translate
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class MemberDirectoryReport:

    @staticmethod
    @log_service_call(logger, "MemberDirectoryReport.generate")
    def generate(db: Session, society_id, *, lang: str | None = None):
        context = build_log_context(society_id=society_id)
        records = (
            db.query(
                MemberIdentity.normalized_identifier,
                UserFlatMapping.role,
                Flat.flat_number,
                Flat.block,
                UserFlatMapping.created_at
            )
            .join(Flat, Flat.id == UserFlatMapping.flat_id)
            .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.is_active
            )
            .all()
        )
        if not records:
            logger.info(
                "Workflow decision: no member directory records | context=%s",
                context
            )

        system_label = translate("report_exports.labels.system", lang)
        rows = [
            [user, role, flat, block, format_timestamp(created_at), system_label]
            for user, role, flat, block, created_at in records
        ]

        return {
            "header_keys": ["user_identifier", "role", "flat", "block", "created_at", "created_by"],
            "headers": [
                translate("report_exports.labels.headers.user_identifier", lang),
                translate("report_exports.labels.headers.role", lang),
                translate("report_exports.labels.headers.flat", lang),
                translate("report_exports.labels.headers.block", lang),
                translate("report_exports.labels.headers.created_at", lang),
                translate("report_exports.labels.headers.created_by", lang),
            ],
            "rows": rows
        }
