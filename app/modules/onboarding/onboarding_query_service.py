#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:52:48 2026

@author: anonymous
"""

# app/modules/onboarding/onboarding_query_service.py

from sqlalchemy.orm import Session
from app.db.models import PendingUser, UserFlatMapping


class OnboardingQueryService:

    @staticmethod
    def get_user_join_status(db: Session, *, society_id, user_identifier):
        mapping = (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.user_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if mapping:
            return "APPROVED"

        pending = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society_id,
                PendingUser.user_identifier == user_identifier,
                PendingUser.status == "pending"
            )
            .first()
        )

        if pending:
            return "PENDING"

        return "NOT_FOUND"
