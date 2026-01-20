#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:46:44 2026

@author: anonymous
"""

# app/modules/onboarding/admin_approval_service.py

from sqlalchemy.orm import Session

from app.db.models import PendingUser, Flat
from app.modules.users.user_flat_service import UserFlatService


class AdminApprovalService:

    @staticmethod
    def approve_user(db: Session, *, society_id, request_code):
        pending = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society_id,
                PendingUser.request_code == request_code,
                PendingUser.status == "pending"
            )
            .first()
        )

        if not pending or pending.status != "pending":
            raise Exception("Invalid pending request.")

        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == pending.flat_number,
                Flat.society_id == pending.society_id
            )
            .first()
        )

        if not flat:
            raise Exception("Flat not found.")

        UserFlatService.assign_user_to_flat(
            db=db,
            society_id=pending.society_id,
            flat_id=flat.id,
            user_identifier=pending.user_identifier
        )

        pending.status = "approved"
        db.commit()
        return pending
