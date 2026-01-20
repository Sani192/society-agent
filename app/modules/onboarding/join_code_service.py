#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 10:44:21 2026

@author: anonymous
"""

# app/modules/onboarding/join_code_service.py

from sqlalchemy.orm import Session
from app.db.models import Society


class JoinCodeService:

    @staticmethod
    def get_society_by_join_code(db: Session, join_code: str):
        societies = db.query(Society).filter(Society.is_active.is_(True)).all()

        for society in societies:
            onboarding = (society.config_json or {}).get("onboarding", {})
            if onboarding.get("join_code") == join_code:
                return society

        return None
