#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 22:58:27 2026

@author: anonymous
"""

# app/modules/reports/sponsors/sponsor_report_service.py

from sqlalchemy.orm import Session

from app.db.models import EventContribution


class SponsorReport:

    @staticmethod
    def generate(db: Session, *, event_id: str):
        rows = (
            db.query(EventContribution)
            .filter(
                EventContribution.event_id == event_id
            )
            .order_by(EventContribution.created_at)
            .all()
        )

        result = []

        for c in rows:
            if c.amount and c.amount > 0:
                result.append({
                    "name": c.source_name,
                    "type": "cash",
                    "amount": int(c.amount)
                })
            else:
                result.append({
                    "name": c.source_name,
                    "type": "in_kind",
                    "details": c.in_kind_details or {}
                })

        return result
