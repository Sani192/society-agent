#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:57:35 2026

@author: anonymous
"""

# app/modules/reports/sponsor_wise.py

from sqlalchemy.orm import Session

from app.db.models import EventContribution
from app.modules.reports.common.resolvers import get_event_or_raise


class SponsorWiseReport:

    @staticmethod
    def generate(db: Session, *, event_id):
        get_event_or_raise(db, event_id)
        contributions = (
            db.query(EventContribution)
            .filter(EventContribution.event_id == event_id)
            .all()
        )

        return [
            {
                "source": c.source_name,
                "type": c.contribution_type,
                "amount": c.amount,
                "notes": c.notes
            }
            for c in contributions
        ]
