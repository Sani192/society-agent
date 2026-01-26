#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 16:22:26 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import EventContribution, Flat


class SponsorContributionReport:

    @staticmethod
    def generate(db: Session, event_id):
        records = (
            db.query(
                EventContribution.contribution_type,
                EventContribution.source_name,
                Flat.flat_number,
                EventContribution.amount,
                EventContribution.in_kind_details
            )
            .outerjoin(Flat, Flat.id == EventContribution.flat_id)
            .filter(EventContribution.event_id == event_id)
            .all()
        )

        rows = []
        total_cash = 0

        for ctype, source, flat, amount, in_kind in records:
            cash = amount or 0
            total_cash += cash

            rows.append([
                ctype,
                source,
                flat or "-",
                cash,
                in_kind or "-"
            ])

        return {
            "headers": [
                "Contribution Type",
                "Source",
                "Flat",
                "Cash Amount",
                "In-kind Contribution"
            ],
            "rows": rows,
            "total_cash": total_cash
        }
