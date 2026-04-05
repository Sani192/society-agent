#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 18:29:55 2026

@author: anonymous
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import ContributionRefund, EventContribution, Event, AuditLog
from app.workflows.engine import WorkflowEngine
from app.utils.logging_helpers import build_log_context, log_service_call
from app.utils.currency import format_currency

logger = logging.getLogger(__name__)

class ContributionRefundService:

    @staticmethod
    @log_service_call(logger, "ContributionRefundService.process_refund")
    def process_refund(
        db: Session,
        *,
        event_id,
        contribution_code,
        amount,
        reason,
        performed_by,
        override_reason=None
    ):
        context = build_log_context(event_id=event_id, performed_by=performed_by)
        logger.info(
            "Processing contribution refund | amount=%s code=%s context=%s",
            amount,
            contribution_code,
            context
        )
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise Exception("Invalid event")

        contribution = (
            db.query(EventContribution)
            .filter(
                EventContribution.event_id == event_id,
                EventContribution.contribution_code == contribution_code
            )
            .first()
        )

        if not contribution:
            raise Exception("Invalid sponsor reference.")

        if not contribution.amount:
            raise Exception("In-kind contribution cannot be refunded.")
        logger.info(
            "Validated contribution for refund | contribution_id=%s context=%s",
            contribution.id,
            context
        )
            
        total_refunded = (
            db.query(func.coalesce(func.sum(ContributionRefund.amount), 0))
            .filter(
                ContributionRefund.contribution_id == contribution.id,
                ContributionRefund.status == "refunded"
            )
            .scalar()
        )
        
        if total_refunded + amount > contribution.amount:
            remaining = max(0, contribution.amount - total_refunded)
            raise Exception(
                f"Refund exceeds contribution amount. "
                f"Remaining refundable amount: {format_currency(remaining)}"
            )
        logger.info(
            "Refund amount validated | total_refunded=%s context=%s",
            total_refunded,
            context
        )

        decision = WorkflowEngine.check_action(
            db=db,
            event_id=event_id,
            action="REFUND_CONTRIBUTION",
            performed_by=performed_by,
            override_reason=override_reason
        )

        is_override = False

        if not decision.allowed:
            logger.warning(
                "Workflow denied contribution refund action | requires_override=%s context=%s",
                decision.requires_override,
                context
            )
            if not decision.requires_override:
                raise Exception(decision.message)
            if not override_reason:
                raise Exception(decision.message)
            is_override = True


        refund = ContributionRefund(
            contribution_id=contribution.id,
            amount=amount,
            reason=reason,
            status="refunded"
        )

        db.add(refund)
        db.flush()
        logger.info("Created contribution refund record | id=%s context=%s", refund.id, context)

        if is_override:
            WorkflowEngine.apply_override(
                db=db,
                society_id=event.society_id,
                event_id=event_id,
                entity_type="contribution_refund",
                entity_id=refund.id,
                action="REFUND_CONTRIBUTION",
                reason=override_reason,
                performed_by=performed_by
            )
            logger.info("Applied workflow override | reason=%s context=%s", override_reason, context)

        db.add(AuditLog(
            society_id=event.society_id,
            entity_type="contribution_refund",
            entity_id=refund.id,
            action="REFUND_CONTRIBUTION",
            reason=(
                f"OVERRIDE: {override_reason}"
                if is_override
                else reason
            ),
            performed_by=performed_by
        ))
        logger.info("Captured contribution refund audit log | context=%s", context)

        db.commit()
        logger.info("Committed contribution refund transaction | context=%s", context)
        
