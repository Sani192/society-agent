#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 18:23:59 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import EventContribution, AuditLog


class ContributionService:

    @staticmethod
    def add_contribution(
        db: Session,
        *,
        event_id,
        society_id,
        contribution_type,
        source_name,
        amount=None,
        in_kind_details=None,
        flat_id=None,
        notes=None,
        performed_by
    ):
        """
        contribution_type:
        - sponsor
        - donation
        - advertising
        - in_kind
        """
        
        count = (
            db.query(EventContribution)
            .filter(EventContribution.event_id == event_id)
            .count()
        )
        
        contribution_code = f"SP-{count + 1:03d}"
        
        contribution = EventContribution(
            event_id=event_id,
            society_id=society_id,
            contribution_code=contribution_code,
            contribution_type=contribution_type,
            source_name=source_name,
            flat_id=flat_id,
            amount=amount,
            in_kind_details=in_kind_details,
            notes=notes
        )

        db.add(contribution)
        db.flush()
        
        db.add(AuditLog(
            society_id=society_id,
            entity_type="event_contribution",
            entity_id=contribution.id,
            action="ADD_CONTRIBUTION",
            reason=notes or "Via WhatsApp",
            performed_by=performed_by
        ))

        db.commit()
        return contribution_code
