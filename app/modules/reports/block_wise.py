#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:57:00 2026

@author: anonymous
"""

# app/modules/reports/block_wise.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import Flat, Payment
from app.modules.reports.common.resolvers import get_event_or_raise
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class BlockWiseReport:

    @staticmethod
    @log_service_call(logger, "BlockWiseReport.generate")
    def generate(db: Session, *, event_id):
        context = build_log_context(event_id=event_id)
        get_event_or_raise(db, event_id)
        rows = (
            db.query(
                Flat.block,
                func.sum(Payment.paid_amount)
            )
            .join(Payment, Payment.flat_id == Flat.id)
            .filter(Payment.event_id == event_id)
            .group_by(Flat.block)
            .all()
        )
        if not rows:
            logger.info(
                "Workflow decision: no block-wise payments found | context=%s",
                context
            )

        return {
            block: amount or 0
            for block, amount in rows
        }
