#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 21:16:26 2026

@author: anonymous
"""

# app/modules/reports/event_summary/service.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import (
    Payment,
    Refund,
    EventExpense,
    EventContribution,
    SocietyBalance
)
from app.modules.reports.common.resolvers import get_event_or_raise
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class EventSummaryReport:

    @staticmethod
    @log_service_call(logger, "EventSummaryReport.generate")
    def generate(db: Session, *, event_id: str):
        context = build_log_context(event_id=event_id)
        # 1️ Load event
        event = get_event_or_raise(db, event_id)

        # 2️ Income from flats (actual paid)
        flat_income = (
            db.query(func.coalesce(func.sum(Payment.paid_amount), 0))
            .filter(
                Payment.event_id == event.id
            )
            .scalar()
        )

        # 3️ Sponsor / contribution income
        sponsor_income = (
            db.query(func.coalesce(func.sum(EventContribution.amount), 0))
            .filter(
                EventContribution.event_id == event.id
            )
            .scalar()
        )

        # 4️ Total expenses
        expenses = (
            db.query(func.coalesce(func.sum(EventExpense.amount), 0))
            .filter(
                EventExpense.event_id == event.id
            )
            .scalar()
        )

        # 5️ Refunds
        refunds = (
            db.query(func.coalesce(func.sum(Refund.amount), 0))
            .filter(
                Refund.event_id == event.id,
                Refund.status == "refunded"
            )
            .scalar()
        )

        # 6️ Opening balance (carry forward)
        balance = (
            db.query(SocietyBalance)
            .filter(
                SocietyBalance.event_id == event.id
            )
            .first()
        )

        opening_balance = balance.opening_balance if balance else 0

        # 7️ Closing balance calculation
        closing_balance = (
            opening_balance
            + flat_income
            + sponsor_income
            - expenses
            - refunds
        )
        logger.info(
            "Workflow decision: calculated closing balance | context=%s",
            context
        )

        return {
            "event": event.name,
            "income": {
                "flats": int(flat_income),
                "sponsors": int(sponsor_income)
            },
            "expenses": int(expenses),
            "refunds": int(refunds),
            "opening_balance": int(opening_balance),
            "closing_balance": int(closing_balance)
        }
