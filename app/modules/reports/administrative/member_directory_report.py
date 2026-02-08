#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:05:44 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import UserFlatMapping, Flat
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)

def format_timestamp(value):
    return value.strftime("%d %b %Y %H:%M") if value else "-"


class MemberDirectoryReport:

    @staticmethod
    @log_service_call(logger, "MemberDirectoryReport.generate")
    def generate(db: Session, society_id):
        context = build_log_context(society_id=society_id)
        records = (
            db.query(
                UserFlatMapping.user_identifier,
                UserFlatMapping.role,
                Flat.flat_number,
                Flat.block,
                UserFlatMapping.created_at
            )
            .join(Flat, Flat.id == UserFlatMapping.flat_id)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.is_active == True
            )
            .all()
        )
        if not records:
            logger.info(
                "Workflow decision: no member directory records | context=%s",
                context
            )

        rows = [
            [user, role, flat, block, format_timestamp(created_at), "System"]
            for user, role, flat, block, created_at in records
        ]

        return {
            "headers": [
                "User Identifier",
                "Role",
                "Flat",
                "Block",
                "Created At",
                "Created By"
            ],
            "rows": rows
        }
