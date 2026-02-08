#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 18:23:59 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from app.db.models import Event, EventContribution, AuditLog
from app.workflows.engine import WorkflowEngine


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
        performed_by,
        override_reason=None
    ):
        """
        contribution_type:
        - sponsor
        - donation
        - advertising
        - in_kind
        """
        
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_CONTRIBUTION",
            performed_by=performed_by,
            override_reason=override_reason
        )

        is_override = False

        if not decision.allowed:
            if not decision.requires_override:
                raise Exception(decision.message)
            if not override_reason:
                raise Exception(decision.message)
            is_override = True

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

        if is_override:
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="event_contribution",
                entity_id=contribution.id,
                action="ADD_CONTRIBUTION",
                reason=override_reason,
                performed_by=performed_by
            )
        
        db.add(AuditLog(
            society_id=society_id,
            entity_type="event_contribution",
            entity_id=contribution.id,
            action="ADD_CONTRIBUTION",
            reason=(
                f"OVERRIDE: {override_reason}"
                if is_override
                else notes or "Via WhatsApp"
            ),
            performed_by=performed_by
        ))

        db.commit()
        return contribution_code
