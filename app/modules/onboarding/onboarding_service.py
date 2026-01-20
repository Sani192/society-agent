#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:45:47 2026

@author: anonymous
"""

# app/modules/onboarding/onboarding_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import PendingUser, Flat, UserFlatMapping
from app.modules.users.user_flat_service import UserFlatService


class OnboardingService:

    @staticmethod
    def start_onboarding(
        db: Session,
        *,
        society,
        user_identifier,
        flat_number
    ):
        onboarding = (society.config_json or {}).get("onboarding")
        if not onboarding:
            raise Exception("Onboarding is not enabled for this society.")
        
        # 1️ BLOCK: already approved user
        existing_mapping = (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society.id,
                UserFlatMapping.user_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if existing_mapping:
            raise Exception("You are already registered with this society.")
        
        # 2 Validate flat
        flat = (
            db.query(Flat)
            .filter(
                Flat.flat_number == flat_number,
                Flat.society_id == society.id,
                Flat.is_active.is_(True)
            )
            .first()
        )

        if not flat:
            raise Exception("Invalid flat number.")

        approval_required = onboarding.get("approval_required", True)
        
        # 3 Auto-approve
        if not approval_required:
            UserFlatService.assign_user_to_flat(
                db=db,
                society_id=society.id,
                flat_id=flat.id,
                user_identifier=user_identifier
            )
            return "APPROVED"


        # 4 Check if user already has a pending request
        existing = (
            db.query(PendingUser)
            .filter(
                PendingUser.society_id == society.id,
                PendingUser.user_identifier == user_identifier,
                PendingUser.status == "pending"
            )
            .first()
        )

        if existing:
            return existing.request_code

        # 5 Generate next human-friendly request code
        count = (
            db.query(PendingUser)
            .filter(PendingUser.society_id == society.id)
            .count()
        )

        request_code = f"REQ-{count + 1:03d}"

        # 6 Create pending request
        pending = PendingUser(
            society_id=society.id,
            request_code=request_code,
            user_identifier=user_identifier,
            flat_number=flat_number
        )

        db.add(pending)
        db.commit()

        return request_code


