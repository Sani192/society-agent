#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  8 14:58:17 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import Refund, Flat, CommitteeMember


class MemberRefundReport:

    @staticmethod
    def generate(db: Session, *, event_id):
        records = (
            db.query(
                Flat.flat_number,
                Refund.amount,
                Refund.reason,
                Refund.created_at,
                CommitteeMember.name.label("approved_by")
            )
            .join(Flat, Flat.id == Refund.flat_id)
            .outerjoin(
                CommitteeMember,
                CommitteeMember.id == Refund.created_by
            )
            .filter(
                Refund.event_id == event_id,
                Refund.status.in_(["approved", "refunded"])
            )
            .order_by(Refund.created_at)
            .all()
        )

        rows = []
        for r in records:
            rows.append([
                r.flat_number,
                r.amount,
                r.reason,
                r.approved_by or "-",
                r.created_at.strftime("%d-%m-%Y %H:%M")
            ])

        return {
            "headers": [
                "Flat",
                "Refund Amount",
                "Reason",
                "Approved By",
                "Date"
            ],
            "rows": rows
        }