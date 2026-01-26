#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 25 17:05:44 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import UserFlatMapping, Flat


class MemberDirectoryReport:

    @staticmethod
    def generate(db: Session, society_id):
        records = (
            db.query(
                UserFlatMapping.user_identifier,
                UserFlatMapping.role,
                Flat.flat_number,
                Flat.block
            )
            .join(Flat, Flat.id == UserFlatMapping.flat_id)
            .filter(
                UserFlatMapping.society_id == society_id,
                UserFlatMapping.is_active == True
            )
            .all()
        )

        rows = [
            [user, role, flat, block]
            for user, role, flat, block in records
        ]

        return {
            "headers": ["User Identifier", "Role", "Flat", "Block"],
            "rows": rows
        }
