#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 18:23:59 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from app.db.models import Event, EventContribution, AuditLog
from app.workflows.engine import WorkflowEngine
from app.utils.logging_helpers import build_log_context, log_service_call

logger = logging.getLogger(__name__)


class ContributionService:

    @staticmethod
    @log_service_call(logger, "ContributionService.add_contribution")
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
        context = build_log_context(
            event_id=event_id,
            society_id=society_id,
            performed_by=performed_by
        )
        logger.info(
            "Adding contribution | type=%s amount=%s source=%s context=%s",
            contribution_type,
            amount,
            source_name,
            context
        )
        
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")
        logger.info("Validated event for contribution | context=%s", context)

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="ADD_CONTRIBUTION",
            performed_by=performed_by,
            override_reason=override_reason
        )

        is_override = False

        if not decision.allowed:
            logger.warning(
                "Workflow denied contribution action | requires_override=%s context=%s",
                decision.requires_override,
                context
            )
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
        logger.info("Generated contribution code | code=%s context=%s", contribution_code, context)
        
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
        logger.info("Created contribution record | id=%s context=%s", contribution.id, context)

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
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)
        
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
        logger.info("Captured contribution audit log | context=%s", context)

        db.commit()
        logger.info("Committed contribution transaction | context=%s", context)
        return contribution_code
