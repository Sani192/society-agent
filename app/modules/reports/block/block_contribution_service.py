#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:07:46 2026

@author: anonymous
"""

# app/modules/reports/block/block_contribution_service.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import Payment, Flat
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class BlockContributionReport:

    @staticmethod
    @log_service_call(logger, "BlockContributionReport.generate")
    def generate(db: Session, *, event_id: str):
        context = build_log_context(event_id=event_id)
        rows = (
            db.query(
                Flat.block,
                func.coalesce(func.sum(Payment.paid_amount), 0)
            )
            .join(Flat, Flat.id == Payment.flat_id)
            .filter(
                Payment.event_id == event_id,
                Flat.is_active.is_(True)
            )
            .group_by(Flat.block)
            .order_by(Flat.block)
            .all()
        )
        if not rows:
            logger.info(
                "Workflow decision: no block contributions found | context=%s",
                context
            )

        return {block: int(total or 0) for block, total in rows}
