#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:38:24 2026

@author: anonymous
"""

# app/modules/reports/expenses/expense_summary_service.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import EventExpense
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class ExpenseSummaryReport:

    @staticmethod
    @log_service_call(logger, "ExpenseSummaryReport.generate")
    def generate(db: Session, *, event_id: str):
        context = build_log_context(event_id=event_id)
        rows = (
            db.query(
                EventExpense.description,
                func.coalesce(func.sum(EventExpense.amount), 0)
            )
            .filter(
                EventExpense.event_id == event_id
            )
            .group_by(EventExpense.description)
            .all()
        )
        if not rows:
            logger.info(
                "Workflow decision: no expenses found | context=%s",
                context
            )

        summary = {}
        for description, total in rows:
            key = description.strip().title()
            summary[key] = int(total or 0)

        if not summary:
            logger.info(
                "Workflow decision: expense summary empty | context=%s",
                context
            )
        return summary
