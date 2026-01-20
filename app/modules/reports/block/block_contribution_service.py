#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:07:46 2026

@author: anonymous
"""

# app/modules/reports/block/block_contribution_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import Payment, Flat


class BlockContributionReport:

    @staticmethod
    def generate(db: Session, *, event_id: str):
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

        return {block: int(total or 0) for block, total in rows}
