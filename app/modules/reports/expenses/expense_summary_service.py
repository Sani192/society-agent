#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:38:24 2026

@author: anonymous
"""

# app/modules/reports/expenses/expense_summary_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import EventExpense


class ExpenseSummaryReport:

    @staticmethod
    def generate(db: Session, *, event_id: str):
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

        summary = {}
        for description, total in rows:
            key = description.strip().title()
            summary[key] = int(total or 0)

        return summary
