#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:55:32 2026

@author: anonymous
"""

# app/modules/onboarding/admin_query_service.py

from sqlalchemy.orm import Session
from app.db.models import PendingUser


class AdminOnboardingQueryService:

    @staticmethod
    def list_pending_users(db: Session, *, society_id):
        return (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society_id,
                PendingUser.status == "pending"
            )
            .order_by(PendingUser.created_at)
            .all()
        )
