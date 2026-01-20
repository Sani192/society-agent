#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 19 23:11:09 2026

@author: anonymous
"""

# app/modules/reports/onboarding/onboarding_pending_service.py

from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.models import PendingUser


class OnboardingPendingReport:

    @staticmethod
    def generate(db: Session, *, society_id: str):
        rows = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society_id,
                PendingUser.status == "pending"
            )
            .order_by(PendingUser.created_at)
            .all()
        )

        result = []
        now = datetime.now(timezone.utc)

        for r in rows:
            days = (now - r.created_at).days
            result.append({
                "request_code": r.request_code,
                "flat_number": r.flat_number,
                "waiting_days": days
            })

        return result
