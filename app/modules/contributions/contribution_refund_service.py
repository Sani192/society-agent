#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 18:29:55 2026

@author: anonymous
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import ContributionRefund, EventContribution, AuditLog

class ContributionRefundService:

    @staticmethod
    def process_refund(
        db: Session,
        *,
        event_id,
        contribution_code,
        amount,
        reason,
        performed_by
    ):
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
                f"Remaining refundable amount: ₹{remaining}"
            )


        refund = ContributionRefund(
            contribution_id=contribution.id,
            amount=amount,
            reason=reason,
            status="refunded"
        )

        db.add(refund)
        db.flush()

        db.add(AuditLog(
            society_id=contribution.society_id,
            entity_type="contribution_refund",
            entity_id=refund.id,
            action="REFUND_CONTRIBUTION",
            reason=reason,
            performed_by=performed_by
        ))

        db.commit()
        
