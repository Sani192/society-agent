#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 05:57:00 2026

@author: anonymous
"""

# app/modules/reports/block_wise.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import Flat, Payment


class BlockWiseReport:

    @staticmethod
    def generate(db: Session, *, event_id):
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

        return {
            block: amount or 0
            for block, amount in rows
        }
