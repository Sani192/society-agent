#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:07:09 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import PendingUser


class OnboardingStatusReport:

    @staticmethod
    def generate(db: Session, society_id):
        records = (
            db.query(
                PendingUser.request_code,
                PendingUser.user_identifier,
                PendingUser.flat_number,
                PendingUser.status,
                PendingUser.created_at
            )
            .filter(PendingUser.society_id == society_id)
            .all()
        )

        rows = [
            [
                req,
                user,
                flat,
                status,
                created.strftime("%d %b %Y")
            ]
            for req, user, flat, status, created in records
        ]

        return {
            "headers": [
                "Request Code",
                "User Identifier",
                "Flat",
                "Status",
                "Requested On"
            ],
            "rows": rows
        }
