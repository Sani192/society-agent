#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jan 17 10:54:04 2026

@author: anonymous
"""

# app/modules/users/user_flat_service.py

from sqlalchemy.orm import Session
from app.db.models import UserFlatMapping


class UserFlatService:

    @staticmethod
    def assign_user_to_flat(
        db: Session,
        *,
        society_id,
        flat_id,
        user_identifier
    ):
        existing = (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.flat_id == flat_id,
                UserFlatMapping.user_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .first()
        )

        if existing:
            return existing

        mapping = UserFlatMapping(
            society_id=society_id,
            flat_id=flat_id,
            user_identifier=user_identifier
        )

        db.add(mapping)
        db.commit()
        return mapping

    @staticmethod
    def get_flats_for_user(
        db: Session,
        *,
        society_id,
        user_identifier
    ):
        return (
            db.query(UserFlatMapping)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.user_identifier == user_identifier,
                UserFlatMapping.is_active.is_(True)
            )
            .all()
        )
