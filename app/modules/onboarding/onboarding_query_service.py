#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:52:48 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import PendingUser, UserFlatMapping, MemberIdentity
from app.utils.identity import normalize_identifier


class OnboardingQueryService:

    @staticmethod
    def get_user_join_status(db: Session, *, society_id, user_identifier):
        normalized_identifier = normalize_identifier(user_identifier) or user_identifier
        mapping = (
            db.query(UserFlatMapping)
            .join(MemberIdentity, MemberIdentity.id == UserFlatMapping.member_identity_id)
            .filter(
                UserFlatMapping.society_id == society_id,
                MemberIdentity.normalized_identifier == normalized_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if mapping:
            return "APPROVED"

        pending = (
            db.query(PendingUser)
            .join(MemberIdentity, MemberIdentity.id == PendingUser.member_identity_id)
            .filter(
                PendingUser.society_id == society_id,
                MemberIdentity.normalized_identifier == normalized_identifier,
                PendingUser.status == "pending"
            )
            .first()
        )

        if pending:
            return "PENDING"

        return "NOT_FOUND"
